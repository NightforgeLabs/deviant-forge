"""Controlled PvE survival ratio from explicit holder/configuration inputs."""
import hashlib
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen

import native_survival_hp as survival
import native_max_hp_ceiling as ceiling
import server
from tests.test_native_max_hp_ceiling import case as max_hp_case


def case(label):
    packet = json.loads((survival.ROOT / 'native-survival-hp-vectors-v1.json').read_text())
    row = next(row for row in packet['vectors'] if row['label'] == label)
    return {**row['input'], 'config_values_resolved_for_library': True,
            'config_source': 'explicit_synthetic', 'player_context': 'pve',
            'property_source_build': '26267212'}, row


class NativeSurvivalHpTests(unittest.TestCase):
    def tearDown(self):
        survival.proof.cache_clear()

    def test_three_source_vectors_and_negative_ratio_not_clamped(self):
        for label in ('uncapped ratio', 'resistance-lowered cap',
                      'upper resistance limit'):
            given, expected = case(label)
            with self.subTest(label=label):
                actual = survival.calculate(given)
                self.assertAlmostEqual(actual['effective_cap'], expected['effective_cap'])
                self.assertAlmostEqual(actual['effective_ratio'], expected['effective_ratio'])
                self.assertEqual(actual['real_max_hp'], expected['real_max_hp'])
                self.assertFalse(actual['game_verified'])
        given, _ = case('uncapped ratio')
        negative = survival.calculate({**given, 'san': 120})
        self.assertEqual(negative['effective_ratio'], -.2)
        self.assertEqual(negative['real_max_hp'], 240)

    def test_configuration_and_pvp_gates(self):
        given, _ = case('uncapped ratio')
        for change in ({'config_values_resolved_for_library': False},
                       {'config_source': 'unknown'},
                       {'player_context': 'pvp'},
                       {'property_source_build': 'other'}):
            with self.subTest(change=change):
                result = survival.calculate({**given, **change})
                self.assertIsNone(result['real_max_hp'])
                self.assertTrue(result['missing'])
        with self.assertRaises(ValueError):
            survival.calculate({**given, 'max_san': float('nan')})

    def test_nested_pve_ratio_flows_to_max_hp_revalidation(self):
        given, _ = max_hp_case('absolute_and_rate')
        given.pop('effective_real_san_hp_ratio')
        given.pop('ratio_is_survival_helper_output')
        survival_values, _ = case('uncapped ratio')
        survival_values.pop('max_hp')
        result = ceiling.calculate({**given, 'survival_inputs': survival_values})
        self.assertEqual(result['max_hp_after'], 162)
        self.assertEqual(result['real_max_hp_after'], 130)
        self.assertEqual(result['hp_after_revalidation'], 130)
        self.assertEqual(result['survival_ratio_source'], 'native_pve_resolved_config')
        withheld = ceiling.calculate({**given, 'survival_inputs': {
            **survival_values, 'config_values_resolved_for_library': False}})
        self.assertIsNone(withheld['hp_after_revalidation'])
        self.assertTrue(any('survival_inputs.' in value for value in withheld['missing']))

    def test_source_tamper_and_read_only_api(self):
        with TemporaryDirectory() as temp:
            folder = Path(temp)
            for name in survival.HASHES:
                (folder / name).write_bytes((survival.ROOT / name).read_bytes())
            (folder / 'native-survival-hp-v1.md').write_text('changed')
            survival.proof.cache_clear()
            with patch.object(survival, 'ROOT', folder):
                with self.assertRaisesRegex(ValueError, 'hash conflict'):
                    survival.proof()
        given, _ = case('resistance-lowered cap')
        with TemporaryDirectory() as temp:
            database = Path(temp) / 'advisor.sqlite3'
            database.write_bytes(b'unchanged sentinel')
            before = hashlib.sha256(database.read_bytes()).hexdigest()
            with patch.object(server, 'DB', database):
                http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
                worker = threading.Thread(target=http.serve_forever, daemon=True)
                worker.start()
                try:
                    request = Request(f'http://127.0.0.1:{http.server_address[1]}/api/native-survival-hp',
                                      data=json.dumps(given).encode(),
                                      headers={'Content-Type': 'application/json'})
                    with urlopen(request, timeout=5) as response:
                        result = json.load(response)
                    self.assertEqual(result['real_max_hp'], 60)
                    self.assertEqual(hashlib.sha256(database.read_bytes()).hexdigest(), before)
                finally:
                    http.shutdown()
                    http.server_close()
