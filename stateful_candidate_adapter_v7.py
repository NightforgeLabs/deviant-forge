"""Reusable state/event operators for three *candidate* main-mod effect families.

Use allow_candidate=True and named semantic assumptions. No returned value is
an identity-and-level verified current effect or a sustained-DPS calculation.
"""
from __future__ import annotations

from copy import deepcopy
from math import isfinite


class CandidateModeRequired(ValueError):
    pass


class UnknownRuleParameter(ValueError):
    pass


def _number(value, name):
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not isfinite(value):
        raise ValueError('invalid ' + name)
    return value


def _nonnegative_int(value, name):
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError('invalid ' + name)
    return value


def initial_state(binding: dict, **kwargs) -> dict:
    op = binding['operator']
    if op == 'inactivity_timed_modifier':
        start = _number(kwargs['start_time_seconds'], 'start time')
        return {'phase': 'waiting', 'window_started_at': start, 'active_until': None,
                'last_time': start, 'seen_event_ids': []}
    if op == 'magazine_phase_modifier':
        if kwargs.get('full_magazine') is not True:
            raise UnknownRuleParameter('full_magazine=True required at initialization')
        capacity = _nonnegative_int(kwargs['magazine_capacity'], 'capacity')
        if capacity == 0: raise ValueError('capacity must be positive')
        return {'magazine_id': kwargs['magazine_id'], 'capacity': capacity,
                'consumed': 0, 'seen_event_ids': []}
    if op == 'counter_ammo_refill':
        capacity = _nonnegative_int(kwargs['magazine_capacity'], 'capacity')
        magazine = _nonnegative_int(kwargs['magazine_bullets'], 'magazine bullets')
        reserve = _nonnegative_int(kwargs['reserve_bullets'], 'reserve bullets')
        if capacity == 0 or magazine > capacity: raise ValueError('invalid magazine state')
        return {'kill_count': 0, 'capacity': capacity, 'magazine': magazine,
                'reserve': reserve, 'seen_event_ids': []}
    raise NotImplementedError(op)


def _record_event(state: dict, event: dict) -> bool:
    event_id = event.get('event_id')
    if not isinstance(event_id, str) or not event_id:
        raise ValueError('mutating events require a nonempty event_id')
    if event_id in state['seen_event_ids']:
        return False
    state['seen_event_ids'].append(event_id)
    return True


def _stat_outputs(nodes: list, *, phase: str | None = None) -> list:
    return [{'type': 'stat_pool_delta', 'stat': n['stat'],
             'percentage_points': n['value'], **({'phase_for_next_shot': phase} if phase else {})}
            for n in nodes]


