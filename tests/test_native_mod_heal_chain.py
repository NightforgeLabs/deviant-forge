"""Battle heal configured input remains separate from actual HP restoration."""
import unittest

import native_mod_frame_catalog
import native_mod_heal_chain
import public_catalog_detail


MOD = 'mod:chest_mod:ardent-shield-battle'


class NativeBattleHealChainTests(unittest.TestCase):
    def test_configured_graph_and_public_detail_keep_execution_unknown(self):
        expected = {7: .048, 8: .048, 17: .12}
        for level, factor in expected.items():
            native = native_mod_frame_catalog.preview(MOD, level)
            line = native['ordered_lines'][2]
            configured = line['configured_heal_input']
            self.assertEqual(configured['configured_parent_factor'], factor)
            self.assertEqual(configured['kill_target_type_raw'], [0])
            self.assertFalse(configured['kill_target_label_proven'])
            self.assertFalse(configured['server_heal_mutation_proven'])
            self.assertIsNone(configured['actual_hp_restored'])
            public = public_catalog_detail.detail(MOD, level)
            self.assertEqual(public['configured_bonus_lines'][2]['native_heal_input_configuration'], configured)
            self.assertTrue(public['configured_bonus_lines'][2]['native_generic_catalog_only'])

    def test_explicit_node_input_vectors_are_not_restored_hp(self):
        for factor, expected in ((.024, 24), (.12, 120)):
            result = native_mod_heal_chain.node_heal_input(
                explicit_max_hp=1000, explicit_stored_fraction=factor)
            self.assertEqual(result['node_heal_value_input'], expected)
            self.assertIsNone(result['actual_hp_restored'])
            self.assertFalse(result['target_eligibility_proven'])
        with self.assertRaises(TypeError):
            native_mod_heal_chain.node_heal_input(explicit_max_hp=1000)
        with self.assertRaises(ValueError):
            native_mod_heal_chain.node_heal_input(
                explicit_max_hp=1000, explicit_stored_fraction=float('nan'))


if __name__ == '__main__':
    unittest.main()
