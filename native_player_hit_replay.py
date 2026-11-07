"""Controlled player-hit replay from supplied post-graph damage and state.

The scenario is not an enemy damage model, an equipped Attack lookup, or an
automatic bridge from outgoing bullet damage. Every guard relevant to these
four source-traced branches must be explicitly supplied.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path

import native_shield_settlement as shield
import native_hp_property_bounds as hp_bounds


ROOT = Path(__file__).with_name('evidence_packets')
HASHES = {
    'native-controlled-player-hit-v1.md': '66afaeb2717b5b2ecd5949633dfbcd91bd0a2a3bc22dd32f7a213cb91bb27e48',
    'native-controlled-player-hit-vectors-v1.json': 'b2532556f82c98ddbce028a294a853422fc89dc965e3d10c89114e0838ae79c5',
}
BOOL_FIELDS = (
    'hit_accepted', 'hit_merge_queued', 'be_hit_type_default', 'recognized_shield',
    'shield_invincible_type', 'level_adapter_disabled', 'part_hp_independent',
    'part_damage_overflow', 'missile_hit', 'stun_hit',
    'illusion_damage_ignore_enabled', 'invincibility_check_enabled',
    'holder_avoid_be_hit_non_no', 'part_dam_rate_invincible',
    'player_state_normal', 'damage_share_group_active', 'must_die', 'must_alive',
    'property_forbid_down', 'hp_property_val_type_abs',
    'hp_property_direct_mapping', 'holder_swimming',
    'death_cause_nuclear_bomb', 'avatar_direct_die_flag', 'dying_action_succeeds',
)
NUMBER_FIELDS = (
    'post_graph_damage', 'attenuation_factor', 'shield_hp', 'shield_max_hp',
    'dps_ratio', 'structure_field', 'field_value', 'temp_field_value',
    'sync_rate',
)
INTEGER_FIELDS = (
    'obstruct_nums', 'holder_hp', 'holder_max_hp', 'max_lock_hp',
)
SCENARIO_FIELDS = ('player_server_path_confirmed', 'isolated_hit_no_concurrent_hp_changes',
                   'damage_is_post_graph')


@lru_cache(maxsize=1)
def proof():
    for name, digest in HASHES.items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Controlled player hit source hash conflict')
    packet = json.loads((ROOT / 'native-controlled-player-hit-vectors-v1.json').read_text())
    if (set(packet) != {'shield_excess_no_hp_overflow', 'unshielded_partial_hp',
                        'unshielded_lethal_hp_floor', 'invincibility_blocked'} or
            [packet[key]['output']['actual_hp_damage'] for key in
             ('shield_excess_no_hp_overflow', 'unshielded_partial_hp',
              'unshielded_lethal_hp_floor', 'invincibility_blocked')] != [0, 80, 40, 0]):
        raise ValueError('Controlled player hit vector conflict')
    native = shield.player_proof()
    return {'build': native['build'], 'source_sha256': HASHES['native-controlled-player-hit-v1.md'],
            'vectors_sha256': HASHES['native-controlled-player-hit-vectors-v1.json'],
            'shield_route_sha256': native['source_sha256'],
            'scope': 'synthetic ordinary CompBeHitPlayerServer hit with explicit state'}


def _unknown(missing, source, status='missing_controlled_player_hit_inputs'):
    return {'status': status, 'post_attenuation_damage': None,
            'shield_hp_after': None, 'holder_hp_after': None,
            'reported_real_damage_hp': None, 'actual_hp_damage': None,
            'hp_change_value': None, 'actual_total_damage': None,
            'health_take_damage_called': None,
            'death_action_requested': None, 'missing': list(dict.fromkeys(missing)),
            'source_method': source, 'game_verified': False,
            'full_build_dps': None}


def _numeric(value, name):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f'{name} must be finite numeric input')
    return value


def replay(values):
    """Run one bounded native player-hit branch, or withhold unsupported state."""
    source = proof()
    if not isinstance(values, dict):
        raise ValueError('Controlled player hit inputs must be an object')
    required = (*BOOL_FIELDS, *NUMBER_FIELDS, *INTEGER_FIELDS, *SCENARIO_FIELDS)
    missing = [name for name in required if name not in values]
    if values.get('player_server_path_confirmed') is not True:
        missing.append('player_server_path_confirmed=true')
    if values.get('isolated_hit_no_concurrent_hp_changes') is not True:
        missing.append('isolated_hit_no_concurrent_hp_changes=true')
    if values.get('damage_is_post_graph') is not True:
        missing.append('damage_is_post_graph=true')
    if values.get('recognized_shield') is True:
        if values.get('shield_state') != 'shield_hold':
            missing.append('recognized shield_state=shield_hold')
        if values.get('shield_exists_after_change') is not True:
            missing.append('shield_exists_after_change=true')
    lower, upper, bound_source, bound_missing = hp_bounds.resolve(values)
    missing.extend(bound_missing)
    if missing:
        return _unknown(missing, source)
    for name in (*BOOL_FIELDS, *SCENARIO_FIELDS):
        if type(values[name]) is not bool:
            raise ValueError(f'{name} must be an explicit boolean')
    for name in NUMBER_FIELDS:
        _numeric(values[name], name)
    for name in INTEGER_FIELDS:
        if type(values[name]) is not int:
            raise ValueError(f'{name} must be a whole number')
    if (values['post_graph_damage'] < 0 or values['obstruct_nums'] < 0 or
            not 0 <= values['attenuation_factor'] <= 1 or values['dps_ratio'] < 0 or
            values['sync_rate'] < 0 or values['holder_hp'] < 0 or
            values['holder_max_hp'] < values['holder_hp'] or
            not lower <= values['holder_hp'] <= upper):
        raise ValueError('Controlled player hit numeric state is outside the supplied domain')
    if not values['hit_accepted'] or values['hit_merge_queued']:
        return _unknown(['accepted, unmerged hit'], source,
                        'unsupported_controlled_player_hit_branch')
    guards = []
    if not values['be_hit_type_default']:
        guards.append('DEFAULT hit type')
    if not values['level_adapter_disabled']:
        guards.append('disabled level adaptation')
    if not values['player_state_normal']:
        guards.append('normal living player state')
    for name in ('structure_field', 'field_value', 'temp_field_value',
                 'part_hp_independent', 'part_damage_overflow', 'missile_hit',
                 'stun_hit', 'illusion_damage_ignore_enabled',
                 'damage_share_group_active', 'max_lock_hp', 'must_die',
                 'must_alive', 'property_forbid_down', 'part_dam_rate_invincible'):
        if values[name]:
            guards.append(f'{name}=0/false')
    if not values['hp_property_val_type_abs'] or not values['hp_property_direct_mapping']:
        guards.append('direct ABS HP property mapping')
    if guards:
        return _unknown(guards, source, 'unsupported_controlled_player_hit_branch')
    attenuated = shield.attenuate({'damage_before_attenuation': values['post_graph_damage'],
                                    'attenuation_factor': values['attenuation_factor'],
                                    'obstruct_nums': values['obstruct_nums']})['post_attenuation_damage']
    hp_before = values['holder_hp']
    if values['recognized_shield']:
        branch = shield.evaluate({
            'recognized_held_shield': True, 'shield_state': 'shield_hold',
            'damage_is_post_attenuation': True,
            'post_attenuation_damage': attenuated,
            'current_shield_hp': values['shield_hp'],
            'maximum_shield_hp': values['shield_max_hp'],
            'invincible_shield_type': values['shield_invincible_type'],
            'shield_exists_after_change': True,
            'player_server_path_confirmed': True,
            'isolated_hit_no_concurrent_hp_changes': True})
        return {'status': 'HIT_SHIELD', 'post_attenuation_damage': attenuated,
                'shield_hp_after': branch['shield_hp_after'],
                'shield_crush_and_destroy_event': branch['shield_crush_and_destroy_event'],
                'holder_hp_after': hp_before, 'reported_real_damage_hp': attenuated,
                'actual_hp_damage': 0, 'hp_change_value': 0,
                'actual_total_damage': 0, 'health_take_damage_called': False,
                'death_action_requested': None, 'source_method': source,
                'hp_property_bound_source': bound_source,
                'game_verified': False, 'full_build_dps': None}
    health_input = attenuated * values['dps_ratio'] if values['dps_ratio'] != 1 else attenuated
    if health_input <= 0:
        return {'status': 'FAILURE', 'post_attenuation_damage': attenuated,
                'holder_hp_after': hp_before, 'actual_hp_damage': 0,
                'reported_real_damage_hp': None,
                'health_take_damage_called': True, 'death_action_requested': None,
                'source_method': source, 'game_verified': False, 'full_build_dps': None}
    if values['invincibility_check_enabled'] and values['holder_avoid_be_hit_non_no']:
        return {'status': 'SUCCESS', 'post_attenuation_damage': attenuated,
                'reported_real_damage_hp': 0, 'holder_hp_after': hp_before,
                'actual_hp_damage': 0, 'hp_change_value': 0,
                'actual_total_damage': 0, 'health_take_damage_called': True,
                'death_action_requested': None, 'source_method': source,
                'hp_property_bound_source': bound_source,
                'game_verified': False, 'full_build_dps': None}
    damage_after_sync = max(round(health_input * values['sync_rate']), 1)
    bounded_hp = min(max(hp_before - damage_after_sync, lower), upper)
    hp_after = int(round(round(bounded_hp, 6)))
    actual = max(hp_before - hp_after, 0)
    action = None
    status = 'SUCCESS'
    if hp_after <= 0:
        if (values['holder_swimming'] or values['death_cause_nuclear_bomb'] or
                values['avatar_direct_die_flag']):
            action = 'DIE'
            status = 'death_action_outcome_unresolved'
        elif values['dying_action_succeeds']:
            action = 'DYING (action succeeded; returns KNOCK_DOWN)'
            status = 'KNOCK_DOWN'
        else:
            action = 'DYING failed, then DIE attempted'
            status = 'death_action_outcome_unresolved'
    return {'status': status, 'post_attenuation_damage': attenuated,
            'health_input': health_input, 'damage_after_sync': damage_after_sync,
            'reported_real_damage_hp': health_input,
            'holder_hp_after': hp_after, 'actual_hp_damage': actual,
            'hp_change_value': min(max(hp_before - hp_after, 0), values['holder_max_hp']),
            'actual_total_damage': actual, 'health_take_damage_called': True,
            'death_action_requested': action, 'source_method': source,
            'hp_property_bound_source': bound_source,
            'game_verified': False, 'full_build_dps': None,
            'scope': 'Controlled player hit with explicit state and property bounds, not a live observed hit.'}