def _advance_inactivity(state: dict, rule: dict, now: float, assumptions: dict) -> list:
    threshold = rule['no_damage_seconds']
    duration = rule['duration_seconds']
    policy = assumptions.get('post_expiry_reset_anchor')
    if policy not in (None, 'expiry_time'):
        raise UnknownRuleParameter('post_expiry_reset_anchor')
    if state['phase'] == 'reset_pending':
        return []
    if state['phase'] == 'active':
        if now < state['active_until']:
            return [{**x, 'active_until_seconds': state['active_until']}
                    for x in _stat_outputs(rule['nodes'])]
        if policy is None:
            state['phase'] = 'reset_pending'
            return []
        state['phase'] = 'waiting'
        state['window_started_at'] = state['active_until']
        state['active_until'] = None
    # A long event gap may cover multiple cycles; skip complete assumed cycles.
    if policy == 'expiry_time':
        cycle = threshold + duration
        completed = int((now - state['window_started_at']) // cycle)
        if completed > 0:
            state['window_started_at'] += completed * cycle
    onset = state['window_started_at'] + threshold
    if now < onset:
        return []
    end = onset + duration
    if now >= end:
        state['phase'] = 'reset_pending'
        return []
    state['phase'] = 'active'
    state['active_until'] = end
    return [{**x, 'active_until_seconds': end} for x in _stat_outputs(rule['nodes'])]


def _inactivity(state: dict, rule: dict, event: dict, assumptions: dict):
    kind = event['type']
    if kind not in ('tick', 'damage_taken', 'reset_cycle'):
        raise ValueError('unsupported inactivity event')
    now = _number(event['time_seconds'], 'event time')
    if now < state['last_time']: raise ValueError('out-of-order event time')
    if kind != 'tick' and not _record_event(state, event):
        return [], ['duplicate_event_ignored']
    if kind == 'damage_taken' and state['phase'] == 'waiting':
        state['window_started_at'] = now
        state['last_time'] = now
        return [], []
    out = _advance_inactivity(state, rule, now, assumptions)
    if kind == 'damage_taken':
        if state['phase'] == 'active':
            policy = assumptions.get('damage_during_active')
            if policy == 'cancels':
                state.update(phase='waiting', window_started_at=now, active_until=None)
                out = []
            elif policy != 'does_not_cancel':
                raise UnknownRuleParameter('damage_during_active')
        elif state['phase'] == 'waiting':
            state['window_started_at'] = now
            out = []
    elif kind == 'reset_cycle':
        if state['phase'] != 'reset_pending':
            raise ValueError('reset_cycle requires reset_pending phase')
        state.update(phase='waiting', window_started_at=now, active_until=None)
        out = []
    state['last_time'] = now
    unresolved = ['post_expiry_reset_anchor'] if state['phase'] == 'reset_pending' else []
    return out, unresolved


def _magazine(state: dict, rule: dict, event: dict, assumptions: dict):
    if assumptions.get('phase_basis') != 'consumed_ammo_fraction':
        raise UnknownRuleParameter('phase_basis=consumed_ammo_fraction required')
    kind = event['type']
    if kind not in ('inspect', 'consume', 'reload'):
        raise ValueError('unsupported magazine event')
    if kind != 'inspect' and not _record_event(state, event):
        return [], ['duplicate_event_ignored']
    if kind == 'consume':
        bullets = _nonnegative_int(event['bullets'], 'consumed bullets')
        if bullets == 0 or state['consumed'] + bullets > state['capacity']:
            raise ValueError('invalid consumed bullets')
        state['consumed'] += bullets
    elif kind == 'reload':
        if event.get('full_magazine') is not True:
            raise UnknownRuleParameter('full_magazine=True required on reload')
        capacity = _nonnegative_int(event['magazine_capacity'], 'capacity')
        if capacity == 0 or event['magazine_id'] == state['magazine_id']:
            raise ValueError('reload requires new magazine identity and positive capacity')
        state.update(magazine_id=event['magazine_id'], capacity=capacity, consumed=0)
    if state['consumed'] == state['capacity']:
        return [], []
    fraction = state['consumed'] / state['capacity']
    if fraction < 0.5:
        phase, node = 'first_half', rule['nodes'][0]
    elif fraction > 0.5:
        phase, node = 'second_half', rule['nodes'][1]
    else:
        owner = assumptions.get('exact_half_boundary_owner')
        if owner not in ('first_half', 'second_half'):
            raise UnknownRuleParameter('exact_half_boundary_owner')
        phase = owner
        node = rule['nodes'][0 if owner == 'first_half' else 1]
    return _stat_outputs([node], phase=phase), []


def _reaper(state: dict, rule: dict, event: dict, assumptions: dict):
    if event['type'] not in ('kill_enemy', 'ammo_state_update'):
        raise ValueError('unsupported counter event')
    if not _record_event(state, event):
        return [], ['duplicate_event_ignored']
    if event['type'] == 'ammo_state_update':
        magazine = _nonnegative_int(event['magazine_bullets'], 'magazine bullets')
        reserve = _nonnegative_int(event['reserve_bullets'], 'reserve bullets')
        if magazine > state['capacity']:
            raise ValueError('magazine exceeds capacity')
        state.update(magazine=magazine, reserve=reserve)
        return [], []
    state['kill_count'] += 1
    if state['kill_count'] < rule['required_count']:
        return [], []
    required = {'refill_semantics': 'fill_to_capacity_from_reserves',
                'insufficient_reserve': 'transfer_available',
                'counter_reset_after_partial_or_empty': True}
    for key, value in required.items():
        if assumptions.get(key) != value:
            raise UnknownRuleParameter(key)
    gap = state['capacity'] - state['magazine']
    transfer = min(gap, state['reserve'])
    state['magazine'] += transfer
    state['reserve'] -= transfer
    state['kill_count'] = 0
    return [{'type': 'ammo_transfer', 'from': 'reserves', 'to': 'magazine',
             'requested_bullets': gap, 'bullets': transfer,
             'magazine_after': state['magazine'], 'reserve_after': state['reserve'],
             'counter_reset': 'after_proc'}], []


def execute_candidate(binding: dict, state: dict, event: dict, *,
                      allow_candidate: bool = False, assumptions: dict | None = None) -> dict:
    """Step an operator and return a new state; never mutate caller state."""
    if not allow_candidate:
        raise CandidateModeRequired('community, level-unbound candidate requires allow_candidate=True')
    if binding['numeric_evidence_mode'] != 'community_primary_text_candidate_only' or binding['level_binding'] is not None:
        raise CandidateModeRequired('unsupported evidence mode or bound level')
    assumptions = assumptions or {}
    updated = deepcopy(state)
    op = binding['operator']
    if op == 'inactivity_timed_modifier':
        outputs, unresolved = _inactivity(updated, binding['rule'], event, assumptions)
    elif op == 'magazine_phase_modifier':
        outputs, unresolved = _magazine(updated, binding['rule'], event, assumptions)
    elif op == 'counter_ammo_refill':
        outputs, unresolved = _reaper(updated, binding['rule'], event, assumptions)
    else:
        raise NotImplementedError(op)
    return {'state': updated, 'outputs': outputs, 'unresolved': unresolved,
            'assumptions_used': assumptions, 'catalog_id': binding['catalog_id'],
            'source_text_sha256': binding['candidate_text_sha256'],
            'source_warning': 'Community primary tooltip candidate; level and current game version are unverified.',
            'numeric_evidence_mode': binding['numeric_evidence_mode'],
            'current_level_certified': False, 'whole_dps_certified': False}
