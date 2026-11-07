from tests.explicit_reference_fixture import explicit_synthetic_reference
"""Source-gated set rules in real published reference and saved-plan paths."""
import math
import unittest

import catalog
import published_reference_model
import published_set_thresholds
import published_timed_combat
import structured_compare


def build(*armor):
    return published_reference_model.build({
        'weapon': {'catalog_id': 'weapon:kam'},
        'armor': [{'catalog_id': identity} for identity in armor]})


def run(selected, **options):
    return published_timed_combat.evaluate(selected, {
        'duration_seconds': 1, 'scenario_mode': 'pve_non_raidzone',
        'set_evidence_mode': 'community_snapshot', **options})


@explicit_synthetic_reference
class SetThresholds(unittest.TestCase):
    def test_source_packet_and_catalog_denominators(self):
        catalog_sets = [row for row in catalog.ENTRIES.values() if row['kind'] == 'set']
        self.assertEqual((len(catalog_sets), sum(len(row['bonuses']) for row in catalog_sets)),
                         (20, 74))
        packet = published_set_thresholds.SOURCE
        self.assertEqual(sum(len(row['thresholds']) for row in packet['sets']), 79)
        self.assertEqual(len(packet['sets']), 21)
        counts = {row['id'].removeprefix('set:').replace('-', '_'): 4
                  for row in catalog_sets}
        _, applied, covered, gaps = published_set_thresholds.evaluate(
            counts, 'pve_non_raidzone', .8, 'community_snapshot',
            {'stamina_fraction': .95, 'current_load': 81,
             'spotted_by_enemies': False, 'ambient_temperature_c': 20,
             'bastille_state_active': True})
        self.assertEqual((len(covered), len(gaps)), (41, 0))
        self.assertEqual(len({row['rule_id'] for row in applied}), 40)
        self.assertEqual(sum(row['source_status'] == 'historical_official_release'
                             for row in applied), 2)

    def test_falcon_thresholds_crit_rate_and_damage_once(self):
        selected = build('armor:falcon-cap', 'armor:falcon-gloves')
        base = published_timed_combat.evaluate(selected, {
            'duration_seconds': 1, 'scenario_mode': 'pve_non_raidzone'})
        self.assertEqual(base['status'], 'partial_timed_total')
        active = run(selected)
        self.assertEqual(active['status'], 'conditional_modeled_total')
        self.assertEqual(active['effective_pools_percent']['crit'], 12)
        self.assertEqual(active['effective_pools_percent']['crit_rate'], 0)
        self.assertAlmostEqual(active['direct_expected']['total_damage'],
                               310 * (1 + .06 * .42))
        self.assertEqual(len({row['rule_id'] for row in active['set_rules_applied']}), 2)
        once = run(build('armor:falcon-cap'))
        self.assertEqual(once['effective_pools_percent']['crit'], 0)
        three = run(build('armor:falcon-cap', 'armor:falcon-gloves',
                          'armor:falcon-pants'),
                    set_condition_inputs={'stamina_fraction': .95})
        self.assertEqual(three['effective_pools_percent']['crit'], 32)
        self.assertEqual(three['effective_pools_percent']['crit_rate'], 5)
        self.assertAlmostEqual(three['direct_expected']['total_damage'],
                               310 * (1 + .11 * .62))

    def test_bastille_historical_gate_hp_and_current_reload(self):
        selected = build('armor:bastille-helmet', 'armor:bastille-gloves')
        current = published_timed_combat.evaluate(selected, {
            'duration_seconds': 1, 'scenario_mode': 'pve_non_raidzone',
            'hp_fraction': .8})
        self.assertEqual(len(current['set_rules_applied']), 1)
        self.assertEqual(current['status'], 'partial_timed_total')
        active = published_timed_combat.evaluate(selected, {
            'duration_seconds': 1, 'scenario_mode': 'pve_non_raidzone',
            'hp_fraction': .8, 'set_evidence_mode': 'historical_official'})
        self.assertEqual(active['status'], 'conditional_modeled_total')
        self.assertEqual(active['effective_pools_percent']['weapon'], 10)
        self.assertEqual(active['effective_pools_percent']['reload_efficiency'], 15)
        self.assertAlmostEqual(active['direct_expected']['total_damage'] /
                               current['direct_expected']['total_damage'], 1.1)
        inactive = published_timed_combat.evaluate(selected, {
            'duration_seconds': 1, 'scenario_mode': 'pve_non_raidzone',
            'hp_fraction': .7, 'set_evidence_mode': 'historical_official'})
        self.assertEqual(inactive['effective_pools_percent']['weapon'], 0)
        self.assertEqual(inactive['status'], 'conditional_modeled_total')
        three = build('armor:bastille-helmet', 'armor:bastille-gloves',
                      'armor:bastille-pants')
        historical = published_timed_combat.evaluate(three, {
            'duration_seconds': 1, 'scenario_mode': 'pve_non_raidzone',
            'hp_fraction': .8, 'set_evidence_mode': 'historical_official',
            'set_condition_inputs': {'bastille_state_active': True}})
        self.assertEqual(historical['effective_pools_percent']['weapon'], 50)

    def test_flat_utility_unit_is_not_reported_as_damage_percentage(self):
        selected = build('armor:rustic-hat', 'armor:rustic-gloves',
                         'armor:rustic-pants')
        result = run(selected)
        hp = next(row for row in result['set_rules_applied']
                  if row['stat'] == 'max_hp')
        self.assertEqual((hp['value'], hp['unit'], hp['percentage_points']),
                         (600, 'flat', None))
        self.assertIsNone(hp['pool'])
        self.assertEqual(result['effective_pools_percent']['weapon'], 0)

    def test_scout_condition_and_cross_set_no_duplicate(self):
        scout = build('armor:scout-hood', 'armor:scout-gloves',
                      'armor:scout-pants')
        unknown = run(scout)
        self.assertEqual(unknown['status'], 'partial_timed_total')
        self.assertTrue(any('not_spotted_by_enemies' in gap
                            for gap in unknown['unresolved']))
        hidden = run(scout, set_condition_inputs={'spotted_by_enemies': False})
        seen = run(scout, set_condition_inputs={'spotted_by_enemies': True})
        self.assertEqual((hidden['effective_pools_percent']['weapon'],
                          seen['effective_pools_percent']['weapon']), (28, 8))
        self.assertEqual(hidden['status'], 'conditional_modeled_total')
        mixed = run(build('armor:falcon-cap', 'armor:falcon-gloves',
                          'armor:renegade-pants', 'armor:renegade-shoes'),
                    weakspot_share=.2, joint_share=0)
        self.assertEqual(mixed['effective_pools_percent']['crit'], 12)
        self.assertEqual(mixed['effective_pools_percent']['weakspot'], 10)
        self.assertEqual(mixed['effective_pools_percent']['reload_efficiency'], 10)
        self.assertEqual(len({row['rule_id'] for row in mixed['set_rules_applied']}), 4)
        self.assertEqual(mixed['status'], 'conditional_modeled_total')
        with self.assertRaisesRegex(ValueError, 'Duplicate armor slot'):
            build('armor:falcon-cap', 'armor:renegade-hood')

    def test_current_treacherous_three_piece_endpoints_and_stack_hypothesis(self):
        selected = build('armor:treacherous-tides-helmet',
                         'armor:treacherous-tides-shoes',
                         'armor:treacherous-tides-gloves')
        full_hp = published_timed_combat.evaluate(selected, {
            'duration_seconds': 1, 'scenario_mode': 'pve_non_raidzone',
            'hp_fraction': 1})
        self.assertEqual(full_hp['status'], 'conditional_modeled_total')
        self.assertEqual(full_hp['effective_pools_percent']['weapon'], 8)
        middle = published_timed_combat.evaluate(selected, {
            'duration_seconds': 1, 'scenario_mode': 'pve_non_raidzone',
            'hp_fraction': .8})
        self.assertEqual(middle['status'], 'partial_timed_total')
        low_unknown = published_timed_combat.evaluate(selected, {
            'duration_seconds': 1, 'scenario_mode': 'pve_non_raidzone',
            'hp_fraction': .6})
        self.assertEqual(low_unknown['status'], 'partial_timed_total')
        low_assumed = published_timed_combat.evaluate(selected, {
            'duration_seconds': 1, 'scenario_mode': 'pve_non_raidzone',
            'hp_fraction': .6, 'set_stack_model': 'additive_named_pools'})
        self.assertEqual(low_assumed['effective_pools_percent']['weapon'], 40)
        self.assertEqual(low_assumed['status'], 'conditional_modeled_total')
        self.assertTrue(any('stacking hypothesis' in note
                            for note in low_assumed['assumptions']))

    def test_unsupported_thresholds_and_ambiguous_boundaries_stay_partial(self):
        lonewolf = run(build('armor:lonewolf-hat', 'armor:lonewolf-gloves',
                             'armor:lonewolf-pants'))
        self.assertEqual(lonewolf['status'], 'partial_timed_total')
        self.assertTrue(any('3-piece' in gap for gap in lonewolf['unresolved']))
        blackstone = build('armor:blackstone-hood', 'armor:blackstone-gloves',
                           'armor:blackstone-pants')
        boundary = run(blackstone,
                       set_condition_inputs={'ambient_temperature_c': 10})
        self.assertEqual(boundary['status'], 'partial_timed_total')
        self.assertTrue(any('ambient_temperature' in gap
                            for gap in boundary['unresolved']))
        with self.assertRaisesRegex(ValueError, 'set evidence'):
            run(build('armor:falcon-cap'), set_evidence_mode='all_verified')
        savior = run(build('armor:savior-helmet', 'armor:savior-pants',
                           'armor:savior-mask'), hp_fraction=.2)
        self.assertEqual(savior['status'], 'partial_timed_total')
        self.assertFalse(any(row.get('set_id') == 'savior_set'
                             for row in savior['set_rules_applied']))
        # The obsolete catalog's movement/load thresholds never replace the
        # newer official Treacherous Tides damage rules, even with opt-in.
        treacherous = run(build('armor:treacherous-tides-helmet',
                                'armor:treacherous-tides-shoes',
                                'armor:treacherous-tides-gloves'), hp_fraction=1)
        self.assertEqual(treacherous['effective_pools_percent']['weapon'], 8)
        self.assertFalse(any(row.get('source_status') == 'community_snapshot_candidate'
                             for row in treacherous['set_rules_applied']))

    def test_saved_plan_set_count_matches_direct_build_and_does_not_mutate(self):
        slots = {'primary': {'catalog_id': 'weapon:kam'},
                 'helmet': {'catalog_id': 'armor:falcon-cap'},
                 'gloves': {'catalog_id': 'armor:falcon-gloves'}}
        plans = [{'id': 'set-plan', 'name': 'Set plan', 'slots': slots}]
        request = {'left': {'kind': 'planned_build', 'planned_build_id': 'set-plan'},
                   'right': {'kind': 'planned_build', 'planned_build_id': 'set-plan'},
                   'context': {'published_reference': {'enabled': True,
                       'left': {}, 'right': {}, 'timed': {
                           'duration_seconds': 1, 'scenario_mode': 'pve_non_raidzone',
                           'shared_target_confirmed': True,
                           'left': {'set_evidence_mode': 'community_snapshot'},
                           'right': {'set_evidence_mode': 'community_snapshot'}}}}}
        result = structured_compare.compare(request, plans)['published_reference']
        left = result['timed_scenarios']['left']
        direct = run(build('armor:falcon-cap', 'armor:falcon-gloves'))
        self.assertTrue(math.isclose(left['known_damage_subtotal'],
                                     direct['known_damage_subtotal']))
        self.assertEqual(result['timed_comparison']['status'],
                         'conditional_model_comparable')
        self.assertEqual(slots['gloves']['catalog_id'], 'armor:falcon-gloves')


if __name__ == '__main__':
    unittest.main()
