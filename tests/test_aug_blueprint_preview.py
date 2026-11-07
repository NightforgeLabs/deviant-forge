import unittest

import planned_advisor as plan


class AugBlueprintPreviewTest(unittest.TestCase):
    def test_only_exact_blueprint_cell(self):
        for tier, stars, expected in ((5, 4, True), (5, 5, False), (5, 6, False), (4, 4, False)):
            result = plan._weapon_reference_timing({'primary': {
                'catalog_id': 'weapon:aug-electron-cloud', 'tier': tier, 'stars': stars}})
            self.assertEqual(expected, result['blueprint_preview'] is not None)
        preview = plan._weapon_reference_timing({'primary': {
            'catalog_id': 'weapon:aug-electron-cloud', 'tier': 5, 'stars': 4}})['blueprint_preview']
        self.assertEqual({'DMG': 231, 'Fire Rate': 720, 'MAG': 40}, preview['raw_stats'])
        self.assertEqual('blueprint_preview', preview['context'])
        self.assertFalse(preview['calculation_included'])
        self.assertTrue(preview['frame_url'].startswith('/media/'))

    def test_other_weapon_never_inherits_preview(self):
        result = plan._weapon_reference_timing({'primary': {
            'catalog_id': 'weapon:scar', 'tier': 5, 'stars': 4}})
        self.assertIsNone(result['blueprint_preview'])


if __name__ == '__main__': unittest.main()
