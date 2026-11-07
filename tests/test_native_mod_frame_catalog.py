"""Source-native frame previews remain separate from owned rolls and combat."""
import unittest
from unittest.mock import patch

import native_mod_frame_catalog as frames
import native_mod_buff_batch2 as batch2
import native_priority_mod_buff as priority
import public_catalog_detail


class NativeModFrameCatalogTests(unittest.TestCase):
    def test_entire_source_grid_and_exact_id_join(self):
        source, identities, previews = frames._source()
        self.assertEqual((len(identities), len(previews)), (1662, 544))
        self.assertEqual(sum(line['state'] == 'configured'
                             for row in previews.values() for line in row['ordered_lines']), 1984)
        self.assertEqual(sum(line['state'] == 'locked'
                             for row in previews.values() for line in row['ordered_lines']), 192)
        self.assertEqual(source['quarantine']['unlinked_frames'][0]['status'], 'unlinked_deprecated')
        coverage = frames.linked_coverage()
        self.assertEqual((coverage['catalog_mod_identities'],
                          coverage['exact_ordinary_catalog_links'],
                      coverage['exact_shiny_catalog_links']), (985, 830, 832))
        self.assertIsNone(frames.preview('mod:helmet_mod:deviation-expert', 8))

    def test_general_lv8_and_shiny_shared_frame_not_core_or_activation(self):
        identity = 'mod:helmet_mod:deviation-expert-general'
        native = frames.preview(identity, 8)
        self.assertEqual(native['native_frame_code'], 0)
        self.assertEqual(native['ordered_entry_levels'], [2, 2, 2, 2])
        self.assertEqual([line['text'] for line in native['ordered_lines']],
                         ['DMG +2.4%', 'Magazine Capacity +4.8%',
                          'Reload Efficiency +3.6%', 'Damage to all monsters +3%'])
        self.assertFalse(native['owned_roll_inferred'])
        self.assertFalse(native['server_buff_execution_proven'])
        shiny = frames.preview(identity, 17, shiny=True)
        self.assertTrue(shiny['shiny'])
        self.assertEqual(shiny['native_frame_code'], 0)
        self.assertNotEqual(shiny['native_item_no'], native['native_item_no'])
        self.assertFalse(shiny['core_rank_inferred'])
        with self.assertRaisesRegex(ValueError, 'Shiny requires level 17'):
            frames.preview(identity, 8, shiny=True)

    def test_native_preferred_display_does_not_replace_calculation_rows(self):
        identity = 'mod:helmet_mod:deviation-expert-general'
        detail = public_catalog_detail.detail(identity, 8)
        self.assertEqual(detail['configured_status'], 'exact_native_catalog_configuration')
        self.assertEqual(len(detail['configured_progression']), 17)
        lines = detail['configured_bonus_lines']
        self.assertEqual([line['raw_text'] for line in lines],
                         ['DMG +2.4%', 'Magazine Capacity +4.8%',
                          'Reload Efficiency +3.6%', 'Damage to all monsters +3%'])
        self.assertEqual([line['value_percent'] for line in lines], [None, 4.8, 3.6, None])
        self.assertTrue(all(line['native_generic_catalog_only'] for line in lines))
        calculated, _, _ = public_catalog_detail.calculation_rows(identity, 8)
        self.assertTrue(all(row['source_status'] != 'native_catalog_configuration_runtime_unverified'
                            for row in calculated))
        self.assertEqual(detail['configured_progression'][0]['bonus_lines'][1]['status'],
                         'locked_at_this_level')
        self.assertEqual(detail['configured_progression'][16]['bonus_lines'][3]['tier'], 2)

    def test_known_aero_survival_shrapnel_and_held_conflict(self):
        cases = [
            ('mod:pants_mod:precision-charge-aero', 26, 'Weapon DMG +2.4%, additional +1.2% for aerial hits'),
            ('mod:weapon_mod:shock-diffusion-survival', 19, 'Max HP +2.4%'),
            ('mod:weapon_mod:shatter-them-all-shrapnel', 1201, 'Shrapnel DMG +2.4%'),
        ]
        for identity, frame, first in cases:
            with self.subTest(identity=identity):
                native = frames.preview(identity, 8)
                self.assertEqual(native['native_frame_code'], frame)
                self.assertEqual(native['ordered_lines'][0]['text'], first)
        held = public_catalog_detail.detail('mod:helmet_mod:overflow-general', 8)
        self.assertEqual(held['configured_bonus_lines'][3]['name'], 'All DMG Boost')
        self.assertEqual(held['configured_bonus_lines'][3]['value_percent'], 3)
        self.assertTrue(held['configured_bonus_lines'][3]['source_conflict'])
        unobserved = public_catalog_detail.detail('mod:helmet_mod:overflow-general', 7)
        self.assertIsNone(unobserved['configured_bonus_lines'][3]['value_percent'])
        self.assertTrue(unobserved['configured_bonus_lines'][3]['source_conflict'])

    def test_packet_hash_change_rejected(self):
        original = frames._sha
        with patch.object(frames, '_sha', side_effect=lambda path: (
                'bad' if path == frames.PACKET else original(path))):
            frames._source.cache_clear()
            with self.assertRaisesRegex(ValueError, 'source hash conflict'):
                frames._source()
        frames._source.cache_clear()

    def test_four_new_graph_target_joins_are_read_only(self):
        packet, graph = priority._source()
        self.assertEqual(set(graph), {581110000, 582001000, 582004000, 582006000})
        self.assertEqual(len(packet['historical_seven']), 7)
        lunar = frames.preview('mod:helmet_mod:deviation-expert-lunar', 10)
        self.assertEqual(lunar['ordered_lines'][0]['native_attributes'],
                         [{'attr_id': 'E02', 'property': 'crit_dam_rate'}])
        self.assertEqual(lunar['ordered_lines'][1]['native_attributes'],
                         [{'attr_id': 'E42', 'property': 'attack_type_dam_add_rate_remote'}])
        self.assertEqual({x['attr_id'] for x in lunar['ordered_lines'][2]['native_attributes']},
                         {'G62', 'G63', 'G64'})
        energy = frames.preview('mod:mask_mod:thunderclap-deviant-energy', 17)
        self.assertEqual({x['attr_id'] for x in energy['ordered_lines'][0]['native_attributes']},
                         {'E32', 'E33', 'E34', 'E38'})
        self.assertFalse(lunar['server_buff_execution_proven'])
        self.assertFalse(energy['runtime_damage_included'])
        self.assertEqual(len([line for row in frames._source()[2].values()
                              for line in priority.annotate(row)['ordered_lines']
                              if line.get('attribute_status') ==
                              'typed_graph_target_verified_execution_unproven']), 80)

    def test_second_batch_adds_eight_targets_with_unbound_runtime_inputs(self):
        packet, graph = batch2._source()
        self.assertEqual(len(graph), 8)
        self.assertEqual(packet['coverage']['typed_target_ids_total'], 17)
        self.assertEqual(len(packet['remaining_buff_ids']), 32)
        self.assertEqual(sum(line.get('attribute_status') ==
                             'typed_graph_target_verified_execution_unproven'
                             for row in frames._source()[2].values()
                             for line in batch2.annotate(row)['ordered_lines']), 131)
        general = frames.preview('mod:helmet_mod:deviation-expert-general', 8)
        first = general['ordered_lines'][0]
        self.assertEqual({x['attr_id'] for x in first['native_attributes']}, {'E42', 'E43'})
        self.assertTrue(first['unbound_level_constant_link'])
        self.assertFalse(first['runtime_value_binding_proven'])
        self.assertFalse(general['runtime_damage_included'])
        lunar = frames.preview('mod:helmet_mod:deviation-expert-lunar-deviant-energy', 17)
        self.assertEqual({x['attr_id'] for x in lunar['ordered_lines'][0]['native_attributes']},
                         {'E32', 'E33', 'E34', 'E38'})
        self.assertEqual(lunar['ordered_lines'][1]['native_attributes'],
                         [{'attr_id': 'E43', 'property': 'attack_type_dam_add_rate_dot'}])
        aero = frames.preview('mod:pants_mod:abnormal-increase-aero-deviant-energy', 17)
        self.assertEqual(aero['ordered_lines'][1]['checker_scope'],
                         'six_state_aerial_checker_server_unverified')
        self.assertTrue(aero['ordered_lines'][1]['unbound_level_constant_link'])
        fortress = frames.preview('mod:mask_mod:light-cannon-fortress-warfare', 17)
        self.assertEqual([line['checker_scope'] for line in fortress['ordered_lines'][:3]],
                         ['tag_305_configured_producer_unverified'] * 3)
        self.assertTrue(all(not line['server_application_proven']
                            for line in fortress['ordered_lines'][:3]))


if __name__ == '__main__':
    unittest.main()
