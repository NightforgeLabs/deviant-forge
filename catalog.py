"""Versioned game catalog, distinct from account sightings and inventory."""
import json,re
from difflib import SequenceMatcher
from pathlib import Path

DATA=json.loads(Path(__file__).with_name('catalog.json').read_text())
CURRENT=json.loads(Path(__file__).with_name('catalog_current.json').read_text())
DETAILS=json.loads(Path(__file__).with_name('catalog_details.json').read_text())
NUMERIC=json.loads(Path(__file__).with_name('catalog_numeric.json').read_text())
SYSTEMS=json.loads(Path(__file__).with_name('catalog_systems.json').read_text())
_magnitudes_path=Path(__file__).with_name('catalog_effect_magnitudes.json')
MAGNITUDES=json.loads(_magnitudes_path.read_text()) if _magnitudes_path.exists() else {'entries':{},'identities_with_numeric_candidates':0,'candidate_rows':0}
_reviewed_path=Path(__file__).with_name('catalog_reviewed_profiles.json')
REVIEWED=json.loads(_reviewed_path.read_text()) if _reviewed_path.exists() else {'entries':{},'conflicts':[]}
_held_path=Path(__file__).with_name('catalog_held_profiles.json')
HELD=json.loads(_held_path.read_text()) if _held_path.exists() else {'entries':{}}
_suffix_held_path=Path(__file__).with_name('catalog_held_suffix_profiles.json')
SUFFIX_HELD=json.loads(_suffix_held_path.read_text()) if _suffix_held_path.exists() else {'entries':{}}
_observed_groups=(REVIEWED['entries'],HELD['entries'],SUFFIX_HELD['entries'])
if sum(map(len,_observed_groups))!=len(set().union(*(set(group) for group in _observed_groups))):
    raise ValueError('Direct observation profile duplicates existing exact profile')
OBSERVED={**REVIEWED['entries'], **HELD['entries'], **SUFFIX_HELD['entries']}
REVIEWED_LEVELS={}
for _observed in OBSERVED.values():
    REVIEWED_LEVELS.setdefault(_observed['catalog_id'],set()).add(_observed['level'])
OBSERVED_ATTRIBUTE_NAMES={
    'power_surge_damage_percent':'Power Surge DMG',
    'power_surge_trigger_chance_percent':'Power Surge Trigger Chance',
    'shock_damage_percent':'Shock DMG',
    'elemental_damage_percent':'Elemental DMG',
    'status_damage_percent':'Status DMG',
    'magazine_capacity_percent':'Magazine Capacity',
    'all_damage_boost_percent':'All DMG Boost',
    'weapon_damage_percent':'Weapon DMG',
    'weakspot_damage_percent':'Weakspot DMG',
    'crit_damage_percent':'Crit DMG',
    'max_hp_percent':'Max HP',
    'generic_damage_percent':'DMG',
    'reload_efficiency_percent':'Reload Efficiency',
    'after_hit_damage_reduction_percent':'Damage reduction after hitting',
    'after_damage_reduction_percent':'Damage reduction after taking damage',
    'metas_kill_heal_percent':'HP recovered after defeating Metas',
    'monster_damage_direction_ambiguous':'Damage from monsters received',
    'deviant_damage_reduction_percent':'Damage reduction against Deviants',
}
SLOTS={'Weapon':'weapon_mod','All Weapons':'weapon_mod','Helmet':'helmet_mod','Mask':'mask_mod','Top':'chest_mod','Gloves':'gloves_mod','Bottoms':'pants_mod','Shoes':'boots_mod'}
def _key(name,variant,slot):
    return (re.sub(r'[^a-z0-9]+',' ',str(name or '').lower()).strip(),re.sub(r'[^a-z0-9]+',' ',str(variant or '').lower()).strip(),slot)
