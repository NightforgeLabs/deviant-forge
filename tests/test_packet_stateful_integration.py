"""Frozen weapon packet timelines and opt-in stateful mod candidates in Forge APIs."""
import unittest

import component_compare
import mod_stateful_api
import weapon_timeline_api


class AdditionalPacketTimelineTests(unittest.TestCase):
    def run_packet(self, weapon_id, actions, *, mode='dated_release', attack=100,
                   psi=100, **extra):
        return weapon_timeline_api.simulate({
            'weapon_id': weapon_id, 'evidence_mode': mode, 'stream_id': 'isolated-v4',
            'actions': actions, 'damage_model': {'basis_values': {'attack': attack, 'psi': psi},
                                                'duration_seconds': 2}, **extra})

    def test_five_packet_families_project_source_base_without_claiming_total(self):
        cases = [
            ('weapon:r500-hammerhead-shark', 'dated_release',
             [{'kind': 'hammerhead_chain_hit', 'at': 0, 'input_id': 'h',
               'primary_target': 'main', 'primary_power_surge_status': True,
               'nearby_affected_targets': ['second']}], {}, 80),
            ('weapon:kvd-boom-boom', 'preview_simulation',
             [{'kind': 'boom_boom_hit', 'at': 0, 'input_id': 'h',
               'explosion_targets': ['dummy']}], {}, 300),
            ('weapon:acs12-pyroclasm-starter', 'preview_simulation',
             [{'kind': 'pyroclasm_charged_shot', 'at': 0, 'input_id': 'h',
               'resolved_damage_units': ['dummy']}], {'observed_charged_rounds': 1}, 95),
            ('weapon:sks-pathfinder', 'preview_simulation',
             [{'kind': 'pathfinder_charged_shot', 'at': 0, 'input_id': 'h',
               'charge_cost': 1, 'pierced_targets': ['dummy']}], {'observed_charges': 1}, 110),
            ('weapon:pdw90-holographic-resonance', 'preview_simulation',
             [{'kind': 'holographic_hit', 'at': n / 20, 'input_id': f'h{n}',
               **({'pulse_targets': ['dummy']} if n == 10 else {})}
              for n in range(11)], {'counter_overflow': 'subtract'}, 800),
        ]
        for weapon, mode, actions, extras, expected in cases:
            with self.subTest(weapon=weapon):
                run = self.run_packet(weapon, actions, mode=mode, **extras)
                self.assertAlmostEqual(run['damage_projection']['known_damage_subtotal'], expected)
                self.assertIsNone(run['total_damage'])
                self.assertIsNone(run['damage_per_second'])
                self.assertGreater(len(run['damage_projection']['unresolved_damage_events']), 0)
                self.assertFalse(run['damage_projection']['scope'].startswith('verified current'))
        orb = self.run_packet('weapon:critical-pulse', [
            {'kind': 'critical_pulse_start_orb', 'at': 0, 'input_id': 'orb',
             'hit_target': 'dummy', 'orb_duration_seconds': 1,
             'first_tick_delay_seconds': 0, 'include_endpoint': False},
            {'kind': 'critical_pulse_orb_tick', 'at': 0, 'input_id': 'tick-a',
             'orb_id': 'orb', 'target': 'dummy', 'distance_meters': 2},
            {'kind': 'critical_pulse_orb_tick', 'at': 0, 'input_id': 'tick-b',
             'orb_id': 'orb', 'target': 'dummy', 'distance_meters': 2}],
            observed_charges=1)
        self.assertEqual(orb['damage_projection']['known_damage_subtotal'], 75)
        self.assertEqual(len(orb['damage_projection']['packets']), 1)

    def test_preview_gate_and_replayed_event_ids(self):
        action = {'kind': 'boom_boom_hit', 'at': 0, 'input_id': 'h',
                  'explosion_targets': ['dummy']}
        with self.assertRaisesRegex(ValueError, 'preview'):
            self.run_packet('weapon:kvd-boom-boom', [action], mode='dated_release')
        replayed = self.run_packet('weapon:kvd-boom-boom', [action, action],
                                   mode='preview_simulation')
        self.assertEqual(replayed['replayed_events_suppressed'], 1)
        self.assertEqual(replayed['damage_projection']['known_damage_subtotal'], 300)
        paired = component_compare.compare({'attributes': []}, {'attributes': []},
            {'weapon_timeline': {
                'left': {'weapon_id': 'weapon:kvd-boom-boom', 'evidence_mode': 'preview_simulation',
                         'stream_id': 'left-v4', 'actions': [action],
                         'damage_model': {'basis_values': {'psi': 100}, 'duration_seconds': 2}},
                'right': {'weapon_id': 'weapon:kvd-boom-boom', 'evidence_mode': 'preview_simulation',
                          'stream_id': 'right-v4', 'actions': [action],
                          'damage_model': {'basis_values': {'psi': 100}, 'duration_seconds': 2}}}})
        self.assertEqual(paired['weapon_timeline_scenarios']['left']['damage_projection']
                         ['known_damage_subtotal'], 300)
        self.assertFalse(paired['game_winner_established'])
        with self.assertRaisesRegex(ValueError, 'packet-only weapon timelines cannot apply'):
            component_compare.compare({'attributes': []}, {'attributes': []},
                {'base_pools': {pool: 0 for pool in component_compare.TIMELINE_DAMAGE_POOLS},
                 'weapon_timeline_pool_mode': 'selected_reviewed_rows',
                 'weapon_timeline': {'left': {'weapon_id': 'weapon:kvd-boom-boom', 'damage_model': {}},
                                     'right': {'weapon_id': 'weapon:kvd-boom-boom', 'damage_model': {}}}})


