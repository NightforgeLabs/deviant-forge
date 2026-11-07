"""Native A00 table bounds are optional and require no-overrides evidence."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import native_hp_property_bounds as bounds
import native_player_hit_replay as player
import native_npc_hit_replay as npc
from tests.test_native_player_hit_replay import case as player_case
from tests.test_native_npc_hit_replay import case as npc_case


def native_mode(values):
    result = {k: v for k, v in values.items()
              if k not in ('hp_property_min', 'hp_property_max')}
    result.update(hp_property_mode='native_table_no_overrides',
                  hp_property_attr_id='A00', property_source_build='26267212',
                  holder_has_real_max_hp=False,
                  maximum_attribute_override_absent=True,
                  entity_specific_bound_override_absent=True)
    return result


class NativeHpPropertyBoundsTests(unittest.TestCase):
    def tearDown(self):
        bounds.proof.cache_clear()

    def test_type_identity_and_native_bounds_are_pinned(self):
        source = bounds.proof()
        self.assertEqual((source['hp_attribute_id'], source['hp_table_min'],
                          source['hp_table_max']), ('A00', 0, 999999999))
        self.assertEqual((source['max_hp_attribute_id'], source['max_hp_table_min']),
                         ('A02', 1))
        self.assertEqual(source['real_max_hp_attribute_id'], 'A01')

    def test_player_and_npc_native_mode_match_explicit_controlled_result(self):
        for module, maker, name in (
                (player, player_case, 'unshielded_lethal_hp_floor'),
                (npc, npc_case, 'monster_lethal_with_dying_trigger')):
            given, expected = maker(name)
            with self.subTest(name=name):
                result = module.replay(native_mode(given))
                self.assertEqual(result['actual_hp_damage'], expected['actual_hp_damage'])
                self.assertEqual(result['status'], expected['status'])
                self.assertEqual(result['hp_property_bound_source'],
                                 'native_A00_table_real_max_hp_absent')
                self.assertFalse(result['game_verified'])

    def test_wrong_type_build_and_unknown_overrides_withhold(self):
        given, _ = npc_case('ordinary_monster_partial_hp')
        native = native_mode(given)
        for change in ({'hp_property_attr_id': 'A02'},
                       {'property_source_build': 'other'},
                       {'holder_has_real_max_hp': True},
                       {'maximum_attribute_override_absent': False},
                       {'entity_specific_bound_override_absent': None}):
            with self.subTest(change=change):
                result = npc.replay({**native, **change})
                self.assertIsNone(result['actual_hp_damage'])
                self.assertTrue(result['missing'])
        with self.assertRaisesRegex(ValueError, 'cannot silently replace'):
            npc.replay({**native, 'hp_property_min': 0})

    def test_real_max_hp_ceiling_requires_actual_holder_value(self):
        given, _ = player_case('unshielded_partial_hp')
        native = native_mode(given)
        native.update(hp_property_mode='native_table_with_real_max_hp',
                      holder_has_real_max_hp=True)
        native.pop('maximum_attribute_override_absent')
        missing = player.replay(native)
        self.assertIsNone(missing['actual_hp_damage'])
        self.assertIn('current_real_max_hp', missing['missing'])
        result = player.replay({**native, 'current_real_max_hp': 100})
        self.assertEqual(result['actual_hp_damage'], 80)
        self.assertEqual(result['holder_hp_after'], 20)
        self.assertEqual(result['hp_property_bound_source'],
                         'native_A00_table_with_current_real_max_hp')
        # A current HP above the supplied dynamic ceiling is not a valid
        # controlled hit input; it needs the separate revalidation path.
        with self.assertRaises(ValueError):
            player.replay({**native, 'current_real_max_hp': 60})

    def test_explicit_effective_bounds_still_apply_with_override(self):
        given, _ = player_case('unshielded_partial_hp')
        given['hp_property_mode'] = 'explicit_effective'
        given['maximum_attribute_override_absent'] = False
        result = player.replay(given)
        self.assertEqual(result['actual_hp_damage'], 80)
        self.assertEqual(result['hp_property_bound_source'], 'caller_supplied_effective_bounds')

    def test_source_hash_tampering_rejected(self):
        with TemporaryDirectory() as temp:
            folder = Path(temp)
            for name in bounds.HASHES:
                (folder / name).write_bytes((bounds.ROOT / name).read_bytes())
            (folder / 'native-hp-property-bounds-v1.json').write_text('{}')
            bounds.proof.cache_clear()
            with patch.object(bounds, 'ROOT', folder):
                with self.assertRaisesRegex(ValueError, 'hash conflict'):
                    bounds.proof()
