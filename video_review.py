"""Persistent, review-first video import state and guarded inventory commit."""
import hashlib,json,sqlite3,uuid
from datetime import datetime,timezone
from pathlib import Path
import catalog
import mod_rolls
import video_import_plan
import field_guide_profiles

def _require_legacy_copy_source(data):
 if field_guide_profiles.source_system(data)!=field_guide_profiles.LEGACY_SYSTEM:
  raise ValueError('A Field Guide or unknown-system hover is not a physical Backpack copy; review its collection progression separately')

def now():return datetime.now(timezone.utc).isoformat(timespec='seconds')
def connect(db):
 c=sqlite3.connect(db,timeout=30);c.row_factory=sqlite3.Row;return c

def ensure_schema(c):
 c.executescript('''CREATE TABLE IF NOT EXISTS video_import_runs(id TEXT PRIMARY KEY,media_id TEXT NOT NULL,fingerprint TEXT NOT NULL UNIQUE,status TEXT NOT NULL,options TEXT NOT NULL,summary TEXT NOT NULL DEFAULT '{}',created TEXT NOT NULL,updated TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS video_import_proposals(id TEXT PRIMARY KEY,run_id TEXT NOT NULL,identity_key TEXT NOT NULL,data TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',inventory_id TEXT,updated TEXT NOT NULL,UNIQUE(run_id,identity_key),FOREIGN KEY(run_id) REFERENCES video_import_runs(id));''')

def fingerprint(path,options):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 h.update(json.dumps(options,sort_keys=True).encode())
 return h.hexdigest()

def create_run(db,media_id,path,options):
 key=fingerprint(path,options)
 with connect(db) as c:
  found=c.execute('SELECT * FROM video_import_runs WHERE fingerprint=?',(key,)).fetchone()
  if found:return dict(found),False
  run_id=uuid.uuid4().hex;ts=now()
  c.execute('INSERT INTO video_import_runs VALUES(?,?,?,?,?,?,?,?)',(run_id,media_id,key,'queued',json.dumps(options),'{}',ts,ts));c.commit()
  return dict(c.execute('SELECT * FROM video_import_runs WHERE id=?',(run_id,)).fetchone()),True

def update_run(db,run_id,status,summary=None):
 with connect(db) as c:
  c.execute('UPDATE video_import_runs SET status=?,summary=?,updated=? WHERE id=?',(status,json.dumps(summary or {}),now(),run_id));c.commit()

def persist_result(db,run_id,result,data_root):
 with connect(db) as c:
  c.execute('BEGIN IMMEDIATE')
  for item in result['proposals']:
   p=dict(item);p['source']={**p['source'],**{k:str(Path(p['source'][k]).resolve().relative_to(data_root.resolve())) for k in ('frame','tooltip','context') if k in p['source']}}
   p['typed_modifiers']=mod_rolls.proposal_modifiers(p)
   # Source encounter is part of the observation identity. Catalog ID and
   # level alone cannot tell whether two hovers show the same physical copy.
   encounter=(p.get('source') or {}).get('encounter')
   if encounter is None:encounter=(p.get('source') or {}).get('timestamp')
   identity_key='|'.join([p['catalog_id'],p['ownership'],str(p['level']),str(encounter)])
   existing=c.execute('SELECT id FROM video_import_proposals WHERE run_id=? AND identity_key=?',(run_id,identity_key)).fetchone()
   if existing:continue
   c.execute('INSERT INTO video_import_proposals(id,run_id,identity_key,data,status,updated) VALUES(?,?,?,?,?,?)',(uuid.uuid4().hex,run_id,identity_key,json.dumps(p),'pending',now()))
  c.execute('UPDATE video_import_runs SET status=?,summary=?,updated=? WHERE id=?',('done',json.dumps({'frames_scanned':result['frames_scanned'],'duration':result['duration'],'warnings':result['warnings'],'proposals':len(result['proposals'])}),now(),run_id));c.commit()

def list_data(db):
 with connect(db) as c:
  runs=[dict(r) for r in c.execute('SELECT * FROM video_import_runs ORDER BY created DESC')]
  proposals=[]
  for r in c.execute('SELECT * FROM video_import_proposals ORDER BY rowid'):
   p=dict(r);p['data']=json.loads(p['data']);proposals.append(p)
  for r in runs:r['summary']=json.loads(r['summary']);r['options']=json.loads(r['options'])
  return runs,proposals

