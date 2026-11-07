"""Join sourced weapon triggers to the explicit timed stat and ammo scheduler.

The source runner resolves caller-entered hit outcomes and periodic schedules.
Its zero-pool packet projection supplies packet bases and coefficients; the
integrated scheduler then applies selected and active mod pools exactly once.
"""
from __future__ import annotations

from copy import deepcopy
import math

import integrated_event_model
import weapon_timeline_api
from weapon_mechanics.damage_projection_v3 import project_event


def _apply_sourced_state(final, source_events, source_packets, binding, proc, direct_basis):
    """Apply sourced stat state after its landing hit, before later packets."""
    events = [row for row in source_events if row.get('effect_type') == 'state_change'
              and row.get('stat')]
    if not events:
        return [], [], set()
    if proc.get('weapon_state_order') != 'after_direct_hit_before_triggered_packet':
        return ([{'reason': 'Weapon stat feedback needs weapon_state_order=after_direct_hit_before_triggered_packet'}],
                [], set())
    rules = {row['name']: row for row in binding['rules']}
    source_basis = {row['event_id']: row['basis'] for row in source_packets}
    shot_ids = {row['event_id'] for row in final['event_trace'] if row['kind'] == 'shot'}
    operations = []
    for index, packet in enumerate(final['packets']):
        operations.append((packet['at'], 0 if packet['event_id'] in shot_ids else 2,
                           index, 'packet', packet))
    for index, event in enumerate(events):
        operations.append((float(event['at']), 1, index, 'state', event))
    operations.sort(key=lambda row: (row[0], row[1], row[2]))
    ramps, stacks, trace, gaps, modeled = {}, {}, [], [], set()
    for at, _, _, kind, payload in operations:
        if kind == 'state':
            rule = rules.get(payload['event'])
            if rule is None or rule.get('stat') != payload.get('stat'):
                gaps.append({'event_id': payload['event_id'],
                             'reason': 'Weapon stat event has no matching source rule'})
                continue
            if rule['kind'] == 'same_target_ramp':
                ramps[payload['event']] = (payload['stat'], float(payload['additive_fraction']) * 100)
            elif rule['kind'] == 'conditional_stack' and rule.get('refresh_model') == 'independent':
                active = [expiry for expiry in stacks.get(payload['event'], []) if expiry > at]
                if len(active) < rule['cap']:
                    active.append(at + float(rule['duration_seconds']))
                stacks[payload['event']] = active
            else:
                gaps.append({'event_id': payload['event_id'],
                             'reason': 'Weapon stat feedback operator or expiry model unsupported'})
                continue
            modeled.add(payload['event_id'])
            trace.append({'event_id': payload['event_id'], 'at': at,
                          'stat': payload['stat'], 'source_rule': payload['event'],
                          'source_status': rule.get('source')})
            continue
        packet = payload
        active = {}
        for stat, percent in ramps.values():
            active[stat] = active.get(stat, 0) + percent
        for name, expiries in stacks.items():
            rule = rules[name]
            count = sum(expiry > at for expiry in expiries)
            active[rule['stat']] = active.get(rule['stat'], 0) + count * float(rule['per_stack']) * 100
        if not active:
            continue
        basis = direct_basis if packet['event_id'] in shot_ids else source_basis.get(packet['event_id'])
        for stat, percent in active.items():
            if stat == 'weapon_damage':
                if packet['damage_class'] != 'weapon':
                    continue
                prior_pool = packet['applied_pools_percent']['weapon']
                packet['damage'] *= (100 + prior_pool + percent) / (100 + prior_pool)
                packet['applied_pools_percent']['weapon'] = prior_pool + percent
            elif stat in ('attack', 'psi'):
                if basis is None:
                    gaps.append({'event_id': packet['event_id'],
                                 'reason': f'{stat} basis classification missing for weapon stat feedback'})
                elif basis == stat:
                    packet['damage'] *= 1 + percent / 100
            else:
                gaps.append({'event_id': packet['event_id'],
                             'reason': f'{stat} weapon stat feedback is not a supported pool or basis'})
        packet['sourced_weapon_state_percent'] = active
    final['total_damage'] = sum(row['damage'] for row in final['packets'])
    final['conditional_damage_per_second'] = final['total_damage'] / final['duration_seconds']
    return gaps, trace, modeled


