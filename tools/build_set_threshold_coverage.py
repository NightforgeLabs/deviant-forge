#!/usr/bin/env python3
"""Rebuild the 74-row set-threshold audit from catalog and source packet."""
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import catalog  # noqa: E402
import published_set_thresholds as thresholds  # noqa: E402


def behavior(descriptors):
    kinds = {row.get('kind') for row in descriptors}
    if kinds <= {'modifier'}:
        return 'static'
    if kinds <= {'conditional_modifier'}:
        return 'conditional'
    if kinds & {'resource_conversion', 'ammunition_restore', 'shield_generation',
                'consumable_use', 'resource_scaled_modifier'}:
        return 'resource_or_shield'
    if kinds & {'timed_modifier', 'stacking_modifier', 'stack_generation',
                'stack_cap_override', 'extra_stack_generation', 'state_activation',
                'state_entry', 'state_exit_penalty', 'duration_refresh',
                'environment_scaled_modifier', 'state_rule_override'}:
        return 'timed_stack_or_state'
    return 'mixed_or_unclassified'


def main():
    catalog_sets = [row for row in catalog.ENTRIES.values() if row['kind'] == 'set']
    counts = {row['id'].removeprefix('set:').replace('-', '_'): 4
              for row in catalog_sets}
    _, _, covered, _ = thresholds.evaluate(
        counts, 'pve_non_raidzone', .8, 'community_snapshot', {
            'stamina_fraction': .95, 'current_load': 81,
            'spotted_by_enemies': False, 'ambient_temperature_c': 20,
            'bastille_state_active': True})
    source_sets = thresholds.SETS
    records = []
    for catalog_set in catalog_sets:
        source = source_sets[catalog_set['id']]
        source_rows = {row['required_items']: row for row in source['thresholds']}
        for bonus in catalog_set['bonuses']:
            required = bonus['required_items']
            row = source_rows[required]
            status = row['binding_status']
            set_id = catalog_set['id'].removeprefix('set:').replace('-', '_')
            if (set_id, required) in covered:
                execution = ('historical_official_opt_in' if status == 'historical_official_release'
                             else 'community_snapshot_opt_in')
            elif (set_id, required) in {
                    ('bastille_set', 2), ('treacherous_tides_set', 2),
                    ('treacherous_tides_set', 3)}:
                execution = ('current_official_endpoint_only' if required == 3
                             else 'current_official_conditional')
            else:
                execution = 'unresolved'
            source_ids = row.get('source_ids') or []
            refs = [thresholds.SOURCE['sources'][key].get('url') or
                    thresholds.SOURCE['sources'][key].get('upstream_repository')
                    for key in source_ids]
            records.append({
                'catalog_set_id': catalog_set['id'], 'required_items': required,
                'catalog_description': bonus['description'],
                'catalog_description_currentness': (
                    'superseded_or_conflicting' if set_id == 'treacherous_tides_set' or
                    (set_id == 'savior_set' and required == 3)
                    else 'historical_snapshot_not_current_certified'),
                'behavior_class': behavior(row.get('descriptors') or []),
                'source_status': status, 'source_refs': refs,
                'execution': execution,
                'remaining_action': (None if execution != 'unresolved' else
                    'Verify current magnitude and activation, or implement the event, stack, resource and rounding semantics with explicit evidence.'),
            })
    if len(records) != 74 or len(covered) != 41:
        raise AssertionError('Set audit changed; inspect catalog and source packet before publishing')
    result = {
        'schema_version': 1,
        'source_packet': 'set-threshold-source-v4.json',
        'source_packet_thresholds': 79,
        'catalog_set_identities': 20,
        'catalog_threshold_descriptions': 74,
        'extra_source_thresholds': 'Four Dark Resonance rows are outside the runtime catalog; Treacherous Tides current one-piece row has no matching runtime description.',
        'source_status_counts': dict(Counter(row['source_status'] for row in records)),
        'behavior_counts': dict(Counter(row['behavior_class'] for row in records)),
        'execution_counts': dict(Counter(row['execution'] for row in records)),
        'records': records,
    }
    path = ROOT / 'evidence_packets' / 'set-threshold-coverage-v1.json'
    path.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ('catalog_threshold_descriptions',
                        'source_status_counts', 'behavior_counts', 'execution_counts')}, indent=2))


if __name__ == '__main__':
    main()
