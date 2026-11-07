"""Five native PvP variants share an identity OTHER max_hp rate table."""
import hashlib
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen

import native_pvp_max_hp_adjust as pvp
import native_max_hp_ceiling as ceiling
import server
from tests.test_native_max_hp_ceiling import case as max_hp_case


def params(rate, variant):
    return {'other_rate': rate, 'pvp_variant': variant,
            'pvp_adjustment_enabled': True, 'player_context': 'pvp',
            'property_source_build': '26267212',
            'pvp_variant_source': 'explicit_synthetic',
            'table_identity_confirmed': True}


class NativePvpMaxHpAdjustTests(unittest.TestCase):
    def tearDown(self):
        pvp.proof.cache_clear()

    def test_all_25_native_boundary_vectors(self):
        packet = json.loads((pvp.ROOT / 'native-pvp-max-hp-table-v1.json').read_text())
        self.assertEqual(len(packet['boundary_vectors']), 25)
        for vector in packet['boundary_vectors']:
            with self.subTest(variant=vector['variant'], rate=vector['rate']):
                result = pvp.adjust(params(vector['rate'], vector['variant']))
                self.assertEqual(result['adjusted_other_rate'], vector['output'])
                self.assertEqual(result['matched_range'], vector['range'])
                self.assertIsNone(result['full_pvp_hp'])

    def test_unknown_variant_build_and_table_withhold(self):
        given = params(.4, 'value_2')
        for change in ({'pvp_variant': 'value_5'},
                       {'property_source_build': 'other'},
                       {'pvp_variant_source': 'guessed'},
                       {'table_identity_confirmed': False}):
            with self.subTest(change=change):
                result = pvp.adjust({**given, **change})
                self.assertIsNone(result['adjusted_other_rate'])
                self.assertTrue(result['missing'])

    def test_scoped_max_hp_adapter_and_no_full_pvp_claim(self):
        given, _ = max_hp_case('absolute_and_rate')
        given['pvp_max_hp_adjust_enabled'] = True
        given['pvp_inputs'] = {k: v for k, v in params(.25, 'value_3').items()
                               if k != 'other_rate'}
        result = ceiling.calculate(given)
        self.assertEqual((result['effective_other_max_hp_rate'],
                          result['max_hp_after'], result['real_max_hp_after']),
                         (.25, 162, 122))
        self.assertIsNotNone(result['pvp_rate_adjustment_source'])
        self.assertIsNone(result['full_pvp_hp'])
        withheld = ceiling.calculate({**given, 'pvp_inputs': {
            **given['pvp_inputs'], 'pvp_variant': 'unresolved'}})
        self.assertIsNone(withheld['max_hp_after'])
        self.assertIn('pvp_inputs.exact pvp_variant', withheld['missing'])

    def test_source_tamper_and_read_only_api(self):
        with TemporaryDirectory() as temp:
            folder = Path(temp)
            for name in pvp.HASHES:
                (folder / name).write_bytes((pvp.ROOT / name).read_bytes())
            (folder / 'native-pvp-max-hp-table-v1.json').write_text('{}')
            pvp.proof.cache_clear()
            with patch.object(pvp, 'ROOT', folder):
                with self.assertRaisesRegex(ValueError, 'hash conflict'):
                    pvp.proof()
        with TemporaryDirectory() as temp:
            database = Path(temp) / 'advisor.sqlite3'
            database.write_bytes(b'unchanged sentinel')
            before = hashlib.sha256(database.read_bytes()).hexdigest()
            with patch.object(server, 'DB', database):
                http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
                worker = threading.Thread(target=http.serve_forever, daemon=True)
                worker.start()
                try:
                    request = Request(f'http://127.0.0.1:{http.server_address[1]}/api/native-pvp-max-hp-rate',
                                      data=json.dumps(params(.6, 'value_1')).encode(),
                                      headers={'Content-Type': 'application/json'})
                    with urlopen(request, timeout=5) as response:
                        result = json.load(response)
                    self.assertEqual(result['matched_range'], [.4, .6])
                    self.assertEqual(result['adjusted_other_rate'], .6)
                    self.assertEqual(hashlib.sha256(database.read_bytes()).hexdigest(), before)
                finally:
                    http.shutdown()
                    http.server_close()
