/* Visual planned-build editor. Catalog identities and ownership remain separate. */
let builderData=null,planned={id:null,name:'New planned build',notes:'',slots:{}},picker=null,builderFilter='all',builderQuery='',builderFamily='all',builderDetail=null,builderSwap='';
const builderTabs=[['Weapon','primary'],['Helmet','helmet'],['Top','top'],['Bottoms','bottoms'],['Shoes','shoes'],['Gloves','gloves'],['Mask','mask']];
const builderSlots=[['primary','Primary weapon'],['secondary','Secondary weapon'],['melee','Melee weapon'],['helmet','Helmet'],['top','Top'],['bottoms','Bottoms'],['shoes','Shoes'],['gloves','Gloves'],['mask','Mask']];
const builderArmor={helmet:'helmet',top:'chest',bottoms:'pants',shoes:'boots',gloves:'gloves',mask:'mask'};
const builderMods={primary:'weapon_mod',secondary:'weapon_mod',helmet:'helmet_mod',top:'chest_mod',bottoms:'pants_mod',shoes:'boots_mod',gloves:'gloves_mod',mask:'mask_mod'};
function plannedBuildChoiceLabels(builds){
  const names=new Map(),labels={};
  for(const build of builds)names.set(build.name,(names.get(build.name)||0)+1);
  const context=build=>{
    const weapon=build.slots?.primary||{};
    if(!weapon.catalog_id)return 'No primary weapon';
    const entry=builderData?.entries?.find(item=>item.id===weapon.catalog_id);
    const weaponName=entry?.name||weapon.catalog_id.replace(/^weapon:/,'').replaceAll('-', ' ');
    const tier=weapon.tier==null?'tier unknown':`Tier ${['','I','II','III','IV','V'][Number(weapon.tier)]||weapon.tier}`;
    const stars=weapon.stars==null?'stars unknown':`${weapon.stars}★`;
    return `${weaponName} · ${tier} · ${stars}`;
  };
  const repeated=new Map();
  for(const build of builds){
    const label=names.get(build.name)>1?`${build.name} · ${context(build)}`:build.name;
    repeated.set(label,(repeated.get(label)||0)+1);
    labels[build.id]=label;
  }
  for(const build of builds)if(repeated.get(labels[build.id])>1)labels[build.id]+=` · ${String(build.id).slice(0,6)}`;
  return labels;
}
async function ensureBuilder(){if(builderData)return;builderData=await(await fetch('/api/builder-catalog')).json()}
function catalogEntry(id){return builderData?.entries.find(e=>e.id===id)}
function entryArt(e,small=false){return e?.artwork?`<img class="game-art ${small?'small-art':''}" src="${esc(e.artwork)}" alt="${esc(e.name)} artwork">`:`<div class="art-missing ${small?'small-art':''}">${e?'Artwork unavailable':'Empty slot'}</div>`}
function ownedLabel(e){return e?.ownership_conflict?'Confirmed unlock; lock declaration conflicts':e?.ownership==='unlocked'?'Owned / unlocked':e?.ownership==='locked'?'Confirmed locked':'Ownership unknown'}
function builderPage() {
  if (!builderData)return '<div class="card">Loading the visual catalog…</div>';
  const filled=Object.values(planned.slots).filter(s=>s.catalog_id).length;
  const choiceLabels=plannedBuildChoiceLabels(builderData.planned_builds);
  return `<div class="builder-start"><div><div class="kicker">DEVIANT FORGE · FIELD GUIDE BUILDER</div><h2>Build your setup</h2><p>Choose equipment from the catalog. Edit selected upgrades beside each item.</p></div><div class="actions"><button class="primary" onclick="newPlannedBuild()">Build manually</button><button class="secondary" onclick="go('import')">Import screenshots or video</button></div></div><div class="builder-toolbar"><label>Build name<input id="plannedName" value="${esc(planned.name)}" oninput="planned.name=this.value"></label><label>Open saved build<select id="savedBuildPicker" aria-label="Open saved build" onchange="if(this.value)openPlannedBuild(this.value)"><option value="">Choose a saved build…</option>${builderData.planned_builds.map(b=>`<option value="${esc(b.id)}" ${b.id===planned.id?'selected':''}>${esc(choiceLabels[b.id])}</option>`).join('')}</select></label><span class="muted small">${filled} / ${builderSlots.length} slots</span><div class="actions"><button class="primary" onclick="savePlannedBuild()">Save build</button><button class="secondary" onclick="duplicatePlannedBuild()">Duplicate</button><button class="secondary" onclick="comparePlannedBuilds()">Compare</button></div></div><div class="builder-layout"><section class="setup-rail"><h2 class="rail-title">Equipped setup</h2><div class="builder-slots">${builderSlots.map(([slot,label])=>slotCard(slot,label)).join('')}</div></section><section class="builder-browser">${picker?pickerHtml():'<div class="card picker-prompt"><h2>Choose a slot</h2><p>Click any gear or mod space in your build to open its compatible catalog.</p></div>'}</section></div><div id="builderCompare"></div>`;
}

