#!/usr/bin/env python3
"""Build an attributed, versioned local catalog from a pinned Apache-2.0 snapshot."""
import json, re, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
COMMIT='d6b1d5b99f84cb6ddc6b8f85144ee067af2a4e45'
BASE=f'https://raw.githubusercontent.com/lReDragol/OnceHuman_Tools/{COMMIT}/data/menu/calc/bd_json/'
SLOT={'mod_helmet':'helmet_mod','mod_mask':'mask_mod','mod_top':'chest_mod','mod_gloves':'gloves_mod','mod_pants':'pants_mod','mod_weapon':'weapon_mod','mod_boots':'boots_mod','helmet':'helmet','mask':'mask','top':'chest','gloves':'gloves','pants':'pants','boots':'boots'}
VARIANTS=sorted(('Downstar Deviant Energy','Resonance Deviant Energy','Crescent Deviant Energy','Lunar Deviant Energy','Mirror Deviant Energy','Wild Deviant Energy','Phantasmal Deviant Energy','Aero Deviant Energy','Power Surge','Unstable Bomber','Frost Vortex','Shrapnel','Burn','Bounce','Fast Gunner','Fortress Warfare','Deviant Energy','Downstar','Resonance','Crescent','Lunar','Mirror','Wild','Phantasmal','Aero','General','Violent','Precision','Survival','Battle'),key=len,reverse=True)
OFFICIAL_LEVEL_PROFILE={1:[1,0,0,0],2:[1,1,0,0],3:[1,1,1,0],4:[1,1,1,1],5:[2,1,1,1],6:[2,2,1,1],7:[2,2,2,1],8:[2,2,2,2],9:[3,2,2,2],10:[3,3,2,2],11:[3,3,3,2],12:[4,3,3,2],13:[4,4,3,2],14:[4,4,4,2],15:[5,4,4,2],16:[5,5,4,2],17:[5,5,5,2]}

def fetch(name):
 req=urllib.request.Request(BASE+name+'.json',headers={'User-Agent':'OnceHumanAdvisor/1 local catalog builder'})
 with urllib.request.urlopen(req,timeout=30) as response:return json.load(response)
def slug(s):return re.sub(r'[^a-z0-9]+','-',s.lower()).strip('-')
def split_mod_name(name):
 for variant in VARIANTS:
  if name.lower().endswith(' '+variant.lower()):return name[:-(len(variant)+1)],variant
 return name,None
def activations(effects):
 out=[]
 for effect in effects:
  if effect.get('event'):out.append({'type':'event','value':effect['event']})
  if effect.get('stack_source'):out.append({'type':'stack_source','value':effect['stack_source']})
  out.extend(activations(effect.get('effects') or []))
 return out

