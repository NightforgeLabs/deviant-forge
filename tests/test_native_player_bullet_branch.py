"""Version-13 ordinary player direct bullet, pre-settlement only."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import native_direct_hit_graph as graph
import planned_advisor

TARGET_NODES = ('155','144','147','289','101','124','285','307','167')


def scenario(**changes):
    row = {'weapon_id':'weapon:aug-electron-cloud',
           'effect_scope':'ordinary_player_direct_bullet', 'attack':100,
           'attack_evidence':'caller_hypothesis',
           'final_skill_rate':1, 'final_keyword_damage_add_rate':0,
           'unit_part_weak_dam_rate':1, 'crit_addition':.5,
           'weakspot_addition':.3, 'final_element_type_dam_add_rate':1,
           'other_dam_rate':0, 'final_field_dam_add_rate':1,
           'dis_dam_rate':1, 'final_dam_add_rate':0,
           'final_special_regulate_factor':1, 'crit':True, 'weakspot':True,
           'use_final_dam_add_rate':True, 'use_final_ignore_dam_rate':True,
           'target_factor_nodes':{key:(.8 if key=='155' else 1) for key in TARGET_NODES},
           'rate_dictionary_state':'absent', 'rounding_model':'python_builtin_expected'}
    row.update(changes)
    return row


class NativePlayerBulletBranchTests(unittest.TestCase):
    def tearDown(self):
        graph.player_source.cache_clear()

    def test_native_terminal_vector_and_post_formula_boundary(self):
        result = graph.player_bullet_scenario(scenario())
        self.assertEqual(result['additional_product'],1.8)
        self.assertEqual(result['target_product'],.8)
        self.assertAlmostEqual(result['graph_final_attack'],144)
        self.assertEqual(result['formula_damage_hp_before_settlement'],144)
        self.assertIsNone(result['final_hp_loss'])
        self.assertEqual(result['attack_evidence'],'caller_hypothesis')
        self.assertFalse(result['game_verified'])
        self.assertIn('shield absorption',result['not_included'])
        self.assertEqual(result['source']['build'],'26267212')

    def test_guard_order_rate_dictionary_and_wrapper_minimum(self):
        no_add=graph.player_bullet_scenario(scenario(use_final_dam_add_rate=False))
        self.assertAlmostEqual(no_add['graph_final_attack'],80)
        no_ignore=graph.player_bullet_scenario(scenario(use_final_ignore_dam_rate=False))
        self.assertAlmostEqual(no_ignore['graph_final_attack'],180)
        rate=graph.player_bullet_scenario(scenario(rate_dictionary_state='present',rate=.5,formula_attack_type_rate=2))
        self.assertAlmostEqual(rate['rate_adjusted_attack'],144)
        minimum=graph.player_bullet_scenario(scenario(attack=.25,crit=False,weakspot=False,
            target_factor_nodes={key:1 for key in TARGET_NODES}))
        self.assertAlmostEqual(minimum['graph_final_attack'],.25)
        self.assertEqual(minimum['formula_damage_hp_before_settlement'],1)
        unknown_round=graph.player_bullet_scenario(scenario(rounding_model=None))
        self.assertIsNone(unknown_round['formula_damage_hp_before_settlement'])

    def test_item_tooltip_attack_scope_keeps_separate_combat_effects(self):
        item=graph.player_bullet_scenario(scenario(attack_value_origin='equipped_item_tooltip'))
        self.assertEqual(item['graph_final_attack'],144)
        self.assertFalse(item['attack_input_scope']['server_holder_equivalence_proven'])
        self.assertIn('already included item Attack affixes',item['attack_input_scope']['must_not_reapply'])
        self.assertIn('attached mod effects',item['attack_input_scope']['excludes'])
        mod=graph.player_bullet_scenario(scenario(attack_value_origin='equipped_item_tooltip',
                                                  final_keyword_damage_add_rate=.2))
        self.assertAlmostEqual(mod['graph_final_attack'],172.8)
        self.assertEqual(mod['crit_weakspot_factor'],1.8)
        preview=graph.player_bullet_scenario(scenario(attack_value_origin='blueprint_preview'))
        self.assertIn('owned item accessories, random and calibration affixes',preview['attack_input_scope']['excludes'])
        with self.assertRaisesRegex(ValueError,'not a verified holder'):
            graph.player_bullet_scenario(scenario(attack_value_origin='equipped_item_tooltip',
                                                 attack_evidence='verified_holder_property'))
        with self.assertRaisesRegex(ValueError,'not a verified holder'):
            graph.player_bullet_scenario(scenario(attack_value_origin='blueprint_preview',
                                                 attack_evidence='verified_holder_property'))
        with self.assertRaisesRegex(ValueError,'Attack value origin'):
            graph.player_bullet_scenario(scenario(attack_value_origin='direct_body_damage'))

    def test_settlement_order_zero_positive_and_outer_rate(self):
        target={key:1 for key in TARGET_NODES}
        zero=graph.player_bullet_scenario(scenario(attack=0, crit=False, weakspot=False,
            target_factor_nodes=target))
        self.assertEqual(0, zero['graph_final_attack'])
        self.assertEqual(0, zero['formula_damage_hp_before_settlement'])
        small=graph.player_bullet_scenario(scenario(attack=1.6, crit=False, weakspot=False,
            target_factor_nodes=target, rate_dictionary_state='present',rate=.5,
            formula_attack_type_rate=1))
        self.assertEqual(1.6, small['graph_final_attack'])
        self.assertEqual(.8, small['rate_adjusted_attack'])
        self.assertEqual(1, small['formula_damage_hp_before_settlement'])
        suppressed=graph.player_bullet_scenario(scenario(attack=20, crit=False, weakspot=False,
            target_factor_nodes=target, rate_dictionary_state='present',rate=0,
            formula_attack_type_rate=1))
        self.assertEqual(0, suppressed['formula_damage_hp_before_settlement'])
        self.assertIsNone(small['final_hp_loss'])

    def test_unknown_inputs_or_wrong_effect_scope_never_produce_total(self):
        missing=scenario()
        del missing['attack']
        result=graph.player_bullet_scenario(missing)
        self.assertEqual(result['status'],'missing_player_bullet_inputs')
        self.assertIn('attack',result['missing'])
        self.assertIsNone(result['graph_final_attack'])
        with self.assertRaisesRegex(ValueError,'ordinary direct bullet'):
            graph.player_bullet_scenario(scenario(effect_scope='status_tick'))
        with self.assertRaisesRegex(ValueError,'all nine'):
            graph.player_bullet_scenario(scenario(target_factor_nodes={'155':.8}))
        unknown_source=graph.player_bullet_scenario(scenario(attack_evidence=None))
        self.assertIn('attack_evidence: verified_holder_property or caller_hypothesis',unknown_source['missing'])
        with self.assertRaisesRegex(ValueError,'Absent rate dictionary'):
            graph.player_bullet_scenario(scenario(rate=.5))

    def test_build_compare_parity_without_equipped_attack_inference(self):
        left={'primary':{'catalog_id':'weapon:aug-electron-cloud','tier':5,'stars':5}}
        expected=planned_advisor.analyze(left,{'native_player_bullet_scenario':scenario()})
        self.assertEqual(expected['native_player_bullet_scenario']['graph_final_attack'],144)
        self.assertIsNone(expected['weapon_reference_timing']['native_attack_property']['equipped_attack'])
        self.assertEqual(expected['weapon_reference_timing']['native_attack_component']['value'],241.2)
        compared=planned_advisor.compare(left,left,{'native_player_bullet_scenario':scenario()})
        self.assertEqual(compared['left']['native_player_bullet_scenario'],expected['native_player_bullet_scenario'])
        self.assertEqual(compared['right']['native_player_bullet_scenario'],expected['native_player_bullet_scenario'])
        self.assertFalse(compared['winner_established'])
        with self.assertRaisesRegex(ValueError,'match the selected primary'):
            planned_advisor.analyze({'primary':{'catalog_id':'weapon:r500-memento'}},
                {'native_player_bullet_scenario':scenario()})

    def test_source_tamper_rejected(self):
        packet=json.loads(graph.PLAYER_TRACE.read_text())
        packet['terminal_equation']='attack+damage'
        with TemporaryDirectory() as temp:
            altered=Path(temp)/'trace.json'
            altered.write_text(json.dumps(packet))
            graph.player_source.cache_clear()
            with patch.object(graph,'PLAYER_TRACE',altered):
                with self.assertRaisesRegex(ValueError,'hash conflict'):
                    graph.player_source()


if __name__=='__main__':
    unittest.main()