by_key={_key(x['name'],x.get('variant'),x['slot']):x for x in DATA['mods']}
by_display={(re.sub(r'[^a-z0-9]+',' ',str(x.get('display_name') or x['name']).lower()).strip(),x['slot']):x for x in DATA['mods']}
for row in CURRENT['records']:
    slot=SLOTS.get(row['modType'])
    if not slot:continue
    key=_key(row['name'],row['variant'],slot)
    entry=by_key.get(key) or by_display.get((re.sub(r'[^a-z0-9]+',' ',(row['name']+' '+row['variant']).lower()).strip(),slot))
    if entry is None:
        new_id='mod:'+slot+':'+re.sub(r'[^a-z0-9]+','-',row['name'].lower()+' '+row['variant'].lower()).strip('-')
        entry={'id':new_id,'kind':'mod','name':row['name'],'display_name':row['name']+' '+row['variant'],'slot':slot,'tree':row['name'],'variant':row['variant'],'rarity':row.get('rarity'),'valid_levels':[1,17],'level_availability':'Entry-specific obtainable levels unverified; official Field Guide system spans Lv. 1–17.','primary_effect':row.get('coreEffect'),'structured_effects':[],'effect_parse_complete':False,'activation_conditions':[],'stacking_rule':'unknown','effect_scope':'current community effect text; calculation semantics unverified','attribute_names':None,'attribute_values_by_level':{},'variable_fields':['shiny transformation','scenario-dependent availability'],'acquisition':{'method':'dungeon/game mode or Mod Dust crate','exact_entry_path':None,'source':'official_mods'},'image_url':row.get('imageUrl'),'source_url':CURRENT['source'].rstrip('/')+'/'+row['slug'],'source':'current_community_catalog','data_status':'community page snapshot '+CURRENT['retrieved_utc'][:10]+'; verify current tooltip'}
        DATA['mods'].append(entry);by_key[key]=entry
    elif entry.get('variant') is None:
        entry['name']=row['name'];entry['variant']=row['variant'];by_key[key]=entry
    entry.setdefault('current_records',[]).append({'slug':row['slug'],'image_url':row.get('imageUrl'),'core_effect':row.get('coreEffect')})
    detail=DETAILS['records'].get(row['slug'],{})
    if detail.get('effect_variants'):
        entry.setdefault('detail_effect_variants',[])
        for description in detail['effect_variants']:
            if description not in entry['detail_effect_variants']:entry['detail_effect_variants'].append(description)
        entry.setdefault('detail_source_urls',[])
        if detail['source_url'] not in entry['detail_source_urls']:entry['detail_source_urls'].append(detail['source_url'])
        if not entry.get('primary_effect') and len(detail['effect_variants'])==1:entry['primary_effect']=detail['effect_variants'][0]
    if not entry.get('image_url') and row.get('imageUrl'):entry['image_url']=row['imageUrl']
    if not entry.get('primary_effect') and row.get('coreEffect'):entry['primary_effect']=row['coreEffect']
    if entry.get('primary_effect') and row.get('coreEffect') and re.sub(r'\s+',' ',entry['primary_effect']).strip()!=re.sub(r'\s+',' ',row['coreEffect']).strip():entry['effect_text_conflict']=True
# Screenshot-confirmed current Helmet identities missing from the older community snapshot.
DATA['mods'].extend(json.loads(Path(__file__).with_name('helmet_screenshot_catalog.json').read_text())['entries'])
# The 2026-10-25 scrolling game video establishes selected family and variant
# identities/positions. These catalog sightings never establish current ownership
# or supply uninspected effects and rolls.
DATA['mods'].extend(json.loads(Path(__file__).with_name('game_video_mod_catalog.json').read_text())['entries'])
DATA['mods'].extend(json.loads(Path(__file__).with_name('helmet_video_mod_catalog.json').read_text())['entries'])
ENTRIES={entry['id']:entry for group in ('mods','weapons','armor','sets') for entry in DATA[group]}
OVERRIDES=json.loads(Path(__file__).with_name('catalog_overrides.json').read_text())
for catalog_id,fields in OVERRIDES.items():
    if catalog_id not in ENTRIES:raise ValueError('Catalog override has unknown entry: '+catalog_id)
    ENTRIES[catalog_id].update(fields)
system_lookup={}
for record in SYSTEMS['records']:
    slot=SLOTS.get(record['apply_range_desc'])
    if slot:system_lookup.setdefault((normalized_name:=re.sub(r'[^a-z0-9]+',' ',record['name'].lower()).strip(),slot),[]).append(record)
for entry in DATA['mods']:
    key=(re.sub(r'[^a-z0-9]+',' ',str(entry.get('display_name') or entry['name']).lower()).strip(),entry['slot'])
    variants=system_lookup.get(key,[])
    entry['catalog_system_records']=[{'item_id':r['item_id'],'system':r['system'],'is_shiny':r['is_shiny'],'source':r.get('source',SYSTEMS['source'])} for r in variants]
    systems={r['system'] for r in variants}
    entry['system_generation']='current_field_guide' if systems=={'new'} else 'legacy_random_roll' if systems=={'legacy'} else 'mixed_or_unverified'
    entry['shiny_available_in_secondary_catalog']=any(r['is_shiny'] for r in variants)
