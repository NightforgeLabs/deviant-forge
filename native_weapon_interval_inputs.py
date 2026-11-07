"""Byte-checked gun-base interval fields for five exact weapon identities.

The native ShootMode numeric enum remains unresolved. These fields are data
inputs, not a selected-weapon RPM until that enum is independently bound.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
from pathlib import Path
import struct

import native_weapon_rate

ROOT = Path(__file__).with_name('evidence_packets')
FIELDS = ROOT / 'native-gun-interval-five-v1.json'
MODES = ROOT / 'native-gun-mode-five-v1.json'
RAW = ROOT / 'native_raw' / 'gun_base_params_data.literal_bytes.bin'
FIELD_SHA256 = 'a5bb8ff21efc947b2194f970730c9dc01878ce158501ed635b8ca96cb657f2ab'
MODE_SHA256 = 'd1fc1e83ad6505d23feea27e2f24040d2c138831f3fdfc4dcfef4fc71f2033ee'
RAW_SHA256 = '7ba048990ee6da61bd37bd82b00e1a11aa8f4df792e429ebae5342a91f505212'
MODE_CONST = ROOT / 'native-shootmode-const-v1.json'
MODE_CONST_SHA256 = '40a1151f0925ab46f3dcfd70d03ba7ca0094e22586fab4edc24e6179c916b289'
FIELD_NAMES = ('auto_time_interval', 'burst_bullet_interval', 'plug_time',
               'single_time_interval', 'burst_bullet_num', 'shoot_time_to_trigger_plug')


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _value(blob, field):
    at = field['byte_offset']
    raw = bytes.fromhex(field['raw_hex'])
    if type(at) is not int or at < 0 or blob[at:at+len(raw)] != raw:
        raise ValueError('Native gun interval byte/offset conflict')
    kind = field['type_code']
    if kind == 18 and len(raw) == 4:
        value = struct.unpack('<f', raw)[0]
    elif kind == 34 and len(raw) == 8:
        value = struct.unpack('<d', raw)[0]
    elif kind == 1 and len(raw) <= 7:
        value = sum((byte & 127) << (index * 7) for index, byte in enumerate(raw))
        if any(byte < 128 for byte in raw[:-1]) or raw[-1] >= 128:
            raise ValueError('Native gun interval varint width conflict')
    else:
        raise ValueError('Native gun interval field type conflict')
    if value != field['value']:
        raise ValueError('Native gun interval decoded value conflict')
    return value


@lru_cache(maxsize=1)
def load():
    for path, expected in ((FIELDS, FIELD_SHA256), (MODES, MODE_SHA256),
                           (RAW, RAW_SHA256), (MODE_CONST, MODE_CONST_SHA256)):
        if _sha(path) != expected:
            raise ValueError('Native gun interval source hash conflict')
    fields = json.loads(FIELDS.read_text())
    modes = json.loads(MODES.read_text())
    constants = json.loads(MODE_CONST.read_text())
    if (constants.get('source_build') != '26267212' or
            constants.get('mapping') != {'SINGLE': 1, 'BURST': 2, 'AUTO': 3} or
            constants.get('class_body', {}).get('body_sha256') !=
            'ddfdd74ca3c5c7e29e532c25f0c78d7c317e78ea438f964d44d49d1d3e1ccf9a'):
        raise ValueError('Native ShootMode constants conflict')
    if (fields.get('installed_build_id') != '26267212' or
            modes.get('installed_build_id') != '26267212' or
            fields.get('source_literal_sha256') != RAW_SHA256 or
            modes.get('source_literal_sha256') != RAW_SHA256 or
            modes.get('typed_interval_packet_sha256') != FIELD_SHA256 or
            len(fields.get('records', [])) != 5 or len(modes.get('records', [])) != 5):
        raise ValueError('Native gun interval source build/packet conflict')
    blob = RAW.read_bytes()
    by_key = {}
    for row in fields['records']:
        key = (row['blueprint_id'], row['gear_id'], row['gun_no'])
        if key in by_key or set(row['native_fields']) != set(FIELD_NAMES):
            raise ValueError('Native gun interval identity/field conflict')
        lower, upper = row['gun_row_bounds']
        if not (0 <= lower < upper <= len(blob)):
            raise ValueError('Native gun interval row bounds conflict')
        values = {}
        for name, field in row['native_fields'].items():
            if not lower <= field['byte_offset'] < upper:
                raise ValueError('Native gun interval field outside row')
            values[name] = _value(blob, field)
        by_key[key] = {'fields': values, 'field_evidence': row['native_fields'],
                       'gun_row_bounds': row['gun_row_bounds']}
    seen = set()
    for row in modes['records']:
        key = (row['blueprint_id'], row['gear_id'], row['gun_no'])
        if key not in by_key or key in seen:
            raise ValueError('Native gun mode identity conflict')
        seen.add(key)
        mode_field = row['adjacent_native_mode_fields']['default_shoot_mode']
        if not by_key[key]['gun_row_bounds'][0] <= mode_field['byte_offset'] < by_key[key]['gun_row_bounds'][1]:
            raise ValueError('Native gun mode outside row')
        by_key[key]['default_shoot_mode_raw'] = _value(blob, mode_field)
        by_key[key]['mode_evidence'] = mode_field
    if len(seen) != len(by_key):
        raise ValueError('Native gun mode row missing')
    return by_key


def selected(native_tier_row, exact_blueprint_rows):
    if native_tier_row is None:
        return None
    blueprint_id = native_tier_row.get('blueprint_id')
    blueprint = exact_blueprint_rows.get(blueprint_id)
    if not blueprint:
        return None
    tier = native_tier_row.get('selected_tier')
    if tier is None or native_tier_row.get('gear_id') is None:
        return None
    selected_tier = blueprint['tiers'].get(tier)
    tier_one = blueprint['tiers'][1]
    if (not selected_tier or selected_tier['gear_id'] != native_tier_row.get('gear_id') or
            selected_tier['gun_no'] != tier_one['gun_no']):
        raise ValueError('Selected native gun tier identity conflict')
    key = (blueprint_id, tier_one['gear_id'], selected_tier['gun_no'])
    row = load().get(key)
    if row is None:
        return None
    modes = {1: 'SINGLE', 2: 'BURST', 3: 'AUTO'}
    mode = modes.get(row['default_shoot_mode_raw'])
    if mode is None:
        raise ValueError('Native default ShootMode not covered by source constants')
    zero_modifier = native_weapon_rate.project({**row['fields'], 'default_shoot_mode': mode}, 0)
    return {'status': 'source_native_base_interval_and_round_argument',
            'blueprint_id': key[0], 'gun_base_source_gear_id': key[1],
            'selected_gear_id': selected_tier['gear_id'], 'gun_no': key[2],
            'fields': row['fields'], 'default_shoot_mode_raw': row['default_shoot_mode_raw'],
            'default_shoot_mode': mode, 'zero_modifier_scenario': zero_modifier,
            'field_evidence': row['field_evidence'], 'mode_evidence': row['mode_evidence'],
            'source_build': '26267212', 'source_sha256': RAW_SHA256,
            'base_rpm_expected': zero_modifier['native_return_expected'],
            'current_equipped_rpm_available': False,
            'missing': ['selected weapon_rpm_add_rate including mods'],
            'scope': 'Source-native base interval and built-in-round fire rate expectation with zero additive RPM modifier; current equipped RPM and final damage remain unknown'}
