import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import shutil

import observed_character_panels as panels
import planned_advisor


class ObservedCharacterPanelsTests(unittest.TestCase):
    def test_two_source_bound_panels_remain_unlinked_to_selected_gear(self):
        observed = panels.observation()
        self.assertEqual(len(observed['sources']), 2)
        self.assertEqual({source['panel'] for source in observed['sources']}, {'overview', 'expanded'})
        self.assertEqual(observed['observed']['primary_weapon_panel'],
                         {'attack': 422, 'fire_rate_display': 720, 'magazine_capacity': 58})
        self.assertEqual(observed['observed']['expanded_basic_stats']['attack'], 20)
        self.assertEqual(observed['observed']['gear_overview']['max_hp'], 14402)
        self.assertEqual(observed['observed']['expanded_battle_stats']['crit_damage_percent'], 5.4)
        self.assertTrue(all(value is None for value in observed['identity'].values()))
        self.assertFalse(observed['calculation_included'])
        bindings = observed['native_display_bindings']
        self.assertEqual(bindings['basic_attack'], 'current_holder_D01_attack')
        self.assertEqual(bindings['primary_weapon_attack'],
                         'holder_attack_if_same_weapon_else_selected_weapon_replacement_preview')
        self.assertEqual(bindings['selected_vs_held_weapon_branch'], 'unknown_in_uploaded_images')
        self.assertIn('nonzero_holder_value_may_precede_preview', bindings['replacement_preview_scope'])
        self.assertFalse(bindings['basic_attack_is_free_addition_to_weapon_attack'])
        self.assertEqual(bindings['crit_damage'], 'current_holder_E02_rate')
        self.assertFalse(bindings['server_holder_or_final_damage_established'])
        for source in observed['sources']:
            self.assertTrue(source['image_url'].startswith('/artwork/observed-character-panel-20261102-'))

        result = planned_advisor.analyze({'primary': {'catalog_id': 'weapon:aug-electron-cloud', 'tier': 5, 'stars': 5}})
        self.assertEqual(result['unlinked_character_panel_observation'], observed)
        self.assertIsNone(result['matched_reference_component'])
        self.assertIsNone(result['native_player_bullet_scenario'])
        self.assertNotEqual(result['weapon_reference_timing']['native_attack_component']['value'], 422,
                            'Unlinked panel Attack must not replace the selected AUG source component')
        other = {'primary': {'catalog_id': 'weapon:mps7-outer-space', 'tier': 5, 'stars': 5}}
        compared = planned_advisor.compare({'primary': {'catalog_id': 'weapon:aug-electron-cloud', 'tier': 5, 'stars': 5}}, other)
        self.assertFalse(compared['winner_established'])
        self.assertIsNone(compared['scoped_outgoing'])
        self.assertIsNone(compared['left']['native_player_bullet_scenario'])
        self.assertIsNone(compared['right']['native_player_bullet_scenario'])
        self.assertEqual(compared['left']['unlinked_character_panel_observation']['observed']['primary_weapon_panel']['attack'], 422)
        self.assertEqual(compared['right']['unlinked_character_panel_observation']['observed']['primary_weapon_panel']['attack'], 422)
        observed['observed']['primary_weapon_panel']['attack'] = 999
        self.assertEqual(panels.observation()['observed']['primary_weapon_panel']['attack'], 422,
                         'One caller must not poison subsequent source observations')

    def test_modified_source_image_is_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            packet = root / 'evidence_packets/observed-character-panels-20261102-v1.json'
            packet.parent.mkdir(parents=True)
            shutil.copy2(panels.PACKET, packet)
            binding = root / 'evidence_packets/gear-panel-stat-bindings-v1.md'
            shutil.copy2(panels.BINDING, binding)
            preview_trace = root / 'evidence_packets/gear-selected-weapon-preview-trace-v1.md'
            shutil.copy2(panels.PREVIEW_TRACE, preview_trace)
            path = root / 'static/artwork/observed-character-panel-20261102-overview.png'
            path.parent.mkdir(parents=True)
            shutil.copy2(panels.ROOT / 'static/artwork/observed-character-panel-20261102-overview.png', path)
            shutil.copy2(panels.ROOT / 'static/artwork/observed-character-panel-20261102-expanded.png', path.with_name('observed-character-panel-20261102-expanded.png'))
            with patch.object(panels, 'ROOT', root), patch.object(panels, 'PACKET', packet), patch.object(panels, 'BINDING', binding), patch.object(panels, 'PREVIEW_TRACE', preview_trace):
                self.assertEqual(panels.observation()['observed']['primary_weapon_panel']['attack'], 422)
                path.write_bytes(b'changed screenshot')
                with self.assertRaisesRegex(ValueError, 'source image changed'):
                    panels.observation()

    def test_modified_native_binding_is_rejected(self):
        with TemporaryDirectory() as directory:
            altered = Path(directory) / 'binding.md'
            altered.write_bytes(panels.BINDING.read_bytes() + b'changed')
            with patch.object(panels, 'BINDING', altered), self.assertRaisesRegex(ValueError, 'native binding trace changed'):
                panels.observation()

    def test_modified_selected_weapon_preview_trace_is_rejected(self):
        with TemporaryDirectory() as directory:
            altered = Path(directory) / 'preview.md'
            altered.write_bytes(panels.PREVIEW_TRACE.read_bytes() + b'changed')
            with patch.object(panels, 'PREVIEW_TRACE', altered), self.assertRaisesRegex(ValueError, 'selected-weapon preview trace changed'):
                panels.observation()


if __name__ == '__main__':
    unittest.main()
