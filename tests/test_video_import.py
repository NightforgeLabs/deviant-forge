import json
import os
import sqlite3
import tempfile
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

import catalog
import engine
import server
import video_review
import video_import_plan
import mod_rolls

CATALOG_ID = 'mod:chest_mod:healing-fortification-battle'


class VideoImportReviewTests(unittest.TestCase):
    def test_field_guide_and_unknown_source_cannot_commit_physical_copy(self):
        for system in ('current_field_guide',None):
            with self.subTest(system=system):
                p=self.make_run()
                with video_review.connect(server.DB) as c:
                    data=json.loads(c.execute('SELECT data FROM video_import_proposals WHERE id=?',(p['id'],)).fetchone()[0])
                    if system is None:data['source'].pop('mod_system',None)
                    else:data['source']['mod_system']=system
                    c.execute('UPDATE video_import_proposals SET data=?,status=? WHERE id=?',
                              (json.dumps(data),'reviewed',p['id']))
                with self.assertRaisesRegex(ValueError,'not a physical Backpack copy'):
                    video_review.commit(server.DB,p['id'])
                self.assertEqual(server.inventory(),[])
                with video_review.connect(server.DB) as c:
                    c.execute('DELETE FROM video_import_proposals')
                    c.execute('DELETE FROM video_import_runs')

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name)
        self.old = (server.DATA, server.MEDIA, server.DB)
        server.DATA, server.MEDIA, server.DB = self.data, self.data / 'media', self.data / 'advisor.sqlite3'
        server.init()
        self.media = self.data / 'media' / 'clip'
        self.media.mkdir(parents=True)
        self.clip = self.media / 'sample.mp4'
        self.clip.write_bytes(b'synthetic unit-test source')
        with server.connect() as c:
            c.execute('INSERT INTO media(id,name,type,size,created) VALUES(?,?,?,?,?)', ('clip','sample.mp4','video',self.clip.stat().st_size,server.now()))
            c.execute('INSERT INTO planned_builds VALUES(?,?,?,?,?,?)', ('build','saved','{}','',server.now(),server.now()))

    def tearDown(self):
        server.DATA, server.MEDIA, server.DB = self.old
        self.tmp.cleanup()

    def proposal(self, ownership='unlocked'):
        frame = self.media / 'frame.png'
        frame.write_bytes(b'frame')
        return {
            'catalog_id': CATALOG_ID, 'name':'Healing Fortification', 'variant':'Battle',
            'title':'Healing Fortification <Battle>', 'slot':'chest_mod','level':9,
            'rarity':'legendary' if ownership=='unlocked' else None,
            'ownership':ownership,
            'ownership_cues':['Equip action','visible level and suffix'] if ownership=='unlocked' else ['Locked label'],
            'main_effect':'Using a healing shot grants damage reduction.',
            'attribute_rows':['Max HP +2.4%'],
            'source':{'timestamp':11.0,'frame':str(frame),'tooltip':str(frame),'mod_system':'legacy_backpack'},
            'extraction':{'attributes':'OCR'},'raw_ocr':'test','confidence':75,'unknowns':['Review OCR'],
        }

    def make_run(self, ownership='unlocked'):
        options={'start':0,'end':1,'interval':1}
        run, created = video_review.create_run(server.DB,'clip',self.clip,options)
        self.assertTrue(created)
        result={'proposals':[self.proposal(ownership)],'frames_scanned':1,'duration':1,'warnings':[]}
        video_review.persist_result(server.DB,run['id'],result,self.data)
        return video_review.list_data(server.DB)[1][0]

    def test_repeat_analysis_and_review_commit_undo_preserve_build(self):
        p=self.make_run()
        again,created=video_review.create_run(server.DB,'clip',self.clip,{'start':0,'end':1,'interval':1})
        self.assertFalse(created)
        self.assertEqual(again['id'],p['run_id'])
        with self.assertRaises(ValueError):video_review.commit(server.DB,p['id'])
        video_review.correction(server.DB,p['id'],{'level':10,'attribute_rows':['Max HP +2.4%']})
        result=video_review.commit(server.DB,p['id'])
        self.assertEqual(result['status'],'committed')
        self.assertTrue(Path(result['backup']).is_file())
        self.assertEqual(video_review.commit(server.DB,p['id'])['status'],'already_committed')
        self.assertEqual(len(server.inventory()),1)
        self.assertEqual(server.inventory()[0]['level'],10)
        self.assertEqual(server.rows('planned_builds')[0]['slots'],'{}')
        self.assertEqual(video_review.undo(server.DB,p['id'])['status'],'reviewed')
        self.assertEqual(server.inventory(),[])
        self.assertEqual(server.rows('planned_builds')[0]['slots'],'{}')
        repeated=video_review.commit(server.DB,p['id'])
        self.assertEqual(repeated['status'],'committed')
        self.assertEqual(len(server.inventory()),1)
        self.assertEqual(video_review.undo(server.DB,p['id'])['status'],'reviewed')
        self.assertEqual(server.inventory(),[])

    def test_locked_frame_cannot_be_added_or_relabelled_owned(self):
        p=self.make_run('locked')
        with self.assertRaises(ValueError):video_review.correction(server.DB,p['id'],{'level':10})
        with self.assertRaises(ValueError):video_review.commit(server.DB,p['id'])
        self.assertEqual(server.inventory(),[])

    def test_backup_roundtrip_preserves_review_proposals(self):
        p=self.make_run()
        exported=server.backup()
        self.assertEqual(exported['version'],8)
        with server.connect() as c:
            c.execute('DELETE FROM video_import_proposals')
            c.execute('DELETE FROM video_import_runs')
        server.restore(exported)
        runs,proposals=video_review.list_data(server.DB)
        self.assertEqual(len(runs),1)
        self.assertEqual(len(proposals),1)
        self.assertEqual(proposals[0]['id'],p['id'])
        self.assertEqual(server.rows('planned_builds')[0]['slots'],'{}')

    def test_single_reviewed_add_preserves_ambiguous_source_direction(self):
        proposal=self.make_run()
        video_review.correction(server.DB,proposal['id'],{
            'catalog_id':'mod:chest_mod:quick-comeback-survival','level':8,'rarity':'epic',
            'attribute_rows':['Max HP + 2.4%','Damage from monsters −+ 3.2%',
                              'Magazine Capacity + 4.8%','All DMG Boost + 3.0%']})
        result=video_review.commit(server.DB,proposal['id'])
        self.assertEqual(result['status'],'committed')
        item=server.inventory()[0]
        self.assertEqual(item['stats']['video_import']['semantic_uncertainties'][0]['field'],'attribute_rows[1]')
        self.assertEqual(item['stats']['attribute_coverage'],'source_direction_ambiguous')

    def test_ambiguous_survival_sign_survives_batch_backup_and_cannot_score(self):
        run,_=video_review.create_run(server.DB,'clip',self.clip,{'start':0,'end':1,'interval':1})
        frame=self.media/'frame.png';frame.write_bytes(b'frame')
        p=self.proposal();p.update({'catalog_id':'mod:chest_mod:quick-comeback-survival',
            'name':'Quick Comeback','title':'Quick Comeback <Survival>','variant':'Survival','level':8,'rarity':'epic'})
        p['source']['context']=str(frame)
        p['attribute_rows']=['Max HP + 2.4%','Receive a DMG Reduction 3.2%for 3.0s after taking damage; cooldown: 6.0',
            'Damage from monsters −+ 3.2%','Increases damage dealt to all DMG Boost by + 3.0%']
        ambiguity={'field':'attribute_rows[2]','issue':'Game text has conflicting direction signs','source_text':p['attribute_rows'][2]}
        p['source_audit']={'status':'source_text_and_numbers_checked; semantic_direction_caveat',
            'main_effect':{'source_text':p['main_effect']},
            'attribute_rows':[{'source_text':row} for row in p['attribute_rows']],
            'semantic_uncertainties':[ambiguity]}
        video_review.persist_result(server.DB,run['id'],{'proposals':[p],'frames_scanned':1,'duration':1,'warnings':[]},self.data)
        with video_review.connect(server.DB) as c:
            summary=json.loads(c.execute('SELECT summary FROM video_import_runs WHERE id=?',(run['id'],)).fetchone()[0])
            summary['qa']={'source_checked':True,'owned_proposals':1,'semantic_uncertain_fields':1}
            c.execute('UPDATE video_import_runs SET summary=? WHERE id=?',(json.dumps(summary),run['id']))
        committed=video_review.commit_checked_batch(server.DB,run['id'])
        self.assertEqual(committed['added'],1)
        item=server.inventory()[0]
        self.assertEqual(item['stats']['video_import']['semantic_uncertainties'][0]['field'],'attribute_rows[2]')
        self.assertEqual(item['stats']['attribute_coverage'],'source_direction_ambiguous')
        self.assertEqual(item['stats']['observed_attribute_lines'][2],p['attribute_rows'][2])
        exported=server.backup();server.restore(exported)
        reloaded=server.inventory()[0]
        self.assertEqual(reloaded['stats']['video_import']['semantic_uncertainties'],[ambiguity])
        reloaded['stats']['catalog_attributes']=[{'name':'Damage from monsters received','direction':'reduction','unit':'percent','value_percent':3.2}]
        alternative={**reloaded,'id':'other','stats':{**reloaded['stats'],'video_import':{},'attribute_coverage':'complete'}}
        result=engine.compare_catalog_selections(reloaded,alternative,{'incoming_monster_hit':100})
        self.assertEqual(result['left']['attributes'],[])
        self.assertEqual(result['left']['numeric_coverage'],'source_direction_ambiguous')
        self.assertIsNone(result['selected_metric'])
        weapon={'id':'weapon','name':'Test weapon','slot':'primary','kind':'instance','stats':{'damage':100,'rpm':600,'magazine':40,'reload_seconds':2,'damage_origin':'tooltip_base','base_component':'weapon','base_context':'unbuffed'},'effects':{}}
        predicted=engine._predicted_score([weapon,reloaded],{'scenario':'PvE'})
        self.assertFalse(predicted['supported'])
        self.assertTrue(any('attribute direction is ambiguous' in x for x in predicted['unresolved']))
        self.assertFalse(any(x.get('component')=='Damage from monsters received' for x in predicted['trace']))

    def test_distinct_levels_remain_separate_proposals_and_cannot_silently_merge(self):
        run,_=video_review.create_run(server.DB,'clip',self.clip,{'start':0,'end':1,'interval':1})
        frame=self.media/'frame.png';frame.write_bytes(b'frame')
        items=[]
        for level in (9,10):
            p=self.proposal();p['level']=level;p['source']['timestamp']=float(level)
            p['source']['context']=str(frame)
            p['attribute_rows']=['Max HP +2.4%','Weapon DMG +3.6%','Magazine Capacity +4.8%','All DMG Boost +3.0%']
            p['source_audit']={'status':'source_text_and_numbers_checked','main_effect':{'source_text':p['main_effect']},'attribute_rows':[{'source_text':row} for row in p['attribute_rows']]}
            items.append(p)
        video_review.persist_result(server.DB,run['id'],{'proposals':items,'frames_scanned':2,'duration':2,'warnings':[]},self.data)
        found=[p for p in video_review.list_data(server.DB)[1] if p['run_id']==run['id']]
        self.assertEqual({p['data']['level'] for p in found},{9,10})
        with video_review.connect(server.DB) as c:
            summary=json.loads(c.execute('SELECT summary FROM video_import_runs WHERE id=?',(run['id'],)).fetchone()[0]);summary['qa']={'source_checked':True,'owned_proposals':2}
            c.execute('UPDATE video_import_runs SET summary=? WHERE id=?',(json.dumps(summary),run['id']))
        with self.assertRaisesRegex(ValueError,'duplicate conflict'):
            video_review.commit_checked_batch(server.DB,run['id'])
        self.assertEqual(server.inventory(),[])

    def test_same_variant_level_separate_hover_encounters_require_identity_review(self):
        run,_=video_review.create_run(server.DB,'clip',self.clip,{'start':0,'end':3,'interval':1})
        frame=self.media/'frame.png';frame.write_bytes(b'frame')
        proposals=[]
        for encounter,value in enumerate((2.4,3.2)):
            p=self.proposal();p['source'].update({'context':str(frame),'timestamp':float(encounter),
                                                  'encounter':encounter})
            p['attribute_rows']=[f'Max HP + {value}%']
            proposals.append(p)
        video_review.persist_result(server.DB,run['id'],{'proposals':proposals,
                                    'frames_scanned':2,'duration':3,'warnings':[]},self.data)
        rows=video_review.list_data(server.DB)[1]
        self.assertEqual(len(rows),2)
        plan=video_import_plan.plan(run['id'],rows,server.inventory())
        self.assertEqual(plan['counts']['conflicting_source_or_distinct_copy_needs_review'],2)
        self.assertEqual({e['source_timestamp'] for e in plan['entries']},{0.0,1.0})
        with self.assertRaises(ValueError):
            video_review.commit(server.DB,rows[0]['id'])
        self.assertEqual(server.inventory(),[])

    def test_explicit_distinct_copy_review_preserves_two_same_level_instances(self):
        run,_=video_review.create_run(server.DB,'clip',self.clip,{'start':0,'end':3,'interval':1})
        frame=self.media/'frame.png';frame.write_bytes(b'frame')
        proposals=[]
        for encounter,value in enumerate((2.4,3.2)):
            p=self.proposal();p['source'].update({'context':str(frame),'timestamp':float(encounter),
                                                  'encounter':encounter})
            p['attribute_rows']=[f'Max HP + {value}%']
            p['source_audit']={'status':'source_text_and_numbers_checked',
                               'main_effect':{'source_text':p['main_effect']},
                               'attribute_rows':[{'source_text':p['attribute_rows'][0]}]}
            proposals.append(p)
        video_review.persist_result(server.DB,run['id'],{'proposals':proposals,
                                    'frames_scanned':2,'duration':3,'warnings':[]},self.data)
        rows=video_review.list_data(server.DB)[1]
        for row in rows:
            video_review.correction(server.DB,row['id'],{'level':9})
        with self.assertRaises(ValueError):video_review.commit(server.DB,rows[0]['id'])
        with self.assertRaises(ValueError):video_review.review_distinct_copy(server.DB,rows[0]['id'],'same')
        for row in rows:
            self.assertTrue(video_review.review_distinct_copy(
                server.DB,row['id'],f'Separate selected card in source encounter {row["data"]["source"]["encounter"]}')['inventory_unchanged'])
        self.assertEqual(server.inventory(),[])
        first=video_review.commit(server.DB,rows[0]['id'])
        second=video_review.commit(server.DB,rows[1]['id'])
        self.assertNotEqual(first['inventory_id'],second['inventory_id'])
        owned=server.inventory()
        self.assertEqual(len(owned),2)
        self.assertEqual({item['stats']['observed_attribute_lines'][0] for item in owned},
                         {'Max HP + 2.4%','Max HP + 3.2%'})
        selection={'top':{'mod_id':CATALOG_ID,'mod_level':9}}
        unresolved=mod_rolls.equipped_build_modifiers(selection,owned)
        self.assertEqual(unresolved['unresolved'][0]['code'],'multiple_owned_instances')
        selection['top']['mod_inventory_id']=first['inventory_id']
        resolved=mod_rolls.equipped_build_modifiers(selection,owned)
        self.assertEqual(len(resolved['modifiers']),1)
        self.assertEqual(resolved['modifiers'][0]['value'],2.4)
        self.assertEqual(video_review.undo(server.DB,rows[1]['id'])['status'],'reviewed')
        self.assertEqual(video_review.undo(server.DB,rows[0]['id'])['status'],'reviewed')
        self.assertEqual(server.inventory(),[])

    def test_one_action_checked_batch_is_explicit_deduplicated_and_undoable(self):
        run,created=video_review.create_run(server.DB,'clip',self.clip,{'start':0,'end':1,'interval':1})
        self.assertTrue(created)
        frame=self.media/'frame.png';frame.write_bytes(b'frame')
        proposals=[]
        for suffix in ('Battle','General'):
            p=self.proposal();p['catalog_id']='mod:chest_mod:healing-fortification-'+suffix.lower()
            p['variant']=suffix;p['title']='Healing Fortification <'+suffix+'>'
            p['attribute_rows']=['Max HP +2.4%','Weapon DMG +3.6%','Magazine Capacity +4.8%','All DMG Boost +3.0%']
            p['source']['context']=str(frame)
            p['source_audit']={'status':'source_text_and_numbers_checked','main_effect':{'source_text':p['main_effect']},'attribute_rows':[{'source_text':row} for row in p['attribute_rows']]}
            proposals.append(p)
        locked=self.proposal('locked');locked['catalog_id']='mod:chest_mod:healing-fortification-violent';locked['source']['context']=str(frame)
        proposals.append(locked)
        video_review.persist_result(server.DB,run['id'],{'proposals':proposals,'frames_scanned':1,'duration':1,'warnings':[]},self.data)
        with video_review.connect(server.DB) as c:
            summary=json.loads(c.execute('SELECT summary FROM video_import_runs WHERE id=?',(run['id'],)).fetchone()[0])
            summary['qa']={'source_checked':True,'owned_proposals':2}
            c.execute('UPDATE video_import_runs SET summary=? WHERE id=?',(json.dumps(summary),run['id']))
        self.assertEqual(server.inventory(),[])
        result=video_review.commit_checked_batch(server.DB,run['id'])
        self.assertEqual(result['added'],2)
        self.assertTrue(Path(result['backup']).is_file())
        self.assertEqual(len(server.inventory()),2)
        batch_rows=[p for p in video_review.list_data(server.DB)[1] if p['status']=='committed']
        with self.assertRaisesRegex(ValueError,'batch undo'):
            video_review.undo(server.DB,batch_rows[0]['id'])
        self.assertEqual(video_review.commit_checked_batch(server.DB,run['id'])['added'],0)
        imported_ids=[row['inventory_id'] for row in batch_rows]
        original_connect=video_review.connect
        connections=[0]
        def connect_with_new_build_reference(db):
            connections[0]+=1
            if connections[0]==2:
                with original_connect(db) as c:
                    c.execute('INSERT INTO loadouts VALUES(?,?,?,?,?,?)',
                              ('late-reference','late',json.dumps(imported_ids),'',server.now(),server.now()))
            return original_connect(db)
        with patch.object(video_review,'connect',side_effect=connect_with_new_build_reference):
            with self.assertRaisesRegex(ValueError,'saved loadout'):
                video_review.undo_checked_batch(server.DB,run['id'],result['batch_id'])
        self.assertEqual(len(server.inventory()),2)
        with original_connect(server.DB) as c:
            c.execute("DELETE FROM loadouts WHERE id='late-reference'")
        self.assertEqual(video_review.undo_checked_batch(server.DB,run['id'],result['batch_id'])['removed'],2)
        self.assertEqual(server.inventory(),[])
        self.assertEqual(server.rows('planned_builds')[0]['slots'],'{}')

    def test_instance_plan_defers_existing_match_and_commits_only_new_copy(self):
        run,_=video_review.create_run(server.DB,'clip',self.clip,{'start':0,'end':2,'interval':1})
        frame=self.media/'frame.png';frame.write_bytes(b'frame')
        proposals=[]
        for variant in ('Battle','General'):
            p=self.proposal();p['catalog_id']='mod:chest_mod:healing-fortification-'+variant.lower()
            p['variant']=variant;p['title']='Healing Fortification <'+variant+'>'
            p['source']['context']=str(frame)
            p['attribute_rows']=['Max HP + 2.4%','Weapon DMG + 3.6%',
                                 'Magazine Capacity + 4.8%','All DMG Boost + 3.0%']
            p['source_audit']={'status':'source_text_and_numbers_checked',
                               'main_effect':{'source_text':p['main_effect']},
                               'attribute_rows':[{'source_text':line} for line in p['attribute_rows']]}
            proposals.append(p)
        video_review.persist_result(server.DB,run['id'],{'proposals':proposals,'frames_scanned':2,'duration':2,'warnings':[]},self.data)
        with video_review.connect(server.DB) as c:
            stamp=server.now();eid='preexisting'
            c.execute('INSERT INTO inventory VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                      (eid,'Healing Fortification','mod_unlock','chest_mod',None,'General',9,None,
                       json.dumps({'observed_attribute_lines':['old OCR row']}),
                       json.dumps({'catalog_id':'mod:chest_mod:healing-fortification-general'}),
                       None,'[]',stamp,stamp,0))
            summary=json.loads(c.execute('SELECT summary FROM video_import_runs WHERE id=?',(run['id'],)).fetchone()[0])
            summary['qa']={'source_checked':True,'owned_proposals':2}
            c.execute('UPDATE video_import_runs SET summary=? WHERE id=?',(json.dumps(summary),run['id']))
        rows=video_review.list_data(server.DB)[1]
        plan=video_import_plan.plan(run['id'],rows,server.inventory())
        self.assertEqual(plan['counts']['new_owned_copy_candidate'],1)
        self.assertEqual(plan['counts']['existing_identity_level_needs_evidence_review'],1)
        existing=next(e['proposal_id'] for e in plan['entries'] if e['classification'].startswith('existing_'))
        with self.assertRaisesRegex(ValueError,'explicit deferral'):
            video_review.commit_checked_batch(server.DB,run['id'])
        with self.assertRaisesRegex(ValueError,'changed'):
            video_review.commit_checked_batch(server.DB,run['id'],'stale-token',[existing])
        self.assertEqual(len(server.inventory()),1)
        committed=video_review.commit_checked_batch(server.DB,run['id'],plan['plan_token'],[existing])
        self.assertEqual((committed['added'],committed['deferred']),(1,1))
        self.assertTrue(Path(committed['backup']).is_file())
        self.assertEqual(len(server.inventory()),2)
        new=next(item for item in server.inventory() if item['id']!='preexisting')
        self.assertEqual(len(new['stats']['typed_modifiers']),4)
        self.assertTrue(all(row['tech_activation']=='unknown' for row in new['stats']['typed_modifiers']))
        selection={'top':{'mod_id':new['effects']['catalog_id'],'mod_level':9,
                          'mod_inventory_id':new['id']}}
        resolved=mod_rolls.equipped_build_modifiers(selection,server.inventory())
        self.assertEqual(len(resolved['modifiers']),4)
        self.assertEqual({row['owned_instance_id'] for row in resolved['modifiers']},{new['id']})
        default=mod_rolls.aggregate(resolved['modifiers'])
        self.assertEqual(default['percent_by_type']['weapon_damage_percent'],0)
        assumed=mod_rolls.aggregate(resolved['modifiers'],tech_policy='assume_active')
        self.assertEqual(assumed['percent_by_type']['weapon_damage_percent'],3.6)
        self.assertEqual(assumed['percent_by_type']['magazine_capacity_percent'],4.8)
        self.assertEqual(assumed['percent_by_type']['all_damage_boost_percent'],0)
        self.assertEqual(server.rows('planned_builds')[0]['slots'],'{}')
        self.assertEqual(video_review.undo_checked_batch(server.DB,run['id'],committed['batch_id'])['removed'],1)
        self.assertEqual([item['id'] for item in server.inventory()],['preexisting'])

    def test_actual_top_source_frames_plan_commit_reload_resolve_undo_in_isolation(self):
        original_db=Path(__file__).resolve().parents[1]/'data'/'advisor.sqlite3'
        if not original_db.is_file():self.skipTest('Actual Top source unavailable')
        wanted={'mod:chest_mod:ardent-shield-battle',
                'mod:chest_mod:resist-advantage-precision'}
        original_data=original_db.parent
        with sqlite3.connect(f'file:{original_db}?mode=ro',uri=True) as source_db:
            selected=[json.loads(raw) for (raw,) in source_db.execute(
                "SELECT data FROM video_import_proposals WHERE run_id=?",
                ('3eca1e237ab643989c03a1b9c767555d',))
                if json.loads(raw).get('catalog_id') in wanted
                and json.loads(raw).get('ownership')=='unlocked']
        if len(selected)!=2:self.skipTest('Two representative reviewed source proposals unavailable')
        for proposal in selected:
            for key,value in list(proposal['source'].items()):
                if key not in ('frame','tooltip','context'):continue
                original=original_data/value
                if not original.is_file():self.skipTest('Source frame unavailable')
                target=self.media/f'{proposal["catalog_id"].split(":")[-1]}-{key}.png'
                shutil.copyfile(original,target)
                proposal['source'][key]=str(target)
        run,_=video_review.create_run(server.DB,'clip',self.clip,
                                      {'start':0,'end':2,'interval':1,'source_fixture':'339s Top recording'})
        video_review.persist_result(server.DB,run['id'],{'proposals':selected,
                                    'frames_scanned':2,'duration':339,'warnings':[]},self.data)
        old_id='existing-real-source-fixture'
        with video_review.connect(server.DB) as c:
            stamp=server.now()
            c.execute('INSERT INTO inventory VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                      (old_id,'Resist Advantage','mod_unlock','chest_mod',None,'Precision',7,None,
                       json.dumps({'observed_attribute_lines':['old OCR row']}),
                       json.dumps({'catalog_id':'mod:chest_mod:resist-advantage-precision'}),
                       None,'[]',stamp,stamp,0))
            summary=json.loads(c.execute('SELECT summary FROM video_import_runs WHERE id=?',(run['id'],)).fetchone()[0])
            summary['qa']={'source_checked':True,'owned_proposals':2}
            c.execute('UPDATE video_import_runs SET summary=? WHERE id=?',(json.dumps(summary),run['id']))
        plan=video_import_plan.plan(run['id'],video_review.list_data(server.DB)[1],server.inventory())
        self.assertEqual(plan['counts']['field_guide_progression_needs_profile_review'],2)
        self.assertEqual(sum(len(row['data']['attribute_rows']) for row in video_review.list_data(server.DB)[1]),8)
        with self.assertRaisesRegex(ValueError,'not a physical Backpack copy'):
            video_review.commit_checked_batch(server.DB,run['id'],plan['plan_token'],
                                              [entry['proposal_id'] for entry in plan['entries']])
        self.assertEqual([item['id'] for item in server.inventory()],[old_id])
        self.assertEqual(server.rows('planned_builds')[0]['slots'],'{}')


if __name__=='__main__': unittest.main()
