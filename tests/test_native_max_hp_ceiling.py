"""Source vectors for controlled max_hp -> real_max_hp -> hp revalidation."""
import hashlib
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen

import native_max_hp_ceiling as ceiling
import server


def case(name):
    packet = json.loads((ceiling.ROOT / 'native-hp-ceiling-v2-vectors.json').read_text())
    row = packet['vectors'][name]
    return {**row['inputs'], 'player_formula_branch_confirmed': True,
            'ratio_is_survival_helper_output': True,
            'property_source_build': '26267212'}, row['output']


class NativeMaxHpCeilingTests(unittest.TestCase):
    def tearDown(self):
        ceiling.proof.cache_clear()

    def test_three_pinned_max_hp_vectors(self):
        for name in ('absolute_and_rate', 'independent_channel_present',
                     'set_override'):
            values, expected = case(name)
            with self.subTest(name=name):
                actual = ceiling.calculate(values)
                for field, value in expected.items():
                    self.assertEqual(actual[field], value, field)
                self.assertFalse(actual['game_verified'])
                self.assertIsNone(actual['full_build_dps'])

    def test_live_context_gates_and_independent_branch(self):
        given, _ = case('absolute_and_rate')
        for change in ({'holder_has_real_max_hp': False},
                       {'ratio_is_survival_helper_output': False},
                       {'pvp_max_hp_adjust_enabled': True},
                       {'property_source_build': 'other'}):
            with self.subTest(change=change):
                result = ceiling.calculate({**given, **change})
                self.assertIsNone(result['hp_after_revalidation'])
                self.assertTrue(result['missing'])
        independent = ceiling.calculate({**given,
            'init_independent_rates': [.1], 'other_independent_rates': [.2]})
        self.assertEqual(independent['max_hp_after'], 120)
        self.assertEqual(independent['real_max_hp_after'], 90)

    def test_invalid_inputs_and_tampered_source(self):
        given, _ = case('absolute_and_rate')
        for change in ({'effective_real_san_hp_ratio': float('nan')},
                       {'base_init_abs': float('nan')},
                       {'hp_before': -1},
                       {'other_independent_rates': 'not a list'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                ceiling.calculate({**given, **change})
        # The recovered helper has no lower clamp; synthetic negative ratios
        # can produce real_max_hp above max_hp before the typed table clamp.
        negative = ceiling.calculate({**given, 'effective_real_san_hp_ratio': -.2})
        self.assertEqual(negative['real_max_hp_after'], 194)
        with TemporaryDirectory() as temp:
            folder = Path(temp)
            for name in ceiling.HASHES:
                (folder / name).write_bytes((ceiling.ROOT / name).read_bytes())
            (folder / 'native-hp-ceiling-v2.md').write_text('altered')
            ceiling.proof.cache_clear()
            with patch.object(ceiling, 'ROOT', folder):
                with self.assertRaisesRegex(ValueError, 'hash conflict'):
                    ceiling.proof()

    def test_read_only_api_and_database_preservation(self):
        given, _ = case('absolute_and_rate')
        with TemporaryDirectory() as temp:
            database = Path(temp) / 'advisor.sqlite3'
            database.write_bytes(b'unchanged test sentinel')
            before = hashlib.sha256(database.read_bytes()).hexdigest()
            with patch.object(server, 'DB', database):
                http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
                worker = threading.Thread(target=http.serve_forever, daemon=True)
                worker.start()
                try:
                    request = Request(f'http://127.0.0.1:{http.server_address[1]}/api/native-max-hp-ceiling',
                                      data=json.dumps(given).encode(),
                                      headers={'Content-Type': 'application/json'})
                    with urlopen(request, timeout=5) as response:
                        result = json.load(response)
                    self.assertEqual((result['max_hp_after'], result['real_max_hp_after'],
                                      result['hp_after_revalidation']), (162, 122, 122))
                    self.assertEqual(hashlib.sha256(database.read_bytes()).hexdigest(), before)
                finally:
                    http.shutdown()
                    http.server_close()


if __name__ == '__main__':
    unittest.main()
