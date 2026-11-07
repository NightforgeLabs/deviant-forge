import json
import os
import tempfile
import sqlite3
import time
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import catalog
import combat_formula
import field_guide_profiles
import mod_rolls
import planned_advisor
import server
import structured_compare


class BuilderFlowTests(unittest.TestCase):
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
        self.http.shutdown()
        self.http.server_close()
        self.thread.join()
        server.DATA,server.MEDIA,server.DB=self.old
        self.temp.cleanup()

    def get(self,path):
        with urlopen(self.base+path) as response:return json.load(response)

    def post(self,path,data):
        request=Request(self.base+path,json.dumps(data).encode(),{'Content-Type':'application/json'})
        with urlopen(request) as response:return json.load(response)

    def test_sourced_star_max_rejects_new_save_but_preserves_existing_invalid_plan(self):
        published=self.get('/api/builder-catalog')['verified_star_limits']
        self.assertEqual({'max':3,'url':'https://oncehuman.th.gl/db/blueprints/13121101',
            'source_status':'exact_named_published_blueprint'},published['weapon:r500'])
        self.assertNotIn('weapon:aug-electron-cloud',published)
        self.assertNotIn('weapon:kam-crank',published)
        self.assertEqual(52,len(published))
        self.assertEqual(3,published['weapon:scar']['max'])
        self.assertEqual(6,published['weapon:mps7-chaos-domain']['max'])
        self.assertNotIn('weapon:aa12',published)
        self.assertEqual(4,published['weapon:kam-pioneer']['max'])
        self.assertNotIn('weapon:nail-gun',published)
        for identity,maximum in [('weapon:r500',3),('weapon:de-50-goshawk',4)]:
            with self.subTest(identity=identity):
                slots={'primary':{'catalog_id':identity,'tier':1,'stars':maximum+1}}
                with self.assertRaisesRegex(ValueError,'published maximum'):
                    server.validate_planned_slots(slots)
                with self.assertRaises(HTTPError) as rejected:
                    self.post('/api/planned-build',{'name':'Invalid new plan','slots':slots})
                self.assertIn('published maximum',rejected.exception.read().decode())
                rejected.exception.close()
                analysis=self.post('/api/planned-analysis',{'slots':slots})
                native=analysis['weapon_reference_timing']['native_selected_tier_star']
                self.assertEqual('exceeds_published_max_stars',native['configuration_status'])
                self.assertIsNone(native['preset_attack_radio'])
                self.assertFalse(native['calculation_included'])
        # An old imported plan is reported verbatim; opening it does not rewrite SQLite.
        saved={'primary':{'catalog_id':'weapon:r500','tier':1,'stars':4}}
        with server.connect() as connection:
            connection.execute('INSERT INTO planned_builds VALUES(?,?,?,?,?,?)',
                ('legacy-invalid','Legacy four-star R500',json.dumps(saved),'','old','old'))
        before=server.DB.read_bytes()
        shown=next(row for row in self.get('/api/builder-catalog')['planned_builds']
                   if row['id']=='legacy-invalid')
        self.assertEqual(saved,shown['slots'])
        self.assertEqual(before,server.DB.read_bytes())
        self.assertEqual('exceeds_published_max_stars',
            self.post('/api/planned-analysis',{'slots':shown['slots']})
            ['weapon_reference_timing']['native_selected_tier_star']['configuration_status'])
        self.assertEqual(before,server.DB.read_bytes())
        # Six-star AUG stays allowed; Burning Rage's page never limits KAM Crank.
        server.validate_planned_slots({'primary':{'catalog_id':'weapon:aug-electron-cloud','tier':5,'stars':6}})
        server.validate_planned_slots({'primary':{'catalog_id':'weapon:kam-crank','tier':5,'stars':5}})
        pioneer={'primary':{'catalog_id':'weapon:kam-pioneer','tier':3,'stars':4}}
        server.validate_planned_slots(pioneer)
        source=self.post('/api/planned-analysis',{'slots':pioneer})['weapon_reference_timing']['native_selected_tier_star']
        self.assertEqual('not_disproved_by_published_max',source['configuration_status'])
        self.assertIsNone(source['preset_attack_radio'])
        with self.assertRaisesRegex(ValueError,'published maximum of 4'):
            server.validate_planned_slots({'primary':{**pioneer['primary'],'stars':5}})

    def test_unowned_reference_calibrations_share_baseline_and_withhold_full_total(self):
        baseline={**combat_formula.PREVIEW}
        encounter={'scenario':'other_unknown','pre_mod_reload_seconds':2,
                   'dodge_fraction':0,'hit_rate':1,'weakspot_fraction':0,
                   'crit_weak_overlap':0,'accepted_energy_returns_per_second':0}
        request={'build_id':None,'baseline':baseline,'modifier_source':'owned_instances',
                 'encounter':encounter,'power_surge':{},'orb':{}}
        before=self.get('/api/state')
        result=self.post('/api/build-combat-formula',request)
        energy=result['result']['energy'];rapid=result['result']['rapid']
        self.assertAlmostEqual(energy['base_direct_hit_after_bonuses'],377.5024)
        self.assertAlmostEqual(rapid['base_direct_hit_after_bonuses'],305.6121)
        self.assertAlmostEqual(energy['rpm_scenario'],720)
        self.assertAlmostEqual(rapid['rpm_scenario'],864)
        self.assertAlmostEqual(energy['durations']['60']['bullet_damage_bounds']['floor'],176444.62176)
        self.assertAlmostEqual(rapid['durations']['60']['bullet_damage_bounds']['floor'],169989.3959346)
        self.assertEqual(energy['durations']['60']['shots_bounds']['floor'],456)
        self.assertEqual(rapid['durations']['60']['shots_bounds']['floor'],524)
        self.assertEqual(rapid['durations']['60']['shot_count_model'],'discrete_first_shot_at_zero_half_open')
        self.assertIsNone(energy['durations']['60']['total_damage_bounds'])
        self.assertIsNone(rapid['durations']['60']['total_damage_bounds'])
        self.assertEqual(result['selected_owned_mods']['resolved_slots'],[])
        edited={**request,'baseline':{**baseline,'crit_damage_bonus':0},
                'encounter':{**encounter,'pre_mod_reload_seconds':None}}
        changed=self.post('/api/build-combat-formula',edited)
        self.assertNotEqual(changed['result']['energy']['hit_groups']['expected_landed_hit'],
                            energy['hit_groups']['expected_landed_hit'])
        self.assertFalse(changed['result']['energy']['durations']['60']['bullet_damage_bounds'])
        after=self.get('/api/state')
        self.assertEqual(before['inventory'],after['inventory'])
        self.assertEqual(before['planned_builds'],after['planned_builds'])

    def test_unowned_two_piece_set_compare_is_unsaved_and_conditional(self):
        before=self.get('/api/state')
        result=self.post('/api/planned-set-compare',{
            'baseline':{'damage':251,'crit_rate':.10,'crit_damage_bonus':.25,
                        'source_ref':'dated catalog estimate'},
            'landed_body_hits':40,'psi_intensity':None,'orb_enemy_hits':None,
            'savior_shield':'active','elemental_model':'shared_bucket'})
        self.assertFalse(result['saved'])
        self.assertFalse(result['ownership_required'])
        self.assertAlmostEqual(result['result']['shelterer']['known_bullet_component'],10291)
        self.assertAlmostEqual(result['result']['savior_active']['known_bullet_component'],11320.1)
        self.assertIsNone(result['result']['selected_savior']['modeled_components_sum'])
        after=self.get('/api/state')
        self.assertEqual(before['inventory'],after['inventory'])
        self.assertEqual(before['planned_builds'],after['planned_builds'])

    def test_real_screenshot_upload_extracts_review_proposal_without_ownership(self):
        source_db=Path(__file__).resolve().parents[1]/'data'/'advisor.sqlite3'
        if not source_db.is_file():self.skipTest('Preserved source frame unavailable')
        with sqlite3.connect(f'file:{source_db}?mode=ro',uri=True) as connection:
            source=next((json.loads(row[0]) for row in connection.execute(
                'SELECT data FROM video_import_proposals WHERE run_id=?',
                ('3eca1e237ab643989c03a1b9c767555d',))
                if json.loads(row[0]).get('catalog_id')=='mod:chest_mod:ardent-shield-battle'
                and json.loads(row[0]).get('ownership')=='unlocked'),None)
        if not source:self.skipTest('Source-checked tooltip unavailable')
        frame=source_db.parent/source['source']['frame']
        if not frame.is_file():self.skipTest('Preserved source frame unavailable')
        request=Request(self.base+'/api/upload',frame.read_bytes(),{'X-Filename':'mod-screenshot.png'})
        with urlopen(request) as response:uploaded=json.load(response)
        self.assertEqual(uploaded['type'],'image')
        job=self.post('/api/video-import/analyze',{'media_id':uploaded['id']})
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            current=self.get('/api/jobs/'+job['id'])
            if current['state'] in ('done','error','cancelled'):break
            time.sleep(.05)
        self.assertEqual(current['state'],'done',current.get('error'))
        state=self.get('/api/state')
        proposals=[row['data'] for row in state['video_import_proposals'] if row['run_id']==job['id']]
        expected=[row for row in proposals if row['catalog_id']==source['catalog_id']]
        self.assertEqual(len(expected),1)
        self.assertEqual(expected[0]['level'],source['level'])
        self.assertEqual(expected[0]['attribute_rows'],source['attribute_rows'])
        self.assertEqual(len(expected[0]['typed_modifiers']),4)
        self.assertTrue(all(row['tech_activation']=='unknown' for row in expected[0]['typed_modifiers']))
        self.assertEqual(state['inventory'],[])

    def test_calibration_worksheet_is_read_only_and_served(self):
        before=server.DB.stat().st_mtime_ns
        with urlopen(self.base+'/calibration-worksheet') as response:
            html=response.read().decode('utf-8')
            self.assertIn('text/html',response.headers['Content-Type'])
        with urlopen(self.base+'/calibration-worksheet.js') as response:
            script=response.read().decode('utf-8')
        self.assertIn('Download blank worksheet',html)
        self.assertIn('href="/calibration-worksheet-blank.json"',html)
        self.assertIn('reload number is before calibration and mod effects',html.lower())
        self.assertIn('deviant-forge.calibration-test',script)
        with urlopen(self.base+'/calibration-worksheet-blank.json') as response:
            blank=json.load(response)
            self.assertIn('application/json',response.headers['Content-Type'])
            self.assertEqual(response.headers['Content-Disposition'],'attachment; filename="deviant-forge-calibration-blank.json"')
        self.assertEqual(blank['schema'],'deviant-forge.calibration-test')
        self.assertIsNone(blank['generated_at'])
        self.assertEqual([trial['status'] for trial in blank['trials']],['not_tested','not_tested'])
        self.assertIsNone(blank['trials'][0]['metrics']['trial_seconds']['value'])
        self.assertEqual(server.DB.stat().st_mtime_ns,before)

    def test_empty_account_complete_planned_build_save_reopen_and_ownership(self):
        initial=self.get('/api/state')
        self.assertEqual(initial['inventory'],[])
        listing=self.get('/api/builder-catalog')
        # Twelve additional Gloves sightings extend the formerly verified
        # catalog, without creating inventory ownership.
        self.assertEqual(len(listing['entries']),1285)
        by_id={e['id']:e for e in listing['entries']}
        self.assertIn('mod:helmet_mod:mag-expansion-general',by_id)
        self.assertIn('mod:helmet_mod:elemental-havoc-violent',by_id)
        ranged=[e for e in listing['entries'] if e['kind']=='weapon' and e['family']!='melee']
        melee=next(e for e in listing['entries'] if e['kind']=='weapon' and e['family']=='melee')
        slots={}
        for slot,source in server.ARMOR_SLOTS.items():
            gear=next(e for e in listing['entries'] if e['kind']=='armor' and e['slot']==source)
            mod=next(e for e in listing['entries'] if e['kind']=='mod' and e['slot']==server.MOD_SLOTS[slot])
            slots[slot]={'catalog_id':gear['id'],'level':10,'tier':3,'stars':2,'mod_id':mod['id'],'mod_level':7}
        for slot,gear in [('primary',ranged[0]),('secondary',ranged[1]),('melee',melee)]:
            slots[slot]={'catalog_id':gear['id'],'level':10,'tier':3,'stars':2}
        weapon_mod=next(e for e in listing['entries'] if e['kind']=='mod' and e['slot']=='weapon_mod')
        slots['primary'].update(mod_id=weapon_mod['id'],mod_level=8)
        saved=self.post('/api/planned-build',{'name':'No-upload plan','slots':slots})
        reopened=self.get('/api/builder-catalog')['planned_builds']
        self.assertEqual(len(reopened),1)
        self.assertEqual(reopened[0]['id'],saved['id'])
        self.assertEqual(reopened[0]['slots'],slots)
        self.assertEqual(self.get('/api/state')['inventory'],[])
        self.post('/api/catalog-ownership',{'catalog_id':weapon_mod['id'],'status':'unlocked','available_level':11})
        matched=next(e for e in self.get('/api/builder-catalog')['entries'] if e['id']==weapon_mod['id'])
        self.assertEqual((matched['ownership'],matched['available_level']),('unlocked',11))
        self.assertEqual(self.get('/api/state')['inventory'],[])
        duplicate=self.post('/api/planned-build',{'name':'No-upload plan copy','slots':slots})
        self.assertNotEqual(duplicate['id'],saved['id'])
        self.assertEqual(len(self.get('/api/builder-catalog')['planned_builds']),2)

    def test_shiny_mod_plan_roundtrip_and_evidence_gate(self):
        slots = {'bottoms': {'catalog_id': 'armor:savior-pants',
                             'mod_id': 'mod:pants_mod:elemental-resonance-aero',
                             'mod_level': 17, 'mod_shiny': True}}
        before_inventory = self.get('/api/state')['inventory']
        saved = self.post('/api/planned-build', {'name': 'Shiny fixture', 'slots': slots})
        reopened = next(row for row in self.get('/api/builder-catalog')['planned_builds']
                        if row['id'] == saved['id'])
        self.assertEqual(reopened['slots'], slots)
        selection = {'kind': 'planned_build', 'planned_build_id': saved['id']}
        blocked = structured_compare.compare({'left': selection, 'right': selection}, [reopened])
        self.assertEqual(blocked['left']['typed_main_effects'][0]['status'],
                         'evidence_opt_in_required')
        opted = structured_compare.compare({'left': selection, 'right': selection,
            'context': {'core_preview_opt_in': True, 'just_reloaded': True,
                        'previous_magazine_elemental_damage_instances': 10}}, [reopened])
        self.assertEqual(opted['left']['typed_main_effects'][0]['status'],
                         'observed_typed_output')
        self.assertEqual(self.get('/api/state')['inventory'], before_inventory)

    def test_incompatible_mod_and_ambiguous_artwork_are_not_guessed(self):
        image=self.get('/api/builder-catalog')
        self.assertTrue(image['artwork_coverage']['mod']['cached']>=837)
        missing=next(e for e in image['entries'] if e['kind']=='weapon' and e['image_missing'])
        self.assertIsNone(missing['artwork'])
        shown=next(e for e in image['entries'] if e['id']=='mod:boots_mod:against-all-odds-precision')
        self.assertIn('against-all-odds-precision',shown['artwork'])
        self.assertIn('against-all-odds-precision',shown['artwork_source'])
        self.assertTrue((server.ROOT/'static'/shown['artwork'].lstrip('/')).is_file())
        armor=next(e for e in image['entries'] if e['kind']=='armor' and e['slot']=='boots')
        wrong_mod=next(e for e in image['entries'] if e['kind']=='mod' and e['slot']=='helmet_mod')
        with self.assertRaisesRegex(ValueError,'incompatible'):
            server.validate_planned_slots({'shoes':{'catalog_id':armor['id'],'mod_id':wrong_mod['id'],'mod_level':1}})
        with self.assertRaisesRegex(ValueError,'Choose a mod before its level'):
            server.validate_planned_slots({'shoes':{'catalog_id':armor['id'],'mod_level':7}})

    def test_weapon_upgrade_dimensions_save_without_fake_equipment_level(self):
        selected={'primary':{'catalog_id':'weapon:awm','tier':5,'stars':3,
                             'calibration_blueprint':'Rapid Sniper Rifle',
                             'calibration_bonus':'Attack +40%; Weakspot DMG +16%',
                             'legacy_enhancement':3}}
        saved=self.post('/api/planned-build',{'name':'Weapon settings','slots':selected})
        reopened=next(b for b in self.get('/api/builder-catalog')['planned_builds'] if b['id']==saved['id'])
        self.assertEqual(reopened['slots'],selected)
        self.assertNotIn('level',reopened['slots']['primary'])
        self.assertEqual(self.get('/api/state')['inventory'],[])
        for field,value in [('tier',6),('stars',7),('legacy_enhancement',11)]:
            invalid={'primary':{**selected['primary'],field:value}}
            with self.assertRaisesRegex(ValueError,'outside supported input range'):
                server.validate_planned_slots(invalid)
        with self.assertRaisesRegex(ValueError,'requires a weapon'):
            server.validate_planned_slots({'helmet':{'catalog_id':'armor:agent-helmet',
                                                    'calibration_blueprint':'Rapid'}})
        changed=json.loads(json.dumps(selected))
        changed['primary']['calibration_bonus']='Attack +45%; Weakspot DMG +16%'
        comparison=planned_advisor.compare(selected,changed)
        self.assertFalse(comparison['winner_established'])
        self.assertIn('calibration_bonus',comparison['changes'][0]['fields'])
        self.assertTrue(any('calibration-blueprint rolls' in reason for reason in comparison['overall_blockers']))

    def test_current_weapon_readout_is_bound_to_its_exact_gear_setup(self):
        selected={'catalog_id':'weapon:aug-electron-cloud','tier':3,'stars':6}
        selected['weapon_readout']={'signature':json.dumps([selected['catalog_id'],3,6,None,None,None]),
                                    'attack':103,'rpm':720,'magazine':40,'reload_seconds':3}
        saved=self.post('/api/planned-build',{'name':'Measured current weapon','slots':{'primary':selected}})
        reopened=next(b for b in self.get('/api/builder-catalog')['planned_builds'] if b['id']==saved['id'])
        self.assertEqual(reopened['slots']['primary']['weapon_readout'],selected['weapon_readout'])
        with self.assertRaisesRegex(ValueError,'different gear setup'):
            server.validate_planned_slots({'primary':{**selected,'stars':5}})
        with self.assertRaisesRegex(ValueError,'Current weapon readout requires a primary weapon'):
            server.validate_planned_slots({'secondary':selected})
        with self.assertRaisesRegex(ValueError,'Invalid current weapon attack'):
            server.validate_planned_slots({'primary':{**selected,'weapon_readout':{**selected['weapon_readout'],'attack':-1}}})
        chance={**selected,'weapon_readout':{**selected['weapon_readout'],'base_trigger_chance_percent':24}}
        self.assertEqual(server.validate_planned_slots({'primary':chance})['primary']['weapon_readout']['base_trigger_chance_percent'],24)
        with self.assertRaisesRegex(ValueError,'Invalid current weapon base trigger chance percent'):
            server.validate_planned_slots({'primary':{**chance,'weapon_readout':{**chance['weapon_readout'],'base_trigger_chance_percent':101}}})

    def test_saved_weapon_measurement_and_gold_calibration_are_instance_specific(self):
        identity='weapon:aug-electron-cloud'
        vanguard={'blueprint_name':'Vanguard Rifle Calibration Blueprint','rarity':'gold','style':'Vanguard Style',
                  'fixed_effects':'After reloading from empty, the next shot is guaranteed to trigger its keyword effect.',
                  'rolls':[{'stat':'Weapon DMG','value_percent':34.3,'range_min':34,'range_max':50},
                           {'stat':'Crit Rate','value_percent':15.3,'range_min':12,'range_max':16}],
                  'source_ref':'libfile_3f0148c85b8c8191b936bc3ad9663123'}
        energy={'blueprint_name':'Energy Rifle Calibration Blueprint','rarity':'gold','style':'Energy Style',
                'fixed_effects':'After taking damage, automatically reload 1 bullet (cooldown: 0.3s). Attack +10%.',
                'rolls':[{'stat':'Weapon DMG','value_percent':42.4,'range_min':34,'range_max':50},
                         {'stat':'Elemental DMG (Blaze, Frost, Shock, Blast)','value_percent':17.5,'range_min':15,'range_max':20}],
                'source_ref':'libfile_a194f3bfeaf081918ba9f3ea67ebb09e'}
        base={'catalog_id':identity,'slot':'primary','tier':4,'stars':6}
        with self.assertRaises(HTTPError):
            self.post('/api/my-gear/add',{**base,'weapon_stats':{'attack':-1,'rpm':690}})
        first=self.post('/api/my-gear/add',{**base,'calibration_profile':vanguard,'weapon_stats':{'attack':137,'rpm':690}})['id']
        second=self.post('/api/my-gear/add',{**base,'tier':5,'calibration_profile':energy})['id']
        gear={row['id']:row for row in self.get('/api/builder-catalog')['my_gear']}
        self.assertEqual(gear[first]['weapon_stats'],{'attack':137,'rpm':690})
        self.assertEqual(gear[first]['calibration_profile']['rarity'],'gold')
        self.assertEqual(gear[first]['calibration_profile']['rolls'][1]['value_percent'],15.3)
        self.assertIsNone(gear[second]['weapon_stats'])
        self.assertEqual(gear[second]['calibration_profile']['rolls'][1]['value_percent'],17.5)
        self.post('/api/my-gear/update',{'id':first,**base,'calibration_profile':vanguard})
        self.assertEqual(next(row for row in self.get('/api/builder-catalog')['my_gear'] if row['id']==first)['weapon_stats'],{'attack':137,'rpm':690})
        self.post('/api/my-gear/update',{'id':first,**base,'tier':5,'calibration_profile':vanguard})
        self.assertIsNone(next(row for row in self.get('/api/builder-catalog')['my_gear'] if row['id']==first)['weapon_stats'])
        self.assertEqual(self.get('/api/state')['inventory'].__len__(),2)

    def test_calibration_rolls_are_optional_and_instance_specific(self):
        base={'catalog_id':'weapon:aug-electron-cloud','slot':'primary','tier':3,'stars':6}
        rapid={'blueprint_name':'Rapid Assault Rifle Calibration Blueprint','rarity':'purple',
               'style':'Rapid Shot Style','fixed_effects':'Fire Rate +15%; Reload Speed +10%; Attack -10%',
               'rolls':[{'stat':'Weapon DMG','value_percent':29.6,'range_min':26,'range_max':33},
                        {'stat':'Weakspot DMG','value_percent':18.6,'range_min':15,'range_max':21}]}
        alternate=json.loads(json.dumps(rapid))
        alternate['rolls'][0]['value_percent']=27.0
        alternate['rolls'][1]['value_percent']=15.5
        first=self.post('/api/my-gear/add',{**base,'calibration_profile':rapid})
        second=self.post('/api/my-gear/add',{**base,'calibration_profile':alternate})
        gear={item['id']:item for item in self.get('/api/builder-catalog')['my_gear']}
        self.assertEqual(len(gear),2)
        self.assertEqual(gear[first['id']]['calibration_profile']['rolls'][0]['value_percent'],29.6)
        self.assertEqual(gear[second['id']]['calibration_profile']['rolls'][0]['value_percent'],27.0)
        self.assertIsNone(gear[first['id']]['calibration_upgrade_level'])
        self.post('/api/my-gear/update',{'id':first['id'],**base})
        retained=next(item for item in self.get('/api/builder-catalog')['my_gear'] if item['id']==first['id'])
        self.assertEqual(retained['calibration_profile'],rapid,'Older settings updates must not clear structured calibration')
        plan={'primary':{'catalog_id':base['catalog_id'],'inventory_id':first['id'],'tier':3,'stars':6,
                         'calibration_profile':rapid}}
        saved=self.post('/api/planned-build',{'name':'Rapid roll','slots':plan})
        changed={'primary':{**plan['primary'],'inventory_id':second['id'],'calibration_profile':alternate}}
        self.assertIn('calibration_profile',planned_advisor.compare(plan,changed)['changes'][0]['fields'])
        reopened=next(row for row in self.get('/api/builder-catalog')['planned_builds'] if row['id']==saved['id'])
        self.assertEqual(reopened['slots'],plan)
        with self.assertRaisesRegex(ValueError,'no pre-2026 legacy calibration upgrade level'):
            server.validate_planned_slots({'primary':{**plan['primary'],'calibration_upgrade_level':2}})
        with self.assertRaisesRegex(ValueError,'no pre-2026 legacy calibration upgrade level'):
            server.validate_planned_slots({'primary':{**plan['primary'],'legacy_enhancement':2}})
        with self.assertRaisesRegex(ValueError,'Calibration blueprint name required'):
            server.validate_planned_slots({'primary':{'catalog_id':base['catalog_id'],'calibration_profile':{'style':'Rapid Shot Style'}}})
        with self.assertRaisesRegex(ValueError,'Invalid calibration roll range'):
            server.validate_planned_slots({'primary':{'catalog_id':base['catalog_id'],'calibration_profile':{**rapid,'rolls':[{'stat':'Weapon DMG','value_percent':29.6,'range_min':33,'range_max':26}]}}})
        server.validate_planned_slots({'primary':{'catalog_id':base['catalog_id'],'calibration_profile':{'blueprint_name':'Unrecorded gold calibration','rarity':'gold','rolls':[]}}})
        with self.assertRaisesRegex(ValueError,'outside its recorded range'):
            server.validate_planned_slots({'primary':{'catalog_id':base['catalog_id'],'calibration_profile':{**rapid,'rolls':[{'stat':'Weapon DMG','value_percent':40,'range_min':26,'range_max':33}]}}})

    def test_accessories_are_explicit_compatible_and_saved_per_weapon(self):
        listing=self.get('/api/builder-catalog')
        items={item['id']:item for item in listing['accessories']}
        self.assertEqual(len(items),10)
        suppressor='accessory:tactical-suppressor'
        grip='accessory:light-front-grip'
        flash_hider='accessory:tactical-flash-hider'
        magazine='accessory:amended-rifle-mag'
        self.assertIn('weapon:aug-electron-cloud',items[suppressor]['compatible_weapon_ids'])
        self.assertEqual(items[flash_hider]['effects'],[['Stability',16]])
        self.assertNotIn('weapon:aug-electron-cloud',items[grip]['compatible_weapon_ids'])
        self.assertIn('weapon:m416',items[grip]['compatible_weapon_ids'])
        self.assertIn('weapon:aug-electron-cloud',items[magazine]['compatible_weapon_ids'])
        self.assertIn('weapon:aug-electron-cloud',items['accessory:infrared-indicator']['compatible_weapon_ids'])
        self.assertNotIn('weapon:aug-electron-cloud',items['accessory:elite-vertical-grip']['compatible_weapon_ids'])
        self.assertNotIn('weapon:kam',items['accessory:elite-vertical-grip']['compatible_weapon_ids'])
        self.assertIn('weapon:kam-pioneer',items['accessory:elite-vertical-grip']['compatible_weapon_ids'])
        self.assertIn('weapon:aug-electron-cloud',items['accessory:recon-combat-optic']['compatible_weapon_ids'])
        self.assertEqual(items['accessory:recon-combat-optic']['zoom'],4)
        self.assertEqual(items['accessory:compact-reflex-sight']['zoom'],2)
        base={'catalog_id':'weapon:aug-electron-cloud','slot':'primary','tier':3,'stars':6}
        with self.assertRaises(HTTPError):
            self.post('/api/my-gear/add',{**base,'accessories':{'muzzle':suppressor}})
        self.post('/api/accessory-ownership',{'accessory_id':suppressor,'status':'unlocked'})
        self.post('/api/accessory-ownership',{'accessory_id':magazine,'status':'unlocked'})
        saved=self.post('/api/my-gear/add',{**base,'accessories':{'muzzle':suppressor,'magazine':magazine}})
        other=self.post('/api/my-gear/add',base)
        gear={item['id']:item for item in self.get('/api/builder-catalog')['my_gear']}
        self.assertEqual(gear[saved['id']]['accessories'],{'muzzle':suppressor,'magazine':magazine})
        self.assertEqual(gear[other['id']]['accessories'],{})
        self.post('/api/my-gear/update',{'id':saved['id'],**base,'accessories':{'muzzle':suppressor}})
        plan={'primary':{'catalog_id':base['catalog_id'],'inventory_id':saved['id'],'accessories':{'muzzle':suppressor}}}
        planned=self.post('/api/planned-build',{'name':'With suppressor','slots':plan})
        self.assertEqual(next(row for row in self.get('/api/builder-catalog')['planned_builds'] if row['id']==planned['id'])['slots'],plan)
        before=planned_advisor.analyze(plan)
        self.assertIn('Bullet Velocity',str(before['slots'][0]['accessories']))
        changed={'primary':{**plan['primary'],'accessories':{}}}
        self.assertIn('accessories',planned_advisor.compare(plan,changed)['changes'][0]['fields'])
        with self.assertRaisesRegex(ValueError,'incompatible'):
            server.validate_planned_slots({'primary':{'catalog_id':base['catalog_id'],'accessories':{'tactics':grip}}})
        self.post('/api/accessory-ownership',{'accessory_id':suppressor,'status':'unknown'})
        self.assertFalse(next(item for item in self.get('/api/builder-catalog')['accessories'] if item['id']==suppressor)['recorded_unlocked'])
        self.assertEqual(next(item for item in self.get('/api/builder-catalog')['my_gear'] if item['id']==saved['id'])['accessories'],{'muzzle':suppressor})
        self.assertEqual(self.get('/api/state')['inventory'].__len__(),2)

    def test_mod_level_override_is_instance_specific_and_preserves_evidence(self):
        mod_id='mod:weapon_mod:shock-diffusion-power-surge'
        manual=self.post('/api/mod-collection/add',{'catalog_id':mod_id})['id']
        with server.connect() as connection:
            connection.execute("INSERT INTO inventory VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ('observed-copy','Shock Diffusion','mod_unlock','weapon_mod',None,'Power Surge',11,None,
                 '{}',json.dumps({'catalog_id':mod_id}),'old-observation','[]',server.now(),server.now(),0))
        build={'primary':{'catalog_id':'weapon:aug-electron-cloud','mod_id':mod_id,'mod_level':11}}
        saved=self.post('/api/planned-build',{'name':'Keep plan level','slots':build})
        self.post('/api/mod-collection/level',{'id':manual,'level':9})
        self.post('/api/mod-collection/level',{'id':manual,'level':10})
        self.post('/api/mod-collection/level',{'id':'observed-copy','level':10})
        mods={item['id']:item for item in self.get('/api/builder-catalog')['owned_mods']}
        self.assertEqual((mods[manual]['level'],mods['observed-copy']['level']),(10,10))
        self.assertEqual(mods['observed-copy']['level_source'],'manual override')
        recorded=next(item for item in self.get('/api/state')['inventory'] if item['id']=='observed-copy')
        self.assertEqual(recorded['stats']['original_observed_level'],11)
        self.assertEqual(recorded['source_observation'],'old-observation')
        self.post('/api/mod-collection/level',{'id':manual,'level':None})
        mods={item['id']:item for item in self.get('/api/builder-catalog')['owned_mods']}
        self.assertIsNone(mods[manual]['level'])
        self.assertEqual(mods['observed-copy']['level'],10)
        self.assertEqual(next(row for row in self.get('/api/builder-catalog')['planned_builds'] if row['id']==saved['id'])['slots'],build)
        for invalid in (0,18,'9.5',True):
            with self.assertRaises(HTTPError):self.post('/api/mod-collection/level',{'id':manual,'level':invalid})

    def test_mod_level_edit_invalidates_old_roll_values_and_restores_source_level(self):
        mod_id='mod:weapon_mod:shock-diffusion-power-surge'
        line='Weapon DMG + 5%'
        typed=mod_rolls.parse_rows([line],source_audit={'status':'source_text_and_numbers_checked','attribute_rows':[{'source_text':line}]})
        stats={'observed_attribute_lines':[line],'typed_modifiers':typed,'video_import':{'proposal_id':'source-evidence'}}
        with server.connect() as connection:
            connection.execute('INSERT INTO inventory VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                ('roll-copy','Shock Diffusion','mod_unlock','weapon_mod',None,'Power Surge',11,None,
                 json.dumps(stats),json.dumps({'catalog_id':mod_id}),'source-observation','[]',server.now(),server.now(),0))
        self.post('/api/mod-collection/level',{'id':'roll-copy','level':10})
        changed=next(item for item in self.get('/api/state')['inventory'] if item['id']=='roll-copy')
        self.assertEqual(changed['stats']['typed_modifiers'],[])
        self.assertEqual(changed['stats']['source_observed_typed_modifiers'],typed)
        self.assertEqual(changed['stats']['observed_attribute_lines'],[line])
        self.post('/api/mod-collection/level',{'id':'roll-copy','level':11})
        restored=next(item for item in self.get('/api/state')['inventory'] if item['id']=='roll-copy')
        self.assertEqual(restored['stats']['typed_modifiers'],typed)

    def test_formula_can_use_exact_field_guide_profile_rows_without_borrowing_inventory(self):
        mod_id='mod:chest_mod:ardent-shield-deviant-energy'
        build=self.post('/api/planned-build',{'name':'Profile formula fixture','slots':{
            'primary':{'catalog_id':'weapon:aug-electron-cloud','tier':5,'stars':5},
            'top':{'catalog_id':'armor:agent-top','mod_id':mod_id,'mod_level':8}}})
        row=mod_rolls.parse_rows(['Weapon DMG + 5%'],source_audit={
            'status':'source_text_and_numbers_checked',
            'attribute_rows':[{'source_text':'Weapon DMG + 5%'}]})[0]
        row['selected_slot']='top'
        request={'build_id':build['id'],'use_tier_v_preview':True,
                 'encounter':{'tech_policy':'assume_active'}}
        owned=self.post('/api/build-combat-formula',request)
        self.assertEqual(owned['modifier_count'],0)
        self.assertTrue(owned['selected_owned_mods']['unresolved'])
        preview={'rows':[row],'issues':[],
                 'selected':[{'slot':'top','catalog_id':mod_id,'level':8,
                              'status':'source_backed_rows_with_unknown_tech','row_count':1}]}
        with patch.object(server.field_guide_profiles,'build_calculation_preview',return_value=preview) as resolver:
            profile=self.post('/api/build-combat-formula',{
                **request,'modifier_source':'personal_field_guide'})
        resolver.assert_called_once()
        self.assertEqual(resolver.call_args.args[1],'personal')
        self.assertEqual(profile['modifier_source'],'personal_field_guide')
        self.assertEqual(profile['modifier_count'],1)
        self.assertEqual(profile['selected_owned_mods']['resolved_slots'],['top'])
        self.assertGreater(profile['result']['energy']['base_direct_hit_after_bonuses'],
                           owned['result']['energy']['base_direct_hit_after_bonuses'])
        self.assertEqual(self.get('/api/state')['planned_builds'][0]['slots']['top']['mod_level'],8)
        with patch.object(server.field_guide_profiles,'build_calculation_preview',return_value={
            'rows':[],'selected':[],'issues':[{'slot':'top','catalog_id':mod_id,
                'reason':'saved mod level differs from this profile'}]}):
            mismatch=self.post('/api/build-combat-formula',{
                **request,'modifier_source':'personal_field_guide'})
        self.assertEqual(mismatch['modifier_count'],0)
        self.assertIsNone(mismatch['result']['energy']['durations']['60']['total_damage_bounds'])
        with server.connect() as connection:
            field_guide_profiles.set_manual(connection,'personal',mod_id,8)
        fight={'dodge_fraction':0,'pre_mod_reload_seconds':2,
               'accepted_energy_returns_per_second':0,'hit_rate':1,
               'weakspot_fraction':.2,'crit_weak_overlap':.02}
        stream={'events_per_active_second':0}
        full={**request,'encounter':fight,'power_surge':stream,'orb':stream}
        unevidenced=self.post('/api/build-combat-formula',{
            **full,'modifier_source':'personal_field_guide'})
        self.assertEqual(unevidenced['modifier_count'],0)
        self.assertIn('no source-checked numerical rows',
                      unevidenced['selected_owned_mods']['unresolved'][0]['reason'])
        self.assertIsNone(unevidenced['result']['energy']['durations']['60']['total_damage_bounds'])
        self.assertFalse(unevidenced['result']['energy']['durations']['60']['complete_under_entered_assumptions'])
        self.assertIsNone(unevidenced['result']['comparison']['60']['winner'])
        self.assertGreater(unevidenced['result']['energy']['base_direct_hit_after_bonuses'],0)
        self.assertIsNotNone(unevidenced['result']['energy']['durations']['60']['bullet_damage_bounds'])
        no_mod=self.post('/api/planned-build',{'name':'Intentional no-mod baseline','slots':{
            'primary':{'catalog_id':'weapon:aug-electron-cloud','tier':5,'stars':5}}})
        no_mod_result=self.post('/api/build-combat-formula',{
            **full,'build_id':no_mod['id'],'modifier_source':'personal_field_guide'})
        self.assertFalse(no_mod_result['selected_owned_mods']['unresolved'])
        self.assertIsNotNone(no_mod_result['result']['energy']['durations']['60']['total_damage_bounds'])
        with self.assertRaises(HTTPError) as invalid:
            self.post('/api/build-combat-formula',{**request,'modifier_source':'new_player'})
        invalid.exception.close()

    def test_unsaved_external_effect_changes_only_supported_component_and_resets(self):
        before_state=self.get('/api/state')
        fight={'dodge_fraction':0,'pre_mod_reload_seconds':2,
               'accepted_energy_returns_per_second':0,'hit_rate':1,
               'weakspot_fraction':.2,'crit_weak_overlap':.02}
        request={'use_tier_v_preview':True,'encounter':fight,
                 'power_surge':{'events_per_active_second':1,
                                'pre_mod_damage_per_event':100,
                                'elemental':False,'status':False},
                 'orb':{'events_per_active_second':0}}
        effect={'source_kind':'food','name':'Synthetic observed food',
                'stat_type':'weapon_damage_percent','value_percent':10,
                'source_note':'Temporary test fixture only','activation':'observed_active',
                'apply_hypothesis':True,'baseline_excludes_effect':True,
                'active_for_interval':True}
        base=self.post('/api/build-combat-formula',request)
        applied=self.post('/api/build-combat-formula',{**request,'external_effect':effect})
        self.assertTrue(applied['external_effect']['applied'])
        self.assertGreater(applied['result']['energy']['base_direct_hit_after_bonuses'],
                           base['result']['energy']['base_direct_hit_after_bonuses'])
        self.assertEqual(applied['result']['energy']['durations']['60']['power_surge']['damage'],
                         base['result']['energy']['durations']['60']['power_surge']['damage'])
        self.assertEqual(applied['modifier_count'],1)
        self.assertEqual(self.post('/api/build-combat-formula',request)['result']['energy']['base_direct_hit_after_bonuses'],
                         base['result']['energy']['base_direct_hit_after_bonuses'])
        excluded=self.post('/api/build-combat-formula',{**request,'external_effect':{
            **effect,'activation':'unknown','apply_hypothesis':False}})
        self.assertEqual(excluded['modifier_count'],0)
        self.assertIsNone(excluded['result']['energy']['durations']['60']['total_damage_bounds'])
        for activation in ('unknown','inactive','assumed_active'):
            with self.subTest(activation=activation),self.assertRaises(HTTPError) as refused:
                self.post('/api/build-combat-formula',{**request,'external_effect':{
                    **effect,'activation':activation}})
            refused.exception.close()
        healing=self.post('/api/build-combat-formula',{**request,'external_effect':{
            **effect,'stat_type':'healing_or_shield_unmodeled','value_percent':20}})
        self.assertEqual(healing['modifier_count'],0)
        self.assertEqual(healing['result']['energy']['base_direct_hit_after_bonuses'],
                         base['result']['energy']['base_direct_hit_after_bonuses'])
        with self.assertRaises(HTTPError) as duplicate:
            self.post('/api/build-combat-formula',{**request,'external_effect':{
                **effect,'baseline_excludes_effect':False}})
        self.assertIn('baseline excludes',duplicate.exception.read().decode())
        duplicate.exception.close()
        after_state=self.get('/api/state')
        self.assertEqual(before_state['inventory'],after_state['inventory'])
        self.assertEqual(before_state['planned_builds'],after_state['planned_builds'])
        self.assertEqual(before_state['field_guide_profiles'],after_state['field_guide_profiles'])

    def test_planned_calibration_sensitivity_reaches_existing_formula_api_without_ownership(self):
        before=self.get('/api/state')
        baseline={**combat_formula.PREVIEW}
        encounter={'scenario':'other_unknown','pre_mod_reload_seconds':2,'dodge_fraction':0,
                   'hit_rate':1,'weakspot_fraction':0,'crit_weak_overlap':0,
                   'accepted_energy_returns_per_second':0,'tech_policy':'exclude_unknown'}
        request={'build_id':None,'baseline':baseline,'modifier_source':'owned_instances',
                 'encounter':encounter,'power_surge':{},'orb':{},
                 'planned_sensitivity':{'psi_intensity':1000,'energy_orb_enemy_hits':0,
                                        'rapid_orb_enemy_hits':0,'elemental_model':'shared_bucket'}}
        response=self.post('/api/build-combat-formula',request)
        self.assertIsNone(response['build_id'])
        self.assertAlmostEqual(response['planned_sensitivity']['energy']['expected_roots_independent_trials'],136.8)
        self.assertAlmostEqual(response['planned_sensitivity']['rapid']['expected_roots_independent_trials'],157.2)
        self.assertAlmostEqual(response['planned_sensitivity']['energy']['included_components_sum'],176444.62176+100890)
        self.assertIsNone(response['result']['energy']['durations']['60']['total_damage_bounds'])
        for key in ('inventory','planned_builds','field_guide_profiles'):
            self.assertEqual(before[key],self.get('/api/state')[key])

    def test_multiple_external_effects_feed_separate_components_without_saving(self):
        before=self.get('/api/state')
        request={'use_tier_v_preview':True,
                 'encounter':{'dodge_fraction':0,'pre_mod_reload_seconds':2,
                              'accepted_energy_returns_per_second':0,'hit_rate':1,
                              'weakspot_fraction':0,'crit_weak_overlap':0},
                 'power_surge':{'events_per_active_second':1,
                                'pre_mod_damage_per_event':100,'status':True,'elemental':False},
                 'orb':{'events_per_active_second':0}}
        weapon={'source_kind':'food','name':'Observed meal','stat_type':'weapon_damage_percent',
                'value_percent':10,'source_note':'Isolated observed fixture','activation':'observed_active',
                'apply_hypothesis':True,'baseline_excludes_effect':True,'active_for_interval':True}
        status={**weapon,'source_kind':'deviation','name':'Observed companion',
                'stat_type':'status_damage_percent','value_percent':20}
        def calculate(effects,compatible=False):
            return self.post('/api/build-combat-formula',{
                **request,'external_effects':effects,'assume_external_compatibility':compatible})
        base=calculate([])
        only_weapon=calculate([weapon])
        only_status=calculate([status])
        both=calculate([weapon,status],True)
        self.assertGreater(only_weapon['result']['energy']['base_direct_hit_after_bonuses'],
                           base['result']['energy']['base_direct_hit_after_bonuses'])
        self.assertEqual(only_weapon['result']['energy']['durations']['60']['power_surge']['damage'],
                         base['result']['energy']['durations']['60']['power_surge']['damage'])
        self.assertEqual(only_status['result']['energy']['base_direct_hit_after_bonuses'],
                         base['result']['energy']['base_direct_hit_after_bonuses'])
        self.assertGreater(only_status['result']['energy']['durations']['60']['power_surge']['damage'],
                           base['result']['energy']['durations']['60']['power_surge']['damage'])
        self.assertEqual(both['result']['energy']['base_direct_hit_after_bonuses'],
                         only_weapon['result']['energy']['base_direct_hit_after_bonuses'])
        self.assertEqual(both['result']['energy']['durations']['60']['power_surge']['damage'],
                         only_status['result']['energy']['durations']['60']['power_surge']['damage'])
        self.assertEqual(calculate([status,weapon],True)['result'],both['result'])
        self.assertEqual(calculate([weapon,status,weapon],True)['result'],both['result'])
        self.assertEqual(len([c for c in both['external_contributions'] if c['applied']]),2)
        same_name_drink={**weapon,'source_kind':'drink','value_percent':20}
        same_named_sources=self.post('/api/build-combat-formula',{
            **request,'external_effects':[weapon,same_name_drink],
            'assume_external_compatibility':True,'assume_external_additive_bucket':True})
        by_kind={item['source_kind']:item for item in same_named_sources['external_contributions']}
        self.assertEqual(set(by_kind),{'food','drink'})
        self.assertTrue(all(item['applied'] for item in by_kind.values()))
        self.assertAlmostEqual(by_kind['drink']['energy_direct_hit_delta'],
                               2*by_kind['food']['energy_direct_hit_delta'])
        self.assertEqual(same_named_sources['result'],self.post('/api/build-combat-formula',{
            **request,'external_effects':[same_name_drink,weapon],
            'assume_external_compatibility':True,'assume_external_additive_bucket':True})['result'])
        withheld=calculate([weapon,status])
        self.assertEqual(withheld['modifier_count'],0)
        self.assertIsNone(withheld['result']['energy']['durations']['60']['total_damage_bounds'])
        disabled=calculate([{**status,'activation':'inactive','apply_hypothesis':False}])
        self.assertEqual(disabled['result']['energy']['base_direct_hit_after_bonuses'],
                         base['result']['energy']['base_direct_hit_after_bonuses'])
        self.assertEqual(disabled['result']['energy']['durations']['60']['power_surge']['damage'],
                         base['result']['energy']['durations']['60']['power_surge']['damage'])
        with_healing=calculate([weapon,{**status,'stat_type':'healing_or_shield_unmodeled',
                                        'name':'Unsupported shield observation'}])
        self.assertEqual(with_healing['result']['energy']['base_direct_hit_after_bonuses'],
                         only_weapon['result']['energy']['base_direct_hit_after_bonuses'])
        self.assertEqual(sum(item['applied'] for item in with_healing['external_effects']),1)
        with self.assertRaises(HTTPError) as error:
            calculate([{**weapon,'baseline_excludes_effect':False}])
        error.exception.close()
        for malformed in ([{}],[None],[weapon,{}],[{'source_kind':'food','name':'missing stat'}]):
            with self.subTest(malformed=malformed), self.assertRaises(HTTPError) as error:
                calculate(malformed)
            self.assertEqual(error.exception.code,400)
            error.exception.close()
        after=self.get('/api/state')
        for key in ('inventory','planned_builds','field_guide_profiles'):
            self.assertEqual(before[key],after[key])


    def test_formula_api_refuses_complete_coverage_without_rolls_or_unique_proposal_slots(self):
        response=self.post('/api/build-combat-formula',{'use_tier_v_preview':True})
        self.assertFalse(response['coverage_complete'])
        self.assertIn('No typed mod rolls',response['coverage_reasons'][0])
        six=self.post('/api/planned-build',{'name':'Six-star Tier V test',
            'slots':{'primary':{'catalog_id':'weapon:aug-electron-cloud','tier':5,'stars':6}}})
        with self.assertRaises(HTTPError) as blocked:
            self.post('/api/build-combat-formula',{'build_id':six['id'],'use_tier_v_preview':True})
        self.assertIn('five-star',blocked.exception.read().decode())
        blocked.exception.close()
        five=self.post('/api/planned-build',{'name':'Five-star Tier V test',
            'slots':{'primary':{'catalog_id':'weapon:aug-electron-cloud','tier':5,'stars':5}}})
        compatible=self.post('/api/build-combat-formula',{'build_id':five['id'],'use_tier_v_preview':True})
        self.assertEqual(compatible['result']['energy']['baseline_source'],combat_formula.PREVIEW['source_ref'])
        rows=['Weapon DMG + 5%']
        proposal={'ownership':'unlocked','slot':'chest_mod','attribute_rows':rows,
                  'source_audit':{'status':'source_text_and_numbers_checked','attribute_rows':[{'source_text':rows[0]}]}}
        with server.connect() as connection:
            connection.execute("INSERT INTO video_import_runs(id,media_id,fingerprint,status,options,summary,created,updated) VALUES(?,?,?,?,?,?,?,?)",
                               ('test-run','test-media','test-fingerprint','reviewed','{}','{}',server.now(),server.now()))
            for pid in ('p1','p2','empty'):
                connection.execute("INSERT INTO video_import_proposals(id,run_id,identity_key,data,status,updated) VALUES(?,?,?,?,?,?)",
                                   (pid,'test-run',pid,json.dumps({**proposal,'attribute_rows':[]} if pid=='empty' else proposal),'reviewed',server.now()))
        with self.assertRaises(HTTPError):
            self.post('/api/build-combat-formula',{'use_tier_v_preview':True,'proposal_ids':['p1','p2']})
        encounter={'dodge_fraction':0,'pre_mod_reload_seconds':2,'accepted_energy_returns_per_second':0,
                   'hit_rate':1,'weakspot_fraction':.2,'crit_weak_overlap':.02}
        streams={'events_per_active_second':0}
        no_proposal=self.post('/api/build-combat-formula',{'use_tier_v_preview':True,'encounter':encounter,
                         'power_surge':streams,'orb':streams})
        self.assertIsNotNone(no_proposal['result']['energy']['durations']['60']['total_damage_bounds'])
        selected_empty=self.post('/api/build-combat-formula',{'use_tier_v_preview':True,'proposal_ids':['empty'],
                         'encounter':encounter,'power_surge':streams,'orb':streams})
        self.assertFalse(selected_empty['coverage_complete'])
        self.assertTrue(any('no typed attribute rows' in reason for reason in selected_empty['coverage_reasons']))
        self.assertIsNone(selected_empty['result']['energy']['durations']['60']['total_damage_bounds'])

    def test_saved_plan_unique_owned_roll_reaches_formula_only_under_explicit_tech_assumption(self):
        mod_id='mod:weapon_mod:shock-rampage-power-surge'
        build=self.post('/api/planned-build',{'name':'Owned mod evidence fixture',
            'slots':{'primary':{'catalog_id':'weapon:aug-electron-cloud','tier':5,'stars':5,
                                'mod_id':mod_id,'mod_level':17}}})
        request={'build_id':build['id'],'use_tier_v_preview':True,
                 'encounter':{'pre_mod_reload_seconds':2,'dodge_fraction':0,'hit_rate':1,
                              'weakspot_fraction':0,'crit_weak_overlap':0,
                              'accepted_energy_returns_per_second':0},
                 'power_surge':{'events_per_active_second':0},'orb':{'events_per_active_second':0}}
        absent=self.post('/api/build-combat-formula',request)
        self.assertEqual(absent['modifier_count'],0)
        self.assertIn('owned instance missing',absent['selected_owned_mods']['unresolved'][0]['reason'])
        with server.connect() as connection:
            connection.execute('INSERT INTO inventory VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                ('exact-instance','Shock Rampage','mod_unlock','weapon_mod',None,'Power Surge',17,None,
                 '{}',json.dumps({'catalog_id':mod_id}),'fixture-source','[]',server.now(),server.now(),0))
        no_rows=self.post('/api/build-combat-formula',request)
        issue=no_rows['selected_owned_mods']['unresolved'][0]
        self.assertEqual(issue['code'],'owned_roll_evidence_missing')
        self.assertEqual((issue['mod_name'],issue['selected_level'],issue['owned_instance_id']),
                         ('Shock Rampage',17,'exact-instance'))
        self.assertEqual(no_rows['modifier_count'],0)
        line='Weapon DMG + 5%'
        typed=mod_rolls.parse_rows([line],source_audit={'status':'source_text_and_numbers_checked',
                                                       'attribute_rows':[{'source_text':line}]})
        stats={'typed_modifiers':typed,'observed_attribute_lines':[line],'original_observed_level':17}
        with server.connect() as connection:
            connection.execute('UPDATE inventory SET stats=? WHERE id=?',(json.dumps(stats),'exact-instance'))
        default=self.post('/api/build-combat-formula',request)
        self.assertEqual(default['selected_owned_mods']['unresolved'],[])
        self.assertEqual(default['candidate_modifier_count'],1)
        self.assertEqual(default['modifier_count'],0)
        self.assertEqual(len(default['result']['energy']['typed_modifiers_tech_gated']),1)
        self.assertIsNone(default['result']['energy']['durations']['60']['total_damage_bounds'])
        assumed=self.post('/api/build-combat-formula',{**request,'encounter':{**request['encounter'],
                                                        'tech_policy':'assume_active'}})
        self.assertEqual(assumed['modifier_count'],1)
        self.assertFalse(assumed['coverage_complete'])
        self.assertTrue(any('Tech-level assumption' in reason for reason in assumed['coverage_reasons']))
        self.assertAlmostEqual(assumed['result']['energy']['base_direct_hit_after_bonuses'],
                               default['result']['energy']['base_direct_hit_after_bonuses']+241*1.1*.05)
        self.assertIsNotNone(assumed['result']['energy']['durations']['60']['bullet_damage_bounds'])
        self.assertIsNone(assumed['result']['energy']['durations']['60']['total_damage_bounds'])
        self.assertEqual(assumed['selected_core_effects'][0]['status'],'unmodeled_core_effect')
        observed=self.post('/api/build-combat-formula',{**request,'encounter':{**request['encounter'],
                                                        'tech_policy':'assume_active'},
                              'power_surge':{'events_per_active_second':0,'rate_origin':'measured_selected_build'}})
        self.assertIsNotNone(observed['result']['energy']['durations']['60']['total_damage_bounds'])
        self.assertEqual(observed['selected_core_effects'][0]['status'],'included_in_entered_observed_rate')
        with server.connect() as connection:
            connection.execute('UPDATE inventory SET level=16 WHERE id=?',('exact-instance',))
        mismatch=self.post('/api/build-combat-formula',request)
        self.assertEqual(mismatch['modifier_count'],0)
        self.assertEqual(mismatch['selected_owned_mods']['unresolved'][0]['code'],'owned_level_mismatch')
        self.assertEqual(mismatch['selected_owned_mods']['unresolved'][0]['available_levels'],[16])

    def test_all_damage_observation_requires_separate_bucket_model(self):
        encounter={'dodge_fraction':0,'pre_mod_reload_seconds':2,'accepted_energy_returns_per_second':0,
                   'hit_rate':1,'weakspot_fraction':0,'crit_weak_overlap':0,'tech_policy':'assume_active'}
        streams={'events_per_active_second':0}
        request={'use_tier_v_preview':True,'encounter':encounter,'power_surge':streams,'orb':streams}
        amount='Increases damage dealt to all DMG Boost by + 3.0%'
        with server.connect() as connection:
            connection.execute("INSERT INTO video_import_runs(id,media_id,fingerprint,status,options,summary,created,updated) VALUES(?,?,?,?,?,?,?,?)",
                               ('all-damage-test-run','test-media','all-damage-test','reviewed','{}','{}',server.now(),server.now()))
            for key,rows in [('all-only',[amount]),('target-mixed',[amount,'Damage to bosses +5%'])]:
                payload={'ownership':'unlocked','slot':'chest_mod','attribute_rows':rows,
                         'source_audit':{'status':'source_text_and_numbers_checked',
                                         'attribute_rows':[{'source_text':line} for line in rows]}}
                connection.execute("INSERT INTO video_import_proposals(id,run_id,identity_key,data,status,updated) VALUES(?,?,?,?,?,?)",
                                   (key,'all-damage-test-run',key,json.dumps(payload),'reviewed',server.now()))
        default=self.post('/api/build-combat-formula',{**request,'proposal_ids':['all-only']})
        self.assertEqual(default['modifier_count'],0)
        self.assertEqual(default['candidate_modifier_count'],1)
        self.assertEqual(default['result']['energy']['typed_modifiers_unmodeled'][0]['raw_text'],amount)
        self.assertIsNone(default['result']['energy']['durations']['60']['total_damage_bounds'])
        self.assertTrue(any('All DMG Boost bucket placement' in x for x in default['coverage_reasons']))
        hypothetical=self.post('/api/build-combat-formula',{**request,'proposal_ids':['all-only'],
            'encounter':{**encounter,'all_damage_model':'independent_outgoing_multiplier'}})
        self.assertEqual(hypothetical['modifier_count'],1)
        self.assertEqual(hypothetical['result']['energy']['all_damage_model'],'independent_outgoing_multiplier')
        self.assertIsNotNone(hypothetical['result']['energy']['durations']['60']['total_damage_bounds'])
        self.assertAlmostEqual(hypothetical['result']['energy']['base_direct_hit_after_bonuses']/default['result']['energy']['base_direct_hit_after_bonuses'],1.03)
        mixed=self.post('/api/build-combat-formula',{**request,'proposal_ids':['target-mixed'],
            'encounter':{**encounter,'all_damage_model':'independent_outgoing_multiplier'}})
        self.assertEqual(mixed['modifier_count'],1)
        self.assertIsNone(mixed['result']['energy']['durations']['60']['total_damage_bounds'])
        self.assertEqual(mixed['result']['energy']['typed_modifiers_unmodeled'][0]['raw_text'],'Damage to bosses +5%')

    def test_defensive_uncertainty_does_not_erase_complete_offense(self):
        encounter={'dodge_fraction':0,'pre_mod_reload_seconds':2,'accepted_energy_returns_per_second':0,
                   'hit_rate':1,'weakspot_fraction':.2,'crit_weak_overlap':.02}
        streams={'events_per_active_second':0}
        request={'use_tier_v_preview':True,'encounter':encounter,'power_surge':streams,'orb':streams}
        baseline=self.post('/api/build-combat-formula',request)['result']['energy']['durations']['60']['total_damage_bounds']
        cases={
            'hp':['Max HP + 2.4%'],
            'defense':['Receive a DMG Reduction 4.8% for 3.0s after taking damage; cooldown: 6.0'],
            'offense_unknown':['DMG ++ 2.4%'],
            'after_hit_unknown':['Additional damage inflicted after hitting a unit is reduced by 9.0%% for 2.0s'],
            'mixed_unknown':['Max HP + 2.4%','DMG ++ 2.4%'],
            'mixed_supported':['Weapon DMG + 5%','Max HP + 2.4%',
                               'Receive a DMG Reduction 4.8% for 3.0s after taking damage; cooldown: 6.0'],
        }
        with server.connect() as connection:
            connection.execute("INSERT INTO video_import_runs(id,media_id,fingerprint,status,options,summary,created,updated) VALUES(?,?,?,?,?,?,?,?)",
                               ('health-test-run','test-media','health-test','reviewed','{}','{}',server.now(),server.now()))
            for key,rows in cases.items():
                payload={'ownership':'unlocked','slot':'chest_mod','attribute_rows':rows,
                         'source_audit':{'status':'source_text_and_numbers_checked',
                                         'attribute_rows':[{'source_text':line} for line in rows]}}
                connection.execute("INSERT INTO video_import_proposals(id,run_id,identity_key,data,status,updated) VALUES(?,?,?,?,?,?)",
                                   (key,'health-test-run',key,json.dumps(payload),'reviewed',server.now()))
        for key in ('hp','defense'):
            output=self.post('/api/build-combat-formula',{**request,'proposal_ids':[key]})
            self.assertEqual(output['result']['energy']['durations']['60']['total_damage_bounds'],baseline)
            self.assertFalse(output['coverage_complete'])
        for key in ('offense_unknown','after_hit_unknown','mixed_unknown'):
            output=self.post('/api/build-combat-formula',{**request,'proposal_ids':[key]})
            self.assertIsNone(output['result']['energy']['durations']['60']['total_damage_bounds'])
        assumed=self.post('/api/build-combat-formula',{**request,'proposal_ids':['mixed_supported'],
                     'encounter':{**encounter,'tech_policy':'assume_active',
                                  'pre_mod_max_hp':1000,'max_hp_excludes_selected_mods':True}})
        self.assertIsNotNone(assumed['result']['energy']['durations']['60']['total_damage_bounds'])
        self.assertGreater(assumed['result']['energy']['durations']['60']['total_damage_bounds']['floor'],baseline['floor'])
        self.assertEqual(assumed['result']['energy']['max_hp_sensitivity']['after_unrounded'],1024)
        self.assertFalse(assumed['coverage_complete'])
        catalog_id='mod:chest_mod:enduring-shield-deviant-energy'
        lines=cases['mixed_supported']
        typed=mod_rolls.parse_rows(lines,source_audit={'status':'source_text_and_numbers_checked',
                                               'attribute_rows':[{'source_text':line} for line in lines]})
        with server.connect() as connection:
            connection.execute('INSERT INTO inventory VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                ('health-owned','Fixture defense','mod_unlock','chest_mod',None,'Battle',9,None,
                 json.dumps({'typed_modifiers':typed,'observed_attribute_lines':lines,'original_observed_level':9}),
                 json.dumps({'catalog_id':catalog_id}),'fixture-source','[]',server.now(),server.now(),0))
        build=self.post('/api/planned-build',{'name':'Defensive roll fixture','slots':{
            'primary':{'catalog_id':'weapon:aug-electron-cloud','tier':5,'stars':5},
            'top':{'catalog_id':'armor:agent-top','mod_id':catalog_id,'mod_level':9,'mod_inventory_id':'health-owned'}}})
        owned=self.post('/api/build-combat-formula',{**request,'build_id':build['id'],
            'encounter':{**encounter,'tech_policy':'assume_active'}})
        self.assertEqual(owned['selected_owned_mods']['unresolved'][0]['offense_blocking'],False)
        self.assertIsNotNone(owned['result']['energy']['durations']['60']['total_damage_bounds'])
        self.assertFalse(owned['coverage_complete'])

    def test_mod_collection_is_explicit_idempotent_and_restorable(self):
        mod_id='mod:weapon_mod:shock-rampage-power-surge'
        plan={'primary':{'catalog_id':'weapon:aug-electron-cloud','mod_id':mod_id,'mod_level':1}}
        saved=self.post('/api/planned-build',{'name':'Collection independent plan','slots':plan})
        first=self.post('/api/mod-collection/add',{'catalog_id':mod_id})
        self.assertTrue(first['created'])
        self.assertIsNone(first['level'])
        repeat=self.post('/api/mod-collection/add',{'catalog_id':mod_id})
        self.assertEqual(repeat['id'],first['id'])
        self.assertFalse(repeat['created'])
        recorded=[item for item in self.get('/api/builder-catalog')['owned_mods'] if item['catalog_id']==mod_id]
        self.assertEqual(len(recorded),1)
        self.assertTrue(recorded[0]['manual_collection'])
        self.assertIsNone(recorded[0]['level'])
        self.assertEqual(self.get('/api/builder-catalog')['planned_builds'][0]['slots'],plan)
        self.post('/api/mod-collection/level',{'id':first['id'],'level':11})
        self.assertEqual(self.get('/api/builder-catalog')['owned_mods'][0]['level'],11)
        with server.connect() as c:
            c.execute('INSERT INTO loadouts VALUES(?,?,?,?,?,?)',('saved-reference','Saved reference',json.dumps([first['id']]),'',server.now(),server.now()))
        with self.assertRaises(HTTPError) as blocked:
            self.post('/api/mod-collection/remove',{'id':first['id']})
        blocked.exception.close()
        self.assertEqual(len(self.get('/api/builder-catalog')['owned_mods']),1)
        with server.connect() as c:c.execute('DELETE FROM loadouts WHERE id=?',('saved-reference',))
        self.post('/api/mod-collection/remove',{'id':first['id']})
        self.assertEqual(self.get('/api/builder-catalog')['owned_mods'],[])
        restored=self.post('/api/mod-collection/add',{'catalog_id':mod_id})
        self.assertEqual(restored['id'],first['id'])
        self.assertTrue(restored['restored'])
        self.assertEqual(self.get('/api/builder-catalog')['owned_mods'][0]['level'],11)
        second=self.post('/api/item',{'catalog_id':mod_id,'name':'Second observed instance','kind':'mod_unlock','level':7})
        self.assertNotEqual(second['id'],first['id'])
        self.post('/api/mod-collection/add',{'catalog_id':mod_id})
        self.assertEqual(len(self.get('/api/builder-catalog')['owned_mods']),2,'Existing multiple instances remain separate')
        self.post('/api/mod-collection/remove',{'id':first['id']})
        self.assertEqual([item['id'] for item in self.get('/api/builder-catalog')['owned_mods']],[second['id']])
        reopened=next(item for item in self.get('/api/builder-catalog')['planned_builds'] if item['id']==saved['id'])
        self.assertEqual(reopened['slots'],plan)
        with self.assertRaises(HTTPError) as invalid:self.post('/api/mod-collection/add',{'catalog_id':'weapon:aug-electron-cloud'})
        invalid.exception.close()


if __name__=='__main__':unittest.main()