TIER_EVIDENCE={}
NUMERIC_CONFLICTS=[]
SEMANTIC_FIELDS=('name','unit','direction','condition','conditional_bonus_percent','activation','stacking','applies_to')
def _semantic_record(attribute):
    """A shared value carries its full meaning, including absent vs present cues."""
    return {field:attribute.get(field) for field in SEMANTIC_FIELDS if field in attribute}

def _semantic_signature(attribute):
    return json.dumps(_semantic_record(attribute),sort_keys=True)

def reconcile_tier_evidence(evidence):
    """Promote only compatible observations from distinct identities."""
    if not evidence:return None,None
    signatures={(row['value_percent'],json.dumps(_semantic_record(row),sort_keys=True)) for row in evidence}
    if len(signatures)>1:
        return None,{'reason':'numeric or semantic conflict','evidence':evidence}
    if len({row['catalog_id'] for row in evidence})<2:return None,None
    first=evidence[0]
    return {**_semantic_record(first),'value_percent':first['value_percent'],'evidence_sources':list(dict.fromkeys(row['source'] for row in evidence)),'validated_entries':sorted({row['catalog_id'] for row in evidence}),'source':'validated across current Field Guide frames'},None

for catalog_id,levels in NUMERIC['profiles'].items():
    if catalog_id not in ENTRIES:raise ValueError('Numeric profile has unknown entry: '+catalog_id)
    entry=ENTRIES[catalog_id]
    for level,profile in levels.items():
        evidence_source=profile.get('source_image') or profile.get('source_url')
        names=[a['name'] for a in profile['attributes']]
        if entry.get('attribute_names') is None:
            entry['attribute_names']=names
            entry['attribute_name_source']=evidence_source
            entry['attribute_name_status']='visually checked current Field Guide frame'
        elif [re.sub(r' \(aerial bonus\)$','',n) for n in entry['attribute_names']]!=names:
            raise ValueError('Numeric profile conflicts with ordered attribute names: '+catalog_id)
        tiers=DATA['official_rules']['mod_levels']['ordered_subattribute_tiers'][level]
        if len(names)!=4:raise ValueError('Expected four ordered attributes: '+catalog_id)
        entry.setdefault('attribute_tier_values',{})
        for name,tier,attribute in zip(names,tiers,profile['attributes']):
            observation={**attribute,'unit':attribute.get('unit','percent'),'direction':attribute.get('direction','increase'),'tier':tier,'source':evidence_source,'source_status':profile.get('source_status','visually checked current Field Guide frame'),'observed_level':int(level)}
            tier_values=entry['attribute_tier_values'].setdefault(name,{})
            previous=tier_values.get(str(tier))
            if previous and (previous['value_percent']!=observation['value_percent'] or _semantic_record(previous)!=_semantic_record(observation)):
                conflict={'catalog_id':catalog_id,'name':name,'tier':tier,'evidence':[previous,observation]}
                NUMERIC_CONFLICTS.append(conflict)
                entry.setdefault('attribute_tier_conflicts',[]).append(conflict)
                tier_values[str(tier)]=None
            elif str(tier) not in tier_values:tier_values[str(tier)]=observation
            TIER_EVIDENCE.setdefault((name,tier,_semantic_signature(observation)),[]).append({'catalog_id':catalog_id,**observation})
SHARED_TIERS={}
SHARED_CONFLICTS={}
for key,evidence in TIER_EVIDENCE.items():
    shared,conflict=reconcile_tier_evidence(evidence)
    if shared:SHARED_TIERS[key]=shared
    if conflict:SHARED_CONFLICTS[key]=conflict
SUFFIXES=json.loads(Path(__file__).with_name('catalog_suffixes.json').read_text())
for entry in DATA['mods']:
    rule=SUFFIXES['rules'].get(entry.get('variant'))
    if rule:
        entry['structured_suffix_effects']=[{'type':'conditional_stat','stat':stat,'condition':rule['condition'],'value':None,'source':rule.get('source',SUFFIXES['source'])} for stat in rule['effects']]

