"""Named cuisine rows must retain typed source joins and unknown effects."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import native_cuisine


class NativeCuisineTests(unittest.TestCase):
    def tearDown(self):
        native_cuisine.records.cache_clear()

    def test_all_eleven_exact_items_are_informational(self):
        rows = native_cuisine.records()
        self.assertEqual(11, len(rows))
        self.assertEqual({f'aid:consumable:{item}' for item in native_cuisine.GLOSSES},
                         {row['catalog_id'] for row in rows})
        self.assertEqual(600, rows[0]['native_buff_nominal_seconds'])
        self.assertTrue(all(row['source']['native_record_id'] in row['catalog_id']
                            and row['source_name_original'] and row['source_description_original']
                            and row['calculation_status'] == 'display_only'
                            and not row['duration_tag_model_applied']
                            for row in rows))
        self.assertFalse(any('腐败' in row['effect_text'] for row in rows))
        mint = next(row for row in rows if row['catalog_id'].endswith('30110379'))
        self.assertEqual(1800, mint['native_buff_nominal_seconds'])
        self.assertTrue(mint['unresolved_secondary_buff_lifetime'])

    def test_source_tamper_or_false_duration_is_rejected(self):
        with TemporaryDirectory() as temp:
            folder = Path(temp)
            for name in (native_cuisine.CUISINE_NAME, native_cuisine.TAG_NAME):
                (folder / name).write_bytes((native_cuisine.PACKETS / name).read_bytes())
            packet = json.loads((folder / native_cuisine.CUISINE_NAME).read_text())
            packet['records'][0]['buffs'][0]['native_buff_record']['life_time']['value'] = 999999
            (folder / native_cuisine.CUISINE_NAME).write_text(json.dumps(packet))
            native_cuisine.records.cache_clear()
            with patch.object(native_cuisine, 'PACKETS', folder):
                with self.assertRaisesRegex(ValueError, 'hash conflict'):
                    native_cuisine.records()


if __name__ == '__main__':
    unittest.main()
