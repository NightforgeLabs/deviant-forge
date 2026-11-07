/* Character-led equipment editor. The existing catalog, persistence and advice API remain authoritative. */
let characterSlot='primary',characterEditKind='gear',characterPreviewId=null;
let characterPreviewDetail=null,characterPreviewLevel=null,characterPreviewRequest=0,characterLevelOpen=false;
let characterPreviewSettings=null;
let characterPane='equipment';
const characterNames={primary:'Primary',secondary:'Secondary',melee:'Melee',helmet:'Helmet',mask:'Mask',top:'Top',gloves:'Gloves',bottoms:'Bottoms',shoes:'Shoes'};
const characterArmorLayout=[['helmet','left','top'],['mask','right','top'],['top','left','middle'],['gloves','right','middle'],['bottoms','left','bottom'],['shoes','right','bottom']];
const previousNewPlannedBuild=newPlannedBuild,previousOpenPlannedBuild=openPlannedBuild;
const previousSelectCatalogItem=selectCatalogItem;
const previousChangeSlotSetting=changeSlotSetting;
// The General suffix glyph is identical byte-for-byte across sourced weapon
// variant images. This current-game sighting has no separate catalog image.
const modSharedSuffixGlyph={
  'mod:weapon_mod:shrapnel-souvenir-general':'/artwork/mod__weapon_mod__shrapnel-smash-general.png'
};

