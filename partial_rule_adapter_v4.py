"""Compute only safe components of v2 partial main-mod rules.

Returned `unresolved` always remains nonempty. Outputs are not the complete
effect and must not be promoted to a whole-build comparison.
"""
from __future__ import annotations

from evaluate_template_v3 import UnknownCombatState
from exact_effect_adapter_v4 import execute, need, stat

REUSED={
    'safe_haven_partial','event_modifier_duration_unknown',
    'base_plus_hp_cost_timed_stack_partial','base_plus_unknown_curve',
    'distance_scaling_partial',
}
NEW={
    'previous_magazine_event_counter','weapon_switch_decay_partial',
    'base_plus_hp_threshold_partial','heal_on_event',
    'resource_recovery_on_event','distance_triggered_ammo_partial',
    'previous_magazine_rate_conversion_partial','stat_conversion',
}
EXECUTABLE=REUSED|NEW


def execute_partial(rule: dict, context: dict) -> dict:
    op=rule['operator']
    if op not in EXECUTABLE:raise NotImplementedError(op)
    if op in REUSED:
        answer=execute(rule,context)
        if not answer['unresolved']:
            raise AssertionError('partial operator missing unresolved mechanics')
        return answer
    n=rule['nodes'];out=[];unresolved=list(rule.get('unresolved',[]))
    if op=='previous_magazine_event_counter':
        reloaded=need(context,'just_reloaded')
        if reloaded:
            count=need(context,'previous_magazine_elemental_damage_instances')
            if not isinstance(count,int) or count<0:raise ValueError('invalid event count')
            node=n[0];bonus=min(count*node['value_per_event'],node['max_bonus_percent'])
            out.append(stat(node['stat'],bonus,event='reload',duration_seconds=rule['duration_seconds'],
                            previous_magazine_instances=count))
    elif op=='weapon_switch_decay_partial':
        switched=need(context,'just_switched_weapon')
        if switched:
            elapsed=need(context,'elapsed_seconds_since_switch')
            if elapsed!=0:raise UnknownCombatState('decay_basis_after_switch')
            out += [stat(x['stat'],x['value'],event='weapon_switch',elapsed_seconds=0) for x in n]
    elif op=='base_plus_hp_threshold_partial':
        out += [stat(x['stat'],x['value']) for x in n]
    elif op=='heal_on_event':
        killed=need(context,'defeated_burning_enemy')
        if killed:out.append({'type':'heal_percent_unbound_basis','value_percent':n[0]['value'],
                              'event':'defeated_burning_enemy'})
    elif op=='resource_recovery_on_event':
        killed=need(context,'defeated_marked_enemy')
        if killed:
            out += [{'type':x['op']+'_unbound_basis','value_percent':x['value'],
                     'event':'defeated_marked_enemy'} for x in n]
    elif op=='distance_triggered_ammo_partial':
        qualifies=need(context,'qualifying_distant_weakspot_hit')
        if qualifies:out.append({'type':'ammo_refill_percent_request','value_percent':n[0]['value'],
                                 'source':'unknown','cooldown_seconds':rule['cooldown_seconds']})
    elif op=='previous_magazine_rate_conversion_partial':
        reloaded=need(context,'just_reloaded')
        if reloaded:
            rate=need(context,'previous_magazine_weakspot_hit_rate_percent')
            node=n[0];steps=rate/node['input_step']
            if not 0<=rate<=100:raise ValueError('invalid weakspot rate')
            if abs(steps-round(steps))>1e-9:raise UnknownCombatState('rate_step_rounding')
            bonus=min(round(steps)*node['value_per_step'],node['max_bonus_percent'])
            out.append(stat(node['stat'],bonus,event='reload',duration_seconds=rule['duration_seconds'],
                            previous_magazine_weakspot_rate_percent=rate))
    elif op=='stat_conversion':
        rate=need(context,'crit_rate_percent')
        node=n[0];steps=rate/node['input_step']
        if rate<0:raise ValueError('invalid crit rate')
        if abs(steps-round(steps))>1e-9:raise UnknownCombatState('rounding_policy')
        out.append(stat(node['output_stat'],round(steps)*node['output_per_step'],
                        source_stat=node['input_stat'],source_value_percent=rate))
    if not unresolved:
        unresolved={
            'heal_on_event':['hp_basis'],
            'resource_recovery_on_event':['hp_and_stamina_basis'],
            'stat_conversion':['rounding_policy'],
        }.get(op,['operator_completion_not_established'])
    return {'outputs':out,'unresolved':unresolved,'whole_dps_certified':False}
