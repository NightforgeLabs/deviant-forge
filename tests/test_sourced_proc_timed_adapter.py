"""Sourced proc events join selected timed pools without direct-hit duplication."""
import copy
import unittest

import component_compare
import integrated_event_model
import sourced_proc_timed_adapter as adapter

ASSUMPTIONS = {'scheduler': 'next_shot_interval',
               'fire_rate_conversion': 'rpm_times_one_plus_bonus',
               'pool_grouping': 'additive_within_named_pool_multiplicative_across_pools',
               'event_order': 'as_list'}
POOLS = {key: 0 for key in integrated_event_model.SUPPORTED_POOLS}
WEAPON = 'weapon:mps7-outer-space'


def scenario(count, *, rpm=1200, duration=2, capacity=None, events=None,
             hit_inputs=None, source_model=None, weapon=WEAPON,
             evidence='dated_release', mods=None, reserve=0):
    if events is None:
        events = [{'kind': 'shot', 'event_id': f's{i}'} for i in range(count)]
    if hit_inputs is None:
        hit_inputs = [{'shot_event_id': f's{i}', 'target': 'dummy',
                       'rolls': {'power_surge': .99},
                       'conditions': {'target_affected_by_power_surge': True}}
                      for i in range(count)]
    return {'model_assumptions': ASSUMPTIONS.copy(), 'base_rpm': rpm,
            'duration_seconds': duration, 'magazine_capacity': capacity or count,
            'starting_magazine_bullets': capacity or count,
            'starting_reserve_bullets': reserve,
            'direct_packet': {'basis_value': 100, 'coefficient_percent': 100,
                              'damage_class': 'weapon', 'element': 'none'},
            'candidate_mods': mods or [], 'events': events,
            'weapon_proc': {'weapon_id': weapon, 'evidence_mode': evidence,
                            'model_mode': 'explicit_assumptions', 'stream_id': 'joined',
                            'hit_inputs': hit_inputs,
                            'damage_model': source_model or {}}}


