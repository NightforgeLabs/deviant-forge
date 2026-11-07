"""Offline client Gear Attack preview for explicitly complete synthetic inputs.

This models only typed D0100/D0101 Attack affixes. It never obtains an owned
weapon, holder change map, equipped Attack, or final damage from a build.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).with_name('evidence_packets')
SOURCE_HASHES = {
    'synthetic-gear-preview-reference-v1.md': '1272f381a8daa38af5428ebaf6b6d7e9c2f71a0d0e48fdcf59b0ea2faddcdac1',
    'synthetic-gear-preview-vectors-v1.json': 'cf04bd32d754240ccc09abb33009b366d463db9514f35291f512b549ace4bf37',
}
CHANNEL = {'D0100': 'abs', 'D0101': 'rate'}
SOURCE_GROUP = {'3': 'init', '13': 'other'}


@lru_cache(maxsize=1)
def proof():
    for name, digest in SOURCE_HASHES.items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Synthetic Gear preview evidence hash conflict')
    vectors = json.loads((ROOT / 'synthetic-gear-preview-vectors-v1.json').read_text())
    if (vectors['game_code_executed'] is not False or
            [(x['name'], x['raw'], x['display']) for x in vectors['weapon_preview_vectors']] !=
            [('replace_abs', 220, 220), ('replace_abs_and_rate', 287.5, 288)]):
        raise ValueError('Synthetic Gear preview vector conflict')
    return {'kind': 'handwritten_offline_model_of_traced_client_methods',
            'reference_sha256': SOURCE_HASHES['synthetic-gear-preview-reference-v1.md'],
            'vectors_sha256': SOURCE_HASHES['synthetic-gear-preview-vectors-v1.json'],
            'native_affixes': ['D0100', 'D0101'], 'property': 'D01 attack',
            'source_groups': {'3': 'init', '13': 'other'}}


def _number(value, label):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f'{label} must be a finite number')
    return value


def _changes(value):
    if not isinstance(value, dict) or set(value) != {'abs', 'rate'}:
        raise ValueError('holder_changes requires only abs and rate channels')
    out = {}
    for channel in ('abs', 'rate'):
        groups = value[channel]
        if not isinstance(groups, dict) or set(groups) != {'init', 'other'}:
            raise ValueError('holder_changes requires init and other source groups')
        out[channel] = {}
        for group in ('init', 'other'):
            attrs = groups[group]
            if not isinstance(attrs, dict) or set(attrs) - {'attack'}:
                raise ValueError('Only D01 Attack holder changes are modeled')
            out[channel][group] = _number(attrs.get('attack', 0), 'Attack holder change')
    return out


def _affix_map(value, label):
    if not isinstance(value, dict):
        raise ValueError(f'{label} must be a source-type map')
    out = {'init': {'abs': 0, 'rate': 0}, 'other': {'abs': 0, 'rate': 0}}
    for source_type, affixes in value.items():
        group = SOURCE_GROUP.get(str(source_type))
        if group is None or not isinstance(affixes, dict):
            raise ValueError(f'{label} has an unsupported source type')
        for affix_id, amount in affixes.items():
            if affix_id not in CHANNEL:
                raise ValueError(f'{label} has an unsupported Attack affix')
            out[group][CHANNEL[affix_id]] += _number(amount, f'{label} {affix_id}')
    return out


def independent_rate(value, rates, calc_type, val_type):
    """Traced rate-addition helper, for independent controls only."""
    value = _number(value, 'independent base')
    if not isinstance(rates, list) or calc_type not in (1, 2) or val_type not in (1, 2):
        raise ValueError('Unsupported independent rate operation')
    factor = 1
    for rate in rates:
        rate = _number(rate, 'independent rate')
        factor *= 1 + rate if calc_type == 1 else 1 - rate
    if val_type == 1:
        return value * factor
    return (1 + value) * factor - 1 if calc_type == 1 else 1 - (1 - value) * factor


def base_formula(initial, absolute, rate, independent=None, set_override=None):
    """Traced default/set/independent branch for an absolute property."""
    if set_override is not None:
        return _number(set_override, 'set override')
    value = _number(initial, 'initial') + _number(absolute, 'absolute')
    if independent:
        return independent_rate(value, independent, 1, 1)
    return value * (1 + _number(rate, 'rate'))


def adjust_absolute(value):
    """D01 clamp, six-place rounding, then Python half-even integer round."""
    return int(round(round(min(max(_number(value, 'Attack'), 0), 130000), 6)))


def project(scenario, selected_weapon_id=None):
    """Replace synthetic held weapon affixes in a complete synthetic snapshot.

    The outcome is a client Gear preview model, never an equipped or final-hit
    value. Identity mismatch and incomplete snapshots withhold numeric output.
    """
    source = proof()
    if not isinstance(scenario, dict) or scenario.get('scenario_kind') != 'synthetic_client_gear_preview':
        raise ValueError('Only explicitly synthetic Gear preview scenarios are accepted')
    weapon_id = scenario.get('weapon_id')
    if not isinstance(weapon_id, str) or not weapon_id:
        raise ValueError('A selected weapon identity is required')
    missing = []
    if weapon_id != selected_weapon_id:
        missing.append('selected weapon identity differs from the scenario')
    if scenario.get('complete_synthetic_holder_map') is not True:
        missing.append('complete synthetic holder change map')
    if scenario.get('other_channels_absent') is not True:
        missing.append('absence of SET, independent, linked-maximum and other affix channels')
    for key in ('holder_changes', 'held_affixes', 'selected_affixes'):
        if key not in scenario:
            missing.append(key)
    if missing:
        return {'status': 'incomplete_synthetic_preview', 'display_attack': None,
                'raw_attack': None, 'missing': missing, 'source_method': source,
                'scenario_only': True, 'equipped_attack_verified': False}
    changes = _changes(scenario['holder_changes'])
    old = _affix_map(scenario['held_affixes'], 'held_affixes')
    selected = _affix_map(scenario['selected_affixes'], 'selected_affixes')
    # Old affixes are removed from their original init/other buckets. The
    # selected affix IDs are summed across source types and tagged GUN_CORE/other.
    init_abs = changes['abs']['init'] - old['init']['abs']
    init_rate = changes['rate']['init'] - old['init']['rate']
    other_abs = changes['abs']['other'] - old['other']['abs']
    other_rate = changes['rate']['other'] - old['other']['rate']
    incoming_abs = selected['init']['abs'] + selected['other']['abs']
    incoming_rate = selected['init']['rate'] + selected['other']['rate']
    initial = init_abs * (1 + init_rate)
    absolute = other_abs + incoming_abs
    rate = other_rate + incoming_rate
    raw = base_formula(initial, absolute, rate)
    return {'status': 'synthetic_client_gear_preview', 'display_attack': adjust_absolute(raw),
            'raw_attack': raw, 'equation_inputs': {'init': initial, 'abs': absolute, 'rate': rate},
            'replacement': {'held_init_abs_removed': old['init']['abs'],
                            'held_init_rate_removed': old['init']['rate'],
                            'held_other_abs_removed': old['other']['abs'],
                            'held_other_rate_removed': old['other']['rate'],
                            'selected_other_abs_added': incoming_abs,
                            'selected_other_rate_added': incoming_rate},
            'missing': [], 'source_method': source, 'scenario_only': True,
            'equipped_attack_verified': False,
            'not_included': ['actual holder change map', 'server equipped Attack',
                             'hit damage', 'damage per second']}
