"""Separate, provenance-aware Field Guide progress for personal and starter profiles.

The Guide records one highest level per exact catalog variant. It is not a
backpack of physical copies, and it never derives ownership from catalog art.
Legacy inventory and planned builds remain separate tables.
"""
import json
import hashlib
import uuid
from collections import defaultdict
from pathlib import Path
from math import isclose
from datetime import datetime, timezone

import catalog
import mod_rolls

PROFILES={'personal':'My existing profile','new_player':'New player · empty'}
SYSTEM='current_field_guide'
LEGACY_SYSTEM='legacy_backpack'


def source_system(data):
    """Explicit reviewed source classification; a generic All Mods label is not enough."""
    source=data.get('source') or {}
    audit=data.get('source_audit') or {}
    values={value for value in (audit.get('mod_system'),source.get('mod_system'),data.get('mod_system')) if value}
    return next(iter(values)) if len(values)==1 else 'conflicting' if values else None


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def ensure_schema(c):
    c.executescript('''
      CREATE TABLE IF NOT EXISTS field_guide_levels(
        profile_id TEXT NOT NULL, catalog_id TEXT NOT NULL, level INTEGER NOT NULL,
        shiny_status TEXT NOT NULL, source_kind TEXT NOT NULL, source_ref TEXT,
        updated TEXT NOT NULL, PRIMARY KEY(profile_id,catalog_id));
      CREATE TABLE IF NOT EXISTS field_guide_level_events(
        id INTEGER PRIMARY KEY AUTOINCREMENT, profile_id TEXT NOT NULL,
        catalog_id TEXT NOT NULL, prior TEXT, next TEXT NOT NULL,
        source_kind TEXT NOT NULL, created TEXT NOT NULL);
    ''')


def _identity(profile_id,catalog_id):
    if profile_id not in PROFILES:
        raise ValueError('Choose the personal or new-player profile')
    entry=catalog.ENTRIES.get(catalog_id)
    if not entry or entry.get('kind')!='mod' or entry.get('family_only') or not entry.get('variant'):
        raise ValueError('Choose one selectable mod with an exact suffix')
    if (entry.get('system_generation')=='legacy_random_roll' or
            not (entry.get('current_records') or entry.get('attribute_names') or entry.get('source_observed_level'))):
        raise ValueError('This suffix is not verified as a current Field Guide entry; keep it as a catalog candidate')
    return entry


def _level(level,shiny_status):
    if isinstance(level,bool) or not isinstance(level,int) or not 0<=level<=17:
        raise ValueError('Field Guide level must be a whole number from 0 to 17')
    if shiny_status not in ('unknown','regular','shiny'):
        raise ValueError('Shiny status must be unknown, regular or shiny')
    if shiny_status=='shiny' and level!=17:
        raise ValueError('Shiny Field Guide entry requires level 17')
    if level==0 and shiny_status!='unknown':
        raise ValueError('A locked entry has no Shiny status')


def rarity_for_level(level):
    return ('not_unlocked' if level==0 else 'common' if level<=2 else
            'uncommon' if level<=4 else 'rare' if level<=6 else
            'epic' if level<=8 else 'legendary')


def get(c,profile_id,catalog_id):
    _identity(profile_id,catalog_id)
    row=c.execute('SELECT * FROM field_guide_levels WHERE profile_id=? AND catalog_id=?',
                  (profile_id,catalog_id)).fetchone()
    return dict(row) if row else None


