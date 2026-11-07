"""Six additional source-qualified weapon event timelines with packet-only arithmetic."""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from decimal import Decimal

from weapon_mechanics.packet_timeline_v4 import PacketTimelineV4, load_timeline_bindings
from weapon_mechanics.damage_projection_v3 import load_damage_bindings, project_event, packet_dps

BINDINGS = load_timeline_bindings()['weapons']
DAMAGE = load_damage_bindings()
HIT_KINDS = {'critical_pulse_start_orb', 'hammerhead_chain_hit', 'boom_boom_hit',
             'pyroclasm_charged_shot', 'pathfinder_charged_shot', 'holographic_hit'}
FIELDS = {
    'resource_balance': ('charges', 'charged_rounds'),
    'critical_pulse_start_orb': ('hit_target', 'orb_duration_seconds', 'first_tick_delay_seconds', 'include_endpoint'),
    'critical_pulse_orb_tick': ('orb_id', 'target', 'distance_meters'),
    'hammerhead_chain_hit': ('primary_target', 'primary_power_surge_status', 'nearby_affected_targets'),
    'boom_boom_hit': ('explosion_targets',),
    'pyroclasm_charged_shot': ('resolved_damage_units',),
    'pathfinder_charged_shot': ('charge_cost', 'pierced_targets'),
    'holographic_hit': ('pulse_targets',),
}
METHOD = {'resource_balance': 'observe_resource_balance',
          'critical_pulse_start_orb': 'critical_pulse_start_orb',
          'critical_pulse_orb_tick': 'critical_pulse_orb_tick',
          'hammerhead_chain_hit': 'hammerhead_chain_hit',
          'boom_boom_hit': 'boom_boom_hit',
          'pyroclasm_charged_shot': 'pyroclasm_charged_shot',
          'pathfinder_charged_shot': 'pathfinder_charged_shot',
          'holographic_hit': 'holographic_hit'}


def _plain(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, tuple):
        return [_plain(x) for x in value]
    if isinstance(value, list):
        return [_plain(x) for x in value]
    if isinstance(value, dict):
        return {key: _plain(val) for key, val in value.items()}
    return value


def simulate(request):
    if not isinstance(request, dict) or request.get('weapon_id') not in BINDINGS:
        raise ValueError('Choose one of the six source packet weapon timelines')
    actions = request.get('actions')
    if not isinstance(actions, list) or not 1 <= len(actions) <= 500:
        raise ValueError('Supply 1–500 ordered source actions')
    weapon_id = request['weapon_id']
    timeline = PacketTimelineV4(weapon_id, request.get('evidence_mode'),
                                request.get('stream_id'),
                                observed_charges=request.get('observed_charges', 0),
                                observed_charged_rounds=request.get('observed_charged_rounds', 0),
                                counter_overflow=request.get('counter_overflow'))
    events, seen, replayed = [], set(), 0
    for index, action in enumerate(actions):
        if not isinstance(action, dict) or action.get('kind') not in FIELDS:
            raise ValueError(f'Action {index} has an unsupported packet-timeline kind')
        kind = action['kind']
        arguments = {key: action[key] for key in FIELDS[kind] if key in action}
        emitted = getattr(timeline, METHOD[kind])(action.get('at'), action.get('input_id'), **arguments)
        for event in emitted:
            if event['event_id'] in seen:
                replayed += 1
            else:
                seen.add(event['event_id'])
                events.append(event)
        if len(events) > 10000:
            raise ValueError('Too many resolved packet events')
    binding = BINDINGS[weapon_id]
    damage_spec = DAMAGE['packets'][binding['packet_id']]
    model = request.get('damage_model')
    projection = None
    if model is not None:
        if not isinstance(model, dict):
            raise ValueError('Packet damage model must be an object')
        if model.get('bonus_pools_percent'):
            raise ValueError('Packet-only source base does not apply bonus pools; use explicit component model separately')
        bases = model.get('basis_values') or {}
        if not isinstance(bases, dict):
            raise ValueError('Basis values must be an object')
        duration = model.get('duration_seconds')
        known, unresolved = [], []
        for event in events:
            if event.get('packet_id'):
                try:
                    result = project_event(event['packet_id'], event,
                                           attack=bases.get('attack'), psi=bases.get('psi'),
                                           evidence_mode=timeline.evidence_mode)
                    known.append(_plain(asdict(result)))
                except ValueError as error:
                    unresolved.append({'event_id': event['event_id'], 'at': float(event['at']),
                                       'reason': str(error)})
            elif event.get('effect_type') == 'unresolved':
                unresolved.append({'event_id': event['event_id'], 'at': float(event['at']),
                                   'reason': event['reason']})
        for action in actions:
            if action['kind'] in HIT_KINDS:
                unresolved.append({'event_id': action['input_id'], 'at': float(action['at']),
                                   'reason': 'Direct bullet damage is outside this packet-only scenario'})
        subtotal = sum(row['total_with_external'] for row in known)
        timing = []
        rate = None
        if duration is None:
            timing.append({'reason': 'Enter exposure duration for a packet-only rate'})
        else:
            rate = float(packet_dps(subtotal, duration_seconds=duration))
        projection = {'scope': 'Sourced base packets only; direct bullets, target mitigation, uncertain class and bonus pools excluded',
                      'known_damage_subtotal': subtotal,
                      'packet_only_damage_per_second': rate,
                      'total_damage': None, 'damage_per_second': None,
                      'packets': known, 'unresolved_damage_events': unresolved,
                      'unresolved_timing': timing}
    source_key = damage_spec['coefficient_source']
    return _plain({'weapon_id': weapon_id, 'family': damage_spec['family'],
                   'evidence_mode': timeline.evidence_mode,
                   'model_mode': 'caller_resolved_packet_targets',
                   'stream_id': timeline.stream_id, 'events': events,
                   'event_counts': dict(Counter(event['effect_type'] for event in events)),
                   'replayed_events_suppressed': replayed, 'ammo': None,
                   'resource_state': {'observed_charges': timeline.observed_charges,
                                      'observed_charged_rounds': timeline.observed_charged_rounds},
                   'sources': {source_key: DAMAGE['sources'][source_key]},
                   'binding_missing': binding['unresolved'],
                   'damage_projection': projection, 'total_damage': None,
                   'damage_per_second': None,
                   'assumptions': ['Only caller-resolved targets and observed resources create packets.',
                                   'Packet subtotal is not complete weapon damage or current game DPS.']})
