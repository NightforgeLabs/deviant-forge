"""Read-only, explicit-input weapon event scenarios for nine sourced families."""
from __future__ import annotations

from collections import Counter
from decimal import Decimal

from weapon_mechanics.operators import D, I
from weapon_mechanics.runner import WeaponTimeline, load_bindings

PACKAGE = load_bindings()
WEAPONS = PACKAGE['weapons']
SOURCES = PACKAGE['sources']
MAX_ACTIONS = 500


def _jsonable(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, list):
        return [_jsonable(row) for row in value]
    if isinstance(value, dict):
        return {key: _jsonable(row) for key, row in value.items()}
    return value


def coverage():
    import weapon_packet_timeline_api
    from packet_family_timed_adapter import ELIGIBILITY
    packet_hooks = {identity: {
        'required_caller_inputs': binding['required_caller_inputs'],
        'evidence_status': binding['evidence_status'],
        'scheduled_hit_coverage': ELIGIBILITY[identity],
        'timed_integration': 'explicit_source_actions_and_named_packet_hypotheses',
        'remaining_source_gaps': binding['unresolved']}
        for identity, binding in weapon_packet_timeline_api.BINDINGS.items()}
    return {'executable_representative_weapons': len(WEAPONS),
            'historical_only_weapons': [identity for identity, binding in WEAPONS.items()
                                        if binding.get('version_scope', '').startswith('historical_release_only')],
            'additional_packet_timeline_weapons': len(weapon_packet_timeline_api.BINDINGS),
            'integrated_timed_representative_weapons': len(WEAPONS),
            'integrated_timed_packet_weapons': len(packet_hooks),
            'packet_hook_coverage': packet_hooks,
            'held_packet_timeline_weapons': [],
            'keyword_families': sorted({row['family'] for row in WEAPONS.values()}),
            'explicit_packet_projection_supported': True,
            'current_full_damage_profiles': 0,
            'scope': 'Dated release or preview event scenarios with explicit inputs; no current-game DPS certification.'}


def simulate(request):
    if not isinstance(request, dict):
        raise ValueError('Weapon timeline request must be an object')
    weapon_id = request.get('weapon_id')
    import weapon_packet_timeline_api
    if weapon_id in weapon_packet_timeline_api.BINDINGS:
        return weapon_packet_timeline_api.simulate(request)
    if weapon_id not in WEAPONS:
        raise ValueError('Choose one of the nine bound weapon timeline scenarios')
    stream_id = request.get('stream_id')
    if not isinstance(stream_id, str) or not stream_id or len(stream_id) > 100:
        raise ValueError('Supply a stable, nonempty stream_id of at most 100 characters')
    actions = request.get('actions')
    if not isinstance(actions, list) or not 1 <= len(actions) <= MAX_ACTIONS:
        raise ValueError('Supply 1–500 ordered source actions')
    magazine = request.get('magazine')
    if magazine is not None and (isinstance(magazine, bool) or not isinstance(magazine, int)
                                or not 1 <= magazine <= 1000):
        raise ValueError('Magazine must be a whole number from 1 to 1000')
    timeline = WeaponTimeline(weapon_id, request.get('evidence_mode'),
                              request.get('model_mode'), magazine=magazine,
                              stream_id=stream_id)
    events = []
    seen_event_ids = set()
    replayed_event_count = 0
    for index, action in enumerate(actions):
        if not isinstance(action, dict):
            raise ValueError('Each source action must be an object')
        kind = action.get('kind')
        input_id = action.get('input_id')
        if not isinstance(input_id, str) or not input_id or len(input_id) > 100:
            raise ValueError('Each source action needs a stable input_id of at most 100 characters')
        at = action.get('at')
        if kind == 'hit':
            out = timeline.hit(at, action.get('target'), weakspot=action.get('weakspot', False),
                               distance=action.get('distance'), rolls=action.get('rolls'),
                               conditions=action.get('conditions'), input_id=input_id)
        elif kind == 'reload':
            out = timeline.reload(at, loaded_rounds=action.get('loaded_rounds'),
                                  refund_roll=action.get('refund_roll'),
                                  refund_rounding=action.get('refund_rounding'), input_id=input_id)
        elif kind == 'observe_stacks':
            out = timeline.observe_keyword_stacks(at, action.get('keyword'),
                                                  action.get('count'), input_id=input_id)
        elif kind == 'fire':
            if timeline.ammo is None:
                raise ValueError('Fire action needs an explicitly entered magazine')
            rounds = I(action.get('rounds', 1), name='rounds')
            if not 1 <= rounds <= 1000:
                raise ValueError('Fire rounds must be 1–1000')
            timestamp = D(at)
            payload = {'at':timestamp, 'rounds':rounds}
            cached = timeline._begin('fire', input_id, timestamp, payload)
            if cached is not None:
                out = cached
            else:
                consumed = timeline.ammo.fire(timestamp, rounds)
                out = timeline._end('fire', input_id, timestamp, payload,
                                    [{'at':timestamp, 'event':'ammo_fired', 'rounds':consumed,
                                      'requested_rounds':rounds}])
        else:
            raise ValueError(f'Action {index}: use hit, fire, reload or observe_stacks; derived events cannot be fed back')
        for event in out:
            if event['event_id'] in seen_event_ids:
                replayed_event_count += 1
                continue
            seen_event_ids.add(event['event_id'])
            events.append(event)
        if len(events) > 10000:
            raise ValueError('Weapon timeline emitted too many events')
    binding = WEAPONS[weapon_id]
    source_ids = sorted({rule['source'] for rule in binding['rules'] if rule.get('source')}
                        | {row['source'] for row in binding.get('damage_events', []) if row.get('source')}
                        | {row['source'] for row in binding.get('modifiers', []) if row.get('source')}
                        | set(binding.get('rework_sources', [])))
    counts = Counter(row['effect_type'] for row in events)
    projection = None
    if request.get('damage_model') is not None:
        import event_damage_projection
        projection = event_damage_projection.project(
            actions, events, binding, request['damage_model'],
            stream_id=stream_id, weapon_id=weapon_id,
            evidence_mode=timeline.evidence_mode)
    return _jsonable({'weapon_id':weapon_id, 'family':binding['family'],
                     'evidence_mode':timeline.evidence_mode, 'model_mode':timeline.model_mode,
                     'stream_id':stream_id, 'events':events,
                     'replayed_events_suppressed':replayed_event_count,
                     'event_counts':dict(counts),
                     'ammo':({'capacity':timeline.ammo.capacity,'rounds':timeline.ammo.rounds}
                             if timeline.ammo else None),
                     'sources':{source_id:SOURCES[source_id] for source_id in source_ids},
                     'version_scope':binding.get('version_scope', 'dated_release_or_preview_model'),
                     'binding_missing':binding.get('missing', []),
                     'damage_projection': projection,
                     'total_damage': projection['total_damage'] if projection else None,
                     'damage_per_second': projection['damage_per_second'] if projection else None,
                     'assumptions':['Each hit is a caller-entered landed hit, not an inferred shot.',
                                    'Every proc roll, target condition and ammo load is explicitly entered.',
                                    'Derived triggers are never fed back as landed hits; damage packets are summed only when explicitly modeled.',
                                    'Release-at-date and preview rules are not verified current in-game tooltips.',
                                    'Event order at an equal timestamp is the supplied action order.']})
