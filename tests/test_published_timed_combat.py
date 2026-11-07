from tests.explicit_reference_fixture import explicit_synthetic_reference
"""Hand-checkable published timed composition under named assumptions."""
import math
import unittest

import published_reference_model
import published_timed_combat
import structured_compare


@explicit_synthetic_reference
class PublishedTimedCombatTests(unittest.TestCase):
    def test_direct_body_crit_weakspot_and_time(self):
        build = published_reference_model.build({'weapon': {'catalog_id': 'weapon:kam'}})
        ordinary = published_timed_combat.evaluate(build, {'duration_seconds': 1})
        self.assertEqual(len(ordinary['shot_times']), 10)
        self.assertTrue(math.isclose(ordinary['known_damage_subtotal'], 315.58))
        self.assertEqual(ordinary['status'], 'conditional_modeled_total')
        branches = published_timed_combat.evaluate(build, {
            'duration_seconds': 1, 'crit_share': .2, 'weakspot_share': .1,
            'joint_share': .05, 'joint_model': 'additive'})
        self.assertTrue(math.isclose(branches['direct_expected']['total_damage'], 345.65))
        self.assertFalse(branches['game_winner_established'])

    def test_sourced_status_proc_uses_six_slot_psi_and_bastille_reload(self):
        build = published_reference_model.build({
            'weapon': {'catalog_id': 'weapon:critical-pulse'},
            'armor': [{'catalog_id': 'armor:bastille-' + slot, 'tier': 5, 'stars': 1}
                      for slot in ('helmet', 'mask', 'gloves', 'boots', 'pants', 'top')]})
        run = published_timed_combat.evaluate(build, {
            'duration_seconds': 1, 'scenario_mode': 'pve_non_raidzone',
            'proc': {'packet_id': 'weapon:critical-pulse/lightning_orb_tick',
                     'count': 2}})
        self.assertEqual(run['status'], 'partial_timed_total')
        self.assertEqual(run['source_proc']['basis_value'], 460)
        self.assertEqual(run['source_proc']['damage_class'], 'status')
        self.assertEqual(run['source_proc']['damage'], 897)
        self.assertTrue(math.isclose(run['timing']['reload_seconds'], 2.6/1.15))
        self.assertEqual(run['set_rules_applied'][0]['rule_id'],
                         'bastille_two_reload_efficiency')
        self.assertTrue(math.isclose(run['known_damage_subtotal'],
                                      run['direct_expected']['total_damage']+897))
        self.assertTrue(any('bastille_set: 1-piece' in gap for gap in run['unresolved']))
        self.assertIn('orb_lifetime_and_tick_count', run['source_uncertainties'])
        no_set = published_reference_model.build({'weapon': {'catalog_id': 'weapon:critical-pulse'}})
        complete = published_timed_combat.evaluate(no_set, {'duration_seconds': 1,
            'proc': {'packet_id': 'weapon:critical-pulse/lightning_orb_tick',
                     'count': 2, 'psi': 100}})
        self.assertEqual(complete['status'], 'conditional_modeled_total')
        self.assertEqual(complete['source_proc']['damage'], 195)

    def test_treacherous_two_piece_gate_and_unknown_three_piece(self):
        armor = [{'catalog_id': 'armor:treacherous-tides-' + slot, 'tier': 5, 'stars': 1}
                 for slot in ('shoes', 'gloves')]
        build = published_reference_model.build({'weapon': {'catalog_id': 'weapon:kam'},
                                                 'armor': armor})
        active = published_timed_combat.evaluate(build, {'duration_seconds': 1,
            'scenario_mode': 'pve_non_raidzone', 'hp_fraction': .6})
        inactive = published_timed_combat.evaluate(build, {'duration_seconds': 1,
            'scenario_mode': 'pve_non_raidzone', 'hp_fraction': .7})
        self.assertEqual(active['effective_pools_percent']['weapon'], 12)
        self.assertEqual(active['effective_pools_percent']['status'], 12)
        self.assertEqual(inactive['effective_pools_percent']['weapon'], 0)
        self.assertTrue(math.isclose(active['known_damage_subtotal'] /
                                      inactive['known_damage_subtotal'], 1.12))
        build3 = published_reference_model.build({'weapon': {'catalog_id': 'weapon:kam'},
            'armor': armor + [{'catalog_id': 'armor:treacherous-tides-helmet',
                               'tier': 5, 'stars': 1}]})
        uncertain = published_timed_combat.evaluate(build3, {'duration_seconds': 1,
            'scenario_mode': 'pve_non_raidzone', 'hp_fraction': .6})
        self.assertEqual(uncertain['status'], 'partial_timed_total')
        self.assertIsNone(uncertain['modeled_total_damage'])
        self.assertTrue(any('treacherous_tides_three' in gap for gap in uncertain['unresolved']))

    def test_unknown_packet_class_or_unmodeled_mod_line_withholds_total(self):
        build = published_reference_model.build({'weapon': {'catalog_id': 'weapon:mps7-outer-space'}})
        base = {'duration_seconds': 1, 'proc': {
            'packet_id': 'weapon:mps7-outer-space/celestial_lightning',
            'count': 1, 'psi': 100}}
        unknown = published_timed_combat.evaluate(build, base)
        self.assertEqual(unknown['status'], 'partial_timed_total')
        self.assertIsNone(unknown['modeled_total_damage'])
        self.assertTrue(any('damage class' in gap for gap in unknown['unresolved']))
        specified = published_timed_combat.evaluate(build, {
            **base, 'proc': {**base['proc'], 'damage_class': 'status'}})
        self.assertEqual(specified['source_proc']['basis'], 'psi')
        self.assertGreater(specified['known_damage_subtotal'], unknown['known_damage_subtotal'])
        flame = published_reference_model.build({'weapon': {'catalog_id': 'weapon:kam'},
            'mods': [{'catalog_id': 'mod:weapon_mod:flame-resonance-general', 'level': 8}]})
        partial = published_timed_combat.evaluate(flame, {'duration_seconds': 1})
        self.assertEqual(partial['status'], 'partial_timed_total')
        self.assertIsNone(partial['conditional_damage_per_second'])
        self.assertTrue(any('Reload Speed' in gap for gap in partial['unresolved']))

    def test_typed_main_stat_once_and_structured_timed_comparison(self):
        build = published_reference_model.build({'weapon': {'catalog_id': 'weapon:kam'}})
        output = {'item_name': 'Synthetic exact stat', 'status': 'observed_typed_output',
                  'evidence_class': 'test fixture', 'outputs': [{
                      'type': 'stat_pool_delta', 'stat': 'weapon_damage_percent',
                      'percentage_points': 10}]}
        run = published_timed_combat.evaluate(build, {'duration_seconds': 1},
                                             typed_main_effects=[output])
        self.assertEqual(run['effective_pools_percent']['weapon'], 10)
        self.assertTrue(math.isclose(run['known_damage_subtotal'], 315.58*1.1))
        request = {'left': {'kind': 'catalog', 'catalog_id': 'weapon:kam'},
                   'right': {'kind': 'catalog', 'catalog_id': 'weapon:kam'},
                   'context': {'published_reference': {'enabled': True,
                       'left': {}, 'right': {},
                       'timed': {'duration_seconds': 1,
                                 'shared_target_confirmed': True,
                                 'left': {}, 'right': {}}}}}
        result = structured_compare.compare(request, [])['published_reference']
        self.assertEqual(result['timed_comparison']['status'], 'conditional_model_comparable')
        self.assertEqual(result['timed_comparison']['right_over_left_damage_per_second'], 1)
        self.assertFalse(result['timed_comparison']['game_winner_established'])

    def test_guided_source_counter_uses_published_shots_and_one_extra_packet(self):
        build = published_reference_model.build({
            'weapon': {'catalog_id': 'weapon:mps7-outer-space'}})
        controls = {'reserve_bullets': 0, 'target_id': 'dummy',
                    'roll_sequence': [.99] * 12,
                    'condition_sequences': {'target_affected_by_power_surge': [True] * 12},
                    'damage_model': {'basis_values': {'psi': 80},
                                     'packet_models': {
                                         'celestial_lightning': {'damage_class': 'status'}}}}
        run = published_timed_combat.evaluate(build, {
            'duration_seconds': .8, 'source_timeline': controls})
        self.assertEqual(run['status'], 'conditional_modeled_total')
        self.assertEqual(len(run['shot_times']), 12)
        self.assertEqual(run['source_proc']['damage'], 400)
        self.assertEqual(len(run['source_timeline']['source_packets']), 1)
        self.assertAlmostEqual(run['known_damage_subtotal'], 1948.288)
        self.assertEqual(run['source_timeline']['final_ammo'], {'magazine': 23, 'reserve': 0})
        self.assertFalse(run['game_winner_established'])
        with self.assertRaisesRegex(ValueError, 'each of 12 shots'):
            published_timed_combat.evaluate(build, {'duration_seconds': .8,
                'source_timeline': {**controls, 'roll_sequence': [.99] * 11}})
        with self.assertRaisesRegex(ValueError, 'Chance rolls'):
            published_timed_combat.evaluate(build, {'duration_seconds': .8,
                'source_timeline': {**controls, 'roll_sequence': [True] * 12}})
        with self.assertRaisesRegex(ValueError, 'either an automatic'):
            published_timed_combat.evaluate(build, {'duration_seconds': .8,
                'source_timeline': controls, 'proc': {'packet_id': 'none', 'count': 0}})

    def test_guided_periodic_preview_ticks_and_missing_effect_packet(self):
        build = published_reference_model.build({
            'weapon': {'catalog_id': 'weapon:kam-crank'}})
        controls = {'reserve_bullets': 0, 'target_id': 'dummy',
                    'evidence_mode': 'preview_simulation',
                    'damage_model': {'basis_values': {'psi': 50},
                        'packet_models': {'burn': {'basis': 'psi', 'damage_class': 'status',
                            'element': 'blaze', 'coefficient_percent': 20,
                            'periodic': {'duration_seconds': 3, 'interval_seconds': 1,
                                         'start_delay_seconds': 0,
                                         'refresh_model': 'independent'}}}}}
        run = published_timed_combat.evaluate(build, {
            'duration_seconds': 4, 'source_timeline': controls})
        self.assertEqual(run['status'], 'conditional_modeled_total')
        self.assertEqual(len(run['shot_times']), 40)
        self.assertEqual(run['source_proc']['damage'], 110)
        self.assertEqual(run['source_timeline']['final_ammo'], {'magazine': 0, 'reserve': 0})
        incomplete = published_timed_combat.evaluate(build, {
            'duration_seconds': 4, 'source_timeline': {
                **controls, 'damage_model': {'basis_values': {'psi': 50}}}})
        self.assertEqual(incomplete['status'], 'partial_timed_total')
        self.assertIsNone(incomplete['modeled_total_damage'])
        self.assertGreater(incomplete['known_damage_subtotal'], 0)
        self.assertTrue(incomplete['unresolved'])

    def test_guided_gilded_gauntlets_unlocks_only_explicit_burn_crits(self):
        base = published_reference_model.build({'weapon': {'catalog_id': 'weapon:kam-crank'}})
        gilded = published_reference_model.build({
            'weapon': {'catalog_id': 'weapon:kam-crank'},
            'armor': [{'catalog_id': 'armor:gilded-gauntlets', 'tier': 5, 'stars': 1}]})
        controls = {'reserve_bullets': 0, 'target_id': 'dummy',
            'evidence_mode': 'preview_simulation',
            'damage_model': {'basis_values': {'psi': 50},
                'packet_models': {'burn': {'basis': 'psi',
                    'damage_class': 'status', 'element': 'blaze',
                    'keyword': 'burn', 'coefficient_percent': 20,
                    'crit': True,
                    'periodic': {'duration_seconds': 3, 'interval_seconds': 1,
                        'start_delay_seconds': 0, 'refresh_model': 'independent'}}}}}
        chosen = published_timed_combat.evaluate(gilded, {
            'duration_seconds': 4, 'scenario_mode': 'pve_non_raidzone',
            'source_timeline': controls})
        packets = [row for row in chosen['source_timeline']['source_packets']
                   if row['event'] == 'burn_tick']
        self.assertEqual(len(packets), 11)
        self.assertEqual(chosen['status'], 'conditional_modeled_total')
        self.assertGreater(chosen['source_proc']['damage'], 110)
        without = published_timed_combat.evaluate(base, {
            'duration_seconds': 4, 'scenario_mode': 'pve_non_raidzone',
            'source_timeline': controls})
        self.assertIsNone(without['modeled_total_damage'])
        self.assertTrue(any('crit' in gap.lower() for gap in without['unresolved']))

    def test_guided_reload_blast_consumes_finite_ammo_and_requires_targets(self):
        build = published_reference_model.build({
            'weapon': {'catalog_id': 'weapon:g17-hazardous-object'}})
        controls = {'reserve_bullets': 0, 'target_id': 'dummy',
                    'reload_after_shots': 1, 'roll_sequence': [.99],
                    'damage_model': {'basis_values': {'psi': 100},
                        'packet_models': {'thrown_reload_blast': {
                            'damage_class': 'weapon', 'target_count': 2}}}}
        run = published_timed_combat.evaluate(build, {
            'duration_seconds': 3, 'source_timeline': controls})
        self.assertEqual(run['status'], 'conditional_modeled_total')
        self.assertEqual(run['source_proc']['damage'], 532)
        self.assertAlmostEqual(run['known_damage_subtotal'], 767.152)
        self.assertEqual(run['source_timeline']['final_ammo'], {'magazine': 0, 'reserve': 0})
        self.assertEqual(run['source_timeline']['events'][1]['loaded_rounds'], 0)
        incomplete = published_timed_combat.evaluate(build, {
            'duration_seconds': 3, 'source_timeline': {
                **controls, 'damage_model': {'basis_values': {'psi': 100},
                    'packet_models': {'thrown_reload_blast': {'damage_class': 'weapon'}}}}})
        self.assertEqual(incomplete['status'], 'partial_timed_total')
        self.assertIsNone(incomplete['modeled_total_damage'])
        self.assertTrue(any('target_count' in gap for gap in incomplete['unresolved']))

    def test_selected_mod_pool_and_set_reload_change_sourced_timeline_once(self):
        controls = {'reserve_bullets': 0, 'target_id': 'dummy',
                    'roll_sequence': [.99] * 12,
                    'condition_sequences': {'target_affected_by_power_surge': [True] * 12},
                    'damage_model': {'basis_values': {'psi': 80},
                        'packet_models': {'celestial_lightning': {'damage_class': 'status'}}}}
        plain = published_reference_model.build({
            'weapon': {'catalog_id': 'weapon:mps7-outer-space'}})
        modded = published_reference_model.build({
            'weapon': {'catalog_id': 'weapon:mps7-outer-space'},
            'mods': [{'catalog_id': 'mod:gloves_mod:status-enhancement-deviant-energy',
                      'level': 17}]})
        before = published_timed_combat.evaluate(
            plain, {'duration_seconds': .8, 'source_timeline': controls})
        after = published_timed_combat.evaluate(
            modded, {'duration_seconds': .8, 'source_timeline': controls})
        self.assertEqual(before['source_proc']['damage'], 400)
        self.assertAlmostEqual(after['source_proc']['damage'], 457.92)
        self.assertEqual(after['status'], 'partial_timed_total')
        self.assertTrue(any('Damage against enemies' in gap for gap in after['unresolved']))
        armor = [{'catalog_id': 'armor:bastille-' + slot, 'tier': 5, 'stars': 1}
                 for slot in ('helmet', 'gloves')]
        with_set = published_reference_model.build({
            'weapon': {'catalog_id': 'weapon:mps7-outer-space'},
            'armor': armor})
        long_control = {**controls, 'reserve_bullets': 5,
                        'roll_sequence': [.99] * 37,
                        'condition_sequences': {'target_affected_by_power_surge': [True] * 37}}
        without_set = published_timed_combat.evaluate(
            plain, {'duration_seconds': 5.2, 'scenario_mode': 'pve_non_raidzone',
                    'source_timeline': {**long_control, 'roll_sequence': [.99] * 35,
                        'condition_sequences': {'target_affected_by_power_surge': [True] * 35}}})
        set_run = published_timed_combat.evaluate(
            with_set, {'duration_seconds': 5.2, 'scenario_mode': 'pve_non_raidzone',
                       'source_timeline': long_control})
        self.assertEqual(len(without_set['shot_times']), 35)
        self.assertEqual(len(set_run['shot_times']), 37)
        self.assertAlmostEqual(set_run['timing']['reload_seconds'], 3 / 1.15)
        self.assertAlmostEqual(set_run['source_timeline']['events'][35]['base_reload_seconds'], 3)
        self.assertEqual(set_run['source_proc']['damage'], 1200)
        self.assertEqual(set_run['status'], 'partial_timed_total')

    def test_guided_source_target_mismatch_blocks_conditional_comparison(self):
        controls = {'reserve_bullets': 0, 'target_id': 'dummy-A',
                    'roll_sequence': [.99] * 12,
                    'condition_sequences': {'target_affected_by_power_surge': [True] * 12},
                    'damage_model': {'basis_values': {'psi': 80},
                        'packet_models': {'celestial_lightning': {'damage_class': 'status'}}}}
        request = {'left': {'kind': 'catalog', 'catalog_id': 'weapon:mps7-outer-space'},
                   'right': {'kind': 'catalog', 'catalog_id': 'weapon:mps7-outer-space'},
                   'context': {'published_reference': {'enabled': True,
                       'left': {}, 'right': {}, 'timed': {'duration_seconds': .8,
                           'shared_target_confirmed': True,
                           'left': {'source_timeline': controls},
                           'right': {'source_timeline': {**controls,
                                                        'target_id': 'dummy-B'}}}}}}
        result = structured_compare.compare(request, [])['published_reference']
        self.assertEqual(result['timed_comparison']['status'], 'partial_or_unmatched')
        self.assertFalse(result['timed_comparison']['source_target_identity_matched'])
        self.assertFalse(result['timed_comparison']['game_winner_established'])

    def test_complete_suffix_lines_do_not_hide_unmodeled_main_mod(self):
        identity = 'mod:gloves_mod:elemental-overload-deviant-energy'
        build = published_reference_model.build({
            'weapon': {'catalog_id': 'weapon:kam'},
            'mods': [{'catalog_id': identity, 'level': 17}]})
        self.assertTrue(all(row['applied_pool'] is not None
                            for row in build['selected_mod_rows']))
        missing = published_timed_combat.evaluate(build, {'duration_seconds': 1})
        self.assertEqual(missing['status'], 'partial_timed_total')
        self.assertIsNone(missing['modeled_total_damage'])
        self.assertTrue(any('main mod effect is not connected' in row
                            for row in missing['unresolved']))
        # A source-checked static operator can close this gate. The fixture is
        # deliberately synthetic; it does not assert this item's current value.
        typed = {'catalog_id': identity, 'item_name': 'Fixture', 'level': 17,
                 'status': 'observed_typed_output', 'outputs': [{
                     'type': 'stat_pool_delta', 'stat': 'status_damage_percent',
                     'percentage_points': 10}]}
        modeled = published_timed_combat.evaluate(
            build, {'duration_seconds': 1}, typed_main_effects=[typed])
        self.assertEqual(modeled['status'], 'conditional_modeled_total')
        self.assertEqual(modeled['effective_pools_percent']['status'],
                         missing['effective_pools_percent']['status'] + 10)


if __name__ == '__main__':
    unittest.main()