def system_context(db,run_id):
 """Read-only full-frame proof and a stale-source token for system review."""
 with connect(db) as c:
  run=c.execute('SELECT * FROM video_import_runs WHERE id=?',(run_id,)).fetchone()
  if not run:raise ValueError('Import run not found')
  rows=list(c.execute('SELECT id,data,status FROM video_import_proposals WHERE run_id=? ORDER BY rowid',(run_id,)))
  if not rows:raise ValueError('Import has no preserved source frames')
  observations=[]
  for row in rows:
   data=json.loads(row['data']);source=data.get('source') or {}
   frame=source.get('frame')
   if not frame:raise ValueError('A proposal has no full source frame')
   path=(Path(db).parent/frame).resolve()
   root=(Path(db).parent/'media'/run['media_id']/'video-review'/run_id).resolve()
   if not path.is_relative_to(root) or not path.is_file():
    raise ValueError('Source frame is missing or outside this import run')
   observations.append((row,source,frame,path))
  count=len(observations)
  proof=[{'proposal_id':observations[i][0]['id'],
          'frame':observations[i][2],
          'sha256':hashlib.sha256(observations[i][3].read_bytes()).hexdigest(),
          'timestamp':observations[i][1].get('timestamp')} for i in range(count)]
  selected={0,count//2,count-1}
  display_frames=[proof[i] for i in sorted(selected)]
  digest=hashlib.sha256(json.dumps({'run_id':run_id,'fingerprint':run['fingerprint'],
             'rows':[(row['id'],row['status'],row['data']) for row in rows],
             'proof':proof},sort_keys=True).encode()).hexdigest()
  return {'run_id':run_id,'media_id':run['media_id'],'proposal_count':count,
          'source_frames':display_frames,'source_proof':proof,'source_frame_count':count,
          'review_token':digest,
          'classification_choices':['current_field_guide','legacy_backpack'],
          'inventory_unchanged':True}

def review_system(db,run_id,system,review_token,cues,confirm=False):
 """Explicit source-context classification; never infer system from mod name."""
 if system not in (field_guide_profiles.SYSTEM,field_guide_profiles.LEGACY_SYSTEM):
  raise ValueError('Choose Field Guide or legacy Backpack')
 required=({'mods_tab_selected','backpack_separate','collection_level_grid'}
           if system==field_guide_profiles.SYSTEM else
           {'backpack_tab_selected','physical_copy_context'})
 if not confirm or not isinstance(cues,list) or not required<=set(cues):
  raise ValueError('Review the full source frames and confirm the specific UI context')
 context=system_context(db,run_id)
 if review_token!=context['review_token']:raise ValueError('Source changed; reopen full-frame system review')
 with connect(db) as c:
  c.execute('BEGIN IMMEDIATE')
  fresh=system_context(db,run_id)
  if fresh['review_token']!=review_token:raise ValueError('Source changed during system review')
  rows=list(c.execute('SELECT id,data FROM video_import_proposals WHERE run_id=?',(run_id,)))
  for row in rows:
   data=json.loads(row['data']);prior=field_guide_profiles.source_system(data)
   if prior not in (None,system):raise ValueError('A proposal has a conflicting system; review it separately')
  stamp=now()
  for row in rows:
   data=json.loads(row['data']);audit=data.get('source_audit') or {}
   audit['mod_system']=system
   audit['system_review']={'reviewed_at':stamp,'context_cues':sorted(required),
                            'source_proof':context['source_proof'],
                            'run_fingerprint':c.execute('SELECT fingerprint FROM video_import_runs WHERE id=?',(run_id,)).fetchone()[0]}
   data['source_audit']=audit
   c.execute('UPDATE video_import_proposals SET data=?,updated=? WHERE id=?',(json.dumps(data),stamp,row['id']))
  c.commit()
  return {'run_id':run_id,'classified':len(rows),'mod_system':system,
          'source_proof':context['source_proof'],
          'source_proof_count':context['source_frame_count'],'inventory_unchanged':True,
          'profile_unchanged':True}

def correction(db,proposal_id,changes):
 allowed={'catalog_id','level','rarity','main_effect','attribute_rows'}
 if set(changes)-allowed:raise ValueError('Unsupported correction field')
 with connect(db) as c:
  row=c.execute('SELECT * FROM video_import_proposals WHERE id=?',(proposal_id,)).fetchone()
  if not row:raise ValueError('Proposal not found')
  if row['status']=='committed':raise ValueError('Committed proposal cannot be edited here')
  data=json.loads(row['data'])
  if data['ownership']!='unlocked':
   raise ValueError('Only a frame with visible Equip and level may become an owned mod; locked/uncertain frames remain review-only')
  identity=str(changes.get('catalog_id',data['catalog_id']))
  entry=catalog.ENTRIES.get(identity)
  if not entry or entry['kind']!='mod':raise ValueError('Choose a catalog mod identity')
  level=changes.get('level',data['level'])
  if isinstance(level,bool) or not isinstance(level,int) or not 1<=level<=17:raise ValueError('Field Guide level must be 1–17')
  rarity=changes.get('rarity',data['rarity'])
  if rarity not in (None,'legendary','epic','rare'):raise ValueError('Rarity must be gold, purple, blue or unknown')
  main=str(changes.get('main_effect',data['main_effect']) or '').strip()[:1200]
  attrs=changes.get('attribute_rows',data['attribute_rows'])
  if not isinstance(attrs,list) or len(attrs)>12 or any(not isinstance(x,str) or len(x)>350 for x in attrs):raise ValueError('Use at most 12 short attribute lines')
  prior={k:data.get(k) for k in allowed}
  data.update({'catalog_id':identity,'name':entry['name'],'variant':entry.get('variant'),'slot':entry.get('slot'),'level':level,'rarity':rarity,'main_effect':main,'attribute_rows':[x.strip() for x in attrs if x.strip()]})
  data['review_corrections']={'reviewed_at':now(),'prior_extraction':prior,'edited_fields':sorted(k for k in allowed if data.get(k)!=prior.get(k))}
  # Any changed identity, level, rarity or text needs a new source check. A
  # tooltip's checked numbers cannot validate a newly chosen variant/level.
  if data.get('source_audit') and any(data.get(key)!=prior.get(key) for key in allowed):
   data['source_audit']=None
  if any(data.get(key)!=prior.get(key) for key in allowed):
   data.pop('instance_review',None)
  data['typed_modifiers']=mod_rolls.proposal_modifiers(data,proposal_id)
  c.execute('UPDATE video_import_proposals SET data=?,status=?,updated=? WHERE id=?',(json.dumps(data),'reviewed',now(),proposal_id));c.commit()
  return {'id':proposal_id,'status':'reviewed'}

def dismiss(db,proposal_id):
 with connect(db) as c:
  row=c.execute('SELECT status FROM video_import_proposals WHERE id=?',(proposal_id,)).fetchone()
  if not row:raise ValueError('Proposal not found')
  if row['status']=='committed':raise ValueError('Undo the inventory commit before dismissing')
  c.execute('UPDATE video_import_proposals SET status=?,updated=? WHERE id=?',('dismissed',now(),proposal_id));c.commit()
  return {'id':proposal_id,'status':'dismissed'}

def review_distinct_copy(db,proposal_id,note):
 """Explicitly distinguish a physical copy; never infer this from catalog ID."""
 note=str(note or '').strip()
 if len(note)<12:raise ValueError('Describe the separate card or source evidence for this physical copy')
 with connect(db) as c:
  row=c.execute('SELECT * FROM video_import_proposals WHERE id=?',(proposal_id,)).fetchone()
  if not row or row['status']!='reviewed':raise ValueError('Review this tooltip before deciding copy identity')
  data=json.loads(row['data'])
  if data.get('ownership')!='unlocked':raise ValueError('Only a source-unlocked mod can be recorded as an owned copy')
  context=(data.get('source') or {}).get('context')
  if not context or not (Path(db).parent/context).is_file():
   raise ValueError('Full source context is required to distinguish copies')
  data['instance_review']={'decision':'distinct_copy','reason':note,'context':context,
                           'reviewed_at':now()}
  c.execute('UPDATE video_import_proposals SET data=?,updated=? WHERE id=?',
            (json.dumps(data),now(),proposal_id));c.commit()
  return {'id':proposal_id,'decision':'distinct_copy','inventory_unchanged':True}

def _backup(db):
 folder=Path(db).parent/'backups';folder.mkdir(exist_ok=True)
 dest=folder/('video-import-before-commit-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')+'.sqlite3')
 source=connect(db);target=sqlite3.connect(dest)
 try:source.backup(target)
 finally:target.close();source.close()
 dest.chmod(0o600)
 return dest