def _reviewed_exact_rows(c,catalog_id,level,shiny_status):
    """Shared catalog evidence from this exact current-system variant and level.

    A recording can inform a blank player's manual entry without giving that
    player Maurice's ownership. Differing same-level sources are never merged.
    """
    if not c.execute("SELECT 1 FROM sqlite_master WHERE name='video_import_proposals'").fetchone():return None
    observations=[];data_root=Path(c.execute('PRAGMA database_list').fetchone()[2]).parent
    for row in c.execute("SELECT p.id,p.run_id,p.data,r.media_id,r.fingerprint,r.created FROM video_import_proposals p JOIN video_import_runs r ON r.id=p.run_id WHERE p.status!='dismissed'"):
        data=json.loads(row['data']);audit=data.get('source_audit') or {}
        if (data.get('catalog_id')!=catalog_id or data.get('level')!=level or
                data.get('shiny_status','unknown')!=shiny_status or data.get('ownership')!='unlocked' or
                source_system(data)!=SYSTEM or not str(audit.get('status') or '').startswith('source_text_and_numbers_checked')):
            continue
        texts=data.get('attribute_rows') or []
        if ([x.get('source_text') for x in audit.get('attribute_rows') or []]!=texts or
                (audit.get('main_effect') or {}).get('source_text')!=data.get('main_effect')):
            continue
        reviewed=audit.get('system_review') or {}
        if reviewed.get('run_fingerprint')!=row['fingerprint']:continue
        proofs=reviewed.get('source_proof') or []
        frame_root=(data_root/'media'/row['media_id']/'video-review'/row['run_id']).resolve()
        if not proofs:continue
        valid=True
        for proof in proofs:
            relative=proof.get('frame') if isinstance(proof,dict) else None
            path=(data_root/relative).resolve() if isinstance(relative,str) else data_root
            if (not path.is_relative_to(frame_root) or not path.is_file() or
                    hashlib.sha256(path.read_bytes()).hexdigest()!=proof.get('sha256')):
                valid=False;break
        if valid:
            context=audit.get('patch_context') or 'reviewed_run:'+row['run_id']+':'+row['fingerprint']
            observations.append((row['id'],data,context,row['created']))
    if not observations:return None
    signatures={(tuple(data['attribute_rows']),data.get('main_effect')) for _,data,_,_ in observations}
    contexts={context for _,_,context,_ in observations}
    if len(signatures)!=1 or len(contexts)!=1:
        return {'conflict':'Source-checked observations at the same exact variant and level disagree or lack a shared patch context; numeric cells are withheld.',
                'proposal_ids':[pid for pid,_,_,_ in observations]}
    proposal_id,data,context,recorded_at=observations[0]
    typed=mod_rolls.proposal_modifiers(data,proposal_id)
    profile=catalog.resolve(catalog_id,level,system=SYSTEM,shiny=shiny_status=='shiny')
    tiers=profile.get('level_profile') or [None]*len(typed)
    records=[]
    for index,item in enumerate(typed):
        records.append({'name':item['raw_text'],'raw_text':item['raw_text'],
                        'value_percent':item.get('value'),'unit':item.get('unit'),
                        'direction':item.get('direction'),'tier':tiers[index] if index<len(tiers) else None,
                        'source':(data.get('source') or {}).get('frame'),
                        'source_status':'source-checked current Field Guide frame',
                        'observed_level':level,'stat_type':item['stat_type'],
                        'calculation_status':item['calculation_status']})
    return {'known_attributes':records,'typed_modifiers':typed,
            'proposal_ids':[pid for pid,_,_,_ in observations],
            'main_effect_raw':data.get('main_effect'),
            'source_frame':(data.get('source') or {}).get('frame'),
            'evidence_context':context,'recorded_at':recorded_at,
            'conflict':None}


