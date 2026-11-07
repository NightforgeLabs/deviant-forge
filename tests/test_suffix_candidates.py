import copy
import hashlib
from pathlib import Path
import unittest

import catalog
import component_compare
import suffix_candidates


class SuffixCandidateTests(unittest.TestCase):
    def test_packet_separates_direct_evidence_from_opt_in_derived_profiles(self):
        totals = suffix_candidates.coverage()
        self.assertEqual((totals['exact_observed_identity_levels'],
                          totals['derived_complete_identity_levels'],
                          totals['derived_partial_identity_levels']), (75, 938, 1567))
        self.assertFalse(totals['ownership_inferred'])
        self.assertFalse(totals['game_build_version_verified'])
        self.assertFalse(totals['level_obtainability_verified'])
        self.assertFalse(set(suffix_candidates.EXACT) & set(suffix_candidates.CANDIDATES))
        self.assertFalse(suffix_candidates.PACKET['layout_conflicts'])
        self.assertFalse(suffix_candidates.PACKET['tier_conflicts'])

    def test_battle_source_corrections_gate_all_three_triggered_rows(self):
        observed = catalog.resolve('mod:boots_mod:against-all-odds-battle', 13)
        self.assertEqual(observed['attribute_coverage'], 'complete')
        self.assertEqual(len(observed['observed_profile']['source_sha256']), 64)
        conditions = [row.get('condition') for row in observed['known_attributes']]
        self.assertIn('after hitting a unit', conditions[0])
        self.assertIn('after taking damage', conditions[1])
        self.assertIn('after defeating a meta', conditions[2])
        self.assertIsNone(conditions[3])
        result = component_compare.compare({'attributes': []},
                                           {'catalog_id':'mod:boots_mod:against-all-odds-battle','level':13})
        self.assertFalse(result['game_winner_established'])
        self.assertTrue(any('Damage reduction after hitting' in reason for reason in result['missing']))
        self.assertFalse(any(row.get('pool') == 'weapon' for row in result['right']['trace']))

    def test_candidate_requires_opt_in_and_does_not_mutate_selection(self):
        profile = next(row for row in suffix_candidates.CANDIDATES.values()
                       if row['profile_status'] == 'candidate_complete'
                       and any(r['stat_type'] == 'weapon_damage_percent' for r in row['rows']))
        item = {'catalog_id':profile['catalog_id'], 'level':profile['level']}
        before = copy.deepcopy(item)
        off = component_compare.compare({'attributes':[]}, item)
        on = component_compare.compare({'attributes':[]}, item, {'suffix_candidate_opt_in':True})
        self.assertEqual(item, before)
        self.assertIsNone(off['right']['suffix_candidate_profile'])
        self.assertEqual(on['right']['suffix_candidate_profile']['status'], 'candidate_complete')
        self.assertGreater(on['component_ratios']['normal']['max'], off['component_ratios']['normal']['max'])
        self.assertTrue(any('candidate' in note for note in on['missing']))
        self.assertTrue(any('complete derived suffix profile' in note for note in on['missing']))
        self.assertFalse(any('numeric profile derived_complete' in note for note in on['missing']))
        self.assertFalse(on['game_winner_established'])

    def test_partial_candidate_never_converts_unknown_tiers_to_zero(self):
        profile = next(row for row in suffix_candidates.CANDIDATES.values()
                       if row['profile_status'] == 'candidate_partial' and row['known_row_count'] > 0)
        result = component_compare.compare({'attributes':[]},
                    {'catalog_id':profile['catalog_id'],'level':profile['level']},
                    {'suffix_candidate_opt_in':True})
        self.assertEqual(result['right']['suffix_candidate_profile']['status'], 'candidate_partial')
        self.assertGreater(result['right']['suffix_candidate_profile']['unknown_rows'], 0)
        self.assertTrue(any('exact magnitude missing' in note for note in result['missing']))
        self.assertTrue(any(row.get('state') == 'excluded: exact magnitude missing'
                            for row in result['right']['trace']))

    def test_derived_battle_layout_keeps_corrected_activation_gates(self):
        profile = next(row for row in suffix_candidates.CANDIDATES.values()
                       if row['catalog_id'] == 'mod:boots_mod:against-all-odds-battle'
                       and row['profile_status'] == 'candidate_complete')
        rows = suffix_candidates.attributes(profile)
        self.assertIn('after hitting a unit', rows[0]['condition'])
        self.assertIn('after taking damage', rows[1]['condition'])
        self.assertIn('after defeating a meta', rows[2]['condition'])
        self.assertNotIn('condition', rows[3])
        result = component_compare.compare({'attributes':[]},
                    {'catalog_id':profile['catalog_id'],'level':profile['level']},
                    {'suffix_candidate_opt_in':True})
        self.assertFalse(result['game_winner_established'])
        self.assertFalse(any(row.get('pool') == 'weapon' for row in result['right']['trace']))

    def test_direct_exact_profile_wins_even_if_candidate_registry_collides(self):
        exact = {'catalog_id':'mod:helmet_mod:deviation-expert-lunar','level':10}
        key = (exact['catalog_id'], exact['level'])
        specimen = next(iter(suffix_candidates.CANDIDATES.values()))
        suffix_candidates.CANDIDATES[key] = specimen
        try:
            result = component_compare.compare(exact, exact, {'suffix_candidate_opt_in':True})
        finally:
            del suffix_candidates.CANDIDATES[key]
        self.assertIsNone(result['left']['suffix_candidate_profile'])
        self.assertEqual(result['left']['numeric_coverage'], 'complete')
        self.assertTrue(any(row['name'] == 'Crit DMG' and row.get('value_percent') == 18
                            for row in result['left']['trace']))

    def test_regular_observation_is_not_promoted_to_shiny_level(self):
        identity = 'mod:mask_mod:thunderclap-deviant-energy'
        regular = catalog.resolve(identity, 17)
        shiny = catalog.resolve(identity, 17, shiny=True)
        self.assertIsNotNone(regular.get('observed_profile'))
        self.assertIsNone(shiny.get('observed_profile'))
        result = component_compare.compare({'attributes':[]},
                    {'catalog_id':identity,'level':17,'shiny':True},
                    {'suffix_candidate_opt_in':True})
        self.assertIsNone(result['right']['suffix_candidate_profile'])

    def test_opt_in_type_and_evidence_version_are_explicit(self):
        with self.assertRaisesRegex(ValueError, 'Suffix candidate opt-in'):
            component_compare.compare({}, {}, {'suffix_candidate_opt_in':'yes'})
        self.assertEqual(len(catalog.SUFFIX_HELD['entries']), 13)
        self.assertTrue(all('game build version unknown' in row['evidence_context']
                            for row in catalog.SUFFIX_HELD['entries'].values()))
        sources = {(row['source_frame'], row['source_sha256'])
                   for row in catalog.SUFFIX_HELD['entries'].values()}
        for filename, expected in sources:
            self.assertEqual(hashlib.sha256(Path(filename).read_bytes()).hexdigest(), expected)


if __name__ == '__main__':
    unittest.main()
