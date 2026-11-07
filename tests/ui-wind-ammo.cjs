const assert=require('assert'),fs=require('fs'),vm=require('vm');
const source=fs.readFileSync('static/app.js','utf8');
const form={t_left_sourceReserve:'0',t_left_sourceTarget:'dummy',
  t_left_sourceReloadAfter:'1',t_left_windAmmoScenario:'created_after_reload'};
const context={structuredForm:form,structuredSides:{left:{}},
  structuredNumber:(key)=>form[key]===undefined||form[key]===''?null:Number(form[key]),
  structuredInput:(key,label)=>`<label>${label}<input id="sc_${key}"></label>`,
  esc:x=>String(x)};
vm.createContext(context);
const fieldsStart=source.indexOf('function publishedSourceTimelineFields');
const fieldsEnd=source.indexOf('\nlet state',fieldsStart+1);
vm.runInContext(source.slice(0,source.indexOf('\nfunction ',1))+source.slice(fieldsStart,fieldsEnd),context);
const choice=vm.runInContext("publishedSourceChoice('left',null)",context);
assert.equal(choice.wind_ammo_scenario,'created_after_reload');
assert.equal(choice.reserve_bullets,0);
assert.equal(choice.reload_after_shots,1);
const html=vm.runInContext("publishedSourceTimelineFields('left')",context);
for(const name of ['created_after_reload','reserve_transfer_after_reload',
                   'not_retained_during_reload'])assert(html.includes(name));
assert(html.includes('Wind Cap bullet'));
assert(source.includes("'sourceReloadAfter','windAmmoScenario'"));
assert(source.includes('row.unique_armor?.selected'));
console.log('Wind Cap scenario selection and modeled-result labeling passed');
