import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import server


class WeaponTimelineHttpTests(unittest.TestCase):
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
                          headers={'Content-Type':'application/json'})
        with urlopen(request, timeout=5) as response:
            return json.load(response)

    def test_read_only_scenario_and_existing_comparison_route(self):
        with urlopen(self.base + '/api/weapon-timeline-coverage', timeout=5) as response:
            coverage = json.load(response)
        self.assertEqual(coverage['executable_representative_weapons'],9)
        scenario={'weapon_id':'weapon:mps5-blue-tiger','evidence_mode':'dated_release',
                  'model_mode':'explicit_assumptions','stream_id':'http-left',
                  'actions':[{'kind':'hit','at':0,'target':'dummy','rolls':{'bounce':'0.1'},
                              'input_id':'hit-1'}]}
        result=self.post('/api/weapon-timeline-simulate',scenario)
        self.assertEqual(result['event_counts']['keyword_trigger'],1)
        self.assertIsNone(result['total_damage'])
        compare=self.post('/api/component-compare',{'left':{'attributes':[]},'right':{'attributes':[]},
            'context':{'weapon_timeline':{'left':scenario,'right':{**scenario,'stream_id':'http-right'}}}})
        self.assertEqual(compare['weapon_timeline_scenarios']['right']['event_counts']['keyword_trigger'],1)
        self.assertFalse(compare['game_winner_established'])
        modeled={**scenario,'damage_model':{
            'basis_values':{'attack':100},
            'direct':{'basis':'attack','damage_class':'weapon',
                      'element':'none','coefficient_percent':100},
            'packet_models':{'bounce':{'basis':'attack','damage_class':'weapon',
                         'element':'none','coefficient_percent':40,'resolved_hits':1}},
            'duration_seconds':2}}
        projected=self.post('/api/weapon-timeline-simulate',modeled)
        self.assertEqual(projected['total_damage'],140)
        self.assertEqual(projected['damage_per_second'],70)
        self.assertEqual(len(projected['damage_projection']['packets']),2)
        compared=self.post('/api/component-compare',{'left':{'attributes':[]},
            'right':{'attributes':[]},'context':{'weapon_timeline':{
                'left':modeled,'right':{**modeled,'stream_id':'http-modeled-right'}}}})
        self.assertEqual(compared['weapon_timeline_scenarios']['right']['total_damage'],140)
        self.assertFalse(compared['game_winner_established'])
        with self.assertRaises(HTTPError) as error:
            self.post('/api/weapon-timeline-simulate',{**scenario,'evidence_mode':'invalid'})
        self.assertEqual(error.exception.code,400)
        error.exception.close()


if __name__=='__main__':
    unittest.main()