def _reviewed_rank_rows(c,catalog_id,target_level,shiny_status):
    """Reuse only the same ordered row and official rank within one reviewed context.

    The source recording remains the observation. This does not claim that the
    target level was photographed or that later patches preserve the value.
    """
    if not c.execute("SELECT 1 FROM sqlite_master WHERE name='video_import_proposals'").fetchone():
        return None
    source_levels=set()
    for row in c.execute("SELECT data FROM video_import_proposals WHERE status!='dismissed'"):
        data=json.loads(row['data'])
        if (data.get('catalog_id')==catalog_id and
                data.get('shiny_status','unknown')==shiny_status and
                isinstance(data.get('level'),int) and data['level']!=target_level):
            source_levels.add(data['level'])
    observed=[]
    for level in sorted(source_levels):
        item=_reviewed_exact_rows(c,catalog_id,level,shiny_status)
        if item:
            if item.get('conflict'):
                return {'conflict':item['conflict'],'proposal_ids':item.get('proposal_ids',[])}
            observed.append(item)
    if not observed:return None
    contexts={item['evidence_context'] for item in observed}
    if len(contexts)!=1:
        return {'conflict':'Reviewed rows come from different or unverified patch contexts; do not combine their ranks.',
                'proposal_ids':[pid for item in observed for pid in item['proposal_ids']]}
    ranks=catalog.DATA['official_rules']['mod_levels']['ordered_subattribute_tiers'][str(target_level)]
    rows=[];typed=[];conflicts=[]
    for index,rank in enumerate(ranks):
        candidates=[(item['known_attributes'][index],item['typed_modifiers'][index])
                    for item in observed
                    if index<len(item['known_attributes']) and
                    item['known_attributes'][index].get('tier')==rank and rank>0]
        if rank==0:
            rows.append({'name':f'Row {index+1}','tier':0,'value_percent':0,
                         'source_status':'inactive at this level by official ordered-rank table',
                         'inactive_by_rank':True})
            continue
        if not candidates:
            rows.append({'name':f'Row {index+1}','tier':rank,'value_percent':None,
                         'source_status':'This exact row and rank were not observed for this variant.'})
            typed.append({'row_index':index,'stat_type':'unparsed','value':None,
                          'raw_text':f'Row {index+1}, rank {rank}: numerical value not observed',
                          'confidence':'rank_not_observed','calculation_status':'unmodeled',
                          'tech_activation':'unknown','evidence':{'catalog_id':catalog_id,'rank':rank}})
            continue
        signatures={(str(row.get('raw_text') or '').strip().casefold(),row.get('stat_type'),row.get('unit'),row.get('direction'),
                     row.get('value_percent'),typed_row.get('value'))
                    for row,typed_row in candidates}
        if len(signatures)!=1:
            conflicts.append(f'Row {index+1} rank {rank} has conflicting reviewed observations.')
            rows.append({'name':f'Row {index+1}','tier':rank,'value_percent':None,
                         'source_status':'conflicting reviewed rank evidence','source_conflict':True})
            typed.append({'row_index':index,'stat_type':'unparsed','value':None,
                          'raw_text':f'Row {index+1}, rank {rank}: conflicting observations',
                          'confidence':'rank_conflict','calculation_status':'unmodeled',
                          'tech_activation':'unknown','evidence':{'catalog_id':catalog_id,'rank':rank}})
            continue
        row,source_typed=candidates[0]
        rows.append({**row,'target_level':target_level,
                     'source_status':f'Same ordered row and rank observed at Lv{row["observed_level"]} in a reviewed recording',
                     'rank_derived':True,'evidence_context':next(iter(contexts))})
        typed.append({**source_typed,'row_index':index,
                      'evidence':{**(source_typed.get('evidence') or {}),
                                  'catalog_id':catalog_id,'rank':rank,
                                  'observed_level':row['observed_level'],
                                  'target_level':target_level,'rank_derived':True},
                      'tech_activation':'unknown'})
    return {'known_attributes':rows,'typed_modifiers':typed,
            'proposal_ids':list(dict.fromkeys(pid for item in observed for pid in item['proposal_ids'])),
            'main_effect_raw':None,'source_frame':None,
            'evidence_context':next(iter(contexts)),
            'recorded_at':observed[0]['recorded_at'],
            'rank_conflicts':conflicts,'rank_derived':True,'conflict':None}


def profile(c,profile_id):
    if profile_id not in PROFILES:raise ValueError('Unknown Field Guide profile')
    rows=[dict(row) for row in c.execute(
        'SELECT * FROM field_guide_levels WHERE profile_id=? ORDER BY catalog_id',(profile_id,))]
    return {'id':profile_id,'name':PROFILES[profile_id],
            'levels':{row['catalog_id']:row for row in rows},
            'default_unrecorded_level':0,
            'meaning':'A zero or absent level means not unlocked in this profile. Existing legacy inventory is separate.',
            'reviewed_batches':profile_batches(c,profile_id),
            'inventory_unchanged':True}


def _batch_events(c,profile_id,batch_id):
    if profile_id not in PROFILES or not isinstance(batch_id,str) or not batch_id:
        raise ValueError('Choose an exact profile and reviewed batch')
    result=[]
    for row in c.execute("SELECT * FROM field_guide_level_events WHERE profile_id=? AND source_kind='reviewed_video' ORDER BY id",
                         (profile_id,)):
        next_row=json.loads(row['next'])
        try:ref=json.loads(next_row.get('source_ref') or '{}')
        except (TypeError,ValueError):continue
        if ref.get('batch_id')==batch_id:result.append((dict(row),next_row,ref))
    return result


def profile_batches(c,profile_id):
    """Show only reversible reviewed saves; source proposals remain untouched."""
    if profile_id not in PROFILES:raise ValueError('Unknown Field Guide profile')
    ids=[]
    for row in c.execute("SELECT next FROM field_guide_level_events WHERE profile_id=? AND source_kind='reviewed_video' ORDER BY id DESC",
                         (profile_id,)):
        try:ref=json.loads(json.loads(row['next']).get('source_ref') or '{}')
        except (TypeError,ValueError):continue
        batch_id=ref.get('batch_id')
        if batch_id and batch_id not in ids:ids.append(batch_id)
    batches=[]
    for batch_id in ids:
        events=_batch_events(c,profile_id,batch_id)
        unchanged=all(get(c,profile_id,event['catalog_id'])==next_row
                      for event,next_row,_ in events)
        batches.append({'batch_id':batch_id,'run_id':events[0][2].get('run_id'),
                        'saved_count':len(events),'undo_available':bool(events and unchanged),
                        'reason':None if unchanged else 'Profile changed since this batch; Undo is blocked.'})
    return batches