function characterFocus(slot,on){
  for(const node of document.querySelectorAll?.(`[data-character-slot="${slot}"]`)||[])
    node.classList?.toggle('hovered',on);
}
function characterArt(entry,small=false){
  const artwork=entry?.artwork||modSharedSuffixGlyph[entry?.id];
  return artwork?`<img class="character-item-art ${small?'small':''}" src="${esc(artwork)}" alt="${esc(entry.name)} artwork">`:
    `<span class="character-item-art missing ${small?'small':''}">${entry?'Artwork unavailable':'Empty'}</span>`;
}
function characterSourceReference(url,label='Catalog source'){
  if(/^https:\/\/(?:www\.)?oncehuman\.game\//.test(String(url||'')))
    return `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(label)} ↗</a>`;
  const host=/^https?:\/\/([^/]+)/.exec(String(url||''))?.[1]?.replace(/^www\./,'')||'unavailable';
  return `<span class="small muted">${esc(label)}: ${esc(host)} · third-party evidence, no external link</span>`;
}
const characterEmptyIcons={primary:'⌖',secondary:'⌖',melee:'⚔',helmet:'◉',mask:'◇',top:'▤',gloves:'✥',bottoms:'▥',shoes:'⌁'};
function characterEquipmentCard(slot){
  const selected=planned.slots[slot]||{},gear=catalogEntry(selected.catalog_id),mod=catalogEntry(selected.mod_id);
  const active=characterSlot===slot,weapon=['primary','secondary','melee'].includes(slot);
  const tier=selected.tier?'T'+['','I','II','III','IV','V'][selected.tier]:'';
  const stars=selected.stars?'★'+selected.stars:'';
  const recycled=selected.inventory_id&&!(builderData?.my_gear||[]).some(item=>item.id===selected.inventory_id);
  const badges=[tier,stars,selected.calibration_profile?.style||'',recycled?'Saved gear entry recycled · build kept':''].filter(Boolean).join(' · ');
  return `<article class="character-equip ${weapon?'weapon-card':'armor-card'} ${active?'active':''} ${gear?'filled':'empty'} ${esc(gear?.rarity||'unknown')}" data-character-slot="${slot}" onmouseenter="characterFocus('${slot}',true)" onmouseleave="characterFocus('${slot}',false)">
    <button class="character-gear-target" aria-label="${esc(characterNames[slot])}: ${esc(gear?.name||'choose equipment')}" onclick="selectCharacterSlot('${slot}','gear',event)" onfocus="characterFocus('${slot}',true)" onblur="characterFocus('${slot}',false)">
      ${gear?characterArt(gear):`<span class="slot-empty-icon" aria-hidden="true">${characterEmptyIcons[slot]}</span>`}<span class="character-gear-copy"><strong>${esc(characterNames[slot])}</strong><span class="character-gear-name">${esc(gear?.name||'Empty slot')}</span>${badges?`<small>${esc(badges)}</small>`:''}</span>
    </button>
    ${builderMods[slot]&&gear?`<div class="character-mod-line"><button class="character-mod-target" data-mod-id="${esc(mod?.id||'')}" data-mod-slot="${slot}" data-mod-level="${esc(selected.mod_level??1)}" onpointerenter="if(this.dataset.modId)showModHover(this.dataset.modId,this.dataset.modSlot,this.dataset.modLevel,null,event)" onfocus="if(this.dataset.modId)showModHover(this.dataset.modId,this.dataset.modSlot,this.dataset.modLevel,null,event)" onpointerleave="scheduleModHoverHide()" onblur="scheduleModHoverHide()" onclick="selectCharacterSlot('${slot}','mod')" aria-label="${esc(characterNames[slot])} mod: ${esc(mod?.name||'empty socket')}">${mod?characterArt(mod,true):'<span class="mod-socket-icon" aria-hidden="true">⬡</span>'}<span>${esc(mod?.name||'Mod socket')}</span></button>${mod?`<button class="character-level-badge" data-mod-id="${esc(mod.id)}" data-mod-slot="${slot}" data-mod-level="${esc(selected.mod_level??1)}" onpointerenter="showModHover(this.dataset.modId,this.dataset.modSlot,this.dataset.modLevel,null,event)" onfocus="showModHover(this.dataset.modId,this.dataset.modSlot,this.dataset.modLevel,null,event)" onpointerleave="scheduleModHoverHide()" onblur="scheduleModHoverHide()" aria-label="Edit ${esc(characterNames[slot])} mod level, currently ${esc(selected.mod_level??'?')}" onclick="showCharacterModLevel('${slot}')">Lv ${esc(selected.mod_level??'?')}</button>`:''}</div>`:''}
  </article>`;
}
function characterRegion(slot,label,extra='',text=true){
  return `<button class="soldier-region region-${slot} ${extra} ${characterSlot===slot?'active':''}" data-character-slot="${slot}" type="button" aria-label="Select ${label.toLowerCase()} equipment" aria-pressed="${characterSlot===slot}" onclick="selectCharacterSlot('${slot}','gear')" onmouseenter="characterFocus('${slot}',true)" onmouseleave="characterFocus('${slot}',false)" onfocus="characterFocus('${slot}',true)" onblur="characterFocus('${slot}',false)">${text?`<span>${label}</span>`:''}</button>`;
}
function characterFigure(){
  return `<div class="soldier-figure" role="group" aria-label="Soldier equipment regions"><div class="soldier-artboard"><img src="/artwork/soldier-navigation-v1.png" alt="Generic full-body soldier navigation figure; selected armor appearance is shown in equipment cards">
    ${characterRegion('helmet','Helmet')}${characterRegion('mask','Mask')}${characterRegion('top','Top')}
    ${characterRegion('gloves','Gloves','hand-left',false)}${characterRegion('gloves','Gloves','hand-right')}
    ${characterRegion('bottoms','Bottoms','leg-left',false)}${characterRegion('bottoms','Bottoms','leg-right')}
    ${characterRegion('shoes','Shoes','foot-left',false)}${characterRegion('shoes','Shoes','foot-right')}
  </div></div>`;
}
function characterBoard(){
  const by=(side,row)=>characterEquipmentCard(characterArmorLayout.find(item=>item[1]===side&&item[2]===row)[0]);
  return `<section class="character-board" aria-label="Character equipment">
    <div class="armor-board"><div class="armor-side left">${by('left','top')}${by('left','middle')}${by('left','bottom')}</div>${characterFigure()}<div class="armor-side right">${by('right','top')}${by('right','middle')}${by('right','bottom')}</div></div>
    <div class="weapon-row">${['primary','secondary','melee'].map(characterEquipmentCard).join('')}</div></section>`;
}
function characterTierControls(slot,selection,proposed=false){
  const current=selection.tier;
  const change=value=>proposed?`changeCharacterPreviewSetting('tier','${value}')`:`changeSlotSetting('${slot}','tier','${value}')`;
  return `<div class="character-control"><b>Craft tier</b><div class="choice-row" role="group" aria-label="Craft tier for ${slot}">
    <button class="${current==null?'active':''}" aria-label="Tier unknown for ${slot}" aria-pressed="${current==null}" onclick="${change('')}">?</button>
    ${[1,2,3,4,5].map(n=>`<button class="${current===n?'active':''}" aria-label="Set tier ${n} for ${slot}" aria-pressed="${current===n}" onclick="${change(n)}">${['','I','II','III','IV','V'][n]}</button>`).join('')}
  </div></div>`;
}
function characterStarControls(slot,selection,entry,proposed=false){
  const source=verifiedBlueprintStarLimit(entry),max=selectableBlueprintStarMax(entry),current=selection.stars;
  const numbers=[...Array(max)].map((_,i)=>i+1);
  if(current>max)numbers.push(current);
  const change=value=>proposed?`changeCharacterPreviewSetting('stars','${value}')`:`changeSlotSetting('${slot}','stars','${value}')`;
  return `<div class="character-control"><b>Blueprint stars</b><div class="choice-row stars" role="group" aria-label="Blueprint stars for ${slot}">
    <button class="${!current?'active':''}" aria-label="Blueprint stars unknown for ${slot}" aria-pressed="${!current}" onclick="${change('')}">?</button>
    ${numbers.map(n=>`<button class="${current===n?'active':''}" aria-label="${n>max&&source?'Saved invalid '+n+' blueprint stars':'Set '+n+' blueprint stars'} for ${slot}" aria-pressed="${current===n}" ${n>max&&source?'disabled':''} onclick="${change(n)}">★<small>${n}</small></button>`).join('')}
  </div>${source?`<small>${current>max?`Selected ${current}★ exceeds the published maximum ${max}★. The saved value is shown but cannot be used as a valid configuration.`:`Published maximum ${max}★ for this exact blueprint.`} Source: ${esc(source.url)}</small>`:'<small>Choices follow catalog rarity; an item-specific maximum has not been verified.</small>'}</div>`;
}
/* Screenshot-backed calibration examples are optional proposals, not owned inventory. */
const calibrationExamples={
  rapid_a:{blueprint_name:'Rapid Assault Rifle Calibration Blueprint',rarity:'purple',style:'Rapid Shot Style',fixed_effects:'Fire Rate +15%; Reload Speed +10%; Attack −10%',rolls:[{stat:'Weapon DMG',value_percent:29.6,range_min:26,range_max:33},{stat:'Weakspot DMG',value_percent:18.6,range_min:15,range_max:21}],source_ref:'libfile_5e9d7ef914648191bd61b1bd3caa68ec'},
  precision:{blueprint_name:'Precision Assault Rifle Calibration Blueprint',rarity:'purple',style:'Precision Style',fixed_effects:'Attack +20%; Range +40%; Fire Rate −10%',rolls:[{stat:'Weapon DMG',value_percent:27.4,range_min:26,range_max:33},{stat:'Crit DMG',value_percent:32.7,range_min:25,range_max:35}],source_ref:'libfile_8283e2e10c0c8191af4ff361c7a44a8a'},
  rapid_b:{blueprint_name:'Rapid Assault Rifle Calibration Blueprint',rarity:'purple',style:'Rapid Shot Style',fixed_effects:'Fire Rate +15%; Reload Speed +10%; Attack −10%',rolls:[{stat:'Weapon DMG',value_percent:27.0,range_min:26,range_max:33},{stat:'Weakspot DMG',value_percent:15.5,range_min:15,range_max:21}],source_ref:'libfile_7867daed783081918eb273d5ddea0d50'},
  energy_gold:{blueprint_name:'Energy Rifle Calibration Blueprint',rarity:'gold',style:'Energy Style',fixed_effects:'After taking damage, automatically reload 1 bullet (cooldown: 0.3s). Attack +10%.',rolls:[{stat:'Weapon DMG',value_percent:42.4,range_min:34,range_max:50},{stat:'Elemental DMG (Blaze, Frost, Shock, Blast)',value_percent:17.5,range_min:15,range_max:20}],source_ref:'libfile_a194f3bfeaf081918ba9f3ea67ebb09e'},
  vanguard_gold:{blueprint_name:'Vanguard Rifle Calibration Blueprint',rarity:'gold',style:'Vanguard Style',fixed_effects:'After reloading from empty, the next shot is guaranteed to trigger its keyword effect.',rolls:[{stat:'Weapon DMG',value_percent:34.3,range_min:34,range_max:50},{stat:'Crit Rate',value_percent:15.3,range_min:12,range_max:16}],source_ref:'libfile_3f0148c85b8c8191b936bc3ad9663123'}
};
let nativeCalibrationChoices=null;
function nativeCalibrationChoicesHtml(){
  const snapshot=nativeCalibrationChoices;
  if(!snapshot||snapshot.weapon_id!==characterPreviewId)return '<button type="button" class="secondary compact" onclick="loadNativeCalibrationChoices()">Browse source calibration options</button>';
  if(snapshot.status!=='source_series_text_candidates')return `<small>${esc(snapshot.missing||'No exact source series link for this weapon.')}</small>`;
  const options=snapshot.choices.map(row=>`<details><summary>${row.style_english_gloss?esc(row.style_english_gloss)+' style (translation) · ':''}${esc(row.native_title)} · source ID ${esc(row.item_id)}${row.public_title?' · '+esc(row.public_title):''}</summary><small>${esc(row.compatible_series_source_text)} Native style: ${esc(row.native_style)}. Possible term ranges are not owned rolls.</small><ul>${row.available_terms.map(term=>`<li>Term ${esc(term.native_term_id)}: ${term.options.map(opt=>`${esc(opt.native_description||opt.property_names.join(', ')||'unresolved native affix')} · ${(opt.minimum_fraction*100).toFixed(1)}–${(opt.maximum_fraction*100).toFixed(1)}%`).join(' or ')}</li>`).join('')}</ul><button type="button" onclick="chooseNativeCalibrationChoice(${Number(row.item_id)})">Use source identity in unsaved proposal</button></details>`).join('');
  return `<small>${esc(snapshot.choices.length)} current native blueprint records explicitly name the ${esc(snapshot.series_token)} series. Source text supports series browsing, not exact instance ownership, rolled values or combat activation.</small>${options}`;
}
async function loadNativeCalibrationChoices(){
  const id=characterPreviewId;if(!id)return;
  try{
    const response=await fetch('/api/native-calibration-choices?weapon_id='+encodeURIComponent(id));
    const packet=await response.json();
    if(!response.ok)throw Error(packet.error||'Calibration source unavailable');
    if(characterPreviewId!==id)return;
    nativeCalibrationChoices=packet;refreshCharacterCalibration();
  }catch(error){notice(String(error.message||error));}
}
function chooseNativeCalibrationChoice(itemId){
  const packet=nativeCalibrationChoices,choice=packet?.weapon_id===characterPreviewId?packet.choices.find(row=>row.item_id===itemId):null;
  if(!choice||!['primary','secondary','melee'].includes(characterSlot))return;
  characterPreviewSettings??={};
  characterPreviewSettings.calibration_profile={blueprint_name:choice.native_title,rarity:'unknown',style:choice.native_style,
    fixed_effects:'',rolls:[],source_ref:'native-calibration-item:'+itemId+'@'+packet.source_build};
  refreshCharacterCalibration();notice('Source blueprint identity copied to this unsaved proposal. No roll or damage bonus was inferred.');
}
function characterCalibrationControls(settings){
  const profile=settings.calibration_profile||{},rolls=profile.rolls||[];
  const input=(key,label,value)=>`<label>${label}<input value="${esc(value??'')}" maxlength="${key==='fixed_effects'?500:key==='style'?80:160}" onchange="changeCharacterCalibration('${key}',this.value)"></label>`;
  const roll=(item,i)=>`<div class="calibration-roll"><label>Bonus ${i+1}<input value="${esc(item.stat||'')}" maxlength="80" placeholder="e.g. Weapon DMG" onchange="changeCharacterCalibrationRoll(${i},'stat',this.value)"></label><label>Value %<input type="number" step="0.1" value="${esc(item.value_percent??'')}" onchange="changeCharacterCalibrationRoll(${i},'value_percent',this.value)"></label><label>Range min %<input type="number" step="0.1" value="${esc(item.range_min??'')}" onchange="changeCharacterCalibrationRoll(${i},'range_min',this.value)"></label><label>Range max %<input type="number" step="0.1" value="${esc(item.range_max??'')}" onchange="changeCharacterCalibrationRoll(${i},'range_max',this.value)"></label><button type="button" aria-label="Remove bonus ${i+1}" onclick="removeCharacterCalibrationRoll(${i})">×</button></div>`;
  return `<details class="character-calibration calibration-profile" ${profile.blueprint_name?'open':''}><summary>Optional calibration blueprint${profile.blueprint_name?' · '+esc(profile.style||profile.blueprint_name):''}</summary><p>Blueprint and rolled bonuses are separate from craft tier and blueprint stars. Screenshot examples only fill this proposal; they do not mark a blueprint owned or consumed. A separate Oct 25 Rapid blueprint shows +20% Fire Rate and different rolls; it is not installed by choosing an Oct 24 proposal.</p><div class="calibration-examples"><b>Seen in your screenshots · choose a proposal</b><button type="button" onclick="chooseCalibrationExample('rapid_a')">Rapid Shot · Oct 24 +15% · 29.6 / 18.6</button><button type="button" onclick="chooseCalibrationExample('precision')">Precision · 27.4 / 32.7</button><button type="button" onclick="chooseCalibrationExample('rapid_b')">Rapid Shot · screenshot +15% · 27.0 / 15.5</button><button type="button" onclick="chooseCalibrationExample('vanguard_gold')">Gold Vanguard · 34.3 / 15.3</button><button type="button" onclick="chooseCalibrationExample('energy_gold')">Gold Energy · 42.4 / 17.5</button></div><details class="calibration-source-choices" ${nativeCalibrationChoices?.weapon_id===characterPreviewId?'open':''}><summary>Source calibration catalog</summary>${nativeCalibrationChoicesHtml()}</details><div class="calibration-profile-fields">${input('blueprint_name','Calibration blueprint name',profile.blueprint_name)}<label>Rarity<select onchange="changeCharacterCalibration('rarity',this.value)">${[['unknown','Unknown'],['purple','Purple'],['gold','Gold'],['other','Other']].map(([value,label])=>`<option value="${value}" ${profile.rarity===value?'selected':''}>${label}</option>`).join('')}</select></label>${input('style','Style',profile.style)}${input('fixed_effects','Fixed style effects',profile.fixed_effects)}</div><div class="calibration-rolls"><b>Exact rolls on this calibration</b>${rolls.map(roll).join('')}<button type="button" ${rolls.length>=4?'disabled':''} onclick="addCharacterCalibrationRoll()">Add bonus line</button></div>${characterPreviewId==='weapon:aug-electron-cloud'?'<p class="small muted">AUG released after new calibration-level upgrades were removed in January 2026. No legacy +0…+10 level applies.</p>':`<label class="calibration-upgrade">Legacy weapon calibration upgrade level, if documented<input type="number" min="0" step="1" value="${esc(settings.calibration_upgrade_level??'')}" onchange="changeCharacterCalibrationUpgrade(this.value)"></label>`}<button type="button" class="text-button" onclick="clearCharacterCalibration()">Clear proposed calibration blueprint</button><details><summary>Earlier freeform calibration notes</summary><div class="calibration-controls">${input('legacy_blueprint','Blueprint note',settings.calibration_blueprint)}${input('legacy_bonus','Bonus note',settings.calibration_bonus)}</div></details></details>`;
}
function characterModSettings(slot,selection,mod){
  if(!mod)return `<button class="secondary compact" onclick="selectCharacterSlot('${slot}','mod')">Attach a mod</button>`;
  return `<div class="selected-mod"><div class="selected-mod-name">${characterArt(mod,true)}<div><b>${esc(mod.name)}</b><small>${esc(mod.variant||'Base')} · ${esc(mod.rarity||'rarity unknown')}</small></div></div>
    <button class="character-level-badge" aria-label="Edit ${esc(characterNames[slot])} mod level, currently ${esc(selection.mod_level??'?')}" onclick="showCharacterModLevel('${slot}')">Lv ${esc(selection.mod_level??'?')} · Edit</button>
    ${characterLevelOpen?`<label class="character-level-editor">Field Guide level <input id="characterModLevel" type="number" min="1" max="17" step="1" value="${esc(selection.mod_level??1)}" aria-label="${esc(characterNames[slot])} Field Guide mod level" onchange="changeSlotSetting('${slot}','mod_level',this.value)"></label>`:''}
    <button class="text-button" onclick="removePlannedMod('${slot}')">Remove mod</button>
  </div>`;
}
function characterAdvanced(slot,selection,entry){
  const isWeapon=['primary','secondary','melee'].includes(slot);
  const cap=maxLegacyEnhancement(entry?.rarity);
  const values=[['','None / current'],...Array.from({length:cap+1},(_,n)=>[n,'+'+n])];
  if(selection.legacy_enhancement>cap)values.push([selection.legacy_enhancement,'Saved +'+selection.legacy_enhancement+' · verify']);
  return `<details class="character-advanced"><summary>Advanced${selection.legacy_enhancement!=null?' · legacy +'+esc(selection.legacy_enhancement):''}</summary>
    ${isWeapon&&entry?.id!=='weapon:aug-electron-cloud'?settingSelect(slot,'legacy_enhancement','Legacy enhancement',selection.legacy_enhancement??'',values):entry?.id==='weapon:aug-electron-cloud'?'<p class="small muted">No legacy +0…+10 enhancement: AUG released after the January 2026 removal.</p>':''}
    <p class="small muted">${isWeapon?'For weapons retained from before the 2026 calibration change. ':''}These settings are saved even where damage scaling is unknown.</p>
    ${selection.level!=null?`<p class="small muted">Earlier saved equipment level: ${esc(selection.level)}. Preserved without a current meaning.</p>`:''}
    <label class="slot-setting">Ownership<select onchange="markBuilderOwnership('${esc(entry.id)}',this.value)"><option value="unknown" ${entry.ownership==='unknown'?'selected':''}>Unknown</option><option value="unlocked" ${entry.ownership==='unlocked'?'selected':''}>Owned / unlocked</option><option value="locked" ${entry.ownership==='locked'?'selected':''}>Confirmed locked</option></select></label>
  </details>`;
}
function characterSettingsHtml(){
  const slot=characterSlot,selection=planned.slots[slot]||{},gear=catalogEntry(selection.catalog_id),mod=catalogEntry(selection.mod_id);
  if(!gear)return `<section class="character-settings empty-detail" id="characterSettings" aria-label="Selected item settings"><div class="slot-empty-icon" aria-hidden="true">${characterEmptyIcons[slot]}</div><div><small>SELECTED SLOT</small><h3>${esc(characterNames[slot])}</h3><p>Select a catalog picture to preview an item.</p></div></section>`;
  if(characterEditKind==='mod'){
    if(!mod)return `<section class="character-settings empty-detail" id="characterSettings" aria-label="Selected mod settings"><div class="mod-socket-icon" aria-hidden="true">⬡</div><div><small>${esc(characterNames[slot].toUpperCase())} MOD</small><h3>Empty socket</h3><p>Select a mod picture to preview it.</p></div></section>`;
    return `<section class="character-settings mod-settings" id="characterSettings" aria-label="Selected mod settings"><div class="character-settings-art">${characterArt(mod)}</div><div class="character-settings-body"><div class="settings-title"><div><small>ATTACHED ${esc(characterNames[slot].toUpperCase())} MOD</small><h3>${esc(mod.name)}</h3><span>${esc(mod.variant||'Base')} · ${esc(mod.rarity||'rarity unknown')}</span></div><button class="text-button" onclick="removePlannedMod('${slot}')">Remove</button></div><p>${esc(mod.effect||'Effect text not cataloged')}</p><label class="character-level-editor">Field Guide level<input id="characterModLevel" type="number" min="1" max="17" step="1" value="${esc(selection.mod_level??1)}" aria-label="${esc(characterNames[slot])} Field Guide mod level" onchange="changeSlotSetting('${slot}','mod_level',this.value)"></label><details class="character-evidence"><summary>Effect and ownership details</summary><p>${esc(mod.effect||'Effect text not cataloged')}</p><p>${esc(ownedLabel(mod))}</p></details></div></section>`;
  }
  const weapon=['primary','secondary','melee'].includes(slot);
  return `<section class="character-settings" id="characterSettings" aria-label="Selected item settings"><div class="character-settings-art">${characterArt(gear)}</div><div class="character-settings-body"><div class="settings-title"><div><small>SELECTED ${esc(characterNames[slot].toUpperCase())}</small><h3>${esc(gear.name)}</h3><span>${esc(gear.rarity||'rarity unknown')}</span></div><button class="text-button" onclick="removePlanned('${slot}')">Remove</button></div><p>${esc(gear.effect||'Effect not cataloged')}</p>
    ${characterTierControls(slot,selection)}${characterStarControls(slot,selection,gear)}
    ${builderMods[slot]?`<div class="settings-mod-row"><b>Mod</b>${characterModSettings(slot,selection,mod)}</div>`:''}
    ${weapon?`<details class="character-calibration" open><summary>Calibration</summary><div class="calibration-controls"><label>Blueprint<input aria-label="Calibration blueprint for ${slot}" value="${esc(selection.calibration_blueprint||'')}" maxlength="160" onchange="changeSlotSetting('${slot}','calibration_blueprint',this.value)"></label><label>Roll / bonus<input aria-label="Calibration roll or bonus for ${slot}" value="${esc(selection.calibration_bonus||'')}" maxlength="160" onchange="changeSlotSetting('${slot}','calibration_bonus',this.value)"></label></div></details>`:''}
    ${characterAdvanced(slot,selection,gear)}
  </div></section>`;
}
function characterCatalogCard(entry){
  const selection=planned.slots[characterSlot]||{},equipped=(picker?.mode==='mod'?selection.mod_id:selection.catalog_id)===entry.id;
  const preview=characterPreviewId===entry.id;
  const level=entry.kind==='mod'?(equipped?selection.mod_level:entry.observed_numeric_levels?.[0]||entry.available_level):null;
  return `<button class="character-catalog-card ${esc(entry.rarity||'unknown')} ${preview?'preview':''} ${equipped?'equipped':''} ${entry.ownership==='locked'?'locked':''}" data-id="${esc(entry.id)}" onclick="previewCharacterItem(this.dataset.id)" aria-label="Preview ${esc(entry.name)}" aria-pressed="${preview}" title="${esc(entry.name)} · ${esc(ownedLabel(entry))}">
    <span class="catalog-card-art">${characterArt(entry)}</span><span class="character-card-name">${esc(entry.base_name)}</span><small>${esc(entry.variant||entry.set_name||entry.weapon_category||entry.family||'')}</small>
    ${level?`<span class="card-level" title="${equipped?'Equipped level':'Catalog level; ownership unchanged'}">Lv ${esc(level)}</span>`:''}<span class="card-state" aria-label="${esc(equipped?'Equipped':entry.ownership==='locked'?'Locked':entry.ownership==='unlocked'?'Owned':'Ownership unknown')}">${equipped?'Equipped':entry.ownership==='locked'?'🔒':entry.ownership==='unlocked'?'✓':'?'}</span>
  </button>`;
}
function characterCatalogResultsHtml(){
  const all=filteredPicker(),shown=builderFamily==='all'?all:all.filter(e=>groupName(e)===builderFamily);
  const label=e=>picker?.mode==='mod'?groupName(e):e.kind==='weapon'?(e.weapon_category||e.family||'Weapons'):'All '+characterNames[characterSlot];
  const groups=shown.reduce((map,e)=>((map[label(e)]??=[]).push(e),map),{});
  const helmetOrder=picker?.mode==='mod'&&characterSlot==='helmet'?['Precise Strike','Deviation Expert']:[];
  return shown.length?Object.entries(groups).sort(([a],[b])=>{
    const x=helmetOrder.indexOf(a),y=helmetOrder.indexOf(b);
    return (x>=0||y>=0)?(x<0?999:x)-(y<0?999:y):a.localeCompare(b);
  }).map(([family,entries])=>`<section class="character-family"><h3>${esc(family)}</h3><div class="character-card-grid">${entries.sort((a,b)=>(a.base_name||a.name).localeCompare(b.base_name||b.name)||(a.variant||'').localeCompare(b.variant||'')).map(characterCatalogCard).join('')}</div></section>`).join(''):
    `<div class="character-empty">No matching items. Try All items or another search.</div>`;
}
function characterPreviewHtml(){
  const entry=catalogEntry(characterPreviewId);
  if(!entry)return characterSettingsHtml();
  const selected=planned.slots[characterSlot]||{},equipped=(picker?.mode==='mod'?selected.mod_id:selected.catalog_id)===entry.id;
  const resolved=characterPreviewDetail?.level===characterPreviewLevel?characterPreviewDetail:null;
  const attrs=resolved?.known_attributes||[];
  const attribute=a=>`${a.name} ${a.value_percent==null?'value unknown':(a.direction==='reduction'?'−':'+')+a.value_percent+'%'}${a.conditional_bonus_percent==null?'':' · extra +'+a.conditional_bonus_percent+'% when '+(a.condition||'condition unknown')}`;
  const mod=entry.kind==='mod',sameLevel=selected.mod_level===characterPreviewLevel;
  const values=equipped?selected:(characterPreviewSettings||{});
  const weapon=entry.kind==='weapon';
  return `<div class="character-preview-item ${equipped?'is-equipped':''}"><div class="character-detail-art">${characterArt(entry)}</div><div class="character-preview-copy"><small>${equipped?'EQUIPPED':'PREVIEW'} · ${esc(entry.rarity||'rarity unknown')}</small><h3>${esc(entry.name)}</h3><p>${esc(resolved?.primary_effect||entry.effect||'Effect not cataloged')}</p>${mod?`<div class="character-visible-stats"><b>Lv ${esc(characterPreviewLevel??1)} stats</b>${attrs.length?`<span>${esc(attrs.slice(0,2).map(attribute).join(' · '))}</span>`:'<span>Numeric values not verified at this level</span>'}</div>`:''}<details class="character-evidence"><summary>Full effects, attributes and ownership</summary><p>${esc(resolved?.primary_effect||entry.effect||'Effect not cataloged')}</p>${mod?`<p>Field Guide level ${esc(characterPreviewLevel??1)} supplies these values. A level shown in the catalog does not confirm ownership.</p>`:''}${attrs.length?`<ul>${attrs.map(a=>`<li>${esc(attribute(a))}${a.source?` <small>${builderSource(a.source)}</small>`:''}</li>`).join('')}</ul>`:'<p>No verified numeric profile for this level.</p>'}<p>${esc(ownedLabel(entry))}</p>${resolved?.unknowns?.length?`<p>${esc(resolved.unknowns.join('; '))}</p>`:''}</details></div>
    <div class="character-detail-controls">${mod?`<label class="character-preview-level">Proposed Field Guide level <input type="number" min="1" max="17" step="1" value="${esc(characterPreviewLevel??1)}" aria-label="Proposed mod level" onchange="changeCharacterPreviewLevel(this.value)"></label>${equipped?`<label class="character-level-editor">Equipped level<input id="characterModLevel" type="number" min="1" max="17" step="1" value="${esc(selected.mod_level??1)}" aria-label="${esc(characterNames[characterSlot])} Field Guide mod level" onchange="changeSlotSetting('${characterSlot}','mod_level',this.value)"></label>`:''}`:`${characterTierControls(characterSlot,values,!equipped)}${characterStarControls(characterSlot,values,entry,!equipped)}${weapon?characterCalibrationControls(values):''}`}
    <button class="primary equip-action" ${equipped&&(!mod||sameLevel)?'disabled':''} onclick="equipCharacterPreview()">${equipped?(mod&&!sameLevel?'Apply level':'Equipped'):'Equip'}</button></div></div>`;
}
function characterCatalogHtml(){
  const slot=characterSlot,canMod=!!builderMods[slot]&&!!planned.slots[slot]?.catalog_id;
  const all=filteredPicker(),families=[...new Set(all.map(groupName))].sort((a,b)=>a.localeCompare(b));
  return `<section class="character-catalog" aria-label="Compatible equipment catalog"><div class="character-catalog-top"><div class="catalog-heading"><div><small>FIELD GUIDE · ${esc(picker?.mode==='mod'?'MODS':'EQUIPMENT')}</small><h2>${esc(characterNames[slot])}</h2></div><div class="catalog-mode"><button class="${picker?.mode==='gear'?'active':''}" onclick="selectCharacterSlot('${slot}','gear')">Equipment</button><button class="${picker?.mode==='mod'?'active':''}" ${canMod?'':'disabled'} onclick="selectCharacterSlot('${slot}','mod')">Mods</button></div></div>
    <div class="character-category-tabs">${builderTabs.map(([label,target])=>`<button class="${slot===target||target==='primary'&&['secondary','melee'].includes(slot)?'active':''}" onclick="characterCategory('${target}')">${label}</button>`).join('')}</div>
    <div class="character-filters"><input id="characterSearch" aria-label="Search compatible items" placeholder="Search ${esc(characterNames[slot].toLowerCase())}…" value="${esc(builderQuery)}" oninput="builderQuery=this.value;renderCharacterResults()"><select aria-label="Filter family or set" id="characterFamily" onchange="builderFamily=this.value;renderCharacterResults()"><option value="all">All families / sets</option>${families.map(f=>`<option value="${esc(f)}" ${builderFamily===f?'selected':''}>${esc(f)}</option>`).join('')}</select><div class="character-scope"><button class="${builderFilter==='all'?'active':''}" onclick="setBuilderFilter('all')">All items</button><button class="${builderFilter==='mine'?'active':''}" onclick="setBuilderFilter('mine')">My items</button></div></div><small id="characterCount" class="character-count">${all.length} compatible choices</small></div>
    <div id="characterResults" class="character-results" data-slot="${slot}" data-mode="${picker?.mode||'gear'}">${characterCatalogResultsHtml()}</div><div id="characterPreview" class="character-detail-dock" aria-label="Selected item details">${characterPreviewHtml()}</div></section>`;
}
function characterStatusHtml(){
  const armor=['helmet','mask','top','gloves','bottoms','shoes'].filter(slot=>planned.slots[slot]?.catalog_id).length;
  const weapons=['primary','secondary','melee'].filter(slot=>planned.slots[slot]?.catalog_id).length;
  const mods=Object.values(planned.slots).filter(x=>x?.mod_id).length;
  const counts={};
  for(const slot of ['helmet','mask','top','gloves','bottoms','shoes']){
    const name=catalogEntry(planned.slots[slot]?.catalog_id)?.set_name;
    if(name)counts[name]=(counts[name]||0)+1;
  }
  const sets=Object.entries(counts).sort((a,b)=>b[1]-a[1]).slice(0,3).map(([name,count])=>`${name} ×${count}`);
  return `<span class="summary-count">${armor}/6 armor</span><span class="summary-count">${weapons}/3 weapons</span><span class="summary-count">${mods} mods</span>${sets.map(x=>`<span class="summary-count">${esc(x)}</span>`).join('')}${builderDirty?'<strong class="summary-unsaved">Unsaved</strong>':''}`;
}
builderPage=function(){
  if(!builderData)return '<div class="card">Loading equipment…</div>';
  if(!picker)picker={slot:characterSlot,mode:'gear',tab:characterSlot};
  const choiceLabels=plannedBuildChoiceLabels(builderData.planned_builds);
  setTimeout(queueBuilderAnalysis,0);
  return `<div class="forge-screen"><div class="character-toolbar"><div class="character-brand"><span>✦</span><b>DEVIANT <em>FORGE</em></b></div><nav class="character-main-nav" aria-label="Main navigation"><button onclick="go('start')">Start here</button><button class="active" aria-current="page">Build</button><button onclick="go('compare')">Compare</button><button onclick="go('catalog')">Library</button><button onclick="go('map')">Abyss guide</button></nav><div class="character-top-actions"><label class="character-build-name"><span>Build name</span><input id="plannedName" aria-label="Build name" value="${esc(planned.name)}" oninput="planned.name=this.value;builderDirty=true;document.querySelector('.character-save-state').textContent='● Unsaved changes'"></label><label class="character-open"><span>Open</span><select id="savedBuildPicker" aria-label="Open saved build" onchange="if(this.value)openPlannedBuild(this.value)"><option value="">Saved builds…</option>${builderData.planned_builds.map(b=>`<option value="${esc(b.id)}" ${b.id===planned.id?'selected':''}>${esc(choiceLabels[b.id])}</option>`).join('')}</select></label><span class="character-save-state">${builderDirty?'● Unsaved changes':planned.id?'✓ Saved locally':'○ New plan'}</span><button class="primary character-save" onclick="savePlannedBuild()">Save</button><details class="character-more"><summary aria-label="More build actions">⋯</summary><div><button onclick="duplicatePlannedBuild()">Duplicate build</button><button onclick="go('compare')">Comparison tools</button><button onclick="newPlannedBuild()">New build</button><button onclick="go('import')">Import images / video</button><button onclick="go('inventory')">My items</button><button onclick="go('upgrades')">Upgrades / farming</button><button onclick="go('map')">Isles of Abyss guide</button><button onclick="go('mechanics')">Sources and mechanics</button><button onclick="document.querySelector('#backupBtn')?.click()">Export backup</button></div></details></div></div>
    <div class="character-layout show-${characterPane}"><div class="character-view-switch" role="group" aria-label="Builder view"><button class="${characterPane==='equipment'?'active':''}" aria-pressed="${characterPane==='equipment'}" onclick="setCharacterPane('equipment')">Loadout</button><button class="${characterPane==='catalog'&&picker?.mode==='gear'?'active':''}" aria-pressed="${characterPane==='catalog'&&picker?.mode==='gear'}" onclick="openSavedGear()">Saved gear</button><button class="${characterPane==='catalog'&&picker?.mode==='mod'?'active':''}" aria-pressed="${characterPane==='catalog'&&picker?.mode==='mod'}" onclick="openModCollection()">Mods</button><button class="${characterPane==='catalog'&&picker?.mode==='accessory'?'active':''}" aria-pressed="${characterPane==='catalog'&&picker?.mode==='accessory'}" onclick="openAccessoryCollection()">Accessories</button></div><div class="character-left">${characterBoard()}</div>${characterCatalogHtml()}</div>
    <details class="builder-secondary character-advice" id="builderSecondary" ${builderComparison?'open':''}><summary><b>Build summary</b>${characterStatusHtml()}<span class="summary-chevron" aria-hidden="true">⌄</span></summary><div class="character-summary-content"><div id="builderSummary">${builderAnalysisHtml()}</div><details class="encounter-panel"><summary>Encounter settings</summary>${builderContextHtml()}</details><div id="builderCompare">${builderComparison?builderComparisonHtml(builderComparison):''}</div></div></details></div>`;
};
function selectCharacterSlot(slot,mode='gear'){
  characterPane='catalog';
  characterSlot=slot;characterEditKind=mode;characterPreviewId=null;characterPreviewDetail=null;characterPreviewLevel=null;characterPreviewSettings=null;characterPreviewRequest++;characterLevelOpen=false;
  openPicker(slot,mode);
  characterEditKind=picker?.mode||mode;
}
function characterCategory(slot){
  selectCharacterSlot(slot,'gear');
}
function showCharacterModLevel(slot){
  characterPane='catalog';
  characterSlot=slot;characterEditKind='mod';characterPreviewId=null;characterPreviewDetail=null;characterPreviewLevel=null;characterPreviewSettings=null;characterPreviewRequest++;characterLevelOpen=true;
  if(picker?.slot!==slot||picker?.mode!=='mod')openPicker(slot,'mod');else render();
  document.querySelector('#characterModLevel')?.focus?.();
}
function setCharacterPane(pane){
  if(!['equipment','catalog'].includes(pane))return;
  if(pane==='equipment')modCollectionMode=false;
  characterPane=pane;
  const layout=document.querySelector('.character-layout');
  if(!layout)return;
  layout.classList.toggle('show-equipment',pane==='equipment');
  layout.classList.toggle('show-catalog',pane==='catalog');
  const buttons=layout.querySelectorAll?.('.character-view-switch button')||[];
  buttons.forEach((button,index)=>{const active=index===0?pane==='equipment':index===1?pane==='catalog'&&picker?.mode!=='mod':pane==='catalog'&&picker?.mode==='mod';button.classList.toggle('active',active);button.setAttribute('aria-pressed',String(active));});
}
function previewCharacterItem(id){
  const entry=catalogEntry(id);
  if(!entry||!builderCompatible(entry,characterSlot,picker?.mode||'gear'))return;
  const scroll=document.querySelector('#characterResults')?.scrollTop||0;
  const selected=planned.slots[characterSlot]||{};
  characterPreviewId=id;characterPreviewDetail=null;
  characterPreviewLevel=entry.kind==='mod'?(selected.mod_id===id?selected.mod_level:entry.observed_numeric_levels?.[0]||entry.available_level||1):null;
  characterPreviewSettings=entry.kind==='mod'?null:(selected.catalog_id===id?{tier:selected.tier,stars:selected.stars,calibration_blueprint:selected.calibration_blueprint,calibration_bonus:selected.calibration_bonus}:{});
  render();
  const result=document.querySelector('#characterResults');if(result)result.scrollTop=scroll;
  loadCharacterPreviewDetail();
}
function loadCharacterPreviewDetail(){
  const id=characterPreviewId,level=characterPreviewLevel,request=++characterPreviewRequest;
  if(!id)return;
  fetch('/api/catalog/'+encodeURIComponent(id)+(level?'?level='+level:'')).then(r=>r.json()).then(detail=>{
    if(request!==characterPreviewRequest||characterPreviewId!==id)return;
    characterPreviewDetail=detail;
    const panel=document.querySelector('#characterPreview');if(panel)panel.innerHTML=characterPreviewHtml();
  }).catch(()=>{});
}
function changeCharacterPreviewLevel(value){
  const level=Number(value);
  if(!Number.isInteger(level)||level<1||level>17){notice('Enter a Field Guide level from 1 to 17');render();return;}
  if(catalogEntry(characterPreviewId)?.kind!=='mod')return;
  characterPreviewLevel=level;characterPreviewDetail=null;
  const panel=document.querySelector('#characterPreview');if(panel)panel.innerHTML=characterPreviewHtml();
  loadCharacterPreviewDetail();
}
function changeCharacterPreviewSetting(key,value){
  const entry=catalogEntry(characterPreviewId);
  if(!entry||entry.kind==='mod'||!['tier','stars','calibration_blueprint','calibration_bonus'].includes(key))return;
  if(!characterPreviewSettings)characterPreviewSettings={};
  if(key==='tier'||key==='stars'){
    if(value==='')delete characterPreviewSettings[key];
    else {
      const n=Number(value),maximum=key==='tier'?5:selectableBlueprintStarMax(entry);
      if(!Number.isInteger(n)||n<1||n>maximum)return;
      characterPreviewSettings[key]=n;
    }
  }else characterPreviewSettings[key]=String(value).trim().slice(0,160);
  const panel=document.querySelector('#characterPreview');if(panel)panel.innerHTML=characterPreviewHtml();
}
async function equipCharacterPreview(){
  const id=characterPreviewId,entry=catalogEntry(id);
  if(!entry||!picker)return;
  characterEditKind=picker.mode;characterLevelOpen=picker.mode==='mod';
  const proposedLevel=entry.kind==='mod'?characterPreviewLevel:null;
  await previousSelectCatalogItem(id,proposedLevel);
  if(entry.kind!=='mod'&&planned.slots[picker.slot]?.catalog_id===id&&characterPreviewSettings){
    const selected=planned.slots[picker.slot];
    for(const key of ['tier','stars','calibration_blueprint','calibration_bonus']){
      if(characterPreviewSettings[key]==null||characterPreviewSettings[key]==='')delete selected[key];
      else selected[key]=characterPreviewSettings[key];
    }
    builderAnalysis=null;queueBuilderAnalysis();
  }
  characterPreviewId=id;characterPreviewLevel=entry.kind==='mod'?planned.slots[picker.slot]?.mod_level:null;characterPreviewDetail=null;
  render();
  loadCharacterPreviewDetail();
}
function renderCharacterResults(){
  const all=filteredPicker(),shown=builderFamily==='all'?all:all.filter(e=>groupName(e)===builderFamily);
  const count=document.querySelector('#characterCount');if(count)count.textContent=shown.length+' compatible choices';
  const area=document.querySelector('#characterResults');if(area)area.innerHTML=characterCatalogResultsHtml();
}
changeSlotSetting=function(slot,key,value){
  previousChangeSlotSetting(slot,key,value);
  if(slot==='primary'&&planned.slots.primary?.weapon_readout&&!characterCurrentReadout(planned.slots.primary)){
    delete planned.slots.primary.weapon_readout;render();
  }
  if(slot===characterSlot&&characterPreviewId===planned.slots[slot]?.catalog_id&&key!=='mod_level'){
    const selected=planned.slots[slot];
    characterPreviewSettings={tier:selected.tier,stars:selected.stars,calibration_blueprint:selected.calibration_blueprint,calibration_bonus:selected.calibration_bonus};
  }
  if(key!=='mod_level'||slot!==characterSlot)return;
  const selected=planned.slots[slot]||{};
  if(!selected.mod_id||selected.mod_id!==characterPreviewId||selected.mod_level===characterPreviewLevel)return;
  characterPreviewLevel=selected.mod_level;characterPreviewDetail=null;
  const panel=document.querySelector('#characterPreview');if(panel)panel.innerHTML=characterPreviewHtml();
  loadCharacterPreviewDetail();
};
newPlannedBuild=function(){characterPane='equipment';characterSlot='primary';characterEditKind='gear';characterPreviewId=null;characterPreviewDetail=null;characterPreviewLevel=null;characterPreviewSettings=null;characterPreviewRequest++;characterLevelOpen=false;previousNewPlannedBuild()};
openPlannedBuild=function(id){
  previousOpenPlannedBuild(id);
  const first=['primary','secondary','melee','helmet','mask','top','gloves','bottoms','shoes'].find(slot=>planned.slots[slot]?.catalog_id)||'primary';
  characterPane='equipment';characterSlot=first;characterEditKind='gear';characterPreviewId=null;characterPreviewDetail=null;characterPreviewLevel=null;characterPreviewSettings=null;characterPreviewRequest++;characterLevelOpen=false;
  picker={slot:first,mode:'gear',tab:['secondary','melee'].includes(first)?'primary':first};
  render();
};

/* Personal collection and compact, item-local actions. */
let characterPreviewInventoryId=null,characterPopoverOrigin='catalog',characterRecycleConfirm=false,characterPointer=null;
let characterSlotMenuOpen=false,characterSlotSearch='';
builderFilter='mine';

characterBoard=function(){
  return `<section class="character-board" aria-label="Character loadout">
    <div class="character-stage">${characterFigure()}${characterCombatStatsHtml()}<div class="character-stage-caption"><strong>LOADOUT</strong><span>Planned equipment · appearance is illustrative</span></div></div>
    <div class="character-gear-panel"><div class="character-gear-head"><div><small>YOUR SETUP</small><h2>Equipment</h2></div><button class="secondary" onclick="openSavedGear()">Saved gear</button></div>
      <div class="character-section-label">Weapons <span>${['primary','secondary','melee'].filter(s=>planned.slots[s]?.catalog_id).length}/3</span></div>
      <div class="character-weapon-grid">${['primary','secondary','melee'].map(characterEquipmentCard).join('')}</div>
      <div class="character-section-label">Armor <span>${['helmet','mask','gloves','shoes','top','bottoms'].filter(s=>planned.slots[s]?.catalog_id).length}/6</span></div>
      <div class="character-armor-grid">${['helmet','mask','gloves','shoes','top','bottoms'].map(characterEquipmentCard).join('')}</div>
      <details class="character-stats"><summary>Build details and known stats</summary><div id="characterKnownStats">${builderAnalysisHtml()}</div></details>
    </div></section>`;
};

function characterCollectionEntries(){
  if(picker?.mode==='mod')return filteredPicker();
  if(builderFilter==='mine')return (builderData.my_gear||[]).map(item=>{
    const entry=catalogEntry(item.catalog_id);
    return entry?{...entry,inventory_id:item.id,inventory_settings:item}:null;
  }).filter(entry=>entry&&builderCompatible(entry,characterSlot,'gear'));
  if(!builderQuery.trim())return [];
  const query=builderQuery.toLowerCase();
  return builderData.entries.filter(entry=>builderCompatible(entry,characterSlot,'gear')&&
    [entry.name,entry.base_name,entry.variant,entry.family,entry.set_name].some(value=>String(value||'').toLowerCase().includes(query)));
}
characterCatalogCard=function(entry){
  const personal=!!entry.inventory_id;
  const selected=planned.slots[characterSlot]||{};
  const preview=characterPreviewId===entry.id&&characterPreviewInventoryId===(entry.inventory_id||null);
  const equipped=personal?selected.inventory_id===entry.inventory_id:selected.catalog_id===entry.id;
  return `<button class="character-catalog-card ${esc(entry.rarity||'unknown')} ${preview?'preview':''} ${equipped?'equipped':''}" data-id="${esc(entry.id)}" data-inventory-id="${esc(entry.inventory_id||'')}" onclick="previewCharacterItem(this.dataset.id,this.dataset.inventoryId||null,event)" aria-label="${personal?'Open saved item':'Preview catalog item'} ${esc(entry.name)}" aria-pressed="${preview}">
    <span class="catalog-card-art">${characterArt(entry)}</span><span class="character-card-name">${esc(entry.base_name)}</span><small>${esc(entry.variant||entry.set_name||entry.weapon_category||entry.family||'')}</small><span class="card-state">${personal?'SAVED':equipped?'EQUIPPED':'PREVIEW'}</span>
  </button>`;
};
characterCatalogResultsHtml=function(){
  const all=characterCollectionEntries(),shown=builderFamily==='all'?all:all.filter(entry=>groupName(entry)===builderFamily);
  if(!shown.length)return `<div class="character-empty">${builderFilter==='all'&&!builderQuery.trim()?'Search a name such as AUG to find variants.':builderFilter==='mine'?'No saved gear for this slot. Choose Find Gear to add one.':'No matching items.'}</div>`;
  const groups=shown.reduce((map,entry)=>((map[groupName(entry)]??=[]).push(entry),map),{});
  return Object.entries(groups).sort(([a],[b])=>a.localeCompare(b)).map(([family,entries])=>`<section class="character-family"><h3>${esc(family)}</h3><div class="character-card-grid">${entries.map(characterCatalogCard).join('')}</div></section>`).join('');
};
characterCatalogHtml=function(){
  const slot=characterSlot,canMod=!!builderMods[slot]&&!!planned.slots[slot]?.catalog_id;
  const all=characterCollectionEntries(),families=[...new Set(all.map(groupName))].sort();
  return `<section class="character-catalog" aria-label="Saved gear"><div class="character-catalog-top"><div class="catalog-heading"><div><small>${picker?.mode==='mod'?'FIELD GUIDE':'SAVED GEAR'}</small><h2>${esc(characterNames[slot])}</h2></div><button class="secondary" onclick="setCharacterPane('equipment')">← Loadout</button></div>
    <div class="character-category-tabs">${builderTabs.map(([label,target])=>`<button class="${slot===target||target==='primary'&&['secondary','melee'].includes(slot)?'active':''}" onclick="characterCategory('${target}')">${label}</button>`).join('')}</div>
    <div class="character-search-mode">${builderFilter==='all'&&picker?.mode==='gear'?`<button onclick="setCharacterScope('mine')">← Saved gear</button>`:`<button onclick="setCharacterScope('all')">Find Gear</button>`}<button class="${picker?.mode==='mod'?'active':''}" ${canMod?'':'disabled'} onclick="selectCharacterSlot('${slot}','mod')">Mods</button></div>
    <div class="character-filters">${builderFilter==='all'||picker?.mode==='mod'?`<input id="characterSearch" aria-label="Search compatible items" placeholder="Search ${esc(characterNames[slot].toLowerCase())}…" value="${esc(builderQuery)}" oninput="builderQuery=this.value;renderCharacterResults()">`:''}<select aria-label="Filter family or set" id="characterFamily" onchange="builderFamily=this.value;renderCharacterResults()"><option value="all">All families / sets</option>${families.map(f=>`<option value="${esc(f)}" ${builderFamily===f?'selected':''}>${esc(f)}</option>`).join('')}</select></div><small id="characterCount" class="character-count">${all.length} ${builderFilter==='mine'?'saved items':'matching choices'}</small></div>
    <div id="characterResults" class="character-results" data-slot="${slot}" data-mode="${picker?.mode||'gear'}">${characterCatalogResultsHtml()}</div></section>`;
};

function characterPopoverHtml(){
  if(characterSlotMenuOpen)return characterSlotMenuHtml();
  const entry=catalogEntry(characterPreviewId);
  if(!entry)return '';
  const owned=(builderData.my_gear||[]).find(item=>item.id===characterPreviewInventoryId);
  const settings=characterPreviewSettings||{},slot=characterSlot;
  const equipped=(entry.kind==='mod'?planned.slots[slot]?.mod_id:planned.slots[slot]?.catalog_id)===entry.id&&(!owned||planned.slots[slot]?.inventory_id===owned.id);
  const attributes=characterPreviewDetail?.known_attributes||[];
  const attributeText=attribute=>`${attribute.name} ${attribute.value_percent==null?'value unknown':(attribute.direction==='reduction'?'−':'+')+attribute.value_percent+'%'}${attribute.conditional_bonus_percent==null?'':' · extra +'+attribute.conditional_bonus_percent+'% when '+(attribute.condition||'condition unknown')}`;
  return `<div id="characterPopover" class="character-popover" role="dialog" aria-label="${esc(entry.name)} actions"><div class="character-popover-head">${characterArt(entry,true)}<div><small>${owned?'SAVED GEAR':entry.kind==='mod'?'MOD PREVIEW':'CATALOG PREVIEW'}</small><h3>${esc(entry.name)}</h3></div><button class="popover-close" aria-label="Close item actions" onclick="closeCharacterPopover()">×</button></div>
    ${entry.kind==='mod'?`<label class="character-preview-level">Proposed Field Guide level<input aria-label="Proposed Field Guide level" type="number" min="1" max="17" value="${esc(characterPreviewLevel||1)}" onchange="changeCharacterPreviewLevel(this.value)"></label><div class="character-visible-stats">${attributes.length?esc(attributes.slice(0,2).map(attributeText).join(' · ')):'Numeric values unverified at this level'}</div>`:`${characterTierControls(slot,settings, true)}${characterStarControls(slot,settings,entry,true)}${entry.kind==='weapon'?characterCalibrationControls(settings):''}${entry.kind==='weapon'&&slot!=='melee'?characterAccessoryControls(settings,entry.id):''}${entry.kind==='weapon'&&slot!=='melee'?characterWeaponStatsControls(settings):''}`}
    <div class="character-popover-actions">${!owned&&entry.kind!=='mod'?`<button class="primary" onclick="addCharacterGear()">Add</button>`:''}<button class="${!owned&&entry.kind!=='mod'?'secondary':'primary'}" ${entry.kind==='mod'&&!planned.slots[slot]?.catalog_id?'disabled title="Equip gear in this slot first"':''} onclick="equipCharacterPreview()">${equipped?'Apply to build':'Equip'}</button>${owned&&entry.kind!=='mod'?`<button class="secondary" onclick="saveCharacterGearSettings()">Save settings</button>`:''}${equipped?`<button class="secondary" onclick="unequipCharacterItem()">Unequip</button>`:''}</div><small class="character-action-help">Equip assigns this item to the current build. Add saves gear to your collection.</small>${entry.kind!=='mod'&&characterPopoverOrigin==='equipment'?`<button class="text-button character-swap" onclick="openCharacterSlotMenu('${slot}')">Choose another ${esc(characterNames[slot].toLowerCase())}</button>`:''}
    ${owned?`<div class="recycle-line">${characterRecycleConfirm?`<button class="danger" onclick="recycleCharacterGear()">Confirm recycle</button><button onclick="characterRecycleConfirm=false;render()">Cancel</button>`:`<button onclick="characterRecycleConfirm=true;render()">Recycle this entry</button>`}<small>Removes this saved entry only. Builds remain.</small></div>`:''}
    <details class="character-popover-details"><summary>Effects, evidence and limits</summary><p>${esc(characterPreviewDetail?.primary_effect||entry.effect||'Effect not cataloged')}</p>${attributes.length?`<ul>${attributes.map(attribute=>`<li>${esc(attributeText(attribute))}</li>`).join('')}</ul>`:''}<p>${esc(owned?owned.source_observation?'Added from confirmed observation':'Manually saved gear':'Preview only · collection unchanged')}</p>${characterPreviewDetail?.unknowns?.length?`<p>${esc(characterPreviewDetail.unknowns.join('; '))}</p>`:''}</details>
  </div>`;
}
function characterSlotMenuHtml(){
  const slot=characterSlot;
  const saved=(builderData.my_gear||[]).map(item=>{const entry=catalogEntry(item.catalog_id);return entry&&builderCompatible(entry,slot,'gear')?{entry,item}:null}).filter(Boolean);
  const query=characterSlotSearch.trim().toLowerCase();
  const found=query?builderData.entries.filter(entry=>builderCompatible(entry,slot,'gear')&&[entry.name,entry.base_name,entry.variant,entry.family,entry.set_name].some(value=>String(value||'').toLowerCase().includes(query))).slice(0,20):[];
  const choice=(entry,item=null)=>{
    const owned=!!item,settings=owned?[item.tier?'T'+['','I','II','III','IV','V'][item.tier]:'Tier unknown',item.stars?item.stars+'★':'Stars unknown',item.calibration_profile?.style||item.calibration_blueprint||'',item.calibration_profile?.rolls?.map(roll=>`${roll.stat} ${roll.value_percent}%`).join(', ')||''].filter(Boolean).join(' · '):'Catalog preview · Add to save';
    const name=esc(entry.name),id=esc(entry.id);
    return owned?`<div class="slot-menu-row"><button class="slot-menu-choice" data-inventory-id="${esc(item.id)}" onclick="equipSavedGearFromChooser(this.dataset.inventoryId)" aria-label="Equip saved ${name}, ${esc(settings)}, instance ${esc(item.id.slice(0,6))}">${characterArt(entry,true)}<span><strong>${name}</strong><small>${esc(settings)} · #${esc(item.id.slice(0,6))}</small></span></button><button class="slot-menu-edit" data-id="${id}" data-inventory-id="${esc(item.id)}" onclick="previewCharacterItem(this.dataset.id,this.dataset.inventoryId,event)" aria-label="Edit or upgrade saved ${name}">Edit / upgrade</button></div>`:
      `<button class="slot-menu-choice" data-id="${id}" onclick="previewCharacterItem(this.dataset.id,null,event)">${characterArt(entry,true)}<span><strong>${name}</strong><small>${settings}</small></span></button>`;
  };
  return `<div id="characterPopover" class="character-popover character-slot-menu" role="dialog" aria-label="Choose ${esc(characterNames[slot])} gear"><div class="character-popover-head"><div><small>${esc(characterNames[slot].toUpperCase())}</small><h3>Choose gear</h3></div><button class="popover-close" aria-label="Close gear choices" onclick="closeCharacterPopover()">×</button></div><div class="slot-menu-scroll"><strong>Saved gear · click to equip</strong>${saved.length?saved.map(({entry,item})=>choice(entry,item)).join(''):'<p class="slot-menu-empty">No saved gear for this slot yet.</p>'}<label class="slot-menu-search">Find Gear<input id="slotGearSearch" type="search" autocomplete="off" placeholder="Search AUG or another item…" value="${esc(characterSlotSearch)}" oninput="setCharacterSlotSearch(this.value)"></label>${query?`<div class="slot-menu-results"><strong>Catalog matches</strong>${found.length?found.map(entry=>choice(entry)).join(''):'<p class="slot-menu-empty">No matching catalog items.</p>'}</div>`:''}</div></div>`;
}
async function equipSavedGearFromChooser(inventoryId){
  const item=(builderData.my_gear||[]).find(row=>row.id===inventoryId),entry=item&&catalogEntry(item.catalog_id),slot=characterSlot;
  if(!item||!entry||!builderCompatible(entry,slot,'gear')||!characterSlotMenuOpen)return;
  characterSlotMenuOpen=false;characterPopoverOrigin='equipment';characterPreviewId=entry.id;characterPreviewInventoryId=item.id;
  characterPreviewSettings={tier:item.tier,stars:item.stars,calibration_blueprint:item.calibration_blueprint,calibration_bonus:item.calibration_bonus,calibration_profile:item.calibration_profile?structuredClone(item.calibration_profile):null,calibration_upgrade_level:item.calibration_upgrade_level,accessories:structuredClone(item.accessories||{}),weapon_stats:item.weapon_stats?structuredClone(item.weapon_stats):null};
  characterPreviewSettings.weapon_stats_context=characterMeasurementSignature(characterPreviewSettings);
  await equipCharacterPreview();
}
function setCharacterSlotSearch(value){
  characterSlotSearch=String(value).slice(0,100);
  const position=document.querySelector('#slotGearSearch')?.selectionStart;
  render();placeCharacterPopover();
  const input=document.querySelector('#slotGearSearch');input?.focus?.({preventScroll:true});
  if(position!=null)input?.setSelectionRange?.(position,position);
}
function openCharacterSlotMenu(slot,trigger=null){
  if(characterSlotMenuOpen&&characterSlot===slot){closeCharacterPopover();return;}
  characterPane='equipment';characterSlot=slot;characterEditKind='gear';picker={slot,mode:'gear',tab:['secondary','melee'].includes(slot)?'primary':slot};
  characterSlotMenuOpen=true;characterSlotSearch='';characterPreviewId=null;characterPreviewInventoryId=null;characterPreviewDetail=null;
  characterPopoverOrigin='equipment';characterPointer=trigger?.detail?{x:trigger.clientX,y:trigger.clientY}:null;
  render();placeCharacterPopover();document.querySelector('#slotGearSearch')?.focus?.({preventScroll:true});
}
const characterBuilderPageWithCatalog=builderPage;
builderPage=function(){
  return characterBuilderPageWithCatalog().replace('<details class="builder-secondary character-advice"',characterPopoverHtml()+'<details class="builder-secondary character-advice"');
};

function placeCharacterPopover(){
  const panel=document.querySelector('#characterPopover');if(!panel)return;
  const inventory=characterPreviewInventoryId||'';
  const anchor=characterPopoverOrigin==='equipment'?document.querySelector(`.character-equip[data-character-slot="${characterSlot}"]`):
    [...document.querySelectorAll('.character-catalog-card')].find(node=>node.dataset.id===characterPreviewId&&(node.dataset.inventoryId||'')===inventory);
  const rect=anchor?.getBoundingClientRect()||{left:innerWidth/2,top:innerHeight/2,right:innerWidth/2,bottom:innerHeight/2};
  const width=panel.offsetWidth,height=panel.offsetHeight,pad=12;
  let left=characterPointer?characterPointer.x-width*.25:rect.right+10;
  if(characterPopoverOrigin==='equipment'){
    const gearLeft=document.querySelector('.character-gear-panel')?.getBoundingClientRect()?.left??pad;
    left=Math.max(gearLeft+8,Math.min(characterPointer?characterPointer.x-width*.25:rect.left,innerWidth-width-pad));
  }else{
    if(left+width>innerWidth-pad)left=rect.left-width-10;
    if(left<pad)left=Math.min(Math.max(pad,rect.left),innerWidth-width-pad);
  }
  panel.style.left=Math.max(pad,left)+'px';
  const top=characterSlotMenuOpen?rect.top:characterPointer?characterPointer.y-height+56:rect.top;
  panel.style.top=Math.max(characterPopoverOrigin==='equipment'?Math.min(100,innerHeight-height-pad):pad,Math.min(top,innerHeight-height-pad))+'px';
}
function closeCharacterPopover(){
  const id=characterPreviewId,inventory=characterPreviewInventoryId,slot=characterSlot,origin=characterPopoverOrigin;
  characterPreviewId=null;characterPreviewInventoryId=null;characterPreviewDetail=null;characterRecycleConfirm=false;characterPointer=null;characterSlotMenuOpen=false;render();
  const target=origin==='equipment'?document.querySelector(`.character-equip[data-character-slot="${slot}"] .character-gear-target`):
    [...(document.querySelectorAll?.('.character-catalog-card')||[])].find(node=>node.dataset.id===id&&(node.dataset.inventoryId||'')===(inventory||''));
  target?.focus?.({preventScroll:true});
}
function unequipCharacterItem(){
  const slot=characterSlot,entry=catalogEntry(characterPreviewId);if(!entry)return;
  closeCharacterPopover();if(entry.kind==='mod')removePlannedMod(slot);else removePlanned(slot);
  notice('Unequipped from this build. Saved gear is unchanged.');
}
function setCharacterScope(scope){
  builderFilter=scope;builderQuery='';builderFamily='all';characterEditKind='gear';
  if(picker)picker.mode='gear';characterPreviewId=null;characterPreviewInventoryId=null;render();
  if(scope==='all')document.querySelector('#characterSearch')?.focus();
}
function openSavedGear(){
  modCollectionMode=false;
  characterPane='catalog';characterEditKind='gear';characterPreviewId=null;characterPreviewInventoryId=null;characterPreviewDetail=null;characterPointer=null;
  builderFilter='mine';builderQuery='';builderFamily='all';
  picker={slot:characterSlot,mode:'gear',tab:['secondary','melee'].includes(characterSlot)?'primary':characterSlot};
  render();
}
const originalSelectCharacterSlot=selectCharacterSlot;
selectCharacterSlot=function(slot,mode='gear',trigger=null){
  if(characterPane==='equipment'&&mode==='gear'&&!planned.slots[slot]?.catalog_id){openCharacterSlotMenu(slot,trigger);return;}
  if(characterPane==='equipment'&&mode==='gear'&&planned.slots[slot]?.catalog_id){
    if(characterPopoverOrigin==='equipment'&&characterPreviewId===planned.slots[slot].catalog_id&&characterSlot===slot){closeCharacterPopover();return;}
    characterPointer=trigger?.detail?{x:trigger.clientX,y:trigger.clientY}:null;
    characterSlot=slot;characterEditKind=mode;characterPopoverOrigin='equipment';
    characterPreviewId=planned.slots[slot].catalog_id;characterPreviewInventoryId=planned.slots[slot].inventory_id||null;
    characterPreviewSettings={...planned.slots[slot]};
    const saved=(builderData.my_gear||[]).find(item=>item.id===characterPreviewInventoryId);
    const current=slot==='primary'?characterCurrentReadout(planned.slots[slot]):null;
    const savedMatches=saved&&characterMeasurementSignature(characterPreviewSettings)===characterMeasurementSignature(saved);
    characterPreviewSettings.weapon_stats=current?Object.fromEntries(['attack','rpm','magazine','reload_seconds'].filter(key=>current[key]!=null).map(key=>[key,current[key]])):savedMatches?saved.weapon_stats||null:null;
    characterPreviewSettings.weapon_stats_context=characterMeasurementSignature(characterPreviewSettings);
    characterRecycleConfirm=false;render();placeCharacterPopover();document.querySelector('#characterPopover .popover-close')?.focus?.({preventScroll:true});loadCharacterPreviewDetail();return;
  }
  characterPreviewInventoryId=null;characterPreviewId=null;characterPointer=null;characterPopoverOrigin='catalog';builderFilter=mode==='mod'?'all':'mine';
  originalSelectCharacterSlot(slot,mode);
};
previewCharacterItem=function(id,inventoryId=null,trigger=null){
  const entry=catalogEntry(id);if(!entry)return;
  if(characterPreviewId===id&&characterPreviewInventoryId===inventoryId){closeCharacterPopover();return;}
  const owned=(builderData.my_gear||[]).find(item=>item.id===inventoryId);
  const selected=planned.slots[characterSlot]||{};
  characterPreviewId=id;characterPreviewInventoryId=inventoryId;characterPointer=trigger?.detail?{x:trigger.clientX,y:trigger.clientY}:null;characterPopoverOrigin=characterSlotMenuOpen?'equipment':'catalog';characterSlotMenuOpen=false;characterRecycleConfirm=false;characterPreviewDetail=null;
  characterPreviewSettings=owned?{tier:owned.tier,stars:owned.stars,calibration_blueprint:owned.calibration_blueprint,calibration_bonus:owned.calibration_bonus,calibration_profile:owned.calibration_profile?structuredClone(owned.calibration_profile):null,calibration_upgrade_level:owned.calibration_upgrade_level,accessories:structuredClone(owned.accessories||{}),weapon_stats:owned.weapon_stats?structuredClone(owned.weapon_stats):null}:selected.catalog_id===id?{tier:selected.tier,stars:selected.stars,calibration_blueprint:selected.calibration_blueprint,calibration_bonus:selected.calibration_bonus,calibration_profile:selected.calibration_profile?structuredClone(selected.calibration_profile):null,calibration_upgrade_level:selected.calibration_upgrade_level,accessories:structuredClone(selected.accessories||{})}:{};
  characterPreviewSettings.weapon_stats_context=characterMeasurementSignature(characterPreviewSettings);
  characterPreviewLevel=entry.kind==='mod'?(selected.mod_id===id?selected.mod_level:entry.observed_numeric_levels?.[0]||entry.available_level||1):null;
  render();placeCharacterPopover();document.querySelector('#characterPopover .popover-close')?.focus?.({preventScroll:true});loadCharacterPreviewDetail();
};
loadCharacterPreviewDetail=function(){
  const id=characterPreviewId,level=characterPreviewLevel,request=++characterPreviewRequest;if(!id)return;
  fetch('/api/catalog/'+encodeURIComponent(id)+(level?'?level='+level:'')).then(r=>r.json()).then(detail=>{
    if(request!==characterPreviewRequest||characterPreviewId!==id)return;
    characterPreviewDetail=detail;const old=document.querySelector('#characterPopover');
    const label=document.activeElement?.getAttribute?.('aria-label');
    if(old){old.outerHTML=characterPopoverHtml();placeCharacterPopover();if(label)[...(document.querySelectorAll?.('#characterPopover [aria-label]')||[])].find(node=>node.getAttribute('aria-label')===label)?.focus?.({preventScroll:true});}
  }).catch(()=>{});
};
changeCharacterPreviewSetting=function(key,value){
  const entry=catalogEntry(characterPreviewId);if(!entry||entry.kind==='mod')return;
  if(!characterPreviewSettings)characterPreviewSettings={};
  if(key==='tier'||key==='stars'){
    if(value==='')delete characterPreviewSettings[key];
    else {const n=Number(value),max=key==='tier'?5:selectableBlueprintStarMax(entry);if(!Number.isInteger(n)||n<1||n>max)return;characterPreviewSettings[key]=n;}
  }else characterPreviewSettings[key]=String(value).trim().slice(0,160);
  const label=document.activeElement?.getAttribute?.('aria-label');
  const old=document.querySelector('#characterPopover');if(old){old.outerHTML=characterPopoverHtml();placeCharacterPopover();if(label)[...(document.querySelectorAll?.('#characterPopover [aria-label]')||[])].find(node=>node.getAttribute('aria-label')===label)?.focus?.({preventScroll:true});}
};
function refreshCharacterCalibration(){const old=document.querySelector('#characterPopover');if(old){old.outerHTML=characterPopoverHtml();placeCharacterPopover();}}
function chooseCalibrationExample(key){
  const example=calibrationExamples[key];if(!example||!catalogEntry(characterPreviewId)||!['primary','secondary','melee'].includes(characterSlot))return;
  characterPreviewSettings??={};characterPreviewSettings.calibration_profile=structuredClone(example);
  refreshCharacterCalibration();notice('Calibration example copied into this proposal. Add or save explicitly.');
}
function changeCharacterCalibration(key,value){
  if(!catalogEntry(characterPreviewId)||!['primary','secondary','melee'].includes(characterSlot))return;
  characterPreviewSettings??={};
  if(key==='legacy_blueprint'||key==='legacy_bonus'){
    characterPreviewSettings[key==='legacy_blueprint'?'calibration_blueprint':'calibration_bonus']=String(value).trim().slice(0,160);
  }else if(['blueprint_name','rarity','style','fixed_effects'].includes(key)){
    const profile={...(characterPreviewSettings.calibration_profile||{})};delete profile.source_ref;
    profile[key]=String(value).trim().slice(0,key==='fixed_effects'?500:key==='style'?80:160);
    characterPreviewSettings.calibration_profile=profile;
  }
  refreshCharacterCalibration();
}
function changeCharacterCalibrationRoll(index,key,value){
  if(!Number.isInteger(index)||index<0||index>3||!['stat','value_percent','range_min','range_max'].includes(key))return;
  characterPreviewSettings??={};const profile={...(characterPreviewSettings.calibration_profile||{})};delete profile.source_ref;
  const rolls=(profile.rolls||[]).map(item=>({...item}));while(rolls.length<=index)rolls.push({});
  if(key==='stat')rolls[index][key]=String(value).trim().slice(0,80);
  else if(String(value).trim()==='')delete rolls[index][key];
  else {const number=Number(value);if(!Number.isFinite(number)||number< -1000||number>1000)return;rolls[index][key]=number;}
  profile.rolls=rolls;characterPreviewSettings.calibration_profile=profile;refreshCharacterCalibration();
}
function addCharacterCalibrationRoll(){characterPreviewSettings??={};const profile={...(characterPreviewSettings.calibration_profile||{})};delete profile.source_ref;const rolls=[...(profile.rolls||[])];if(rolls.length>=4)return;rolls.push({});profile.rolls=rolls;characterPreviewSettings.calibration_profile=profile;refreshCharacterCalibration();}
function removeCharacterCalibrationRoll(index){const profile={...(characterPreviewSettings?.calibration_profile||{})};delete profile.source_ref;profile.rolls=(profile.rolls||[]).filter((_,i)=>i!==index);characterPreviewSettings.calibration_profile=profile;refreshCharacterCalibration();}
function changeCharacterCalibrationUpgrade(value){if(characterPreviewId==='weapon:aug-electron-cloud'){notice('AUG has no pre-2026 calibration upgrade level');return;}characterPreviewSettings??={};if(String(value).trim()==='')delete characterPreviewSettings.calibration_upgrade_level;else{const number=Number(value);if(!Number.isInteger(number)||number<0||number>100){notice('Enter a nonnegative recorded calibration upgrade level');return;}characterPreviewSettings.calibration_upgrade_level=number;}refreshCharacterCalibration();}
function clearCharacterCalibration(){if(!characterPreviewSettings)return;delete characterPreviewSettings.calibration_profile;refreshCharacterCalibration();}
changeCharacterPreviewLevel=function(value){
  const level=Number(value);if(!Number.isInteger(level)||level<1||level>17){notice('Enter a Field Guide level from 1 to 17');return;}
  characterPreviewLevel=level;characterPreviewDetail=null;const old=document.querySelector('#characterPopover');if(old){old.outerHTML=characterPopoverHtml();placeCharacterPopover();document.querySelector('#characterPopover input[aria-label="Proposed Field Guide level"]')?.focus?.({preventScroll:true});}loadCharacterPreviewDetail();
};
function characterSettingsPayload(){
  const s=characterPreviewSettings||{};
  return {catalog_id:characterPreviewId,slot:characterSlot,...Object.fromEntries(['tier','stars','calibration_blueprint','calibration_bonus'].filter(k=>s[k]!=null&&s[k]!=='').map(k=>[k,s[k]])),calibration_profile:s.calibration_profile||null,calibration_upgrade_level:s.calibration_upgrade_level??null,accessories:s.accessories||{},weapon_stats:characterProposedStats(s)};
}
async function reloadMyGear(){builderData.my_gear=(await(await fetch('/api/builder-catalog')).json()).my_gear;}
async function addCharacterGear(){try{
  const local=characterPopoverOrigin==='equipment',item=await api('my-gear/add',characterSettingsPayload());await reloadMyGear();
  if(local){characterPreviewInventoryId=item.id;render();placeCharacterPopover();notice('Added to saved gear. Equip when you want it in this build.');}
  else{characterPreviewId=null;characterPreviewInventoryId=null;builderFilter='mine';builderQuery='';builderFamily='all';render();notice('Added to saved gear. Equip when you want it in this build.');}
}catch(error){fail(error)}}
async function saveCharacterGearSettings(){try{
  await api('my-gear/update',{id:characterPreviewInventoryId,...characterSettingsPayload()});await reloadMyGear();render();placeCharacterPopover();notice('Saved gear settings updated');
}catch(error){fail(error)}}
async function recycleCharacterGear(){try{
  if(!characterRecycleConfirm||!characterPreviewInventoryId)return;
  await api('my-gear/recycle',{id:characterPreviewInventoryId});await reloadMyGear();closeCharacterPopover();notice('Saved gear entry recycled; builds remain');
}catch(error){fail(error)}}
equipCharacterPreview=async function(){
  const id=characterPreviewId,entry=catalogEntry(id),slot=characterSlot;if(!entry||!picker)return;
  const settings=characterPreviewSettings||{},inventoryId=characterPreviewInventoryId;
  try{
    await previousSelectCatalogItem(id,entry.kind==='mod'?characterPreviewLevel:null);
    const selected=planned.slots[slot];if(!selected)return;
    if(entry.kind!=='mod'){
      for(const key of ['tier','stars','calibration_blueprint','calibration_bonus','calibration_profile','calibration_upgrade_level','accessories']){
        if(settings[key]==null||settings[key]==='')delete selected[key];else selected[key]=settings[key];
      }
      if(inventoryId)selected.inventory_id=inventoryId;else delete selected.inventory_id;
      if(slot==='primary'){
        const measured=characterProposedStats(settings);
        if(measured&&Object.keys(measured).length)selected.weapon_readout={...measured,signature:characterReadoutSignature(selected)};
        else if(selected.weapon_readout&&!characterCurrentReadout(selected))delete selected.weapon_readout;
      }
    }
    characterPane='equipment';characterSlotMenuOpen=false;characterPreviewId=null;characterPreviewInventoryId=null;characterRecycleConfirm=false;builderDirty=true;builderAnalysis=null;render();queueBuilderAnalysis();notice('Equipped in this build. Saved gear is unchanged.');
  }catch(error){fail(error)}
};
renderCharacterResults=function(){
  const all=characterCollectionEntries(),shown=builderFamily==='all'?all:all.filter(e=>groupName(e)===builderFamily);
  const count=document.querySelector('#characterCount');if(count)count.textContent=shown.length+(builderFilter==='mine'?' saved items':' matching choices');
  const area=document.querySelector('#characterResults');if(area)area.innerHTML=characterCatalogResultsHtml();
};
document.addEventListener?.('keydown',event=>{if(event.key!=='Escape')return;if(characterPane==='catalog'&&picker?.mode==='mod'){event.preventDefault();exitModPicker();return;}if(characterPreviewId||characterSlotMenuOpen){event.preventDefault();closeCharacterPopover();}});
document.addEventListener?.('pointerdown',event=>{if(characterPane==='catalog'&&picker?.mode==='mod')return;if((characterPreviewId||characterSlotMenuOpen)&&!event.target.closest('#characterPopover,.character-catalog-card,.character-equip'))closeCharacterPopover();});
document.addEventListener?.('toggle',event=>{if(event.target.closest?.('#characterPopover'))placeCharacterPopover();},true);
globalThis.addEventListener?.('resize',placeCharacterPopover);

/* Goal-based mod discovery is read-only. Candidates are evidence matches, not DPS ranks. */
let characterModGoal='electric',characterModView='overall',characterModGuidance=null,characterModRequest=0;
let characterGuidanceWeaponSlot='primary';
const characterGoalOptions=[['burn','Burn Mod'],['electric','Power Surge Mod'],['frost','Frost Vortex Mod'],['bullseye',"The Bull's Eye Mod"],['fortress_warfare','Fortress Warfare Mod'],['unstable_bomber','Unstable Bomber Mod'],['fast_gunner','Fast Gunner Mod'],['bounce','Bounce Mod'],['shrapnel','Shrapnel Mod']];

async function loadCharacterModGuidance(){
  const request=++characterModRequest;
  characterModGuidance=null;
  render();
  try{
    const result=await api('mod-guidance',{goal:characterModGoal,weapon_id:planned.slots[characterGuidanceWeaponSlot]?.catalog_id||null,weapon_slot:characterGuidanceWeaponSlot,slots:planned.slots});
    if(request!==characterModRequest)return;
    characterModGuidance=result;
    render();
  }catch(error){if(request===characterModRequest){characterModGuidance={error:String(error)};render();}}
}
function setCharacterModGoal(goal){
  if(!characterGoalOptions.some(option=>option[0]===goal))return;
  characterModGoal=goal;loadCharacterModGuidance();
}
function setCharacterModView(view){if(!['overall','owned'].includes(view))return;characterModView=view;render();}
function characterGuidanceCandidate(candidate){
  const entry=catalogEntry(candidate.id),instances=candidate.owned_instances||[];
  const level=instances[0]?.level||entry?.observed_numeric_levels?.[0]||1;
  return `<article class="mod-guidance-card"><div class="mod-guidance-art">${characterArt(entry,true)}</div><div><small>${esc(characterNames[candidate.target_slot]||candidate.slot)} · ${esc(candidate.match)}${instances.length?' · Saved mod':''}</small><strong>${esc(candidate.name)}</strong><p>${esc(candidate.effect||'Effect wording unavailable')}</p><small>${candidate.verified_numeric_levels.includes(level)?`Numeric attributes recorded at Lv ${esc(level)}; main effect not verified`:'Numeric effect at this level unverified'} · Trigger and damage impact unverified</small>${!candidate.can_equip_in_current_build?`<small>Equip ${esc(characterNames[candidate.target_slot]||candidate.target_slot)} gear first to apply</small>`:''}${/^https:\/\//.test(candidate.source_url||'')?`${characterSourceReference(candidate.source_url,'Catalog source')}`:''}</div><button class="secondary compact" data-id="${esc(candidate.id)}" data-slot="${esc(candidate.target_slot)}" data-level="${esc(level)}" onclick="previewGuidedMod(this.dataset.id,this.dataset.slot,this.dataset.level,event)">Preview</button></article>`;
}
function characterGuidanceGroup(label,items){
  if(!items.length)return `<section class="mod-guidance-group"><h3>${label}</h3><p class="muted">No ${characterModView==='owned'?'saved':'cataloged'} mod has effect wording matching this goal in this group.</p></section>`;
  const first=items.slice(0,6),more=items.slice(6);
  return `<section class="mod-guidance-group"><h3>${label} <small>${items.length} wording matches</small></h3>${first.map(characterGuidanceCandidate).join('')}${more.length?`<details><summary>Show ${more.length} more catalog matches</summary>${more.map(characterGuidanceCandidate).join('')}</details>`:''}</section>`;
}
function characterModGuidanceHtml(){
  const guide=characterModGuidance,groups=guide?.[characterModView];
  return `<section class="character-catalog mod-guidance" aria-label="Mod suggestions"><div class="character-catalog-top"><div class="catalog-heading"><div><small>BUILD MODS</small><h2>What damage do you want?</h2></div><button class="secondary" onclick="setCharacterPane('equipment')">← Loadout</button></div>
    <label class="mod-goal-label">Damage goal <select aria-label="Damage goal" onchange="setCharacterModGoal(this.value)">${characterGoalOptions.map(([key,label])=>`<option value="${key}" ${key===characterModGoal?'selected':''}>${label}</option>`).join('')}</select></label>
    <div class="mod-guidance-switch" role="group" aria-label="Mod suggestion scope"><button class="${characterModView==='overall'?'active':''}" aria-pressed="${characterModView==='overall'}" onclick="setCharacterModView('overall')">Best overall</button><button class="${characterModView==='owned'?'active':''}" aria-pressed="${characterModView==='owned'}" onclick="setCharacterModView('owned')">Best with your gear</button></div>
    <p class="mod-guidance-limit">${guide&&!guide.error?esc(guide.method):'Matching catalog effects…'} These are candidates, not proven best-in-slot or damage rankings. Preview does not equip or add gear.</p>
    ${guide?.weapon_note?`<p class="mod-guidance-limit">${esc(guide.weapon_note)}</p>`:''}</div>
    <div class="mod-guidance-results">${guide?.error?`<p role="alert">${esc(guide.error)}</p>`:groups?`${characterGuidanceGroup('Weapon mods',groups.weapon)}${characterGuidanceGroup('Clothing and armor mods',groups.armor)}`:'<p>Checking catalog and saved mods…</p>'}</div></section>`;
}
const collectionCatalogHtml=characterCatalogHtml;
characterCatalogHtml=function(){return picker?.mode==='mod'?characterModGuidanceHtml():collectionCatalogHtml();};
const collectionSelectCharacterSlot=selectCharacterSlot;
selectCharacterSlot=function(slot,mode='gear',trigger=null){
  if(mode==='mod'&&['primary','secondary'].includes(slot))characterGuidanceWeaponSlot=slot;
  collectionSelectCharacterSlot(slot,mode,trigger);
  if(mode==='mod')loadCharacterModGuidance();
};
function previewGuidedMod(id,slot,level,trigger){
  const entry=catalogEntry(id);
  if(!entry||entry.kind!=='mod'||!builderCompatible(entry,slot,'mod'))return;
  characterSlot=slot;characterEditKind='mod';picker={slot,mode:'mod',tab:slot};
  previewCharacterItem(id,null,trigger);
  characterPreviewLevel=Number(level)||1;
  loadCharacterPreviewDetail();
}
showCharacterModLevel=function(slot){
  const selected=planned.slots[slot]||{};
  if(!selected.mod_id)return selectCharacterSlot(slot,'mod');
  characterPane='equipment';characterSlot=slot;characterEditKind='mod';
  picker={slot,mode:'mod',tab:slot};
  characterPreviewId=selected.mod_id;characterPreviewInventoryId=null;
  characterPreviewLevel=selected.mod_level||1;characterPreviewDetail=null;
  characterPopoverOrigin='equipment';characterPointer=null;characterRecycleConfirm=false;
  render();placeCharacterPopover();
  document.querySelector('#characterPopover input[aria-label="Proposed Field Guide level"]')?.focus?.({preventScroll:true});
  loadCharacterPreviewDetail();
};

/* A game crafting-screen preview is a reference, never an equipped-item measurement. */
const characterWeaponReferences={'weapon:aug-electron-cloud':{tier:3,attack:101,rpm:720,magazine:40,source_id:'libfile_4b8ae3617b708191a6b13f5fbbc22c07',source_label:'Game crafting preview · 24 Oct 2026'}};
const characterObservedTooltip={catalog_id:'weapon:aug-electron-cloud',tier:4,stars:5,style:'Vanguard Style',attack:213,rpm:720,magazine:40,crit_rate_percent:25.3,crit_damage_percent:25,weakspot_damage_percent:60,source_ref:'libfile_458a126cd8bc8191b6c0ed58b5669c12'};
function characterMeasurementSignature(s){return JSON.stringify([s?.tier??null,s?.stars??null,s?.calibration_blueprint||null,s?.calibration_bonus||null,s?.calibration_profile||null,s?.calibration_upgrade_level??null,s?.accessories&&Object.keys(s.accessories).length?s.accessories:null]);}
function characterProposedStats(s){return s?.weapon_stats_context===characterMeasurementSignature(s)?s.weapon_stats||null:null;}
function characterWeaponStatsControls(s){
  const measured=characterProposedStats(s)||{};
  const field=(key,label,step)=>`<label>${label}<input type="number" min="0" step="${step}" aria-label="Saved weapon ${label}" value="${esc(measured[key]??'')}" onchange="changeCharacterPreviewWeaponStat('${key}',this.value)"></label>`;
  return `<details class="character-weapon-measure" ${measured.attack!=null||measured.rpm!=null?'open':''}><summary>Current weapon Attack and fire rate · optional</summary><p>Use values shown on this exact crafted weapon. Its inventory tooltip Attack includes applicable weapon Attack affixes; RPM includes relevant Q0900 rate affixes. Attached mods and wearer armor, food and set effects are outside those item tooltip rows and remain separate calculation inputs. A blueprint preview uses a synthetic star-only item, not your owned weapon. Attack × fire rate is an Attack-rate proxy, not direct-hit damage or DPS.</p><div>${field('attack','Attack','0.1')}${field('rpm','Fire rate (RPM)','1')}</div><small>Saved with this gear configuration. Changing tier, stars, calibration or accessories needs a fresh measurement.</small></details>`;
}
function changeCharacterPreviewWeaponStat(key,value){
  if(!['attack','rpm'].includes(key))return;
  characterPreviewSettings??={};
  const parsed=String(value).trim()===''?null:Number(value),max=key==='rpm'?5000:100000;
  if(parsed!=null&&(!Number.isFinite(parsed)||parsed<=0||parsed>max)){notice('Enter a positive current '+(key==='rpm'?'fire rate':'Attack'));return;}
  const prior=characterProposedStats(characterPreviewSettings)||{};
  characterPreviewSettings.weapon_stats={...prior};
  if(parsed==null)delete characterPreviewSettings.weapon_stats[key];else characterPreviewSettings.weapon_stats[key]=parsed;
  characterPreviewSettings.weapon_stats_context=characterMeasurementSignature(characterPreviewSettings);
}
function characterReadoutSignature(selected){return JSON.stringify([selected?.catalog_id||null,selected?.tier??null,selected?.stars??null,selected?.calibration_blueprint||null,selected?.calibration_bonus||null,selected?.inventory_id||null,selected?.calibration_profile||null,selected?.calibration_upgrade_level??null,selected?.accessories&&Object.keys(selected.accessories).length?selected.accessories:null]);}
function characterCurrentReadout(selected){const input=selected?.weapon_readout;if(input?.signature===characterReadoutSignature(selected))return input;const old=JSON.stringify([selected?.catalog_id||null,selected?.tier??null,selected?.stars??null,selected?.calibration_blueprint||null,selected?.calibration_bonus||null,selected?.inventory_id||null]);return !selected?.calibration_profile&&selected?.calibration_upgrade_level==null&&!Object.keys(selected?.accessories||{}).length&&input?.signature===old?input:null;}
function characterDirectRate(attack,rpm,magazine,reloadSeconds){
  if(!Number.isFinite(attack)||attack<=0||!Number.isFinite(rpm)||rpm<=0)return null;
  const burst=attack*rpm/60;
  const sustained=Number.isFinite(magazine)&&magazine>0&&Number.isFinite(reloadSeconds)&&reloadSeconds>=0?attack*magazine/(magazine*60/rpm+reloadSeconds):null;
  return {burst,sustained};
}
function setCharacterReadoutInput(key,value){
  if(!['attack','rpm','magazine','reload_seconds','base_trigger_chance_percent'].includes(key))return;
  const selected=planned.slots.primary;if(!selected?.catalog_id)return;
  const parsed=String(value).trim()===''?null:Number(value);
  const maximum=key==='rpm'?5000:key==='magazine'?1000:key==='reload_seconds'?120:key==='base_trigger_chance_percent'?100:100000;
  if(parsed!=null&&(!Number.isFinite(parsed)||parsed<0||parsed>maximum||(key==='magazine'&&!Number.isInteger(parsed))||(!['reload_seconds','base_trigger_chance_percent'].includes(key)&&parsed===0))){notice('Enter a valid current weapon '+key.replaceAll('_',' '));render();return;}
  const prior=characterCurrentReadout(selected)||{};
  selected.weapon_readout={...prior,signature:characterReadoutSignature(selected)};
  delete selected.weapon_readout.source_ref;
  if(parsed==null)delete selected.weapon_readout[key];else selected.weapon_readout[key]=parsed;
  builderDirty=true;render();
}
function characterCombatModHtml(selected){
  if(!selected?.mod_id)return '';
  const entry=catalogEntry(selected.mod_id);
  if(!entry)return '';
  const matches=(builderData.owned_mods||[]).filter(item=>item.catalog_id===selected.mod_id&&item.level===selected.mod_level&&item.observed_tooltip);
  const observed=matches.length===1?matches[0].observed_tooltip:null;
  const lines=observed?.attribute_lines||[];
  const core=observed?.core_effect||entry.effect||'Core effect unavailable';
  const scenario=builderAnalysis?.trigger_scenario;
  const trigger=scenario?.one_stack_percent!=null?`<div class="combat-trigger-scenario"><b>One active stack · trigger chance</b><span>${esc(scenario.base_percent)}% → ${esc(scenario.one_stack_percent)}% <small>(+${esc(scenario.change_percentage_points)} percentage points)</small></span><small>${esc(scenario.limit)}</small><details><summary>Scenario sources</summary><small>Base: ${esc(scenario.base_source)} · mod: ${esc(scenario.mod_source)}.</small></details></div>`:scenario?.needs?`<small>${esc(scenario.needs)}</small>`:'';
  return `<section class="combat-mod-impact" aria-label="Selected mod effects"><strong>Selected mod affects combat</strong><b>${esc(entry.base_name||entry.name)} · Lv ${esc(selected.mod_level??'?')}</b><span>${esc(core)}</span>${trigger}${lines.length?`<ul>${lines.map(line=>`<li>${esc(line)}</li>`).join('')}</ul>`:''}<small>${observed?.source_ref?'Exact game tooltip recorded. ':''}These effects are separate from direct fire. Power Surge event frequency and damage are unresolved, so total combat DPS is unknown; the mod's effect is not zero.</small></section>`;
}
function characterSelectedSourceRowsHtml(analysis,selected){
  const order=['primary','helmet','mask','gloves','shoes','top','bottoms'];
  const parts=order.map(slot=>(analysis?.slots||[]).find(part=>part.slot===slot)).filter(part=>part?.gear||part?.mod);
  if(!parts.length)return '';
  const fmt=value=>new Intl.NumberFormat('en-US',{maximumFractionDigits:2}).format(Math.abs(Number(value)));
  const lines=parts.map(part=>{
    const mod=part.mod,attrs=(mod?.attributes||[]).filter(row=>!row.locked),numeric=attrs.filter(row=>row.value_percent!=null);
    const bonuses=numeric.map(row=>`${esc(row.name)} ${Number(row.value_percent)<0||row.direction==='decrease'?'−':'+'}${fmt(row.value_percent)}%${row.conditional_bonus_percent!=null?`; extra +${fmt(row.conditional_bonus_percent)}% ${esc(row.condition||'when active')}`:row.condition?` (${esc(row.condition)})`:''}`);
    const uncertain=attrs.filter(row=>row.value_percent==null).length;
    const candidate=numeric.some(row=>String(row.source_status||'').startsWith('published_formula_candidate'));
    const source=!mod?'gear selection':candidate?'published level model':numeric.length?'held tooltip or exact-level row':'numeric rows unavailable';
    const details=[part.gear?.effect?`Gear: ${part.gear.effect}`:null,mod?.effect?`Mod: ${mod.effect}`:null].filter(Boolean);
    return `<li><b>${esc(part.label)} · ${esc(part.gear?.name||'No gear')}${mod?` · ${esc(mod.name)} Lv ${esc(mod.level??'?')}`:''}</b><span>${mod?bonuses.length?bonuses.join(' · '):'Mod numeric lines unavailable':'No mod attached'}${uncertain?` · ${uncertain} line${uncertain===1?'':'s'} unresolved`:''}</span>${mod?`<small>${esc(source)}; triggers and stacking are not included in the direct rate.</small>`:''}${details.length?`<details><summary>Main effects</summary><p>${details.map(esc).join(' · ')}</p></details>`:''}</li>`;
  }).join('');
  const profile=selected?.calibration_profile;
  const calibration=profile?`<div class="combat-known"><b>Planned calibration · ${esc(profile.style||profile.blueprint_name||'selected blueprint')}</b><span>${esc(profile.fixed_effects||'Fixed effect not recorded')}${(profile.rolls||[]).length?` · ${profile.rolls.map(row=>`${esc(row.stat)} ${Number(row.value_percent)<0?'−':'+'}${fmt(row.value_percent)}%`).join(' · ')}`:''}</span><small>Selected blueprint text; its effect is not silently added to an unknown current Attack.</small></div>`:'';
  const sets=(analysis?.sets||[]).filter(group=>group.count>0);
  return `${calibration}<section class="combat-known combat-selected"><b>What the selected gear contributes</b>${sets.length?`<span>Equipped set pieces: ${sets.map(group=>`${esc(group.name)} ${esc(group.count)}`).join(' · ')}. Set activation is separate.</span>`:''}<ul>${lines}</ul><small>Numeric lines are item-level facts or labeled published candidates. They are not a full damage total.</small></section>`;
}
function characterCombatStatsHtml(){
  const selected=planned.slots.primary||{},primary=catalogEntry(selected.catalog_id),analysis=builderAnalysis;
  const timing=analysis?.weapon_reference_timing;
  const invalidStar=timing?.native_selected_tier_star?.configuration_status==='exceeds_published_max_stars';
  const current=characterCurrentReadout(selected),actual=invalidStar?null:characterDirectRate(current?.attack,current?.rpm,current?.magazine,current?.reload_seconds);
  const saved=(builderData.my_gear||[]).find(item=>item.id===selected.inventory_id);
  const savedDiffers=Boolean(saved&&((saved.tier??null)!==(selected.tier??null)||(saved.stars??null)!==(selected.stars??null)));
  const fmt=value=>new Intl.NumberFormat('en-US',{maximumFractionDigits:1}).format(value);
  const style=selected.calibration_profile?.style;
  const setup=[selected.tier?`Tier ${selected.tier}`:null,selected.stars?`${selected.stars}★`:null,style].filter(Boolean).join(' ');
  const gap=invalidStar?timing.native_selected_tier_star.missing_star_reason:primary?`Need a matching direct-hit damage value for this ${setup||'selected'} weapon to calculate its damage.`:'Select a primary weapon.';
  const input=(key,label,step='1',max='')=>`<label>${label}<input type="number" min="0" ${max?`max="${max}"`:''} step="${step}" aria-label="Current primary weapon ${label}" value="${esc(current?.[key]??'')}" onchange="setCharacterReadoutInput('${key}',this.value)"></label>`;
  const recorded=[['Attack',current?.attack],['Fire rate (RPM)',current?.rpm],['Magazine',current?.magazine],['Crit rate (%)',current?.crit_rate_percent],['Crit DMG (%)',current?.crit_damage_percent],['Weakspot DMG (%)',current?.weakspot_damage_percent]].filter(([,value])=>value!=null);
  const selectedNative=timing?.native_selected_tier_star;
  const nativeAttack=timing?.native_attack_component;
  const attackProperty=timing?.native_attack_property;
  const nativeRate=timing?.native_interval_inputs?.zero_modifier_scenario;
  const nativeTierHtml=selectedNative?`<div class="combat-known"><b>Source-native tier/star Attack inputs</b><span>${selectedNative.gun_preset_attack!=null?`Tier ${esc(selectedNative.selected_tier)} gun_preset_attack ${esc(fmt(selectedNative.gun_preset_attack))}`:'Tier field unavailable'} · ${selectedNative.preset_attack_radio!=null?`${esc(selectedNative.selected_stars)}★ preset_attack_radio ${esc(fmt(selectedNative.preset_attack_radio))}`:'Star field unavailable'}</span><small>Build ${esc(selectedNative.steam_build_id)} · blueprint ${esc(selectedNative.blueprint_id)}${selectedNative.gear_id?` · gear ${esc(selectedNative.gear_id)}`:''}. The copied native method multiplies these fields without rounding. Calibration, selected bonuses and final hit damage are separate.</small>${attackProperty?`<small>Attack property rule: (initial + absolute Attack affixes) × (1 + Attack rate), then bounds. D0100 supplies absolute Attack; D0101 supplies rate. Active equipped sources and overrides are unverified, so this is not your equipped Attack.${attackProperty.attack_property_scenario?.conditional_prebound!=null?` Explicit input scenario before bounds: ${esc(fmt(attackProperty.attack_property_scenario.conditional_prebound))}.`:''}</small>`:''}${selectedNative.public_blueprint_title?`<small>Published blueprint: ${esc(selectedNative.public_blueprint_title)}${selectedNative.public_tier_one_gear_title?` · named Tier I page: ${esc(selectedNative.public_tier_one_gear_title)}`:' · Tier I gear page not independently inspected'}. No public gear numeric fields were imported for this batch.${selectedNative.name_bridge?` ${esc(selectedNative.name_bridge.source_statement)}`:''}</small>`:''}${selectedNative.public_tier_one?.star_table_status==='not present on inspected gear page'?'<small>The inspected Tier I gear page has no public star table; this star ratio is native evidence only.</small>':''}${selectedNative.identity_only_reason?`<small>${esc(selectedNative.identity_only_reason)} No damage value is imported.</small>`:''}${selectedNative.missing_star_reason?`<small>${esc(selectedNative.missing_star_reason)} The tier field remains available independently; neither field is final damage.</small>`:''}${selectedNative.catalog_id==='weapon:r500-memento'&&selectedNative.selected_tier===1&&selectedNative.selected_stars===4?'<small>The public 4★ page shows DMG 195; this native method returns 195.5 before any downstream display or damage conversion. That downstream rule is unresolved.</small>':''}</div>`:'';
  const referenceHtml=timing?.reference_status==='native_identity_only'?nativeTierHtml:timing?`<div class="combat-known"><b>Published Tier I weapon reference · not your crafted stats</b><span>${timing.rpm!=null?`${fmt(timing.rpm)} RPM`:`Fire Rate ${esc(timing.fire_rate_raw??'?')} (RPM unit unverified)`} · ${timing.magazine!=null?`${fmt(timing.magazine)}-round magazine`:'magazine unknown'}</span><small>${esc(timing.scope)}</small>${timing.native_evidence?.weapon_rpm_affix_value!=null?`<small>Local build ${esc(timing.native_evidence.steam_build_id)} has gun-base RPM affix ${esc(timing.native_evidence.weapon_rpm_affix_value)}${timing.native_evidence.weapon_rpm!=null?` and separate weapon_rpm ${esc(fmt(timing.native_evidence.weapon_rpm))}`:''}; how these apply to your crafted weapon is unknown.</small>`:''}</div>${nativeTierHtml}`:'';
  const preview=timing?.blueprint_preview;
  const previewHtml=preview?`<div class="combat-known"><b>Observed blueprint preview · Tier V · 4★</b><span>DMG ${esc(preview.raw_stats.DMG)} · Fire Rate ${esc(preview.raw_stats["Fire Rate"])} · MAG ${esc(preview.raw_stats.MAG)}</span><small>${esc(preview.scope)}${preview.frame_url?` <a href="${esc(preview.frame_url)}" target="_blank" rel="noopener">Source frame</a>`:''}</small></div>`:'';
  return `<aside id="characterCombatStats" class="character-combat-stats" aria-label="Current build combat stats"><div class="combat-stats-head"><small>BUILD DAMAGE</small><strong>${esc(primary?.name||'No primary weapon')}</strong></div><div class="combat-dps"><span>Selected build damage</span><b>Unknown</b><small>${esc(gap)}</small>${nativeAttack?.value!=null?`<small>Native tier/star weapon Attack component: <b>${esc(fmt(nativeAttack.value))}</b> (unrounded method output; not final hit damage).</small>`:''}${nativeRate?.native_return_expected!=null?`<small>Native base fire rate: <b>${esc(fmt(nativeRate.native_return_expected))} RPM</b> (0 RPM bonus; built-in-round expectation). Equipped RPM remains unknown.</small>`:''}</div><div class="combat-stats-scroll"><details class="combat-advanced"><summary>Recorded values and sources</summary>${actual?`<div class="combat-known"><b>Recorded Attack-rate proxy · not game damage</b><span>${fmt(actual.burst)} /s${actual.sustained!=null?` · ${fmt(actual.sustained)} /s with reload`:''}</span></div>`:''}${referenceHtml}${previewHtml}${primary?`<div class="combat-measure-form"><b>Exact current weapon readout</b><span>Inventory tooltip Attack includes native weapon/star and relevant item Attack affixes; RPM includes relevant Q0900 rate affixes. Attached mods and wearer armor, food and set effects do not feed those item tooltip rows and remain separate combat effects. Blueprint preview values are a star-only synthetic item, not this owned readout. Neither tooltip row proves the server holder property. Attack is not direct-hit damage.</span>${savedDiffers?`<span class="combat-setup-warning">Plan: Tier ${esc(selected.tier??'?')} ${esc(selected.stars??'?')}★; saved gear: Tier ${esc(saved.tier??'?')} ${esc(saved.stars??'?')}★. Values are not copied between them.</span>`:''}<div>${input('attack','Attack','0.1')}${input('rpm','Fire rate (RPM)')}</div>${selected.mod_id==='mod:weapon_mod:shock-rampage-power-surge'&&selected.mod_level===17?`<details><summary>Optional Power Surge trigger</summary>${input('base_trigger_chance_percent','Base Power Surge trigger chance (%)','0.1','100')}</details>`:''}<details><summary>Magazine and reload</summary><div>${input('magazine','Magazine')}${input('reload_seconds','Reload seconds','0.1')}</div></details></div>`:''}${recorded.length?`<div class="combat-stats-section">Recorded weapon values</div>${recorded.map(([label,value])=>`<div class="combat-stat-row"><span>${esc(label)}</span><b>${esc(fmt(value))}</b></div>`).join('')}`:''}${characterSelectedSourceRowsHtml(analysis,selected)}${characterCombatModHtml(selected)}</details></div></aside>`;
}

// The normal Build view calls the same selected-build timed service as Compare.
// These controls are an unsaved source-page hypothesis, never a crafted stat.
let builderTimedInputs={},builderTimedResult=null,builderTimedResultKey='',builderTimedWeaponKey='';
const characterCombatStatsBeforeTimed=characterCombatStatsHtml;
let builderBulletInputs={},builderBulletResult=null,builderBulletResultKey='',builderBulletWeaponKey='',builderBulletRequest=0;
function builderBulletScenarioHtml(){
  const selected=planned.slots.primary||{};
  if(!selected.catalog_id)return '';
  const weaponKey=JSON.stringify([selected.catalog_id,selected.tier,selected.stars,selected.calibration_profile,
    selected.calibration_blueprint,selected.calibration_bonus,selected.inventory_id,selected.accessories]);
  if(builderBulletWeaponKey!==weaponKey){
    builderBulletWeaponKey=weaponKey;builderBulletInputs={};builderBulletResult=null;++builderBulletRequest;
  }
  const value=(key,fallback='')=>builderBulletInputs[key]??fallback;
  const field=(key,label,fallback='')=>`<label>${esc(label)}<input id="bullet-${key}" type="number" min="0" step="any" value="${esc(value(key,fallback))}" oninput="builderBulletInputs.${key}=this.value;invalidateBuilderBulletScenario()"></label>`;
  const checked=key=>value(key,false)===true?'checked':'';
  const attackSource=value('source','item_tooltip');
  return `<details class="combat-advanced"><summary>One direct bullet · controlled native graph</summary><p class="small">Enter this selected weapon's inventory-tooltip Attack and an explicit crit/weakspot outcome. Saved readouts are not copied into this field because their source may be a Gear summary. All other source graph factors stay neutral only if you confirm that scenario; this is not measured damage or a full-build DPS result.</p><label>Attack reading source<select id="bullet-source" onchange="builderBulletInputs.source=this.value;invalidateBuilderBulletScenario()"><option value="item_tooltip" ${attackSource==='item_tooltip'?'selected':''}>Exact selected item tooltip</option><option value="gear_weapon_summary" ${attackSource==='gear_weapon_summary'?'selected':''}>Gear Config Primary Weapon summary · current or preview unknown</option><option value="basic_holder" ${attackSource==='basic_holder'?'selected':''}>Expanded Basic Stats Attack · current holder</option></select></label><div class="formgrid">${field('attack','Entered Attack')}${field('critBonus','Crit damage addition (%)')}${field('weakBonus','Weakspot damage addition (%)')}</div><label><input id="bullet-crit" type="checkbox" ${checked('crit')} onchange="builderBulletInputs.crit=this.checked;invalidateBuilderBulletScenario()"> This bullet crits</label><label><input id="bullet-weak" type="checkbox" ${checked('weak')} onchange="builderBulletInputs.weak=this.checked;invalidateBuilderBulletScenario()"> This bullet hits a weakspot</label><label><input id="bullet-tooltip" type="checkbox" ${checked('tooltip')} onchange="builderBulletInputs.tooltip=this.checked;invalidateBuilderBulletScenario()"> Attack was read from this exact selected item configuration</label><label><input id="bullet-neutral" type="checkbox" ${checked('neutral')} onchange="builderBulletInputs.neutral=this.checked;invalidateBuilderBulletScenario()"> Model all other source graph and target factors as neutral (1 or 0 as appropriate); no attack-type rate dictionary</label><button type="button" class="secondary" onclick="runBuilderBulletScenario()">Calculate this conditional bullet</button><div id="bullet-result" aria-live="polite">${builderBulletResultHtml()}</div></details>`;
}
function builderBulletResultHtml(){
  const result=builderBulletResultKey===JSON.stringify([planned.slots.primary||{},builderBulletInputs])?builderBulletResult:null;
  const outcome=result?.native_player_bullet_scenario;
  if(outcome?.status==='conditional_player_bullet_formula')return `<strong>Conditional pre-settlement graph value: ${esc(outcome.graph_final_attack)}</strong><small>${esc(result.attack)} × (1 + ${esc(result.crit)} + ${esc(result.weak)}) × neutral other factors = ${esc(outcome.graph_final_attack)}. Joint crit and weakspot additions share one factor.</small><small>Item-tooltip Attack is a caller-supplied hypothesis for holder Attack; equivalence is unproven. Final HP loss and DPS remain unknown.</small><details><summary>Native proof and exclusions</summary><small>Game build ${esc(outcome.source.build)} · trace SHA-256 ${esc(outcome.source.trace_sha256)}. Item Attack already includes applicable item affixes. This scenario omits status, procs, reload, field adjustments, shield, target mitigation, level settlement and invulnerability.</small></details>`;
  return result?.error?`<small class="note warn">${esc(result.error)}</small>`:'';
}
function builderObservedPanelHtml(){
  const observation=builderAnalysis?.unlinked_character_panel_observation;
  if(!observation)return '';
  const weapon=observation.observed.primary_weapon_panel;
  const basic=observation.observed.expanded_basic_stats;
  const battle=observation.observed.expanded_battle_stats;
  const bindings=observation.native_display_bindings;
  const links=observation.sources.map(source=>`<a href="${esc(source.image_url)}" target="_blank" rel="noopener">${esc(source.panel)} source</a>`).join(' · ');
  return `<details class="combat-advanced"><summary>Observed Gear Config panels · unlinked</summary><p class="small">Primary Weapon panel: Attack ${esc(weapon.attack)}, Fire Rate ${esc(weapon.fire_rate_display)}, magazine ${esc(weapon.magazine_capacity)}. Character panel: Psi ${esc(basic.psi_intensity)}, HP ${esc(basic.hp_current)}/${esc(basic.hp_max)}; Basic Attack ${esc(basic.attack)}. Battle panel: Crit Rate ${esc(battle.crit_rate_percent)}%, Crit DMG ${esc(battle.crit_damage_percent)}%, Weakspot DMG ${esc(battle.weakspot_damage_percent)}%.</p><small>Native Gear summary can use current holder Attack. With another weapon selected, it may show a client replacement preview, but a nonzero holder value can still take precedence. These images do not reveal which branch produced ${esc(weapon.attack)}. Expanded Basic Attack ${esc(basic.attack)} reads current holder D01, not a free +${esc(basic.attack)} bonus; do not add it to the summary. Battle crit, crit-damage and weakspot rows read current holder E01/E02/E03; a displayed 0.0% crit rate does not determine this bullet's outcome. None of these values is matched to this plan or applied to its damage. Exact weapon/armor IDs, tier, stars and calibration are not visible. ${links}.</small><details><summary>Native display binding</summary><small>Build ${esc(bindings.installed_build_id)} · binding SHA-256 ${esc(bindings.source_sha256)} · preview SHA-256 ${esc(bindings.replacement_preview_source_sha256)}. The preview copies holder changes, removes held-weapon affixes, adds selected-weapon affixes, then recalculates and rounds. Actual item IDs, affix maps and holder changes are unavailable; no 422-from-20 calculation is supported.</small></details></details>`;
}
function builderHistoricalGearTourHtml(){
  const bundle=builderAnalysis?.historical_gear_tour_snapshot;
  if(!bundle)return '';
  const tour=bundle.observation,one=bundle.controlled_one_bullet_example;
  const item=tour.recorded_weapon,summary=tour.recorded_gear_summary;
  const nov2=tour.later_nov2_summary;
  const basic=builderAnalysis.unlinked_character_panel_observation?.observed?.expanded_basic_stats;
  const source=(row,label)=>`<a href="${esc(row.source_frame.url)}" target="_blank" rel="noopener">${esc(label)} at 0:${String(row.source_frame.second).padStart(2,'0')}</a>`;
  const armor=tour.equipped_items.filter(row=>row.slot!=='primary_weapon_1').map(row=>{
    const stats=Object.entries(row.tooltip_basic_stats||{}).map(([key,value])=>`${esc(key)} ${esc(value)}`).join(' · ');
    return `<li>${esc(row.slot)}: ${esc(row.name_visible)} · Tier ${esc(row.tier)}${row.stars_visible==null?' · stars not readable':` · ${esc(row.stars_visible)}★`}${stats?` · ${stats}`:''} · ${source(row,'frame')} · native item ID unlinked</li>`;
  }).join('');
  const mods=tour.attached_mods.map(row=>`<li><details><summary>${esc(row.slot)}: ${esc(row.name_visible)} &lt;${esc(row.suffix_visible)}&gt; Lv${esc(row.level_visible)} · ${source(row,'frame')}</summary><small>Core: ${esc(row.core_effect_visible)}</small><ul>${row.rolls_visible.map(roll=>`<li>${esc(roll)}</li>`).join('')}</ul><small>Observed name and suffix; native item ID unlinked. Not applied to this calculation.${row.native_frame_candidate?` Candidate frame ${esc(row.native_frame_candidate.native_frame_code)}; ordinary/Shiny item IDs ${row.native_frame_candidate.candidate_native_item_nos.map(esc).join(' / ')}. The filmed variant is not identified.${row.native_frame_candidate.newly_typed_graph_targets.map(link=>` Line ${esc(link.position)} targets ${link.native_attributes.map(attr=>esc(attr.attr_id)).join(', ')} in native graph; buff application is not proven.`).join('')}`:''}</small></details></li>`).join('');
  return `<details class="combat-advanced"><summary>Nov 1 recorded AUG setup · historical</summary><p class="small">Nov 1 item tooltip: Tier ${esc(item.tier)} ${esc(item.stars)}★ AUG, DMG ${esc(item.item_tooltip.DMG)}, Fire Rate ${esc(item.item_tooltip['Fire Rate'])}, MAG ${esc(item.item_tooltip.MAG)}. Same tour's Gear summary: Primary Weapon Attack ${esc(summary.primary_weapon_attack)}, Fire Rate ${esc(summary.fire_rate)}, magazine ${esc(summary.magazine_capacity)}. Nov 2 unlinked screenshots: Primary Weapon Attack ${esc(nov2.primary_weapon_attack)}${basic?`, Basic Attack ${esc(basic.attack)}`:''}. These are distinct rows and setups; neither 456 nor 20 is added to item DMG 400.</p><small>${source(tour.equipped_items[0],'Nov 1 item tooltip')} · <a href="${esc(tour.source_frames.gear_summary.url)}" target="_blank" rel="noopener">Gear summary at 0:24</a>. Controlled one-bullet example: ${esc(one.recorded_item_tooltip_dmg)} × neutral graph factors = ${esc(one.neutral_graph_value)} before settlement, only if the historical item tooltip is used as the Attack leaf. The tooltip may already include calibration and item affixes; DV adds neither native base Attack nor calibration again. Recorded mods and wearer bonuses are not applied. This is not current damage or DPS.</small><details><summary>Six recorded armor pieces</summary><ul>${armor}</ul><small>These are observed names and tiers, not imported ownership or current selections.</small></details><details><summary>Seven recorded mod cards</summary><ul>${mods}</ul><small>These cards describe the Nov 1 tour only; selecting or saving a current build does not import them. Visible attachment does not prove server buff application.</small><details><summary>Inputs still needed for an active-effect replay</summary><ul>${tour.mod_application.required_for_complete_replay.map(req=>`<li>${esc(req)}</li>`).join('')}</ul></details></details></details>`;
}
function invalidateBuilderBulletScenario(){
  ++builderBulletRequest;builderBulletResult=null;
  const area=document.querySelector('#bullet-result');if(area)area.innerHTML='';
}
async function runBuilderBulletScenario(){
  const selected=planned.slots.primary||{},request=++builderBulletRequest;
  const get=key=>document.querySelector('#bullet-'+key);
  const number=(key,label,allowZero=false)=>{
    const raw=get(key)?.value?.trim()??'',value=Number(raw);
    if(raw===''||!Number.isFinite(value)||value<0||(!allowZero&&value===0))throw Error(`Enter ${label}.`);
    return value;
  };
  try{
    if(!selected.catalog_id)throw Error('Select a primary weapon first.');
    const attackSource=get('source')?.value||'item_tooltip';
    if(attackSource==='gear_weapon_summary')throw Error('Gear summary Attack may be current-holder or selected-weapon preview. Its branch and exact item mapping are unknown; use an exact item tooltip for this bullet scenario.');
    if(attackSource==='basic_holder')throw Error('Expanded Basic Attack reads the current holder, but its selected weapon context is unknown; use an exact item tooltip for this bullet scenario.');
    if(attackSource!=='item_tooltip')throw Error('Choose a supported Attack reading source.');
    if(!get('tooltip')?.checked)throw Error('Confirm Attack came from this selected item configuration.');
    if(!get('neutral')?.checked)throw Error('Confirm the neutral graph and target-factor scenario.');
    const attack=number('attack','positive item-tooltip Attack');
    const crit=number('critBonus','Crit damage addition, including 0',true)/100;
    const weak=number('weakBonus','Weakspot damage addition, including 0',true)/100;
    const inputs={attack:String(attack),critBonus:String(crit*100),weakBonus:String(weak*100),
      crit:Boolean(get('crit')?.checked),weak:Boolean(get('weak')?.checked),tooltip:true,neutral:true};
    builderBulletInputs=inputs;
    const signature=JSON.stringify([selected,inputs]);
    const target_factor_nodes=Object.fromEntries(['155','144','147','289','101','124','285','307','167'].map(key=>[key,1]));
    const scenario={weapon_id:selected.catalog_id,effect_scope:'ordinary_player_direct_bullet',
      attack,attack_evidence:'caller_hypothesis',attack_value_origin:'equipped_item_tooltip',
      final_skill_rate:1,final_keyword_damage_add_rate:0,unit_part_weak_dam_rate:1,
      crit_addition:crit,weakspot_addition:weak,final_element_type_dam_add_rate:1,
      other_dam_rate:0,final_field_dam_add_rate:1,dis_dam_rate:1,final_dam_add_rate:0,
      final_special_regulate_factor:1,crit:inputs.crit,weakspot:inputs.weak,
      use_final_dam_add_rate:true,use_final_ignore_dam_rate:true,
      target_factor_nodes,rate_dictionary_state:'absent',rounding_model:null};
    const result=await api('planned-analysis',{slots:planned.slots,
      assumptions:{...builderAssumptions(),native_player_bullet_scenario:scenario}});
    if(request!==builderBulletRequest||signature!==JSON.stringify([planned.slots.primary||{},builderBulletInputs]))return;
    builderBulletResult={native_player_bullet_scenario:result.native_player_bullet_scenario,attack,crit,weak};
    builderBulletResultKey=signature;
    const area=document.querySelector('#bullet-result');
    if(area)area.innerHTML=builderBulletResultHtml();
  }catch(error){
    if(request!==builderBulletRequest)return;
    builderBulletResult={error:String(error.message||error)};
    builderBulletResultKey=JSON.stringify([planned.slots.primary||{},builderBulletInputs]);
    const area=document.querySelector('#bullet-result');if(area)area.textContent=builderBulletResult.error;
  }
}
function builderNativeArmorPreviewHtml(){
  const armor=(builderAnalysis?.slots||[]).filter(part=>part.gear&&
    ['helmet','mask','top','gloves','bottoms','shoes'].includes(part.slot));
  if(!armor.length)return '';
  const known=armor.filter(part=>part.native_armor_base_preview?.status==='source_base_preview_only');
  const unavailable=armor.length-known.length;
  const lines=known.map(part=>{
    const source=part.native_armor_base_preview;
    return `<li>${esc(part.label)} · ${esc(source.name)} · Tier ${esc(source.tier)} ${esc(source.stars)}★: HP ${esc(source.hp)}, Psi ${esc(source.psi_intensity)}</li>`;
  }).join('');
  return `<div class="combat-known"><b>Armor base previews · ${known.length}/${armor.length} selected pieces</b>${lines?`<ul>${lines}</ul>`:''}${unavailable?`<small>${unavailable} selected piece${unavailable===1?'':'s'} lack${unavailable===1?'s':''} an exact native match or chosen supported tier/stars.</small>`:''}<small>Source base values before materials, calibration, set effects and other player state. These are not equipped HP/Psi totals or damage.</small></div>`;
}
// The two source-pinned vectors explain the copied client preview ordering.
// They are fixed, offline examples; no build, inventory or observed panel value
// is supplied to this view, and switching examples makes no API request.
let builderGearPreviewExample='';
const builderGearPreviewExamples={
  replace_abs:{name:'Absolute replacement',holder:120,old:100,retained:20,selected:200,
    holderRate:0,selectedRate:0,prebound:220,raw:220,display:220},
  replace_abs_and_rate:{name:'Absolute and rate replacement',holder:150,old:100,
    retained:50,selected:200,holderRate:5,selectedRate:10,prebound:250,
    raw:287.5,display:288}
};
function builderGearPreviewExampleResultHtml(){
  const row=builderGearPreviewExamples[builderGearPreviewExample];
  if(!row)return '<p>No complete holder and selected-weapon snapshot is supplied for this build. No preview Attack is calculated.</p>';
  return `<div class="combat-known"><b>${esc(row.name)} · synthetic example</b>
    <ol><li>Holder other-source Attack absolute: ${esc(row.holder)}. Remove held weapon D0100 ${esc(row.old)} from its source bucket → ${esc(row.retained)} retained.</li>
    <li>Add selected weapon D0100 ${esc(row.selected)} as GUN_CORE/other → ${esc(row.retained)} + ${esc(row.selected)} = ${esc(row.prebound)}.</li>
    <li>Retained D0101 rate ${esc(row.holderRate)}% + selected D0101 rate ${esc(row.selectedRate)}% → (${esc(row.prebound)}) × (1 + ${esc(row.holderRate+row.selectedRate)}%) = ${esc(row.raw)}.</li>
    <li>Clamp Attack to 0–130,000, then half-even integer round → <b>${esc(row.display)} preview Attack</b>.</li></ol>
    <small>These inputs are invented test vectors for the traced client Gear preview, not values from the selected build or Maurice’s observed 422/20 panels. No equipped Attack, hit damage or DPS follows from them.</small></div>`;
}
function builderGearPreviewExamplesHtml(){
  return `<details class="combat-advanced" id="syntheticGearPreview"><summary>Gear Attack preview math · offline examples</summary>
    <p class="small">Source-traced client order: remove held weapon affixes from their original source buckets, add selected D0100/D0101 affixes, apply Attack property bounds and display rounding. A complete holder and both weapon affix maps are needed for a real preview.</p>
    <small>Provenance: installed build 26267212; ItemDataTools.get_player_replace_affix_list → CompPropertyFormulaClient.get_preview_ability_changes_client → _calc_attr_by_base_formula → adjust_attr_val. Pinned Forge source packet SHA-256 1272f381a8da…; these are handwritten test vectors, with no game code executed.</small>
    <div class="actions"><button type="button" class="secondary" onclick="selectBuilderGearPreviewExample('replace_abs')">Example: absolute replacement</button><button type="button" class="secondary" onclick="selectBuilderGearPreviewExample('replace_abs_and_rate')">Example: absolute + rate</button><button type="button" class="secondary" onclick="selectBuilderGearPreviewExample('')">Clear example</button></div>
    <div id="gearPreviewExample" aria-live="polite">${builderGearPreviewExampleResultHtml()}</div></details>`;
}
function selectBuilderGearPreviewExample(key){
  if(key!==''&&!Object.hasOwn(builderGearPreviewExamples,key))return;
  builderGearPreviewExample=key;
  const node=document.querySelector('#gearPreviewExample');
  if(node)node.innerHTML=builderGearPreviewExampleResultHtml();
}
// These inputs correspond to release-backed source timeline bindings. The
// evaluator still checks the selected weapon and every entered outcome.
function builderSourceFamily(id){
  return ({'weapon:mps7-outer-space':'outer_space',
    'weapon:g17-hazardous-object':'hazardous_object'})[id]||'';
}
function builderTimedField(key,label,value,step='1'){
  const shown=builderTimedInputs[key]??value??'';
  return `<label>${esc(label)}<input id="br-${key}" type="number" min="0" step="${step}" value="${esc(shown)}" oninput="builderTimedInputs.${key}=this.value"></label>`;
}
function builderTimedModelHtml(){
  const selected=planned.slots.primary||{},weapon=catalogEntry(selected.catalog_id);
  if(!weapon)return '';
  const weaponKey=JSON.stringify([selected.catalog_id,selected.tier,selected.stars,
    selected.calibration_profile,selected.calibration_blueprint,selected.calibration_bonus]);
  if(builderTimedWeaponKey!==weaponKey){
    builderTimedWeaponKey=weaponKey;
    // Prior weapon's manually entered packet, projectile count and reload must
    // never follow a new crafted configuration.
    builderTimedInputs={mode:builderTimedInputs.mode||'page',
      tier:String(selected.tier??1),stars:String(selected.stars??1)};
    builderTimedResult=null;
  }
  const signature=JSON.stringify(planned.slots),run=builderTimedResultKey===signature?builderTimedResult:null;
  const mode=builderTimedInputs.mode||'page';
  const fmt=value=>new Intl.NumberFormat('en-US',{maximumFractionDigits:5}).format(value);
  const line=row=>`<li>${esc(row.name)} · ${row.applied_pool?`${esc(row.applied_percentage_points)}% to ${esc(row.applied_pool)}`:
    String(row.stat_type||'').startsWith('resonance_')?`event stack ${esc(row.value_percent??row.components?.per_stack_percent??'?')}% · requires ordered outcomes`:'not in this total'}</li>`;
  const coreLine=row=>row.static_pools_percent?Object.entries(row.static_pools_percent).map(([pool,value])=>
    `<li>${esc(row.item_name||row.catalog_id)} main effect · +${esc(value)}% ${esc(pool)}${row.stack_model==='no_hp_cost_events'?' · assumes no HP-cost events':row.stack_model==='no_stamina_loss_events'?' · assumes no stamina-loss events':''}</li>`).join(''):
    `<li>${esc(row.item_name||row.catalog_id)} main effect · +${esc(row.percentage_points)}% ${esc(row.pool)}</li>`;
  const coreExtra=row=>row.dynamic_rule?.every_bullets?`<li>${esc(row.catalog_id)} counter · +${esc(row.dynamic_rule.per_step_percent)}% Weapon per ${esc(row.dynamic_rule.every_bullets)} consumed rounds, cap ${esc(row.dynamic_rule.maximum_percent)}%; scheduled-shot average ${esc(fmt(modeled?.bullet_counter_average_percent??0))}%.</li>`:'';
  const modeled=run?.model,packets=modeled?.resonance_timeline?.packets||[];
  const sourceFamily=builderSourceFamily(selected.catalog_id);
  const striving=planned.slots.shoes?.mod_id==='mod:boots_mod:power-of-striving-downstar-deviant-energy'&&planned.slots.shoes?.mod_level===9&&!planned.slots.shoes?.mod_shiny;
  const siphon=planned.slots.bottoms?.mod_id==='mod:pants_mod:bullet-siphon-aero-deviant-energy'&&planned.slots.bottoms?.mod_level===12&&!planned.slots.bottoms?.mod_shiny;
  const sourced=modeled?.source_timeline;
  const why=run?.error||modeled?.unresolved?.[0]||run?.missing||'';
  const basis=run?.source_baseline?.stats, pools=modeled?.effective_pools_percent||{}, shotCount=modeled?.shot_times?.length??0;
  const directFormula=!modeled?.included_effect_ids&&basis&&shotCount&&modeled?.direct_expected?.components&&
    Object.entries(modeled.direct_expected.components).every(([name,value])=>name==='normal'||!value)&&
    !modeled.source_proc?.damage&&!modeled.resonance_timeline&&
    basis.damage_per_projectile!=null&&basis.projectiles_per_shot!=null&&
    Math.abs((basis.damage_per_projectile*basis.projectiles_per_shot*shotCount*
      (1+((pools.weapon||0)+(modeled.bullet_counter_average_percent||0))/100)*(1+(pools.all||0)/100))-
      modeled.direct_expected.total_damage)<1e-7?
    `${fmt(basis.damage_per_projectile)} × ${esc(basis.projectiles_per_shot)} projectile(s) × ${shotCount} shots × (1 + ${fmt((pools.weapon||0)+(modeled.bullet_counter_average_percent||0))}% Weapon) × (1 + ${fmt(pools.all||0)}% All) = ${fmt(modeled.direct_expected.total_damage)}. Status, weakspot, magazine and HP lines do not add damage to these body shots unless their relevant events occur.`:'';
  const summary=run?`<div class="combat-known combat-scenario-result" aria-live="polite"><b>${run.error?'Scenario input needed':modeled?.modeled_total_damage!=null?'Conditional scenario · not actual damage':'Scenario subtotal · incomplete'}</b>
    <span>${modeled?fmt(modeled.modeled_total_damage??modeled.known_damage_subtotal):'—'}${modeled?' over '+fmt(modeled.duration_seconds)+' seconds':''}</span>
    ${modeled?.conditional_damage_per_second!=null?`<small>${fmt(modeled.conditional_damage_per_second)} per second in this entered scenario</small>`:''}
    ${run.reference_differs_from_selected?`<small>Hypothetical Tier ${esc(run.reference_tier)} ${esc(run.reference_stars)}★ weapon page; your planned weapon is Tier ${esc(run.selected_tier??'?')} ${esc(run.selected_stars??'?')}★.</small>`:''}
    ${modeled?.included_effect_ids?`<small>Body-shot replay only; entered values already include the declared selected effects. Forge applied no gear, mod, set or proc bonus a second time.</small>`:''}
    ${why?`<small>Missing: ${esc(why)}</small>`:''}
    ${modeled?`<details><summary>Why this scenario result?</summary><p>${run.reference_kind==='caller_entered_direct_packet'?'Entered direct body damage':'Page damage'} ${esc(run.source_baseline?.stats?.damage_per_projectile??'?')} per assumed projectile · ${esc(run.source_baseline?.stats?.fire_rate??'?')} RPM · ${esc(run.source_baseline?.stats?.magazine_capacity??'?')} rounds. ${run.reference_kind==='caller_entered_direct_packet'?'These values were entered for this scenario, not converted from Attack.':'The displayed page damage unit is a named hypothesis.'} ${run.source_baseline?.source_timing?`Fire Rate and magazine come from the exact Tier I item-page labels; ${run.source_baseline.source_timing.fire_rate_rpm.unit_evidence==='explicit_secondary_rpm_label'?'the second source explicitly labels RPM':'RPM is the published reference model interpretation of Fire Rate'}. Displayed DMG remains a caller-selected per-projectile assumption.`:''} ${/^https:\/\//.test(run.source_baseline?.source_url||'')?`<a href="${esc(run.source_baseline.source_url)}" target="_blank" rel="noopener">Item page source ↗</a>`:''}</p>
      <ul>${(run.selected_mod_rows||[]).map(line).join('')}${(modeled.typed_core_pools_applied||[]).map(row=>coreLine(row)+coreExtra(row)).join('')}${(modeled.set_rules_applied||[]).map(row=>`<li>Set rule · ${esc(row.rule_id)}</li>`).join('')}</ul>
      ${directFormula?`<p>Body-shot calculation: ${directFormula}</p>`:''}
      ${packets.length?`<p>Ordered hit damage: ${packets.map(row=>fmt(row.damage)).join(' + ')}.</p>`:''}
      <p>Bullets: ${modeled.direct_expected?.total_damage==null?'unknown':fmt(modeled.direct_expected.total_damage)}. Procs and extra packets: ${modeled.source_proc?fmt(modeled.source_proc.damage):'not modeled'}.</p>
      ${sourced?`<p>Reload and ammo: ${esc(sourced.events?.filter(row=>row.kind==='reload').length??0)} modeled reloads; final magazine ${esc(sourced.final_ammo?.magazine??'?')}, reserve ${esc(sourced.final_ammo?.reserve??'?')}. ${esc(sourced.source_packets?.length??0)} sourced packets.</p>`:''}
      ${(modeled.unresolved||[]).length?`<p>Unknown portions: ${esc(modeled.unresolved.join('; '))}</p>`:''}
      ${(modeled.unresolved||[]).length>1?`<p>Other unresolved effects: ${esc(modeled.unresolved.slice(1).join('; '))}</p>`:''}
      <p>Conditional model only; this is neither measured current damage nor a game-verified winner.</p></details>`:''}</div>`:'';
  const read=(key)=>builderTimedInputs[key]??'';
  return `${summary}<details class="combat-advanced"><summary>Advanced scenario calculator</summary><section class="combat-measure-form" aria-label="Selected build damage scenario"><b>Conditional model inputs</b>
    <label>Direct packet basis<select id="br-mode" onchange="setBuilderTimedMode(this.value)"><option value="page" ${mode==='page'?'selected':''}>Named item page · per-projectile hypothesis</option><option value="caller" ${mode==='caller'?'selected':''}>Enter direct body damage per projectile</option></select></label>
    ${mode==='page'?`<span>Reference tier/stars may differ from your selected weapon; that is a labeled hypothetical comparison.</span><div>${builderTimedField('tier','Reference tier',selected.tier??1)}${builderTimedField('stars','Reference stars',selected.stars??1)}</div><label class="combat-model-scope"><input id="br-assumeRpm" type="checkbox" ${read('assumeRpm')?'checked':''} onchange="builderTimedInputs.assumeRpm=this.checked"> If this page only says Fire Rate, interpret that value as RPM for this scenario</label>`:
      `<span>Attack is not assumed equal to direct damage. Choose whether these entered values are before or after the selected effects.</span><label>Entered packet scope<select id="br-baselineScope" onchange="builderTimedInputs.packetScope=this.value"><option value="before_selected_effects" ${read('packetScope')!=='after_selected_effects_direct_only'?'selected':''}>Before selected effects · conditional model</option><option value="after_selected_effects_direct_only" ${read('packetScope')==='after_selected_effects_direct_only'?'selected':''}>After selected effects · body-shot replay only</option></select></label><label class="combat-model-scope"><input id="br-preEffects" type="checkbox" ${read('preEffects')?'checked':''} onchange="builderTimedInputs.preEffects=this.checked"> Before-effect values exclude selected weapon, gear, mod and set effects</label><label class="combat-model-scope"><input id="br-postEffects" type="checkbox" ${read('postEffects')?'checked':''} onchange="builderTimedInputs.postEffects=this.checked"> After-effect values already include the selected effect state; replay body shots without applying it again</label><div>${builderTimedField('directDamage','Direct body damage per projectile','', '0.1')}${builderTimedField('rpm','Entered RPM','')}${builderTimedField('magazine','Entered magazine','')}</div>`}
    <div>${builderTimedField('projectiles','Projectiles per shot','')}${builderTimedField('reload','Reload seconds','', '0.1')}${builderTimedField('duration','Seconds','', '0.01')}</div>
    <details><summary>Ordered hit outcomes for Resonance · optional for other builds</summary><p>Zero-based shot indices, comma separated; blank means no hits of that kind. Enter a named element only for elemental indices.</p>
      <div><label>Elemental shot indices<input id="br-elemental" value="${esc(read('elemental'))}" oninput="builderTimedInputs.elemental=this.value"></label><label>Weakspot shot indices<input id="br-weakspot" value="${esc(read('weakspot'))}" oninput="builderTimedInputs.weakspot=this.value"></label><label>Crit shot indices<input id="br-crit" value="${esc(read('crit'))}" oninput="builderTimedInputs.crit=this.value"></label><label>Element<input id="br-element" placeholder="shock, blaze, frost, blast" value="${esc(read('element'))}" oninput="builderTimedInputs.element=this.value"></label>${builderTimedField('weakbonus','Base weakspot bonus %','')}${builderTimedField('critbonus','Base crit bonus %','')}</div></details>
    ${sourceFamily?`<details ${read('sourceEnabled')?'open':''}><summary>Selected weapon proc and encounter</summary><p>Source timeline uses the selected weapon's release-backed triggers. Enter outcomes for every scheduled shot; these are assumptions, not observed results. Blank means this proc is not modeled.</p>
      <label class="combat-model-scope"><input id="br-sourceEnabled" type="checkbox" ${read('sourceEnabled')?'checked':''} onchange="builderTimedInputs.sourceEnabled=this.checked"> Model selected weapon's sourced events</label>
      <div>${builderTimedField('reserve','Starting reserve bullets','')}
      <label>Target identity<input id="br-target" value="${esc(read('target'))}" oninput="builderTimedInputs.target=this.value"></label>
      <label>Chance rolls, one per scheduled shot<input id="br-rolls" value="${esc(read('rolls'))}" oninput="builderTimedInputs.rolls=this.value"></label>
      ${builderTimedField('psi','Entered Psi basis','', '0.1')}
      <label>Extra packet class<select id="br-packetClass" onchange="builderTimedInputs.packetClass=this.value"><option value="">Choose class</option><option value="weapon" ${read('packetClass')==='weapon'?'selected':''}>Weapon</option><option value="status" ${read('packetClass')==='status'?'selected':''}>Status</option></select></label></div>
      ${sourceFamily==='outer_space'?`<label>Target affected by Power Surge, true/false per shot<input id="br-conditions" value="${esc(read('conditions'))}" oninput="builderTimedInputs.conditions=this.value"></label>`:
       `<div>${builderTimedField('reloadAfter','Early reload after shots','')}${builderTimedField('targetCount','Blast targets','')}</div>`}
      <p>${sourceFamily==='outer_space'?'Lightning triggers after 12 qualifying hits on the same target; its Psi basis and Weapon/Status class remain explicit.':'The reload blast uses actual consumed magazine rounds; target count and its Weapon/Status class remain explicit.'}</p></details>`:''}
    <label class="combat-model-scope"><input id="br-directOnly" type="checkbox" ${read('directOnly')?'checked':''} onchange="builderTimedInputs.directOnly=this.checked"> Direct-packet scope: explicitly exclude the selected weapon's unbound unique effect</label>
    ${planned.slots.shoes?.mod_id==='mod:boots_mod:against-all-odds-precision'&&planned.slots.shoes?.mod_level===7&&!planned.slots.shoes?.mod_shiny?`<label class="combat-model-scope"><input id="br-coreNoHpCost" type="checkbox" ${read('coreNoHpCost')?'checked':''} onchange="builderTimedInputs.coreNoHpCost=this.checked"> Against All Odds &lt;Precision&gt; Lv7: assume no HP-cost events in this encounter; exclude its timed extra stacks</label>`:''}
    ${striving?`<label class="combat-model-scope"><input id="br-coreNoStamina" type="checkbox" ${read('coreNoStamina')?'checked':''} onchange="builderTimedInputs.coreNoStamina=this.checked"> Power of Striving &lt;Downstar Deviant Energy&gt; Lv9: assume no stamina-loss events; exclude the unresolved extra bonus</label><label>Target position for the two Downstar bonus lines<select id="br-downstarPosition" onchange="builderTimedInputs.downstarPosition=this.value"><option value="" ${!read('downstarPosition')?'selected':''}>Unknown · keep total partial</option><option value="not_below" ${read('downstarPosition')==='not_below'?'selected':''}>Target is not below the player · inactive</option><option value="below_within_5m" ${read('downstarPosition')==='below_within_5m'?'selected':''}>Target below the player, within 5 m · maximum</option></select></label>`:''}
    ${siphon?`<label>Bullet Siphon aerial-hit bonus lines<select id="br-aerialHits" onchange="builderTimedInputs.aerialHits=this.value"><option value="" ${!read('aerialHits')?'selected':''}>Unknown · keep total partial</option><option value="none" ${read('aerialHits')==='none'?'selected':''}>No aerial hits · extra inactive</option><option value="all" ${read('aerialHits')==='all'?'selected':''}>All hits aerial · extra maximum</option></select></label>`:''}
    <button type="button" class="secondary" onclick="runBuilderTimedModel()">Calculate conditional scenario</button></section></details>`;
}
characterCombatStatsHtml=function(){
  return characterCombatStatsBeforeTimed().replace(
    '<div class="combat-stats-scroll">',
    '<div class="combat-stats-scroll">'+builderNativeArmorPreviewHtml()+builderTimedModelHtml()+builderBulletScenarioHtml()+builderGearPreviewExamplesHtml()+builderObservedPanelHtml()+builderHistoricalGearTourHtml());
};
function setBuilderTimedMode(mode){
  if(!['page','caller'].includes(mode))return;
  builderTimedInputs.mode=mode;builderTimedResult=null;
  const node=document.querySelector('#characterCombatStats');if(node)node.outerHTML=characterCombatStatsHtml();
}
async function runBuilderTimedModel(){
  const selected=planned.slots.primary||{},signature=JSON.stringify(planned.slots);
  const get=key=>document.querySelector('#br-'+key)?.value?.trim()??'';
  const number=(key,label,integer=false)=>{const raw=get(key),value=Number(raw);if(raw===''||!Number.isFinite(value)||value<=0||(integer&&!Number.isInteger(value)))throw Error(`Enter ${label}.`);return value};
  const indices=(key)=>{const raw=get(key);if(!raw)return[];const values=raw.split(',').map(x=>Number(x.trim()));if(values.some(x=>!Number.isInteger(x)||x<0)||new Set(values).size!==values.length)throw Error(`Enter unique nonnegative ${key} shot indices.`);return values};
  try{
    const mode=get('mode')||builderTimedInputs.mode||'page';
    const packetScope=mode==='caller'?(get('baselineScope')||'before_selected_effects'):null;
    if(mode==='caller'&&packetScope==='before_selected_effects'&&!document.querySelector('#br-preEffects')?.checked)throw Error('Confirm the entered damage, RPM, magazine and reload are before selected weapon, gear, mod and set effects. Already-buffed values would double count them.');
    if(mode==='caller'&&packetScope==='after_selected_effects_direct_only'&&!document.querySelector('#br-postEffects')?.checked)throw Error('Confirm the entered body-shot values already include the selected effect state; this replay cannot calculate full build damage.');
    const tier=mode==='page'?number('tier','a reference tier 1–5',true):Number(selected.tier??1);
    const stars=mode==='page'?number('stars','reference stars 1–6',true):Number(selected.stars??1);
    if(tier>5||stars>6)throw Error('Reference tier must be 1–5 and stars 1–6.');
    const elemental=indices('elemental'),weakspot=indices('weakspot'),crit=indices('crit');
    const element=get('element').toLowerCase();if(elemental.length&&!['shock','blaze','frost','blast'].includes(element))throw Error('Name the elemental hit type.');
    const weakbonus=get('weakbonus'),critbonus=get('critbonus');
    const timed={duration_seconds:number('duration','a duration in seconds'),
      crit_share:0,weakspot_share:0,joint_share:0,
      exclude_unbound_weapon_effect:Boolean(document.querySelector('#br-directOnly')?.checked),
      ...(planned.slots.shoes?.mod_id==='mod:boots_mod:against-all-odds-precision'&&planned.slots.shoes?.mod_level===7&&!planned.slots.shoes?.mod_shiny&&document.querySelector('#br-coreNoHpCost')?.checked?{core_no_hp_cost_events:true}:{}),
      ...(planned.slots.shoes?.mod_id==='mod:boots_mod:power-of-striving-downstar-deviant-energy'&&planned.slots.shoes?.mod_level===9&&!planned.slots.shoes?.mod_shiny&&document.querySelector('#br-coreNoStamina')?.checked?{core_no_stamina_loss_events:true}:{}),
      resonance_outcomes:{crit_shot_indices:crit,weakspot_shot_indices:weakspot,
        elemental_shot_indices:elemental,element:elemental.length?element:'none',reserve_bullets:0},
      resonance_baseline:{...(weakbonus!==''?{weakspot_bonus_percent:Number(weakbonus)}:{}),
        ...(critbonus!==''?{crit_bonus_percent:Number(critbonus)}:{})}};
    if(builderContext.scenario==='PvE')timed.scenario_mode='pve_non_raidzone';
    if(builderContext.scenario==='RaidZone')timed.scenario_mode='raidzone';
    const sourceFamily=builderSourceFamily(selected.catalog_id);
    const sourceEnabled=Boolean(sourceFamily&&document.querySelector('#br-sourceEnabled')?.checked);
    if(sourceEnabled){
      const reserveRaw=get('reserve');
      if(reserveRaw===''||!Number.isInteger(Number(reserveRaw))||Number(reserveRaw)<0)throw Error('Enter starting reserve bullets, including zero.');
      const target=get('target');if(!target)throw Error('Enter the encounter target identity.');
      const rollsRaw=get('rolls');if(!rollsRaw)throw Error('Enter one chance roll per scheduled shot.');
      const rolls=rollsRaw.split(',').map(x=>Number(x.trim()));
      if(rollsRaw.split(',').some(x=>x.trim()==='')||rolls.some(x=>!Number.isFinite(x)||x<0||x>=1))throw Error('Chance rolls must be comma-separated values from 0 to below 1.');
      const packetClass=get('packetClass');if(!['weapon','status'].includes(packetClass))throw Error('Choose the extra packet damage class.');
      const source={reserve_bullets:Number(reserveRaw),target_id:target,roll_sequence:rolls,
        evidence_mode:'dated_release',model_mode:'explicit_assumptions',
        damage_model:{basis_values:{psi:number('psi','the entered Psi basis')},packet_models:{}}};
      if(sourceFamily==='outer_space'){
        const raw=get('conditions');if(!raw)throw Error('Enter target Power Surge status for each scheduled shot.');
        const words=raw.split(',').map(x=>x.trim().toLowerCase());
        if(words.some(x=>x!=='true'&&x!=='false'))throw Error('Enter true or false for each target Power Surge status.');
        source.condition_sequences={target_affected_by_power_surge:words.map(x=>x==='true')};
        source.damage_model.packet_models.celestial_lightning={damage_class:packetClass};
      }else{
        source.reload_after_shots=number('reloadAfter','shots before early reload',true);
        source.damage_model.packet_models.thrown_reload_blast={damage_class:packetClass,
          target_count:number('targetCount','blast target count',true)};
      }
      timed.source_timeline=source;
      timed.resonance_outcomes.reserve_bullets=source.reserve_bullets;
    }
    builderTimedInputs={...builderTimedInputs,mode,tier:String(tier),stars:String(stars),
      projectiles:get('projectiles'),reload:get('reload'),duration:get('duration'),
      directDamage:get('directDamage'),rpm:get('rpm'),magazine:get('magazine'),
      packetScope,preEffects:Boolean(document.querySelector('#br-preEffects')?.checked),
      postEffects:Boolean(document.querySelector('#br-postEffects')?.checked),
      assumeRpm:Boolean(document.querySelector('#br-assumeRpm')?.checked),
      elemental:get('elemental'),weakspot:get('weakspot'),crit:get('crit'),element:get('element'),
      weakbonus,critbonus,directOnly:timed.exclude_unbound_weapon_effect,
      coreNoHpCost:timed.core_no_hp_cost_events===true,
      coreNoStamina:timed.core_no_stamina_loss_events===true,
      downstarPosition:get('downstarPosition'),
      aerialHits:get('aerialHits'),
      sourceEnabled,reserve:get('reserve'),target:get('target'),rolls:get('rolls'),
      psi:get('psi'),packetClass:get('packetClass'),conditions:get('conditions'),
      reloadAfter:get('reloadAfter'),targetCount:get('targetCount')};
    const packet={projectiles_per_shot:number('projectiles','a whole projectile count',true),
                  reload_seconds:number('reload','reload seconds')};
    const downstarPosition=get('downstarPosition');
    const fractions={};
    if(planned.slots.shoes?.mod_id==='mod:boots_mod:power-of-striving-downstar-deviant-energy'&&planned.slots.shoes?.mod_level===9&&!planned.slots.shoes?.mod_shiny&&['not_below','below_within_5m'].includes(downstarPosition))
      fractions['enemy below player, maximum at 5 meters']=downstarPosition==='below_within_5m'?1:0;
    const aerialHits=get('aerialHits');
    if(planned.slots.bottoms?.mod_id==='mod:pants_mod:bullet-siphon-aero-deviant-energy'&&planned.slots.bottoms?.mod_level===12&&!planned.slots.bottoms?.mod_shiny&&['none','all'].includes(aerialHits))
      fractions['aerial hit']=aerialHits==='all'?1:0;
    const reference={weapon_id:selected.catalog_id,tier,stars,
      ...(Object.keys(fractions).length?{condition_fractions:fractions}:{}),
      ...(mode==='caller'?{caller_packet_scenario:{...packet,
          assume_direct_body_damage_per_projectile:true,
          baseline_bonus_scope:packetScope,
          ...(packetScope==='after_selected_effects_direct_only'?{included_effect_ids:[...new Set([selected.catalog_id,...Object.values(planned.slots).filter(item=>item&&catalogEntry(item.catalog_id)?.kind==='armor').flatMap(item=>[item.catalog_id,item.mod_id].filter(Boolean)),selected.mod_id].filter(Boolean))]}:{}),
          direct_body_damage_per_projectile:number('directDamage','direct body damage per projectile'),
          rpm:number('rpm','current RPM'),magazine_capacity:number('magazine','current magazine',true)}}:
        {item_page_scenario:{...packet,assume_displayed_damage_per_projectile:true,
          assume_fire_rate_as_rpm:Boolean(document.querySelector('#br-assumeRpm')?.checked)}})};
    const result=await api('build-timed-readout',{slots:planned.slots,reference,timed});
    if(signature!==JSON.stringify(planned.slots))return;
    builderTimedResult=result;builderTimedResultKey=signature;
  }catch(error){builderTimedResult={error:String(error.message||error)};builderTimedResultKey=signature;}
  const node=document.querySelector('#characterCombatStats');if(node)node.outerHTML=characterCombatStatsHtml();
}

/* Mod backpack: families and variants at left, selected gear center, facts at right. */
let modSlotFilter='all',modSearch='',modOriginSlot='primary',modCollectionMode=false,modReferenceScope='game';
let fieldGuideProfile='personal',fieldGuideSelection=null,fieldGuidePreview=null,fieldGuideDraft=null,fieldGuideMath=null,fieldGuideRequest=0,modDetailOpen=false;
let modCatalogDetail=null,modCatalogLevel=8,modCatalogShiny=false,modCatalogRequest=0,modProfileEditing=false,modRecordsMode=false;
function fieldGuideRecorded(id){return state.field_guide_profiles?.[fieldGuideProfile]?.levels?.[id]||null;}
function fieldGuideRarity(level){return !level?'unknown':level<=2?'common':level<=4?'uncommon':level<=6?'rare':level<=8?'epic':'legendary'}
function setFieldGuideProfile(profile){
  if(!['personal','new_player'].includes(profile))return;
  fieldGuideProfile=profile;fieldGuidePreview=null;fieldGuideDraft=null;fieldGuideMath=null;fieldGuideRequest++;
  if(profile==='new_player')characterModView='all';
  if(modRecordsMode){if(fieldGuideSelection)openModProfileEditor();else modRender(false)}
  else{resetModCollectionDetail();modRender(false)}
}
async function fieldGuideCardClick(id){
  const entry=catalogEntry(id);
  if(!entry||entry.kind!=='mod')return;
  if(modRecordsMode){fieldGuideSelection=id;modDetailOpen=true;await openModProfileEditor();return}
  fieldGuideSelection=id;modProfileEditing=false;fieldGuidePreview=null;fieldGuideDraft=null;fieldGuideMath=null;
  modCatalogLevel=entry.source_observed_level||8;
  modCatalogShiny=false;modCatalogDetail=null;modDetailOpen=true;
  ++fieldGuideRequest;modRender();await loadModCatalogDetail();
}
async function loadModCatalogDetail(){
  const id=fieldGuideSelection,level=modCatalogLevel,shiny=modCatalogShiny,request=++modCatalogRequest;
  if(!id)return;
  try{
    const response=await fetch('/api/public-mod-detail/'+encodeURIComponent(id)+'?level='+level+(shiny?'&shiny=1':'')+'&compact=1');
    const detail=await response.json();
    if(!response.ok)throw Error(detail.error||'Catalog detail unavailable');
    if(request!==modCatalogRequest||id!==fieldGuideSelection||level!==modCatalogLevel||shiny!==modCatalogShiny||modProfileEditing)return;
    modCatalogDetail=detail;modRender();
  }catch(error){
    if(request!==modCatalogRequest||id!==fieldGuideSelection||modProfileEditing)return;
    modCatalogDetail={catalog_id:id,preview_level:level,error:String(error.message||error)};modRender();
  }
}
function setModCatalogLevel(value){
  const level=Number(value);
  if(!Number.isInteger(level)||level<1||level>17||!fieldGuideSelection)return;
  modCatalogLevel=level;if(level!==17)modCatalogShiny=false;
  modCatalogDetail=null;modRender();return loadModCatalogDetail();
}
function setModCatalogShiny(value){
  if(!fieldGuideSelection||modCatalogLevel!==17)return;
  modCatalogShiny=value==='shiny';modCatalogDetail=null;modRender();return loadModCatalogDetail();
}
async function openModProfileEditor(){
  if(!fieldGuideSelection)return;
  modProfileEditing=true;modCatalogRequest++;fieldGuidePreview=null;fieldGuideDraft=null;fieldGuideMath=null;
  const id=fieldGuideSelection,profile=fieldGuideProfile,request=++fieldGuideRequest;
  modRender();
  try{
    const saved=fieldGuideRecorded(id);
    const result=await api('field-guide/preview',{profile_id:profile,catalog_id:id,
      level:saved?.level??0,shiny_status:saved?.shiny_status||'unknown'});
    if(request===fieldGuideRequest&&id===fieldGuideSelection&&profile===fieldGuideProfile&&modProfileEditing){fieldGuidePreview=result;modRender()}
  }catch(error){if(request===fieldGuideRequest&&modProfileEditing){fieldGuidePreview={catalog_id:id,error:String(error.message||error)};modRender()}}
}
function closeModProfileEditor(){fieldGuideRequest++;if(modRecordsMode){fieldGuideSelection=null;fieldGuidePreview=null;modDetailOpen=false;modRender();return}modProfileEditing=false;modRender()}
async function previewFieldGuideDraft(){
  const id=fieldGuideSelection,raw=document.querySelector('#fieldGuideLevel')?.value;
  let shiny=document.querySelector('#fieldGuideShiny')?.value||'unknown';
  if(!id||raw===''||!/^\d+$/.test(raw||''))return notice('Enter a whole level from 0 to 17.');
  const level=Number(raw),profile=fieldGuideProfile,request=++fieldGuideRequest;
  if(level===0)shiny='unknown';
  fieldGuideDraft={level,shiny};fieldGuideMath=null;
  try{
    const result=await api('field-guide/preview',{profile_id:profile,catalog_id:id,level,shiny_status:shiny});
    if(request!==fieldGuideRequest||fieldGuideSelection!==id||fieldGuideProfile!==profile)return;
    fieldGuidePreview=result;modRender();
  }catch(error){if(request===fieldGuideRequest){fieldGuidePreview=null;fail(error)}}
}
async function saveFieldGuideLevel(){
  const id=fieldGuideSelection,raw=document.querySelector('#fieldGuideLevel')?.value;
  let shiny=document.querySelector('#fieldGuideShiny')?.value||'unknown';
  if(!id||raw===''||!/^\d+$/.test(raw||''))return notice('Enter a whole level from 0 to 17.');
  if(Number(raw)===0)shiny='unknown';
  const profile=fieldGuideProfile,request=++fieldGuideRequest;
  try{
    const result=await api('field-guide/level',{profile_id:profile,catalog_id:id,
      level:Number(raw),shiny_status:shiny});
    if(request!==fieldGuideRequest||fieldGuideProfile!==profile||fieldGuideSelection!==id)return;
    const latest=await(await fetch('/api/state')).json();
    if(request!==fieldGuideRequest||fieldGuideProfile!==profile||fieldGuideSelection!==id)return;
    state.field_guide_profiles=latest.field_guide_profiles;
    fieldGuideDraft=null;fieldGuidePreview=result;fieldGuideMath=null;modRender(false);
    notice(result.proposed_level===0?'Marked not unlocked in this profile':'Field Guide level recorded in this profile');
  }catch(error){fail(error)}
}
function invalidateFieldGuideMath(){fieldGuideRequest++;fieldGuideMath=null;const target=document.querySelector('#fieldGuideMathResult');if(target)target.innerHTML=''}
async function previewFieldGuideMath(){
  const id=fieldGuideSelection,profile=fieldGuideProfile,request=++fieldGuideRequest;
  if(!id||!fieldGuideRecorded(id)?.level)return notice('Record this exact variant level first.');
  const hit=document.querySelector('#fieldGuidePreHit')?.value;
  const rpmText=document.querySelector('#fieldGuidePreRpm')?.value;
  const magText=document.querySelector('#fieldGuidePreMag')?.value;
  const reloadText=document.querySelector('#fieldGuidePreReload')?.value;
  if(hit&&(rpmText===''||magText===''||reloadText===''))return notice('Enter a pre-mod hit, RPM, magazine and reload time together.');
  const baseline=hit?{base_origin:'pre_mod_unbuffed',base_direct_hit:Number(hit),
    rpm:Number(rpmText),magazine:Number(magText),reload_seconds:Number(reloadText),
    tech_policy:document.querySelector('#fieldGuideTechAssume')?.checked?'assume_active':'exclude_unknown'}:
    {base_origin:'unknown',tech_policy:document.querySelector('#fieldGuideTechAssume')?.checked?'assume_active':'exclude_unknown'};
  if(hit&&(!baseline.rpm||!baseline.magazine||!Number.isFinite(baseline.reload_seconds)))return notice('Enter a pre-mod hit, RPM, magazine and reload time together.');
  try{
    const result=await api('field-guide/calculation-preview',{profile_id:profile,catalog_id:id,baseline});
    if(request!==fieldGuideRequest||fieldGuideProfile!==profile||fieldGuideSelection!==id)return;
    fieldGuideMath=result;modRender(false);
  }catch(error){if(request===fieldGuideRequest)fail(error)}
}
// The catalog preview never reads or writes a personal profile. Published-model
// rows may be supplied by the catalog resolver alongside photographed rows.
function modCatalogRows(detail){
  const configured=detail?.configured_bonus_lines;
  const published=detail?.bonus_lines;
  const rows=Array.isArray(configured)&&configured.length?configured.map((row,index)=>{
    const held=Array.isArray(published)?published[index]:null;
    const candidateConflict=detail?.published_candidate_conflicts?.find(item=>item.position===index+1);
    if(row.source_conflict&&row.native_configured_candidate)
      return {...row,raw_text:`Native build configuration: ${row.native_configured_candidate}`,value_percent:null,
        published_candidate_conflict:candidateConflict||null,
        held_conflict_text:held?.status==='observed_value_published_conflict'?
          (held.raw_text||`${held.name}${held.value_percent==null?'':` +${held.value_percent}%`}`):null,
        held_conflict_source:held?.status==='observed_value_published_conflict'?held.source_ref:null};
    if(held?.status==='observed_value_published_conflict'&&row.native_corroboration?.status==='recorded_card_text_agrees')
      return {...row,held_published_layout_conflict:true,published_candidate_conflict:candidateConflict||null};
    return {...row,published_candidate_conflict:candidateConflict||null};
  }):published||detail?.published_bonus_lines||detail?.modeled_attributes||detail?.catalog_model?.bonus_lines||detail?.known_attributes||[];
  if(!Array.isArray(rows))return [];
  if(rows.length)return rows;
  const names=detail?.known_attribute_names||detail?.entry?.attribute_names||[];
  const tiers=detail?.level_profile||[];
  return names.map((name,index)=>({name,tier:tiers[index],value_percent:null}));
}
function modCatalogRowText(row){
  if(row.raw_text)return String(row.raw_text);
  const name=row.name||row.label||row.stat||'Bonus';
  if(row.locked||row.status==='locked_at_this_level')return String(name)+' · locked at this level';
  const amount=row.display_value??row.formatted_value??(row.value_percent==null?null:`${row.direction==='reduction'?'−':'+'}${row.value_percent}%`);
  return amount==null?String(name)+' · amount not verified':String(name)+' '+String(amount);
}
function modCatalogSourceLabel(row){
  if(row.status==='source_conflict'||row.source_conflict)return 'Conflicting meanings · current contribution unknown';
  if(row.held_published_layout_conflict)return 'Held line value · published layout conflicts';
  if(row.published_layout_conflict)return row.value_percent==null?'Published layout conflicts with held line · candidate withheld':'Held line value · published layout conflicts';
  if(row.status==='published_formula_candidate_generation_unverified')return 'Published table model · current game generation unverified';
  if(row.status==='locked_at_this_level')return 'Official level chart';
  if(row.source_status==='native_catalog_configuration_runtime_unverified')return row.source_warning?'Native source · English label differs':'Native catalog config · activation unverified';
  const source=row.source_status?String(row.source_status).replaceAll('_',' '):'';
  return row.native_corroboration?.status==='exact_configured_tooltip_agrees'?
    source+' · native E42 tooltip agrees; activation unverified':source;
}
function modCatalogPanel(){
  if(!fieldGuideSelection)return '<div class="mod-catalog-empty"><h3>Choose a mod</h3><p>Select any mod to see its effect and bonuses. Ownership is not required.</p></div>';
  const entry=catalogEntry(fieldGuideSelection),detail=modCatalogDetail?.catalog_id===fieldGuideSelection&&modCatalogDetail?.preview_level===modCatalogLevel?modCatalogDetail:null;
  const family=modFamilyName(entry),variant=modReferenceVariant(entry);
  const slot=modSlotTabs.find(([key])=>key===entry.slot)?.[1]||entry.slot;
  const rows=modCatalogRows(detail),effect=detail?.core_effect?.text||detail?.primary_effect||entry.effect;
  const effectStatus=detail?.core_effect?.status==='exact_level_source'?'Source-checked effect at this level':modCatalogShiny?'Shiny main-effect increase is not verified for this entry':detail?.core_effect?.status==='published_variants_level_unmapped'?'Published effect variants; no source maps them to this Field Guide level':'Catalog effect wording; exact level strength may vary';
  const effectVariants=detail?.core_effect?.status==='published_variants_level_unmapped'?(detail.core_effect.unbound_variants||[]):[];
  const conditions=(detail?.core_effect?.conditions||detail?.entry?.activation_conditions||[]).filter(Boolean);
  const progression=detail?.configured_progression?.length?detail.configured_progression:detail?.progression||detail?.level_progression||[];
  const legacy=detail?.system_scope==='legacy_instance_specific';
  const native=detail?.native_mod_identity||entry.native_mod_identity;
  const nativeCore=detail?.native_main_effect;
  const nativeCoreNote=nativeCore?`<p>Native Shatter Them All effect ranks (separate from Field Guide levels): ${nativeCore.effect_ranks.map(row=>`rank ${esc(row.effect_rank)}: +${esc(row.shrapnel_damage_per_body_part_percent)}% per body part, cap +${esc(row.cap_percent)}%`).join('; ')}. The source generation path maps native total levels 7–8 to rank 4 and 9–17 to rank 5; this family has no native entry rows for ranks 1–3. The standard collection tooltip reads rank ${esc(nativeCore.standard_tooltip_effect_rank)}. ${nativeCore.preview_shiny?`Shiny has a separate +${esc(nativeCore.shiny_separate_effect.shrapnel_damage_percent)}% Shrapnel DMG source line. `:''}The native total level is not proven to be the Field Guide badge level. Runtime arithmetic remains unresolved; these values are not applied to the calculation.</p>`:'';
  const nativeNote=native?`<p>Native item IDs · build ${esc(native.steam_build_id)}: ${native.normal?`normal ${esc(native.normal.item_id)}`:'normal ID not linked'}${native.shiny?` → Shiny ${esc(native.shiny.item_id)}`:''}${native.normal_to_shiny_link_verified?' (replacement link verified)':''}. ${native.native_family?.family_membership_verified?'This variant belongs to a source-confirmed native mod family. ':''}Identity only: no ownership, level rule or damage bonus inferred.</p>${native.native_artwork_path?`<div class="mod-native-art-source"><img src="${esc(native.native_artwork_path)}" alt="Native mod icon"><small>Game file icon · ${esc(native.normal?.icon_artwork?.source_pack||native.shiny?.icon_artwork?.source_pack||'source pack')}</small></div>`:''}`:'';
  const progressionHtml=[...new Set([1,8,modCatalogLevel,17])].sort((a,b)=>a-b).map(level=>{
    const row=Array.isArray(progression)?progression.find(item=>item.level===level):progression?.[String(level)];
    const tiers=row?.tiers||row?.bonus_lines?.map(line=>line.tier);
    return row?`<span class="${level===modCatalogLevel?'current':''}">Lv ${level} · ${esc(Array.isArray(tiers)?tiers.join(' / '):'see level chart')}</span>`:'';
  }).join('');
  const source=detail?.core_effect?.source_ref||detail?.entry?.source_url||entry.artwork_source;
  return `<div class="mod-catalog-head"><button class="secondary mod-catalog-back" onclick="toggleModDetail(false)">← All mods</button><small>MOD CATALOG · ${esc(slot.toUpperCase())} · ${esc(entry.rarity||'rarity unknown')}</small><h3>${esc(family)} ${variant?`<em>&lt;${esc(variant)}&gt;</em>`:''}</h3><p>Preview any level to decide whether this mod is worth pursuing.</p></div>
    ${legacy?'':`<label class="mod-catalog-level">Preview level <select id="modCatalogLevel" aria-label="Preview mod level" onchange="setModCatalogLevel(this.value)">${Array.from({length:17},(_,index)=>index+1).map(level=>`<option value="${level}" ${level===modCatalogLevel?'selected':''}>Lv ${level}</option>`).join('')}</select></label>`}
    ${!legacy&&modCatalogLevel===17?`<label class="mod-catalog-shiny">Variant <select aria-label="Preview regular or Shiny" onchange="setModCatalogShiny(this.value)"><option value="regular" ${!modCatalogShiny?'selected':''}>Regular</option><option value="shiny" ${modCatalogShiny?'selected':''}>Shiny</option></select></label>`:''}
    <section class="mod-catalog-core"><h4>Main effect</h4><p>${esc(effect||'Exact effect at this level is not mapped.')}</p>${effectVariants.length?`<p>Published effect variants for this exact mod:</p><ul>${effectVariants.map(row=>`<li>${esc(row.text)}</li>`).join('')}</ul>`:''}${conditions.length?`<p class="mod-catalog-condition">Activates when ${esc(conditions.join('; '))}</p>`:''}<small>${esc(effectStatus)}</small></section>
    <section class="mod-catalog-bonuses"><h4>${legacy?'Bonus rolls':'Four bonus lines · Lv '+esc(modCatalogLevel)}</h4>${detail?.error?`<p role="alert">${esc(detail.error)}</p>`:!detail?'<p>Loading catalog bonuses…</p>':rows.length?`<ol>${rows.map((row,index)=>`<li><span class="mod-catalog-row-number">${index+1}</span><span><b>${esc(modCatalogRowText(row))}</b>${row.published_candidate_conflict?`<small>Published candidate ${esc(row.published_candidate_conflict.published_name)} +${esc(row.published_candidate_conflict.published_value_percent)}% conflicts with this native line; excluded from damage calculations.</small>`:''}${row.held_conflict_text?`<small>Separate recorded card: ${esc(row.held_conflict_text)}. The native configured wording above is not a verified replacement for that observation.</small>`:''}${row.condition?`<small>When ${esc(row.condition)}</small>`:''}${row.conditional_bonus_percent!=null?`<small>Conditional extra +${esc(row.conditional_bonus_percent)}%</small>`:''}${row.source_warning?`<small>${esc(row.source_warning)}${row.recorded_english_label&&row.recorded_english_label!==row.name?` Recorded card label: ${esc(row.recorded_english_label)}.`:''}</small>`:''}${row.tier!=null?`<small>Tier ${esc(row.tier)}${modCatalogSourceLabel(row)?` · ${esc(modCatalogSourceLabel(row))}`:''}</small>`:''}</span></li>`).join('')}</ol>`:legacy?'<p>Legacy bonus rolls are instance specific; inspect the actual item.</p>':'<p>The four fixed bonus identities are not yet verified for this exact suffix. The catalog cannot give reliable amounts at this level.</p>'}</section>
    ${legacy?'':`<section class="mod-catalog-progression"><h4>Level progression</h4><div>${progressionHtml||'Level chart unavailable'}</div><small>Four ordered bonus tiers; choose any level above to inspect its values. ${detail?.configured_status==='exact_native_catalog_configuration'?'Native configured lines do not prove an owned roll or active buff. Shiny core effects are separate.':'Shiny affects the Lv 17 main effect.'}</small></section>`}
    <details class="mod-catalog-evidence"><summary>Sources and catalog limits</summary>${nativeNote}${nativeCoreNote}${source&&/^https:\/\//.test(source)?`<p>${characterSourceReference(source,'Core effect source')}</p>`:''}${[...new Set(rows.map(row=>row.source_ref).filter(Boolean))].map(ref=>`<p>${characterSourceReference(ref,'Bonus table source')}</p>`).join('')}${[...new Set((detail?.published_candidate_conflicts||[]).map(row=>row.published_source_ref).filter(Boolean))].map(ref=>`<p>${characterSourceReference(ref,'Disputed published bonus source')}</p>`).join('')}${rows.filter(row=>row.native_heal_input_configuration).map(row=>`<p>Battle heal graph · configured parent fraction ${esc(100*row.native_heal_input_configuration.configured_parent_factor)}%. With an explicitly supplied stored fraction, NodeHeal input is max HP × that stored fraction. Kill target type, save/cast order and actual HP restored remain unverified.</p>`).join('')}${(detail?.configured_missing||detail?.missing||detail?.unknowns)?.length?`<p>${esc((detail.configured_missing||detail.missing||detail.unknowns).join(' '))}</p>`:''}${detail?.native_buff_graph_review_coverage?`<p>Native buff graphs reviewed: ${esc(detail.native_buff_graph_review_coverage.primary_graphs_reviewed)}/49; ${esc(detail.native_buff_graph_review_coverage.all_graphs_with_direct_or_indirect_attribute_target)} attribute-target paths and ${esc(detail.native_buff_graph_review_coverage.all_effect_only_graphs)} effect-node paths. Review does not prove the selected buff is active or its combat value.</p>`:''}<p>This preview is read-only.</p></details>`;
}
function fieldGuidePanel(){return modProfileEditing?fieldGuideProfilePanel():modCatalogPanel()}
function fieldGuideProfilePanel(){
  if(!fieldGuideSelection)return '<h3>Choose a mod</h3><p>Select one exact family and suffix. Level 0 means not unlocked in this profile. This does not change equipped gear or legacy Backpack copies.</p>';
  const entry=catalogEntry(fieldGuideSelection),saved=fieldGuideRecorded(fieldGuideSelection);
  const result=fieldGuidePreview?.catalog_id===fieldGuideSelection?fieldGuidePreview:null;
  const level=saved?.level??0,draft=fieldGuideDraft||{level,shiny:saved?.shiny_status||'unknown'},rows=result?.known_attributes||[];
  const math=fieldGuideMath?.catalog_id===fieldGuideSelection&&fieldGuideMath?.profile_id===fieldGuideProfile?fieldGuideMath:null;
  const mathPane=saved?.level?`<details><summary>Optional calculation preview for this profile</summary><p class="small">Known variant rows are profile-specific. Unknown Tech activation is excluded unless you choose a clearly labeled hypothetical. Already-buffed hits must not be entered as pre-mod values.</p><label><input id="fieldGuideTechAssume" onchange="invalidateFieldGuideMath()" type="checkbox"> What-if only: assume unknown Tech rows active</label><div class="formgrid"><label>Pre-mod direct hit<input id="fieldGuidePreHit" oninput="invalidateFieldGuideMath()" type="number" min="0" step="any" placeholder="optional"></label><label>Pre-mod RPM<input id="fieldGuidePreRpm" oninput="invalidateFieldGuideMath()" type="number" min="0" step="any" placeholder="optional"></label><label>Pre-mod magazine<input id="fieldGuidePreMag" oninput="invalidateFieldGuideMath()" type="number" min="0" step="any" placeholder="optional"></label><label>Pre-mod reload seconds<input id="fieldGuidePreReload" oninput="invalidateFieldGuideMath()" type="number" min="0" step="any" placeholder="optional"></label></div><button class="secondary" onclick="previewFieldGuideMath()">Show supported row impact</button><div id="fieldGuideMathResult">${math?`<p class="note">${esc(math.rows.length)} catalog rows · ${esc(math.scenario.modifiers.tech_gated_rows.length)} Tech-gated · ${esc(math.scenario.modifiers.unmodeled_rows.length)} unmodeled. ${math.scenario.component_results?`Modeled direct hit ${esc(math.scenario.component_results.direct_hit??'unknown')}; this is a partial assumption-based result.`:'Enter a complete pre-mod baseline to see a partial direct-hit result.'} No full build DPS is claimed.</p><ul>${math.rows.map(row=>`<li>${esc(row.raw_text)} · ${esc(row.stat_type)} · ${esc(row.calculation_status)}</li>`).join('')}</ul>`:''}</div></details>`:'';
  return `<button class="secondary" onclick="closeModProfileEditor()">← Field Guide records</button><small>${esc(fieldGuideProfile==='personal'?'PERSONAL PROFILE':'NEW PLAYER PROFILE')}</small><h3>${esc(entry?.name||fieldGuideSelection)} &lt;${esc(entry?.variant||'?')}&gt;</h3><p>Exact variant · ${esc(({chest_mod:'Top',weapon_mod:'Weapon',helmet_mod:'Helmet',pants_mod:'Bottoms',boots_mod:'Shoes',gloves_mod:'Gloves',mask_mod:'Mask'})[entry?.slot]||entry?.slot||'?')}. ${saved?`Recorded Lv ${esc(level)} · ${esc(({reviewed_video:'from reviewed video',manual:'entered manually'})[saved.source_kind]||'source recorded')}`:'No Field Guide level recorded in this profile. Existing inventory is separate.'}</p>${result?.error?`<p role="alert">${esc(result.error)}</p>`:`<label>Field Guide level (0 = not unlocked)<input id="fieldGuideLevel" type="number" min="0" max="17" step="1" value="${esc(draft.level)}" onchange="previewFieldGuideDraft()"></label><label>Shiny identity<select id="fieldGuideShiny" onchange="previewFieldGuideDraft()"><option value="unknown" ${draft.shiny==='unknown'?'selected':''}>Unknown</option><option value="regular" ${draft.shiny==='regular'?'selected':''}>Regular</option><option value="shiny" ${draft.shiny==='shiny'?'selected':''}>Shiny Lv17</option></select></label><button class="primary" onclick="saveFieldGuideLevel()">Save profile level</button><p class="small">The official level table gives four subattribute tiers. Numeric values appear only where this exact variant and tier have source-backed data. Unknown Tech activation remains excluded.</p>${result?`<p class="small">Tier allocation: ${esc(result.level_profile?.join(' / ')||'none at level 0')} · ${esc(fieldGuideCoverageLabel(result.numeric_coverage))} · ${esc(fieldGuideDecisionLabel(result.decision))}</p>${rows.length?`<ul>${rows.map(row=>`<li>${row.raw_text?esc(row.raw_text):`${esc(row.name)}: ${row.value_percent==null?'value unknown':`${esc(row.value_percent)}%`}`}${row.condition?` · ${esc(row.condition)}`:''}</li>`).join('')}</ul>`:'<p>No numeric attributes verified at this level.</p>'}<p class="small">Values at other levels and core-effect calculations may still be unknown. ${esc(fieldGuideUnknownLabels(result))}</p>`:'<p>Choose a level to preview source-backed details.</p>'}`}${mathPane}<details><summary>Optional source evidence and separate records</summary>${result?.reviewed_main_effect_raw?`<p>Source-checked main effect (text only; calculation rule separate): ${esc(result.reviewed_main_effect_raw)}</p>`:''}${entry?.source_observed_level?`<p>The game recording showed Lv ${esc(entry.source_observed_level)} for this catalog variant. That is source evidence, not ownership in this profile.</p>`:''}${fieldGuideProfile==='personal'?modOwnedInstances(fieldGuideSelection).map(item=>`<p>Existing mod record ${esc(item.id.slice(0,8))} · Lv ${esc(item.level??'?')} · system ${esc(item.stats?.mod_system||item.effects?.mod_system||'unclassified')}.</p>`).join(''):''}<p>This profile does not change your saved inventory or builds. System-unverified records stay visible but are not silently treated as Field Guide progress or legacy Backpack copies. A video hover is a collection observation, not a new physical copy.</p></details>`;
}
function fieldGuideUnknownLabels(result){const notes=(result.unknowns||[]).map(note=>result.reviewed_exact_rows?.length&&String(note).startsWith('Exact sub-attribute values for this mod, variant and level are absent from the catalog.')?'The general catalog lacks an independent numeric table for this level; the amounts above come from reviewed footage, not a complete level curve.':note);return notes.join(' ')||'No further catalog note.'}
function fieldGuideCoverageLabel(value){
  if(fieldGuidePreview?.rank_derived)return ({complete:'All active rows have same-rank values from reviewed footage; target level not photographed',partial:'Some rows have same-rank values from reviewed footage; others remain unknown',none:'No same-rank numerical values observed for this level'})[value]||'Numerical evidence needs review';
  return ({complete:'All shown values observed at this exact level',partial:'Some values observed at this exact level',none:'No numerical values verified at this exact level'})[value]||'Numerical evidence needs review'
}
function fieldGuideDecisionLabel(value){return ({same_level_observation:'This level is already recorded',higher_level_progression:'Higher level preview',lower_level_correction:'Lower level needs review',new_unlock:'New unlock preview',record_locked:'Not unlocked in this profile',stale_lower_level_observation:'Older level observation retained',shiny_identity_needs_review:'Shiny identity needs review'})[value]||'Progression needs review'}
let modSelectedDetail=null,modSelectedRequest=0;
const modSlotTabs=[['all','All slots','✧'],['weapon_mod','Weapon','⌖'],['helmet_mod','Helmet','◉'],['chest_mod','Top','▤'],['pants_mod','Bottoms','▥'],['boots_mod','Shoes','⌁'],['gloves_mod','Gloves','✥'],['mask_mod','Mask','◇']];
// Silhouettes extracted from the nine-category game strip supplied by Maurice.
const modGoalIcons={burn:'burn',electric:'electric',frost:'frost',bullseye:'bullseye',fortress_warfare:'fortress-warfare',unstable_bomber:'unstable-bomber',fast_gunner:'fast-gunner',bounce:'bounce',shrapnel:'shrapnel'};
function modGoalIcon(goal){return modGoalIcons[goal]?`<img src="/artwork/mod-category-${modGoalIcons[goal]}.png" alt="" aria-hidden="true">`:'⬡';}
function modGoalForEntry(entry){
  if(entry?.slot==='weapon_mod'){const known=Object.entries(modReferenceWeaponOrder).find(([,families])=>families.includes(modReferenceFamily(entry)));if(known)return known[0];}
  const text=[entry?.name,entry?.tree,entry?.variant].join(' ').toLowerCase();
  const cues=[['electric',['power surge','shock']],['burn',['burn','blaze']],['frost',['frost vortex']],['bullseye',['bullseye',"bull's eye"]],['fortress_warfare',['fortress warfare']],['unstable_bomber',['unstable bomber']],['fast_gunner',['fast gunner']],['bounce',['bounce']],['shrapnel',['shrapnel']]];
  return cues.find(([,terms])=>terms.some(term=>text.includes(term)))?.[0]||null;
}
const modCategoryTerms={burn:['burn','blaze','element dmg','elemental dmg','elemental damage'],electric:['power surge','shock dmg','shock damage','element dmg','elemental dmg','elemental damage'],frost:['frost vortex','frost dmg','frost damage','element dmg','elemental dmg','elemental damage'],bullseye:['bulls eye',"bull's eye",'bullseye'],fortress_warfare:['fortress warfare'],unstable_bomber:['unstable bomber'],fast_gunner:['fast gunner'],bounce:['bounce'],shrapnel:['shrapnel']};
// Power Surge is verified by Library libfile_394a04a04a7481918470cfeffe022619;
// Fortress Warfare's first two are in libfile_dde7b66d07048191beb1a3c665dbdfae,
// with the next two supplied directly by the user. Other family orders remain unverified.
const modVerifiedFamilyOrder={electric:['Shock Rampage','Shock Diffusion','Static Shock','Surge Amplifier'],fortress_warfare:['United We Stand','Durable Territory','Portable Territory','Final Territory']};
const modTargetSlots={helmet_mod:'helmet',mask_mod:'mask',chest_mod:'top',gloves_mod:'gloves',pants_mod:'bottoms',boots_mod:'shoes'};
const modOriginalPopoverHtml=characterPopoverHtml;
characterPopoverHtml=function(){return characterPane==='catalog'&&picker?.mode==='mod'?'':modOriginalPopoverHtml();};
const modOriginalSelectCharacterSlot=selectCharacterSlot;
selectCharacterSlot=function(slot,mode='gear',trigger=null){
  modCollectionMode=false;
  if(mode==='mod')modReferenceScope='game';
  if(mode==='mod'){
    modOriginSlot=slot;modSlotFilter=builderMods[slot]||'weapon_mod';
    if(modSlotFilter!=='weapon_mod')characterModGoal='all';
    modSearch='';characterPreviewId=null;modSelectedDetail=null;
  }
  modOriginalSelectCharacterSlot(slot,mode,trigger);
};
function openModCollection(){
  hideModHover();
  modRecordsMode=false;
  modCollectionMode=true;resetModCollectionDetail();modBrowseScroll=0;modReferenceScope='game';modOriginSlot=null;modSlotFilter='weapon_mod';modSearch='';
  characterModGoal='burn';characterModView='all';characterPane='catalog';characterEditKind='mod';
  characterPreviewId=null;characterPreviewDetail=null;characterPreviewInventoryId=null;modSelectedDetail=null;
  picker={slot:null,mode:'mod',tab:'all'};
  render();
}
function openFieldGuideRecords(){
  openModCollection();
  modRecordsMode=true;modProfileEditing=true;modDetailOpen=false;
  modRender(false);
}
function exitModPicker(){
  hideModHover();
  modRecordsMode=false;
  resetModCollectionDetail();modCollectionMode=false;
  if(characterPane==='catalog'&&picker?.mode==='mod'){
    characterPreviewId=null;characterPreviewDetail=null;modSelectedDetail=null;
    modOriginSlot=characterNames[characterSlot]?characterSlot:'primary';
    picker={slot:modOriginSlot,mode:'gear',tab:modOriginSlot};
    characterEditKind='gear';characterPane='equipment';render();return;
  }
  setCharacterPane('equipment');
}
function modOwnedInstances(id){return (builderData.owned_mods||[]).filter(item=>item.catalog_id===id);}
const currentHelmetOrder=['precise-strike','deviation-expert','first-move-advantage','mag-expansion','work-of-proficiency','fortunes-favor','momentum-up','elemental-havoc','weapon-symphony','quick-toss'];
const currentHelmetLabels=['Precise Strike','Deviation Expert','First-Move Advantage','Mag Expansion','Work of Proficiency',"Fortune's Favor",'Momentum Up','Elemental Havoc','Weapon Symphony','Quick Toss'];
function helmetFamilyKey(entry){if(entry.slot!=='helmet_mod')return null;return currentHelmetOrder.find(key=>entry.id===`mod:helmet_mod:${key}`||entry.id.startsWith(`mod:helmet_mod:${key}-`))||null;}
function modFamilyName(entry){return modReferenceFamily(entry);}
function modCategoryEntryMatches(entry){if(characterModGoal==='all')return true;if(characterModView==='all'&&modReferenceScope==='game')return modReferenceMatchesGoal(entry,characterModGoal);const searchable=[entry.name,entry.base_name,entry.tree,entry.effect].join(' ').toLowerCase();return (modCategoryTerms[characterModGoal]||[]).some(term=>searchable.includes(term));}
function modPickerRows(){
  let rows=[];
  if(modCollectionMode){
    rows=(builderData.entries||[]).filter(entry=>entry.kind==='mod'&&modCategoryEntryMatches(entry)).flatMap(entry=>{
      const instances=modOwnedInstances(entry.id),target_slot=entry.slot==='weapon_mod'?'primary':modTargetSlots[entry.slot];
      if(characterModView==='owned')return instances.map(instance=>({entry,target_slot,match:null,instances:[instance]}));
      return [{entry,target_slot,match:null,instances}];
    });
  }else if(characterModView==='all'){
    rows=(builderData.entries||[]).filter(entry=>entry.kind==='mod'&&modCategoryEntryMatches(entry)).map(entry=>({entry,target_slot:entry.slot==='weapon_mod'?(['primary','secondary'].includes(modOriginSlot)?modOriginSlot:'primary'):modTargetSlots[entry.slot],match:null,instances:modOwnedInstances(entry.id)}));
  }else{
    const groups=characterModGuidance?.[characterModView];
    if(!groups)return [];
    rows=[...groups.weapon,...groups.armor].flatMap(candidate=>{
      const entry=catalogEntry(candidate.id),instances=candidate.owned_instances||[];
      if(!entry)return [];
      if(characterModView==='owned')return instances.map(instance=>({entry,target_slot:candidate.target_slot,match:candidate.match,instances:[instance]}));
      return [{entry,target_slot:candidate.target_slot,match:candidate.match,instances}];
    });
  }
  if(characterModView==='all')rows=rows.filter(row=>modReferenceScope==='game'?modReferenceIsCurrent(row.entry):!modReferenceIsCurrent(row.entry));
  if(characterModView==='all'){
    const withVariants=new Set(rows.filter(row=>row.entry.variant).map(row=>row.entry.slot+'|'+modFamilyName(row.entry)));
    rows=rows.filter(row=>row.entry.variant||!withVariants.has(row.entry.slot+'|'+modFamilyName(row.entry)));
  }

  if(modSlotFilter!=='all')rows=rows.filter(row=>row.entry.slot===modSlotFilter);
  const query=modSearch.trim().toLowerCase();
  if(query)rows=rows.filter(row=>[row.entry.name,row.entry.base_name,row.entry.variant,row.entry.tree,row.entry.effect].some(value=>String(value||'').toLowerCase().includes(query)));
  modReferenceSortRows(rows,characterModGoal);
  return rows;
}
let modBrowseScroll=0;
function modRender(preserveScroll=true){
  hideModHover();
  const listBefore=document.querySelector('#modFamilyList');
  if(!preserveScroll)modBrowseScroll=0;
  else if(listBefore&&!document.querySelector('.mod-backpack')?.classList?.contains?.('detail-open'))modBrowseScroll=listBefore.scrollTop||0;
  render();const list=document.querySelector('#modFamilyList');if(list)list.scrollTop=modBrowseScroll;
}
function resetModCollectionDetail(){if(!modCollectionMode)return;fieldGuideSelection=null;fieldGuidePreview=null;fieldGuideDraft=null;fieldGuideMath=null;fieldGuideRequest++;modCatalogRequest++;modCatalogDetail=null;modProfileEditing=modRecordsMode;modDetailOpen=false}
function setModReferenceScope(scope){if(!['game','other'].includes(scope))return;resetModCollectionDetail();modReferenceScope=scope;characterPreviewId=null;modSelectedDetail=null;modRender(false);}
function setModSlotFilter(slot){if(!modSlotTabs.some(tab=>tab[0]===slot))return;resetModCollectionDetail();modSlotFilter=slot;if(modCollectionMode||characterModView==='all')characterModGoal=slot==='weapon_mod'?'burn':'all';modSearch='';characterPreviewId=null;modSelectedDetail=null;modRender(false);}
function toggleModDetail(force){if(!modCollectionMode)return;modDetailOpen=typeof force==='boolean'?force:!modDetailOpen;modRender();if(modDetailOpen)document.querySelector('#modCollectionDetail')?.focus?.({preventScroll:true});else document.querySelector('#modDetailToggle')?.focus?.({preventScroll:true})}
document.addEventListener?.('keydown',event=>{if(event.key!=='Escape'||!modCollectionMode||!modDetailOpen||!globalThis.matchMedia?.('(max-width:850px)').matches)return;event.preventDefault();event.stopImmediatePropagation?.();toggleModDetail(false)},true);
function setModSearch(value){modSearch=String(value).slice(0,100);const pos=document.querySelector('#modSearch')?.selectionStart;if(modCollectionMode&&fieldGuideSelection&&!modPickerRows().some(row=>row.entry.id===fieldGuideSelection))resetModCollectionDetail();modRender(false);const input=document.querySelector('#modSearch');input?.focus?.({preventScroll:true});if(pos!=null)input?.setSelectionRange?.(pos,pos);if(!modPickerRows().some(row=>row.entry.id===characterPreviewId&&row.target_slot===characterSlot)){characterPreviewId=null;modSelectedDetail=null;const panel=document.querySelector('#modFocusedDetails');if(panel)panel.innerHTML=modFocusedHtml();}}
function modRowLevel(row){return row.instances[0]?.level||row.entry.observed_numeric_levels?.[0]||1;}
let modLevelEditorId=null;
function openModLevelEditor(id){
  if(!modCollectionMode||(builderData.owned_mods||[]).every(item=>item.id!==id))return;
  modLevelEditorId=id;modRender();document.querySelector('#modLevelDraft')?.focus?.({preventScroll:true});
}
function cancelModLevelEditor(){modLevelEditorId=null;modRender();}
async function commitModLevelEditor(id,clear=false){
  const value=clear?'':document.querySelector('#modLevelDraft')?.value;
  if(!clear&&value===undefined)return;
  await setModCollectionLevel(id,value);
  if((builderData.owned_mods||[]).some(item=>item.id===id&&item.level===(clear?null:Number(value)))){
    modLevelEditorId=null;modRender();
  }
}
function modVariantCard(row){
  const entry=row.entry,profileEntry=modRecordsMode?fieldGuideRecorded(entry.id):null;
  const instance=modRecordsMode&&fieldGuideProfile==='new_player'?null:row.instances[0];
  const level=profileEntry?.level||modRowLevel(row),selected=modCollectionMode?fieldGuideSelection===entry.id:characterPreviewId===entry.id&&characterSlot===row.target_slot&&characterPreviewLevel===level;
  if(entry.family_only)return '<div class="mod-variant-card unrecorded" role="note" aria-label="Family only; variant details unverified"><span class="mod-variant-frame"><span class="mod-missing-icon" aria-hidden="true">⬡</span></span><span class="mod-variant-caption">Variants and effects not verified</span></div>';
  const levelLabel=modCollectionMode?(modRecordsMode?(profileEntry?.level?`Field Guide Lv ${profileEntry.level}`:
    instance?`Existing mod record Lv ${instance.level??'?'} · system unverified`:
    'Field Guide level not recorded in this profile'):instance?`Recorded Lv ${instance.level??'?'}`:'Preview any level in details'):instance?instance.level==null?'Recorded · level unknown':`Recorded Lv ${instance.level}`:entry.ownership==='unlocked'?`Field Guide Lv ${entry.available_level??'?'} recorded`:entry.source_observed_level?`Seen Lv ${entry.source_observed_level} in game video · current ownership unknown`:entry.observed_numeric_levels?.includes(level)?`Catalog profile Lv ${level}`:'Level unverified';
  const observedRarity=modCollectionMode?(profileEntry?.level?fieldGuideRarity(profileEntry.level):instance?.observed_rarity||entry.rarity||'unknown'):instance?.observed_rarity||entry.rarity||'unknown';
  const locked=modCollectionMode?false:entry.ownership==='locked'&&!instance;
  const recordedUnlock=modCollectionMode?!!profileEntry?.level:entry.ownership==='unlocked'&&!instance;
  const historicalLock=modReferenceSourceLocked(entry);
  const videoLocked=historicalLock&&!instance&&!locked&&!recordedUnlock;
  const state=modRecordsMode&&fieldGuideProfile==='new_player'?(profileEntry?.level?'Unlocked in new-player profile':'Ownership unverified in new-player profile'):
    modRecordsMode&&profileEntry?.level?`Field Guide Lv ${profileEntry.level} in personal profile`:
    modRecordsMode&&instance?`Existing mod record Lv ${instance.level??'?'}; system unverified; Field Guide progress not yet confirmed`:
    modRecordsMode?'Ownership unverified in this profile; select to enter a known level':
    modCollectionMode?'Catalog preview; click for effects and bonuses':
    instance?`Recorded in your mods${historicalLock?' · lock seen in 2026-10-25 video':''}`:
    locked?'Locked in records; no owned mod instance':
    recordedUnlock?`Unlock recorded; no owned mod instance${historicalLock?' · lock seen in 2026-10-25 video':''}`:
    videoLocked?'Lock seen in 2026-10-25 video; current status unknown':'Unlock state unknown';
  const action=modCollectionMode?'fieldGuideCardClick(this.dataset.modId)':'previewGuidedMod(this.dataset.modId,this.dataset.modSlot,this.dataset.modLevel,event)';
  const chip=modCollectionMode?(profileEntry?.level??instance?.level??'?'):instance?(instance.level??'?'):entry.available_level??(entry.source_observed_level??(entry.observed_numeric_levels?.includes(level)?level:'?'));
  const marker=modCollectionMode&&profileEntry?.level?'<span class="mod-owned-mark" aria-label="Field Guide level recorded">✓</span>':modCollectionMode&&instance?'<span class="mod-backpack-mark" aria-label="Existing mod record; system unverified">•</span>':instance?'<span class="mod-owned-mark" aria-label="Recorded in your mods">✓</span>':recordedUnlock?'<span class="mod-owned-mark" aria-label="Field Guide unlock recorded">✓</span>':locked&&historicalLock?'<span class="mod-lock-mark mod-video-lock-mark" aria-label="Locked in source video; current profile not unlocked">🔒</span>':locked?'<span class="mod-lock-mark" aria-label="Not unlocked in this profile">🔒</span>':videoLocked?'<span class="mod-lock-mark mod-video-lock-mark" aria-label="Locked in 2026-10-25 video; current status unknown">🔒</span>':'';
  const sighting=!!entry.source_observed_level&&!instance&&!recordedUnlock;
  const suffixNeedsTooltip=modReferenceSuffixNeedsTooltip(entry);
  const evidenceNote=modCollectionMode&&!profileEntry?.level?(instance?`<small class="mod-variant-evidence">Existing Lv ${esc(instance.level??'?')}<br>System unverified</small>`:suffixNeedsTooltip?'<small class="mod-variant-evidence">Suffix needs tooltip</small>':''):historicalLock?`<small class="mod-variant-evidence">Locked in video · 10/25/26<br>${instance?'Owned now recorded':recordedUnlock?'Unlock now recorded':locked?'Locked in records':'Current status unknown'}</small>`:
    sighting?`<small class="mod-variant-evidence">Seen in video<br>${recordedUnlock?'Unlock now recorded':locked?'Locked in records':'Ownership unknown'}</small>`:
    suffixNeedsTooltip?'<small class="mod-variant-evidence">Suffix needs tooltip</small>':'';
  const suffixCaution=suffixNeedsTooltip?' · suffix spelling needs game-tooltip confirmation':'';
  const card=`<button class="mod-variant-card ${esc(observedRarity)} ${locked?'locked':''} ${videoLocked?'source-locked':''} ${modCollectionMode?profileEntry?.level?'recorded':instance?'existing-unclassified':'unrecorded':instance||recordedUnlock?'recorded':'unrecorded'} ${selected?'selected':''} ${evidenceNote?'has-evidence':''}" data-mod-id="${esc(entry.id)}" data-mod-slot="${esc(row.target_slot)}" data-mod-level="${esc(level)}" data-instance-id="${esc(instance?.id||'')}" ${modCollectionMode?'':`onpointerenter="showModHover(this.dataset.modId,this.dataset.modSlot,this.dataset.modLevel,this.dataset.instanceId,event)" onfocus="showModHover(this.dataset.modId,this.dataset.modSlot,this.dataset.modLevel,this.dataset.instanceId,event)" onpointerleave="scheduleModHoverHide()" onblur="scheduleModHoverHide()"`} aria-label="${modCollectionMode?modRecordsMode?'Record level for':'View details for':'Preview'} ${esc(entry.name)} · ${esc(levelLabel)} · ${state}${suffixCaution}" aria-pressed="${selected}" title="${esc(entry.name)} · ${esc(levelLabel)} · ${state}${suffixCaution}" onclick="${action}"><span class="mod-variant-frame">${entry.artwork||modSharedSuffixGlyph[entry.id]?characterArt(entry,true):'<span class="mod-missing-icon" aria-label="Artwork unavailable">⬡</span>'}</span><span class="mod-variant-level">${esc(chip)}</span>${marker}<span class="mod-variant-caption">${esc(modReferenceVariant(entry))}${evidenceNote}</span></button>`;
  if(modCollectionMode||!instance)return card;
  const editing=modLevelEditorId===instance.id;
  return `<div class="mod-variant-wrap">${card}<button type="button" class="mod-level-edit-trigger" aria-label="Edit level of ${esc(entry.name)} instance ${esc(instance.id.slice(0,5))}" data-instance-id="${esc(instance.id)}" onclick="openModLevelEditor(this.dataset.instanceId)">${esc(chip)}</button>${editing?`<div class="mod-level-editor" role="group" aria-label="Edit recorded Field Guide level"><label>Level · ${esc(instance.level_source||'source unknown')}<input id="modLevelDraft" aria-label="New recorded mod level" type="number" min="1" max="17" step="1" value="${esc(instance.level??'')}" onkeydown="if(event.key==='Enter')commitModLevelEditor('${esc(instance.id)}');if(event.key==='Escape'){event.stopPropagation();cancelModLevelEditor()}"></label><div><button class="primary" onclick="commitModLevelEditor('${esc(instance.id)}')">Save</button><button onclick="cancelModLevelEditor()">Cancel</button><button onclick="commitModLevelEditor('${esc(instance.id)}',true)">Clear</button></div><small>Only this saved instance changes. Builds keep their chosen level.</small></div>`:''}</div>`;
}
function modFamilyGroups(rows){
  if(!rows.length)return `<div class="mod-backpack-empty">${characterModView==='owned'?'No recorded mods match these filters.':'No catalog variants match these filters.'}</div>`;
  const groups=[];
  for(const row of rows){const family=modFamilyName(row.entry),slot=row.entry.slot,key=slot+'|'+family;let group=groups.find(item=>item.key===key);if(!group){group={key,family,slot,rows:[]};groups.push(group);}group.rows.push(row);}
  return groups.map(group=>{
    const art=modReferenceFamilyArt[`${group.slot}|${group.family}`],displayArt=art&&art.current_match!=='mismatch';
    const nativeLinked=group.rows.filter(row=>row.entry.native_mod_identity?.native_family?.family_membership_verified).length;
    const artTitle=art?`${art.partial?'Partial source emblem; covered pixels are not reconstructed':art.current_match===false?'Historical family art; current-game identity unverified':art.current_match==='motif_only'?'Named-slot catalog artwork; visible motif matches game crop, hidden detail unverified':'Game family artwork'} · ${art.source}${art.seconds==null?'':` at ${art.seconds}s`}`:'';
    const state=art?.current_match==='mismatch'?'<span class="mod-family-source-state">Current game emblem unavailable</span>':art?.partial?'<span class="mod-family-source-state" title="The source label covers part of this emblem">Partial source art</span>':art?.current_match===false?'<span class="mod-family-source-state">Current art unverified</span>':art?.current_match==='motif_only'?'<span class="mod-family-source-state">Hidden detail unverified</span>':art?'':'<span>Family emblem unverified</span>';
    return `<section class="mod-family" data-mod-slot="${esc(group.slot)}" aria-label="${esc(group.family)} variants"><div class="mod-family-name ${displayArt?'has-family-art':''}">${displayArt?`<img class="mod-family-art${art.native_icon?' mod-family-art-native':''}${art.path==='/artwork/family__weapon_mod__shield-breaker.webp'?' mod-family-art-shield-breaker':''}" src="${esc(art.path)}" alt="" title="${esc(artTitle)}">`:''}<small>${esc(modSlotTabs.find(tab=>tab[0]===group.slot)?.[1]||group.slot)}</small><h3>${esc(group.family)}</h3>${state}${nativeLinked?`<span class="mod-family-source-state">${nativeLinked} variant${nativeLinked===1?'':'s'} linked to native family</span>`:''}</div><div class="mod-family-cards">${group.rows.map(modVariantCard).join('')}</div></section>`;
  }).join('');
}
function modFocusedHtml(){
  const entry=catalogEntry(characterPreviewId),detail=modSelectedDetail?.entry?.id===characterPreviewId&&modSelectedDetail?.level===characterPreviewLevel?modSelectedDetail:null;
  if(!entry)return `<div class="mod-focus-empty"><span>⬡</span><p>Select a mod icon to inspect its effects and proposed level.</p></div>`;
  const owned=modOwnedInstances(entry.id),active=planned.slots[characterSlot]?.mod_id===entry.id;
  const attrs=detail?.known_attributes||[];
  const effect=detail?.verified_main_effect||detail?.primary_effect||entry.effect;
  const effectStatus=detail?.verified_main_effect?'Main effect verified at this level':'Catalog effect wording · exact-level magnitude and trigger not verified';
  const source=detail?.entry?.source_url;
  return `<div class="mod-focus-title"><small>${esc(characterNames[characterSlot])} MOD · ${owned.length?'RECORDED IN YOUR GEAR':'CATALOG PREVIEW'}</small><h3>${esc(entry.name)}</h3><span>${esc(entry.rarity||'Rarity unknown')} · ${esc(modReferenceVariant(entry))}${owned.length?` · Recorded ${owned.map(item=>'Lv '+esc(item.level??'?')).join(', ')}`:''}</span></div>
    <label class="mod-focus-level">Proposed Field Guide level <input type="number" min="1" max="17" step="1" aria-label="Proposed Field Guide level" value="${esc(characterPreviewLevel||1)}" onchange="setFocusedModLevel(this.value)"></label>
    <div class="mod-focus-section"><h4>Core Effects</h4><p>${esc(effect||'Core effect not cataloged')}</p><small>${esc(effectStatus)}</small></div>
    <div class="mod-focus-section"><h4>Attribute Effects</h4>${detail?attrs.length?attrs.map(attr=>`<div class="mod-attribute"><b>${esc(attr.name)} ${attr.value_percent==null?'value unknown':`${attr.direction==='reduction'?'−':'+'}${esc(attr.value_percent)}%`}</b><small>${attr.condition?`Condition: ${esc(attr.condition)} · `:''}Observed at Lv ${esc(attr.observed_level||characterPreviewLevel)}${attr.conditional_bonus_percent!=null?` · extra +${esc(attr.conditional_bonus_percent)}% when condition holds`:''}</small></div>`).join(''):'<p>Numeric attributes are unverified at this level.</p>':'<p>Loading level evidence…</p>'}</div>
    <div class="mod-focus-section mod-tech"><h4>Tech Level thresholds</h4><p>Threshold unlock effects are not verified for this entry. The game reference levels are not copied into your gear.</p></div>
    <div class="mod-focus-actions"><button class="primary" ${planned.slots[characterSlot]?.catalog_id?'':'disabled title="Equip gear in this slot first"'} onclick="equipCharacterPreview()">${active?'Apply level':'Equip'}</button><small>Equip assigns this preview to the current build. It does not add an item to your recorded gear.</small></div>
    <details class="mod-focus-evidence"><summary>Evidence and unknowns</summary>${source&&/^https:\/\//.test(source)?`<p>${characterSourceReference(source,'Catalog source')}</p>`:''}<p>${esc(detail?.unknowns?.join('; ')||'No additional exact-level evidence cataloged.')}</p></details>`;
}
let modHoverState=null,modHoverPanel=null,modHoverHideTimer=null,modHoverRequest=0;
const modHoverCache=new Map();
function cancelModHoverHide(){if(modHoverHideTimer){clearTimeout(modHoverHideTimer);modHoverHideTimer=null;}}
function scheduleModHoverHide(){cancelModHoverHide();modHoverHideTimer=setTimeout(()=>{
  if(modHoverPanel?.matches?.(':hover')||modHoverPanel?.contains?.(document.activeElement))return;
  hideModHover();
},240);}
function hideModHover(){cancelModHoverHide();modHoverRequest++;modHoverState=null;if(modHoverPanel)modHoverPanel.hidden=true;updateModCollectionAside();}
async function refreshModCollection(){builderData=await(await fetch('/api/builder-catalog')).json();modRender();}
async function addCollectionMod(id){
  const entry=catalogEntry(id);if(!modCollectionMode||entry?.kind!=='mod')return;
  try{const result=await api('mod-collection/add',{catalog_id:id});await refreshModCollection();notice(result.created?'Added to your mods · level unknown':result.restored?'Restored your mod recording':'Already recorded in your mods');}
  catch(error){fail(error);}
}
async function removeCollectionMod(id){
  const instance=(builderData.owned_mods||[]).find(item=>item.id===id&&item.manual_collection);
  if(!modCollectionMode||!instance)return;
  try{await api('mod-collection/remove',{id});await refreshModCollection();notice('Collection mark removed. Click its card to restore it. Saved builds are unchanged.');}
  catch(error){fail(error);}
}
async function setModCollectionLevel(id,value){
  const instance=(builderData.owned_mods||[]).find(item=>item.id===id);
  if(!modCollectionMode||!instance)return;
  try{await api('mod-collection/level',{id,level:value===''?null:value});await refreshModCollection();notice(value===''?'Mod level cleared to unknown':'Recorded mod level updated manually');}
  catch(error){fail(error);}
}
function clickCollectionModCard(id,event){
  if(!modCollectionMode)return;
  const instance=modOwnedInstances(id)[0];
  if(!instance)return addCollectionMod(id);
  showModHover(id,catalogEntry(id)?.slot==='weapon_mod'?'primary':modTargetSlots[catalogEntry(id)?.slot],instance.level||1,instance.id,event);
}
function modHoverHtml(state){
  const {entry,slot,level,instanceId,detail}=state,active=planned.slots[slot]?.mod_id===entry.id;
  const instances=modOwnedInstances(entry.id),instance=instances.find(item=>item.id===instanceId)||instances[0],owned=!!instance;
  const ownLevelUnknown=modCollectionMode&&instance&&instance.level==null;
  const attrs=ownLevelUnknown?[]:detail?.known_attributes||[],effect=detail?.verified_main_effect||detail?.primary_effect||entry.effect;
  const exact=!ownLevelUnknown&&!!detail?.verified_main_effect,source=detail?.entry?.source_url||entry.artwork_source;
  const family=modFamilyName(entry),scope=entry.slot==='weapon_mod'?'Weapon Mods · All Weapons':`${modSlotTabs.find(tab=>tab[0]===entry.slot)?.[1]||entry.slot} Mods`;
  const levelKnown=instance?instance.level!=null:!modCollectionMode&&(active||entry.observed_numeric_levels?.includes(level));
  const attrText=a=>`${a.name} ${a.value_percent==null?'value unknown':`${a.direction==='reduction'?'−':'+'}${a.value_percent}%`}`;
  return `<div class="mod-hover-head ${esc(entry.rarity||'unknown')}"><h3>${esc(family)}${entry.variant?` <em>&lt;${esc(modReferenceVariant(entry))}&gt;</em>`:''}</h3><span>${esc(scope)}</span></div>
    <div class="mod-hover-scroll"><div class="mod-hover-core">${entry.artwork?`<img src="${esc(entry.artwork)}" alt="" aria-hidden="true">`:''}<b>${esc(family)}</b><p>${esc(effect||'Core effect not cataloged')}</p><small>${exact?'Main effect verified at this level':'Catalog effect wording; exact-level magnitude or trigger remains unverified'}</small></div>
    <div class="mod-hover-level"><span aria-hidden="true">${modGoalIcon(modCollectionMode?modGoalForEntry(entry):characterModGoal)}</span><b>${levelKnown?'Lv '+esc(level):entry.source_observed_level?`Seen Lv ${esc(entry.source_observed_level)} in game video · not recorded in your gear`:'Level unverified'}</b><strong>${esc(entry.tree||family)}</strong></div>
    <div class="mod-hover-attributes"><h4>Attribute Effects</h4>${ownLevelUnknown?'<p>Your instance level and rolls are unknown; catalog examples are not copied to it.</p>':detail?attrs.length?attrs.map(a=>`<div><span>${esc(attrText(a))}</span>${a.condition?`<small>When ${esc(a.condition)}</small>`:''}${a.conditional_bonus_percent!=null?`<small>Conditional bonus +${esc(a.conditional_bonus_percent)}%</small>`:''}</div>`).join(''):'<p>Numeric attributes are unverified at this level.</p>':'<p>Loading level evidence…</p>'}</div>
    <div class="mod-hover-tech"><h4>Tech Level thresholds</h4><p>No verified threshold effects for this variant. Reference screenshot values are not copied into your gear.</p></div>
    <small class="mod-hover-state">${modCollectionMode?owned?`${instances.length} recorded instance${instances.length===1?'':'s'} · no build change`:'Not recorded · catalog preview only':active?'Equipped in this build':owned?'Recorded in your gear':'Catalog preview · ownership unchanged'}${/^https:\/\//.test(source||'')?` · ${characterSourceReference(source,'Source')}`:''}</small></div>
    <div class="mod-hover-actions">${modCollectionMode?state.confirmRemove?`<span>Remove this manual mark?</span><button onclick="modHoverAction('cancel_remove')">Cancel</button><button class="danger" onclick="modHoverAction('confirm_remove')">Remove</button>`:owned?`${`<span>${esc(instance.level_source||'source unknown')}</span><button onclick="openModLevelEditor('${esc(instance.id)}')">Edit level</button>${instance.manual_collection?`<button onclick="modHoverAction('remove_prompt')">Remove mark</button>`:''}`}`:`<button class="primary" onclick="modHoverAction('add')">Add to my mods</button>`:active?`<button onclick="modHoverAction('edit')">Edit level</button><button onclick="modHoverAction('unequip')">Unequip</button>`:owned&&instance.level==null?`<span>Owned level unknown</span><button onclick="modHoverAction('open_collection')">Set level in Mods</button>`:`<button onclick="modHoverAction('select')">Select</button><button class="primary" ${planned.slots[slot]?.catalog_id?'':'disabled'} onclick="modHoverAction('equip')">Equip</button>`}</div>`;
}
function modCollectionAsideHtml(state){
  if(!state?.entry)return `<div class="mod-collection-aside-empty"><span aria-hidden="true">◇</span><h3>Inspect a mod</h3><p>Hover or focus a card to see its family, effect and evidence here. The card-local tooltip remains available.</p><p>Browsing never equips a mod or changes your build.</p></div>`;
  const entry=state.entry,instance=modOwnedInstances(entry.id).find(item=>item.id===state.instanceId);
  const detail=state.detail,attributes=instance?.level==null?[]:detail?.known_attributes||[];
  const art=modReferenceFamilyArt[`${entry.slot}|${modFamilyName(entry)}`];
  return `<div class="mod-collection-aside-content"><small>SELECTED CATALOG ENTRY · ${esc(modSlotTabs.find(([slot])=>slot===entry.slot)?.[1]||entry.slot)}</small>${art&&art.current_match!=='mismatch'?`<img class="mod-collection-aside-art" src="${esc(art.path)}" alt="">`:''}<h3>${esc(modFamilyName(entry))}</h3><p class="mod-collection-aside-variant">${esc(modReferenceVariant(entry))} · ${instance?`Recorded Lv ${esc(instance.level??'?')}`:'Not recorded'}</p>${entry.source_observed_level?`<p>Seen at Lv ${esc(entry.source_observed_level)} in the supplied game recording. This is a catalog sighting, not your saved mod level or current ownership.</p>`:''}<h4>Core effect</h4><p>${esc(detail?.verified_main_effect||detail?.primary_effect||entry.effect||'Effect not cataloged')}</p><small>${detail?.verified_main_effect?'Verified for this level':'Catalog wording; exact-level effect unverified'}</small><h4>Attribute rows</h4>${attributes.length?`<ul>${attributes.map(row=>`<li>${esc(row.name||'Attribute')} ${row.value_percent==null?'value unknown':`${row.direction==='reduction'?'−':'+'}${esc(row.value_percent)}%`}</li>`).join('')}</ul>`:'<p>Numeric rows are unknown for this entry or level.</p>'}<h4>Build impact</h4><p>Inspecting this card changes nothing. Adding it records possession; equip it from a compatible loadout slot to test a build.</p>${art?.current_match==='mismatch'?'<p class="mod-collection-art-caution">The archived symbol differs from the supplied current-game image, so it is withheld. A verified complete emblem is still needed.</p>':art?.current_match===false?'<p class="mod-collection-art-caution">Full catalog artwork; exact current-game detail remains unverified.</p>':''}</div>`;
}
function updateModCollectionAside(){const panel=document.querySelector('#modCollectionDetail');if(panel&&modCollectionMode)panel.innerHTML=fieldGuidePanel()}
function placeModHover(){
  const state=modHoverState,panel=modHoverPanel;if(!state||!panel||panel.hidden)return;
  const rect=state.anchor?.getBoundingClientRect?.();if(!rect){hideModHover();return;}
  const pad=12,width=panel.offsetWidth,height=panel.offsetHeight;
  let left=rect.right+10;if(left+width>innerWidth-pad)left=rect.left-width-10;
  panel.style.left=Math.max(pad,Math.min(left,innerWidth-width-pad))+'px';
  panel.style.top=Math.max(pad,Math.min(rect.top,innerHeight-height-pad))+'px';
}
function modShouldFloatDetails(trigger){
  // On wide collection layouts the adjacent detail pane already exposes the
  // focused card to keyboard and screen-reader users. A second fixed panel
  // obscures the next cards. Clicking a recorded card still opens its actions.
  const aside=document.querySelector('#modCollectionDetail');
  const paneVisible=modCollectionMode&&aside&&typeof getComputedStyle==='function'&&getComputedStyle(aside).display!=='none';
  return !paneVisible||trigger?.type==='click';
}
function showModHover(id,slot,rawLevel,instanceId,trigger){
  const entry=catalogEntry(id),anchor=trigger?.currentTarget;
  if(!entry||entry.kind!=='mod'||!anchor||!document.createElement)return;
  cancelModHoverHide();const level=Math.max(1,Math.min(17,Number(rawLevel)||1)),floatPanel=modShouldFloatDetails(trigger);
  if(modHoverState?.id===id&&modHoverState?.slot===slot&&modHoverState?.level===level&&modHoverState?.anchor===anchor){
    if(!floatPanel){if(modHoverPanel)modHoverPanel.hidden=true;updateModCollectionAside();return;}
    if(modHoverPanel){modHoverPanel.hidden=false;modHoverPanel.innerHTML=modHoverHtml(modHoverState);placeModHover();return;}
  }
  const token=++modHoverRequest,key=id+'|'+level;
  modHoverState={id,slot,level,instanceId,entry,anchor,detail:modHoverCache.get(key)||null};
  if(floatPanel){
    if(!modHoverPanel){modHoverPanel=document.createElement('div');modHoverPanel.id='modHoverPanel';modHoverPanel.className='mod-hover-tooltip';modHoverPanel.setAttribute('role','region');modHoverPanel.addEventListener('pointerenter',cancelModHoverHide);modHoverPanel.addEventListener('pointerleave',scheduleModHoverHide);modHoverPanel.addEventListener('focusin',cancelModHoverHide);modHoverPanel.addEventListener('focusout',scheduleModHoverHide);document.body.appendChild(modHoverPanel);}
    modHoverPanel.hidden=false;modHoverPanel.setAttribute('aria-label',entry.name+' details');modHoverPanel.innerHTML=modHoverHtml(modHoverState);placeModHover();
  }else if(modHoverPanel)modHoverPanel.hidden=true;
  updateModCollectionAside();
  if(modHoverState.detail)return;
  fetch('/api/catalog/'+encodeURIComponent(id)+'?level='+level).then(r=>r.json()).then(detail=>{
    if(token!==modHoverRequest||!modHoverState||modHoverState.id!==id)return;
    if(detail.error)return;
    modHoverCache.set(key,detail);if(modHoverCache.size>80)modHoverCache.delete(modHoverCache.keys().next().value);
    modHoverState.detail=detail;if(modHoverPanel&&!modHoverPanel.hidden){modHoverPanel.innerHTML=modHoverHtml(modHoverState);placeModHover();}updateModCollectionAside();
  }).catch(()=>{});
}
async function modHoverAction(action){
  const state=modHoverState;if(!state)return;
  if(modCollectionMode){
    if(action==='remove_prompt'||action==='cancel_remove'){state.confirmRemove=action==='remove_prompt';modHoverPanel.innerHTML=modHoverHtml(state);placeModHover();return;}
    hideModHover();
    if(action==='add')await addCollectionMod(state.id);
    if(action==='confirm_remove')await removeCollectionMod(state.instanceId||modOwnedInstances(state.id).find(item=>item.manual_collection)?.id);
    return;
  }
  hideModHover();
  if(action==='open_collection'){openModCollection();return;}
  if(action==='equip'&&state.instanceId&&modOwnedInstances(state.id).find(item=>item.id===state.instanceId)?.level==null){notice('Record this owned mod’s actual level in Mods before equipping it.');return;}
  if(action==='unequip'){removePlannedMod(state.slot);return;}
  if(action==='edit'){showCharacterModLevel(state.slot);return;}
  if(characterPane!=='catalog'||picker?.mode!=='mod')return;
  previewGuidedMod(state.id,state.slot,state.level);
  if(action==='equip'){await equipCharacterPreview();hideModHover();}
}
document.addEventListener?.('keydown',event=>{if(event.key==='Escape'&&modHoverState){event.preventDefault();event.stopImmediatePropagation?.();hideModHover();}},true);
globalThis.addEventListener?.('resize',placeModHover);
function setFocusedModLevel(value){const level=Number(value);if(!Number.isInteger(level)||level<1||level>17){notice('Enter a Field Guide level from 1 to 17');return;}characterPreviewLevel=level;modSelectedDetail=null;const panel=document.querySelector('#modFocusedDetails');if(panel)panel.innerHTML=modFocusedHtml();loadFocusedModDetail();}
async function loadFocusedModDetail(){
  const id=characterPreviewId,level=characterPreviewLevel,request=++modSelectedRequest;if(!id)return;
  try{const response=await fetch('/api/catalog/'+encodeURIComponent(id)+'?level='+level),detail=await response.json();if(!response.ok)throw Error(detail.error||'Mod detail unavailable');if(request!==modSelectedRequest||id!==characterPreviewId||level!==characterPreviewLevel)return;modSelectedDetail=detail;const panel=document.querySelector('#modFocusedDetails');if(panel)panel.innerHTML=modFocusedHtml();}catch(error){if(request===modSelectedRequest){modSelectedDetail=null;const panel=document.querySelector('#modFocusedDetails');if(panel)panel.innerHTML='<p class="muted">Mod detail unavailable.</p>';}}
}
previewGuidedMod=function(id,slot,level){
  const entry=catalogEntry(id);if(!entry||entry.kind!=='mod'||!builderCompatible(entry,slot,'mod'))return;
  characterSlot=slot;characterEditKind='mod';picker={slot,mode:'mod',tab:slot};
  characterPreviewId=id;characterPreviewInventoryId=null;characterPreviewLevel=Number(level)||1;characterPreviewDetail=null;modSelectedDetail=null;
  modRender();[...(document.querySelectorAll?.('.mod-variant-card')||[])].find(node=>node.dataset.modId===id)?.focus?.({preventScroll:true});loadFocusedModDetail();
};
function autoSelectVisibleMod(){const rows=modPickerRows().filter(row=>!row.entry.family_only);if(!rows.length){characterPreviewId=null;modSelectedDetail=null;modRender();return;}if(rows.some(row=>row.entry.id===characterPreviewId&&row.target_slot===characterSlot))return;const equipped=planned.slots[modOriginSlot]?.mod_id;const row=characterModView==='all'?rows[0]:rows.find(item=>item.entry.id===equipped)||rows.find(item=>item.entry.slot==='weapon_mod'&&item.entry.artwork&&item.entry.observed_numeric_levels?.length)||rows[0];previewGuidedMod(row.entry.id,row.target_slot,modRowLevel(row));}
const oldLoadCharacterModGuidance=loadCharacterModGuidance;
loadCharacterModGuidance=async function(){await oldLoadCharacterModGuidance();};
setCharacterModView=function(view){
  if(!(modCollectionMode?['owned','all']:['overall','owned','all']).includes(view))return;
  resetModCollectionDetail();
  characterModView=view;
  modSlotFilter=modCollectionMode?(view==='all'?'weapon_mod':'all'):(builderMods[modOriginSlot]||'weapon_mod');
  if(modSlotFilter!=='weapon_mod')characterModGoal='all';
  modSearch='';characterPreviewId=null;modSelectedDetail=null;modRender(false);
};
setCharacterModGoal=function(goal){
  if(!characterGoalOptions.some(option=>option[0]===goal)&&!(modCollectionMode&&goal==='all'))return;
  if(modCollectionMode)resetModCollectionDetail();
  characterModGoal=goal;modSearch='';characterPreviewId=null;modSelectedDetail=null;
  if(modCollectionMode){modRender(false);return;}
  loadCharacterModGuidance();
  if(characterModView==='all')modRender(false);
};
function modPickerShell(){
  const collection=modCollectionMode,rows=modPickerRows(),gear=collection?null:catalogEntry(planned.slots[modOriginSlot]?.catalog_id),weaponBrowse=modSlotFilter==='weapon_mod',goalLabel=characterGoalOptions.find(([key])=>key===characterModGoal)?.[1]||(weaponBrowse?'All Weapon Mods':'All Mods');
  const scopes=collection?(modRecordsMode&&fieldGuideProfile==='new_player'?[['all','All Mods']]:[['all','All Mods'],['owned','My Mods']]):[['overall','Best overall'],['owned','Best with your gear'],['all','All Mods']];
  return `<section class="character-catalog mod-backpack ${collection?`collection ${modDetailOpen?'detail-open':'detail-closed'}`:''}" aria-label="${collection?'Mod collection':'Mod backpack'}"><div class="mod-backpack-head"><div><small>${collection?modRecordsMode?'FIELD GUIDE RECORDS':'MOD COLLECTION':`MOD BACKPACK · ${esc(characterNames[modOriginSlot])}`}</small><h2>${esc(goalLabel)}</h2></div><div class="mod-backpack-controls"><button class="secondary" onclick="exitModPicker()">← Loadout</button></div><div class="mod-backpack-scopes" role="group" aria-label="Mod catalog scope">${scopes.map(([key,label])=>`<button class="${characterModView===key?'active':''}" aria-pressed="${characterModView===key}" onclick="setCharacterModView('${key}')">${label}</button>`).join('')}</div><p>${collection?modRecordsMode?'Choose an exact mod and suffix to review or record its Field Guide level.':'Select any mod and suffix to see its main effect, four bonuses, and level progression. Previewing does not change your records.':characterModView==='all'?'Catalog variants matching this mechanic; cards do not imply ownership.':characterModView==='owned'?'Only mods recorded in your inventory; matching is not a damage ranking.':'Catalog mechanic matches; this is not a proven damage ranking.'} ${characterModView==='all'?(modReferenceScope==='game'?'Families and order verified in the supplied game recording.':'Other catalog entries are preserved for earlier records; absence from the recording does not mean unobtainable.'):''}${modReferenceScope==='game'&&modReferenceUnresolved[characterModGoal]?` ${modReferenceUnresolved[characterModGoal]}; that label stays unresolved.`:''}</p>${characterModView==='all'?`<div class="mod-backpack-scopes" role="group" aria-label="Catalog reference scope"><button class="${modReferenceScope==='game'?'active':''}" aria-pressed="${modReferenceScope==='game'}" onclick="setModReferenceScope('game')">Seen in game recording</button><button class="${modReferenceScope==='other'?'active':''}" aria-pressed="${modReferenceScope==='other'}" onclick="setModReferenceScope('other')">Other catalog entries</button></div>`:''}</div>
    ${collection&&modProfileEditing?`<div class="mod-profile-controls" role="group" aria-label="Field Guide profile"><span>Collection profile</span><button class="${fieldGuideProfile==='personal'?'active':''}" aria-pressed="${fieldGuideProfile==='personal'}" onclick="setFieldGuideProfile('personal')">My existing profile</button><button class="${fieldGuideProfile==='new_player'?'active':''}" aria-pressed="${fieldGuideProfile==='new_player'}" onclick="setFieldGuideProfile('new_player')">New player · empty</button><button id="modDetailToggle" class="mod-detail-toggle" type="button" aria-controls="modCollectionDetail" aria-expanded="${modDetailOpen}" onclick="toggleModDetail()">${modDetailOpen?'Hide details':'Show details'}${fieldGuideSelection?` · ${esc(catalogEntry(fieldGuideSelection)?.name||'selected mod')}`:''}</button><small>${fieldGuideProfile==='personal'?`${(state.inventory||[]).filter(i=>i.kind==='mod_unlock'&&!i.archived).length} existing saved mod records remain separate until their Field Guide system is verified.`:'New-player collection starts empty; your personal inventory remains unchanged.'}</small></div>`:''}
    <div class="mod-slot-tabs" role="group" aria-label="Mod slot">${modSlotTabs.filter(([key])=>key!=='all').map(([key,label])=>`<button class="${modSlotFilter===key?'active':''}" aria-label="${label} mods" aria-pressed="${modSlotFilter===key}" onclick="setModSlotFilter('${key}')">${label}</button>`).join('')}<details class="mod-view-menu"><summary>Views</summary><div><button onclick="setCharacterPane('equipment')">Loadout</button><button onclick="openSavedGear()">Saved gear</button><button onclick="openModCollection()">Mods</button><button onclick="openFieldGuideRecords()">Field Guide records</button><button onclick="openAccessoryCollection()">Accessories</button></div></details></div>
    ${weaponBrowse?`<nav class="mod-damage-rail" aria-label="Weapon mod mechanic category">${characterGoalOptions.map(([key,label])=>`<button class="${characterModGoal===key?'active':''}" title="${esc(label)}" aria-label="${esc(label)}" aria-pressed="${characterModGoal===key}" onclick="setCharacterModGoal('${key}')"><span class="mod-category-icon" aria-hidden="true">${modGoalIcon(key)}</span><span class="mod-category-name">${esc(label)}</span></button>`).join('')}</nav>`:''}
    <div class="mod-mechanic-heading">${weaponBrowse?esc(goalLabel):modSlotFilter==='all'?'All Mods':`${esc(modSlotTabs.find(([key])=>key===modSlotFilter)?.[1]||'Mod')} Mods`}</div>
    <div class="mod-backpack-body"><div class="mod-library"><div class="mod-library-top"><span>${rows.length} ${characterModView==='owned'?'recorded instances':'known catalog entries'}${collection?' · unrecorded cards are dim':characterModView==='all'?' · full catalog':' · effect matches'}</span>${collection?`<button class="secondary" onclick="setModSlotFilter('all')" aria-pressed="${modSlotFilter==='all'}">All slots</button>`:''}<input id="modSearch" type="search" aria-label="Search mods" placeholder="Search mods…" value="${esc(modSearch)}" oninput="setModSearch(this.value)"></div><div id="modFamilyList" class="mod-family-list">${modFamilyGroups(rows)}</div></div>
      ${collection?`<aside class="mod-collection-detail" id="modCollectionDetail" tabindex="-1" aria-label="${modRecordsMode?'Field Guide record editor':'Mod catalog details'}" aria-live="polite">${fieldGuidePanel()}</aside>`:`<div class="mod-weapon-stage"><small>${esc((characterNames[modOriginSlot]||'Weapon').toUpperCase())} · CURRENT BUILD</small>${gear?`<div class="mod-weapon-art">${characterArt(gear)}</div><h3>${esc(gear.name)}</h3>`:'<div class="mod-weapon-art empty">Gear not selected</div>'}<p>${gear?'Hover or focus a mod for nearby details. Equip is an explicit action.':'Choose gear in this slot before applying a mod.'}</p></div>`}</div></section>`;
}
characterModGuidanceHtml=function(){return modPickerShell();};
