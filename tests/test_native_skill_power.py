"""Native D41 arithmetic, source buckets and controlled AUG graph input."""
import hashlib
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen

import native_skill_power as psi
import native_aug_surge_input as aug
import native_player_hit_replay as player_hit
import server
from tests.test_native_player_hit_replay import case as player_case


def case(name):
    packet = json.loads((psi.ROOT / 'native-skill-power-v1-vectors.json').read_text())
    row = next(row for row in packet['synthetic_vectors'] if row['name'] == name)
    return {**row['inputs'], 'property_source_build': '26267212',
            'property_id': 'D41', 'base_initial_source': 'explicit_synthetic',
            'channel_values_explicit': True,
            'active_source_map_complete': True}, row


def aug_values(skill_inputs):
    return {'property_source_build': '26267212',
            'weapon_blueprint_id': 13451401, 'fixed_skill_id': 'WS15704',
            'graph_branch': 'node129', 'graph_inputs_explicit': True,
            'skill_power_inputs': skill_inputs,
            'skill_dam_base_dam_surge': .5, 'dam_up': 0,
            'pvp_ratio': 1}


class NativeSkillPowerTests(unittest.TestCase):
    def tearDown(self):
        psi.proof.cache_clear()
        aug.proof.cache_clear()

    def test_all_six_source_vectors_and_source_buckets(self):
        names = ('conditional_stock_armor_only', 'synthetic_init_and_other',
                 'synthetic_init_independent', 'synthetic_other_independent',
                 'synthetic_set_override', 'synthetic_ceiling')
        for name in names:
            given, expected = case(name)
            with self.subTest(name=name):
                actual = psi.calculate(given)
                self.assertEqual(actual['initial_skill_power'], expected['calculated_init'])
                self.assertEqual(actual['raw_skill_power'], expected['raw'])
                self.assertEqual(actual['stored_skill_power'], expected['stored_skill_power'])
                self.assertFalse(actual['active_holder_total_established'])
        for source_type, bucket in [('EQUIP', 'INIT'), ('BUFF', 'OTHER'),
                                    ('PASSIVE', 'OTHER'), ('MOD', 'OTHER')]:
            self.assertEqual(psi.source_bucket(source_type), bucket)
        self.assertIsNone(psi.source_bucket('unidentified'))

    def test_missing_channels_set_zero_and_invalid_values(self):
        given, _ = case('conditional_stock_armor_only')
        for change in ({'active_source_map_complete': False},
                       {'base_initial_source': 'guessed'},
                       {'property_id': 'D01'}):
            with self.subTest(change=change):
                self.assertIsNone(psi.calculate({**given, **change})['stored_skill_power'])
        self.assertEqual(psi.calculate({**given, 'set_value': 0})['stored_skill_power'], 0)
        with self.assertRaises(ValueError):
            psi.calculate({**given, 'other_rate': float('nan')})

    def test_conditional_armor_psi_feeds_aug_configured_input_only(self):
        given, _ = case('conditional_stock_armor_only')
        result = aug.calculate(aug_values(given))
        self.assertEqual(result['skill_power_input'], 115)
        self.assertEqual(result['configured_attack_value'], 57.5)
        self.assertIsNone(result['actual_proc_damage'])
        self.assertIsNone(result['damage_packets'])
        self.assertIsNone(result['full_build_dps'])
        self.assertEqual((result['configured_formula_attack_type'],
                          result['configured_formula_attack_type_code'],
                          result['configured_keyword_code']), ('Dot', 4, 302))
        self.assertFalse(result['automatic_weak_body_flag_for_dot'])
        self.assertIsNone(result['weakspot_eligibility'])
        self.assertIsNone(result['crit_eligibility'])
        self.assertIsNone(result['damage_class'])
        self.assertFalse(result['attack_value_to_hit_info_bridge_established'])
        missing = aug.calculate(aug_values({**given, 'active_source_map_complete': False}))
        self.assertIsNone(missing['configured_attack_value'])
        wrong = aug.calculate({**aug_values(given), 'weapon_blueprint_id': 13451402})
        self.assertIsNone(wrong['configured_attack_value'])

    def test_two_stage_vector_requires_independent_hit_bridge_assumption(self):
        supplied = aug_values(case('conditional_stock_armor_only')[0])
        supplied.pop('skill_power_inputs')
        configured = aug.calculate({**supplied, 'skill_power': 100,
                                    'skill_power_origin': 'explicit_synthetic'})
        self.assertEqual(configured['configured_attack_value'], 50)
        self.assertIsNone(configured['actual_proc_damage'])
        # This 50-point post-graph hit is supplied separately. The AUG
        # executor's attack_value -> hit_info bridge is not established.
        target, _ = player_case('unshielded_partial_hp')
        settled = player_hit.replay({**target, 'post_graph_damage': 50})
        self.assertEqual((settled['holder_hp_after'], settled['actual_hp_damage']), (50, 50))

    def test_source_hash_tamper_and_read_only_apis(self):
        with TemporaryDirectory() as temp:
            folder = Path(temp)
            for name in psi.HASHES:
                (folder / name).write_bytes((psi.ROOT / name).read_bytes())
            (folder / 'native-skill-power-v1.md').write_text('changed')
            psi.proof.cache_clear()
            with patch.object(psi, 'ROOT', folder):
                with self.assertRaisesRegex(ValueError, 'hash conflict'):
                    psi.proof()
        given, _ = case('conditional_stock_armor_only')
        with TemporaryDirectory() as temp:
            database = Path(temp) / 'advisor.sqlite3'
            database.write_bytes(b'unchanged sentinel')
            before = hashlib.sha256(database.read_bytes()).hexdigest()
            with patch.object(server, 'DB', database):
                http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
                worker = threading.Thread(target=http.serve_forever, daemon=True)
                worker.start()
                try:
                    for route, data, field, expected in (
                            ('native-skill-power', given, 'stored_skill_power', 115),
                            ('native-aug-configured-input', aug_values(given),
                             'configured_attack_value', 57.5)):
                        request = Request(f'http://127.0.0.1:{http.server_address[1]}/api/{route}',
                                          data=json.dumps(data).encode(),
                                          headers={'Content-Type': 'application/json'})
                        with urlopen(request, timeout=5) as response:
                            result = json.load(response)
                        self.assertEqual(result[field], expected)
                    self.assertEqual(hashlib.sha256(database.read_bytes()).hexdigest(), before)
                finally:
                    http.shutdown()
                    http.server_close()