def preview(c,profile_id,catalog_id,level,shiny_status='unknown',source_kind='manual'):
    entry=_identity(profile_id,catalog_id)
    _level(level,shiny_status)
    current=get(c,profile_id,catalog_id)
    previous=current['level'] if current else 0
    decision=('record_locked' if level==0 else 'new_unlock' if previous==0 else
              'same_level_observation' if level==previous else
              'higher_level_progression' if level>previous else 'lower_level_correction')
    if level==previous==17 and current and current['shiny_status']!=shiny_status:
        decision='shiny_identity_needs_review'
    resolved=catalog.resolve(catalog_id,level,system=SYSTEM,shiny=shiny_status=='shiny') if level else None
    rows=(resolved or {}).get('known_attributes') or []
    observed=(_reviewed_exact_rows(c,catalog_id,level,shiny_status) or
              _reviewed_rank_rows(c,catalog_id,level,shiny_status)) if level else None
    unknowns=list((resolved or {}).get('unknowns') or [])
    typed_observed=[]
    if observed:
        if observed.get('conflict'):
            unknowns.append(observed['conflict'])
            rows=[{**row,'value_percent':None,'source_conflict':True} for row in rows]
        else:
            rows=[dict(row) for row in observed['known_attributes']]
            typed_observed=[dict(row) for row in observed['typed_modifiers']]
            if observed.get('rank_derived'):
                row_notes=[]
                for index,row in enumerate(rows,1):
                    if row.get('inactive_by_rank'):
                        row_notes.append(f'row {index} inactive at this level')
                    elif row.get('rank_derived'):
                        row_notes.append(f'row {index} same rank as reviewed Lv{row["observed_level"]}')
                    else:
                        row_notes.append(f'row {index} rank {row.get("tier")} value unknown')
                unknowns.insert(0,'Rank-by-row evidence: '+('; '.join(row_notes))+'. These are dated observations, not a screenshot of this level; verify the current patch before treating values as current.')
                unknowns.extend(observed.get('rank_conflicts') or [])
            static=(resolved or {}).get('known_attributes') or []
            for typed in typed_observed:
                index=typed.get('row_index')
                if not isinstance(index,int) or index>=len(static) or index>=len(rows):continue
                item=rows[index]
                known=static[index].get('value_percent');seen=item.get('value_percent')
                if known is not None and seen is not None and not isclose(known,seen,rel_tol=0,abs_tol=1e-8):
                    unknowns.append(f'Catalog and video values conflict in row {index+1}; neither is used.')
                    item['value_percent']=None;item['source_conflict']=True
                    typed['value']=None;typed['calculation_status']='unmodeled'
    coverage=('complete' if rows and all(row.get('value_percent') is not None for row in rows)
              else 'partial' if rows else 'none')
    return {'profile_id':profile_id,'catalog_id':catalog_id,'name':entry['name'],
            'slot':entry['slot'],'variant':entry['variant'],'system':SYSTEM,
            'current_level':previous,'proposed_level':level,'shiny_status':shiny_status,
            'rarity_from_official_level':rarity_for_level(level),
            'decision':decision,'source_kind':source_kind,
            'level_profile':(resolved or {}).get('level_profile'),
            'known_attributes':rows,
            'numeric_coverage':coverage,
            'unknowns':unknowns,
            'reviewed_exact_rows':typed_observed,
            'reviewed_proposal_ids':observed.get('proposal_ids') if observed else [],
            'reviewed_main_effect_raw':observed.get('main_effect_raw') if observed else None,
            'reviewed_source_frame':observed.get('source_frame') if observed else None,
            'rank_derived':bool(observed and observed.get('rank_derived')),
            'evidence_context':observed.get('evidence_context') if observed else None,
            'evidence_recorded_at':observed.get('recorded_at') if observed else None,
            'unresolved_attribute_count':sum(row.get('value_percent') is None for row in rows),
            'tech_activation':'unknown',
            'calculation_status':'not activated; save collection progress without inventing damage',
            'inventory_unchanged':True}