function settingSelect(slot,key,label,value,values) {
  return `<label class="slot-setting">${label}<select aria-label="${esc(label)} for ${esc(slot)}" onchange="changeSlotSetting('${slot}','${key}',this.value)">${values.map(([v,text])=>`<option value="${esc(v)}" ${String(value??'')===String(v)?'selected':''}>${esc(text)}</option>`).join('')}</select></label>`;
}
function maxBlueprintStars(rarity) {
  return {legendary:6,epic:5,rare:4,fine:4,uncommon:3,common:3}[String(rarity||'').toLowerCase()]||6;
}
function verifiedBlueprintStarLimit(entry){
  return builderData?.verified_star_limits?.[entry?.id]||null;
}
function selectableBlueprintStarMax(entry){return verifiedBlueprintStarLimit(entry)?.max??maxBlueprintStars(entry?.rarity)}
function maxLegacyEnhancement(rarity) {
  return {legendary:10,epic:7,rare:4,fine:4,uncommon:3,common:3}[String(rarity||'').toLowerCase()]||10;
}
function gearSettingsHtml(slot,selection) {
  const tier=settingSelect(slot,'tier','Craft tier',selection.tier??'',[['','Not set'],...[1,2,3,4,5].map(n=>[n,'Tier '+['','I','II','III','IV','V'][n]])]);
  const entry=catalogEntry(selection.catalog_id),rarity=entry?.rarity;
  const sourced=verifiedBlueprintStarLimit(entry),cap=selectableBlueprintStarMax(entry);
  const starValues=[['','Not set'],...[1,2,3,4,5,6].filter(n=>n<=cap).map(n=>[n,'★ '+n])];
  if (selection.stars>cap)starValues.push([selection.stars,sourced?'Saved ★ '+selection.stars+' · exceeds sourced max '+cap:'Saved ★ '+selection.stars+' · verify']);
  const stars=settingSelect(slot,'stars','Blueprint stars',selection.stars||'',starValues);
  const weapon=['primary','secondary','melee'].includes(slot);
  const legacyCap=maxLegacyEnhancement(rarity);
  const legacyValues=[['','None / current'],...Array.from({length:legacyCap+1},(_,n)=>[n,'+'+n])];
  if(selection.legacy_enhancement>legacyCap)legacyValues.push([selection.legacy_enhancement,'Saved +'+selection.legacy_enhancement+' · verify']);
  return `<div class="gear-settings" aria-label="${esc(slot)} upgrade settings">${tier}${stars}${weapon?`<label class="slot-setting wide">Calibration blueprint<input aria-label="Calibration blueprint for ${esc(slot)}" placeholder="Style / blueprint name, if used" maxlength="160" value="${esc(selection.calibration_blueprint||'')}" onchange="changeSlotSetting('${slot}','calibration_blueprint',this.value)"></label><label class="slot-setting wide">Calibration roll / bonus<input aria-label="Calibration roll or bonus for ${esc(slot)}" placeholder="Record the actual roll; calculation unknown" maxlength="160" value="${esc(selection.calibration_bonus||'')}" onchange="changeSlotSetting('${slot}','calibration_bonus',this.value)"></label>${selection.catalog_id==='weapon:aug-electron-cloud'?'<p class="setting-hint">AUG Electron Cloud launched after the January 2026 removal of new calibration-level upgrades; no legacy +0…+10 setting applies.</p>':settingSelect(slot,'legacy_enhancement','Legacy enhancement',selection.legacy_enhancement??'',legacyValues)}<p class="setting-hint">Enhancement is for weapons retained from before the 2026 removal. Tier, stars, and calibration rolls are saved; their damage values remain unknown.</p>`:`<p class="setting-hint">Tier and blueprint stars are saved; resulting armor stats remain unknown.</p>`}<p class="setting-hint">${sourced?`This exact blueprint's published maximum is ${sourced.max}★. ${selection.stars>sourced.max?'Saved selection exceeds that maximum; it remains visible until you correct it.':'The limit applies only to this named blueprint.'} Source: ${esc(sourced.url)}`:'Blueprint star choices reflect catalog rarity; an item-specific maximum has not been verified.'}</p>${selection.level!=null?`<details class="legacy-field"><summary>Earlier saved field</summary>Legacy equipment level ${esc(selection.level)} is preserved but has no current calculation meaning.</details>`:''}</div>`;
}
function slotCard(slot,label) {
  const s=planned.slots[slot]||{},gear=catalogEntry(s.catalog_id),mod=catalogEntry(s.mod_id);
  return `<div class="equip-slot ${picker?.slot===slot?'focus':''}"><div class="slot-heading"><b>${esc(label)}</b>${gear?`<button class="text-button" onclick="removePlanned('${slot}')">Remove gear</button>`:''}</div><button class="gear-pick" onclick="openPicker('${slot}','gear')">${entryArt(gear)}<span><b>${esc(gear?.name||'Choose '+label.toLowerCase())}</b><small>${gear?`${esc(gear.rarity||'rarity unknown')} · Tier ${s.tier??'not set'} · ★ ${s.stars||'not set'}`:'Browse all equipment'}</small><small>${gear?ownedLabel(gear):''}</small></span><span class="pick-action">${gear?'Replace':'Add'}</span></button>${gear?gearSettingsHtml(slot,s):''}${builderMods[slot]?`<div class="mod-line"><button class="mod-pick" ${gear?'':'disabled title="Choose gear first"'} onclick="openPicker('${slot}','mod')">${entryArt(mod,true)}<span><b>${esc(mod?.base_name||'Attach compatible mod')}</b><small>${mod?`${esc(mod.variant||'Base')} · ${ownedLabel(mod)}`:'No mod attached'}</small></span><span class="pick-action">${mod?'Replace':'Attach'}</span></button>${mod?`<label class="mod-level">Mod level<input aria-label="${esc(label)} mod level" type="number" min="1" max="17" step="1" value="${esc(s.mod_level??1)}" onchange="changeSlotSetting('${slot}','mod_level',this.value)"></label><label class="mod-level"><input aria-label="${esc(label)} Shiny mod" type="checkbox" ${s.mod_shiny?'checked':''} onchange="changeSlotSetting('${slot}','mod_shiny',this.checked)"> Shiny card</label>`:''}</div>${mod?`<button class="text-button" onclick="removePlannedMod('${slot}')">Remove mod</button>`:''}`:''}</div>`;
}
function changeSlotSetting(slot,key,value) {
  const selected=planned.slots[slot];if(!selected?.catalog_id)return;
  if ((key==='mod_level'||key==='mod_shiny')&&!selected.mod_id)return;
  if (selected.catalog_id==='weapon:aug-electron-cloud'&&key==='legacy_enhancement'){notice('AUG has no pre-2026 legacy calibration upgrade');return;}
  if (key==='mod_shiny') {
    selected.mod_shiny=Boolean(value);
  } else if (key==='calibration_blueprint'||key==='calibration_bonus') {
    if (!['primary','secondary','melee'].includes(slot))return;
    selected[key]=String(value).trim().slice(0,160);
  } else if (['legacy_enhancement','tier','stars'].includes(key)&&value==='') {
    delete selected[key];
  } else {
    if (String(value).trim()==='')return;
    const entry=catalogEntry(selected.catalog_id),rarity=entry?.rarity;
    const n=Number(value),max=key==='mod_level'?17:key==='tier'?5:key==='stars'?selectableBlueprintStarMax(entry):key==='legacy_enhancement'?maxLegacyEnhancement(rarity):NaN;
    const min=key==='stars'||key==='legacy_enhancement'?0:1;
    if (!Number.isInteger(n)||n<min||n>max) {notice('Enter a supported '+key.replaceAll('_',' ')+' value');return;}
    selected[key]=n;
  }
  if (builderDetail?.id===(key==='mod_level'?selected.mod_id:selected.catalog_id) && key==='mod_level')builderDetail.level=selected.mod_level;
  render();
  if (key==='mod_level'&&builderDetail?.id===selected.mod_id)loadBuilderDetail(selected.mod_id);
}

