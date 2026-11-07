const assert=require('assert');
const fs=require('fs');
const worksheet=require('../static/calibration-worksheet.js');
const context={scenario:'Isles of Abyss PvE',patch_or_date:'2026-10-25',target:'example boss',weapon:'AUG Electron Cloud',tier:'V',blueprint_stars:'5',gear_and_sets:'Mayfly / 3 Savior / 2 Shelterer',mods_and_levels:'Shock Rampage Power Surge Lv17',tech_level_and_active_rows:'unknown'};
const energy={status:'tested',calibration_rolls:'Energy Style; values from this test only',reload_confirmed_pre_effect:true,
  metrics:{trial_seconds:{value:'60',origin:'measured'},pre_effect_reload_seconds:{value:'2',origin:'measured'},
           shots_fired:{value:'720',origin:'measured'},shots_landed:{value:'600',origin:'measured'},
           body_only_hits:{value:'300',origin:'measured'},crit_only_hits:{value:'100',origin:'measured'},
           weakspot_only_hits:{value:'100',origin:'measured'},crit_weakspot_hits:{value:'50',origin:'measured'},
           power_surge_triggers:{value:'12',origin:'measured'},orb_appearances:{value:'5',origin:'assumed'}}};
const sample=()=>({context,energy,rapid:{status:'not_tested'}});
const blank=worksheet.blank();
const servedBlank=JSON.parse(fs.readFileSync('static/calibration-worksheet-blank.json','utf8'));
assert.deepStrictEqual(servedBlank,{...blank,generated_at:null},'same-origin blank download stays in sync with the worksheet schema');
assert.equal(blank.schema_version,1);
assert.equal(blank.trials[0].metrics.trial_seconds.value,null,'blank is unknown, not zero');
assert.equal(blank.trials[1].status,'not_tested');
assert.equal(blank.storage,'download only; not saved to Forge');
const data=worksheet.build(sample());
assert.equal(data.trials[0].metrics.trial_seconds.value,60);
assert.equal(data.trials[0].calibration_rolls_evidence,'user_entered_unverified');
assert.equal(data.trials[0].metrics.orb_appearances.origin,'assumed');
assert.equal(data.trials[1].metrics.body_damage.value,null);
assert(data.uncertainties.trigger_hypotheses.note.includes('p × (1 + r)'));
assert(data.uncertainties.all_damage_boost.note.includes('target-category'));
assert(data.source_notes.some(x=>x.includes('2026-05-27')));
assert.equal(JSON.parse(JSON.stringify(data)).trials[0].metrics.power_surge_triggers.value,12,'download representation round trips');
assert.throws(()=>worksheet.build({...sample(),energy:{...energy,reload_confirmed_pre_effect:false}}),/confirm reload/);
assert.throws(()=>worksheet.build({...sample(),energy:{...energy,calibration_rolls:''}}),/exact calibration style and rolls, or write unknown/);
const unknownRoll=worksheet.build({...sample(),energy:{...energy,calibration_rolls:'unknown'}}).trials[0];
assert.equal(unknownRoll.calibration_rolls_evidence,'unknown');
assert(unknownRoll.provenance_warnings.some(x=>x.includes('cannot characterize')),'unknown roll must remain visibly incomplete');
assert.throws(()=>worksheet.build({...sample(),context:{...context,tech_level_and_active_rows:''}}),/tech level/);
assert.throws(()=>worksheet.build({...sample(),energy:{...energy,metrics:{...energy.metrics,shots_landed:{value:721,origin:'measured'}}}}),/cannot exceed/);
assert.throws(()=>worksheet.build({...sample(),energy:{...energy,metrics:{...energy.metrics,shots_landed:{value:5,origin:'measured'},body_only_hits:{value:6,origin:'measured'},crit_only_hits:{value:null,origin:'unknown'},weakspot_only_hits:{value:null,origin:'unknown'},crit_weakspot_hits:{value:null,origin:'unknown'}}}}),/groups exceed landed shots/,'partial known groups cannot exceed landed shots');
const manyTriggers=worksheet.build({...sample(),energy:{...energy,metrics:{...energy.metrics,power_surge_eligible_hits:{value:4,origin:'measured'},power_surge_triggers:{value:9,origin:'measured'}}}}).trials[0];
assert(manyTriggers.consistency_warnings.some(x=>x.includes('exceed eligible hits')),'possible multi-trigger case needs a warning, not a fabricated hard cap');
assert.throws(()=>worksheet.build({...sample(),energy:{...energy,metrics:{...energy.metrics,shots_fired:{value:1.5,origin:'measured'}}}}),/whole number/);
assert.throws(()=>worksheet.build({...sample(),energy:{...energy,metrics:{...energy.metrics,trial_seconds:{value:60,origin:'unknown'}}}}),/mark the entered number/);
assert.throws(()=>worksheet.build({...sample(),trigger:{base_chance_percent:{value:101,origin:'assumed'}}}),/outside|number/);
const observedZero=worksheet.build({...sample(),energy:{...energy,metrics:{...energy.metrics,orb_appearances:{value:0,origin:'measured'}}}});
assert.equal(observedZero.trials[0].metrics.orb_appearances.value,0,'observed zero remains distinct from unknown');
console.log('Calibration worksheet schema passed: blank/filled export, origin, reload, context and count validation');
