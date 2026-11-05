set -euo pipefail
python3 - <<'PY'
import json,time,subprocess
from pathlib import Path
def read():
 d=dict(line.split('=',1) for line in subprocess.check_output(['systemctl','show','ipad-battery-monitor','-p','MainPID','-p','MemoryCurrent','-p','CPUUsageNSec'],text=True).splitlines())
 pid=int(d['MainPID']);rss=next(int(x.split()[1])*1024 for x in Path(f'/proc/{pid}/status').read_text().splitlines() if x.startswith('VmRSS:'))
 return {'pid':pid,'memory_cgroup_bytes':int(d['MemoryCurrent']),'rss_bytes':rss,'cpu_ns':int(d['CPUUsageNSec'])}
before=read();start=time.monotonic();time.sleep(60);after=read();elapsed=time.monotonic()-start
assert before['pid']==after['pid'],'Service restarted during measurement'
print(json.dumps({'elapsed_seconds':elapsed,'cpu_seconds':(after['cpu_ns']-before['cpu_ns'])/1e9,'cpu_percent_one_core':(after['cpu_ns']-before['cpu_ns'])/1e9/elapsed*100,'before':before,'after':after}))
PY
