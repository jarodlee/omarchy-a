"""Build the static account-enabled site from a pinned upstream checkout.

Usage: python3 build-taxonomy-accounts.py UPSTREAM_CHECKOUT NEW_OUTPUT_DIRECTORY
No downloads, upstream build scripts, model credentials or real user data.
"""
from pathlib import Path
import re
import shutil
import subprocess
import sys

source=Path(sys.argv[1]).resolve();destination=Path(sys.argv[2]).resolve()
revision=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
assert revision=='276b88c4ff57d6bb9da986c68d7058a0cbc5225f', 'Review another upstream revision before building'
assert not destination.exists(), 'Do not overwrite an existing deployment or user files'
destination.mkdir(parents=True)
for name in ['index.html','sw.js','manifest.webmanifest','LICENSE']:shutil.copy2(source/name,destination/name)
for name in ['assets','explore','diagnose','children']:shutil.copytree(source/name,destination/name)
(destination/'data').mkdir()
for name in ['topics.json','dependencies.json','cn-curriculum-standards.json','questions.json','id-aliases.json']:
    shutil.copy2(source/'data'/name,destination/'data'/name)
extension=Path(__file__).parent
for name in ['server-sync.js','server-sync.css','account.js']:shutil.copy2(extension/name,destination/'assets'/name)
shutil.copy2(extension/'account.html',destination/'account.html')
(destination/'assets/stats-config.js').write_text("window.CNM_STATS = {cloudflareToken: '', endpoint: '', onEvent: null};\n")
p=destination/'diagnose/share.js';p.write_text(p.read_text().replace('https://math.pansgo.com/?from=share','https://math.ghtxx.cn/?from=share'))
for p in destination.rglob('*.html'):
    if p.name=='account.html':continue
    s=re.sub(r'<script\s+src="([^"]+)"([^>]*)>',r'<script type="application/x-cnm-gated" data-src="\1"\2>',p.read_text())
    s=s.replace('</head>','<link rel="stylesheet" href="/assets/server-sync.css"></head>')
    s=re.sub(r'<body([^>]*)>',r'<body\1 data-sync-loading><div id="cnm-sync-overlay" role="status">正在载入服务器记录…</div>',s,count=1)
    p.write_text(s.replace('</body>','<script src="/assets/server-sync.js"></script></body>'))
p=destination/'sw.js';s=p.read_text().replace("var VERSION = 'v6';","var VERSION = 'ghtxx-accounts-v1';")
s=s.replace('var SHELL = [',"var SHELL = [\n  'account.html', 'assets/server-sync.js', 'assets/server-sync.css', 'assets/account.js',")
s=s.replace("if (url.pathname === '/sw.js') return;","if (url.pathname === '/sw.js' || url.pathname.indexOf('/api/') === 0) return;")
p.write_text(s)
p=destination/'assets/children.js';s=p.read_text().replace('all[childId] = keepImportedHistory ? arr : arr.slice(0, MAX_RECORDS);','all[childId] = arr;').replace('all[toId] = keepImportedHistory ? to : to.slice(0, MAX_RECORDS);','all[toId] = to;');p.write_text(s)
replacements={
 '档案和诊断记录保存在当前浏览器中，不上传，也没有账号。清除浏览器数据或更换设备前，请先导出备份，再在新浏览器中导入。':'档案和诊断记录按账号保存在服务器。换设备后登录同一账号即可载入；请留意页面顶部的同步状态，也可导出额外备份。',
 '导出所有孩子的资料和各学科诊断记录，在其他浏览器中导入即可继续查看。':'可额外导出所有孩子的资料和诊断记录。日常换设备只需登录同一账号；导入功能用于合并旧备份。',
 '汇总本机诊断里的薄弱 / 不稳知识点，按章查看并一键再测。数据只留在这台浏览器，不会上传。':'汇总当前账号的薄弱和不稳知识点，按章查看并一键再测。记录会同步到服务器。',
 '数据只留在本机。':'记录按当前账号同步到服务器。',
 '根据本机诊断记录汇总，数据只留在这台浏览器。':'根据当前账号的诊断记录汇总，并同步到服务器。',
 '个。进度和出过的题只保存在这台浏览器里。':'个。进度和出过的题会按账号同步到服务器。'
}
for p in destination.rglob('*'):
    if p.suffix not in ('.html','.js') or 'vendor' in p.parts:continue
    s=p.read_text()
    for old,new in replacements.items():s=s.replace(old,new)
    p.write_text(s)
(destination/'DEPLOYMENT.txt').write_text(f'Source: https://github.com/xiaoyang111222/cn-math-taxonomy\nCommit: {revision}\nLicense: CC BY-NC 4.0; vendor licenses retained.\nLocal changes: account-gated server sync, privacy text, history retention, analytics disabled, self-hosted share URL and cache version.\n')
print(destination)