def build():
 raw_mods=fetch('mods_config');weapons=fetch('weapon_list')['weapons'];armor=fetch('items_and_sets')
 mods=[]
 for tree,entries in raw_mods.items():
  for entry in entries:
   name,variant=split_mod_name(entry['name'])
   slot=SLOT[tree]
   effects=entry.get('effects') or [];description=entry.get('description') or ''
   simple_weapon=bool(re.fullmatch(r'\s*Weapon DMG\s*\+\s*\d+(?:\.\d+)?%\s*',description,re.I))
   mods.append({'id':'mod:'+slot+':'+slug(entry['name']),'kind':'mod','name':name,'display_name':entry['name'],'slot':slot,'tree':entry.get('category') or name,'variant':variant,'rarity':entry.get('rarity'),'valid_levels':[1,17],'level_availability':'Entry-specific drop levels unverified; official Field Guide uses Lv. 1–17.','primary_effect':description or None,'structured_effects':effects,'effect_parse_complete':simple_weapon,'activation_conditions':activations(effects),'stacking_rule':'unknown unless fully specified by a current official rule','effect_scope':'main effect only; activation and stacking may be incomplete','attribute_names':None,'attribute_values_by_level':{},'variable_fields':['shiny transformation','scenario-dependent availability'],'acquisition':{'method':'dungeon/game mode or Mod Dust crate','exact_entry_path':None,'source':'official_mods'},'image_url':None,'source_url':entry.get('source_url'),'data_status':'community snapshot; requires current tooltip check','source':'community_catalog'})
 catalog={'schema_version':1,'catalog_version':'2026-10-22','source_snapshot':{'repository':'https://github.com/lReDragol/OnceHuman_Tools','commit':COMMIT,'license':'Apache-2.0','source_date':'2026-03-19','status':'corroborated community data; later game changes may supersede it'},'official_rules':{'mod_levels':{'valid':[1,17],'ordered_subattribute_tiers':{str(k):v for k,v in OFFICIAL_LEVEL_PROFILE.items()},'source':'https://www.oncehuman.game/news/devBlog/20251212/40781_1276354.html','note':'Tier positions are known; values and attribute identity for a specific mod/variant are not inferred from level alone.'},'mod_unlock':{'rule':'Field Guide entry unlocks when obtained; highest-level entry is equippable. Old mods may remain separately usable.','source':'https://www.oncehuman.game/news/devBlog/20251212/40781_1276354.html'},'mod_drop_levels':{'normal':[1,12],'hard':[7,15],'master':[8,17],'nightmare':[9,17],'nightmare_first_clear':[12,17],'source':'https://www.oncehuman.game/news/devBlog/20260123/40781_1283429.html','scope':'Dungeon Mod Crate level ranges; does not establish a specific mod drop location or chance.'}},'mods':mods,'weapons':[],'armor':[],'sets':[]}
 for w in weapons:
  catalog['weapons'].append({'id':'weapon:'+slug(w['name']),'kind':'weapon','name':w['name'],'family':w.get('type'),'slot':'primary','rarity':w.get('rarity'),'effect':(w.get('mechanics') or {}).get('description'),'structured_effects':(w.get('mechanics') or {}).get('effects') or [],'historical_base_stats':w.get('base_stats'),'acquisition':{'blueprint_fragment_type':w.get('blueprint_fragment_type'),'exact_path':None},'source':'community_catalog','data_status':'March 2026 snapshot; current damage values not assumed'})
 for a in armor['items']:
  catalog['armor'].append({'id':'armor:'+slug(a['name']),'kind':'armor','name':a['name'],'slot':SLOT.get(a.get('type'),a.get('type')),'rarity':a.get('rarity'),'set_id':a.get('set_id'),'historical_base_stat_hint':a.get('base_stat_hint'),'source_url':a.get('source_url'),'source':'community_catalog','data_status':'March 2026 snapshot; current stats not assumed'})
 for s in armor['sets']:
  catalog['sets'].append({'id':'set:'+slug(s['name']),'kind':'set','name':s['name'],'rarity':s.get('rarity'),'bonuses':s.get('bonuses',[]),'source':'community_catalog','data_status':'March 2026 snapshot; verify current bonuses'})
 # Official later additions are metadata until complete current per-item stats are known.
 official=json.loads((ROOT/'knowledge.json').read_text())
 for item in official['catalog']:
  if item['name'].lower().endswith('suffix mod'):continue
  target=catalog['weapons'] if item['slot']=='primary' else catalog['armor']
  if any(x['name'].lower()==item['name'].lower() for x in target):continue
  target.append({'id':('weapon:' if target is catalog['weapons'] else 'armor:')+slug(item['name']),'kind':'weapon' if target is catalog['weapons'] else 'armor','name':item['name'],'slot':item['slot'],'family':item['family'],'structured_effects':[],'acquisition':item.get('acquisition'),'source':item['source'],'data_status':item['status']+'; numeric details incomplete'})
 (ROOT/'catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n')
 print('mods',len(catalog['mods']),'weapons',len(catalog['weapons']),'armor',len(catalog['armor']),'sets',len(catalog['sets']))
if __name__=='__main__':build()
