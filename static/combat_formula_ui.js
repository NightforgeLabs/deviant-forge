// Read-only component formula. Blank inputs remain unknown; examples are opt-in.
let combatFormulaRequest=0;
let combatCoverageRequest=0;
let combatFormulaExample=false;
let combatFormulaSetupKey=null;
let combatFormulaBaselineKey=null;
function cfSourceReference(url,label='Source'){
 const value=String(url||'');
 if(/^https:\/\/(?:www\.)?oncehuman\.game\//.test(value))return `<a href="${esc(value)}" target="_blank" rel="noopener noreferrer">${esc(label)} ↗</a>`;
 const host=/^https?:\/\/([^/]+)/.exec(value)?.[1]?.replace(/^www\./,'')||'source unavailable';
 return `<span class="small muted">${esc(label)} · ${esc(host)} (third-party evidence; no external link)</span>`;
}
function invalidateCombatFormula(){combatFormulaRequest++;combatCoverageRequest++;const output=document.querySelector('#cf-Results');if(output)output.innerHTML='<p class="note warn">Inputs changed. Calculate again to update the result.</p>';const coverage=document.querySelector('#cf-Coverage');if(coverage&&coverage.innerHTML)coverage.innerHTML='<p class="small muted">Inputs or assumptions changed. Explain the selected build again to refresh this breakdown.</p>';const counter=document.querySelector('#cf-CounterResult');if(counter)counter.innerHTML=''}
function cfClearCounterInputs(){
 for(const id of ['CounterHits','CounterChance']){const field=$('#cf-'+id);if(field)field.value=''}
 const start=$('#cf-CounterStart');if(start)start.value='0';
 for(const id of ['CounterArmed','CounterReload']){const field=$('#cf-'+id);if(field)field.checked=false}
 const output=$('#cf-CounterResult');if(output)output.innerHTML='';
}
function cfClearSetupInputs(){
 for(const id of ['Damage','RPM','Mag','Crit','CritBonus','WeakBonus','MaxHP','Reload','Dodge','Hit','WeakShare','Overlap','EnergyOverlap','RapidOverlap','Returns','Psi','SurgeRate','SurgeDamage','SurgePsi','SurgeUptime','OrbRate','OrbDamage','OrbPsi','OrbUptime']){const field=$('#cf-'+id);if(field)field.value=''}
 for(const id of ['PreMod','PreModHP','MagSourceAssume']){const field=$('#cf-'+id);if(field)field.checked=false}
 for(const prefix of ['Surge','Orb'])for(const suffix of ['Elemental','Status','Field','RateGated']){const field=$('#cf-'+prefix+suffix);if(field)field.value=''}
 const magChance=$('#cf-MagBaseChance');if(magChance)magChance.value='';
 const magHits=$('#cf-MagLandedHits');if(magHits)magHits.value='40';
 cfClearCounterInputs();
 combatFormulaExample=false;
 cfClearExternalEffect();
}
function cfClearExternalEffect(){
 for(const suffix of ['', '-1', '-2'])cfClearExternalRow(suffix);
 for(const id of ['ExternalCompatibility','ExternalAdditive']){const field=$('#cf-'+id);if(field)field.checked=false}
}
function cfClearExternalRow(suffix=''){
 for(const id of ['ExternalName','ExternalValue','ExternalNote']){const field=$('#cf-'+id+suffix);if(field)field.value=''}
 for(const [id,value] of [['ExternalKind','other'],['ExternalStat',''],['ExternalActivation','unknown']]){const field=$('#cf-'+id+suffix);if(field)field.value=value}
 for(const id of ['ExternalApply','ExternalBaseline','ExternalInterval']){const field=$('#cf-'+id+suffix);if(field)field.checked=false}
 const panel=$('#cf-ExternalRow'+suffix);if(panel&&suffix){panel.open=false;panel.hidden=true}
 cfUpdateExternalSummaries();invalidateCombatFormula();
}
function cfExternalEffectAt(suffix=''){
 const name=val('cf-ExternalName'+suffix),note=val('cf-ExternalNote'+suffix),value=val('cf-ExternalValue'+suffix);
 if(!name&&!note&&!value&&!val('cf-ExternalStat'+suffix)&&!$('#cf-ExternalApply'+suffix)?.checked)return null;
 const activation=val('cf-ExternalActivation'+suffix);
 if(!['unknown','inactive','observed_active'].includes(activation))throw Error('Choose a valid external-effect activation state.');
 if($('#cf-ExternalApply'+suffix).checked&&activation!=='observed_active')throw Error('Confirm that the effect was observed active before applying its hypothetical amount.');
 return {source_kind:val('cf-ExternalKind'+suffix),name,stat_type:val('cf-ExternalStat'+suffix),
  value_percent:value===''?null:Number(value),source_note:note,
  activation,apply_hypothesis:$('#cf-ExternalApply'+suffix).checked,
  baseline_excludes_effect:$('#cf-ExternalBaseline'+suffix).checked,
  active_for_interval:$('#cf-ExternalInterval'+suffix).checked};
}
function cfExternalEffect(){return cfExternalEffectAt('')}
function cfExternalEffects(){return ['', '-1', '-2'].map(cfExternalEffectAt).filter(Boolean)}
function cfExternalStatName(stat){return ({weapon_damage_percent:'Weapon DMG',crit_damage_percent:'Crit DMG',weakspot_damage_percent:'Weakspot DMG',elemental_damage_percent:'Elemental DMG',status_damage_percent:'Status DMG',magazine_capacity_percent:'Magazine Capacity',reload_efficiency_percent:'Reload Efficiency',max_hp_percent:'Max HP',weapon_vulnerability_unmodeled:'Weapon Vulnerability · unmodeled',status_vulnerability_unmodeled:'Status Vulnerability · unmodeled',healing_or_shield_unmodeled:'Healing or shield · unmodeled',other_unmodeled:'Other · unmodeled'})[stat]||stat||'unknown stat'}
function cfExternalRow(suffix,label){return `<details class="cf-external-row" id="cf-ExternalRow${suffix}"${suffix?' hidden':' open'} ontoggle="cfExternalRowToggle('${suffix}')"><summary><span id="cf-ExternalSummary${suffix}">${esc(label)} · not entered</span></summary><div class="cf-external-body"><div class="formgrid"><label>Source kind<select id="cf-ExternalKind${suffix}"><option value="other">Other</option><option value="gear">Gear</option><option value="deviation">Deviation</option><option value="food">Food</option><option value="drink">Drink</option><option value="injection">Injection</option></select></label><label>Effect name<input id="cf-ExternalName${suffix}" type="text" maxlength="80" placeholder="observed name"></label><label>Exact observed stat<select id="cf-ExternalStat${suffix}"><option value="">Choose exact stat</option><option value="weapon_damage_percent">Weapon DMG %</option><option value="crit_damage_percent">Crit DMG %</option><option value="weakspot_damage_percent">Weakspot DMG %</option><option value="elemental_damage_percent">Elemental DMG %</option><option value="status_damage_percent">Status DMG %</option><option value="magazine_capacity_percent">Magazine Capacity %</option><option value="reload_efficiency_percent">Reload Efficiency %</option><option value="max_hp_percent">Max HP %</option><option value="weapon_vulnerability_unmodeled">Weapon Vulnerability · bucket not modeled</option><option value="status_vulnerability_unmodeled">Status Vulnerability · bucket not modeled</option><option value="healing_or_shield_unmodeled">Healing or shield · effect not modeled</option><option value="other_unmodeled">Other · effect not modeled</option></select></label>${cfField('ExternalValue'+suffix,'Observed percentage (supported stat only)')}<label>Activation<select id="cf-ExternalActivation${suffix}"><option value="unknown">Unknown · excluded</option><option value="inactive">Inactive · excluded</option><option value="observed_active">Observed active · eligible</option></select></label><label>Source note<input id="cf-ExternalNote${suffix}" type="text" maxlength="500" placeholder="what you saw and where"></label></div><label><input id="cf-ExternalApply${suffix}" type="checkbox"> Hypothetical: include this numeric effect</label><label><input id="cf-ExternalBaseline${suffix}" type="checkbox"> Entered baseline is unbuffed and excludes this effect and other same-bucket bonuses</label><label><input id="cf-ExternalInterval${suffix}" type="checkbox"> Assume active for the entire modeled interval</label><button class="secondary" type="button" onclick="cfClearExternalRow('${suffix}')">Clear row</button></div></details>`}
function cfExternalRowToggle(suffix){
 const current=$('#cf-ExternalRow'+suffix);if(!current?.open)return;
 for(const other of ['', '-1', '-2'])if(other!==suffix){const node=$('#cf-ExternalRow'+other);if(node)node.open=false}
}
function cfAddExternalEffect(){
 const suffix=['-1','-2'].find(key=>$('#cf-ExternalRow'+key)?.hidden);
 if(!suffix)return;
 const row=$('#cf-ExternalRow'+suffix);row.hidden=false;row.open=true;
 cfExternalRowToggle(suffix);cfUpdateExternalSummaries();invalidateCombatFormula();
 $('#cf-ExternalName'+suffix)?.focus?.();
}
function cfUpdateExternalSummaries(){
 for(const [index,suffix] of ['', '-1', '-2'].entries()){
  const node=$('#cf-ExternalSummary'+suffix);if(!node)continue;
  const name=val('cf-ExternalName'+suffix),stat=val('cf-ExternalStat'+suffix),amount=val('cf-ExternalValue'+suffix);
  const kind=val('cf-ExternalKind'+suffix),activation=val('cf-ExternalActivation'+suffix);
  node.textContent=!name&&!stat?'Effect '+(index+1)+' · not entered':
   'Effect '+(index+1)+' · '+(name||'name needed')+' · '+cfExternalStatName(stat)+(amount===''?'':' '+amount+'%')+
   ' · '+(activation==='observed_active'?($('#cf-ExternalApply'+suffix)?.checked?'active · hypothetical inclusion':'active · excluded until confirmed'):activation==='inactive'?'inactive · excluded':'activation unknown · excluded');
 }
 const add=$('#cf-ExternalAddButton');if(add)add.hidden=['-1','-2'].every(key=>!$('#cf-ExternalRow'+key)?.hidden);
}

function cfField(id,label,hint=''){return `<label>${esc(label)}<input id="cf-${id}" type="number" min="0" step="any" placeholder="${esc(hint)}"></label>`}
function cfSelect(id,label,options){return `<label>${esc(label)}<select id="cf-${id}"${['Build','Proposal','ModEvidence','Baseline','ActiveWeapon','Scenario','FightShape'].includes(id)?' onchange="cfGuideUpdate()"':''}>${options.map(([v,t])=>`<option value="${esc(v)}">${esc(t)}</option>`).join('')}</select></label>`}
function cfFightGuide(shape){return ({open_field:'Open-field boss: record time spent dodging, landed-shot share, and accepted Energy ammo returns while firing. Shielded hits are not assumed to trigger a return.',stationary:'Stationary target: measure landed-shot and weakspot shares even if aiming is easy. No perfect accuracy or field uptime is assumed.',mobile:'Moving target: measure landed-shot share and the time the target remains inside the AUG field. No hit rate or field uptime is inferred from this choice.'})[shape]||'Choose an encounter pattern to see which observations matter. This choice never fills numeric inputs.'}
// Optional finite-hit sensitivity. The main component formula uses entered average
// Power Surge event rates; these hypothetical counter states never feed that total.
function cfFiniteCounter({landed_hits,root_probability,instances_per_root=1,starting_counter=0,starting_armed=false,reload_clears=false,same_hit=false}){
 const hits=Number(landed_hits),p=Number(root_probability),m=Number(instances_per_root),start=Number(starting_counter);
 if(!Number.isInteger(hits)||hits<0||hits>2000)throw Error('Landed eligible weapon hits must be 0–2000');
 if(!Number.isFinite(p)||p<0||p>1)throw Error('Root trigger chance must be between 0 and 1');
 if(![1,2].includes(m))throw Error('Emitted instances per root must be 1 or 2 for this sensitivity');
 if(!Number.isInteger(start)||start<0||start>19)throw Error('Starting counter must be 0–19');
 if(starting_armed&&start)throw Error('Choose either an armed start or a partial starting counter');
 const states=Array(21).fill(0);states[reload_clears?0:starting_armed?20:start]=1;
 let resolved=0;
 for(let hit=0;hit<hits;hit++){
  const next=Array(21).fill(0);
  for(let count=0;count<=20;count++){
   const weight=states[count];if(!weight)continue;
   // A previously armed effect resolves on this eligible landed weapon hit.
   const wasArmed=count===20;
   const before=wasArmed?0:count;
   if(wasArmed)resolved+=weight;
   next[before]+=weight*(1-p);
   const after=before+m;
   if(same_hit&&after>=20){resolved+=weight*p;next[0]+=weight*p}
   else next[Math.min(20,after)]+=weight*p;
  }
  for(let i=0;i<states.length;i++)states[i]=next[i];
 }
 return {expected_resolutions:resolved,armed_probability:states[20],expected_roots:hits*p,steady_rate_shortcut:hits*p*m/20,threshold:20,hits,
  source:'https://www.oncehumandb.com/mods/thunderclap-power-surge'};
}
function cfCounterInvalidate(){invalidateCombatFormula()}
function cfCounterExample(){
 $('#cf-CounterHits').value='20';$('#cf-CounterChance').value='30';$('#cf-CounterStart').value='0';$('#cf-CounterArmed').checked=false;$('#cf-CounterReload').checked=false;
 cfCounterInvalidate();$('#cf-CounterResult').innerHTML='<p class="note warn">Synthetic 20-hit, 30% example loaded. This is not a measured trigger chance or an equipped Thunderclap claim.</p>';
}
function cfCounterPreview(){try{
 const buildId=val('cf-Build'),build=(state.planned_builds||[]).find(b=>b.id===buildId);
 if(!build)throw Error('Choose a saved planned build above to anchor this counter preview');
 const rawHits=val('cf-CounterHits'),rawChance=val('cf-CounterChance'),rawStart=val('cf-CounterStart');
 if(rawHits===''||rawChance==='')throw Error('Enter landed weapon hits and a root Power Surge trigger chance');
 const common={landed_hits:Number(rawHits),root_probability:Number(rawChance)/100,starting_counter:rawStart===''?0:Number(rawStart),starting_armed:$('#cf-CounterArmed').checked};
 const reload=$('#cf-CounterReload').checked;
 const one=cfFiniteCounter({...common,instances_per_root:1});
 const two=cfFiniteCounter({...common,instances_per_root:2});
 const same=cfFiniteCounter({...common,instances_per_root:2,same_hit:true});
 const cleared=reload?cfFiniteCounter({...common,instances_per_root:2,reload_clears:true}):null;
 const selected=build.slots?.mask?.mod_id||null;
 const selection=selected?.includes('thunderclap')?'The saved Mask choice names Thunderclap; its exact level damage is still unresolved.':selected?'The saved plan uses another Mask mod. Thunderclap is only a hypothetical replacement here.':'No Mask mod is recorded in the saved plan. Thunderclap is only hypothetical here.';
 const fmt=n=>Number(n).toFixed(6);
 $('#cf-CounterResult').innerHTML=`<div class="note"><b>${esc(build.name)} · finite Power Surge counter</b><p>${esc(selection)} This read-only count is separate from the average Power Surge and orb damage terms above; it is never added to their total. Evidence retrieved October 25, 2026; source publication date unknown.</p><div class="grid two"><div><strong>Next eligible hit (hypothesis)</strong><p>${esc(common.landed_hits)} landed eligible weapon hits at an entered ${esc(rawChance)}% constant root chance: one emitted instance → ${fmt(one.expected_resolutions)} expected Thunderclaps, ${fmt(one.armed_probability)} probability left armed; two emitted instances → ${fmt(two.expected_resolutions)} expected Thunderclaps, ${fmt(two.armed_probability)} left armed.</p></div><div><strong>Same-hit rival interpretation</strong><p>Two emitted instances with same-hit resolution → ${fmt(same.expected_resolutions)} expected Thunderclaps. A simple rate shortcut gives ${fmt(two.steady_rate_shortcut)}, which ignores warmup and armed state.</p></div></div>${cleared?`<p>With a reload immediately before the entered hits: keep counter → ${fmt(two.expected_resolutions)} expected; clear counter → ${fmt(cleared.expected_resolutions)} expected. The actual reload persistence is unknown.</p>`:''}<p>Twenty single-instance successes only arm the next-hit model at hit 20; a 21st eligible landed hit resolves it. A miss is not a landed hit. A Mayfly child instance counting as a second trigger is a hypothesis; it never recursively rolls another root here.</p><details><summary>Evidence and unresolved rules</summary><p>Source wording says after 20 Power Surge triggers, the next hit summons Celestial Thunder. A lower listed effect variant says next weapon hit. This model assumes independent Bernoulli root trials, eligible landed weapon hits, no cooldown, no expiry and discarded overflow only for sensitivity; those behaviors are not verified. Proc-only hits, orb eligibility, swap/reload persistence and exact damage magnitude are unresolved. Shock Rampage's time-varying chance is not included in the fixed input probability.</p><p>Evidence snapshot retrieved October 25, 2026; source publication date unknown. This is not an effective patch date.</p>${cfSourceReference(one.source,"Thunderclap listing")} · <span class="small muted">Mayfly commentary · YouTube (third-party evidence; no external link)</span></details></div>`;
 }catch(error){const node=$('#cf-CounterResult');if(node)node.innerHTML=`<p class="note warn">${esc(error.message||String(error))}</p>`}
}
function cfCounterPane(){return `<details class="cf-counter card" oninput="event.stopPropagation();cfCounterInvalidate()" onchange="event.stopPropagation();cfCounterInvalidate()"><summary><b>Thunderclap finite-hit check</b> · optional, read-only</summary><p class="small">Uses the saved build selected above. The main formula's entered average Power Surge event rate does not model this 20-trigger armed state. This check never adds damage to a build total.</p><div class="formgrid"><label>Landed eligible weapon hits<input id="cf-CounterHits" type="number" min="0" max="2000" step="1" placeholder="unknown"></label><label>Root Power Surge trigger chance (%)<input id="cf-CounterChance" type="number" min="0" max="100" step="any" placeholder="unknown"></label><label>Starting trigger count 0–19<input id="cf-CounterStart" type="number" min="0" max="19" step="1" value="0"></label><label><input id="cf-CounterArmed" type="checkbox"> Already armed before these hits</label><label><input id="cf-CounterReload" type="checkbox"> Reload immediately before these hits: compare keep versus clear</label></div><div class="actions"><button class="secondary" type="button" onclick="cfCounterExample()">Load synthetic 20-hit example</button><button class="primary" type="button" onclick="cfCounterPreview()">Preview counter alternatives</button></div><div id="cf-CounterResult" aria-live="polite"></div></details>`}
function combatFormulaCard(){
 combatFormulaRequest++;
 combatCoverageRequest++;
 combatFormulaExample=false;
 combatFormulaBaselineKey=JSON.stringify(['personal','','primary','tier_v_preview',{}]);
 combatFormulaSetupKey=JSON.stringify(['personal','','primary','','owned_instances','tier_v_preview','isles_of_abyss',{}]);
 const builds=state.planned_builds||[],proposals=(state.video_import_proposals||[]).filter(p=>p.data.ownership==='unlocked'&&p.status!=='dismissed'&&p.data.source_audit);
 const buildLabels=typeof plannedBuildChoiceLabels==='function'?plannedBuildChoiceLabels(builds):Object.fromEntries(builds.map(b=>[b.id,b.name]));
 const booleanOptions=[['','Unknown'],['true','Yes'],['false','No']];
 const stream=(prefix,title)=>`<div class="card"><h3>${title}</h3>${prefix==='Surge'?'<p class="small muted">Ordinary Power Surge is not field-gated; field eligibility belongs to the separate orb stream. Official May 13, 2026 release.</p>':''}<div class="formgrid">${cfField(prefix+'Rate','Raw events per active second','unknown')}${cfField(prefix+'Damage','Pre-mod damage per event','or use Psi coefficient')}${cfField(prefix+'Psi','Psi coefficient','unknown')}${cfSelect(prefix+'Elemental','Counts as Elemental damage?',booleanOptions)}${cfSelect(prefix+'Status','Counts as Status damage?',booleanOptions)}${prefix==='Orb'?cfSelect(prefix+'Field','Orb creation requires AUG field?',booleanOptions)+cfSelect(prefix+'RateGated','Does orb rate already include field eligibility?',booleanOptions)+cfField(prefix+'Uptime','Orb field eligibility fraction 0–1, if not included in rate','unknown'):''}</div></div>`;
 return `<section class="card" aria-label="Build component formula" style="margin-top:18px" oninput="invalidateCombatFormula();cfGuideUpdate();cfUpdateExternalSummaries()" onchange="invalidateCombatFormula();cfGuideUpdate();cfUpdateExternalSummaries()"><div class="kicker">COMPONENT FORMULA · READ ONLY</div><h2>Build damage over 60s and 300s</h2><p class="note">Select a saved build, then choose exact owned instances or matching Personal Field Guide rows. Video proposals remain hypothetical. No inventory or build is changed.</p><p class="small muted" id="cf-ProfileBoundary">Choose exact owned instances or exact-level Personal Field Guide rows as the calculation source. Either path still requires Tech and formula evidence.</p><div class="formgrid">
 ${cfSelect('Build','Saved planned build',[['','Isolated scenario'],...builds.map(b=>[b.id,buildLabels[b.id]])])}
 ${cfSelect('ActiveWeapon','Active weapon in saved build',[['primary','Primary'],['secondary','Secondary'],['melee','Melee']])}
 ${cfSelect('Proposal','Reviewed mod proposal to preview',[['','None'],...proposals.map(p=>[p.id,(p.data.title||p.data.name||p.data.catalog_id)+' · Lv '+(p.data.level??'?')])])}
 ${cfSelect('ModEvidence','Selected mod evidence',[['owned_instances','Exact owned instances'],['personal_field_guide','Personal Field Guide · exact variant and level']])}
 ${cfSelect('Baseline','Weapon baseline',[['tier_v_preview','Sourced uncalibrated Tier V AUG crafting preview'],['manual','Enter verified pre-mod weapon values']])}
 ${cfSelect('Scenario','Scenario rules',[['isles_of_abyss','Isles of Abyss PvE · no Cradle'],['other_unknown','Other scenario · rules unverified']])}
 <div class="cf-coverage-panel"><div class="cf-coverage-intro"><div><b>What this saved setup contributes</b><p>Check each selected item and mod row before trusting a build total. This only reads the plan.</p></div><button class="secondary" type="button" onclick="loadBuildCoverage()">Explain selected build</button></div><div class="cf-magazine-controls"><b>Cold / warm magazine · unsaved event what-if</b><p class="small muted">Uses the selected saved AUG calibration and weapon mod. Enter an assumed unmodified Power Surge chance; no chance is inferred from a saved build. This counts root triggers and possible spawned orbs, not damage or a build winner.</p><div class="formgrid">${cfField('MagBaseChance','Assumed base Power Surge chance %')}<label>Illustrative landed hits in this burst · 1–200; zero not modeled<input id="cf-MagLandedHits" type="number" min="1" max="200" step="1" value="40"></label></div><label><input id="cf-MagSourceAssume" type="checkbox"><span>Preview the unlinked Shock Rampage Lv17 screenshot: +6% relative trigger and +5% per stack, assuming the row is active. This does not save or equip it.</span></label><p class="small muted">Choose a saved plan, enter a chance and landed hits, then select “Explain selected build.” A full 40-shot magazine is illustrative unless this build's magazine and hit count are confirmed.</p></div><div id="cf-Coverage" aria-live="polite"></div></div>
 </div><div class="cf-guided"><div class="cf-guide-copy"><b>What Forge can answer now</b><p id="cf-GuideScope">This isolated scenario uses the sourced five-star Tier V AUG crafting preview only as an illustrative baseline. Direct-hit comparisons use stated bucket assumptions. A full fight total still needs reload, hit mix, Power Surge and orb observations.</p>${cfSelect('FightShape','Encounter pattern · measurement guide only',[['open_field','Open-field boss while dodging'],['stationary','Stationary target'],['mobile','Moving target']])}<p id="cf-FightGuide">${cfFightGuide('open_field')}</p><p id="cf-GuidedNext"><b>Next action:</b> With “Isolated scenario” selected, show the sourced Tier V preview. A saved weapon with a different tier or star count needs its own pre-mod measurements.</p><button class="primary" id="cf-Preview" onclick="runCombatFormula()">Show supported preview</button></div><div id="cf-GuidedEvidence"><b>Sourced crafting preview</b><p>Tier V AUG · 241 DMG · 720 RPM · 40 magazine. This is a blueprint preview, not your measured equipped damage.</p><small>Energy and Rapid Shot rolls are modeled with stated stacking assumptions.</small></div></div><details class="cf-expert"><summary>Expert inputs · add measurements or test assumptions</summary><p class="small muted">Optional screenshot reference: the five-star Tier V crafting preview is 241 DMG, 720 RPM, 40 MAG, 10% crit, 25% crit bonus and 60% weakspot bonus. It is used only when that baseline is selected and cannot be attached to a saved weapon with a different tier or star count. Manual values must be before calibration, selected mods and other active buffs in the same damage buckets; observed equipped hits already contain bonuses.</p><div class="formgrid">${cfField('Damage','Manual pre-mod DMG')}${cfField('RPM','Manual pre-mod RPM')}${cfField('Mag','Manual pre-mod magazine')}${cfField('Crit','Manual pre-mod crit rate 0–1')}${cfField('CritBonus','Manual pre-mod crit damage bonus 0–1')}${cfField('WeakBonus','Manual pre-mod weakspot damage bonus 0–1')}</div><label><input id="cf-PreMod" type="checkbox"> I confirm these manual values are pre-mod, uncalibrated and unbuffed, excluding gear, food and deviation bonuses in the modeled buckets.</label><label><input id="cf-TechAssume" type="checkbox"> What-if: assume every selected mod roll is active at this Tech level.</label><label><input id="cf-AllDamageHypothesis" type="checkbox"> Hypothetical only: treat observed All DMG Boost as an independent multiplier on outgoing damage.</label><p class="small muted">The observed roll amount is source checked, but its actual bucket placement and interaction with target-category bonuses are unverified. Without this opt-in, Forge withholds a complete total when this roll is selected. This checkbox never changes saved gear.</p><p class="small muted">In Isles of Abyss, the number of active mod attributes depends on Tech level. This app does not yet know which roll rows are active for your Tech level, so unchecked rows are excluded from the model, not treated as zero in game.</p>
 <div class="card cf-external-effects"><h3>External effects · unsaved what-if</h3><p class="small muted">Enter up to three observed effects from gear, deviations or consumables. Only exact supported stat types reach the existing formula. Unknown activation and unverified stacking stay excluded.</p>${cfExternalRow('','Effect 1')}${cfExternalRow('-1','Effect 2')}${cfExternalRow('-2','Effect 3')}<button id="cf-ExternalAddButton" class="secondary" type="button" onclick="cfAddExternalEffect()">Add effect</button><label><input id="cf-ExternalCompatibility" type="checkbox"> Hypothetical: named sources can coexist with each other and selected gear for this interval</label><label><input id="cf-ExternalAdditive" type="checkbox"> Hypothetical: repeated stat types add within the same typed bucket, including selected gear</label><p class="small muted">Source kinds do not establish food or drink slot legality, Chef rules, duration or damage buckets. Source values and assumptions are never saved.</p></div>
 <div class="card"><h3>Health sensitivity · separate from DPS</h3><p class="small muted">Enter Max HP before selected mod rolls. Game stacking and HP rounding are unverified.</p><div class="formgrid">${cfField("MaxHP","Pre-mod Max HP")}</div><label><input id="cf-PreModHP" type="checkbox"> This HP baseline excludes selected mod rolls.</label></div><h3>Fight and hit mix</h3><div class="formgrid">${cfField('Reload','Pre-effect reload seconds (before calibration speed and mod efficiency)')}${cfField('Dodge','Dodge downtime fraction 0–1')}${cfField('Hit','Hit fraction 0–1')}${cfField('WeakShare','Weakspot fraction among hits 0–1')}${cfField('Overlap','Shared crit + weakspot overlap fraction (fallback)')}${cfField('EnergyOverlap','Energy crit + weakspot overlap (if different)')}${cfField('RapidOverlap','Rapid Shot crit + weakspot overlap (if different)')}${cfField('Returns','Accepted Energy ammo returns per second while firing; enter 0 if observed none')}${cfField('Psi','Current Psi intensity, if using Psi coefficients')}</div><div class="grid two">${stream('Surge','Power Surge stream')}${stream('Orb','Orb stream')}</div><label><input id="cf-SurgeMeasuredCore" type="checkbox"> I measured the entered Power Surge event rate on this exact selected build, including its Shock Rampage core effect.</label><p class="small muted">Only check this for an observed event rate from this build and encounter. It does not establish Thunderclap damage or other unmodeled effects.</p><div class="actions"><button class="secondary" onclick="fillCombatExample()">Fill illustrative example</button><button class="primary" onclick="runCombatFormula()">Calculate components</button></div></details><div id="cf-Results" aria-live="polite"></div>${cfCounterPane()}<p class="small muted">Safe Haven gains stacks out of combat, so this boss-fight formula never applies it as a permanent damage buff. Other conditional core effects and set bonuses remain unmodeled unless their actual uptime and damage term are established.</p></section>`;
}
function cfGuideUpdate(){
 const id=val('cf-Build'),slot=val('cf-ActiveWeapon'),build=(state.planned_builds||[]).find(b=>b.id===id);
 const weapon=build?.slots?.[slot]||{},compatible=weapon.catalog_id==='weapon:aug-electron-cloud'&&Number(weapon.tier)===5&&Number(weapon.stars)===5;
 if(build&&!compatible&&val('cf-Baseline')==='tier_v_preview')$('#cf-Baseline').value='manual';
 const gearIdentity=build?.slots||{},profile=val('guideBuildProfile')||'personal';
 const baselineKey=JSON.stringify([profile,id,slot,val('cf-Baseline'),gearIdentity]);
 const setupKey=JSON.stringify([profile,id,slot,val('cf-Proposal'),val('cf-ModEvidence'),val('cf-Baseline'),val('cf-Scenario'),gearIdentity]);
 if(combatFormulaBaselineKey!==null&&baselineKey!==combatFormulaBaselineKey)cfClearSetupInputs();
 if(combatFormulaSetupKey!==null&&setupKey!==combatFormulaSetupKey){
   cfClearExternalEffect();
   $('#cf-TechAssume').checked=false;$('#cf-AllDamageHypothesis').checked=false;const measuredCore=$('#cf-SurgeMeasuredCore');if(measuredCore)measuredCore.checked=false;
   const magAssume=$('#cf-MagSourceAssume');if(magAssume)magAssume.checked=false;
   const magChance=$('#cf-MagBaseChance');if(magChance)magChance.value='';
   const magHits=$('#cf-MagLandedHits');if(magHits)magHits.value='40';
   cfClearCounterInputs();
   invalidateCombatFormula();
   combatCoverageRequest++;
   const coverage=$('#cf-Coverage');if(coverage)coverage.innerHTML=build?'<p class="small muted">Plan or assumptions changed. Explain this build again for current coverage.</p>':'<p class="small muted">Choose a saved plan to inspect item coverage.</p>';
 }
 combatFormulaBaselineKey=baselineKey;
 combatFormulaSetupKey=setupKey;
 const manual=val('cf-Baseline')==='manual';
 const manualValues=['Damage','RPM','Mag'].every(key=>Number($('#cf-'+key)?.value)>0);
 const manualConfirmed=manual&&manualValues&&$('#cf-PreMod')?.checked===true;
 const noSelectedMod=!!build&&!!weapon.catalog_id&&!weapon.mod_id;
 const scope=$('#cf-GuideScope');if(scope){
   const fight='A full fight total still needs reload, hit mix, Power Surge and orb observations.';
   const scenario=val('cf-Scenario')==='isles_of_abyss'?'':' Other scenario rules remain unverified.';
   scope.textContent=(manual?
     `${build?'This saved setup':'This isolated scenario'} uses pre-mod weapon values only after you enter and confirm them. The separate five-star Tier V crafting screenshot is not applied. ${fight}`:
     `${build?'This saved Tier V, five-star AUG matches the screenshot metadata, so it can use':'This isolated scenario uses'} the sourced crafting preview only as an illustrative baseline, not measured equipped damage. Direct-hit comparisons use stated bucket assumptions. ${fight}`)+scenario;
 }
 const message=manualConfirmed&&noSelectedMod?'<b>Next action:</b> This setup has an unsaved, user-confirmed pre-mod baseline. Select an owned mod in the build editor if you want its effects compared; no mod tooltip is missing.':
   manualConfirmed?'<b>Next action:</b> This selected setup has an unsaved, user-confirmed pre-mod baseline. Review its mod evidence and remaining fight observations; these numbers are not source-verified.':
   manual&&manualValues?'<b>Next action:</b> Confirm that the entered values are before the selected mod and calibration. They are not used yet.':
   manual?`<b>Next action:</b> ${build?'This saved build':'This scenario'} needs its own pre-mod weapon damage, firing rate and magazine. Enter the measured baseline before comparing.`:
   `<b>Next action:</b> ${build?'This saved Tier V AUG can use the sourced crafting preview as an illustrative baseline.':'With “Isolated scenario” selected, show the sourced Tier V preview.'} Model bucket rules remain assumptions.`;
 const target=$('#cf-GuidedNext');if(target)target.innerHTML=message;
 const fightGuide=$('#cf-FightGuide');if(fightGuide)fightGuide.textContent=cfFightGuide(val('cf-FightShape'));
 const evidence=$('#cf-GuidedEvidence');if(evidence)evidence.innerHTML=manualConfirmed?
   `<b>Unsaved manual baseline for this setup</b><p>${esc(val('cf-Damage'))} DMG · ${esc(val('cf-RPM'))} RPM · ${esc(val('cf-Mag'))} magazine, confirmed before selected mod and calibration. User-entered what-if; not measured or saved by Forge.</p>`:
   manual?'<b>For this selected setup</b><p>Pre-mod weapon damage, fire rate and magazine are not confirmed yet. The five-star Tier V crafting screenshot must not be reused for a different weapon, tier or star count.</p>':
   '<b>Sourced crafting preview</b><p>Tier V AUG · 241 DMG · 720 RPM · 40 magazine. This is a blueprint preview, not your measured equipped damage.</p><small>Energy and Rapid Shot rolls are modeled with stated stacking assumptions.</small>';
 const button=$('#cf-Preview');if(button){button.hidden=false;button.textContent=manualConfirmed?'Show supported preview':manualValues&&manual?'Confirm pre-mod values':manual?'Enter baseline measurements':'Show supported preview';button.setAttribute('onclick',manual&&!manualConfirmed?"cfFocusNext('cf-"+(manualValues?'PreMod':'Damage')+"')":"runCombatFormula()")}
}
function cfCoverageLabel(status,activation){if(status==='included_what_if')return activation==='verified_active'?'Included · Tech verified active':'Included only if Tech assumed active';const label=({
 included_reference:'Illustrative source baseline',manual_what_if:'User-confirmed manual what-if',
 tech_gated:'Tech activation unknown',tech_verified_inactive:'Verified inactive at this Tech level',unmodeled:'Not calculated',not_modeled:'Not calculated',
 core_unmodeled:'Core effect not calculated',missing_evidence:'Evidence needed',
 missing_typed_evidence:'Text recorded; numerical evidence needed',missing_baseline:'Pre-mod values needed',
 excluded_unresolved:'Instance or level unresolved',inactive_weapon:'Inactive weapon; excluded',
 condition_unknown:'Threshold or condition unverified',observed_only:'Observed readout only'
 })[status]||status;return ['unmodeled','excluded_unresolved'].includes(status)&&activation==='verified_active'?label+' · Tech verified active':label}
function cfEvidenceTargetAttrs(target,buildId){
 if(!target)return '';
 return ` data-build-id="${esc(buildId||'')}" data-owned-id="${esc(target.owned_instance_id||'')}" data-slot="${esc(target.slot||'')}" data-mod-id="${esc(target.catalog_id||'')}" data-level="${esc(target.level??'')}" data-source-ref="${esc(target.source_ref||'')}"`;
}
function cfCoverageAction(report){
 if(report.next_action_kind==='review_existing_evidence'&&report.next_action_target)return `<button class="secondary" type="button"${cfEvidenceTargetAttrs(report.next_action_target,report.build_id)} onclick="cfOpenExistingEvidence(this)">Review existing evidence</button>`;
 if(report.next_action_kind==='select_mod')return '<button class="secondary" type="button" onclick="go(\'builder\')">Select a mod</button>';
 return '';
}
function cfExistingEvidenceHtml(item,index,buildId){
 const source=item.existing_evidence;if(!source)return '';
 const target={owned_instance_id:item.owned_instance_id,slot:item.slot,catalog_id:item.catalog_id,level:item.level,source_ref:source.source_ref};
 const rows=source.typed_preview||[],unsupported=[...new Set(rows.filter(row=>row.calculation_status!=='assumption_scenario').map(row=>row.stat_type.replaceAll('_',' ')))];
 const location=source.image_url?'The full original frame is displayed below.':source.source_ref?.startsWith('libfile_')?'The original is referenced in ChatGPT Library; an in-app image preview is unavailable.':'An in-app image preview is unavailable for this recorded source.';
 const conflict=item.row_order_discrepancy;
 const orderWarning=conflict?`<div class="note warn"><b>Source disagreement · ${esc(conflict.unique_content_count)} distinct recorded positions.</b> The saved observation and tooltip differ in value, count, or order. Row position may change Tech activation. Neither version is applied to calculations. Compare both with the original image before attachment.<p>Saved observation · ${esc(conflict.observed_source||'source location unknown')}</p><ol>${conflict.observed_attribute_lines.map(line=>`<li>${esc(line)}</li>`).join('')}</ol><p>Tooltip · ${esc(conflict.tooltip_source||'source location unknown')}</p><ol>${conflict.tooltip_attribute_lines.map(line=>`<li>${esc(line)}</li>`).join('')}</ol></div>`:'';
 return `<details id="cf-Evidence-${index}" class="cf-existing-evidence"${cfEvidenceTargetAttrs(target,buildId)}><summary>Review existing evidence · ${esc(item.name)} Lv ${esc(item.level??'?')}</summary><p class="note">Exact owned instance ${esc(item.owned_instance_id)}. Original source: ${esc(source.source_name||'filename unavailable')} (${esc(source.source_ref)}). ${location}</p>${source.image_url?`<a href="${esc(source.image_url)}" target="_blank" rel="noopener" aria-label="Open full original source image"><img class="cf-source-image" src="${esc(source.image_url)}" alt="Full original game screenshot for this exact mod and level"></a>`:''}${source.transcription_note?`<p class="small muted">${esc(source.transcription_note)}</p>`:''}${orderWarning}<p><b>Core effect, separate from suffix rows:</b> ${esc(source.core_effect||'unknown')}</p><ol>${rows.map(row=>`<li>${esc(row.raw_text)} · ${esc(row.stat_type.replaceAll('_',' '))} · ${row.visible_magnitude==null?'amount unreadable':esc(row.visible_magnitude)+'%'} · ${esc(row.calculation_status)} · Tech ${esc(row.tech_activation)} · ${esc(row.confidence==='source_checked'?'source checked':source.image_url?'recorded; compare original image':'original image unavailable')}</li>`).join('')}</ol><p class="note warn">${rows.length} recorded ${rows.length===1?'line is':'lines are'} not attached as typed numerical rolls. ${unsupported.length?`Formula placement or evidence remains unsupported for: ${esc(unsupported.join(', '))}. `:''}Tech activation is unknown unless separately verified. This preview does not change gear. Applying evidence requires a separate source-checked review and explicit Apply confirmation.</p></details>`;
}
function cfOpenExistingEvidence(button){
 const target=button?.dataset||{},build=(state.planned_builds||[]).find(item=>item.id===target.buildId);
 const selected=build?.slots?.[target.slot];
 if(!build||val('cf-Build')!==target.buildId||selected?.mod_id!==target.modId||Number(selected?.mod_level)!==Number(target.level)||selected?.mod_inventory_id&&selected.mod_inventory_id!==target.ownedId){
  const output=$('#cf-Coverage');if(output)output.innerHTML='<p class="note warn">The selected mod changed. Explain this build again before reviewing its evidence.</p>';
  return false;
 }
 const details=[...document.querySelectorAll('.cf-existing-evidence')].find(node=>['buildId','ownedId','slot','modId','level','sourceRef'].every(key=>node.dataset[key]===target[key]));
 if(!details)return false;
 details.open=true;details.scrollIntoView({block:'nearest',behavior:'smooth'});return true;
}
async function cfReviewExistingEvidence(button){await loadBuildCoverage();return cfOpenExistingEvidence(button)}
function cfMagazineHtml(item){
 if(!item)return '';
 const source=item.sources||{},r=item.rapid_style_evidence,style=esc(item.calibration_style||'No recorded style');
 const modLabel=item.mod_id==='mod:weapon_mod:shock-rampage-power-surge'?'Shock Rampage <Power Surge>':item.mod_id?String(item.mod_id).split(':').pop().replaceAll('-',' '):'no selected weapon mod';
 const shockSourceGap=item.mod_id==='mod:weapon_mod:shock-rampage-power-surge'&&item.mod_level===17;
 let result='';
 if(item.status==='unlinked_source_requires_opt_in')result='<p class="note warn">The selected Lv17 mod has an original screenshot, but its values are not linked to Personal progress. Opt in above to preview them without saving.</p>';
 else if(item.status==='enter_base_chance')result='<p class="note warn">Enter an assumed base Power Surge chance above; no trigger count is inferred from the selected plan.</p>';
 else if(item.cold_expected_roots!=null){
  result=`<p><b>Cold: ${augFmt(item.cold_expected_roots)}</b> expected roots; <b>four stacks throughout: ${augFmt(item.warm_four_stacks_expected_roots)}</b> across ${esc(item.landed_hits)} landed hits.</p>`;
  if(item.armed_cold_expected_roots!=null)result+=`<p>With a separately assumed empty reload, Vanguard's guaranteed first root replaces its normal chance: <b>${augFmt(item.armed_cold_expected_roots)}</b> cold roots; ${augFmt(item.armed_warm_four_stacks_expected_roots)} warm. The guaranteed root adds one stack only after that hit in this model.</p>`;
  result+=`<details><summary>Per-stack chances and AUG field-order alternatives</summary><p>Cold chances: ${(item.cold_per_stack_chances||[]).map(p=>augFmt(p*100)+'%').join(' → ')}. Field before first Power Surge → ${augFmt(item.cold_orbs_field_before_first_ps)} possible spawned orbs; Power Surge before field → ${augFmt(item.cold_orbs_ps_before_field)}. Warm equivalents: ${augFmt(item.warm_orbs_field_before_first_ps)} or ${augFmt(item.warm_orbs_ps_before_field)}.${item.armed_cold_expected_roots!=null?` Armed cold alternatives: ${augFmt(item.armed_cold_orbs_field_before_first_ps)} or ${augFmt(item.armed_cold_orbs_ps_before_field)}.`:''} These are spawn hypotheses, not confirmed collisions.</p></details>`;
 }else if(item.unarmed_expected_roots!=null)result=`<p><b>Unarmed: ${augFmt(item.unarmed_expected_roots)}</b> expected roots; <b>after an assumed empty reload: ${augFmt(item.armed_after_empty_reload_expected_roots)}</b> across ${esc(item.landed_hits)} landed hits. The first guaranteed root replaces its ordinary chance.</p><details><summary>AUG field-order alternatives</summary><p>Unarmed spawned-orb hypotheses: ${augFmt(item.unarmed_orbs_field_before_first_ps)} if the field precedes first Power Surge, or ${augFmt(item.unarmed_orbs_ps_before_field)} if Power Surge precedes it. Armed: ${augFmt(item.armed_orbs_field_before_first_ps)} or ${augFmt(item.armed_orbs_ps_before_field)}. Initial full magazine does not establish an empty reload.</p></details>`;
 const rapid=r?`<details><summary>Two Rapid blueprint candidates: purple 15% / gold 20%</summary><p>The saved plan records an Oct 24 ${esc(r.saved_blueprint_rarity||'purple-background')} candidate blueprint: ${esc(r.saved_effects_raw)}${r.saved_source_image?' in '+esc(r.saved_source_image):''}. The separate Oct 25 gold one-use candidate shows +20% Fire Rate, raw Reload Speed +10%, Attack −10%. Neither screenshot proves crafting or installation on this weapon; the older candidate is not labeled obsolete. The <a href="${esc(r.official_release_source)}" target="_blank" rel="noopener">May 21, 2025 official table ↗</a> also lists +20% Fire Rate and +10% Reload Efficiency. Raw Reload Speed and Reload Efficiency are not assumed identical.</p><p>Separate illustrative Tier V five-star screenshot baseline: ${augFmt(r.illustrative_base_rpm)} RPM and ${esc(r.illustrative_magazine)} magazine, which does not match this saved plan's Tier/stars. Using only that illustrative input, applying the recorded 15% would give ${augFmt(r.saved_scenario_rpm)} RPM / ${augFmt(r.saved_first_to_last_seconds)}s first-to-last shot; applying the separate 20% would give ${augFmt(r.standalone_20_percent_scenario_rpm)} RPM / ${augFmt(r.standalone_first_to_last_seconds)}s. The Oct 24 crafting preview itself still displays 720 RPM, so these are arithmetic sensitivities, not its observed final stats. No measured cycle, installed roll or DPS correction is inferred.</p><small>Saved screenshot ${esc(r.saved_source_ref||'unverified')} · separate blueprint ${esc(r.standalone_blueprint_source_ref)} · Tier V example ${esc(r.illustrative_uncalibrated_source)}. The saved profile remains unchanged.</small></details>`:'';
 return `<div class="card cf-magazine-preview"><h4>Selected AUG · cold / warm Power Surge</h4><p class="small muted">${esc(item.active_weapon_slot)} · Tier ${esc(item.tier??'?')} · ${esc(item.stars??'?')} stars · ${style} · ${esc(modLabel)}${item.mod_id?' Lv '+esc(item.mod_level??'?'):''}. Entered ${esc(item.landed_hits)} landed hits do not prove this build's effective capacity, fired shots or accuracy.</p>${result}${rapid}<p class="note warn">Hypothetical event counts, not saved damage or DPS. ${shockSourceGap?"The selected Lv17 Shock source remains unlinked; ":""}Proc behavior${shockSourceGap?" and Tech activation":""} remain unverified.</p><details><summary>Sources, limits and model assumptions</summary><p>Rapid and Vanguard saved plans differ in stars and mod, so this is not an isolated calibration comparison. Independent-trial RNG, stack expiry, first-hit field order and actual orb collisions remain unverified.</p><ul>${Object.entries(source).filter(([,v])=>v).map(([k,v])=>`<li>${esc(k)} · ${v.startsWith('https://')?cfSourceReference(v,'Source'):esc(v)}</li>`).join('')}</ul><ul>${(item.warnings||[]).map(w=>`<li>${esc(w)}</li>`).join('')}</ul><small>Source check October 25, 2026. Historical publication dates do not certify this build's current proc distribution.</small></details></div>`;
}
function cfCoverageHtml(report){
 const count=report.row_counts||{},activation=report.activation_counts||{},included=count.included_what_if||0,gated=count.tech_gated||0,inactive=count.tech_verified_inactive||0;
 const summary=`${included} roll rows in selected what-if (${activation.verified_active||0} Tech verified, ${activation.assumed_active||0} Tech assumed) · ${gated} Tech unknown · ${inactive} verified inactive · ${report.missing_mod_items||0} mod instances lack usable exact numeric roll evidence. An included row does not make its whole item or the build fully calculated.`;
 const baselinePending=(report.items||[]).some(item=>item.kind==='weapon'&&item.status==='missing_baseline'&&item.slot===val('cf-ActiveWeapon'));
 const primary=baselinePending?'Enter and confirm pre-mod damage, firing rate and magazine for this exact saved weapon.':report.next_action||'Review the unresolved effects.';
 const later=baselinePending&&report.next_action?`<details class="cf-later-action"><summary>After that: ${esc(report.next_action)}</summary>${cfCoverageAction(report)}</details>`:'';
 return `<div class="cf-coverage-report"><p class="note warn">${esc(summary)}</p><p class="cf-next-action"><b>Next action:</b> ${esc(primary)} ${baselinePending?'':cfCoverageAction(report)}</p>${later}${cfMagazineHtml(report.selected_magazine_preview)}<div class="cf-coverage-list">${(report.items||[]).map((item,index)=>`<div class="cf-coverage-item"><div class="cf-coverage-head"><b>${esc(item.slot)} · ${esc(item.name)}</b><span class="badge">${esc(item.kind)} · ${esc(cfCoverageLabel(item.status))}</span></div><ul>${(item.rows||[]).map(row=>`<li><span>${esc(row.text)}</span><small>${esc(cfCoverageLabel(row.status,row.activation_status))}${row.next_action?' · '+esc(row.next_action):''}</small></li>`).join('')}</ul>${item.next_action?`<p class="small muted"><b>${baselinePending?'Later':'Next'}:</b> ${esc(item.next_action)}</p>`:''}${cfExistingEvidenceHtml(item,index,report.build_id)}<details><summary>Evidence and modeling details</summary><ul>${(item.rows||[]).map(row=>`<li>${esc(row.stat_type||'effect')} · ${esc(row.source==null?'source not recorded':typeof row.source==='string'?row.source:JSON.stringify(row.source))}</li>`).join('')}</ul>${item.issues?.length?`<p>${esc(item.issues.join('; '))}</p>`:''}</details></div>`).join('')}</div><p class="small muted">${esc(report.scope||'This report does not change saved gear.')}</p></div>`
}
async function loadBuildCoverage(){
 cfGuideUpdate();
 const request=++combatCoverageRequest,buildId=val('cf-Build'),output=$('#cf-Coverage');
 if(!output)return;
 if(!buildId){output.innerHTML='<p class="note">Choose a saved build to see its selected items. An isolated scenario has no equipped items.</p>';return}
 output.innerHTML='<p class="note">Reading this saved plan…</p>';
 try{
  const hitText=val('cf-MagLandedHits');
  const hitCount=hitText===''?null:Number(hitText);
  if(hitCount!==null&&(!Number.isInteger(hitCount)||hitCount<1||hitCount>200)){
   output.innerHTML='<p class="note warn">Enter 1–200 whole landed hits for this burst. The saved-build coverage has not been refreshed.</p>';return;
  }
  const data=await api('build-contribution-coverage',{build_id:buildId,active_weapon_slot:val('cf-ActiveWeapon'),baseline_mode:val('cf-Baseline'),manual_baseline:val('cf-Baseline')==='manual'?{damage:num('cf-Damage'),rpm:num('cf-RPM'),magazine:num('cf-Mag'),confirmed_pre_mod:$('#cf-PreMod').checked}:null,scenario:val('cf-Scenario'),tech_policy:$('#cf-TechAssume').checked?'assume_active':'exclude_unknown',all_damage_model:$('#cf-AllDamageHypothesis').checked?'independent_outgoing_multiplier':'exclude_unverified',magazine_hypothesis:{base_chance:val('cf-MagBaseChance')===''?null:Number(val('cf-MagBaseChance'))/100,landed_hits:hitCount,use_unlinked_shock17:$('#cf-MagSourceAssume').checked}});
  if(request===combatCoverageRequest){
   output.innerHTML=cfCoverageHtml(data)+(hitCount===null?'<p class="note warn">Cold / warm preview skipped: enter 1–200 whole landed hits if you want this optional event count.</p>':'');
   const baselinePending=(data.items||[]).some(item=>item.kind==='weapon'&&item.status==='missing_baseline'&&item.slot===val('cf-ActiveWeapon'));
   const action=baselinePending?'Enter and confirm pre-mod damage, firing rate and magazine for this exact saved weapon.':data.next_action||'Review the unresolved effects.';
   const guide=$('#cf-GuidedNext');if(guide)guide.innerHTML=`<b>Next action:</b> ${esc(action)}`;
   const button=$('#cf-Preview');if(button)button.hidden=!baselinePending&&['review_existing_evidence','select_mod'].includes(data.next_action_kind);
  }
 }catch(error){if(request===combatCoverageRequest)output.innerHTML=`<p class="note warn">${esc(error.message||String(error))}</p>`}
}
function cfFocusNext(id){const field=$('#'+id);if(!field)return;const details=field.closest('details');if(details)details.open=true;field.focus();field.scrollIntoView({block:'center',behavior:'smooth'})}
function cfNextAction(missing,response){
 const issue=response?.selected_owned_mods?.unresolved?.[0];
 if(issue?.code==='owned_roll_evidence_missing'){
  const item=(state.inventory||[]).find(item=>item.id===issue.owned_instance_id&&item.level===issue.selected_level&&item.effects?.catalog_id===issue.mod_id);
  const stats=item?.stats||{},source=stats.observed_tooltip||{};
  const levels=[stats.original_observed_level,stats.screenshot_import?.observed_level,source.observed_level].filter(x=>x!=null);
  const specific=source.source_ref==='libfile_84a17de486208191951ea249c448e8c6'&&issue.mod_id==='mod:weapon_mod:shock-rampage-power-surge'&&item?.slot==='weapon_mod'&&item?.variant==='Power Surge'&&issue.selected_level===17;
  const generic=source.catalog_id===issue.mod_id&&source.slot===item?.slot&&source.variant===item?.variant&&source.observed_level===issue.selected_level;
  if(source.source_ref&&levels.some(level=>level!==issue.selected_level))return {text:`${issue.mod_name} is selected at Lv ${issue.selected_level??'?'}, but its stored tooltip was observed at Lv ${levels.find(level=>level!==issue.selected_level)}. That older evidence cannot verify this level. Review the exact current-level tooltip before attaching rows.`,page:'import',label:'Review level evidence'};
  if(source.source_ref&&levels.every(level=>level===issue.selected_level)&&(specific||generic))return {text:`${issue.mod_name} Lv ${issue.selected_level??'?'} already has a recorded game tooltip. Review its exact source and staged rows in the selected-build breakdown. Tech and effect formulas remain unresolved; nothing is attached until a separate source-checked Apply.`,reviewExisting:{owned_instance_id:item.id,slot:issue.slot,catalog_id:issue.mod_id,level:issue.selected_level,source_ref:source.source_ref}};
  return {text:`${issue.mod_name} Lv ${issue.selected_level??'?'} is saved as owned, but its instance has no source-checked attribute lines. Import its exact tooltip, review the match and rows, then choose Apply evidence for this owned instance.`,page:'import',label:'Review mod evidence'};
 }
 if(issue?.code==='owned_level_mismatch')return {text:`The saved ${issue.slot} mod is set to Lv ${issue.selected_level??'?'}, but the owned instance is recorded at Lv ${(issue.available_levels||[]).join(', ')||'unknown'}. Check the actual level before changing the saved plan.`,page:'builder',label:'Check saved mod'};
 if(issue?.code==='roll_level_mismatch')return {text:`This owned mod is Lv ${issue.selected_level??'?'}, but its numeric rows were observed at Lv ${issue.observed_level??'?'}. Capture current-level rows before calculating their effects.`,page:'import',label:'Import current tooltip'};
 if(issue)return {text:`${issue.slot}: ${issue.reason}. Confirm the exact owned instance, level and source evidence before including its rolls.`,page:'inventory',label:'Check owned mod'};
 if(response?.coverage_reasons?.some(x=>/No mod is selected on the active/i.test(x)))return {text:'This saved plan has no mod selected on its active weapon. Choose an owned mod in the build editor to include its rolls.',page:'builder',label:'Open build editor'};
 if(response?.hypothetical_proposal_ids?.length&&response?.coverage_reasons?.some(x=>/no typed attribute rows/i.test(x)))return {text:'The selected proposal has no verified attribute rows. Check its evidence before comparing.',field:null};
 if(response?.coverage_reasons?.some(x=>/All DMG Boost bucket/i.test(x)))return {text:'The All DMG Boost amount is recorded, but its place in the full damage formula is unverified. Review the optional multiplier what-if; otherwise the total stays unknown.',field:'cf-AllDamageHypothesis'};
 if(response?.coverage_reasons?.some(x=>/unmodeled|unverified/i.test(x)))return {text:'A selected mod has an unsupported or unverified attribute row. Check its source and applicability; supported components remain partial.',field:null};
 if(response?.coverage_reasons?.some(x=>/Tech level/i.test(x)))return {text:'Confirm which mod rows are active at your current Tech level; an explicit what-if control is under Expert inputs.',field:'cf-TechAssume'};
 const first=missing?.[0]||'';
 if(val('cf-FightShape')==='mobile'&&missing?.some(x=>/hit rate/i.test(x)))return {text:'For this moving target, about what fraction of fired shots land?',field:'cf-Hit'};
 if(/dodge downtime/i.test(first))return {text:'About what fraction of this fight will you spend dodging instead of firing?',field:'cf-Dodge'};
 if(/reload/i.test(first))return {text:'How many seconds is the reload before this calibration’s Reload Speed and selected mod Reload Efficiency? Do not enter the already-modified final reload time.',field:'cf-Reload'};
 if(/ammo returns/i.test(first))return {text:'How many Energy bullets return per second while you are firing? Enter observed zero if none.',field:'cf-Returns'};
 if(/hit rate/i.test(first))return {text:'Roughly what fraction of your shots hit this target?',field:'cf-Hit'};
 if(/crit|weakspot|overlap/i.test(first))return {text:'What fraction of landed shots hit a weakspot? Crit overlap can be entered separately.',field:'cf-WeakShare'};
 const prefix=/Power Surge/i.test(first)?'Surge':/orb/i.test(first)?'Orb':null;
 if(prefix){const field=/event rate|stream/i.test(first)?'Rate':/damage|Psi/i.test(first)?'Damage':/field requirement/i.test(first)?'Field':/uptime/i.test(first)?'Uptime':/classification/i.test(first)?'Elemental':'Rate';return {text:`Check the ${prefix==='Surge'?'Power Surge':'orb'} observation or classification named in the unresolved inputs.`,field:'cf-'+prefix+field}}
 return {text:first?'Open Expert inputs and supply the first missing observation.':'Review the source and assumptions before using this comparison.',field:first?'cf-Reload':null}
}
function cfFlag(id){let v=val('cf-'+id);return v===''?null:v==='true'}
function cfStream(prefix){return {events_per_active_second:num('cf-'+prefix+'Rate'),rate_origin:prefix==='Surge'&&$('#cf-SurgeMeasuredCore')?.checked?'measured_selected_build':'entered_assumption',pre_mod_damage_per_event:num('cf-'+prefix+'Damage'),psi_coefficient:num('cf-'+prefix+'Psi'),elemental:cfFlag(prefix+'Elemental'),status:cfFlag(prefix+'Status'),requires_field:prefix==='Surge'?false:cfFlag(prefix+'Field'),rate_includes_field_uptime:prefix==='Surge'?null:cfFlag(prefix+'RateGated'),field_uptime_fraction:prefix==='Surge'?null:num('cf-'+prefix+'Uptime')}}
function fillCombatExample(){
 combatFormulaExample=true;
 cfClearExternalEffect();
 const values={Reload:2,Dodge:0.2,Hit:0.85,WeakShare:0.2,Overlap:0.02,Returns:0,Psi:100,SurgeRate:1.5,SurgePsi:0.5,OrbRate:0.6,OrbPsi:0.42,OrbUptime:0.75};
 for(const [k,v] of Object.entries(values))$('#cf-'+k).value=v;
 $('#cf-EnergyOverlap').value='';$('#cf-RapidOverlap').value='';
 $('#cf-TechAssume').checked=false;$('#cf-AllDamageHypothesis').checked=false;const measuredCore=$('#cf-SurgeMeasuredCore');if(measuredCore)measuredCore.checked=false;
 for(const prefix of ['Surge','Orb'])$('#cf-'+prefix+'Damage').value='';
 for(const prefix of ['Surge','Orb']){$('#cf-'+prefix+'Elemental').value='true';$('#cf-'+prefix+'Status').value=prefix==='Surge'?'true':'false'}$('#cf-OrbField').value='true';$('#cf-OrbRateGated').value='false';
 invalidateCombatFormula();
 $('#cf-Results').innerHTML='<p class="note warn">Illustrative inputs loaded: reload, dodge, hit mix, Psi, event rates and field uptime are assumptions, not observed values. Click Calculate to see a conditional example.</p>';
}
function cfOne(name,d,coreEffects=[]){let health=d.max_hp_sensitivity;const shockUnknown=coreEffects.some(effect=>effect.name==='Shock Rampage'&&effect.total_blocking);let rows=['60','300'].map(t=>{let x=d.durations[t],b=x.bullet_damage_bounds,s=x.power_surge,o=x.orb,total=x.total_damage_bounds;
 return `<div class="card"><h4>${t} seconds · ${name}</h4><p>${x.shot_count_model==='continuous_expected_ammo_return_exposure'?'Expected shot exposure (fractional return-rate model)':x.shot_count_model==='discrete_first_shot_at_zero_half_open'?'Integer firing opportunities (first shot at 0; endpoint excluded)':'Firing opportunities'} ${x.shots_bounds?augFmt(x.shots_bounds.floor)+'–'+augFmt(x.shots_bounds.ceil):'unknown'}; bullet ${b?augFmt(b.floor)+'–'+augFmt(b.ceil):'unknown'}; Power Surge ${s?.damage==null?'unknown':augFmt(s.damage)+(shockUnknown?' entered stream only; Shock Rampage contribution unknown':'')}; orb ${o?.damage==null?'unknown':augFmt(o.damage)}.</p><p>Conditional total ${total?`<b>${augFmt(total.floor)}–${augFmt(total.ceil)}</b> damage · ${augFmt(x.average_dps_bounds.floor)}–${augFmt(x.average_dps_bounds.ceil)} average DPS`:'unknown until all components are supplied'}.</p>${x.missing.length?`<details><summary>${x.missing.length} unresolved inputs</summary><p class="note warn">${esc(x.missing.join('; '))}</p></details>`:''}</div>`}).join('');
 return `<div><h3>${name}</h3><p>Modeled direct body hit ${augFmt(d.base_direct_hit_after_bonuses)} (bucket assumptions apply), RPM ${augFmt(d.rpm_scenario)}, magazine ${d.magazine_bounds.floor}–${d.magazine_bounds.ceil}. ${d.hit_groups?'Expected landed hit '+augFmt(d.hit_groups.expected_landed_hit):'Expected hit mix unknown'}.</p>${health?.has_selected_max_hp_roll?`<p>Max HP what-if: ${(d.typed_modifiers_tech_gated||[]).some(row=>row.stat_type==='max_hp_percent')&&health.bonus_percent===0?'gain unknown; Tech activation unverified':health.after_unrounded==null?'enter confirmed pre-mod Max HP':`${augFmt(health.pre_mod_max_hp)} → ${augFmt(health.after_unrounded)} unrounded (+${augFmt(health.bonus_percent)}%)`}. Separate from DPS; Tech activation and stacking assumptions apply.</p>`:''}<details><summary>Calibration evidence and source</summary><p>Game screenshot: <code>${esc(d.calibration_source||'not recorded')}</code>. ${esc(d.baseline_source_kind||'Baseline provenance unknown')}.</p><ul>${(d.calibration_observed_effects||[]).map(effect=>`<li>${esc(effect)}</li>`).join('')}</ul><small>These observed bonuses are placed into assumed calculation buckets; the source does not verify stacking order.</small></details>${rows}</div>`}
function cfSelectedCounter(){
 const hits=val('cf-CounterHits'),chance=val('cf-CounterChance');
 if(hits===''||chance==='')return null;
 return {eligible_landed_hits:Number(hits),root_trigger_chance:Number(chance)/100,starting_counter:Number(val('cf-CounterStart')||0),starting_armed:$('#cf-CounterArmed').checked};
}
function cfCoreEffectsHtml(effects){
 if(!effects?.length)return '<p class="small muted">No Shock Rampage on the active weapon or Thunderclap in the selected Mask. Their core effects are not added to this total.</p>';
 return `<div class="note warn"><b>Selected core effects · separate from typed roll rows</b><ul>${effects.map(effect=>`<li><b>${esc(effect.slot)} · ${esc(effect.name)}:</b> ${esc(effect.component)} — ${esc(effect.reason)} ${effect.total_blocking?'The full fight total is withheld.':'The entered measured rate already includes this frequency effect; it is not multiplied again.'}${effect.needed?' Next: '+esc(effect.needed):''}${effect.counter_preview?` Conditional finite event count: ${augFmt(effect.counter_preview.next_hit_two_instances.expected_resolutions)} under next-hit/two-instance assumptions versus ${augFmt(effect.counter_preview.same_hit_two_instances.expected_resolutions)} under same-hit assumptions. Damage remains unknown.`:''} ${cfSourceReference(effect.source,'Source')} <small>Retrieved ${esc(effect.source_retrieved)}; publication date unknown.</small></li>`).join('')}</ul></div>`;
}
function cfRollEvidence(result){
 const energy=result.energy,groups=[['Included under explicit Tech or external-effect what-if',energy.typed_modifiers_used],['Excluded: Tech activation unverified',energy.typed_modifiers_tech_gated],['Not modeled or not source checked',energy.typed_modifiers_unmodeled]];
 return `<details><summary>Selected mod rows · evidence and effect (${groups.reduce((sum,[,rows])=>sum+(rows?.length||0),0)})</summary><p class="small">A video proposal is a hypothetical preview, not owned gear. An assumed-active row remains unverified at your Tech level. Source-checked amounts do not prove a damage bucket.</p>${groups.map(([label,rows])=>`<h4>${esc(label)} · ${rows?.length||0}</h4>${rows?.length?`<ul>${rows.map(row=>`<li>${esc(row.raw_text||row.stat_type||'Unresolved row')} · ${esc(row.stat_type||'unparsed')} · ${esc(row.confidence||'evidence unknown')}${row.model_exclusion?' · bucket unverified; excluded':''}${row.evidence?.proposal_id?' · hypothetical proposal':row.owned_instance_id?' · owned instance':''}</li>`).join('')}</ul>`:'<p class="small muted">None</p>'}`).join('')}</details>`
}
async function runCombatFormula(){cfGuideUpdate();const request=++combatFormulaRequest,output=$('#cf-Results');if(!output)return;output.innerHTML='<p class="note">Calculating with the displayed inputs…</p>';try{
 const buildId=val('cf-Build'),proposalId=val('cf-Proposal'),mode=val('cf-Baseline');let baseline=null;
 if(mode==='manual'){
  if(!$('#cf-PreMod').checked)throw Error('Confirm that manual weapon inputs are pre-mod, uncalibrated and unbuffed.');
  baseline={base_origin:'pre_mod_unbuffed',damage:num('cf-Damage'),rpm:num('cf-RPM'),magazine:num('cf-Mag'),crit_rate:num('cf-Crit'),crit_damage_bonus:num('cf-CritBonus'),weakspot_damage_bonus:num('cf-WeakBonus'),source_ref:'user-entered pre-mod baseline'};
 }
 const d=await api('build-combat-formula',{build_id:buildId||null,active_weapon_slot:val('cf-ActiveWeapon'),modifier_source:val('cf-ModEvidence')||'owned_instances',external_effects:cfExternalEffects(),assume_external_compatibility:$('#cf-ExternalCompatibility').checked,assume_external_additive_bucket:$('#cf-ExternalAdditive').checked,proposal_ids:proposalId?[proposalId]:[],use_tier_v_preview:mode==='tier_v_preview',baseline,
  encounter:{scenario:val('cf-Scenario'),pre_mod_max_hp:num('cf-MaxHP'),max_hp_excludes_selected_mods:$('#cf-PreModHP').checked,pre_mod_reload_seconds:num('cf-Reload'),dodge_fraction:num('cf-Dodge'),hit_rate:num('cf-Hit'),weakspot_fraction:num('cf-WeakShare'),crit_weak_overlap:num('cf-Overlap'),energy_crit_weak_overlap:num('cf-EnergyOverlap'),rapid_crit_weak_overlap:num('cf-RapidOverlap'),accepted_energy_returns_per_second:num('cf-Returns'),psi_intensity:num('cf-Psi'),tech_policy:$('#cf-TechAssume').checked?'assume_active':'exclude_unknown',all_damage_model:$('#cf-AllDamageHypothesis').checked?'independent_outgoing_multiplier':'exclude_unverified'},
  power_surge:cfStream('Surge'),orb:cfStream('Orb'),core_counter:cfSelectedCounter()});
 if(request!==combatFormulaRequest||output.isConnected===false||$('#cf-Results')!==output)return;
 const r=d.result,terms=r.energy.assumptions;
 const missing=[...new Set([...r.energy.durations['60'].missing,...r.rapid.durations['60'].missing,...r.energy.durations['300'].missing,...r.rapid.durations['300'].missing])],next=cfNextAction(missing,d);
 const effects=d.external_effects||[];
 const externalHtml=effects.length?`<details class="cf-external-summary"><summary>Unsaved external effects · ${effects.filter(x=>x.applied).length} modeled of ${effects.length} observations</summary><p class="small muted">Each amount is user entered. Changes below remove one source at a time from the combined hypothetical model. Do not add these marginals: interacting buckets can make their sum differ from the combined change. They are not measured game contributions.</p><ul>${effects.map((item,i)=>{const c=(d.external_contributions||[])[i]||{};return `<li><b>${esc(item.source_kind)} · ${esc(item.name)}</b> · ${esc(cfExternalStatName(item.stat_type))}${item.value_percent==null?'':' '+esc(item.value_percent)+'%'} · ${esc(item.reason)}${c.applied?` · Energy direct-hit change ${augFmt(c.energy_direct_hit_delta)}; Rapid ${augFmt(c.rapid_direct_hit_delta)}; Power Surge/60s ${c.power_surge_60s_delta==null?'unknown':augFmt(c.power_surge_60s_delta)}; orb/60s ${c.orb_60s_delta==null?'unknown':augFmt(c.orb_60s_delta)}`:''}. <small>Source note: ${esc(item.source_note||'none')}</small></li>`}).join('')}</ul>${(d.external_assumptions||[]).map(x=>`<p class="note warn">${esc(x)}</p>`).join('')}</details>`:'';
 const summaryFor=(name,choice)=>{const duration=choice.durations['60'],bounds=duration?.bullet_damage_bounds,finite=Number.isFinite(bounds?.floor),hit=choice.hit_groups?.expected_landed_hit;return {name,value:finite?bounds.floor:hit,unit:finite?'modeled 60s bullet component':'modeled expected direct hit',finite}};
 const energySummary=summaryFor('Energy',r.energy),rapidSummary=summaryFor('Rapid Shot',r.rapid);
 const summaries=[energySummary,rapidSummary];const sameUnit=energySummary.unit===rapidSummary.unit;
 const delta=sameUnit&&Number.isFinite(energySummary.value)&&Number.isFinite(rapidSummary.value)?Math.abs(energySummary.value-rapidSummary.value):null;
 const lead=delta==null?'No supported comparison yet':delta<1e-9?'These components tie':(energySummary.value>rapidSummary.value?'Energy':'Rapid Shot')+' leads by '+augFmt(delta)+' '+energySummary.unit;
 const resultSummary=`<p class="cf-result-scope"><b>Modeled components — not full-build DPS.</b> ${esc(lead)}.</p><div class="cf-result-metrics">${summaries.map(x=>`<div><span>${esc(x.name)}</span><strong>${Number.isFinite(x.value)?augFmt(x.value):'Unknown'}</strong><small>${esc(x.unit)}</small></div>`).join('')}</div>`;
 output.innerHTML=`<div class="card"><h3>Formula output · ${esc(d.build_name||'isolated scenario')}</h3>${resultSummary}<p class="cf-next-action"><b>Next action:</b> ${esc(next.text)}${next.reviewExisting?` <button class="secondary" type="button"${cfEvidenceTargetAttrs(next.reviewExisting,buildId)} onclick="cfReviewExistingEvidence(this)">Review existing evidence</button>`:''}${next.field?` <button class="secondary" type="button" onclick="cfFocusNext('${next.field}')">Enter this value</button>`:''}${next.page?` <button class="secondary" type="button" onclick="go('${next.page}')">${esc(next.label)}</button>`:''}</p>${combatFormulaExample?'<p class="note warn"><b>Illustrative example inputs remain in this calculation.</b> They are not measurements from your build; verify or replace them before using the result for a decision.</p>':''}<details class="cf-result-deep"><summary>Full component math and evidence</summary><p class="note warn">${esc(d.warning||'Conditional model only; not verified game total DPS.')}</p>${externalHtml}<p>Source: ${esc(r.energy.baseline_source||'manual')}. Mod evidence: ${d.modifier_source==='personal_field_guide'?'Personal Field Guide exact-level rows':'exact owned instances'}. Active weapon: ${esc(d.selected_owned_mods.active_weapon_slot)}; inactive weapon slots ignored: ${esc(d.selected_owned_mods.ignored_weapon_slots.join(', ')||'none')}. Typed roll rows applied: ${d.modifier_count} of ${d.candidate_modifier_count}. Tech activation unknown and excluded: ${r.energy.typed_modifiers_tech_gated.length}. ${r.energy.tech_activation_policy==='assume_active'?'Unknown roll rows are included only under your explicit what-if assumption.':'Excluded rows are not zero in game.'} Selected mod slots with typed rows: ${esc(d.selected_owned_mods.resolved_slots.join(', ')||'none')}. Hypothetical proposals: ${d.hypothetical_proposal_ids.length}.</p>${d.coverage_reasons.length?`<p class="note warn">Roll coverage is incomplete: ${esc(d.coverage_reasons.join('; '))}</p>`:''}${d.selected_owned_mods.unresolved.length?`<p class="note warn">Unresolved saved mods: ${esc(d.selected_owned_mods.unresolved.map(x=>x.slot+': '+x.reason).join('; '))}</p>`:''}${cfCoreEffectsHtml(d.selected_core_effects)}${cfRollEvidence(r)}<div class="grid two">${cfOne('Energy',r.energy,d.selected_core_effects)}${cfOne('Rapid Shot',r.rapid,d.selected_core_effects)}</div><details><summary>Formula and assumptions</summary><p>Without ammo returns, finite firing opportunities are integer shots: first at t=0, only shots before the active-time endpoint count, and each new magazine begins after M/(RPM/60) plus reload. A positive entered ammo-return rate uses continuous expected shot exposure because exact return times are unknown. Expected bullet damage uses normal, crit, weakspot and overlap weights, hit fraction and the selected mod's typed bonuses. Ordinary Power Surge is not field-gated; orb rate is adjusted for field eligibility only if not already reflected in that rate. Power Surge/orb damage = entered event rate × active seconds × entered pre-mod event damage (or Psi × coefficient) × explicitly classified bonus factors and field uptime. A total appears only when every term is resolved.</p><ul>${terms.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></details></details></div>`;
}catch(e){if(request===combatFormulaRequest&&output.isConnected!==false&&$('#cf-Results')===output)output.innerHTML=`<p class="note warn">${esc(e.message||String(e))}</p>`}}
