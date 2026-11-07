const fs=require('fs'),vm=require('vm'),assert=require('assert');
const elements=new Map();
const element=id=>{if(!elements.has(id))elements.set(id,{value:'',checked:false,innerHTML:'',textContent:'',setAttribute(){}});return elements.get(id)};
let resolveRequest,requestBody,route;
const ctx={
 state:{planned_builds:[{id:'plan',name:'Current plan',slots:{primary:{catalog_id:'weapon:aug-electron-cloud',tier:4}}}],video_import_proposals:[]},
 document:{querySelector:element},$:element,val:id=>element('#'+id).value,
 num:id=>{const value=element('#'+id).value;return value===''?null:Number(value)},
 esc:value=>String(value??'').replaceAll('<','&lt;').replaceAll('>','&gt;'),
 augFmt:value=>String(value??'—'),
 api:(path,body)=>new Promise(resolve=>{route=path;requestBody=body;resolveRequest=resolve})
};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync('static/combat_formula_ui.js','utf8'),ctx);
const html=vm.runInContext('combatFormulaCard()',ctx);
assert(html.includes('Explain selected build')&&html.includes('id="cf-Coverage"'));
const existing=vm.runInContext(`cfCoverageHtml({items:[{kind:'mod',slot:'primary',name:'Shock Rampage',level:17,owned_instance_id:'shock17',status:'missing_evidence',rows:[],existing_evidence:{source_ref:'libfile_84a17de486208191951ea249c448e8c6',source_name:'image(20261024-114335).png',core_effect:'Trigger +5%',typed_preview:[{raw_text:'Power Surge DMG +6%',stat_type:'power_surge_damage_percent',visible_magnitude:6,calculation_status:'unmodeled',tech_activation:'unknown',confidence:'ocr_unverified'}]}}],row_counts:{},activation_counts:{},missing_mod_items:1,next_action:'Review existing evidence',next_action_kind:'review_existing_evidence'})`,ctx);
assert(existing.includes('Review existing evidence')&&existing.includes('cf-existing-evidence'));
assert(existing.includes('Power Surge DMG +6%')&&existing.includes('Tech unknown'));
assert(existing.includes('Applying evidence requires a separate source-checked review'));
assert(!existing.includes('onclick="applyVideoEvidence'), 'read-only preview cannot Apply');
const withImage=vm.runInContext(`cfExistingEvidenceHtml({name:'Shock Rampage',level:17,owned_instance_id:'shock17',existing_evidence:{source_ref:'libfile_84a17de486208191951ea249c448e8c6',source_name:'image(20261024-114335).png',image_url:'/media/evidence/shock-rampage-power-surge-lv17-2d4bd6b5.png',attribute_lines:['All DMG Boost +3%'],typed_preview:[],transcription_note:'The stored wording is abbreviated.'}},0)`,ctx);
assert(withImage.includes('cf-source-image')&&withImage.includes('Open full original'));
assert(withImage.includes('stored wording is abbreviated')&&!withImage.includes('in-app image preview is unavailable'));
const oneRow=vm.runInContext(`cfExistingEvidenceHtml({name:'Health Guard',slot:'helmet',catalog_id:'mod:helmet_mod:health-guard-general',level:9,owned_instance_id:'hp-one',existing_evidence:{source_ref:'media/local-hp.png',attribute_lines:['Max HP +2.4%'],typed_preview:[{raw_text:'Max HP +2.4%',stat_type:'max_hp_percent',visible_magnitude:2.4,calculation_status:'assumption_scenario',tech_activation:'unknown',confidence:'source_checked'}]}},1,'plan')`,ctx);
assert(oneRow.includes('1 recorded line is')&&!oneRow.includes('four rows')&&!oneRow.includes('Power Surge')&&!oneRow.includes('ChatGPT Library'));
const reversedRows=vm.runInContext(`cfExistingEvidenceHtml(${JSON.stringify({name:'Health Guard',slot:'helmet',catalog_id:'mod:helmet_mod:health-guard-general',level:9,owned_instance_id:'hp-one',row_order_discrepancy:{unique_content_count:2,observed_attribute_lines:['Max HP +2.4%','Weapon DMG +5%'],tooltip_attribute_lines:['Weapon DMG +5%','Max HP +2.4%'],observed_source:'frame-a',tooltip_source:'frame-b'},existing_evidence:{source_ref:'frame-b',attribute_lines:['Weapon DMG +5%','Max HP +2.4%'],typed_preview:[]}})},1,'plan')`,ctx);
assert(reversedRows.includes('Source disagreement · 2 distinct recorded positions'));
assert(reversedRows.includes('Saved observation · frame-a')&&reversedRows.includes('Tooltip · frame-b'));
assert(reversedRows.includes('Neither version is applied to calculations'));
const changedRows=vm.runInContext(`cfExistingEvidenceHtml(${JSON.stringify({name:'Health Guard',slot:'helmet',catalog_id:'mod:helmet_mod:health-guard-general',level:9,owned_instance_id:'hp-one',row_order_discrepancy:{unique_content_count:3,observed_attribute_lines:['Weapon DMG +5%','Reload Efficiency +3.6%'],tooltip_attribute_lines:['Weapon DMG +5%','Reload Efficiency +4.1%'],observed_source:'frame-a',tooltip_source:'frame-b'},existing_evidence:{source_ref:'frame-b',attribute_lines:['Weapon DMG +5%','Reload Efficiency +4.1%'],typed_preview:[]}})},1,'plan')`,ctx);
assert(changedRows.includes('Source disagreement · 3 distinct recorded positions'));
assert(changedRows.includes('Reload Efficiency +3.6%')&&changedRows.includes('Reload Efficiency +4.1%'));
const laterTarget={owned_instance_id:'hp-one',slot:'helmet',catalog_id:'mod:helmet_mod:health-guard-general',level:9,source_ref:'media/local-hp.png'};
const multi=vm.runInContext(`cfCoverageHtml(${JSON.stringify({build_id:'plan',items:[{kind:'mod',slot:'primary',name:'Shock Rampage',catalog_id:'mod:weapon_mod:shock-rampage-power-surge',level:17,owned_instance_id:'shock17',status:'missing_evidence',rows:[],existing_evidence:{source_ref:'libfile_source',typed_preview:[]}},{kind:'mod',slot:'helmet',name:'Health Guard',catalog_id:laterTarget.catalog_id,level:9,owned_instance_id:'hp-one',status:'missing_evidence',rows:[],existing_evidence:{source_ref:laterTarget.source_ref,typed_preview:[]}}],next_action_kind:'review_existing_evidence',next_action:'Review Health Guard',next_action_target:laterTarget})})`,ctx);
assert(multi.includes('data-owned-id="hp-one"')&&multi.includes('data-mod-id="mod:helmet_mod:health-guard-general"'));
ctx.state.planned_builds[0].slots.primary.mod_id='mod:weapon_mod:shock-rampage-power-surge';
ctx.state.planned_builds[0].slots.helmet={mod_id:laterTarget.catalog_id,mod_level:9,mod_inventory_id:'hp-one'};
element('#cf-Build').value='plan';
const firstNode={dataset:{buildId:'plan',ownedId:'shock17',slot:'primary',modId:'mod:weapon_mod:shock-rampage-power-surge',level:'17',sourceRef:'libfile_source'},open:false,scrollIntoView(){}};
const laterNode={dataset:{buildId:'plan',ownedId:'hp-one',slot:'helmet',modId:laterTarget.catalog_id,level:'9',sourceRef:laterTarget.source_ref},open:false,scrollIntoView(){}};
ctx.document.querySelectorAll=()=>[firstNode,laterNode];
assert.equal(vm.runInContext(`cfOpenExistingEvidence({dataset:${JSON.stringify(laterNode.dataset)}})`,ctx),true);
assert.equal(firstNode.open,false,'later target must not open first preview');
assert.equal(laterNode.open,true);
laterNode.open=false;ctx.state.planned_builds[0].slots.helmet.mod_id='different-mod';
assert.equal(vm.runInContext(`cfOpenExistingEvidence({dataset:${JSON.stringify(laterNode.dataset)}})`,ctx),false,'stale selected target rejected');
assert.equal(laterNode.open,false);
const emptyMod=vm.runInContext(`cfCoverageHtml({items:[],row_counts:{},activation_counts:{},missing_mod_items:0,next_action:'Select an owned mod',next_action_kind:'select_mod'})`,ctx);
assert(emptyMod.includes('Select a mod')&&!emptyMod.includes('cf-existing-evidence'));
element('#cf-ActiveWeapon').value='primary';
const orderedActions=vm.runInContext(`cfCoverageHtml({items:[
 {kind:'weapon',slot:'primary',name:'AUG',status:'missing_baseline',rows:[],next_action:'Enter the baseline'},
 {kind:'mod',slot:'primary',name:'Shock Rampage',status:'missing_evidence',rows:[],next_action:'Review existing evidence'}
],row_counts:{},activation_counts:{},missing_mod_items:1,next_action:'Review existing evidence for this exact mod',next_action_kind:'review_existing_evidence',next_action_target:{owned_instance_id:'shock17',slot:'primary',catalog_id:'mod:weapon_mod:shock-rampage-power-surge',level:17,source_ref:'frame-a'},build_id:'plan'})`,ctx);
assert(orderedActions.includes('Next action:</b> Enter and confirm pre-mod damage'));
assert(orderedActions.includes('<summary>After that: Review existing evidence for this exact mod'));
assert(orderedActions.includes('<b>Later:</b> Review existing evidence'));
assert(!orderedActions.includes('Next action:</b> Review existing evidence for this exact mod'));
element('#cf-Build').value='plan';
element('#cf-ActiveWeapon').value='primary';
element('#cf-Baseline').value='manual';
element('#cf-Scenario').value='isles_of_abyss';
vm.runInContext('cfGuideUpdate()',ctx);
element('#cf-Damage').value='213';
element('#cf-RPM').value='720';
element('#cf-Mag').value='40';
element('#cf-PreMod').checked=true;
for(const invalid of ['0','201','1.5','not-a-number']){
 element('#cf-MagLandedHits').value=invalid;
 vm.runInContext('loadBuildCoverage()',ctx);
 assert(element('#cf-Coverage').innerHTML.includes('1–200 whole landed hits'),invalid+' must be rejected before API submission');
}
element('#cf-MagLandedHits').value='';
const pending=vm.runInContext('loadBuildCoverage()',ctx);
assert.equal(requestBody.magazine_hypothesis.landed_hits,null,'cleared field cannot silently submit 40');
assert.equal(route,'build-contribution-coverage');
assert.equal(requestBody.build_id,'plan');
assert.equal(requestBody.tech_policy,'exclude_unknown');
assert.equal(requestBody.all_damage_model,'exclude_unverified');
assert.equal(requestBody.manual_baseline.damage,213);
assert.equal(requestBody.manual_baseline.rpm,720);
assert.equal(requestBody.manual_baseline.magazine,40);
assert.equal(requestBody.manual_baseline.confirmed_pre_mod,true);
assert.equal(vm.runInContext("cfCoverageLabel('included_what_if','verified_active')",ctx),'Included · Tech verified active');
assert.equal(vm.runInContext("cfCoverageLabel('included_what_if','assumed_active')",ctx),'Included only if Tech assumed active');
assert.equal(vm.runInContext("cfCoverageLabel('tech_verified_inactive')",ctx),'Verified inactive at this Tech level');
resolveRequest({items:[
 {kind:'weapon',slot:'primary',name:'AUG',status:'not_modeled',rows:[{text:'pre-mod unknown',status:'missing_baseline'}]},
 {kind:'mod',slot:'primary',name:'Shock Rampage',status:'partial',rows:[
   {text:'Weapon DMG +5%',status:'included_what_if',activation_status:'assumed_active',source:'frame-a'},
   {text:'Unknown proc',status:'unmodeled',source:'frame-b'}]}
 ],row_counts:{included_what_if:1,unmodeled:1},activation_counts:{assumed_active:1},missing_mod_items:0,
 next_action:'Capture exact source.',scope:'Selected plan only.'});
