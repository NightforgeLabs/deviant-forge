from tests.explicit_reference_fixture import explicit_synthetic_reference
"""Published calculator scenario contracts; these are model tests, not game calibration."""
import math
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen

import published_reference_model as model
import server


KAM = 'weapon:kam'
FLAME = 'mod:weapon_mod:flame-resonance-general'


@explicit_synthetic_reference
class PublishedReferenceModelTests(unittest.TestCase):
    def test_source_native_scaling_and_level_specific_four_line_inputs(self):
        left = model.build({'weapon': {'catalog_id': KAM},
                            'mods': [{'catalog_id': FLAME, 'level': 8}]})
        right = model.build({'weapon': {'catalog_id': KAM, 'stars': 2,
                                        'tier': 3, 'calibration': 4},
                             'mods': [{'catalog_id': FLAME, 'level': 17}]})
        self.assertEqual(left['weapon_source_native_baseline']['stats']['damage_per_projectile'], 31)
        self.assertTrue(math.isclose(right['weapon_scaled_reference']['damage_multiplier'], 1.3068))
        self.assertEqual(left['selected_pools_percent']['all'], 0)
        self.assertEqual(right['selected_pools_percent']['all'], 0)
        self.assertEqual(len(left['selected_mod_rows']), 4)
        self.assertEqual(len(right['selected_mod_rows']), 4)
        self.assertEqual(left['timing']['magazine'], 42)
        self.assertEqual(right['timing']['magazine'], 45)
        self.assertTrue(math.isclose(left['direct_only']['reference_hit'], 31))
        self.assertTrue(math.isclose(right['direct_only']['reference_hit'], 31 * 1.3068))
        self.assertTrue(any('exact native configured position' in gap for gap in left['unresolved']))
        self.assertTrue(any('Reload Speed' in gap for gap in left['unresolved']))
        self.assertFalse(right['game_winner_established'])

    def test_different_weapon_armor_set_suffix_family_scenarios(self):
        result = model.compare({
            'left': {'weapon': {'catalog_id': 'weapon:mps5-blue-tiger', 'stars': 2,
                                'tier': 3, 'calibration': 4},
                     'mods': [{'catalog_id': 'mod:weapon_mod:flame-resonance-violent',
                               'level': 8}],
                     'armor': [{'catalog_id': 'armor:agent-shoes', 'stars': 1, 'tier': 5}]},
            'right': {'weapon': {'catalog_id': 'weapon:socr-the-last-valor',
                                 'stars': 2, 'tier': 3, 'calibration': 4},
                      'mods': [{'catalog_id': FLAME, 'level': 17}],
                      'armor': [{'catalog_id': 'armor:bastille-boots',
                                 'stars': 1, 'tier': 5}]}})
        self.assertGreater(result['right_over_left_reference_ratios']['reference_hit'], 1)
        self.assertEqual(result['left']['armor_profiles'][0]['stats']['hp'], 1062)
        self.assertEqual(result['right']['armor_profiles'][0]['stats']['hp'], 1180)
        self.assertEqual(result['right']['armor_psi']['known_psi_total'], 46)
        self.assertFalse(result['right']['armor_psi']['complete_six_slot_build'])
        self.assertFalse(result['game_winner_established'])

    def test_missing_layout_and_zero_armor_rows_are_unknown_not_zero(self):
        result = model.build({'weapon': {'catalog_id': KAM},
                              'mods': [{'catalog_id': 'mod:weapon_mod:flame-resonance-deviant-energy',
                                        'level': 8}],
                              'armor': [{'catalog_id': 'armor:treacherous-tides-helmet',
                                         'stars': 3, 'tier': 1}]})
        self.assertEqual(len(result['selected_mod_rows']), 4)
        self.assertTrue(all(row['applied_pool'] is None for row in result['selected_mod_rows']))
        self.assertTrue(any('no supported direct-reference pool' in gap for gap in result['unresolved']))
        self.assertIsNone(result['armor_profiles'][0]['stats']['hp'])
        self.assertIsNone(result['armor_hp_for_supplied_slots'])

    def test_conditional_helmet_is_not_passively_counted(self):
        lunar = {'catalog_id': 'mod:helmet_mod:deviation-expert-lunar', 'level': 10}
        base = model.build({'weapon': {'catalog_id': KAM}, 'mods': [lunar]})
        active = model.build({'weapon': {'catalog_id': KAM}, 'mods': [lunar],
                              'condition_fractions': {'low hp': 0.5}})
        self.assertEqual(base['selected_pools_percent']['weapon'], 0)
        self.assertEqual(active['selected_pools_percent']['weapon'], 3.6)
        self.assertEqual(active['selected_pools_percent']['all'], 3)
        self.assertTrue(any('activity/magnitude fraction' in gap for gap in base['unresolved']))

    def test_no_unlabeled_database_baseline_or_silent_missing_weapon(self):
        # The source-native KAM baseline is 31. Neither the current database
        # page's damage number nor an arbitrary reference may be substituted.
        baseline = model.build({'weapon': {'catalog_id': KAM}})['weapon_source_native_baseline']
        self.assertEqual(baseline['evidence'],
                         'published_calculator_source_baseline_unverified_game_basis')
        self.assertEqual(baseline['stats']['damage_per_projectile'], 31)
        with self.assertRaisesRegex(ValueError, 'exact selectable mod'):
            model.build({'weapon': {'catalog_id': KAM},
                         'mods': [{'catalog_id': 'set:agent', 'level': 8}]})
        missing = model.compare({'left': {'weapon': {'catalog_id': KAM}},
                                 'right': {'weapon': {'catalog_id': 'weapon:socr-cosmic-visitor'}}})
        self.assertIsNone(missing['right']['weapon_source_native_baseline'])
        self.assertIsNone(missing['right']['direct_only']['reference_hit'])
        self.assertIsNone(missing['right_over_left_reference_ratios']['reference_hit'])
        self.assertTrue(any('no exact item-ID' in gap for gap in missing['right']['unresolved']))

    def test_complete_six_slot_armor_and_http_contract(self):
        right = {'weapon': {'catalog_id': KAM},
                 'armor': [{'catalog_id': 'armor:bastille-' + suffix,
                            'stars': 1, 'tier': 5}
                           for suffix in ('helmet', 'mask', 'gloves', 'boots', 'pants', 'top')]}
        result = model.build(right)
        self.assertEqual(result['armor_hp_for_supplied_slots'], 5900)
        self.assertEqual(result['armor_psi']['known_psi_total'], 460)
        self.assertTrue(result['armor_psi']['complete_six_slot_build'])
        self.assertEqual(next(row for row in result['armor_profiles'] if row['slot'] == 'chest')
                         ['published_table_slot'], 'top')
        http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        try:
            request = Request(f'http://127.0.0.1:{http.server_port}/api/published-reference-compare',
                              data=json.dumps({'left': {'weapon': {'catalog_id': KAM}},
                                               'right': right}).encode(),
                              headers={'Content-Type': 'application/json'}, method='POST')
            with urlopen(request) as response:
                payload = json.load(response)
            self.assertEqual(payload['right']['armor_psi']['known_psi_total'], 460)
            self.assertEqual(payload['right_over_left_reference_ratios']['reference_hit'], 1)
            self.assertFalse(payload['game_winner_established'])
        finally:
            http.shutdown()
            http.server_close()
            thread.join(timeout=2)


if __name__ == '__main__':
    unittest.main()