def set_manual(c,profile_id,catalog_id,level,shiny_status='unknown'):
    result=preview(c,profile_id,catalog_id,level,shiny_status,'manual')
    current=get(c,profile_id,catalog_id)
    stamp=now()
    next_row={'profile_id':profile_id,'catalog_id':catalog_id,'level':level,
              'shiny_status':shiny_status,'source_kind':'manual','source_ref':None,'updated':stamp}
    c.execute('REPLACE INTO field_guide_levels VALUES(?,?,?,?,?,?,?)',
              (profile_id,catalog_id,level,shiny_status,'manual',None,stamp))
    c.execute('INSERT INTO field_guide_level_events(profile_id,catalog_id,prior,next,source_kind,created) VALUES(?,?,?,?,?,?)',
              (profile_id,catalog_id,json.dumps(current) if current else None,json.dumps(next_row),'manual',stamp))
    return {**result,'saved':True,'source_kind':'manual','profile_level_only':True}


def preview_video(c,profile_id,proposal):
    """Upload and manual entry share the same identity/level reconciliation.

    A video hover is an observation. Unknown source system or Shiny identity
    remains a hold; this function has no mutation or commit side effect.
    """
    data=proposal.get('data') or proposal
    source=data.get('source') or {}
    system=source_system(data)
    if system!=SYSTEM:
        return {'decision':'source_system_needs_review','source_system':system or 'unknown',
                'catalog_id':data.get('catalog_id'),'inventory_unchanged':True}
    if data.get('ownership')=='locked':
        return {'decision':'locked_preview_not_owned','catalog_id':data.get('catalog_id'),
                'inventory_unchanged':True}
    level=data.get('level')
    if isinstance(level,bool) or not isinstance(level,int) or not 1<=level<=17:
        return {'decision':'level_needs_review','catalog_id':data.get('catalog_id'),
                'inventory_unchanged':True}
    shiny=data.get('shiny_status','unknown')
    result=preview(c,profile_id,data.get('catalog_id'),level,shiny,'video_observation')
    if result['decision']=='lower_level_correction':
        result['decision']='stale_lower_level_observation'
    result['source_frame']=source.get('frame')
    result['source_timestamp']=source.get('timestamp')
    result['requires_source_review']=True
    return result


