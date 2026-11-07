from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import native_food_bonus as food


class NativeFoodBonusTests(unittest.TestCase):
    def test_two_raw_source_graphs_are_not_applied_effects(self):
        rows = food.records()
        self.assertEqual(set(rows), {30119705, 30119710})
        self.assertEqual([x['raw_value'] for x in rows[30119705]['raw_attributes']], [0.1]*4)
        self.assertEqual([x['raw_value'] for x in rows[30119710]['raw_attributes']], [0.08])
        self.assertTrue(all(row['application']=='source_graph_fields_only_not_applied' for row in rows.values()))

    def test_unpinned_source_is_rejected(self):
        with TemporaryDirectory() as temp:
            bad = Path(temp)/'source.json'
            bad.write_text('{}')
            food.records.cache_clear()
            with patch.object(food, 'PACKET', bad), self.assertRaisesRegex(ValueError, 'hash conflict'):
                food.records()
        food.records.cache_clear()


if __name__ == '__main__':
    unittest.main()
