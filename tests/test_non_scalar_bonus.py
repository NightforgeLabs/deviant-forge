import unittest
from collections import Counter

import catalog
import component_compare
import public_catalog_detail
import public_semantic_crosscheck
import published_calculator_adapter as adapter
import published_reference_model


LUNAR = 'mod:helmet_mod:elemental-havoc-lunar'
RESONANCE = 'mod:gloves_mod:crit-amplifier-resonance-deviant-energy'
WEAPON = {'catalog_id': 'weapon:aug-electron-cloud', 'tier': 1,
          'item_page_scenario': {'assume_displayed_damage_per_projectile': True, 'assume_fire_rate_as_rpm': True,
                                 'projectiles_per_shot': 1}}


class NonScalarBonusTests(unittest.TestCase):
    def test_lv10_non_scalar_groups_and_exact_maximum_exceptions(self):
        groups = Counter()
        monster_scope = 0
        general_scope = 0
        for identity, entry in catalog.ENTRIES.items():
            if entry['kind'] != 'mod' or entry.get('family_only'):
                continue
            rows, status, _ = public_catalog_detail.calculation_rows(identity, 10)
            if status != 'published_candidate_partial':
                continue
            if any('native_monster_scope_not_published_enemy_scope' in
                   (row.get('published_conflict_reasons') or []) for row in rows):
                monster_scope += 1
            if any('native_remote_dot_scope_not_all_damage' in
                   (row.get('published_conflict_reasons') or []) for row in rows):
                general_scope += 1
            kinds = {'lunar' if public_catalog_detail.low_hp_maximum(row) is not None
                     else 'resonance' if 'resonance_' in str(row.get('stat_type'))
                     else 'other' for row in rows if row.get('value_percent') is None and
                     not set(row.get('published_conflict_reasons') or []) & {
                         'native_monster_scope_not_published_enemy_scope',
                         'native_remote_dot_scope_not_all_damage'}}
            self.assertLessEqual(len(kinds), 1, identity)
            if kinds:
                groups[next(iter(kinds))] += 1
        self.assertEqual({'lunar': 41, 'resonance': 45, 'other': 57}, groups)
        self.assertEqual(monster_scope, 742)
        self.assertEqual(general_scope, 87)
        self.assertTrue(public_semantic_crosscheck.layout_conflicts(
            'mod:helmet_mod:overflow-general'))
        exact, status, _ = public_catalog_detail.calculation_rows(
            'mod:helmet_mod:deviation-expert-lunar', 10)
        self.assertEqual('complete', status)
        self.assertEqual(18, exact[0]['value_percent'])
        self.assertEqual('low HP', exact[0]['condition'])

    def test_sourced_lunar_maximum_is_bounded_and_fraction_is_explicit(self):
        choice = {'catalog_id': LUNAR, 'level': 10}
        unknown = component_compare.compare({'name': 'none'}, choice)
        self.assertEqual(1, unknown['component_ratios']['normal']['min'])
        self.assertAlmostEqual(1.072, unknown['component_ratios']['normal']['max'])
        self.assertTrue(any('scaling curve is unpublished' in gap
                            for gap in unknown['missing']))
        entered = component_compare.compare({'name': 'none'}, choice,
            {'hp_percent': 29, 'condition_uptime': {'low hp': 1},
             'condition_strength': {'low hp': .5}})
        self.assertAlmostEqual(1.036, entered['component_ratios']['normal']['min'])
        self.assertAlmostEqual(1.036, entered['component_ratios']['normal']['max'])
        for fraction, expected in ((None, 0), (0, 0), (.5, 3.6), (1, 7.2)):
            build = {'weapon': WEAPON, 'mods': [choice]}
            if fraction is not None:
                build['condition_fractions'] = {'low hp': fraction}
            result = published_reference_model.build(build)
            self.assertAlmostEqual(expected, result['selected_pools_percent']['weapon'])
            self.assertTrue(any('scenario assumption' in gap for gap in result['unresolved']))
            self.assertFalse(result['game_winner_established'])

    def test_resonance_events_are_not_passive_bonuses(self):
        rows, status, _ = public_catalog_detail.calculation_rows(RESONANCE, 10)
        self.assertEqual('published_candidate_partial', status)
        self.assertIsNone(public_catalog_detail.low_hp_maximum(rows[0]))
        result = published_reference_model.build({'weapon': WEAPON,
            'mods': [{'catalog_id': RESONANCE, 'level': 10}]})
        self.assertEqual(0, result['selected_pools_percent']['crit'])
        self.assertEqual(0, result['selected_pools_percent']['elemental'])
        self.assertTrue(any('no supported direct-reference pool or scalar value' in gap
                            for gap in result['unresolved']))
        self.assertIsNone(public_catalog_detail.low_hp_maximum({
            'stat_type': 'lunar_weapon_dmg', 'condition': 'scales with low hp',
            'components': {'max_bonus_percent': 12}, 'source_conflict': True}))

    def test_official_reload_efficiency_needs_base_seconds(self):
        known = adapter.derive_timing({'stats': {'rpm': 720, 'magazine': 40,
                                                  'reload_seconds': 3.2}},
                                      reload_efficiency_percent=25)
        self.assertAlmostEqual(2.56, known['reload_seconds'])
        self.assertEqual(3.2, known['base_reload_seconds'])
        self.assertIn('20250521', known['reload_formula_source_url'])
        missing = adapter.derive_timing({'stats': {'rpm': 720, 'magazine': 40,
                                                    'reload_score': 47}},
                                        reload_efficiency_percent=25)
        self.assertIsNone(missing['reload_seconds'])
        self.assertIsNone(missing['reload_formula_source_url'])
        self.assertIsNone(missing['cycle_seconds'])
        self.assertTrue(any('score cannot be converted' in gap
                            for gap in missing['unresolved']))


if __name__ == '__main__':
    unittest.main()
