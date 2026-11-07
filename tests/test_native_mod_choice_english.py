from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import native_mod_choice_english as english


class NativeModChoiceEnglishTests(unittest.TestCase):
    def tearDown(self):
        english.load.cache_clear()

    def test_exact_titles_and_dual_key_links(self):
        rows = english.load()
        self.assertEqual(579, len(rows))
        self.assertEqual(5760, sum(len(row['options']) for row in rows.values()))
        self.assertEqual(5760, sum(bool(option['catalog_systems_id'])
                                   for row in rows.values() for option in row['options']))
        self.assertEqual(468, sum(bool(option['canonical_catalog_id'])
                                  for row in rows.values() for option in row['options']))
        self.assertEqual(rows[37167141]['english_title'], 'Upper Body - Deviant Energy')
        self.assertEqual(rows[37167208]['english_title'], 'Shiny - Bounce - Non-Keyword')
        linked = rows[37180480]
        self.assertEqual(linked['english_title'], 'Flight Deviant Energy Shiny Mod Selection')
        self.assertEqual(len(linked['options']), 18)
        self.assertTrue(all(option['shiny'] and option['canonical_catalog_id']
                            for option in linked['options']))

    def test_unknown_source_bytes_rejected(self):
        with TemporaryDirectory() as temp:
            bad = Path(temp) / 'english.json'
            bad.write_text('{}')
            english.load.cache_clear()
            with patch.object(english, 'PACKET', bad), self.assertRaisesRegex(ValueError, 'hash conflict'):
                english.load()


if __name__ == '__main__':
    unittest.main()
