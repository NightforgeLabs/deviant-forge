"""Source-typed DOT bucket math remains a controlled component, not proc DPS."""
import hashlib
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen

import native_dot_modifier_buckets as dot
import native_aug_surge_input as aug
import server


def scenario(rows=None):
    return {'property_source_build': '26267212', 'formula_attack_type': 4,
            'attack_is_buff': True, 'active_affixes_complete': True,
            'other_property_contributions_zero': True,
            'controlled_graph_base': 100,
            'active_affixes': rows if rows is not None else [
                {'source_id': 'mod-one', 'affix_id': 'E4300', 'value': .1, 'active': True},
                {'source_id': 'mod-two', 'affix_id': 'E4300', 'value': .2, 'active': True}]}


class DotBucketsTests(unittest.TestCase):
    def tearDown(self):
        dot.proof.cache_clear()
        aug.proof.cache_clear()

    def test_same_property_adds_before_graph(self):
        result = dot.calculate(scenario())
        self.assertAlmostEqual(result['typed_property_additions']['dot_attack_type'], .3)
        self.assertAlmostEqual(result['controlled_base_after_dot_factor_pre_round'], 130)
        self.assertNotEqual(result['controlled_base_after_dot_factor_pre_round'], 132)
        self.assertIsNone(result['actual_proc_damage'])
        self.assertIsNone(result['full_build_dps'])

    def test_element_and_keyword_are_typed_but_not_applied_to_aug(self):
        rows = scenario()['active_affixes'] + [
            {'source_id': 'element', 'affix_id': 'E3400', 'value': .4, 'active': True},
            {'source_id': 'keyword', 'affix_id': 'E12100', 'value': .5, 'active': True}]
        result = dot.calculate(scenario(rows))
        self.assertAlmostEqual(result['controlled_base_after_dot_factor_pre_round'], 130)
        self.assertFalse(result['lightning_element_factor_applied'])
        self.assertFalse(result['surge_keyword_factor_applied'])
        self.assertEqual(len(result['missing_joins']), 2)
        self.assertEqual(result['native_tag_names'],
                         {'element_type_3': 'lightning', 'keyword_302': 'surge'})

    def test_explicit_element_leaf_only_and_aug_metadata(self):
        rows = scenario()['active_affixes'] + [
            {'source_id': 'element', 'affix_id': 'E3400', 'value': .4, 'active': True}]
        controlled = dot.calculate({**scenario(rows), 'event_element_type_leaf': 3,
                                    'event_element_type_leaf_source': 'explicit_synthetic'})
        self.assertTrue(controlled['lightning_element_factor_applied'])
        self.assertAlmostEqual(controlled['controlled_base_after_dot_and_element_pre_round'], 182)
        self.assertFalse(controlled['surge_keyword_factor_applied'])
        self.assertIsNone(controlled['actual_proc_damage'])
        with self.assertRaisesRegex(ValueError, 'explicitly sourced'):
            dot.calculate({**scenario(rows), 'event_element_type_leaf': 3})
        input_values = {'property_source_build': '26267212', 'weapon_blueprint_id': 13451401,
                        'fixed_skill_id': 'WS15704', 'graph_branch': 'node129',
                        'graph_inputs_explicit': True, 'skill_power': 100,
                        'skill_power_origin': 'explicit_synthetic',
                        'skill_dam_base_dam_surge': .5, 'dam_up': 0, 'pvp_ratio': 1}
        aug_result = aug.calculate(input_values)
        self.assertEqual((aug_result['element_label'], aug_result['configured_keyword_label']),
                         ('lightning', 'surge'))
        self.assertFalse(aug_result['keyword_type_leaf_established'])
        self.assertIsNone(aug_result['actual_proc_damage'])

    def test_incomplete_or_inactive_withholds_and_invalid_source_rejected(self):
        self.assertIsNone(dot.calculate({**scenario(), 'active_affixes_complete': False})[
            'controlled_base_after_dot_factor_pre_round'])
        rows = scenario()['active_affixes']
        self.assertIsNone(dot.calculate(scenario([{**rows[0], 'active': False}]))[
            'controlled_base_after_dot_factor_pre_round'])
        with self.assertRaisesRegex(ValueError, 'unique'):
            dot.calculate(scenario([rows[0], rows[0]]))
        with self.assertRaisesRegex(ValueError, 'known exact'):
            dot.calculate(scenario([{**rows[0], 'affix_id': 'E9999'}]))
        with self.assertRaisesRegex(ValueError, 'bounds'):
            dot.calculate(scenario([{**rows[0], 'value': 11}]))

    def test_pinned_source_and_read_only_api(self):
        with TemporaryDirectory() as temp:
            folder = Path(temp)
            for name in dot.HASHES:
                (folder / name).write_bytes((dot.ROOT / name).read_bytes())
            (folder / 'native-dot-modifier-buckets-v1.md').write_text('changed')
            dot.proof.cache_clear()
            with patch.object(dot, 'ROOT', folder):
                with self.assertRaisesRegex(ValueError, 'hash conflict'):
                    dot.proof()
        dot.proof.cache_clear()
        with TemporaryDirectory() as temp:
            database = Path(temp) / 'advisor.sqlite3'
            database.write_bytes(b'unchanged sentinel')
            before = hashlib.sha256(database.read_bytes()).hexdigest()
            with patch.object(server, 'DB', database):
                http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
                worker = threading.Thread(target=http.serve_forever, daemon=True)
                worker.start()
                try:
                    request = Request(f'http://127.0.0.1:{http.server_address[1]}/api/native-dot-modifier-buckets',
                                      data=json.dumps(scenario()).encode(),
                                      headers={'Content-Type': 'application/json'})
                    with urlopen(request) as response:
                        result = json.load(response)
                    self.assertAlmostEqual(result['controlled_base_after_dot_factor_pre_round'], 130)
                    self.assertIsNone(result['actual_proc_damage'])
                finally:
                    http.shutdown()
                    worker.join()
                    http.server_close()
            self.assertEqual(before, hashlib.sha256(database.read_bytes()).hexdigest())
