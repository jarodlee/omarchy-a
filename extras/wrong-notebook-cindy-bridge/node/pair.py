"""Run on the owner-authorized iPad through its existing pinned SSH identity."""
from pathlib import Path
import json
import os
import pwd
import subprocess
import sys
import tempfile
import time
import urllib.request

assert os.geteuid() == 0
assert b'apple,j71b\0' in Path('/proc/device-tree/compatible').read_bytes()
incoming = json.load(sys.stdin)
assert incoming['port'] == 37309 and len(incoming['key']) >= 32
p = Path('/var/lib/wrong-notebook/config/app-config.json')
assert not p.is_symlink()
original = p.read_bytes()
config = json.loads(original)
backup = Path('/var/lib/omarchy-maintenance/wrong-notebook-before-cindy.json')
assert not backup.is_symlink()
if not backup.exists():
    backup.write_bytes(original)
    backup.chmod(0o600)
instances = config.setdefault('openai', {}).setdefault('instances', [])
item = {'id': 'cindy-local-bridge', 'name': 'MacMini Cindy', 'apiKey': incoming['key'],
        'baseUrl': 'http://127.0.0.1:37309/v1', 'model': 'cindy'}
index = next((i for i, value in enumerate(instances) if value.get('id') == item['id']), None)
if index is None:
    assert len(instances) < 10
    instances.append(item)
else:
    instances[index] = item
config['openai']['activeInstanceId'] = item['id']
config['aiProvider'] = 'openai'
config['aiConcurrencyLimit'] = 1
config.setdefault('timeouts', {})['analyze'] = 300000
account = pwd.getpwnam('wrong-notebook')


def replace(data):
    with tempfile.NamedTemporaryFile(dir=p.parent, delete=False) as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
        temporary = Path(f.name)
    os.chown(temporary, account.pw_uid, account.pw_gid)
    temporary.chmod(0o600)
    temporary.replace(p)


replace((json.dumps(config, ensure_ascii=False, indent=2) + '\n').encode())
try:
    subprocess.run(['systemctl', 'restart', 'wrong-notebook.service'], check=True, timeout=15)
    for _ in range(15):
        try:
            with urllib.request.urlopen('http://127.0.0.1:3000/api/health', timeout=2) as response:
                assert response.status == 200
            break
        except Exception:
            time.sleep(.5)
    else:
        raise RuntimeError('Notebook readiness timeout')
except BaseException:
    replace(original)
    subprocess.run(['systemctl', 'restart', 'wrong-notebook.service'], timeout=15)
    raise
print('CINDY_PROVIDER_PAIRED')
