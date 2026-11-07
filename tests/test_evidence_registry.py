import math
import unittest

import catalog
import component_compare
import evidence_registry
import planned_advisor


class EvidenceRegistryTests(unittest.TestCase):
    def test_catalog_coverage_is_partitioned_without_claiming_complete_weapons(self):
        report = evidence_registry.coverage()
        self.assertEqual((report['weapon_catalog'], report['weapon_bound_partial'], report['weapon_unbound']),
                         (138, 26, 112))
        self.assertEqual(report['fully_parameterized_current_weapons'], 0)
        self.assertEqual((report['weapon_historical_stat_references'],
                          report['weapon_direct_database_stat_references'],
                          report['weapon_reference_conflicts']), (0, 0, 0))
        self.assertEqual((report['armor_set_count'], report['armor_thresholds']), (21, 79))
        self.assertEqual((report['suffix_exact_profiles'], report['suffix_complete_exact_profiles'],
                          report['suffix_partial_exact_profiles']), (75, 68, 7))
        self.assertEqual(report['suffix_candidates_executable'], 0)
        self.assertEqual(report['suffix_derived_opt_in_profiles'], 2505)
        self.assertEqual(report['suffix_cross_slot_layouts_fully_corroborated'], 6)
        self.assertEqual(report['suffix_cross_slot_tier_candidates_corroborated'], 23)
        self.assertEqual(set(evidence_registry.WEAPON_ENTRIES) |
                         set(evidence_registry.PACKETS['weapons-v2-delta']['coverage']['remaining_unbound_ids']),
                         {key for key, entry in catalog.ENTRIES.items() if entry['kind'] == 'weapon'})

    def test_weapon_revision_replaces_preview_values_without_promoting_current_status(self):
        old = evidence_registry.PACKETS['weapons']['entries']['weapon:kam-abyss-glance']
        current = evidence_registry.binding('weapon:kam-abyss-glance')
        old_event = next(event for event in old['events'] if event['event'] == 'frost_vortex')
        revised_event = next(event for event in current['evidence']['events'] if event['event'] == 'frost_vortex')
        self.assertEqual(old_event['trigger']['hits'], 15)
        self.assertEqual(revised_event['trigger']['hits'], 14)
        self.assertEqual(current['binding_status'], 'partial_official_release_historical')
        self.assertFalse(current['current_numeric_profile_complete'])
        aug = evidence_registry.binding('weapon:aug-electron-cloud')
        self.assertEqual(aug['binding_status'], 'partial_preview_numbers')
        self.assertEqual(aug['evidence']['events'][0]['evidence_status'], 'preview_numeric')
        self.assertIn('may26', aug['sources'])
        sn700 = evidence_registry.binding('weapon:sn700')['stat_references']
        self.assertIsNone(sn700['historical_catalog_profile'])
        self.assertIsNone(sn700['database_page_reference'])
        self.assertIsNone(sn700['selected_crafted_weapon_tier'])
        self.assertIsNone(sn700['attack_stat_reference'])
        self.assertIsNone(evidence_registry.binding('weapon:aug-electron-cloud')['stat_references']['selected_crafted_weapon_tier'])

    def test_suffix_candidates_are_not_applied_as_exact_levels(self):
        known = evidence_registry.binding('mod:boots_mod:against-all-odds-precision', 7)
        unknown = evidence_registry.binding('mod:boots_mod:against-all-odds-precision', 8)
        self.assertEqual(known['binding_status'], 'verified_exact_row')
        self.assertEqual(unknown['binding_status'], 'no_exact_profile')
        self.assertFalse(unknown['candidate_transfer_allowed'])
        held = evidence_registry.binding('mod:boots_mod:against-all-odds-deviant-energy', 12)
        self.assertEqual(held['binding_status'], 'verified_exact_catalog_profile')
        self.assertTrue(held['exact_profile_in_catalog'])
        self.assertTrue(held['exact_profile_in_suffix_packet'])
        self.assertTrue(held['v3_direct_observation'])
        self.assertEqual(len(held['evidence']['source_sha256']), 64)

    def test_armor_preview_and_unknown_weapon_are_reported_not_zeroed(self):
        result = component_compare.compare(
            {'items': [{'catalog_id': 'weapon:aug-electron-cloud'}],
             'sets': [{'name': 'Treacherous Tides', 'count': 4}]},
            {'attributes': []})
        audit = result['left']['evidence_audit']
        self.assertEqual(audit['items'][0]['binding_status'], 'partial_preview_numbers')
        self.assertEqual(audit['earned_set_thresholds'][-1]['binding_status'], 'official_preview_only')
        self.assertTrue(any('not a current executable rule' in message for message in result['missing']))
        self.assertTrue(any('not fully parameterized' in message for message in result['missing']))
        self.assertFalse(result['game_winner_established'])

    def test_treacherous_three_piece_uses_only_released_hp_endpoints(self):
        left = {'attributes': []}
        right = {'sets': [{'name': 'Treacherous Tides', 'count': 3}]}
        def bonus(hp):
            result = component_compare.compare(left, right,
                                                {'scenario': 'pve non-raidzone', 'hp_percent': hp})
            rows = [row for row in result['right']['trace'] if row.get('rule_id') == 'treacherous_tides_three']
            self.assertEqual(len(rows), 2)
            self.assertFalse(result['game_winner_established'])
            return rows[0]['applied_range_percent'], result['missing']
        self.assertEqual(bonus(100)[0], [8, 8])
        self.assertEqual(bonus(60)[0], [28, 28])
        self.assertEqual(bonus(29)[0], [28, 28])
        self.assertEqual(bonus(80)[0], [8, 28])
        self.assertTrue(any('scaling curve' in line for line in bonus(80)[1]))
        self.assertTrue(any('stacking' in line for line in bonus(60)[1]))

    def test_bastille_two_piece_reload_is_conditional_on_source_scenario(self):
        left = {'attributes': []}
        right = {'sets': [{'name': 'Bastille', 'count': 2}]}
        timing = {'rpm': 600, 'magazine': 10, 'reload_seconds': 2}
        result = component_compare.compare(left, right,
                                           {'scenario': 'pve non-raidzone', 'timing': timing})
        self.assertTrue(math.isclose(result['firing_cycle']['right']['reload_seconds'], 2 / 1.15))
        self.assertTrue(math.isclose(result['firing_cycle']['throughput_ratio_floor_range'][0],
                                      (1 + 2) / (1 + 2 / 1.15)))
        uncertain = component_compare.compare(left, right, {'timing': timing})
        self.assertLess(uncertain['firing_cycle']['throughput_ratio_floor_range'][0],
                        uncertain['firing_cycle']['throughput_ratio_floor_range'][1])
        self.assertFalse(uncertain['game_winner_established'])

    def test_treacherous_shield_preview_not_described_as_live(self):
        rule = next(row for row in component_compare.SET_RULES
                    if row['id'] == 'treacherous_tides_four_shield')
        self.assertIn('preview only', rule['evidence_status'])
        self.assertIn('preview-only', planned_advisor._rule_description(rule))

    def test_community_set_modifiers_require_explicit_opt_in_and_keep_provenance(self):
        empty = {'attributes': []}
        agent = {'sets': [{'name': 'Agent', 'count': 2}]}
        default = component_compare.compare(empty, agent)
        self.assertEqual(default['component_ratios']['weakspot']['max'], 1)
        scenario = component_compare.compare(empty, agent, {'community_candidate_opt_in': True})
        self.assertEqual(scenario['component_ratios']['weakspot']['max'], 1.10)
        row = next(row for row in scenario['right']['trace'] if row.get('rule_id', '').startswith('community_candidate:'))
        self.assertIn('explicit assumption', row['source_status'])
        self.assertTrue(any('current effect and stacking unverified' in note for note in scenario['missing']))
        self.assertFalse(scenario['game_winner_established'])
        shielded = component_compare.compare(empty, {'sets': [{'name': 'Savior', 'count': 2}]},
            {'community_candidate_opt_in': True, 'condition_uptime': {'shield_positive': 1}})
        self.assertEqual(shielded['component_ratios']['normal']['max'], 1.10)
        self.assertEqual(shielded['component_ratios']['status']['max'], 1.10)
        bastille = component_compare.compare(empty, {'sets': [{'name': 'Bastille', 'count': 2}]},
            {'community_candidate_opt_in': True, 'scenario': 'pve non-raidzone'})
        self.assertEqual(len([row for row in bastille['right']['trace']
                              if row.get('rule_id') == 'bastille_two_reload_efficiency']), 1)


if __name__ == '__main__':
    unittest.main()
