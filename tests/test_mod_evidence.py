import json, tempfile, threading, unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from PIL import Image
import mod_evidence, mod_rolls, server, video_review

CATALOG_ID='mod:chest_mod:healing-fortification-battle'
ROWS=['Weapon DMG + 5%','Reload Efficiency + 3.6%',
      'Damage from monsters −+ 3.2%','Max HP + 2.4%']


class EvidenceAttachTests(unittest.TestCase):
 def test_cross_system_or_unknown_source_cannot_attach(self):
  for system in ('current_field_guide',None):
   with self.subTest(system=system):
    with server.connect() as c:
     data=json.loads(c.execute("SELECT data FROM video_import_proposals WHERE id='proposal'").fetchone()[0])
     if system is None:data['source'].pop('mod_system',None)
     else:data['source']['mod_system']=system
     c.execute("UPDATE video_import_proposals SET data=? WHERE id='proposal'",(json.dumps(data),))
    before=self.owned()
    with self.assertRaisesRegex(ValueError,'systems must be explicitly reviewed and match'):
     mod_evidence.preview(self.db,self.root,'proposal','owned')
    self.assertEqual(self.owned(),before)

 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.db=self.root/'advisor.sqlite3'
  self.old=server.DATA,server.MEDIA,server.DB
  server.DATA=self.root;server.MEDIA=self.root/'media';server.DB=self.db;server.init()
  folder=self.root/'media'/'clip';folder.mkdir(parents=True)
  for name in ('source.png','tooltip.png','context.png'):
   Image.new('RGB',(2,2),(20,40,60)).save(folder/name)
  self.source={key:str(Path('media/clip')/name) for key,name in [('frame','source.png'),('tooltip','tooltip.png'),('context','context.png')]}
  self.source['timestamp']=12.5;self.source['mod_system']='legacy_backpack'
  self.data={'catalog_id':CATALOG_ID,'name':'Healing Fortification','variant':'Battle',
   'slot':'chest_mod','level':9,'rarity':'legendary','ownership':'unlocked',
   'ownership_cues':['Equip action','visible level and suffix'],
   'main_effect':'Healing grants a conditional effect.','attribute_rows':ROWS,
   'source':self.source,
   'source_audit':{'status':'source_text_and_numbers_checked','main_effect':{'source_text':'Healing grants a conditional effect.'},
                   'attribute_rows':[{'source_text':row} for row in ROWS]}}
  with server.connect() as c:
   c.execute("INSERT INTO video_import_runs VALUES(?,?,?,?,?,?,?,?)",('run','clip','fixture-hash','done','{}','{}',server.now(),server.now()))
   c.execute("INSERT INTO video_import_proposals(id,run_id,identity_key,data,status,updated) VALUES(?,?,?,?,?,?)",
             ('proposal','run','identity',json.dumps(self.data),'pending',server.now()))
   c.execute('INSERT INTO inventory VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
             ('owned','Healing Fortification','mod_unlock','chest_mod',None,'Battle',9,None,
              '{}',json.dumps({'catalog_id':CATALOG_ID,'mod_system':'legacy_backpack'}),None,'[]',server.now(),server.now(),0))
   c.execute('INSERT INTO planned_builds VALUES(?,?,?,?,?,?)',
             ('plan','Saved test plan',json.dumps({'top':{'mod_id':CATALOG_ID,'mod_level':9}}),'',server.now(),server.now()))

 def tearDown(self):
  server.DATA,server.MEDIA,server.DB=self.old;self.tmp.cleanup()

 def owned(self):
  with server.connect() as c:return dict(c.execute("SELECT * FROM inventory WHERE id='owned'").fetchone())

 def source(self):
  with server.connect() as c:return json.loads(c.execute("SELECT data FROM video_import_proposals WHERE id='proposal'").fetchone()[0])

 def test_conflicting_observation_order_blocks_apply_without_inventory_write(self):
  typed=mod_rolls.parse_rows(ROWS[:2],source_audit={'status':'source_text_and_numbers_checked',
      'attribute_rows':[{'source_text':row} for row in ROWS[:2]]})
  stats={'observed_attribute_lines':[ROWS[0],ROWS[1]],
         'observed_tooltip':{'attribute_lines':[ROWS[1],ROWS[0]],'source_ref':'older-frame'},
         'typed_modifiers':typed}
  with server.connect() as c:
   c.execute("UPDATE inventory SET stats=? WHERE id='owned'",(json.dumps(stats),))
  before=self.owned()
  preview=mod_evidence.preview(self.db,self.root,'proposal','owned')
  self.assertTrue(preview['row_order_discrepancy'])
  self.assertIn('Apply is blocked',preview['warning'])
  self.assertTrue(all(value == 0 for value in preview['before_assumed_percent_by_type'].values()),
                  'conflicting older typed rows cannot appear as active before values')
  with self.assertRaisesRegex(ValueError,'disagree in row value, count, or order'):
   mod_evidence.apply(self.db,self.root,'proposal','owned',preview['token'],confirm=True,replace_existing=True)
  self.assertEqual(self.owned(),before)

 def test_partial_value_and_count_disagreements_block_attachment(self):
  saved=['Weapon DMG + 5%','Reload Efficiency + 3.6%']
  cases=[['Weapon DMG + 5%','Reload Efficiency + 4.1%'],
         ['Weapon DMG + 5%'],
         ['Weapon DMG + 5%','Reload Efficiency + 3.6%','Max HP + 2.4%']]
  for tooltip in cases:
   with self.subTest(tooltip=tooltip):
    stats={'observed_attribute_lines':saved,
           'observed_tooltip':{'attribute_lines':tooltip,'source_ref':'older-frame'}}
    with server.connect() as c:
     c.execute("UPDATE inventory SET stats=? WHERE id='owned'",(json.dumps(stats),))
    before=self.owned()
    review=mod_evidence.preview(self.db,self.root,'proposal','owned')
    self.assertTrue(review['row_order_discrepancy'])
    self.assertEqual(review['source_disagreement']['saved_rows'],saved)
    self.assertEqual(review['source_disagreement']['tooltip_rows'],tooltip)
    self.assertIsNone(review['after_assumed_percent_by_type'])
    self.assertIn('Apply is blocked',review['warning'])
    with self.assertRaisesRegex(ValueError,'disagree in row value, count, or order'):
     mod_evidence.apply(self.db,self.root,'proposal','owned',review['token'],confirm=True,replace_existing=True)
    self.assertEqual(self.owned(),before)

 def test_matching_sources_keep_legitimate_duplicate_valued_positions(self):
  rows=['Weapon DMG + 5%','Weapon DMG + 5%']
  stats={'observed_attribute_lines':rows,
         'observed_tooltip':{'attribute_lines':list(rows),'source_ref':'same-frame'}}
  with server.connect() as c:
   c.execute("UPDATE inventory SET stats=? WHERE id='owned'",(json.dumps(stats),))
  review=mod_evidence.preview(self.db,self.root,'proposal','owned')
  self.assertFalse(review['row_order_discrepancy'])
  self.assertIsNone(review['source_disagreement'])
  self.assertEqual(review['before_rows'],rows)

 def test_preview_apply_undo_and_saved_plan_math(self):
  before=self.owned();plan=server.planned_builds()[0]['slots']
  review=mod_evidence.preview(self.db,self.root,'proposal','owned')
  self.assertEqual(review['before_rows'],[])
  self.assertEqual(len(review['after_rows']),4)
  self.assertEqual(review['source']['context'],self.source['context'])
  self.assertEqual(review['default_tech_gated_count'],3)
  self.assertEqual(review['after_assumed_percent_by_type']['weapon_damage_percent'],5)
  self.assertEqual(self.owned(),before)
  with self.assertRaisesRegex(ValueError,'explicitly Apply'):
   mod_evidence.apply(self.db,self.root,'proposal','owned',review['token'])
  with self.assertRaisesRegex(ValueError,'changed'):
   mod_evidence.apply(self.db,self.root,'proposal','owned','0'*64,confirm=True)
  applied=mod_evidence.apply(self.db,self.root,'proposal','owned',review['token'],confirm=True)
  self.assertEqual(applied['status'],'attached')
  self.assertTrue(Path(applied['backup']).is_file())
  self.assertEqual(mod_evidence.apply(self.db,self.root,'proposal','owned',review['token'],confirm=True)['status'],'already_attached')
  with server.connect() as c:
   c.execute('INSERT INTO inventory VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
             ('second','Healing Fortification','mod_unlock','chest_mod',None,'Battle',9,None,
              '{}',json.dumps({'catalog_id':CATALOG_ID}),None,'[]',server.now(),server.now(),0))
  with self.assertRaisesRegex(ValueError,'already linked to another'):
   mod_evidence.preview(self.db,self.root,'proposal','second')
  with server.connect() as c:c.execute("DELETE FROM inventory WHERE id='second'")
  after=self.owned();stats=json.loads(after['stats'])
  self.assertEqual(stats['original_observed_level'],9)
  self.assertEqual(stats['observed_attribute_lines'],ROWS)
  self.assertEqual([x['calculation_status'] for x in stats['typed_modifiers']],
                   ['assumption_scenario','assumption_scenario','excluded_ambiguous','assumption_scenario'])
  self.assertIsNone(stats['typed_modifiers'][2]['value'])
  self.assertTrue(all(x['tech_activation']=='unknown' for x in stats['typed_modifiers']))
  self.assertEqual(server.planned_builds()[0]['slots'],plan)
  resolved=mod_rolls.equipped_build_modifiers(plan,server.inventory())
  self.assertEqual(len(resolved['modifiers']),3)
  self.assertTrue(resolved['unresolved'])  # unsupported/ambiguous rows remain visible
  base={'base_origin':'pre_mod_unbuffed','base_direct_hit':100,'rpm':600,'magazine':30,'reload_seconds':2}
  gated=mod_rolls.scenario(resolved['modifiers'],base)
  assumed=mod_rolls.scenario(resolved['modifiers'],{**base,'tech_policy':'assume_active'})
  self.assertEqual(gated['component_results']['direct_hit'],100)
  self.assertAlmostEqual(assumed['component_results']['direct_hit'],105)
  self.assertAlmostEqual(assumed['component_results']['reload_seconds_after_efficiency'],2/1.036)
  self.assertAlmostEqual(mod_rolls.scenario(resolved['modifiers'],{**base,'tech_policy':'assume_active','pre_mod_max_hp':1000,'max_hp_excludes_selected_mods':True})['component_results']['max_hp_sensitivity']['after_unrounded'],1024)
  self.assertEqual(mod_evidence.undo(self.db,'owned',applied['undo_id'])['status'],'undone')
  self.assertEqual(self.owned(),before)
  self.assertEqual(server.planned_builds()[0]['slots'],plan)

 def test_matching_source_and_ownership_guards(self):
  baseline=self.owned()
  cases=[('catalog_id','mod:chest_mod:quick-comeback-survival'),('slot','weapon_mod'),
         ('variant','Survival'),('level',8),('ownership','locked')]
  for key,value in cases:
   with self.subTest(key=key):
    changed=dict(self.data);changed[key]=value
    with server.connect() as c:c.execute("UPDATE video_import_proposals SET data=? WHERE id='proposal'",(json.dumps(changed),))
    with self.assertRaises(ValueError):mod_evidence.preview(self.db,self.root,'proposal','owned')
  with server.connect() as c:c.execute("UPDATE video_import_proposals SET data=? WHERE id='proposal'",(json.dumps(self.data),))
  altered={**self.data,'review_corrections':{'edited_fields':['level'],'reviewed_at':'2026-10-25T14:00:00+00:00'}}
  with server.connect() as c:c.execute("UPDATE video_import_proposals SET data=? WHERE id='proposal'",(json.dumps(altered),))
  with self.assertRaisesRegex(ValueError,'new source-frame check'):
   mod_evidence.preview(self.db,self.root,'proposal','owned')
  with server.connect() as c:c.execute("UPDATE video_import_proposals SET data=? WHERE id='proposal'",(json.dumps(self.data),))
  video_review.correction(self.db,'proposal',{'level':8})
  with server.connect() as c:
   corrected=json.loads(c.execute("SELECT data FROM video_import_proposals WHERE id='proposal'").fetchone()[0])
  self.assertIsNone(corrected['source_audit'])
  with server.connect() as c:c.execute("UPDATE video_import_proposals SET data=? WHERE id='proposal'",(json.dumps(self.data),))
  changed=dict(self.data);changed['source']={**self.source,'context':'../../outside.png'}
  with server.connect() as c:c.execute("UPDATE video_import_proposals SET data=? WHERE id='proposal'",(json.dumps(changed),))
  with self.assertRaises(ValueError):mod_evidence.preview(self.db,self.root,'proposal','owned')
  self.assertEqual(self.owned(),baseline)

 def test_stale_preview_duplicate_evidence_and_newer_edit_refuse_undo(self):
  review=mod_evidence.preview(self.db,self.root,'proposal','owned')
  with server.connect() as c:c.execute("UPDATE inventory SET name='Renamed' WHERE id='owned'")
  with self.assertRaisesRegex(ValueError,'changed'):
   mod_evidence.apply(self.db,self.root,'proposal','owned',review['token'],confirm=True)
  with server.connect() as c:c.execute("UPDATE inventory SET name='Healing Fortification' WHERE id='owned'")
  fresh=mod_evidence.preview(self.db,self.root,'proposal','owned')
  applied=mod_evidence.apply(self.db,self.root,'proposal','owned',fresh['token'],confirm=True)
  with server.connect() as c:c.execute("UPDATE inventory SET name='Changed after attach' WHERE id='owned'")
  with self.assertRaisesRegex(ValueError,'changed'):
   mod_evidence.undo(self.db,'owned',applied['undo_id'])
  self.assertEqual(self.owned()['name'],'Changed after attach')

 def test_archived_owner_still_blocks_same_source(self):
  review=mod_evidence.preview(self.db,self.root,'proposal','owned')
  mod_evidence.apply(self.db,self.root,'proposal','owned',review['token'],confirm=True)
  with server.connect() as c:
   c.execute("UPDATE inventory SET archived=1 WHERE id='owned'")
   c.execute('INSERT INTO inventory VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
             ('second','Healing Fortification','mod_unlock','chest_mod',None,'Battle',9,None,
              '{}',json.dumps({'catalog_id':CATALOG_ID}),None,'[]',server.now(),server.now(),0))
  with server.connect() as c:second_before=dict(c.execute("SELECT * FROM inventory WHERE id='second'").fetchone())
  with self.assertRaisesRegex(ValueError,'already linked to another'):
   mod_evidence.preview(self.db,self.root,'proposal','second')
  with server.connect() as c:self.assertEqual(dict(c.execute("SELECT * FROM inventory WHERE id='second'").fetchone()),second_before)

 def test_existing_roll_rows_require_explicit_replacement_and_undo(self):
  original_rows=['Weapon DMG + 3%','Magazine Capacity + 2%']
  with server.connect() as c:
   c.execute("UPDATE inventory SET stats=? WHERE id='owned'",(json.dumps({'observed_attribute_lines':original_rows,'roll_evidence_observation':'old-frame'}),))
  before=self.owned()
  review=mod_evidence.preview(self.db,self.root,'proposal','owned')
  self.assertTrue(review['replacing_existing'])
  self.assertEqual(review['before_rows'],original_rows)
  self.assertEqual(len(review['after_rows']),4)
  with self.assertRaisesRegex(ValueError,'confirm replacement'):
   mod_evidence.apply(self.db,self.root,'proposal','owned',review['token'],confirm=True)
  self.assertEqual(self.owned(),before)
  applied=mod_evidence.apply(self.db,self.root,'proposal','owned',review['token'],confirm=True,replace_existing=True)
  self.assertEqual(json.loads(self.owned()['stats'])['observed_attribute_lines'],ROWS)
  self.assertEqual(mod_evidence.undo(self.db,'owned',applied['undo_id'])['status'],'undone')
  self.assertEqual(self.owned(),before)

 def test_http_review_then_explicit_apply_and_undo(self):
  http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
  thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
  def post(path,data):
   request=Request(f'http://127.0.0.1:{http.server_port}/api/{path}',
                   data=json.dumps(data).encode(),headers={'Content-Type':'application/json'})
   with urlopen(request,timeout=5) as response:return json.load(response)
  try:
   original=self.owned()
   review=post('mod-evidence/preview',{'proposal_id':'proposal','inventory_id':'owned'})
   self.assertEqual(review['identity']['variant'],'Battle')
   self.assertEqual(self.owned(),original)
   applied=post('mod-evidence/apply',{'proposal_id':'proposal','inventory_id':'owned',
                                      'token':review['token'],'confirm':True})
   self.assertEqual(applied['status'],'attached')
   self.assertEqual(len(json.loads(self.owned()['stats'])['typed_modifiers']),4)
   undone=post('mod-evidence/undo',{'inventory_id':'owned','undo_id':applied['undo_id']})
   self.assertEqual(undone['status'],'undone')
   self.assertEqual(self.owned(),original)
  finally:
   http.shutdown();http.server_close();thread.join()


if __name__=='__main__':unittest.main()
