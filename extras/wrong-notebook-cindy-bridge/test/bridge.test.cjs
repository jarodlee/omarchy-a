const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {Bridge,normalize}=require('../node/worker.cjs');
const body={model:'cindy',messages:[{role:'user',content:'test'}]};
async function fixture(t,onJob){
 const directory=fs.mkdtempSync(path.join(os.tmpdir(),'cindy-notebook-test-'));
 const bridge=new Bridge({directory,port:0,onJob});await bridge.listen();
 t.after(async()=>{await bridge.stop();fs.rmSync(directory,{recursive:true,force:true});});
 return{bridge,url:'http://127.0.0.1:'+bridge.port,headers:{Authorization:'Bearer '+bridge.key,'Content-Type':'application/json'}};
}
test('requires authentication and does not expose key in status',async t=>{
 const{bridge,url,headers}=await fixture(t,()=>{});
 assert.equal((await fetch(url+'/v1/models')).status,401);
 const models=await(await fetch(url+'/v1/models',{headers})).json();assert.equal(models.data[0].id,'cindy');
 assert(!JSON.stringify(bridge.status()).includes(bridge.key));
 assert.equal(fs.statSync(path.join(bridge.directory,'bridge.key')).mode&0o777,0o600);
});
test('rejects unsupported tools, remote image URLs and invalid bytes before inference',()=>{
 assert.throws(()=>normalize({...body,tools:[{}]}));
 assert.throws(()=>normalize({model:'other',messages:body.messages}));
 assert.throws(()=>normalize({model:'cindy',messages:[{role:'user',content:[{type:'image_url',image_url:{url:'http://127.0.0.1/private'}}]}]}));
 assert.throws(()=>normalize({model:'cindy',messages:[{role:'user',content:[{type:'image_url',image_url:{url:'data:image/png;base64,AAAA'}}]}]}));
});
test('buffers completed reply into OpenAI format without inventing usage',async t=>{
 let bridge;const f=await fixture(t,id=>setTimeout(()=>bridge.complete(id,'42','actual-test-model',{taskId:'owned-task',runId:'owned-run'}),10));bridge=f.bridge;
 const r=await fetch(f.url+'/v1/chat/completions',{method:'POST',headers:f.headers,body:JSON.stringify(body)});
 assert.equal(r.status,200);const d=await r.json();assert.equal(d.choices[0].message.content,'42');assert.equal(d.model,'actual-test-model');assert.equal(d.usage,undefined);
});
test('coalesces retry of the same pending payload rather than creating two model runs',async t=>{
 let bridge,runs=0;const f=await fixture(t,id=>{runs++;setTimeout(()=>bridge.complete(id,'same','test',{}),50);});bridge=f.bridge;
 const call=()=>fetch(f.url+'/v1/chat/completions',{method:'POST',headers:f.headers,body:JSON.stringify(body)}).then(r=>r.json());
 const[a,b]=await Promise.all([call(),call()]);assert.equal(runs,1);assert.equal(a.id,b.id);
});
test('SSE keeps OpenAI chunk shape and reports model failure as an error',async t=>{
 let bridge;const f=await fixture(t,id=>setTimeout(()=>bridge.complete(id,'stream-answer','test',{}),20));bridge=f.bridge;
 const r=await fetch(f.url+'/v1/chat/completions',{method:'POST',headers:f.headers,body:JSON.stringify({...body,stream:true})});
 const text=await r.text();assert(text.includes('chat.completion.chunk'));assert(text.includes('stream-answer'));assert(text.endsWith('data: [DONE]\n\n'));
 bridge.onJob=id=>setTimeout(()=>bridge.fail(id,'native failure'),5);
 const bad=await fetch(f.url+'/v1/chat/completions',{method:'POST',headers:f.headers,body:JSON.stringify({...body,messages:[{role:'user',content:'fail'}]})});
 assert.equal(bad.status,502);assert.equal((await bad.json()).error.message,'native failure');
});
test('requires both real probe outcomes before changing notebook provider',async t=>{
 const{bridge}=await fixture(t,()=>{});await assert.rejects(bridge.pair(),/Both real/);
});
test('public HTTPS mode survives worker restart without starting private iPad SSH forwarding',async t=>{
 const{bridge}=await fixture(t,()=>{});
 fs.writeFileSync(bridge.configFile,JSON.stringify({ipadHost:'192.168.1.207',publicEndpoint:'https://cindy-ctb.ghtxx.cn/v1'}));
 const second=new Bridge({directory:bridge.directory,port:0});
 second.startTunnel=()=>{throw Error('Unexpected dependence on private iPad address');};
 await second.listen();
 try{assert.equal((await fetch('http://127.0.0.1:'+second.port+'/v1/models')).status,401);assert.equal(second.ssh,null);}
 finally{await second.stop();}
});
test('reuses persisted receipt identity when a client retries after worker restart',async t=>{
 const{bridge}=await fixture(t,()=>{}),j=bridge.submit(body,'stable-hash');
 j.receipt={taskId:'owned-task',runId:'owned-run'};bridge.receipts[j.id].receipt=j.receipt;bridge.save();
 const second=new Bridge({directory:bridge.directory,port:0});
 const recovered=second.submit(body,'stable-hash');assert.equal(recovered.id,j.id);assert.equal(recovered.receipt.runId,'owned-run');
});
