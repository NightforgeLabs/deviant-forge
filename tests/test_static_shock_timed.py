"""Static Shock modifies Power Surge damage and target status lifetime, not ticks."""
from copy import deepcopy
import unittest

from tests.explicit_reference_fixture import explicit_synthetic_reference
import mod_core_typed
import published_reference_model
import published_timed_combat
import structured_compare

MOD = 'mod:weapon_mod:static-shock-survival'
WEAPON = 'weapon:mps7-outer-space'
STATUS = {'base_duration_seconds': 6, 'refresh_model': 'replace_per_target',
          'event_order': 'after_landing_hit'}


def typed():
    row = mod_core_typed.evaluate(MOD, 11)
    row['item_name'] = 'Static Shock <Survival>'
    return row


def controls(count, *, triggers=(0,), status_duration=6, periodic=None):
    packet = {'basis': 'psi', 'damage_class': 'status', 'element': 'shock',
              'coefficient_percent': 100, 'keyword': 'power_surge', 'resolved_hits': 1}
    if periodic is not None:
        packet['periodic'] = periodic
    return {'reserve_bullets': 0, 'target_id': 'dummy',
            'roll_sequence': [.1 if i in triggers else .99 for i in range(count)],
            'condition_sequences': {'target_affected_by_power_surge':
                [False] + [True] * (count - 1)},
            'damage_model': {'basis_values': {'psi': 100},
                             'packet_models': {'power_surge': packet}}}


