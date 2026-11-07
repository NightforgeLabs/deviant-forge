"""Hand-checkable selected-pool, timed-state, ammo and scheduler fixtures."""
import copy
import unittest

import component_compare
import integrated_event_model as model
import structured_compare

ASSUMPTIONS = {'scheduler': 'next_shot_interval',
               'fire_rate_conversion': 'rpm_times_one_plus_bonus',
               'pool_grouping': 'additive_within_named_pool_multiplicative_across_pools',
               'event_order': 'as_list'}
POOLS = {pool: 0 for pool in model.SUPPORTED_POOLS}
DIRECT = {'basis_value': 100, 'coefficient_percent': 100,
          'damage_class': 'weapon', 'element': 'none'}


def request(events, mods=(), *, duration=35, capacity=10, magazine=10, reserve=0):
    return {'model_assumptions': ASSUMPTIONS.copy(), 'base_rpm': 600,
            'duration_seconds': duration, 'magazine_capacity': capacity,
            'starting_magazine_bullets': magazine,
            'starting_reserve_bullets': reserve, 'start_time_seconds': 0,
            'direct_packet': DIRECT.copy(), 'candidate_mods': list(mods), 'events': events}


class IntegratedEventTests(unittest.TestCase):
    def test_official_gilded_burn_crit_is_effect_specific_and_explicit(self):
        burn = {'kind': 'triggered_packet', 'event_id': 'burn-1', 'at': .1,
                'packet': {'basis_value': 100, 'coefficient_percent': 100,
                           'damage_class': 'status', 'element': 'blaze',
                           'keyword': 'burn', 'crit': True}}
        scenario = request([{'kind': 'shot', 'event_id': 'bullet-1'}, burn], duration=1)
        scenario.update(selected_armor_ids=['armor:gilded-gauntlets'],
                        encounter_mode='pve_non_raidzone',
                        outcome_assumptions={'base_crit_bonus_percent': 25,
                                             'joint_multiplier': 'multiplicative'})
        result = model.evaluate(scenario, static_pools=POOLS)
        self.assertEqual([row['damage'] for row in result['packets']], [100, 125])
        self.assertEqual(result['total_damage'], 225)
        self.assertEqual(result['packets'][1]['crit_eligibility_source'], model.GILDED_BURN_SOURCE)
        self.assertEqual(result['packets'][1]['applied_pools_percent']['crit'], 0)
        for change in ({'selected_armor_ids': []}, {'encounter_mode': 'raidzone'},
                       {'selected_armor_ids': ['armor:savior-gloves']},
                       {'events': [scenario['events'][0], {**burn, 'packet':
                           {**burn['packet'], 'keyword': 'power_surge'}}]},
                       {'events': [scenario['events'][0], {**burn, 'packet':
                           {**burn['packet'], 'weakspot': True}}]}):
            with self.assertRaisesRegex(ValueError, 'Status crit/weakspot eligibility'):
                model.evaluate({**scenario, **change}, static_pools=POOLS)
        without_crit = {**scenario, 'selected_armor_ids': [], 'events': [scenario['events'][0],
            {**burn, 'packet': {**burn['packet'], 'crit': False}}]}
        self.assertEqual(model.evaluate(without_crit, static_pools=POOLS)['total_damage'], 200)
        with self.assertRaisesRegex(ValueError, 'base crit bonus'):
            model.evaluate({**scenario, 'outcome_assumptions':
                {'joint_multiplier': 'multiplicative'}}, static_pools=POOLS)

    def test_covered_advance_window_and_static_pool_added_once(self):
        covered = {'catalog_id': 'mod:boots_mod:covered-advance-battle', 'level': 10,
                   'allow_candidate': True,
                   'assumptions': {'damage_during_active': 'does_not_cancel'}}
        scenario = request([{'kind': 'wait', 'at': 4},
                            {'kind': 'shot', 'event_id': 's1'},
                            {'kind': 'wait', 'at': 34},
                            {'kind': 'shot', 'event_id': 's2'}], [covered])
        before = copy.deepcopy(scenario)
        result = model.evaluate(scenario, static_pools={**POOLS, 'weapon': 10})
        self.assertAlmostEqual(result['packets'][0]['damage'], 130)
        self.assertAlmostEqual(result['packets'][1]['damage'], 110)
        self.assertEqual(result['shot_times'], [4, 34])
        self.assertAlmostEqual(result['total_damage'], 240)
        self.assertEqual(scenario, before)
        self.assertFalse(result['game_winner_established'])
        self.assertFalse(result['current_level_certified'])

    def test_momentum_phase_changes_next_shot_times_and_later_damage(self):
        momentum = {'catalog_id': 'mod:helmet_mod:momentum-up', 'level': 10,
                    'allow_candidate': True,
                    'assumptions': {'phase_basis': 'consumed_ammo_fraction',
                                    'exact_half_boundary_owner': 'second_half'}}
        events = [{'kind': 'shot', 'event_id': f's{i}'} for i in range(6)]
        result = model.evaluate(request(events, [momentum], duration=1), static_pools=POOLS)
        self.assertEqual([row['damage'] for row in result['packets']],
                         [100, 100, 100, 100, 100, 130])
        self.assertAlmostEqual(result['shot_times'][1], 60 / 660)
        self.assertAlmostEqual(result['shot_times'][5] - result['shot_times'][4], .1)
        self.assertEqual(result['total_damage'], 630)
        proc_events = [{'kind': 'shot', 'event_id': f'p{i}'} for i in range(5)] + [
            {'kind': 'triggered_packet', 'event_id': 'proc', 'at': .5,
             'packet': {'basis_value': 100, 'coefficient_percent': 100,
                        'damage_class': 'weapon', 'element': 'none'}}]
        proc = model.evaluate(request(proc_events, [momentum], duration=1), static_pools=POOLS)
        self.assertEqual(proc['packets'][-1]['damage'], 130)
        self.assertEqual(proc['final_ammo']['magazine'], 5)
        with self.assertRaisesRegex(ValueError, 'exact_half_boundary_owner'):
            model.evaluate(request(events, [{**momentum, 'assumptions':
                {'phase_basis': 'consumed_ammo_fraction'}}], duration=1), static_pools=POOLS)

    def test_momentum_reload_starts_a_new_magazine_phase(self):
        momentum = {'catalog_id': 'mod:helmet_mod:momentum-up', 'level': 10,
                    'allow_candidate': True,
                    'assumptions': {'phase_basis': 'consumed_ammo_fraction',
                                    'exact_half_boundary_owner': 'second_half'}}
        events = [{'kind': 'shot', 'event_id': 's1'},
                  {'kind': 'shot', 'event_id': 's2'},
                  {'kind': 'reload', 'event_id': 'r1', 'at': .2,
                   'loaded_rounds': 2, 'base_reload_seconds': .2},
                  {'kind': 'shot', 'event_id': 's3'}]
        result = model.evaluate(request(events, [momentum], duration=1,
                                        capacity=2, magazine=2, reserve=2),
                                static_pools=POOLS)
        self.assertEqual([packet['damage'] for packet in result['packets']],
                         [100, 130, 100])
        self.assertAlmostEqual(result['shot_times'][1], .1)
        self.assertAlmostEqual(result['shot_times'][2], .4)
        self.assertEqual(result['final_ammo'], {'magazine': 1, 'reserve': 0})

    def test_ruthless_reaper_refills_only_finite_reserve_and_replay_is_once(self):
        reaper = {'catalog_id': 'mod:pants_mod:ruthless-reaper', 'level': 10,
                  'allow_candidate': True,
                  'assumptions': {'refill_semantics': 'fill_to_capacity_from_reserves',
                                  'insufficient_reserve': 'transfer_available',
                                  'counter_reset_after_partial_or_empty': True}}
        events = [{'kind': 'shot', 'event_id': 's1'},
                  {'kind': 'kill_enemy', 'event_id': 'k1', 'at': .05},
                  {'kind': 'kill_enemy', 'event_id': 'k1', 'at': .05},
                  {'kind': 'kill_enemy', 'event_id': 'k2', 'at': .06},
                  {'kind': 'shot', 'event_id': 's2'},
                  {'kind': 'shot', 'event_id': 's3'}]
        result = model.evaluate(request(events, [reaper], duration=1,
                                        capacity=3, magazine=1, reserve=2), static_pools=POOLS)
        self.assertEqual(result['total_damage'], 300)
        self.assertEqual(result['shot_times'], [0, .1, .2])
        self.assertEqual(result['final_ammo'], {'magazine': 0, 'reserve': 0})
        self.assertEqual(result['replayed_events_suppressed'], 1)
        with self.assertRaisesRegex(ValueError, 'No magazine bullet'):
            model.evaluate(request([{'kind': 'shot', 'event_id': 's1'},
                                    {'kind': 'shot', 'event_id': 's2'}],
                                   [reaper], duration=1, capacity=3, magazine=1,
                                   reserve=2), static_pools=POOLS)

    def test_keyword_bonus_only_tags_exact_keyword(self):
        events = [{'kind': 'shot', 'event_id': 's1'},
                  {'kind': 'triggered_packet', 'event_id': 'p1', 'at': .1,
                   'packet': {'basis_value': 100, 'coefficient_percent': 100,
                              'damage_class': 'status', 'element': 'none',
                              'keyword': 'power_surge'}},
                  {'kind': 'triggered_packet', 'event_id': 'p2', 'at': .2,
                   'packet': {'basis_value': 100, 'coefficient_percent': 100,
                              'damage_class': 'status', 'element': 'none',
                              'keyword': 'shock'}}]
        result = model.evaluate(request(events, duration=1),
                                static_pools={**POOLS, 'power_surge': 50})
        self.assertEqual([row['damage'] for row in result['packets']], [100, 150, 100])
        self.assertEqual(result['total_damage'], 350)
        self.assertNotIn('power_surge', result['packets'][0]['applied_pools_percent'])
        self.assertNotIn('power_surge', result['packets'][2]['applied_pools_percent'])

    def test_missing_scheduler_assumption_rejects_timing_feedback(self):
        scenario = request([{'kind': 'shot', 'event_id': 's1'}], duration=1)
        del scenario['model_assumptions']['fire_rate_conversion']
        with self.assertRaisesRegex(ValueError, 'four named scheduler'):
            model.evaluate(scenario, static_pools=POOLS)

    def test_reload_efficiency_recomputes_shot_time(self):
        events = [{'kind': 'shot', 'event_id': 's1'},
                  {'kind': 'reload', 'event_id': 'r1', 'at': .1,
                   'loaded_rounds': 1, 'base_reload_seconds': 1},
                  {'kind': 'shot', 'event_id': 's2'}]
        result = model.evaluate(request(events, duration=1, capacity=1,
                                        magazine=1, reserve=1),
                                static_pools={**POOLS, 'reload': 100})
        self.assertEqual(result['shot_times'], [0, .6])
        self.assertEqual(result['total_damage'], 200)
        self.assertEqual(result['final_ammo'], {'magazine': 0, 'reserve': 0})

    def test_selected_exact_core_base_feeds_packet_once_and_candidates_do_not_duplicate(self):
        base = {pool: 0 for pool in component_compare.POOLS.values()}
        plain = request([{'kind': 'shot', 'event_id': 's1'}], duration=1)
        left, right = {'attributes': []}, {
            'catalog_id': 'mod:boots_mod:against-all-odds-deviant-energy', 'level': 12}
        compared = component_compare.compare(left, right, {
            'base_pools': base, 'core_unknown_variant_opt_in': True,
            'core_unknown_build_opt_in': True,
            'integrated_combat': {'left': plain, 'right': {
                **plain, 'magazine_capacity_is_final': True}}})
        self.assertEqual(compared['integrated_event_scenarios']['left']['total_damage'], 100)
        self.assertAlmostEqual(compared['integrated_event_scenarios']['right']['total_damage'], 113.3)
        self.assertEqual(compared['integrated_event_scenarios']['right']
                         ['selected_row_pools_percent']['weapon'], 10)
        self.assertFalse(compared['game_winner_established'])
        momentum = {'catalog_id': 'mod:helmet_mod:momentum-up', 'level': 10,
                    'allow_candidate': True,
                    'assumptions': {'phase_basis': 'consumed_ammo_fraction'}}
        other = {'catalog_id': momentum['catalog_id'], 'level': 10}
        with self.assertRaisesRegex(ValueError, 'avoid double counting'):
            component_compare.compare(other, other,
                {'base_pools': base, 'core_candidate_opt_in': True,
                 'integrated_combat': {'left': {**plain, 'candidate_mods': [momentum]},
                                       'right': {**plain, 'candidate_mods': [momentum]}}})

    def test_selected_magazine_bonus_requires_entered_final_capacity(self):
        base = {pool: 0 for pool in component_compare.POOLS.values()}
        plain = request([{'kind': 'shot', 'event_id': 's1'}], duration=1)
        bonus = {'attributes': [{'name': 'Magazine Capacity', 'value_percent': 20}]}
        with self.assertRaisesRegex(ValueError, 'magazine bonus changes shot timing'):
            component_compare.compare({'attributes': []}, bonus, {
                'base_pools': base,
                'integrated_combat': {'left': plain, 'right': plain}})
        final = {**plain, 'magazine_capacity_is_final': True}
        result = component_compare.compare({'attributes': []}, bonus, {
            'base_pools': base,
            'integrated_combat': {'left': plain, 'right': final}})
        self.assertEqual(result['integrated_event_scenarios']['right']['magazine_capacity_basis'],
                         'caller_entered_final_capacity_with_selected_bonus')

    def test_shiny_selected_mod_does_not_inherit_regular_candidate_timing(self):
        base = {pool: 0 for pool in component_compare.POOLS.values()}
        momentum = {'catalog_id': 'mod:helmet_mod:momentum-up', 'level': 17,
                    'allow_candidate': True,
                    'assumptions': {'phase_basis': 'consumed_ammo_fraction',
                                    'exact_half_boundary_owner': 'second_half'}}
        scenario = request([{'kind': 'shot', 'event_id': 's1'}],
                           [momentum], duration=1)
        ordinary = {'catalog_id': momentum['catalog_id'], 'level': 17}
        shiny = {**ordinary, 'shiny': True}
        with self.assertRaisesRegex(ValueError, 'not bound to the selected Shiny variant'):
            component_compare.compare(shiny, shiny, {
                'base_pools': base,
                'integrated_combat': {'left': scenario, 'right': scenario}})
        modeled = component_compare.compare(ordinary, ordinary, {
            'base_pools': base,
            'integrated_combat': {'left': scenario, 'right': scenario}})
        self.assertFalse(modeled['integrated_event_scenarios']['left']['current_level_certified'])
        plan = {'id': 'synthetic-shiny-momentum', 'name': 'Shiny candidate gate fixture',
                'slots': {'helmet': {'mod_id': momentum['catalog_id'],
                                     'mod_level': 17, 'mod_shiny': True}}}
        chosen = {'kind': 'planned_build', 'planned_build_id': plan['id']}
        with self.assertRaisesRegex(ValueError, 'not bound to the selected Shiny variant'):
            structured_compare.compare({'left': chosen, 'right': chosen,
                'context': {'base_pools': base,
                            'integrated_combat': {'left': scenario, 'right': scenario}}},
                [plan])


if __name__ == '__main__':
    unittest.main()
