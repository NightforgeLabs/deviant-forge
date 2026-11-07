"""Historical real-frame values stay separate from current planned ownership."""
import copy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import historical_gear_tour as tour
import planned_advisor


class HistoricalGearTourTests(unittest.TestCase):
    def setUp(self):
        tour._verified.cache_clear()

    def tearDown(self):
        tour._verified.cache_clear()

    def test_recorded_equipped_tour_and_neutral_graph_are_scoped(self):
        row = tour.snapshot()
        self.assertEqual(row['recorded_date'], '2026-11-01')
        self.assertEqual(row['recorded_weapon']['item_tooltip'],
                         {'DMG': 400, 'Fire Rate': 720, 'MAG': 40})
        self.assertEqual(row['recorded_gear_summary']['primary_weapon_attack'], 456)
        self.assertEqual(row['recorded_gear_summary']['fire_rate'], 792)
        self.assertEqual(row['later_nov2_summary']['primary_weapon_attack'], 422)
        self.assertEqual(len(row['equipped_items']), 7)
        self.assertEqual(len(row['attached_mods']), 7)
        self.assertEqual([item['name_visible'] for item in row['equipped_items'][1:]],
                         ['Mayfly Goggles', 'Shelterer Mask', 'Savior Gloves',
                          'Savior Shoes', 'Shelterer Top', 'Savior Pants'])
        self.assertEqual({item['source_frame']['second'] for item in row['attached_mods']},
                         {15, 19, 28, 33, 39, 44, 50})
        for item in row['equipped_items'] + row['attached_mods']:
            self.assertEqual(item['catalog_identity_status'],
                             'observed_name_unlinked_to_native_item_id')
            self.assertTrue(item['source_frame']['url'].startswith('/artwork/historical-gear-tour-nov1-'))
            self.assertNotIn('catalog_id', item)
        self.assertEqual({item['native_frame_candidate']['native_frame_code']
                          for item in row['attached_mods']}, {201, 10, 3})
        self.assertEqual({item['name_visible']: len(item['native_frame_candidate']['newly_typed_graph_targets'])
                          for item in row['attached_mods']}['Deviation Expert'], 3)
        for mod in row['attached_mods']:
            candidate = mod['native_frame_candidate']
            self.assertEqual(len(candidate['candidate_native_item_nos']), 2)
            self.assertFalse(candidate['candidate_variant_proven'])
            self.assertFalse(candidate['server_application_proven'])
        self.assertFalse(row['current_build_inferred'])
        self.assertFalse(row['calculation_included'])
        self.assertTrue(row['mod_application']['visible_attachment_recorded'])
        self.assertFalse(row['mod_application']['server_buff_application_proven'])
        self.assertFalse(row['mod_application']['historical_damage_effects_applied'])
        self.assertEqual(len(row['mod_application']['required_for_complete_replay']), 6)
        self.assertIn('item_no', row['mod_application']['required_for_complete_replay'][0])
        self.assertIn('mod_bag_v2', row['mod_application']['required_for_complete_replay'][2])
        controlled = tour.controlled_one_bullet_example()
        self.assertEqual(controlled['recorded_item_tooltip_dmg'], 400)
        self.assertEqual(controlled['neutral_graph_value'], 400)
        self.assertFalse(controlled['native_base_attack_added'])
        self.assertFalse(controlled['calibration_or_item_affix_added_again'])
        self.assertFalse(controlled['attached_mods_added'])
        self.assertFalse(controlled['holder_attack_equivalence_proven'])
        self.assertIsNone(controlled['current_build_damage'])
        self.assertIsNone(controlled['final_hp_loss'])
        row['recorded_weapon']['item_tooltip']['DMG'] = 999
        self.assertEqual(tour.snapshot()['recorded_weapon']['item_tooltip']['DMG'], 400)

    def test_aug_plan_gets_read_only_history_without_importing_six_star_setup(self):
        plan = {'primary': {'catalog_id': 'weapon:aug-electron-cloud',
                            'tier': 5, 'stars': 5}}
        before = copy.deepcopy(plan)
        result = planned_advisor.analyze(plan)
        self.assertEqual(plan, before)
        historical = result['historical_gear_tour_snapshot']
        self.assertEqual(historical['observation']['recorded_weapon']['stars'], 6)
        self.assertFalse(historical['observation']['ownership_mutated'])
        self.assertIsNone(result['native_player_bullet_scenario'])
        self.assertIsNone(planned_advisor.analyze({
            'primary': {'catalog_id': 'weapon:mps7-outer-space'}})
            ['historical_gear_tour_snapshot'])

    def test_changed_packet_or_frame_is_rejected(self):
        with TemporaryDirectory() as temporary:
            packet = Path(temporary) / 'packet.json'
            packet.write_bytes(tour.PACKET.read_bytes() + b' ')
            with patch.object(tour, 'PACKET', packet):
                tour._verified.cache_clear()
                with self.assertRaisesRegex(ValueError, 'packet hash conflict'):
                    tour.snapshot()
        original = tour._sha
        with patch.object(tour, '_sha', side_effect=lambda path: (
                'bad' if str(path).endswith('historical-gear-tour-nov1-15.png')
                else original(path))):
            tour._verified.cache_clear()
            with self.assertRaisesRegex(ValueError, 'item frame changed'):
                tour.snapshot()


if __name__ == '__main__':
    unittest.main()
