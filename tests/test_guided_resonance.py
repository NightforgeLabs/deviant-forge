"""Guided published source and advanced scheduler must use the same stack math."""
import copy
import unittest

import component_compare
import published_reference_model
import published_timed_combat
import structured_compare


MOD = 'mod:gloves_mod:crit-amplifier-resonance-deviant-energy'
WEAPON = 'weapon:aug-electron-cloud'
PAGE = {'assume_displayed_damage_per_projectile': True, 'assume_fire_rate_as_rpm': True,
        'projectiles_per_shot': 1, 'reload_seconds': 2.5}
OUTCOMES = {'crit_shot_indices': [1], 'weakspot_shot_indices': [],
            'elemental_shot_indices': [0], 'element': 'shock',
            'reserve_bullets': 0}
BASELINE = {'crit_bonus_percent': 100, 'weakspot_bonus_percent': 100}


def guided_build():
    return published_reference_model.build({
        'weapon': {'catalog_id': WEAPON, 'tier': 1, 'item_page_scenario': PAGE},
        'mods': [{'catalog_id': MOD, 'level': 10}]})


def guided_options(outcomes=OUTCOMES):
    return {'duration_seconds': .18, 'resonance_outcomes': outcomes,
            'resonance_baseline': BASELINE,
            'enemy_damage_bucket_model': 'independent_multiplicative'}


