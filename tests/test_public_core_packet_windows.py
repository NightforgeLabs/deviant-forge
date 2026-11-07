from tests.explicit_reference_fixture import explicit_synthetic_reference
"""Timed community source text is applied to eligible, scheduled packets once."""
import unittest
import copy
import json
from pathlib import Path

import published_main_core as core
import published_reference_model as reference
import published_timed_combat as combat
import published_timed_scheduler as scheduler
import integrated_event_model
import structured_compare


def run(family, *, duration=8, reserve=20, **extra):
    identity = 'mod:pants_mod:' + family + '-aero'
    build = reference.build({'weapon': {'catalog_id': 'weapon:mps7-outer-space'},
        'mods': [{'catalog_id': identity, 'level': 10}],
        'condition_fractions': {'damage against enemies': 0,
                                'aerial hit for extra component': 0}})
    _, ids = scheduler._events(build['timing'], duration, reserve, None, False,
                               build['weapon_source_native_baseline']['stats']['reload_time_seconds'])
    options = {'duration_seconds': duration, 'published_item_core_opt_in': True,
        'core_effect_text': core.PUBLIC[identity]['effect_text_variants_unranked'][0],
        'source_timeline': {'reserve_bullets': reserve, 'target_id': 'dummy',
            'roll_sequence': [.99] * len(ids),
            'condition_sequences': {'target_affected_by_power_surge': [True] * len(ids)},
            'damage_model': {'basis_values': {'psi': 80},
                'packet_models': {'celestial_lightning': {'damage_class': 'status'}}}},
        **extra}
    return combat.evaluate(build, options)


