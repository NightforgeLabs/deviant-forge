import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen

import server


class PacketStatefulHttpTests(unittest.TestCase):
    def setUp(self):
        self.http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.http.server_port}'

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join(timeout=5)

    def post(self, path, body):
        request = Request(self.base + path, data=json.dumps(body).encode(),
                          headers={'Content-Type': 'application/json'})
        with urlopen(request, timeout=5) as response:
            return json.load(response)

    def test_packet_and_candidate_routes(self):
        with urlopen(self.base + '/api/weapon-timeline-coverage', timeout=5) as response:
            self.assertEqual(json.load(response)['additional_packet_timeline_weapons'], 6)
        with urlopen(self.base + '/api/mod-stateful-coverage', timeout=5) as response:
            self.assertEqual(json.load(response)['executable_candidate_bindings'], 39)
        packet = self.post('/api/weapon-timeline-simulate', {
            'weapon_id': 'weapon:kvd-boom-boom', 'evidence_mode': 'preview_simulation',
            'stream_id': 'http-v4', 'actions': [{'kind': 'boom_boom_hit', 'at': 0,
                                               'input_id': 'h', 'explosion_targets': ['dummy']}],
            'damage_model': {'basis_values': {'psi': 100}, 'duration_seconds': 2}})
        self.assertEqual(packet['damage_projection']['known_damage_subtotal'], 300)
        self.assertIsNone(packet['total_damage'])
        state = self.post('/api/mod-stateful-simulate', {
            'catalog_id': 'mod:helmet_mod:momentum-up', 'level': 10,
            'allow_candidate': True,
            'initial': {'magazine_capacity': 10, 'magazine_id': 'm1', 'full_magazine': True},
            'assumptions': {'phase_basis': 'consumed_ammo_fraction'},
            'events': [{'type': 'inspect'}]})
        self.assertEqual(state['outputs'][0]['stat'], 'fire_rate_percent')
        self.assertFalse(state['current_level_certified'])


if __name__ == '__main__':
    unittest.main()
