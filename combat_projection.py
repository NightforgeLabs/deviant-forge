"""Explicit-input combat component budget; no catalog values are inferred here.

This is a reusable expectation model. The default direct Weapon crit/weakspot
factor follows the copied version-13 native graph. Trigger independence,
packet stacking, overlap, enemy defense, and pool applicability remain separate.
"""
import math
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR

import native_direct_hit_graph

BRANCHES = {'normal', 'crit', 'weakspot', 'crit_weakspot',
            'status', 'elemental_nonstatus', 'power_surge', 'shock', 'unstable_bomber'}


def number(value, label, low=0, high=1_000_000):
    if isinstance(value, bool):
        raise ValueError(f'{label} must be numeric')
    try:
        result = float(value)
    except (ValueError, TypeError):
        raise ValueError(f'{label} must be numeric') from None
    if not math.isfinite(result) or not low <= result <= high:
        raise ValueError(f'{label} outside supported range')
    return result


def reload_seconds(base_reload_seconds, reload_efficiency_percent):
    """Official 2025-05-21 rule: final = base / (1 + efficiency)."""
    base = number(base_reload_seconds, 'base reload seconds')
    efficiency = number(reload_efficiency_percent, 'reload efficiency percent', -99, 100000)
    return base / (1 + efficiency / 100)


def relative_trigger_chance(base_chance, relative_bonus_fraction):
    """Apply a relative trigger bonus to an entered base chance, capped at 1."""
    base = number(base_chance, 'base trigger chance', 0, 1)
    bonus = number(relative_bonus_fraction, 'relative trigger bonus', -1, 1000)
    return min(1, base * (1 + bonus))


def capped_affine_coefficient(intercept_percent, per_resource_percent, resource, cap_percent):
    """Calculate a user-supplied capped linear coefficient in percentage points."""
    intercept = number(intercept_percent, 'coefficient intercept', 0)
    per_resource = number(per_resource_percent, 'coefficient per resource', 0)
    amount = number(resource, 'resource amount', 0)
    cap = number(cap_percent, 'coefficient cap', 0)
    return min(cap, intercept + per_resource * amount)


