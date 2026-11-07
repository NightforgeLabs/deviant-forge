"""Admission of 52 exact identities from 55 bounded native interval rows."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import native_weapon_interval_expanded as expanded
import planned_advisor


def timing(identity, tier=1):
    return planned_advisor.analyze({'primary': {'catalog_id': identity,
                                                'tier': tier, 'stars': 1}}).get('weapon_reference_timing') or {}


class NativeWeaponIntervalExpandedTest(unittest.TestCase):
    def tearDown(self):
        expanded.load.cache_clear()

    def test_exact_admission_count_and_named_vectors(self):
        report = expanded.load()
        self.assertEqual(len(report['by_catalog']), 55)
        admitted = [identity for identity in report['by_catalog']
                    if (timing(identity).get('native_interval_inputs') or {}).get('base_rpm_expected') is not None]
        self.assertEqual(len(admitted), 52)
        for identity, expected, mode in (
            ('weapon:de-50-goshawk', 190, 'SINGLE'),
            ('weapon:r500-memento', 145, 'SINGLE'),
            ('weapon:aug-electron-cloud', 720, 'AUTO'),
            ('weapon:sn700-finale', 40, 'SINGLE'),
        ):
            with self.subTest(identity=identity):
                one = timing(identity)['native_interval_inputs']
                five = timing(identity, 5)['native_interval_inputs']
                self.assertEqual(one['base_rpm_expected'], expected)
                self.assertEqual(five['base_rpm_expected'], expected)
                self.assertEqual(one['default_shoot_mode'], mode)
                self.assertFalse(one['current_equipped_rpm_available'])

    def test_unaccepted_and_identity_only_rows_remain_withheld(self):
        for identity in ('weapon:de-50', 'weapon:nail-gun', 'weapon:mps7-chaos-domain'):
            self.assertIsNone(timing(identity).get('native_interval_inputs'))
        row = dict(timing('weapon:r500-memento')['native_selected_tier_star'])
        row['blueprint_id'] = 13111201
        with self.assertRaisesRegex(ValueError, 'blueprint identity conflict'):
            expanded.selected(row)
        row = dict(timing('weapon:r500-memento')['native_selected_tier_star'])
        row['gear_id'] = 10111201
        with self.assertRaisesRegex(ValueError, 'selected tier→gun conflict'):
            expanded.selected(row)

    def test_pinned_raw_source_hash_cannot_be_bypassed(self):
        with TemporaryDirectory() as temp:
            fake = Path(temp) / 'gun.bin'
            fake.write_bytes(b'wrong gun data')
            expanded.load.cache_clear()
            with patch.object(expanded, 'RAW', fake), self.assertRaisesRegex(ValueError, 'source hash conflict'):
                expanded.load()

    def test_saved_build_compare_sees_different_bound_rates_without_winner(self):
        left = {'primary': {'catalog_id': 'weapon:r500-memento', 'tier': 1, 'stars': 1}}
        right = {'primary': {'catalog_id': 'weapon:aug-electron-cloud', 'tier': 5, 'stars': 5}}
        comparison = planned_advisor.compare(left, right)
        self.assertEqual(comparison['left']['weapon_reference_timing']['native_interval_inputs']['base_rpm_expected'], 145)
        self.assertEqual(comparison['right']['weapon_reference_timing']['native_interval_inputs']['base_rpm_expected'], 720)
        self.assertFalse(comparison['winner_established'])


if __name__ == '__main__':
    unittest.main()
