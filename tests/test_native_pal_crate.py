import unittest

import aid_catalog
import native_pal_crate


class NativePalCrateTests(unittest.TestCase):
    def test_english_exact_reward_crosswalk(self):
        rewards = native_pal_crate.records()
        self.assertEqual(len(rewards), 21)
        self.assertEqual({row['english_name'] for row in rewards.values()},
                         {'Cattiva', 'Chillet', 'Chillet Ignis'})
        self.assertEqual(len({row['native_icon_token'] for row in rewards.values()}), 3)
        self.assertTrue(all(not row['local_icon_verified'] for row in rewards.values()))
        self.assertEqual((rewards[36000061]['english_name'],
                          rewards[36000061]['skill_rating_source_text'],
                          rewards[36000061]['activity_rating_source_text']),
                         ('Cattiva', 3, 3))

    def test_aid_keeps_pool_and_pity_scope_without_odds(self):
        crate = aid_catalog.overview()['categories'][2]['ready_items'][0]
        self.assertEqual(crate['catalog_id'], 'aid:crate:37560018')
        self.assertEqual(len(crate['rewards']), 21)
        self.assertEqual(crate['native_reward_crosswalk_sha256'], native_pal_crate.PACKET_SHA256)
        self.assertEqual({row['english_name'] for row in crate['rewards']},
                         {'Cattiva', 'Chillet', 'Chillet Ignis'})
        self.assertEqual([row['pool_role'] for row in crate['rewards']].count('rare'), 3)
        self.assertTrue(all(row['skill_rating_text_value'] == 5 and
                            row['activity_rating_text_value'] == 5
                            for row in crate['rewards'] if row['pool_role'] == 'rare'))
        self.assertEqual(crate['source_guarantee']['max_opens'], 15)
        self.assertEqual(crate['draw_mode'], 'unknown')
        self.assertFalse(any('probability' in row for row in crate['rewards']))
        self.assertFalse(any(row['local_icon_verified'] for row in crate['rewards']))


if __name__ == '__main__':
    unittest.main()