def normalized(value):
    return re.sub(r'[^a-z0-9]+',' ',str(value or '').lower().replace('b.p.',' ')).strip()

def matching(text,kind=None,slot=None,minimum=.82):
    """Conservative OCR title match; close alternatives stay in review."""
    text=re.sub(r'(<[^>\n]{1,50})\n\s*([^>\n]{1,40}>)',r'\1 \2',str(text or ''))
    lines=[normalized(line) for line in str(text or '').splitlines() if len(normalized(line))>=5]
    pool=[e for e in ENTRIES.values() if (kind is None or e['kind']==kind) and (slot is None or e.get('slot')==slot)]
    exact=[e for e in pool if normalized(e.get('display_name') or e['name']) in lines]
    if exact:
        longest=max(len(normalized(e.get('display_name') or e['name'])) for e in exact)
        exact=[e for e in exact if len(normalized(e.get('display_name') or e['name']))==longest]
        if len(exact)==1:
            e=exact[0]
            return {'status':'matched','id':e['id'],'confidence':1.0,'candidates':[{'id':e['id'],'name':e.get('display_name') or e['name'],'score':1.0}]}
    scored=[]
    for entry in pool:
        target=normalized(entry.get('display_name') or entry['name'])
        if not target:continue
        score=max((1.0 if target==line else SequenceMatcher(None,target,line).ratio() if abs(len(target)-len(line))<25 else 0) for line in lines) if lines else 0
        if score>=minimum:scored.append((round(score,3),entry))
    scored.sort(key=lambda pair:(pair[0],len(pair[1].get('display_name') or pair[1]['name'])),reverse=True)
    if not scored:return {'status':'no_match','candidates':[]}
    best=scored[0]
    runner=scored[1][0] if len(scored)>1 else 0
    if best[0]-runner<.08:return {'status':'ambiguous','candidates':[{'id':e['id'],'name':e.get('display_name') or e['name'],'score':s} for s,e in scored[:5]]}
    return {'status':'matched','id':best[1]['id'],'confidence':best[0],'candidates':[{'id':best[1]['id'],'name':best[1].get('display_name') or best[1]['name'],'score':best[0]}]}

