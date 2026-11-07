import hashlib
import json
import sqlite3
import unittest
from collections import Counter
from pathlib import Path

import catalog
import field_guide_profiles
import planned_advisor

ROOT = Path(__file__).resolve().parents[1]


class ReviewedCatalogProfileTests(unittest.TestCase):
    def test_exact_recording_overlay_is_source_checked_and_never_ownership(self):
        snapshot = catalog.REVIEWED
        self.assertEqual(len(snapshot['entries']), 43)
        self.assertEqual(snapshot['conflicts'], [])
        for entry in snapshot['entries'].values():
            self.assertEqual(entry['evidence_status'],
                             'source_text_and_numbers_checked; exact current Field Guide variant and level')
            self.assertNotIn('ownership', entry)
            frame = ROOT / 'data' / entry['source_frame']
            self.assertEqual(hashlib.sha256(frame.read_bytes()).hexdigest(), entry['source_sha256'])
        coverage = Counter(catalog.resolve(entry['catalog_id'], entry['level'])['attribute_coverage']
                           for entry in snapshot['entries'].values())
        self.assertEqual(coverage, {'complete': 36, 'partial': 7})
        summary = catalog.coverage()
        self.assertEqual(summary['exact_mod_level_profiles'], 68)
        self.assertEqual(summary['selectable_mod_variants'], 984)
        self.assertEqual(summary['theoretical_mod_level_grid'], 16728)

    def test_held_against_all_odds_de12_is_exact_observation_not_owned_inference(self):
        identity = 'mod:boots_mod:against-all-odds-deviant-energy'
        observed = catalog.HELD['entries'][identity + ':12:unknown']
        self.assertNotIn('ownership', observed)
        self.assertEqual(hashlib.sha256(Path(observed['source_media']).read_bytes()).hexdigest(),
                         observed['source_sha256'])
        resolved = catalog.resolve(identity, 12)
        self.assertEqual(resolved['attribute_coverage'], 'complete')
        self.assertEqual([(row['name'], row['value_percent']) for row in resolved['known_attributes']],
                         [('Elemental DMG', 6.4), ('Status DMG', 3.6),
                          ('Magazine Capacity', 7.2), ('All DMG Boost', 3.0)])
        self.assertEqual(resolved['observed_profile']['source_timestamp_seconds'], 24)
        self.assertNotIn('attribute_coverage', catalog.resolve(identity, 11))

    def test_ambiguous_defensive_direction_stays_unknown(self):
        result = catalog.resolve('mod:chest_mod:quick-comeback-survival', 8)
        self.assertEqual(result['attribute_coverage'], 'partial')
        monster = next(row for row in result['known_attributes']
                       if row['name'] == 'Damage from monsters received')
        self.assertIsNone(monster['value_percent'])
        self.assertEqual(monster['direction'], 'ambiguous')
        self.assertTrue(result['observed_profile']['source_sha256'])

    def test_planned_build_uses_exact_profile_without_inferring_ownership(self):
        item = planned_advisor._entry('mod:chest_mod:quick-comeback-precision', 13)
        self.assertEqual(item['attribute_coverage'], 'complete')
        self.assertEqual([(row['name'], row['value_percent']) for row in item['attributes']],
                         [('Weakspot DMG', 7.2), ('Weapon DMG', 4.8),
                          ('Magazine Capacity', 7.2), ('All DMG Boost', 3.0)])
        result = planned_advisor.compare({}, {'top': {'catalog_id': 'armor:agent-top',
            'mod_id': 'mod:chest_mod:quick-comeback-precision', 'mod_level': 13}})
        self.assertFalse(result['component_analysis']['game_winner_established'])
        self.assertAlmostEqual(result['component_analysis']['component_ratios']['normal']['min'],
                               1.048 * 1.03)

    def test_export_matches_read_only_database_evidence(self):
        c = sqlite3.connect(f'file:{(ROOT / "data/advisor.sqlite3").resolve()}?mode=ro', uri=True)
        c.row_factory = sqlite3.Row
        try:
            for entry in catalog.REVIEWED['entries'].values():
                current = field_guide_profiles._reviewed_exact_rows(
                    c, entry['catalog_id'], entry['level'], entry['shiny_status'])
                self.assertIsNone(current['conflict'])
                self.assertEqual(current['known_attributes'], entry['attributes'])
        finally:
            c.close()


if __name__ == '__main__':
    unittest.main()
