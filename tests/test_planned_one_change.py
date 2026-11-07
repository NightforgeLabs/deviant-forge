import unittest
from contextlib import nullcontext
from unittest.mock import patch

import planned_one_change
import combat_formula


BASE = {'base_origin': 'pre_mod_unbuffed', 'damage': 100, 'rpm': 720,
        'magazine': 40, 'crit_rate': .10, 'crit_damage_bonus': .25,
        'weakspot_damage_bonus': .60}
ENCOUNTER = {'pre_mod_reload_seconds': 2, 'hit_rate': 1, 'dodge_fraction': 0,
             'weakspot_fraction': 0, 'crit_weak_overlap': 0,
             'accepted_energy_returns_per_second': 0}


def entered(value, *, stat='weapon_damage_percent', name='One roll'):
    return {'kind': 'entered_row', 'name': name, 'stat_type': stat,
            'value_percent': value, 'source_note': 'Isolated observed-row test'}


def payload(a=None, b=None):
    return {'calibration': 'energy', 'assume_rows_active': True,
            'baseline': dict(BASE), 'encounter': dict(ENCOUNTER),
            'a': a or entered(10, name='A'), 'b': b or entered(20, name='B')}


class PlannedOneChangeTests(unittest.TestCase):
    def test_replacement_reversal_tie_and_shared_baseline(self):
        original = planned_one_change.compare(payload())
        a, b = original['a'], original['b']
        self.assertAlmostEqual(a['expected_landed_hit'], 100 * 1.10 * 1.524 * 1.025)
        self.assertAlmostEqual(b['expected_landed_hit'], 100 * 1.10 * 1.624 * 1.025)
        self.assertAlmostEqual(original['delta_b_minus_a_direct_hit'], 100 * 1.10 * .10)
        self.assertEqual(original['bullet_component_leader'], 'b')
        self.assertFalse(original['ownership_required'])
        self.assertFalse(original['complete_game_prediction'])
        reverse = planned_one_change.compare(payload(entered(20), entered(10)))
        self.assertAlmostEqual(reverse['delta_b_minus_a_bullet_60s'],
                               -original['delta_b_minus_a_bullet_60s'])
        self.assertEqual(reverse['bullet_component_leader'], 'a')
        tie = planned_one_change.compare(payload(entered(10), entered(10)))
        self.assertEqual(tie['bullet_component_leader'], 'tie')
        changed = payload()
        changed['baseline']['damage'] = 200
        doubled = planned_one_change.compare(changed)
        self.assertAlmostEqual(doubled['delta_b_minus_a_bullet_60s'],
                               2 * original['delta_b_minus_a_bullet_60s'])
        self.assertEqual(doubled['a']['stat_type'], original['a']['stat_type'])

    def test_unknown_activation_or_rule_is_not_zero_or_a_winner(self):
        unknown = payload(entered(10), entered(20))
        unknown['assume_rows_active'] = False
        result = planned_one_change.compare(unknown)
        self.assertTrue(result['a']['unresolved_roll'])
        self.assertIsNone(result['delta_b_minus_a_bullet_60s'])
        self.assertIsNone(result['bullet_component_leader'])
        unsupported = planned_one_change.compare(payload(entered(10),
            {'kind': 'entered_row', 'name': 'Unverified proc', 'stat_type': 'other_unmodeled',
             'value_percent': None, 'source_note': 'Tooltip has no usable rule'}))
        self.assertTrue(unsupported['b']['unresolved_roll'])
        self.assertIsNone(unsupported['delta_b_minus_a_direct_hit'])
        self.assertIsNone(unsupported['bullet_component_leader'])
        no_roll = planned_one_change.compare(payload({'kind': 'none'}, {'kind': 'none'}))
        self.assertFalse(no_roll['a']['unresolved_roll'])
        self.assertEqual(no_roll['bullet_component_leader'], 'tie')
        status = planned_one_change.compare(payload(entered(10), entered(20, stat='status_damage_percent')))
        self.assertIsNone(status['bullet_component_leader'])
        self.assertIn('status_damage_percent', status['unscored_component_types'])

    def test_weakspot_row_is_not_a_whole_item_tie_in_body_hit_encounter(self):
        result = planned_one_change.compare(payload({'kind': 'none'},
            entered(20, stat='weakspot_damage_percent')))
        self.assertEqual(result['delta_b_minus_a_bullet_60s'], 0)
        self.assertIsNone(result['bullet_component_leader'])
        self.assertIn('weakspot_damage_percent', result['unscored_component_types'])
        self.assertIn('weakspot share 0', result['scope'])

    def test_reviewed_row_uses_exact_identity_level_and_new_player_does_not_own(self):
        seen = []
        def reviewed(_connection, profile, catalog_id, level, shiny):
            seen.append((profile, catalog_id, level, shiny))
            return {'name': 'Test mod', 'variant': 'Violent', 'reviewed_source_frame': 'checked-frame.png',
                    'reviewed_exact_rows': [{'row_index': 0, 'stat_type': 'weapon_damage_percent',
                                             'value': 5, 'confidence': 'source_checked',
                                             'calculation_status': 'assumption_scenario'}]}
        spec = {'kind': 'reviewed_row', 'catalog_id': 'mod:top:test-violent', 'level': 8, 'row_index': 0}
        with patch.object(planned_one_change.field_guide_profiles, 'preview', side_effect=reviewed):
            result = planned_one_change.compare(payload({'kind': 'none'}, spec), object())
        self.assertEqual(seen, [('new_player', 'mod:top:test-violent', 8, 'unknown')])
        self.assertEqual(result['b']['value_percent'], 5)
        self.assertGreater(result['delta_b_minus_a_bullet_60s'], 0)
        self.assertIn('Other rows and the mod core', result['b']['unknowns'][0])
        with patch.object(planned_one_change.field_guide_profiles, 'preview', return_value={
                'name': 'Test mod', 'variant': 'Violent', 'reviewed_exact_rows': []}):
            with self.assertRaisesRegex(ValueError, 'no usable reviewed'):
                planned_one_change.compare(payload({'kind': 'none'}, spec), object())
        with patch.object(planned_one_change.field_guide_profiles, 'preview', return_value={
                'name': 'Test mod', 'variant': 'Violent', 'rank_derived': True,
                'reviewed_exact_rows': [{'row_index': 0, 'stat_type': 'weapon_damage_percent',
                                         'value': 5, 'confidence': 'source_checked',
                                         'calculation_status': 'assumption_scenario'}]}):
            with self.assertRaisesRegex(ValueError, 'rank-derived'):
                planned_one_change.compare(payload({'kind': 'none'}, spec), object())

    def test_baseline_provenance_and_invalid_manual_values(self):
        data = payload()
        data['baseline']['base_origin'] = 'observed_equipped'
        with self.assertRaisesRegex(ValueError, 'pre-mod'):
            planned_one_change.compare(data)
        for value in (float('inf'), -1, None):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'finite percentage'):
                planned_one_change.compare(payload(entered(value), entered(20)))

    def test_manual_row_stays_user_entered_even_when_modeled(self):
        original = combat_formula.compare
        seen = []
        def capture(baseline, modifiers, encounter, proc, orb):
            seen.extend(modifiers)
            return original(baseline, modifiers, encounter, proc, orb)
        with patch.object(planned_one_change.combat_formula, 'compare', side_effect=capture):
            planned_one_change.compare(payload())
        self.assertEqual(len(seen), 2)
        self.assertTrue(all(row['confidence'] == 'user_entered_hypothetical' for row in seen))
        self.assertTrue(all(row['external_hypothesis_confirmed'] is True for row in seen))

    def test_api_handler_uses_read_only_generic_engine_without_inventory(self):
        import server
        fake = object.__new__(server.Handler)
        fake.path = '/api/planned-one-change'
        fake.body = lambda _max: payload()
        fake.respond = lambda result, status=200: (status, result)
        with patch.object(server, 'connect', return_value=nullcontext(None)), \
             patch.object(server, 'inventory', side_effect=AssertionError('inventory accessed')), \
             patch.object(server, 'planned_builds', side_effect=AssertionError('plans accessed')):
            status, response = server.Handler.do_POST(fake)
        self.assertEqual(status, 200)
        self.assertEqual(response['bullet_component_leader'], 'b')
        self.assertAlmostEqual(response['delta_b_minus_a_direct_hit'], 11)
        self.assertFalse(response['saved'])


if __name__ == '__main__':
    unittest.main()