def resolve(catalog_id,level=None,system='current_field_guide',shiny=False):
    entry=ENTRIES.get(catalog_id)
    if not entry:raise ValueError('Unknown catalog entry')
    result={'entry':entry,'known_effects':(entry.get('structured_effects') or [])+(entry.get('structured_suffix_effects') or []),'primary_effect':entry.get('primary_effect') or entry.get('effect'),'verified_main_effect':None,'verified_shiny_main_effect':None,'effect_candidates':entry.get('detail_effect_variants') or [],'effect_magnitude_candidates':MAGNITUDES['entries'].get(catalog_id,[]),'level':level,'system':system,'shiny':shiny,'shiny_acquisition':None,'level_profile':None,'known_attribute_names':entry.get('attribute_names'),'attribute_tiers':None,'known_attributes':None,'possible_crate_difficulties':None,'unknowns':[]}
    if entry['kind']=='mod':
        if entry.get('source_observed_level'):
            result['unknowns'].append('A level badge was seen in the supplied game recording; this does not establish current ownership or an owned instance level.')
            if not result['primary_effect']:
                result['unknowns'].append('This variant\'s current core effect was not inspected in the recording.')
        if system not in ('current_field_guide','legacy_random_roll'):raise ValueError('Unknown mod system')
        if system=='legacy_random_roll':
            result['known_attribute_names']=None
            result['unknowns'].append('Legacy backpack mod sub-attributes are instance-specific; inspect this actual item.')
            return result
        if shiny:
            if level!=17:raise ValueError('Shiny Field Guide mod requires level 17')
            result['shiny_acquisition']={'paths':['duplicate Lv. 17 transformation chance','Scenario Honor Rating reward','Mod Collection Progress reward'],'entry_specific_eligibility':'unverified','source':'https://www.oncehuman.game/news/update/20260709/40780_1307147.html'}
            if not ((NUMERIC['profiles'].get(catalog_id) or {}).get('17') or {}).get('verified_shiny_main_effect'):
                result['unknowns'].append('Shiny main-effect increase is not numerically cataloged for this entry.')
        if not result['primary_effect'] and result['effect_candidates']:result['unknowns'].append('Detail page supplies effect-level descriptions, but their mapping to this Field Guide level is unresolved.')
        if entry.get('effect_text_conflict'):result['unknowns'].append('Pinned and current community descriptions differ; verify the current in-game tooltip.')
        if level is None:result['unknowns'].append('Mod level was not identified.')
        elif not isinstance(level,int) or not 1<=level<=17:raise ValueError('Mod level must be 1–17')
        else:
            result['level_profile']=DATA['official_rules']['mod_levels']['ordered_subattribute_tiers'][str(level)]
            photographed=(NUMERIC['profiles'].get(catalog_id) or {}).get(str(level)) or {}
            if shiny and photographed.get('verified_shiny_main_effect'):
                result['verified_shiny_main_effect']=photographed['verified_shiny_main_effect']
            verified_main=photographed.get('verified_main_effect')
            if verified_main:
                if result['primary_effect'] and re.sub(r'\s+',' ',verified_main['text']).strip()!=re.sub(r'\s+',' ',result['primary_effect']).strip():
                    result['unknowns'].append('Photographed main effect conflicts with catalog text at this level; review required.')
                else:
                    result['verified_main_effect']=verified_main
                    result['primary_effect']=verified_main['text']
            if entry.get('attribute_names'):result['attribute_tiers']=[{'name':name,'tier':tier} for name,tier in zip(entry['attribute_names'],result['level_profile'])]
            drops=DATA['official_rules']['mod_drop_levels']
            result['possible_crate_difficulties']=[name for name,bounds in drops.items() if isinstance(bounds,list) and bounds[0]<=level<=bounds[1]]
            if entry.get('attribute_names'):
                attributes=[]
                for name,tier in zip(entry['attribute_names'],result['level_profile']):
                    plain=re.sub(r' \(aerial bonus\)$','',name)
                    tier_values=entry.get('attribute_tier_values',{}).get(plain,{})
                    if tier==0:
                        exemplar=next((value for value in tier_values.values() if value),None)
                        attributes.append({'name':plain,'tier':0,'value_percent':0,'source':NUMERIC['official_level_source'],**(_semantic_record(exemplar) if exemplar else {'unit':'percent','direction':'unverified'})})
                        continue
                    own=tier_values.get(str(tier))
                    own_semantics=next((value for value in tier_values.values() if value),None)
                    shared_key=(plain,tier,_semantic_signature(own_semantics)) if own_semantics else None
                    # A matching display label on another mod is not evidence
                    # that this exact variant has the same fixed rank value.
                    shared=None
                    if own:attributes.append({'name':plain,**own})
                    elif shared:attributes.append({'name':plain,'tier':tier,**shared,'source':'validated across current Field Guide frames'})
                    else:attributes.append({'name':plain,'tier':tier,'value_percent':None,'source':None,
                                            **(_semantic_record(own_semantics) if own_semantics else {}),
                                            'semantic_source':own_semantics.get('source') if own_semantics else None,
                                            'conflict':bool(shared_key in SHARED_CONFLICTS or str(tier) in tier_values)})
                result['known_attributes']=attributes
                result['attribute_coverage']='complete' if all(a['value_percent'] is not None for a in attributes) else 'partial'
                if result['attribute_coverage']!='complete':result['unknowns'].append('At least one numeric attribute tier has no verified current Field Guide value; no interpolation used.')
                if any(a.get('conflict') for a in attributes):result['unknowns'].append('Conflicting numeric or semantic tier evidence requires review.')
            else:result['unknowns'].append('Exact sub-attribute values for this mod, variant and level are absent from the catalog.')
            if not entry.get('attribute_names'):result['unknowns'].append('The four fixed sub-attribute identities for this variant are not yet verified in the catalog.')
        if 'scenario-dependent availability' in (entry.get('variable_fields') or []):result['unknowns'].append('Scenario-dependent availability is not fully cataloged.')
        if entry.get('structured_suffix_effects'):result['unknowns'].append('Official suffix conditions are known, but magnitudes and stacking are unverified.')
        if level is not None and system== 'current_field_guide':
            observed=(OBSERVED.get(f'{catalog_id}:{level}:shiny') if shiny else
                      OBSERVED.get(f'{catalog_id}:{level}:regular') or
                      OBSERVED.get(f'{catalog_id}:{level}:unknown'))
            if observed:
                static=result.get('known_attributes') or []
                rows=[]
                for index,raw in enumerate(observed['attributes']):
                    row={**raw,'name':OBSERVED_ATTRIBUTE_NAMES.get(raw.get('stat_type'),raw['name']),
                         'evidence_context':observed['evidence_context'],
                         'source_sha256':observed['source_sha256']}
                    if (index<len(static) and static[index].get('value_percent') is not None and
                            row.get('value_percent') is not None and
                            static[index]['value_percent']!=row['value_percent']):
                        row['value_percent']=None
                        row['source_conflict']=True
                    rows.append(row)
                result['known_attributes']=rows
                result['known_attribute_names']=[row['name'] for row in rows]
                result['attribute_tiers']=[{'name':row['name'],'tier':row['tier']} for row in rows]
                result['attribute_coverage']='complete' if all(row.get('value_percent') is not None for row in rows) else 'partial'
                result['observed_profile']={'source_frame':observed['source_frame'],
                    'source_sha256':observed['source_sha256'], 'recorded_at':observed['recorded_at'],
                    'evidence_context':observed['evidence_context'], 'status':observed['evidence_status'],
                    'source_timestamp_seconds':observed.get('source_timestamp_seconds')}
                result['observed_main_effect']=observed.get('main_effect_raw')
                if not result.get('primary_effect'):
                    result['primary_effect']=observed.get('main_effect_raw')
                result['unknowns']=[note for note in result['unknowns'] if not note.startswith((
                    'At least one numeric attribute tier', 'Exact sub-attribute values',
                    'The four fixed sub-attribute identities'))]
                if result['attribute_coverage']!='complete':
                    result['unknowns'].append('At least one source-checked tooltip row has ambiguous magnitude or direction.')
                if any(row.get('source_conflict') for row in rows):
                    result['unknowns'].append('Static and source-checked exact-level numeric evidence conflict; conflicting cells withheld.')
    return result