function newPlannedBuild(){planned={id:null,name:'New planned build',notes:'',slots:{}};picker=null;builderSwap='';render()}
function openPlannedBuild(id){let b=builderData.planned_builds.find(x=>x.id===id);if(!b)return;planned={id:b.id,name:b.name,notes:b.notes||'',slots:structuredClone(b.slots)};picker=null;builderSwap='';render();notice('Planned build reopened')}
async function savePlannedBuild(){try{let name=($('#plannedName')?.value||planned.name).trim();let result=await api('planned-build',{id:planned.id,name,notes:planned.notes,slots:planned.slots});planned.id=result.id;planned.name=name;builderData.planned_builds=await(await fetch('/api/builder-catalog')).json().then(x=>x.planned_builds);render();notice('Planned build saved; ownership unchanged')}catch(e){fail(e)}}
function duplicatePlannedBuild(){planned={...structuredClone(planned),id:null,name:planned.name+' copy'};render();notice('Copy ready to save')}
function removePlanned(slot){delete planned.slots[slot];builderSwap='';render()}
function removePlannedMod(slot){if(!planned.slots[slot])return;delete planned.slots[slot].mod_id;delete planned.slots[slot].mod_level;delete planned.slots[slot].mod_shiny;builderSwap='';render()}
function openPicker(slot,mode){if(mode==='mod'&&!planned.slots[slot]?.catalog_id)return;picker={slot,mode,tab:slot==='secondary'?'primary':slot==='melee'?'primary':slot};builderFamily='all';builderQuery='';builderDetail=null;render()}
function pickerTab(tab){if(!picker)return;picker.tab=tab;picker.slot=tab==='primary'?(picker.slot==='secondary'?'secondary':picker.slot==='melee'?'melee':'primary'):tab;if(picker.mode==='mod'&&!planned.slots[picker.slot]?.catalog_id)picker.mode='gear';builderFamily='all';builderQuery='';builderDetail=null;render()}
function filteredPicker(){if(!picker)return[];let slot=picker.slot,kind=picker.mode==='mod'?'mod':slot in builderArmor?'armor':'weapon';let required=kind==='mod'?builderMods[slot]:kind==='armor'?builderArmor[slot]:null;return builderData.entries.filter(e=>e.kind===kind&&(!required||e.slot===required)&&(kind!=='weapon'||(slot==='melee'?e.family==='melee':e.family!=='melee'))&&(builderFilter==='all'||e.ownership==='unlocked')&&(!builderQuery||[e.name,e.base_name,e.variant,e.family,e.set_name].some(x=>String(x||'').toLowerCase().includes(builderQuery.toLowerCase()))))}
function groupName(e){return e.kind==='mod'?e.tree||e.base_name:e.kind==='armor'?e.set_name||'Individual armor':e.weapon_category||'Weapon category unverified'}
function pickerHtml(){let all=filteredPicker(),families=[...new Set(all.map(groupName))].sort((a,b)=>a.localeCompare(b)),shown=builderFamily==='all'?all:all.filter(e=>groupName(e)===builderFamily),groups=Object.groupBy?Object.groupBy(shown,groupName):shown.reduce((m,e)=>((m[groupName(e)]??=[]).push(e),m),{});return `<div class="picker-head"><div class="kicker">${picker.mode==='mod'?'FIELD GUIDE MODS':'EQUIPMENT CATALOG'} · ${esc(picker.slot.toUpperCase())}</div><div class="builder-tabs">${builderTabs.map(([label,tab])=>`<button class="${picker.tab===tab?'active':''}" onclick="pickerTab('${tab}')">${label}</button>`).join('')}</div><div class="picker-controls"><div class="tabs"><button class="${picker.mode==='gear'?'active':''}" onclick="openPicker('${picker.slot}','gear')">Equipment</button><button class="${picker.mode==='mod'?'active':''}" ${builderMods[picker.slot]?'':'disabled'} onclick="openPicker('${picker.slot}','mod')">Mods</button></div><div class="tabs"><button class="${builderFilter==='all'?'active':''}" onclick="setBuilderFilter('all')">All items</button><button class="${builderFilter==='mine'?'active':''}" onclick="setBuilderFilter('mine')">My items</button></div><input id="builderSearch" aria-label="Search catalog" placeholder="Search names, variants, sets…" value="${esc(builderQuery)}" oninput="builderQuery=this.value;updatePickerResults()"><select id="builderFamily" onchange="builderFamily=this.value;updatePickerResults()"><option value="all">All families / sets</option>${families.map(f=>`<option value="${esc(f)}" ${f===builderFamily?'selected':''}>${esc(f)}</option>`).join('')}</select></div><p class="small muted">${shown.length} choices · ${builderFilter==='mine'?'confirmed unlocked only':'ownership may be unknown'} · ${esc(JSON.stringify(builderData.artwork_coverage))}</p>${builderSwap?`<p class="note">${esc(builderSwap)}</p>`:''}</div><div id="builderDetail">${builderDetail?detailHtml(builderDetail):''}</div><div id="pickerResults">${pickerResults(shown,groups)}</div>`}
function pickerResults(shown,groups){if(!shown.length)return empty('No matching items','Try All items, another family, or a different search.');return Object.entries(groups).sort(([a],[b])=>a.localeCompare(b)).map(([family,entries])=>`<section class="mod-family"><h3>${esc(family)}</h3><div class="icon-grid">${entries.sort((a,b)=>(a.base_name||a.name).localeCompare(b.base_name||b.name)||(a.variant||'').localeCompare(b.variant||'')).map(e=>entryCard(e)).join('')}</div></section>`).join('')}
function entryCard(e){let activeSelection=Object.values(planned.slots).find(s=>s.catalog_id===e.id||s.mod_id===e.id),active=Boolean(activeSelection),locked=e.ownership==='locked',level=activeSelection?(e.kind==='mod'?activeSelection.mod_level:activeSelection.tier):e.available_level;return `<button class="item-icon ${esc(e.rarity||'unknown')} ${locked?'locked':''} ${active?'selected':''}" onclick="selectCatalogItem('${esc(e.id)}')" title="${esc(e.name)} · ${esc(e.variant||'Base')}">${e.artwork?`<img src="${esc(e.artwork)}" alt="${esc(e.name)} artwork" loading="lazy">`:'<span class="no-art">Artwork unavailable</span>'}<span class="level-chip">${e.kind==='mod'?(level?'Lv '+level:'Lv ?'):(activeSelection?.tier?'Tier '+['','I','II','III','IV','V'][activeSelection.tier]:'Tier ?')}</span><span class="ownership-chip">${locked?'🔒':e.ownership==='unlocked'?'✓':'?'}</span><span class="icon-name">${esc(e.base_name)}</span><span class="icon-variant">${esc(e.variant||e.set_name||'Base')} · ${esc(e.rarity||'rarity unknown')}</span>${active?'<span class="in-build-chip">In build</span>':''}</button>`}
function setBuilderFilter(value){builderFilter=value;render()}
function updatePickerResults(){let root=$('#pickerResults');if(!root)return;let all=filteredPicker(),shown=builderFamily==='all'?all:all.filter(e=>groupName(e)===builderFamily),groups=shown.reduce((m,e)=>((m[groupName(e)]??=[]).push(e),m),{});root.innerHTML=pickerResults(shown,groups)}
async function selectCatalogItem(id,proposedLevel){let e=catalogEntry(id);if(!e||!picker)return;let slot=picker.slot,mode=picker.mode,previous=planned.slots[slot]||{},selection={...previous};if(mode==='mod'){if(!selection.catalog_id){fail(Error('Choose gear before attaching a mod'));return}if(selection.mod_id!==id)selection.mod_shiny=false;selection.mod_id=id;const level=Number(proposedLevel);selection.mod_level=Number.isInteger(level)&&level>=1&&level<=17?level:e.available_level||selection.mod_level||1}else{if(selection.catalog_id!==id){for(const field of ['level','tier','stars','calibration_blueprint','calibration_bonus','calibration_profile','calibration_upgrade_level','accessories','legacy_enhancement','inventory_id','weapon_readout'])delete selection[field]}selection.catalog_id=id}planned.slots[slot]=selection;builderSwap=`${mode==='mod'?'Mod':'Gear'} selected: ${e.base_name}${e.variant?' <'+e.variant+'>':''}. ${ownedLabel(e)}. ${e.effect?'Effect: '+e.effect.slice(0,125)+'. ':''}Overall damage benefit needs applicable effects and weapon context.`;builderDetail={id,level:mode==='mod'?selection.mod_level:selection.level};render();await loadBuilderDetail(id);await summarizeBuilderSwap(previous,e,slot,mode)}
async function summarizeBuilderSwap(previous,e,slot,mode){let oldId=mode==='mod'?previous.mod_id:previous.catalog_id,old=catalogEntry(oldId);if(!old||oldId===e.id)return;if(mode!=='mod'){builderSwap=`${old.name} → ${e.name}. New effect: ${String(e.effect||'unresolved').slice(0,125)}. Overall damage winner unresolved without verified current weapon, armor, and encounter rules.`;render();return}try{let leftLevel=previous.mod_level||1,rightLevel=planned.slots[slot]?.mod_level||1;let result=await api('compare-catalog-selections',{left:{catalog_id:oldId,level:leftLevel},right:{catalog_id:e.id,level:rightLevel},assumptions:{}});if(planned.slots[slot]?.mod_id!==e.id)return;let changes=(result.attribute_changes||[]).filter(x=>x.numeric_delta_percent!=null).slice(0,3).map(x=>`${x.name} ${x.numeric_delta_percent>0?'+':''}${x.numeric_delta_percent} percentage points`);builderSwap=`${old.base_name} → ${e.base_name}${e.variant?' <'+e.variant+'>':''}. ${changes.length?'Known listed changes: '+changes.join(', ')+'. ':'Exact attribute changes remain incomplete. '}Main effects ${result.main_effect_changed?'differ':'match'}. ${result.winner_established?'Scoped result available in Compare.':'Overall damage winner unresolved.'}`;render();return}catch{}builderSwap=`${old.name} → ${e.name}. Their effects differ; overall damage winner unresolved without supported mechanics and context.`;render()}
async function previewCatalogItem(id){let e=catalogEntry(id);if(!e||!picker||builderDetail?.id===id)return;builderDetail={id,level:e.available_level||1};await loadBuilderDetail(id)}
async function loadBuilderDetail(id){try{let level=builderDetail?.level;let response=await fetch('/api/catalog/'+encodeURIComponent(id)+(level?'?level='+level:''));let data=await response.json();if(!response.ok)throw Error(data.error||'Catalog lookup failed');if(builderDetail?.id!==id||builderDetail?.level!==level)return;builderDetail={id,level,result:data};let area=$('#builderDetail');if(area)area.innerHTML=detailHtml(builderDetail)}catch(e){fail(e)}}
function detailHtml(detail){
  const e=catalogEntry(detail.id),r=detail.result;
  if(!e)return '';
  return `<div class="card item-detail"><div class="detail-title">${entryArt(e)}<div><h3>${esc(e.base_name)}</h3><p>${esc(e.variant||e.set_name||e.family||'')} · ${esc(e.rarity||'rarity unknown')}</p></div></div><p>${esc(r?.primary_effect||e.effect||'Effect details unavailable')}</p><p class="small muted">Edit selected settings on the equipped card.</p></div>`;
}

