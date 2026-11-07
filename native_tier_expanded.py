"""Bounded ten-weapon native evidence intake; no inferred damage formula."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import native_tier_star as native

ROOT = Path(__file__).parent / 'evidence_packets'
STATIC = ROOT / 'native-expanded-static-v1.json'
PUBLIC = ROOT / 'native-expanded-public-v1.json'
RAW = ROOT / 'native_raw'
BLUEPRINT_TITLE_EXCEPTIONS = {13212401: 'Format B.P.'}


def validate(static: dict, public: dict, captures: dict[str, bytes], catalog_entries: dict) -> dict:
    source = static.get('source') or {}
    hashes = source.get('literal_sha256') or {}
    if (static.get('schema_version') != 1 or public.get('schema_version') != 1 or
            source.get('steam_build_id') != '26267212' or
            public.get('static_artifact_sha256') != hashlib.sha256(
                json.dumps(static, indent=2).encode() + b'\n').hexdigest()):
        raise ValueError('Expanded source schema or linked artifact hash conflict')
    for name, expected in hashes.items():
        if name not in captures or hashlib.sha256(captures[name]).hexdigest() != expected:
            raise ValueError(f'{name}: expanded capture hash conflict')
    if (len(static.get('samples', [])) != 10 or len(public.get('records', [])) != 10 or
            public.get('coverage', {}).get('missing_public_star_table') != 1):
        raise ValueError('Expanded bounded sample count changed')
    by_public = {}
    for row in public['records']:
        bp = row['blueprint_id']
        name = row['public_tier_one_gear_title'].removesuffix(' (Tier 1)')
        if (bp in by_public or row['public_tier_one_gear_title'] != name + ' (Tier 1)' or
                row['public_blueprint_title'] != BLUEPRINT_TITLE_EXCEPTIONS.get(bp, name + ' B.P.') or
                row['blueprint_url'] != f'https://oncehuman.th.gl/db/blueprints/{bp}' or
                row['tier_one_gear_url'] !=
                f'https://oncehuman.th.gl/db/gear/{row["tier_one_gear_id"]}'):
            raise ValueError('Expanded public blueprint/gear source identity conflict')
        matches = [identity for identity, entry in catalog_entries.items()
                   if entry['kind'] == 'weapon' and entry['name'] == name]
        if len(matches) != 1:
            raise ValueError('Expanded public weapon name is not a unique catalog identity')
        by_public[bp] = (matches[0], row)
    if len(by_public) != 10:
        raise ValueError('Expanded public blueprint set is incomplete')
    gun_map = native._item_to_gun(captures['item_to_gun_mapping_data'])
    equip, origin, blueprint, attr, base = (captures[key] for key in
        ('equip_data', 'equip_origin_data', 'gun_blueprint_data',
         'gun_blueprint_attr_data', 'gun_base_params_data'))
    base_names = native._names(base)
    results, seen_gears = {}, set()
    for sample in static['samples']:
        bp = sample['blueprint_id']
        if bp not in by_public or bp in results:
            raise ValueError('Expanded native blueprint is missing or duplicated in public sources')
        catalog_id, page = by_public[bp]
        if sample['tier_one_gear_id'] != page['tier_one_gear_id']:
            raise ValueError('Expanded Tier I native gear conflicts with public page')
        pair_at = sample['gear_to_blueprint_pair_offset']
        pair_raw = bytes.fromhex(sample['gear_to_blueprint_pair_raw_hex'])
        if blueprint[pair_at:pair_at+len(pair_raw)] != pair_raw:
            raise ValueError('Expanded blueprint mapping raw bytes conflict')
        gear, after_gear = native._uvar(blueprint, pair_at)
        mapped_bp, after_bp = native._uvar(blueprint, after_gear)
        if (gear != page['tier_one_gear_id'] or mapped_bp != bp or
                after_bp != pair_at + len(pair_raw)):
            raise ValueError('Expanded gear-to-blueprint mapping conflict')
        native_gear, _ = native._uvar(blueprint, sample['gear_varuint_offset'])
        if (native_gear != gear or not sample['blueprint_row_start_offset'] <=
                sample['gear_varuint_offset'] < sample['blueprint_row_end_offset_exclusive']):
            raise ValueError('Expanded blueprint row gear identity conflict')
        tiers, stars = {}, {}
        for row in sample['tiers']:
            number, gear_id = row['tier'], row['gear_id']
            if (number in tiers or gear_id in seen_gears or not 1 <= number <= 5 or
                    row['gun_no'] != sample['shared_gun_no'] or
                    gun_map.get(gear_id) != row['gun_no']):
                raise ValueError('Expanded tier/gear/gun identity conflict')
            seen_gears.add(gear_id)
            at = row['equip_index_offset']
            indexed_gear, at = native._uvar(equip, at)
            relative, at = native._uvar(equip, at)
            tag, _ = native._uvar(equip, at)
            if indexed_gear != gear_id or 92938 + relative != row['equip_row_offset'] or tag != 1:
                raise ValueError('Expanded equip index/row conflict')
            at = row['origin_index_offset']
            origin_gear, at = native._uvar(origin, at)
            origin_relative, _ = native._uvar(origin, at)
            if (origin_gear != gear_id or 15721 + origin_relative != row['origin_row_offset'] or
                    origin[row['origin_row_offset']:row['origin_row_offset']+2] != b'\x96\x4b'):
                raise ValueError('Expanded origin index/row conflict')
            for key, expected in (('native_tier_field',number),
                                  ('native_blueprint_field',bp),
                                  ('native_origin_id_field',gear_id)):
                field = row[key]
                if not row['equip_row_offset'] <= field['byte_offset'] < row['equip_decoded_end_offset']:
                    raise ValueError('Expanded equip field outside row')
                if native._native_value(equip,field,'integer') != expected:
                    raise ValueError('Expanded native gear identity field conflict')
            field = row['gun_preset_attack']
            if (field['native_field'] != 'gun_preset_attack' or field['type_code'] != 18 or
                    not row['origin_row_offset'] < field['byte_offset'] < row['origin_row_offset']+40):
                raise ValueError('Expanded native origin field/type conflict')
            value = native._native_value(origin,field,'float32')
            if value <= 0:
                raise ValueError('Expanded native attack is nonpositive')
            tiers[number] = {'gear_id':gear_id, 'gun_preset_attack':value,
                             'byte_offset':field['byte_offset']}
        for row in sample['star_ratios']:
            star = row['star']
            if (star in stars or not 1 <= star <= 6 or
                    row['native_field'] != 'preset_attack_radio' or
                    row['type_code'] not in (18,34)):
                raise ValueError('Expanded native star identity/descriptor conflict')
            at = row['record_offset']
            record_bp, after_bp = native._uvar(attr,at)
            raw = bytes.fromhex(row['raw_hex'])
            if (record_bp != bp or attr[after_bp] != star or
                    attr[after_bp+1:after_bp+3] != b'\x96\x26' or
                    attr[after_bp+3] != int(row['record_tag_hex'],16) or
                    attr[row['value_byte_offset']+len(raw):row['value_byte_offset']+len(raw)+4]
                    != b'\x15\x17\x16\x04'):
                raise ValueError('Expanded native blueprint/star row conflict')
            value = native._native_value(attr,{'byte_offset':row['value_byte_offset'],
                'raw_hex':row['raw_hex'],'value':row['value']},
                'float32' if row['type_code']==18 else 'float64')
            if not 0 < value <= 2:
                raise ValueError('Expanded native star ratio outside bounded positive range')
            stars[star] = {'preset_attack_radio':value,'byte_offset':row['value_byte_offset']}
        fields = sample['gun_base_native_fields']
        for key in ('weapon_magazine_size_affix_value','weapon_range_affix_value',
                    'weapon_rpm','weapon_rpm_affix_value'):
            field = fields[key]
            if base_names[field['name_index']] != key or field['native_field'] != key:
                raise ValueError('Expanded gun-base field descriptor conflict')
            kind = 'float64' if key=='weapon_rpm' else 'integer'
            native._native_value(base,field,kind)
        observed = page['observed_page_fields']
        if (tiers[1]['gear_id'] != gear or
                observed['DMG'] != tiers[1]['gun_preset_attack'] or
                observed['Fire Rate'] != fields['weapon_rpm_affix_value']['value'] or
                observed['Magazine Capacity'] != fields['weapon_magazine_size_affix_value']['value'] or
                observed['Full DMG Range']['value'] != fields['weapon_range_affix_value']['value']):
            raise ValueError('Expanded public Tier I values conflict with located native fields')
        table = observed.get('DMG per star')
        if page['star_table_status'] == 'not present on inspected gear page':
            if table is not None:
                raise ValueError('Expanded absent public star table is misrepresented')
        elif not isinstance(table,list) or len(table)!=6:
            raise ValueError('Expanded public star table incomplete')
        if set(tiers) != set(range(1,6)) or set(stars) != set(range(1,7)):
            raise ValueError('Expanded native tier/star grid incomplete')
        results[catalog_id] = {'catalog_id':catalog_id,'name':page['public_tier_one_gear_title'],
            'blueprint_id':bp,'tiers':tiers,'stars':stars,
            'public_tier_one':{'url':page['tier_one_gear_url'],
                'blueprint_url':page['blueprint_url'],
                'displayed_dmg':observed['DMG'], 'fire_rate_raw':observed['Fire Rate'],
                'magazine_capacity':observed['Magazine Capacity'],
                'star_damage':table,'star_table_status':page['star_table_status']},
            'source_access_date':page['source_access_date'],
            'source_game_build':page['source_game_build']}
    if len(results)!=10 or len(seen_gears)!=50:
        raise ValueError('Expanded native ten-weapon coverage changed')
    memento=results.get('weapon:r500-memento')
    if (not memento or memento['tiers'][1]['gun_preset_attack']!=170 or
            memento['stars'][4]['preset_attack_radio']!=1.15 or
            memento['public_tier_one']['star_damage'][3]!=195):
        raise ValueError('Memento non-universal star product counterexample lost')
    return {'schema_version':1,'steam_build_id':source['steam_build_id'],
        'source_literal_sha256':hashes,'by_catalog':results,
        'counts':{'weapons':10,'native_tier_rows':50,'native_star_rows':60,
                  'public_tier_one_named_pages':10,'public_star_tables':9,
                  'formula_ready_fields':0},
        'scope':'Exact named identity and native fields only; source consumer arithmetic and crafted configuration unresolved'}


def load_current(catalog_entries: dict) -> dict:
    static_bytes = STATIC.read_bytes()
    static, public = json.loads(static_bytes), json.loads(PUBLIC.read_bytes())
    if public['static_artifact_sha256'] != hashlib.sha256(static_bytes).hexdigest():
        raise ValueError('Expanded public packet does not link to exact static artifact bytes')
    captures = {name:(RAW/f'{name}.literal_bytes.bin').read_bytes()
                for name in static['source']['literal_sha256']}
    return validate(static,public,captures,catalog_entries)


def selected(report: dict, catalog_id: str, tier: int | None, stars: int | None):
    row = report['by_catalog'].get(catalog_id)
    if row is None:
        return None
    tier_row = row['tiers'].get(tier) if isinstance(tier,int) and not isinstance(tier,bool) else None
    star_row = row['stars'].get(stars) if isinstance(stars,int) and not isinstance(stars,bool) else None
    return {'catalog_id':catalog_id,'blueprint_id':row['blueprint_id'],
        'selected_tier':tier,'selected_stars':stars,
        'gun_preset_attack':tier_row['gun_preset_attack'] if tier_row else None,
        'preset_attack_radio':star_row['preset_attack_radio'] if star_row else None,
        'gear_id':tier_row['gear_id'] if tier_row else None,
        'source_offsets':{'origin_attack':tier_row['byte_offset'] if tier_row else None,
                          'blueprint_star':star_row['byte_offset'] if star_row else None},
        'public_tier_one':row['public_tier_one'],
        'steam_build_id':report['steam_build_id'], 'calculation_included':False,
        'unresolved':'Native consumer equation, damage unit, rounding, calibration and crafted Attack remain unknown'}
