"""Reproduce directly observed v3 suffix profiles; never transfer a roll."""
import json
from pathlib import Path

ROOT = Path(__file__).parent
packet = json.loads((ROOT / 'evidence_packets/suffix-candidate-v3.json').read_text())
observations = {row['id']: row for row in json.loads((ROOT / 'evidence_packets/suffix-cross-slot-v2.json').read_text())['independent_observations']}
already = set(json.loads((ROOT / 'catalog_reviewed_profiles.json').read_text())['entries'])
already.update(json.loads((ROOT / 'catalog_held_profiles.json').read_text())['entries'])
corrections = {(row['observation_id'], row['row_index']): row for row in packet['source_corrections']}
entries = {}
for profile in packet['exact_observations']:
    catalog_id, level = profile['catalog_id'], profile['level']
    key = f'{catalog_id}:{level}:unknown'
    if key in already:
        continue
    observed = next((observations[ref] for ref in profile['source_refs'] if ref in observations), None)
    if observed is None:
        # The older packet already resolves through static numeric evidence.
        # Preserve that path and add only the newly held video/screenshot rows.
        continue
    source = observed['source']
    if not source.get('path') or not source.get('sha256'):
        raise ValueError(f'Missing source provenance: {key}')
    stamp = f"#t={source['time_seconds']}s" if source.get('time_seconds') is not None else ''
    attributes = []
    for index, raw in enumerate(observed['rows']):
        condition = corrections.get((observed['id'], index), {}).get('corrected_condition', raw.get('condition'))
        stat_type = raw['stat_type']
        row = {'name': stat_type, 'stat_type': stat_type,
               'tier': raw['tier'], 'value_percent': raw['value_percent'],
               'unit': 'percent', 'direction': 'increase',
               'source': source['path'] + stamp,
               'source_status': 'directly observed variant and level; game build version unknown'}
        if condition and condition != 'unconditional':
            row['condition'] = 'low HP' if condition == 'scales_with_low_hp' else condition
        if raw.get('conditional_bonus_percent') is not None:
            row['conditional_bonus_percent'] = raw['conditional_bonus_percent']
        attributes.append(row)
    entries[key] = {'catalog_id': catalog_id, 'level': level,
                    'source_frame': source['path'], 'source_media': source['path'],
                    'source_timestamp_seconds': source.get('time_seconds'),
                    'source_sha256': source['sha256'], 'recorded_at': '2026-11-01',
                    'evidence_context': f"exact {source['kind']} {observed['id']}; game build version unknown",
                    'evidence_status': 'direct source observation; exact variant and level; game build version unknown',
                    'source_refs': profile['source_refs'], 'shiny_status': 'unknown',
                    'attributes': attributes}
if len(entries) != 13:
    raise ValueError(f'Expected 13 new held direct profiles, found {len(entries)}')
(ROOT / 'catalog_held_suffix_profiles.json').write_text(json.dumps({'entries': entries, 'source_packet': 'evidence_packets/suffix-candidate-v3.json', 'ownership_inferred': False}, indent=2) + '\n')