def plan_video_run(c,profile_id,run_id):
    """Read-only progression plan from reviewed observations, not copies."""
    if profile_id not in PROFILES:raise ValueError('Unknown Field Guide profile')
    run=c.execute('SELECT fingerprint FROM video_import_runs WHERE id=?',(run_id,)).fetchone()
    if not run:raise ValueError('Import run not found')
    rows=list(c.execute('SELECT id,data,status FROM video_import_proposals WHERE run_id=? ORDER BY rowid',(run_id,)))
    groups=defaultdict(list);held=[];source_snapshot=[];verified_proofs={};source_hashes=[]
    database_file=c.execute('PRAGMA database_list').fetchone()[2]
    data_root=Path(database_file).parent
    frame_root=(data_root/'media'/c.execute('SELECT media_id FROM video_import_runs WHERE id=?',(run_id,)).fetchone()[0]
                /'video-review'/run_id).resolve()
    for row in rows:
        data=json.loads(row['data']);source_snapshot.append((row['id'],row['status'],row['data']))
        relative=(data.get('source') or {}).get('frame')
        frame=(data_root/relative).resolve() if isinstance(relative,str) else data_root
        frame_hash=(hashlib.sha256(frame.read_bytes()).hexdigest()
                    if frame.is_relative_to(frame_root) and frame.is_file() else None)
        source_hashes.append((row['id'],relative,frame_hash))
        if row['status']=='dismissed' or data.get('ownership')!='unlocked':continue
        audit=data.get('source_audit') or {}
        reviewed=audit.get('system_review') or {}
        proofs=reviewed.get('source_proof') or []
        proof_key=json.dumps(proofs,sort_keys=True)
        if proof_key not in verified_proofs:
            valid=bool(proofs) and len(proofs)==len(rows)
            for proof in proofs:
                proof_relative=proof.get('frame') if isinstance(proof,dict) else None
                path=(data_root/proof_relative).resolve() if isinstance(proof_relative,str) else data_root
                if not path.is_relative_to(frame_root) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=proof.get('sha256'):
                    valid=False;break
            verified_proofs[proof_key]=valid
        own_proof=next((p for p in proofs if p.get('proposal_id')==row['id']),None)
        own_frame_valid=bool(own_proof and own_proof.get('frame')==relative
                             and own_proof.get('sha256')==frame_hash)
        checked=(str(audit.get('status') or '').startswith('source_text_and_numbers_checked')
                 and (audit.get('main_effect') or {}).get('source_text')==data.get('main_effect')
                 and [x.get('source_text') for x in audit.get('attribute_rows') or []]==(data.get('attribute_rows') or []))
        reason=None
        if (source_system(data)!=SYSTEM or reviewed.get('run_fingerprint')!=run['fingerprint']
                or not verified_proofs[proof_key] or not own_frame_valid):
            reason='source system context needs review'
        elif not checked:reason='tooltip rows need source review'
        elif data.get('shiny_status','unknown')=='shiny' and data.get('level')!=17:
            reason='Shiny identity conflicts with level'
        else:
            try:
                entry=_identity(profile_id,data.get('catalog_id'))
                _level(data.get('level'),data.get('shiny_status','unknown'))
                if entry['slot']!=data.get('slot') or entry['variant']!=data.get('variant'):
                    reason='catalog slot or suffix conflicts with reviewed source'
            except (ValueError,KeyError) as error:reason=str(error)
        if reason:held.append({'proposal_id':row['id'],'catalog_id':data.get('catalog_id'),'reason':reason})
        else:groups[data['catalog_id']].append((row['id'],data))
    entries=[]
    for catalog_id,observations in sorted(groups.items()):
        highest=max(data['level'] for _,data in observations)
        top=[(pid,data) for pid,data in observations if data['level']==highest]
        readings={(tuple(data.get('attribute_rows') or []),data.get('main_effect'),data.get('shiny_status','unknown')) for _,data in top}
        if len(readings)>1:
            held.extend({'proposal_id':pid,'catalog_id':catalog_id,'reason':'conflicting highest-level tooltip or Shiny readings'} for pid,_ in top)
            continue
        shiny=top[0][1].get('shiny_status','unknown')
        prior=get(c,profile_id,catalog_id)
        previous=prior['level'] if prior else 0
        if prior and highest==previous and prior['shiny_status']!=shiny and 'unknown' not in (prior['shiny_status'],shiny):
            held.extend({'proposal_id':pid,'catalog_id':catalog_id,'reason':'same-level Shiny identity conflict'} for pid,_ in top)
            continue
        decision=('new_unlock' if previous==0 else 'higher_level_progression' if highest>previous
                  else 'same_level_observation' if highest==previous else 'stale_lower_level_observation')
        preview_result=preview(c,profile_id,catalog_id,highest,shiny,'video_observation')
        entries.append({'catalog_id':catalog_id,'proposal_ids':[pid for pid,_ in observations],
                        'selected_proposal_ids':[pid for pid,_ in top],
                        'source_levels':sorted({data['level'] for _,data in observations}),
                        'level':highest,'previous_level':previous,'shiny_status':shiny,
                        'decision':decision,'known_attributes':preview_result['known_attributes'],
                        'numeric_coverage':preview_result['numeric_coverage'],
                        'tech_activation':'unknown'})
    profile_snapshot=[dict(row) for row in c.execute('SELECT * FROM field_guide_levels WHERE profile_id=? ORDER BY catalog_id',(profile_id,))]
    token=hashlib.sha256(json.dumps({'run_id':run_id,'fingerprint':run['fingerprint'],
                     'profile_id':profile_id,'source':source_snapshot,
                     'source_hashes':source_hashes,'profile':profile_snapshot},sort_keys=True).encode()).hexdigest()
    return {'run_id':run_id,'profile_id':profile_id,'entries':entries,'held':held,
            'source_observations':len(rows),'eligible_progressions':sum(e['decision'] in ('new_unlock','higher_level_progression') for e in entries),
            'plan_token':token,'inventory_unchanged':True,'tech_activation':'unknown'}


