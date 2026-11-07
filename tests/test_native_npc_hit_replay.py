"""NPC settlement is conditional on an explicit monster/NPC component path."""
import hashlib
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen

import native_npc_hit_replay as npc
import server


def case(name):
    packet = json.loads((npc.ROOT / 'native-npc-hit-vectors-v1.json').read_text())
    inputs = {**packet[name]['inputs'],
              'monster_component_binding_confirmed': True,
              'npc_health_component_confirmed': True,
              'isolated_hit_no_concurrent_hp_changes': True,
              'damage_is_post_graph': True}
    if inputs['recognized_held_shield']:
        inputs.update(shield_state='shield_hold', shield_exists_after_change=True)
    return inputs, packet[name]['output']


class ControlledNpcHitReplayTests(unittest.TestCase):
    def tearDown(self):
        npc.proof.cache_clear()

    def test_all_source_vectors_and_player_death_separation(self):
        for name in ('ordinary_monster_partial_hp',
                     'monster_lethal_with_dying_trigger',
                     'monster_shield_excess_no_hp_overflow'):
            given, expected = case(name)
            with self.subTest(name=name):
                actual = npc.replay(given)
                for field, value in expected.items():
                    self.assertEqual(actual[field], value, field)
                self.assertFalse(actual['game_verified'])
                self.assertIsNone(actual['named_boss_binding'])
                self.assertIsNone(actual['full_build_dps'])
        lethal, _ = case('monster_lethal_with_dying_trigger')
        self.assertEqual(npc.replay(lethal)['status'], 'KNOCK_DOWN_NPC')
        self.assertNotEqual(npc.replay({**lethal, 'has_on_dying_event_trigger': False})['status'],
                            'KNOCK_DOWN_NPC')

    def test_missing_binding_shield_state_and_unsupported_branches_withhold(self):
        given, _ = case('ordinary_monster_partial_hp')
        for change in ({'monster_component_binding_confirmed': False},
                       {'npc_health_component_confirmed': False},
                       {'damage_is_post_graph': False},
                       {'isolated_hit_no_concurrent_hp_changes': False}):
            with self.subTest(change=change):
                result = npc.replay({**given, **change})
                self.assertIsNone(result['actual_hp_damage'])
                self.assertTrue(result['missing'])
        shielded, _ = case('monster_shield_excess_no_hp_overflow')
        result = npc.replay({**shielded, 'shield_exists_after_change': False})
        self.assertIsNone(result['actual_hp_damage'])
        for change in ({'animal_anesthetic_intercept': True},
                       {'hit_accepted': False}, {'npc_state_dead': True},
                       {'field_value': 5}, {'part_damage_overflow': True},
                       {'holder_avoid_be_hit_non_no': True}):
            with self.subTest(change=change):
                result = npc.replay({**given, **change})
                self.assertIsNone(result['actual_hp_damage'])
                self.assertEqual(result['status'], 'unsupported_controlled_npc_hit_branch')

    def test_finite_state_and_source_integrity(self):
        given, _ = case('ordinary_monster_partial_hp')
        for change in ({'post_graph_damage': float('nan')},
                       {'npc_hp': 101}, {'obstruct_nums': -1},
                       {'attenuation_factor': 1.1},
                       {'recognized_held_shield': 1}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                npc.replay({**given, **change})
        with TemporaryDirectory() as temp:
            folder = Path(temp)
            for name in npc.HASHES:
                (folder / name).write_bytes((npc.ROOT / name).read_bytes())
            (folder / 'native-npc-hit-v1.md').write_text('changed')
            npc.proof.cache_clear()
            with patch.object(npc, 'ROOT', folder):
                with self.assertRaisesRegex(ValueError, 'hash conflict'):
                    npc.proof()

    def test_read_only_api_and_database_preservation(self):
        given, _ = case('monster_shield_excess_no_hp_overflow')
        with TemporaryDirectory() as temp:
            database = Path(temp) / 'advisor.sqlite3'
            database.write_bytes(b'unchanged test sentinel')
            before = hashlib.sha256(database.read_bytes()).hexdigest()
            with patch.object(server, 'DB', database):
                http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
                worker = threading.Thread(target=http.serve_forever, daemon=True)
                worker.start()
                try:
                    request = Request(f'http://127.0.0.1:{http.server_address[1]}/api/native-npc-hit-replay',
                                      data=json.dumps(given).encode(),
                                      headers={'Content-Type': 'application/json'})
                    with urlopen(request, timeout=5) as response:
                        result = json.load(response)
                    self.assertEqual(result['post_attenuation_damage'], 80)
                    self.assertEqual(result['actual_hp_damage'], 0)
                    self.assertEqual(result['reported_real_damage_hp'], 80)
                    self.assertEqual(hashlib.sha256(database.read_bytes()).hexdigest(), before)
                finally:
                    http.shutdown()
                    http.server_close()


if __name__ == '__main__':
    unittest.main()
