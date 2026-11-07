"""Explicit Wind Cap ammo hypotheses and finite-ammo event ordering."""
from __future__ import annotations
from tests.explicit_reference_fixture import explicit_synthetic_reference

import copy
import unittest

import integrated_event_model as model
import published_reference_model as reference
import published_timed_combat as combat

ASSUMPTIONS = {'scheduler': 'next_shot_interval',
               'fire_rate_conversion': 'rpm_times_one_plus_bonus',
               'pool_grouping': 'additive_within_named_pool_multiplicative_across_pools',
               'event_order': 'as_list'}
POOLS = {key: 0 for key in model.SUPPORTED_POOLS}


def event_request(events, *, magazine=1, reserve=0, capacity=2):
    return {'model_assumptions': ASSUMPTIONS, 'base_rpm': 600,
            'duration_seconds': 2, 'magazine_capacity': capacity,
            'starting_magazine_bullets': magazine,
            'starting_reserve_bullets': reserve,
            'direct_packet': {'basis_value': 100, 'coefficient_percent': 100,
                              'damage_class': 'weapon', 'element': 'none'},
            'events': events}


def reload_event():
    return {'kind': 'reload', 'event_id': 'reload-0', 'at': 0,
            'loaded_rounds': 0, 'base_reload_seconds': .25,
            'consume_remaining_magazine_for_blast': True}


def load_event(model_name='created_after_reload', event_id='load-0'):
    return {'kind': 'ammo_load', 'event_id': event_id, 'at': 0,
            'rounds': 1, 'source_effect': 'wind_intepreter_cap',
            'linked_reload_event_id': 'reload-0', 'source_model': model_name}


@explicit_synthetic_reference
class WindAmmoScenarioTests(unittest.TestCase):
    def test_created_bullet_survives_reload_and_replay_cannot_double_count(self):
        events = [reload_event(), load_event(), load_event(),
                  {'kind': 'shot', 'event_id': 'shot-0'}]
        before = copy.deepcopy(events)
        result = model.evaluate(event_request(events), static_pools=POOLS)
        self.assertEqual(result['shot_times'], [.25])
        self.assertEqual(result['final_ammo'], {'magazine': 0, 'reserve': 0})
        self.assertEqual(result['replayed_events_suppressed'], 1)
        load = next(row for row in result['event_trace'] if row['kind'] == 'ammo_load')
        self.assertEqual(load['candidate_outputs'][0]['rounds_loaded'], 1)
        self.assertEqual(events, before)
        with self.assertRaisesRegex(ValueError, 'One Wind bullet load'):
            model.evaluate(event_request([reload_event(), load_event(),
                                          load_event(event_id='load-1')]),
                           static_pools=POOLS)

    def test_capacity_reserve_source_and_reload_order_are_explicit(self):
        full = model.evaluate(event_request([{'kind': 'reload', 'event_id': 'reload-0',
            'at': 0, 'loaded_rounds': 2, 'base_reload_seconds': .25,
            'consume_remaining_magazine_for_blast': True}, load_event()],
            reserve=2), static_pools=POOLS)
        self.assertEqual(full['final_ammo'], {'magazine': 2, 'reserve': 0})
        self.assertEqual(full['event_trace'][-1]['candidate_outputs'][0]['rounds_loaded'], 0)
        empty = model.evaluate(event_request([reload_event(),
            load_event('reserve_transfer_after_reload')]), static_pools=POOLS)
        self.assertEqual(empty['final_ammo'], {'magazine': 0, 'reserve': 0})
        bound = model.evaluate(event_request([reload_event(),
            load_event('not_retained_during_reload')]), static_pools=POOLS)
        self.assertEqual(bound['final_ammo'], empty['final_ammo'])
        with self.assertRaisesRegex(ValueError, 'must follow'):
            model.evaluate(event_request([load_event(), reload_event()]), static_pools=POOLS)
        delayed = load_event();delayed['at'] = .1
        with self.assertRaisesRegex(ValueError, 'same time'):
            model.evaluate(event_request([reload_event(), delayed]), static_pools=POOLS)
        interrupted = {'kind': 'reload', 'event_id': 'reload-1', 'at': .1,
                       'loaded_rounds': 0, 'base_reload_seconds': .25,
                       'consume_remaining_magazine_for_blast': True}
        with self.assertRaisesRegex(ValueError, 'before previous reload completes'):
            model.evaluate(event_request([reload_event(), load_event(), interrupted]),
                           static_pools=POOLS)

    def test_hazardous_reload_blast_one_load_per_explosion_not_per_target(self):
        build = reference.build({'weapon': {'catalog_id': 'weapon:g17-hazardous-object'},
                                 'armor': [{'catalog_id': 'armor:wind-intepreter-cap'}]})
        baseline = {'duration_seconds': 3, 'scenario_mode': 'pve_non_raidzone',
            'source_timeline': {'reserve_bullets': 0, 'target_id': 'dummy',
                'reload_after_shots': 1,
                'damage_model': {'basis_values': {'psi': 100},
                    'packet_models': {'thrown_reload_blast': {
                        'damage_class': 'weapon', 'target_count': 2}}}}}
        absent = combat.evaluate(build, {**baseline, 'source_timeline': {
            **baseline['source_timeline'], 'roll_sequence': [.99]}})
        self.assertEqual(absent['status'], 'partial_timed_total')
        self.assertEqual(len(absent['shot_times']), 1)
        created = combat.evaluate(build, {**baseline, 'source_timeline': {
            **baseline['source_timeline'], 'roll_sequence': [.99, .99],
            'wind_ammo_scenario': 'created_after_reload'}})
        self.assertEqual(created['status'], 'conditional_modeled_total')
        self.assertEqual(len(created['shot_times']), 2)
        self.assertEqual(len(created['source_timeline']['source_packets']), 1)
        self.assertEqual(len(created['source_timeline']['wind_ammo_trace']), 1)
        self.assertEqual(created['source_timeline']['wind_ammo_trace'][0]
                         ['candidate_outputs'][0]['rounds_loaded'], 1)
        self.assertAlmostEqual(created['known_damage_subtotal'], 1135.304)
        self.assertFalse(created['game_winner_established'])
        for scenario in ('reserve_transfer_after_reload', 'not_retained_during_reload'):
            with self.subTest(scenario=scenario):
                lower = combat.evaluate(build, {**baseline, 'source_timeline': {
                    **baseline['source_timeline'], 'roll_sequence': [.99],
                    'wind_ammo_scenario': scenario}})
                self.assertEqual(len(lower['shot_times']), 1)
                self.assertAlmostEqual(lower['known_damage_subtotal'], 900.152)
                self.assertEqual(lower['source_timeline']['final_ammo'],
                                 {'magazine': 0, 'reserve': 0})
                self.assertEqual(lower['status'], 'conditional_modeled_total')
        with self.assertRaisesRegex(ValueError, 'requires selected cap'):
            plain = reference.build({'weapon': {'catalog_id': 'weapon:g17-hazardous-object'}})
            combat.evaluate(plain, {**baseline, 'source_timeline': {
                **baseline['source_timeline'], 'roll_sequence': [.99],
                'wind_ammo_scenario': 'created_after_reload'}})
        with self.assertRaisesRegex(ValueError, 'PvE non-RaidZone'):
            combat.evaluate(build, {**baseline, 'scenario_mode': 'raidzone',
                'source_timeline': {**baseline['source_timeline'],
                    'roll_sequence': [.99],
                    'wind_ammo_scenario': 'created_after_reload'}})


if __name__ == '__main__':
    unittest.main()
