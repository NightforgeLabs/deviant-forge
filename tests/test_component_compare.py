import copy
import json
import math
import unittest
from pathlib import Path

import component_compare


CASE = json.loads((Path(__file__).resolve().parents[1] / 'examples/helmet_lunar_reported.json').read_text())


class ComponentCompareTests(unittest.TestCase):
    def test_shared_unknown_condition_cancels_in_identical_builds_and_timing(self):
        same = {'name': 'same', 'main_effect': 'identical', 'attributes': [
            {'name': 'Weapon DMG', 'value_percent': 10, 'condition': 'low HP', 'source': 'card'},
            {'name': 'Fire Rate', 'value_percent': 10, 'condition': 'low HP', 'source': 'card'}]}
        result = component_compare.compare(same, copy.deepcopy(same),
                                           {'timing': {'rpm': 600, 'magazine': 10, 'reload_seconds': 2}})
        for branch in result['component_ratios'].values():
            self.assertAlmostEqual(branch['min'], 1)
            self.assertAlmostEqual(branch['max'], 1)
        self.assertEqual(result['firing_cycle']['throughput_ratio_floor_range'], [1, 1])

    def test_reported_helmet_rows_keep_core_and_defense(self):
        original = copy.deepcopy(CASE)
        result = component_compare.compare(CASE['left'], CASE['right'], CASE['context'], CASE['runs'])
        self.assertEqual(CASE, original)
        self.assertTrue(result['main_effect_same'])
        self.assertIn({'name': 'Damage from monsters received', 'value_percent': 4.8,
                       'condition': 'low HP', 'direction': 'reduction'}, result['shared_rows'])
        self.assertAlmostEqual(result['component_ratios']['normal']['min'], 1 / 1.072)
        self.assertAlmostEqual(result['component_ratios']['normal']['max'], 1)
        self.assertAlmostEqual(result['component_ratios']['crit']['min'], (1 / 1.072) * (1 / 1.18))
        self.assertAlmostEqual(result['component_ratios']['status']['min'], 1)
        self.assertAlmostEqual(result['component_ratios']['status']['max'], 1.096 * 1.272 / 1.20)
        self.assertFalse(result['game_winner_established'])
        self.assertEqual(result['empirical']['left']['total_damage'], 895534)
        self.assertEqual(result['empirical']['right']['total_damage'], 895757)
        self.assertEqual(result['empirical']['damage_delta_right_minus_left'], 223)
        self.assertIsNone(result['empirical']['left']['damage_per_second'])
        self.assertTrue(any('Buffs' in warning for warning in result['empirical']['warnings']))
        self.assertFalse(result['empirical']['winner_established'])

    def test_unknown_and_inactive_conditions(self):
        unknown = component_compare.compare(CASE['left'], CASE['right'])
        self.assertLess(unknown['component_ratios']['normal']['min'], 1)
        self.assertEqual(unknown['component_ratios']['normal']['max'], 1)
        self.assertEqual(unknown['component_ratios']['status']['min'], 1)
        self.assertGreater(unknown['component_ratios']['status']['max'], 1)
        for hp in (29, 50, 90):
            unresolved = component_compare.compare(CASE['left'], CASE['right'], {'hp_percent': hp})
            self.assertAlmostEqual(unresolved['component_ratios']['normal']['min'], 1 / 1.072)
            self.assertAlmostEqual(unresolved['component_ratios']['normal']['max'], 1)
        stated_max = component_compare.compare(CASE['left'], CASE['right'],
                                               {**CASE['context'], 'condition_uptime': {'low hp': 1}})
        self.assertAlmostEqual(stated_max['component_ratios']['status']['min'], 1)
        self.assertAlmostEqual(stated_max['component_ratios']['status']['max'], 1.096 * 1.272 / 1.20)
        full_strength = component_compare.compare(CASE['left'], CASE['right'],
            {**CASE['context'], 'condition_uptime': {'low hp': 1}, 'condition_strength': {'low hp': 1}})
        self.assertAlmostEqual(full_strength['component_ratios']['status']['min'], 1.096 * 1.272 / 1.20)
        inactive = component_compare.compare(CASE['left'], CASE['right'],
                                             {'condition_uptime': {'low hp': 0}})
        self.assertAlmostEqual(inactive['component_ratios']['normal']['min'], 1)

    def test_generic_conditional_bonus_keeps_passive_base(self):
        item = {'main_effect': 'same', 'attributes': [
            {'name': 'Weapon DMG', 'value_percent': 2.4, 'conditional_bonus_percent': 1.2,
             'condition': 'aerial hit', 'source': 'reviewed card'}]}
        empty = {'main_effect': 'same', 'attributes': []}
        inactive = component_compare.compare(empty, item, {'condition_uptime': {'aerial hit': 0}})
        active = component_compare.compare(empty, item, {'condition_uptime': {'aerial hit': 1}})
        self.assertAlmostEqual(inactive['component_ratios']['normal']['min'], 1.024)
        self.assertAlmostEqual(active['component_ratios']['normal']['min'], 1.036)
        self.assertEqual(active['right']['trace'][0]['source'], 'reviewed card')

    def test_unverified_row_is_calculated_only_as_labeled_input_assumption(self):
        result = component_compare.compare({'attributes': []},
            {'attributes': [{'name': 'Weapon DMG', 'value_percent': 100,
                             'source': 'guess', 'source_status': 'unverified'}]})
        self.assertEqual(result['component_ratios']['normal']['min'], 2)
        self.assertTrue(any('unverified' in note and 'input assumption' in note for note in result['missing']))
        self.assertFalse(result['game_winner_established'])

    def test_component_mix_and_firing_cycle_are_conditional(self):
        left = {'main_effect': 'same', 'attributes': []}
        right = {'main_effect': 'same', 'attributes': [
            {'name': 'Magazine Capacity', 'value_percent': 20},
            {'name': 'Reload Efficiency', 'value_percent': 25},
            {'name': 'Status DMG', 'value_percent': 10}]}
        context = {'timing': {'rpm': 600, 'magazine': 10, 'reload_seconds': 2},
                   'old_damage_shares': {'normal': .6, 'status': .4}}
        result = component_compare.compare(left, right, context)
        self.assertAlmostEqual(result['conditional_weighted_ratio']['min'], 1.04)
        self.assertEqual(result['firing_cycle']['right']['magazine_floor'], 12)
        self.assertGreater(result['firing_cycle']['throughput_ratio_floor_range'][0], 1)
        self.assertFalse(result['game_winner_established'])

    def test_multiple_equipment_pieces_and_proc_specific_pool(self):
        left = {'name': 'Build A', 'items': [
            {'name': 'Weapon mod', 'main_effect': 'identical effect', 'attributes': [
                {'name': 'Power Surge DMG', 'value_percent': 5, 'source': 'card A'}]},
            {'name': 'Helmet', 'attributes': [
                {'name': 'Weapon DMG', 'value_percent': 2, 'source': 'card B'}]}]}
        right = {'name': 'Build B', 'items': [
            {'name': 'Helmet', 'attributes': [
                {'name': 'Weapon DMG', 'value_percent': 4, 'source': 'card C'}]},
            {'name': 'Weapon mod', 'main_effect': 'identical effect', 'attributes': [
                {'name': 'Power Surge DMG', 'value_percent': 10, 'source': 'card D'}]}]}
        result = component_compare.compare(left, right)
        self.assertTrue(result['main_effect_same'])
        self.assertAlmostEqual(result['component_ratios']['normal']['min'], 1.04 / 1.02)
        self.assertAlmostEqual(result['component_ratios']['power_surge']['min'], 1.10 / 1.05)
        self.assertAlmostEqual(result['component_ratios']['shock']['min'], 1)
        self.assertEqual(result['right']['trace'][0]['item'], 'Helmet')

    def test_saved_plan_path_audits_all_selected_items_without_fake_rank(self):
        import planned_advisor
        left = {'helmet': {'catalog_id': 'armor:agent-helmet',
                           'mod_id': 'mod:helmet_mod:deviation-expert-lunar', 'mod_level': 10}}
        right = {'helmet': {'catalog_id': 'armor:agent-helmet',
                            'mod_id': 'mod:helmet_mod:deviation-expert-lunar-deviant-energy', 'mod_level': 10}}
        result = planned_advisor.compare(left, right)
        analysis = result['component_analysis']
        self.assertFalse(analysis['game_winner_established'])
        self.assertTrue(analysis['main_effect_same'])
        self.assertTrue(any('Agent Helmet: no reviewed numeric rows' in reason for reason in analysis['missing']))
        self.assertEqual(left['helmet']['mod_id'], 'mod:helmet_mod:deviation-expert-lunar')

    def test_exact_catalog_id_and_level_autoloads_reviewed_rows_without_ownership(self):
        empty = {'attributes': []}
        selected = {'catalog_id': 'mod:chest_mod:quick-comeback-precision', 'level': 13}
        snapshot = copy.deepcopy(selected)
        result = component_compare.compare(empty, selected)
        self.assertEqual(selected, snapshot)
        self.assertAlmostEqual(result['component_ratios']['normal']['min'], 1.048 * 1.03)
        self.assertTrue(result['right']['trace'][0]['source'].startswith('media/'))
        self.assertEqual(result['right']['trace'][0]['source_status'], 'source-checked current Field Guide frame')
        self.assertEqual(len(result['right']['trace'][0]['source_sha256']), 64)
        self.assertFalse(result['game_winner_established'])
        ambiguous = component_compare.compare(empty,
            {'catalog_id': 'mod:chest_mod:quick-comeback-survival', 'level': 8})
        self.assertTrue(any('numeric profile partial' in note for note in ambiguous['missing']))
        self.assertTrue(any('Damage from monsters received: component or operator not modeled' in note
                            for note in ambiguous['missing']))

    def test_exact_sourced_main_effect_rules_and_shiny_gate(self):
        import catalog
        empty = {'name': 'baseline', 'attributes': []}
        def selected(identity, level):
            return {'name': identity, 'catalog_id': identity, 'level': level,
                    'main_effect': catalog.resolve(identity, level)['primary_effect'], 'attributes': []}
        distance = selected('mod:pants_mod:distant-strike-survival', 10)
        near = component_compare.compare(empty, distance, {'distance_meters': 10})
        far = component_compare.compare(empty, distance, {'distance_meters': 25})
        self.assertEqual(near['component_ratios']['weakspot']['min'], 1)
        self.assertAlmostEqual(far['component_ratios']['weakspot']['min'], 1.2)
        self.assertAlmostEqual(far['component_ratios']['weakspot']['max'], 1.4)
        aao = selected('mod:boots_mod:against-all-odds-precision', 7)
        no_cost = component_compare.compare(empty, aao, {'hp_consumed_percent': 0})
        unknown = component_compare.compare(empty, aao)
        two_stacks = component_compare.compare(empty, aao,
                                               {'effect_stacks': {aao['catalog_id']: 2}})
        self.assertAlmostEqual(no_cost['component_ratios']['normal']['min'], 1.1)
        self.assertAlmostEqual(unknown['component_ratios']['normal']['max'], 1.25)
        self.assertAlmostEqual(two_stacks['component_ratios']['status']['min'], 1.2)
        striving = selected('mod:boots_mod:power-of-striving-downstar-deviant-energy', 9)
        result = component_compare.compare(empty, striving)
        self.assertAlmostEqual(result['component_ratios']['normal']['min'], 1.1)
        self.assertTrue(any('conditional main-effect' in line for line in result['missing']))
        shiny_only = selected('mod:pants_mod:elemental-resonance-aero', 17)
        gated = component_compare.compare(empty, shiny_only)
        self.assertEqual(gated['component_ratios']['elemental_nonstatus']['max'], 1)
        self.assertTrue(any('not verified' in line for line in gated['missing']))

    def test_official_two_piece_set_condition_and_unknown_threshold(self):
        empty = {'name': 'no set', 'attributes': []}
        tides = {'name': 'set build', 'sets': [{'name': 'Treacherous Tides', 'count': 2}], 'attributes': []}
        active = component_compare.compare(empty, tides, {'scenario': 'PvE non-RaidZone', 'hp_percent': 50})
        inactive = component_compare.compare(empty, tides, {'scenario': 'PvE non-RaidZone', 'hp_percent': 80})
        unknown = component_compare.compare(empty, tides)
        self.assertAlmostEqual(active['component_ratios']['normal']['min'], 1.12)
        self.assertAlmostEqual(active['component_ratios']['status']['min'], 1.12)
        self.assertEqual(inactive['component_ratios']['normal']['min'], 1)
        self.assertEqual(unknown['component_ratios']['normal']['min'], 1)
        self.assertAlmostEqual(unknown['component_ratios']['normal']['max'], 1.12)
        three = component_compare.compare(empty, {**tides, 'sets': [{'name': 'Treacherous Tides', 'count': 3}]},
                                          {'scenario': 'PvE non-RaidZone', 'hp_percent': 50})
        self.assertTrue(any('stacking' in reason for reason in three['missing']))
        self.assertEqual([row['applied_range_percent'] for row in three['right']['trace']
                          if row.get('rule_id') == 'treacherous_tides_three'], [[28, 28], [28, 28]])
        self.assertFalse(three['game_winner_established'])
        import planned_advisor
        saved = planned_advisor.compare({}, {'helmet': {'catalog_id': 'armor:treacherous-tides-helmet'},
                                             'top': {'catalog_id': 'armor:treacherous-tides-top'}},
                                        {'scenario': 'PvE non-RaidZone', 'hp_percent': 50})
        self.assertAlmostEqual(saved['component_analysis']['component_ratios']['normal']['min'], 1.12)
        self.assertFalse(saved['winner_established'])

    def test_verified_shiny_rules_are_gated_and_parameterized(self):
        empty = {'attributes': []}
        ferocious = {'catalog_id': 'mod:boots_mod:ferocious-charge-downstar', 'level': 17,
                     'name': 'Ferocious Charge', 'shiny': True, 'attributes': []}
        condition = 'kill within 10m in previous 8s'
        unknown = component_compare.compare(empty, ferocious)
        active = component_compare.compare(empty, ferocious,
                                           {'condition_uptime': {condition: 1}})
        self.assertEqual(unknown['component_ratios']['normal']['min'], 1)
        self.assertAlmostEqual(unknown['component_ratios']['normal']['max'], 1.2)
        self.assertAlmostEqual(active['component_ratios']['status']['min'], 1.2)
        ordinary = component_compare.compare(empty, {**ferocious, 'shiny': False})
        self.assertEqual(ordinary['component_ratios']['normal']['max'], 1)
        resonance = {'catalog_id': 'mod:pants_mod:elemental-resonance-aero',
                     'level': 17, 'shiny': True, 'attributes': []}
        measured = component_compare.compare(empty, resonance,
                         {'prior_magazine_elemental_events': 30, 'seconds_since_reload': 5})
        self.assertAlmostEqual(measured['component_ratios']['elemental_nonstatus']['min'], 1.24)
        expired = component_compare.compare(empty, resonance,
                         {'prior_magazine_elemental_events': 30, 'seconds_since_reload': 15})
        self.assertEqual(expired['component_ratios']['elemental_nonstatus']['max'], 1)
        incomplete = component_compare.compare(empty, resonance,
                         {'prior_magazine_elemental_events': 2})
        self.assertEqual(incomplete['component_ratios']['elemental_nonstatus']['min'], 1)
        self.assertAlmostEqual(incomplete['component_ratios']['elemental_nonstatus']['max'], 1.02)
        with self.assertRaises(ValueError):
            component_compare.compare(empty, resonance,
                                      {'prior_magazine_elemental_events': 1.5})

    def test_official_wind_cap_bomber_rate_is_keyword_scoped(self):
        empty = {'attributes': []}
        cap = {'catalog_id': 'armor:wind-intepreter-cap', 'name': 'Wind Intepreter Cap',
               'attributes': []}
        active = component_compare.compare(empty, cap, {'scenario': 'PvE non-RaidZone'})
        unknown = component_compare.compare(empty, cap)
        raid = component_compare.compare(empty, cap, {'scenario': 'RaidZone'})
        self.assertAlmostEqual(active['component_ratios']['unstable_bomber']['min'], 1.25)
        self.assertEqual(active['component_ratios']['normal']['min'], 1)
        self.assertEqual(unknown['component_ratios']['unstable_bomber']['min'], 1)
        self.assertAlmostEqual(unknown['component_ratios']['unstable_bomber']['max'], 1.25)
        self.assertEqual(raid['component_ratios']['unstable_bomber']['max'], 1)
        self.assertFalse(active['game_winner_established'])

    def test_five_source_checked_exact_level_main_rules_are_parameterized(self):
        import catalog
        empty = {'attributes': []}
        def item(identity, level):
            return {'catalog_id': identity, 'level': level, 'attributes': []}
        static = 'mod:weapon_mod:static-shock-survival'
        shock = component_compare.compare(empty, item(static, 11))
        self.assertTrue(catalog.resolve(static, 11)['verified_main_effect']['source_sha256'])
        self.assertAlmostEqual(shock['component_ratios']['power_surge']['min'], 1.2)
        self.assertEqual(shock['component_ratios']['normal']['min'], 1)
        self.assertTrue(any('duration' in reason for reason in shock['missing']))
        unverified_level = component_compare.compare(empty, item(static, 12))
        self.assertEqual(unverified_level['component_ratios']['power_surge']['max'], 1)
        amplifier = 'mod:weapon_mod:surge-amplifier-survival'
        unknown = component_compare.compare(empty, item(amplifier, 10))
        two = component_compare.compare(empty, item(amplifier, 10),
                                        {'effect_stacks': {amplifier: 2}})
        self.assertEqual(unknown['component_ratios']['power_surge']['min'], 1)
        self.assertAlmostEqual(unknown['component_ratios']['power_surge']['max'], 1.2)
        self.assertAlmostEqual(two['component_ratios']['power_surge']['min'], 1.1)
        overflow = 'mod:helmet_mod:overflow-general'
        timing = {'rpm': 600, 'magazine': 10, 'reload_seconds': 2}
        active = component_compare.compare(empty, item(overflow, 8),
                    {'after_empty_reload': True, 'timing': timing})
        inactive = component_compare.compare(empty, item(overflow, 8),
                    {'after_empty_reload': False, 'timing': timing})
        self.assertGreater(active['firing_cycle']['throughput_ratio_floor_range'][0], 1)
        self.assertEqual(inactive['firing_cycle']['throughput_ratio_floor_range'], [1, 1])
        siphon = 'mod:pants_mod:bullet-siphon-aero-deviant-energy'
        zero = component_compare.compare(empty, item(siphon, 12),
                    {'bullets_consumed_in_magazine': 0})
        seven = component_compare.compare(empty, item(siphon, 12),
                    {'bullets_consumed_in_magazine': 7})
        capped = component_compare.compare(empty, item(siphon, 12),
                    {'bullets_consumed_in_magazine': 50})
        self.assertAlmostEqual(zero['component_ratios']['normal']['min'], 1.05)
        self.assertAlmostEqual(seven['component_ratios']['normal']['min'], 1.09)
        self.assertAlmostEqual(capped['component_ratios']['normal']['min'], 1.25)
        with self.assertRaises(ValueError):
            component_compare.compare(empty, item(siphon, 12),
                    {'bullets_consumed_in_magazine': 2.5})
        elemental = component_compare.compare(empty,
                    item('mod:gloves_mod:elemental-overload-resonance', 9))
        self.assertAlmostEqual(elemental['component_ratios']['elemental_nonstatus']['min'], 1.18)
        self.assertEqual(elemental['component_ratios']['normal']['min'], 1)
        self.assertFalse(elemental['game_winner_established'])

    def test_bad_inputs_and_unequal_runs_never_create_winner(self):
        with self.assertRaises(ValueError):
            component_compare.compare({}, {}, {'old_damage_shares': {'normal': .8}})
        with self.assertRaises(ValueError):
            component_compare.compare({}, {}, {'hp_percent': math.inf})
        with self.assertRaises(ValueError):
            component_compare.compare({}, {}, {'base_pools': []})
        with self.assertRaises(ValueError):
            component_compare.compare({}, {}, {'effect_stacks': []})
        with self.assertRaises(ValueError):
            component_compare.compare({}, {}, runs={'left': [{'damage': 100, 'rounds': 10.5}]})
        with self.assertRaises(ValueError):
            component_compare.compare({}, {}, {'timing': {'rpm': 600, 'magazine': 1, 'reload_seconds': 0},
                                                 'base_pools': {'magazine': -99}})
        result = component_compare.compare({}, {}, runs={'left': [{'damage': 100, 'rounds': 10}],
                                                          'right': [{'damage': 200, 'rounds': 11}]})
        self.assertTrue(any('Unequal' in warning for warning in result['empirical']['warnings']))
        self.assertFalse(result['empirical']['winner_established'])


if __name__ == '__main__':
    unittest.main()