pending.then(()=>{
 const output=element('#cf-Coverage').innerHTML;
 assert(output.includes('Weapon DMG +5%')&&output.includes('Unknown proc'));
 assert(output.includes('Cold / warm preview skipped'),'blank hit count must be visible as omitted');
 assert(output.includes('An included row does not make its whole item'));
 assert(output.includes('pre-mod unknown')&&output.includes('Capture exact source.'));
 assert(output.includes('<details>')&&output.includes('frame-a'));
 assert(output.includes('Included only if Tech assumed active'));
 assert(output.includes('0 Tech verified, 1 Tech assumed'));
 element('#cf-Coverage').innerHTML='<p>old explanation</p>';
 vm.runInContext('invalidateCombatFormula()',ctx);
 assert(element('#cf-Coverage').innerHTML.includes('refresh this breakdown'));
 const stale=vm.runInContext('loadBuildCoverage()',ctx);
 element('#cf-Build').value='';
 vm.runInContext('cfGuideUpdate()',ctx);
 assert.equal(element('#cf-Damage').value,'','build change clears A values before stale response arrives');
 resolveRequest({items:[],row_counts:{},missing_mod_items:0});
 return stale;
}).then(()=>{
 assert(!element('#cf-Coverage').innerHTML.includes('Selected plan only.'));
 element('#cf-Build').value='plan';
 vm.runInContext('cfGuideUpdate()',ctx);
 element('#cf-Coverage').innerHTML='<p>old assumptions</p>';
 element('#cf-TechAssume').checked=true;
 element('#cf-AllDamageHypothesis').checked=true;
 const oldAssumptions=vm.runInContext('loadBuildCoverage()',ctx);
 assert.equal(requestBody.tech_policy,'assume_active');
 vm.runInContext('fillCombatExample()',ctx);
 assert.equal(element('#cf-TechAssume').checked,false);
 assert.equal(element('#cf-AllDamageHypothesis').checked,false);
 assert(element('#cf-Coverage').innerHTML.includes('refresh this breakdown'));
 resolveRequest({items:[],row_counts:{},missing_mod_items:0,scope:'stale assumed source'});
 return oldAssumptions;
}).then(()=>{
 assert(!element('#cf-Coverage').innerHTML.includes('stale assumed source'));
 ctx.state.planned_builds.push({id:'other-plan',name:'Other tier',slots:{primary:{catalog_id:'weapon:aug-electron-cloud',tier:3,stars:5}}});
 vm.runInContext('cfGuideUpdate()',ctx);
 element('#cf-Damage').value='213';element('#cf-RPM').value='720';element('#cf-Mag').value='40';element('#cf-PreMod').checked=true;
 element('#cf-Build').value='other-plan';vm.runInContext('cfGuideUpdate()',ctx);
 assert.equal(element('#cf-Damage').value,'');
 assert.equal(element('#cf-PreMod').checked,false);
 const explained=vm.runInContext('loadBuildCoverage()',ctx);
 assert.equal(requestBody.build_id,'other-plan');
 assert.equal(requestBody.manual_baseline.damage,null,'Explain cannot reuse previous build damage');
 assert.equal(requestBody.manual_baseline.confirmed_pre_mod,false);
 resolveRequest({items:[],row_counts:{},missing_mod_items:0});
 return explained.then(()=>vm.runInContext('runCombatFormula()',ctx));
}).then(()=>{
 assert(element('#cf-Results').innerHTML.includes('Confirm that manual weapon inputs are pre-mod'),
   'formula also refuses the prior build baseline until fresh confirmation');
 console.log('Build coverage UI passed: selected items, Tech states, manual provenance and stale response guards');
}).catch(error=>{console.error(error);process.exitCode=1});
