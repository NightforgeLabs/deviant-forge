"""Isolated video → reviewed collection → calculation path; never user data."""
import hashlib
import json
import sqlite3
import tempfile
import unittest
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import field_guide_profiles as guide
import video_review
import server


ID='mod:weapon_mod:shock-diffusion-power-surge'
RANK_ID='mod:chest_mod:ardent-shield-battle'


class FieldGuideVideoPathTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.db=self.root/'fixture.sqlite3'
        with video_review.connect(self.db) as c:
            video_review.ensure_schema(c)
            guide.ensure_schema(c)
            c.execute('CREATE TABLE inventory(id TEXT PRIMARY KEY, note TEXT)')
            c.execute('INSERT INTO inventory VALUES(?,?)',('legacy-preserved','unchanged'))
            c.execute('INSERT INTO video_import_runs VALUES(?,?,?,?,?,?,?,?)',
                      ('run','media','media-hash','done','{}','{}','now','now'))
            for index,level in enumerate((9,11)):
                relative=f'media/media/video-review/run/frame-{index}.png'
                frame=self.root/relative
                frame.parent.mkdir(parents=True,exist_ok=True)
                frame.write_bytes(b'full-frame-context-'+bytes([index]))
                labels=['Power Surge DMG + 3.6%','Power Surge Trigger Chance + 3.6%',
                        'Shock DMG + 3.6%','All DMG Boost + 3%']
                data={'catalog_id':ID,'name':'Shock Diffusion','slot':'weapon_mod',
                      'variant':'Power Surge','level':level,'ownership':'unlocked',
                      'shiny_status':'unknown','main_effect':'Source checked effect',
                      'attribute_rows':labels,
                      'source':{'frame':relative,'context':relative,'timestamp':float(index)},
                      'source_audit':{'status':'source_text_and_numbers_checked',
                                      'main_effect':{'source_text':'Source checked effect'},
                                      'attribute_rows':[{'source_text':x} for x in labels]}}
                c.execute('INSERT INTO video_import_proposals(id,run_id,identity_key,data,status,updated) VALUES(?,?,?,?,?,?)',
                          (f'p{index}','run',f'hover{index}',json.dumps(data),'pending','now'))
        self.initial_inventory=self._inventory()

    def tearDown(self):self.temp.cleanup()

    def _inventory(self):
        with video_review.connect(self.db) as c:
            return [tuple(row) for row in c.execute('SELECT * FROM inventory ORDER BY id')]

    def _review(self):
        context=video_review.system_context(self.db,'run')
        self.assertEqual(len(context['source_frames']),2)
        return video_review.review_system(self.db,'run',guide.SYSTEM,context['review_token'],
            ['mods_tab_selected','backpack_separate','collection_level_grid'],True)

    def _rank_fixture(self):
        """Synthetic same-variant observations without a prefilled numeric catalog curve."""
        lines=['Weapon DMG + 5%','Max HP + 3%','Magazine Capacity + 4%',
               'Reload Efficiency + 2%']
        with video_review.connect(self.db) as c:
            for pid in ('p0','p1'):
                data=json.loads(c.execute('SELECT data FROM video_import_proposals WHERE id=?',(pid,)).fetchone()[0])
                data.update({'catalog_id':RANK_ID,'slot':'chest_mod','name':'Ardent Shield',
                             'variant':'Battle','attribute_rows':lines})
                data['source_audit']['attribute_rows']=[{'source_text':x} for x in lines]
                c.execute('UPDATE video_import_proposals SET data=? WHERE id=?',(json.dumps(data),pid))

    def test_unknown_source_stale_token_and_missing_cue_hold(self):
        with video_review.connect(self.db) as c:
            before=guide.plan_video_run(c,'personal','run')
        self.assertEqual(len(before['held']),2)
        context=video_review.system_context(self.db,'run')
        with self.assertRaisesRegex(ValueError,'specific UI context'):
            video_review.review_system(self.db,'run',guide.SYSTEM,context['review_token'],
                                       ['mods_tab_selected'],True)
        with self.assertRaisesRegex(ValueError,'Source changed'):
            video_review.review_system(self.db,'run',guide.SYSTEM,'stale',
                ['mods_tab_selected','backpack_separate','collection_level_grid'],True)
        self.assertEqual(self._inventory(),self.initial_inventory)

    def test_source_frame_change_after_review_holds_profile_save(self):
        result=self._review()
        proof=self.root/result['source_proof'][0]['frame']
        proof.write_bytes(b'changed-after-review')
        with video_review.connect(self.db) as c:
            plan=guide.plan_video_run(c,'personal','run')
            self.assertEqual(len(plan['held']),2)
            with self.assertRaisesRegex(ValueError,'need review'):
                guide.save_video_run(c,'personal','run',plan['plan_token'],True)
            self.assertEqual(guide.profile(c,'personal')['levels'],{})
        self.assertEqual(self._inventory(),self.initial_inventory)

    def test_non_displayed_source_frame_change_invalidates_four_frame_batch(self):
        with video_review.connect(self.db) as c:
            original=json.loads(c.execute("SELECT data FROM video_import_proposals WHERE id='p1'").fetchone()[0])
            for index in (2,3):
                relative=f'media/media/video-review/run/frame-{index}.png'
                frame=self.root/relative;frame.write_bytes(b'full-frame-context-'+bytes([index]))
                data={**original,'source':{**original['source'],'frame':relative,
                                           'context':relative,'timestamp':float(index)}}
                c.execute('INSERT INTO video_import_proposals(id,run_id,identity_key,data,status,updated) VALUES(?,?,?,?,?,?)',
                          (f'p{index}','run',f'hover{index}',json.dumps(data),'pending','now'))
        context=video_review.system_context(self.db,'run')
        self.assertEqual([x['proposal_id'] for x in context['source_frames']],['p0','p2','p3'])
        self.assertEqual(len(context['source_proof']),4)
        video_review.review_system(self.db,'run',guide.SYSTEM,context['review_token'],
            ['mods_tab_selected','backpack_separate','collection_level_grid'],True)
        with video_review.connect(self.db) as c:
            prior=guide.plan_video_run(c,'personal','run')
            self.assertEqual(prior['held'],[])
        (self.root/'media/media/video-review/run/frame-1.png').write_bytes(b'tampered-middle-frame')
        with video_review.connect(self.db) as c:
            changed=guide.plan_video_run(c,'personal','run')
            self.assertNotEqual(changed['plan_token'],prior['plan_token'])
            self.assertTrue(any(x['proposal_id']=='p1' for x in changed['held']))
            with self.assertRaisesRegex(ValueError,'changed|need review'):
                guide.save_video_run(c,'personal','run',prior['plan_token'],True)
            self.assertEqual(guide.profile(c,'personal')['levels'],{})
        self.assertEqual(self._inventory(),self.initial_inventory)

    def test_atomic_profile_batch_undo_preserves_source_and_blocks_later_edit(self):
        self._review()
        with video_review.connect(self.db) as c:
            plan=guide.plan_video_run(c,'personal','run')
            saved=guide.save_video_run(c,'personal','run',plan['plan_token'],True)
            batch=saved['batch_id'];self.assertTrue(batch)
            self.assertTrue(guide.profile(c,'personal')['reviewed_batches'][0]['undo_available'])
            with self.assertRaisesRegex(ValueError,'Confirm'):
                guide.undo_video_run(c,'personal',batch)
            guide.set_manual(c,'personal',ID,12)
            c.commit()
            with self.assertRaisesRegex(ValueError,'changed'):
                guide.undo_video_run(c,'personal',batch,True)
            self.assertEqual(guide.get(c,'personal',ID)['level'],12)
            self.assertFalse(guide.profile(c,'personal')['reviewed_batches'][0]['undo_available'])
        with video_review.connect(self.db) as c:
            plan=guide.plan_video_run(c,'new_player','run')
            saved=guide.save_video_run(c,'new_player','run',plan['plan_token'],True)
            result=guide.undo_video_run(c,'new_player',saved['batch_id'],True)
            self.assertEqual(result['restored_count'],1)
            self.assertIsNone(guide.get(c,'new_player',ID))
            self.assertEqual(c.execute('SELECT COUNT(*) FROM video_import_proposals').fetchone()[0],2)
            with self.assertRaisesRegex(ValueError,'changed'):
                guide.undo_video_run(c,'new_player',saved['batch_id'],True)
        self.assertEqual(self._inventory(),self.initial_inventory)

    def test_review_plan_save_reload_matches_manual_and_excludes_unknown_tech(self):
        self._review()
        with video_review.connect(self.db) as c:
            plan=guide.plan_video_run(c,'personal','run')
            self.assertEqual(plan['held'],[])
            self.assertEqual(len(plan['entries']),1)
            self.assertEqual(plan['entries'][0]['source_levels'],[9,11])
            self.assertEqual(plan['entries'][0]['decision'],'new_unlock')
            self.assertEqual(plan['entries'][0]['level'],11)
            self.assertEqual(guide.profile(c,'new_player')['levels'],{})
            with self.assertRaisesRegex(ValueError,'Confirm'):
                guide.save_video_run(c,'personal','run',plan['plan_token'])
        with video_review.connect(self.db) as c:
            result=guide.save_video_run(c,'personal','run',plan['plan_token'],True)
        self.assertEqual(result['saved_count'],1)
        with video_review.connect(self.db) as c:
            saved=guide.get(c,'personal',ID)
            self.assertEqual(saved['level'],11)
            self.assertEqual(saved['source_kind'],'reviewed_video')
            self.assertEqual(guide.profile(c,'new_player')['levels'],{})
            video=guide.calculation_preview(c,'personal',ID)
            self.assertFalse(guide.calculation_preview(c,'new_player',ID)['owned_in_profile'])
            self.assertEqual(video['scenario']['modifiers']['used_rows'],[])
            self.assertTrue(video['scenario']['modifiers']['unmodeled_rows'])
            self.assertTrue(all(row['tech_activation']=='unknown' for row in video['rows']))
            guide.set_manual(c,'new_player',ID,11)
            manual=guide.calculation_preview(c,'new_player',ID)
            self.assertEqual(video['known_attributes'],manual['known_attributes'])
            self.assertEqual([r['value'] for r in video['rows']],[r['value'] for r in manual['rows']])
            staged=guide.calculation_preview(c,'personal',ID,{'base_origin':'pre_mod_unbuffed',
                'base_direct_hit':100,'rpm':600,'magazine':40,'reload_seconds':2,
                'tech_policy':'assume_active'})
            self.assertEqual(staged['scenario']['modifiers']['percent_by_type'].get('power_surge_damage_percent',0),0)
            self.assertIsNotNone(staged['scenario']['component_results']['direct_hit'])
            self.assertEqual(c.execute('SELECT count(*) FROM field_guide_level_events').fetchone()[0],2)
        self.assertEqual(self._inventory(),self.initial_inventory)

    def test_same_rank_manual_preview_uses_only_reviewed_exact_variant_context(self):
        self._rank_fixture()
        self._review()
        with video_review.connect(self.db) as c:
            before=c.total_changes
            target=guide.preview(c,'new_player',RANK_ID,10)
            self.assertTrue(target['rank_derived'])
            self.assertEqual(target['level_profile'],[3,3,2,2])
            self.assertEqual([r['observed_level'] for r in target['known_attributes']],[9,11,9,9])
            self.assertEqual([r['value_percent'] for r in target['known_attributes']],[5,3,4,2])
            self.assertTrue(all(r['evidence']['target_level']==10 for r in target['reviewed_exact_rows']))
            self.assertIn('not a screenshot of this level',' '.join(target['unknowns']))
            self.assertFalse(guide.preview(c,'new_player','mod:chest_mod:quick-comeback-battle',10)['rank_derived'],
                             'another family cannot borrow these values')
            self.assertFalse(guide.preview(c,'new_player',RANK_ID,10,'regular')['rank_derived'],
                             'unknown Shiny identity cannot supply a reviewed regular variant')
            self.assertFalse(guide.preview(c,'new_player',RANK_ID,17,'shiny')['rank_derived'],
                             'level alone cannot turn an unknown variant into Shiny evidence')
            self.assertEqual(guide.preview(c,'new_player',RANK_ID,0)['known_attributes'],[])
            low=guide.preview(c,'new_player',RANK_ID,1)
            self.assertEqual(low['known_attributes'][0]['value_percent'],None)
            self.assertTrue(all(r['inactive_by_rank'] for r in low['known_attributes'][1:]))
            self.assertFalse(guide.calculation_preview(c,'new_player',RANK_ID)['owned_in_profile'])
            self.assertEqual(c.total_changes,before,'read-only preview cannot create profile ownership')
            guide.set_manual(c,'new_player',RANK_ID,10)
            manual=guide.calculation_preview(c,'new_player',RANK_ID)
            self.assertEqual([r['value'] for r in manual['rows']],[5,3,4,2])
            self.assertEqual(manual['scenario']['modifiers']['used_rows'],[])
            self.assertFalse(guide.calculation_preview(c,'personal',RANK_ID)['owned_in_profile'])
        self.assertEqual(self._inventory(),self.initial_inventory)

    def test_derived_manual_rows_match_later_exact_reviewed_video_at_that_level(self):
        self._rank_fixture()
        self._review()
        with video_review.connect(self.db) as c:
            derived=guide.preview(c,'new_player',RANK_ID,10)
            data=json.loads(c.execute("SELECT data FROM video_import_proposals WHERE id='p0'").fetchone()[0])
            relative='media/media/video-review/run/frame-2.png'
            frame=self.root/relative;frame.write_bytes(b'full-frame-context-two')
            data.update({'level':10,'source':{**data['source'],'frame':relative,
                                           'context':relative,'timestamp':2.0}})
            c.execute('INSERT INTO video_import_proposals(id,run_id,identity_key,data,status,updated) VALUES(?,?,?,?,?,?)',
                      ('p2','run','hover2',json.dumps(data),'pending','now'))
        context=video_review.system_context(self.db,'run')
        video_review.review_system(self.db,'run',guide.SYSTEM,context['review_token'],
            ['mods_tab_selected','backpack_separate','collection_level_grid'],True)
        with video_review.connect(self.db) as c:
            exact=guide.preview(c,'new_player',RANK_ID,10)
            self.assertFalse(exact['rank_derived'])
            self.assertEqual([r['value_percent'] for r in derived['known_attributes']],
                             [r['value_percent'] for r in exact['known_attributes']])
            self.assertEqual([r['value'] for r in derived['reviewed_exact_rows']],
                             [r['value'] for r in exact['reviewed_exact_rows']])
            self.assertEqual(guide.profile(c,'new_player')['levels'],{})

    def test_same_rank_never_combines_different_patch_contexts(self):
        self._rank_fixture()
        self._review()
        with video_review.connect(self.db) as c:
            for pid,patch in (('p0','patch-a'),('p1','patch-b')):
                data=json.loads(c.execute('SELECT data FROM video_import_proposals WHERE id=?',(pid,)).fetchone()[0])
                data['source_audit']['patch_context']=patch
                c.execute('UPDATE video_import_proposals SET data=? WHERE id=?',(json.dumps(data),pid))
            target=guide.preview(c,'new_player',RANK_ID,10)
            self.assertFalse(target['rank_derived'])
            self.assertIn('different or unverified patch contexts',' '.join(target['unknowns']))
            self.assertEqual(target['reviewed_exact_rows'],[])
            self.assertEqual(guide.profile(c,'new_player')['levels'],{})

    def test_same_rank_conflicting_stat_identity_is_withheld(self):
        self._rank_fixture()
        with video_review.connect(self.db) as c:
            data=json.loads(c.execute("SELECT data FROM video_import_proposals WHERE id='p1'").fetchone()[0])
            data['attribute_rows'][0]='Status DMG + 5%'
            data['source_audit']['attribute_rows'][0]={'source_text':'Status DMG + 5%'}
            c.execute("UPDATE video_import_proposals SET data=? WHERE id='p1'",(json.dumps(data),))
        self._review()
        with video_review.connect(self.db) as c:
            target=guide.preview(c,'new_player',RANK_ID,10)
            self.assertTrue(target['rank_derived'])
            self.assertIsNone(target['known_attributes'][0]['value_percent'])
            self.assertTrue(target['known_attributes'][0]['source_conflict'])
            self.assertIn('row 1 rank 3',' '.join(target['unknowns']).lower())
            self.assertEqual(target['reviewed_exact_rows'][0]['value'],None)

    def test_same_exact_level_manual_and_reviewed_upload_resolve_same_selected_build(self):
        numeric_id='mod:chest_mod:resist-advantage-precision'
        lines=['Weakspot DMG +3.6%','Weapon DMG +2.4%',
               'Magazine Capacity +1.2%','All DMG Boost +1.5%']
        with video_review.connect(self.db) as c:
            c.execute("DELETE FROM video_import_proposals WHERE id='p1'")
            data=json.loads(c.execute("SELECT data FROM video_import_proposals WHERE id='p0'").fetchone()[0])
            data.update({'catalog_id':numeric_id,'name':'Resist Advantage','slot':'chest_mod',
                         'variant':'Precision','level':6,'main_effect':'Fixture checked core',
                         'attribute_rows':lines})
            data['source_audit'].update({'main_effect':{'source_text':'Fixture checked core'},
                                         'attribute_rows':[{'source_text':x} for x in lines]})
            c.execute("UPDATE video_import_proposals SET data=? WHERE id='p0'",(json.dumps(data),))
        context=video_review.system_context(self.db,'run')
        video_review.review_system(self.db,'run',guide.SYSTEM,context['review_token'],
            ['mods_tab_selected','backpack_separate','collection_level_grid'],True)
        with video_review.connect(self.db) as c:
            plan=guide.plan_video_run(c,'personal','run')
            self.assertEqual(plan['held'],[])
            self.assertEqual(plan['eligible_progressions'],1)
            guide.save_video_run(c,'personal','run',plan['plan_token'],True)
            guide.set_manual(c,'new_player',numeric_id,6)
        slots={'top':{'mod_id':numeric_id,'mod_level':6}}
        base={'base_origin':'pre_mod_unbuffed','base_direct_hit':100,'rpm':600,
              'magazine':40,'reload_seconds':2,'tech_policy':'assume_active'}
        with video_review.connect(self.db) as c:
            upload=guide.build_calculation_preview(c,'personal',slots,base)
            manual=guide.build_calculation_preview(c,'new_player',slots,base)
            self.assertEqual(guide.get(c,'personal',numeric_id)['source_kind'],'reviewed_video')
            self.assertEqual(guide.get(c,'new_player',numeric_id)['source_kind'],'manual')
            self.assertEqual([r['stat_type'] for r in upload['rows']],
                             [r['stat_type'] for r in manual['rows']])
            self.assertEqual([r['value'] for r in upload['rows']],
                             [r['value'] for r in manual['rows']])
            self.assertEqual(upload['scenario']['component_results'],
                             manual['scenario']['component_results'])
            self.assertEqual(upload['scenario']['component_results']['direct_hit'],102.4)
            self.assertEqual(guide.profile(c,'personal')['levels'][numeric_id]['level'],6)
            self.assertEqual(guide.profile(c,'new_player')['levels'][numeric_id]['level'],6)
        self.assertEqual(self._inventory(),self.initial_inventory)

    def test_stale_plan_and_repeat_save_do_not_duplicate_levels(self):
        self._review()
        with video_review.connect(self.db) as c:
            plan=guide.plan_video_run(c,'personal','run')
            guide.set_manual(c,'personal',ID,12)
        with video_review.connect(self.db) as c:
            with self.assertRaisesRegex(ValueError,'changed'):
                guide.save_video_run(c,'personal','run',plan['plan_token'],True)
        with video_review.connect(self.db) as c:
            fresh=guide.plan_video_run(c,'personal','run')
            self.assertEqual(fresh['entries'][0]['decision'],'stale_lower_level_observation')
            self.assertEqual(guide.save_video_run(c,'personal','run',fresh['plan_token'],True)['saved_count'],0)
            self.assertEqual(guide.get(c,'personal',ID)['level'],12)

    def test_conflicting_highest_level_readings_hold_entire_save(self):
        with video_review.connect(self.db) as c:
            source=c.execute("SELECT data FROM video_import_proposals WHERE id='p1'").fetchone()[0]
            changed=json.loads(source)
            changed['level']=9
            changed['attribute_rows'][0]='Power Surge DMG + 4.1%'
            changed['source_audit']['attribute_rows'][0]['source_text']='Power Surge DMG + 4.1%'
            c.execute("UPDATE video_import_proposals SET data=? WHERE id='p1'",(json.dumps(changed),))
        self._review()
        with video_review.connect(self.db) as c:
            plan=guide.plan_video_run(c,'personal','run')
            self.assertEqual(len(plan['held']),2)
            with self.assertRaisesRegex(ValueError,'need review'):
                guide.save_video_run(c,'personal','run',plan['plan_token'],True)
            self.assertEqual(guide.profile(c,'personal')['levels'],{})
        self.assertEqual(self._inventory(),self.initial_inventory)

    def test_selected_profile_build_uses_only_matching_level_and_tech_assumption(self):
        numeric_id='mod:chest_mod:resist-advantage-precision'
        with video_review.connect(self.db) as c:
            guide.set_manual(c,'personal',numeric_id,6)
        slots={'top':{'mod_id':numeric_id,'mod_level':6},
               'secondary':{'mod_id':ID,'mod_level':11}}
        base={'base_origin':'pre_mod_unbuffed','base_direct_hit':100,'rpm':600,
              'magazine':40,'reload_seconds':2}
        with video_review.connect(self.db) as c:
            personal=guide.build_calculation_preview(c,'personal',slots,base)
            self.assertEqual(personal['scenario']['component_results']['direct_hit'],100)
            self.assertEqual(personal['selected'][-1]['status'],'inactive_weapon')
            assumed=guide.build_calculation_preview(c,'personal',slots,{**base,'tech_policy':'assume_active'})
            self.assertEqual(assumed['scenario']['component_results']['direct_hit'],102.4)
            self.assertFalse(assumed['full_build_complete'])
            blank=guide.build_calculation_preview(c,'new_player',slots,{**base,'tech_policy':'assume_active'})
            self.assertEqual(blank['rows'],[])
            self.assertEqual(blank['scenario']['component_results']['direct_hit'],100)
            self.assertTrue(blank['issues'])
            mismatch=guide.build_calculation_preview(c,'personal',{'top':{'mod_id':numeric_id,'mod_level':5}},base)
            self.assertEqual(mismatch['rows'],[])
            self.assertEqual(mismatch['issues'][0]['profile_level'],6)
            physical=guide.build_calculation_preview(c,'personal',{'top':{'mod_id':numeric_id,'mod_level':6,'mod_inventory_id':'legacy'}},base)
            self.assertEqual(physical['rows'],[])
            self.assertIn('physical inventory instance',physical['issues'][0]['reason'])
        self.assertEqual(self._inventory(),self.initial_inventory)

    def test_exact_top_tooltip_rows_reach_manual_profile_without_invented_effects(self):
        top_id='mod:chest_mod:ardent-shield-battle'
        texts=['Additional damage inflicted after hitting a unit is reduced by 6.0%% for 2.0s',
               'Receive a DMG Reduction 3.2%for 3.0s after taking damage; cooldown: 6.0',
               'Defeating Metas recovers 4.8%HP.','Max HP + 2.4%']
        frame='media/media/video-review/toprun/top.png'
        path=self.root/frame;path.parent.mkdir(parents=True);path.write_bytes(b'full-top-tooltip')
        data={'catalog_id':top_id,'name':'Ardent Shield','variant':'Battle',
              'slot':'chest_mod','level':8,'ownership':'unlocked',
              'main_effect':'Observed conditional effect','attribute_rows':texts,
              'source':{'frame':frame,'context':frame,'timestamp':2},
              'source_audit':{'status':'source_text_and_numbers_checked',
                              'main_effect':{'source_text':'Observed conditional effect'},
                              'attribute_rows':[{'source_text':text} for text in texts]}}
        with video_review.connect(self.db) as c:
            c.execute('INSERT INTO video_import_runs VALUES(?,?,?,?,?,?,?,?)',
                      ('toprun','media','hash-top','done','{}','{}','now','now'))
            c.execute('INSERT INTO video_import_proposals(id,run_id,identity_key,data,status,updated) VALUES(?,?,?,?,?,?)',
                      ('top','toprun','hover',json.dumps(data),'pending','now'))
        context=video_review.system_context(self.db,'toprun')
        video_review.review_system(self.db,'toprun',guide.SYSTEM,context['review_token'],
            ['mods_tab_selected','backpack_separate','collection_level_grid'],True)
        with video_review.connect(self.db) as c:
            plan=guide.plan_video_run(c,'personal','toprun')
            self.assertEqual(plan['entries'][0]['known_attributes'][3]['value_percent'],2.4)
            guide.set_manual(c,'new_player',top_id,8)
            detail=guide.calculation_preview(c,'new_player',top_id)
            self.assertEqual(len(detail['known_attributes']),4)
            self.assertEqual(detail['reviewed_main_effect_raw'],'Observed conditional effect')
            self.assertEqual([row['value_percent'] for row in detail['known_attributes']],[6.0,3.2,4.8,2.4])
            self.assertEqual([row['raw_text'] for row in detail['rows']],texts)
            self.assertEqual(detail['scenario']['modifiers']['used_rows'],[])
            self.assertEqual(detail['scenario']['modifiers']['tech_gated_rows'][0]['stat_type'],'max_hp_percent')
            self.assertEqual(len(detail['scenario']['modifiers']['unmodeled_rows']),3)
            self.assertEqual(guide.profile(c,'personal')['levels'],{})
        self.assertEqual(self._inventory(),self.initial_inventory)

    def test_http_review_plan_save_and_profile_preview(self):
        original=server.DB
        server.DB=self.db
        http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        thread=threading.Thread(target=http.serve_forever,daemon=True)
        thread.start()
        def post(path,payload):
            request=urllib.request.Request(f'http://127.0.0.1:{http.server_port}/api/{path}',
                data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(request,timeout=5) as response:
                return json.load(response)
        try:
            context=post('video-import/system-context',{'run_id':'run'})
            self.assertEqual(context['proposal_count'],2)
            reviewed=post('video-import/review-system',{'run_id':'run',
                'mod_system':guide.SYSTEM,'review_token':context['review_token'],
                'context_cues':['mods_tab_selected','backpack_separate','collection_level_grid'],
                'confirm':True})
            self.assertEqual(reviewed['classified'],2)
            plan=post('field-guide/video-plan',{'profile_id':'personal','run_id':'run'})
            self.assertEqual(plan['eligible_progressions'],1)
            saved=post('field-guide/video-save',{'profile_id':'personal','run_id':'run',
                                                  'plan_token':plan['plan_token'],'confirm':True})
            self.assertEqual(saved['saved_count'],1)
            personal=post('field-guide/calculation-preview',{'profile_id':'personal','catalog_id':ID})
            blank=post('field-guide/calculation-preview',{'profile_id':'new_player','catalog_id':ID})
            self.assertEqual(personal['level'],11)
            self.assertFalse(blank['owned_in_profile'])
            self.assertEqual(personal['rows'][0]['tech_activation'],'unknown')
            undone=post('field-guide/video-undo',{'profile_id':'personal',
                'batch_id':saved['batch_id'],'confirm':True})
            self.assertEqual(undone['restored_count'],1)
            self.assertTrue(undone['raw_source_preserved'])
            self.assertFalse(post('field-guide/calculation-preview',
                {'profile_id':'personal','catalog_id':ID})['owned_in_profile'])
            self.assertEqual(self._inventory(),self.initial_inventory)
        finally:
            http.shutdown();http.server_close();thread.join(timeout=5)
            server.DB=original


if __name__=='__main__':unittest.main()
