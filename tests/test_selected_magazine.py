import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import core_effects
import server

SHOCK = 'mod:weapon_mod:shock-rampage-power-surge'
AUG = 'weapon:aug-electron-cloud'


class SelectedMagazineTests(unittest.TestCase):
    def rapid(self):
        return {'primary': {'catalog_id': AUG, 'tier': 4, 'stars': 6,
                            'mod_id': SHOCK, 'mod_level': 17,
                            'calibration_profile': {'blueprint_name':'Rapid Assault Rifle Calibration Blueprint', 'rarity':'purple', 'style': 'Rapid Shot Style',
                                                    'fixed_effects': 'Fire Rate +15%; Reload Speed +10%; Attack −10%',
                                                    'source_ref': 'source-rapid'}}}

    def test_cold_warm_actual_selection(self):
        for hits, expected in ((1, .318), (4, 1.30090727325),
                               (10, 3.396459216416596), (20, 7.113084462569966),
                               (40, 14.668662916563)):
            result = core_effects.selected_magazine(self.rapid(), base_chance=.3,
                landed_hits=hits, use_unlinked_shock17=True)
            self.assertAlmostEqual(result['cold_expected_roots'], expected, places=11)
            self.assertAlmostEqual(result['cold_orbs_ps_before_field'], expected-.318, places=11)
            self.assertEqual(result['saved_effective_rows_added'], 0)
            self.assertIsNone(result['full_damage_or_dps'])
        self.assertAlmostEqual(result['warm_four_stacks_expected_roots'], 15.12)
        self.assertEqual([round(p, 3) for p in result['cold_per_stack_chances']],
                         [.318, .333, .348, .363, .378])
        self.assertEqual(result['stars'], 6)
        self.assertIn('+15%', result['calibration_observed_effects'])

    def test_rapid_source_conflict_stays_unsaved(self):
        slots=self.rapid()
        slots['primary']['calibration_profile']['source_ref']='libfile_5e9d7ef914648191bd61b1bd3caa68ec'
        slots['primary']['calibration_profile']['rarity']='purple'
        result=core_effects.selected_magazine(slots,base_chance=.3,landed_hits=1,use_unlinked_shock17=True)
        evidence=result['rapid_style_evidence']
        self.assertEqual(evidence['saved_fire_rate_percent'],15)
        self.assertAlmostEqual(evidence['saved_scenario_rpm'],828)
        self.assertEqual(evidence['standalone_20_percent_scenario_rpm'],864)
        self.assertAlmostEqual(evidence['saved_first_to_last_seconds'],39/(828/60))
        self.assertFalse(evidence['saved_profile_changed'])
        self.assertEqual(evidence['saved_blueprint_rarity'],'purple')
        self.assertTrue(evidence['both_are_candidate_blueprints'])
        self.assertFalse(evidence['standalone_installed_on_saved_weapon'])
        self.assertEqual(slots['primary']['calibration_profile']['fixed_effects'],'Fire Rate +15%; Reload Speed +10%; Attack −10%')

    def test_combined_vanguard_and_shock_armed_first_root(self):
        slots=self.rapid()
        slots['primary']['calibration_profile']={'style':'Vanguard Style','source_ref':'source-vanguard'}
        one=core_effects.selected_magazine(slots,base_chance=.3,landed_hits=1,use_unlinked_shock17=True)
        self.assertEqual(one['status'],'conditional_unlinked_source_plus_vanguard')
        self.assertAlmostEqual(one['cold_expected_roots'],.318)
        self.assertAlmostEqual(one['armed_cold_expected_roots'],1)
        self.assertAlmostEqual(one['armed_cold_orbs_ps_before_field'],0)
        four=core_effects.selected_magazine(slots,base_chance=.3,landed_hits=4,use_unlinked_shock17=True)
        self.assertGreater(four['armed_cold_expected_roots'],four['cold_expected_roots'])
        self.assertAlmostEqual(four['armed_cold_expected_roots'],2.014059925,places=9)
        self.assertEqual(four['saved_effective_rows_added'],0)
        self.assertIsNone(four['full_damage_or_dps'])

    def test_unlinked_source_and_unknown_inputs_do_not_activate(self):
        no_opt = core_effects.selected_magazine(self.rapid(), base_chance=.3)
        self.assertEqual(no_opt['status'], 'unlinked_source_requires_opt_in')
        self.assertNotIn('cold_expected_roots', no_opt)
        no_chance = core_effects.selected_magazine(self.rapid(), use_unlinked_shock17=True)
        self.assertEqual(no_chance['status'], 'enter_base_chance')
        self.assertNotIn('cold_expected_roots', no_chance)
        self.assertIsNone(core_effects.selected_magazine({'primary': {'catalog_id': AUG}}))
        with self.assertRaises(ValueError):core_effects.selected_magazine(self.rapid(), base_chance=1.2, use_unlinked_shock17=True)
        with self.assertRaises(ValueError):core_effects.selected_magazine(self.rapid(), landed_hits=True)

    def test_vanguard_armed_replaces_first_chance(self):
        slots={'primary':{'catalog_id':AUG,'tier':4,'stars':5,
                          'calibration_profile':{'style':'Vanguard Style','source_ref':'source-vanguard'}}}
        result=core_effects.selected_magazine(slots,base_chance=.3)
        self.assertAlmostEqual(result['unarmed_expected_roots'],12)
        self.assertAlmostEqual(result['armed_after_empty_reload_expected_roots'],12.7)
        self.assertAlmostEqual(result['unarmed_orbs_ps_before_field'],11.7)
        self.assertAlmostEqual(result['armed_orbs_ps_before_field'],11.7)
        self.assertEqual(result['stars'],5)


class MagazineAPITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.old=server.DATA,server.MEDIA,server.DB
        server.DATA=Path(self.temp.name);server.MEDIA=server.DATA/'media';server.DB=server.DATA/'advisor.sqlite3'
        server.init()
        self.http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
        self.base=f'http://127.0.0.1:{self.http.server_port}'

    def tearDown(self):
        self.http.shutdown();self.http.server_close();self.thread.join()
        server.DATA,server.MEDIA,server.DB=self.old
        self.temp.cleanup()

    def post(self,path,data):
        req=Request(self.base+path,json.dumps(data).encode(),{'Content-Type':'application/json'})
        try:
            with urlopen(req) as result:return json.load(result)
        except HTTPError as error:raise AssertionError(error.read().decode()) from error

    def test_saved_plan_to_explanation_without_baseline_or_data_write(self):
        slots=SelectedMagazineTests().rapid()
        slots['primary']['mod_inventory_id']='shock-observed'
        with server.connect() as c:
            c.execute('INSERT INTO inventory VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                ('shock-observed','Observed Shock Rampage','mod_unlock','weapon_mod',None,'Power Surge',17,None,
                 json.dumps({'observed_attribute_lines':['Power Surge DMG +6%']}),
                 json.dumps({'catalog_id':SHOCK}),'fixture-source','[]',server.now(),server.now(),0))
        plan=self.post('/api/planned-build',{'name':'Rapid with selected Shock Lv17','slots':slots})
        base={'build_id':plan['id'],'active_weapon_slot':'primary'}
        blocked=self.post('/api/build-contribution-coverage',base)['selected_magazine_preview']
        self.assertEqual(blocked['status'],'unlinked_source_requires_opt_in')
        cleared=self.post('/api/build-contribution-coverage',{**base,'magazine_hypothesis':{
            'base_chance':.3,'landed_hits':None,'use_unlinked_shock17':True}})
        self.assertIsNone(cleared['selected_magazine_preview'])
        self.assertIn('items',cleared)
        for invalid in (0,201,1.5,'invalid'):
            with self.subTest(invalid=invalid),self.assertRaises(AssertionError):
                self.post('/api/build-contribution-coverage',{**base,'magazine_hypothesis':{
                    'base_chance':.3,'landed_hits':invalid,'use_unlinked_shock17':True}})

        preview=self.post('/api/build-contribution-coverage',{**base,'magazine_hypothesis':{
            'base_chance':.3,'landed_hits':40,'use_unlinked_shock17':True}})
        self.assertAlmostEqual(preview['selected_magazine_preview']['cold_expected_roots'],14.668662916563)
        self.assertEqual(preview['selected_magazine_preview']['calibration_style'],'Rapid Shot Style')
        self.assertFalse(preview['selected_magazine_preview']['full_damage_or_dps'])
        with server.connect() as c:
            self.assertEqual(c.execute('SELECT count(*) FROM inventory').fetchone()[0],1)
            self.assertEqual(c.execute('SELECT count(*) FROM planned_builds').fetchone()[0],1)


if __name__=='__main__':unittest.main()
