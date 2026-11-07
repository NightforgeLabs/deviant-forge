from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest
from unittest.mock import patch

import native_armor_previews as armor
import planned_advisor


class NativeArmorPreviewTests(unittest.TestCase):
    def test_exact_coverage_and_source_vectors(self):
        rows = armor.records()
        self.assertEqual((len(rows), sum(len(x['star_previews']) for x in rows)), (1018, 4828))
        self.assertEqual((armor.by_exact_gear_id(21011802, 1)['hp'],
                          armor.by_exact_gear_id(21011802, 1)['psi_intensity']), (80, 24))
        self.assertEqual((armor.by_exact_gear_id(21001004, 6)['hp'],
                          armor.by_exact_gear_id(21001004, 6)['psi_intensity']), (400, 75))
        self.assertEqual((armor.by_exact_gear_id(25003503, 6)['hp'],
                          armor.by_exact_gear_id(25003503, 6)['psi_intensity']), (300, 36))
        self.assertIsNone(armor.by_exact_gear_id(21011802, 7))
        self.assertIsNone(armor.by_exact_gear_id(99999999, 1))
        anchors = {row['name']: row for row in rows if row.get('source_anchor_title')}
        self.assertEqual(set(anchors), {'Shelterer Hat', 'Snow Panther Top', 'Gravity Tide Gloves'})
        self.assertEqual(anchors['Shelterer Hat']['source_anchor_gear_id'], 21001004)
        self.assertEqual(anchors['Shelterer Hat']['tier_choices'][-1]['gear_id'], 21001005)
        self.assertEqual(armor.by_exact_gear_id(21001005, 6)['hp'], 925)
        self.assertTrue(all(row['equipped_hp_or_psi'] is None for row in rows))
        self.assertEqual(sum(row['catalog_identity_status']=='native_gear_id_only' for row in rows), 1015)
        self.assertEqual(sum(bool(row['forge_catalog_id']) for row in rows), 801)
        self.assertEqual(sum(row['aid_search_representative'] for row in rows), 323)
        self.assertEqual(sum(row['gear_vs_blueprint_title_status']=='different_installed_titles_same_exact_native_BP_link' for row in rows), 218)
        rustic = next(row for row in rows if row['native_gear_id'] == 21000001)
        self.assertEqual((rustic['name'], rustic['installed_blueprint_name'], rustic['forge_catalog_id']),
                         ('Rustic Hat', 'Rustic Hat B.P.', 'armor:rustic-hat'))
        lonewolf = next(row for row in rows if row['native_gear_id'] == 21000701)
        self.assertEqual((lonewolf['name'], lonewolf['installed_blueprint_name']),
                         ('Lonewolf Hat', 'Lonewolf Hood B.P.'))
        gilded = next(row for row in rows if row['native_gear_id'] == 25010902)
        self.assertEqual((gilded['name'], gilded['forge_catalog_id']), ('Gilded Gloves', None))
        self.assertEqual([choice['tier'] for choice in gilded['tier_choices']], [2, 3, 4, 5])

    def test_packet_hash_and_identity_conflicts_rejected(self):
        with TemporaryDirectory() as temp:
            folder = Path(temp)
            for name in armor.SOURCES:
                (folder/name).write_bytes((armor.PACKETS/name).read_bytes())
            row = json.loads((folder/'native-armor-base-preview-v1.json').read_text())
            row['records'][0]['gear_id'] = 99999999
            (folder/'native-armor-base-preview-v1.json').write_text(json.dumps(row))
            armor.records.cache_clear()
            with patch.object(armor, 'PACKETS', folder), self.assertRaisesRegex(ValueError, 'hash conflict'):
                armor.records()
        armor.records.cache_clear()

    def test_name_packet_hash_conflict_rejected(self):
        with TemporaryDirectory() as temp:
            folder = Path(temp)
            for name in [*armor.SOURCES, armor.NAME_INDEX[0], armor.NAME_CROSSWALK[0]]:
                (folder/name).write_bytes((armor.PACKETS/name).read_bytes())
            name = armor.NAME_INDEX[0]
            altered = json.loads((folder/name).read_text())
            altered['records'][0]['installed_english_name'] = 'Guessed Hat'
            (folder/name).write_text(json.dumps(altered))
            armor.records.cache_clear()
            with patch.object(armor, 'PACKETS', folder), self.assertRaisesRegex(ValueError, 'name source hash conflict'):
                armor.records()
        armor.records.cache_clear()

    def test_selected_build_receives_only_exact_base_preview(self):
        result = planned_advisor.analyze({'helmet': {'catalog_id': 'armor:shelterer-hat', 'tier': 5, 'stars': 6},
                                          'gloves': {'catalog_id': 'armor:gilded-gauntlets', 'tier': 5, 'stars': 6}})
        parts = {part['slot']: part for part in result['slots']}
        self.assertEqual((parts['helmet']['native_armor_base_preview']['hp'],
                          parts['helmet']['native_armor_base_preview']['psi_intensity']), (925, 115))
        self.assertIsNone(parts['helmet']['native_armor_base_preview']['equipped_stats'])
        self.assertEqual(parts['gloves']['native_armor_base_preview']['status'], 'no_exact_native_identity')
        self.assertEqual(armor.for_catalog_configuration('armor:rustic-hat', 5, 6)['status'], 'source_star_unavailable')
        self.assertEqual(armor.for_catalog_configuration('armor:shelterer-hat', None, 6)['status'], 'tier_or_stars_not_selected')


if __name__ == '__main__':
    unittest.main()
