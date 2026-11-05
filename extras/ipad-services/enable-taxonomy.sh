set -euo pipefail
systemd-analyze verify /etc/systemd/system/cn-math-taxonomy.service
systemctl daemon-reload
systemctl enable --now cn-math-taxonomy.service
python3 - <<'PY'
import json,time,urllib.request
from pathlib import Path
for attempt in range(10):
 try:
  with urllib.request.urlopen('http://127.0.0.1:3002/data/topics.json',timeout=3) as f: data=json.load(f)
  print('LOCAL_TAXONOMY_DATA_OK',type(data).__name__)
  break
 except OSError:time.sleep(.5)
else:raise RuntimeError('Static server not ready')
p=Path('/etc/cloudflared-ctb/config.yml')
s=p.read_text()
if 'hostname: math.ghtxx.cn' not in s:
 marker='  - service: http_status:404'
 assert s.count(marker)==1
 b=p.with_name('config.before-taxonomy.yml')
 if not b.exists():
  b.write_bytes(p.read_bytes());b.chmod(0o600)
 p.write_text(s.replace(marker,'  - hostname: math.ghtxx.cn\n    service: http://127.0.0.1:3002\n'+marker))
PY
/opt/cloudflared/2026.10.7/cloudflared --config /etc/cloudflared-ctb/config.yml tunnel ingress validate
systemctl restart cloudflared-ctb.service
echo TAXONOMY_TUNNEL_CONFIGURED