class SourcedProcTimedTests(unittest.TestCase):
    def test_selected_gilded_crit_changes_only_explicit_burn_ticks(self):
        burn = {'basis': 'psi', 'damage_class': 'status', 'element': 'blaze',
                'keyword': 'burn', 'coefficient_percent': 20,
                'crit': True, 'crit_eligible': True,
                'periodic': {'duration_seconds': 3, 'interval_seconds': 1,
                             'start_delay_seconds': 0, 'refresh_model': 'independent'}}
        request = scenario(7, weapon='weapon:kam-crank', evidence='preview_simulation',
            hit_inputs=[{'shot_event_id': f's{i}', 'target': 'dummy'} for i in range(7)],
            source_model={'basis_values': {'psi': 50}, 'packet_models': {'burn': burn}})
        request.update(duration_seconds=4, selected_armor_ids=['armor:gilded-gauntlets'],
            encounter_mode='pve_non_raidzone',
            outcome_assumptions={'base_crit_bonus_percent': 25,
                                 'joint_multiplier': 'multiplicative'})
        result = adapter.evaluate(request, static_pools=POOLS)
        self.assertAlmostEqual(result['total_damage'], 737.5)
        self.assertEqual([row['damage'] for row in result['packets'] if row['crit']], [12.5] * 3)
        self.assertTrue(all(row['crit_eligibility_source'] == integrated_event_model.GILDED_BURN_SOURCE
                            for row in result['packets'] if row['crit']))
        without = copy.deepcopy(request)
        without['selected_armor_ids'] = []
        partial = adapter.evaluate(without, static_pools=POOLS)
        self.assertIsNone(partial['total_damage'])
        self.assertTrue(any('crit/weakspot eligibility' in row['reason']
                            for row in partial['unresolved_source_packets']))

    def test_counter_packet_gets_current_pools_once(self):
        source = {'basis_values': {'psi': 80},
                  'packet_models': {'celestial_lightning': {'damage_class': 'status'}}}
        request = scenario(12, source_model=source)
        before = copy.deepcopy(request)
        result = adapter.evaluate(request,
            static_pools={**POOLS, 'weapon': 20, 'status': 10, 'elemental': 30})
        self.assertEqual(result['total_damage'], 2012)
        self.assertAlmostEqual(result['shot_times'][-1], .55)
        self.assertEqual(len(result['source_packets']), 1)
        self.assertAlmostEqual(result['packets'][-1]['damage'], 572)
        self.assertEqual(request, before)
        self.assertFalse(result['game_winner_established'])

    def test_explicit_chance_outcome_and_keyword_scope(self):
        request = scenario(1, hit_inputs=[{'shot_event_id': 's0', 'target': 'dummy',
            'rolls': {'power_surge': .1},
            'conditions': {'target_affected_by_power_surge': False}}],
            source_model={'basis_values': {'psi': 50}, 'packet_models': {
                'power_surge': {'basis': 'psi', 'damage_class': 'status',
                                'element': 'shock', 'coefficient_percent': 100,
                                'resolved_hits': 1, 'keyword': 'power_surge'}}})
        result = adapter.evaluate(request, static_pools={**POOLS, 'power_surge': 20})
        self.assertEqual(result['total_damage'], 160)
        self.assertEqual(result['packets'][0]['damage'], 100)
        self.assertEqual(result['packets'][1]['damage'], 60)
        absent = copy.deepcopy(request)
        absent['weapon_proc']['hit_inputs'][0]['rolls']['power_surge'] = .99
        self.assertEqual(adapter.evaluate(absent, static_pools={**POOLS, 'power_surge': 20})
                         ['total_damage'], 100)
        del request['weapon_proc']['damage_model']['packet_models']
        partial = adapter.evaluate(request, static_pools=POOLS)
        self.assertIsNone(partial['total_damage'])
        self.assertEqual(partial['known_damage_subtotal'], 100)

    def test_periodic_ticks_apply_state_at_tick_time_not_trigger_time(self):
        request = scenario(7, weapon='weapon:kam-crank', evidence='preview_simulation',
            hit_inputs=[{'shot_event_id': f's{i}', 'target': 'dummy'} for i in range(7)],
            source_model={'basis_values': {'psi': 50}, 'packet_models': {'burn': {
                'basis': 'psi', 'damage_class': 'status', 'element': 'blaze',
                'coefficient_percent': 20,
                'periodic': {'duration_seconds': 3, 'interval_seconds': 1,
                             'start_delay_seconds': 0, 'refresh_model': 'independent'}}}})
        request['duration_seconds'] = 4
        result = adapter.evaluate(request, static_pools=POOLS)
        self.assertEqual(result['total_damage'], 730)
        for actual, expected in zip([row['at'] for row in result['packets']
                                     if row['event_id'].find('/tick/') >= 0],
                                    [.3, 1.3, 2.3], strict=True):
            self.assertAlmostEqual(actual, expected)

    def test_finite_reaper_refill_enables_counter_trigger(self):
        reaper = {'catalog_id': 'mod:pants_mod:ruthless-reaper', 'level': 10,
                  'allow_candidate': True,
                  'assumptions': {'refill_semantics': 'fill_to_capacity_from_reserves',
                                  'insufficient_reserve': 'transfer_available',
                                  'counter_reset_after_partial_or_empty': True}}
        events = [{'kind': 'shot', 'event_id': 's0'},
                  {'kind': 'kill_enemy', 'event_id': 'k1', 'at': .01},
                  {'kind': 'kill_enemy', 'event_id': 'k2', 'at': .02}]
        events += [{'kind': 'shot', 'event_id': f's{i}'} for i in range(1, 13)]
        request = scenario(13, capacity=12, reserve=1, events=events,
            mods=[reaper], source_model={'basis_values': {'psi': 80},
                'packet_models': {'celestial_lightning': {'damage_class': 'status'}}})
        result = adapter.evaluate(request, static_pools=POOLS)
        self.assertEqual(result['final_ammo'], {'magazine': 0, 'reserve': 0})
        self.assertEqual(len(result['shot_times']), 13)
        self.assertEqual(len(result['source_packets']), 1)
        self.assertEqual(result['total_damage'], 1700)
        self.assertFalse(result['current_level_certified'])

    def test_scheduled_reload_changes_later_sourced_proc_chance(self):
        events = [{'kind': 'shot', 'event_id': 's0'},
                  {'kind': 'reload', 'event_id': 'r1', 'at': .1,
                   'loaded_rounds': 1, 'base_reload_seconds': .1},
                  {'kind': 'shot', 'event_id': 's1'}]
        inputs = [{'shot_event_id': 's0', 'target': 'dummy',
                   'rolls': {'power_surge': .99},
                   'conditions': {'target_affected_by_power_surge': False}},
                  {'shot_event_id': 's1', 'target': 'dummy',
                   'rolls': {'power_surge': .4},
                   'conditions': {'target_affected_by_power_surge': False}}]
        request = scenario(2, capacity=1, reserve=1, events=events,
            hit_inputs=inputs, source_model={'basis_values': {'psi': 50},
                'packet_models': {'power_surge': {
                    'basis': 'psi', 'damage_class': 'status', 'element': 'shock',
                    'coefficient_percent': 100, 'resolved_hits': 1}}})
        result = adapter.evaluate(request, static_pools=POOLS)
        self.assertEqual([row['kind'] for row in result['source_actions']],
                         ['hit', 'reload', 'hit'])
        self.assertAlmostEqual(result['shot_times'][1], .2)
        self.assertEqual(result['total_damage'], 250)
        self.assertEqual(len(result['source_packets']), 1)

    def test_selected_weapon_identity_guard_and_independent_scenario(self):
        base = {pool: 0 for pool in component_compare.POOLS.values()}
        request = scenario(1)
        selected = {'catalog_id': 'weapon:aug-electron-cloud'}
        with self.assertRaisesRegex(ValueError, 'disagrees with selected gear'):
            component_compare.compare(selected, selected, {
                'base_pools': base,
                'integrated_combat': {'left': request, 'right': request}})
        independent = scenario(1)
        independent['weapon_proc']['independent_weapon_scenario'] = True
        result = component_compare.compare({'attributes': []}, {'attributes': []}, {
            'base_pools': base,
            'integrated_combat': {'left': independent, 'right': independent}})
        self.assertEqual(result['integrated_event_scenarios']['left']['total_damage'], 100)
        self.assertIn('Independent weapon scenario',
                      ' '.join(result['integrated_event_scenarios']['left']['selected_row_gaps']))

    def test_predator_ramp_changes_later_weapon_packets_once(self):
        request = scenario(3, weapon='weapon:mg4-predator',
            hit_inputs=[{'shot_event_id': f's{i}', 'target': 'dummy',
                         'rolls': {'fast_gunner': .99}} for i in range(3)])
        request['weapon_proc']['weapon_state_order'] = 'after_direct_hit_before_triggered_packet'
        result = adapter.evaluate(request, static_pools={**POOLS, 'weapon': 20})
        for actual, expected in zip([packet['damage'] for packet in result['packets']],
                                    [120, 124, 128], strict=True):
            self.assertAlmostEqual(actual, expected)
        self.assertEqual(result['total_damage'], 372)
        self.assertEqual(len(result['weapon_state_trace']), 3)
        unspecified = copy.deepcopy(request)
        del unspecified['weapon_proc']['weapon_state_order']
        partial = adapter.evaluate(unspecified, static_pools=POOLS)
        self.assertIsNone(partial['total_damage'])
        self.assertTrue(any('weapon_state_order' in gap['reason']
                            for gap in partial['unresolved_source_packets']))

    def test_doombringer_attack_stack_expires_at_named_boundary(self):
        request = scenario(3, weapon='weapon:dbsg-doombringer', duration=20,
            events=[{'kind': 'shot', 'event_id': 's0', 'at': 0},
                    {'kind': 'shot', 'event_id': 's1', 'at': 1},
                    {'kind': 'shot', 'event_id': 's2', 'at': 16}],
            hit_inputs=[{'shot_event_id': f's{i}', 'target': 'dummy',
                         'distance': 100, 'rolls': {'bullseye': .99},
                         'conditions': {'all_pellets_hit_non_meta_human': True}}
                        for i in range(3)])
        request['direct_packet']['basis_kind'] = 'attack'
        request['weapon_proc']['weapon_state_order'] = 'after_direct_hit_before_triggered_packet'
        result = adapter.evaluate(request, static_pools=POOLS)
        self.assertAlmostEqual(result['total_damage'], 312)
        self.assertAlmostEqual(result['packets'][1]['damage'], 112)
        self.assertEqual(result['packets'][2]['damage'], 100)
        unknown = copy.deepcopy(request)
        del unknown['direct_packet']['basis_kind']
        blocked = adapter.evaluate(unknown, static_pools=POOLS)
        self.assertIsNone(blocked['total_damage'])
        self.assertTrue(any('basis classification missing' in gap['reason']
                            for gap in blocked['unresolved_source_packets']))

    def test_hazardous_reload_blast_uses_consumed_magazine_and_target_count(self):
        events = [{'kind': 'shot', 'event_id': 's0'},
                  {'kind': 'reload', 'event_id': 'r1', 'at': 1,
                   'consume_remaining_magazine_for_blast': True,
                   'refund_outcome': 'none', 'loaded_rounds': 0,
                   'base_reload_seconds': 1}]
        request = scenario(1, weapon='weapon:g17-hazardous-object',
            capacity=5, duration=3, events=events,
            hit_inputs=[{'shot_event_id': 's0', 'target': 'dummy',
                         'rolls': {'unstable_bomber': .99}}],
            source_model={'basis_values': {'psi': 100}, 'packet_models': {
                'thrown_reload_blast': {'damage_class': 'weapon',
                                        'target_count': 2}}})
        result = adapter.evaluate(request, static_pools=POOLS)
        self.assertEqual(result['total_damage'], 344)
        self.assertEqual(result['final_ammo'], {'magazine': 0, 'reserve': 0})
        self.assertEqual(result['event_trace'][1]['consumed_magazine_rounds'], 4)
        self.assertEqual(result['source_packets'][0]['source_packet_id'],
                         'weapon:g17-hazardous-object/thrown_reload_blast')
        capped = copy.deepcopy(request)
        capped['magazine_capacity'] = 30
        capped['starting_magazine_bullets'] = 30
        capped['weapon_proc']['damage_model']['packet_models']['thrown_reload_blast']['target_count'] = 1
        self.assertEqual(adapter.evaluate(capped, static_pools=POOLS)['total_damage'], 580)
        unknown = copy.deepcopy(request)
        del unknown['weapon_proc']['damage_model']['packet_models']['thrown_reload_blast']['target_count']
        partial = adapter.evaluate(unknown, static_pools=POOLS)
        self.assertIsNone(partial['total_damage'])
        self.assertEqual(partial['known_damage_subtotal'], 100)

    def test_hazardous_reload_rejects_unmirrored_ammo_and_refund(self):
        events = [{'kind': 'shot', 'event_id': 's0'},
                  {'kind': 'reload', 'event_id': 'r1', 'at': 1,
                   'loaded_rounds': 0, 'base_reload_seconds': 1}]
        request = scenario(1, weapon='weapon:g17-hazardous-object',
            capacity=5, duration=3, events=events,
            hit_inputs=[{'shot_event_id': 's0', 'target': 'dummy',
                         'rolls': {'unstable_bomber': .99}}])
        with self.assertRaisesRegex(ValueError, 'must consume the actual modeled remaining magazine'):
            adapter.evaluate(request, static_pools=POOLS)
        request['events'][1]['consume_remaining_magazine_for_blast'] = True
        with self.assertRaisesRegex(ValueError, 'refund_outcome=none'):
            adapter.evaluate(request, static_pools=POOLS)
        request['events'][1]['refund_outcome'] = 'none'
        request['events'][1]['loaded_rounds'] = 1
        with self.assertRaisesRegex(ValueError, 'finite reserve'):
            adapter.evaluate(request, static_pools=POOLS)


if __name__ == '__main__':
    unittest.main()
