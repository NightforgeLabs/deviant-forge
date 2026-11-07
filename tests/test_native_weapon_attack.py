"""Exact source-native tier/star Attack component and its missing-input gates."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import native_weapon_attack
import planned_advisor


def component(weapon, tier, stars):
    result = planned_advisor.analyze({'primary': {
        'catalog_id': weapon, 'tier': tier, 'stars': stars}})
    return result['weapon_reference_timing']['native_attack_component']


class NativeWeaponAttackTest(unittest.TestCase):
    def tearDown(self):
        native_weapon_attack.method_source.cache_clear()

    def test_copied_method_identity_and_unrounded_vectors(self):
        source = native_weapon_attack.method_source()
        self.assertEqual(source['method'], 'get_gun_omg_value')
        self.assertEqual(source['build'], '26267212')
        for weapon, tier, stars, expected in (
            ('weapon:aug-electron-cloud', 1, 1, 34.0),
            ('weapon:aug-electron-cloud', 4, 6, 165.0),
            ('weapon:aug-electron-cloud', 5, 5, 241.2),
            ('weapon:r500-memento', 1, 4, 195.5),
        ):
            with self.subTest(weapon=weapon, tier=tier, stars=stars):
                row = component(weapon, tier, stars)
                self.assertEqual(row['status'], 'source_native_base_weapon_attack_component')
                self.assertAlmostEqual(row['value'], expected)
                self.assertEqual(row['value'], row['gun_preset_attack'] * row['preset_attack_radio'])
                self.assertEqual(row['rounding'], 'none_in_this_method')
                self.assertIn('final hit damage', row['not_included'])

    def test_missing_star_and_invalid_blueprint_do_not_compute(self):
        no_star = component('weapon:aug-electron-cloud', 5, None)
        self.assertIsNone(no_star['value'])
        self.assertEqual(no_star['missing'], ['preset_attack_radio'])
        # An older saved configuration can exceed an exact blueprint maximum.
        gate = component('weapon:r500', 1, 4)
        self.assertEqual(gate['status'], 'invalid_selected_stars')
        self.assertIsNone(gate['value'])

    def test_compare_exposes_same_component_without_overall_winner(self):
        left = {'primary': {'catalog_id': 'weapon:aug-electron-cloud', 'tier': 4, 'stars': 6}}
        right = {'primary': {'catalog_id': 'weapon:aug-electron-cloud', 'tier': 5, 'stars': 5}}
        result = planned_advisor.compare(left, right)
        self.assertEqual(result['left']['weapon_reference_timing']['native_attack_component']['value'], 165)
        self.assertAlmostEqual(result['right']['weapon_reference_timing']['native_attack_component']['value'], 241.2)
        self.assertFalse(result['winner_established'])

    def test_trace_tamper_is_rejected(self):
        packet = json.loads(native_weapon_attack.TRACE.read_text())
        next(row for row in packet['cases'] if row['method'] == 'get_gun_omg_value')['return_expression'] = '(preset_attack + attack_radio)'
        with TemporaryDirectory() as temp:
            path = Path(temp) / 'trace.json'
            path.write_text(json.dumps(packet))
            native_weapon_attack.method_source.cache_clear()
            with patch.object(native_weapon_attack, 'TRACE', path), patch.object(native_weapon_attack, 'TRACE_SHA256', native_weapon_attack.hashlib.sha256(path.read_bytes()).hexdigest()):
                with self.assertRaisesRegex(ValueError, 'operation conflict'):
                    native_weapon_attack.method_source()


if __name__ == '__main__':
    unittest.main()
