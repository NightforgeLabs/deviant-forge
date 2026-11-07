"""Catalog variant, weapon linkage and exact typed main-rule integration."""
import copy
import unittest

import component_compare
import structured_compare

SHOES = 'mod:boots_mod:against-all-odds-deviant-energy'
SHINY = 'mod:pants_mod:elemental-resonance-aero'
BASE = {key: 0 for key in component_compare.TIMELINE_DAMAGE_POOLS}


def timeline(weapon='weapon:mps5-blue-tiger'):
    return {'weapon_id': weapon, 'evidence_mode': 'dated_release',
            'model_mode': 'explicit_assumptions', 'stream_id': 'linkage',
            'actions': [{'kind': 'hit', 'at': 0, 'target': 'dummy',
                         'input_id': 'h1', 'rolls': {'bounce': .999999}}],
            'damage_model': {'basis_values': {'attack': 100},
                             'direct': {'basis': 'attack', 'damage_class': 'weapon',
                                        'element': 'none', 'coefficient_percent': 100},
                             'duration_seconds': 1}}


class StructuredPipelineTests(unittest.TestCase):
    def test_set_name_is_not_a_single_equipment_selection(self):
        choice = {'kind': 'catalog', 'catalog_id': 'set:agent-set'}
        with self.assertRaisesRegex(ValueError, 'exact selectable catalog item'):
            structured_compare.compare({'left': choice, 'right': choice}, [])

    def test_shiny_variant_and_preview_gate_survive_structured_selection(self):
        selection = {'kind': 'catalog', 'catalog_id': SHINY, 'level': 17, 'shiny': True}
        request = {'left': selection, 'right': selection}
        before = copy.deepcopy(request)
        blocked = structured_compare.compare(request, [])
        self.assertEqual(blocked['left']['typed_main_effects'][0]['status'],
                         'evidence_opt_in_required')
        request['context'] = {'core_preview_opt_in': True, 'just_reloaded': True,
                              'previous_magazine_elemental_damage_instances': 10}
        opted = structured_compare.compare(request, [])
        typed = opted['left']['typed_main_effects'][0]
        self.assertEqual(typed['status'], 'observed_typed_output')
        self.assertEqual(typed['outputs'][0]['percentage_points'], 10)
        self.assertFalse(any(':typed:' in str(row.get('rule_id'))
                             for row in opted['left']['trace']),
                         '15-second preview buff cannot become a passive pool row')
        self.assertEqual(request['left'], before['left'])
        self.assertTrue(opted['selection_metadata']['left']['shiny'])

    def test_saved_plan_preserves_shiny_mod_scope_without_mutating_plan(self):
        plan = {'id': 'shiny-plan', 'name': 'Shiny preview plan',
                'slots': {'bottoms': {'mod_id': SHINY, 'mod_level': 17,
                                      'mod_shiny': True}}}
        before = copy.deepcopy(plan)
        selection = {'kind': 'catalog', 'catalog_id': SHINY, 'level': 17, 'shiny': True}
        request = {'left': {'kind': 'planned_build', 'planned_build_id': 'shiny-plan'},
                   'right': selection}
        blocked = structured_compare.compare(request, [plan])
        self.assertEqual(blocked['left']['typed_main_effects'][0]['status'],
                         'evidence_opt_in_required')
        request['context'] = {'core_preview_opt_in': True, 'just_reloaded': True,
                              'previous_magazine_elemental_damage_instances': 10}
        opted = structured_compare.compare(request, [plan])
        self.assertEqual(opted['left']['typed_main_effects'][0]['status'],
                         opted['right']['typed_main_effects'][0]['status'])
        self.assertEqual(opted['left']['typed_main_effects'][0]['outputs'],
                         opted['right']['typed_main_effects'][0]['outputs'])
        self.assertEqual(plan, before)

    def test_weapon_identity_mismatch_is_explicit_and_blocks_auto_pool_link(self):
        chosen = {'kind': 'catalog', 'catalog_id': 'weapon:aug-electron-cloud'}
        context = {'weapon_timeline': {'left': timeline(), 'right': timeline()}}
        result = structured_compare.compare({'left': chosen, 'right': chosen,
                                             'context': context}, [])
        self.assertEqual(result['weapon_timeline_linkage']['left']['status'], 'mismatch')
        self.assertIn('different weapon', ' '.join(result['missing']))
        self.assertFalse(result['game_winner_established'])
        context['base_pools'] = BASE.copy()
        context['weapon_timeline_pool_mode'] = 'selected_reviewed_rows'
        with self.assertRaisesRegex(ValueError, 'disagrees with the selected active weapon'):
            structured_compare.compare({'left': chosen, 'right': chosen,
                                        'context': context}, [])
        matching = {'kind': 'catalog', 'catalog_id': 'weapon:mps5-blue-tiger'}
        result = structured_compare.compare({'left': matching, 'right': matching,
                                             'context': {'weapon_timeline': context['weapon_timeline']}}, [])
        self.assertEqual(result['weapon_timeline_linkage']['left']['status'], 'matched')
        plan = {'id': 'plan-weapon', 'name': 'Plan weapon',
                'slots': {'primary': {'catalog_id': 'weapon:aug-electron-cloud'}}}
        plan_result = structured_compare.compare(
            {'left': {'kind': 'planned_build', 'planned_build_id': 'plan-weapon'},
             'right': {'kind': 'planned_build', 'planned_build_id': 'plan-weapon'},
             'context': {'weapon_timeline': context['weapon_timeline']}}, [plan])
        self.assertEqual(plan_result['weapon_timeline_linkage']['left']['status'], 'mismatch')

    def test_held_base_bonus_enters_arithmetic_only_under_existing_opt_ins_once(self):
        left, right = {'attributes': []}, {'catalog_id': SHOES, 'level': 12}
        off = component_compare.compare(left, right, {'base_pools': BASE.copy()})
        context = {'base_pools': BASE.copy(), 'core_unknown_variant_opt_in': True,
                   'core_unknown_build_opt_in': True}
        on = component_compare.compare(left, right, context)
        typed_rows = [row for row in on['right']['trace']
                      if ':typed:' in str(row.get('rule_id'))]
        self.assertEqual([row['name'] for row in typed_rows], ['Weapon DMG', 'Status DMG'])
        self.assertEqual([row['value_percent'] for row in typed_rows], [10, 10])
        self.assertAlmostEqual(on['component_ratios']['normal']['min'] /
                               off['component_ratios']['normal']['min'], 1.1)
        self.assertIn('stack_expiration_policy', ' '.join(on['missing']))
        self.assertIn('unknown', ' '.join(on['missing']).lower())
        self.assertFalse(on['game_winner_established'])
        timeline_context = {**context, 'weapon_timeline_pool_mode': 'selected_reviewed_rows',
                            'weapon_timeline': {'left': timeline(), 'right': timeline()}}
        linked = component_compare.compare(left, right, timeline_context)
        self.assertEqual(linked['weapon_timeline_pool_application']['sides']['right']
                         ['selected_reviewed_row_pools_percent']['weapon'], 10)
        self.assertAlmostEqual(linked['weapon_timeline_scenarios']['right']['total_damage'], 113.3)


if __name__ == '__main__':
    unittest.main()
