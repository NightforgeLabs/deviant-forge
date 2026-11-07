import unittest

import combat_projection
import component_compare


class CombatProjectionTests(unittest.TestCase):
    def test_basis_and_damage_class_are_independent_and_joint_share_is_entered(self):
        result = combat_projection.components({
            'shots': 100, 'duration_seconds': 20,
            'direct': {'normal_damage_per_shot': 100, 'crit_bonus_percent': 50,
                       'weakspot_bonus_percent': 100, 'crit_share': .25,
                       'weakspot_share': .20, 'crit_weakspot_share': .05},
            'events': [
                {'name': 'Psi-basis weapon hit', 'basis': 'psi', 'damage_class': 'weapon',
                 'branch': 'normal', 'basis_value': 500, 'coefficient_percent': 120,
                 'count': 2},
                {'name': 'Attack-basis status tick', 'basis': 'attack', 'damage_class': 'status',
                 'branch': 'status', 'basis_value': 1000, 'coefficient_percent': 50,
                 'chance_per_shot': .1, 'ticks_per_event': 2}]})
        self.assertAlmostEqual(result['components']['normal'], 7200)
        self.assertAlmostEqual(result['components']['crit'], 3000)
        self.assertAlmostEqual(result['components']['weakspot'], 3000)
        self.assertAlmostEqual(result['components']['crit_weakspot'], 1250)
        self.assertAlmostEqual(result['components']['status'], 10000)
        self.assertAlmostEqual(result['total_damage'], 24450)
        self.assertAlmostEqual(result['damage_per_second'], 1222.5)
        self.assertEqual(result['event_trace'][0]['basis'], 'psi')
        self.assertEqual(result['event_trace'][0]['damage_class'], 'weapon')

    def test_reload_transform_and_invalid_probability(self):
        self.assertAlmostEqual(combat_projection.reload_seconds(2, 25), 1.6)
        self.assertAlmostEqual(combat_projection.relative_trigger_chance(.12, .5), .18)
        self.assertEqual(combat_projection.relative_trigger_chance(.8, .5), 1)
        self.assertEqual(combat_projection.capped_affine_coefficient(50, 5, 20, 100), 100)
        self.assertEqual(combat_projection.weighted_counter([1, 2, 3, 2], 3),
                         {'triggers': 2, 'remainder': 2, 'carry_over': True})
        self.assertEqual(combat_projection.weighted_counter([1, 2, 3, 2], 3, False),
                         {'triggers': 2, 'remainder': 2, 'carry_over': False})
        self.assertEqual(combat_projection.weighted_counter([5, 1], 3)['triggers'], 2)
        self.assertEqual(combat_projection.weighted_counter([5, 1], 3, False)['triggers'], 1)
        self.assertEqual(combat_projection.periodic_tick_count(5, 2, 1), 2)
        self.assertEqual(combat_projection.periodic_tick_count(5, 2, 1, True), 3)
        self.assertEqual(combat_projection.periodic_tick_count(1 + 1e-12, .1, 0, False), 11)
        self.assertEqual(combat_projection.periodic_tick_count(.3, .1, 0, False), 3)
        self.assertEqual(combat_projection.periodic_tick_count(.3, .1, 0, True), 4)
        with self.assertRaises(ValueError):
            combat_projection.components({'shots': 10, 'direct': {
                'normal_damage_per_shot': 100, 'crit_share': .1,
                'weakspot_share': .1, 'crit_weakspot_share': .2}})
        with self.assertRaises(ValueError):
            combat_projection.components({'shots': 10, 'events': [{
                'basis': 'psi', 'damage_class': 'status', 'branch': 'status',
                'basis_value': 100, 'coefficient_percent': 50,
                'chance_per_shot': 1.2}]})

    def test_component_comparison_uses_explicit_budget_without_fake_winner(self):
        profile = {'shots': 10, 'duration_seconds': 5,
                   'direct': {'normal_damage_per_shot': 100,
                              'crit_share': 0, 'weakspot_share': 0,
                              'crit_weakspot_share': 0},
                   'events': [{'basis': 'psi', 'damage_class': 'status',
                               'branch': 'status', 'basis_value': 100,
                               'coefficient_percent': 100, 'count': 1}]}
        result = component_compare.compare(
            {'attributes': []},
            {'attributes': [{'name': 'Status DMG', 'value_percent': 10,
                             'source': 'reviewed card'}]},
            {'combat_profile': profile, 'base_pools': {'status': 0}})
        projected = result['conditional_combat_projection']
        self.assertEqual(projected['left_damage_range'], [1100, 1100])
        self.assertEqual(projected['right_damage_range'], [1110, 1110])
        self.assertEqual(projected['right_dps_range'], [222, 222])
        self.assertFalse(result['game_winner_established'])
        with self.assertRaises(ValueError):
            component_compare.compare({}, {}, {'combat_profile': {'shots': 10}})

    def test_additive_joint_hit_uses_additive_pool_ratio(self):
        profile = {'shots': 1, 'direct': {'normal_damage_per_shot': 100,
                  'crit_bonus_percent': 100, 'weakspot_bonus_percent': 100,
                  'crit_share': 1, 'weakspot_share': 1, 'crit_weakspot_share': 1,
                  'joint_multiplier': 'additive'}}
        result = component_compare.compare({'attributes': []},
            {'attributes': [{'name': 'Crit DMG', 'value_percent': 100,
                             'source': 'entered test', 'source_status': 'assumed'}]},
            {'combat_profile': profile, 'base_pools': {'crit': 100, 'weakspot': 100}})
        self.assertEqual(result['conditional_combat_projection']['left_damage_range'], [300, 300])
        self.assertEqual(result['conditional_combat_projection']['right_damage_range'], [400, 400])
        self.assertAlmostEqual(result['component_ratios']['crit_weakspot']['min'], 4 / 3)
        for entered, derived in (({'crit': 100}, 'weakspot'), ({'weakspot': 100}, 'crit'), ({}, 'crit')):
            inferred = component_compare.compare({'attributes': []},
                {'attributes': [{'name': 'Crit DMG', 'value_percent': 100, 'source': 'entered test'}]},
                {'combat_profile': profile, 'base_pools': entered})
            self.assertEqual(inferred['conditional_combat_projection']['right_damage_range'], [400, 400])
            self.assertIn(derived, inferred['base_pools_derived_from_profile'])
            self.assertNotIn(derived, inferred['missing_base_pools'])
        with self.assertRaisesRegex(ValueError, 'disagrees'):
            component_compare.compare({'attributes': []}, {'attributes': []},
                {'combat_profile': profile, 'base_pools': {'crit': 90}})

    def test_weapon_class_power_surge_ignores_status_pool(self):
        profile = {'shots': 1, 'events': [
            {'basis': 'psi', 'damage_class': 'weapon', 'branch': 'power_surge',
             'basis_value': 100, 'coefficient_percent': 100, 'count': 1}]}
        result = component_compare.compare({'attributes': []},
            {'attributes': [{'name': 'Status DMG', 'value_percent': 100,
                             'source': 'entered test', 'source_status': 'assumed'}]},
            {'combat_profile': profile, 'base_pools': {'status': 0}})
        self.assertEqual(result['conditional_combat_projection']['left_damage_range'], [100, 100])
        self.assertEqual(result['conditional_combat_projection']['right_damage_range'], [100, 100])
        weapon = component_compare.compare({'attributes': []},
            {'attributes': [{'name': 'Weapon DMG', 'value_percent': 100,
                             'source': 'entered test', 'source_status': 'assumed'}]},
            {'combat_profile': profile, 'base_pools': {'weapon': 0}})
        self.assertEqual(weapon['conditional_combat_projection']['right_damage_range'], [200, 200])

    def test_status_class_does_not_imply_elemental_event(self):
        event={'basis':'attack','damage_class':'status','branch':'status',
               'basis_value':100,'coefficient_percent':100,'count':1}
        alternative={'attributes':[{'name':'Elemental DMG','value_percent':100,
                                    'source':'isolated input','source_status':'assumed'}]}
        def compare(tag=None):
            profile={'shots':1,'events':[{**event,**(tag or {})}]}
            return component_compare.compare({'attributes':[]},alternative,
                    {'combat_profile':profile,'base_pools':{'elemental':0}})
        unknown=compare()
        self.assertIsNone(unknown['conditional_combat_projection'])
        self.assertTrue(any('element classification' in reason for reason in unknown['missing']))
        shock=compare({'element':'Shock'})
        self.assertEqual(shock['conditional_combat_projection']['right_damage_range'],[200,200])
        non_elemental=compare({'element':'none'})
        self.assertEqual(non_elemental['conditional_combat_projection']['right_damage_range'],[100,100])
        explicit=compare({'elemental_pool_applies':True})
        self.assertEqual(explicit['conditional_combat_projection']['right_damage_range'],[200,200])
        with self.assertRaisesRegex(ValueError,'conflicts'):
            compare({'element':'Shock','elemental_pool_applies':False})

    def test_snowline_repeats_tagged_trigger_effect_without_duplication_of_vortex(self):
        profile = {'shots': 10, 'events': [
            {'name': 'Vortex packet', 'basis': 'psi', 'damage_class': 'status',
             'branch': 'status', 'basis_value': 100, 'coefficient_percent': 100,
             'count': 1, 'trigger_family': 'frost_vortex', 'triggered_effect': False},
            {'name': 'Spear triggered by Vortex', 'basis': 'psi', 'damage_class': 'status',
             'branch': 'status', 'basis_value': 50, 'coefficient_percent': 100,
             'count': 1, 'trigger_family': 'frost_vortex', 'triggered_effect': True}]}
        ordinary = combat_projection.components(profile)
        repeated = combat_projection.components(profile, {'frost_vortex': 1})
        self.assertEqual(ordinary['total_damage'], 150)
        self.assertEqual(repeated['total_damage'], 200)
        self.assertEqual(repeated['event_trace'][0]['events_per_trigger'], 1)
        self.assertEqual(repeated['event_trace'][1]['events_per_trigger'], 2)
        snowline = {'catalog_id': 'armor:snowline-elite-vest', 'attributes': []}
        result = component_compare.compare({}, snowline,
                    {'combat_profile': profile, 'snowline_rule_active': True})
        self.assertEqual(result['conditional_combat_projection']['right_damage_range'], [200, 200])
        self.assertEqual(result['conditional_combat_projection']['right_over_left_range'], [4 / 3, 4 / 3])
        unknown = component_compare.compare({}, snowline, {'combat_profile': profile})
        self.assertEqual(unknown['conditional_combat_projection']['right_damage_range'], [150, 150])
        self.assertTrue(any('scenario applicability' in reason for reason in unknown['missing']))
        self.assertFalse(result['game_winner_established'])


if __name__ == '__main__':
    unittest.main()
