"""Bounded first-step/event outputs for four previously descriptor-only families.

Do not use for current-level comparisons without an exact identity/level binding.
Unknown caps, decay curves and blast geometry remain unresolved.
"""
from evaluate_template_v3 import UnknownCombatState
from exact_effect_adapter_v4 import need, stat
from partial_rule_adapter_v4 import EXECUTABLE as V4_EXECUTABLE, execute_partial as execute_v4

ADDED={
    'bomb_hit_counter_partial','shrapnel_special_hit_partial',
    'decaying_final_damage_partial','hp_loss_conversion_partial',
}
EXECUTABLE=V4_EXECUTABLE|ADDED


def execute_partial(rule:dict,context:dict)->dict:
    op=rule['operator']
    if op in V4_EXECUTABLE:return execute_v4(rule,context)
    if op not in ADDED:raise NotImplementedError(op)
    node=rule['nodes'][0];out=[]
    if op=='bomb_hit_counter_partial':
        hits=need(context,'qualified_hits_for_this_bomb')
        step=node['hits_per_step']
        if not isinstance(hits,int) or hits<0:raise ValueError('invalid hit count')
        if hits>step:raise UnknownCombatState('maximum_bonus_and_counter_scope_after_first_step')
        if hits==step:
            out.append({'type':'final_damage_bonus_percent','ability':'unstable_bomber',
                        'percentage_points':node['value_per_step'],
                        'qualified_hits':hits,'scope':'first_complete_step_only'})
    elif op=='shrapnel_special_hit_partial':
        ordinal=need(context,'shrapnel_ordinal')
        if not isinstance(ordinal,int) or ordinal<1:raise ValueError('invalid shrapnel ordinal')
        if ordinal==node['ordinal']:
            out.append({'type':'special_damage_event_descriptor','ability':'shrapnel',
                        'damage_bonus_percent':node['damage_bonus_percent'],
                        'guaranteed_critical':node['guaranteed_critical'],
                        'explosive':node['explosive'],'explosion_radius_meters':'unknown',
                        'explosion_target_count':'unknown'})
    elif op=='decaying_final_damage_partial':
        seconds=need(context,'seconds_since_effect_start')
        if seconds<0:raise ValueError('negative time')
        if seconds>0:raise UnknownCombatState('decay_basis')
        out.append({'type':'final_damage_bonus_percent','ability':'frost_vortex',
                    'percentage_points':node['value'],'time_seconds':0})
    elif op=='hp_loss_conversion_partial':
        loss=need(context,'qualified_hp_loss_percent')
        if loss<0:raise ValueError('negative HP loss')
        step=node['hp_loss_step_percent']
        if loss>step:raise UnknownCombatState('maximum_stack_or_cap_after_first_step')
        if 0<loss<step:raise UnknownCombatState('rounding_at_step_boundary')
        if loss==step:
            out += [stat(s,node['value_per_step_percent'],
                         qualifying_hp_loss_percent=loss,scope='first_complete_step_only')
                    for s in node['stats']]
    return {'outputs':out,'unresolved':rule['unresolved'],
            'source_level_binding':'none_unless_separate_exact_observation',
            'whole_dps_certified':False}
