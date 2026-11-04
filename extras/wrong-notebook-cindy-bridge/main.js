const active = new Map();
let capabilities, last;
async function node(method,params={}) {
 const r=await cindy.node.request({method,params,timeoutMs:60000});
 if(!r.ok)throw new Error(r.message||'Node bridge request failed');
 return r.result;
}
async function caps(){return capabilities||(capabilities=await cindy.tasks.capabilities());}
function pause(ms){return new Promise(r=>setTimeout(r,ms));}
function textOf(m){
 if(typeof m.content==='number'||typeof m.content==='boolean')return String(m.content);
 if(typeof m.text==='string')return m.text;
 if(typeof m.content==='string')return m.content;
 if(Array.isArray(m.content))return m.content.filter(c=>c.type==='text').map(c=>c.text||'').join('\n');
 return '';
}
async function finalText(taskId,id){
 for(let attempt=0;attempt<8;attempt++){
  let after;
  for(let n=0;n<10;n++){
   const page=await cindy.tasks.readMessages({taskId,limit:50,...(after?{after}:{})});
   const m=(page.messages||page.items||[]).find(m=>(m.id||m.messageId)===id);
   if(m)return textOf(m);
   after=page.nextCursor;if(!after)break;
  }
  await pause(750);
 }
 throw new Error('\u6700\u7ec8\u56de\u590d\u6682\u4e0d\u53ef\u8bfb\u53d6\uff0c\u6ca1\u6709\u91cd\u65b0\u6d3e\u53d1\u6a21\u578b\u8bf7\u6c42\u3002');
}
async function execute(id){
 if(active.has(id))return;active.set(id,{});
 try{
  const support=await caps(),job=await node('bridge/get_job',{id});
  if(job.images.length&&!support.messageAttachments?.kinds?.includes('image'))throw new Error('\u5f53\u524d Cindy \u672a\u58f0\u660e\u56fe\u7247\u9644\u4ef6\u652f\u6301\uff0c\u672a\u4e22\u56fe\u6539\u53d1\u6587\u5b57\u3002');
  const attachments=[];
  for(const image of job.images){
   let base64='';
   for(let part=0;part<image.parts;part++)base64+=(await node('bridge/image_chunk',{id,image:image.index,part})).data;
   attachments.push({base64,name:image.name});
  }
  let receipt=job.receipt||{};
  if(!receipt.taskId){
   const selected=(await node('bridge/status')).route;
   const made=await cindy.tasks.create({requestKey:'wn-create-'+id,title:'\u9519\u9898\u672c\u63a8\u7406 '+id.slice(0,8),isolatedWorkspace:true,permissionMode:'ask',hidden:support.hiddenTasks===true,...(selected?{route:selected}:{})});
   receipt={taskId:made.taskId,revision:made.revision};
   await node('bridge/save_receipt',{id,receipt});
  }
  active.set(id,receipt);
  if(!receipt.runId){
   const sent=await cindy.tasks.send({taskId:receipt.taskId,expectedRevision:receipt.revision,requestKey:'wn-send-'+id,text:job.prompt,...(attachments.length?{attachments}:{})});
   receipt={...receipt,runId:sent.runId};await node('bridge/save_receipt',{id,receipt});active.set(id,receipt);
  }
  if(!receipt.taskId||!receipt.runId)throw new Error('\u4efb\u52a1\u56de\u6267\u4e0d\u5b8c\u6574\uff0c\u672a\u91cd\u65b0\u6d3e\u53d1\u3002');
  const start=Date.now();let run;
  while(Date.now()-start<240000){
   const raw=await cindy.tasks.getRun({runId:receipt.runId});run=raw.run||raw;
   last={id,...receipt,state:run.status||run.state,outcome:run.outcome,outputMessageId:run.outputMessageId,acceptedConfig:run.acceptedConfig,runFields:Object.keys(run)};
   const state=run.status||run.state||run.outcome;
   if(run.outputMessageId&&['completed','done','succeeded'].includes(state))break;
   if(['failed','cancelled','interrupted'].includes(state))throw new Error('Cindy \u4efb\u52a1\u5df2\u7ec8\u6b62\uff1a'+state);
   await pause(1500);
  }
  if(!run?.outputMessageId)throw new Error('\u7b49\u5f85\u6700\u7ec8\u56de\u6267\u8d85\u65f6\uff0c\u8bf7\u67e5\u770b\u540e\u53f0\u4efb\u52a1\uff0c\u6ca1\u6709\u91cd\u65b0\u6d3e\u53d1\u3002');
  let text=await finalText(receipt.taskId,run.outputMessageId);
  if(!text.trim())throw new Error('\u6a21\u578b\u6700\u7ec8\u56de\u590d\u4e3a\u7a7a\u3002');
  if(job.expectJson){text=text.trim().replace(/^```(?:json)?\s*/i,'').replace(/\s*```$/,'');JSON.parse(text);}
  if(text.length>120000)throw new Error('\u6a21\u578b\u56de\u590d\u8fc7\u957f\uff0c\u672a\u622a\u65ad\u4e3a\u6210\u529f\u3002');
  await node('bridge/complete',{id,text,model:run.acceptedConfig?.model||'cindy',receipt:{...receipt,outputMessageId:run.outputMessageId}});
  last={...last,state:'completed',outputCharacters:text.length};
  try{await cindy.tasks.archive({taskId:receipt.taskId});}catch(_){}
 }catch(e){
  last={...(last||{}),id,state:'failed',error:String(e.message||e).slice(0,600)};
  try{await node('bridge/fail',{id,message:last.error});}catch(_){}
 }finally{active.delete(id);}
}
cindy.onHostMessage(async msg=>{
 if(msg.type==='event'&&msg.name==='node-notification'&&msg.method==='bridge/job'){void execute(msg.params.id);return;}
 if(msg.type!=='tool-call')return;
 try{
  let result;
  if(msg.tool==='status')result={bridge:await node('bridge/status'),taskCapabilities:await caps()};
  else if(msg.tool==='configure')result=await node('bridge/configure',{ipadHost:msg.args.ipadHost});
  else if(msg.tool==='self_test')result=await node('bridge/self_test',msg.args);
  else if(msg.tool==='diagnostics')result={bridge:await node('bridge/status'),last,active:Array.from(active.values())};
  else if(msg.tool==='pair_notebook')result=await node('bridge/pair');
  else if(msg.tool==='list_models')result=await cindy.tasks.models();
  else if(msg.tool==='select_model'){
   const catalog=await cindy.tasks.models();
   const selected=catalog.models.find(m=>m.id===msg.args.id);
   if(!selected)throw new Error('模型来源已不可用，请重新选择。');
   result=await node('bridge/set_route',{route:selected.route});
  }
  else if(msg.tool==='choose_model'){
   if(typeof cindy.pickModel!=='function')throw new Error('请到插件详情的模型与任务中选择模型；当前宿主没有统一选择器接口。');
   const selected=await cindy.pickModel({...((await node('bridge/status')).route?{initial:(await node('bridge/status')).route}:{}),...(msg.mobilePageId?{mobilePageId:msg.mobilePageId}:{})});
   if(!selected.ok)throw new Error(selected.message||selected.errorCode);
   result=await node('bridge/set_route',{route:selected.route});
  }
  else if(msg.tool==='inspect_task'){
   const run=await cindy.tasks.getRun({runId:msg.args.runId});
   const task=await cindy.tasks.get({taskId:msg.args.taskId});
   const page=await cindy.tasks.readMessages({taskId:msg.args.taskId,limit:20});
   result={run,task,messages:(page.messages||page.items||[]).map(m=>({id:m.id||m.messageId,role:m.role,characters:textOf(m).length})),pageFields:Object.keys(page)};
  }
  else if(msg.tool==='stop')result=await node('bridge/stop');
  else throw new Error('Unknown tool');
  await cindy.send({type:'tool-result',callId:msg.callId,ok:true,result});
 }catch(e){await cindy.send({type:'tool-result',callId:msg.callId,ok:false,errorCode:'BRIDGE_ERROR',message:String(e.message||e).slice(0,800)});}
});
void node('bridge/status').then(s=>{for(const id of s.pendingIds||[])void execute(id);}).catch(()=>{});
