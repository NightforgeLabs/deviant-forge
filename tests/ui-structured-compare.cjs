// Headless UI → isolated API exercise. No desktop window is opened.
const assert=require('assert'),fs=require('fs'),vm=require('vm'),os=require('os'),path=require('path'),net=require('net');
const {spawn}=require('child_process');
async function freePort(){return new Promise((resolve,reject)=>{let s=net.createServer();s.on('error',reject);s.listen(0,'127.0.0.1',()=>{let p=s.address().port;s.close(()=>resolve(p))})})}
async function main(){
 const temp=fs.mkdtempSync(path.join(os.tmpdir(),'forge-structured-')),port=await freePort(),base=`http://127.0.0.1:${port}`;
 const child=spawn('python3',['server.py','--host','127.0.0.1','--port',String(port)],{cwd:process.cwd(),env:{...process.env,OH_ADVISOR_DATA:temp},stdio:'ignore'});
 try{
  let ready=false;for(let i=0;i<80;i++){try{if((await fetch(base+'/api/health')).ok){ready=true;break}}catch{}await new Promise(r=>setTimeout(r,100))}assert(ready);
  const before=await(await fetch(base+'/api/state')).json(),nodes=new Map();
  const document={body:{classList:{contains(){return false},remove(){},toggle(){}}},querySelector(sel){if(!nodes.has(sel))nodes.set(sel,{value:'',checked:false,disabled:false,textContent:'',innerHTML:'',focus(){this.focused=true},setAttribute(){},getAttribute(){return null}});return nodes.get(sel)},querySelectorAll(){return []}};
  const ctx={document,window:{scrollTo(){}},fetch:(url,opts)=>fetch(url.startsWith('/')?base+url:url,opts),setTimeout(){},URL,URLSearchParams,Blob,console,renderCount:0};vm.createContext(ctx);
  vm.runInContext(fs.readFileSync('static/app.js','utf8').replace(/refresh\(\)\.catch\(fail\);\s*$/,''),ctx);
  ctx.saved=before;vm.runInContext('state=saved;render=()=>{renderCount++}',ctx);
  const markup=vm.runInContext('structuredComponentCard()',ctx);
  assert.equal(vm.runInContext('structuredForm.jointModel',ctx),'additive');
  assert(markup.includes('Native v13 direct-hit rule'));
  assert(markup.includes('Search exact name or suffix'));
  const slots=['Helmet mod','Mask mod','Gloves mod','Shoes mod','Chest / top mod','Legs / bottoms mod'];
  for(let i=1;i<slots.length;i++)assert(markup.indexOf(slots[i-1])<markup.indexOf(slots[i]));
  assert(markup.includes('Existing saved planned build'));
  assert(markup.includes('sc_suffixCandidate'));
  assert(markup.includes('sc_timelineLeft')&&markup.includes('sc_timelineRight'));
  assert(markup.includes('sc_coreCandidate'));
  assert(markup.includes('sc_referenceEnabled'));
  assert(markup.includes('Set source model'));
  assert(markup.includes('sc_t_left_setStamina')&&markup.includes('sc_t_right_setSpotted'));
  await vm.runInContext('loadPublishedReferenceWeapons()',ctx);
  assert(vm.runInContext('publishedReferenceWeapons.length',ctx)>=128);
  assert(vm.runInContext('publishedReferencePackets.length',ctx)>=14);
  assert(markup.includes('Show six packet-hook input requirements'));
  await vm.runInContext('loadPacketHookRequirements()',ctx);
  assert(document.querySelector('#packetHookRequirements').innerHTML.includes('ordinary_uncharged_shot'));
  assert(document.querySelector('#packetHookRequirements').innerHTML.includes('weapon:pdw90-holographic-resonance'));
  document.querySelector('#sc_left_query').value='Agent Set';
  await vm.runInContext("lookupStructuredCatalog('left')",ctx);
  assert(!vm.runInContext('structuredResults.left.some(x=>x.kind==="set")',ctx));
  document.querySelector('#sc_left_query').value='Against All Odds';
  await vm.runInContext("lookupStructuredCatalog('left')",ctx);
  assert(vm.runInContext('structuredResults.left.length',ctx)>=10);
  const shoes='mod:boots_mod:against-all-odds-deviant-energy';
  document.querySelector('#sc_left_options').value=shoes;
  vm.runInContext("structuredChooseCatalog('left')",ctx);
  assert.equal(vm.runInContext('structuredSides.left.catalogId',ctx),shoes);
  document.querySelector('#sc_left_level').value='12';vm.runInContext("structuredLevelChanged('left')",ctx);
  assert.equal(vm.runInContext('structuredSides.left.level',ctx),'12');
  document.querySelector('#sc_left_options').value='mod:boots_mod:against-all-odds-precision';
  vm.runInContext("structuredChooseCatalog('left')",ctx);
  assert.equal(vm.runInContext('structuredSides.left.level',ctx),'','changing variant clears the old level');
  document.querySelector('#sc_left_options').value=shoes;vm.runInContext("structuredChooseCatalog('left')",ctx);
  document.querySelector('#sc_left_level').value='12';vm.runInContext("structuredLevelChanged('left')",ctx);
  document.querySelector('#sc_right_query').value='Against All Odds';await vm.runInContext("lookupStructuredCatalog('right')",ctx);
  document.querySelector('#sc_right_options').value=shoes;vm.runInContext("structuredChooseCatalog('right')",ctx);
  document.querySelector('#sc_right_level').value='12';vm.runInContext("structuredLevelChanged('right')",ctx);
  await vm.runInContext('runStructuredComparison()',ctx);
  assert(document.querySelector('#sc_result').innerHTML.includes('Game winner: unverified.'));
  assert(!document.querySelector('#sc_result').innerHTML.includes('Incomplete numeric profile.'));
  assert(vm.runInContext('structuredLast.left.evidence_audit.items[0].binding_status',ctx)==='verified_exact_catalog_profile');
  document.querySelector('#sc_referenceEnabled').checked=true;
  document.querySelector('#sc_r_left_weaponId').value='weapon:kam';
  document.querySelector('#sc_r_right_weaponId').value='weapon:kam';
  vm.runInContext('rememberStructuredInputs()',ctx);
  await vm.runInContext('runStructuredComparison()',ctx);
  assert(document.querySelector('#sc_result').innerHTML.includes('Published direct-only reference'));
  assert(document.querySelector('#sc_result').innerHTML.includes('Connected typed effect evidence'));
  assert.equal(vm.runInContext('structuredLast.published_reference.left.weapon_id',ctx),'weapon:kam');
  assert.equal(vm.runInContext('structuredLast.published_reference.game_winner_established',ctx),false);
  assert(markup.includes('sc_r_left_itemPage')&&markup.includes('sc_r_right_projectiles')&&
    markup.includes('sc_r_left_assumeRpm'));
  document.querySelector('#sc_r_left_weaponId').value='weapon:aug-electron-cloud';
  document.querySelector('#sc_r_right_weaponId').value='weapon:aug-electron-cloud';
  document.querySelector('#sc_r_left_itemPage').checked=true;
  document.querySelector('#sc_r_right_itemPage').checked=true;
  document.querySelector('#sc_r_left_assumeRpm').checked=true;
  document.querySelector('#sc_r_right_assumeRpm').checked=true;
  document.querySelector('#sc_r_left_projectiles').value='1';
  document.querySelector('#sc_r_right_projectiles').value='1';
  document.querySelector('#sc_r_left_tier').value='1';
  document.querySelector('#sc_r_right_tier').value='4';
  vm.runInContext('rememberStructuredInputs()',ctx);
  await vm.runInContext('runStructuredComparison()',ctx);
  assert.equal(vm.runInContext('structuredLast.published_reference.left.direct_only.reference_hit',ctx),34*1.03);
  assert.equal(vm.runInContext('structuredLast.published_reference.right.direct_only.reference_hit',ctx),132*1.03);
  assert.equal(vm.runInContext('structuredLast.published_reference.right_over_left_reference_ratios.reference_hit',ctx),132/34);
  assert.equal(vm.runInContext('structuredLast.published_reference.game_winner_established',ctx),false);
  assert(document.querySelector('#sc_result').innerHTML.includes('Exact named item-page conditional model'));
  document.querySelector('#sc_r_right_stars').value='2';
  vm.runInContext('rememberStructuredInputs()',ctx);
  await vm.runInContext('runStructuredComparison()',ctx);
  assert.equal(vm.runInContext('structuredLast.published_reference.right.direct_only.reference_hit',ctx),139*1.03);
  document.querySelector('#sc_r_right_stars').value='';
  document.querySelector('#sc_r_right_tier').value='5';
  document.querySelector('#sc_r_right_stars').value='2';
  vm.runInContext('rememberStructuredInputs()',ctx);
  await vm.runInContext('runStructuredComparison()',ctx);
  assert(document.querySelector('#sc_result').innerHTML.includes('no exact item page damage'));
  vm.runInContext("structuredSides.left.catalogId='weapon:aug-electron-cloud';structuredSides.left.itemKind='weapon'",ctx);
  document.querySelector('#sc_r_left_weaponId').value='weapon:socr-cosmic-visitor';
  document.querySelector('#sc_r_right_tier').value='4';
  document.querySelector('#sc_r_right_stars').value='';
  vm.runInContext('rememberStructuredInputs()',ctx);
  await vm.runInContext('runStructuredComparison()',ctx);
  assert(document.querySelector('#sc_result').innerHTML.includes('Reference weapon must match the selected item'));
  vm.runInContext("structuredSides.left.catalogId='mod:boots_mod:against-all-odds-deviant-energy';structuredSides.left.itemKind='mod'",ctx);
  document.querySelector('#sc_r_left_itemPage').checked=false;
  document.querySelector('#sc_r_right_itemPage').checked=false;
  document.querySelector('#sc_r_left_projectiles').value='';
  document.querySelector('#sc_r_right_projectiles').value='';
  document.querySelector('#sc_r_left_tier').value='';
  document.querySelector('#sc_r_right_tier').value='';
  document.querySelector('#sc_r_right_stars').value='';
  document.querySelector('#sc_r_left_weaponId').value='weapon:kam';
  document.querySelector('#sc_r_right_weaponId').value='weapon:kam';
  vm.runInContext('rememberStructuredInputs()',ctx);
  document.querySelector('#sc_timedEnabled').checked=true;
  document.querySelector('#sc_timedDuration').value='1';
  document.querySelector('#sc_timedTarget').checked=true;
  document.querySelector('#sc_timedSetMode').value='community_snapshot';
  document.querySelector('#sc_t_left_setStamina').value='.95';
  document.querySelector('#sc_t_left_setSpotted').value='false';
  vm.runInContext('rememberStructuredInputs()',ctx);
  assert.equal(vm.runInContext('structuredContext().published_reference.timed.left.set_evidence_mode',ctx),'community_snapshot');
  assert.equal(vm.runInContext('structuredContext().published_reference.timed.left.set_condition_inputs.stamina_fraction',ctx),.95);
  assert.equal(vm.runInContext('structuredContext().published_reference.timed.left.set_condition_inputs.spotted_by_enemies',ctx),false);
  await vm.runInContext('runStructuredComparison()',ctx);
  assert.equal(vm.runInContext('structuredLast.published_reference.left.weapon_source_native_baseline',ctx),null);
  assert(document.querySelector('#sc_result').innerHTML.includes('no exact item-ID'));
  assert.equal(vm.runInContext('structuredLast.published_reference.timed_comparison.game_winner_established',ctx),false);
  document.querySelector('#sc_timedEnabled').checked=false;
  document.querySelector('#sc_referenceEnabled').checked=false;
  vm.runInContext('rememberStructuredInputs()',ctx);
  document.querySelector('#sc_right_query').value='Elemental Havoc';
  await vm.runInContext("lookupStructuredCatalog('right')",ctx);
  assert(vm.runInContext('structuredResults.right.length',ctx)>0);
  document.querySelector('#sc_right_options').value='mod:helmet_mod:elemental-havoc-lunar';
  vm.runInContext("structuredChooseCatalog('right')",ctx);
  document.querySelector('#sc_right_level').value='10';vm.runInContext("structuredLevelChanged('right')",ctx);
  await vm.runInContext('runStructuredComparison()',ctx);
  assert(document.querySelector('#sc_result').innerHTML.includes('Incomplete numeric profile.'));
  assert(/Other active bonus pools were not entered \([^<]*\)\. Ratios/.test(document.querySelector('#sc_result').innerHTML));
  assert(!document.querySelector('#sc_result').innerHTML.includes('Complete derived profile — unverified.'));
  assert(!document.querySelector('#sc_result').innerHTML.includes('))}'));
  assert.equal(vm.runInContext('structuredLast.right.suffix_candidate_profile',ctx),null);
  document.querySelector('#sc_coreCandidate').checked=true;
  vm.runInContext('rememberStructuredInputs()',ctx);
  await vm.runInContext('runStructuredComparison()',ctx);
  assert(document.querySelector('#sc_result').innerHTML.includes('Main-effect what-if.'));
  assert(vm.runInContext('structuredLast.right.trace.some(row=>String(row.rule_id||" ").includes(":core:"))',ctx));
  document.querySelector('#sc_coreCandidate').checked=false;
  vm.runInContext('rememberStructuredInputs()',ctx);
  document.querySelector('#sc_suffixCandidate').checked=true;
  vm.runInContext('rememberStructuredInputs()',ctx);
  await vm.runInContext('runStructuredComparison()',ctx);
  assert(document.querySelector('#sc_result').innerHTML.includes('Complete derived profile — unverified.'));
  assert(!document.querySelector('#sc_result').innerHTML.includes('Incomplete numeric profile.'));
  assert.equal(vm.runInContext('structuredLast.right.suffix_candidate_profile.status',ctx),'candidate_complete');
  document.querySelector('#sc_right_query').value='Deviation Expert';
  await vm.runInContext("lookupStructuredCatalog('right')",ctx);
  document.querySelector('#sc_right_options').value='mod:helmet_mod:deviation-expert-general';
  vm.runInContext("structuredChooseCatalog('right')",ctx);
  document.querySelector('#sc_right_level').value='4';vm.runInContext("structuredLevelChanged('right')",ctx);
  await vm.runInContext('runStructuredComparison()',ctx);
  assert(document.querySelector('#sc_result').innerHTML.includes('Incomplete derived profile — unverified.'));
  assert(document.querySelector('#sc_result').innerHTML.includes('Incomplete numeric profile.'));
  assert.equal(vm.runInContext('structuredLast.right.suffix_candidate_profile.status',ctx),'candidate_partial');
  const eventScenario={weapon_id:'weapon:mps5-blue-tiger',evidence_mode:'dated_release',
    model_mode:'explicit_assumptions',stream_id:'structured-left',
    actions:[{kind:'hit',at:0,target:'dummy',rolls:{bounce:.1},input_id:'h1'}],
    damage_model:{basis_values:{attack:100},direct:{basis:'attack',damage_class:'weapon',
      element:'none',coefficient_percent:100},packet_models:{bounce:{basis:'attack',
      damage_class:'weapon',element:'none',coefficient_percent:40,resolved_hits:1}},duration_seconds:2}};
  document.querySelector('#sc_timelineLeft').value=JSON.stringify(eventScenario);
  document.querySelector('#sc_timelineRight').value=JSON.stringify({...eventScenario,stream_id:'structured-right'});
  vm.runInContext('rememberStructuredInputs()',ctx);
  await vm.runInContext('runStructuredComparison()',ctx);
  assert.equal(vm.runInContext('structuredLast.weapon_timeline_scenarios.left.total_damage',ctx),140);
  assert(document.querySelector('#sc_result').innerHTML.includes('known damage 140.0'));
  assert(document.querySelector('#sc_result').innerHTML.includes('No verified game DPS.'));
  document.querySelector('#sc_timelineRight').value='';
  vm.runInContext('rememberStructuredInputs()',ctx);
  await vm.runInContext('runStructuredComparison()',ctx);
  assert(document.querySelector('#sc_result').innerHTML.includes('Enter both weapon event scenarios'));
  document.querySelector('#sc_timelineLeft').value='';
  vm.runInContext('rememberStructuredInputs()',ctx);
  // Guided form builds a complete sourced Outer Space scenario without JSON.
  assert(vm.runInContext('structuredComponentCard()',ctx).includes('Guided weapon damage scenarios'));
  document.querySelector('#sc_guidedEnabled').checked=true;
  document.querySelector('#sc_guidedTarget').value='same dummy';
  const guided={weaponId:'weapon:mps7-outer-space',hits:'12',duration:'2',attack:'100',psi:'80',
    basis:'attack',damageClass:'weapon',element:'none',coefficient:'100',weaponPool:'20',
    statusPool:'10',elementPool:'30',allPool:'0',rollMode:'fail',affected:'true',packetClass:'status',evidenceMode:'dated_release',reloadAfter:'false'};
  for(const side of ['left','right'])for(const [name,value] of Object.entries(guided))
    document.querySelector(`#sc_g_${side}_${name}`).value=value;
  document.querySelector('#sc_g_right_packetClass').value='weapon';
  vm.runInContext('rememberStructuredInputs()',ctx);
  await vm.runInContext('runStructuredComparison()',ctx);
  assert.equal(vm.runInContext('structuredLast.weapon_timeline_scenarios.left.total_damage',ctx),2012);
  assert.equal(vm.runInContext('structuredLast.weapon_timeline_scenarios.right.total_damage',ctx),2064);
  assert(document.querySelector('#sc_result').innerHTML.includes('Modeled scenario only:'));
  assert(document.querySelector('#sc_result').innerHTML.includes('alternative higher'));
  assert.equal(vm.runInContext('structuredLast.game_winner_established',ctx),false);
  assert(vm.runInContext('structuredComponentCard()',ctx).includes('Conflicting Memories · older Shrapnel rule only'));
  document.querySelector('#sc_g_left_weaponId').value='weapon:mg4-conflicting-memories';
  document.querySelector('#sc_g_left_packetClass').value='';
  vm.runInContext('rememberStructuredInputs()',ctx);
  assert.throws(()=>vm.runInContext("guidedWeaponScenario('left','same dummy')",ctx),/current Conflicting Memories proc rule changed in 2026/);
  document.querySelector('#sc_g_left_evidenceMode').value='historical_release';
  vm.runInContext('rememberStructuredInputs()',ctx);
  assert.equal(vm.runInContext("guidedWeaponScenario('left','same dummy').evidence_mode",ctx),'historical_release');
  document.querySelector('#sc_g_left_weaponId').value='weapon:mps7-outer-space';
  document.querySelector('#sc_g_left_evidenceMode').value='dated_release';
  vm.runInContext('rememberStructuredInputs()',ctx);
  await vm.runInContext('runStructuredComparison()',ctx);
  assert.equal(vm.runInContext('structuredLast.weapon_timeline_scenarios.left.total_damage',ctx),null);
  assert(document.querySelector('#sc_result').innerHTML.includes('no comparable complete winner'));
  for(const side of ['left','right']){
    const values={weaponId:'weapon:g17-hazardous-object',hits:'4',duration:'4',attack:'100',psi:'100',
      weaponPool:'0',statusPool:'0',elementPool:'0',allPool:'0',affected:'false',
      packetClass:'status',targetCount:'1',rpm:'120',magazine:'10',reload:'1',reloadAfter:'true'};
    for(const [name,value] of Object.entries(values))document.querySelector(`#sc_g_${side}_${name}`).value=value;
  }
  vm.runInContext('rememberStructuredInputs()',ctx);
  await vm.runInContext('runStructuredComparison()',ctx);
  assert.equal(vm.runInContext('structuredLast.weapon_timeline_scenarios.left.total_damage',ctx),558);
  assert.equal(vm.runInContext('structuredLast.weapon_timeline_scenarios.left.damage_per_second',ctx),139.5);
  assert(document.querySelector('#sc_result').innerHTML.includes('Modeled scenario only:'));
  document.querySelector('#sc_g_right_hits').value='3';
  vm.runInContext('rememberStructuredInputs()',ctx);
  await vm.runInContext('runStructuredComparison()',ctx);
  assert(document.querySelector('#sc_result').innerHTML.includes('no comparable complete winner'));
  document.querySelector('#sc_g_right_hits').value='4';
  document.querySelector('#sc_g_left_targetCount').value='';
  vm.runInContext('rememberStructuredInputs()',ctx);
  await vm.runInContext('runStructuredComparison()',ctx);
  assert(document.querySelector('#sc_result').innerHTML.includes('enter the Hazardous Object blast target count'));
  // Different complete hit counts are comparable only when entered firing cycles explain them.
  const baseCycle={weaponId:'weapon:mps5-blue-tiger',duration:'1',attack:'100',psi:'',
    basis:'attack',damageClass:'weapon',element:'none',coefficient:'100',weaponPool:'0',
    statusPool:'0',elementPool:'0',allPool:'0',rollMode:'fail',affected:'false',
    packetClass:'',targetCount:'',rpm:'600',magazine:'20',reload:'1',reloadAfter:'false',
    evidenceMode:'dated_release'};
  for(const side of ['left','right'])for(const [name,value] of Object.entries(baseCycle))
    document.querySelector(`#sc_g_${side}_${name}`).value=value;
  document.querySelector('#sc_g_left_hits').value='10';
  document.querySelector('#sc_g_right_hits').value='12';
  document.querySelector('#sc_g_right_rpm').value='720';
  vm.runInContext('rememberStructuredInputs()',ctx);
  await vm.runInContext('runStructuredComparison()',ctx);
  assert.equal(vm.runInContext('structuredLast.weapon_timeline_scenarios.left.damage_per_second',ctx),1000);
  assert.equal(vm.runInContext('structuredLast.weapon_timeline_scenarios.right.damage_per_second',ctx),1200);
  assert(document.querySelector('#sc_result').innerHTML.includes('counts explained by entered RPM'));
  document.querySelector('#sc_g_right_duration').value='2';
  vm.runInContext('rememberStructuredInputs()',ctx);
  await vm.runInContext('runStructuredComparison()',ctx);
  assert(document.querySelector('#sc_result').innerHTML.includes('no comparable complete winner'));
  document.querySelector('#sc_g_left_duration').value='2';
  document.querySelector('#sc_g_right_duration').value='2';
  document.querySelector('#sc_g_right_rpm').value='600';
  vm.runInContext('rememberStructuredInputs()',ctx);
  await vm.runInContext('runStructuredComparison()',ctx);
  assert(document.querySelector('#sc_result').innerHTML.includes('no comparable complete winner'));
  document.querySelector('#sc_g_left_duration').value='2';
  document.querySelector('#sc_g_right_duration').value='2';
  document.querySelector('#sc_g_left_hits').value='17';
  document.querySelector('#sc_g_right_hits').value='10';
  for(const side of ['left','right'])document.querySelector(`#sc_g_${side}_magazine`).value='5';
  document.querySelector('#sc_g_left_reload').value='0.1';
  document.querySelector('#sc_g_right_reload').value='0.5';
  vm.runInContext('rememberStructuredInputs()',ctx);
  await vm.runInContext('runStructuredComparison()',ctx);
  assert.equal(vm.runInContext('structuredLast.weapon_timeline_scenarios.left.total_damage',ctx),1700);
  assert.equal(vm.runInContext('structuredLast.weapon_timeline_scenarios.right.total_damage',ctx),1000);
  assert(document.querySelector('#sc_result').innerHTML.includes('counts explained by entered RPM'));
  document.querySelector('#sc_g_left_hits').value='10';
  document.querySelector('#sc_g_left_reload').value='0.5';
  vm.runInContext('rememberStructuredInputs()',ctx);
  await vm.runInContext('runStructuredComparison()',ctx);
  assert(document.querySelector('#sc_result').innerHTML.includes('Modeled scenario only:</b> tie'));
  // Catalog selection now feeds reviewed numeric rows into paired weapon packets.
  document.querySelector('#sc_right_query').value='Against All Odds';
  await vm.runInContext("lookupStructuredCatalog('right')",ctx);
  document.querySelector('#sc_right_options').value=shoes;
  vm.runInContext("structuredChooseCatalog('right')",ctx);
  document.querySelector('#sc_right_level').value='12';
  vm.runInContext("structuredLevelChanged('right')",ctx);
  document.querySelector('#sc_guidedAutoPools').checked=true;
  for(const name of ['weapon','status','elemental','all','crit','weakspot'])
    document.querySelector(`#sc_${name}`).value='0';
  for(const side of ['left','right'])for(const name of ['weaponPool','statusPool','elementPool','allPool'])
    document.querySelector(`#sc_g_${side}_${name}`).value='';
  vm.runInContext('rememberStructuredInputs()',ctx);
  await vm.runInContext('runStructuredComparison()',ctx);
  assert.equal(vm.runInContext('structuredLast.weapon_timeline_pool_application.mode',ctx),'selected_reviewed_rows');
  assert.equal(vm.runInContext('structuredLast.weapon_timeline_scenarios.left.total_damage',ctx),
               vm.runInContext('structuredLast.weapon_timeline_scenarios.right.total_damage',ctx));
  assert(document.querySelector('#sc_result').innerHTML.includes('Selected reviewed rows applied'));
  assert.equal(vm.runInContext('structuredLast.game_winner_established',ctx),false);
  document.querySelector('#sc_guidedAutoPools').checked=false;
  document.querySelector('#sc_guidedEnabled').checked=false;
  vm.runInContext('rememberStructuredInputs()',ctx);
  document.querySelector('#sc_right_query').value='Elemental Resonance Aero';
  await vm.runInContext("lookupStructuredCatalog('right')",ctx);
  document.querySelector('#sc_right_options').value='mod:pants_mod:elemental-resonance-aero';
  vm.runInContext("structuredChooseCatalog('right')",ctx);
  document.querySelector('#sc_right_level').value='17';
  vm.runInContext("structuredLevelChanged('right')",ctx);
  document.querySelector('#sc_right_shiny').checked=true;
  vm.runInContext("structuredShinyChanged('right')",ctx);
  await vm.runInContext('runStructuredComparison()',ctx);
  assert.equal(vm.runInContext('structuredLast.right.typed_main_effects[0].status',ctx),'evidence_opt_in_required');
  document.querySelector('#sc_corePreview').checked=true;
  vm.runInContext('rememberStructuredInputs()',ctx);
  await vm.runInContext('runStructuredComparison()',ctx);
  assert.equal(vm.runInContext('structuredLast.right.typed_main_effects[0].status',ctx),'combat_context_missing');
  assert.equal(vm.runInContext('structuredLast.selection_metadata.right.shiny',ctx),true);
  document.querySelector('#sc_corePreview').checked=false;
  document.querySelector('#sc_right_query').value='Against All Odds';
  await vm.runInContext("lookupStructuredCatalog('right')",ctx);
  document.querySelector('#sc_right_options').value=shoes;
  vm.runInContext("structuredChooseCatalog('right')",ctx);
  document.querySelector('#sc_right_level').value='12';
  vm.runInContext("structuredLevelChanged('right')",ctx);
  document.querySelector('#sc_coreUnknownVariant').checked=true;
  document.querySelector('#sc_coreUnknownBuild').checked=true;
  vm.runInContext('rememberStructuredInputs()',ctx);
  await vm.runInContext('runStructuredComparison()',ctx);
  assert.equal(vm.runInContext('structuredLast.right.trace.filter(row=>String(row.rule_id||" ").includes(":typed:")).length',ctx),2);
  // Native select supports arrows; Enter selects the focused result and Escape clears.
  let prevented=false;document.querySelector('#sc_right_query').value='Against All Odds';await vm.runInContext("lookupStructuredCatalog('right')",ctx);
  ctx.keyEvent={key:'Enter',preventDefault(){prevented=true}};vm.runInContext("structuredSearchKeydown(keyEvent,'right')",ctx);
  assert(prevented);assert(vm.runInContext('structuredSides.right.catalogId',ctx));
  ctx.keyEvent={key:'Escape',preventDefault(){}};vm.runInContext("structuredOptionKeydown(keyEvent,'right')",ctx);
  assert.equal(vm.runInContext('structuredSides.right.catalogId',ctx),'');
  assert.equal(vm.runInContext('structuredSides.left.catalogId',ctx),shoes,'clearing right preserves left');
  vm.runInContext("page='map';go('compare')",ctx);
  assert.equal(vm.runInContext('structuredSides.left.catalogId',ctx),shoes,'navigation back preserves unsaved draft');
  vm.runInContext('clearStructuredComparison()',ctx);
  assert.equal(vm.runInContext('structuredSides.left.catalogId',ctx),'');
  assert.equal(vm.runInContext('structuredLast',ctx),null);
  assert(vm.runInContext('structuredComponentCard()',ctx).includes('Stateful main-mod candidate scenarios'));
  const stateful={catalog_id:'mod:helmet_mod:momentum-up',level:10,allow_candidate:true,
    initial:{magazine_capacity:10,magazine_id:'m1',full_magazine:true},
    assumptions:{phase_basis:'consumed_ammo_fraction'},events:[{type:'inspect'}]};
  for(const side of ['left','right']){
    document.querySelector(`#sc_${side}_query`).value='Momentum Up';
    await vm.runInContext(`lookupStructuredCatalog('${side}')`,ctx);
    document.querySelector(`#sc_${side}_options`).value='mod:helmet_mod:momentum-up';
    vm.runInContext(`structuredChooseCatalog('${side}')`,ctx);
    document.querySelector(`#sc_${side}_level`).value='10';
    vm.runInContext(`structuredLevelChanged('${side}')`,ctx);
  }
  document.querySelector('#sc_statefulLeft').value=JSON.stringify(stateful);
  document.querySelector('#sc_statefulRight').value=JSON.stringify(stateful);
  vm.runInContext('rememberStructuredInputs()',ctx);
  await vm.runInContext('runStructuredComparison()',ctx);
  assert.equal(vm.runInContext('structuredLast.mod_stateful_scenarios.left.outputs[0].stat',ctx),'fire_rate_percent');
  assert(document.querySelector('#sc_result').innerHTML.includes('Stateful main-mod candidates'));
  assert.equal(vm.runInContext('structuredLast.game_winner_established',ctx),false);
  document.querySelector('#sc_statefulLeft').value='';
  document.querySelector('#sc_statefulRight').value='';
  for(const name of ['weapon','status','elemental','all','crit','weakspot','fireRatePool',
                     'reloadEfficiencyPool','powerSurgePool','shockPool','bomberPool'])
    document.querySelector(`#sc_${name}`).value='0';
  const integrated={model_assumptions:{scheduler:'next_shot_interval',
    fire_rate_conversion:'rpm_times_one_plus_bonus',
    pool_grouping:'additive_within_named_pool_multiplicative_across_pools',event_order:'as_list'},
    base_rpm:600,duration_seconds:1,magazine_capacity:10,starting_magazine_bullets:10,
    starting_reserve_bullets:0,direct_packet:{basis_value:100,coefficient_percent:100,
      damage_class:'weapon',element:'none'},candidate_mods:[{
      catalog_id:'mod:helmet_mod:momentum-up',level:10,allow_candidate:true,
      assumptions:{phase_basis:'consumed_ammo_fraction'}}],
    events:[{kind:'shot',event_id:'s1'},{kind:'shot',event_id:'s2'}]};
  document.querySelector('#sc_integratedLeft').value=JSON.stringify(integrated);
  document.querySelector('#sc_integratedRight').value=JSON.stringify(integrated);
  vm.runInContext('rememberStructuredInputs()',ctx);
  await vm.runInContext('runStructuredComparison()',ctx);
  assert.equal(vm.runInContext('structuredLast.integrated_event_scenarios.left.total_damage',ctx),200);
  assert(Math.abs(vm.runInContext('structuredLast.integrated_event_scenarios.left.shot_times[1]',ctx)-60/660)<1e-9);
  assert(document.querySelector('#sc_result').innerHTML.includes('Integrated timed combat'));
  assert.equal(vm.runInContext('structuredLast.game_winner_established',ctx),false);
  for(const side of ['left','right']){
    document.querySelector(`#sc_${side}_query`).value='Outer Space';
    await vm.runInContext(`lookupStructuredCatalog('${side}')`,ctx);
    document.querySelector(`#sc_${side}_options`).value='weapon:mps7-outer-space';
    vm.runInContext(`structuredChooseCatalog('${side}')`,ctx);
  }
  const sourced={...integrated,base_rpm:1200,duration_seconds:2,magazine_capacity:12,
    starting_magazine_bullets:12,candidate_mods:[],
    events:Array.from({length:12},(_,i)=>({kind:'shot',event_id:`s${i}`}))};
  sourced.weapon_proc={weapon_id:'weapon:mps7-outer-space',evidence_mode:'dated_release',
    model_mode:'explicit_assumptions',stream_id:'ui-source',
    hit_inputs:Array.from({length:12},(_,i)=>({shot_event_id:`s${i}`,target:'dummy',
      rolls:{power_surge:.99},conditions:{target_affected_by_power_surge:true}})),
    damage_model:{basis_values:{psi:80},packet_models:{celestial_lightning:{damage_class:'status'}}}};
  document.querySelector('#sc_integratedLeft').value=JSON.stringify(sourced);
  document.querySelector('#sc_integratedRight').value=JSON.stringify(sourced);
  vm.runInContext('rememberStructuredInputs()',ctx);
  await vm.runInContext('runStructuredComparison()',ctx);
  assert.equal(vm.runInContext('structuredLast.integrated_event_scenarios.left.total_damage',ctx),1600);
  assert(document.querySelector('#sc_result').innerHTML.includes('1 resolved extra packets'));
  const unresolved=JSON.parse(JSON.stringify(sourced));
  unresolved.weapon_proc.damage_model.packet_models={};
  document.querySelector('#sc_integratedRight').value=JSON.stringify(unresolved);
  vm.runInContext('rememberStructuredInputs()',ctx);
  await vm.runInContext('runStructuredComparison()',ctx);
  assert.equal(vm.runInContext('structuredLast.integrated_event_scenarios.right.total_damage',ctx),null);
  assert(document.querySelector('#sc_result').innerHTML.includes('unknown complete total'));
  for(const side of ['left','right']){
    document.querySelector(`#sc_${side}_query`).value='KVD';
    await vm.runInContext(`lookupStructuredCatalog('${side}')`,ctx);
    document.querySelector(`#sc_${side}_options`).value='weapon:kvd-boom-boom';
    vm.runInContext(`structuredChooseCatalog('${side}')`,ctx);
  }
  const packetHook={...integrated,base_rpm:600,duration_seconds:2,magazine_capacity:1,
    starting_magazine_bullets:1,candidate_mods:[],events:[{kind:'shot',event_id:'s0'}]};
  packetHook.weapon_proc={weapon_id:'weapon:kvd-boom-boom',evidence_mode:'preview_simulation',
    stream_id:'ui-six',source_actions:[{kind:'boom_boom_hit',shot_event_id:'s0',
      input_id:'hit',explosion_targets:['dummy']}],
    damage_model:{basis_values:{psi:100}},
    packet_hypotheses:{'weapon:kvd-boom-boom/explosion':{damage_class:'status'}}};
  document.querySelector('#sc_integratedLeft').value=JSON.stringify(packetHook);
  document.querySelector('#sc_integratedRight').value=JSON.stringify(packetHook);
  vm.runInContext('rememberStructuredInputs()',ctx);
  await vm.runInContext('runStructuredComparison()',ctx);
  assert.equal(vm.runInContext('structuredLast.integrated_event_scenarios.left.total_damage',ctx),400);
  assert(document.querySelector('#sc_result').innerHTML.includes('1 resolved extra packets'));
  document.querySelector('#sc_integratedLeft').value='';
  document.querySelector('#sc_integratedRight').value='';
  for(const side of ['left','right']){
    document.querySelector(`#sc_${side}_query`).value='Critical Pulse';
    await vm.runInContext(`lookupStructuredCatalog('${side}')`,ctx);
    document.querySelector(`#sc_${side}_options`).value='weapon:critical-pulse';
    vm.runInContext(`structuredChooseCatalog('${side}')`,ctx);
    document.querySelector(`#sc_t_${side}_packetId`).value='weapon:critical-pulse/lightning_orb_tick';
    document.querySelector(`#sc_t_${side}_procCount`).value='2';
    document.querySelector(`#sc_t_${side}_psi`).value='100';
  }
  document.querySelector('#sc_referenceEnabled').checked=true;
  document.querySelector('#sc_timedEnabled').checked=true;
  document.querySelector('#sc_timedDuration').value='1';
  document.querySelector('#sc_timedTarget').checked=true;
  vm.runInContext('rememberStructuredInputs()',ctx);
  await vm.runInContext('runStructuredComparison()',ctx);
  assert.equal(vm.runInContext('structuredLast.published_reference.timed_scenarios.left.source_proc',ctx),undefined);
  // A removed unanchored direct basis cannot silently drive a proc timeline.
  assert.equal(vm.runInContext('structuredLast.published_reference.timed_comparison.status',ctx),'partial_or_unmatched');
  assert(document.querySelector('#sc_result').innerHTML.includes('Timed total unavailable'));
  assert(markup.includes('Generate sourced hits, counters, ticks and reloads'));
  for(const side of ['left','right']){
    document.querySelector(`#sc_${side}_query`).value='Outer Space';
    await vm.runInContext(`lookupStructuredCatalog('${side}')`,ctx);
    document.querySelector(`#sc_${side}_options`).value='weapon:mps7-outer-space';
    vm.runInContext(`structuredChooseCatalog('${side}')`,ctx);
    document.querySelector(`#sc_t_${side}_packetId`).value='weapon:mps7-outer-space/celestial_lightning';
    document.querySelector(`#sc_t_${side}_sourceMode`).value='timeline';
    document.querySelector(`#sc_t_${side}_sourceReserve`).value='0';
    document.querySelector(`#sc_t_${side}_sourceTarget`).value='dummy';
    document.querySelector(`#sc_t_${side}_sourceRolls`).value=Array(12).fill('0.99').join(',');
    document.querySelector(`#sc_t_${side}_sourceConditionKey`).value='target_affected_by_power_surge';
    document.querySelector(`#sc_t_${side}_sourceConditionFlags`).value=Array(12).fill('true').join(',');
    document.querySelector(`#sc_t_${side}_packetClass`).value='status';
    document.querySelector(`#sc_t_${side}_psi`).value='80';
  }
  document.querySelector('#sc_timedDuration').value='0.8';
  vm.runInContext('rememberStructuredInputs()',ctx);
  await vm.runInContext('runStructuredComparison()',ctx);
  assert.equal(vm.runInContext('structuredLast.published_reference.timed_scenarios.left.source_proc',ctx),undefined);
  assert.equal(vm.runInContext('structuredLast.published_reference.timed_scenarios.left.modeled_total_damage',ctx),null);
  assert.equal(vm.runInContext('structuredLast.published_reference.timed_comparison.status',ctx),'partial_or_unmatched');
  assert(document.querySelector('#sc_result').innerHTML.includes('unknown'));
  document.querySelector('#sc_t_right_packetClass').value='';
  vm.runInContext('rememberStructuredInputs()',ctx);
  await vm.runInContext('runStructuredComparison()',ctx);
  assert.equal(vm.runInContext('structuredLast.published_reference.timed_scenarios.right.modeled_total_damage',ctx),null);
  assert.equal(vm.runInContext('structuredLast.published_reference.timed_comparison.status',ctx),'partial_or_unmatched');
  document.querySelector('#sc_t_right_packetClass').value='status';
  for(const side of ['left','right']){
    document.querySelector(`#sc_${side}_query`).value='Hazardous Object';
    await vm.runInContext(`lookupStructuredCatalog('${side}')`,ctx);
    document.querySelector(`#sc_${side}_options`).value='weapon:g17-hazardous-object';
    vm.runInContext(`structuredChooseCatalog('${side}')`,ctx);
    document.querySelector(`#sc_t_${side}_packetId`).value='weapon:g17-hazardous-object/thrown_reload_blast';
    document.querySelector(`#sc_t_${side}_sourceRolls`).value='0.99';
    document.querySelector(`#sc_t_${side}_sourceConditionKey`).value='';
    document.querySelector(`#sc_t_${side}_sourceConditionFlags`).value='';
    document.querySelector(`#sc_t_${side}_sourceReloadAfter`).value='1';
    document.querySelector(`#sc_t_${side}_packetClass`).value='weapon';
    document.querySelector(`#sc_t_${side}_targetCount`).value='2';
    document.querySelector(`#sc_t_${side}_psi`).value='100';
  }
  document.querySelector('#sc_timedDuration').value='3';
  vm.runInContext('rememberStructuredInputs()',ctx);
  await vm.runInContext('runStructuredComparison()',ctx);
  assert.equal(vm.runInContext('structuredLast.published_reference.timed_scenarios.left.source_proc',ctx),undefined);
  assert.equal(vm.runInContext('structuredLast.published_reference.timed_scenarios.left.modeled_total_damage',ctx),null);
  for(const side of ['left','right']){
    document.querySelector(`#sc_${side}_query`).value='Boom';
    await vm.runInContext(`lookupStructuredCatalog('${side}')`,ctx);
    document.querySelector(`#sc_${side}_options`).value='weapon:kvd-boom-boom';
    vm.runInContext(`structuredChooseCatalog('${side}')`,ctx);
    document.querySelector(`#sc_t_${side}_sourceReloadAfter`).value='';
    document.querySelector(`#sc_t_${side}_sourceRolls`).value='';
    document.querySelector(`#sc_t_${side}_sourceTargets`).value='dummy';
    document.querySelector(`#sc_t_${side}_evidenceMode`).value='preview_simulation';
    document.querySelector(`#sc_t_${side}_packetClass`).value='status';
    document.querySelector(`#sc_t_${side}_psi`).value='100';
  }
  document.querySelector('#sc_timedDuration').value='0.1';
  vm.runInContext('rememberStructuredInputs()',ctx);
  await vm.runInContext('runStructuredComparison()',ctx);
  assert.equal(vm.runInContext('structuredLast.published_reference.timed_scenarios.left.source_proc',ctx),undefined);
  assert.equal(vm.runInContext('structuredLast.published_reference.timed_comparison.status',ctx),'partial_or_unmatched');
  document.querySelector('#sc_t_right_packetClass').value='';
  vm.runInContext('rememberStructuredInputs()',ctx);
  await vm.runInContext('runStructuredComparison()',ctx);
  assert.equal(vm.runInContext('structuredLast.published_reference.timed_scenarios.right.modeled_total_damage',ctx),null);
  for(const side of ['left','right']){
    document.querySelector(`#sc_${side}_query`).value='Against All Odds';
    await vm.runInContext(`lookupStructuredCatalog('${side}')`,ctx);
    document.querySelector(`#sc_${side}_options`).value='mod:boots_mod:against-all-odds-precision';
    vm.runInContext(`structuredChooseCatalog('${side}')`,ctx);
    document.querySelector(`#sc_${side}_level`).value='7';
    vm.runInContext(`structuredLevelChanged('${side}')`,ctx);
    document.querySelector(`#sc_r_${side}_weaponId`).value='weapon:aug-electron-cloud';
    document.querySelector(`#sc_r_${side}_itemPage`).checked=true;
    document.querySelector(`#sc_r_${side}_assumeRpm`).checked=true;
    document.querySelector(`#sc_r_${side}_projectiles`).value='1';
    document.querySelector(`#sc_r_${side}_tier`).value='1';
    document.querySelector(`#sc_r_${side}_stars`).value='1';
    document.querySelector(`#sc_r_${side}_pageReload`).value='2.5';
    document.querySelector(`#sc_t_${side}_sourceMode`).value='';
    document.querySelector(`#sc_t_${side}_packetId`).value='';
    document.querySelector(`#sc_t_${side}_coreNoHpCost`).checked=true;
  }
  document.querySelector('#sc_timedDuration').value='1';
  vm.runInContext('rememberStructuredInputs()',ctx);
  await vm.runInContext('runStructuredComparison()',ctx);
  assert.equal(vm.runInContext('structuredLast.published_reference.timed_scenarios.left.effective_pools_percent.weapon',ctx),12.4);
  assert.equal(vm.runInContext('structuredLast.published_reference.timed_comparison.status',ctx),'partial_or_unmatched');
  assert(document.querySelector('#sc_result').innerHTML.includes('exact_current_field_guide_frame'));
  for(const side of ['left','right']){
    document.querySelector(`#sc_${side}_query`).value='Weapon Amplifier';
    await vm.runInContext(`lookupStructuredCatalog('${side}')`,ctx);
    document.querySelector(`#sc_${side}_options`).value='mod:gloves_mod:weapon-amplifier-aero';
    vm.runInContext(`structuredChooseCatalog('${side}')`,ctx);
    document.querySelector(`#sc_${side}_level`).value='10';
    vm.runInContext(`structuredLevelChanged('${side}')`,ctx);
    await vm.runInContext(`structuredCatalogPreview('${side}')`,ctx);
    assert(document.querySelector(`#sc_t_${side}_coreEffectText`).innerHTML.includes('Weapon DMG +9%'));
    document.querySelector(`#sc_r_${side}_weaponId`).value='weapon:aug-electron-cloud';
    document.querySelector(`#sc_t_${side}_coreEffectText`).value=side==='left'?'Weapon DMG +3%':'Weapon DMG +9%';
    document.querySelector(`#sc_t_${side}_coreNoHpCost`).checked=false;
  }
  document.querySelector('#sc_coreCandidate').checked=true;
  vm.runInContext('rememberStructuredInputs()',ctx);
  await vm.runInContext('runStructuredComparison()',ctx);
  assert.equal(vm.runInContext('structuredLast.published_reference.timed_scenarios.right.effective_pools_percent.weapon-structuredLast.published_reference.timed_scenarios.left.effective_pools_percent.weapon',ctx),6);
  assert.equal(vm.runInContext('structuredLast.published_reference.timed_scenarios.left.modeled_total_damage',ctx),null);
  assert.equal(vm.runInContext('structuredLast.published_reference.timed_scenarios.right.modeled_total_damage',ctx),null);
  for(const side of ['left','right']){
    document.querySelector(`#sc_r_${side}_enemyFraction`).value='1';
    document.querySelector(`#sc_r_${side}_aerialFraction`).value='0';
    document.querySelector(`#sc_t_${side}_enemyBucketModel`).value='independent_multiplicative';
  }
  vm.runInContext('rememberStructuredInputs()',ctx);
  await vm.runInContext('runStructuredComparison()',ctx);
  assert.equal(vm.runInContext('structuredLast.published_reference.timed_scenarios.left.status',ctx),'partial_timed_total');
  assert.equal(vm.runInContext('structuredLast.published_reference.timed_scenarios.right.status',ctx),'partial_timed_total');
  assert.equal(vm.runInContext('structuredLast.published_reference.timed_comparison.status',ctx),'partial_or_unmatched');
  assert(document.querySelector('#sc_result').innerHTML.includes('scenario hypothesis'));
  assert(document.querySelector('#sc_result').innerHTML.includes('Utility lines outside outgoing damage'));
  document.querySelector('#sc_t_left_coreCritIndices').value='0, 2';
  vm.runInContext('rememberStructuredInputs()',ctx);
  assert.equal(JSON.stringify(vm.runInContext('structuredContext().published_reference.timed.left.core_crit_hit_indices',ctx)),
    '[0,2]');
  document.querySelector('#sc_t_left_coreWeakspotCounts').value='18';
  document.querySelector('#sc_t_left_coreAllElementalEvents').checked=true;
  document.querySelector('#sc_t_left_coreTimedStackModel').value='independent';
  document.querySelector('#sc_t_left_coreReloadRefreshModel').value='replace';
  document.querySelector('#sc_t_left_coreKillIndices').value='33';
  document.querySelector('#sc_t_left_coreRefillCapModel').value='per_trigger';
  vm.runInContext('rememberStructuredInputs()',ctx);
  assert.equal(JSON.stringify(vm.runInContext('structuredContext().published_reference.timed.left.core_weakspot_hits_by_magazine',ctx)), '[18]');
  assert.equal(JSON.stringify(vm.runInContext('structuredContext().published_reference.timed.left.core_kill_shot_indices',ctx)), '[33]');
  assert.equal(vm.runInContext('structuredContext().published_reference.timed.left.core_all_elemental_events_modeled',ctx),true);
  assert.equal(vm.runInContext('structuredContext().published_reference.timed.left.core_refill_cap_model',ctx),'per_trigger');
  vm.runInContext('clearStructuredComparison()',ctx);
  const after=await(await fetch(base+'/api/state')).json();assert.deepEqual(after,before,'selection and comparison must not save personal state');
  console.log('Structured Compare search, keyboard, repeated choice, clear/back, API and read-only persistence passed');
 }finally{child.kill();fs.rmSync(temp,{recursive:true,force:true})}
}
main().catch(error=>{console.error(error);process.exitCode=1});
