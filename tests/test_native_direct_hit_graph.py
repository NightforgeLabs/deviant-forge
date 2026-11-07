"""Controlled graph-layer vectors and strict direct-hit source scope."""
import unittest

import native_direct_hit_graph
import combat_projection


class NativeDirectHitGraphTest(unittest.TestCase):
    def test_graph_identity_and_joint_outcomes(self):
        self.assertEqual(native_direct_hit_graph.source()['version'], 13)
        for crit, weak, expected in [(False, False, 1), (True, False, 1.5),
                                     (False, True, 1.3), (True, True, 1.8)]:
            self.assertAlmostEqual(native_direct_hit_graph.joint_factor(
                .5, .3, crit=crit, weakspot=weak), expected)

    def test_full_graph_with_explicit_unit_factors(self):
        inputs = {'base_attack': 100, 'final_skill_rate': 1,
                  'final_keyword_damage_add_rate': 0,
                  'unit_part_weak_dam_rate': 1, 'crit_addition': .5,
                  'weakspot_addition': .3,
                  'final_element_type_dam_add_rate': 1,
                  'other_dam_rate': 0, 'final_field_dam_add_rate': 1,
                  'dis_dam_rate': 1, 'final_dam_add_rate': 0,
                  'attack_ignore_dam_rate': 1,
                  'final_special_regulate_factor': 1,
                  'crit': True, 'weakspot': True}
        result = native_direct_hit_graph.graph_layer(**inputs)
        self.assertAlmostEqual(result['pre_wrapper_final_attack'], 180)
        self.assertIsNone(result['final_hit_damage'])
        inputs['final_keyword_damage_add_rate'] = .2
        self.assertAlmostEqual(native_direct_hit_graph.graph_layer(**inputs)['pre_wrapper_final_attack'], 216)
        inputs['use_final_dam_add_rate'] = False
        self.assertAlmostEqual(native_direct_hit_graph.graph_layer(**inputs)['pre_wrapper_final_attack'], 100)

    def test_invalid_flags_and_nonfinite_inputs_rejected(self):
        with self.assertRaises(ValueError):
            native_direct_hit_graph.joint_factor(.5, .3, crit=1, weakspot=False)
        with self.assertRaises(ValueError):
            native_direct_hit_graph.joint_factor(float('nan'), .3, crit=True)

    def test_direct_projection_defaults_to_native_joint_factor(self):
        direct = {'normal_damage_per_shot': 100, 'crit_bonus_percent': 50,
                  'weakspot_bonus_percent': 30, 'crit_share': 1,
                  'weakspot_share': 1, 'crit_weakspot_share': 1}
        native = combat_projection.components({'shots': 1, 'direct': direct})
        self.assertEqual(native['components']['crit_weakspot'], 180)
        self.assertEqual(native['direct_joint_source']['version'], 13)
        hypothetical = combat_projection.components({'shots': 1,
            'direct': {**direct, 'joint_multiplier': 'multiplicative'}})
        self.assertAlmostEqual(hypothetical['components']['crit_weakspot'], 195)
        self.assertEqual(hypothetical['direct_joint_source'], 'explicit_multiplicative_what_if')


if __name__ == '__main__':
    unittest.main()
