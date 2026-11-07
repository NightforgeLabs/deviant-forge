"""Controlled player-hit replay requires all source-traced state inputs."""
import hashlib
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen

import native_player_hit_replay as replay
import server


def case(name):
    packet = json.loads((replay.ROOT / 'native-controlled-player-hit-vectors-v1.json').read_text())
    values = {**packet[name]['inputs'],
              'player_server_path_confirmed': True,
              'isolated_hit_no_concurrent_hp_changes': True,
              'damage_is_post_graph': True}
    if values['recognized_shield']:
        values.update(shield_state='shield_hold', shield_exists_after_change=True)
    return values, packet[name]['output']


class ControlledPlayerHitReplayTests(unittest.TestCase):
    def tearDown(self):
        replay.proof.cache_clear()

    def test_all_four_source_vectors(self):
        for name in ('shield_excess_no_hp_overflow', 'unshielded_partial_hp',
                     'unshielded_lethal_hp_floor', 'invincibility_blocked'):
            given, expected = case(name)
            with self.subTest(name=name):
                actual = replay.replay(given)
                for field, value in expected.items():
                    self.assertEqual(actual[field], value, field)
                self.assertFalse(actual['game_verified'])
                self.assertIsNone(actual['full_build_dps'])
                self.assertEqual(actual['source_method']['build'], '26267212')

    def test_missing_state_withholds_results_and_unsupported_branches(self):
        given, _ = case('unshielded_partial_hp')
        for change in ({'damage_is_post_graph': False},
                       {'player_server_path_confirmed': False},
                       {'isolated_hit_no_concurrent_hp_changes': False},
                       {'holder_hp': None}):
            with self.subTest(change=change):
                candidate = {**given, **change}
                if 'holder_hp' in change:
                    candidate.pop('holder_hp')
                result = replay.replay(candidate)
                self.assertIsNone(result['actual_hp_damage'])
                self.assertTrue(result['missing'])
        for change in ({'hit_accepted': False}, {'hit_merge_queued': True},
                       {'must_die': True}, {'field_value': 5},
                       {'player_state_normal': False}):
            with self.subTest(change=change):
                result = replay.replay({**given, **change})
                self.assertIsNone(result['actual_hp_damage'])
                self.assertEqual(result['status'], 'unsupported_controlled_player_hit_branch')

    def test_shield_scope_and_dying_action_gate(self):
        given, _ = case('shield_excess_no_hp_overflow')
        result = replay.replay({**given, 'shield_exists_after_change': False})
        self.assertIsNone(result['actual_hp_damage'])
        self.assertIn('shield_exists_after_change=true', result['missing'])
        lethal, _ = case('unshielded_lethal_hp_floor')
        result = replay.replay({**lethal, 'dying_action_succeeds': False})
        self.assertEqual(result['actual_hp_damage'], 40)
        self.assertNotEqual(result['status'], 'KNOCK_DOWN')
        self.assertEqual(result['status'], 'death_action_outcome_unresolved')

    def test_numeric_and_boolean_domains(self):
        given, _ = case('unshielded_partial_hp')
        for change in ({'post_graph_damage': float('nan')},
                       {'obstruct_nums': -1}, {'holder_hp': 101},
                       {'recognized_shield': 1}, {'attenuation_factor': 1.1}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                replay.replay({**given, **change})

    def test_pinned_source_hash_rejects_tampering(self):
        with TemporaryDirectory() as temp:
            folder = Path(temp)
            for name in replay.HASHES:
                (folder / name).write_bytes((replay.ROOT / name).read_bytes())
            (folder / 'native-controlled-player-hit-v1.md').write_text('altered')
            replay.proof.cache_clear()
            with patch.object(replay, 'ROOT', folder):
                with self.assertRaisesRegex(ValueError, 'hash conflict'):
                    replay.proof()

    def test_read_only_local_api_and_database_preservation(self):
        given, _ = case('unshielded_partial_hp')
        with TemporaryDirectory() as temp:
            database = Path(temp) / 'advisor.sqlite3'
            database.write_bytes(b'unchanged sentinel')
            before = hashlib.sha256(database.read_bytes()).hexdigest()
            with patch.object(server, 'DB', database):
                http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
                worker = threading.Thread(target=http.serve_forever, daemon=True)
                worker.start()
                try:
                    request = Request(f'http://127.0.0.1:{http.server_address[1]}/api/native-player-hit-replay',
                                      data=json.dumps(given).encode(),
                                      headers={'Content-Type': 'application/json'})
                    with urlopen(request, timeout=5) as response:
                        result = json.load(response)
                    self.assertEqual(result['actual_hp_damage'], 80)
                    self.assertEqual(result['holder_hp_after'], 20)
                    self.assertEqual(hashlib.sha256(database.read_bytes()).hexdigest(), before)
                finally:
                    http.shutdown()
                    http.server_close()


if __name__ == '__main__':
    unittest.main()