def coverage():
    selectable=[e for e in DATA['mods'] if not e.get('family_only')]
    complete=sum(resolve(e['id'],level).get('attribute_coverage')=='complete' for e in selectable for level in range(1,18))
    return {'version':DATA['catalog_version'],'snapshot':DATA['source_snapshot'],'current_snapshot':{k:CURRENT[k] for k in ('source','retrieved_utc','page_records','parsed_records','rejected_records')},'detail_snapshot':{'retrieved_utc':DETAILS['retrieved_utc'],'pages':len(DETAILS['records']),'with_effect_variants':sum(bool(x.get('effect_variants')) for x in DETAILS['records'].values())},'counts':{k:len(DATA[k]) for k in ('mods','weapons','armor','sets')},'selectable_mod_variants':len(selectable),'current_mod_identities':sum(bool(x.get('current_records')) for x in DATA['mods']),'mods_without_parsed_variant':sum(not x.get('variant') for x in DATA['mods']),'mods_without_main_effect':sum(not x.get('primary_effect') for x in DATA['mods']),'mods_without_icon_link':sum(not x.get('image_url') for x in DATA['mods']),'effect_text_conflicts':sum(bool(x.get('effect_text_conflict')) for x in DATA['mods']),'structured_mod_effects':sum(bool(x['structured_effects']) for x in DATA['mods']),'official_suffix_variants':sum(bool(x.get('structured_suffix_effects')) for x in DATA['mods']),'verified_mod_attribute_identities':sum(bool(x.get('attribute_names')) for x in DATA['mods']),'source_checked_recording_attribute_identities':len(REVIEWED_LEVELS),'effective_known_attribute_identities':sum(bool(x.get('attribute_names') or REVIEWED_LEVELS.get(x['id'])) for x in selectable),'exact_mod_level_profiles':complete,'fully_resolved_mod_identities':sum(any(resolve(e['id'],level).get('attribute_coverage')=='complete' for level in range(1,18)) for e in selectable),'validated_shared_attribute_tiers':len(SHARED_TIERS),'cross_identity_tiers_applied':False,'shared_tier_conflicts':len(SHARED_CONFLICTS),'entry_tier_conflicts':len(NUMERIC_CONFLICTS),'unmapped_effect_candidate_identities':MAGNITUDES['identities_with_numeric_candidates'],'unmapped_effect_candidate_rows':MAGNITUDES['candidate_rows'],'theoretical_mod_level_grid':len(selectable)*17,'per_identity_obtainable_levels_verified':False}
