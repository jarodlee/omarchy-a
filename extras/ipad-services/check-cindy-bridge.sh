set -euo pipefail
python3 - <<'PY'
import json,urllib.request
from pathlib import Path
d=json.loads(Path('/var/lib/wrong-notebook/config/app-config.json').read_text())
i=next(x for x in d['openai']['instances'] if x['id']==d['openai']['activeInstanceId'])
assert i['id']=='cindy-local-bridge'
body={'model':i['model'],'messages':[{'role':'user','content':'Calculate 19 + 23. Reply with only the integer.'}]}
r=urllib.request.Request(i['baseUrl']+'/chat/completions',data=json.dumps(body).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+i['apiKey']})
with urllib.request.urlopen(r,timeout=180) as f: answer=json.load(f)
assert answer['choices'][0]['message']['content'].strip()=='42'
print('IPAD_TO_CINDY_END_TO_END_OK')
for port,path in [(3000,'/api/health'),(3001,'/health')]:
 with urllib.request.urlopen('http://127.0.0.1:'+str(port)+path,timeout=5) as f: print('HEALTH',port,f.status)
PY
