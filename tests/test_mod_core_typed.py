import unittest
import json
from pathlib import Path

import component_compare
import mod_core_typed


class TypedMainEffectTests(unittest.TestCase):
    def test_four_photographed_cards_replay_without_active_rank_claim(self):
        audit=json.loads((Path(__file__).resolve().parents[1] /
                          'evidence_packets/exact-card-source-scope-v1.json').read_text())
        self.assertEqual(len(audit['records']),4)
        for row in audit['records']:
            context=({'bullets_consumed_in_magazine':12}
                     if 'bullet-siphon' in row['catalog_id'] else {})
            result=mod_core_typed.evaluate(row['catalog_id'],row['displayed_level'],
                                            context=context)
            self.assertEqual(result['status'],'observed_typed_output')
            self.assertFalse(result['active_owned_core_proven'])
            self.assertFalse(result['displayed_level_to_active_entry_rank_proven'])
            self.assertIn('active equipped core rank',result['source_warning'])
            self.assertFalse(row['active_owned_core_proven'])
            self.assertFalse(row['displayed_level_to_active_rank_proven'])

    def test_coverage_and_exact_source_scope(self):
        counts = mod_core_typed.coverage()
        self.assertEqual(counts['exact_observations'], 54)
        self.assertEqual(counts['exact_by_evidence']['evidence_class_counts'],
                         {'current_field_guide_frame': 51,
                          'held_game_video': 1, 'official_preview_card': 2})
        self.assertEqual(counts['partial_known_component_operators'], 170)
        self.assertEqual(counts['whole_dps_certified'], 0)
        exact = mod_core_typed.evaluate('mod:pants_mod:bullet-siphon-aero-deviant-energy',
                                        12, context={'bullets_consumed_in_magazine': 12})
        self.assertEqual(exact['status'], 'observed_typed_output')
        self.assertEqual([row['percentage_points'] for row in exact['outputs']], [5, 8])
        self.assertEqual(exact['observed_level'], 12)
        self.assertFalse(exact['current_version_certified'])
        self.assertIsNone(mod_core_typed.evaluate(
            'mod:pants_mod:bullet-siphon-aero-deviant-energy', 13))

    def test_heal_shield_and_ammo_remain_distinct_from_damage(self):
        item = 'mod:chest_mod:rejuvenating-precision'
        blocked = mod_core_typed.evaluate(item, 11)
        self.assertEqual(blocked['status'], 'variant_kind_unknown')
        context = {'core_unknown_variant_opt_in': True, 'enemy_defeated': True,
                   'max_hp_points': 1000, 'current_hp_points': 900,
                   'shield_points': 400, 'cooldown_available': True}
        result = mod_core_typed.evaluate(item, 11, context=context)
        self.assertEqual([row['type'] for row in result['outputs']],
                         ['heal', 'shield_generation_request'])
        self.assertEqual(result['outputs'][0]['actual_hp_restored_points'], 100)
        self.assertEqual(result['outputs'][1]['points'], 100)
        self.assertEqual(result['outputs'][1]['actual_shield_applied_points'],
                         'requires_shield_capacity_rule')
        compared = component_compare.compare({'attributes': []},
            {'catalog_id': item, 'level': 11}, context)
        typed = compared['right']['typed_main_effects'][0]
        self.assertEqual(typed['outputs'][0]['type'], 'heal')
        self.assertEqual(typed['outputs'][1]['type'], 'shield_generation_request')
        self.assertFalse(compared['game_winner_established'])
        ammo = mod_core_typed.evaluate('mod:chest_mod:quick-comeback-precision', 13,
            context={'core_unknown_variant_opt_in': True, 'healing_shot_used': True,
                     'current_magazine_bullets': 10,
                     'magazine_capacity_bullets': 30,
                     'inventory_bullets': 15})
        self.assertEqual(ammo['outputs'][1]['type'], 'ammo_transfer')
        self.assertEqual(ammo['outputs'][1]['bullets'], 15)

    def test_preview_unknown_build_and_missing_state_are_not_silent(self):
        preview = 'mod:boots_mod:ferocious-charge-downstar'
        blocked = mod_core_typed.evaluate(preview, 17, shiny=True,
                                          context={'event_buff_active': True})
        self.assertEqual(blocked['status'], 'evidence_opt_in_required')
        assumed = mod_core_typed.evaluate(preview, 17, shiny=True,
            context={'core_preview_opt_in': True, 'event_buff_active': True})
        self.assertEqual(assumed['evidence_mode_opt_in'], 'preview')
        self.assertIn('preview', assumed['source_warning'].lower())
        self.assertFalse(assumed['current_version_certified'])
        held = 'mod:boots_mod:against-all-odds-deviant-energy'
        blocked_held = mod_core_typed.evaluate(held, 12,
            context={'core_unknown_variant_opt_in': True})
        self.assertEqual(blocked_held['status'], 'evidence_opt_in_required')
        accepted_held = mod_core_typed.evaluate(held, 12,
            context={'core_unknown_variant_opt_in': True,
                     'core_unknown_build_opt_in': True})
        self.assertEqual(accepted_held['evidence_mode_opt_in'], 'unknown_game_build')
        missing = mod_core_typed.evaluate('mod:pants_mod:bullet-siphon-aero-deviant-energy', 12)
        self.assertEqual(missing['status'], 'combat_context_missing')
        self.assertIn('bullets_consumed_in_magazine', missing['missing'][0])

    def test_partial_candidate_requires_opt_in_and_current_identity(self):
        item = 'mod:mask_mod:delayed-blast-deviant-energy'
        self.assertIsNone(mod_core_typed.evaluate(item, 10,
            context={'qualified_hits_for_this_bomb': 4}))
        result = mod_core_typed.evaluate(item, 10,
            context={'core_candidate_opt_in': True,
                     'qualified_hits_for_this_bomb': 4})
        self.assertEqual(result['status'], 'explicit_community_candidate_output')
        self.assertEqual(result['numeric_binding'],
                         'community_strength_unbound_to_selected_level')
        self.assertTrue(result['missing'])
        self.assertEqual(result['outputs'][0]['type'], 'final_damage_bonus_percent')
        historical = mod_core_typed.evaluate('mod:mask_mod:delayed-blast', 10,
            context={'core_candidate_opt_in': True,
                     'qualified_hits_for_this_bomb': 5})
        self.assertEqual(historical['status'], 'historical_identity_unmatched')
        self.assertEqual(historical['outputs'], [])


if __name__ == '__main__':
    unittest.main()
