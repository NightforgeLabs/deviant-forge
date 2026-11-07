"""Exact-identity admission of bounded native interval rows.

The source packet has 55 typed rows; only rows also backed by an installed
numeric weapon identity are active. This module checks raw bytes and the
independent item→gun index before returning a zero-modifier base-rate scenario.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
from pathlib import Path

import native_tier_star
import native_weapon_interval_inputs as first_five
import native_weapon_rate

ROOT = Path(__file__).with_name('evidence_packets')
PACKET = ROOT / 'native-gun-interval-expanded-v1.json'
PACKET_SHA256 = '5dea2e2f4593c0db938a6549298783811b515b9e1899e6012829a68b344c8fb4'
RAW = ROOT / 'native_raw' / 'gun_base_params_data.literal_bytes.bin'
RAW_SHA256 = first_five.RAW_SHA256
ITEM_INDEX = ROOT / 'native_raw' / 'item_to_gun_mapping_data.literal_bytes.bin'
ITEM_INDEX_SHA256 = '4e9620f90570b18d73d5a9bda2253bd21a6383983dadc783e22aa337ef32cdeb'
FIELD_NAMES = set(first_five.FIELD_NAMES) | {'burst_time_interval', 'default_shoot_mode'}


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@lru_cache(maxsize=1)
def load():
    for path, expected in ((PACKET, PACKET_SHA256), (RAW, RAW_SHA256),
                           (ITEM_INDEX, ITEM_INDEX_SHA256)):
        if _sha(path) != expected:
            raise ValueError('Expanded native interval source hash conflict')
    packet = json.loads(PACKET.read_text())
    if (packet.get('installed_build_id') != '26267212' or
            packet.get('source_hashes', {}).get('gun_base_literal_sha256') != RAW_SHA256 or
            packet.get('coverage', {}).get('bounded_typed_interval_and_mode_rows') != 55 or
            len(packet.get('records', [])) != 55 or
            len(packet.get('withheld', [])) != 33):
        raise ValueError('Expanded native interval build or coverage conflict')
    first = first_five.load()  # includes the independently checked ShootMode constants
    blob = RAW.read_bytes()
    item_to_gun = native_tier_star._item_to_gun(ITEM_INDEX.read_bytes())
    by_catalog = {}
    for row in packet['records']:
        identity = row['forge_id']
        if identity in by_catalog or set(row['native_fields']) != FIELD_NAMES:
            raise ValueError('Expanded native interval duplicate identity or field conflict')
        lower, upper = row['gun_row_bounds']
        if (not 0 <= lower < upper <= len(blob) or
                item_to_gun.get(row['tier_one_gear_id']) != row['gun_no']):
            raise ValueError('Expanded native interval row or item→gun index conflict')
        fields = {}
        for name, evidence in row['native_fields'].items():
            if not lower <= evidence['byte_offset'] < upper:
                raise ValueError('Expanded native interval field outside exact gun row')
            fields[name] = first_five._value(blob, evidence)
        if fields['default_shoot_mode'] not in (1, 2, 3):
            raise ValueError('Expanded native ShootMode outside proven enum')
        overlap = first.get((row['blueprint_id'], row['tier_one_gear_id'], row['gun_no']))
        if overlap and (any(fields[name] != overlap['fields'][name] for name in first_five.FIELD_NAMES) or
                        fields['default_shoot_mode'] != overlap['default_shoot_mode_raw']):
            raise ValueError('Expanded native interval conflicts with first five source rows')
        by_catalog[identity] = {'source_row': row, 'fields': fields}
    return {'by_catalog': by_catalog, 'item_to_gun': item_to_gun,
            'source_packet_sha256': PACKET_SHA256, 'source_build': '26267212'}


def selected(native_tier_row):
    if native_tier_row is None:
        return None
    report = load()
    identity = native_tier_row.get('catalog_id')
    bound = report['by_catalog'].get(identity)
    if bound is None:
        return None
    source = bound['source_row']
    if (native_tier_row.get('steam_build_id') != report['source_build'] or
            native_tier_row.get('blueprint_id') != source['blueprint_id']):
        raise ValueError('Expanded native interval blueprint identity conflict')
    # A source-name proposal alone is insufficient. Require the already
    # accepted numeric origin-Attack row for this exact Forge identity.
    if (native_tier_row.get('gun_preset_attack') is None or
            native_tier_row.get('source_offsets', {}).get('origin_attack') is None):
        return None
    selected_gear = native_tier_row.get('gear_id')
    if selected_gear is None:
        return None
    if report['item_to_gun'].get(selected_gear) != source['gun_no']:
        raise ValueError('Expanded native interval selected tier→gun conflict')
    fields = bound['fields']
    mode = {1: 'SINGLE', 2: 'BURST', 3: 'AUTO'}[fields['default_shoot_mode']]
    zero_modifier = native_weapon_rate.project({**fields, 'default_shoot_mode': mode}, 0)
    return {'status': 'source_native_base_interval_and_round_argument',
            'catalog_id': identity, 'blueprint_id': source['blueprint_id'],
            'gun_base_source_gear_id': source['tier_one_gear_id'],
            'selected_gear_id': selected_gear, 'gun_no': source['gun_no'],
            'fields': fields, 'default_shoot_mode_raw': fields['default_shoot_mode'],
            'default_shoot_mode': mode, 'zero_modifier_scenario': zero_modifier,
            'field_evidence': source['native_fields'],
            'source_build': report['source_build'],
            'source_sha256': RAW_SHA256, 'source_packet_sha256': PACKET_SHA256,
            'base_rpm_expected': zero_modifier['native_return_expected'],
            'current_equipped_rpm_available': False,
            'missing': ['selected weapon_rpm_add_rate including mods'],
            'scope': 'Source-native base interval and built-in-round fire rate expectation with zero additive RPM modifier; current equipped RPM and final damage remain unknown'}
