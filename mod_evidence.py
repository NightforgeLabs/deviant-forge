"""Explicit, source-checked evidence attachment for an already owned mod.

Preview is read-only. Apply and Undo use scoped inventory snapshots and never
change video proposals, ownership, saved builds, or Tech activation.
"""
from __future__ import annotations
import hashlib, json, sqlite3
from pathlib import Path
from PIL import Image
import catalog, mod_rolls, video_review, field_guide_profiles


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), default=str)


def _digest(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _row_digest(row):
    data=dict(row)
    stats=json.loads(data['stats'] or '{}')
    stats.pop('evidence_attachments',None)
    data['stats']=stats
    return _digest(data)


def _source_path(root, relative):
    if not isinstance(relative,str) or not relative:
        raise ValueError('Full source frame and context are required')
    base=Path(root).resolve()
    target=(base/relative).resolve()
    if not target.is_relative_to(base) or not target.is_file():
        raise ValueError('Source frame or context is missing or outside local evidence storage')
    try:
        with Image.open(target) as image:image.verify()
    except (OSError,ValueError) as error:
        raise ValueError('Source frame or context image is unreadable') from error
    return relative


def _checked(c, root, proposal_id, inventory_id):
    if not isinstance(proposal_id,str) or not isinstance(inventory_id,str):
        raise ValueError('Choose one reviewed proposal and one owned mod instance')
    proposal=c.execute('SELECT * FROM video_import_proposals WHERE id=?',(proposal_id,)).fetchone()
    item=c.execute("SELECT * FROM inventory WHERE id=? AND kind='mod_unlock' AND archived=0",(inventory_id,)).fetchone()
    if not proposal or proposal['status'] not in ('pending','reviewed'):
        raise ValueError('A current uncommitted video proposal is required')
    if not item:raise ValueError('Existing owned mod instance not found')
    # Archived inventory still owns its evidence history. Reusing a proposal
    # would make restoration produce two owners of the same source record.
    for other in c.execute("SELECT id,stats FROM inventory WHERE kind='mod_unlock' AND id<>?",(inventory_id,)):
        if any(x.get('proposal_id')==proposal_id for x in (json.loads(other['stats'] or '{}').get('evidence_attachments') or [])):
            raise ValueError('This exact source proposal is already linked to another owned mod instance')
    data=json.loads(proposal['data'])
    source_system=field_guide_profiles.source_system(data)
    item_stats=json.loads(item['stats'] or '{}')
    item_effects=json.loads(item['effects'] or '{}')
    item_system=item_stats.get('mod_system') or item_effects.get('mod_system')
    if not source_system or not item_system or source_system!=item_system:
        raise ValueError('Source and owned mod systems must be explicitly reviewed and match before attaching evidence')
    if data.get('ownership')!='unlocked':raise ValueError('Locked or uncertain evidence cannot be attached to owned gear')
    if not {'Equip action','visible level and suffix'}<=set(data.get('ownership_cues') or []):
        raise ValueError('Video does not establish this exact owned mod variant and level')
    entry=catalog.ENTRIES.get(data.get('catalog_id'))
    effects=json.loads(item['effects'] or '{}')
    if (not entry or entry.get('kind')!='mod' or entry.get('slot')!=data.get('slot')
        or entry.get('variant')!=data.get('variant')
        or effects.get('catalog_id')!=data.get('catalog_id') or item['slot']!=data.get('slot')
        or item['variant']!=data.get('variant') or item['level']!=data.get('level')):
        raise ValueError('Owned identity, slot, suffix and level must exactly match the source tooltip')
    rows=data.get('attribute_rows') or []
    audit=data.get('source_audit') or {}
    edits=set((data.get('review_corrections') or {}).get('edited_fields') or [])
    if edits & {'catalog_id','level','rarity'}:
        reviewed_at=(data.get('review_corrections') or {}).get('reviewed_at') or ''
        if not audit.get('checked_at') or audit['checked_at']<=reviewed_at:
            raise ValueError('Corrected identity or level needs a new source-frame check')
    if (not rows or not str(audit.get('status') or '').startswith('source_text_and_numbers_checked')
        or (audit.get('main_effect') or {}).get('source_text')!=data.get('main_effect')
        or [x.get('source_text') for x in audit.get('attribute_rows') or []]!=rows):
        raise ValueError('All attached text and numbers must match the checked source frame')
    source=data.get('source') or {}
    for key in ('frame','context','tooltip'):
        _source_path(root,source.get(key))
    typed=mod_rolls.proposal_modifiers(data,proposal_id)
    if len(typed)!=len(rows):raise ValueError('Parsed row count differs from source rows')
    stats=json.loads(item['stats'] or '{}')
    attachments=stats.get('evidence_attachments') or []
    if any(x.get('proposal_id')==proposal_id for x in attachments):
        return proposal,item,data,stats,typed,True
    return proposal,item,data,stats,typed,False


def _same_attachment(stats, data, proposal_id):
    return any(x.get('proposal_id')==proposal_id and x.get('source_audit')==data.get('source_audit')
               and x.get('source')==data.get('source') for x in stats.get('evidence_attachments') or [])


def preview(db, root, proposal_id, inventory_id):
    with video_review.connect(db) as c:
        proposal,item,data,stats,typed,attached=_checked(c,root,proposal_id,inventory_id)
        token=_digest({'proposal_id':proposal_id,'proposal_data':proposal['data'],
                       'proposal_status':proposal['status'],'item':dict(item)})
    order_conflict=mod_rolls.observed_row_order_conflict(stats)
    before=mod_rolls.aggregate([] if order_conflict else stats.get('typed_modifiers') or [],tech_policy='assume_active')
    after=mod_rolls.aggregate([] if order_conflict else typed,tech_policy='assume_active')
    gated=mod_rolls.aggregate([] if order_conflict else typed)
    replacing=bool(stats.get('typed_modifiers') or stats.get('observed_attribute_lines')) and not attached
    observed_tooltip=stats.get('observed_tooltip') or {}
    disagreement=({'saved_rows':list(stats['observed_attribute_lines']),
                   'tooltip_rows':list(observed_tooltip['attribute_lines']),
                   'saved_source':item['source_observation'],
                   'tooltip_source':observed_tooltip.get('source_ref')}
                  if order_conflict else None)
    return {'proposal_id':proposal_id,'inventory_id':inventory_id,'token':token,'already_attached':attached,
            'replacing_existing':replacing,'row_order_discrepancy':order_conflict,
            'source_disagreement':disagreement,
            'identity':{'catalog_id':data['catalog_id'],'name':data.get('name'),'slot':data['slot'],
                        'variant':data['variant'],'level':data['level'],'rarity':data.get('rarity')},
            'source':data['source'],'main_effect':data['main_effect'],
            'before_rows':stats.get('observed_attribute_lines') or [],'after_rows':typed,
            'before_assumed_percent_by_type':before['percent_by_type'],
            'after_assumed_percent_by_type':None if order_conflict else after['percent_by_type'],
            'default_tech_gated_count':len(gated['tech_gated_rows']),
            'unmodeled_count':len(after['unmodeled_rows']),
            'warning':('The saved observation and tooltip disagree in row value, count, or order; Apply is blocked until both sources are reconciled. ' if order_conflict else '')+('Existing roll evidence will be replaced only after explicit confirmation; its prior values remain in the backup and Undo. ' if replacing else '')+'Review-only until Apply. Unknown Tech rows stay inactive by default. Assumed percentages are not verified total DPS. Saved builds and ownership do not change.'}


def apply(db, root, proposal_id, inventory_id, token, confirm=False, replace_existing=False):
    if confirm is not True or not isinstance(token,str) or len(token)!=64:
        raise ValueError('Review the preview and explicitly Apply its current token')
    with video_review.connect(db) as c:
        proposal,item,data,stats,typed,attached=_checked(c,root,proposal_id,inventory_id)
        if mod_rolls.observed_row_order_conflict(stats):
            raise ValueError('Recorded sources disagree in row value, count, or order; reconcile both sources before Apply')
        if attached:
            if _same_attachment(stats,data,proposal_id):
                return {'status':'already_attached','inventory_id':inventory_id,'backup':None}
            raise ValueError('Attached source changed; review before attempting another link')
        if (stats.get('typed_modifiers') or stats.get('observed_attribute_lines')) and replace_existing is not True:
            raise ValueError('Explicitly confirm replacement of existing roll evidence')
        current=_digest({'proposal_id':proposal_id,'proposal_data':proposal['data'],
                         'proposal_status':proposal['status'],'item':dict(item)})
        if current!=token:raise ValueError('Proposal or owned mod changed; reopen preview before Apply')
    backup=video_review._backup(db)
    with video_review.connect(db) as c:
        c.execute('BEGIN IMMEDIATE')
        proposal,item,data,stats,typed,attached=_checked(c,root,proposal_id,inventory_id)
        if mod_rolls.observed_row_order_conflict(stats):
            raise ValueError('Recorded sources disagree in row value, count, or order; reconcile both sources before Apply')
        if (stats.get('typed_modifiers') or stats.get('observed_attribute_lines')) and replace_existing is not True:
            raise ValueError('Explicitly confirm replacement of existing roll evidence')
        current=_digest({'proposal_id':proposal_id,'proposal_data':proposal['data'],
                         'proposal_status':proposal['status'],'item':dict(item)})
        if current!=token or attached:raise ValueError('Evidence changed; reopen preview before Apply')
        stamp=video_review.now()
        prior=dict(item)
        cur=c.execute("INSERT INTO undo(entity,entity_id,prior,created) VALUES('inventory',?,?,?)",
                      (inventory_id,json.dumps(prior),stamp))
        undo_id=cur.lastrowid
        stats['observed_attribute_lines']=list(data['attribute_rows'])
        stats['source_observed_typed_modifiers']=typed
        stats['typed_modifiers']=typed
        stats['original_observed_level']=data['level']
        stats['observed_mod_main_effect']=data['main_effect']
        stats['attribute_coverage']='source_text_checked_with_unknown_tech'
        stats['evidence_attachments']=(stats.get('evidence_attachments') or [])+[{
            'proposal_id':proposal_id,'undo_id':undo_id,'source':data['source'],
            'source_audit':data['source_audit'],'attached_at':stamp}]
        evidence=json.loads(item['evidence'] or '[]')
        evidence.append({'kind':'source_checked_video_rolls','proposal_id':proposal_id,
                         'source':data['source'],'level':data['level'],'variant':data['variant']})
        c.execute('UPDATE inventory SET stats=?,evidence=?,last_seen=? WHERE id=?',
                  (json.dumps(stats),json.dumps(evidence),stamp,inventory_id))
        updated=c.execute('SELECT * FROM inventory WHERE id=?',(inventory_id,)).fetchone()
        after_digest=_row_digest(updated)
        stats['evidence_attachments'][-1]['after_digest']=after_digest
        c.execute('UPDATE inventory SET stats=? WHERE id=?',(json.dumps(stats),inventory_id))
    return {'status':'attached','inventory_id':inventory_id,'proposal_id':proposal_id,
            'undo_id':undo_id,'backup':str(backup),'typed_rows':len(typed),
            'tech_unknown_rows':sum(x.get('tech_activation')=='unknown' for x in typed)}


def undo(db, inventory_id, undo_id):
    if isinstance(undo_id,bool) or not isinstance(undo_id,int):
        raise ValueError('Choose an evidence attachment to undo')
    with video_review.connect(db) as c:
        item=c.execute('SELECT * FROM inventory WHERE id=?',(inventory_id,)).fetchone()
        log=c.execute("SELECT * FROM undo WHERE id=? AND entity='inventory' AND entity_id=?",(undo_id,inventory_id)).fetchone()
        if not item or not log:raise ValueError('Attachment undo record not found')
        attachments=(json.loads(item['stats'] or '{}').get('evidence_attachments') or [])
        if not attachments or attachments[-1].get('undo_id')!=undo_id or _row_digest(item)!=attachments[-1].get('after_digest'):
            raise ValueError('Owned instance changed since attachment; preserve newer work and restore from backup if needed')
        prior=json.loads(log['prior'])
        if not isinstance(prior,dict) or prior.get('id')!=inventory_id:raise ValueError('Invalid evidence rollback snapshot')
    backup=video_review._backup(db)
    with video_review.connect(db) as c:
        c.execute('BEGIN IMMEDIATE')
        item=c.execute('SELECT * FROM inventory WHERE id=?',(inventory_id,)).fetchone()
        log=c.execute("SELECT * FROM undo WHERE id=? AND entity='inventory' AND entity_id=?",(undo_id,inventory_id)).fetchone()
        if not item or not log:raise ValueError('Attachment changed before Undo')
        attachments=(json.loads(item['stats'] or '{}').get('evidence_attachments') or [])
        if not attachments or attachments[-1].get('undo_id')!=undo_id or _row_digest(item)!=attachments[-1].get('after_digest'):
            raise ValueError('Owned instance changed before Undo; rollback refused')
        prior=json.loads(log['prior'])
        cols=[key for key in prior if key!='id']
        c.execute('UPDATE inventory SET '+','.join(key+'=?' for key in cols)+' WHERE id=?',
                  [prior[key] for key in cols]+[inventory_id])
        c.execute('DELETE FROM undo WHERE id=?',(undo_id,))
    return {'status':'undone','inventory_id':inventory_id,'backup':str(backup)}