function changeBuilderOption(key,value){if(picker?.slot)changeSlotSetting(picker.slot,key,value)}

async function markBuilderOwnership(id,status){try{let level=$('#availableLevel')?.value?Number($('#availableLevel').value):null;await api('catalog-ownership',{catalog_id:id,status,available_level:level});builderData=await(await fetch('/api/builder-catalog')).json();render();notice('Ownership recorded separately from the planned build')}catch(e){fail(e)}}
function comparePlannedBuilds(targetId){let candidates=builderData.planned_builds.filter(b=>b.id!==planned.id);if(!candidates.length){$('#builderCompare').innerHTML='<p class="note">Save a second planned build to compare slot choices.</p>';return}if(!targetId&&candidates.length>1){$('#builderCompare').innerHTML=`<div class="card"><h3>Compare with which build?</h3><div class="actions">${candidates.map(b=>`<button class="secondary" onclick="comparePlannedBuilds('${esc(b.id)}')">${esc(b.name)}</button>`).join('')}</div></div>`;return}let other=candidates.find(b=>b.id===targetId)||candidates[0];let changes=builderSlots.map(([slot,label])=>{let a=planned.slots[slot]||{},b=other.slots[slot]||{};return a.catalog_id!==b.catalog_id||a.mod_id!==b.mod_id?`${label}: ${catalogEntry(a.catalog_id)?.name||'empty'}${a.mod_id?' + '+catalogEntry(a.mod_id)?.name:''} ↔ ${catalogEntry(b.catalog_id)?.name||'empty'}${b.mod_id?' + '+catalogEntry(b.mod_id)?.name:''}`:null}).filter(Boolean);$('#builderCompare').innerHTML=`<div class="card"><h3>${esc(planned.name)} vs ${esc(other.name)}</h3><p>${changes.length?changes.map(esc).join('<br>'):'Same catalog choices.'}</p><p class="note warn">Overall outgoing damage remains unresolved for unmodeled effects or missing weapon and target context. Use Compare for supported scoped calculations.</p><details><summary>Comparison scope</summary>Planned builds can contain unowned items. This view compares identities and attached mods; it does not turn unknown mechanics into zero benefit.</details></div>`}
