"""Controlled native DOT/lightning factor and target reduction ordering."""
import hashlib
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen

import native_lightning_dot_hit as hit
import server


def source_case(index):
    packet = json.loads((hit.ROOT / 'native-lightning-dot-factors-v1.json').read_text())
    row = packet['synthetic_explicit_leaf_vectors'][index]
    return {**row['inputs'], 'property_source_build': '26267212',
            'formula_attack_type': 4, 'element_type_leaf': 3,
            'leaves_source': 'explicit_synthetic',
            'all_other_graph_factors_unity': True,
            'final_damage_switch': 1, 'final_ignore_switch': 1}, row


class LightningDotHitTests(unittest.TestCase):
    def tearDown(self):
        hit.proof.cache_clear()

    def test_two_native_vectors_and_separate_reductions(self):
        for index in (0, 1):
            given, expected = source_case(index)
            with self.subTest(index=index):
                actual = hit.calculate(given)
                self.assertAlmostEqual(actual['graph_pre_round'], expected['graph_pre_round'])
                self.assertEqual(actual['positive_wrapper_result'], expected['positive_wrapper_result'])
                self.assertEqual(actual['target_reduction_factors_G44_G53_G104'],
                                 expected['ordered_reduction_factors'])
                self.assertFalse(actual['remote_attack_type_E42_applied'])
                self.assertFalse(actual['surge_keyword_E121_applied'])
                self.assertIsNone(actual['actual_hp_loss'])
                self.assertIsNone(actual['full_build_dps'])

    def test_missing_event_leaf_or_other_factors_withholds(self):
        given, _ = source_case(0)
        for change in ({'element_type_leaf': None}, {'leaves_source': None},
                       {'all_other_graph_factors_unity': False},
                       {'final_ignore_switch': None}):
            self.assertIsNone(hit.calculate({**given, **change})['graph_pre_round'])
        with self.assertRaisesRegex(ValueError, 'finite'):
            hit.calculate({**given, 'attack': float('nan')})

    def test_graph_clamp_and_positive_wrapper_are_separate(self):
        given, _ = source_case(0)
        zero = hit.calculate({**given, 'target_lightning_ignore_dam_rate': 2})
        self.assertEqual((zero['graph_pre_round'], zero['positive_wrapper_result']), (0, 0))
        small = hit.calculate({**given, 'attack': .1})
        self.assertEqual(small['positive_wrapper_result'], 1)

    def test_source_pin_and_read_only_api(self):
        with TemporaryDirectory() as temp:
            folder = Path(temp)
            for name in hit.HASHES:
                (folder / name).write_bytes((hit.ROOT / name).read_bytes())
            (folder / 'native-lightning-dot-factors-v1.md').write_text('changed')
            hit.proof.cache_clear()
            with patch.object(hit, 'ROOT', folder):
                with self.assertRaisesRegex(ValueError, 'hash conflict'):
                    hit.proof()
        hit.proof.cache_clear()
        with TemporaryDirectory() as temp:
            database = Path(temp) / 'advisor.sqlite3'
            database.write_bytes(b'unchanged sentinel')
            before = hashlib.sha256(database.read_bytes()).hexdigest()
            with patch.object(server, 'DB', database):
                http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
                worker = threading.Thread(target=http.serve_forever, daemon=True)
                worker.start()
                try:
                    given, _ = source_case(1)
                    request = Request(f'http://127.0.0.1:{http.server_address[1]}/api/native-lightning-dot-hit',
                                      data=json.dumps(given).encode(),
                                      headers={'Content-Type': 'application/json'})
                    with urlopen(request) as response:
                        result = json.load(response)
                    self.assertAlmostEqual(result['graph_pre_round'], 44.46)
                    self.assertEqual(result['positive_wrapper_result'], 44)
                finally:
                    http.shutdown()
                    worker.join()
                    http.server_close()
            self.assertEqual(before, hashlib.sha256(database.read_bytes()).hexdigest())
