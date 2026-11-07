"""Native calibration choices remain source options, never selected roll stats."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import native_calibration_catalog as choices


class NativeCalibrationCatalogTests(unittest.TestCase):
    def tearDown(self):
        choices._source.cache_clear()

    def test_aug_current_series_and_term_ranges_are_source_bound(self):
        packet = choices.choices('weapon:aug-electron-cloud')
        self.assertEqual('source_series_text_candidates', packet['status'])
        self.assertEqual(13, len(packet['choices']))
        self.assertEqual('26267212', packet['source_build'])
        self.assertFalse(packet['calculation_included'])
        self.assertEqual(13, len({row['item_id'] for row in packet['choices']}))
        self.assertTrue(all(row['item_id'] >= 30399141 and row['native_title'] and
                            row['native_style'] and row['available_terms'] and
                            not row['ownership_inferred'] and not row['selected_rolls_inferred'] and
                            not row['calculation_included'] for row in packet['choices']))
        self.assertTrue(any(row['item_id'] == 30399151 and '转能' in row['native_title']
                            for row in packet['choices']))
        for row in packet['choices']:
            for term in row['available_terms']:
                self.assertGreater(len(term['options']), 0)
                for option in term['options']:
                    self.assertLessEqual(option['minimum_fraction'], option['maximum_fraction'])
                    self.assertIn(option['property_mapping_status'], ('typed_property_names', 'unresolved_native_affix_property'))
                    if not option['property_names']:
                        self.assertEqual('unresolved_native_affix_property', option['property_mapping_status'])

    def test_no_fuzzy_weapon_or_conflicted_english_name(self):
        unknown = choices.choices('weapon:kam-crank')
        self.assertEqual('exact_series_bridge_missing', unknown['status'])
        self.assertEqual([], unknown['choices'])
        with self.assertRaisesRegex(ValueError, 'exact weapon'):
            choices.choices('armor:gilded-gauntlets')
        links, _, public = choices._source()
        conflict = public[30399103]
        self.assertIn('conflicts', conflict['identity_status'])
        self.assertNotIn(30399103, {row['item_id'] for row in choices.choices('weapon:aug-electron-cloud')['choices']})
        self.assertEqual(94, sum(row['native_is_valid_token']['value'] == 1 and
                                  row['source_old_blueprint_notice'] is None for row in links['records']))

    def test_literal_series_expansion_does_not_promote_aliases_or_rolls(self):
        for weapon_id, series, count in (
            ('weapon:mg4-conflicting-memories', 'MG4', 13),
            ('weapon:m416-autumn-equinox', 'M416', 13),
            ('weapon:scar', 'SCAR', 13),
            ('weapon:glock', 'Glock', 15),
        ):
            packet = choices.choices(weapon_id)
            self.assertEqual((series, count), (packet['series_token'], len(packet['choices'])))
            self.assertTrue(all(series in row['compatible_series_source_text'] for row in packet['choices']))
            self.assertTrue(all(not row['selected_rolls_inferred'] and not row['calculation_included']
                                for row in packet['choices']))
        self.assertEqual([], choices.choices('weapon:sn700-gulped-lore')['choices'])
        self.assertEqual([], choices.choices('weapon:kam-crank')['choices'])

    def test_source_tamper_is_rejected(self):
        original = choices.PACKETS
        with TemporaryDirectory() as temp:
            folder = Path(temp)
            for name in choices.SOURCES:
                (folder / name).write_bytes((original / name).read_bytes())
            packet = json.loads((folder / 'native-calibration-item-compatibility.json').read_text())
            packet['records'][0]['calibration_item_id'] = 0
            (folder / 'native-calibration-item-compatibility.json').write_text(json.dumps(packet))
            choices._source.cache_clear()
            with patch.object(choices, 'PACKETS', folder):
                with self.assertRaisesRegex(ValueError, 'hash conflict'):
                    choices.choices('weapon:aug-electron-cloud')


if __name__ == '__main__':
    unittest.main()
