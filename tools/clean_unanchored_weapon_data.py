"""Remove unanchored weapon numbers from the active app after a full backup.

The source packets remain in the dated rollback snapshot. This command never
edits personal SQLite state, media, identity catalogs, images, or named item
pages. Run against an isolated checkout first and verify tests before install.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKETS = ROOT / 'evidence_packets'


def save(path, payload):
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n')


def clean():
    baseline_path = PACKETS / 'weapon-baselines-published.json'
    baseline = json.loads(baseline_path.read_text())
    removed_baselines = max(len(baseline['weapons']), baseline.get('removed_count', 0))
    baseline['weapons'] = {}
    baseline['model_status'] = 'archived_unanchored_values_removed_from_active_app'
    baseline['removed_count'] = removed_baselines
    save(baseline_path, baseline)

    v3_path = PACKETS / 'weapon-reference-v3.json'
    v3 = json.loads(v3_path.read_text())
    removed_historical = removed_pages = 0
    for row in v3['rows'].values():
        removed_historical += row.get('historical_catalog_profile') is not None
        removed_pages += row.get('database_page_reference') is not None
        row['historical_catalog_profile'] = None
        row['database_page_reference'] = None
        row['typed_field_discrepancies'] = {}
        row['profile_use_gate'] = 'archived_unanchored_numbers_removed; exact item-ID pages or explicit caller inputs required'
    for key in ('historical_profile_records', 'historical_damage_values',
                'historical_rpm_magazine_reload_seconds_complete',
                'direct_database_page_transcriptions',
                'database_pages_with_historical_overlap',
                'overlapping_rows_with_typed_field_discrepancy'):
        v3['counts'][key] = 0
    v3['counts']['source_statuses'] = {'numeric_rows_removed': len(v3['rows'])}
    v3['active_numeric_status'] = 'unanchored_historical_and_page_numbers_removed'
    save(v3_path, v3)

    removed_deltas = {}
    for name in ('weapon-reference-v4-delta.json', 'weapon-reference-v5-delta.json'):
        path = PACKETS / name
        packet = json.loads(path.read_text())
        removed_deltas[name] = len(packet['new_database_page_references'])
        packet['new_database_page_references'] = {}
        if 'new_page_count' in packet:
            packet['new_page_count'] = 0
        if 'combined_direct_page_count' in packet:
            packet['combined_direct_page_count'] = 0
        if 'summary' in packet and isinstance(packet['summary'], dict):
            packet['summary'] = {'active_direct_page_refs': 0,
                                 'archive_status': 'unanchored_numeric_rows_removed'}
        packet['active_numeric_status'] = 'unanchored_page_numbers_removed'
        save(path, packet)
    profile_path = ROOT / 'weapon_profiles.json'
    profiles = json.loads(profile_path.read_text())
    removed_legacy_profiles = len(profiles['profiles'])
    profiles['profiles'] = {}
    profiles['active_numeric_status'] = 'unanchored_legacy_profile_removed'
    save(profile_path, profiles)
    armor_path = PACKETS / 'armor-table-published.json'
    armor = json.loads(armor_path.read_text())
    removed_armor_rows = sum(len(star['levels']) for slot in armor['items'].values()
                             for rarity in slot.values()
                             for star in rarity['stars'].values())
    armor['items'] = {}
    armor['calibration_bonuses'] = {}
    armor['removed_unanchored_rows'] = max(removed_armor_rows,
                                          armor.get('removed_unanchored_rows', 0))
    armor['model_status'] = 'archived_slot_rarity_candidate_values_removed_from_active_app'
    save(armor_path, armor)
    magnitude_path = ROOT / 'catalog_effect_magnitudes.json'
    magnitudes = json.loads(magnitude_path.read_text())
    removed_magnitude_rows = magnitudes['candidate_rows']
    magnitudes['entries'] = {}
    magnitudes['identities_with_numeric_candidates'] = 0
    magnitudes['candidate_rows'] = 0
    magnitudes['removed_unmapped_candidate_rows'] = max(
        removed_magnitude_rows, magnitudes.get('removed_unmapped_candidate_rows', 0))
    magnitudes['active_status'] = 'unmapped_field_guide_level_magnitudes_archived'
    save(magnitude_path, magnitudes)
    return {'unanchored_calculator_baselines_removed': removed_baselines,
            'historical_profile_rows_removed': removed_historical,
            'unlabeled_page_rows_removed': removed_pages + sum(removed_deltas.values()),
            'legacy_damage_profiles_removed': removed_legacy_profiles,
            'unanchored_generic_armor_rows_removed': armor['removed_unanchored_rows'],
            'unmapped_mod_effect_magnitude_rows_removed': magnitudes['removed_unmapped_candidate_rows'],
            'exact_named_item_tier_pages_retained': 5,
            'personal_database_changed': False, 'images_changed': False}


if __name__ == '__main__':
    print(json.dumps(clean(), indent=2))
