(function(){
 'use strict';
 const context=window.CnmAccountContext,api=window.CnmSync.api,main=document.getElementById('account-content'),status=document.getElementById('account-status');
 function el(tag,text){const n=document.createElement(tag);if(text)n.textContent=text;return n;}
 function action(text,fn){const b=el('button',text);b.type='button';b.onclick=()=>Promise.resolve(fn()).catch(e=>status.textContent=e.message);return b;}
 function input(form,name,title,type,autocomplete){const label=el('label',title),field=el('input');field.name=name;field.type=type;field.required=true;field.autocomplete=autocomplete||'off';if(name==='username'){field.minLength=3;field.maxLength=80;field.pattern='[a-z0-9_.@+\\-]{3,80}';}if(name==='password'){field.minLength=10;field.maxLength=256;}label.append(field);form.append(label);return field;}
 function authForm(mode){
  main.replaceChildren();const form=el('form');
  main.append(el('h2',mode==='setup'?'设置第一个管理员':mode==='register'?'使用邀请码注册':'登录'));
  input(form,'username','账号（小写字母、数字或邮箱）','text','username');
  input(form,'password','密码（至少 10 个字符）','password',mode==='login'?'current-password':'new-password');
  if(mode==='register')input(form,'invite','管理员提供的一次性邀请码','text');
  const submit=el('button',mode==='login'?'登录':mode==='setup'?'创建管理员并登录':'注册并登录');submit.type='submit';form.append(submit);main.append(form);
  form.onsubmit=async e=>{e.preventDefault();submit.disabled=true;status.textContent='正在提交…';
   try{const d=Object.fromEntries(new FormData(form));await api('/api/auth/'+mode,d);location.replace(window.CnmSync.safeNext());}
   catch(err){status.textContent=err.message;submit.disabled=false;}
  };
  if(mode==='login')main.append(action('有邀请码？注册账号',()=>authForm('register')));
  if(mode==='register')main.append(action('已有账号，返回登录',()=>authForm('login')));
 }
 if(context.user){
  main.append(el('p','当前账号：'+context.user.username),action('继续学习',()=>location.assign('/children/')));
  if(context.user.admin){
   main.append(el('h2','邀请其他家庭或学生'),el('p','每个邀请码只能注册一个账号，七天内有效。请私下交给使用者。'));
   const output=el('textarea');output.readOnly=true;output.setAttribute('aria-label','新生成的一次性邀请码');
   main.append(action('生成一次性邀请码',async()=>{const r=await api('/api/invites');output.value=r.invite;status.textContent='邀请码已生成，七天内有效。';}),output);
  }
  main.append(action('退出当前账号',()=>window.CnmSync.logout()));
 }else if(context.setupRequired){
  if(context.canSetup)authForm('setup');
  else main.append(el('p','管理员尚未完成初始化。请等待管理员设置账号后，向其索取邀请码。'));
 }else authForm('login');
})();
