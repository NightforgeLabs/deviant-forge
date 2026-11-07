import unittest

import aid_catalog
import native_random_crates


class NativeRandomCrateTests(unittest.TestCase):
    def test_exact_configured_coverage_with_test_row_withheld(self):
        rows = native_random_crates.records()
        self.assertEqual(len(rows), 54)
        self.assertEqual(sum(len(row['rewards']) for row in rows), 1252)
        self.assertNotIn('aid:crate:37560004', {row['catalog_id'] for row in rows})
        self.assertNotIn('aid:crate:37560018', {row['catalog_id'] for row in rows})
        self.assertTrue(all(row['draw_mode'] == 'unknown' and
                            row['availability'] == 'current_obtainability_unknown' and
                            row['source_guarantee'] is None and
                            row['reward_membership_only']
                            for row in rows))
        self.assertFalse(any('probability' in reward for row in rows
                             for reward in row['rewards']))

    def test_named_and_unindexed_rewards_stay_distinct(self):
        row = next(row for row in native_random_crates.records()
                   if row['catalog_id'] == 'aid:crate:38600133')
        self.assertEqual(row['name'], 'Stardust Secret Crate: S12 (Epic)')
        self.assertTrue(any(reward['name'] == 'Face-Covered Laugh'
                            for reward in row['rewards']))
        missing = next(reward for reward in row['rewards']
                       if reward['native_item_id'] == '3005')
        self.assertEqual(missing['name'], 'Unlabeled item ID 3005')
        self.assertEqual(missing['source_identity_status'], 'no_indexed_item_data_row')
        self.assertFalse(missing['local_icon_verified'])

    def test_aid_has_55_described_crates_and_no_inferred_odds(self):
        category = aid_catalog.overview()['categories'][2]
        self.assertEqual(category['ready_count'], 55)
        self.assertEqual(sum(len(row['rewards']) for row in category['ready_items']), 1273)
        self.assertEqual(len({row['catalog_id'] for row in category['ready_items']}), 55)
        self.assertEqual(category['ready_items'][0]['catalog_id'], 'aid:crate:37560018')
        self.assertEqual(category['ready_items'][0]['source_guarantee']['max_opens'], 15)
        self.assertTrue(all(row['source_guarantee'] is None
                            for row in category['ready_items'][1:]))


if __name__ == '__main__':
    unittest.main()
