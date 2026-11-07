/* Accessory collection and per-weapon attachment proposals. Catalog records are not ownership. */
const accessorySlots=[['muzzle','Muzzle'],['optic','Optic'],['tactics','Tactics'],['magazine','Magazine']];
function accessoryById(id){return (builderData?.accessories||[]).find(item=>item.id===id);}
function accessoryEffectText(item){return [item?.zoom?`Zoom ${item.zoom}×`:null,...(item?.effects||[]).map(([name,value])=>`${name} ${value>0?'+':''}${value}%`)].filter(Boolean).join(' · ');}
function characterAccessoryControls(settings,weaponId){
  const items=builderData?.accessories||[];
  const selected=settings.accessories||{};
  const options=accessorySlots.map(([slot,label])=>{
    const current=selected[slot]||'';
    const compatible=items.filter(item=>item.slot===slot&&item.compatible_weapon_ids.includes(weaponId));
    const chosen=accessoryById(current);
    return `<div class="accessory-setting"><label>${label}<select aria-label="${label} accessory" onchange="changeCharacterAccessory('${slot}',this.value)"><option value="">None</option>${compatible.map(item=>`<option value="${esc(item.id)}" ${current===item.id?'selected':''} ${!item.recorded_unlocked&&current!==item.id?'disabled':''}>${esc(item.name)}${item.recorded_unlocked?'':' · unlock unrecorded'}</option>`).join('')}</select></label>${chosen?`<small>${esc(accessoryEffectText(chosen))}${!chosen.recorded_unlocked?' · unlock record cleared; attachment retained':''}</small>`:''}${!compatible.length?'<small>No supported catalog accessory for this socket and weapon yet.</small>':''}</div>`;
  }).join('');
  return `<details class="character-calibration accessory-controls" ${Object.keys(selected).length?'open':''}><summary>Accessories${Object.keys(selected).length?' · '+Object.keys(selected).length+' attached':''}</summary><p>Attachment slots are separate from mods and calibration. Record an unlock in Accessories first; these listed effects are not added to DPS without a verified formula.</p>${options}<button type="button" class="text-button" onclick="openAccessoryCollection()">Browse accessories and record unlocks</button></details>`;
}
function changeCharacterAccessory(slot,id){
  if(!accessorySlots.some(item=>item[0]===slot)||!characterPreviewId)return;
  const item=accessoryById(id),weapon=characterPreviewId;
  if(id&&(!item||item.slot!==slot||!item.compatible_weapon_ids.includes(weapon)||!item.recorded_unlocked)){
    notice('Record a compatible accessory unlock first');return;
  }
  characterPreviewSettings??={};
  const selected={...(characterPreviewSettings.accessories||{})};
  if(id)selected[slot]=id;else delete selected[slot];
  characterPreviewSettings.accessories=selected;
  const old=document.querySelector('#characterPopover');
  if(old){old.outerHTML=characterPopoverHtml();placeCharacterPopover();document.querySelector(`#characterPopover [aria-label="${slot[0].toUpperCase()+slot.slice(1)} accessory"]`)?.focus?.({preventScroll:true});}
}
function accessoryCollectionHtml(){
  const items=builderData?.accessories||[];
  return `<section class="character-catalog accessory-collection" aria-label="Accessory collection"><div class="accessory-collection-head"><div><small>ATTACHMENT CATALOG · ${items.length} SCREENSHOT-BACKED ITEMS</small><h2>Accessories</h2><p>Record which accessories you have unlocked, then select compatible ones while editing a saved weapon. Grey means no unlock recorded here, not locked in the game. The catalog is incomplete.</p></div><button class="secondary" onclick="setCharacterPane('equipment')">← Loadout</button></div><div class="accessory-family-grid">${accessorySlots.map(([slot,label])=>`<section class="accessory-family"><h3>${label}</h3>${items.filter(item=>item.slot===slot).map(item=>`<article class="accessory-card ${esc(item.rarity)} ${item.recorded_unlocked?'recorded':'unrecorded'}"><div class="accessory-card-head"><img class="accessory-socket" src="${esc(item.artwork)}" alt="${esc(item.name)} artwork cropped from the supplied game screenshot"><div><b>${esc(item.name)}</b><small>${esc(item.rarity)} · ${esc(label)}</small></div></div><p class="accessory-effects">${esc(accessoryEffectText(item))}</p><p><b>Fits:</b> ${esc(item.compatibility)}</p><details><summary>Source and availability</summary><p>${esc(item.acquisition)}. Listed effects and compatibility come from game screenshot ${esc(item.source_ref)}. Unlock state is your manual record.</p></details><button class="${item.recorded_unlocked?'secondary':'primary'}" data-accessory-id="${esc(item.id)}" onclick="setAccessoryOwnership(this.dataset.accessoryId,${item.recorded_unlocked?'false':'true'})">${item.recorded_unlocked?'Clear unlock mark':'Record unlocked'}</button></article>`).join('')}</section>`).join('')}</div></section>`;
}
const accessoryPriorCatalogHtml=characterCatalogHtml;
characterCatalogHtml=function(){return picker?.mode==='accessory'?accessoryCollectionHtml():accessoryPriorCatalogHtml();};
function openAccessoryCollection(){
  if(typeof hideModHover==='function')hideModHover();
  modCollectionMode=false;characterPane='catalog';characterPreviewId=null;characterPreviewInventoryId=null;
  characterSlotMenuOpen=false;picker={slot:null,mode:'accessory',tab:'all'};render();
}
async function setAccessoryOwnership(id,unlocked){
  try{await api('accessory-ownership',{accessory_id:id,status:unlocked?'unlocked':'unknown'});
    builderData=await(await fetch('/api/builder-catalog')).json();render();
    notice(unlocked?'Accessory unlock recorded; no build changed':'Unlock mark cleared; saved attachments and builds retained');
  }catch(error){fail(error)}
}
