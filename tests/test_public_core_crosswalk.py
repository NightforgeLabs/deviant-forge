"""Source item IDs are identity evidence, not Field Guide rank conversion."""
import hashlib
import json
from pathlib import Path
import unittest

import catalog
import public_catalog_detail

ROOT = Path(__file__).resolve().parent.parent
PACKET = json.loads((ROOT / 'evidence_packets/public-core-crosswalk-v1.json').read_text())


class PublicCoreCrosswalkTests(unittest.TestCase):
    def test_current_unranked_identities_and_shiny_gate(self):
        # This v1 crosswalk remains a 64-row historical source snapshot.
        # The later exact-ID catalog addition must not silently relabel its provenance.
        historical = ROOT / 'evidence_packets/catalog-systems-before-native-reconciliation.json'
        self.assertEqual(PACKET['source_catalog_systems_sha256'],
                         hashlib.sha256(historical.read_bytes()).hexdigest())
        rows = PACKET['records']
        self.assertEqual(len(rows), 64)
        self.assertEqual(sum(row['normal_source_item_id'] is not None for row in rows), 57)
        self.assertEqual(sum(row['normal_source_item_id'] is None for row in rows), 7)
        self.assertEqual(len({row['catalog_id'] for row in rows}), 64)
        for row in rows:
            entry = catalog.ENTRIES[row['catalog_id']]
            self.assertEqual(entry['system_generation'], 'current_field_guide')
            self.assertEqual(public_catalog_detail.detail(row['catalog_id'],level=10)
                             ['core_effect']['status'], 'published_variants_level_unmapped')
            self.assertIsNone(row['field_guide_level_mapping'])
            if row['normal_source_item_id'] is None:
                self.assertEqual(row['source_status'], 'shiny_only_no_normal_source_item')
                self.assertTrue(row['catalog_id'].startswith('mod:boots_mod:slow-and-steady-'))
            else:
                self.assertEqual(row['source_status'], 'normal_item_crosswalk_rank_unmapped')


if __name__ == '__main__':
    unittest.main()
