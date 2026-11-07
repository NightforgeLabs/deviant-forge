"""Strict context boundary for v1's reference stat projection.

Missing combat observations mean unknown, never an inactive buff or zero stacks.
This remains a stat projection example, not a complete event/DPS simulator.
"""
from evaluate_template import stat_projection as _v1_projection


class UnknownCombatState(ValueError):
    pass


def stat_projection(rule: dict, context: dict) -> dict[str, float]:
    op=rule['operator']
    required=[]
    if op=='threshold_modifier': required.append(rule['threshold']['resource'])
    if op=='state_conditional_modifier': required.append('states')
    if op=='target_conditional_modifier': required.append('target_states')
    if op=='proximity_conditional_modifier': required.append('enemies_within_distance')
    if op=='event_timed_modifier':
        buffs=context.get('active_event_buffs')
        if not isinstance(buffs,dict) or rule['event'] not in buffs or buffs[rule['event']] is None:
            raise UnknownCombatState('active_event_buffs.'+rule['event'])
    if op in ('event_timed_stack','periodic_stack_and_hit_decay'): required.append('stacks')
    if op=='magazine_phase_modifier': required.append('magazine_consumed_percent')
    for node in rule.get('nodes',[]):
        if node['op']=='conditional_stat_delta_percent' and 'resource' in node.get('condition',{}):
            required.append(node['condition']['resource'])
    for key in required:
        if key not in context or context[key] is None:
            raise UnknownCombatState(key)
    return _v1_projection(rule,context)
