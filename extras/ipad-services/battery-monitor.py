#!/usr/bin/env python3
"""Read-only battery telemetry with a bounded seven-day SQLite history."""
import json
import logging
import os
from pathlib import Path
import signal
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).parent
POWER = Path(os.environ.get('BATTERY_POWER_PATH', '/sys/class/power_supply'))
DATABASE = Path(os.environ.get('BATTERY_DATABASE', '/var/lib/ipad-battery-monitor/history.sqlite3'))
STOP = threading.Event()
FIELDS = {'capacity': ('battery', 'capacity'), 'status': ('battery', 'status'),
          'current_uA': ('battery', 'current_now'), 'voltage_uV': ('battery', 'voltage_now'),
          'temperature_deciC': ('battery', 'temp'), 'health': ('battery', 'health'),
          'online': ('lightning', 'online'), 'usb_type': ('lightning', 'usb_type'),
          'input_limit_uA': ('lightning', 'input_current_limit')}
TEXT = {'status', 'health', 'usb_type'}


def snapshot():
    result = {'timestamp': int(time.time())}
    for key, (supply, name) in FIELDS.items():
        try:
            value = (POWER / supply / name).read_text().strip()
            result[key] = value[:100] if key in TEXT else int(value)
        except (OSError, ValueError):
            result[key] = None
    return result


def connection():
    return sqlite3.connect(DATABASE, timeout=2)


def initialize():
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    with connection() as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('CREATE TABLE IF NOT EXISTS samples (timestamp INTEGER PRIMARY KEY, capacity INTEGER, current_uA INTEGER, temperature_deciC INTEGER, input_limit_uA INTEGER, status TEXT)')


def record(row):
    with connection() as db:
        db.execute('INSERT OR REPLACE INTO samples VALUES (?,?,?,?,?,?)',
                   tuple(row[k] for k in ('timestamp', 'capacity', 'current_uA', 'temperature_deciC', 'input_limit_uA', 'status')))
        db.execute('DELETE FROM samples WHERE timestamp < ?', (row['timestamp'] - 7 * 86400,))


def history(hours):
    with connection() as db:
        db.row_factory = sqlite3.Row
        rows = db.execute('SELECT * FROM samples WHERE timestamp >= ? ORDER BY timestamp',
                          (int(time.time()) - hours * 3600,)).fetchall()
    return [dict(row) for row in rows]


def sample_loop():
    while not STOP.is_set():
        try:
            record(snapshot())
        except (OSError, sqlite3.Error):
            logging.exception('Unable to save battery sample')
        STOP.wait(60)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def respond(self, status, body, content_type):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlsplit(self.path)
        if parsed.path == '/':
            return self.respond(200, (ROOT / 'index.html').read_bytes(), 'text/html; charset=utf-8')
        if parsed.path == '/favicon.ico':
            return self.respond(204, b'', 'image/x-icon')
        if parsed.path == '/health':
            return self.respond(200, b'{"ok":true}', 'application/json')
        if parsed.path != '/api/battery':
            return self.respond(404, b'Not found', 'text/plain')
        try:
            hours = int(parse_qs(parsed.query).get('hours', ['6'])[0])
            if hours not in (1, 6, 24):
                raise ValueError()
        except (ValueError, IndexError):
            return self.respond(400, b'Invalid hours', 'text/plain')
        try:
            data = {'current': snapshot(), 'history': history(hours), 'sample_interval_seconds': 60,
                    'retention_days': 7, 'timezone': 'browser-local', 'read_only': True}
            self.respond(200, json.dumps(data, separators=(',', ':')).encode(), 'application/json; charset=utf-8')
        except (OSError, sqlite3.Error):
            self.respond(503, b'{"error":"telemetry unavailable"}', 'application/json')


class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 16

    def get_request(self):
        sock, addr = super().get_request()
        sock.settimeout(5)
        return sock, addr


def main():
    os.umask(0o077)
    initialize()
    worker = threading.Thread(target=sample_loop, daemon=True)
    worker.start()
    server = Server((os.environ.get('BATTERY_BIND', '0.0.0.0'), int(os.environ.get('BATTERY_PORT', '3001'))), Handler)
    server.timeout = 1
    def stop(*_args):
        STOP.set()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    logging.warning('Read-only battery monitor listening on port %s', server.server_port)
    try:
        while not STOP.is_set():
            server.handle_request()
    finally:
        server.server_close()
        worker.join(timeout=3)


if __name__ == '__main__':
    main()
