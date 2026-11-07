"""Bounded monster/NPC hit replay from explicit post-graph damage and state.

This source-traced path never infers a named boss's HP, shield, component class,
or a complete outgoing-damage/DPS result from catalog identity.
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
    'native-npc-hit-v1.md': '663424d3748ad99bf79f220a6489981a5a5d3c523efb825d28acd3ecfcef3889',
    'native-npc-hit-vectors-v1.json': '59d3326a648577f409f5c65de3a475ea570260364cbde30b4256e786bae30aca',
}
BOOL_FIELDS = (
    'animal_anesthetic_intercept', 'hit_accepted', 'hit_merge_queued',
    'be_hit_type_default', 'recognized_held_shield', 'shield_invincible_type',
    'npc_state_dead', 'level_adapter_disabled', 'part_hp_independent',
    'part_damage_overflow', 'invincibility_check_enabled',
    'holder_avoid_be_hit_non_no', 'damage_share_group_active', 'must_die',
    'must_alive', 'property_forbid_down', 'hp_property_val_type_abs',
    'hp_property_direct_mapping', 'has_on_dying_event_trigger',
)
NUMBER_FIELDS = (
    'post_graph_damage', 'attenuation_factor', 'shield_hp', 'shield_max_hp',
    'dps_ratio', 'structure_field', 'field_value', 'temp_field_value',
    'sync_rate',
)
INTEGER_FIELDS = (
    'obstruct_nums', 'npc_hp', 'npc_max_hp', 'max_lock_hp',
)
SCENARIO_FIELDS = (
    'monster_component_binding_confirmed', 'npc_health_component_confirmed',
    'isolated_hit_no_concurrent_hp_changes', 'damage_is_post_graph',
)


@lru_cache(maxsize=1)
def proof():
    for name, digest in HASHES.items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Controlled NPC hit source hash conflict')
    packet = json.loads((ROOT / 'native-npc-hit-vectors-v1.json').read_text())
    if (set(packet) != {'ordinary_monster_partial_hp',
                        'monster_lethal_with_dying_trigger',
                        'monster_shield_excess_no_hp_overflow'} or
            [packet[key]['output']['actual_hp_damage'] for key in
             ('ordinary_monster_partial_hp', 'monster_lethal_with_dying_trigger',
              'monster_shield_excess_no_hp_overflow')] != [80, 40, 0]):
        raise ValueError('Controlled NPC hit vector conflict')
    return {'build': shield.proof()['build'],
            'source_sha256': HASHES['native-npc-hit-v1.md'],
            'vectors_sha256': HASHES['native-npc-hit-vectors-v1.json'],
            'scope': 'synthetic CompBeHitMonsterServer to CompHealthNpcServer hit'}


def _unknown(missing, source, status='missing_controlled_npc_hit_inputs'):
    return {'status': status, 'post_attenuation_damage': None,
            'shield_hp_after': None, 'npc_hp_after': None,
            'reported_real_damage_hp': None, 'actual_hp_damage': None,
            'hp_change_value': None, 'actual_total_damage': None,
            'health_take_damage_called': None,
            'missing': list(dict.fromkeys(missing)), 'source_method': source,
            'game_verified': False, 'named_boss_binding': None,
            'full_build_dps': None}


def replay(values):
    """Replay only a fully specified ordinary monster/NPC branch."""
    source = proof()
    if not isinstance(values, dict):
        raise ValueError('Controlled NPC hit inputs must be an object')
    required = (*BOOL_FIELDS, *NUMBER_FIELDS, *INTEGER_FIELDS, *SCENARIO_FIELDS)
    missing = [name for name in required if name not in values]
    for name in SCENARIO_FIELDS:
        if values.get(name) is not True:
            missing.append(name + '=true')
    if values.get('recognized_held_shield') is True:
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
        value = values[name]
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError(f'{name} must be finite numeric input')
    for name in INTEGER_FIELDS:
        if type(values[name]) is not int:
            raise ValueError(f'{name} must be a whole number')
    if (values['post_graph_damage'] < 0 or values['obstruct_nums'] < 0 or
            not 0 <= values['attenuation_factor'] <= 1 or
            values['dps_ratio'] < 0 or values['sync_rate'] < 0 or
            values['npc_hp'] < 0 or values['npc_max_hp'] < values['npc_hp'] or
            not lower <= values['npc_hp'] <= upper or
            values['shield_hp'] < 0 or values['shield_max_hp'] < values['shield_hp']):
        raise ValueError('Controlled NPC hit numeric state is outside supplied domain')
    guards = []
    if values['animal_anesthetic_intercept'] or not values['hit_accepted'] or values['hit_merge_queued']:
        guards.append('accepted, unmerged, non-anesthetic hit')
    if not values['be_hit_type_default']:
        guards.append('DEFAULT hit type')
    if not values['level_adapter_disabled']:
        guards.append('disabled level adaptation')
    if values['npc_state_dead'] or values['npc_hp'] <= 0:
        guards.append('living NPC with positive HP')
    for name in ('structure_field', 'field_value', 'temp_field_value',
                 'part_hp_independent', 'part_damage_overflow',
                 'damage_share_group_active', 'max_lock_hp', 'must_die',
                 'must_alive', 'property_forbid_down'):
        if values[name]:
            guards.append(name + '=0/false')
    if values['invincibility_check_enabled'] and values['holder_avoid_be_hit_non_no']:
        guards.append('NPC invincibility branch')
    if not values['hp_property_val_type_abs'] or not values['hp_property_direct_mapping']:
        guards.append('direct ABS HP property mapping')
    if guards:
        return _unknown(guards, source, 'unsupported_controlled_npc_hit_branch')
    attenuated = shield.attenuate({
        'damage_before_attenuation': values['post_graph_damage'],
        'attenuation_factor': values['attenuation_factor'],
        'obstruct_nums': values['obstruct_nums'],
    })['post_attenuation_damage']
    if values['recognized_held_shield']:
        shield_after = (values['shield_hp'] if values['shield_invincible_type'] else
                        min(max(values['shield_hp'] - attenuated, 0), values['shield_max_hp']))
        return {'status': 'HIT_SHIELD', 'post_attenuation_damage': attenuated,
                'reported_real_damage_hp': attenuated, 'shield_hp_after': shield_after,
                'npc_hp_after': values['npc_hp'], 'actual_hp_damage': 0,
                'hp_change_value': 0, 'actual_total_damage': 0,
                'health_take_damage_called': False, 'source_method': source,
                'hp_property_bound_source': bound_source,
                'game_verified': False, 'named_boss_binding': None,
                'full_build_dps': None}
    health_input = (attenuated * values['dps_ratio'] if values['dps_ratio'] != 1
                    else attenuated)
    if health_input <= 0:
        return _unknown(['positive health input'], source,
                        'unsupported_controlled_npc_hit_branch')
    after_sync = max(round(health_input * values['sync_rate']), 1)
    bounded = min(max(values['npc_hp'] - after_sync, lower), upper)
    hp_after = int(round(round(bounded, 6)))
    actual = max(values['npc_hp'] - hp_after, 0)
    status = ('SUCCESS' if hp_after > 0 else
              'KNOCK_DOWN_NPC' if values['has_on_dying_event_trigger'] else
              'DIE_action_and_kill_type_unmodeled')
    return {'status': status, 'post_attenuation_damage': attenuated,
            'health_input': health_input, 'damage_after_sync': after_sync,
            'reported_real_damage_hp': health_input, 'npc_hp_after': hp_after,
            'actual_hp_damage': actual,
            'hp_change_value': min(actual, values['npc_max_hp']),
            'actual_total_damage': actual, 'health_take_damage_called': True,
            'source_method': source, 'game_verified': False,
            'hp_property_bound_source': bound_source,
            'named_boss_binding': None, 'full_build_dps': None}