class GuidedResonanceTests(unittest.TestCase):
    def test_guided_and_advanced_ordered_packets_agree(self):
        build = guided_build()
        before = copy.deepcopy(build)
        guided = published_timed_combat.evaluate(build, guided_options())
        self.assertEqual(build, before)
        self.assertEqual([34, 68.816, 34],
                         [round(packet['damage'], 4)
                          for packet in guided['resonance_timeline']['packets']])
        self.assertAlmostEqual(136.816, guided['known_damage_subtotal'])
        self.assertEqual('explicit_ordered_resonance_outcomes',
                         guided['direct_expected']['mode'])
        self.assertEqual(2, len(guided['resonance_timeline']['resonance_sources']))
        self.assertEqual('partial_timed_total', guided['status'])  # Main core remains unmodeled.
        self.assertTrue(any('selected main mod effect' in gap for gap in guided['unresolved']))
        assumptions = {'scheduler': 'next_shot_interval',
                       'fire_rate_conversion': 'rpm_times_one_plus_bonus',
                       'pool_grouping': 'additive_within_named_pool_multiplicative_across_pools',
                       'event_order': 'as_list'}
        advanced = {'model_assumptions': assumptions,
                    'resonance_assumptions': {
                        'trigger': 'explicit_resolved_packet_outcome',
                        'activation': 'after_packet', 'expiry': 'per_instance_half_open',
                        'cap': 'discard_excess_until_expiry'},
                    'outcome_assumptions': {'base_crit_bonus_percent': 100,
                                             'base_weakspot_bonus_percent': 100,
                                             'joint_multiplier': 'multiplicative'},
                    'base_rpm': 720, 'duration_seconds': .18,
                    'magazine_capacity': 42, 'starting_magazine_bullets': 42,
                    'starting_reserve_bullets': 0, 'magazine_capacity_is_final': True,
                    'direct_packet': {'basis_value': 34, 'coefficient_percent': 100,
                                      'damage_class': 'weapon', 'element': 'none'},
                    'events': [
                        {'kind': 'shot', 'event_id': 'a', 'at': 0,
                         'packet_outcome': {'element': 'shock'}},
                        {'kind': 'shot', 'event_id': 'b', 'at': 1/12,
                         'packet_outcome': {'crit': True}},
                        {'kind': 'shot', 'event_id': 'c', 'at': 1/6}]}
        pools = {name: 0 for name in component_compare.POOLS.values()}
        modeled = component_compare.compare({'attributes': []},
            {'catalog_id': MOD, 'level': 10},
            {'base_pools': pools, 'integrated_combat': {'left': advanced, 'right': advanced}})
        self.assertAlmostEqual(guided['known_damage_subtotal'],
                               modeled['integrated_event_scenarios']['right']['total_damage'])
        self.assertFalse(modeled['game_winner_established'])

    def test_empty_outcomes_are_explicit_and_resonance_is_not_passive(self):
        empty = {**OUTCOMES, 'crit_shot_indices': [],
                 'elemental_shot_indices': [], 'element': 'none'}
        run = published_timed_combat.evaluate(guided_build(), guided_options(empty))
        self.assertEqual([34, 34, 34],
                         [packet['damage'] for packet in run['resonance_timeline']['packets']])
        self.assertEqual([], [output for event in run['resonance_timeline']['event_trace']
                              for output in event['candidate_outputs']
                              if output['type'] == 'resonance_stack_activation'])
        missing = published_timed_combat.evaluate(guided_build(), {'duration_seconds': .18})
        self.assertIsNone(missing['resonance_timeline'])
        self.assertTrue(any('explicit crit, weakspot and elemental' in gap
                            for gap in missing['unresolved']))

    def test_invalid_or_unanchored_outcomes_are_rejected(self):
        for outcomes, message in (
            ({**OUTCOMES, 'crit_shot_indices': [1, 1]}, 'unique'),
            ({**OUTCOMES, 'crit_shot_indices': [3]}, 'scheduled shots'),
            ({**OUTCOMES, 'element': 'none'}, 'Named elemental'),
            ({**OUTCOMES, 'weakspot_shot_indices': [True]}, 'unique')):
            with self.subTest(outcomes=outcomes), self.assertRaisesRegex(ValueError, message):
                published_timed_combat.evaluate(guided_build(), guided_options(outcomes))

    def test_sourced_elemental_packet_activates_later_crit_once(self):
        # Explicit synthetic direct basis tests event composition, never source-native coverage.
        build = published_reference_model.build({
            'weapon': {'catalog_id': 'weapon:mps7-outer-space',
                       'caller_packet_scenario': {
                           'assume_direct_body_damage_per_projectile': True, 'baseline_bonus_scope':'before_selected_effects',
                           'direct_body_damage_per_projectile': 100,
                           'projectiles_per_shot': 1, 'rpm': 900,
                           'magazine_capacity': 35, 'reload_seconds': 3}},
            'mods': [{'catalog_id': MOD, 'level': 10}]})
        self.assertEqual(build['weapon_scaled_reference']['model'],
                         'caller_entered_direct_packet_hypothesis_no_game_basis_claim')
        count = 13
        controls = {'reserve_bullets': 0, 'target_id': 'dummy',
                    'roll_sequence': [.99] * count,
                    'condition_sequences': {'target_affected_by_power_surge': [True] * count},
                    'damage_model': {'basis_values': {'psi': 80},
                        'packet_models': {'celestial_lightning': {'damage_class': 'status'}}}}
        run = published_timed_combat.evaluate(build, {
            'duration_seconds': .85, 'source_timeline': controls,
            'crit_share': 0, 'weakspot_share': 0, 'joint_share': 0,
            'resonance_baseline': {'crit_bonus_percent': 30},
            'resonance_outcomes': {'crit_shot_indices': [12],
                'weakspot_shot_indices': [], 'elemental_shot_indices': [],
                'element': 'none', 'reserve_bullets': 0}})
        packets = run['resonance_timeline']['packets']
        self.assertEqual(13, len(run['shot_times']))
        self.assertEqual(1, len(run['source_timeline']['source_packets']))
        self.assertAlmostEqual(132.4, packets[-1]['damage'])
        self.assertEqual(2.4, packets[-1]['applied_pools_percent']['crit'])
        self.assertEqual(1, sum(packet['damage'] == 400 for packet in packets))
        self.assertEqual('partial_timed_total', run['status'])
        with self.assertRaisesRegex(ValueError, 'reserve bullets disagree'):
            published_timed_combat.evaluate(build, {
                'duration_seconds': .85, 'source_timeline': controls,
                'crit_share': 0, 'weakspot_share': 0, 'joint_share': 0,
                'resonance_baseline': {'crit_bonus_percent': 30},
                'resonance_outcomes': {'crit_shot_indices': [12],
                    'weakspot_shot_indices': [], 'elemental_shot_indices': [],
                    'element': 'none', 'reserve_bullets': 1}})

    def test_unanchored_import_does_not_become_guided_damage(self):
        build = published_reference_model.build({
            'weapon': {'catalog_id': 'weapon:kam'},
            'mods': [{'catalog_id': MOD, 'level': 10}]})
        self.assertIsNone(build['weapon_scaled_reference'])
        run = published_timed_combat.evaluate(build, {
            **guided_options(), 'resonance_baseline': {}})
        self.assertIsNone(run['modeled_total_damage'])
        self.assertEqual(0, run['known_damage_subtotal'])

    def test_guided_weakspot_trigger_only_changes_later_elemental_hit(self):
        other = 'mod:gloves_mod:crit-amplifier-resonance'
        build = published_reference_model.build({
            'weapon': {'catalog_id': WEAPON, 'tier': 1,
                       'item_page_scenario': PAGE},
            'mods': [{'catalog_id': other, 'level': 10}]})
        run = published_timed_combat.evaluate(build, guided_options({
            'crit_shot_indices': [], 'weakspot_shot_indices': [0],
            'elemental_shot_indices': [1], 'element': 'shock',
            'reserve_bullets': 0}))
        self.assertEqual([68, 34.204, 34],
                         [round(packet['damage'], 4)
                          for packet in run['resonance_timeline']['packets']])

    def test_catalog_and_saved_plan_guided_results_match(self):
        plan = {'id': 'synthetic-guided-resonance', 'name': 'Synthetic Resonance',
                'slots': {'primary': {'catalog_id': WEAPON, 'tier': 1},
                          'gloves': {'mod_id': MOD, 'mod_level': 10}}}
        request = {'left': {'kind': 'catalog', 'catalog_id': MOD, 'level': 10},
                   'right': {'kind': 'planned_build', 'planned_build_id': plan['id']},
                   'context': {'published_reference': {'enabled': True,
                       'left': {'weapon_id': WEAPON, 'tier': 1, 'item_page_scenario': PAGE},
                       'right': {'weapon_id': WEAPON, 'tier': 1, 'item_page_scenario': PAGE},
                       'timed': {'duration_seconds': .18, 'shared_target_confirmed': True,
                                 'left': guided_options(), 'right': guided_options()}}}}
        result = structured_compare.compare(request, [plan])['published_reference']
        self.assertEqual(136.816, result['timed_scenarios']['left']['known_damage_subtotal'])
        self.assertEqual(result['timed_scenarios']['left']['known_damage_subtotal'],
                         result['timed_scenarios']['right']['known_damage_subtotal'])
        self.assertEqual(2, len(result['timed_scenarios']['right']['resonance_timeline']['resonance_sources']))
        self.assertFalse(result['timed_comparison']['game_winner_established'])


if __name__ == '__main__':
    unittest.main()