def save_video_run(c,profile_id,run_id,plan_token,confirm=False):
    """Explicit profile-only save; caller provides a fresh reviewed plan token."""
    if not confirm:raise ValueError('Confirm this reviewed profile progression explicitly')
    c.execute('BEGIN IMMEDIATE')
    plan=plan_video_run(c,profile_id,run_id)
    if plan_token!=plan['plan_token']:raise ValueError('Review plan changed; reopen before saving')
    if plan['held']:raise ValueError('Some source observations still need review; no levels saved')
    stamp=now();saved=[];batch_id=uuid.uuid4().hex
    for item in plan['entries']:
        if item['decision'] not in ('new_unlock','higher_level_progression'):continue
        catalog_id=item['catalog_id'];prior=get(c,profile_id,catalog_id)
        ref=json.dumps({'run_id':run_id,'batch_id':batch_id,
                        'proposal_ids':item['proposal_ids'],
                        'selected_proposal_ids':item['selected_proposal_ids']},sort_keys=True)
        next_row={'profile_id':profile_id,'catalog_id':catalog_id,'level':item['level'],
                  'shiny_status':item['shiny_status'],'source_kind':'reviewed_video',
                  'source_ref':ref,'updated':stamp}
        c.execute('REPLACE INTO field_guide_levels VALUES(?,?,?,?,?,?,?)',
                  (profile_id,catalog_id,item['level'],item['shiny_status'],'reviewed_video',ref,stamp))
        c.execute('INSERT INTO field_guide_level_events(profile_id,catalog_id,prior,next,source_kind,created) VALUES(?,?,?,?,?,?)',
                  (profile_id,catalog_id,json.dumps(prior) if prior else None,json.dumps(next_row),'reviewed_video',stamp))
        saved.append(catalog_id)
    c.commit()
    return {'run_id':run_id,'profile_id':profile_id,'batch_id':batch_id if saved else None,
            'saved_catalog_ids':saved,
            'saved_count':len(saved),'inventory_unchanged':True,'tech_activation':'unknown'}


def undo_video_run(c,profile_id,batch_id,confirm=False):
    """Atomically restore only an untouched reviewed profile batch."""
    if not confirm:raise ValueError('Confirm profile batch Undo explicitly')
    c.execute('BEGIN IMMEDIATE')
    events=_batch_events(c,profile_id,batch_id)
    if not events:raise ValueError('Reviewed profile batch not found')
    for event,next_row,_ in events:
        if get(c,profile_id,event['catalog_id'])!=next_row:
            raise ValueError('Profile changed after this batch; Undo is blocked')
    stamp=now()
    for event,next_row,_ in events:
        prior=json.loads(event['prior']) if event['prior'] else None
        if prior is None:
            c.execute('DELETE FROM field_guide_levels WHERE profile_id=? AND catalog_id=?',
                      (profile_id,event['catalog_id']))
        else:
            c.execute('REPLACE INTO field_guide_levels VALUES(?,?,?,?,?,?,?)',
                      tuple(prior[key] for key in ('profile_id','catalog_id','level','shiny_status',
                                                    'source_kind','source_ref','updated')))
        c.execute('INSERT INTO field_guide_level_events(profile_id,catalog_id,prior,next,source_kind,created) VALUES(?,?,?,?,?,?)',
                  (profile_id,event['catalog_id'],json.dumps(next_row),
                   json.dumps(prior if prior is not None else {'absent':True,'batch_id':batch_id}),
                   'undo_reviewed_video',stamp))
    c.commit()
    return {'profile_id':profile_id,'batch_id':batch_id,'restored_count':len(events),
            'raw_source_preserved':True,'inventory_unchanged':True,'builds_unchanged':True}


def calculation_preview(c,profile_id,catalog_id,baseline=None):
    """Read-only, profile-scoped rows; no implicit Tech or bucket activation."""
    recorded=get(c,profile_id,catalog_id)
    if not recorded or recorded['level']==0:
        return {'profile_id':profile_id,'catalog_id':catalog_id,'owned_in_profile':False,
                'rows':[],'reason':'This exact variant has no unlocked level in this profile.',
                'inventory_unchanged':True}
    detail=preview(c,profile_id,catalog_id,recorded['level'],recorded['shiny_status'],recorded['source_kind'])
    parsed=list(detail['reviewed_exact_rows'])
    for index,row in enumerate([] if parsed else detail['known_attributes']):
        magnitude=row.get('value_percent');name=row['name']
        if magnitude is None or row.get('direction') not in (None,'increase'):
            parsed.append({'row_index':index,'stat_type':'unparsed','value':None,
                           'raw_text':name,'confidence':'catalog_value_unknown',
                           'tech_activation':'unknown','calculation_status':'unmodeled',
                           'evidence':{'catalog_id':catalog_id,'rank':row.get('tier')}})
            continue
        text=f'{name} + {magnitude}%'
        source={'frame':row.get('source'),'observed_level':row.get('observed_level')}
        checked=str(row.get('source_status') or '').startswith('visually checked')
        audit={'status':'source_text_and_numbers_checked' if checked else 'catalog_candidate',
               'attribute_rows':[{'source_text':text}]}
        item=mod_rolls.parse_rows([text],source=source,source_audit=audit)[0]
        item['row_index']=index
        item['evidence'].update({'catalog_id':catalog_id,'rank':row.get('tier'),
                                 'source_status':row.get('source_status')})
        parsed.append(item)
    base=baseline if baseline is not None else {'base_origin':'unknown'}
    result=mod_rolls.scenario(parsed,base)
    return {'profile_id':profile_id,'catalog_id':catalog_id,'owned_in_profile':True,
            'level':recorded['level'],'source_kind':recorded['source_kind'],
            'source_ref':recorded['source_ref'],'shiny_status':recorded['shiny_status'],
            'known_attributes':detail['known_attributes'],'rows':parsed,
            'reviewed_main_effect_raw':detail['reviewed_main_effect_raw'],
            'reviewed_source_frame':detail['reviewed_source_frame'],
            'scenario':result,'tech_activation':'unknown',
            'unknowns':detail['unknowns'],
            'warning':'This is a profile-specific isolated preview. Unknown Tech rows are excluded by default; unsupported effects and damage buckets remain unresolved.',
            'inventory_unchanged':True}