def _semantic_uncertainties(data):
 audit=data.get('source_audit') or {}
 found=[dict(x) for x in audit.get('semantic_uncertainties') or []]
 for index,row in enumerate(data.get('attribute_rows') or []):
  if 'damage from monsters' in row.casefold() and any(mark in row for mark in ('−+','—+','-+')):
   field=f'attribute_rows[{index}]'
   if not any(x.get('field')==field for x in found):
    found.append({'field':field,'issue':'Source displays both minus-like and plus signs; direction unresolved.', 'source_text':row})
 return found

def commit(db,proposal_id):
 with connect(db) as c:
  row=c.execute('SELECT * FROM video_import_proposals WHERE id=?',(proposal_id,)).fetchone()
  if not row:raise ValueError('Proposal not found')
  if row['status']=='committed':return {'status':'already_committed','inventory_id':row['inventory_id'],'backup':None}
  if row['status']!='reviewed':raise ValueError('Review and save corrections before adding to My Mods')
  reviewed_data=row['data']
  data=json.loads(row['data'])
  _require_legacy_copy_source(data)
  if data['ownership']!='unlocked' or not {'Equip action','visible level and suffix'}<=set(data['ownership_cues']):raise ValueError('This frame does not prove ownership')
  entry=catalog.ENTRIES.get(data['catalog_id'])
  if not entry or entry['kind']!='mod' or data['slot']!=entry['slot']:raise ValueError('Catalog identity or slot conflict')
  if not isinstance(data['level'],int) or not 1<=data['level']<=17:raise ValueError('Known Field Guide level required')
  peers=[]
  for other in c.execute('SELECT id,status,data FROM video_import_proposals WHERE run_id=? AND id<>?',
                         (row['run_id'],proposal_id)):
   if other['status']=='dismissed':continue
   candidate=json.loads(other['data'])
   if candidate.get('ownership')=='unlocked' and candidate.get('catalog_id')==data['catalog_id'] and candidate.get('level')==data['level']:
    peers.append(other['id'])
  distinct=(data.get('instance_review') or {}).get('decision')=='distinct_copy'
  if peers and not distinct:
   raise ValueError('Another source observation has this variant and level; review physical-copy identity before adding')
  existing=None
  for item in c.execute("SELECT * FROM inventory WHERE kind='mod_unlock' AND archived=0"):
   if json.loads(item['effects'] or '{}').get('catalog_id')==data['catalog_id']:existing=item;break
  if existing and not distinct:
   raise ValueError('A matching catalog variant is already recorded; review whether this is its evidence or a distinct owned copy')
 backup=_backup(db)
 with connect(db) as c:
  c.execute('BEGIN IMMEDIATE')
  row=c.execute('SELECT * FROM video_import_proposals WHERE id=?',(proposal_id,)).fetchone()
  if not row or row['status']!='reviewed' or row['data']!=reviewed_data:raise ValueError('Proposal changed; reopen review')
  data=json.loads(row['data'])
  _require_legacy_copy_source(data)
  if (data.get('instance_review') or {}).get('decision')!='distinct_copy':
   for item in c.execute("SELECT effects FROM inventory WHERE kind='mod_unlock' AND archived=0"):
    if json.loads(item['effects'] or '{}').get('catalog_id')==data['catalog_id']:raise ValueError('Mod became owned during review; reopen collection')
  iid=uuid.uuid4().hex;stamp=now()
  ambiguities=_semantic_uncertainties(data)
  stats={'observed_rarity':data['rarity'],'observed_attribute_lines':data['attribute_rows'],
         'observed_attribute_ocr_status':'reviewed_from_video',
         'attribute_coverage':'source_direction_ambiguous' if ambiguities else 'reviewed_text_only',
         'typed_modifiers':mod_rolls.proposal_modifiers(data,proposal_id),
         'video_import':{'proposal_id':proposal_id,'source':data['source'],'review_corrections':data.get('review_corrections'),
                         'instance_review':data.get('instance_review'),
                         'source_audit':data.get('source_audit'),'semantic_uncertainties':ambiguities}}
  effects={'catalog_id':data['catalog_id'],'mod_system':field_guide_profiles.LEGACY_SYSTEM,
           'text':data['main_effect'],'observed_text':data['main_effect'],'calculation_status':'catalog_partial'}
  evidence=[{'kind':'reviewed_video_tooltip','proposal_id':proposal_id,'source':data['source'],
             'ownership_cues':data['ownership_cues'],'semantic_uncertainties':ambiguities}]
  c.execute('INSERT INTO inventory VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(iid,entry['name'],'mod_unlock',entry['slot'],None,entry.get('variant'),data['level'],None,json.dumps(stats),json.dumps(effects),None,json.dumps(evidence),stamp,stamp,0))
  c.execute("INSERT INTO undo(entity,entity_id,prior,created) VALUES('inventory',?,'null',?)",(iid,stamp))
  c.execute('UPDATE video_import_proposals SET status=?,inventory_id=?,updated=? WHERE id=?',('committed',iid,stamp,proposal_id))
  c.commit()
  return {'status':'committed','inventory_id':iid,'backup':str(backup)}

def undo(db,proposal_id):
 with connect(db) as c:
  row=c.execute('SELECT * FROM video_import_proposals WHERE id=?',(proposal_id,)).fetchone()
  if not row or row['status']!='committed':raise ValueError('No committed proposal to undo')
  if json.loads(row['data']).get('batch_commit'):raise ValueError('Use batch undo for this source-checked import')
  iid=row['inventory_id'];last=c.execute('SELECT * FROM undo ORDER BY id DESC LIMIT 1').fetchone()
  if not last or last['entity']!='inventory' or last['entity_id']!=iid or last['prior']!='null':raise ValueError('Other changes followed; restore from backup instead of undoing the wrong action')
  for build in c.execute('SELECT item_ids FROM loadouts'):
   if iid in json.loads(build['item_ids']):raise ValueError('A saved loadout now uses this mod; remove it from the loadout first')
  for build in c.execute('SELECT slots FROM planned_builds'):
   if iid in json.dumps(json.loads(build['slots'])):raise ValueError('A saved build now refers to this mod; remove it from the build first')
  c.execute('DELETE FROM inventory WHERE id=?',(iid,));c.execute('DELETE FROM undo WHERE id=?',(last['id'],))
  c.execute('UPDATE video_import_proposals SET status=?,inventory_id=NULL,updated=? WHERE id=?',('reviewed',now(),proposal_id));c.commit()
  return {'status':'reviewed','undone_inventory_id':iid}

def commit_checked_batch(db,run_id,plan_token=None,defer_ids=None):
 """One explicit action for a source-checked run; never called by video analysis."""
 with connect(db) as c:
  run=c.execute('SELECT * FROM video_import_runs WHERE id=?',(run_id,)).fetchone()
  if not run or run['status']!='done':raise ValueError('Completed video review not found')
  qa=json.loads(run['summary']).get('qa') or {}
  if qa.get('source_checked') is not True or not qa.get('owned_proposals'):
   raise ValueError('This run has not passed source checking')
  entries=[]
  for row in c.execute('SELECT * FROM video_import_proposals WHERE run_id=?',(run_id,)):
   data=json.loads(row['data'])
   if row['status']!='dismissed' and data['ownership']=='unlocked':entries.append((row,data))
  if len(entries)!=qa['owned_proposals']:raise ValueError('Proposal count changed; source check must be repeated')
  seen=set()
  for row,data in entries:
   _require_legacy_copy_source(data)
   if row['status'] not in ('pending','committed'):raise ValueError('Proposal changed after source check')
   entry=catalog.ENTRIES.get(data['catalog_id'])
   if not entry or entry['kind']!='mod' or data['slot']!=entry['slot'] or data['catalog_id'] in seen:
    raise ValueError('Catalog identity, slot, or duplicate conflict')
   seen.add(data['catalog_id'])
   if not isinstance(data['level'],int) or not 1<=data['level']<=17 or data['rarity'] not in ('legendary','epic','rare'):
    raise ValueError('An owned level or rarity remains unverified')
   if not {'Equip action','visible level and suffix'}<=set(data.get('ownership_cues') or []):
    raise ValueError('An ownership cue remains unverified')
   if len(data.get('attribute_rows') or [])!=4 or not data.get('main_effect'):
    raise ValueError('A tooltip remains incomplete')
   audit=data.get('source_audit') or {}
   if (not str(audit.get('status','')).startswith('source_text_and_numbers_checked')
       or (audit.get('main_effect') or {}).get('source_text')!=data['main_effect']
       or [x.get('source_text') for x in audit.get('attribute_rows') or []]!=data['attribute_rows']):
    raise ValueError('A proposal lacks current frame-checked text and numeric audit')
   context=data.get('source',{}).get('context','')
   if not context or not (Path(db).parent/context).is_file():
    raise ValueError('Source context is missing')
  current_inventory=[]
  for item in c.execute("SELECT id,kind,level,archived,stats,effects FROM inventory"):
   unpacked=dict(item)
   unpacked['effects']=json.loads(unpacked['effects'] or '{}')
   unpacked['stats']=json.loads(unpacked['stats'] or '{}')
   current_inventory.append(unpacked)
  proposal_rows=[{'id':row['id'],'run_id':run_id,'status':row['status'],
                  'data':json.loads(row['data'])}
                 for row in c.execute('SELECT * FROM video_import_proposals WHERE run_id=? ORDER BY rowid',(run_id,))]
  batch_plan=video_import_plan.plan(run_id,proposal_rows,current_inventory)
  if plan_token is not None and batch_plan['plan_token']!=plan_token:
   raise ValueError('Owned instances or reviewed proposals changed; reopen the batch plan')
  unresolved={item['proposal_id'] for item in batch_plan['entries']
              if item['classification'] not in ('new_owned_copy_candidate','already_committed')}
  deferred=set(defer_ids or [])
  if unresolved!=deferred or (unresolved and plan_token is None):
   raise ValueError('Existing or ambiguous copies require explicit deferral and individual evidence review')
  fresh=[(row,data) for row,data in entries if row['status']=='pending'
         and row['id'] not in deferred]
  if not fresh:return {'status':'nothing_to_add','added':0,'deferred':len(deferred),'backup':None,'batch_id':None}
 backup=_backup(db)
 batch_id=uuid.uuid4().hex;stamp=now()
 with connect(db) as c:
  c.execute('BEGIN IMMEDIATE')
  # Fresh reads inside the write lock guard changes since preflight.
  for row,data in fresh:
   current=c.execute('SELECT status,data FROM video_import_proposals WHERE id=?',(row['id'],)).fetchone()
   if not current or current['status']!='pending' or current['data']!=row['data']:
    raise ValueError('Proposal changed; reopen video review')
   _require_legacy_copy_source(json.loads(current['data']))
   for item in c.execute("SELECT effects FROM inventory WHERE kind='mod_unlock' AND archived=0"):
    if json.loads(item['effects'] or '{}').get('catalog_id')==data['catalog_id']:
     raise ValueError('Mod became owned during the batch; reopen collection')
   entry=catalog.ENTRIES[data['catalog_id']]
   iid=uuid.uuid4().hex
   ambiguities=_semantic_uncertainties(data)
   stats={'observed_rarity':data['rarity'],'observed_attribute_lines':data['attribute_rows'],
          'observed_attribute_ocr_status':'source_text_checked_from_video',
          'attribute_coverage':'source_direction_ambiguous' if ambiguities else 'source_text_checked',
          'typed_modifiers':mod_rolls.proposal_modifiers(data,row['id']),
          'video_import':{'proposal_id':row['id'],'source':data['source'],'batch_id':batch_id,
                          'source_audit':data.get('source_audit'),'semantic_uncertainties':ambiguities}}
   effects={'catalog_id':data['catalog_id'],'mod_system':field_guide_profiles.LEGACY_SYSTEM,'text':data['main_effect'],
            'observed_text':data['main_effect'],'calculation_status':'catalog_partial'}
   evidence=[{'kind':'source_checked_video_tooltip','proposal_id':row['id'],'source':data['source'],
              'ownership_cues':data['ownership_cues'],'semantic_uncertainties':ambiguities,
              'numeric_rows':'source checked where legible; see source audit'}]
   c.execute('INSERT INTO inventory VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
             (iid,entry['name'],'mod_unlock',entry['slot'],None,entry.get('variant'),data['level'],None,
              json.dumps(stats),json.dumps(effects),None,json.dumps(evidence),stamp,stamp,0))
   c.execute("INSERT INTO undo(entity,entity_id,prior,created) VALUES('inventory',?,'null',?)",(iid,stamp))
   data['batch_commit']={'id':batch_id,'inventory_id':iid,'created':stamp}
   c.execute('UPDATE video_import_proposals SET data=?,status=?,inventory_id=?,updated=? WHERE id=?',
             (json.dumps(data),'committed',iid,stamp,row['id']))
  summary=json.loads(c.execute('SELECT summary FROM video_import_runs WHERE id=?',(run_id,)).fetchone()[0])
  summary.setdefault('qa',{})['last_batch_id']=batch_id
  c.execute('UPDATE video_import_runs SET summary=?,updated=? WHERE id=?',(json.dumps(summary),stamp,run_id))
  c.commit()
 return {'status':'committed','added':len(fresh),'deferred':len(deferred),'backup':str(backup),'batch_id':batch_id}

def undo_checked_batch(db,run_id,batch_id):
 with connect(db) as c:
  rows=[]
  for row in c.execute('SELECT * FROM video_import_proposals WHERE run_id=?',(run_id,)):
   data=json.loads(row['data'])
   if data.get('batch_commit',{}).get('id')==batch_id:rows.append((row,data))
  if not rows or any(row['status']!='committed' for row,_ in rows):raise ValueError('Batch is not fully committed')
  ids={row['inventory_id'] for row,_ in rows}
  latest=list(c.execute('SELECT * FROM undo ORDER BY id DESC LIMIT ?', (len(rows),)))
  if len(latest)!=len(rows) or {r['entity_id'] for r in latest}!=ids or any(r['entity']!='inventory' or r['prior']!='null' for r in latest):
   raise ValueError('Other changes followed; use the saved backup instead of undoing unrelated work')
  for build in c.execute('SELECT item_ids FROM loadouts'):
   if ids.intersection(json.loads(build['item_ids'])):raise ValueError('A saved loadout uses an imported mod')
  for build in c.execute('SELECT slots FROM planned_builds'):
   if any(iid in build['slots'] for iid in ids):raise ValueError('A saved build uses an imported mod')
 with connect(db) as c:
  c.execute('BEGIN IMMEDIATE')
  locked_latest=list(c.execute('SELECT * FROM undo ORDER BY id DESC LIMIT ?', (len(rows),)))
  if len(locked_latest)!=len(rows) or {r['entity_id'] for r in locked_latest}!=ids:
   raise ValueError('Other changes followed; use the saved backup instead')
  for build in c.execute('SELECT item_ids FROM loadouts'):
   if ids.intersection(json.loads(build['item_ids'])):
    raise ValueError('A saved loadout uses an imported mod')
  for build in c.execute('SELECT slots FROM planned_builds'):
   if any(iid in build['slots'] for iid in ids):
    raise ValueError('A saved build uses an imported mod')
  for row,data in rows:
   c.execute('DELETE FROM inventory WHERE id=?',(row['inventory_id'],))
   data.pop('batch_commit',None)
   c.execute('UPDATE video_import_proposals SET data=?,status=?,inventory_id=NULL,updated=? WHERE id=?',
             (json.dumps(data),'pending',now(),row['id']))
  for entry in latest:c.execute('DELETE FROM undo WHERE id=?',(entry['id'],))
  summary=json.loads(c.execute('SELECT summary FROM video_import_runs WHERE id=?',(run_id,)).fetchone()[0])
  if summary.get('qa',{}).get('last_batch_id')==batch_id:summary['qa'].pop('last_batch_id',None)
  c.execute('UPDATE video_import_runs SET summary=?,updated=? WHERE id=?',(json.dumps(summary),now(),run_id))
  c.commit()
 return {'status':'undone','removed':len(rows)}
