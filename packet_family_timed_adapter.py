"""Generic shot-linked hook for the six source-qualified packet timelines.

The packet runner owns charges, counters, cooldowns and resolved target events;
the explicit combat scheduler owns bullet ammo, timing and active gear pools.
"""
from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import Path

import integrated_event_model
import weapon_packet_timeline_api as packet_api

ELIGIBILITY = json.loads((Path(__file__).parent / 'packet_timed_eligibility.json').read_text())['weapons']
if set(ELIGIBILITY) != set(packet_api.BINDINGS):
    raise RuntimeError('Packet hook eligibility table must cover every sourced packet weapon')


def evaluate(scenario, *, static_pools, static_sources=None):
    if not isinstance(scenario, dict) or not isinstance(scenario.get('weapon_proc'), dict):
        raise ValueError('Enter a weapon_proc packet hook')
    proc = scenario['weapon_proc']
    weapon_id = proc.get('weapon_id')
    if weapon_id not in packet_api.BINDINGS:
        raise ValueError('Choose one of the six source packet weapon bindings')
    first = integrated_event_model.evaluate(scenario, static_pools=static_pools,
                                            static_sources=static_sources)
    shots = {row['event_id']: row['at'] for row in first['event_trace']
             if row['kind'] == 'shot'}
    requested = proc.get('source_actions')
    if not isinstance(requested, list) or not 1 <= len(requested) <= 500:
        raise ValueError('Enter 1–500 explicit packet source actions')
    source_actions = []
    linked = set()
    policy = ELIGIBILITY[weapon_id]
    for action in requested:
        if not isinstance(action, dict) or action.get('kind') not in packet_api.FIELDS:
            raise ValueError('Packet source action kind is unsupported')
        item = dict(action)
        shot_id = item.pop('shot_event_id', None)
        if item['kind'] in packet_api.HIT_KINDS:
            if shot_id not in shots:
                raise ValueError('Hit packet action needs a selected scheduled shot_event_id')
            key = (item['kind'], shot_id)
            if key in linked:
                raise ValueError('One source hit kind cannot be attached twice to one shot')
            linked.add(key)
            if 'at' in item and not math.isclose(float(item['at']), shots[shot_id], abs_tol=1e-9):
                raise ValueError('Packet action time disagrees with scheduled shot')
            item['at'] = shots[shot_id]
        else:
            if shot_id is not None:
                raise ValueError('Resource observations and orb ticks use explicit time, not a shot link')
            at = item.get('at')
            if isinstance(at, bool) or not isinstance(at, (int, float)) or not math.isfinite(at) or not 0 <= at <= scenario['duration_seconds']:
                raise ValueError('Nonshot packet action needs explicit time within encounter')
        if not isinstance(item.get('input_id'), str) or not item['input_id']:
            raise ValueError('Each packet source action needs a stable input_id')
        source_actions.append(item)
    linked_shots = {shot_id for kind, shot_id in linked
                    if kind == policy['hit_action_kind']}
    wrong_hit_kinds = {kind for kind, _ in linked if kind != policy['hit_action_kind']}
    if wrong_hit_kinds:
        raise ValueError('Source hit action kind does not match the selected weapon binding')
    exclusions = proc.get('ineligible_shots') or {}
    if not isinstance(exclusions, dict):
        raise ValueError('ineligible_shots must map scheduled shot IDs to explicit reasons')
    if policy['coverage'] == 'every_landed_hit' and exclusions:
        raise ValueError('Every landed shot needs its source hit action for this weapon')
    if set(exclusions) & linked_shots or set(exclusions) - set(shots):
        raise ValueError('Ineligible shot entries must be distinct selected shots without source hit actions')
    if policy['coverage'] == 'conditional' and any(
            reason != policy['ineligible_reason'] for reason in exclusions.values()):
        raise ValueError('Ineligible shot reason must match the named source eligibility policy')
    missing_hits = set(shots) - linked_shots - set(exclusions)
    if missing_hits:
        raise ValueError('Every eligible modeled landed hit needs a source action or explicit ineligible_shots entry: '
                         + ', '.join(sorted(missing_hits)))
    model = proc.get('damage_model') or {}
    if not isinstance(model, dict) or model.get('bonus_pools_percent') or model.get('direct'):
        raise ValueError('Source packet projection cannot repeat direct hits or selected bonus pools')
    if model.get('duration_seconds') not in (None, scenario['duration_seconds']):
        raise ValueError('Source packet and scheduler encounter durations differ')
    model = {**model, 'duration_seconds': scenario['duration_seconds']}
    source = packet_api.simulate({'weapon_id': weapon_id,
        'evidence_mode': proc.get('evidence_mode'),
        'stream_id': proc.get('stream_id'),
        'actions': source_actions, 'damage_model': model,
        'observed_charges': proc.get('observed_charges', 0),
        'observed_charged_rounds': proc.get('observed_charged_rounds', 0),
        'counter_overflow': proc.get('counter_overflow')})
    projection = source['damage_projection']
    unresolved = [row for row in projection['unresolved_damage_events']
                  if row.get('reason') != 'Direct bullet damage is outside this packet-only scenario']
    hypotheses = proc.get('packet_hypotheses') or {}
    if not isinstance(hypotheses, dict):
        raise ValueError('Packet hypotheses must be keyed by source packet identity')
    events = deepcopy(scenario['events'])
    times = {row['event_id']: row['at'] for row in first['event_trace']
             if row['event_id'] is not None}
    merged = []
    for order, event in enumerate(events):
        item = dict(event)
        if item['kind'] == 'shot':
            item['at'] = times[item['event_id']]
        merged.append((float(item['at']), 0, order, item))
    source_events = {row['event_id']: row for row in source['events']}
    source_packets = []
    bases = model.get('basis_values') or {}
    for order, packet in enumerate(projection['packets']):
        packet_id = packet['packet_id']
        hypothesis = hypotheses.get(packet_id) or {}
        if not isinstance(hypothesis, dict):
            raise ValueError('Packet hypothesis must be an object')
        damage_class = packet['damage_class']
        element = packet['element']
        for name, sourced in (('damage_class', damage_class), ('element', element)):
            if sourced is not None and name in hypothesis and hypothesis[name] != sourced:
                raise ValueError(f'{packet_id}: {name} hypothesis conflicts with sourced binding')
        damage_class = damage_class or hypothesis.get('damage_class')
        element = element if element is not None else hypothesis.get('element')
        if damage_class not in ('weapon', 'status') or element not in integrated_event_model.ELEMENTS:
            unresolved.append({'event_id': packet['event_id'],
                               'reason': f'{packet_id}: explicit Weapon/Status class and element required'})
            continue
        keyword = hypothesis.get('keyword')
        if keyword is not None and keyword not in integrated_event_model.KEYWORD_POOLS:
            raise ValueError(f'{packet_id}: unsupported keyword pool')
        basis = packet['basis']
        basis_value = bases.get(basis) if basis != 'reference_damage' else (
            model.get('reference_values') or {}).get(
                packet_api.DAMAGE['packets'][packet_id]['reference_key'])
        if basis_value is None:
            unresolved.append({'event_id': packet['event_id'],
                               'reason': f'{packet_id}: caller basis missing'})
            continue
        coefficient_percent = float(packet['coefficient']) * 100
        expected = float(basis_value) * coefficient_percent * packet['instances'] / 100
        if not math.isclose(float(packet['raw_damage']), expected, rel_tol=1e-9, abs_tol=1e-9):
            unresolved.append({'event_id': packet['event_id'],
                               'reason': f'{packet_id}: source transform cannot be represented by named pools'})
            continue
        at = float(source_events[packet['event_id']]['at'])
        if at > scenario['duration_seconds']:
            unresolved.append({'event_id': packet['event_id'],
                               'reason': f'{packet_id}: packet after encounter duration'})
            continue
        item = {'kind': 'triggered_packet', 'event_id': packet['event_id'], 'at': at,
                'packet': {'basis_value': basis_value,
                           'coefficient_percent': coefficient_percent,
                           'resolved_hits': packet['instances'],
                           'damage_class': damage_class, 'element': element,
                           **({'keyword': keyword} if keyword else {})}}
        merged.append((at, 1, order, item))
        source_packets.append({'event_id': packet['event_id'],
                               'source_packet_id': packet_id,
                               'source_status': packet['evidence_status'],
                               'source_unresolved': packet['unresolved'],
                               'target': source_events[packet['event_id']].get('target')})
    merged.sort(key=lambda row: (row[0], row[1], row[2]))
    final = integrated_event_model.evaluate({**scenario, 'events': [row[3] for row in merged]},
                                            static_pools=static_pools,
                                            static_sources=static_sources)
    if final['shot_times'] != first['shot_times']:
        raise ValueError('Packet hook changed scheduled shot times; timing feedback requires a sourced operator')
    complete = not unresolved
    return {**final, 'weapon_id': weapon_id, 'family': source['family'],
            'evidence_mode': source['evidence_mode'],
            'source_actions': source_actions, 'source_events': source['events'],
            'source_hit_coverage': {'linked_shots': sorted(linked_shots),
                                    'ineligible_shots': exclusions,
                                    'coverage_policy': policy['coverage']},
            'source_packets': source_packets,
            'source_replayed_events_suppressed': source['replayed_events_suppressed'],
            'weapon_sources': source['sources'],
            'weapon_binding_missing': source['binding_missing'],
            'resource_state': source['resource_state'],
            'timed_result': final, 'known_damage_subtotal': final['total_damage'],
            'total_damage': final['total_damage'] if complete else None,
            'conditional_total_damage': final['total_damage'] if complete else None,
            'conditional_damage_per_second': final['conditional_damage_per_second'] if complete else None,
            'unresolved_source_packets': unresolved,
            'assumptions': ['Every source hit hook names its scheduled shot; other events have explicit times.',
                            'Charges, charged rounds, targets, cooldowns and counter policy come from entered observations or dated bindings.',
                            'Sourced packet classes, elements and keyword grouping use source values or explicit hypotheses.',
                            'Source base packets exclude intrinsic bonuses, target mitigation and unentered effects.',
                            'Preview and historical coefficients are conditional scenarios, not certified current-game damage.'],
            'game_winner_established': False}
