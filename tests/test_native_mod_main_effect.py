"""Native source ranks are display facts, not Field Guide levels or damage."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import native_mod_main_effect as native
import public_catalog_detail


class NativeModMainEffectTests(unittest.TestCase):
    def tearDown(self):
        native._source.cache_clear()

    def test_all_five_exact_normal_and_shiny_identities(self):
        expected = {
            'general': ('19500001', '19505001'),
            'precision': ('19500203', '19505073'),
            'shrapnel': ('19500304', '19505109'),
            'survival': ('19500405', '19505145'),
            'violent': ('19500102', '19505037'),
        }
        for identity in native.VARIANTS:
            variant = identity.rsplit('-', 1)[-1]
            normal = native.for_catalog(identity)
            shiny = native.for_catalog(identity, shiny=True)
            self.assertEqual(expected[variant], (normal['normal_item_id'], normal['shiny_item_id']))
            self.assertEqual([3, 6, 9, 12, 15], [x['shrapnel_damage_per_body_part_percent']
                                                  for x in normal['effect_ranks']])
            self.assertEqual([9, 18, 27, 36, 45], [x['cap_percent'] for x in normal['effect_ranks']])
            self.assertEqual(5, shiny['shiny_separate_effect']['shrapnel_damage_percent'])
            self.assertIsNone(normal['field_guide_level_mapping'])
            self.assertFalse(normal['selected_rank_inferred'])
            self.assertFalse(shiny['calculation_included'])
            self.assertEqual('native_mod_v2_generation_only_not_field_guide_badge',
                             normal['generated_level_scope'])
            self.assertEqual([4, 5], normal['native_family_available_entry_ranks'])
            self.assertEqual([1, 1, 2, 2, 3, 3, 4, 4] + [5] * 9,
                             [row['effect_rank'] for row in normal['native_generated_total_level_to_rank']])
            self.assertFalse(normal['native_generated_total_level_to_rank'][0]['family_entry_row_available'])
            self.assertTrue(normal['native_generated_total_level_to_rank'][6]['family_entry_row_available'])
            self.assertEqual(normal, public_catalog_detail.detail(identity, 10)['native_main_effect'])
            self.assertTrue(public_catalog_detail.detail(identity, 17, shiny=True)['native_main_effect']['preview_shiny'])
        self.assertIsNone(native.for_catalog('mod:weapon_mod:shrapnel-souvenir-general'))

    def test_composite_offsets_never_become_effect_ids(self):
        trace, _, _, _ = native._source()
        rows = trace['mod_entry_table']['family_10101_rows']
        self.assertEqual([(10101, 4), (10101, 5)],
                         [(row['entry_no'], row['entry_level']) for row in rows])
        self.assertEqual([114923, 115003], [row['key_offset'] for row in rows])
        self.assertNotIn(28088, [row['entry_no'] for row in rows])
        self.assertNotIn(28168, [row['entry_no'] for row in rows])

    def test_changed_or_unlinked_packet_is_rejected(self):
        with TemporaryDirectory() as temp:
            folder = Path(temp)
            for name in (native.TRACE_NAME, native.GROUP_NAME,
                         native.COMPOSITE_NAME, native.LEVEL_NAME):
                (folder / name).write_bytes((native.PACKETS / name).read_bytes())
            trace = json.loads((folder / native.TRACE_NAME).read_text())
            trace['ordinary_effect_display_levels'][4]['per_part_percent'] = 99
            (folder / native.TRACE_NAME).write_text(json.dumps(trace))
            native._source.cache_clear()
            with patch.object(native, 'PACKETS', folder):
                with self.assertRaisesRegex(ValueError, 'hash conflict'):
                    native.for_catalog('mod:weapon_mod:shatter-them-all-general')


if __name__ == '__main__':
    unittest.main()
