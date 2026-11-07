const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=require('path').join(__dirname,'..','static','builder-character.js');
const requests=[];
const items={
  'mod:weapon_mod:flame-resonance-general':{id:'mod:weapon_mod:flame-resonance-general',kind:'mod',name:'Flame Resonance General',base_name:'Flame Resonance',variant:'General',slot:'weapon_mod',rarity:'legendary',effect:'Max Burn stack +2, Burn duration -20%',source_observed_level:8},
  'mod:gloves_mod:flame-resonance-general':{id:'mod:gloves_mod:flame-resonance-general',kind:'mod',name:'Flame Resonance General',base_name:'Flame Resonance',variant:'General',slot:'gloves_mod',rarity:'legendary',effect:'Glove effect'},
  'mod:weapon_mod:flame-resonance-burn':{id:'mod:weapon_mod:flame-resonance-burn',kind:'mod',name:'Flame Resonance Burn',base_name:'Flame Resonance',variant:'Burn',slot:'weapon_mod',rarity:'legendary',effect:'Burn effect'}
};
const rows=[{name:'Status DMG',value_percent:6,tier:2,source_status:'published model'},{name:'Burn DMG',value_percent:7,tier:2,condition:'target is Burning'},{name:'Weapon DMG',value_percent:5,tier:2},{name:'Reload Speed',value_percent:4,tier:2}];
const document={addEventListener(){},querySelector(){return null},querySelectorAll(){return []}};
const context={document,window:{},console,setTimeout,clearTimeout,URL,Blob,
  newPlannedBuild(){},openPlannedBuild(){},selectCatalogItem(){},changeSlotSetting(){},
  loadCharacterModGuidance(){},characterPopoverHtml(){},selectCharacterSlot(){},
  catalogEntry:id=>items[id],esc:value=>String(value??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;'),
  api(path){requests.push({method:'POST',path});return Promise.resolve({catalog_id:'mod:weapon_mod:flame-resonance-general'})},
  fetch(url){requests.push({method:'GET',url});const id=decodeURIComponent(url.split('/api/public-mod-detail/')[1].split('?')[0]);const level=Number(new URL(url,'http://local').searchParams.get('level'));return Promise.resolve({ok:true,json:async()=>({catalog_id:id,preview_level:level,core_effect:{text:items[id].effect,status:'catalog_text_level_strength_unconfirmed',source_ref:'https://example.com/mod'},bonus_lines:rows,progression:[{level:1,bonus_lines:[{tier:1},{tier:0},{tier:0},{tier:0}]},{level:8,bonus_lines:[{tier:2},{tier:2},{tier:2},{tier:2}]},{level:17,bonus_lines:[{tier:5},{tier:5},{tier:5},{tier:2}]}],missing:[]})})},
  state:{field_guide_profiles:{personal:{levels:{}},new_player:{levels:{}}},inventory:[]},
  builderData:{entries:Object.values(items),owned_mods:[]},planned:{slots:{}},render(){},notice(){},fail(){},
  builderMods:{},characterModView:'all',characterModGoal:'burn',picker:null};
vm.createContext(context);
vm.runInContext(fs.readFileSync(require('path').join(__dirname,'..','static','mod-reference.js'),'utf8'),context);
vm.runInContext(fs.readFileSync(source,'utf8'),context);
vm.runInContext('modRender=()=>{}',context);
const run=code=>vm.runInContext(code,context);
async function main(){
  const weapon='mod:weapon_mod:flame-resonance-general';
  await run(`fieldGuideCardClick('${weapon}')`);
  let html=run('fieldGuidePanel()');
  assert(html.includes('Flame Resonance <em>&lt;General&gt;</em>'));
  assert(html.includes('MOD CATALOG · WEAPON'));
  assert(html.includes('Max Burn stack +2'));
  assert.equal((html.match(/mod-catalog-row-number/g)||[]).length,4);
  assert(html.includes('When target is Burning'));
  assert(html.includes('Lv 1 · 1 / 0 / 0 / 0')&&html.includes('Lv 17 · 5 / 5 / 5 / 2'));
  assert(!html.includes('PERSONAL PROFILE')&&!html.includes('Save profile')&&!html.includes('Shiny identity')&&!html.includes('Manage my Field Guide record'));
  assert.equal(run("modCatalogRowText({name:'HP',value_percent:null})"),'HP · amount not verified','missing values are never invented');
  assert.equal(run("modCatalogSourceLabel({status:'source_conflict'})"),'Conflicting meanings · current contribution unknown');
  assert(run("modCatalogSourceLabel({source_status:'visually checked current Field Guide frame',native_corroboration:{status:'exact_configured_tooltip_agrees'}})").includes('native E42 tooltip agrees; activation unverified'));
  assert.equal(run("modCatalogSourceLabel({source_status:'native_catalog_configuration_runtime_unverified',source_warning:'Native label differs'})"),'Native source · English label differs');
  assert.equal(run("modCatalogSourceLabel({published_layout_conflict:true,value_percent:3})"),'Held line value · published layout conflicts');
  assert.equal(run("modCatalogSourceLabel({held_published_layout_conflict:true,value_percent:null})"),'Held line value · published layout conflicts');
  assert.equal(run("modCatalogSourceLabel({published_layout_conflict:true,value_percent:null})"),'Published layout conflicts with held line · candidate withheld');
  run("modCatalogDetail={configured_bonus_lines:[{name:'Native label',source_conflict:true,native_configured_candidate:'Damage to all monsters +3%'},{name:'Native agrees',native_corroboration:{status:'recorded_card_text_agrees'},value_percent:null}],bonus_lines:[{name:'Held exact label',value_percent:3,published_layout_conflict:true,status:'observed_value_published_conflict'},{name:'Held line',value_percent:2.4,published_layout_conflict:true,status:'observed_value_published_conflict'}]}");
  assert.equal(run('modCatalogRows(modCatalogDetail)[0].name'),'Native label');
  assert(run('modCatalogRows(modCatalogDetail)[0].raw_text').includes('Native build configuration: Damage to all monsters +3%'));
  assert.equal(run('modCatalogRows(modCatalogDetail)[0].value_percent'),null);
  assert.equal(run('modCatalogRows(modCatalogDetail)[0].held_conflict_text'),'Held exact label +3%');
  assert.equal(run('modCatalogRows(modCatalogDetail)[1].held_published_layout_conflict'),true);
  const packet=JSON.parse(fs.readFileSync(require('path').join(__dirname,'..','evidence_packets','historical-gear-tour-20261101-v1.json')));
  const withFrame=row=>({...row,source_frame:{second:(row.frames||[row.frame])[0].second,url:'/artwork/historical-gear-tour-nov1-'+(row.frames||[row.frame])[0].second+'.png'}});
  const observed={recorded_weapon:{tier:5,stars:6,item_tooltip:packet.equipped_items_at_recording_time[0].tooltip_basic_stats},recorded_gear_summary:packet.temporal_gate.historical_gear_summary,later_nov2_summary:packet.temporal_gate.later_screenshot_summary,equipped_items:packet.equipped_items_at_recording_time.map(withFrame),attached_mods:packet.attached_mods_at_recording_time.map(withFrame),source_frames:{gear_summary:{url:'/artwork/historical-gear-tour-nov1-summary.png'}},mod_application:{server_buff_application_proven:false,required_for_complete_replay:['Equipment item_no and unique item_id','Historical mod_bag_v2[mod_code].total_level','Verified server equip acceptance and buff/affix application']}};
  observed.attached_mods[1].native_frame_candidate={native_frame_code:10,candidate_native_item_nos:[19500442,19505189],newly_typed_graph_targets:[{position:1,native_attributes:[{attr_id:'E02'}]}]};
  run('builderAnalysis='+JSON.stringify({historical_gear_tour_snapshot:{observation:observed,controlled_one_bullet_example:{recorded_item_tooltip_dmg:400,neutral_graph_value:400}},unlinked_character_panel_observation:{observed:{expanded_basic_stats:{attack:20}}}}));
  const historical=run('builderHistoricalGearTourHtml()');
  assert(historical.includes('Nov 1 recorded AUG setup · historical'));
  assert(historical.includes('DMG 400')&&historical.includes('Attack 456')&&historical.includes('Attack 422')&&historical.includes('Basic Attack 20'));
  for(const item of packet.equipped_items_at_recording_time.slice(1))assert(historical.includes(item.name_visible),'armor '+item.name_visible);
  for(const mod of packet.attached_mods_at_recording_time){assert(historical.includes(mod.name_visible),'mod '+mod.name_visible);assert(historical.includes(mod.core_effect_visible),'core '+mod.name_visible);for(const roll of mod.rolls_visible)assert(historical.includes(roll),'roll '+mod.name_visible)}
  assert(historical.includes('Six recorded armor pieces')&&historical.includes('Seven recorded mod cards'));
  assert(historical.includes('Visible attachment does not prove server buff application'));
  assert(historical.includes('Candidate frame 10')&&historical.includes('The filmed variant is not identified')&&historical.includes('targets E02'));
  assert(historical.includes('Equipment item_no and unique item_id')&&historical.includes('mod_bag_v2'));
  assert(historical.includes('0:15')&&historical.includes('0:50')&&historical.includes('native item ID unlinked'));
  assert(historical.includes('does not import them')&&historical.includes('not current damage or DPS'));
  assert(historical.includes('/artwork/historical-gear-tour-nov1-13.png'));
  run('builderAnalysis=null');
  assert.equal(run('builderHistoricalGearTourHtml()'),'');
  const configured={catalog_id:weapon,preview_level:8,configured_status:'exact_native_catalog_configuration',native_buff_graph_review_coverage:{primary_graphs_reviewed:49,all_graphs_with_direct_or_indirect_attribute_target:46,all_effect_only_graphs:3},core_effect:{text:'Max Burn stack +2'},bonus_lines:rows,configured_bonus_lines:[
    {raw_text:'DMG +2.4%',name:'DMG +2.4%',tier:2,source_status:'native_catalog_configuration_runtime_unverified'},
    {raw_text:'Magazine Capacity +4.8%',name:'Magazine Capacity +4.8%',tier:2,source_status:'native_catalog_configuration_runtime_unverified'},
    {raw_text:'Reload Efficiency +3.6%',name:'Reload Efficiency +3.6%',tier:2,source_status:'native_catalog_configuration_runtime_unverified',native_heal_input_configuration:{configured_parent_factor:0.048}},
    {raw_text:'Damage to all monsters +3%',name:'Damage to all monsters +3%',tier:2,source_status:'native_catalog_configuration_runtime_unverified'}],configured_progression:[{level:8,bonus_lines:[{tier:2},{tier:2},{tier:2},{tier:2}]}]};
  configured.published_candidate_conflicts=[
    {position:1,published_name:'All DMG Boost',published_value_percent:2.4,published_source_ref:'https://example.com/published',calculation_status:'excluded_native_source_conflict'},
    {position:3,published_name:'Reload Speed',published_value_percent:3.6,published_source_ref:'https://example.com/published',calculation_status:'excluded_native_source_conflict'},
    {position:4,published_name:'Damage against enemies',published_value_percent:3,published_source_ref:'https://example.com/published',calculation_status:'excluded_native_source_conflict'}];
  run('modCatalogDetail='+JSON.stringify(configured));
  const nativeHtml=run('modCatalogPanel()');
  assert(nativeHtml.includes('Damage to all monsters +3%')&&nativeHtml.includes('Reload Efficiency +3.6%'));
  assert.equal((nativeHtml.match(/excluded from damage calculations/g)||[]).length,3);
  assert(nativeHtml.includes('Published candidate All DMG Boost +2.4% conflicts with this native line'));
  assert(nativeHtml.includes('Published candidate Reload Speed +3.6% conflicts with this native line'));
  assert(nativeHtml.includes('Published candidate Damage against enemies +3% conflicts with this native line'));
  assert(nativeHtml.includes('Disputed published bonus source'));
  assert(!run('modCatalogRows(modCatalogDetail)[1].published_candidate_conflict'));
  assert(!nativeHtml.includes('When target is Burning'));
  assert(nativeHtml.includes('Native configured lines do not prove an owned roll or active buff'));
  assert(nativeHtml.includes('NodeHeal input is max HP × that stored fraction')&&nativeHtml.includes('actual HP restored remain unverified'));
  assert(nativeHtml.includes('Native buff graphs reviewed: 49/49')&&nativeHtml.includes('46 attribute-target paths and 3 effect-node paths'));
  run('modCatalogDetail=null');
  assert.equal(requests.filter(x=>x.method==='POST').length,0,'catalog click stays read-only');
  run('setModCatalogLevel(1)');await new Promise(setImmediate);
  assert(run('fieldGuidePanel()').includes('Four bonus lines · Lv 1'));
  run('setModCatalogLevel(17)');await new Promise(setImmediate);
  run("setModCatalogShiny('shiny')");await new Promise(setImmediate);
  assert(requests.at(-1).url.endsWith('level=17&shiny=1&compact=1'));
  await run("fieldGuideCardClick('mod:gloves_mod:flame-resonance-general')");
  html=run('fieldGuidePanel()');
  assert(html.includes('MOD CATALOG · GLOVES')&&html.includes('Glove effect'));
  await run("fieldGuideCardClick('mod:weapon_mod:flame-resonance-burn')");
  assert(run('fieldGuidePanel()').includes('&lt;Burn&gt;'));
  run("modCatalogDetail={catalog_id:fieldGuideSelection,preview_level:modCatalogLevel,core_effect:{text:null,status:'published_variants_level_unmapped',unbound_variants:[{text:'Status DMG +8% after empty magazine'},{text:'Status DMG +10% after empty magazine'}]},bonus_lines:[],progression:[],missing:[]}");
  html=run('fieldGuidePanel()');
  assert(html.includes('Published effect variants for this exact mod'));
  assert(html.includes('no source maps them to this Field Guide level'));
  assert(html.includes('Status DMG +8%')&&html.includes('Status DMG +10%'));
  assert(!html.includes('Source-checked effect at this level'));
  run("modCatalogDetail={catalog_id:fieldGuideSelection,preview_level:modCatalogLevel,core_effect:{text:'Native source only',status:'catalog_text_level_strength_unconfirmed'},bonus_lines:[{name:'Damage to all monsters',value_percent:3,tier:2,status:'exact_native_catalog_configuration',source_status:'native_catalog_configuration_runtime_unverified',source_warning:'Native source means damage to all monsters. Runtime target application is unverified.',recorded_english_label:'All DMG Boost'}],progression:[],missing:[]}");
  html=run('fieldGuidePanel()');
  assert(html.includes('Damage to all monsters'));
  assert(html.includes('Recorded card label: All DMG Boost'));
  assert(html.includes('Native source · English label differs'));
  run("modCatalogDetail={catalog_id:fieldGuideSelection,preview_level:modCatalogLevel,core_effect:{text:'Each Shrapnel body part +15%, cap +45%',status:'catalog_text_level_strength_unconfirmed'},native_main_effect:{effect_ranks:[{effect_rank:1,shrapnel_damage_per_body_part_percent:3,cap_percent:9},{effect_rank:5,shrapnel_damage_per_body_part_percent:15,cap_percent:45}],standard_tooltip_effect_rank:5,preview_shiny:true,shiny_separate_effect:{shrapnel_damage_percent:5}},bonus_lines:[],progression:[],missing:[]}");
  html=run('fieldGuidePanel()');
  assert(html.includes('rank 1: +3% per body part, cap +9%'));
  assert(html.includes('Shiny has a separate +5% Shrapnel DMG source line'));
  assert(html.includes('native total levels 7–8 to rank 4 and 9–17 to rank 5'));
  assert(html.includes('not proven to be the Field Guide badge level'));
  assert(html.includes('not applied to the calculation'));
  await run(`fieldGuideCardClick('${weapon}')`);
  assert.equal(requests.filter(x=>x.method==='POST').length,0);
  run('openFieldGuideRecords()');
  await run(`fieldGuideCardClick('${weapon}')`);
  assert(run('fieldGuidePanel()').includes('Save profile level'),'profile editor remains in its dedicated context');
  run('closeModProfileEditor()');
  assert(!run('fieldGuidePanel()').includes('Save profile level'));
  console.log('Mod catalog detail preview passed');
}
main().catch(error=>{console.error(error);process.exitCode=1});
