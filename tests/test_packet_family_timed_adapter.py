"""All six frozen packet timelines feed the shared timed combat scheduler."""
import copy
import unittest

import component_compare
import packet_family_timed_adapter as adapter
import weapon_timeline_api
from tests.test_sourced_proc_timed_adapter import POOLS, scenario


def packet_scenario(weapon, source_actions, *, count=1, evidence='dated_release',
                    attack=100, psi=100, hypothesis=None, **resources):
    result = scenario(count, weapon=weapon)
    result['weapon_proc'] = {'weapon_id': weapon, 'evidence_mode': evidence,
        'stream_id': 'six-family-fixture', 'source_actions': source_actions,
        'damage_model': {'basis_values': {'attack': attack, 'psi': psi}},
        'packet_hypotheses': hypothesis or {}, **resources}
    return result


class PacketFamilyTimedTests(unittest.TestCase):
    def test_coverage_lists_all_integrated_packet_hooks_and_missing_inputs(self):
        coverage = weapon_timeline_api.coverage()
        self.assertEqual(coverage['integrated_timed_packet_weapons'], 6)
        self.assertEqual(coverage['integrated_timed_representative_weapons'], 9)
        self.assertIn('orb_duration_seconds', coverage['packet_hook_coverage']
                      ['weapon:critical-pulse']['required_caller_inputs'])
        self.assertEqual(coverage['packet_hook_coverage']
                         ['weapon:pdw90-holographic-resonance']['scheduled_hit_coverage']
                         ['coverage'], 'every_landed_hit')

    def test_critical_pulse_orb_uses_entered_charge_schedule_and_timed_status_pool(self):
        weapon = 'weapon:critical-pulse'
        actions = [{'kind': 'critical_pulse_start_orb', 'shot_event_id': 's0',
                    'input_id': 'orb', 'hit_target': 'dummy',
                    'orb_duration_seconds': 1, 'first_tick_delay_seconds': 0,
                    'include_endpoint': False},
                   {'kind': 'critical_pulse_orb_tick', 'at': 0,
                    'input_id': 'tick', 'orb_id': 'orb', 'target': 'dummy',
                    'distance_meters': 2}]
        request = packet_scenario(weapon, actions, observed_charges=1)
        before = copy.deepcopy(request)
        result = adapter.evaluate(request, static_pools={**POOLS, 'status': 20})
        self.assertEqual(result['total_damage'], 190)
        self.assertEqual(len(result['source_packets']), 1)
        self.assertEqual(result['resource_state']['observed_charges'], 0)
        self.assertEqual(request, before)
        self.assertFalse(result['game_winner_established'])

    def test_hammerhead_chain_keeps_unresolved_main_target_separate(self):
        weapon = 'weapon:r500-hammerhead-shark'
        actions = [{'kind': 'hammerhead_chain_hit', 'shot_event_id': 's0',
                    'input_id': 'h', 'primary_target': 'main',
                    'primary_power_surge_status': True,
                    'nearby_affected_targets': ['second']}]
        hypothesis = {weapon + '/shock_chain': {'damage_class': 'status'}}
        result = adapter.evaluate(packet_scenario(weapon, actions,
            hypothesis=hypothesis), static_pools=POOLS)
        self.assertIsNone(result['total_damage'])
        self.assertEqual(result['known_damage_subtotal'], 180)
        self.assertTrue(any('main_target_150_percent' in row['reason']
                            for row in result['unresolved_source_packets']))

    def test_boom_boom_preview_cooldown_and_class_hypothesis(self):
        weapon = 'weapon:kvd-boom-boom'
        actions = [{'kind': 'boom_boom_hit', 'shot_event_id': 's0',
                    'input_id': 'h', 'explosion_targets': ['dummy']}]
        hypothesis = {weapon + '/explosion': {'damage_class': 'status'}}
        request = packet_scenario(weapon, actions, evidence='preview_simulation',
                                  hypothesis=hypothesis)
        self.assertEqual(adapter.evaluate(request, static_pools=POOLS)['total_damage'], 400)
        request['weapon_proc']['evidence_mode'] = 'dated_release'
        with self.assertRaisesRegex(ValueError, 'preview'):
            adapter.evaluate(request, static_pools=POOLS)
        request['weapon_proc']['evidence_mode'] = 'preview_simulation'
        del request['weapon_proc']['packet_hypotheses'][weapon + '/explosion']
        partial = adapter.evaluate(request, static_pools=POOLS)
        self.assertIsNone(partial['total_damage'])
        self.assertEqual(partial['known_damage_subtotal'], 100)

    def test_pyroclasm_charged_units_are_explicit_and_count_once(self):
        weapon = 'weapon:acs12-pyroclasm-starter'
        actions = [{'kind': 'pyroclasm_charged_shot', 'shot_event_id': 's0',
                    'input_id': 'h', 'resolved_damage_units': ['dummy', 'dummy']}]
        request = packet_scenario(weapon, actions, evidence='preview_simulation',
                                  observed_charged_rounds=1)
        result = adapter.evaluate(request, static_pools=POOLS)
        self.assertEqual(result['total_damage'], 290)
        self.assertEqual(len(result['source_packets']), 2)
        self.assertEqual(result['resource_state']['observed_charged_rounds'], 0)

    def test_pathfinder_charge_and_pierce_targets_are_explicit(self):
        weapon = 'weapon:sks-pathfinder'
        actions = [{'kind': 'pathfinder_charged_shot', 'shot_event_id': 's0',
                    'input_id': 'h', 'charge_cost': 1,
                    'pierced_targets': ['a', 'b']}]
        request = packet_scenario(weapon, actions, evidence='preview_simulation',
                                  observed_charges=1)
        result = adapter.evaluate(request, static_pools=POOLS)
        self.assertEqual(result['total_damage'], 320)
        self.assertEqual(len(result['source_packets']), 2)
        request['weapon_proc']['observed_charges'] = 0
        with self.assertRaisesRegex(ValueError, 'charge balance'):
            adapter.evaluate(request, static_pools=POOLS)

    def test_holographic_counter_requires_explicit_element_and_targets(self):
        weapon = 'weapon:pdw90-holographic-resonance'
        actions = [{'kind': 'holographic_hit', 'shot_event_id': f's{i}',
                    'input_id': f'h{i}',
                    **({'pulse_targets': ['dummy']} if i == 10 else {})}
                   for i in range(11)]
        hypothesis = {weapon + '/area_pulse': {'element': 'none'}}
        request = packet_scenario(weapon, actions, count=11,
            evidence='preview_simulation', counter_overflow='subtract',
            hypothesis=hypothesis)
        result = adapter.evaluate(request, static_pools=POOLS)
        self.assertEqual(result['total_damage'], 1900)
        self.assertEqual(len(result['source_packets']), 1)
        del request['weapon_proc']['packet_hypotheses'][weapon + '/area_pulse']
        self.assertIsNone(adapter.evaluate(request, static_pools=POOLS)['total_damage'])
        incomplete = copy.deepcopy(request)
        incomplete['weapon_proc']['source_actions'] = [actions[-1]]
        with self.assertRaisesRegex(ValueError, 'Every eligible modeled landed hit'):
            adapter.evaluate(incomplete, static_pools=POOLS)
        inconsistent = copy.deepcopy(request)
        inconsistent['weapon_proc']['ineligible_shots'] = {'s0': 'missed'}
        with self.assertRaisesRegex(ValueError, 'Every landed shot needs'):
            adapter.evaluate(inconsistent, static_pools=POOLS)

    def test_shot_link_and_selection_guard_prevent_independent_double_count(self):
        weapon = 'weapon:kvd-boom-boom'
        actions = [{'kind': 'boom_boom_hit', 'shot_event_id': 'not-a-shot',
                    'input_id': 'h', 'explosion_targets': ['dummy']}]
        request = packet_scenario(weapon, actions, evidence='preview_simulation')
        with self.assertRaisesRegex(ValueError, 'scheduled shot_event_id'):
            adapter.evaluate(request, static_pools=POOLS)
        request['weapon_proc']['source_actions'][0]['shot_event_id'] = 's0'
        request['weapon_proc']['source_actions'].append(
            copy.deepcopy(request['weapon_proc']['source_actions'][0]))
        with self.assertRaisesRegex(ValueError, 'attached twice'):
            adapter.evaluate(request, static_pools=POOLS)
        request['weapon_proc']['source_actions'].pop()
        base = {pool: 0 for pool in component_compare.POOLS.values()}
        with self.assertRaisesRegex(ValueError, 'disagrees with selected gear'):
            component_compare.compare({'catalog_id': 'weapon:aug-electron-cloud'},
                {'catalog_id': 'weapon:aug-electron-cloud'},
                {'base_pools': base, 'integrated_combat': {'left': request,
                                                          'right': request}})

    def test_conditional_charged_hook_requires_explicit_ordinary_shot_exclusion(self):
        weapon = 'weapon:sks-pathfinder'
        actions = [{'kind': 'pathfinder_charged_shot', 'shot_event_id': 's1',
                    'input_id': 'charged', 'charge_cost': 1,
                    'pierced_targets': ['dummy']}]
        request = packet_scenario(weapon, actions, count=2,
            evidence='preview_simulation', observed_charges=1)
        with self.assertRaisesRegex(ValueError, 'Every eligible modeled landed hit'):
            adapter.evaluate(request, static_pools=POOLS)
        request['weapon_proc']['ineligible_shots'] = {'s0': 'ordinary_uncharged_shot'}
        result = adapter.evaluate(request, static_pools=POOLS)
        self.assertEqual(result['total_damage'], 310)
        self.assertEqual(result['source_hit_coverage']['ineligible_shots'],
                         {'s0': 'ordinary_uncharged_shot'})
        request['weapon_proc']['ineligible_shots'] = {'s0': 'missed'}
        with self.assertRaisesRegex(ValueError, 'named source eligibility policy'):
            adapter.evaluate(request, static_pools=POOLS)


if __name__ == '__main__':
    unittest.main()
