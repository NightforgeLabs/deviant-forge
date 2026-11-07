"""D01 typed Attack source, ordering and incomplete-equipped gates."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import native_attack_accumulator as attack
import planned_advisor


class NativeAttackAccumulatorTest(unittest.TestCase):
    def tearDown(self):
        attack.source.cache_clear()
        attack.source_scope.cache_clear()

    def test_source_binding_and_default_order(self):
        proof = attack.source()
        self.assertEqual(proof['property_name'], 'attack')
        self.assertEqual(proof['absolute_affix'], 'D0100')
        result = attack.project({'initial_attack': 100, 'changes': [
            {'source_id': 'weapon', 'affix_id': 'D0100', 'value': 20},
            {'source_id': 'buff', 'affix_id': 'D0100', 'value': -5},
            {'source_id': 'rate', 'affix_id': 'D0101', 'value': .1},
        ], 'all_active_sources_known': True, 'set_override': False,
            'independent_effect': False, 'bound_override': False})
        self.assertEqual(result['known_absolute_sum'], 15)
        self.assertAlmostEqual(result['value_before_bounds'], 126.5)
        self.assertTrue(result['scenario_only'])
        self.assertFalse(result['equipped_attack_verified'])

    def test_unknown_source_and_special_branches_withhold_property(self):
        base = {'initial_attack': 100, 'changes': [{'source_id':'a','affix_id':'D0100','value':20}]}
        partial = attack.project(base)
        self.assertIsNone(partial['value_before_bounds'])
        self.assertEqual(partial['conditional_prebound'], 120)
        self.assertIn('complete active affix, calibration, buff and equipment source map', partial['missing'])
        for key in ('set_override', 'independent_effect', 'bound_override'):
            scenario = {**base, 'all_active_sources_known': True, 'set_override': False,
                        'independent_effect': False, 'bound_override': False, key: True}
            self.assertIsNone(attack.project(scenario)['value_before_bounds'])

    def test_wrong_bucket_duplicate_or_untyped_value_rejected(self):
        for row in ({'source_id':'weapon','affix_id':'D1100','value':20},
                    {'source_id':'weapon','affix_id':'Weapon DMG','value':.2},
                    {'source_id':'weapon','affix_id':'D0100','value':float('nan')}):
            with self.subTest(row=row), self.assertRaises(ValueError):
                attack.project({'initial_attack':100,'changes':[row]})
        with self.assertRaisesRegex(ValueError, 'must be unique'):
            attack.project({'initial_attack':100,'changes':[
                {'source_id':'same','affix_id':'D0100','value':10},
                {'source_id':'same','affix_id':'D0100','value':.1}]})
        shared_source = attack.project({'initial_attack':100,'changes':[
            {'source_id':'same','affix_id':'D0100','value':10},
            {'source_id':'same','affix_id':'D0101','value':.1}]})
        self.assertAlmostEqual(shared_source['conditional_prebound'],121)

    def test_selected_build_and_compare_do_not_promote_native_base(self):
        left = {'primary':{'catalog_id':'weapon:aug-electron-cloud','tier':5,'stars':5,
                           'calibration_profile':{'style':'Energy Style','rolls':[{'stat':'Crit DMG','value_percent':10}]}}}
        right = {'primary':{'catalog_id':'weapon:r500-memento','tier':1,'stars':4}}
        a = planned_advisor.analyze(left)['weapon_reference_timing']
        self.assertEqual(a['native_attack_component']['value'], 241.2)
        self.assertEqual(a['native_attack_property']['native_base_weapon_component'], 241.2)
        self.assertIsNone(a['native_attack_property']['equipped_attack'])
        scope = a['native_attack_property']['producer_scope']
        self.assertEqual(scope['origin_rows_checked'], 480)
        self.assertEqual(scope['ordinary_origin_D0100_rows'], 0)
        self.assertTrue(scope['observed_gun_origin_helper_injects_given_only'])
        self.assertTrue(scope['calibration_generation_is_not_activation'])
        self.assertIn('D1100', scope['origin_affix_ids'])
        self.assertNotIn('D0100', scope['origin_affix_ids'])
        b = planned_advisor.compare(left,right)
        self.assertEqual(b['left']['weapon_reference_timing']['native_attack_property'], a['native_attack_property'])
        self.assertIsNone(b['right']['weapon_reference_timing']['native_attack_property']['equipped_attack'])
        self.assertFalse(b['winner_established'])
        scenario = {'native_attack_affix_scenario': {'initial_attack':100,
            'changes':[{'source_id':'manual-absolute','affix_id':'D0100','value':20}],
            'all_active_sources_known': True, 'set_override': False,
            'independent_effect':False,'bound_override':False}}
        modeled = planned_advisor.analyze(left, scenario)['weapon_reference_timing']['native_attack_property']
        self.assertEqual(modeled['attack_property_scenario']['value_before_bounds'],120)
        self.assertIsNone(modeled['equipped_attack'])

    def test_given_item_injection_is_not_ordinary_planned_attack(self):
        native = {'value': 241.2, 'source_method': {'method':'get_gun_omg_value'}}
        ordinary = attack.selected(native)
        self.assertIsNone(ordinary['equipped_attack'])
        self.assertIsNone(ordinary['attack_property_scenario'])
        self.assertEqual(ordinary['producer_scope']['ordinary_origin_D0100_rows'],0)
        self.assertTrue(ordinary['producer_scope']['observed_gun_origin_helper_injects_given_only'])

    def test_tampered_packet_rejected_even_with_changed_file_hash(self):
        source = attack.ROOT / 'native-attack-affix-types-v1.json'
        packet = json.loads(source.read_text())
        packet['rows']['D0100']['fields']['attr_id']['decoded_value'] = 'D11'
        with TemporaryDirectory() as temp:
            root = Path(temp)
            for name in attack.SOURCES:
                (root/name).write_bytes((attack.ROOT/name).read_bytes())
            (root/source.name).write_text(json.dumps(packet))
            import hashlib
            fake = {**attack.SOURCES, source.name: hashlib.sha256((root/source.name).read_bytes()).hexdigest()}
            attack.source.cache_clear()
            with patch.object(attack,'ROOT',root),patch.object(attack,'SOURCES',fake):
                with self.assertRaisesRegex(ValueError,'binding conflict'):
                    attack.source()


if __name__ == '__main__':
    unittest.main()
