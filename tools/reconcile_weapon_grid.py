#!/usr/bin/env python3
"""Import source-reviewed Weapon Field Guide levels without altering inventory or builds."""
import hashlib,json,sqlite3,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path('~/Projects/once-human-advisor')
sys.path.insert(0,str(ROOT))
import catalog
import field_guide_profiles as guide
DATA=Path(__file__).with_name('weapon_reconciliation_evidence.json')
DB=ROOT/'data/advisor.sqlite3'
VIDEO=Path('~/Videos/screenrecording-2026-10-25_04-01-49.mp4')
HELD={('Flame Resonance','Deviant Energy'),('Spreading Marks','General'),('Bombardier Souvenir','Violent')}
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for part in iter(lambda:f.read(1024*1024),b''):h.update(part)
 return h.hexdigest()
def run(apply=False):
 data=json.loads(DATA.read_text())
 if sha(VIDEO)!=data['source_video_sha256']:raise ValueError('Original video hash changed')
 pairs={}
 for e in catalog.ENTRIES.values():
  if e.get('kind')=='mod' and e.get('slot')=='weapon_mod' and e.get('variant'):
   pairs.setdefault((e['name'],e['variant']),[]).append(e)
 candidates=[];held=[];locked=0
 for x in data['items']:
  if x['state']=='historical_locked':
   locked+=1
   continue
  if x['state']!='historical_unlocked' or not isinstance(x['level'],int):raise ValueError('Incomplete source row')
  if (x['family'],x['suffix']) in HELD:
   held.append({'family':x['family'],'variant':x['suffix'],'level':x['level'],'reason':'current catalog suffix spelling differs or is ambiguous'})
   continue
  key=(x['family'].replace('Multi-Bounce','Multi Bounce'),x['suffix'])
  matches=pairs.get(key,[])
  if len(matches)!=1:raise ValueError(f'Catalog identity unresolved: {key}, {matches}')
  entry=matches[0]
  guide._identity('personal',entry['id'])
  guide._level(x['level'],'unknown')
  frame=Path(x['local_evidence_frame'])
  if sha(frame)!=x['local_evidence_sha256']:raise ValueError('Source frame hash mismatch: '+str(frame))
  candidates.append((entry,x))
 if len(data['items'])!=184 or len(candidates)!=147 or len(held)!=3 or locked!=34:
  raise ValueError('Weapon grid coverage changed')
 c=sqlite3.connect(DB,timeout=30);c.row_factory=sqlite3.Row
 inserted=[];preserved=[]
 try:
  if apply:c.execute('BEGIN IMMEDIATE')
  inventory={}
  for row in c.execute("SELECT id,level,stats,effects FROM inventory WHERE kind='mod_unlock' AND archived=0"):
   identity=json.loads(row['effects'] or '{}').get('catalog_id')
   if identity:inventory.setdefault(identity,[]).append(row)
  stamp=datetime.now(timezone.utc).isoformat(timespec='seconds')
  for entry,x in candidates:
   identity=entry['id'];current=c.execute('SELECT * FROM field_guide_levels WHERE profile_id=? AND catalog_id=?',('personal',identity)).fetchone()
   copies=inventory.get(identity,[])
   if current or any(json.loads(row['stats'] or '{}').get('manual_level_override') or row['level'] not in (None,x['level']) for row in copies):
    preserved.append({'catalog_id':identity,'source_level':x['level'],'reason':'existing profile or later inventory edit'})
    continue
   evidence={'evidence_id':x['evidence_id'],'video':str(VIDEO) if x.get('source_video') else None,
             'video_sha256':data['source_video_sha256'] if x.get('source_video') else None,
             'source_date':x['source_date'],'source_time_seconds':x.get('original_video_time_seconds'),
             'source_time_range_seconds':x.get('original_video_time_seconds_range'),
             'time_precision':x['time_precision'],'frame':x['local_evidence_frame'],
             'frame_sha256':x['local_evidence_sha256'],
             'cue':'numbered card in account Field Guide Weapon grid',
             'tooltip_attributes':'not inspected','tech_activation':'unknown'}
   ref=json.dumps(evidence,sort_keys=True)
   kind='reviewed_screenshot_grid' if not x.get('source_video') else 'reviewed_video_grid'
   next_row={'profile_id':'personal','catalog_id':identity,'level':x['level'],'shiny_status':'unknown','source_kind':kind,'source_ref':ref,'updated':stamp}
   if apply:
    c.execute('INSERT INTO field_guide_levels VALUES(?,?,?,?,?,?,?)',('personal',identity,x['level'],'unknown',kind,ref,stamp))
    c.execute('INSERT INTO field_guide_level_events(profile_id,catalog_id,prior,next,source_kind,created) VALUES(?,?,?,?,?,?)',('personal',identity,None,json.dumps(next_row),kind,stamp))
   inserted.append(identity)
  if apply:c.commit()
 finally:c.close()
 print(json.dumps({'mode':'apply' if apply else 'check','historical_unlocked':150,'historical_locked':34,
                   'exact_catalog_identities_held':held,'profile_levels_added_or_addable':len(inserted),
                   'existing_edits_preserved':preserved,'inventory_unchanged':True},indent=2))
if __name__=='__main__':run('--apply' in sys.argv)
