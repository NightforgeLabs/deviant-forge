"""V7.1 stateful candidate adapter: time advancement precedes damage events.

The v7 packet and adapter remain frozen. Import this adapter for integration.
"""
from __future__ import annotations

from copy import deepcopy

import stateful_candidate_adapter_v7 as base

CandidateModeRequired = base.CandidateModeRequired
UnknownRuleParameter = base.UnknownRuleParameter
initial_state = base.initial_state


def _inactivity(state: dict, rule: dict, event: dict, assumptions: dict):
    kind = event['type']
    if kind not in ('tick', 'damage_taken', 'reset_cycle'):
        raise ValueError('unsupported inactivity event')
    now = base._number(event['time_seconds'], 'event time')
    if now < state['last_time']:
        raise ValueError('out-of-order event time')
    if kind != 'tick' and not base._record_event(state, event):
        return [], ['duplicate_event_ignored']

    # At the exact activation threshold, the tooltip does not state whether
    # damage or activation wins. Require an explicit ordering assumption.
    if (kind == 'damage_taken' and state['phase'] == 'waiting'
            and now == state['window_started_at'] + rule['no_damage_seconds']):
        order = assumptions.get('activation_boundary_order')
        if order == 'damage_preempts_activation':
            state['window_started_at'] = now
            state['last_time'] = now
            return [], []
        if order != 'activation_precedes_damage':
            raise UnknownRuleParameter('activation_boundary_order')

    # Advance elapsed time first. Without this, a damage event at t=5 would
    # erase a buff that activated at t=4, making results depend on tick sampling.
    outputs = base._advance_inactivity(state, rule, now, assumptions)
    if state['phase'] == 'reset_pending':
        # Sparse and dense paths must have the same expired-state shape.
        state['active_until'] = None

    if kind == 'damage_taken':
        if state['phase'] == 'active':
            if now == state['active_until'] - rule['duration_seconds']:
                order = assumptions.get('activation_boundary_order')
                if order == 'damage_preempts_activation':
                    state.update(phase='waiting', window_started_at=now,
                                 active_until=None)
                    state['last_time'] = now
                    return [], []
                if order != 'activation_precedes_damage':
                    raise UnknownRuleParameter('activation_boundary_order')
            policy = assumptions.get('damage_during_active')
            if policy == 'cancels':
                state.update(phase='waiting', window_started_at=now,
                             active_until=None)
                outputs = []
            elif policy != 'does_not_cancel':
                raise UnknownRuleParameter('damage_during_active')
        elif state['phase'] == 'waiting':
            state['window_started_at'] = now
            outputs = []
    elif kind == 'reset_cycle':
        if state['phase'] != 'reset_pending':
            raise ValueError('reset_cycle requires reset_pending phase')
        state.update(phase='waiting', window_started_at=now, active_until=None)
        outputs = []

    state['last_time'] = now
    unresolved = ['post_expiry_reset_anchor'] if state['phase'] == 'reset_pending' else []
    return outputs, unresolved


def execute_candidate(binding: dict, state: dict, event: dict, *,
                      allow_candidate: bool = False, assumptions: dict | None = None) -> dict:
    """Run a candidate event step with v7.1 inactivity event ordering."""
    if binding['operator'] != 'inactivity_timed_modifier':
        result = base.execute_candidate(binding, state, event,
                                        allow_candidate=allow_candidate,
                                        assumptions=assumptions)
        return {**result, 'adapter_version': 'v7.1'}
    if not allow_candidate:
        raise CandidateModeRequired('community, level-unbound candidate requires allow_candidate=True')
    if (binding['numeric_evidence_mode'] != 'community_primary_text_candidate_only'
            or binding['level_binding'] is not None):
        raise CandidateModeRequired('unsupported evidence mode or bound level')
    assumptions = assumptions or {}
    updated = deepcopy(state)
    outputs, unresolved = _inactivity(updated, binding['rule'], event, assumptions)
    return {'state': updated, 'outputs': outputs, 'unresolved': unresolved,
            'assumptions_used': assumptions, 'catalog_id': binding['catalog_id'],
            'source_text_sha256': binding['candidate_text_sha256'],
            'source_warning': 'Community primary tooltip candidate; level and current game version are unverified.',
            'numeric_evidence_mode': binding['numeric_evidence_mode'],
            'current_level_certified': False, 'whole_dps_certified': False,
            'adapter_version': 'v7.1'}
