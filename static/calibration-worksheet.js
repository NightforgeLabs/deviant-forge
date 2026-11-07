/* Optional, local-only recording worksheet. No game, inventory or network access. */
(function(root){
'use strict';
const VERSION=1;
const METRICS={
  trial_seconds:{label:'Trial length (seconds)',positive:true},
  pre_effect_reload_seconds:{label:'Reload before calibration and mod effects (seconds)',positive:true},
  shots_fired:{label:'Shots fired',integer:true},
  shots_landed:{label:'Shots landed',integer:true},
  body_only_hits:{label:'Body hits without crit',integer:true},
  crit_only_hits:{label:'Crit body hits',integer:true},
  weakspot_only_hits:{label:'Weakspot hits without crit',integer:true},
  crit_weakspot_hits:{label:'Crit weakspot hits',integer:true},
  body_damage:{label:'Normal body damage per hit',positive:true},
  crit_body_damage:{label:'Crit body damage per hit',positive:true},
  weakspot_damage:{label:'Weakspot damage per hit',positive:true},
  crit_weakspot_damage:{label:'Crit weakspot damage per hit',positive:true},
  power_surge_eligible_hits:{label:'Hits eligible for ordinary Power Surge',integer:true},
  power_surge_triggers:{label:'Ordinary Power Surge triggers',integer:true},
  power_surge_damage:{label:'Damage per ordinary Power Surge event',positive:true},
  orb_appearances:{label:'AUG orb appearances',integer:true},
  orb_impacts:{label:'AUG orb impacts',integer:true},
  orb_damage:{label:'Damage per AUG orb impact',positive:true},
};
const ORIGINS=['unknown','measured','assumed'];
function numberValue(value,spec){
  if(value===null||value===undefined||String(value).trim()==='')return null;
  const n=Number(value);
  if(!Number.isFinite(n)||n<0||(spec.positive&&n===0)||(spec.integer&&!Number.isInteger(n))||(spec.percent&&n>100))
    throw Error(spec.label+' must be '+(spec.integer?'a whole number':'a number')+(spec.positive?' greater than zero':' at least zero'));
  return n;
}
function entry(value,origin,spec){
  if(!ORIGINS.includes(origin))throw Error(spec.label+': choose measured, assumed or unknown');
  const n=numberValue(value,spec);
  if(n!==null&&origin==='unknown')throw Error(spec.label+': mark the entered number as measured or assumed');
  if(n===null&&origin!=='unknown')throw Error(spec.label+': enter a number or mark it unknown');
  return {value:n,origin};
}
function trial(input,id){
  const status=input.status||'not_tested';
  if(!['not_tested','tested'].includes(status))throw Error(id+': invalid trial status');
  const metrics={};for(const [key,spec] of Object.entries(METRICS)){
    const supplied=input.metrics?.[key]||{};
    metrics[key]=entry(supplied.value,supplied.origin||'unknown',spec);
  }
  const result={calibration:id,status,calibration_rolls:String(input.calibration_rolls||'').trim(),
    notes:String(input.notes||'').trim(),metrics,consistency_warnings:[],provenance_warnings:[]};
  if(status==='tested'){
    if(!result.calibration_rolls)throw Error(id+': record the exact calibration style and rolls, or write unknown');
    result.calibration_rolls_evidence=/^unknown\b/i.test(result.calibration_rolls)?'unknown':'user_entered_unverified';
    if(result.calibration_rolls_evidence==='unknown')result.provenance_warnings.push('Calibration style and rolls are unknown; this trial cannot characterize the calibration.');
    for(const key of ['trial_seconds','pre_effect_reload_seconds']){
      if(metrics[key].value===null)throw Error(id+': record '+METRICS[key].label+' for a tested trial');
    }
    if(input.reload_confirmed_pre_effect!==true)throw Error(id+': confirm reload is before calibration and mod effects');
  }
  else result.calibration_rolls_evidence=result.calibration_rolls?'user_entered_unverified':'not_tested';
  result.reload_confirmed_pre_effect=input.reload_confirmed_pre_effect===true;
  const value=key=>metrics[key].value;
  if(value('shots_fired')!==null&&value('shots_landed')!==null&&value('shots_landed')>value('shots_fired'))
    throw Error(id+': shots landed cannot exceed shots fired');
  const hits=['body_only_hits','crit_only_hits','weakspot_only_hits','crit_weakspot_hits'].map(value);
  if(value('shots_landed')!==null&&hits.filter(x=>x!==null).reduce((a,b)=>a+b,0)>value('shots_landed'))
    throw Error(id+': exclusive body/crit/weakspot groups exceed landed shots');
  if(value('power_surge_eligible_hits')!==null&&value('power_surge_triggers')!==null&&value('power_surge_triggers')>value('power_surge_eligible_hits'))
    result.consistency_warnings.push('Ordinary Power Surge triggers exceed eligible hits. Confirm which events were counted, including multi-trigger effects or changing targets; no universal one-trigger-per-hit cap is assumed.');
  return result;
}
function build(input){
  if(!input||typeof input!=='object')throw Error('Worksheet input is required');
  const context=input.context||{};
  const energy=trial(input.energy||{},'Energy'),rapid=trial(input.rapid||{},'Rapid Shot');
  if(energy.status==='tested'||rapid.status==='tested'){
    for(const key of ['scenario','patch_or_date','target','weapon','tier','blueprint_stars','gear_and_sets','mods_and_levels','tech_level_and_active_rows'])
      if(!String(context[key]||'').trim())throw Error('Record '+key.replaceAll('_',' ')+' (or write unknown) before reviewing a tested trial');
  }
  const result={schema:'deviant-forge.calibration-test',schema_version:VERSION,
    generated_at:new Date().toISOString(),storage:'download only; not saved to Forge',
    context:{scenario:String(context.scenario||'').trim(),patch_or_date:String(context.patch_or_date||'').trim(),
      target:String(context.target||'').trim(),weapon:String(context.weapon||'').trim(),
      tier:String(context.tier||'').trim(),blueprint_stars:String(context.blueprint_stars||'').trim(),
      gear_and_sets:String(context.gear_and_sets||'').trim(),mods_and_levels:String(context.mods_and_levels||'').trim(),
      tech_level_and_active_rows:String(context.tech_level_and_active_rows||'').trim(),
      ammunition:String(context.ammunition||'').trim(),buffs_and_deviant:String(context.buffs_and_deviant||'').trim(),
      target_category_bonuses:String(context.target_category_bonuses||'').trim()},
    trials:[energy,rapid],
    uncertainties:{trigger_hypotheses:{base_chance_percent:entry(input.trigger?.base_chance_percent?.value,input.trigger?.base_chance_percent?.origin||'unknown',{label:'Base Power Surge trigger chance',percent:true}),
      listed_increase_percent:entry(input.trigger?.listed_increase_percent?.value,input.trigger?.listed_increase_percent?.origin||'unknown',{label:'Listed trigger increase',percent:true}),
      note:'Relative p × (1 + r) versus percentage-point p + r are alternative hypotheses, not verified game rules. Count eligible hits and ordinary triggers separately; do not infer AUG orb count from either.'},
      all_damage_boost:{without_roll_body_hit:entry(input.all_damage?.without_roll_body_hit?.value,input.all_damage?.without_roll_body_hit?.origin||'unknown',{label:'Body hit without All DMG roll'}),
        with_roll_body_hit:entry(input.all_damage?.with_roll_body_hit?.value,input.all_damage?.with_roll_body_hit?.origin||'unknown',{label:'Body hit with All DMG roll'}),
        note:'Hold target, body-hit type, range and other buffs fixed if both states are naturally available. The All DMG bucket and its interaction with target-category bonuses remain unverified.'}},
    source_notes:[
      'Maurice Tier V five-filled-star AUG crafting preview, 2026-10-24: 241 DMG, 720 RPM, 40 MAG (libfile_b01c1d5ded9081918892fbd7b7f674b7); reference only, not a trial measurement.',
      'Energy and Rapid Shot calibration tooltip screenshots, 2026-10-24 (libfile_a52887f909c481918310b2bac02dc446; libfile_2ddcabd50f60819187d35ddc0e411389); photographed rolls are not proof of stacking order.',
      'Shock Rampage Power Surge Lv17 game tooltip, 2026-10-24 (libfile_84a17de486208191951ea249c448e8c6); core trigger text and suffix roll are distinct.',
      'Official 2025-05-21 reload note: final reload time = base reload time / (1 + Reload Efficiency bonus). Reload Speed is a separately displayed term: https://www.oncehuman.game/news/update/20250521/40780_1235763.html',
      'Official AUG field update effective 2026-05-27: https://www.oncehuman.game/news/devBlog/20260521/40781_1301130.html; proc/orb damage coefficient and inheritance remain unverified.'
    ]};
  return result;
}
function blank(){return build({});}
function readForm(form){
  const field=name=>form.elements.namedItem(name);
  const value=name=>field(name)?.value??'';
  const metric=(prefix,key)=>({value:value(prefix+'_'+key),origin:value(prefix+'_'+key+'_origin')||'unknown'});
  const readTrial=prefix=>({status:value(prefix+'_status'),calibration_rolls:value(prefix+'_rolls'),notes:value(prefix+'_notes'),
    reload_confirmed_pre_effect:!!field(prefix+'_reload_confirm')?.checked,
    metrics:Object.fromEntries(Object.keys(METRICS).map(key=>[key,metric(prefix,key)]))});
  const contextKeys=['scenario','patch_or_date','target','weapon','tier','blueprint_stars','gear_and_sets','mods_and_levels','tech_level_and_active_rows','ammunition','buffs_and_deviant','target_category_bonuses'];
  return build({context:Object.fromEntries(contextKeys.map(key=>[key,value(key)])),energy:readTrial('energy'),rapid:readTrial('rapid'),
    trigger:{base_chance_percent:metric('trigger','base_chance_percent'),listed_increase_percent:metric('trigger','listed_increase_percent')},
    all_damage:{without_roll_body_hit:metric('all_damage','without_roll_body_hit'),with_roll_body_hit:metric('all_damage','with_roll_body_hit')}});
}
function download(data,name){const blob=new Blob([JSON.stringify(data,null,2)+'\n'],{type:'application/json'}),url=URL.createObjectURL(blob);
  const link=document.createElement('a');link.href=url;link.download=name;document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function renderMetrics(){
  const keys=Object.keys(METRICS),basic=['trial_seconds','pre_effect_reload_seconds','body_damage','power_surge_triggers','orb_appearances'];
  function field(name,label){return `<div class="metric"><label for="${name}">${label}</label><input id="${name}" name="${name}" type="number" min="0" step="any" placeholder="unknown"><select name="${name}_origin" aria-label="Source of ${label}"><option value="unknown">Unknown</option><option value="measured">Measured</option><option value="assumed">Assumed</option></select></div>`;}
  for(const prefix of ['energy','rapid'])for(const part of ['basic','expert']){
    const target=document.getElementById(prefix+'-'+part);if(!target)continue;
    target.innerHTML=keys.filter(key=>part==='basic'===basic.includes(key)).map(key=>field(prefix+'_'+key,METRICS[key].label)).join('');
  }
  for(const [group,fields] of [['trigger',['base_chance_percent','listed_increase_percent']],['all_damage',['without_roll_body_hit','with_roll_body_hit']]]){
    const target=document.getElementById(group+'-metrics');if(!target)continue;
    target.innerHTML=fields.map(key=>field(group+'_'+key,key.replaceAll('_',' '))).join('');
  }
}
function init(){const form=document.getElementById('worksheet'),output=document.getElementById('worksheet-preview');if(!form||!output)return;
  renderMetrics();
  document.getElementById('preview-button').onclick=()=>{try{const data=readForm(form);output.textContent=JSON.stringify(data,null,2);output.dataset.state='ready';}catch(error){output.textContent=error.message;output.dataset.state='error'}};
  document.getElementById('export-button').onclick=()=>{try{const data=readForm(form);output.textContent='Validated. Downloading JSON; nothing was saved in Forge.';output.dataset.state='ready';download(data,'deviant-forge-calibration-test.json');}catch(error){output.textContent=error.message;output.dataset.state='error'}};
}
const api={VERSION,METRICS,entry,trial,build,blank,readForm};
if(typeof module!=='undefined'&&module.exports)module.exports=api;
root.CalibrationWorksheet=api;
if(typeof document!=='undefined')document.addEventListener('DOMContentLoaded',init);
})(typeof window!=='undefined'?window:globalThis);
