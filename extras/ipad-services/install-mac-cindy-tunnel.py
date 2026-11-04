"""Create a dedicated per-user Cloudflare connector after creating its tunnel.

Uses only that tunnel's local credentials, never account certs in source control.
Run on the Mac hosting Cindy. Existing files are deliberately not overwritten.
"""
from pathlib import Path
import os
import plistlib
import subprocess

home = Path.home()
directory = home / '.cloudflared'
tunnel_id = 'c473f2f5-06d2-445e-86a1-632f0bacf158'
credentials = directory / (tunnel_id + '.json')
assert credentials.is_file() and not credentials.is_symlink()
assert credentials.stat().st_uid == os.getuid()
credentials.chmod(0o600)
config = directory / 'cindy-ctb-api.yml'
agent = home / 'Library/LaunchAgents/app.cindy.ctb-api-tunnel.plist'
assert not config.exists() and not agent.exists()
config.write_text(f'''tunnel: {tunnel_id}
credentials-file: {credentials}
metrics: 127.0.0.1:37311
protocol: http2
edge-ip-version: "4"
ingress:
  - hostname: cindy-ctb.ghtxx.cn
    service: http://127.0.0.1:37309
  - service: http_status:404
''')
config.chmod(0o600)
binary = '/opt/homebrew/bin/cloudflared'
subprocess.run([binary, '--config', str(config), 'tunnel', 'ingress', 'validate'], check=True)
agent.parent.mkdir(exist_ok=True)
agent.write_bytes(plistlib.dumps({
    'Label': 'app.cindy.ctb-api-tunnel',
    'ProgramArguments': [binary, '--no-autoupdate', '--config', str(config), 'tunnel', 'run'],
    'RunAtLoad': True, 'KeepAlive': True, 'ThrottleInterval': 15,
    'StandardOutPath': str(directory / 'cindy-ctb-api.log'),
    'StandardErrorPath': str(directory / 'cindy-ctb-api.log'),
}))
agent.chmod(0o600)
subprocess.run(['launchctl', 'bootstrap', f'gui/{os.getuid()}', str(agent)], check=True)
