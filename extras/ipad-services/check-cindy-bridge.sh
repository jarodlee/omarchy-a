set -euo pipefail
python3 - <<'PY'
import json,urllib.request
from pathlib import Path
d=json.loads(Path('/var/lib/wrong-notebook/config/app-config.json').read_text())
i=next(x for x in d['openai']['instances'] if x['id']==d['openai']['activeInstanceId'])
assert i['id']=='cindy-local-bridge'
assert i['baseUrl']=='https://cindy-ctb.ghtxx.cn/v1'
print('PROVIDER_USES_PUBLIC_HTTPS')
body={'model':i['model'],'messages':[{'role':'user','content':'Calculate 19 + 23. Reply with only the integer.'}]}
r=urllib.request.Request(i['baseUrl']+'/chat/completions',data=json.dumps(body).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+i['apiKey']})
with urllib.request.urlopen(r,timeout=180) as f: answer=json.load(f)
assert answer['choices'][0]['message']['content'].strip()=='42'
print('IPAD_TO_CINDY_END_TO_END_OK')
fixture=Path('/run/cindy-bridge-question.png')
if fixture.exists():
 import base64
 image=base64.b64encode(fixture.read_bytes()).decode()
 body={'model':i['model'],'messages':[{'role':'user','content':[{'type':'text','text':'Solve the arithmetic in the attached image. Reply with only the integer.'},{'type':'image_url','image_url':{'url':'data:image/png;base64,'+image}}]}]}
 r=urllib.request.Request(i['baseUrl']+'/chat/completions',data=json.dumps(body).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+i['apiKey']})
 with urllib.request.urlopen(r,timeout=180) as f: answer=json.load(f)
 assert answer['choices'][0]['message']['content'].strip()=='745'
 fixture.unlink()
 print('IPAD_PUBLIC_HTTPS_IMAGE_OK')
for port,path in [(3000,'/api/health'),(3001,'/health')]:
 with urllib.request.urlopen('http://127.0.0.1:'+str(port)+path,timeout=5) as f: print('HEALTH',port,f.status)
PY
