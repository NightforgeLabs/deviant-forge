"""Read-only, opt-in stateful community mod scenarios."""
from __future__ import annotations

import json
from pathlib import Path

from stateful_candidate_adapter_v7_1 import initial_state, execute_candidate

PACKET = json.loads((Path(__file__).parent / 'evidence_packets/mod-core-v7-stateful-candidates.json').read_text())
BINDINGS = {row['catalog_id']: row for row in PACKET['bindings']}


def coverage():
    return {'candidate_bindings': len(BINDINGS),
            'executable_candidate_bindings': len(BINDINGS),
            'adapter_version': 'v7.1',
            'operator_counts': PACKET['statistics']['operator_counts'],
            'exact_level_observations': 0, 'current_numeric_bindings': 0,
            'scope': 'Opt-in March 2026 community candidate state operators; no current level or whole DPS certified.'}


def simulate(request):
    if not isinstance(request, dict):
        raise ValueError('Stateful mod scenario must be an object')
    identity = request.get('catalog_id')
    binding = BINDINGS.get(identity)
    if binding is None:
        raise ValueError('Choose one of the 39 candidate stateful mod identities')
    level = request.get('level')
    if isinstance(level, bool) or not isinstance(level, int) or not 1 <= level <= 17:
        raise ValueError('Enter a mod level 1–17 for scenario identity; candidate strength is not bound to that level')
    if request.get('allow_candidate') is not True:
        raise ValueError('Community stateful candidate requires allow_candidate=true')
    initial = request.get('initial')
    assumptions = request.get('assumptions') or {}
    events = request.get('events')
    if not isinstance(initial, dict) or not isinstance(assumptions, dict):
        raise ValueError('Initial state and assumptions must be objects')
    if not isinstance(events, list) or len(events) > 500:
        raise ValueError('Supply at most 500 ordered state events')
    state = initial_state(binding, **initial)
    trace = []
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            raise ValueError(f'State event {index} must be an object')
        result = execute_candidate(binding, state, event,
                                   allow_candidate=True, assumptions=assumptions)
        state = result['state']
        trace.append({'event_index': index, 'event': event,
                      'outputs': result['outputs'], 'unresolved': result['unresolved'],
                      'state_after': state})
    return {'catalog_id': identity, 'selected_level': level,
            'operator': binding['operator'], 'evidence_mode': 'explicit_community_candidate',
            'source_text_sha256': binding['candidate_text_sha256'],
            'source_warning': 'Community primary tooltip candidate; selected level and current game version are unverified.',
            'current_level_certified': False, 'whole_dps_certified': False,
            'outputs': [output for step in trace for output in step['outputs']],
            'trace': trace, 'final_state': state,
            'unresolved': sorted(set(issue for step in trace for issue in step['unresolved']))}
