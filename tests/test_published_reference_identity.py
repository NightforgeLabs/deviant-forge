"""Published reference identity evidence must not rewrite catalog or saved plans."""
import math
import unittest

import catalog
import catalog_coverage_extended
import published_calculator_adapter as adapter
import published_reference_model as model
import published_timed_combat
import structured_compare


class PublishedReferenceIdentityTests(unittest.TestCase):
    def test_short_weapon_names_use_exact_full_name_reference_and_mechanics(self):
        packet={'assume_direct_body_damage_per_projectile': True, 'baseline_bonus_scope':'before_selected_effects',
                'direct_body_damage_per_projectile': 100,
                'projectiles_per_shot': 1, 'rpm': 600,
                'magazine_capacity': 10, 'reload_seconds': 2}
        for short, full in (('weapon:pyroclasm-starter', 'weapon:acs12-pyroclasm-starter'),
                            ('weapon:pathfinder', 'weapon:sks-pathfinder')):
            with self.subTest(short=short):
                selected = model.build({'weapon': {'catalog_id': short,
                    'caller_packet_scenario':packet}})
                canonical = model.build({'weapon': {'catalog_id': full,
                    'caller_packet_scenario':packet}})
                self.assertEqual(selected['weapon_id'], short)
                self.assertEqual(selected['weapon_mechanics_id'], full)
                self.assertEqual(selected['weapon_source_native_baseline']['stats'],
                                 canonical['weapon_source_native_baseline']['stats'])
                self.assertEqual(selected['direct_only'], canonical['direct_only'])
                self.assertEqual(selected['weapon_source_native_baseline']['evidence'],
                                 'caller_entered_direct_packet_hypothesis')
                self.assertEqual(catalog.ENTRIES[short]['id'], short)
                self.assertEqual(catalog.ENTRIES[full]['id'], full)
        short = model.build({'weapon': {'catalog_id': 'weapon:pyroclasm-starter',
                                        'caller_packet_scenario': packet}})
        timed = published_timed_combat.evaluate(short, {'duration_seconds': 1})
        self.assertEqual(timed['status'], 'partial_timed_total')
        self.assertTrue(any('sourced extra packets' in gap for gap in timed['unresolved']))

    def test_exact_blueprint_rarity_is_reference_only_and_snowland_stays_unknown(self):
        examples = {'armor:rustic-hat': ('common', 42, 11, 3),
                    'armor:rustic-jacket': ('common', 109, 8, 4),
                    'armor:rustic-pants': ('common', 101, 9, 3),
                    'armor:rustic-shoes': ('common', 84, 6, 3),
                    'armor:rustic-gloves': ('common', 63, 8, 3),
                    'armor:frost-tactical-vest': ('epic', 140, 10, 4)}
        for identity, (rarity, hp, psi, pollution) in examples.items():
            with self.subTest(identity=identity):
                profile = model.build({'weapon': {'catalog_id': 'weapon:kam'},
                                       'armor': [{'catalog_id': identity}]})['armor_profiles'][0]
                self.assertEqual(profile['catalog_rarity'], 'uncommon')
                self.assertEqual(profile['published_reference_rarity'], rarity)
                self.assertTrue(profile['rarity_conflict'])
                self.assertEqual(profile['stats'], {'hp': None, 'psi_intensity': None,
                                                    'pollution_resist': pollution})
                self.assertEqual(catalog.ENTRIES[identity]['rarity'], 'uncommon')
                higher = model.build({'weapon': {'catalog_id': 'weapon:kam'},
                                      'armor': [{'catalog_id': identity, 'tier': 2}]})['armor_profiles'][0]
                self.assertIsNone(higher['stats']['pollution_resist'])
        snowland = model.build({'weapon': {'catalog_id': 'weapon:kam'},
                                'armor': [{'catalog_id': 'armor:snowland-rustic-hat'}]})['armor_profiles'][0]
        self.assertIsNone(snowland['stats']['hp'])
        self.assertIsNone(snowland['rarity_evidence'])

    def test_direct_and_saved_plan_selection_same_reference_without_mutation(self):
        packet={'assume_direct_body_damage_per_projectile':True, 'baseline_bonus_scope':'before_selected_effects',
                'direct_body_damage_per_projectile':100,
                'projectiles_per_shot':1,'rpm':600,
                'magazine_capacity':10,'reload_seconds':2}
        plan = {'id': 'identity-plan', 'name': 'Identity plan', 'slots': {
            'primary': {'catalog_id': 'weapon:pyroclasm-starter'},
            'helmet': {'catalog_id': 'armor:rustic-hat'}}}
        import copy
        before = copy.deepcopy(plan)
        request = {'left': {'kind': 'planned_build', 'planned_build_id': plan['id']},
                   'right': {'kind': 'catalog', 'catalog_id': 'armor:rustic-hat'},
                   'context': {'published_reference': {'enabled': True,
                       'left': {'weapon_id': 'weapon:pyroclasm-starter',
                                'caller_packet_scenario':packet},
                       'right': {'weapon_id': 'weapon:pyroclasm-starter',
                                 'caller_packet_scenario':packet}}}}
        result = structured_compare.compare(request, [plan])['published_reference']
        self.assertEqual(result['left']['weapon_source_native_baseline']['stats'],
                         result['right']['weapon_source_native_baseline']['stats'])
        self.assertEqual(result['left']['armor_profiles'][0]['stats'],
                         result['right']['armor_profiles'][0]['stats'])
        self.assertEqual(plan, before)

    def test_coverage_grouping_and_numeric_layout_limits(self):
        report = catalog_coverage_extended.coverage()
        self.assertEqual(report['mod_grouping']['distinct_names'], 138)
        self.assertEqual(report['mod_grouping']['distinct_name_slot_pairs'], 144)
        self.assertEqual(report['mod_grouping']['distinct_tree_or_name_labels'], 152)
        self.assertEqual(report['selectable_mod_variants'], 984)
        self.assertEqual(report['published_fixed_layout_identities'], 881)
        self.assertEqual(report['level10_four_numeric_bonus_identities'], 70)
        self.assertEqual(report['level10_partial_bonus_identities'], 914)
        self.assertEqual(report['published_formula_candidate_profiles'], 14977)
        self.assertEqual(report['published_formula_blocked_profiles'], 1751)


if __name__ == '__main__':
    unittest.main()