class StatefulModIntegrationTests(unittest.TestCase):
    def test_candidate_gate_and_two_executable_families(self):
        momentum = {'catalog_id': 'mod:helmet_mod:momentum-up', 'level': 10,
                    'allow_candidate': True,
                    'initial': {'magazine_capacity': 10, 'magazine_id': 'm1',
                                'full_magazine': True},
                    'assumptions': {'phase_basis': 'consumed_ammo_fraction',
                                    'exact_half_boundary_owner': 'second_half'},
                    'events': [{'type': 'consume', 'event_id': 'shots-1', 'bullets': 5}]}
        with self.assertRaisesRegex(ValueError, 'allow_candidate'):
            mod_stateful_api.simulate({**momentum, 'allow_candidate': False})
        run = mod_stateful_api.simulate(momentum)
        self.assertEqual(run['outputs'][0]['stat'], 'weapon_damage_percent')
        self.assertEqual(run['outputs'][0]['percentage_points'], 30)
        self.assertFalse(run['current_level_certified'])
        reaper = {'catalog_id': 'mod:pants_mod:ruthless-reaper', 'level': 10,
                  'allow_candidate': True,
                  'initial': {'magazine_capacity': 30, 'magazine_bullets': 10,
                              'reserve_bullets': 15},
                  'assumptions': {'refill_semantics': 'fill_to_capacity_from_reserves',
                                  'insufficient_reserve': 'transfer_available',
                                  'counter_reset_after_partial_or_empty': True},
                  'events': [{'type': 'kill_enemy', 'event_id': 'k1'},
                             {'type': 'kill_enemy', 'event_id': 'k1'},
                             {'type': 'kill_enemy', 'event_id': 'k2'}]}
        run = mod_stateful_api.simulate(reaper)
        self.assertEqual(run['outputs'][0]['bullets'], 15)
        self.assertEqual(run['final_state']['reserve'], 0)
        self.assertIn('duplicate_event_ignored', run['unresolved'])
        covered = {'catalog_id': 'mod:boots_mod:covered-advance-battle',
                   'level': 10, 'allow_candidate': True,
                   'initial': {'start_time_seconds': 0},
                   'assumptions': {'damage_during_active': 'does_not_cancel'},
                   'events': [{'type': 'damage_taken', 'event_id': 'hit',
                               'time_seconds': 5}]}
        active = mod_stateful_api.simulate(covered)
        self.assertEqual(len(active['outputs']), 3)
        self.assertEqual(active['final_state']['active_until'], 34)
        self.assertFalse(active['current_level_certified'])
        dense = mod_stateful_api.simulate({**covered, 'events': [
            {'type': 'tick', 'time_seconds': 4.5},
            {'type': 'damage_taken', 'event_id': 'hit', 'time_seconds': 5}]})
        self.assertEqual(dense['trace'][-1]['outputs'], active['trace'][-1]['outputs'])
        self.assertEqual(dense['final_state'], active['final_state'])
        with self.assertRaisesRegex(ValueError, 'activation_boundary_order'):
            mod_stateful_api.simulate({**covered, 'events': [
                {'type': 'damage_taken', 'event_id': 'boundary', 'time_seconds': 4}]})

    def test_selected_mod_linkage_keeps_candidate_output_separate(self):
        scenario = {'catalog_id': 'mod:helmet_mod:momentum-up', 'level': 10,
                    'allow_candidate': True,
                    'initial': {'magazine_capacity': 10, 'magazine_id': 'm1',
                                'full_magazine': True},
                    'assumptions': {'phase_basis': 'consumed_ammo_fraction'},
                    'events': [{'type': 'inspect'}]}
        item = {'catalog_id': 'mod:helmet_mod:momentum-up', 'level': 10}
        compared = component_compare.compare(item, item,
            {'mod_stateful': {'left': scenario, 'right': scenario}})
        self.assertEqual(compared['mod_stateful_scenarios']['left']['outputs'][0]['type'],
                         'stat_pool_delta')
        self.assertEqual(compared['component_ratios']['normal']['min'], 1)
        self.assertFalse(compared['game_winner_established'])
        with self.assertRaisesRegex(ValueError, 'match selected gear'):
            component_compare.compare({'attributes': []}, item,
                {'mod_stateful': {'left': scenario, 'right': scenario}})


if __name__ == '__main__':
    unittest.main()
