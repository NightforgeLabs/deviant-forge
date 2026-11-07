"""Controlled PvE survival ratio and real_max_hp from explicit source inputs."""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path

import native_hp_property_bounds as bounds


ROOT = Path(__file__).with_name('evidence_packets')
HASHES = {
    'native-survival-hp-v1.md': 'a5a8b7cd3d7d78c808809498398699c4a5efcddabb41f65184afab7101c7afc7',
    'native-survival-hp-vectors-v1.json': '153aa62a56ecb0a1e04a00d8791d2382326ee4a315d77c2a85d36e5d98349ce9',
}
NUMBERS = ('max_san', 'san', 'san_hp_ratio', 'base_cap',
           'resistance_rate', 'resistance_limit', 'contamination_resistance')


@lru_cache(maxsize=1)
def proof():
    for name, digest in HASHES.items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Native survival HP source hash conflict')
    packet = json.loads((ROOT / 'native-survival-hp-vectors-v1.json').read_text())
    expected = {'uncapped ratio': 160, 'resistance-lowered cap': 60,
                'upper resistance limit': 80}
    if (len(packet['vectors']) != 3 or packet['pvp_coefficients'] is not None or
            {row['label']: row['real_max_hp'] for row in packet['vectors']} != expected):
        raise ValueError('Native survival HP vector conflict')
    return {'build': bounds.proof()['build'],
            'source_sha256': HASHES['native-survival-hp-v1.md'],
            'vectors_sha256': HASHES['native-survival-hp-vectors-v1.json'],
            'scope': 'controlled player PvE survival helper with resolved config values'}


def _unknown(missing, source):
    return {'status': 'missing_controlled_survival_hp_inputs',
            'effective_cap': None, 'effective_ratio': None,
            'raw_real_max_hp': None, 'real_max_hp': None,
            'missing': list(dict.fromkeys(missing)), 'source_method': source,
            'game_verified': False, 'full_build_dps': None}


def calculate(values):
    """Compute the source expression; never assume live holder or config values."""
    source = proof()
    if not isinstance(values, dict):
        raise ValueError('Controlled survival HP inputs must be an object')
    required = ('max_hp', *NUMBERS, 'config_values_resolved_for_library',
                'config_source', 'player_context', 'property_source_build')
    missing = [name for name in required if name not in values]
    if values.get('config_values_resolved_for_library') is not True:
        missing.append('config_values_resolved_for_library=true')
    if values.get('config_source') not in ('explicit_synthetic', 'verified_library_override',
                                           'verified_player_config', 'verified_defaults_after_absence'):
        missing.append('explicit config_source')
    if values.get('player_context') != 'pve':
        missing.append('player_context=pve')
    if values.get('property_source_build') != source['build']:
        missing.append('property_source_build=26267212')
    if missing:
        return _unknown(missing, source)
    if type(values['max_hp']) is not int or not 1 <= values['max_hp'] <= 999999999:
        raise ValueError('max_hp must be a typed integer within native property bounds')
    for name in NUMBERS:
        if type(values[name]) not in (int, float) or not math.isfinite(values[name]):
            raise ValueError(f'{name} must be finite numeric input')
    cap = values['base_cap'] - min(
        values['resistance_rate'] * values['contamination_resistance'],
        values['resistance_limit'])
    ratio = min((values['max_san'] - values['san']) * values['san_hp_ratio'] / 100,
                cap)
    raw = (1 - ratio) * values['max_hp']
    stored = int(round(round(max(0, min(raw, 999999999)), 6)))
    return {'status': 'controlled_pve_survival_hp',
            'effective_cap': cap, 'effective_ratio': ratio,
            'raw_real_max_hp': raw, 'real_max_hp': stored,
            'config_source': values['config_source'],
            'source_method': source, 'game_verified': False,
            'full_build_dps': None,
            'scope': 'Explicit resolved config/holder inputs; not a live player or named boss HP.'}
