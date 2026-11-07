from tests.explicit_reference_fixture import explicit_synthetic_reference
"""Structured Compare binds selected equipment to the published reference once."""
import math
import unittest

import structured_compare


FLAME = 'mod:weapon_mod:flame-resonance-general'
KAM = 'weapon:kam'


@explicit_synthetic_reference
class PublishedReferenceSelectionTests(unittest.TestCase):
    def test_reload_speed_unknown_withholds_only_cycle_metric(self):
        request = {'left': {'kind': 'catalog', 'catalog_id': FLAME, 'level': 8},
                   'right': {'kind': 'catalog', 'catalog_id': FLAME, 'level': 17},
                   'context': {'published_reference': {'enabled': True,
                       'left': {'weapon_id': KAM,
                                'condition_fractions': {'damage against enemies': 0}},
                       'right': {'weapon_id': KAM,
                                 'condition_fractions': {'damage against enemies': 0}}}}}
        reference = structured_compare.compare(request, [])['published_reference']
        self.assertEqual(reference['status'], 'partial_reference')
        self.assertEqual(reference['direct_reference_metric_complete']['left'], {
            'reference_hit': False, 'firing_damage_per_second': False,
            'reload_cycle_damage_per_second': False})
        self.assertIsNone(reference['right_over_left_reference_ratios']['reference_hit'])
        self.assertIsNone(reference['right_over_left_reference_ratios']['firing_damage_per_second'])
        self.assertIsNone(reference['right_over_left_reference_ratios']['reload_cycle_damage_per_second'])

    def test_saved_plan_and_direct_selection_share_metric_completeness(self):
        plans = [{'id': 'metric-plan', 'name': 'Metric plan', 'slots': {
            'primary': {'catalog_id': KAM, 'mod_id': FLAME, 'mod_level': 8}}}]
        options = {'condition_fractions': {'damage against enemies': 0}}
        request = {'left': {'kind': 'planned_build', 'planned_build_id': 'metric-plan'},
                   'right': {'kind': 'catalog', 'catalog_id': FLAME, 'level': 8},
                   'context': {'published_reference': {'enabled': True,
                       'left': options, 'right': {'weapon_id': KAM, **options}}}}
        reference = structured_compare.compare(request, plans)['published_reference']
        self.assertEqual(reference['direct_reference_metric_complete']['left'],
                         reference['direct_reference_metric_complete']['right'])
        self.assertEqual(reference['direct_reference_metric_complete']['left'], {
            'reference_hit': False, 'firing_damage_per_second': False,
            'reload_cycle_damage_per_second': False})
        self.assertIsNone(reference['right_over_left_reference_ratios']['reference_hit'])
        self.assertIsNone(reference['right_over_left_reference_ratios']['reload_cycle_damage_per_second'])
        self.assertEqual(plans[0]['slots']['primary']['mod_level'], 8)

    def test_unmapped_firearm_damage_withholds_direct_reference(self):
        identity = 'mod:boots_mod:secluded-strike-mirror'
        request = {'left': {'kind': 'catalog', 'catalog_id': identity, 'level': 10},
                   'right': {'kind': 'catalog', 'catalog_id': identity, 'level': 10},
                   'context': {'published_reference': {'enabled': True,
                       'left': {'weapon_id': KAM,
                                'condition_fractions': {'attack from behind': 0,
                                                        'damage against enemies': 0}},
                       'right': {'weapon_id': KAM,
                                 'condition_fractions': {'attack from behind': 0,
                                                         'damage against enemies': 0}}}}}
        reference = structured_compare.compare(request, [])['published_reference']
        self.assertFalse(reference['direct_reference_complete']['left'])
        self.assertIsNone(reference['right_over_left_reference_ratios']['reference_hit'])

    def test_single_mod_levels_use_explicit_reference_and_keep_typed_separate(self):
        request = {'left': {'kind': 'catalog', 'catalog_id': FLAME, 'level': 8},
                   'right': {'kind': 'catalog', 'catalog_id': FLAME, 'level': 17},
                   'context': {'published_reference': {'enabled': True,
                       'left': {'weapon_id': KAM}, 'right': {'weapon_id': KAM}}}}
        result = structured_compare.compare(request, [])
        reference = result['published_reference']
        self.assertEqual(reference['status'], 'partial_reference')
        self.assertIsNone(reference['right_over_left_reference_ratios']['reference_hit'])
        self.assertFalse(reference['direct_reference_metric_complete']['left']['reference_hit'])
        self.assertFalse(reference['direct_reference_metric_complete']['right']['reference_hit'])
        self.assertEqual(len(reference['left']['selected_mod_rows']), 4)
        self.assertIn('status_proc', reference['not_combined_mechanics'])
        self.assertIn('crit', reference['linked_typed_sensitivity'])
        self.assertIn('status', reference['linked_typed_sensitivity'])
        self.assertFalse(reference['game_winner_established'])
        self.assertTrue(reference['component_sensitivity_available'])

    def test_saved_plan_uses_its_weapon_armor_mod_and_set_evidence(self):
        plans = [{'id': 'synthetic', 'name': 'Synthetic', 'slots': {
            'primary': {'catalog_id': KAM, 'tier': 3, 'stars': 2,
                        'mod_id': FLAME, 'mod_level': 8},
            'shoes': {'catalog_id': 'armor:agent-shoes', 'tier': 5, 'stars': 1}}}]
        request = {'left': {'kind': 'planned_build', 'planned_build_id': 'synthetic'},
                   'right': {'kind': 'catalog', 'catalog_id': FLAME, 'level': 17},
                   'context': {'published_reference': {'enabled': True,
                       'left': {}, 'right': {'weapon_id': KAM}}}}
        result = structured_compare.compare(request, plans)
        reference = result['published_reference']
        self.assertEqual(reference['selection_builds']['left']['weapon']['tier'], 3)
        self.assertEqual(reference['selection_builds']['left']['mods'][0]['level'], 8)
        self.assertEqual(reference['left']['armor_profiles'][0]['stats']['hp'], 1062)
        self.assertTrue(reference['linked_set_thresholds']['left'])
        self.assertTrue(reference['selection_gaps']['right'])
        self.assertEqual(result['selection_metadata']['left']['planned_build_id'], 'synthetic')
        self.assertEqual(plans[0]['slots']['primary']['mod_level'], 8)

    def test_mod_without_reference_weapon_is_explicitly_incomplete(self):
        request = {'left': {'kind': 'catalog', 'catalog_id': FLAME, 'level': 8},
                   'right': {'kind': 'catalog', 'catalog_id': FLAME, 'level': 17},
                   'context': {'published_reference': {'enabled': True,
                       'left': {}, 'right': {}}}}
        result = structured_compare.compare(request, [])['published_reference']
        self.assertEqual(result['status'], 'needs_reference_weapon')
        self.assertFalse(result['game_winner_established'])

    def test_blocked_bonus_layout_does_not_publish_known_subset_ratio(self):
        request = {'left': {'kind': 'catalog', 'catalog_id': FLAME, 'level': 8},
                   'right': {'kind': 'catalog',
                             'catalog_id': 'mod:weapon_mod:flame-resonance-deviant-energy',
                             'level': 8},
                   'context': {'published_reference': {'enabled': True,
                       'left': {'weapon_id': KAM}, 'right': {'weapon_id': KAM}}}}
        reference = structured_compare.compare(request, [])['published_reference']
        self.assertEqual(reference['status'], 'partial_reference')
        self.assertFalse(reference['direct_reference_complete']['right'])
        self.assertIsNone(reference['right_over_left_reference_ratios']['reference_hit'])

    def test_selected_weapon_identity_cannot_disagree(self):
        request = {'left': {'kind': 'catalog', 'catalog_id': KAM},
                   'right': {'kind': 'catalog', 'catalog_id': KAM},
                   'context': {'published_reference': {'enabled': True,
                       'left': {'weapon_id': 'weapon:mps5-blue-tiger'},
                       'right': {}}}}
        with self.assertRaisesRegex(ValueError, 'must match'):
            structured_compare.compare(request, [])

    def test_armor_slot_and_source_zero_remain_unknown(self):
        request = {'left': {'kind': 'catalog',
                            'catalog_id': 'armor:treacherous-tides-helmet'},
                   'right': {'kind': 'catalog', 'catalog_id': 'armor:bastille-helmet'},
                   'context': {'published_reference': {'enabled': True,
                       'left': {'weapon_id': KAM, 'armor_stars': 3, 'armor_tier': 1},
                       'right': {'weapon_id': KAM, 'armor_stars': 1, 'armor_tier': 5}}}}
        result = structured_compare.compare(request, [])['published_reference']
        self.assertIsNone(result['left']['armor_hp_for_supplied_slots'])
        self.assertIsNotNone(result['right']['armor_hp_for_supplied_slots'])
        self.assertEqual(result['right_over_left_reference_ratios']['reference_hit'], 1)


if __name__ == '__main__':
    unittest.main()