def evaluate(scenario, *, static_pools, static_sources=None):
    if not isinstance(scenario, dict) or not isinstance(scenario.get('weapon_proc'), dict):
        raise ValueError('Enter a sourced weapon_proc object')
    proc = scenario['weapon_proc']
    weapon_id = proc.get('weapon_id')
    if weapon_id not in weapon_timeline_api.WEAPONS:
        raise ValueError('Choose a supported sourced weapon event binding')
    hit_inputs = proc.get('hit_inputs')
    if not isinstance(hit_inputs, list) or any(not isinstance(row, dict) for row in hit_inputs):
        raise ValueError('Enter one explicit hit input for every scheduled shot')
    prior = integrated_event_model.evaluate(scenario, static_pools=static_pools,
                                            static_sources=static_sources)
    shots = [row for row in prior['event_trace'] if row['kind'] == 'shot']
    by_shot = {}
    for row in hit_inputs:
        identifier = row.get('shot_event_id')
        if not isinstance(identifier, str) or not identifier or identifier in by_shot:
            raise ValueError('Each hit input needs a unique scheduled shot_event_id')
        if row.get('weakspot') is True:
            raise ValueError('Weakspot hit needs an eligible direct-packet model; not supported here')
        by_shot[identifier] = row
    if set(by_shot) != {row['event_id'] for row in shots}:
        raise ValueError('Hit inputs must match every distinct scheduled shot exactly')
    binding = weapon_timeline_api.WEAPONS[weapon_id]
    has_reload_blast = any(row['kind'] == 'reload_blast' for row in binding['rules'])
    actions = []
    for row in prior['event_trace']:
        if row['kind'] == 'reload':
            if not has_reload_blast:
                actions.append({'kind': 'reload', 'input_id': row['event_id'],
                                'at': row['at']})
        elif row['kind'] == 'shot':
            source = by_shot[row['event_id']]
            actions.append({'kind': 'hit', 'input_id': row['event_id'],
                            'at': row['at'], 'target': source.get('target'),
                            'rolls': source.get('rolls'),
                            'conditions': source.get('conditions'),
                            'weakspot': False,
                            **({'distance': source['distance']} if 'distance' in source else {})})
    source_model = proc.get('damage_model') or {}
    if not isinstance(source_model, dict) or source_model.get('direct') is not None:
        raise ValueError('Sourced proc damage_model cannot repeat direct bullet packets')
    if source_model.get('bonus_pools_percent'):
        raise ValueError('Sourced proc projection must use zero pools; selected pools apply in timed scheduler')
    if source_model.get('duration_seconds') not in (None, scenario['duration_seconds']):
        raise ValueError('Sourced proc and scheduler encounter durations differ')
    source_model = {**source_model, 'duration_seconds': scenario['duration_seconds']}
    source = weapon_timeline_api.simulate({'weapon_id': weapon_id,
        'evidence_mode': proc.get('evidence_mode'),
        'model_mode': proc.get('model_mode'),
        'stream_id': proc.get('stream_id'),
        'actions': actions, 'damage_model': source_model})
    projection = source['damage_projection']
    unresolved = [row for row in projection['unresolved_damage_events']
                  if not row['event_id'].endswith('/landed')]
    if has_reload_blast:
        original_reloads = {row['event_id']: row for row in scenario['events']
                            if row['kind'] == 'reload'}
        packet_model = (source_model.get('packet_models') or {}).get('thrown_reload_blast') or {}
        for reload in (row for row in prior['event_trace'] if row['kind'] == 'reload'):
            entered = original_reloads[reload['event_id']]
            if entered.get('consume_remaining_magazine_for_blast') is not True:
                raise ValueError('Reload blast must consume the actual modeled remaining magazine')
            if entered.get('refund_outcome') != 'none':
                raise ValueError('Reload blast needs refund_outcome=none; refund destination is unresolved')
            event_id = f"{proc['stream_id']}/{weapon_id}/reload/input-{reload['event_id']}/blast"
            target_count = packet_model.get('target_count')
            damage_class = packet_model.get('damage_class')
            if target_count is None or damage_class not in ('weapon', 'status'):
                unresolved.append({'event_id': event_id,
                                   'reason': 'Reload blast needs explicit target_count and Weapon/Status class'})
                continue
            blast_event = {'event_id': event_id, 'at': reload['at'],
                           'event': 'thrown_reload_blast', 'weapon_id': weapon_id,
                           'effect_type': 'damage_packet',
                           'consumed_ammo': reload['consumed_magazine_rounds'],
                           'target_count': target_count, 'instances': target_count}
            projected = project_event('weapon:g17-hazardous-object/thrown_reload_blast',
                blast_event, psi=(source_model.get('basis_values') or {}).get('psi'),
                evidence_mode=proc.get('evidence_mode'))
            source['events'].append(blast_event)
            projection['packets'].append({'event_id': event_id, 'at': reload['at'],
                'event': 'thrown_reload_blast', 'basis': 'psi',
                'basis_value': float((source_model.get('basis_values') or {})['psi']),
                'damage_class': damage_class, 'element': 'blast',
                'coefficient_percent': float(projected.coefficient * 100),
                'crit': False, 'weakspot': False, 'instances': target_count,
                'damage': float(projected.raw_damage),
                'source_status': projected.evidence_status + '; source packet '
                                 + projected.packet_id,
                'source_packet_id': projected.packet_id,
                'source_unresolved': list(projected.unresolved)})
    packet_models = source_model.get('packet_models') or {}
    original = deepcopy(scenario['events'])
    scheduled = {row['event_id']: row['at'] for row in prior['event_trace']
                 if row['event_id'] is not None}
    combined = []
    for order, event in enumerate(original):
        item = dict(event)
        if item['kind'] == 'shot':
            item['at'] = scheduled[item['event_id']]
        combined.append((float(item['at']), 0, order, item))
    source_packets = []
    for order, packet in enumerate(projection['packets']):
        if packet['event'] == 'direct_hit':
            continue
        name = packet['event']
        descriptor = packet_models.get(name) or packet_models.get(name.removesuffix('_tick')) or {}
        keyword = descriptor.get('keyword')
        if keyword is not None and keyword not in integrated_event_model.SUPPORTED_KEYWORDS:
            raise ValueError(f'{name}: unsupported keyword pool')
        damage_class = packet.get('damage_class')
        element = packet.get('element')
        if damage_class not in ('weapon', 'status') or element is None:
            unresolved.append({'event_id': packet['event_id'],
                               'reason': f'{name}: explicit Weapon/Status class and element required'})
            continue
        gilded_burn_crit = (packet.get('crit') is True and
            packet.get('weakspot') is not True and
            name == 'burn_tick' and
            keyword == 'burn' and damage_class == 'status' and element == 'blaze' and
            'armor:gilded-gauntlets' in (scenario.get('selected_armor_ids') or []) and
            scenario.get('encounter_mode') == 'pve_non_raidzone')
        if (packet.get('crit') or packet.get('weakspot')) and not gilded_burn_crit:
            unresolved.append({'event_id': packet['event_id'],
                               'reason': f'{name}: crit/weakspot eligibility outside timed scheduler'})
            continue
        expected = (packet['basis_value'] * packet['coefficient_percent']
                    * packet['instances'] / 100)
        if not math.isclose(packet['damage'], expected, rel_tol=1e-9, abs_tol=1e-9):
            unresolved.append({'event_id': packet['event_id'],
                               'reason': f'{name}: source packet includes a transform not represented by named pools'})
            continue
        item = {'kind': 'triggered_packet', 'event_id': packet['event_id'],
                'at': packet['at'], 'packet': {
                    'basis_value': packet['basis_value'],
                    'coefficient_percent': packet['coefficient_percent'],
                    'resolved_hits': packet['instances'],
                    'damage_class': damage_class, 'element': element,
                    **({'crit': True} if gilded_burn_crit else {}),
                    **({'keyword': keyword} if keyword else {})}}
        combined.append((float(packet['at']), 1, order, item))
        source_packets.append({'event_id': packet['event_id'], 'event': name,
                               'basis': packet['basis'],
                               'source_status': packet['source_status'],
                               'source_packet_id': packet.get('source_packet_id'),
                               'source_unresolved': packet.get('source_unresolved') or []})
    combined.sort(key=lambda row: (row[0], row[1], row[2]))
    second = {**scenario, 'events': [row[3] for row in combined]}
    final = integrated_event_model.evaluate(second, static_pools=static_pools,
                                            static_sources=static_sources)
    if final['shot_times'] != prior['shot_times']:
        raise ValueError('Sourced packets changed scheduled shot times; timing feedback needs an explicit rule')
    state_gaps, state_trace, modeled_state_ids = _apply_sourced_state(
        final, source['events'], source_packets, binding, proc,
        scenario['direct_packet'].get('basis_kind'))
    unresolved = [row for row in unresolved if row.get('event_id') not in modeled_state_ids]
    unresolved.extend(state_gaps)
    complete = not unresolved
    return {**final,
            'weapon_id': weapon_id, 'family': source['family'],
            'evidence_mode': source['evidence_mode'],
            'source_actions': actions, 'source_events': source['events'],
            'source_packets': source_packets, 'source_replayed_events_suppressed': source['replayed_events_suppressed'],
            'weapon_state_trace': state_trace,
            'weapon_sources': source['sources'], 'weapon_binding_missing': source['binding_missing'],
            'timed_result': final, 'known_damage_subtotal': final['total_damage'],
            'total_damage': final['total_damage'] if complete else None,
            'conditional_total_damage': final['total_damage'] if complete else None,
            'conditional_damage_per_second': final['conditional_damage_per_second'] if complete else None,
            'unresolved_source_packets': unresolved,
            'assumptions': ['One caller-entered landed hit per scheduled shot; outcomes and target conditions are explicit.',
                            'Sourced direct-hit projections are discarded; timed scheduler counts each direct shot once.',
                            'Sourced packets at equal timestamps follow original input events.',
                            'Supported weapon stat feedback follows the named after-direct-hit ordering; unsupported feedback blocks a complete modeled total.',
                            'Current-game proc odds, damage buckets and candidate level strengths remain unverified.'],
            'game_winner_established': False}
