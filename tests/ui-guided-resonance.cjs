// Form contract only; the Python guided test covers the isolated API and scheduler.
const assert=require('assert'),fs=require('fs'),vm=require('vm');
const node={value:'',checked:false,innerHTML:'',classList:{contains(){return false}}};
const ctx={document:{querySelector(){return node},querySelectorAll(){return []}},
           window:{scrollTo(){}},setTimeout(){},console,fetch:async()=>({ok:true,json:async()=>({})})};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync('static/app.js','utf8').replace(/refresh\(\)\.catch\(fail\);\s*$/,''),ctx);
const form=vm.runInContext('publishedTimedControls()',ctx);
for(const name of ['resonanceCritIndices','resonanceWeakIndices','resonanceElementalIndices',
                   'resonanceElement','resonanceReserve','resonanceBaseCrit','resonanceBaseWeak'])
  assert(form.includes(`t_left_${name}`),name);
vm.runInContext("Object.assign(structuredForm,{referenceEnabled:true,timedEnabled:true,timedDuration:'0.18',t_left_resonanceCritIndices:'1',t_left_resonanceWeakIndices:'none',t_left_resonanceElementalIndices:'0',t_left_resonanceElement:'shock',t_left_resonanceReserve:'0',t_left_resonanceBaseCrit:'100',t_left_resonanceBaseWeak:'100'})",ctx);
const timed=vm.runInContext('structuredContext().published_reference.timed.left',ctx);
assert.deepEqual(JSON.parse(JSON.stringify(timed.resonance_outcomes)),{
  crit_shot_indices:[1],weakspot_shot_indices:[],elemental_shot_indices:[0],
  element:'shock',reserve_bullets:0});
assert.deepEqual(JSON.parse(JSON.stringify(timed.resonance_baseline)),{
  crit_bonus_percent:100,weakspot_bonus_percent:100});
vm.runInContext("structuredForm.t_left_resonanceWeakIndices=''",ctx);
assert.throws(()=>vm.runInContext('structuredContext()',ctx),/all three Resonance/);
vm.runInContext("Object.assign(structuredForm,{t_left_resonanceWeakIndices:'none',t_left_sourceMode:'timeline',t_left_sourceReserve:'3'})",ctx);
assert.throws(()=>vm.runInContext('structuredContext()',ctx),/reserve rounds disagree/);
console.log('Guided Resonance form controls, explicit outcomes, baseline and missing-input gate passed');