@explicit_synthetic_reference
class PublicCorePacketWindowTests(unittest.TestCase):
    def assert_native_scope_partial(self, result):
        self.assertEqual(result['status'], 'partial_timed_total')
        self.assertIsNone(result['modeled_total_damage'])
        self.assertTrue(any('Native configured bonus targets four monster classes' in gap
                            for gap in result['unresolved']))

    def test_execution_ledger_covers_all_source_variants_without_rank_mapping(self):
        from build_public_core_execution_v2 import build
        actual = build()
        saved = json.loads((Path(__file__).resolve().parent.parent /
                            'evidence_packets/public-core-execution-v2.json').read_text())
        self.assertEqual(actual, saved)
        self.assertEqual(actual['counts'], {
            'blocked_attack_basis_and_mark_events': 1,
            'conditional_direct_timeline': 6,
            'conditional_sourced_packet_timeline': 17})
        self.assertTrue(all(row['source_item_effect_level_to_field_guide_level'] is None
                            for row in actual['records']))

    def test_abnormal_increase_activates_after_empty_magazine_on_status_only(self):
        result = run('abnormal-increase')
        self.assert_native_scope_partial(result)
        self.assertEqual(result['timed_core_packet_windows']['damage_delta'], 80)
        self.assertEqual(len(result['timed_core_packet_windows']['packet_adjustments']), 2)
        self.assertEqual({row['pool'] for row in result['timed_core_packet_windows']['packet_adjustments']},
                         {'status'})
        self.assertAlmostEqual(result['source_proc']['damage'], 1680)
        self.assertFalse(result['game_winner_established'])

    def test_elemental_resonance_counts_previous_magazine_instances(self):
        missing = run('elemental-resonance')
        self.assertEqual(missing['status'], 'partial_timed_total')
        self.assertTrue(any('all previous-magazine' in gap for gap in missing['unresolved']))
        result = run('elemental-resonance', core_all_elemental_events_modeled=True)
        self.assertEqual(result['status'], 'partial_timed_total')
        self.assertTrue(any('All DMG Boost magnitude or activation missing' in gap
                            for gap in result['unresolved']))
        windows = result['timed_core_packet_windows']['windows']
        self.assertEqual(len(windows), 1)
        self.assertEqual(windows[0]['previous_elemental_instances'], 2)
        self.assertAlmostEqual(windows[0]['bonus_percent'], .4)
        self.assertAlmostEqual(result['timed_core_packet_windows']['damage_delta'], 3.2)

    def test_precision_charge_requires_and_caps_entered_weakspot_counts(self):
        missing = run('precision-charge')
        self.assertEqual(missing['status'], 'partial_timed_total')
        self.assertTrue(any('weakspot-hit count' in gap for gap in missing['unresolved']))
        inconsistent = run('precision-charge', core_weakspot_hits_by_magazine=[18])
        self.assertEqual(inconsistent['status'], 'partial_timed_total')
        self.assertTrue(any('consistent overall direct weakspot share' in gap
                            for gap in inconsistent['unresolved']))
        result = run('precision-charge', core_weakspot_hits_by_magazine=[18],
                     weakspot_share=.4, joint_share=0)
        self.assertEqual(result['status'], 'partial_timed_total')
        self.assertTrue(any('Native monster-type properties are not generic All DMG Boost' in gap
                            for gap in result['unresolved']))
        self.assertEqual(result['timed_core_packet_windows']['windows'][0]['bonus_percent'], 20)
        self.assertGreater(result['timed_core_packet_windows']['damage_delta'], 0)
        capped = run('precision-charge', core_weakspot_hits_by_magazine=[35],
                     weakspot_share=.8, joint_share=0)
        self.assertEqual(capped['timed_core_packet_windows']['windows'][0]['bonus_percent'], 24)
        with self.assertRaisesRegex(ValueError, 'within fired shots'):
            run('precision-charge', core_weakspot_hits_by_magazine=[36])

    def test_status_stack_overlap_requires_named_duration_model_when_relevant(self):
        unknown = run('abnormal-increase', duration=12, reserve=70)
        self.assertEqual(unknown['status'], 'partial_timed_total')
        self.assertTrue(any('overlapping active stacks' in gap for gap in unknown['unresolved']))
        modeled = run('abnormal-increase', duration=12, reserve=70,
                      core_timed_stack_model='independent')
        self.assert_native_scope_partial(modeled)
        self.assertTrue(any(row['bonus_percent'] == 20 for row in
                            modeled['timed_core_packet_windows']['packet_adjustments']))

    def test_reload_rampage_transfers_finite_reserve_and_buffs_later_packets(self):
        identity = 'mod:pants_mod:reload-rampage-aero'
        build = reference.build({'weapon': {'catalog_id': 'weapon:mps7-outer-space'},
            'mods': [{'catalog_id': identity, 'level': 10}],
            'condition_fractions': {'damage against enemies': 0,
                                    'aerial hit for extra component': 0}})
        text = core.PUBLIC[identity]['effect_text_variants_unranked'][0]
        rule = core._community_text(identity, text, {})['timed_rule']
        base_reload = build['weapon_source_native_baseline']['stats']['reload_time_seconds']
        def scenario(kills, reserve=10, model='per_trigger'):
            active_kills = kills if model == 'per_trigger' else []
            events, shots = scheduler._events(build['timing'], 5, reserve, None, False,
                base_reload, set(active_kills), rule)
            result = combat.evaluate(build, {'duration_seconds': 5,
                'published_item_core_opt_in': True, 'core_effect_text': text,
                'core_kill_shot_indices': kills, 'core_refill_cap_model': model,
                'source_timeline': {'reserve_bullets': reserve, 'target_id': 'dummy',
                    'roll_sequence': [.99] * len(shots),
                    'condition_sequences': {'target_affected_by_power_surge': [True] * len(shots)},
                    'damage_model': {'basis_values': {'psi': 80},
                        'packet_models': {'celestial_lightning': {'damage_class': 'status'}}}}})
            return events, result
        baseline_events, baseline = scenario([])
        events, boosted = scenario([33])
        self.assert_native_scope_partial(baseline)
        self.assert_native_scope_partial(boosted)
        self.assertEqual(baseline['source_proc']['shot_count'], 35)
        self.assertEqual(boosted['source_proc']['shot_count'], 37)
        kill = next(event for event in events if event['kind'] == 'kill_enemy')
        self.assertEqual(kill['ammo_transfer_rounds'], 2)
        self.assertEqual(boosted['source_timeline']['final_ammo']['reserve'], 0)
        self.assertEqual(boosted['timed_core_packet_windows']['damage_delta'], 20)
        self.assertEqual(len(boosted['timed_core_packet_windows']['direct_packet_adjustments']), 3)
        self.assertGreater(boosted['known_damage_subtotal'], baseline['known_damage_subtotal'])
        _, no_reserve = scenario([33], reserve=0)
        self.assertEqual(no_reserve['source_timeline']['final_ammo']['reserve'], 0)
        self.assertEqual(no_reserve['source_proc']['shot_count'], 35)
        _, unresolved = scenario([33], model=None)
        self.assertEqual(unresolved['status'], 'partial_timed_total')
        self.assertTrue(any('refill cap' in gap for gap in unresolved['unresolved']))

    def test_explicit_kill_transfer_cannot_create_ammo_or_replay(self):
        assumptions = {'scheduler': 'next_shot_interval',
            'fire_rate_conversion': 'rpm_times_one_plus_bonus',
            'pool_grouping': 'additive_within_named_pool_multiplicative_across_pools',
            'event_order': 'as_list'}
        kill = {'kind': 'kill_enemy', 'event_id': 'k1', 'at': 0,
                'ammo_transfer_rounds': 1, 'ammo_transfer_cap_rounds': 1}
        scenario = {'model_assumptions': assumptions, 'base_rpm': 600,
            'duration_seconds': 1, 'magazine_capacity': 2,
            'starting_magazine_bullets': 2, 'starting_reserve_bullets': 1,
            'direct_packet': {'basis_value': 100, 'coefficient_percent': 100,
                              'damage_class': 'weapon', 'element': 'none'},
            'events': [{'kind': 'shot', 'event_id': 's1', 'at': 0}, kill, kill,
                       {'kind': 'shot', 'event_id': 's2', 'at': .1}]}
        pools = {name: 0 for name in integrated_event_model.SUPPORTED_POOLS}
        result = integrated_event_model.evaluate(scenario, static_pools=pools)
        self.assertEqual(result['final_ammo'], {'magazine': 1, 'reserve': 0})
        self.assertEqual(result['replayed_events_suppressed'], 1)
        scenario['events'][1] = {**kill, 'ammo_transfer_rounds': 2}
        scenario['events'].pop(2)
        with self.assertRaisesRegex(ValueError, 'finite reserve'):
            integrated_event_model.evaluate(scenario, static_pools=pools)

    def test_selected_kam_versus_outer_space_remains_partial_with_conflicted_scope(self):
        left = 'mod:pants_mod:critical-surge-aero'
        right = 'mod:pants_mod:abnormal-increase-aero'
        source = reference.build({'weapon': {'catalog_id': 'weapon:mps7-outer-space'}})
        _, shots = scheduler._events(source['timing'], 8, 20, None, False,
            source['weapon_source_native_baseline']['stats']['reload_time_seconds'])
        plans = [
            {'id': 'left', 'name': 'KAM scenario', 'slots': {
                'primary': {'catalog_id': 'weapon:kam'},
                'pants': {'mod_id': left, 'mod_level': 10}}},
            {'id': 'right', 'name': 'Outer Space scenario', 'slots': {
                'primary': {'catalog_id': 'weapon:mps7-outer-space'},
                'pants': {'mod_id': right, 'mod_level': 10}}},
        ]
        before = copy.deepcopy(plans)
        fractions = {'damage against enemies': 0,
                     'aerial hit for extra component': 0}
        request = {'left': {'kind': 'planned_build', 'planned_build_id': 'left'},
                   'right': {'kind': 'planned_build', 'planned_build_id': 'right'},
                   'context': {'core_candidate_opt_in': True,
                       'published_reference': {'enabled': True,
                           'left': {'condition_fractions': fractions},
                           'right': {'condition_fractions': fractions},
                           'timed': {'duration_seconds': 8,
                               'shared_target_confirmed': True,
                               'left': {'core_effect_text': core.PUBLIC[left]
                                        ['effect_text_variants_unranked'][0]},
                               'right': {'core_effect_text': core.PUBLIC[right]
                                         ['effect_text_variants_unranked'][0],
                                   'source_timeline': {'reserve_bullets': 20,
                                       'target_id': 'dummy',
                                       'roll_sequence': [.99] * len(shots),
                                       'condition_sequences': {
                                           'target_affected_by_power_surge': [True] * len(shots)},
                                       'damage_model': {'basis_values': {'psi': 80},
                                           'packet_models': {'celestial_lightning': {
                                               'damage_class': 'status'}}}}}}}}}
        result = structured_compare.compare(request, plans)['published_reference']
        self.assertEqual(result['timed_comparison']['status'], 'partial_or_unmatched')
        self.assert_native_scope_partial(result['timed_scenarios']['left'])
        self.assert_native_scope_partial(result['timed_scenarios']['right'])
        self.assertIsNone(result['timed_comparison']['right_over_left_damage_per_second'])
        self.assertFalse(result['timed_comparison']['game_winner_established'])
        self.assertEqual(plans, before)


if __name__ == '__main__':
    unittest.main()
