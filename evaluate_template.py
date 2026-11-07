"""Small reference evaluator for known stat nodes, not a whole damage engine.

The caller supplies combat state and event stack count. Unknown timing, damage
formula, and HP/shield operators are deliberately not evaluated here.
"""
from __future__ import annotations

from collections import defaultdict


def stat_projection(rule: dict, context: dict) -> dict[str, float]:
    if rule.get('unresolved'):
        raise ValueError('rule has unresolved parameters')
    operator=rule['operator']
    eligible={
        'static_modifier','tradeoff_static_modifier','event_timed_modifier',
        'event_timed_stack','threshold_modifier','state_conditional_modifier',
        'target_conditional_modifier','proximity_conditional_modifier',
        'base_plus_threshold','magazine_phase_modifier','periodic_stack_and_hit_decay',
    }
    if operator not in eligible:
        raise NotImplementedError(operator)
    active=True
    if operator=='threshold_modifier':
        t=rule['threshold']; active=_compare(context[t['resource']],t['comparison'],t['value'])
    elif operator=='state_conditional_modifier':
        active=rule['state'] in context.get('states',())
    elif operator=='target_conditional_modifier':
        active=rule['target_state'] in context.get('target_states',())
    elif operator=='proximity_conditional_modifier':
        active=context.get('enemies_within_distance',None)==rule['enemy_count']
    elif operator=='event_timed_modifier':
        active=context.get('active_event_buffs',{}).get(rule['event'],False)
    if not active:
        return {}
    stacks=1
    if operator in {'event_timed_stack','periodic_stack_and_hit_decay'}:
        stacks=max(0,min(int(context.get('stacks',0)),int(rule['max_stacks'])))
    out=defaultdict(float)
    for n in rule['nodes']:
        if n['op']=='stat_delta_percent':
            out[n['stat']]+=n['value']*stacks
        elif n['op']=='conditional_stat_delta_percent':
            c=n['condition']; value=context.get(c['resource'])
            if value is not None and _compare(value,c['comparison'],c['value']):
                out[n['stat']]+=n['value']
        elif n['op']=='magazine_phase_stat_delta':
            spent=context['magazine_consumed_percent']
            if n['phase_percent'][0] <= spent < n['phase_percent'][1]:
                out[n['stat']]+=n['value']
    return dict(out)


def _compare(actual: float, comparison: str, target: float) -> bool:
    if comparison=='above': return actual>target
    if comparison=='below': return actual<target
    raise ValueError(comparison)
