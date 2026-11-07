"""Trace 18 newly named native blueprints without guessing gameplay damage.

The full 33-record static snapshot is hash-linked to 18 public blueprint names.
Only the new 18 are added here; previously installed five and ten are checked
against this snapshot so a changed row cannot silently replace prior evidence.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import native_tier_star as native
import native_tier_expanded as expanded

ROOT = Path(__file__).parent / 'evidence_packets'
STATIC = ROOT / 'native-complete-static-v1.json'
NAMES = ROOT / 'native-new-public-names-v1.json'
RAW = ROOT / 'native_raw'

# This rename is explicitly stated on the linked public item page. It does not
# identify the separate base TEC9 weapon or assert identical configurations.
RENAMED = {'FP9 - Additional Rules': {
    'catalog_id':'weapon:tec9-additional-rules',
    'source_url':'https://www.oncehumandb.com/weapons/tec9-additional-rules',
    'source_statement':'Previously listed as TEC9 - Additional Rules.'}}


def _named_identity(title: str, entries: dict) -> tuple[str, dict | None]:
    name = title.removesuffix(' B.P.')
    if title != name + ' B.P.':
        raise ValueError('Native blueprint title is not an exact named page title')
    matches = [identity for identity, row in entries.items()
               if row['kind'] == 'weapon' and row['name'] == name]
    if len(matches) == 1:
        return matches[0], None
    bridge = RENAMED.get(name)
    if not bridge or matches or bridge['catalog_id'] not in entries:
        raise ValueError(f'{name}: no unique source-backed catalog identity')
    if entries[bridge['catalog_id']]['name'] != 'TEC9 - Additional Rules':
        raise ValueError('FP9/TEC9 source alias conflicts with catalog identity')
    return bridge['catalog_id'], bridge


def validate(static: dict, names: dict, captures: dict[str, bytes], entries: dict,
             *, prior_five: dict, prior_ten: dict) -> dict:
    src = static.get('source') or {}
    hashes = src.get('literal_sha256') or {}
    if (static.get('schema_version') != 1 or names.get('schema_version') != 1 or
            src.get('steam_build_id') != '26267212' or
            static.get('partition') != {'prior_five_blueprints':5,
                'prior_ten_blueprints':10,'newly_exposed_complete_blueprints':18,
                'all_unique_complete_blueprints':33} or
            static.get('coverage') != {'blueprints':33,'tier_attack_rows':165,
                                        'star_ratio_rows':198} or
            names.get('coverage') != {'new_blueprint_titles':18,
                'direct_tier_one_gear_titles':8,'newly_checked_tier_two_to_five_pages':0}):
        raise ValueError('33-record native/public snapshot schema or coverage changed')
    for key, expected in hashes.items():
        if key not in captures or hashlib.sha256(captures[key]).hexdigest() != expected:
            raise ValueError(f'{key}: pinned complete-snapshot capture hash conflict')
    if len(static.get('samples',[])) != 33 or len(names.get('records',[])) != 18:
        raise ValueError('Complete native/public row count changed')
    samples = {row['blueprint_id']:row for row in static['samples']}
    if len(samples) != 33:
        raise ValueError('Duplicate native blueprint in complete snapshot')
    prior_ids = set(prior_five['by_blueprint']) | {
        row['blueprint_id'] for row in prior_ten['by_catalog'].values()}
    if len(prior_ids) != 15 or len(prior_ids & set(samples)) != 15:
        raise ValueError('Prior native evidence is missing from complete snapshot')
    for bp in prior_ids:
        sample=samples[bp]
        old=(prior_five['by_blueprint'].get(bp) or next(
            row for row in prior_ten['by_catalog'].values() if row['blueprint_id']==bp))
        if (len(sample['tiers']) != 5 or len(sample['star_ratios']) != 6 or
                any(row['gear_id'] != old['tiers'][row['tier']]['gear_id'] or
                    row['gun_preset_attack']['value'] != old['tiers'][row['tier']]['gun_preset_attack']
                    for row in sample['tiers']) or
                any(row['value'] != old['stars'][row['star']]['preset_attack_radio']
                    for row in sample['star_ratios'])):
            raise ValueError('Complete snapshot conflicts with previously installed native fields')
    named = {}
    for record in names['records']:
        bp = record['blueprint_id']
        if bp in named or bp in prior_ids or bp not in samples:
            raise ValueError('New blueprint name duplicates or lacks a native row')
        catalog_id, alias = _named_identity(record['public_blueprint_title'],entries)
        if (record['public_blueprint_url'] != f'https://oncehuman.th.gl/db/blueprints/{bp}' or
                record['tier_one_gear_id_from_native_mapping'] != samples[bp]['tier_one_gear_id']):
            raise ValueError('Public blueprint URL or native Tier I gear link conflict')
        gear_title=record.get('public_tier_one_gear_title')
        gear_url=record.get('public_tier_one_gear_url_if_directly_checked')
        if (gear_title is None) != (gear_url is None):
            raise ValueError('Partially reported direct Tier I page evidence')
        if gear_title is not None and (
                gear_title != record['public_blueprint_title'].removesuffix(' B.P.')+' (Tier 1)' or
                gear_url != f'https://oncehuman.th.gl/db/gear/{samples[bp]["tier_one_gear_id"]}'):
            raise ValueError('Direct Tier I page name or exact gear URL conflict')
        if catalog_id in {r[0] for r in named.values()}:
            raise ValueError('Two new blueprints map to one catalog weapon')
        named[bp]=(catalog_id, record, alias)
    if len(named)!=18 or set(samples)-prior_ids != set(named):
        raise ValueError('New public names do not partition the native 33-row snapshot')
    gun_map=native._item_to_gun(captures['item_to_gun_mapping_data'])
    equip,origin,blueprint,attr,base=(captures[key] for key in
        ('equip_data','equip_origin_data','gun_blueprint_data',
         'gun_blueprint_attr_data','gun_base_params_data'))
    base_names=native._names(base)
    accepted={}
    seen_gears=set()
    for bp,(catalog_id,public,alias) in named.items():
        sample=samples[bp]
        pair_at=sample['gear_to_blueprint_pair_offset']
        raw=bytes.fromhex(sample['gear_to_blueprint_pair_raw_hex'])
        if blueprint[pair_at:pair_at+len(raw)] != raw:
            raise ValueError('New blueprint mapping bytes conflict with capture')
        mapped_gear,at=native._uvar(blueprint,pair_at)
        mapped_bp,end=native._uvar(blueprint,at)
        tier_one=sample['tier_one_gear_id']
        if (mapped_gear!=tier_one or mapped_bp!=bp or end!=pair_at+len(raw) or
                native._uvar(blueprint,sample['gear_varuint_offset'])[0]!=tier_one or
                not sample['blueprint_row_start_offset']<=sample['gear_varuint_offset']<
                sample['blueprint_row_end_offset_exclusive']):
            raise ValueError('New native gear-to-blueprint row identity conflict')
        tiers,stars={},{}
        for row in sample['tiers']:
            number,gear=row['tier'],row['gear_id']
            if (number in tiers or gear in seen_gears or not 1<=number<=5 or
                    row['gun_no']!=sample['shared_gun_no'] or gun_map.get(gear)!=row['gun_no']):
                raise ValueError('New native gear/tier/gun identity conflict')
            seen_gears.add(gear)
            at=row['equip_index_offset']
            indexed_gear,at=native._uvar(equip,at)
            relative,at=native._uvar(equip,at)
            tag,_=native._uvar(equip,at)
            if indexed_gear!=gear or 92938+relative!=row['equip_row_offset'] or tag!=1:
                raise ValueError('New equip index-to-row conflict')
            at=row['origin_index_offset']
            origin_gear,at=native._uvar(origin,at)
            origin_relative,_=native._uvar(origin,at)
            if (origin_gear!=gear or 15721+origin_relative!=row['origin_row_offset'] or
                    origin[row['origin_row_offset']:row['origin_row_offset']+2]!=b'\x96\x4b'):
                raise ValueError('New origin index-to-row conflict')
            for key,want in [('native_tier_field',number),
                             ('native_blueprint_field',bp),
                             ('native_origin_id_field',gear)]:
                field=row[key]
                if not row['equip_row_offset']<=field['byte_offset']<row['equip_decoded_end_offset']:
                    raise ValueError('New native equipment field outside row')
                if native._native_value(equip,field,'integer')!=want:
                    raise ValueError('New native gear identity field conflict')
            field=row['gun_preset_attack']
            if (field['native_field']!='gun_preset_attack' or field['type_code']!=18 or
                    not row['origin_row_offset']<field['byte_offset']<row['origin_row_offset']+40):
                raise ValueError('New origin attack field/type conflict')
            value=native._native_value(origin,field,'float32')
            if value<=0:
                raise ValueError('New source-native attack nonpositive')
            tiers[number]={'gear_id':gear,'gun_preset_attack':value,
                           'byte_offset':field['byte_offset']}
        if tiers[1]['gear_id']!=tier_one or set(tiers)!=set(range(1,6)):
            raise ValueError('New Tier I gear or native series incomplete')
        for row in sample['star_ratios']:
            star=row['star']
            if (star in stars or not 1<=star<=6 or row['native_field']!='preset_attack_radio'
                    or row['type_code'] not in (18,34)):
                raise ValueError('New native blueprint/star descriptor conflict')
            at=row['record_offset']
            record_bp,after_bp=native._uvar(attr,at)
            raw=bytes.fromhex(row['raw_hex'])
            if (record_bp!=bp or attr[after_bp]!=star or
                    attr[after_bp+1:after_bp+3]!=b'\x96\x26' or
                    attr[after_bp+3]!=int(row['record_tag_hex'],16) or
                    attr[row['value_byte_offset']+len(raw):row['value_byte_offset']+len(raw)+4]
                    !=b'\x15\x17\x16\x04'):
                raise ValueError('New native blueprint/star record conflict')
            value=native._native_value(attr,{'byte_offset':row['value_byte_offset'],
                'raw_hex':row['raw_hex'],'value':row['value']},
                'float32' if row['type_code']==18 else 'float64')
            if not 0<value<=2:
                raise ValueError('New star ratio outside bounded positive range')
            stars[star]={'preset_attack_radio':value,
                         'byte_offset':row['value_byte_offset']}
        if set(stars)!=set(range(1,7)):
            raise ValueError('New native star series incomplete')
        fields=sample['gun_base_native_fields']
        for key in ('weapon_magazine_size_affix_value','weapon_range_affix_value',
                    'weapon_rpm','weapon_rpm_affix_value'):
            field=fields[key]
            if field['native_field']!=key or base_names[field['name_index']]!=key:
                raise ValueError('New gun-base field descriptor conflict')
            native._native_value(base,field,'float64' if key=='weapon_rpm' else 'integer')
        accepted[catalog_id]={
            'catalog_id':catalog_id,'blueprint_id':bp,
            'public_blueprint_title':public['public_blueprint_title'],
            'public_blueprint_url':public['public_blueprint_url'],
            'public_tier_one_gear_title':public.get('public_tier_one_gear_title'),
            'public_tier_one_gear_url':public.get('public_tier_one_gear_url_if_directly_checked'),
            'identity_proof':'native_blueprint_and_direct_gear_page' if public.get('public_tier_one_gear_title') else 'native_blueprint_and_named_blueprint_page',
            'name_bridge':alias,'source_access_date':public['source_access_date'],
            'public_page_build':public['public_page_build'],'tiers':tiers,'stars':stars}
    if len(accepted)!=18 or len(seen_gears)!=90:
        raise ValueError('New native evidence count conflict')
    return {'schema_version':1,'steam_build_id':src['steam_build_id'],
            'source_literal_sha256':hashes,'by_catalog':accepted,
            'counts':{'prior_accepted':15,'new_accepted':18,'new_rejected':0,
                'total_accepted_blueprints':33,'new_tier_rows':90,
                'new_star_rows':108,'new_direct_tier_one_names':8,
                'new_blueprint_only_names':10,'formula_ready_fields':0},
            'scope':'source-native identity and located fields only; no final gameplay damage equation'}


def load_current(entries:dict, prior_five:dict, prior_ten:dict)->dict:
    raw=STATIC.read_bytes()
    names=json.loads(NAMES.read_bytes())
    if names.get('native_catalog_sha256')!=hashlib.sha256(raw).hexdigest():
        raise ValueError('New public name packet does not link to exact 33-row artifact bytes')
    static=json.loads(raw)
    captures={key:(RAW/f'{key}.literal_bytes.bin').read_bytes()
              for key in static['source']['literal_sha256']}
    return validate(static,names,captures,entries,prior_five=prior_five,prior_ten=prior_ten)


def selected(report:dict,catalog_id:str,tier:int|None,stars:int|None):
    row=report['by_catalog'].get(catalog_id)
    if row is None:
        return None
    t=row['tiers'].get(tier) if isinstance(tier,int) and not isinstance(tier,bool) else None
    s=row['stars'].get(stars) if isinstance(stars,int) and not isinstance(stars,bool) else None
    return {'catalog_id':catalog_id,'blueprint_id':row['blueprint_id'],
        'selected_tier':tier,'selected_stars':stars,
        'gun_preset_attack':t['gun_preset_attack'] if t else None,
        'preset_attack_radio':s['preset_attack_radio'] if s else None,
        'gear_id':t['gear_id'] if t else None,
        'source_offsets':{'origin_attack':t['byte_offset'] if t else None,
                          'blueprint_star':s['byte_offset'] if s else None},
        'public_blueprint_title':row['public_blueprint_title'],
        'public_blueprint_url':row['public_blueprint_url'],
        'public_tier_one_gear_title':row['public_tier_one_gear_title'],
        'public_tier_one_gear_url':row['public_tier_one_gear_url'],
        'public_tier_one':{'star_damage':None,'star_table_status':'not inspected'},
        'name_bridge':row['name_bridge'],
        'identity_proof':row['identity_proof'],
        'steam_build_id':report['steam_build_id'],
        'calculation_included':False,
        'unresolved':'No public numeric Tier I page check for this batch; native consumer equation, damage unit, rounding, calibration and crafted Attack remain unknown'}