@explicit_synthetic_reference
class StaticShockTimedTests(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.build = published_reference_model.build({'weapon': {'catalog_id': WEAPON},
            'mods': [{'catalog_id': MOD, 'level': 11}]})
        self.duration = .2
        self.shots = len(published_timed_combat.evaluate(self.build,
            {'duration_seconds': self.duration})['shot_times'])

    def run_status(self, entered, *, with_mod=True, status=STATUS):
        return published_timed_combat.evaluate(self.build,
            {'duration_seconds': self.duration, 'source_timeline': entered,
             'power_surge_status_model': status},
            typed_main_effects=[typed()] if with_mod else [])

    def test_instant_damage_once_and_status_lifetime_only(self):
        entered = controls(self.shots)
        before = deepcopy(entered)
        plain = self.run_status(entered, with_mod=False)
        selected = self.run_status(entered)
        self.assertEqual(before, entered)
        self.assertEqual(1, len(plain['source_timeline']['source_packets']))
        self.assertEqual(1, len(selected['source_timeline']['source_packets']))
        self.assertAlmostEqual(103, plain['source_proc']['damage'])
        self.assertAlmostEqual(123.6, selected['source_proc']['damage'])
        self.assertEqual(20, selected['effective_pools_percent']['power_surge'])
        window = selected['source_timeline']['status_duration_transforms'][0]
        self.assertEqual(6, window['base_duration_seconds'])
        self.assertEqual(3, window['effective_duration_seconds'])
        self.assertEqual(3, window['status_windows'][0]['end_seconds'])
        self.assertFalse(window['damage_packet_count_changed'])
        self.assertEqual('partial_timed_total', selected['status'])
        self.assertFalse(selected['game_winner_established'])

    def test_expiry_refresh_and_condition_mismatch_are_explicit(self):
        short = {**STATUS, 'base_duration_seconds': .2}
        entered = controls(self.shots)
        entered['condition_sequences']['target_affected_by_power_surge'] = [False, True, False]
        result = self.run_status(entered, status=short)
        self.assertEqual(.1, result['source_timeline']['status_duration_transforms'][0]
                         ['effective_duration_seconds'])
        self.assertEqual([], result['source_timeline']['status_duration_unresolved'])
        entered['condition_sequences']['target_affected_by_power_surge'][2] = True
        conflict = self.run_status(entered, status=short)
        self.assertTrue(any('conflicts with modeled status expiry' in gap
                            for gap in conflict['unresolved']))
        self.assertIsNone(conflict['modeled_total_damage'])
        entered = controls(self.shots, triggers=(0, 1))
        refreshed = self.run_status(entered, status=short)
        windows = refreshed['source_timeline']['status_duration_transforms'][0]['status_windows']
        self.assertEqual(2, len(windows))
        self.assertAlmostEqual(refreshed['shot_times'][1], windows[0]['end_seconds'])
        self.assertGreater(windows[1]['end_seconds'], refreshed['shot_times'][2])

    def test_explicit_periodic_damage_schedule_is_not_halved(self):
        periodic = {'duration_seconds': 2, 'interval_seconds': .05,
                    'start_delay_seconds': 0, 'refresh_model': 'independent',
                    'include_endpoint': False}
        entered = controls(self.shots, periodic=periodic)
        plain = self.run_status(entered, with_mod=False)
        selected = self.run_status(entered)
        self.assertEqual(len(plain['source_timeline']['source_packets']),
                         len(selected['source_timeline']['source_packets']))
        self.assertEqual(2, entered['damage_model']['packet_models']['power_surge']
                         ['periodic']['duration_seconds'])
        self.assertTrue(all(row['event'] == 'power_surge_tick'
                            for row in selected['source_timeline']['source_packets']))
        self.assertEqual(3, selected['source_timeline']['status_duration_transforms'][0]
                         ['effective_duration_seconds'])
        # The repeating damage is a caller hypothesis, not ordinary Power Surge evidence.
        self.assertTrue(all(row['source_status'] == 'caller_explicit_packet_assumption'
                            for row in selected['source_timeline']['source_packets']))

    def test_instant_lightning_and_missing_lifetime_are_not_inferred(self):
        entered = controls(self.shots, triggers=())
        entered['condition_sequences']['target_affected_by_power_surge'] = [False] * self.shots
        entered['damage_model']['packet_models'] = {
            'celestial_lightning': {'damage_class': 'status', 'keyword': 'shock'}}
        plain = self.run_status(entered, with_mod=False)
        selected = self.run_status(entered)
        self.assertEqual(plain['source_proc']['damage'], selected['source_proc']['damage'])
        self.assertEqual([], selected['source_timeline']['status_duration_transforms'][0]
                         ['status_windows'])
        no_model = self.run_status(controls(self.shots), status=None)
        self.assertTrue(any('base lifetime' in gap for gap in no_model['unresolved']))
        self.assertIsNone(no_model['modeled_total_damage'])

    def test_direct_only_gap_does_not_claim_status_damage_ticks(self):
        result = published_timed_combat.evaluate(
            self.build, {'duration_seconds': self.duration},
            typed_main_effects=[typed()])
        self.assertTrue(any('linked status application and baseline lifetime' in gap
                            for gap in result['unresolved']))
        self.assertFalse(any('tick schedule' in gap for gap in result['unresolved']))
        self.assertIsNone(result['modeled_total_damage'])

    def test_critical_pulse_orb_ticks_keep_weapon_specific_schedule(self):
        build = published_reference_model.build({
            'weapon': {'catalog_id': 'weapon:critical-pulse'},
            'mods': [{'catalog_id': MOD, 'level': 11}]})
        recipe = {'charged_shot_indices': [0], 'observed_charges': 1,
                  'orb_duration_seconds': 1, 'first_tick_delay_seconds': 0,
                  'include_endpoint': False, 'orb_tick_times': [0, .5],
                  'orb_tick_target': 'dummy', 'orb_tick_distance_meters': 2}
        source = {'reserve_bullets': 0, 'target_id': 'dummy',
                  'packet_recipe': recipe, 'damage_model': {'basis_values': {'psi': 100}}}
        options = {'duration_seconds': .6, 'source_timeline': source,
                   'power_surge_status_model': STATUS}
        plain = published_timed_combat.evaluate(build, options)
        selected = published_timed_combat.evaluate(build, options,
                                                    typed_main_effects=[typed()])
        self.assertEqual(2, len(plain['source_timeline']['source_packets']))
        self.assertEqual(2, len(selected['source_timeline']['source_packets']))
        self.assertEqual(plain['source_proc']['damage'], selected['source_proc']['damage'])
        self.assertEqual([], selected['source_timeline']['status_duration_transforms'][0]
                         ['status_windows'])

    def test_catalog_and_saved_plan_use_same_status_path(self):
        entered = controls(self.shots)
        plan = {'id': 'synthetic-static-shock', 'name': 'Static Shock test plan',
                'slots': {'primary': {'catalog_id': WEAPON,
                                      'mod_id': MOD, 'mod_level': 11}}}
        request = {'left': {'kind': 'catalog', 'catalog_id': MOD, 'level': 11},
                   'right': {'kind': 'planned_build', 'planned_build_id': plan['id']},
                   'context': {'published_reference': {'enabled': True,
                       'left': {'weapon_id': WEAPON}, 'right': {'weapon_id': WEAPON},
                       'timed': {'duration_seconds': self.duration,
                           'shared_target_confirmed': True,
                           'left': {'source_timeline': entered,
                                    'power_surge_status_model': STATUS},
                           'right': {'source_timeline': entered,
                                     'power_surge_status_model': STATUS}}}}}
        result = structured_compare.compare(request, [plan])['published_reference']
        left, right = result['timed_scenarios']['left'], result['timed_scenarios']['right']
        self.assertEqual(left['source_proc']['damage'], right['source_proc']['damage'])
        self.assertEqual(left['source_timeline']['status_duration_transforms'],
                         right['source_timeline']['status_duration_transforms'])
        self.assertFalse(result['timed_comparison']['game_winner_established'])


if __name__ == '__main__':
    unittest.main()
