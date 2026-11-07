// Isolated loopback UI → API regression; never opens a desktop window.
const assert=require('assert'),fs=require('fs'),vm=require('vm'),os=require('os'),path=require('path'),net=require('net');
const {spawn}=require('child_process');
async function freePort(){return new Promise((resolve,reject)=>{let s=net.createServer();s.on('error',reject);s.listen(0,'127.0.0.1',()=>{let p=s.address().port;s.close(()=>resolve(p))})})}
async function main(){
  const temp=fs.mkdtempSync(path.join(os.tmpdir(),'forge-component-'));
  const port=await freePort(),base=`http://127.0.0.1:${port}`;
  const child=spawn('python3',['server.py','--host','127.0.0.1','--port',String(port)],{cwd:process.cwd(),env:{...process.env,OH_ADVISOR_DATA:temp},stdio:'ignore'});
  try{
    let ready=false;
    for(let i=0;i<80;i++){try{let r=await fetch(base+'/api/health');if(r.ok){ready=true;break}}catch{}await new Promise(r=>setTimeout(r,100))}
    assert(ready,'isolated app did not start');
    const before=await(await fetch(base+'/api/state')).json();
    const nodes=new Map();
    const document={querySelector(sel){if(!nodes.has(sel))nodes.set(sel,{value:'',textContent:'',innerHTML:''});return nodes.get(sel)},querySelectorAll(){return []}};
    const ctx={document,window:{},fetch:(url,opts)=>fetch(url.startsWith('/')?base+url:url,opts),setTimeout(){},URL,Blob,console};
    vm.createContext(ctx);
    vm.runInContext(fs.readFileSync('static/app.js','utf8').replace(/refresh\(\)\.catch\(fail\);\s*$/,''),ctx);
    assert(vm.runInContext('componentCompareCard()',ctx).includes('any gear or mod'));
    assert(vm.runInContext('componentCompareCard()',ctx).includes('catalog_id and level'));
    await vm.runInContext('loadHelmetExample()',ctx);
    assert(document.querySelector('#componentLeft').value.includes('Damage from monsters received'));
    await vm.runInContext('runReviewedComparison()',ctx);
    const html=document.querySelector('#componentResults').innerHTML;
    assert(html.includes('Shared listed rows: Damage from monsters received 4.8%'));
    assert(html.includes('895534 current / 895757 alternative'));
    assert(html.includes('Buffs are missing or differ across runs.'));
    assert(html.includes('No timed DPS.'));
    assert(html.includes('Game winner: unverified.'));
    const custom={left:{name:'Current build',items:[{name:'helmet',attributes:[{name:'Weapon DMG',value_percent:4,source:'review'}]}]},
                  right:{name:'Changed build',items:[{name:'helmet',attributes:[{name:'Weapon DMG',value_percent:8,source:'review'}]}]},context:{}};
    const response=await fetch(base+'/api/component-compare',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(custom)});
    assert(response.ok);
    const result=await response.json();
    assert(result.component_ratios.normal.min>1);
    assert.equal(result.game_winner_established,false);
    const modeled={...custom,context:{base_pools:{weapon:0},combat_profile:{shots:10,duration_seconds:5,
      direct:{normal_damage_per_shot:100,crit_share:0,weakspot_share:0,crit_weakspot_share:0}}}};
    const projected=await fetch(base+'/api/component-compare',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(modeled)});
    assert(projected.ok);
    const projection=await projected.json();
    assert.equal(projection.conditional_combat_projection.left_damage_range[0],1040);
    assert.equal(projection.conditional_combat_projection.right_damage_range[0],1080);
    ctx.projection=projection;
    assert(vm.runInContext('componentComparisonHtml(projection)',ctx).includes('Conditional DPS:'));
    const exact=await fetch(base+'/api/component-compare',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({left:{attributes:[]},right:{catalog_id:'mod:chest_mod:quick-comeback-precision',level:13}})});
    assert(exact.ok);
    const sourced=await exact.json();
    assert(Math.abs(sourced.component_ratios.normal.min-1.048*1.03)<1e-10);
    assert.equal(sourced.right.trace[0].source_sha256.length,64);
    const shoes=await(await fetch(base+'/api/catalog/mod%3Aboots_mod%3Aagainst-all-odds-deviant-energy?level=12')).json();
    assert.equal(shoes.attribute_coverage,'complete');
    assert.deepEqual(shoes.known_attributes.map(row=>row.value_percent),[6.4,3.6,7.2,3]);
    assert.equal(shoes.observed_profile.source_timestamp_seconds,24);
    const coverage=await(await fetch(base+'/api/evidence-coverage')).json();
    assert.equal(coverage.weapon_bound_partial,26);
    assert.equal(coverage.fully_parameterized_current_weapons,0);
    const aug=await(await fetch(base+'/api/evidence-binding/weapon%3Aaug-electron-cloud')).json();
    assert.equal(aug.binding_status,'partial_preview_numbers');
    assert.equal(aug.evidence.events[0].evidence_status,'preview_numeric');
    const bastille=await fetch(base+'/api/component-compare',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({left:{attributes:[]},right:{sets:[{name:'Bastille',count:2}]},
        context:{scenario:'pve non-raidzone',timing:{rpm:600,magazine:10,reload_seconds:2}}})});
    assert(bastille.ok);
    assert(Math.abs((await bastille.json()).firing_cycle.right.reload_seconds-2/1.15)<1e-9);
    const candidate=await fetch(base+'/api/component-compare',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({left:{attributes:[]},right:{sets:[{name:'Agent',count:2}]},
        context:{community_candidate_opt_in:true}})});
    assert(candidate.ok);
    const assumed=await candidate.json();
    assert.equal(assumed.component_ratios.weakspot.max,1.1);
    assert.equal(assumed.game_winner_established,false);
    const weaponScenario={weapon_id:'weapon:mps5-blue-tiger',evidence_mode:'dated_release',
      model_mode:'explicit_assumptions',stream_id:'ui-source-left',
      actions:[{kind:'hit',at:0,target:'dummy',rolls:{bounce:.1},input_id:'hit-1'}],
      damage_model:{basis_values:{attack:100},direct:{basis:'attack',damage_class:'weapon',
        element:'none',coefficient_percent:100},packet_models:{bounce:{basis:'attack',
        damage_class:'weapon',element:'none',coefficient_percent:40,resolved_hits:1}},duration_seconds:2}};
    const eventResponse=await fetch(base+'/api/component-compare',{method:'POST',
      headers:{'Content-Type':'application/json'},body:JSON.stringify({left:{attributes:[]},
        right:{attributes:[]},context:{weapon_timeline:{left:weaponScenario,
          right:{...weaponScenario,stream_id:'ui-source-right'}}}})});
    assert(eventResponse.ok);
    const eventComparison=await eventResponse.json();
    assert.equal(eventComparison.weapon_timeline_scenarios.left.total_damage,140);
    ctx.eventComparison=eventComparison;
    const eventHtml=vm.runInContext('componentComparisonHtml(eventComparison)',ctx);
    assert(eventHtml.includes('known damage 140.0'));
    assert(eventHtml.includes('conditional rate 70.0 per second'));
    assert(eventHtml.includes('No verified game DPS.'));
    const typedResponse=await fetch(base+'/api/component-compare',{method:'POST',
      headers:{'Content-Type':'application/json'},body:JSON.stringify({left:{attributes:[]},
        right:{catalog_id:'mod:chest_mod:rejuvenating-precision',level:11},context:{
          core_unknown_variant_opt_in:true,enemy_defeated:true,max_hp_points:1000,
          current_hp_points:900,shield_points:400,cooldown_available:true}})});
    assert(typedResponse.ok);
    const typed=await typedResponse.json();
    assert.deepEqual(typed.right.typed_main_effects[0].outputs.map(x=>x.type),
      ['heal','shield_generation_request']);
    ctx.typed=typed;
    const typedHtml=vm.runInContext('componentComparisonHtml(typed)',ctx);
    assert(typedHtml.includes('100 HP restored'));
    assert(typedHtml.includes('actual shield depends on capacity'));
    assert(typedHtml.includes('not extra component multipliers'));
    const after=await(await fetch(base+'/api/state')).json();
    assert.deepEqual(after,before,'read-only comparison must not mutate state');
    console.log('Isolated component UI → API and persistence regression passed');
  }finally{child.kill();fs.rmSync(temp,{recursive:true,force:true})}
}
main().catch(error=>{console.error(error);process.exitCode=1});
