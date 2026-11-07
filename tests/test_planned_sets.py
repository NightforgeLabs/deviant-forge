import unittest
from unittest.mock import patch

import combat_formula


def request(**changes):
    data={'baseline':{'damage':251,'crit_rate':.10,'crit_damage_bonus':.25,
                      'source_ref':'dated unsaved catalog estimate'},
          'landed_body_hits':40,'psi_intensity':None,'orb_enemy_hits':None,
          'hp_percent':None,'savior_shield':'unknown','elemental_model':'shared_bucket',
          'pre_effect_reload_seconds':None,'pieces_per_alternative':2,
          'set_a':'bastille','set_b':'treacherous_tides'}
    data.update(changes)
    return data


class PlannedSetsTests(unittest.TestCase):
    def test_strict_hp_boundaries_and_known_reload_survive_unknown_hp(self):
        unknown=combat_formula.compare_reference_sets(request())
        self.assertIsNone(unknown['hp_percent'])
        self.assertIsNone(unknown['a']['selected_bullet_component'])
        self.assertIsNone(unknown['b']['selected_bullet_component'])
        self.assertEqual(unknown['a']['reload_efficiency_percent'],15)
        self.assertIsNone(unknown['delta_b_minus_a_bullets'])
        at_zero=combat_formula.compare_reference_sets(request(hp_percent=0))
        self.assertEqual(at_zero['a']['weapon_damage_percent'],0)
        self.assertEqual(at_zero['b']['weapon_damage_percent'],12)
        below=combat_formula.compare_reference_sets(request(hp_percent=69.999))
        self.assertEqual((below['a']['weapon_damage_percent'],below['b']['weapon_damage_percent']),(0,12))
        exact=combat_formula.compare_reference_sets(request(hp_percent=70))
        self.assertEqual((exact['a']['weapon_damage_percent'],exact['b']['weapon_damage_percent']),(0,0))
        self.assertEqual(exact['delta_b_minus_a_bullets'],0)
        above=combat_formula.compare_reference_sets(request(hp_percent=70.001))
        self.assertEqual((above['a']['weapon_damage_percent'],above['b']['weapon_damage_percent']),(10,0))
        self.assertAlmostEqual(above['a']['selected_bullet_component'],11320.1)
        self.assertAlmostEqual(at_zero['b']['selected_bullet_component'],11525.92)
        entered=combat_formula.compare_reference_sets(request(hp_percent=None,pre_effect_reload_seconds=2))
        self.assertAlmostEqual(entered['a']['reload_seconds_if_entered'],2/1.15)
        self.assertEqual(entered['b']['reload_seconds_if_entered'],2)

    def test_shield_states_and_source_qualified_status_bucket(self):
        uncertain=combat_formula.compare_reference_sets(request(set_a='shelterer',set_b='savior'))
        self.assertAlmostEqual(uncertain['a']['selected_bullet_component'],10291)
        self.assertIsNone(uncertain['b']['selected_bullet_component'])
        self.assertIsNone(uncertain['b']['status_damage_percent'])
        self.assertIn('catalog',uncertain['a']['evidence'][0])
        self.assertIn('official',uncertain['b']['evidence'][0])
        off=combat_formula.compare_reference_sets(request(set_a='shelterer',set_b='savior',savior_shield='inactive'))
        on=combat_formula.compare_reference_sets(request(set_a='shelterer',set_b='savior',savior_shield='active'))
        self.assertEqual(off['b']['weapon_damage_percent'],0)
        self.assertEqual(off['b']['status_damage_percent'],0)
        self.assertEqual(on['b']['weapon_damage_percent'],10)
        self.assertEqual(on['b']['status_damage_percent'],10)
        self.assertAlmostEqual(on['b']['selected_bullet_component'],11320.1)
        self.assertAlmostEqual(on['b']['power_surge_damage_per_psi'],8.58)
        self.assertAlmostEqual(on['a']['power_surge_damage_per_psi'],8.28)
        separate=combat_formula.compare_reference_sets(request(set_a='shelterer',set_b='savior',savior_shield='active',elemental_model='separate_factors'))
        self.assertAlmostEqual(separate['a']['power_surge_damage_per_psi'],8.424)
        self.assertAlmostEqual(separate['b']['power_surge_damage_per_psi'],8.58)

    def test_same_choice_tie_and_swap_reverses_shared_context_delta(self):
        first=combat_formula.compare_reference_sets(request(hp_percent=69.999))
        reversed_=combat_formula.compare_reference_sets(request(hp_percent=69.999,set_a='treacherous_tides',set_b='bastille'))
        self.assertAlmostEqual(reversed_['delta_b_minus_a_bullets'],-first['delta_b_minus_a_bullets'])
        same=combat_formula.compare_reference_sets(request(set_a='savior',set_b='savior'))
        self.assertTrue(same['identical_choice'])
        self.assertIsNone(same['a']['selected_bullet_component'])
        self.assertEqual(same['a']['unresolved_conditions'],same['b']['unresolved_conditions'])
        self.assertFalse(first['complete_game_prediction'])
        self.assertEqual(first['a']['piece_count'],2)
        self.assertEqual(first['b']['piece_count'],2)

    def test_exact_piece_count_and_hp_domain(self):
        with self.assertRaisesRegex(ValueError,'exactly two'):
            combat_formula.compare_reference_sets(request(pieces_per_alternative=3))
        with self.assertRaisesRegex(ValueError,'supported range'):
            combat_formula.compare_reference_sets(request(hp_percent=100.001))
        with self.assertRaisesRegex(ValueError,'supported'):
            combat_formula.compare_reference_sets(request(set_a='unknown_set'))

    def test_api_is_read_only_and_keeps_both_choices(self):
        import server
        fake=object.__new__(server.Handler)
        fake.path='/api/planned-set-compare'
        fake.body=lambda _max:request(hp_percent=70.001)
        fake.respond=lambda body,status=200:(status,body)
        with patch.object(server,'inventory',side_effect=AssertionError('inventory accessed')), \
             patch.object(server,'planned_builds',side_effect=AssertionError('plans accessed')):
            status,body=server.Handler.do_POST(fake)
        self.assertEqual(status,200)
        self.assertEqual((body['result']['set_a'],body['result']['set_b']),('bastille','treacherous_tides'))
        self.assertFalse(body['saved'])
        self.assertFalse(body['ownership_required'])


if __name__=='__main__':unittest.main()
