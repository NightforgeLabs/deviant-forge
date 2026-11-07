"""Controlled player max-HP and current-HP revalidation from native channels."""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path

import native_hp_property_bounds as bounds
import native_survival_hp
import native_pvp_max_hp_adjust


ROOT = Path(__file__).with_name('evidence_packets')
HASHES = {
    'native-hp-ceiling-v2.md': '15bae4af9db83b1c0a85312dc81e8cf01710cd186e7156890400be845cfafbc0',
    'native-hp-ceiling-v2-vectors.json': 'c1e42256911ac45903e0eb6b3979717a68ee7bded78918a6623cb27fd03e7ec8',
}
NUMBERS = ('base_init_abs', 'init_abs_change', 'init_rate', 'other_abs',
           'other_rate')
OTHER = ('init_independent_rates', 'other_independent_rates', 'set_value',
         'pvp_max_hp_adjust_enabled', 'holder_has_real_max_hp', 'hp_before')
SCENARIO = ('player_formula_branch_confirmed', 'property_source_build')


@lru_cache(maxsize=1)
def proof():
    for name, digest in HASHES.items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Native player HP ceiling source hash conflict')
    packet = json.loads((ROOT / 'native-hp-ceiling-v2-vectors.json').read_text())
    expected = {'absolute_and_rate': (162, 122, 122),
                'independent_channel_present': (130, 98, 98),
                'set_override': (180, 135, 135)}
    if (set(packet['vectors']) != set(expected) or
            packet['static_controls']['hardcoded_attr_mapping'].get('hp') != 'real_max_hp'):
        raise ValueError('Native player HP ceiling vector conflict')
    for name, outputs in expected.items():
        row = packet['vectors'][name]['output']
        if (row['max_hp_after'], row['real_max_hp_after'],
                row['hp_after_revalidation']) != outputs:
            raise ValueError('Native player HP ceiling vector conflict')
    return {'build': bounds.proof()['build'],
            'source_sha256': HASHES['native-hp-ceiling-v2.md'],
            'vectors_sha256': HASHES['native-hp-ceiling-v2-vectors.json'],
            'scope': 'controlled player max_hp -> real_max_hp -> current hp revalidation'}


def _unknown(missing, source, status='missing_controlled_player_hp_inputs'):
    return {'status': status, 'initial_max_hp_channel': None,
            'raw_max_hp': None, 'max_hp_after': None,
            'real_max_hp_after': None, 'hp_after_revalidation': None,
            'hp_loss_from_ceiling': None, 'missing': list(dict.fromkeys(missing)),
            'source_method': source, 'game_verified': False,
            'full_build_dps': None}


def _abs_bound(value, minimum):
    return int(round(round(min(max(value, minimum), 999999999.0), 6)))


