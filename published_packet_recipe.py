"""Turn explicit guided controls into shot-linked packet actions.

This module supplies no proc chance, charge acquisition, target selection or
damage coefficient. Those values remain caller observations or hypotheses.
"""
from __future__ import annotations

import math

import weapon_packet_timeline_api as packet_api


def _indices(value, count):
    if not isinstance(value, list) or any(isinstance(i, bool) or not isinstance(i, int)
                                           or i < 0 or i >= count for i in value):
        raise ValueError('Enter zero-based charged shot indices within the generated shots')
    if len(set(value)) != len(value):
        raise ValueError('Charged shot indices cannot repeat')
    return set(value)


def _targets(value, name, *, required=True):
    if value is None and not required:
        return []
    if not isinstance(value, list) or (required and not value) or any(
            not isinstance(x, str) or not x.strip() for x in value):
        raise ValueError(f'Enter explicit {name} target identities')
    return value


def _whole(value, name, *, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f'{name} must be a whole number at least {minimum}')
    return value


def build(weapon_id, events, recipe, target, duration):
    if weapon_id not in packet_api.BINDINGS or not isinstance(recipe, dict):
        raise ValueError('Selected packet weapon needs guided packet controls')
    shots = [event for event in events if event['kind'] == 'shot']
    charged = _indices(recipe.get('charged_shot_indices'), len(shots)) if weapon_id in (
        'weapon:critical-pulse', 'weapon:acs12-pyroclasm-starter',
        'weapon:sks-pathfinder') else set()
    actions, excluded = [], {}
    def hit(index, kind, **kwargs):
        actions.append({'kind': kind, 'shot_event_id': shots[index]['event_id'],
                        'input_id': f'guided-{index}', **kwargs})
    if weapon_id == 'weapon:critical-pulse':
        if len(charged) != 1:
            raise ValueError('Guided Critical Pulse requires exactly one observed charged shot; use advanced events for multiple orbs')
        observed = _whole(recipe.get('observed_charges'), 'Observed charges', minimum=1)
        index = next(iter(charged))
        orb_duration = recipe.get('orb_duration_seconds')
        delay = recipe.get('first_tick_delay_seconds')
        if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or x < 0
               for x in (orb_duration, delay)) or orb_duration <= 0:
            raise ValueError('Enter observed orb duration and first tick delay in seconds')
        endpoint = recipe.get('include_endpoint')
        if not isinstance(endpoint, bool):
            raise ValueError('Select whether the orb duration endpoint counts as a tick')
        hit(index, 'critical_pulse_start_orb', hit_target=target,
            orb_duration_seconds=orb_duration, first_tick_delay_seconds=delay,
            include_endpoint=endpoint)
        tick_times = recipe.get('orb_tick_times')
        if not isinstance(tick_times, list) or not tick_times:
            raise ValueError('Enter explicit orb tick times; the tick interval is not sourced')
        tick_target = recipe.get('orb_tick_target')
        _targets([tick_target] if tick_target is not None else None, 'orb tick')
        distance = recipe.get('orb_tick_distance_meters')
        if isinstance(distance, bool) or not isinstance(distance, (int, float)) or not math.isfinite(distance) or distance < 0:
            raise ValueError('Enter observed orb tick distance in meters')
        for number, at in enumerate(tick_times):
            if isinstance(at, bool) or not isinstance(at, (int, float)) or not math.isfinite(at) or not 0 <= at <= duration:
                raise ValueError('Orb tick times must be within the encounter')
            actions.append({'kind': 'critical_pulse_orb_tick', 'at': at,
                            'input_id': f'guided-tick-{number}', 'orb_id': f'guided-{index}',
                            'target': tick_target, 'distance_meters': distance})
        for number, shot in enumerate(shots):
            if number not in charged:
                excluded[shot['event_id']] = 'no_observed_charge_spent'
        resources = {'observed_charges': observed}
    elif weapon_id == 'weapon:r500-hammerhead-shark':
        flags = recipe.get('power_surge_flags')
        if not isinstance(flags, list) or len(flags) != len(shots) or any(not isinstance(x, bool) for x in flags):
            raise ValueError('Enter one target Power Surge true/false value per generated shot')
        nearby = _targets(recipe.get('nearby_affected_targets'), 'nearby affected', required=False)
        for index, flag in enumerate(flags):
            hit(index, 'hammerhead_chain_hit', primary_target=target,
                primary_power_surge_status=flag, nearby_affected_targets=nearby if flag else [])
        resources = {}
    elif weapon_id == 'weapon:kvd-boom-boom':
        targets = _targets(recipe.get('explosion_targets'), 'explosion')
        for index in range(len(shots)):
            hit(index, 'boom_boom_hit', explosion_targets=targets)
        resources = {}
    elif weapon_id == 'weapon:acs12-pyroclasm-starter':
        units = _targets(recipe.get('resolved_damage_units'), 'charged pellet or damage unit')
        observed = _whole(recipe.get('observed_charged_rounds'), 'Observed charged rounds')
        for index, shot in enumerate(shots):
            if index in charged:
                hit(index, 'pyroclasm_charged_shot', resolved_damage_units=units)
            else:
                excluded[shot['event_id']] = 'ordinary_uncharged_round'
        resources = {'observed_charged_rounds': observed}
    elif weapon_id == 'weapon:sks-pathfinder':
        targets = _targets(recipe.get('pierced_targets'), 'pierced')
        cost = _whole(recipe.get('charge_cost'), 'Charge cost', minimum=1)
        observed = _whole(recipe.get('observed_charges'), 'Observed charges')
        for index, shot in enumerate(shots):
            if index in charged:
                hit(index, 'pathfinder_charged_shot', charge_cost=cost,
                    pierced_targets=targets)
            else:
                excluded[shot['event_id']] = 'ordinary_uncharged_shot'
        resources = {'observed_charges': observed}
    else:
        targets = _targets(recipe.get('pulse_targets'), 'pulse', required=len(shots) >= 11)
        overflow = recipe.get('counter_overflow')
        if overflow not in ('subtract', 'reset'):
            raise ValueError('Choose a named Holographic hit-counter overflow model')
        for index in range(len(shots)):
            hit(index, 'holographic_hit', **({'pulse_targets': targets}
                if (index + 1) % 11 == 0 else {}))
        resources = {'counter_overflow': overflow}
    return actions, excluded, resources
