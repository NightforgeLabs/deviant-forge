import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

import core_effects
import server


class CoreEffectTests(unittest.TestCase):
    def test_finite_boundaries_and_source_scope(self):
        self.assertEqual(core_effects.finite_counter(20, 1, 1)['expected_resolutions'], 0)
        self.assertEqual(core_effects.finite_counter(21, 1, 1)['expected_resolutions'], 1)
        self.assertAlmostEqual(core_effects.finite_counter(20, .3, 2)['expected_resolutions'], .032553356881300954)
        self.assertAlmostEqual(core_effects.finite_counter(20, .3, 2, same_hit=True)['expected_resolutions'], .04796189736621132)
        self.assertEqual(core_effects.finite_counter(0, 1, armed=True)['expected_resolutions'], 0)
        self.assertEqual(core_effects.finite_counter(1, 0, armed=True)['expected_resolutions'], 1)
        self.assertEqual(core_effects.SNAPSHOT_DATE, '2026-10-25')

    def test_selected_core_requires_measured_rate_and_never_infers_thunder_damage(self):
        slots={'primary':{'mod_id':'mod:weapon_mod:shock-rampage-power-surge'},
               'mask':{'mod_id':'mod:mask_mod:thunderclap-power-surge'}}
        unknown=core_effects.selected(slots)
        self.assertTrue(all(row['total_blocking'] for row in unknown))
        self.assertIsNone(unknown[1]['counter_preview'])
        observed=core_effects.selected(slots,power_surge={'events_per_active_second':.3,'rate_origin':'measured_selected_build'},
            counter={'eligible_landed_hits':20,'root_trigger_chance':.3})
        self.assertFalse(observed[0]['total_blocking'])
        self.assertTrue(observed[1]['total_blocking'])
        self.assertAlmostEqual(observed[1]['counter_preview']['next_hit_two_instances']['expected_resolutions'],.032553356881300954)
        self.assertEqual(core_effects.selected({'secondary':slots['primary']},active_weapon_slot='primary'),[])


class CoreEffectAPITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.old=(server.DATA,server.MEDIA,server.DB)
        server.DATA=Path(self.temp.name)
        server.MEDIA=server.DATA/'media'
        server.DB=server.DATA/'advisor.sqlite3'
        server.init()
        self.http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True)
        self.thread.start()
        self.base=f'http://127.0.0.1:{self.http.server_port}'

    def tearDown(self):
        self.http.shutdown();self.http.server_close();self.thread.join()
        server.DATA,server.MEDIA,server.DB=self.old
        self.temp.cleanup()

    def post(self,path,data):
        request=Request(self.base+path,json.dumps(data).encode(),{'Content-Type':'application/json'})
        with urlopen(request) as response:return json.load(response)

    def fixture_mod(self,identity,slot,item_id):
        typed=[{'row_index':0,'stat_type':'weapon_damage_percent','value':5,'unit':'percent',
                'calculation_status':'assumption_scenario','confidence':'source_checked','tech_activation':'verified_active',
                'tech_activation_evidence':'synthetic fixture','raw_text':'Weapon DMG +5%'}]
        with server.connect() as connection:
            connection.execute('INSERT INTO inventory VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (item_id,'Fixture '+item_id,'mod_unlock',slot,None,'Power Surge',9,None,
                 json.dumps({'typed_modifiers':typed,'observed_attribute_lines':['Weapon DMG +5%'],'original_observed_level':9}),
                 json.dumps({'catalog_id':identity}),'fixture-source','[]',server.now(),server.now(),0))

    def test_selected_build_to_api_finite_coverage(self):
        shock='mod:weapon_mod:shock-rampage-power-surge'
        thunder='mod:mask_mod:thunderclap-power-surge'
        self.fixture_mod(shock,'weapon_mod','shock-fixture')
        self.fixture_mod(thunder,'mask_mod','thunder-fixture')
        base={'primary':{'catalog_id':'weapon:aug-electron-cloud','tier':5,'stars':5}}
        normal=self.post('/api/planned-build',{'name':'No core fixture','slots':base})
        shock_slots={**base,'primary':{**base['primary'],'mod_id':shock,'mod_level':9,'mod_inventory_id':'shock-fixture'}}
        shock_build=self.post('/api/planned-build',{'name':'Shock fixture','slots':shock_slots})
        thunder_slots={**shock_slots,'mask':{'catalog_id':'armor:savior-mask','mod_id':thunder,'mod_level':9,'mod_inventory_id':'thunder-fixture'}}
        both=self.post('/api/planned-build',{'name':'Both core fixture','slots':thunder_slots})
        encounter={'dodge_fraction':0,'pre_mod_reload_seconds':2,'accepted_energy_returns_per_second':0,
                   'hit_rate':1,'weakspot_fraction':.2,'crit_weak_overlap':.02}
        streams={'events_per_active_second':0}
        request={'use_tier_v_preview':True,'encounter':encounter,'power_surge':streams,'orb':streams}
        before=self.post('/api/build-combat-formula',{**request,'build_id':normal['id']})
        self.assertIsNotNone(before['result']['energy']['durations']['60']['total_damage_bounds'])
        no_rate=self.post('/api/build-combat-formula',{**request,'build_id':shock_build['id']})
        self.assertIsNone(no_rate['result']['energy']['durations']['60']['total_damage_bounds'])
        self.assertEqual(no_rate['selected_core_effects'][0]['mod_id'],shock)
        self.assertEqual(no_rate['selected_core_effects'][0]['status'],'unmodeled_core_effect')
        observed=self.post('/api/build-combat-formula',{**request,'build_id':shock_build['id'],
            'power_surge':{'events_per_active_second':0,'rate_origin':'measured_selected_build'}})
        self.assertIsNotNone(observed['result']['energy']['durations']['60']['total_damage_bounds'])
        self.assertEqual(observed['selected_core_effects'][0]['status'],'included_in_entered_observed_rate')
        finite=self.post('/api/build-combat-formula',{**request,'build_id':both['id'],
            'power_surge':{'events_per_active_second':0,'rate_origin':'measured_selected_build'},
            'core_counter':{'eligible_landed_hits':20,'root_trigger_chance':.3}})
        self.assertIsNone(finite['result']['energy']['durations']['60']['total_damage_bounds'])
        self.assertEqual(finite['selected_core_effects'][1]['mod_id'],thunder)
        self.assertAlmostEqual(finite['selected_core_effects'][1]['counter_preview']['next_hit_two_instances']['expected_resolutions'],.032553356881300954)
        self.assertIn('selected core effect',finite['result']['energy']['durations']['60']['missing'][-1])
        with server.connect() as connection:
            self.assertEqual(connection.execute('SELECT count(*) FROM inventory').fetchone()[0],2)


if __name__=='__main__':unittest.main()
