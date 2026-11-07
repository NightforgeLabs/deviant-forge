import math
import unittest

import native_sparkling_pumpkin as soup


class SparklingPumpkinTests(unittest.TestCase):
    def test_sourced_graph_identity_and_controlled_vector(self):
        self.assertEqual(soup.proof()['configured_buff_id'], 403136600)
        value = soup.configured_input({
            'item_4010_first_value': .20,
            'pal_4010_first_values': [.05, .10],
        })
        self.assertAlmostEqual(value['effect_rate_if_helper_called'], .35)
        self.assertAlmostEqual(value['configured_E121_node_input_if_reached'], .135)
        self.assertEqual(value['nominal_buff_lifetime_seconds'], 1980)
        self.assertTrue(value['helper_emits_effect_rate_key'])
        self.assertIsNone(value['actual_aug_damage'])
        self.assertFalse(value['active_buff_proven'])

    def test_empty_inputs_are_conditional_constructor_default(self):
        value = soup.configured_input({
            'item_4010_first_value': None,
            'pal_4010_first_values': [],
        })
        self.assertFalse(value['helper_emits_effect_rate_key'])
        self.assertEqual(value['constructor_default_if_key_absent'], 0.0)
        self.assertAlmostEqual(value['configured_E121_node_input_if_reached'], .1)
        self.assertFalse(value['item_use_transfer_proven'])

    def test_reject_unbound_or_nonfinite_inputs(self):
        for data in (
            {'item_4010_first_value': .2, 'pal_4010_first_values': [], 'ingredient_quality': 5},
            {'item_4010_first_value': True, 'pal_4010_first_values': []},
            {'item_4010_first_value': None, 'pal_4010_first_values': [math.inf]},
            {'item_4010_first_value': None, 'pal_4010_first_values': '0.1'},
        ):
            with self.subTest(data=data), self.assertRaises(ValueError):
                soup.configured_input(data)


if __name__ == '__main__':
    unittest.main()
