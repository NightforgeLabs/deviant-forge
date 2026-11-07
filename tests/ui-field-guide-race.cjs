const fs=require('fs'),vm=require('vm'),assert=require('assert');
const context={document:{querySelector(){return {onclick:null,innerHTML:'',value:''}},querySelectorAll(){return []}},
  window:{},fetch(){throw Error('No network expected')},setTimeout(){},console,URL,Blob};
vm.createContext(context);
vm.runInContext(fs.readFileSync('static/app.js','utf8').replace(/refresh\(\)\.catch\(fail\);\s*$/,''),context);
vm.runInContext(`state={field_guide_profiles:{personal:{reviewed_batches:[]},new_player:{reviewed_batches:[]}}};
  let selectedProfile='personal';const pending=[],errors=[];
  api=(path,data)=>new Promise((resolve,reject)=>pending.push({path,data,resolve,reject}));
  render=()=>{};val=()=>selectedProfile;fail=e=>errors.push(String(e.message||e));`,context);
async function run(){
  const personal=vm.runInContext("previewGuideRun('run')",context);
  vm.runInContext("selectedProfile='new_player';guideProfileChanged('run')",context);
  const newcomer=vm.runInContext("previewGuideRun('run')",context);
  assert.equal(vm.runInContext('pending.length',context),2);
  vm.runInContext("pending[1].resolve({profile_id:'new_player',plan_token:'new',held:[],entries:[],eligible_progressions:0})",context);
  await newcomer;
  vm.runInContext("pending[0].resolve({profile_id:'personal',plan_token:'old',held:[],entries:[],eligible_progressions:0})",context);
  await personal;
  assert.equal(vm.runInContext("guideRunReviews.run.plan.profile_id",context),'new_player');
  const html=vm.runInContext("fieldGuideReviewPane({id:'run'})",context);
  assert(html.includes('<option value="new_player" selected>'));
  assert(!html.includes('Save only these reviewed levels to personal'));
  vm.runInContext("selectedProfile='personal';guideProfileChanged('run')",context);
  const oldError=vm.runInContext("previewGuideRun('run')",context);
  vm.runInContext("selectedProfile='new_player';guideProfileChanged('run')",context);
  const fresh=vm.runInContext("previewGuideRun('run')",context);
  vm.runInContext("pending[3].resolve({profile_id:'new_player',plan_token:'fresh',held:[],entries:[],eligible_progressions:0})",context);
  await fresh;
  vm.runInContext("pending[2].reject(Error('stale Personal error'))",context);
  await oldError;
  assert.equal(vm.runInContext('errors.length',context),0,'stale error must not replace the newer profile state');
  assert.equal(vm.runInContext("guideRunReviews.run.plan.plan_token",context),'fresh');
  console.log('Field Guide profile response race passed');
}
run().catch(error=>{console.error(error);process.exitCode=1});
