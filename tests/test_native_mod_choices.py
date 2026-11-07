"""Configured choose-one mod lists never become random pools or owned grants."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import native_mod_choices


class ModChoiceTests(unittest.TestCase):
    def tearDown(self):
        native_mod_choices.records.cache_clear()

    def test_all_source_lists_and_exact_english_names(self):
        rows = native_mod_choices.records()
        self.assertEqual(579, len(rows))
        self.assertEqual(5760, sum(row['option_count'] for row in rows))
        self.assertEqual(468, sum(row['mapped_option_count'] for row in rows))
        self.assertEqual(5760, sum(row['catalog_systems_option_count'] for row in rows))
        by_id = {row['native_container_id']: row for row in rows}
        self.assertEqual((10, 16, 10), tuple(by_id[i]['option_count']
            for i in (37167141, 37167208, 37181192)))
        self.assertEqual('Upper Body - Deviant Energy', by_id[37167141]['name'])
        self.assertEqual('上身·异能', by_id[37167141]['native_title'])
        self.assertEqual('Shiny - Bounce - Non-Keyword', by_id[37167208]['name'])
        self.assertTrue(all(row['title_status']=='exact_installed_english_key' for row in rows))
        self.assertTrue(all(not option['shiny'] for option in by_id[37167141]['options']))
        self.assertTrue(all(option['shiny'] for option in by_id[37167208]['options']))
        self.assertEqual(1, by_id[37181192]['mapped_option_count'])
        self.assertTrue(all(row['draw_mode'] == 'selectable_list_not_random_pool'
                            and row['availability'] == 'unknown' and
                            row['calculation_status'] == 'informational_selection_list'
                            for row in rows))
        self.assertFalse(any('probability' in row or 'odds' in row for row in rows))

    def test_source_hash_guard(self):
        with TemporaryDirectory() as temp:
            bad = Path(temp) / 'packet.json'
            packet = json.loads(native_mod_choices.PACKET.read_text())
            packet['records'][0]['choices'][0]['item_no'] = 0
            bad.write_text(json.dumps(packet))
            native_mod_choices.records.cache_clear()
            with patch.object(native_mod_choices, 'PACKET', bad):
                with self.assertRaisesRegex(ValueError, 'hash conflict'):
                    native_mod_choices.records()


if __name__ == '__main__':
    unittest.main()
