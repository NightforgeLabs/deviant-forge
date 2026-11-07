"""Identical installed English labels must not merge different native properties."""
import hashlib
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen

import component_compare
import native_combat_labels as labels
import server


class NativeCombatLabelTests(unittest.TestCase):
    def tearDown(self):
        labels.proof.cache_clear()

    def test_identical_weapon_label_has_two_distinct_native_properties(self):
        left = labels.resolve('Weapon DMG', 'D0102', '26267212')
        right = labels.resolve('Weapon DMG', 'E4200', '26267212')
        self.assertEqual((left['property_id'], left['native_property']), ('D01', 'attack'))
        self.assertEqual((right['property_id'], right['native_property']),
                         ('E42', 'attack_type_dam_add_rate_remote'))
        self.assertEqual(left['english_format'], right['english_format'])
        unlabeled = labels.resolve('Weapon DMG')
        self.assertEqual(unlabeled['status'], 'ambiguous_native_label')
        self.assertIsNone(unlabeled['property_id'])
        self.assertEqual(unlabeled['candidate_affix_ids'], ['D0102', 'E4200'])

    def test_exact_other_labels_and_generic_elemental_unbound(self):
        for affix, label, property_id in (
                ('E4300', 'Status DMG', 'E43'),
                ('E3400', 'Shock DMG', 'E34'),
                ('E12100', 'Power Surge DMG', 'E121')):
            self.assertEqual(labels.resolve(label, affix, '26267212')['property_id'], property_id)
        self.assertIsNone(labels.resolve('Elemental DMG')['property_id'])
        self.assertEqual(labels.resolve('Status DMG', 'E3400', '26267212')['status'],
                         'native_label_id_conflict')
        self.assertIsNone(labels.resolve('Weapon DMG', 'D0102', 'wrong build')['property_id'])

    def test_component_compare_does_not_assign_native_label_to_generic_pool(self):
        empty = {'attributes': []}
        for affix in (None, 'D0102', 'E4200'):
            row = {'name': 'Weapon DMG', 'value_percent': 20,
                   'source_kind': 'installed_native_affix', 'source_build': '26267212',
                   'source': 'native affix fixture'}
            if affix:
                row['native_affix_id'] = affix
            result = component_compare.compare(empty, {'attributes': [row]})
            self.assertEqual(result['component_ratios']['normal']['min'], 1)
            binding = result['right']['trace'][0]['native_binding']
            self.assertEqual(binding['property_id'], None if affix is None else
                             ('D01' if affix == 'D0102' else 'E42'))
            self.assertTrue(any('native affix label alone' in reason for reason in result['missing']))
        ordinary = component_compare.compare(empty, {'attributes': [
            {'name': 'Weapon DMG', 'value_percent': 20, 'source': 'reviewed ordinary mod card'}]})
        self.assertAlmostEqual(ordinary['component_ratios']['normal']['min'], 1.2)

    def test_source_tamper_and_local_api_do_not_change_database(self):
        with TemporaryDirectory() as temp:
            folder = Path(temp)
            for name in labels.HASHES:
                (folder / name).write_bytes((labels.ROOT / name).read_bytes())
            (folder / 'native-combat-english-labels-v1.md').write_text('changed')
            labels.proof.cache_clear()
            with patch.object(labels, 'ROOT', folder):
                with self.assertRaisesRegex(ValueError, 'hash conflict'):
                    labels.proof()
        labels.proof.cache_clear()
        with TemporaryDirectory() as temp:
            database = Path(temp) / 'advisor.sqlite3'
            database.write_bytes(b'unchanged sentinel')
            before = hashlib.sha256(database.read_bytes()).hexdigest()
            with patch.object(server, 'DB', database):
                http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
                worker = threading.Thread(target=http.serve_forever, daemon=True)
                worker.start()
                try:
                    data = {'label': 'Weapon DMG', 'affix_id': 'D0102',
                            'source_build': '26267212'}
                    request = Request(f'http://127.0.0.1:{http.server_address[1]}/api/native-combat-affix-label',
                                      data=json.dumps(data).encode(),
                                      headers={'Content-Type': 'application/json'})
                    with urlopen(request) as response:
                        result = json.load(response)
                    self.assertEqual(result['property_id'], 'D01')
                finally:
                    http.shutdown()
                    worker.join()
                    http.server_close()
            self.assertEqual(before, hashlib.sha256(database.read_bytes()).hexdigest())
