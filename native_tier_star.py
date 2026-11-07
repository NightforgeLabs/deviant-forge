"""Validate located native tier/star fields without promoting a damage formula.

Only pinned literal captures are read. The exact tier/gear/blueprint binding is
checked against independent named item pages. A matching public number does not
establish the native consumer equation or current crafted weapon damage.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import struct

ROOT = Path(__file__).parent / 'evidence_packets'
TIER_SAMPLE = ROOT / 'native-gun-tier-sample-v1.json'
STAR_SAMPLE = ROOT / 'native-blueprint-star-sample-v1.json'
RAW = ROOT / 'native_raw'
CAPTURE_NAMES = ('equip_data', 'equip_origin_data',
                 'item_to_gun_mapping_data', 'gun_blueprint_attr_data')


def _uvar(blob: bytes, offset: int) -> tuple[int, int]:
    value = 0
    for end in range(offset, min(offset + 7, len(blob))):
        byte = blob[end]
        value |= (byte & 127) << (7 * (end - offset))
        if byte < 128:
            return value, end + 1
    raise ValueError('Native integer or offset is incomplete')


def _native_value(blob: bytes, field: dict, kind: str):
    at, raw = field['byte_offset'], bytes.fromhex(field['raw_hex'])
    if not isinstance(at, int) or isinstance(at, bool) or at < 0 or blob[at:at+len(raw)] != raw:
        raise ValueError(f'{kind}: raw byte location conflicts with capture')
    if kind == 'integer':
        value, end = _uvar(blob, at)
        if end != at + len(raw):
            raise ValueError('Native integer width conflict')
    elif kind == 'float32':
        if len(raw) != 4:
            raise ValueError('Native float32 width conflict')
        value = struct.unpack('<f', raw)[0]
    elif kind == 'float64':
        if len(raw) != 8:
            raise ValueError('Native float64 width conflict')
        value = struct.unpack('<d', raw)[0]
    else:
        raise ValueError('Unknown native field type')
    if not isinstance(value, (int, float)) or not math.isfinite(value) or value != field['value']:
        raise ValueError('Native decoded value conflicts with sample')
    return value


def _item_to_gun(blob: bytes) -> dict[int, int]:
    """Follow actual item index pointers, rather than assuming gear ID patterns."""
    if blob[2345] != 11:
        raise ValueError('Native item-to-gun index marker conflict')
    count, at = _uvar(blob, 2346)
    if count != 2371:
        raise ValueError('Native item-to-gun index count conflict')
    at += count * 8
    result = {}
    for _ in range(count):
        gear, at = _uvar(blob, at)
        relative, at = _uvar(blob, at)
        value_at = 18 + relative
        if gear in result or blob[value_at:value_at+2] != b'\x96\x05':
            raise ValueError('Native item-to-gun index/value conflict')
        gun, _ = _uvar(blob, value_at + 2)
        result[gear] = gun
    if at != len(blob) - 1:
        raise ValueError('Native item-to-gun index has trailing bytes')
    return result


def _names(blob: bytes) -> list[str]:
    count = struct.unpack_from('<I', blob)[0]
    if not 0 < count < 10000:
        raise ValueError('Native string count conflict')
    offsets = struct.unpack_from(f'<{count + 1}I', blob, 4)
    if offsets[0] != 0 or any(a > b for a, b in zip(offsets, offsets[1:])):
        raise ValueError('Native string offsets conflict')
    start = 4 + 4 * (count + 1)
    if start + offsets[-1] > len(blob):
        raise ValueError('Native string pool crosses capture')
    return [blob[start + offsets[i]:start + offsets[i+1]].decode()
            for i in range(count)]


def validate(tier_sample: dict, star_sample: dict, captures: dict[str, bytes],
             named_rows: dict) -> dict:
    if (tier_sample.get('schema_version') != 1 or star_sample.get('schema_version') != 1 or
            tier_sample.get('steam_build_id') != '26267212' or
            'final damage formula/configuration remains unverified' not in star_sample.get('status', '')):
        raise ValueError('Native tier/star schema or evidence scope changed')
    hashes = tier_sample['source_literals_sha256']
    hashes = {**hashes, 'gun_blueprint_attr_data': star_sample['source_literal_sha256']}
    for name in CAPTURE_NAMES:
        if name not in captures or hashlib.sha256(captures[name]).hexdigest() != hashes[name]:
            raise ValueError(f'{name}: pinned literal capture hash conflict')
    if (not any(d['native_field'] == 'gun_preset_attack' and d['type_code'] == 18
                for d in tier_sample['origin_descriptor_for_attack']) or
            not any(d['native_field'] == 'preset_attack_radio' and d['type_code'] == 34
                    for d in star_sample['descriptor_fields'])):
        raise ValueError('Native field descriptor conflict')
    by_blueprint = {int(row['blueprint_id']): (identity, row)
                    for identity, row in named_rows.items()}
    if len(by_blueprint) != len(named_rows):
        raise ValueError('Named blueprint identities are ambiguous')
    if len(tier_sample['samples']) != len(by_blueprint) or len(star_sample['records']) != len(by_blueprint):
        raise ValueError('Native sample does not cover the bounded identity set')
    result = {}
    seen_gears = set()
    equip, origin, mapping, attr = (captures[name] for name in CAPTURE_NAMES)
    equip_names, origin_names, attr_names = _names(equip), _names(origin), _names(attr)
    if (equip_names[15] != 'blueprint_no' or equip_names[17] != 'equip_origin_id' or
            origin_names[1] != 'gun_preset_attack' or
            not any(attr_names[attr[at]] == 'preset_attack_radio' and attr[at+1] in (18, 34)
                    for at in range(2187, 2203, 2))):
        raise ValueError('Native descriptor names conflict with captured schema')
    actual_guns = _item_to_gun(mapping)
    for sample in tier_sample['samples']:
        bp = sample['blueprint_id']
        if bp not in by_blueprint or bp in result:
            raise ValueError('Unknown or duplicate native blueprint')
        identity, named = by_blueprint[bp]
        if sample['public_identity_name'] != named['name'] and not (
                identity == 'weapon:qbj97-fiery-trees-and-silver-flowers' and
                sample['public_identity_name'] == 'QBJ97 - Fiery Trees and Silver Flowers'):
            raise ValueError('Native/public weapon name conflict')
        tiers = {}
        if len(sample['tiers']) != 5:
            raise ValueError('Incomplete native tier series')
        for tier in sample['tiers']:
            number, gear, gun = tier['tier'], tier['gear_id'], tier['gun_no']
            page = named['tiers'].get(str(number))
            if (number in tiers or gear in seen_gears or not page or
                    str(gear) != page['item_id'] or
                    gun != sample['shared_gun_no_across_five_tiers'] or
                    actual_guns.get(gear) != gun):
                raise ValueError('Native tier identity conflicts with blueprint Crafts item')
            seen_gears.add(gear)
            at = tier['equip_index_offset']
            indexed_gear, at = _uvar(equip, at)
            relative, at = _uvar(equip, at)
            tag, _ = _uvar(equip, at)
            if (indexed_gear != gear or tag != 1 or
                    92938 + relative != tier['equip_row_start_offset']):
                raise ValueError('Native equipment index/row conflict')
            at = tier['origin_index_offset']
            origin_gear, at = _uvar(origin, at)
            origin_relative, _ = _uvar(origin, at)
            if (origin_gear != gear or 15721 + origin_relative != tier['origin_row_start_offset'] or
                    origin[tier['origin_row_start_offset']:tier['origin_row_start_offset']+2] != b'\x96\x4b'):
                raise ValueError('Native origin index/row conflict')
            for field, expected in (('art_lv', number), ('equip_origin_id', gear),
                                    ('blueprint_no', bp), ('gun_no_field', gun)):
                native = tier[field]
                if not tier['equip_row_start_offset'] <= native['byte_offset'] < tier['equip_row_end_offset_exclusive']:
                    raise ValueError('Native equipment field outside named row')
                if _native_value(equip, native, 'integer') != expected:
                    raise ValueError('Native equipment identity field conflict')
            native_attack = tier['gun_preset_attack']
            if (native_attack['native_field'] != 'gun_preset_attack' or
                    native_attack['type'] != 'float32_le' or
                    not tier['origin_row_start_offset'] < native_attack['byte_offset'] <
                    tier['origin_row_start_offset'] + 40):
                raise ValueError('Native origin attack field scope conflict')
            value = _native_value(origin, native_attack, 'float32')
            if value <= 0:
                raise ValueError('Native origin attack must be positive')
            tiers[number] = {'gear_id': gear, 'gun_no': gun,
                             'gun_preset_attack': value,
                             'byte_offset': native_attack['byte_offset'],
                             'public_page_displayed_dmg': page['damage'],
                             'public_page_url': page['thgl_gear_url'],
                             'matches_public_display_number': value == page['damage']}
        result[bp] = {'catalog_id': identity, 'blueprint_id': bp, 'name': named['name'],
                      'tiers': tiers}
    for sample in star_sample['records']:
        bp = sample['blueprint_id']
        if bp not in result or 'stars' in result[bp] or len(sample['stars']) != 6:
            raise ValueError('Native star record identity or count conflict')
        if sample['name'] != next(row['public_identity_name'] for row in tier_sample['samples']
                                  if row['blueprint_id'] == bp):
            raise ValueError('Native star name conflict')
        stars = {}
        for row in sample['stars']:
            star = row['star']
            if (star in stars or row['blueprint_id'] != bp or row['native_field'] != 'preset_attack_radio' or
                    not 1 <= star <= 6 or row['type_code'] not in (18, 34)):
                raise ValueError('Native star identity or field conflict')
            at = row['record_start_offset']
            record_bp, after_bp = _uvar(attr, at)
            if (record_bp != bp or attr[after_bp] != star or
                    attr[after_bp+1:after_bp+3] != b'\x96\x26' or
                    attr[after_bp+3] != int(row['record_tag_hex'], 16) or
                    attr[row['record_end_marker_offset']:row['record_end_marker_offset']+4]
                    != b'\x15\x17\x16\x04'):
                raise ValueError('Native blueprint/star row marker conflict')
            native = {'byte_offset': row['value_byte_offset'],
                      'raw_hex': row['value_raw_hex'], 'value': row['value']}
            if native['byte_offset'] + len(bytes.fromhex(native['raw_hex'])) != row['record_end_marker_offset']:
                raise ValueError('Native star ratio is not the terminal located field')
            value = _native_value(attr, native,
                                  'float32' if row['type_code'] == 18 else 'float64')
            if not 0 < value <= 2:
                raise ValueError('Native star ratio outside bounded positive range')
            stars[star] = {'preset_attack_radio': value,
                           'byte_offset': row['value_byte_offset'],
                           'source_native_type': row['type_code']}
        result[bp]['stars'] = stars
    if any(set(row['tiers']) != set(range(1, 6)) or set(row['stars']) != set(range(1, 7))
           for row in result.values()):
        raise ValueError('Native item tier/star grid incomplete')
    return {'schema_version': 1, 'steam_build_id': tier_sample['steam_build_id'],
            'source_literal_sha256': hashes, 'by_blueprint': result,
            'counts': {'blueprints': len(result), 'tier_rows': len(seen_gears),
                       'star_rows': sum(len(row['stars']) for row in result.values()),
                       'formula_ready_fields': 0},
            'scope': 'source-native tier and star fields only; no current Attack, damage unit or consumer equation'}


def load_current(named_rows: dict) -> dict:
    tier_sample = json.loads(TIER_SAMPLE.read_text())
    star_sample = json.loads(STAR_SAMPLE.read_text())
    captures = {name: (RAW / f'{name}.literal_bytes.bin').read_bytes()
                for name in CAPTURE_NAMES}
    return validate(tier_sample, star_sample, captures, named_rows)


def selected(report: dict, catalog_id: str, tier: int | None, stars: int | None):
    row = next((value for value in report['by_blueprint'].values()
                if value['catalog_id'] == catalog_id), None)
    if row is None:
        return None
    tier_row = row['tiers'].get(tier) if isinstance(tier, int) and not isinstance(tier, bool) else None
    star_row = row['stars'].get(stars) if isinstance(stars, int) and not isinstance(stars, bool) else None
    return {'catalog_id': catalog_id, 'blueprint_id': row['blueprint_id'],
            'selected_tier': tier, 'selected_stars': stars,
            'gun_preset_attack': tier_row['gun_preset_attack'] if tier_row else None,
            'preset_attack_radio': star_row['preset_attack_radio'] if star_row else None,
            'gear_id': tier_row['gear_id'] if tier_row else None,
            'source_offsets': {'origin_attack': tier_row['byte_offset'] if tier_row else None,
                               'blueprint_star': star_row['byte_offset'] if star_row else None},
            'steam_build_id': report['steam_build_id'],
            'calculation_included': False,
            'unresolved': ('Native consumer equation, damage unit, calibration, mods, '
                           'and crafted Attack are not established')}
