"""Five exact native gun-base rows stay separate from unresolved ShootMode."""
import unittest

import native_weapon_interval_inputs
import planned_advisor


class NativeWeaponIntervalInputsTest(unittest.TestCase):
    def test_exact_rows_and_cross_tier_gun_join(self):
        expected = {
            'weapon:aug-electron-cloud': (3, 0.0833, 60 / 0.0833),
            'weapon:socr-cosmic-visitor': (3, 0.1166, 60 / 0.1166),
            'weapon:compound-bow-the-burden-of-betrayal': (3, 0.93, 60 / 0.93),
            'weapon:sn700-finale': (1, 0.5, 40),
            'weapon:qbj97-fiery-trees-and-silver-flowers': (3, 0.0923, 60 / 0.0923),
        }
        self.assertEqual(len(native_weapon_interval_inputs.load()), 5)
        for identity, (mode, interval, argument) in expected.items():
            for tier in (1, 5):
                with self.subTest(identity=identity, tier=tier):
                    analysis = planned_advisor.analyze({'primary': {
                        'catalog_id': identity, 'tier': tier, 'stars': 1}})
                    row = analysis['weapon_reference_timing']['native_interval_inputs']
                    self.assertEqual(row['default_shoot_mode_raw'], mode)
                    self.assertEqual(row['fields']['auto_time_interval'], interval)
                    self.assertAlmostEqual(row['zero_modifier_scenario']['round_call_argument'], argument)
                    self.assertEqual(row['base_rpm_expected'], round(argument))
                    self.assertFalse(row['current_equipped_rpm_available'])
                    self.assertIn('selected weapon_rpm_add_rate including mods', row['missing'])

    def test_wrong_identity_and_unbound_weapon_do_not_borrow_row(self):
        aug = planned_advisor.analyze({'primary': {
            'catalog_id': 'weapon:aug-electron-cloud', 'tier': 5, 'stars': 1}})
        row = dict(aug['weapon_reference_timing']['native_selected_tier_star'])
        row['gear_id'] = 10451404
        with self.assertRaisesRegex(ValueError, 'tier identity conflict'):
            native_weapon_interval_inputs.selected(row, planned_advisor.NATIVE_TIER_STAR_EVIDENCE['by_blueprint'])
        other = planned_advisor.analyze({'primary': {
            'catalog_id': 'weapon:mps7-chaos-domain', 'tier': 1, 'stars': 1}})
        self.assertIsNone(other['weapon_reference_timing']['native_interval_inputs'])


if __name__ == '__main__':
    unittest.main()
