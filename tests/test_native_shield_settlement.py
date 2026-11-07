"""Recognized held-shield HP branch; final health loss stays unresolved."""
import hashlib
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen

import native_shield_settlement as shield
import server


def inputs(damage, current, maximum, invincible=False):
    return {'recognized_held_shield': True, 'shield_state': 'shield_hold',
            'damage_is_post_attenuation': True,
            'post_attenuation_damage': damage, 'current_shield_hp': current,
            'maximum_shield_hp': maximum, 'invincible_shield_type': invincible,
            'shield_exists_after_change': True}


class NativeShieldSettlementTests(unittest.TestCase):
    def tearDown(self):
        shield.proof.cache_clear()
        shield.player_proof.cache_clear()

    def test_pinned_synthetic_vectors_shield_events_and_no_hp_loss(self):
        packet = json.loads((shield.ROOT / 'native-shield-synthetic-vectors-v1.json').read_text())
        for vector in packet['vectors']:
            source = vector['input']
            result = shield.evaluate(inputs(source['post_attenuation_damage'],
                source['current_shield_hp'], source['maximum_shield_hp'],
                source['invincible_shield_type']))
            with self.subTest(vector=source['name']):
                self.assertEqual(result['shield_hp_after'], vector['shield_hp_after'])
                self.assertEqual(result['shield_be_hit_event'], vector['shield_be_hit_event'])
                self.assertEqual(result['shield_crush_and_destroy_event'],
                                 vector['shield_crush_and_destroy_event'])
                self.assertEqual(result['damage_hp_without_apply_return'],
                                 vector['damage_hp_without_apply_return'])
                self.assertIsNone(result['applied_hp_loss'])
                self.assertIsNone(result['overflow_applied_to_hp'])
                self.assertFalse(result['game_verified'])
                self.assertEqual(result['source_method']['build'], '26267212')

    def test_recognition_post_attenuation_and_lifecycle_must_be_explicit(self):
        base = inputs(35, 20, 100)
        for change, phrase in [({'recognized_held_shield': None}, 'recognized_held_shield=true'),
                               ({'damage_is_post_attenuation': False}, 'damage_is_post_attenuation=true'),
                               ({'shield_exists_after_change': None}, 'shield_exists_after_change=true')]:
            with self.subTest(change=change):
                result = shield.evaluate({**base, **change})
                self.assertIsNone(result['shield_hp_after'])
                self.assertIn(phrase, result['missing'])
        unrecognized = shield.evaluate({**base, 'recognized_held_shield': False})
        self.assertEqual(unrecognized['status'], 'shield_branch_not_applicable')
        self.assertIsNone(unrecognized['damage_hp_without_apply_return'])
        wrong_state = shield.evaluate({**base, 'shield_state': 'shield_crush'})
        self.assertIsNone(wrong_state['shield_hp_after'])
        self.assertEqual(wrong_state['status'], 'shield_branch_not_applicable')

    def test_zero_boundary_invincible_and_invalid_numbers(self):
        self.assertTrue(shield.evaluate(inputs(0, 0, 100))['shield_crush_and_destroy_event'])
        self.assertTrue(shield.evaluate(inputs(40, 0, 100, True))['shield_crush_and_destroy_event'])
        for bad in ({**inputs(10, 5, 100), 'post_attenuation_damage': -1},
                    {**inputs(10, 5, 100), 'current_shield_hp': 101},
                    {**inputs(10, 5, 100), 'maximum_shield_hp': float('nan')},
                    {**inputs(10, 5, 100), 'invincible_shield_type': 0}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                shield.evaluate(bad)

    def test_source_traced_attenuation_and_isolated_player_shield_bypass(self):
        attenuated = shield.attenuate({'damage_before_attenuation': 100,
                                      'attenuation_factor': .2, 'obstruct_nums': 1})
        self.assertAlmostEqual(attenuated['post_attenuation_damage'], 80)
        self.assertIsNone(attenuated['applied_hp_loss'])
        self.assertEqual(shield.attenuate({'damage_before_attenuation': 100,
            'attenuation_factor': 1.2, 'obstruct_nums': 1})['post_attenuation_damage'], 0)
        self.assertAlmostEqual(shield.attenuate({'damage_before_attenuation': 100,
            'attenuation_factor': 1.2, 'obstruct_nums': 2})['post_attenuation_damage'], 4)
        for current, after in ((50, 0), (90, 10)):
            with self.subTest(shield_hp=current):
                given = {**inputs(attenuated['post_attenuation_damage'], current, 100),
                         'player_server_path_confirmed': True,
                         'isolated_hit_no_concurrent_hp_changes': True}
                result = shield.evaluate(given)
                self.assertEqual(result['shield_hp_after'], after)
                self.assertEqual(result['player_hit_result'], 'HIT_SHIELD')
                self.assertEqual(result['real_damage_hp_event_amount'], 80)
                self.assertEqual(result['damage_hp_without_apply_return'], 80)
                self.assertEqual(result['applied_hp_loss'], 0)
                self.assertEqual(result['hp_change_value'], 0)
                self.assertIs(result['overflow_applied_to_hp'], False)
                self.assertIs(result['health_take_damage_called'], False)
                self.assertFalse(result['game_verified'])
        unshielded = shield.evaluate({**given, 'recognized_held_shield': False})
        self.assertIsNone(unshielded['applied_hp_loss'])
        self.assertIsNone(unshielded['health_take_damage_called'])
        incomplete = shield.evaluate({**given, 'isolated_hit_no_concurrent_hp_changes': False})
        self.assertIsNone(incomplete['applied_hp_loss'])
        self.assertIsNone(incomplete['overflow_applied_to_hp'])

    def test_attenuation_operand_and_player_flag_gates(self):
        result = shield.attenuate({'damage_before_attenuation': 100})
        self.assertIsNone(result['post_attenuation_damage'])
        self.assertIn('attenuation_factor', result['missing'])
        for bad in ({'damage_before_attenuation': 100, 'attenuation_factor': .2, 'obstruct_nums': -1},
                    {'damage_before_attenuation': 100, 'attenuation_factor': .2, 'obstruct_nums': True},
                    {'damage_before_attenuation': float('nan'), 'attenuation_factor': .2, 'obstruct_nums': 1}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                shield.attenuate(bad)
        with self.assertRaisesRegex(ValueError, 'explicit boolean'):
            shield.evaluate({**inputs(20, 50, 100), 'player_server_path_confirmed': 1})

    def test_source_tamper_is_rejected(self):
        with TemporaryDirectory() as temp:
            folder = Path(temp)
            for name in shield.HASHES:
                (folder / name).write_bytes((shield.ROOT / name).read_bytes())
            (folder / 'native-shield-hit-settlement-v1.md').write_text('changed')
            shield.proof.cache_clear()
            with patch.object(shield, 'ROOT', folder):
                with self.assertRaisesRegex(ValueError, 'hash conflict'):
                    shield.proof()

    def test_player_source_tamper_is_rejected(self):
        with TemporaryDirectory() as temp:
            folder = Path(temp)
            for name in shield.PLAYER_HASHES:
                (folder / name).write_bytes((shield.ROOT / name).read_bytes())
            (folder / 'native-player-hp-route-v1.md').write_text('changed')
            shield.player_proof.cache_clear()
            with patch.object(shield, 'ROOT', folder):
                with self.assertRaisesRegex(ValueError, 'hash conflict'):
                    shield.player_proof()

    def test_read_only_local_api_has_same_boundary(self):
        with TemporaryDirectory() as temp:
            database = Path(temp) / 'advisor.sqlite3'
            database.write_bytes(b'unchanged test sentinel')
            before = hashlib.sha256(database.read_bytes()).hexdigest()
            with patch.object(server, 'DB', database):
                http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
                worker = threading.Thread(target=http.serve_forever, daemon=True)
                worker.start()
                try:
                    url = f'http://127.0.0.1:{http.server_address[1]}/api/native-shield-branch'
                    request = Request(url, data=json.dumps(inputs(35, 20, 100)).encode(),
                                      headers={'Content-Type': 'application/json'})
                    with urlopen(request, timeout=5) as response:
                        result = json.load(response)
                    self.assertEqual(result['shield_hp_after'], 0)
                    self.assertIsNone(result['applied_hp_loss'])
                    request = Request(f'http://127.0.0.1:{http.server_address[1]}/api/native-hit-attenuation',
                                      data=json.dumps({'damage_before_attenuation': 100,
                                          'attenuation_factor': .2, 'obstruct_nums': 1}).encode(),
                                      headers={'Content-Type': 'application/json'})
                    with urlopen(request, timeout=5) as response:
                        attenuation = json.load(response)
                    self.assertAlmostEqual(attenuation['post_attenuation_damage'], 80)
                    self.assertEqual(hashlib.sha256(database.read_bytes()).hexdigest(), before)
                finally:
                    http.shutdown()
                    http.server_close()


if __name__ == '__main__':
    unittest.main()
