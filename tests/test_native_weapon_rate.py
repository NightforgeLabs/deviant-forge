"""Recovered native mode/interval/RPM arithmetic, without inferred gun rows."""
import unittest

import native_weapon_rate


class NativeWeaponRateTest(unittest.TestCase):
    def test_method_sources_and_mode_vectors(self):
        self.assertEqual(len(native_weapon_rate.method_source()), 2)
        cases = [
            ({'default_shoot_mode': 'SINGLE', 'single_time_interval': 0.2}, 0.2, 300),
            ({'default_shoot_mode': 'SINGLE', 'single_time_interval': 0.2,
              'shoot_time_to_trigger_plug': 4, 'plug_time': 0.4}, 0.3, 200),
            ({'default_shoot_mode': 'BURST', 'burst_bullet_interval': 0.05,
              'burst_bullet_num': 3, 'single_time_interval': 0.2}, 0.35, 60 / 0.35 * 3),
            ({'default_shoot_mode': 'AUTO', 'auto_time_interval': 0.0833}, 0.0833, 60 / 0.0833),
        ]
        for fields, interval, raw_rate in cases:
            with self.subTest(fields=fields):
                result = native_weapon_rate.project(fields)
                self.assertEqual(result['status'], 'parameterized_native_round_argument')
                self.assertAlmostEqual(result['base_interval_seconds'], interval)
                self.assertAlmostEqual(result['round_call_argument'], raw_rate)
                self.assertIsNone(result['native_return'])
                self.assertEqual(result['round_binding'], 'builtin_expected_no_module_assignment')
                self.assertEqual(result['native_return_expected'], round(raw_rate))

    def test_fractional_rate_and_burst_count(self):
        result = native_weapon_rate.project(
            {'default_shoot_mode': 'AUTO', 'auto_time_interval': 0.1}, 0.25)
        self.assertAlmostEqual(result['adjusted_interval_seconds'], 0.08)
        self.assertAlmostEqual(result['round_call_argument'], 750)
        burst = native_weapon_rate.project(
            {'default_shoot_mode': 'BURST', 'burst_bullet_interval': 0.0,
             'burst_bullet_num': 3, 'single_time_interval': 0.1}, 0.25)
        self.assertAlmostEqual(burst['round_call_argument'], 2250)

    def test_missing_invalid_and_zero_are_distinct(self):
        missing = native_weapon_rate.project({'default_shoot_mode': 'AUTO'})
        self.assertEqual(missing['missing'], ['auto_time_interval'])
        self.assertIsNone(missing['round_call_argument'])
        self.assertEqual(native_weapon_rate.project(
            {'default_shoot_mode': 'AUTO', 'auto_time_interval': 0})['native_return'], 0)
        self.assertEqual(native_weapon_rate.project(
            {'default_shoot_mode': 'CHARGE'})['status'], 'unsupported_native_shoot_mode')
        for fields, rate in [
            ({'default_shoot_mode': 'AUTO', 'auto_time_interval': -0.1}, 0),
            ({'default_shoot_mode': 'AUTO', 'auto_time_interval': 0.1}, -1),
            ({'default_shoot_mode': 'BURST', 'burst_bullet_interval': 0.1,
              'burst_bullet_num': 0, 'single_time_interval': 0.1}, 0),
        ]:
            with self.assertRaises(ValueError):
                native_weapon_rate.project(fields, rate)
        half = native_weapon_rate.project({'default_shoot_mode': 'AUTO',
                                           'auto_time_interval': 60 / 10.5})
        self.assertEqual(half['round_binding'], 'half_tie_unresolved')
        self.assertIsNone(half['native_return_expected'])


if __name__ == '__main__':
    unittest.main()
