"""Selected reviewed equipment rows feed explicit weapon scenarios without double entry."""
import copy
import unittest

import component_compare


BASE = {key: 0 for key in component_compare.TIMELINE_DAMAGE_POOLS}


def scenario():
    return {'weapon_id': 'weapon:mps5-blue-tiger', 'evidence_mode': 'dated_release',
            'model_mode': 'explicit_assumptions', 'stream_id': 'auto-pool',
            'actions': [{'kind': 'hit', 'at': 0, 'target': 'dummy', 'input_id': 'h1',
                         'rolls': {'bounce': 0.999999}}],
            'damage_model': {'basis_values': {'attack': 100},
                             'direct': {'basis': 'attack', 'damage_class': 'weapon',
                                        'element': 'none', 'coefficient_percent': 100},
                             'duration_seconds': 1}}


def row(name, value, **extra):
    return {'name': name, 'value_percent': value, 'source': 'explicit_test_review', **extra}


class TimelinePoolApplicationTests(unittest.TestCase):
    def alternatives(self):
        return ({'name': 'left', 'attributes': [row('Weapon DMG', 10),
                                                row('Power Surge DMG', 5)]},
                {'name': 'right', 'attributes': [row('Weapon DMG', 20)]})

    def context(self):
        return {'base_pools': BASE.copy(),
                'weapon_timeline_pool_mode': 'selected_reviewed_rows',
                'weapon_timeline': {'left': scenario(), 'right': scenario()}}

    def test_selected_rows_apply_only_to_supported_pools_without_mutating_input(self):
        left, right = self.alternatives()
        context = self.context()
        before = copy.deepcopy((left, right, context))
        result = component_compare.compare(left, right, context)
        runs = result['weapon_timeline_scenarios']
        self.assertAlmostEqual(runs['left']['total_damage'], 110)
        self.assertAlmostEqual(runs['right']['total_damage'], 120)
        self.assertFalse(result['game_winner_established'])
        application = result['weapon_timeline_pool_application']
        self.assertEqual(application['sides']['left']['applied_damage_pools_percent']['weapon'], 10)
        self.assertEqual(application['sides']['right']['applied_damage_pools_percent']['weapon'], 20)
        self.assertEqual(application['sides']['left']['unapplied_component_pools_percent']['power_surge'], 5)
        self.assertIn('typed core outputs', application['scope'])
        self.assertEqual((left, right, context), before)

    def test_missing_baseline_manual_double_entry_and_uncertain_activation_block(self):
        left, right = self.alternatives()
        context = self.context()
        del context['base_pools']['status']
        with self.assertRaisesRegex(ValueError, 'common baseline pools.*status'):
            component_compare.compare(left, right, context)
        context = self.context()
        context['weapon_timeline']['left']['damage_model']['bonus_pools_percent'] = {'weapon': 10}
        with self.assertRaisesRegex(ValueError, 'remove manual bonus_pools_percent'):
            component_compare.compare(left, right, context)
        context = self.context()
        left['attributes'].append(row('Weapon DMG', 10, condition='low hp'))
        with self.assertRaisesRegex(ValueError, 'activation or strength is unresolved for weapon'):
            component_compare.compare(left, right, context)
        context['condition_uptime'] = {'low hp': 1}
        context['condition_strength'] = {'low hp': .5}
        resolved = component_compare.compare(left, right, context)
        self.assertAlmostEqual(resolved['weapon_timeline_scenarios']['left']['total_damage'], 115)

    def test_selected_catalog_identity_uses_sourced_rows_not_ownership(self):
        context = self.context()
        left = {'catalog_id': 'mod:boots_mod:against-all-odds-deviant-energy', 'level': 12}
        right = {'catalog_id': 'mod:boots_mod:against-all-odds-deviant-energy', 'level': 12}
        result = component_compare.compare(left, right, context)
        self.assertEqual(result['weapon_timeline_scenarios']['left']['total_damage'],
                         result['weapon_timeline_scenarios']['right']['total_damage'])
        self.assertFalse(result['game_winner_established'])
        self.assertIsNotNone(result['weapon_timeline_pool_application'])


if __name__ == '__main__':
    unittest.main()
