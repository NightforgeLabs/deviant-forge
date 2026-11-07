"""Synthetic Gear preview ordering; no player or equipped stat inference."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import native_gear_preview as preview
import planned_advisor


WEAPON = 'weapon:aug-electron-cloud'


def scenario(holder_abs, held_abs, selected_abs, *, holder_rate=0, selected_rate=0):
    incoming = {'D0100': selected_abs}
    if selected_rate:
        incoming['D0101'] = selected_rate
    return {'scenario_kind': 'synthetic_client_gear_preview', 'weapon_id': WEAPON,
            'complete_synthetic_holder_map': True, 'other_channels_absent': True,
            'holder_changes': {
                'abs': {'init': {}, 'other': {'attack': holder_abs}},
                'rate': {'init': {}, 'other': {'attack': holder_rate}}},
            'held_affixes': {'13': {'D0100': held_abs}},
            'selected_affixes': {'13': incoming}}


class NativeGearPreviewTest(unittest.TestCase):
    def test_pinned_synthetic_reference_vectors_and_planned_api(self):
        vectors = json.loads((preview.ROOT / 'synthetic-gear-preview-vectors-v1.json').read_text())
        inputs = [scenario(120, 100, 200),
                  scenario(150, 100, 200, holder_rate=.05, selected_rate=.10)]
        slots = {'primary': {'catalog_id': WEAPON, 'tier': 5, 'stars': 5}}
        for fixture, given in zip(vectors['weapon_preview_vectors'], inputs):
            with self.subTest(fixture=fixture['name']):
                result = planned_advisor.analyze(slots, {'synthetic_gear_preview_scenario': given})[
                    'synthetic_gear_preview_scenario']
                self.assertEqual(result['raw_attack'], fixture['raw'])
                self.assertEqual(result['display_attack'], fixture['display'])
                self.assertEqual(result['equation_inputs']['abs'], fixture['equation_inputs']['abs'])
                self.assertTrue(result['scenario_only'])
                self.assertFalse(result['equipped_attack_verified'])
                self.assertIsNone(planned_advisor.analyze(slots)['synthetic_gear_preview_scenario'])
        self.assertIsNone(planned_advisor.analyze(slots)['weapon_reference_timing'][
            'native_attack_property']['equipped_attack'])
        self.assertEqual(planned_advisor.analyze(slots)['unlinked_character_panel_observation'][
            'observed']['primary_weapon_panel']['attack'], 422)

    def test_missing_snapshot_or_identity_withholds_output_and_compare_does_not_reuse(self):
        given = scenario(120, 100, 200)
        partial = preview.project({**given, 'complete_synthetic_holder_map': False}, WEAPON)
        self.assertIsNone(partial['display_attack'])
        self.assertIn('complete synthetic holder change map', partial['missing'])
        mismatch = preview.project(given, 'weapon:r500-memento')
        self.assertIsNone(mismatch['display_attack'])
        self.assertIn('selected weapon identity differs from the scenario', mismatch['missing'])
        self.assertIsNone(planned_advisor.analyze({}, {'synthetic_gear_preview_scenario': given})[
            'synthetic_gear_preview_scenario']['display_attack'])
        left = {'primary': {'catalog_id': WEAPON}}
        right = {'primary': {'catalog_id': 'weapon:r500-memento'}}
        compared = planned_advisor.compare(left, right, {'synthetic_gear_preview_scenario': given})
        self.assertEqual(compared['left']['synthetic_gear_preview_scenario']['display_attack'], 220)
        self.assertIsNone(compared['right']['synthetic_gear_preview_scenario']['display_attack'])
        self.assertFalse(compared['winner_established'])

    def test_source_buckets_selected_remap_set_independent_and_adjustment(self):
        given = scenario(0, 0, 200)
        given['holder_changes']['abs']['init'] = {'attack': 120}
        given['held_affixes'] = {'3': {'D0100': 100}}
        given['selected_affixes'] = {'3': {'D0100': 200}}
        result = preview.project(given, WEAPON)
        self.assertEqual(result['equation_inputs'], {'init': 20, 'abs': 200, 'rate': 0})
        self.assertEqual(result['display_attack'], 220)
        self.assertAlmostEqual(preview.independent_rate(.2, [.1, .05], 1, 2), .386)
        self.assertAlmostEqual(preview.independent_rate(.2, [.1, .05], 2, 2), .316)
        self.assertAlmostEqual(preview.independent_rate(100, [.1, .05], 1, 1), 115.5)
        self.assertEqual(preview.base_formula(20, 50, .1, [.2], 320), 320)
        self.assertEqual(preview.base_formula(20, 50, .1, [], 0), 0)
        self.assertEqual([preview.adjust_absolute(x) for x in (10.5, 11.5, -4, 130000.9)],
                         [10, 12, 0, 130000])

    def test_wrong_affix_untyped_or_unsupported_channels_rejected(self):
        base = scenario(120, 100, 200)
        for bad in ({**base, 'selected_affixes': {'13': {'D1100': 200}}},
                    {**base, 'selected_affixes': {'13': {'D0100': float('nan')}}},
                    {**base, 'selected_affixes': {'99': {'D0100': 200}}},
                    {**base, 'holder_changes': {**base['holder_changes'], 'set': {}}}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                preview.project(bad, WEAPON)
        with self.assertRaisesRegex(ValueError, 'explicitly synthetic'):
            preview.project({**base, 'scenario_kind': 'owned_weapon'}, WEAPON)

    def test_source_hash_conflict_rejected(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            for name in preview.SOURCE_HASHES:
                (root / name).write_bytes((preview.ROOT / name).read_bytes())
            (root / 'synthetic-gear-preview-reference-v1.md').write_text('wrong source')
            preview.proof.cache_clear()
            with patch.object(preview, 'ROOT', root):
                with self.assertRaisesRegex(ValueError, 'hash conflict'):
                    preview.proof()
            preview.proof.cache_clear()


if __name__ == '__main__':
    unittest.main()
