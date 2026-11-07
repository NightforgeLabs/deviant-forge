"""Typed native title fields stay distinct from candidate localization and effects."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import aid_catalog
import native_cuisine
import native_named_catalog


class TypedNamedCatalogTests(unittest.TestCase):
    def tearDown(self):
        native_named_catalog.records.cache_clear()

    def test_typed_counts_and_nine_candidate_corrections(self):
        rows = native_named_catalog.records()
        packet = json.loads(native_named_catalog.PACKET.read_text())
        self.assertEqual(513, len(rows))
        self.assertEqual((501, 12),
                         (sum(r['category'] == 'food_drink' for r in rows),
                          sum(r['category'] == 'whims_deviations' for r in rows)))
        self.assertEqual(8, sum(r['status'] == 'no_indexed_item_data_row'
                                for r in packet['records']))
        self.assertEqual(9, len(packet['prior_candidate_disagreements']))
        corrected=next(r for r in rows if r['catalog_id'] == 'aid:consumable:30111093')
        self.assertEqual('Delicious Wild Vegetable Fried Eggs', corrected['name'])
        self.assertEqual('美味野菜煎蛋', corrected['source_title_original'].split('_$')[0])
        self.assertTrue(corrected['english_packet_sha256'])
        old_ids = {int(r['source']['native_record_id']) for r in
                   [*aid_catalog.load()['records'], *native_cuisine.records()]
                   if r['category'] in ('food_drink', 'whims_deviations')}
        self.assertTrue(old_ids.isdisjoint({r['item_id'] for r in
            packet['prior_candidate_disagreements']}))
        self.assertTrue(all(r['calculation_status'] == 'display_only' and
                            r['availability'] == 'unknown' for r in rows))
        self.assertFalse(any('formula_binding' in r for r in rows))

    def test_food_buff_lifetimes_and_whim_token_remain_scoped(self):
        rows = {r['catalog_id']: r for r in native_named_catalog.records()}
        mint = rows['aid:consumable:30110379']
        self.assertTrue(mint['unresolved_secondary_buff_lifetime'])
        self.assertEqual([1800, None], [r['nominal_seconds'] for r in mint['native_buff_rows']])
        ingredient = rows['aid:consumable:30104003']
        self.assertIsNone(ingredient['source_use_function'])
        self.assertEqual(ingredient['native_buff_rows'], [])
        whim = rows['aid:consumable:30139001']
        self.assertEqual('bandage', whim['source_use_function'])
        self.assertEqual('typed_same_id_candidate_not_applied', whim['native_buff_rows'][0]['status'])
        self.assertFalse(whim['unresolved_secondary_buff_lifetime'])

    def test_hash_conflict_and_installed_name_conflict_rejected(self):
        with TemporaryDirectory() as temp:
            altered = Path(temp) / 'packet.json'
            altered.write_text('{}')
            native_named_catalog.records.cache_clear()
            with patch.object(native_named_catalog, 'PACKET', altered):
                with self.assertRaisesRegex(ValueError, 'hash conflict'):
                    native_named_catalog.records()
        named = native_cuisine.records()
        broken = [{**named[0], 'source_name_original': 'wrong source title'}, *named[1:]]
        with patch.object(native_cuisine, 'records', return_value=broken):
            with self.assertRaisesRegex(ValueError, 'conflicts with installed named item'):
                aid_catalog.overview()


if __name__ == '__main__':
    unittest.main()
