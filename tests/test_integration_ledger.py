import unittest
import json
import threading
from http.server import ThreadingHTTPServer
from urllib.request import urlopen

import catalog
import integration_ledger
import server


class IntegrationLedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger = integration_ledger.build()
        cls.rows = cls.ledger['records']

    def test_exact_catalog_cardinality_and_unique_keys(self):
        expected = {'mod': 984, 'weapon': 138, 'armor': 162, 'set_threshold': 74}
        self.assertEqual(sum(expected.values()), len(self.rows))
        self.assertEqual(len(self.rows), len({row['catalog_id'] for row in self.rows}))
        for kind, total in expected.items():
            self.assertEqual(total, sum(row['kind'] == kind for row in self.rows))
            self.assertEqual(total, sum(self.ledger['counts'][kind].values()))

    def test_no_item_claimed_complete_without_all_requirements(self):
        for row in self.rows:
            if row['category'] == 'complete':
                self.assertFalse(row['known_missing'], row['catalog_id'])
                self.assertTrue(all(req['wired_path'] for req in row['requirements']), row['catalog_id'])
            self.assertTrue(row['requirements'])
            self.assertTrue(all(req['owner'] and req['next_action'] for req in row['requirements'] if req['missing']))

    def test_conflicting_memories_ledger_never_calls_old_rule_current(self):
        row = next(item for item in self.rows if item['catalog_id'] ==
                   'weapon:mg4-conflicting-memories')
        proc = next(req for req in row['requirements'] if req['name'] ==
                    'unique damage/proc effects and event ordering')
        self.assertEqual(proc['evidence'], 'historical_release_only_current_rework_unresolved')
        self.assertIn('September 2026 rework', proc['missing'])
        self.assertIn('historical_release', proc['missing'])
        self.assertIn('shipped current MG4 tooltip', proc['next_action'])

    def test_weapon_damage_basis_not_promoted(self):
        weapons = [row for row in self.rows if row['kind'] == 'weapon']
        self.assertEqual(0, sum(row['damage_basis_anchored'] for row in weapons))
        self.assertEqual(0, sum(row['name_matched_calculator_baseline'] for row in weapons))
        crank = next(row for row in weapons if row['catalog_id'] == 'weapon:kam-crank')
        self.assertIn('different named weapons', crank['requirements'][0]['missing'])
        self.assertNotEqual('complete', crank['category'])

    def test_aug_source_audit_separates_known_timing_from_missing_seconds(self):
        aug = next(row for row in self.rows if row['catalog_id'] == 'weapon:aug-electron-cloud')
        self.assertEqual([1,2,3,4,5], aug['exact_named_item_tiers'])
        self.assertEqual([1], aug['exact_named_item_star_cells']['5'])
        self.assertEqual([1,2,3,4,5,6], aug['exact_named_item_star_cells']['4'])
        self.assertEqual('evidence_packets/aug-electron-cloud-basis-audit.json',
                         aug['source_basis_audit'])
        self.assertIn('Tier 5 stars 2–6', aug['requirements'][0]['missing'])
        self.assertIn('720 RPM and 40 rounds', aug['requirements'][1]['missing'])
        self.assertIn('2.3 seconds/score 47', aug['requirements'][1]['missing'])
        self.assertNotEqual('complete', aug['category'])

    def test_non_scalar_layouts_name_code_gap_and_missing_curve_separately(self):
        self.assertEqual({'published_lunar_low_hp_maximum': 41,
                          'published_resonance_event_stack': 45,
                          'observed_lunar_maximum_curve_unknown': 3},
                         self.ledger['non_scalar_bonus_lv10'])
        lunar = next(row for row in self.rows if row['catalog_id'] ==
                     'mod:helmet_mod:elemental-havoc-lunar')
        self.assertEqual('candidate_bounded_low_hp', lunar['requirements'][0]['state'])
        self.assertIn('HP scaling curve', lunar['requirements'][0]['missing'])
        self.assertIn('component_compare._rows', lunar['requirements'][0]['wired_path'])
        resonance = next(row for row in self.rows if row['catalog_id'] ==
                         'mod:gloves_mod:crit-amplifier-resonance-deviant-energy')
        self.assertEqual('candidate_timed_operator_guided_and_advanced', resonance['requirements'][0]['state'])
        self.assertIn('refresh/overflow', resonance['requirements'][0]['missing'])
        self.assertEqual(2, sum(bool(row['structured_components'])
                                for row in resonance['bonus_lines_lv10']))

    def test_public_coverage_exposes_non_scalar_counts(self):
        http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        worker = threading.Thread(target=http.serve_forever, daemon=True)
        worker.start()
        try:
            with urlopen(f'http://127.0.0.1:{http.server_port}/api/integration-coverage') as response:
                result = json.load(response)
            self.assertEqual(self.ledger['non_scalar_bonus_lv10'],
                             result['non_scalar_bonus_lv10'])
            self.assertEqual(self.ledger['scoped_exact_level_model_ready'],
                             result['scoped_exact_level_model_ready'])
            self.assertNotIn('records', result)
        finally:
            http.shutdown();http.server_close();worker.join(timeout=2)

    def test_mod_missing_layout_is_not_numerically_complete(self):
        row = next(row for row in self.rows if row['catalog_id'] == 'mod:helmet_mod:fateful-strike')
        self.assertEqual(0, row['lv10_numeric_active_rows'])
        self.assertEqual('display_only', row['category'])

    def test_against_all_odds_lv7_is_scoped_only_when_no_hp_cost_entered(self):
        row = next(row for row in self.rows if row['catalog_id'] ==
                   'mod:boots_mod:against-all-odds-precision')
        self.assertEqual([7], row['scoped_exact_level_model_ready'])
        self.assertIn('Explicit no HP-cost events',
                      row['scoped_exact_level_paths'][0]['scenario_inputs'][0])
        self.assertEqual('partial', row['category'])  # Other levels and HP-cost stacks remain open.

    def test_striving_and_bullet_exact_scopes_require_named_events(self):
        for identity, level, phrase in (
            ('mod:boots_mod:power-of-striving-downstar-deviant-energy', 9, 'no stamina-loss events'),
            ('mod:pants_mod:bullet-siphon-aero-deviant-energy', 12, 'bullet consumption')):
            row = next(r for r in self.rows if r['catalog_id'] == identity)
            self.assertEqual([level], row['scoped_exact_level_model_ready'])
            self.assertIn(phrase, row['scoped_exact_level_paths'][0]['scenario_inputs'][0])
            self.assertEqual('partial', row['category'])

    def test_set_records_match_runtime_descriptions(self):
        self.assertEqual(sum(len(item['bonuses']) for item in catalog.DATA['sets']), 74)
        self.assertEqual(74, sum(row['kind'] == 'set_threshold' for row in self.rows))

    def test_wind_cap_connected_effect_remains_partial_without_ammo_source(self):
        wind = next(row for row in self.rows if row['catalog_id'] == 'armor:wind-intepreter-cap')
        self.assertEqual('partial', wind['category'])
        self.assertIn('wind_intepreter', wind['requirements'][1]['wired_path'])
        self.assertIn('bullet source', wind['requirements'][1]['missing'])


if __name__ == '__main__':
    unittest.main()
