#!/usr/bin/env python3
"""LAN-only service index: public links and fixed loopback health checks."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import threading
import time
import urllib.request
from urllib.parse import urlsplit,parse_qs

ROOT=Path(__file__).parent
TARGETS={'notebook':'http://127.0.0.1:3000/api/health',
         'taxonomy':'http://127.0.0.1:3002/api/health',
         'battery':'http://127.0.0.1:3001/health'}
lock=threading.Lock()
cached={'at':0,'services':{}}
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))

def status():
    with lock:
        if time.monotonic()-cached['at']<10:return cached['services']
        result={}
        for key,url in TARGETS.items():
            try:
                with opener.open(url,timeout=1) as r:ok=r.status==200
            except OSError:ok=False
            result[key]={'ok':ok}
        cached.update(at=time.monotonic(),services=result)
        return result

class Server(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,*args):
        self.slots=threading.BoundedSemaphore(8)
        super().__init__(*args)
    def process_request(self,request,address):
        if not self.slots.acquire(blocking=False):request.close();return
        try:super().process_request(request,address)
        except BaseException:self.slots.release();raise
    def process_request_thread(self,request,address):
        try:super().process_request_thread(request,address)
        finally:self.slots.release()

class Handler(BaseHTTPRequestHandler):
    def setup(self):super().setup();self.connection.settimeout(10)
    def log_message(self,*args):pass
    def do_HEAD(self):self.do_GET()
    def do_GET(self):
        parsed=urlsplit(self.path);path=parsed.path
        if path in ['/','/index.html']:
            data=(ROOT/'index.html').read_bytes();kind='text/html; charset=utf-8';code=200
        elif path=='/health':
            data=b'{"ok":true,"service":"omarchy-home"}';kind='application/json';code=200
        elif path=='/api/status':
            data=json.dumps({'services':status()}).encode();kind='application/json';code=200
        elif path in ['/battery','/battery/','/api/battery']:
            target='http://127.0.0.1:3001/'
            kind='text/html; charset=utf-8'
            if path=='/api/battery':
                try:
                    q=parse_qs(parsed.query,max_num_fields=2)
                    hours=int(q.get('hours',['6'])[0])
                    if hours not in (1,6,24) or set(q)-{'hours'}:raise ValueError()
                except (ValueError,IndexError):
                    self.send_error(400);return
                target+='api/battery?hours='+str(hours);kind='application/json'
            try:
                with opener.open(target,timeout=3) as r:data=r.read(2*1024*1024+1)
                if len(data)>2*1024*1024:raise OSError('Battery response too large')
                code=200
            except OSError:data=b'{"error":"battery monitor unavailable"}';kind='application/json';code=503
        else:data=b'Not found';kind='text/plain';code=404
        self.send_response(code);self.send_header('Content-Type',kind)
        self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff');self.send_header('X-Frame-Options','DENY')
        self.send_header('Referrer-Policy','same-origin');self.end_headers()
        if self.command!='HEAD':self.wfile.write(data)

if __name__=='__main__':Server(('0.0.0.0',80),Handler).serve_forever()
