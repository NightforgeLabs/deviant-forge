"""Field-level validation of located native weapon rows with variable star ranges.

Native records are evidence only. A missing star row is null, never zero or an
inferred multiplier; no row here is a final damage input.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import native_tier_star as native

ROOT = Path(__file__).parent / 'evidence_packets'
PARTIAL = ROOT / 'native-partial-star-catalog-v1.json'
ANCHORS = ROOT / 'native-partial-public-anchors-v1.json'
RAW = ROOT / 'native_raw'
PARTIAL_SHA256 = '8283fd954c1b1e987ac9e9a674b170783705827dd36dbffea5d38d3b3beb94bb'


def validate(packet: dict, anchors: dict, captures: dict[str, bytes],
             entries: dict, prior: dict) -> dict:
    source = packet.get('source') or {}
    hashes = source.get('literal_sha256') or {}
    if (packet.get('schema_version') != 1 or anchors.get('schema_version') != 1 or
            source.get('steam_build_id') != '26267212' or
            packet.get('coverage') != {'blueprints': 92, 'tier_attack_rows': 460,
                                       'star_ratio_rows': 429} or
            packet.get('stored_star_count_distribution') !=
            {'3': 25, '4': 14, '5': 20, '6': 33}):
        raise ValueError('Partial native packet schema or field coverage changed')
    for name, expected in hashes.items():
        if name not in captures or hashlib.sha256(captures[name]).hexdigest() != expected:
            raise ValueError(f'{name}: pinned native literal hash conflict')
    samples = packet.get('samples') or []
    by_blueprint = {row['blueprint_id']: row for row in samples}
    if len(samples) != 92 or len(by_blueprint) != 92:
        raise ValueError('Partial native blueprint count or uniqueness conflict')
    prior_by_blueprint = {row['blueprint_id']: row for row in prior.values()}
    if len(prior_by_blueprint) != 33 or not set(prior_by_blueprint) <= set(by_blueprint):
        raise ValueError('Prior complete native records are not retained')
    anchor_rows = {row['blueprint_id']: row for row in anchors.get('anchors', [])}
    if set(anchor_rows) != {13121101, 13111201, 13421301} or len(anchors['anchors']) != 3:
        raise ValueError('Named partial blueprint anchor set changed')
    checks = {row['blueprint_id']: row for row in packet.get('public_max_star_spot_checks', [])}
    if set(checks) != set(anchor_rows):
        raise ValueError('Public max-star checks do not cover named anchors')

    gun_map = native._item_to_gun(captures['item_to_gun_mapping_data'])
    equip, origin, blueprint, attr, base = (captures[key] for key in
        ('equip_data', 'equip_origin_data', 'gun_blueprint_data',
         'gun_blueprint_attr_data', 'gun_base_params_data'))
    base_names = native._names(base)
    accepted, seen_gears, distribution = {}, set(), Counter()
    for bp, sample in by_blueprint.items():
        if bp in prior_by_blueprint:
            old = prior_by_blueprint[bp]
            if (len(sample['tiers']) != 5 or len(sample['star_ratios']) != 6 or
                    sample['tier_one_gear_id'] != old['tiers'][1]['gear_id'] or
                    any(row['gear_id'] != old['tiers'][row['tier']]['gear_id'] or
                        row['gun_preset_attack']['value'] !=
                        old['tiers'][row['tier']]['gun_preset_attack']
                        for row in sample['tiers']) or
                    any(row['value'] != old['stars'][row['star']]['preset_attack_radio']
                        for row in sample['star_ratios'])):
                raise ValueError('Partial snapshot conflicts with installed complete record')
        pair_at = sample['gear_to_blueprint_pair_offset']
        raw = bytes.fromhex(sample['gear_to_blueprint_pair_raw_hex'])
        gear, at = native._uvar(blueprint, pair_at)
        mapped_bp, end = native._uvar(blueprint, at)
        if (blueprint[pair_at:end] != raw or end != pair_at + len(raw) or
                mapped_bp != bp or gear != sample['tier_one_gear_id'] or
                native._uvar(blueprint, sample['gear_varuint_offset'])[0] != gear or
                not sample['blueprint_row_start_offset'] <=
                sample['gear_varuint_offset'] < sample['blueprint_row_end_offset_exclusive']):
            raise ValueError('Partial gear-to-blueprint identity conflict')
        tiers, stars = {}, {}
        if len(sample['tiers']) != 5:
            raise ValueError('Partial native tier count changed')
        for row in sample['tiers']:
            number, gear_id = row['tier'], row['gear_id']
            if (number in tiers or number not in range(1, 6) or gear_id in seen_gears or
                    row['gun_no'] != sample['shared_gun_no'] or
                    gun_map.get(gear_id) != row['gun_no']):
                raise ValueError('Partial tier/gear/gun mapping conflict')
            seen_gears.add(gear_id)
            at = row['equip_index_offset']
            indexed, at = native._uvar(equip, at)
            relative, at = native._uvar(equip, at)
            tag, _ = native._uvar(equip, at)
            if indexed != gear_id or 92938 + relative != row['equip_row_offset'] or tag != 1:
                raise ValueError('Partial equip index or row conflict')
            at = row['origin_index_offset']
            origin_gear, at = native._uvar(origin, at)
            origin_relative, _ = native._uvar(origin, at)
            if (origin_gear != gear_id or 15721 + origin_relative != row['origin_row_offset'] or
                    origin[row['origin_row_offset']:row['origin_row_offset']+2] != b'\x96\x4b'):
                raise ValueError('Partial origin index or row conflict')
            for key, want in (('native_tier_field', number),
                              ('native_blueprint_field', bp),
                              ('native_origin_id_field', gear_id)):
                field = row[key]
                if (not row['equip_row_offset'] <= field['byte_offset'] <
                        row['equip_decoded_end_offset'] or
                        native._native_value(equip, field, 'integer') != want):
                    raise ValueError('Partial native tier identity field conflict')
            attack = row['gun_preset_attack']
            if (attack['native_field'] != 'gun_preset_attack' or
                    attack['type_code'] != 18 or
                    not row['origin_row_offset'] < attack['byte_offset'] <
                    row['origin_row_offset'] + 40):
                raise ValueError('Partial origin attack field/type conflict')
            value = native._native_value(origin, attack, 'float32')
            if value <= 0:
                raise ValueError('Partial origin attack is nonpositive')
            tiers[number] = {'gear_id': gear_id, 'gun_preset_attack': value,
                             'byte_offset': attack['byte_offset']}
        if set(tiers) != set(range(1, 6)) or tiers[1]['gear_id'] != gear:
            raise ValueError('Partial native tier set or Tier I gear conflict')
        for row in sample['star_ratios']:
            star = row['star']
            if (star in stars or star not in range(1, 7) or
                    row['native_field'] != 'preset_attack_radio' or
                    row['type_code'] not in (18, 34)):
                raise ValueError('Partial native star descriptor conflict')
            at = row['record_offset']
            record_bp, after = native._uvar(attr, at)
            raw = bytes.fromhex(row['raw_hex'])
            if (record_bp != bp or attr[after] != star or
                    attr[after+1:after+3] != b'\x96\x26' or
                    attr[after+3] != int(row['record_tag_hex'], 16) or
                    attr[row['value_byte_offset']+len(raw):
                         row['value_byte_offset']+len(raw)+4] != b'\x15\x17\x16\x04'):
                raise ValueError('Partial blueprint/star identity conflict')
            value = native._native_value(attr, {'byte_offset': row['value_byte_offset'],
                'raw_hex': row['raw_hex'], 'value': row['value']},
                'float32' if row['type_code'] == 18 else 'float64')
            if not 0 < value <= 2:
                raise ValueError('Partial native star ratio outside bounded range')
            stars[star] = {'preset_attack_radio': value,
                           'byte_offset': row['value_byte_offset']}
        if len(stars) not in (3, 4, 5, 6) or set(stars) != set(range(1, len(stars)+1)):
            raise ValueError('Partial native star sequence has a gap')
        distribution[len(stars)] += 1
        fields = sample['gun_base_native_fields']
        for key in ('weapon_magazine_size_affix_value', 'weapon_range_affix_value',
                    'weapon_rpm', 'weapon_rpm_affix_value'):
            field = fields[key]
            if field['native_field'] != key or base_names[field['name_index']] != key:
                raise ValueError('Partial gun-base field descriptor conflict')
            native._native_value(base, field, 'float64' if key == 'weapon_rpm' else 'integer')
        accepted[bp] = {'blueprint_id': bp, 'tier_one_gear_id': gear,
                        'tiers': tiers, 'stars': stars,
                        'stored_star_count': len(stars)}
    if (len(seen_gears) != 460 or distribution != Counter({3:25, 4:14, 5:20, 6:33}) or
            sum(len(r['stars']) for r in accepted.values()) != 429):
        raise ValueError('Partial native field acceptance counts changed')

    by_catalog = {}
    for bp, anchor in anchor_rows.items():
        spot = checks[bp]
        row = accepted[bp]
        if (anchor['public_blueprint_url'] != f'https://oncehuman.th.gl/db/blueprints/{bp}' or
                spot['url'] != anchor['public_blueprint_url'] or
                spot['stored_star_rows'] != row['stored_star_count'] or
                spot['published_max_stars'] != anchor['published_max_stars'] or
                anchor['published_max_stars'] != row['stored_star_count']):
            raise ValueError('Partial public identity or max-star source conflict')
        identity = anchor['catalog_id']
        if bp == 13421301:
            if (identity is not None or anchor['identity_status'] !=
                    'unbound_mixed_crafts_KAM_Crank_is_distinct'):
                raise ValueError('KAM Burning Rage must not inherit KAM Crank identity')
            continue
        if (anchor['identity_status'] != 'exact_name' or not identity or
                identity not in entries or entries[identity]['kind'] != 'weapon' or
                anchor['public_blueprint_title'] != entries[identity]['name'] + ' B.P.' or
                identity in by_catalog or bp in prior_by_blueprint):
            raise ValueError('Partial public name does not uniquely bind catalog weapon')
        by_catalog[identity] = {**row, 'catalog_id': identity,
            'public_blueprint_title': anchor['public_blueprint_title'],
            'public_blueprint_url': anchor['public_blueprint_url'],
            'published_max_stars': anchor['published_max_stars']}
    if len(by_catalog) != 2:
        raise ValueError('Partial catalog identity count changed')
    return {'schema_version': 1, 'steam_build_id': source['steam_build_id'],
        'source_literal_sha256': hashes, 'by_blueprint': accepted,
        'by_catalog': by_catalog,
        'counts': {'prior_complete_records':33, 'new_native_blueprints':59,
                   'new_tier_attack_fields':295, 'new_star_ratio_fields':231,
                   'new_catalog_identity_bindings':2, 'new_unbound_blueprints':57,
                   'formula_ready_fields':0},
        'stored_star_distribution': dict(distribution),
        'scope': 'Located native fields, not complete gameplay damage or crafted Attack'}


def load_current(entries: dict, prior_five: dict, prior_ten: dict,
                 prior_remaining: dict) -> dict:
    raw = PARTIAL.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARTIAL_SHA256:
        raise ValueError('Partial native source artifact hash conflict')
    packet = json.loads(raw)
    anchors = json.loads(ANCHORS.read_bytes())
    captures = {name:(RAW / f'{name}.literal_bytes.bin').read_bytes()
                for name in packet['source']['literal_sha256']}
    prior = dict(prior_five['by_blueprint'])
    prior.update({r['blueprint_id']:r for r in prior_ten['by_catalog'].values()})
    prior.update({r['blueprint_id']:r for r in prior_remaining['by_catalog'].values()})
    return validate(packet, anchors, captures, entries, prior)


def selected(report: dict, catalog_id: str, tier: int | None, stars: int | None):
    row = report['by_catalog'].get(catalog_id)
    if row is None:
        return None
    t = row['tiers'].get(tier) if type(tier) is int else None
    s = row['stars'].get(stars) if type(stars) is int else None
    invalid = type(stars) is int and stars > row['published_max_stars']
    missing = (f'Selected {stars}★ exceeds the published maximum of '
               f'{row["published_max_stars"]}★ for this exact blueprint.' if invalid else
               f'No stored native star record for {stars}★; this is within the '
               f'published maximum {row["published_max_stars"]}★, but this capture '
               f'has located rows only for 1–{row["stored_star_count"]}★.'
               if type(stars) is int and s is None else None)
    return {'catalog_id':catalog_id, 'blueprint_id':row['blueprint_id'],
        'selected_tier':tier, 'selected_stars':stars,
        'gun_preset_attack':t['gun_preset_attack'] if t else None,
        'preset_attack_radio':s['preset_attack_radio'] if s else None,
        'gear_id':t['gear_id'] if t else None,
        'source_offsets':{'origin_attack':t['byte_offset'] if t else None,
                          'blueprint_star':s['byte_offset'] if s else None},
        'stored_star_count':row['stored_star_count'],
        'published_max_stars':row['published_max_stars'],
        'configuration_status':'exceeds_published_max_stars' if invalid else 'not_disproved_by_published_max',
        'missing_star_reason':missing,
        'public_blueprint_title':row['public_blueprint_title'],
        'public_blueprint_url':row['public_blueprint_url'],
        'public_tier_one_gear_title':row.get('public_tier_one_gear_title'),
        'public_tier_one_gear_url':row.get('public_tier_one_gear_url'),
        'name_bridge':None, 'steam_build_id':report['steam_build_id'],
        'calculation_included':False,
        'unresolved':'Native consumer equation, damage unit, rounding, calibration and crafted Attack remain unknown'}
