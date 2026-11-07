"""Explicitly gated set-threshold scenarios from the source-attributed packet.

The March 2026 catalog snapshot is a hypothesis for the November game build.
Only descriptors with a complete, named operator are executed here. An earned
threshold whose refresh, rounding, packet eligibility or magnitude is missing
remains unresolved in the caller.
"""
from __future__ import annotations

import json
import math
from pathlib import Path


SOURCE = json.loads((Path(__file__).parent / 'evidence_packets' /
                     'set-threshold-source-v4.json').read_text())
SETS = {row['catalog_id']: row for row in SOURCE['sets']}
POOLS = {'weapon_damage': 'weapon', 'status_damage': 'status',
         'elemental_damage': 'elemental', 'critical_damage': 'crit',
         'critical_rate': 'crit_rate', 'weakspot_damage': 'weakspot',
         'magazine_capacity': 'magazine', 'reload_efficiency': 'reload_efficiency'}
UTILITY = {'head_damage_reduction', 'cold_resistance', 'heat_resistance',
           'heavy_melee_damage', 'torso_damage_reduction', 'rolling_stamina_cost',
           'jump_height', 'max_hp', 'gathering_speed', 'max_load',
           'movement_speed', 'melee_damage', 'status_damage_reduction',
           'incoming_damage', 'tactical_item_damage', 'sprint_speed',
           'stamina_recovery_speed'}
MODES = {'current_release', 'historical_official', 'community_snapshot'}


def _input_number(inputs, key, minimum, maximum):
    value = inputs.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f'{key} must be a finite number from {minimum} to {maximum}')
    return float(value)


def _condition(trigger, hp, inputs):
    if trigger == 'hp_percent_above_70':
        return None if hp is None else hp > .7
    if trigger == 'hp_percent_below_50':
        return None if hp is None else hp < .5
    if trigger == 'stamina_percent_above_90':
        value = _input_number(inputs, 'stamina_fraction', 0, 1)
        return None if value is None else value > .9
    if trigger == 'current_load_above_80':
        value = _input_number(inputs, 'current_load', 0, 1_000_000)
        return None if value is None else value > 80
    if trigger == 'not_spotted_by_enemies':
        value = inputs.get('spotted_by_enemies')
        if value is not None and not isinstance(value, bool):
            raise ValueError('spotted_by_enemies must be true or false')
        return None if value is None else not value
    if trigger == 'ambient_temperature_c_between_10_and_30':
        value = _input_number(inputs, 'ambient_temperature_c', -100, 100)
        # The source does not state whether the endpoints count as between.
        return None if value is None or value in (10, 30) else 10 < value < 30
    if trigger == 'bastille_state_active':
        value = inputs.get('bastille_state_active')
        if value is not None and not isinstance(value, bool):
            raise ValueError('bastille_state_active must be true or false')
        return value
    return None


def _fields(descriptor):
    if descriptor.get('kind') == 'modifier' and descriptor.get('trigger') == 'equipped':
        return [(descriptor.get('stat'), descriptor.get('value_percent', descriptor.get('value')),
                 descriptor.get('unit', 'percent'))]
    if descriptor.get('kind') == 'conditional_modifier':
        if isinstance(descriptor.get('stats'), list):
            return [(row.get('stat'), row.get('value_percent'), 'percent')
                    for row in descriptor['stats']]
        return [(descriptor.get('stat'), descriptor.get('value_percent'), 'percent')]
    return None


def evaluate(counts, encounter_mode, hp_fraction, evidence_mode='current_release', inputs=None):
    """Return pools, applied rows, covered thresholds, and missing inputs.

    `counts` uses catalog set IDs. A false condition covers its threshold with
    zero contribution; an unknown condition leaves the threshold unresolved.
    """
    if evidence_mode not in MODES:
        raise ValueError('Choose current_release, historical_official or community_snapshot set evidence')
    inputs = {} if inputs is None else inputs
    if not isinstance(inputs, dict):
        raise ValueError('Set condition inputs must be an object')
    pools = {name: 0.0 for name in POOLS.values()}
    applied, covered, missing = [], set(), []
    if evidence_mode == 'current_release':
        return pools, applied, covered, missing
    for set_id, count in counts.items():
        source_set = SETS.get('set:' + set_id.replace('_', '-'))
        if source_set is None:
            continue
        for threshold in source_set['thresholds']:
            required = threshold['required_items']
            if required > count:
                continue
            status = threshold['binding_status']
            if status == 'historical_official_release':
                if required not in (1, 3) or set_id != 'bastille_set':
                    continue
            elif status == 'community_snapshot_candidate':
                if evidence_mode != 'community_snapshot':
                    continue
            else:
                continue
            descriptors = threshold.get('descriptors') or []
            # The historical three-piece source also describes entering and
            # leaving Bastille state. Only its explicit active-state Weapon
            # value is a supported outgoing-damage component here.
            if status == 'historical_official_release' and required == 3:
                fields = [('weapon_damage', 40, 'percent')]
            elif not descriptors or any(_fields(row) is None for row in descriptors):
                continue
            else:
                fields = [field for row in descriptors for field in _fields(row)]
            if any(stat not in POOLS and stat not in UTILITY or unit not in ('percent', 'flat') or
                   isinstance(value, bool) or not isinstance(value, (int, float))
                   for stat, value, unit in fields):
                continue
            triggers = {row['trigger'] for row in descriptors
                        if row['kind'] == 'conditional_modifier'}
            if status == 'historical_official_release' and required == 3:
                triggers.add('bastille_state_active')
            outcomes = [_condition(trigger, hp_fraction, inputs) for trigger in triggers]
            rule_id = f'{set_id}:{required}:{status}'
            covered.add((set_id, required))
            if encounter_mode != 'pve_non_raidzone':
                missing.append(f'{rule_id}: source scenario requires explicit PvE non-RaidZone mode')
                continue
            if None in outcomes:
                missing.append(f'{rule_id}: explicit {", ".join(sorted(triggers))} condition required')
                continue
            if False in outcomes:
                continue
            source_ids = threshold.get('source_ids') or []
            refs = [SOURCE['sources'][key].get('url') or SOURCE['sources'][key].get('upstream_repository')
                    for key in source_ids]
            for stat, value, unit in fields:
                pool = POOLS.get(stat)
                if pool and unit != 'percent':
                    missing.append(f'{rule_id}: {stat} is not a percentage pool')
                    continue
                if pool:
                    pools[pool] += float(value)
                applied.append({'rule_id': rule_id, 'set_id': set_id,
                                'required_items': required, 'stat': stat,
                                'pool': pool, 'value': value, 'unit': unit,
                                'percentage_points': value if unit == 'percent' else None,
                                'source_status': status, 'source_refs': refs,
                                'scenario_evidence_mode': evidence_mode})
    return pools, applied, covered, missing