def calculate(values):
    """Calculate only the supplied player branch; never derive live buckets."""
    source = proof()
    if not isinstance(values, dict):
        raise ValueError('Controlled player HP inputs must be an object')
    missing = [name for name in (*NUMBERS, *OTHER, *SCENARIO) if name not in values]
    if values.get('player_formula_branch_confirmed') is not True:
        missing.append('player_formula_branch_confirmed=true')
    if 'survival_inputs' not in values:
        if 'effective_real_san_hp_ratio' not in values:
            missing.append('effective_real_san_hp_ratio')
        if values.get('ratio_is_survival_helper_output') is not True:
            missing.append('ratio_is_survival_helper_output=true')
    elif 'effective_real_san_hp_ratio' in values:
        raise ValueError('Provide survival_inputs or a helper ratio, not both')
    if values.get('property_source_build') != source['build']:
        missing.append('property_source_build=26267212')
    if values.get('holder_has_real_max_hp') is not True:
        missing.append('holder_has_real_max_hp=true')
    pvp_enabled = values.get('pvp_max_hp_adjust_enabled')
    if type(pvp_enabled) is not bool:
        missing.append('explicit pvp_max_hp_adjust_enabled boolean')
    elif pvp_enabled and 'pvp_inputs' not in values:
        missing.append('pvp_inputs for sourced OTHER max_hp rate adjustment')
    elif not pvp_enabled and 'pvp_inputs' in values:
        raise ValueError('pvp_inputs conflict with disabled PvP max_hp adjustment')
    if missing:
        return _unknown(missing, source)
    for name in (*NUMBERS,):
        if type(values[name]) not in (int, float) or not math.isfinite(values[name]):
            raise ValueError(f'{name} must be finite numeric input')
    if type(values['hp_before']) is not int or not 0 <= values['hp_before'] <= 999999999:
        raise ValueError('hp_before must be an integer within the native HP table range')
    for name in ('init_independent_rates', 'other_independent_rates'):
        sequence = values[name]
        if not isinstance(sequence, list):
            raise ValueError(f'{name} must be an explicitly supplied list')
        if any(type(rate) not in (int, float) or not math.isfinite(rate) for rate in sequence):
            raise ValueError(f'{name} must contain finite numeric rates')
    set_value = values['set_value']
    if set_value is not None and (type(set_value) not in (int, float) or not math.isfinite(set_value)):
        raise ValueError('set_value must be finite numeric input or null')
    if 'survival_inputs' not in values:
        ratio = values['effective_real_san_hp_ratio']
        if type(ratio) not in (int, float) or not math.isfinite(ratio):
            raise ValueError('Survival helper output must be finite numeric input')
    adjusted_other_rate = values['other_rate']
    pvp_source = None
    if pvp_enabled:
        pvp_inputs = values['pvp_inputs']
        if not isinstance(pvp_inputs, dict) or 'other_rate' in pvp_inputs:
            raise ValueError('pvp_inputs must be an object without a duplicate other_rate')
        adjustment = native_pvp_max_hp_adjust.adjust({**pvp_inputs,
                                                      'other_rate': values['other_rate']})
        if adjustment['adjusted_other_rate'] is None:
            return _unknown(['pvp_inputs.' + name for name in adjustment['missing']], source)
        adjusted_other_rate = adjustment['adjusted_other_rate']
        pvp_source = adjustment['source_method']
    init_abs = values['base_init_abs'] + values['init_abs_change']
    initial = (init_abs if values['init_independent_rates'] else
               init_abs * (1 + values['init_rate']))
    if set_value is not None:
        raw_max = set_value
    elif values['other_independent_rates']:
        raw_max = initial + values['other_abs']
    else:
        raw_max = (initial + values['other_abs']) * (1 + adjusted_other_rate)
    stored_max = _abs_bound(raw_max, 1)
    if 'survival_inputs' in values:
        survival = values['survival_inputs']
        if not isinstance(survival, dict) or 'max_hp' in survival:
            raise ValueError('survival_inputs must be an object without a duplicate max_hp')
        survival_result = native_survival_hp.calculate({**survival, 'max_hp': stored_max})
        if survival_result['real_max_hp'] is None:
            return _unknown(['survival_inputs.' + name for name in survival_result['missing']],
                            source)
        ratio = survival_result['effective_ratio']
        real_max = survival_result['real_max_hp']
        ratio_source = 'native_pve_resolved_config'
    else:
        real_max = _abs_bound((1 - ratio) * stored_max, 0)
        ratio_source = 'caller_supplied_survival_helper_output'
    hp_after = _abs_bound(max(min(values['hp_before'], real_max), 0), 0)
    return {'status': 'controlled_player_hp_revalidation',
            'initial_max_hp_channel': initial, 'raw_max_hp': raw_max,
            'max_hp_after': stored_max, 'real_max_hp_after': real_max,
            'hp_after_revalidation': hp_after,
            'hp_loss_from_ceiling': max(values['hp_before'] - hp_after, 0),
            'survival_ratio_source': ratio_source,
            'effective_other_max_hp_rate': adjusted_other_rate,
            'pvp_rate_adjustment_source': pvp_source,
            'full_pvp_hp': None,
            'source_method': source, 'game_verified': False,
            'full_build_dps': None,
            'scope': 'Synthetic supplied player channels; not a live equipped HP total.'}
