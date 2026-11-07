"""One source-pinned PvP OTHER max_hp rate adjustment, not a full PvP model."""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).with_name('evidence_packets')
HASHES = {
    'native-pvp-max-hp-table-v1.json': '0c6c36ea55849b247a558b7c125899464315c575a52230c0c8945f4d11ba9e79',
    'native-survival-pvp-hp-v2.md': '244b549508d0f9794be2e875f91f640e0b7a23ea8ab58637e68e111210a74941',
}
VARIANTS = {'value', 'value_1', 'value_2', 'value_3', 'value_4'}


@lru_cache(maxsize=1)
def proof():
    for name, digest in HASHES.items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Native PvP max_hp table source hash conflict')
    packet = json.loads((ROOT / 'native-pvp-max-hp-table-v1.json').read_text())
    ranges = packet['ranges_in_native_order']
    pairs = [(row['range'][0]['value'], row['range'][1]['value'],
              row['multiplier'], row['addend']) for row in ranges]
    if (packet['source_pyc_sha256'] !=
            '156e21565337a3b2d64ac36709b4be72c0974ac0d3a1ff88734a619866d22604' or
            packet['literal_sha256'] !=
            '74fcb94dfc6b8602ed84ff7377853fdac9b73ef6c4e22962078f2ba266f2a8da' or
            packet['outer_map_key'] != 'max_hp_rate' or
            packet['bracket_rule'] != 'lower < c_rate <= upper' or
            set(packet['variant_fields']) != VARIANTS or
            pairs != [(0.2, 0.4, 1.0, 0.0), (0.6, 10.0, 1.0, 0.0),
                      (0.4, 0.6, 1.0, 0.0)] or
            len(packet['boundary_vectors']) != 25 or
            any(row['output'] != row['rate'] for row in packet['boundary_vectors'])):
        raise ValueError('Native PvP max_hp table structure or coefficients conflict')
    return {'build': '26267212', 'variants': sorted(VARIANTS),
            'source_sha256': HASHES['native-pvp-max-hp-table-v1.json'],
            'consumer_source_sha256': HASHES['native-survival-pvp-hp-v2.md'],
            'scope': 'only the OTHER max_hp rate adjustment in the copied PvP table'}


def adjust(values):
    source = proof()
    if not isinstance(values, dict):
        raise ValueError('PvP max_hp adjustment inputs must be an object')
    missing = []
    if values.get('pvp_adjustment_enabled') is not True:
        missing.append('pvp_adjustment_enabled=true')
    if values.get('player_context') != 'pvp':
        missing.append('player_context=pvp')
    if values.get('property_source_build') != source['build']:
        missing.append('property_source_build=26267212')
    if values.get('pvp_variant') not in VARIANTS:
        missing.append('exact pvp_variant')
    if values.get('pvp_variant_source') not in ('explicit_synthetic', 'confirmed_holder'):
        missing.append('explicit pvp_variant_source')
    if values.get('table_identity_confirmed') is not True:
        missing.append('table_identity_confirmed=true')
    if 'other_rate' not in values:
        missing.append('other_rate')
    if missing:
        return {'status': 'missing_controlled_pvp_max_hp_inputs',
                'adjusted_other_rate': None, 'matched_range': None,
                'missing': missing, 'source_method': source,
                'game_verified': False, 'full_pvp_hp': None}
    rate = values['other_rate']
    if type(rate) not in (int, float) or not math.isfinite(rate):
        raise ValueError('other_rate must be finite numeric input')
    packet = json.loads((ROOT / 'native-pvp-max-hp-table-v1.json').read_text())
    matched = None
    adjusted = rate
    for row in packet['ranges_in_native_order']:
        lower, upper = (value['value'] for value in row['range'])
        if lower < rate <= upper:
            matched = [lower, upper]
            adjusted = row['multiplier'] * rate + row['addend']
            break
    return {'status': 'controlled_pvp_other_max_hp_rate_adjustment',
            'input_other_rate': rate, 'adjusted_other_rate': adjusted,
            'matched_range': matched, 'pvp_variant': values['pvp_variant'],
            'source_method': source, 'game_verified': False,
            'full_pvp_hp': None,
            'scope': 'Identity adjustment in this copied table only; other PvP effects unknown.'}
