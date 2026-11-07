"""Selected community core text applied to already sourced timed damage packets.

This layer does not create hits or infer item effect rank. Its inputs are the
finite-ammo scheduler's actual shot/reload trace and classified damage packets.
"""
from __future__ import annotations

import math


PACKET_RULES = {'empty_magazine_status_stacks',
                'previous_magazine_elemental_instances',
                'previous_magazine_weakspot_rate',
                'kill_refill_and_damage_until_reload'}


def _reloads(connected, capacity):
    events = connected['events']
    trace = {row['event_id']: row for row in connected['scheduler']['event_trace']}
    remaining = capacity
    shots_in_magazine = 0
    empty_times, reloads = [], []
    for event in events:
        if event['kind'] == 'shot':
            remaining -= 1
            shots_in_magazine += 1
            if remaining == 0:
                empty_times.append(event['at'])
        elif event['kind'] == 'kill_enemy':
            remaining += event.get('ammo_transfer_rounds', 0)
        elif event['kind'] == 'reload':
            outputs = trace[event['event_id']]['candidate_outputs']
            complete = [row['seconds'] for row in outputs
                        if row.get('type') == 'reload_completed_at']
            if len(complete) != 1:
                raise ValueError('Sourced reload completion time is missing')
            reloads.append({'start': event['at'], 'end': complete[0],
                            'shots_previous_magazine': shots_in_magazine})
            remaining = (0 if event.get('consume_remaining_magazine_for_blast') else remaining) + event['loaded_rounds']
            shots_in_magazine = 0
    return empty_times, reloads


def apply(rule, connected, timing, options):
    """Return source packet damage delta, resolved windows and explicit gaps."""
    if rule['kind'] not in PACKET_RULES:
        raise ValueError('Core rule is not a sourced-packet window')
    empty_times, reloads = _reloads(connected, timing['magazine'])
    gaps, windows = [], []
    kind = rule['kind']
    if kind == 'empty_magazine_status_stacks':
        windows = [{'start': at, 'end': at + rule['duration_seconds'],
                    'bonus_percent': rule['value_percent']} for at in empty_times]
    elif kind == 'previous_magazine_elemental_instances':
        if reloads and options.get('core_all_elemental_events_modeled') is not True:
            gaps.append('Elemental Resonance needs confirmation that all previous-magazine elemental damage instances are modeled')
        else:
            source_ids = {row['event_id'] for row in connected['source_packets']}
            prior_start = -math.inf
            packets = connected['scheduler']['packets']
            for reload in reloads:
                instances = sum(row.get('resolved_hits', 1) for row in packets
                                if row['event_id'] in source_ids and
                                prior_start <= row['at'] < reload['start'] and
                                row.get('element') not in (None, 'none', 'non_elemental'))
                windows.append({'start': reload['end'],
                                'end': reload['end'] + rule['duration_seconds'],
                                'bonus_percent': min(rule['maximum_percent'],
                                                     instances * rule['value_percent']),
                                'previous_elemental_instances': instances})
                prior_start = reload['end']
    elif kind == 'previous_magazine_weakspot_rate':
        entered = options.get('core_weakspot_hits_by_magazine')
        if reloads and (not isinstance(entered, list) or len(entered) != len(reloads)):
            gaps.append('Precision Charge needs one explicit weakspot-hit count for each completed magazine')
        else:
            for index, reload in enumerate(reloads):
                hits = entered[index]
                shots = reload['shots_previous_magazine']
                if isinstance(hits, bool) or not isinstance(hits, int) or not 0 <= hits <= shots:
                    raise ValueError('Previous-magazine weakspot hits must be whole counts within fired shots')
                steps = math.floor((100 * hits / shots) / rule['per_rate_percent']) if shots else 0
                next_reload = reloads[index + 1]['start'] if index + 1 < len(reloads) else math.inf
                windows.append({'start': reload['end'],
                                'end': min(reload['end'] + rule['duration_seconds'], next_reload),
                                'bonus_percent': min(rule['maximum_percent'], steps * rule['value_percent']),
                                'previous_weakspot_hits': hits, 'previous_shots': shots})
    elif kind == 'kill_refill_and_damage_until_reload':
        next_reload = math.inf
        for event in reversed(connected['events']):
            if event['kind'] == 'reload':
                next_reload = event['at']
            elif event['kind'] == 'kill_enemy':
                windows.append({'start': event['at'], 'end': next_reload,
                                'bonus_percent': rule['value_percent'],
                                'kill_event_id': event['event_id'],
                                'ammo_transfer_rounds': event.get('ammo_transfer_rounds', 0)})
        windows.reverse()
    if gaps:
        return {'damage_delta': 0.0, 'windows': windows, 'packet_adjustments': [],
                'unresolved': gaps}
    source_ids = {row['event_id'] for row in connected['source_packets']}
    direct_ids = {event['event_id'] for event in connected['events'] if event['kind'] == 'shot'}
    changes = []
    for packet in connected['scheduler']['packets']:
        is_direct = packet['event_id'] in direct_ids
        if packet['event_id'] not in source_ids and not (
                kind == 'kill_refill_and_damage_until_reload' and is_direct):
            continue
        packet_pool = (packet.get('damage_class') if kind == 'kill_refill_and_damage_until_reload'
                       else rule['pool'])
        if packet_pool == 'status' and packet.get('damage_class') != 'status':
            continue
        if packet_pool == 'elemental' and packet.get('element') in (None, 'none', 'non_elemental'):
            continue
        if packet_pool not in ('weapon', 'status', 'elemental'):
            continue
        at = packet['at']
        active = [window for window in windows if window['start'] < at < window['end']
                  or kind not in ('empty_magazine_status_stacks',
                                  'kill_refill_and_damage_until_reload') and
                  window['start'] <= at < window['end']]
        if kind == 'empty_magazine_status_stacks':
            if len(active) > 1 and options.get('core_timed_stack_model') != 'independent':
                gaps.append('Abnormal Increase overlapping active stacks need an explicit independent-duration hypothesis')
                continue
            bonus = sum(window['bonus_percent'] for window in active[-rule['max_stacks']:])
        else:
            if kind == 'previous_magazine_elemental_instances' and len(active) > 1 and \
                    options.get('core_reload_refresh_model') != 'replace':
                gaps.append('Elemental Resonance overlapping active reload windows need an explicit replacement hypothesis')
                continue
            bonus = active[-1]['bonus_percent'] if active else 0.0
        if not bonus:
            continue
        old = packet.get('applied_pools_percent', {}).get(packet_pool)
        if old is None or old <= -100:
            gaps.append(f"{packet['event_id']}: eligible packet lacks a resolved {packet_pool} pool")
            continue
        delta = packet['damage'] * bonus / (100 + old)
        changes.append({'event_id': packet['event_id'], 'at': at,
                        'pool': packet_pool, 'bonus_percent': bonus,
                        'damage_delta': delta, 'direct': is_direct})
    return {'damage_delta': sum(row['damage_delta'] for row in changes if not row['direct']),
            'direct_packet_adjustments': [row for row in changes if row['direct']],
            'windows': windows, 'packet_adjustments': changes,
            'unresolved': gaps}
