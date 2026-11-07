const fs=require('fs'),assert=require('assert');
const css=fs.readFileSync('static/style.css','utf8');
const js=fs.readFileSync('static/builder-character.js','utf8');
const app=fs.readFileSync('static/app.js','utf8');
assert(css.includes('@media(max-width:1000px){.shell{grid-template-columns:minmax(0,1fr)}'),'Narrow shell must release the fixed sidebar column');
assert(css.includes('.shell>aside nav{display:flex;gap:4px;min-width:0;overflow-x:auto;scrollbar-width:thin}'),'All navigation destinations must remain reachable on narrow layouts');
assert(css.includes('.forge-screen .mod-family[data-mod-slot="mask_mod"] .mod-family-cards{grid-template-columns:repeat(5,minmax(0,1fr))}'),'Weapon and source-verified Mask family rows must retain five cards');
assert(css.includes('.forge-screen .mod-family[data-mod-slot="gloves_mod"] .mod-family-cards{grid-template-columns:repeat(6,minmax(0,1fr))}'),'Source-verified Gloves and other armor rows must use six cards at desktop width');
assert(css.includes('.forge-screen .mod-family-name{align-self:stretch}'),'Family identity must span the full wrapped variant group');
for(const token of [
  'body.builder-mode{height:100dvh;overflow:hidden}',
  'body.builder-mode .shell,body.builder-mode main,body.builder-mode #view{height:100dvh;min-height:0;overflow:hidden}',
  'body.builder-mode #notice{position:fixed;',
  '.forge-screen{height:100dvh;min-height:0;overflow:hidden;display:grid;grid-template-rows:56px minmax(0,1fr) 42px}',
  '.forge-screen .character-layout{height:auto;min-height:0;overflow:hidden;',
  '.forge-screen .character-catalog{display:grid;grid-template-rows:auto minmax(0,1fr) clamp(192px,25dvh,240px);height:100%;min-height:0;overflow:hidden}',
  '.forge-screen .character-results{min-height:0;overflow-y:auto;overflow-x:hidden;',
  '.forge-screen .character-detail-dock{height:auto;min-height:0;overflow:hidden}',
  '.forge-screen .character-summary-content{position:absolute;bottom:100%;',
  '.forge-screen .show-equipment .character-catalog,.forge-screen .show-catalog .character-left{display:none}'
]) assert(css.includes(token),`Missing fixed-viewport rule: ${token}`);
assert(!/scrollIntoView\?\.\(\{behavior:"smooth",block:"start"\}\)/.test(fs.readFileSync('static/builder-workflow.js','utf8')));
assert(app.includes("results.scrollTop=previousPosition"),'Catalog scroll must survive updates');
assert(js.includes('character-view-switch')&&js.includes('setCharacterPane'),'Narrow Equipment/Catalog switch missing');
assert(js.includes('<button onclick="go(\'map\')">Abyss guide</button>'),'Guide must be visible in primary Build navigation');
assert(css.includes('.forge-screen .character-main-nav{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));grid-auto-rows:32px;height:64px}'),'Four primary routes must fit a readable two-row narrow navigation');
assert(js.indexOf('id="characterResults"')<js.indexOf('id="characterPreview"'));
for(const slot of ['helmet','mask','top','gloves','bottoms','shoes'])assert(js.includes(`characterRegion('${slot}'`));
assert(js.includes("['primary','secondary','melee'].map(characterEquipmentCard)"));
for(const [width,height] of [[1280,720],[1440,900],[2596,1296],[3440,1350]]){
  const screen=Math.min(width,2400),left=screen*(width<=1350 ? .51 : .52),right=screen-left;
  const workspace=height-56-42,weapon=height<=760?92:112,stage=workspace-weapon;
  const dock=height<=760?210:Math.min(240,Math.max(192,.25*height));
  const catalogTop=width<=1350?135:120,results=workspace-catalogTop-dock;
  const columns=screen>=2100?4:3,card=(right-44-(columns-1)*10)/columns;
  assert(workspace>0&&stage>0&&results>=200,`Viewport cannot hold builder at ${width}×${height}`);
  assert(left>=600&&right>=600&&card>=175,`Catalog or equipment too narrow at ${width}×${height}`);
  assert(Math.min(left*.75,stage*.66667)*1.5<=stage+.02,'Soldier must fit stage');
  console.log(`${width}×${height}: ${workspace}px workspace, ${stage}px soldier stage, ${Math.round(results)}px catalog results, ${columns} × ${Math.round(card)}px cards`);
}
console.log('Viewport structure checks passed; DOM overflow still requires rendered verification');