def build_calculation_preview(c,profile_id,slots,baseline=None,active_weapon_slot='primary'):
    """Read-only selected-build roll path; never borrow another profile or Backpack."""
    if profile_id not in PROFILES:raise ValueError('Unknown Field Guide profile')
    if not isinstance(slots,dict):raise ValueError('Saved build slots are required')
    if active_weapon_slot not in ('primary','secondary','melee'):
        raise ValueError('Choose an active weapon slot')
    selected=[];rows=[];issues=[];seen=set()
    for slot,choice in slots.items():
        if not isinstance(choice,dict) or not choice.get('mod_id'):continue
        if slot in ('primary','secondary','melee') and slot!=active_weapon_slot:
            selected.append({'slot':slot,'catalog_id':choice['mod_id'],'status':'inactive_weapon'})
            continue
        identity=choice['mod_id'];level=choice.get('mod_level')
        if identity in seen:
            issues.append({'slot':slot,'catalog_id':identity,'reason':'same Field Guide variant selected in multiple active slots'})
            continue
        seen.add(identity)
        if choice.get('mod_inventory_id'):
            issues.append({'slot':slot,'catalog_id':identity,'reason':'saved selection is linked to a physical inventory instance; profile substitution is not automatic'})
            continue
        try:item=calculation_preview(c,profile_id,identity)
        except ValueError as error:
            issues.append({'slot':slot,'catalog_id':identity,'reason':str(error)})
            continue
        if not item['owned_in_profile']:
            issues.append({'slot':slot,'catalog_id':identity,'reason':'this profile has no unlocked level for the selected mod'})
            continue
        if level!=item['level']:
            issues.append({'slot':slot,'catalog_id':identity,'reason':'saved mod level differs from this profile; review the selection before calculation',
                           'selected_level':level,'profile_level':item['level']})
            continue
        if not item['rows']:
            issues.append({'slot':slot,'catalog_id':identity,
                           'reason':'selected Field Guide mod has no source-checked numerical rows at this exact level; its effects are unknown'})
            selected.append({'slot':slot,'catalog_id':identity,'level':item['level'],
                             'status':'missing_numeric_evidence','row_count':0,
                             'source_kind':item['source_kind']})
            continue
        selected.append({'slot':slot,'catalog_id':identity,'level':item['level'],
                         'status':'source_backed_rows_with_unknown_tech',
                         'row_count':len(item['rows']),'source_kind':item['source_kind']})
        rows.extend({**row,'selected_slot':slot} for row in item['rows'])
    scenario=mod_rolls.scenario(rows,baseline if baseline is not None else {'base_origin':'unknown'})
    incomplete=[row for row in rows if row.get('calculation_status')!='assumption_scenario']
    return {'profile_id':profile_id,'selected':selected,'issues':issues,'rows':rows,
            'scenario':scenario,'roll_coverage_complete':bool(rows) and not issues and not incomplete and not scenario['modifiers']['tech_gated_rows'],
            'full_build_complete':False,
            'warning':'Selected Field Guide rows give only an isolated partial sensitivity. Tech, main effects, set bonuses and damage bucket interactions are not silently assumed.',
            'inventory_unchanged':True}
