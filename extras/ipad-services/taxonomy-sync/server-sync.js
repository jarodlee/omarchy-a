/* Account-scoped, optimistic server sync. Learning input never goes to analytics. */
(function () {
 'use strict';
 const SET=Storage.prototype.setItem, REMOVE=Storage.prototype.removeItem;
 const local=window.localStorage;
 let keys=[],user=null,revision=0,dirty=false,busy=false,conflict=false,timer,bar,status;
 const accountPage=location.pathname==='/account.html';
 const pendingKey=id=>'cnmSync.pending.'+id;
 const rawSet=(k,v)=>SET.call(local,k,v),rawDel=k=>REMOVE.call(local,k);
 function node(tag,text){const e=document.createElement(tag);if(text)e.textContent=text;return e;}
 function button(label,fn){const b=node('button',label);b.type='button';b.onclick=fn;return b;}
 async function api(path,body={},method='POST'){
  const r=await fetch(path,{method,credentials:'same-origin',cache:'no-store',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const d=await r.json();if(!r.ok)throw Object.assign(new Error(d.error||'服务器暂时不可用。'),{status:r.status});return d;
 }
 function snapshot(){const d={};for(const k of keys){const v=local.getItem(k);if(v!==null)d[k]=v;}return d;}
 function replace(data){for(const k of keys){if(Object.hasOwn(data,k))rawSet(k,data[k]);else rawDel(k);}}
 function download(data,name){const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=node('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
 function message(t){if(status)status.textContent=t;}
 function stash(){rawSet(pendingKey(user.id),JSON.stringify({revision,data:snapshot()}));}
 function changed(){
  if(!user)return;
  dirty=true;
  try{stash();message(conflict?'存在同步冲突，本机修改已保留。':'有本机修改，等待同步…');}
  catch(e){conflict=true;message('本机存储已满，请立即导出本机记录，暂勿退出。');return;}
  clearTimeout(timer);timer=setTimeout(flush,700);
 }
 async function flush(){
  if(!dirty||busy||conflict)return;
  busy=true;
  const data=snapshot(),sent=JSON.stringify(data),base=revision;
  try{
   const d=await api('/api/state',{revision:base,data},'PUT');revision=d.revision;
   rawSet('cnmSync.revision',String(revision));
   if(JSON.stringify(snapshot())===sent){dirty=false;rawDel(pendingKey(user.id));message('已保存到服务器');}
   else{stash();message('正在同步后续修改…');}
  }catch(e){
   if(e.status===409){conflict=true;message('另一设备已更新：本机修改已保留，请导出后载入服务器版本。');}
   else if(e.status===401){conflict=true;message('登录已过期，本机修改已保留。请到账号页重新登录。');}
   else message('暂未同步：'+e.message+' 本机修改已保留。');
  }finally{busy=false;if(dirty&&!conflict)timer=setTimeout(flush,5000);}
 }
 function safeNext(){const p=new URLSearchParams(location.search).get('next');return p&&p.startsWith('/')&&!p.startsWith('//')?p:'/';}
 async function loadServer(){
  if((dirty||conflict)&&!confirm('载入前建议先导出本机记录。确认载入服务器版本？本机待同步副本仍会保留。'))return;
  const d=await api('/api/state/read');
  if(dirty||conflict)rawSet('cnmSync.recovery.'+user.id+'.'+Date.now(),JSON.stringify({revision,data:snapshot()}));
  replace(d.data);rawDel(pendingKey(user.id));rawSet('cnmSync.revision',String(d.revision));
  dirty=false;conflict=false;location.reload();
 }
 function exportLocal(){
  const profiles=JSON.parse(local.getItem('cnmChildren.v1')||'null');
  const records=JSON.parse(local.getItem('cnmChildren.records.v1')||'{}');
  if(profiles&&profiles.children?.length)download({format:'cn-math-taxonomy.children',version:1,exportedAt:new Date().toISOString(),profiles,records},'学习档案备份.json');
  else download({format:'cnm-server-sync',version:1,data:snapshot()},'本机学习记录.json');
 }
 async function logout(){
  await flush();
  if(dirty||busy||conflict){message('还有未同步的修改，请先导出并处理冲突，再退出账号。');return;}
  await api('/api/auth/logout');replace({});rawDel('cnmSync.owner');rawDel('cnmSync.revision');
  user=null;location.replace('/account.html');
 }
 function showBar(){
  bar=node('aside');bar.id='cnm-sync-bar';bar.setAttribute('aria-label','账号与同步');
  const name=node('a',user.username+' · '+(user.admin?'管理员':'我的账号'));name.href='/account.html';bar.append(name);
  status=node('span');status.setAttribute('role','status');status.setAttribute('aria-live','polite');bar.append(status);
  bar.append(button('同步',()=>{flush().catch(e=>message(e.message));}),button('载入服务器版本',()=>loadServer().catch(e=>message(e.message))),button('导出本机记录',exportLocal),button('退出',()=>logout().catch(e=>message(e.message))));
  if(local.getItem('cnmSync.legacy')){
   bar.append(button('导入此设备旧记录',async()=>{
    try{
     const d=await api('/api/state/read');
     const populated=Object.values(d.data).some(v=>{try{const a=JSON.parse(v);return a&&((a.children&&a.children.length)||(Array.isArray(a)&&a.length)||Object.keys(a).some(k=>!['v','current','children'].includes(k)));}catch(e){return true;}});
     if(populated){
      const old=JSON.parse(local.getItem('cnmSync.legacy'));const profiles=JSON.parse(old['cnmChildren.v1']||'null');
      if(profiles?.children?.length)download({format:'cn-math-taxonomy.children',version:1,exportedAt:new Date().toISOString(),profiles,records:JSON.parse(old['cnmChildren.records.v1']||'{}')},'旧设备档案备份.json');
      else download({format:'cnm-server-sync',version:1,data:old},'旧设备学习记录.json');
      alert('服务器已有记录，未覆盖。已导出旧记录；孩子档案可在“档案”页通过原有导入功能合并。');return;
     }
     if(dirty||busy||conflict){alert('请先完成同步并载入服务器版本，再导入旧记录。');return;}
     if(!confirm('将这台设备原有的学习记录导入当前账号？只应导入你有权管理的记录。'))return;
     const old=JSON.parse(local.getItem('cnmSync.legacy'));await api('/api/state',{revision:d.revision,data:old},'PUT');location.reload();
    }catch(e){message(e.message);}
   }));
  }
  document.body.prepend(bar);
 }
 async function scripts(){
  for(const old of document.querySelectorAll('script[type="application/x-cnm-gated"]')){
   await new Promise((resolve,reject)=>{const s=document.createElement('script');s.src=old.getAttribute('data-src');s.async=false;s.onload=resolve;s.onerror=()=>reject(Error('页面资源加载失败，请刷新重试。'));old.replaceWith(s);});
  }
 }
 async function hydrate(me){
  keys=me.keys;user=me.user;
  const owner=local.getItem('cnmSync.owner');
  if(!owner){const old=snapshot();if(Object.keys(old).length&&!local.getItem('cnmSync.legacy'))rawSet('cnmSync.legacy',JSON.stringify(old));}
  const d=await api('/api/state/read');
  let pending=null;try{pending=JSON.parse(local.getItem(pendingKey(user.id))||'null');}catch(e){throw Error('本机待同步副本格式异常，请保留此浏览器数据并联系管理员。');}
  if(pending){revision=pending.revision;replace(pending.data);dirty=true;conflict=revision!==d.revision;}
  else{revision=d.revision;replace(d.data);}
  rawSet('cnmSync.owner',user.id);rawSet('cnmSync.revision',String(revision));
  Storage.prototype.setItem=function(k,v){const result=SET.call(this,k,v);if(this===local&&keys.includes(String(k)))changed();return result;};
  Storage.prototype.removeItem=function(k){const result=REMOVE.call(this,k);if(this===local&&keys.includes(String(k)))changed();return result;};
  showBar();message(conflict?'待同步副本与另一设备冲突，请先导出本机记录。':dirty?'正在恢复待同步修改…':'已载入服务器记录');
  if(dirty&&!conflict)await flush();
  setInterval(async()=>{
   if(document.hidden||busy)return;
   if(dirty){if(!conflict)await flush();return;}
   try{const remote=await api('/api/state/version');if(remote.revision!==revision)message('另一设备有新记录，点击“载入服务器版本”查看。');}catch(e){message('服务器暂不可达，本机操作稍后同步。');}
  },20000);
  window.addEventListener('online',()=>{if(!conflict)flush();});
  window.addEventListener('beforeunload',e=>{if(dirty||busy){e.preventDefault();e.returnValue='';}});
  window.addEventListener('storage',e=>{if(e.key==='cnmSync.owner'&&e.newValue!==user?.id){conflict=true;location.reload();}else if(keys.includes(e.key)){conflict=true;message('另一标签页已修改本机记录，请刷新本页后继续。');}});
 }
 async function start(){
  const me=await api('/api/me');window.CnmAccountContext=me;
  if(!me.user&&!accountPage){location.replace('/account.html?next='+encodeURIComponent(location.pathname+location.search+location.hash));return;}
  if(me.user){
   if(!navigator.locks)throw Error('当前浏览器不支持安全的多标签页同步，请更新浏览器后重试。');
   const locked=await new Promise((resolve,reject)=>{
    navigator.locks.request('cnm-server-sync-editor',{ifAvailable:true},async lock=>{resolve(!!lock);if(lock)await new Promise(()=>{});}).catch(reject);
   });
   if(!locked)throw Error('学习网站已在另一个标签页打开。请在该页操作，或关闭它后重试。');
   await hydrate(me);
  }
  window.CnmSync={api,logout,flush,safeNext,exportLocal};
  await scripts();document.body.removeAttribute('data-sync-loading');document.getElementById('cnm-sync-overlay')?.remove();
  if('serviceWorker' in navigator)navigator.serviceWorker.register('/sw.js').catch(()=>{});
 }
 start().catch(e=>{
  const overlay=document.getElementById('cnm-sync-overlay');if(overlay){overlay.textContent='无法载入账号记录：'+e.message+' 本机记录没有清除。';overlay.append(button('重试',()=>location.reload()));}
 });
})();