def weighted_counter(event_weights, threshold, carry_over=True):
    """Count threshold crossings in an explicitly ordered weighted event stream."""
    if not isinstance(event_weights, list) or len(event_weights) > 100000:
        raise ValueError('Event weights must be a list of at most 100000 values')
    threshold = number(threshold, 'counter threshold', 0.000001)
    total = 0.0
    triggers = 0
    for weight in event_weights:
        total += number(weight, 'event weight')
        crossed = int(total // threshold) if carry_over else int(total >= threshold)
        triggers += crossed
        if crossed:
            total = total - crossed * threshold if carry_over else 0.0
    return {'triggers': triggers, 'remainder': total,
            'carry_over': bool(carry_over)}


def periodic_tick_count(duration_seconds, interval_seconds, start_delay_seconds,
                        include_endpoint=False):
    """Count a supplied periodic schedule; initial delay and endpoint are explicit."""
    duration = number(duration_seconds, 'period duration')
    interval = number(interval_seconds, 'tick interval', 0.000001)
    delay = number(start_delay_seconds, 'tick start delay')
    if delay > duration or delay == duration and not include_endpoint:
        return 0
    # Decimal preserves user-entered decimal boundaries without erasing a real
    # tick that occurs just before a slightly later duration.
    cycles = (Decimal(str(duration)) - Decimal(str(delay))) / Decimal(str(interval))
    if include_endpoint:
        return int(cycles.to_integral_value(rounding=ROUND_FLOOR)) + 1
    return int(cycles.to_integral_value(rounding=ROUND_CEILING))


def components(profile, repeat_triggers=None):
    """Return baseline expected damage by branch from explicitly entered packets.

    A basis (Attack or Psi) and damage class (Weapon or Status) are independent
    tags. The caller must select the receiving branch for each event.
    """
    if not isinstance(profile, dict):
        raise ValueError('Combat profile must be an object')
    repeat_triggers = repeat_triggers or {}
    if not isinstance(repeat_triggers, dict):
        raise ValueError('Triggered-effect repeat rules must be an object')
    shots = number(profile.get('shots'), 'shots', 1)
    if not shots.is_integer():
        raise ValueError('Shots must be a whole number')
    result = {name: 0.0 for name in BRANCHES}
    packets = []
    direct = profile.get('direct')
    direct_joint_model = None
    if direct is not None:
        if not isinstance(direct, dict):
            raise ValueError('Direct hit profile must be an object')
        normal = number(direct.get('normal_damage_per_shot'), 'normal damage per shot')
        crit = number(direct.get('crit_bonus_percent', 0), 'crit bonus percent') / 100
        weak = number(direct.get('weakspot_bonus_percent', 0), 'weakspot bonus percent') / 100
        pcrit = number(direct.get('crit_share'), 'crit share', 0, 1)
        pweak = number(direct.get('weakspot_share'), 'weakspot share', 0, 1)
        joint = number(direct.get('crit_weakspot_share'), 'crit and weakspot share', 0, 1)
        if not max(0, pcrit + pweak - 1) <= joint <= min(pcrit, pweak):
            raise ValueError('Crit and weakspot joint share is inconsistent with marginal shares')
        model = direct.get('joint_multiplier', 'additive')
        if model not in ('multiplicative', 'additive'):
            raise ValueError('Joint multiplier must be additive or multiplicative')
        direct_joint_model = model
        shares = {'normal': 1 - pcrit - pweak + joint,
                  'crit': pcrit - joint, 'weakspot': pweak - joint,
                  'crit_weakspot': joint}
        multipliers = {'normal': 1, 'crit': 1 + crit, 'weakspot': 1 + weak,
                       'crit_weakspot': (1 + crit) * (1 + weak) if model == 'multiplicative' else native_direct_hit_graph.joint_factor(crit, weak, crit=True, weakspot=True)}
        for branch, share in shares.items():
            damage = shots * normal * share * multipliers[branch]
            result[branch] += damage
            if damage:
                packets.append({'branch': branch, 'damage_class': 'weapon',
                                'kind': 'direct', 'damage': damage})
    events = profile.get('events') or []
    if not isinstance(events, list) or len(events) > 100:
        raise ValueError('Events must be a list of at most 100 entries')
    trace = []
    for event in events:
        if not isinstance(event, dict):
            raise ValueError('Each event must be an object')
        branch = event.get('branch')
        if branch not in BRANCHES:
            raise ValueError('Event branch is unrecognized')
        basis = event.get('basis')
        damage_class = event.get('damage_class')
        if basis not in ('attack', 'psi') or damage_class not in ('weapon', 'status'):
            raise ValueError('Event needs independent attack/psi basis and weapon/status damage class')
        if 'elemental_pool_applies' in event and not isinstance(event['elemental_pool_applies'], bool):
            raise ValueError('Elemental pool applicability must be true or false')
        element = event.get('element')
        if element is not None:
            if not isinstance(element, str) or element.lower() not in ('blaze', 'frost', 'shock', 'blast', 'none', 'non_elemental'):
                raise ValueError('Event element must be Blaze, Frost, Shock, Blast, or none')
            element = element.lower()
        elemental = (event['elemental_pool_applies'] if 'elemental_pool_applies' in event else
                     element not in ('none', 'non_elemental') if element is not None else None)
        if element is not None and 'elemental_pool_applies' in event and elemental != (element not in ('none', 'non_elemental')):
            raise ValueError('Event element conflicts with elemental pool applicability')
        if ('count' in event) == ('chance_per_shot' in event):
            raise ValueError('Event needs exactly one count or chance_per_shot')
        count = number(event['count'], 'event count') if 'count' in event else shots * number(event['chance_per_shot'], 'chance per shot', 0, 1)
        magnitude = number(event.get('basis_value'), 'event basis value') * number(event.get('coefficient_percent'), 'event coefficient percent') / 100
        repeats = number(event.get('events_per_trigger', 1), 'events per trigger')
        if event.get('triggered_effect') is True and event.get('trigger_family') in repeat_triggers:
            repeats += number(repeat_triggers[event['trigger_family']], 'extra triggered-effect activations')
        ticks = number(event.get('ticks_per_event', 1), 'ticks per event')
        uptime = number(event.get('condition_uptime', 1), 'event condition uptime', 0, 1)
        damage = count * magnitude * repeats * ticks * uptime
        result[branch] += damage
        packets.append({'branch': branch, 'damage_class': damage_class,
                        'kind': 'event', 'damage': damage,
                        'element': element, 'elemental_pool_applies': elemental})
        trace.append({'name': event.get('name') or branch, 'branch': branch,
                      'basis': basis, 'damage_class': damage_class, 'element': element,
                      'expected_triggers': count, 'events_per_trigger': repeats,
                      'trigger_family': event.get('trigger_family'),
                      'triggered_effect': event.get('triggered_effect') is True,
                      'damage': damage,
                      'source': event.get('source')})
    duration = profile.get('duration_seconds')
    if duration is not None:
        duration = number(duration, 'duration seconds', 0.000001)
    return {'components': result, 'total_damage': sum(result.values()),
            'packets': packets,
            'direct_joint_model': direct_joint_model,
            'direct_joint_source': (native_direct_hit_graph.source() if direct_joint_model == 'additive'
                                    else 'explicit_multiplicative_what_if' if direct_joint_model else None),
            'duration_seconds': duration, 'damage_per_second': sum(result.values()) / duration if duration else None,
            'event_trace': trace,
            'assumptions': ['Entered trigger chance is an expectation per shot; cooldown and event dependence are not included.',
                            'Entered ticks do not account for refresh, overlap or enemy mitigation.',
                            'Attack/Psi basis and Weapon/Status damage class are independent; receiving branch is explicitly entered.',
                            'Damage per second is returned only when an encounter duration is entered.']}
