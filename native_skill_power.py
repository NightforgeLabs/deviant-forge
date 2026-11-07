"""Controlled D41 skill_power aggregation with explicit INIT/OTHER channels."""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).with_name('evidence_packets')
HASHES = {
    'native-skill-power-v1.md': 'e0267e29a05332d7960236e89149d0a69e4df08d03ea86b803453e7b7e5cbf0a',
    'native-skill-power-v1-vectors.json': 'abc630f227f356403c8859c2e911fdbc5e890dabdc2e3368a65047e79d7da09e',
}
CHANNELS = ('base_initial', 'init_abs', 'init_rate', 'init_independent',
            'other_abs', 'other_rate', 'other_independent', 'set_value')
INIT_TYPES = {'INIT', 'EQUIP', 'SUMMON', 'TRANS', 'DUNGEON',
              'SEASON_STAGE_ADJUST', 'DEVIATION_AGE_INIT', 'DUNGEON_MULTI_SCRIPT'}
OTHER_TYPES = {'BUFF', 'PASSIVE', 'MOD'}


@lru_cache(maxsize=1)
def proof():
    for name, digest in HASHES.items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Native D41 source hash conflict')
    packet = json.loads((ROOT / 'native-skill-power-v1-vectors.json').read_text())
    row = packet['source']['D41_row']
    expected = [115, 183.125, 168.75, 135, 250.568, 9999]
    if (row['calc_type'] != 0 or row['val_type'] != 2 or row['min'] != 0 or
            row['max'] != 9999 or len(packet['synthetic_vectors']) != 6 or
            [v['stored_skill_power'] for v in packet['synthetic_vectors']] != expected or
            packet['source']['D41_affix_prototypes']['D4100']['attr_id'] != 'D41'):
        raise ValueError('Native D41 type or vector conflict')
    return {'build': '26267212', 'property_id': 'D41',
            'property_name': 'skill_power',
            'source_sha256': HASHES['native-skill-power-v1.md'],
            'vectors_sha256': HASHES['native-skill-power-v1-vectors.json'],
            'scope': 'player property formula with supplied INIT/OTHER/SET channels'}


def _unknown(missing, source):
    return {'status': 'missing_controlled_D41_inputs',
            'initial_skill_power': None, 'raw_skill_power': None,
            'stored_skill_power': None,
            'missing': list(dict.fromkeys(missing)),
            'source_method': source, 'game_verified': False,
            'active_holder_total_established': False, 'full_build_dps': None}


def source_bucket(source_type):
    """Route only native source types established by this packet."""
    if source_type in INIT_TYPES:
        return 'INIT'
    if source_type in OTHER_TYPES:
        return 'OTHER'
    return None


def calculate(values):
    """Calculate D41 only when every channel and its scenario scope is explicit."""
    source = proof()
    if not isinstance(values, dict):
        raise ValueError('Controlled D41 inputs must be an object')
    required = (*CHANNELS, 'property_source_build', 'property_id',
                'base_initial_source', 'channel_values_explicit',
                'active_source_map_complete')
    missing = [name for name in required if name not in values]
    if values.get('property_source_build') != source['build']:
        missing.append('property_source_build=26267212')
    if values.get('property_id') != 'D41':
        missing.append('property_id=D41')
    if values.get('base_initial_source') not in (
            'explicit_synthetic', 'confirmed_holder_table', 'confirmed_combat_unit',
            'generic_table_fallback_hypothesis'):
        missing.append('explicit base_initial_source')
    if values.get('channel_values_explicit') is not True:
        missing.append('channel_values_explicit=true')
    if values.get('active_source_map_complete') is not True:
        missing.append('active_source_map_complete=true')
    if missing:
        return _unknown(missing, source)
    for name in ('base_initial', 'init_abs', 'init_rate', 'other_abs', 'other_rate'):
        if type(values[name]) not in (int, float) or not math.isfinite(values[name]):
            raise ValueError(f'{name} must be finite numeric input')
    for name in ('init_independent', 'other_independent'):
        entries = values[name]
        if not isinstance(entries, list) or any(
                type(rate) not in (int, float) or not math.isfinite(rate)
                for rate in entries):
            raise ValueError(f'{name} must be an explicitly supplied finite numeric list')
    set_value = values['set_value']
    if set_value is not None and (type(set_value) not in (int, float) or
                                  not math.isfinite(set_value)):
        raise ValueError('set_value must be finite numeric input or null')
    init_abs_total = values['base_initial'] + values['init_abs']
    initial = (init_abs_total if values['init_independent'] else
               init_abs_total * (1 + values['init_rate']))
    if set_value is not None:
        raw = set_value
        branch = 'SET_override'
    elif values['other_independent']:
        raw = initial + values['other_abs']
        branch = 'OTHER_independent_bypasses_rate'
    else:
        raw = (initial + values['other_abs']) * (1 + values['other_rate'])
        branch = 'ordinary_INIT_OTHER'
    stored = round(round(min(max(raw, 0), 9999), 6), 3)
    return {'status': 'controlled_D41_skill_power',
            'initial_skill_power': initial, 'raw_skill_power': raw,
            'stored_skill_power': stored, 'selected_branch': branch,
            'source_buckets': {'EQUIP': 'INIT', 'BUFF': 'OTHER',
                               'PASSIVE': 'OTHER', 'MOD': 'OTHER'},
            'source_method': source, 'game_verified': False,
            'active_holder_total_established': False,
            'full_build_dps': None,
            'scope': 'Supplied channels only; no owned equipment activation or holder map inferred.'}
