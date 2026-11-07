import copy
import unittest

import structured_compare


SHOES = 'mod:boots_mod:against-all-odds-deviant-energy'


class StructuredCompareTests(unittest.TestCase):
    def test_structured_evidence_policy_is_opt_in_and_unsaved(self):
        import copy
        import suffix_candidates
        profile = next(row for row in suffix_candidates.CANDIDATES.values()
                       if row['profile_status'] == 'candidate_complete'
                       and any(part['stat_type'] == 'weapon_damage_percent' for part in row['rows']))
        request = {'left': {'kind':'catalog','catalog_id':profile['catalog_id'],'level':profile['level']},
                   'right': {'kind':'catalog','catalog_id':profile['catalog_id'],'level':profile['level']}}
        before = copy.deepcopy(request)
        without = structured_compare.compare(request, [])
        request['context'] = {'suffix_candidate_opt_in':True}
        with_candidate = structured_compare.compare(request, [])
        self.assertIsNone(without['left']['suffix_candidate_profile'])
        self.assertEqual(with_candidate['left']['suffix_candidate_profile']['status'], 'candidate_complete')
        self.assertFalse(with_candidate['game_winner_established'])
        self.assertEqual(request['left'], before['left'])

    def test_exact_catalog_selection_uses_held_profile_without_ownership(self):
        request = {'left': {'kind': 'catalog', 'catalog_id': SHOES, 'level': 12},
                   'right': {'kind': 'catalog', 'catalog_id': SHOES, 'level': 12}}
        snapshot = copy.deepcopy(request)
        result = structured_compare.compare(request, [])
        self.assertEqual(request, snapshot)
        self.assertEqual(result['left']['evidence_audit']['items'][0]['binding_status'],
                         'verified_exact_catalog_profile')
        self.assertEqual([row['value_percent'] for row in result['left']['trace'] if row.get('value_percent')],
                         [6.4, 3.6, 7.2, 3.0])
        self.assertTrue(result['selection_metadata']['read_only'])
        self.assertFalse(result['game_winner_established'])

    def test_saved_plan_is_read_only_and_action_ordered(self):
        plan = {'id': 'plan-1', 'name': 'Test plan', 'slots': {
            'bottoms': {'mod_id': 'mod:pants_mod:abnormal-increase', 'mod_level': 10},
            'top': {'mod_id': 'mod:chest_mod:ardent-shield-battle', 'mod_level': 8},
            'shoes': {'mod_id': SHOES, 'mod_level': 12},
            'gloves': {'mod_id': 'mod:gloves_mod:crit-amplifier', 'mod_level': 10},
            'mask': {'mod_id': 'mod:mask_mod:blaze-amplifier', 'mod_level': 10},
            'helmet': {'mod_id': 'mod:helmet_mod:deviation-expert', 'mod_level': 10}}}
        snapshot = copy.deepcopy(plan)
        result = structured_compare.compare(
            {'left': {'kind': 'planned_build', 'planned_build_id': 'plan-1'},
             'right': {'kind': 'catalog', 'catalog_id': SHOES, 'level': 12}}, [plan])
        self.assertEqual(plan, snapshot)
        self.assertEqual([row['catalog_id'] for row in result['left']['evidence_audit']['items']],
                         ['mod:helmet_mod:deviation-expert', 'mod:mask_mod:blaze-amplifier',
                          'mod:gloves_mod:crit-amplifier', SHOES,
                          'mod:chest_mod:ardent-shield-battle', 'mod:pants_mod:abnormal-increase'])
        self.assertEqual(result['selection_metadata']['left']['kind'], 'planned_build')
        self.assertIn('hypothetical', result['selection_metadata']['left']['note'])

    def test_saved_plan_uses_same_opt_in_suffix_policy(self):
        plan = {'id':'candidate-plan', 'name':'Candidate plan', 'slots': {
            'helmet': {'mod_id':'mod:helmet_mod:elemental-havoc-lunar', 'mod_level':10}}}
        before = copy.deepcopy(plan)
        request = {'left': {'kind':'planned_build','planned_build_id':'candidate-plan'},
                   'right': {'kind':'catalog','catalog_id':SHOES,'level':12}}
        off = structured_compare.compare(request, [plan])
        request['context'] = {'suffix_candidate_opt_in':True}
        on = structured_compare.compare(request, [plan])
        self.assertFalse(off['left']['suffix_candidate_profiles'])
        self.assertEqual(on['left']['suffix_candidate_profiles'][0]['status'], 'candidate_complete')
        self.assertEqual(plan, before)

    def test_missing_or_invalid_selection_stops_before_modeling(self):
        right = {'kind': 'catalog', 'catalog_id': SHOES, 'level': 12}
        for left in ({'kind': 'catalog', 'catalog_id': SHOES},
                     {'kind': 'catalog', 'catalog_id': SHOES, 'level': 18},
                     {'kind': 'catalog', 'catalog_id': 'mod:missing', 'level': 12},
                     {'kind': 'planned_build', 'planned_build_id': 'missing'}):
            with self.assertRaises(ValueError):
                structured_compare.compare({'left': left, 'right': right}, [])


if __name__ == '__main__':
    unittest.main()
