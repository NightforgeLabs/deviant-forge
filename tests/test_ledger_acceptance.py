"""Strict ledger and source-gated complete component paths, without fake item totals."""
import copy
import unittest

import integration_ledger
import published_reference_model
import published_timed_combat
import structured_compare


MOD = 'mod:boots_mod:against-all-odds-deviant-energy'
WEAPON = 'weapon:aug-electron-cloud'
PAGE = {'assume_displayed_damage_per_projectile': True, 'assume_fire_rate_as_rpm': True,
        'projectiles_per_shot': 1, 'reload_seconds': 2.5}
BODY = {'duration_seconds': .18, 'crit_share': 0,
        'weakspot_share': 0, 'joint_share': 0}
GATES = {'core_unknown_variant_opt_in': True,
         'core_unknown_build_opt_in': True,
         'core_no_hp_cost_events': True}


def build():
    return published_reference_model.build({
        'weapon': {'catalog_id': WEAPON, 'tier': 1,
                   'item_page_scenario': PAGE},
        'mods': [{'catalog_id': MOD, 'level': 12}]})


class LedgerAcceptanceTests(unittest.TestCase):
    def test_exact_lv12_base_is_selected_once_and_source_gated(self):
        selected = build()
        before = copy.deepcopy(selected)
        off = published_timed_combat.evaluate(selected, BODY)
        on = published_timed_combat.evaluate(selected, {**BODY, **GATES})
        self.assertEqual(before, selected)
        self.assertAlmostEqual(105.06, off['known_damage_subtotal'])
        self.assertAlmostEqual(115.566, on['known_damage_subtotal'])
        self.assertEqual(0, off['effective_pools_percent']['weapon'])
        self.assertEqual(10, on['effective_pools_percent']['weapon'])
        self.assertEqual(13.6, on['effective_pools_percent']['status'])
        self.assertEqual(1, sum(row.get('catalog_id') == MOD
                                for row in on['typed_core_pools_applied']))
        self.assertIn('requires explicit unknown-variant', off['unresolved'][0])
        self.assertEqual('held_game_video_unknown_build_scenario',
                         on['typed_core_pools_applied'][0]['source'])
        self.assertTrue(any('unique effect has no linked' in gap
                            for gap in on['unresolved']))
        self.assertIsNone(on['modeled_total_damage'])

    def test_body_only_does_not_require_unused_crit_baselines(self):
        selected = published_reference_model.build({
            'weapon': {'catalog_id': WEAPON, 'tier': 1,
                       'item_page_scenario': PAGE}})
        run = published_timed_combat.evaluate(selected, BODY)
        self.assertAlmostEqual(102, run['known_damage_subtotal'])
        self.assertFalse(any('crit or weakspot damage baseline' in gap
                             for gap in run['unresolved']))
        self.assertEqual('partial_timed_total', run['status'])
        named_scope = published_timed_combat.evaluate(selected, {
            **BODY, 'exclude_unbound_weapon_effect': True})
        self.assertEqual('conditional_modeled_total', named_scope['status'])
        self.assertEqual(WEAPON, named_scope['explicitly_excluded_unbound_weapon_effect'])
        self.assertTrue(any('direct-body-only scenario' in note
                            for note in named_scope['assumptions']))
        self.assertFalse(named_scope['game_winner_established'])

    def test_structured_catalog_and_saved_plan_core_parity(self):
        plan = {'id': 'synthetic-aaod', 'name': 'Synthetic Against All Odds',
                'slots': {'primary': {'catalog_id': WEAPON, 'tier': 1},
                          'shoes': {'mod_id': MOD, 'mod_level': 12}}}
        request = {'left': {'kind': 'catalog', 'catalog_id': MOD, 'level': 12},
                   'right': {'kind': 'planned_build', 'planned_build_id': plan['id']},
                   'context': {'core_unknown_variant_opt_in': True,
                               'core_unknown_build_opt_in': True,
                               'published_reference': {'enabled': True,
                                   'left': {'weapon_id': WEAPON, 'tier': 1,
                                            'item_page_scenario': PAGE},
                                   'right': {'weapon_id': WEAPON, 'tier': 1,
                                             'item_page_scenario': PAGE},
                                   'timed': {'duration_seconds': .18,
                                             'shared_target_confirmed': True,
                                             'left': {**BODY, 'core_no_hp_cost_events': True},
                                             'right': {**BODY, 'core_no_hp_cost_events': True}}}}}
        result = structured_compare.compare(request, [plan])['published_reference']
        left, right = result['timed_scenarios']['left'], result['timed_scenarios']['right']
        self.assertAlmostEqual(115.566, left['known_damage_subtotal'])
        self.assertEqual(left['known_damage_subtotal'], right['known_damage_subtotal'])
        self.assertEqual(10, right['effective_pools_percent']['weapon'])
        self.assertEqual('partial_or_unmatched', result['timed_comparison']['status'])
        self.assertFalse(result['timed_comparison']['game_winner_established'])

    def test_ledger_records_exact_gap_owner_and_strict_counts(self):
        ledger = integration_ledger.build()
        self.assertEqual({'partial': 941, 'display_only': 43}, ledger['counts']['mod'])
        self.assertEqual({'partial': 20, 'display_only': 118}, ledger['counts']['weapon'])
        self.assertEqual({'partial': 120, 'display_only': 42}, ledger['counts']['armor'])
        gilded = next(row for row in ledger['records']
                      if row['catalog_id'] == 'armor:gilded-gauntlets')
        self.assertEqual('partial', gilded['category'])
        self.assertEqual('current_official_conditional', gilded['requirements'][1]['state'])
        self.assertIn('Burn crit eligibility', gilded['requirements'][1]['wired_path'])
        self.assertIn('Burn packet coefficient', gilded['requirements'][1]['next_action'])
        selected = next(row for row in ledger['records'] if row['catalog_id'] == MOD)
        self.assertEqual('exact_lv12_base_guided_opt_in_partial', selected['requirements'][1]['state'])
        self.assertIn('HP-cost stack', selected['requirements'][1]['missing'])
        self.assertIn('controlled HP-cost contrast', selected['requirements'][1]['next_action'])
        self.assertEqual('partial', selected['category'])
        self.assertEqual({'levels': 4, 'identities': 4},
                         {key: ledger['scoped_exact_level_model_ready'][key]
                          for key in ('levels', 'identities')})
        elemental = next(row for row in ledger['records'] if row['catalog_id'] ==
                         'mod:gloves_mod:elemental-overload-resonance')
        self.assertEqual([9], elemental['scoped_exact_level_model_ready'])
        self.assertEqual(4, elemental['scoped_exact_level_paths'][0]['numeric_lines'])
        self.assertEqual(2, elemental['scoped_exact_level_paths'][0]['event_lines'])
        self.assertEqual('held_semantic_layout_conflict_partial',
                         elemental['requirements'][0]['state'])
        self.assertIn('All DMG Boost vs published Damage against enemies',
                      elemental['requirements'][0]['missing'])
        self.assertEqual('candidate_timed_operator_guided_and_advanced',
                         elemental['requirements'][1]['state'])
        self.assertEqual('partial', elemental['category'])  # Other levels remain unbound.
        for row in ledger['records']:
            for req in row['requirements']:
                if req['missing']:
                    self.assertTrue(req['owner'] and req['next_action'], row['catalog_id'])

    def test_exact_elemental_overload_level9_selected_and_saved_plan_match(self):
        mod = 'mod:gloves_mod:elemental-overload-resonance'
        weapon = 'weapon:aug-electron-cloud'
        page = {'assume_displayed_damage_per_projectile': True, 'assume_fire_rate_as_rpm': True,
                'projectiles_per_shot': 1, 'reload_seconds': 2.5}
        outcomes = {'crit_shot_indices': [], 'weakspot_shot_indices': [1],
                    'elemental_shot_indices': [0], 'element': 'shock',
                    'reserve_bullets': 0}
        one = {'duration_seconds': .18, 'resonance_outcomes': outcomes,
               'resonance_baseline': {'crit_bonus_percent': 0,
                                      'weakspot_bonus_percent': 100},
               'exclude_unbound_weapon_effect': True}
        plan = {'id': 'synthetic-elemental-level9', 'name': 'Synthetic observed level',
                'slots': {'primary': {'catalog_id': weapon, 'tier': 1},
                          'gloves': {'mod_id': mod, 'mod_level': 9}}}
        request = {'left': {'kind': 'catalog', 'catalog_id': mod, 'level': 9},
                   'right': {'kind': 'planned_build', 'planned_build_id': plan['id']},
                   'context': {'published_reference': {'enabled': True,
                       'left': {'weapon_id': weapon, 'tier': 1,
                                'item_page_scenario': page},
                       'right': {'weapon_id': weapon, 'tier': 1,
                                 'item_page_scenario': page},
                       'timed': {'duration_seconds': .18,
                                 'shared_target_confirmed': True,
                                 'left': one, 'right': one}}}}
        result = structured_compare.compare(request, [plan])['published_reference']
        for side in ('left', 'right'):
            run = result['timed_scenarios'][side]
            self.assertEqual('conditional_modeled_total', run['status'])
            self.assertAlmostEqual(146.66376, run['modeled_total_damage'])
            self.assertEqual(18, run['effective_pools_percent']['elemental'])
            self.assertEqual([41.3236, 70.32016, 35.02],
                             [round(packet['damage'], 5)
                              for packet in run['resonance_timeline']['packets']])
            self.assertEqual([], run['unresolved'])
        self.assertEqual('conditional_model_comparable',
                         result['timed_comparison']['status'])
        self.assertFalse(result['timed_comparison']['game_winner_established'])


if __name__ == '__main__':
    unittest.main()
