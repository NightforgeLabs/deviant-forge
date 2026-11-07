from tests.explicit_reference_fixture import explicit_synthetic_reference
"""Guided packet hooks share the published finite-shot scheduler."""
import copy
import unittest

import published_reference_model
import published_timed_combat
import weapon_packet_timeline_api


def run(weapon, duration, recipe, *, bases, hypothesis=None, evidence='dated_release',
        reserve=0, target='dummy'):
    build = published_reference_model.build({'weapon': {'catalog_id': weapon}})
    controls = {'reserve_bullets': reserve, 'target_id': target,
                'evidence_mode': evidence, 'packet_recipe': recipe,
                'damage_model': {'basis_values': bases},
                'packet_hypotheses': {weapon_packet_timeline_api.BINDINGS[weapon]['packet_id']:
                                      hypothesis or {}}}
    return published_timed_combat.evaluate(build, {'duration_seconds': duration,
                                                   'source_timeline': controls}), build, controls


@explicit_synthetic_reference
class PublishedPacketRecipeTests(unittest.TestCase):
    def test_six_families_have_one_direct_hit_per_shot_and_sourced_extras(self):
        cases = [
            ('weapon:critical-pulse', .1,
             {'charged_shot_indices': [0], 'observed_charges': 1,
              'orb_duration_seconds': 1, 'first_tick_delay_seconds': 0,
              'include_endpoint': False, 'orb_tick_times': [0],
              'orb_tick_target': 'dummy', 'orb_tick_distance_meters': 2},
             {'psi': 100}, {}, 'dated_release', 1, 75),
            ('weapon:r500-hammerhead-shark', .1,
             {'power_surge_flags': [True], 'nearby_affected_targets': ['second']},
             {'psi': 100}, {'damage_class': 'status'}, 'dated_release', 1, 80),
            ('weapon:kvd-boom-boom', .1, {'explosion_targets': ['dummy']},
             {'psi': 100}, {'damage_class': 'status'}, 'preview_simulation', 1, 300),
            ('weapon:acs12-pyroclasm-starter', .1,
             {'charged_shot_indices': [0], 'observed_charged_rounds': 1,
              'resolved_damage_units': ['dummy', 'dummy']},
             {'attack': 100}, {}, 'preview_simulation', 1, 190),
            ('weapon:sks-pathfinder', .1,
             {'charged_shot_indices': [0], 'observed_charges': 1,
              'charge_cost': 1, 'pierced_targets': ['dummy', 'second']},
             {'attack': 100}, {}, 'preview_simulation', 1, 220),
            ('weapon:pdw90-holographic-resonance', .69,
             {'pulse_targets': ['dummy'], 'counter_overflow': 'subtract'},
             {'attack': 100}, {'element': 'none'}, 'preview_simulation', 11, 800),
        ]
        for weapon, duration, recipe, bases, hypothesis, evidence, shots, extra in cases:
            with self.subTest(weapon=weapon):
                before = copy.deepcopy(recipe)
                result, _, _ = run(weapon, duration, recipe, bases=bases,
                                   hypothesis=hypothesis, evidence=evidence)
                self.assertEqual(len(result['shot_times']), shots)
                self.assertEqual(result['source_proc']['shot_count'], shots)
                self.assertEqual(result['source_proc']['damage'], extra)
                self.assertEqual(result['source_timeline']['final_ammo']['reserve'], 0)
                self.assertEqual(recipe, before)
                self.assertFalse(result['game_winner_established'])
                if weapon == 'weapon:r500-hammerhead-shark':
                    self.assertEqual(result['status'], 'partial_timed_total')
                    self.assertTrue(any('main_target_150_percent' in gap
                                        for gap in result['unresolved']))
                else:
                    self.assertEqual(result['status'], 'conditional_modeled_total')

    def test_missing_charge_and_counter_coverage_do_not_become_zero(self):
        weapon = 'weapon:sks-pathfinder'
        recipe = {'charged_shot_indices': [0], 'observed_charges': 0,
                  'charge_cost': 1, 'pierced_targets': ['dummy']}
        with self.assertRaisesRegex(ValueError, 'charge balance'):
            run(weapon, .1, recipe, bases={'attack': 100},
                evidence='preview_simulation')
        weapon = 'weapon:pdw90-holographic-resonance'
        with self.assertRaisesRegex(ValueError, 'pulse target'):
            run(weapon, .69, {'counter_overflow': 'subtract'},
                bases={'attack': 100}, evidence='preview_simulation')

    def test_preview_gate_and_unknown_class_keep_timed_total_conditional(self):
        weapon = 'weapon:kvd-boom-boom'
        recipe = {'explosion_targets': ['dummy']}
        with self.assertRaisesRegex(ValueError, 'preview'):
            run(weapon, .1, recipe, bases={'psi': 100})
        partial, _, _ = run(weapon, .1, recipe, bases={'psi': 100},
                            evidence='preview_simulation')
        self.assertEqual(partial['status'], 'partial_timed_total')
        self.assertIsNone(partial['modeled_total_damage'])
        self.assertEqual(partial['source_proc']['damage'], 0)

    def test_finite_reserve_and_repeat_are_deterministic(self):
        weapon = 'weapon:kvd-boom-boom'
        recipe = {'explosion_targets': ['dummy']}
        first, build, controls = run(weapon, .35, recipe, bases={'psi': 100},
                                     hypothesis={'damage_class': 'status'},
                                     evidence='preview_simulation', reserve=0)
        second = published_timed_combat.evaluate(build, {'duration_seconds': .35,
                                                          'source_timeline': controls})
        self.assertEqual(len(first['shot_times']), 3)
        self.assertEqual(first['source_proc']['damage'], 300)  # 2 s cooldown
        self.assertEqual(first['known_damage_subtotal'], second['known_damage_subtotal'])
        self.assertEqual(len(first['source_timeline']['source_packets']), 1)

    def test_holographic_counter_survives_real_magazine_reload_and_finite_reserve(self):
        weapon = 'weapon:pdw90-holographic-resonance'
        controls = {'pulse_targets': ['dummy'], 'counter_overflow': 'subtract'}
        before, _, _ = run(weapon, 5.5, controls, bases={'attack': 100},
                           hypothesis={'element': 'none'},
                           evidence='preview_simulation', reserve=1)
        after, _, _ = run(weapon, 5.6, controls, bases={'attack': 100},
                          hypothesis={'element': 'none'},
                          evidence='preview_simulation', reserve=1)
        self.assertEqual(len(before['shot_times']), 50)
        self.assertEqual(len(after['shot_times']), 51)
        self.assertEqual(before['source_proc']['damage'], 3200)
        self.assertEqual(after['source_proc']['damage'], 3200)  # 51st hit is below next 11-hit trigger
        self.assertEqual(after['source_timeline']['final_ammo'], {'magazine': 0, 'reserve': 0})
        reloads = [row for row in after['source_timeline']['events'] if row['kind'] == 'reload']
        self.assertEqual(len(reloads), 1)
        self.assertEqual(reloads[0]['loaded_rounds'], 1)
        self.assertEqual(reloads[0]['base_reload_seconds'], 2.2)

    def test_selected_weapon_changes_required_action_semantics(self):
        with self.assertRaisesRegex(ValueError, 'pulse target'):
            run('weapon:pdw90-holographic-resonance', .69,
                {'explosion_targets': ['dummy'], 'counter_overflow': 'subtract'},
                bases={'attack': 100}, evidence='preview_simulation')


if __name__ == '__main__':
    unittest.main()
