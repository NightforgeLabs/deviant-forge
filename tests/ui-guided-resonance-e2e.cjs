// Guided form → isolated loopback API → shared scheduler, without a desktop window.
const assert=require('assert'),fs=require('fs'),vm=require('vm'),os=require('os'),path=require('path'),net=require('net');
const {spawn}=require('child_process');
async function freePort(){return new Promise((resolve,reject)=>{const s=net.createServer();s.on('error',reject);s.listen(0,'127.0.0.1',()=>{const p=s.address().port;s.close(()=>resolve(p))})})}
async function main(){
 const temp=fs.mkdtempSync(path.join(os.tmpdir(),'forge-resonance-'));
 const port=await freePort(),base=`http://127.0.0.1:${port}`;
 const child=spawn('python3',['server.py','--host','127.0.0.1','--port',String(port)],
   {cwd:process.cwd(),env:{...process.env,OH_ADVISOR_DATA:temp},stdio:'ignore'});
 try{
  let ready=false;for(let i=0;i<80;i++){try{if((await fetch(base+'/api/health')).ok){ready=true;break}}catch{}await new Promise(r=>setTimeout(r,100))}assert(ready);
  const nodes=new Map(),document={body:{classList:{contains(){return false},remove(){},toggle(){}}},
    querySelector(sel){if(!nodes.has(sel))nodes.set(sel,{value:'',checked:false,disabled:false,textContent:'',innerHTML:'',focus(){},setAttribute(){},getAttribute(){return null}});return nodes.get(sel)},
    querySelectorAll(){return []}};
  const ctx={document,window:{scrollTo(){}},fetch:(url,opts)=>fetch(url.startsWith('/')?base+url:url,opts),setTimeout(){},URL,URLSearchParams,Blob,console};
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync('static/app.js','utf8').replace(/refresh\(\)\.catch\(fail\);\s*$/,''),ctx);
  const initial=await(await fetch(base+'/api/state')).json();ctx.initial=initial;
  vm.runInContext('state=initial;render=()=>{}',ctx);
  const mod='mod:gloves_mod:crit-amplifier-resonance-deviant-energy';
  ctx.mod=mod;
  vm.runInContext("for(const side of ['left','right'])Object.assign(structuredSides[side],{kind:'catalog',catalogId:mod,itemKind:'mod',level:'10'})",ctx);
  const set=(name,value)=>{document.querySelector('#sc_'+name).value=String(value)};
  for(const name of ['referenceEnabled','timedEnabled','timedTarget'])document.querySelector('#sc_'+name).checked=true;
  set('timedDuration','.18');
  for(const side of ['left','right']){
    set(`r_${side}_weaponId`,'weapon:aug-electron-cloud');
    document.querySelector(`#sc_r_${side}_itemPage`).checked=true;
    document.querySelector(`#sc_r_${side}_assumeRpm`).checked=true;
    set(`r_${side}_projectiles`,'1');set(`r_${side}_tier`,'1');set(`r_${side}_pageReload`,'2.5');
    set(`t_${side}_resonanceCritIndices`,'1');set(`t_${side}_resonanceWeakIndices`,'none');
    set(`t_${side}_resonanceElementalIndices`,'0');set(`t_${side}_resonanceElement`,'shock');
    set(`t_${side}_resonanceReserve`,'0');set(`t_${side}_resonanceBaseCrit`,'100');
    set(`t_${side}_resonanceBaseWeak`,'100');set(`t_${side}_enemyBucketModel`,'independent_multiplicative');
  }
  await vm.runInContext('runStructuredComparison()',ctx);
  const output=vm.runInContext('structuredLast.published_reference.timed_scenarios.left',ctx);
  assert(output);
  assert.equal(output.known_damage_subtotal,136.816);
  assert.deepEqual(JSON.parse(JSON.stringify(output.resonance_timeline.packets.map(p=>p.damage))),[34,68.816,34]);
  assert(document.querySelector('#sc_result').innerHTML.includes('explicit ordered direct'));
  assert(document.querySelector('#sc_result').innerHTML.includes('2 sourced Resonance rules'));
  assert.equal(vm.runInContext('structuredLast.published_reference.timed_comparison.game_winner_established',ctx),false);
  console.log('Guided Resonance UI → isolated API → ordered scheduler passed');
 }finally{child.kill('SIGTERM');fs.rmSync(temp,{recursive:true,force:true})}
}
main().catch(error=>{console.error(error);process.exitCode=1});
