#!/usr/bin/env python3
import argparse, base64, io, json, math, os, re, shutil, sqlite3, subprocess, threading, time, uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, unquote, parse_qs
from PIL import Image
import engine
import build_source_rows
import outgoing
import planned_advisor
import native_shield_settlement
import native_player_hit_replay
import native_npc_hit_replay
import native_max_hp_ceiling
import native_survival_hp
import native_pvp_max_hp_adjust
import native_skill_power
import native_aug_surge_input
import native_dot_modifier_buckets
import native_lightning_dot_hit
import native_combat_labels
import native_sparkling_pumpkin
import native_mod_identity
import native_mod_frame_catalog
import native_mod_buff_review
import catalog_coverage_extended, catalog, recognition, mod_guidance, accessories, video_import, video_review, video_import_coverage, video_import_plan, mod_evidence, media_preview, aug_compare, mod_rolls, combat_formula, build_coverage, field_guide_profiles, core_effects, external_effects, planned_one_change

ROOT = Path(__file__).resolve().parent
try:
    APP_VERSION = (ROOT / "VERSION").read_text().strip()
except OSError:
    APP_VERSION = "unknown"
ARTWORK = json.loads((ROOT/"artwork_manifest.json").read_text()) if (ROOT/"artwork_manifest.json").exists() else {"records":{},"coverage":{}}
DATA = Path(os.environ.get("OH_ADVISOR_DATA",ROOT / "data")).resolve()
MEDIA = DATA / "media"
DB = DATA / "advisor.sqlite3"
KNOWLEDGE = json.loads((ROOT / "knowledge.json").read_text())
MAX_UPLOAD = 2 * 1024**3
MIME = {".mp4":"video/mp4",".mkv":"video/x-matroska",".png":"image/png",".jpg":"image/jpeg",".jpeg":"image/jpeg"}
jobs = {}; job_lock = threading.Lock()

def now(): return datetime.now(timezone.utc).isoformat(timespec="seconds")
@contextmanager
def connect():
    c=sqlite3.connect(DB,timeout=30)
    c.row_factory=sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()
def video_proposal_modifiers(proposal_ids):
    """Read-only selection of reviewed video rows; no ownership claim or commit."""
    if not isinstance(proposal_ids,list) or not 1<=len(proposal_ids)<=9 or len(set(proposal_ids))!=len(proposal_ids):
        raise ValueError('Choose one to nine distinct video mod proposals')
    result=[]
    with connect() as c:
        for proposal_id in proposal_ids:
            if not isinstance(proposal_id,str):raise ValueError('Invalid proposal ID')
            row=c.execute('SELECT data,status FROM video_import_proposals WHERE id=?',(proposal_id,)).fetchone()
            if not row or row['status']=='dismissed':raise ValueError('Video mod proposal unavailable')
            proposal=json.loads(row['data'])
            if proposal.get('ownership')!='unlocked':raise ValueError('Locked or uncertain mod cannot be treated as selected gear')
            result.extend(mod_rolls.proposal_modifiers(proposal,proposal_id))
    return result

def init():
    DATA.mkdir(parents=True,exist_ok=True); MEDIA.mkdir(exist_ok=True)
    with connect() as c:
        c.executescript("""CREATE TABLE IF NOT EXISTS schema_version(version INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS media(id TEXT PRIMARY KEY, name TEXT, type TEXT, size INTEGER, created TEXT, retained INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS observations(id TEXT PRIMARY KEY, media_id TEXT, image TEXT, timestamp REAL, ocr TEXT, fields TEXT, confidence REAL, state TEXT DEFAULT 'pending', created TEXT, FOREIGN KEY(media_id) REFERENCES media(id));
        CREATE TABLE IF NOT EXISTS inventory(id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL, slot TEXT, family TEXT, variant TEXT, level INTEGER, stars INTEGER, stats TEXT, effects TEXT, source_observation TEXT, evidence TEXT, confirmed TEXT, last_seen TEXT, archived INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS loadouts(id TEXT PRIMARY KEY, name TEXT NOT NULL, item_ids TEXT NOT NULL, notes TEXT, created TEXT, updated TEXT);
        CREATE TABLE IF NOT EXISTS planned_builds(id TEXT PRIMARY KEY, name TEXT NOT NULL, slots TEXT NOT NULL, notes TEXT, created TEXT, updated TEXT);
        CREATE TABLE IF NOT EXISTS catalog_ownership(catalog_id TEXT PRIMARY KEY, status TEXT NOT NULL, available_level INTEGER, updated TEXT NOT NULL, source TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS activities(id TEXT PRIMARY KEY, name TEXT NOT NULL, minutes REAL, source_url TEXT, notes TEXT, created TEXT);
        CREATE TABLE IF NOT EXISTS upgrades(id TEXT PRIMARY KEY, build_id TEXT NOT NULL, item_id TEXT NOT NULL, title TEXT NOT NULL, proposed_stats TEXT NOT NULL, cost TEXT, acquisition TEXT, source_url TEXT, status TEXT DEFAULT 'planned', created TEXT);
        CREATE TABLE IF NOT EXISTS measurements(id TEXT PRIMARY KEY, build_id TEXT NOT NULL, item_ids TEXT NOT NULL, target TEXT NOT NULL, buffs TEXT NOT NULL, conditions TEXT NOT NULL, scenario TEXT NOT NULL, normal_hit REAL NOT NULL, crit_hit_damage REAL, weakspot_hit_damage REAL, crit_weakspot_hit_damage REAL, rpm REAL, magazine INTEGER, reload_seconds REAL, source_observation TEXT, note TEXT, created TEXT, item_fingerprint TEXT);
        CREATE TABLE IF NOT EXISTS revisions(id TEXT PRIMARY KEY, title TEXT, source_url TEXT, affected TEXT, created TEXT);
        CREATE TABLE IF NOT EXISTS undo(id INTEGER PRIMARY KEY AUTOINCREMENT, entity TEXT, entity_id TEXT, prior TEXT, created TEXT);""")
        video_review.ensure_schema(c)
        field_guide_profiles.ensure_schema(c)
        if not c.execute("SELECT 1 FROM schema_version").fetchone(): c.execute("INSERT INTO schema_version VALUES(1)")
        version=c.execute("SELECT version FROM schema_version").fetchone()[0]
        if version<2:
            c.execute("ALTER TABLE activities ADD COLUMN target_id TEXT")
            c.execute("UPDATE schema_version SET version=2")
            version=2
        if version<3:c.execute("UPDATE schema_version SET version=3");version=3
        if version<4:
            columns={r[1] for r in c.execute("PRAGMA table_info(measurements)")}
            for name,kind in (("rpm","REAL"),("magazine","INTEGER"),("reload_seconds","REAL")):
                if name not in columns:c.execute(f"ALTER TABLE measurements ADD COLUMN {name} {kind}")
            c.execute("UPDATE schema_version SET version=4")
            version=4
        if version<5:
            columns={r[1] for r in c.execute("PRAGMA table_info(measurements)")}
            if "item_fingerprint" not in columns:c.execute("ALTER TABLE measurements ADD COLUMN item_fingerprint TEXT")
            c.execute("UPDATE schema_version SET version=5")
            version=5
        if version<6:c.execute("UPDATE schema_version SET version=6")

def rows(table):
    with connect() as c: return [dict(x) for x in c.execute(f"SELECT * FROM {table}")]
def unpack_item(r):
    r=dict(r)
    for k in ("stats","effects","evidence"):
        r[k]=json.loads(r[k] or ("[]" if k=="evidence" else "{}"))
    catalog_id=r['effects'].get('catalog_id')
    if r.get('kind')=='mod_unlock' and catalog_id in catalog.ENTRIES:
        source_direction_ambiguous=(r['stats'].get('attribute_coverage')=='source_direction_ambiguous' or
            bool((r['stats'].get('video_import') or {}).get('semantic_uncertainties')))
        if r['stats'].get('attribute_coverage')=='unverified_ocr':
            r['stats']['observed_attribute_ocr_status']='unverified_ocr'
            del r['stats']['attribute_coverage']
        current=catalog_item_data(catalog_id,r.get('level'))
        r['stats']={**r['stats'],**{k:v for k,v in current['stats'].items() if k.startswith('catalog_') or k=='attribute_coverage'}}
        if source_direction_ambiguous:
            r['stats']['attribute_coverage']='source_direction_ambiguous'
        r['effects']={**r['effects'],'catalog_unknowns':current['effects']['catalog_unknowns'],'catalog_effects':current['effects']['catalog_effects']}
    return r
def inventory(): return [unpack_item(r) for r in rows("inventory") if not r["archived"]]
def personal_gear():
    """Explicit inventory entries, never planned-build or catalog ownership guesses."""
    result=[]
    for item in inventory():
        identity=item.get('effects',{}).get('catalog_id')
        entry=catalog.ENTRIES.get(identity)
        if not entry or entry['kind'] not in ('weapon','armor'):continue
        saved=item.get('stats') or {}
        result.append({'id':item['id'],'catalog_id':identity,'name':item['name'],
            'slot':item.get('slot'),'stars':item.get('stars'),
            'tier':saved.get('craft_tier'),'calibration_blueprint':saved.get('calibration_blueprint'),
            'calibration_bonus':saved.get('calibration_bonus'),
            'calibration_profile':saved.get('calibration_profile'),
            'calibration_upgrade_level':saved.get('calibration_upgrade_level'),
            'accessories':saved.get('accessories') or {},
            'weapon_stats':saved.get('weapon_stats') if saved.get('weapon_stats_context')==gear_measurement_context(identity,item.get('stars'),saved) else None,
            'source_observation':item.get('source_observation')})
    return result

def gear_measurement_context(identity,stars,stats):
    """A tooltip measurement belongs to one exact saved weapon configuration."""
    return json.dumps([identity,stats.get('craft_tier'),stars,stats.get('calibration_blueprint'),
        stats.get('calibration_bonus'),stats.get('calibration_profile'),stats.get('calibration_upgrade_level'),
        stats.get('accessories') or None],sort_keys=True)

def validate_weapon_stats(values,entry):
    if values is None:return None
    if entry.get('kind')!='weapon' or entry.get('family')=='melee' or not isinstance(values,dict) or set(values)-{'attack','rpm','magazine','reload_seconds'}:
        raise ValueError('Current weapon values require a ranged weapon')
    for key,maximum in (('attack',100000),('rpm',5000),('magazine',1000),('reload_seconds',120)):
        number=values.get(key)
        if number is None:continue
        if isinstance(number,bool) or not isinstance(number,(int,float)) or not math.isfinite(number) or not 0<=number<=maximum or (key!='reload_seconds' and number==0) or (key=='magazine' and int(number)!=number):
            raise ValueError('Invalid current weapon '+key.replace('_',' '))
    return {key:values[key] for key in ('attack','rpm','magazine','reload_seconds') if values.get(key) is not None}
def personal_mods():
    """Explicit mod inventory, including manual collection entries; catalog browsing is not ownership."""
    return [{'id': item['id'], 'catalog_id': item['effects']['catalog_id'],
             'level': item.get('level'), 'slot': catalog.ENTRIES[item['effects']['catalog_id']].get('slot'),
             'observed_rarity': (item.get('stats') or {}).get('observed_rarity'),
             'observed_tooltip':(item.get('stats') or {}).get('observed_tooltip'),
             'manual_collection': bool((item.get('stats') or {}).get('collection_entry')),
             'level_source': 'manual override' if (item.get('stats') or {}).get('manual_level_override') else
                 'manual entry' if (item.get('stats') or {}).get('collection_entry') else
                 'game screenshot' if (item.get('stats') or {}).get('screenshot_import') else
                 'game recording' if item.get('source_observation') else 'source unknown'}
            for item in inventory() if item.get('kind') == 'mod_unlock'
            and item.get('effects', {}).get('catalog_id') in catalog.ENTRIES
            and catalog.ENTRIES[item['effects']['catalog_id']].get('kind') == 'mod']
def loadouts():
    out=rows("loadouts")
    for x in out: x["item_ids"]=json.loads(x["item_ids"])
    return out
def planned_builds():
    out=rows("planned_builds")
    for x in out:x['slots']=json.loads(x['slots'])
    return out
def catalog_ownership():return {x['catalog_id']:x for x in rows('catalog_ownership')}

def validate_owned_accessories(selected):
    """Saved personal gear may only claim accessories explicitly marked unlocked."""
    attachments=selected.get('accessories') or {}
    if not attachments:return
    marked=catalog_ownership()
    if any(marked.get(accessory_id,{}).get('status')!='unlocked' for accessory_id in attachments.values()):
        raise ValueError('Record the accessory as unlocked before saving it on personal gear')

BUILD_SLOTS=('primary','secondary','melee','helmet','top','bottoms','shoes','gloves','mask')
ARMOR_SLOTS={'helmet':'helmet','top':'chest','bottoms':'pants','shoes':'boots','gloves':'gloves','mask':'mask'}
MOD_SLOTS={'primary':'weapon_mod','secondary':'weapon_mod','helmet':'helmet_mod','top':'chest_mod','bottoms':'pants_mod','shoes':'boots_mod','gloves':'gloves_mod','mask':'mask_mod'}
def sourced_native_star_rows():
    return {**planned_advisor.NATIVE_PARTIAL_EVIDENCE['by_catalog'],
            **planned_advisor.NATIVE_CROSSWALK_EVIDENCE['by_catalog'],
            **planned_advisor.NATIVE_CROSSWALK_V2_EVIDENCE['by_catalog']}
def validate_planned_slots(slots, *, allow_sourced_invalid_stars=False):
    if not isinstance(slots,dict):raise ValueError('Build slots must be an object')
    if set(slots)-set(BUILD_SLOTS):raise ValueError('Unknown equipment slot')
    for slot,selection in slots.items():
        if not isinstance(selection,dict):raise ValueError('Invalid slot selection')
        identity=selection.get('catalog_id')
        if identity:
            entry=catalog.ENTRIES.get(identity)
            if not entry or entry['kind'] not in ('weapon','armor'):raise ValueError('Select a known weapon or armor item')
            if slot in ('primary','secondary','melee') and entry['kind']!='weapon':raise ValueError('Weapon required for '+slot)
            if slot=='melee' and entry.get('family')!='melee':raise ValueError('Melee weapon required')
            if slot in ('primary','secondary') and entry.get('family')=='melee':raise ValueError('Ranged weapon required')
            if slot in ARMOR_SLOTS and (entry['kind']!='armor' or entry.get('slot')!=ARMOR_SLOTS[slot]):raise ValueError('Armor must match '+slot)
        elif any(selection.get(k) is not None for k in ('mod_id','level','tier','stars','legacy_enhancement','calibration_blueprint','calibration_bonus','calibration_profile','calibration_upgrade_level','accessories')):raise ValueError('Choose gear before its mod or upgrades')
        attachments=selection.get('accessories')
        if attachments is not None:
            if slot not in ('primary','secondary') or not isinstance(attachments,dict) or len(attachments)>5:
                raise ValueError('Accessories require a ranged weapon')
            for attachment_slot,accessory_id in attachments.items():
                item=accessories.ITEMS.get(accessory_id) if isinstance(accessory_id,str) else None
                if not item or item['slot']!=attachment_slot or not accessories.compatible(item,entry,ARTWORK.get('records',{}).get(identity)):
                    raise ValueError('Accessory is incompatible with this weapon or attachment slot')
        mod=selection.get('mod_id')
        if selection.get('mod_shiny') is not None and not isinstance(selection['mod_shiny'], bool):
            raise ValueError('Mod Shiny flag must be true or false')
        if mod:
            entry=catalog.ENTRIES.get(mod)
            if not entry or entry['kind']!='mod' or entry.get('slot')!=MOD_SLOTS.get(slot):raise ValueError('Mod is incompatible with '+slot)
            if entry.get('family_only'):raise ValueError('This mod family has no verified selectable variant yet')
        elif selection.get('mod_level') is not None or selection.get('mod_shiny') is not None:raise ValueError('Choose a mod before its level or Shiny flag')
        for key,minimum,maximum in (('level',1,100),('tier',1,5),('stars',0,6),('mod_level',1,17),('legacy_enhancement',0,10)):
            value=selection.get(key)
            if value is not None and (not isinstance(value,int) or value<minimum or value>maximum):raise ValueError(f'{key} outside supported input range')
        source_max=(sourced_native_star_rows().get(identity) or {}).get('published_max_stars')
        if (source_max is not None and selection.get('stars') is not None and
                selection['stars'] > source_max and not allow_sourced_invalid_stars):
            raise ValueError(f'{catalog.ENTRIES[identity]["name"]} blueprint has a published maximum of {source_max} stars; selected {selection["stars"]} cannot be saved')
        for key in ('calibration_blueprint','calibration_bonus'):
            value=selection.get(key)
            if value is not None and (slot not in ('primary','secondary','melee') or not isinstance(value,str) or len(value)>160):
                raise ValueError(f'{key} requires a weapon and at most 160 characters')
        # The AUG launched after the January 2026 removal of new weapon
        # calibration-level upgrades. It cannot be a grandfathered +0…+10 copy.
        if identity == 'weapon:aug-electron-cloud' and (selection.get('legacy_enhancement') is not None or selection.get('calibration_upgrade_level') is not None):
            raise ValueError('AUG Electron Cloud has no pre-2026 legacy calibration upgrade level')
        upgrade=selection.get('calibration_upgrade_level')
        if upgrade is not None and (slot not in ('primary','secondary','melee') or isinstance(upgrade,bool) or not isinstance(upgrade,int) or not 0<=upgrade<=100):
            raise ValueError('Calibration upgrade level requires a weapon and a nonnegative recorded value')
        profile=selection.get('calibration_profile')
        if profile is not None:
            if slot not in ('primary','secondary','melee') or not isinstance(profile,dict) or set(profile)-{'blueprint_name','rarity','style','fixed_effects','rolls','source_ref'}:
                raise ValueError('Calibration blueprint requires a weapon')
            for key,limit in (('blueprint_name',160),('style',80),('fixed_effects',500),('source_ref',120)):
                value=profile.get(key)
                if value is not None and (not isinstance(value,str) or len(value)>limit):raise ValueError('Invalid calibration '+key)
            if not str(profile.get('blueprint_name') or '').strip():raise ValueError('Calibration blueprint name required')
            if profile.get('rarity') not in (None,'unknown','purple','gold','other'):raise ValueError('Invalid calibration rarity')
            rolls=profile.get('rolls') or []
            if not isinstance(rolls,list) or len(rolls)>4:raise ValueError('Invalid calibration rolls')
            for roll in rolls:
                if not isinstance(roll,dict) or set(roll)-{'stat','value_percent','range_min','range_max'} or not isinstance(roll.get('stat'),str) or not roll['stat'].strip() or len(roll['stat'])>80:
                    raise ValueError('Invalid calibration roll')
                for key in ('value_percent','range_min','range_max'):
                    value=roll.get(key)
                    if value is not None and (isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not -1000<=value<=1000):raise ValueError('Invalid calibration roll value')
                if roll.get('value_percent') is None:raise ValueError('Calibration roll value required')
                if roll.get('range_min') is not None and roll.get('range_max') is not None and roll['range_min']>roll['range_max']:
                    raise ValueError('Invalid calibration roll range')
                if roll.get('range_min') is not None and roll['value_percent']<roll['range_min'] or roll.get('range_max') is not None and roll['value_percent']>roll['range_max']:
                    raise ValueError('Calibration roll is outside its recorded range')
        if selection.get('legacy_enhancement') is not None and slot not in ('primary','secondary','melee'):
            raise ValueError('Legacy weapon enhancement requires a weapon slot')
        readout=selection.get('weapon_readout')
        if readout is not None:
            if slot!='primary' or not identity or not isinstance(readout,dict) or set(readout)-{'signature','attack','rpm','magazine','reload_seconds','crit_rate_percent','crit_damage_percent','weakspot_damage_percent','base_trigger_chance_percent','source_ref'}:
                raise ValueError('Current weapon readout requires a primary weapon')
            if readout.get('source_ref') is not None and (not isinstance(readout['source_ref'],str) or len(readout['source_ref'])>120):
                raise ValueError('Invalid current weapon source')
            signature=readout.get('signature')
            if not isinstance(signature,str) or len(signature)>4000:
                raise ValueError('Invalid current weapon readout signature')
            try: snapshot=json.loads(signature)
            except (ValueError,TypeError):raise ValueError('Invalid current weapon readout signature') from None
            expected=[identity,selection.get('tier'),selection.get('stars'),selection.get('calibration_blueprint') or None,selection.get('calibration_bonus') or None,selection.get('inventory_id') or None]
            if snapshot!=expected+[profile,upgrade,attachments or None] and not (not attachments and snapshot==expected+[profile,upgrade]) and not (profile is None and upgrade is None and not attachments and snapshot==expected):
                raise ValueError('Current weapon readout belongs to a different gear setup')
            for key,maximum in (('attack',100000),('rpm',5000),('magazine',1000),('reload_seconds',120),('crit_rate_percent',1000),('crit_damage_percent',1000),('weakspot_damage_percent',1000),('base_trigger_chance_percent',100)):
                number=readout.get(key)
                if number is None:continue
                if isinstance(number,bool) or not isinstance(number,(int,float)) or not math.isfinite(number) or not 0<=number<=maximum or (key in ('attack','rpm','magazine') and number==0) or (key=='magazine' and int(number)!=number):
                    raise ValueError('Invalid current weapon '+key.replace('_',' '))
        if mod and selection.get('mod_level') is None:raise ValueError('Choose a mod level')
    return slots

def builder_catalog():
    owned={i.get('effects',{}).get('catalog_id'):i for i in inventory() if i.get('effects',{}).get('catalog_id')}
    manual=catalog_ownership()
    profile_levels={row['catalog_id']:row for row in rows('field_guide_levels') if row['profile_id']=='personal'}
    sightings={}
    for observation in observations():
        identification=observation['fields'].get('identification') or {}
        identity=identification.get('catalog_id');status=identification.get('ownership')
        if identity and status=='locked':sightings[identity]='locked'
    entries=[]
    for e in catalog.ENTRIES.values():
        if e['kind'] not in ('mod','weapon','armor'):continue
        identity=e['id'];mark=manual.get(identity);observed=owned.get(identity);profile=profile_levels.get(identity)
        conflict=bool((observed or profile) and mark and mark['status']=='locked')
        status='unlocked' if observed or profile else mark['status'] if mark else 'locked' if sightings.get(identity)=='locked' else 'unknown'
        art=ARTWORK.get('records',{}).get(identity,{})
        native=native_mod_identity.for_catalog(identity) if e['kind']=='mod' else None
        artwork=art.get('local_path') or (native or {}).get('native_artwork_path')
        set_entry=catalog.ENTRIES.get(e.get('set_id')) if e.get('set_id') else None
        entries.append({'id':identity,'kind':e['kind'],'name':e.get('display_name') or e['name'],'base_name':e['name'],'variant':e.get('variant'),'family_only':bool(e.get('family_only')),'slot':e.get('slot'),'family':e.get('family'),'weapon_category':art.get('weapon_category'),'tree':e.get('tree'),'set_name':set_entry['name'] if set_entry else e.get('set_name'),'rarity':e.get('rarity'),'effect':e.get('primary_effect') or e.get('effect'),'artwork':artwork,'artwork_source':art.get('source_page') or e.get('source_url'),'native_mod_identity':native,'image_missing':not bool(artwork),'ownership':status,'ownership_conflict':conflict,'available_level':observed.get('level') if observed and (observed.get('level') is not None or (observed.get('stats') or {}).get('manual_level_override')) else profile['level'] if profile else mark['available_level'] if mark else None,'observed_numeric_levels':sorted({int(level) for level in (catalog.NUMERIC['profiles'].get(identity) or {})} | catalog.REVIEWED_LEVELS.get(identity,set())) if e['kind']=='mod' else [],'source_observed_level':e.get('source_observed_level'),'source_observed_unlock_status':e.get('source_observed_unlock_status'),'source_video':e.get('source_video'),'source_video_timestamp_seconds':e.get('source_video_timestamp_seconds'),'data_status':e.get('data_status')})
    accessory_marks=catalog_ownership()
    star_limits={identity:{'max':row['published_max_stars'],'url':row['public_blueprint_url'],
                           'source_status':'exact_named_published_blueprint'}
                 for identity,row in sourced_native_star_rows().items()}
    return {'entries':entries,'verified_star_limits':star_limits,
            'artwork_coverage':ARTWORK.get('coverage',{}),'planned_builds':planned_builds(),'my_gear':personal_gear(),'owned_mods':personal_mods(),
            'accessories':[{**item,'recorded_unlocked':accessory_marks.get(item['id'],{}).get('status')=='unlocked',
                'compatible_weapon_ids':[weapon_id for weapon_id,weapon in catalog.ENTRIES.items()
                    if accessories.compatible(accessories.ITEMS[item['id']],weapon,ARTWORK.get('records',{}).get(weapon_id))]}
                for item in accessories.public_items()]}
def upgrades():
    out=rows("upgrades")
    for x in out:
        x["proposed_stats"]=json.loads(x["proposed_stats"] or "{}")
        x["cost"]=json.loads(x["cost"] or "{}")
    return out
def measurements():
    out=rows("measurements")
    for x in out:x["item_ids"]=json.loads(x["item_ids"])
    return out
def observations():
    out=rows("observations")
    for x in out: x["fields"]=json.loads(x["fields"] or "{}")
    return out
def catalog_item_data(catalog_id,level=None):
    result=catalog.resolve(catalog_id,level)
    entry=result['entry']
    stats={'catalog_level_profile':result['level_profile']} if result['level_profile'] else {}
    if result['attribute_tiers']:stats['catalog_attribute_tiers']=result['attribute_tiers']
    if result['known_attributes']:stats['catalog_attributes']=result['known_attributes']
    if result.get('attribute_coverage'):stats['attribute_coverage']=result['attribute_coverage']
    effects={'catalog_id':catalog_id,'catalog_effects':result['known_effects'],'catalog_effect_candidates':result['effect_candidates'],'catalog_source':entry['source'],'catalog_unknowns':result['unknowns'],'text':result['primary_effect'] or '', 'calculation_status':'catalog_partial'}
    return {'name':entry['name'],'slot':entry.get('slot'),'variant':entry.get('variant'),'level':level,'kind':'mod_unlock' if entry['kind']=='mod' else 'unlock','stats':stats,'effects':effects}
def enrich_catalog_item(item,catalog_id):
    resolved=catalog_item_data(catalog_id,item.get('level'))
    merged={**resolved,**item}
    merged['stats']={**resolved['stats'],**(item.get('stats') or {})}
    merged['effects']={**resolved['effects'],**(item.get('effects') or {})}
    merged['effects']['catalog_id']=catalog_id
    merged['effects']['catalog_effects']=resolved['effects']['catalog_effects']
    merged['effects']['catalog_source']=resolved['effects']['catalog_source']
    merged['effects']['catalog_unknowns']=resolved['effects']['catalog_unknowns']
    if not merged['effects'].get('text'):merged['effects']['text']=resolved['effects']['text']
    if catalog.ENTRIES[catalog_id]['kind']=='mod' and merged.get('kind')=='instance':merged['kind']='mod_unlock'
    return merged
def catalog_search(query='',kind='',slot='',offset=0,limit=30):
    text=query.casefold().strip()
    entries=[e for e in catalog.ENTRIES.values() if (not kind or e['kind']==kind) and (not slot or e.get('slot')==slot) and (not text or text in ' '.join(str(e.get(k) or '') for k in ('name','display_name','variant','tree','family','primary_effect')).casefold())]
    entries.sort(key=lambda e:(e['kind'],e.get('name',''),e.get('variant') or ''))
    owned={i.get('effects',{}).get('catalog_id') for i in inventory()}
    sightings={o['fields'].get('identification',{}).get('catalog_id'):o['fields'].get('identification',{}).get('ownership') for o in observations() if o['fields'].get('identification',{}).get('catalog_id')}
    return {'total':len(entries),'offset':offset,'limit':limit,'entries':[{**e,'image_url':ARTWORK.get('records',{}).get(e['id'],{}).get('local_path'),'image_missing':not bool(ARTWORK.get('records',{}).get(e['id'],{}).get('local_path')),'owned':e['id'] in owned,'sighting':sightings.get(e['id'],'unseen')} for e in entries[offset:offset+limit]],'coverage':catalog_coverage_extended.coverage()}
def auto_confirm_catalog_mod(observation_id):
    """Confirm only an exact catalog title plus Field Guide level and Equip cue."""
    with connect() as c:
        obs=c.execute('SELECT * FROM observations WHERE id=?',(observation_id,)).fetchone()
        if not obs:return False
        fields=json.loads(obs['fields'] or '{}');identity=fields.get('identification') or {}
        catalog_id=identity.get('catalog_id');match=identity.get('match') or {}
        if not (catalog_id and catalog_id.startswith('mod:') and match.get('confidence')==1.0 and identity.get('ownership')=='unlocked' and identity.get('level') in range(1,18)):
            return False
        if not {'equip action','visible Field Guide level'}<=set(identity.get('cues') or []):return False
        existing=None
        for row in c.execute("SELECT * FROM inventory WHERE kind='mod_unlock' AND archived=0"):
            if json.loads(row['effects'] or '{}').get('catalog_id')==catalog_id:existing=row;break
        level=max(identity['level'],existing['level'] or 0) if existing else identity['level']
        data=catalog_item_data(catalog_id,level)
        if fields.get('mod_roll_lines'):
            data['stats']['observed_attribute_lines']=fields['mod_roll_lines']['value']
            data['stats']['observed_attribute_ocr_status']='unverified_ocr'
            data['stats']['roll_evidence_observation']=observation_id
        iid=existing['id'] if existing else uuid.uuid4().hex
        evidence=json.loads(existing['evidence'] or '[]') if existing else []
        if not any(e.get('observation_id')==observation_id for e in evidence):
            evidence.append({'observation_id':observation_id,'image':obs['image'],'timestamp':obs['timestamp'],'media_id':obs['media_id'],'cues':identity['cues']})
        if existing:
            previous_stats=json.loads(existing['stats'] or '{}')
            previous_effects=json.loads(existing['effects'] or '{}')
            data['stats']={**previous_stats,**data['stats']}
            data['effects']={**previous_effects,**data['effects']}
        vals=(iid,data['name'],data['kind'],data['slot'],None,data['variant'],level,None,json.dumps(data['stats']),json.dumps(data['effects']),observation_id,json.dumps(evidence),existing['confirmed'] if existing else now(),now(),0)
        c.execute('REPLACE INTO inventory VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',vals)
        c.execute("UPDATE observations SET state='confirmed' WHERE id=?",(observation_id,))
        return True
def process_video_run(run_id,media_id,path,options):
    with job_lock:jobs[run_id].update(state='running',progress=0)
    video_review.update_run(DB,run_id,'running')
    try:
        folder=MEDIA/media_id/'video-review'/run_id
        def report(percent):
            with job_lock:jobs[run_id]['progress']=percent
        def cancelled():
            with job_lock:return jobs[run_id].get('cancel',False)
        result=(video_import.analyze(path,folder,options['start'],options['end'],options['interval'],report,cancelled)
                if path.suffix.lower() in ('.mp4','.mkv') else video_import.analyze_image(path,folder))
        if result.get('cancelled'):
            video_review.update_run(DB,run_id,'cancelled',{'warning':'Analysis cancelled; no inventory changed'})
            with job_lock:jobs[run_id].update(state='cancelled')
            return
        video_review.persist_result(DB,run_id,result,DATA)
        with job_lock:jobs[run_id].update(state='done',progress=100,proposals=len(result['proposals']))
    except Exception as error:
        video_review.update_run(DB,run_id,'error',{'error':str(error)})
        with job_lock:jobs[run_id].update(state='error',error=str(error))

def safe_name(name): return re.sub(r"[^\w. -]","_",Path(name).name)[:100] or "recording"

def probe(path):
    p=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","json",str(path)],capture_output=True,text=True,timeout=20)
    if p.returncode: raise ValueError("Video could not be decoded")
    return float(json.loads(p.stdout).get("format",{}).get("duration",0))
def ocr_image(path):
    p=subprocess.run(["tesseract",str(path),"stdout","tsv"],capture_output=True,text=True,timeout=45)
    if p.returncode: return "",0
    words=[]; conf=[]; last_line=None
    for line in p.stdout.splitlines()[1:]:
        cols=line.split("\t",11)
        if len(cols)<12 or not cols[11].strip(): continue
        try: score=float(cols[10])
        except ValueError: continue
        line_key=tuple(cols[1:5])
        if last_line is not None and line_key!=last_line: words.append("\n")
        words.append(cols[11].strip()); conf.append(score); last_line=line_key
    return " ".join(words).replace(" \n ","\n"), round(sum(conf)/len(conf),1) if conf else 0
def parse_ocr(text):
    """Candidates only. Each field carries confidence and must be confirmed."""
    fields={}; lines=text.splitlines() if "\n" in text else [text]
    line=next((x.strip() for x in lines if len(x.strip())>=4),"")
    if line: fields["name"]={"value":line[:100],"confidence":"low","reason":"First readable OCR line; verify against image"}
    patterns={"level":r"\b(?:Lv\.?|Level)\s*(\d{1,2})\b","stars":r"\b(\d)\s*(?:star|stars|★)","damage":r"(?m)^\s*(?:Damage|DMG|Attack)\s*[:+]?\s*(\d+(?:\.\d+)?)\b","rpm":r"\b(?:Fire\s*Rate|RPM)\s*[:+]?\s*(\d+(?:\.\d+)?)","magazine":r"\b(?:Magazine|Capacity)\s*[:+]?\s*(\d+)","reload_seconds":r"\bReload(?:\s+Time)?\s*[:+]?\s*(\d+(?:\.\d+)?)\s*s(?:ec)?\b"}
    for key,pat in patterns.items():
        m=re.search(pat,text,re.I)
        if m: fields[key]={"value":float(m.group(1)) if "." in m.group(1) else int(m.group(1)),"confidence":"medium","reason":"OCR pattern; verify label and value"}
    for index,row in enumerate(lines[:-1]):
        if re.search(r'\bDMG\b',row,re.I) and re.search(r'Fire\s*Rate',row,re.I):
            nums=re.findall(r'(?<!\d)\d{2,5}(?!\d)',lines[index+1])
            if len(nums)>=3:
                for key,value in zip(('damage','rpm','magazine'),nums[:3]):fields[key]={"value":int(value),"confidence":"medium","reason":"Basic Stats header and next-row number triplet; verify against image"}
                break
    # Preserve the full OCR line; percentages are not silently mapped to damage formulas.
    attr_re=re.compile(r"\b(?:Crit(?:ical)?(?:\s+(?:Rate|DMG|Damage))?|Weak\s*Spot(?:\s+(?:Rate|DMG|Damage))?|Weapon\s+DMG|Status\s+DMG|Elemental\s+DMG|Reload(?:\s+Speed)?|HP|Attack)\b[^\n]{0,45}?[+\-]?\d+(?:\.\d+)?\s*%",re.I)
    attributes=[m.group(0).strip() for m in attr_re.finditer(text)]
    # New Field Guide suffix attributes often use keyword-specific labels.
    marker=next((i for i,row in enumerate(lines) if re.search(r'^[^\n]{0,12}?\b(?:1[0-7]|[1-9])[ \t]+(?:General|Violent|Precision|Survival|Battle|Power Surge|[A-Z][A-Za-z -]*Deviant Energy|Resonance|Downstar|Crescent|Lunar|Mirror|Wild|Phantasmal|Aero)[ \t]*$',row)),None)
    if marker is not None:
        tail='\n'.join(lines[marker+1:]).split('Level 5 and above')[0]
        roll_lines=[]
        for row in tail.splitlines():
            clean=row.strip(' |')
            if not clean:continue
            if re.search(r'\bEquip\b|\bUnlock\b',clean,re.I):break
            if re.search(r'[+\-]\s*\d+(?:\.\d+)?\s*%',clean):roll_lines.append(clean)
            elif clean.endswith('+'):roll_lines.append(clean)
            elif roll_lines and re.match(r'^\d+(?:\.\d+)?\s*%',clean):roll_lines[-1]+=' '+clean
            elif roll_lines and len(clean)>3:roll_lines[-1]+=' '+clean
        fields['mod_roll_lines']={'value':roll_lines,'confidence':'low','reason':'Only lines below Field Guide level; OCR requires roll verification'}
        for line in roll_lines:
            if re.search(r'[+\-]\s*\d+(?:\.\d+)?\s*%',line) and line not in attributes:attributes.append(line)
    if attributes:fields["attributes"]={"value":attributes,"confidence":"low","reason":"Exact OCR snippets; verify text and chosen variant"}
    effect_lines=[x.strip() for x in lines if re.search(r"\b(?:on hit|after reload|when|trigger|stack|cooldown|chance|status|shrapnel|bounce|burn|frost vortex|power surge)\b",x,re.I)]
    if effect_lines:fields["effect_text"]={"value":"\n".join(effect_lines)[:1200],"confidence":"low","reason":"OCR effect lines, not interpreted as a formula"}
    slots={"weapon mod":"weapon_mod","helmet mod":"helmet_mod","mask mod":"mask_mod","chest mod":"chest_mod","gloves mod":"gloves_mod","pants mod":"pants_mod","boots mod":"boots_mod"}
    for label,slot in slots.items():
        if re.search(r"\b"+re.escape(label)+r"\b",text,re.I):fields["slot"]={"value":slot,"confidence":"medium","reason":"OCR slot label"};break
    set_match=re.search(r"\b(?:Set\s*[:：]\s*|(?:Part of|Piece of)\s+)([A-Za-z][A-Za-z '\-]{3,55}?)\s*(?:Set)?\s*(?:\n|$)",text,re.I)
    if set_match:fields["set_name"]={"value":set_match.group(1).strip(),"confidence":"low","reason":"OCR set label; verify exact name"}
    return fields
def process(job_id,media_id,opts):
    with job_lock: jobs[job_id].update(state="running",progress=0)
    try:
        with connect() as c: media=dict(c.execute("SELECT * FROM media WHERE id=?",(media_id,)).fetchone())
        path=MEDIA/media_id/safe_name(media["name"]); output=MEDIA/media_id/"frames"/job_id; output.mkdir(parents=True,exist_ok=True)
        frames=[]
        if media["type"]=="image": frames=[(0,path)]
        else:
            duration=probe(path); start=max(0,float(opts.get("start",0))); end=min(duration,float(opts.get("end") or duration))
            if end<=start: raise ValueError("End time must be after start time")
            interval=max(1,float(opts.get("interval",3)))
            times=[round(start+i*interval,2) for i in range(min(240,int((end-start)/interval)+1))]
            for i,t in enumerate(times):
                with job_lock:
                    if jobs[job_id].get("cancel"): jobs[job_id]["state"]="cancelled"; return
                frame=output/f"{i:04d}.png"
                crop=opts.get("crop")
                cmd=["ffmpeg","-hide_banner","-loglevel","error","-ss",str(t),"-i",str(path),"-frames:v","1"]
                if crop:
                    vals=[int(crop.get(k,0)) for k in ("w","h","x","y")]
                    if vals[0]<=0 or vals[1]<=0 or min(vals[2:])<0: raise ValueError("Invalid crop")
                    cmd += ["-vf",f"crop={vals[0]}:{vals[1]}:{vals[2]}:{vals[3]}"]
                subprocess.run(cmd+["-y",str(frame)],capture_output=True,timeout=40)
                if frame.exists(): frames.append((t,frame))
                with job_lock: jobs[job_id]["progress"]=round((i+1)/max(len(times),1)*45)
        seen=set(); saved=0
        for i,(stamp,frame) in enumerate(frames):
            with job_lock:
                if jobs[job_id].get("cancel"): jobs[job_id]["state"]="cancelled"; return
            with Image.open(frame) as im:
                if min(im.size)<300: continue
            raw,confidence=ocr_image(frame)
            if len(raw.strip())<8 or confidence<20: continue
            signature=re.sub(r"\W+","",raw.lower())
            if signature in seen: continue
            seen.add(signature)
            oid=uuid.uuid4().hex
            fields=parse_ocr(raw)
            identification=recognition.identify(raw,frame)
            if identification['match']['status']=='no_match' and not re.search(r'Weapon Mods|Armor Mods|Basic Stats|Blueprint|B\.P\.|Set Effect|Unlock|\bEquip\b|Locked',raw,re.I) and not any(k in fields for k in ('damage','rpm','magazine','slot')):
                continue
            fields['identification']=identification
            if identification.get('catalog_id'):
                fields['name']={'value':identification['name'],'confidence':'high' if identification['match']['confidence']>=.95 else 'medium','reason':'Matched to versioned catalog; verify visible title'}
                fields['slot']={'value':identification['slot'],'confidence':'high','reason':'Catalog slot for matched entry'}
                if identification.get('level') is not None:fields['level']={'value':identification['level'],'confidence':'medium','reason':'Field Guide level OCR; verify card number'}
                if identification.get('variant'):fields['variant']={'value':identification['variant'],'confidence':'high','reason':'Matched catalog variant'}
            with connect() as c: c.execute("INSERT INTO observations VALUES(?,?,?,?,?,?,?,?,?)",(oid,media_id,str(frame.relative_to(DATA)),stamp,raw,json.dumps(fields),confidence,"pending",now()))
            # Imported sightings remain review proposals; video analysis never claims ownership.
            saved+=1
            with job_lock: jobs[job_id]["progress"]=45+round((i+1)/max(len(frames),1)*55)
        with job_lock: jobs[job_id].update(state="done",progress=100,observations=saved)
    except Exception as e:
        with job_lock: jobs[job_id].update(state="error",error=str(e))

def backup():
    tables={t:rows(t) for t in ("media","observations","inventory","loadouts","planned_builds","catalog_ownership","activities","revisions","upgrades","measurements","video_import_runs","video_import_proposals","field_guide_levels","field_guide_level_events","undo")}
    media={}
    for entry in tables["media"]:
        folder=MEDIA/entry["id"]
        if folder.exists():
            for path in folder.rglob("*"):
                if path.is_file() and path.stat().st_size<=30*1024**2:
                    media[str(path.relative_to(DATA))]=base64.b64encode(path.read_bytes()).decode()
    return {"format":"once-human-advisor-backup","version":8,"exported":now(),"tables":tables,"files":media}
def restore(data):
    if data.get("format")!="once-human-advisor-backup" or data.get("version") not in (1,2,3,4,5,6,7,8): raise ValueError("Unsupported backup format")
    permitted={"media","observations","inventory","loadouts","activities","revisions"}
    if data["version"]>=2:permitted.add("upgrades")
    if data["version"]>=3:permitted.add("measurements")
    if data["version"]>=6:permitted.update(("planned_builds","catalog_ownership"))
    if data["version"]>=7:permitted.update(("video_import_runs","video_import_proposals"))
    if data["version"]>=8:permitted.update(("field_guide_levels","field_guide_level_events","undo"))
    tables=data.get("tables",{})
    if set(tables)!=permitted or any(not isinstance(v,list) for v in tables.values()): raise ValueError("Invalid backup tables")
    files=data.get("files",{})
    if not isinstance(files,dict) or len(files)>500: raise ValueError("Invalid media bundle")
    decoded={}
    for name,encoded in files.items():
        p=Path(name)
        if p.is_absolute() or ".." in p.parts or not str(p).startswith("media/"): raise ValueError("Unsafe media path")
        if len(encoded)>42*1024**2: raise ValueError("Media too large")
        decoded[name]=base64.b64decode(encoded,validate=True)
    with connect() as c:
        for t in ("video_import_proposals","video_import_runs","observations","measurements","loadouts","planned_builds","catalog_ownership","inventory","activities","revisions","upgrades","media"): c.execute(f"DELETE FROM {t}")
        if data["version"]>=8:
            for t in ("field_guide_level_events","field_guide_levels","undo"):c.execute(f"DELETE FROM {t}")
        for t in ("media","observations","inventory","loadouts","planned_builds","catalog_ownership","activities","revisions","upgrades","measurements","video_import_runs","video_import_proposals","field_guide_levels","field_guide_level_events","undo"):
            if t not in tables:continue
            expected=[r[1] for r in c.execute(f"PRAGMA table_info({t})")]
            for row in tables[t]:
                if t=="activities" and data["version"]==1:row={**row,"target_id":None}
                if t=="measurements" and data["version"]==3:row={**row,"rpm":None,"magazine":None,"reload_seconds":None}
                if t=="measurements" and data["version"]<5:row={**row,"item_fingerprint":None}
                if not isinstance(row,dict) or set(row)!=set(expected): raise ValueError(f"Invalid {t} row")
                c.execute(f"INSERT INTO {t}({','.join(expected)}) VALUES({','.join('?'*len(expected))})",[row[k] for k in expected])
    for name,content in decoded.items():
        dest=DATA/name; dest.parent.mkdir(parents=True,exist_ok=True); dest.write_bytes(content)

class Handler(BaseHTTPRequestHandler):
    def log_message(self,fmt,*args): pass
    def respond(self,obj,status=200):
        body=json.dumps(obj,default=str).encode(); self.send_response(status); self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body)
    def body(self,limit=10*1024**2):
        n=int(self.headers.get("Content-Length",0))
        if n<=0 or n>limit: raise ValueError("Invalid request size")
        return json.loads(self.rfile.read(n))
    def file(self,path,ctype,download_name=None):
        if not path.is_file(): return self.respond({"error":"Not found"},404)
        content=path.read_bytes(); self.send_response(200); self.send_header("Content-Type",ctype); self.send_header("Content-Length",str(len(content))); self.send_header("Cache-Control","no-store")
        if download_name:self.send_header("Content-Disposition",f'attachment; filename="{download_name}"')
        self.end_headers(); self.wfile.write(content)
    def media_file(self,path,ctype,head_only=False):
        if not path.is_file(): return self.respond({"error":"Not found"},404)
        size=path.stat().st_size
        first,last=0,size-1
        raw=self.headers.get('Range')
        if raw:
            match=re.fullmatch(r'bytes=(\d*)-(\d*)',raw.strip())
            if not match or (not match[1] and not match[2]):
                match=None
            if match:
                if match[1]:
                    first=int(match[1]);last=int(match[2]) if match[2] else size-1
                else:
                    count=int(match[2]);first=max(0,size-count)
                last=min(last,size-1)
            if not match or first>=size or last<first:
                self.send_response(416)
                self.send_header('Content-Range',f'bytes */{size}')
                self.send_header('Content-Length','0')
                self.end_headers()
                return
        self.send_response(206 if raw else 200)
        self.send_header('Content-Type',ctype)
        self.send_header('Accept-Ranges','bytes')
        self.send_header('Content-Length',str(last-first+1))
        self.send_header('Cache-Control','no-store')
        if raw:self.send_header('Content-Range',f'bytes {first}-{last}/{size}')
        self.end_headers()
        if head_only:return
        with path.open('rb') as source:
            source.seek(first)
            remaining=last-first+1
            while remaining:
                block=source.read(min(1024**2,remaining))
                if not block:break
                try:self.wfile.write(block)
                except (BrokenPipeError,ConnectionResetError):break
                remaining-=len(block)
    def do_HEAD(self):
        path=urlparse(self.path).path
        if path.startswith('/media/'):
            p=Path(unquote(path.lstrip('/')))
            if '..' in p.parts or p.suffix.lower() not in MIME:
                self.send_error(400);return
            return self.media_file(DATA/p,MIME[p.suffix.lower()],head_only=True)
        self.send_error(404)
    def do_GET(self):
        try:
            path=urlparse(self.path).path
            if path=="/" or path=="/forge": return self.file(ROOT/"static/forge.html","text/html; charset=utf-8")
            if path=="/classic": return self.file(ROOT/"static/index.html","text/html; charset=utf-8")
            if path=="/forge.js": return self.file(ROOT/"static/forge.js","text/javascript; charset=utf-8")
            if path=="/forge.css": return self.file(ROOT/"static/forge.css","text/css; charset=utf-8")
            if path.startswith("/fonts/"):
                fn=path[len("/fonts/"):]
                if re.fullmatch(r"[A-Za-z0-9_.-]+\.woff2",fn) and (ROOT/"static/fonts"/fn).is_file():
                    return self.file(ROOT/"static/fonts"/fn,"font/woff2")
                return self.respond({"error":"Not found"},404)
            if path.startswith("/icons/"):
                fn=path[len("/icons/"):]
                if re.fullmatch(r"[A-Za-z0-9_.-]+\.(webp|png)",fn) and (ROOT/"static/icons"/fn).is_file():
                    return self.file(ROOT/"static/icons"/fn,"image/webp" if fn.endswith(".webp") else "image/png")
                return self.respond({"error":"Not found"},404)
            if path.startswith("/live-icons/"):
                fn=path[len("/live-icons/"):]
                if re.fullmatch(r"[A-Za-z0-9_.-]+\.(webp|png)",fn) and (DATA/"live/icons"/fn).is_file():
                    return self.file(DATA/"live/icons"/fn,"image/webp" if fn.endswith(".webp") else "image/png")
                return self.respond({"error":"Not found"},404)
            if path=="/api/forge/update/status":
                import forge as _forge, forge_update as _fu, forge_live as _fl
                return self.respond({"job":_fu.status(),"info":_forge.data_info(),"history":[{k:e.get(k) for k in ("id","kind","mode","finished","summary","ok")} for e in _fl.log_tail(8)]})
            if path=="/api/forge/path/status":
                import forge_path as _fp
                return self.respond(_fp.status())
            if path=="/api/forge/handoff":
                import forge_update as _fu
                return self.respond({"text":_fu.handoff_text()})
            if path=="/api/forge/state":
                import forge as _forge
                prof=_forge.load_profile()
                return self.respond({"profile":prof,"catalog":_forge.ui_catalog(),"result":_forge.optimize(prof),"inventory":_forge.inventory(prof),"saves":_forge.profile_saves(),"slots":_forge.profile_slots()})
            if path=="/api/forge/crate":
                import forge_crates as _crates
                q=parse_qs(urlparse(self.path).query); g=lambda k:(q.get(k) or [None])[0]
                try: return self.respond(_crates.advise(g("id") or "", slot=g("slot") or None, level=int(g("level")) if (g("level") or "").isdigit() else None, aim=g("aim") or None))
                except ValueError as e: return self.respond({"error":str(e)},400)
            if path=="/api/forge/dust":
                import forge_crates as _crates
                q=parse_qs(urlparse(self.path).query); g=lambda k:(q.get(k) or ["0"])[0]
                return self.respond(_crates.dust_plan(int(g("dust")) if g("dust").isdigit() else 0, int(g("bought")) if g("bought").isdigit() else 0))
            if path=="/api/forge/mod_info":
                import forge as _forge
                q=parse_qs(urlparse(self.path).query); g=lambda k:(q.get(k) or [""])[0]
                prof=_forge.load_profile()
                return self.respond(_forge.mod_info(g("name"),g("variant") or "General",int(g("level")) if g("level").isdigit() else 0,prof.get("scenario") or "boss"))
            if path=="/api/forge/survive":
                import forge as _forge, forge_survive as _fs
                try: return self.respond(_fs.survive_cached(_forge.load_profile()))
                except Exception as e: return self.respond({"error":str(e)},500)
            if path=="/api/forge/effort":
                import forge as _forge
                return self.respond(_forge.effort_compare())
            if path=="/api/forge/theory":
                import forge as _forge, forge_theory as _theory
                q=parse_qs(urlparse(self.path).query)
                prof=_forge.load_profile()
                scn=(q.get("scenario") or [prof.get("scenario") or "boss"])[0]
                if scn not in _forge.fe.SCENARIOS: scn="boss"
                marked=(q.get("marked") or ["0"])[0]=="1"
                return self.respond(_theory.theory(scn, marked=marked))
            if path=="/calibration-worksheet": return self.file(ROOT/"static/calibration-worksheet.html","text/html; charset=utf-8")
            if path=="/calibration-worksheet.js": return self.file(ROOT/"static/calibration-worksheet.js","text/javascript; charset=utf-8")
            if path=="/calibration-worksheet-blank.json": return self.file(ROOT/"static/calibration-worksheet-blank.json","application/json; charset=utf-8","deviant-forge-calibration-blank.json")
            if path=="/app.js": return self.file(ROOT/"static/app.js","text/javascript; charset=utf-8")
            if path=="/helmet-case.json": return self.file(ROOT/"examples/helmet_lunar_reported.json","application/json; charset=utf-8")
            if path=="/abyss-map.js": return self.file(ROOT/"static/abyss-map.js","text/javascript; charset=utf-8")
            if path=="/combat_formula_ui.js": return self.file(ROOT/"static/combat_formula_ui.js","text/javascript; charset=utf-8")
            if path=="/planned_compare_ui.js": return self.file(ROOT/"static/planned_compare_ui.js","text/javascript; charset=utf-8")
            if path=="/mod-reference.js": return self.file(ROOT/"static/mod-reference.js","text/javascript; charset=utf-8")
            if path=="/builder.js": return self.file(ROOT/"static/builder.js","text/javascript; charset=utf-8")
            if path=="/builder-workflow.js": return self.file(ROOT/"static/builder-workflow.js","text/javascript; charset=utf-8")
            if path=="/builder-character.js": return self.file(ROOT/"static/builder-character.js","text/javascript; charset=utf-8")
            if path=="/builder-accessories.js": return self.file(ROOT/"static/builder-accessories.js","text/javascript; charset=utf-8")
            if path=="/icon.svg":return self.file(ROOT/"desktop/deviant-forge.svg","image/svg+xml")
            if path=="/style.css": return self.file(ROOT/"static/style.css","text/css; charset=utf-8")
            if path=="/api/app-update":
                import forge_appupdate as _au
                return self.respond(_au.status(refresh=parse_qs(urlparse(self.path).query).get("refresh",["0"])[0]=="1"))
            if path=="/api/health":return self.respond({'app':'deviant-forge','status':'ready','version':APP_VERSION,'app_dir':str(ROOT)})
            if path=="/api/native-calibration-choices":
                import native_calibration_catalog
                weapon_id=parse_qs(urlparse(self.path).query).get('weapon_id',[None])[0]
                return self.respond(native_calibration_catalog.choices(weapon_id))
            if path.startswith("/api/native-gun-suffix/"):
                import native_gun_suffix
                import published_item_tier
                identity=unquote(path.split('/api/native-gun-suffix/',1)[1])
                if identity not in catalog.ENTRIES or catalog.ENTRIES[identity]['kind']!='weapon':
                    return self.respond({'error':'Unknown weapon identity'},404)
                staged=native_gun_suffix.load_current(published_item_tier.ROWS)
                records=[row for row in staged['source_packet']['records']
                         if row['catalog_id']==identity]
                return self.respond({'catalog_id':identity,
                    'status':'decoded_native_fields_evidence_only' if records else 'not_in_bounded_sample',
                    'calculation_included':False,
                    'source':staged['source_packet']['source'],
                    'records':records,
                    'source_conflicts':[row for row in staged['source_conflicts']
                                        if row['catalog_id']==identity],
                    'unresolved':['Field consumer, source-native unit and crafted configuration scope are not yet established']
                    if records else []})
            if path=="/api/published-reference-weapons":
                import published_calculator_adapter
                import published_item_tier
                import published_timed_combat
                entries=[]
                for identity,entry in catalog.ENTRIES.items():
                    if entry['kind']!='weapon':continue
                    try:
                        baseline=published_calculator_adapter.load_published_weapon_baseline(
                            published_calculator_adapter.PACKETS,identity)
                    except LookupError:baseline=None
                    tiers=sorted(int(tier) for tier in published_item_tier.ROWS.get(identity,{}).get('tiers',{}))
                    entries.append({'catalog_id':identity,'name':entry.get('display_name') or entry['name'],
                                    'numeric':False,
                                    'raw_imported_damage_available':bool(baseline and baseline['stats'].get('damage_per_projectile') is not None),
                                    'item_page_tiers':tiers,
                                    'damage_basis_status':'explicit_item_page_scenario_available' if tiers else 'unanchored_import_quarantined'})
                packets=[{'packet_id':key,'event':row['event'],
                          'weapon_id':row.get('weapon_id'),'basis':row['basis'],
                          'damage_class':row.get('damage_class'),
                          'element':row.get('element'),
                          'coefficient_kind':row['coefficient']['kind']}
                         for key,row in published_timed_combat.PACKETS.items()]
                return self.respond({'weapons':sorted(entries,key=lambda row:row['name'].lower()),
                                     'source_packets':sorted(packets,key=lambda row:row['packet_id'])})
            if path=="/api/evidence-coverage":
                import evidence_registry
                return self.respond(evidence_registry.coverage())
            if path=="/api/aid-catalog":
                import aid_catalog
                data=aid_catalog.overview()
                categories=parse_qs(urlparse(self.path).query,keep_blank_values=True).get('category')
                if categories is not None:
                    if len(categories)!=1 or categories[0] not in {row['id'] for row in data['categories']}:
                        raise ValueError('Choose one known Aid category')
                    selected=categories[0]
                    for row in data['categories']:
                        if row['id']!=selected:row['ready_items']=[]
                    data['loaded_category']=selected
                return self.respond(data)
            if path=="/api/integration-coverage":
                import integration_ledger
                ledger=integration_ledger.build()
                return self.respond({key:ledger[key] for key in ('schema_version','definition','global_damage_blocker','counts','non_scalar_bonus_lv10','scoped_exact_level_model_ready','total_records')})
            if path.startswith('/api/integration-ledger/'):
                import integration_ledger
                identity=unquote(path.split('/api/integration-ledger/',1)[1])
                record=next((row for row in integration_ledger.build()['records'] if row['catalog_id']==identity),None)
                return self.respond(record if record else {'error':'Unknown integration identity'},200 if record else 404)
            if path=="/api/weapon-timeline-coverage":
                import weapon_timeline_api
                return self.respond(weapon_timeline_api.coverage())
            if path=="/api/mod-stateful-coverage":
                import mod_stateful_api
                return self.respond(mod_stateful_api.coverage())
            if path.startswith('/api/evidence-binding/'):
                import evidence_registry
                identity=unquote(path.split('/api/evidence-binding/',1)[1])
                raw_level=parse_qs(urlparse(self.path).query).get('level',[None])[0]
                return self.respond(evidence_registry.binding(identity,int(raw_level) if raw_level else None))
            if path.startswith('/artwork/'):
                filename=unquote(path.rsplit('/',1)[-1])
                if not re.fullmatch(r'[a-zA-Z0-9_.-]+\.(png|webp)',filename):return self.respond({'error':'Invalid path'},400)
                return self.file(ROOT/'static'/'artwork'/filename,'image/png' if filename.endswith('.png') else 'image/webp')
            if path.startswith("/media/"):
                p=Path(unquote(path.lstrip("/")))
                if ".." in p.parts or p.suffix.lower() not in MIME: return self.respond({"error":"Invalid path"},400)
                return self.media_file(DATA/p,MIME[p.suffix.lower()])
            if path=="/api/state":
                video_runs,video_proposals=video_review.list_data(DB)
                media_rows=rows("media")
                current_inventory=inventory()
                source_observations=observations()
                legacy_staging={media["id"]:video_import_plan.legacy_observation_staging(media["id"],source_observations,current_inventory)
                                for media in media_rows if any(o["media_id"]==media["id"] and o["state"]=="confirmed" for o in source_observations)}
                with connect() as c:
                    profiles={key:field_guide_profiles.profile(c,key) for key in field_guide_profiles.PROFILES}
                return self.respond({"video_import_runs":video_runs,"video_import_proposals":video_proposals,"video_import_coverage":video_import_coverage.reports(video_runs,video_proposals,media_rows,current_inventory),"video_import_plans":{run["id"]:video_import_plan.plan(run["id"],video_proposals,current_inventory) for run in video_runs},"legacy_mod_staging":legacy_staging,"field_guide_profiles":profiles,"inventory":current_inventory,"loadouts":loadouts(),"planned_builds":planned_builds(),"observations":source_observations,"media":media_rows,"activities":rows("activities"),"upgrades":upgrades(),"measurements":measurements(),"revisions":rows("revisions"),"knowledge":KNOWLEDGE,"rules":json.loads((ROOT/"rules.json").read_text()),"catalog_coverage":catalog_coverage_extended.coverage()})
            if path=="/api/builder-catalog":return self.respond(builder_catalog())
            if path=="/api/catalog":
                query=parse_qs(urlparse(self.path).query)
                return self.respond(catalog_search(query.get('q',[''])[0],query.get('kind',[''])[0],query.get('slot',[''])[0],max(0,int(query.get('offset',[0])[0]))))
            if path.startswith("/api/public-mod-detail/"):
                import public_catalog_detail
                catalog_id=unquote(path.split('/api/public-mod-detail/',1)[1])
                query=parse_qs(urlparse(self.path).query)
                raw_level=query.get('level',[None])[0]
                result = public_catalog_detail.detail(
                    catalog_id, int(raw_level) if raw_level is not None else None,
                    shiny=query.get('shiny',['0'])[0]=='1')
                result['native_mod_identity'] = native_mod_identity.for_catalog(catalog_id)
                result['native_frame_catalog_preview'] = native_mod_frame_catalog.preview(
                    catalog_id, result['preview_level'], shiny=result.get('shiny') is True)
                if result['native_frame_catalog_preview'] is not None:
                    result['native_buff_graph_review_coverage'] = native_mod_buff_review.coverage()
                if catalog_id in native_mod_identity.TWO_FRAME_IDENTITIES:
                    result['native_four_line_preview'] = native_mod_identity.two_frame_preview(
                        catalog_id, result['preview_level'], shiny=result.get('shiny') is True)
                if (catalog_id == 'mod:pants_mod:precision-charge-aero' and
                        isinstance(result.get('preview_level'), int)):
                    result['native_core_math_configuration'] = native_mod_identity.aero_core_math_configuration()
                    result['native_four_line_preview'] = native_mod_identity.aero_four_line_preview(
                        result['preview_level'], shiny=result.get('shiny') is True)
                    native_preview = native_mod_identity.precision_charge_aero_preview(
                        result['preview_level'], shiny=result.get('shiny') is True)
                    result['native_first_line_preview'] = native_preview
                    if (native_preview['status'] == 'exact_native_catalog_tooltip_configuration' and
                            result.get('bonus_lines')):
                        first = result['bonus_lines'][0]
                        agrees = (first.get('name') == 'Weapon DMG' and
                                  first.get('value_percent') == native_preview['base_percent'] and
                                  first.get('conditional_bonus_percent') ==
                                  native_preview['aerial_extra_percent'])
                        if not agrees:
                            first['native_corroboration'] = {
                                'status': 'native_catalog_value_conflict',
                                'property_id': 'E42', 'entry_level': native_preview['entry_level'],
                                'effect_activated': False}
                            first['source_conflict'] = True
                            first['value_percent'] = None
                            first['conditional_bonus_percent'] = None
                            result.setdefault('missing', []).append(
                                'Native Aero first-line configuration conflicts with the catalog row; value withheld')
                if query.get('compact', ['0'])[0] == '1':
                    # The catalog panel fetches the chosen level separately. Its
                    # progression strip reads only the ordered tier numbers.
                    for key in ('progression', 'configured_progression'):
                        result[key] = [
                            {'level': row['level'],
                             'tiers': [line.get('tier') for line in row['bonus_lines']]}
                            for row in result.get(key, [])
                        ]
                    result.pop('native_frame_catalog_preview', None)
                    result['response_scope'] = 'catalog_ui_compact'
                return self.respond(result)
            if path.startswith("/api/catalog/"):
                catalog_id=unquote(path.split('/api/catalog/',1)[1])
                query=parse_qs(urlparse(self.path).query)
                raw_level=query.get('level',[None])[0]
                return self.respond(catalog.resolve(catalog_id,int(raw_level) if raw_level else None,shiny=query.get('shiny',['0'])[0]=='1'))
            if path.startswith("/api/jobs/"): return self.respond(jobs.get(path.split("/")[-1],{"error":"Unknown job"}))
            if path=="/api/backup": return self.respond(backup())
            return self.respond({"error":"Not found"},404)
        except Exception as e: return self.respond({"error":str(e)},400)
    def do_POST(self):
        try:
            path=urlparse(self.path).path
            if path=="/api/app-update/install":
                if self.client_address[0] not in ("127.0.0.1","::1"): return self.respond({'error':'local only'},403)
                import forge_appupdate as _au
                return self.respond(_au.install())
            if path=="/api/shutdown":
                # used by the Windows starter/installer to stop an older copy; only from this computer
                if self.client_address[0] not in ("127.0.0.1","::1"): return self.respond({'error':'local only'},403)
                self.respond({'ok':True,'version':APP_VERSION})
                import threading as _t, os as _os
                _t.Timer(0.3, lambda: _os._exit(0)).start(); return
            if path=="/api/forge/path/start":
                import forge_path as _fp
                return self.respond(_fp.start())
            if path=="/api/forge/update/check":
                import forge_update as _fu
                b=self.body() if int(self.headers.get("Content-Length",0) or 0)>0 else {}
                return self.respond(_fu.start("quick" if b.get("mode")=="quick" else "full"))
            if path=="/api/forge/update/undo":
                import forge_update as _fu
                try: return self.respond(_fu.rollback())
                except RuntimeError as e: return self.respond({"error":str(e)},409)
            if path=="/api/forge/verdict":
                import forge_live as _fl
                b=self.body(); return self.respond({"verdicts":_fl.set_verdict(str(b.get("key",""))[:200],b.get("verdict") if b.get("verdict") in ("not_new","cool","wrong") else None,str(b.get("note") or ""))})
            if path=="/api/forge/typed":
                import forge as _forge, forge_live as _fl
                b=self.body(); kind=b.get("kind"); name=str(b.get("name") or "").strip()[:80]
                if not name: return self.respond({"error":"Give it a name"},400)
                if kind=="scenarios" and isinstance(b.get("entry"),dict) and not name.startswith("c_"):
                    b["entry"].setdefault("name",name); name=_fl.scenario_key(name)
                _fl.save_item(kind,name,b.get("entry")); _forge.reload_data(); _fl.mark_seen(_forge.gamedata(),"typed in")
                prof=_forge.load_profile()
                return self.respond({"key":name,"profile":prof,"catalog":_forge.ui_catalog(),"result":_forge.optimize(prof),"inventory":_forge.inventory(prof)})
            if path=="/api/forge/profile/slot":
                import forge as _forge
                b=self.body()
                try: prof=_forge.slot_action(str(b.get("action") or ""),b.get("slot"),b.get("name"))
                except ValueError as e: return self.respond({"error":str(e)},400)
                return self.respond({"profile":prof,"catalog":_forge.ui_catalog(),"result":_forge.optimize(prof),"inventory":_forge.inventory(prof),"saves":_forge.profile_saves(),"slots":_forge.profile_slots()})
            if path in ("/api/forge/profile/fresh","/api/forge/profile/restore"):
                import forge as _forge
                b=self.body()
                try: prof=_forge.start_fresh(b.get("starchrom")) if path.endswith("fresh") else _forge.restore_profile(b.get("id"))
                except ValueError as e: return self.respond({"error":str(e)},400)
                return self.respond({"profile":prof,"catalog":_forge.ui_catalog(),"result":_forge.optimize(prof),"inventory":_forge.inventory(prof),"saves":_forge.profile_saves(),"slots":_forge.profile_slots()})
            if path=="/api/forge/profile":
                import forge as _forge
                prof=_forge.save_profile(self.body())
                return self.respond({"profile":prof,"catalog":_forge.ui_catalog(),"result":_forge.optimize(prof),"inventory":_forge.inventory(prof)})
            if path=="/api/upload":
                n=int(self.headers.get("Content-Length",0)); name=safe_name(self.headers.get("X-Filename","recording")); ext=Path(name).suffix.lower()
                if ext not in MIME or n<=0 or n>MAX_UPLOAD: raise ValueError("Unsupported file or size")
                media_id=uuid.uuid4().hex; folder=MEDIA/media_id; folder.mkdir()
                target=folder/name
                with target.open("wb") as f:
                    left=n
                    while left:
                        chunk=self.rfile.read(min(left,1024**2));
                        if not chunk: raise ValueError("Incomplete upload")
                        f.write(chunk); left-=len(chunk)
                kind="video" if ext in (".mp4",".mkv") else "image"
                if kind=="image":
                    with Image.open(target) as im: im.verify()
                else: probe(target)
                with connect() as c: c.execute("INSERT INTO media(id,name,type,size,created) VALUES(?,?,?,?,?)",(media_id,name,kind,n,now()))
                return self.respond({"id":media_id,"name":name,"type":kind})
            data=self.body(60*1024**2 if path=="/api/restore" else 10*1024**2)
            if path=="/api/native-sparkling-pumpkin-input":
                return self.respond(native_sparkling_pumpkin.configured_input(data))
            if path=="/api/native-aero-core-scenario":
                if not isinstance(data,dict) or set(data)!={
                        'magazine_size','qualifying_weak_remote_events',
                        'reload_post_event_clip_left','secondary_level'}:
                    raise ValueError('Enter only the four explicit native Aero scenario inputs')
                return self.respond(native_mod_identity.aero_core_conditional_scenario(**data))
            if path=="/api/native-aero-buff-refresh-scenario":
                if not isinstance(data,dict) or set(data)!={'existing_buff_stacks','incoming_stacks'}:
                    raise ValueError('Enter only explicit existing and incoming buff stacks')
                return self.respond(native_mod_identity.aero_core_conditional_refresh(**data))
            if path=="/api/native-shield-branch":
                return self.respond(native_shield_settlement.evaluate(data))
            if path=="/api/native-hit-attenuation":
                return self.respond(native_shield_settlement.attenuate(data))
            if path=="/api/native-player-hit-replay":
                return self.respond(native_player_hit_replay.replay(data))
            if path=="/api/native-npc-hit-replay":
                return self.respond(native_npc_hit_replay.replay(data))
            if path=="/api/native-max-hp-ceiling":
                return self.respond(native_max_hp_ceiling.calculate(data))
            if path=="/api/native-survival-hp":
                return self.respond(native_survival_hp.calculate(data))
            if path=="/api/native-pvp-max-hp-rate":
                return self.respond(native_pvp_max_hp_adjust.adjust(data))
            if path=="/api/native-skill-power":
                return self.respond(native_skill_power.calculate(data))
            if path=="/api/native-aug-configured-input":
                return self.respond(native_aug_surge_input.calculate(data))
            if path=="/api/native-dot-modifier-buckets":
                return self.respond(native_dot_modifier_buckets.calculate(data))
            if path=="/api/native-lightning-dot-hit":
                return self.respond(native_lightning_dot_hit.calculate(data))
            if path=="/api/native-combat-affix-label":
                return self.respond(native_combat_labels.resolve(
                    data.get('label'), data.get('affix_id'), data.get('source_build')))
            if path=="/api/field-guide/preview":
                with connect() as c:
                    return self.respond(field_guide_profiles.preview(c,data.get('profile_id'),data.get('catalog_id'),
                        data.get('level'),data.get('shiny_status','unknown')))
            if path=="/api/field-guide/level":
                with connect() as c:
                    return self.respond(field_guide_profiles.set_manual(c,data.get('profile_id'),data.get('catalog_id'),
                        data.get('level'),data.get('shiny_status','unknown')))
            if path=="/api/field-guide/video-preview":
                with connect() as c:
                    row=c.execute('SELECT data FROM video_import_proposals WHERE id=?',(data.get('proposal_id'),)).fetchone()
                    if not row:raise ValueError('Video proposal not found')
                    return self.respond(field_guide_profiles.preview_video(c,data.get('profile_id'),json.loads(row['data'])))
            if path=="/api/field-guide/video-plan":
                with connect() as c:
                    return self.respond(field_guide_profiles.plan_video_run(c,data.get('profile_id'),data.get('run_id')))
            if path=="/api/field-guide/video-save":
                with connect() as c:
                    return self.respond(field_guide_profiles.save_video_run(c,data.get('profile_id'),data.get('run_id'),
                        data.get('plan_token'),data.get('confirm') is True))
            if path=="/api/field-guide/video-undo":
                with connect() as c:
                    return self.respond(field_guide_profiles.undo_video_run(c,data.get('profile_id'),
                        data.get('batch_id'),data.get('confirm') is True))
            if path=="/api/field-guide/calculation-preview":
                with connect() as c:
                    return self.respond(field_guide_profiles.calculation_preview(c,data.get('profile_id'),
                        data.get('catalog_id'),data.get('baseline')))
            if path=="/api/field-guide/build-preview":
                build=next((item for item in planned_builds() if item['id']==data.get('build_id')),None)
                if build is None:raise ValueError('Choose one saved planned build')
                with connect() as c:
                    result=field_guide_profiles.build_calculation_preview(c,data.get('profile_id'),build['slots'],
                        data.get('baseline'),data.get('active_weapon_slot','primary'))
                return self.respond({'build_id':build['id'],'build_name':build['name'],**result})
            if path=="/api/media-preview":
                mid=data.get('media_id')
                if not isinstance(mid,str):raise ValueError('Choose a saved video')
                with connect() as c:media=c.execute('SELECT name,type FROM media WHERE id=?',(mid,)).fetchone()
                if not media or media['type']!='video':raise ValueError('Choose a saved video')
                return self.respond(media_preview.request(mid,MEDIA/mid/safe_name(media['name'])))
            if path=="/api/aug-calibration-compare":
                if data.get('mod_proposal_ids'):
                    data['typed_modifiers']=video_proposal_modifiers(data['mod_proposal_ids'])
                return self.respond(aug_compare.compare(data))
            if path=="/api/build-contribution-coverage":
                build_id=data.get('build_id')
                if not isinstance(build_id,str) or not build_id:
                    raise ValueError('Choose a saved build')
                build=next((b for b in planned_builds() if b['id']==build_id),None)
                if build is None:raise ValueError('Saved build not found')
                active=data.get('active_weapon_slot','primary')
                groups=planned_advisor._set_summary(build['slots'],{'scenario':data.get('scenario','other_unknown')})
                result=build_coverage.report(build['slots'],inventory(),catalog.ENTRIES,accessories.ITEMS,
                    active_weapon_slot=active,tech_policy=data.get('tech_policy','exclude_unknown'),
                    all_damage_model=data.get('all_damage_model','exclude_unverified'),
                    baseline_mode=data.get('baseline_mode','manual'),
                    manual_baseline=data.get('manual_baseline'),set_groups=groups)
                magazine=data.get('magazine_hypothesis') or {}
                if not isinstance(magazine,dict):raise ValueError('Magazine hypothesis must be an object')
                hits=magazine.get('landed_hits',40)
                preview=(None if hits is None else core_effects.selected_magazine(
                    build['slots'],active_weapon_slot=active,
                    base_chance=magazine.get('base_chance'),landed_hits=hits,
                    use_unlinked_shock17=magazine.get('use_unlinked_shock17',False)))
                return self.respond({'build_id':build_id,'build_name':build['name'],
                                     'selected_magazine_preview':preview,**result})
            if path=="/api/planned-set-compare":
                return self.respond({'result':combat_formula.compare_reference_sets(data),
                                     'saved':False,'ownership_required':False})
            if path=="/api/planned-one-change":
                with connect() as c:
                    return self.respond(planned_one_change.compare(data,c))
            if path=="/api/build-combat-formula":
                build_id=data.get('build_id')
                build=None
                modifier_source=data.get('modifier_source','owned_instances')
                if modifier_source not in ('owned_instances','personal_field_guide'):
                    raise ValueError('Choose an available mod evidence source')
                resolved=mod_rolls.equipped_build_modifiers({},[],active_weapon_slot=data.get('active_weapon_slot','primary'))
                if build_id is not None:
                    if not isinstance(build_id,str):raise ValueError('Build ID must be text')
                    build=next((b for b in planned_builds() if b['id']==build_id),None)
                    if build is None:raise ValueError('Saved build not found')
                    resolved=mod_rolls.equipped_build_modifiers(build['slots'],inventory(),active_weapon_slot=data.get('active_weapon_slot','primary'))
                if modifier_source=='personal_field_guide':
                    if not build:raise ValueError('Field Guide rows require an exact saved build')
                    with connect() as c:
                        profile_rows=field_guide_profiles.build_calculation_preview(
                            c,'personal',build['slots'],None,data.get('active_weapon_slot','primary'))
                    resolved={'modifiers':profile_rows['rows'],
                              'unresolved':[{'slot':issue['slot'],'mod_id':issue.get('catalog_id'),
                                             'reason':issue['reason'],'offense_blocking':True}
                                            for issue in profile_rows['issues']],
                              'resolved_slots':sorted({item['slot'] for item in profile_rows['selected']
                                                       if item['status']=='source_backed_rows_with_unknown_tech' and item['row_count']}),
                              'active_weapon_slot':data.get('active_weapon_slot','primary'),
                              'ignored_weapon_slots':sorted({item['slot'] for item in profile_rows['selected']
                                                              if item['status']=='inactive_weapon'})}
                proposed=[]
                missing_proposal_rows=[]
                if data.get('proposal_ids'):
                    proposed=video_proposal_modifiers(data['proposal_ids'])
                    evidenced_ids={row.get('evidence',{}).get('proposal_id') for row in proposed}
                    missing_proposal_rows=[proposal_id for proposal_id in data['proposal_ids'] if proposal_id not in evidenced_ids]
                    proposed_slots=set()
                    equivalent={'chest_mod':'top','helmet_mod':'helmet','weapon_mod':data.get('active_weapon_slot','primary'),
                                'pants_mod':'bottoms','boots_mod':'shoes','gloves_mod':'gloves','mask_mod':'mask'}
                    for proposal_id in data['proposal_ids']:
                        with connect() as c:
                            row=c.execute('SELECT data FROM video_import_proposals WHERE id=?',(proposal_id,)).fetchone()
                        item=json.loads(row['data']);target=equivalent.get(item.get('slot'))
                        if not target:raise ValueError('Proposal slot is not supported by this build formula')
                        if target in proposed_slots:
                            raise ValueError('Two proposed mods target the same build slot; preview one at a time')
                        proposed_slots.add(target)
                        if build and target and (build['slots'].get(target) or {}).get('mod_id'):
                            raise ValueError('A proposed mod would stack with a mod already selected for that saved slot; choose an isolated scenario or update the build explicitly')
                baseline=data.get('baseline')
                if baseline is None and data.get('use_tier_v_preview'):
                    primary=(build or {}).get('slots',{}).get(data.get('active_weapon_slot','primary'),{})
                    if build and (primary.get('catalog_id')!='weapon:aug-electron-cloud' or primary.get('tier')!=5 or primary.get('stars')!=5):
                        raise ValueError('Tier V AUG preview requires the same five-star Tier V AUG; enter this saved weapon’s own pre-mod baseline instead')
                    baseline=combat_formula.PREVIEW
                if baseline is None:raise ValueError('Enter a pre-mod baseline or explicitly choose the sourced Tier V AUG preview')
                if not isinstance(baseline,dict):raise ValueError('Baseline must be an object')
                selected_modifiers=resolved['modifiers']+proposed
                if 'external_effects' in data:
                    external=external_effects.resolve_many(
                        data.get('external_effects'),selected_modifiers,
                        assume_compatible_sources=data.get('assume_external_compatibility',False),
                        assume_same_stat_additive=data.get('assume_external_additive_bucket',False))
                else:
                    legacy_external=external_effects.resolve(data.get('external_effect'),selected_modifiers)
                    external={'rows':[legacy_external['row']] if legacy_external['row'] else [],
                              'details':[legacy_external['detail']] if legacy_external['detail'] else [],
                              'blocking':legacy_external['blocking'],'assumptions':[]}
                modifiers=selected_modifiers+external['rows']
                result=combat_formula.compare(baseline,modifiers,data.get('encounter'),data.get('power_surge'),data.get('orb'))
                external_contributions=[]
                for item in external['details']:
                    contribution={'source_kind':item.get('source_kind'),
                                  'name':item.get('name'),'stat_type':item.get('stat_type'),
                                  'applied':item.get('applied',False),'reason':item.get('reason')}
                    if item.get('applied'):
                        own=next((row for row in external['rows']
                                  if row.get('stat_type')==item.get('stat_type')
                                  and str(row.get('evidence',{}).get('external_source_name','')).casefold()==str(item.get('name','')).casefold()
                                  and row.get('evidence',{}).get('source_kind')==item.get('source_kind')),
                                 None)
                        if own is not None:
                            without=combat_formula.compare(baseline,[row for row in modifiers if row is not own],
                                                           data.get('encounter'),data.get('power_surge'),data.get('orb'))
                            contribution['energy_direct_hit_delta']=(
                                result['energy']['base_direct_hit_after_bonuses']-
                                without['energy']['base_direct_hit_after_bonuses'])
                            contribution['rapid_direct_hit_delta']=(
                                result['rapid']['base_direct_hit_after_bonuses']-
                                without['rapid']['base_direct_hit_after_bonuses'])
                            for stream in ('power_surge','orb'):
                                present=result['energy']['durations']['60'][stream]['damage']
                                previous=without['energy']['durations']['60'][stream]['damage']
                                contribution[stream+'_60s_delta']=(present-previous if present is not None and previous is not None else None)
                    external_contributions.append(contribution)
                selected_cores=core_effects.selected(build['slots'] if build else {},
                    active_weapon_slot=data.get('active_weapon_slot','primary'),
                    power_surge=data.get('power_surge'),counter=data.get('core_counter'))
                blocking_core=any(effect['total_blocking'] for effect in selected_cores)
                unmodeled=result['energy']['typed_modifiers_unmodeled']
                tech_gated=result['energy']['typed_modifiers_tech_gated']
                # Health and explicitly defensive rolls are still disclosed as
                # uncertain, but cannot erase a complete outgoing-damage model.
                # Unknown/offensive rows and unresolved identities remain blockers.
                blocking_roll_issues=bool(
                    any(issue.get('offense_blocking',True) for issue in resolved['unresolved'])
                    or missing_proposal_rows
                    or any(mod_rolls.may_affect_offense(row) for row in unmodeled+tech_gated))
                if blocking_roll_issues or blocking_core:
                    result['comparison']={k:{'delta_energy_minus_rapid_bounds':None,'winner':None} for k in ('60','300')}
                    for choice in ('energy','rapid'):
                        for duration in ('60','300'):
                            term=result[choice]['durations'][duration]
                            term['total_damage_bounds']=None
                            term['average_dps_bounds']=None
                            term['complete_under_entered_assumptions']=False
                            if blocking_roll_issues:term['missing'].append('source-checked, active rolls for every selected mod instance')
                            if blocking_core:term['missing'].append('selected core effect not included in this finite-fight calculation')
                coverage_reasons=[]
                if not modifiers:
                    active=data.get('active_weapon_slot','primary')
                    if build and not (build['slots'].get(active) or {}).get('mod_id'):
                        coverage_reasons.append('No mod is selected on the active '+active+' weapon in this saved plan')
                    else:coverage_reasons.append('No typed mod rolls were supplied or resolved')
                if missing_proposal_rows:coverage_reasons.append('One or more selected video proposals have no typed attribute rows')
                if resolved['unresolved']:coverage_reasons.append('One or more selected owned mod instances have unresolved rolls')
                if any(row.get('stat_type')=='all_damage_boost_percent' and row.get('model_exclusion') for row in unmodeled):
                    coverage_reasons.append('All DMG Boost bucket placement is unverified; its observed amount is excluded unless the independent-multiplier what-if is explicitly selected')
                if unmodeled:coverage_reasons.append('One or more selected roll rows are unmodeled or unverified')
                if tech_gated:coverage_reasons.append('Selected roll activation at this Tech level is unknown')
                if any(row.get('tech_activation')!='verified_active' and not row.get('external_hypothesis_confirmed') for row in result['energy']['typed_modifiers_used']):
                    coverage_reasons.append('One or more roll rows were included only by a Tech-level assumption')
                for item in external['details']:
                    coverage_reasons.append('External effect '+str(item.get('name'))+': '+str(item.get('reason'))+'; amount and duration are user-entered, not verified game data')
                coverage_reasons.extend(external['assumptions'])
                for effect in selected_cores:
                    if effect['total_blocking']:coverage_reasons.append(effect['name']+' core effect is excluded: '+effect['reason'])
                    else:coverage_reasons.append(effect['name']+' core frequency is included only by an entered measured-rate claim, not independently verified')
                planned_sensitivity=None
                if 'planned_sensitivity' in data:
                    if build_id is not None or modifiers or data.get('proposal_ids'):
                        raise ValueError('Planned calibration sensitivity requires an isolated unsaved baseline without selected gear or modifiers')
                    planned_sensitivity=combat_formula.planned_calibration_sensitivity(
                        result,data.get('encounter') or {},data['planned_sensitivity'])
                return self.respond({'build_id':build_id,'build_name':build['name'] if build else None,
                                     'planned_sensitivity':planned_sensitivity,
                                     'modifier_source':modifier_source,
                                     'external_effect':external['details'][0] if len(external['details'])==1 else None,
                                     'external_effects':external['details'],
                                     'external_contributions':external_contributions,
                                     'external_assumptions':external['assumptions'],
                                     'selected_owned_mods':resolved,'hypothetical_proposal_ids':data.get('proposal_ids') or [],
                                     'selected_core_effects':selected_cores,
                                     'modifier_count':len(result['energy']['typed_modifiers_used']),
                                     'candidate_modifier_count':len(modifiers),'result':result,
                                     'coverage_complete':not coverage_reasons,'coverage_reasons':coverage_reasons,
                                     'warning':('Hypothetical proposals are not owned or equipped. Roll coverage is incomplete; this is a conditional comparison, not verified total DPS.' if data.get('proposal_ids') else
                                                'Selected core effects are absent from the damage model; complete finite-fight totals are withheld.' if blocking_core else
                                                'Selected mod rows have an unresolved offensive rule, activation state or evidence match; a complete damage total is withheld.' if blocking_roll_issues else
                                                'No eligible offensive mod rolls are selected; this compares baseline and calibration terms while health or defensive evidence stays separate.' if not modifiers else
                                                'Roll coverage is incomplete; this is a conditional comparison, not verified total DPS.' if coverage_reasons else
                                                'Conditional comparison under the entered encounter assumptions; not measured game DPS.')})
            if path=="/api/video-import/build-mod-math":
                build_id=data.get('build_id')
                if not isinstance(build_id,str):raise ValueError('Choose a saved build')
                build=next((b for b in planned_builds() if b['id']==build_id),None)
                if build is None:raise ValueError('Saved build not found')
                resolved=mod_rolls.equipped_build_modifiers(build['slots'],inventory(),active_weapon_slot=data.get('active_weapon_slot','primary'))
                baseline=data.get('baseline') or {'base_origin':'unknown'}
                return self.respond({'build_id':build_id,'resolved':resolved,
                                     'scenario':mod_rolls.scenario(resolved['modifiers'],baseline),
                                     'note':'Only uniquely resolved owned mod instances are aggregated. Missing or duplicate instance rolls are not guessed. Baseline must be pre-mod and supplied separately.'})
            if path=="/api/video-import/mod-math":
                modifiers=video_proposal_modifiers(data.get('proposal_ids'))
                baseline=data.get('baseline')
                if baseline is None:
                    baseline={'base_origin':'pre_mod_unbuffed','base_direct_hit':aug_compare.BASELINE['damage'],
                              'rpm':aug_compare.BASELINE['rpm'],'magazine':aug_compare.BASELINE['magazine'],
                              'reload_seconds':data.get('reload_seconds'),
                              'elemental_event_damage':data.get('elemental_event_damage'),
                              'status_event_damage':data.get('status_event_damage'),
                              'elemental_events_per_second':data.get('elemental_events_per_second'),
                              'status_events_per_second':data.get('status_events_per_second')}
                    baseline_source=aug_compare.BASELINE['source_ref']
                else:
                    if not isinstance(baseline,dict):raise ValueError('Baseline must be an object')
                    baseline_source='user-entered pre-mod baseline; not independently verified'
                return self.respond({'modifiers':modifiers,'baseline_source':baseline_source,
                                    'scenario':mod_rolls.scenario(modifiers,baseline),
                                    'calibration_sensitivity':aug_compare.mod_calibration_sensitivity(modifiers,
                                        {'reference_reload_seconds':baseline.get('reload_seconds'),
                                         'pre_mod_elemental_event_damage':baseline.get('elemental_event_damage'),
                                         'pre_mod_status_event_damage':baseline.get('status_event_damage'),
                                         'elemental_events_per_second':baseline.get('elemental_events_per_second'),
                                         'status_events_per_second':baseline.get('status_events_per_second')})})
            if path=="/api/video-import/analyze":
                mid=str(data.get('media_id') or '')
                with connect() as c:media=c.execute('SELECT * FROM media WHERE id=?',(mid,)).fetchone()
                if not media or media['type'] not in ('video','image'):raise ValueError('Choose a saved video or screenshot')
                path_on_disk=MEDIA/mid/safe_name(media['name'])
                if not path_on_disk.is_file():raise ValueError('Source media is missing')
                duration=video_import.video_info(path_on_disk)['duration'] if media['type']=='video' else 1
                start=float(data.get('start') or 0) if media['type']=='video' else 0
                end=float(data.get('end') or duration) if media['type']=='video' else 1
                interval=float(data.get('interval') or 1) if media['type']=='video' else 1
                if not 0<=start<end<=duration+.05 or not 0<interval<=5:raise ValueError('Choose a valid time range and interval up to 5 seconds')
                options={'start':start,'end':min(end,duration),'interval':interval}
                run,created=video_review.create_run(DB,mid,path_on_disk,options)
                if created:
                    rid=run['id'];jobs[rid]={'id':rid,'state':'queued','progress':0,'media_id':mid,'cancel':False}
                    threading.Thread(target=process_video_run,args=(rid,mid,path_on_disk,options),daemon=True).start()
                    return self.respond(jobs[rid])
                return self.respond({'id':run['id'],'state':run['status'],'reused':True})
            if path=="/api/video-import/correct":return self.respond(video_review.correction(DB,str(data.get('id') or ''),data.get('changes') or {}))
            if path=="/api/video-import/system-context":return self.respond(video_review.system_context(DB,str(data.get('run_id') or '')))
            if path=="/api/video-import/review-system":return self.respond(video_review.review_system(DB,str(data.get('run_id') or ''),
                data.get('mod_system'),data.get('review_token'),data.get('context_cues'),data.get('confirm') is True))
            if path=="/api/video-import/dismiss":return self.respond(video_review.dismiss(DB,str(data.get('id') or '')))
            if path=="/api/video-import/commit":return self.respond(video_review.commit(DB,str(data.get('id') or '')))
            if path=="/api/video-import/review-distinct-copy":return self.respond(video_review.review_distinct_copy(DB,str(data.get('id') or ''),data.get('reason')))
            if path=="/api/video-import/commit-checked-batch":return self.respond(video_review.commit_checked_batch(DB,str(data.get('run_id') or ''),data.get('plan_token'),data.get('defer_ids')))
            if path=="/api/video-import/undo-checked-batch":return self.respond(video_review.undo_checked_batch(DB,str(data.get('run_id') or ''),str(data.get('batch_id') or '')))
            if path=="/api/video-import/undo":return self.respond(video_review.undo(DB,str(data.get('id') or '')))
            if path=="/api/mod-evidence/preview":
                return self.respond(mod_evidence.preview(DB,DATA,data.get('proposal_id'),data.get('inventory_id')))
            if path=="/api/mod-evidence/apply":
                return self.respond(mod_evidence.apply(DB,DATA,data.get('proposal_id'),data.get('inventory_id'),
                                                       data.get('token'),data.get('confirm'),data.get('replace_existing')))
            if path=="/api/mod-evidence/undo":
                return self.respond(mod_evidence.undo(DB,data.get('inventory_id'),data.get('undo_id')))
            if path=="/api/process":
                mid=data.get("media_id")
                with connect() as c: exists=c.execute("SELECT 1 FROM media WHERE id=?",(mid,)).fetchone()
                if not exists: raise ValueError("Unknown media")
                jid=uuid.uuid4().hex; jobs[jid]={"id":jid,"state":"queued","progress":0,"media_id":mid,"cancel":False}
                threading.Thread(target=process,args=(jid,mid,data),daemon=True).start(); return self.respond(jobs[jid])
            if path=="/api/cancel": jobs[data["id"]]["cancel"]=True; return self.respond({"ok":True})
            if path=="/api/confirm":
                oid=data["observation_id"]
                with connect() as c:
                    obs=c.execute("SELECT * FROM observations WHERE id=?",(oid,)).fetchone()
                    if not obs: raise ValueError("Unknown observation")
                    item=data["item"]
                    catalog_id=item.get('catalog_id') or (item.get('effects') or {}).get('catalog_id')
                    if catalog_id:
                        observed=(json.loads(obs['fields'] or '{}').get('identification') or {})
                        if observed.get('ownership')=='locked' and observed.get('catalog_id')==catalog_id:raise ValueError('This frame shows a locked entry, not owned inventory')
                        item=enrich_catalog_item(item,catalog_id)
                    name=str(item.get("name","")).strip()
                    if not name: raise ValueError("Item name required")
                    iid=data.get("merge_id") or uuid.uuid4().hex
                    old=c.execute("SELECT * FROM inventory WHERE id=?",(iid,)).fetchone()
                    if old: c.execute("INSERT INTO undo(entity,entity_id,prior,created) VALUES(?,?,?,?)",("inventory",iid,json.dumps(dict(old)),now()))
                    else: c.execute("INSERT INTO undo(entity,entity_id,prior,created) VALUES(?,?,?,?)",("inventory",iid,"null",now()))
                    evidence=json.loads(old["evidence"] or "[]") if old else []
                    evidence.append({"observation_id":oid,"image":obs["image"],"timestamp":obs["timestamp"],"media_id":obs["media_id"]})
                    vals=(iid,name,item.get("kind","instance"),item.get("slot"),item.get("family"),item.get("variant"),item.get("level"),item.get("stars"),json.dumps(item.get("stats",{})),json.dumps(item.get("effects",{})),oid,json.dumps(evidence),now(),now(),0)
                    c.execute("REPLACE INTO inventory VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",vals)
                    c.execute("UPDATE observations SET state='confirmed' WHERE id=?",(oid,))
                return self.respond({"id":iid})
            if path=="/api/item":
                item=data
                catalog_id=item.get('catalog_id') or (item.get('effects') or {}).get('catalog_id')
                if catalog_id:item=enrich_catalog_item(item,catalog_id)
                name=str(item.get("name","")).strip()
                if not name: raise ValueError("Item name required")
                iid=item.get("id") or uuid.uuid4().hex
                with connect() as c:
                    old=c.execute("SELECT * FROM inventory WHERE id=?",(iid,)).fetchone()
                    c.execute("INSERT INTO undo(entity,entity_id,prior,created) VALUES(?,?,?,?)",("inventory",iid,json.dumps(dict(old)) if old else "null",now()))
                    evidence=json.loads(old["evidence"] or "[]") if old else []
                    vals=(iid,name,item.get("kind","instance"),item.get("slot"),item.get("family"),item.get("variant"),item.get("level"),item.get("stars"),json.dumps(item.get("stats",{})),json.dumps(item.get("effects",{})),old["source_observation"] if old else None,json.dumps(evidence),now(),now(),0)
                    c.execute("REPLACE INTO inventory VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",vals)
                return self.respond({"id":iid})
            if path=="/api/mod-collection/add":
                identity=str(data.get('catalog_id') or '')
                entry=catalog.ENTRIES.get(identity)
                if not entry or entry.get('kind')!='mod':raise ValueError('Choose a catalog mod')
                if entry.get('family_only'):raise ValueError('This mod family has no verified selectable variant yet')
                with connect() as c:
                    active=None;archived=None
                    for row in c.execute("SELECT * FROM inventory WHERE kind='mod_unlock' ORDER BY last_seen DESC"):
                        if json.loads(row['effects'] or '{}').get('catalog_id')!=identity:continue
                        if not row['archived']:
                            active=row;break
                        if archived is None and json.loads(row['stats'] or '{}').get('collection_entry'):
                            archived=row
                    if active:return self.respond({'id':active['id'],'created':False,'level':active['level']})
                    if archived:
                        c.execute("INSERT INTO undo(entity,entity_id,prior,created) VALUES(?,?,?,?)",('inventory',archived['id'],json.dumps(dict(archived)),now()))
                        c.execute('UPDATE inventory SET archived=0,last_seen=? WHERE id=?',(now(),archived['id']))
                        return self.respond({'id':archived['id'],'created':False,'restored':True,'level':archived['level']})
                    iid=uuid.uuid4().hex
                    resolved=catalog_item_data(identity,None)
                    stats={**resolved['stats'],'collection_entry':True}
                    vals=(iid,resolved['name'],'mod_unlock',resolved['slot'],None,resolved['variant'],None,None,
                          json.dumps(stats),json.dumps(resolved['effects']),None,'[]',now(),now(),0)
                    c.execute('INSERT INTO inventory VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',vals)
                    c.execute("INSERT INTO undo(entity,entity_id,prior,created) VALUES(?,?,?,?)",('inventory',iid,'null',now()))
                return self.respond({'id':iid,'created':True,'level':None})
            if path=="/api/mod-collection/level":
                iid=str(data.get('id') or '')
                raw=data.get('level')
                if isinstance(raw,bool):raise ValueError('Field Guide level must be a whole number or unknown')
                try:level=None if raw is None or raw=='' else int(raw)
                except (ValueError,TypeError):raise ValueError('Field Guide level must be a whole number or unknown') from None
                if level is not None and str(raw).strip() not in (str(level),):raise ValueError('Field Guide level must be a whole number or unknown')
                with connect() as c:
                    old=c.execute('SELECT * FROM inventory WHERE id=? AND kind=\'mod_unlock\' AND archived=0',(iid,)).fetchone()
                    if not old:raise ValueError('Recorded mod instance not found')
                    stats=json.loads(old['stats'] or '{}')
                    identity=json.loads(old['effects'] or '{}').get('catalog_id')
                    entry=catalog.ENTRIES.get(identity)
                    if not entry or entry.get('kind')!='mod':raise ValueError('Recorded mod identity is unavailable')
                    minimum,maximum=entry.get('valid_levels') or (1,17)
                    if level is not None and not minimum<=level<=maximum:
                        raise ValueError(f'Field Guide level must be {minimum}–{maximum} or unknown')
                    if (old['source_observation'] or stats.get('video_import') or stats.get('observed_attribute_lines')) and 'original_observed_level' not in stats:
                        stats['original_observed_level']=old['level']
                    if 'original_observed_level' in stats and isinstance(stats.get('typed_modifiers'),list):
                        stats.setdefault('source_observed_typed_modifiers',stats['typed_modifiers'])
                    if 'source_observed_typed_modifiers' in stats:
                        stats['typed_modifiers']=stats['source_observed_typed_modifiers'] if level==stats.get('original_observed_level') else []
                        stats['attribute_coverage']='source_level_mismatch' if level!=stats.get('original_observed_level') else 'source_level_restored'
                    stats['manual_level_override']=True
                    stats['manual_level_override_at']=now()
                    c.execute("INSERT INTO undo(entity,entity_id,prior,created) VALUES(?,?,?,?)",('inventory',iid,json.dumps(dict(old)),now()))
                    c.execute('UPDATE inventory SET level=?,stats=?,last_seen=? WHERE id=?',(level,json.dumps(stats),now(),iid))
                return self.respond({'id':iid,'level':level})
            if path=="/api/mod-collection/remove":
                iid=str(data.get('id') or '')
                with connect() as c:
                    old=c.execute('SELECT * FROM inventory WHERE id=? AND kind=\'mod_unlock\' AND archived=0',(iid,)).fetchone()
                    if not old or not json.loads(old['stats'] or '{}').get('collection_entry'):raise ValueError('Only a manually recorded mod can be removed here')
                    for saved in c.execute('SELECT item_ids FROM loadouts'):
                        if iid in json.loads(saved['item_ids']):raise ValueError('A saved loadout references this mod; remove it from that loadout first')
                    c.execute("INSERT INTO undo(entity,entity_id,prior,created) VALUES(?,?,?,?)",('inventory',iid,json.dumps(dict(old)),now()))
                    c.execute('UPDATE inventory SET archived=1,last_seen=? WHERE id=?',(now(),iid))
                return self.respond({'id':iid,'archived':True,'restorable':True})
            if path=="/api/my-gear/add":
                identity=data.get('catalog_id');entry=catalog.ENTRIES.get(identity)
                if not entry or entry['kind'] not in ('weapon','armor'):raise ValueError('Choose catalog equipment to add')
                slot=str(data.get('slot') or '')
                if slot not in BUILD_SLOTS:raise ValueError('Choose a compatible equipment slot')
                settings={key:data[key] for key in ('tier','stars','calibration_blueprint','calibration_bonus','calibration_profile','calibration_upgrade_level','accessories') if data.get(key) is not None}
                validate_planned_slots({slot:{'catalog_id':identity,**settings}})
                validate_owned_accessories(settings)
                weapon_stats=validate_weapon_stats(data.get('weapon_stats'),entry)
                record=catalog_item_data(identity)
                iid=uuid.uuid4().hex
                stats={**record['stats'],'craft_tier':settings.get('tier'),
                    'calibration_blueprint':settings.get('calibration_blueprint'),
                    'calibration_bonus':settings.get('calibration_bonus'),
                    'calibration_profile':settings.get('calibration_profile'),
                    'calibration_upgrade_level':settings.get('calibration_upgrade_level')}
                if settings.get('accessories'):stats['accessories']=settings['accessories']
                if weapon_stats:
                    stats['weapon_stats']=weapon_stats
                    stats['weapon_stats_context']=gear_measurement_context(identity,settings.get('stars'),stats)
                with connect() as c:
                    c.execute("INSERT INTO inventory VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (iid,entry.get('display_name') or entry['name'],'instance',entry.get('slot'),entry.get('family'),
                        entry.get('variant'),None,settings.get('stars'),json.dumps(stats),json.dumps(record['effects']),
                        None,'[]',now(),now(),0))
                    c.execute("INSERT INTO undo(entity,entity_id,prior,created) VALUES(?,?,?,?)",('inventory',iid,'null',now()))
                return self.respond({'id':iid})
            if path=="/api/my-gear/update":
                iid=str(data.get('id') or '')
                with connect() as c:
                    old=c.execute('SELECT * FROM inventory WHERE id=? AND archived=0',(iid,)).fetchone()
                    if not old:raise ValueError('My Gear item not found')
                    identity=json.loads(old['effects'] or '{}').get('catalog_id')
                    entry=catalog.ENTRIES.get(identity)
                    if not entry or entry['kind'] not in ('weapon','armor'):raise ValueError('This is not equipment in My Gear')
                    slot=str(data.get('slot') or '')
                    settings={key:data[key] for key in ('tier','stars','calibration_blueprint','calibration_bonus','calibration_profile','calibration_upgrade_level','accessories') if data.get(key) is not None}
                    validate_planned_slots({slot:{'catalog_id':identity,**settings}})
                    weapon_stats=validate_weapon_stats(data.get('weapon_stats'),entry) if 'weapon_stats' in data else None
                    stats=json.loads(old['stats'] or '{}')
                    if settings.get('accessories')!=(stats.get('accessories') or {}):validate_owned_accessories(settings)
                    for key,column in (('tier','craft_tier'),('calibration_blueprint','calibration_blueprint'),('calibration_bonus','calibration_bonus')):
                        if key in settings:stats[column]=settings[key]
                        else:stats.pop(column,None)
                    for key in ('calibration_profile','calibration_upgrade_level'):
                        if key in data:
                            if data[key] is None:stats.pop(key,None)
                            else:stats[key]=settings[key]
                    if 'accessories' in data:
                        if settings.get('accessories'):stats['accessories']=settings['accessories']
                        else:stats.pop('accessories',None)
                    context=gear_measurement_context(identity,settings.get('stars'),stats)
                    if 'weapon_stats' in data:
                        if weapon_stats:
                            stats['weapon_stats']=weapon_stats
                            stats['weapon_stats_context']=context
                        else:
                            stats.pop('weapon_stats',None)
                            stats.pop('weapon_stats_context',None)
                    elif stats.get('weapon_stats_context')!=context:
                        stats.pop('weapon_stats',None)
                        stats.pop('weapon_stats_context',None)
                    c.execute("INSERT INTO undo(entity,entity_id,prior,created) VALUES(?,?,?,?)",('inventory',iid,json.dumps(dict(old)),now()))
                    c.execute('UPDATE inventory SET stars=?,stats=?,last_seen=? WHERE id=?',(settings.get('stars'),json.dumps(stats),now(),iid))
                return self.respond({'id':iid})
            if path=="/api/my-gear/recycle":
                iid=str(data.get('id') or '')
                with connect() as c:
                    old=c.execute('SELECT * FROM inventory WHERE id=? AND archived=0',(iid,)).fetchone()
                    if not old:raise ValueError('My Gear item not found')
                    identity=json.loads(old['effects'] or '{}').get('catalog_id')
                    if catalog.ENTRIES.get(identity,{}).get('kind') not in ('weapon','armor'):raise ValueError('This is not equipment in My Gear')
                    c.execute("INSERT INTO undo(entity,entity_id,prior,created) VALUES(?,?,?,?)",('inventory',iid,json.dumps(dict(old)),now()))
                    c.execute('UPDATE inventory SET archived=1 WHERE id=?',(iid,))
                return self.respond({'ok':True})
            if path=="/api/archive":
                with connect() as c:
                    old=c.execute("SELECT * FROM inventory WHERE id=?",(data["id"],)).fetchone()
                    if not old: raise ValueError("Unknown item")
                    c.execute("INSERT INTO undo(entity,entity_id,prior,created) VALUES(?,?,?,?)",("inventory",data["id"],json.dumps(dict(old)),now()))
                    c.execute("UPDATE inventory SET archived=1 WHERE id=?",(data["id"],))
                return self.respond({"ok":True})
            if path=="/api/undo":
                with connect() as c:
                    entry=c.execute("SELECT * FROM undo ORDER BY id DESC LIMIT 1").fetchone()
                    if not entry: return self.respond({"ok":False})
                    prior=json.loads(entry["prior"])
                    if prior is None: c.execute("DELETE FROM inventory WHERE id=?",(entry["entity_id"],))
                    else:
                        cols=list(prior); c.execute(f"REPLACE INTO inventory({','.join(cols)}) VALUES({','.join('?'*len(cols))})",list(prior.values()))
                    c.execute("DELETE FROM undo WHERE id=?",(entry["id"],))
                return self.respond({"ok":True})
            if path=="/api/loadout":
                iid=data.get("id") or uuid.uuid4().hex; ids=list(dict.fromkeys(map(str,data.get("item_ids",[]))))
                chosen=[i for i in inventory() if i["id"] in ids]
                if len(chosen)!=len(ids): raise ValueError("Loadout contains unknown items")
                issues=engine.validate_loadout(chosen)
                if issues: raise ValueError("; ".join(issues))
                with connect() as c: c.execute("REPLACE INTO loadouts VALUES(?,?,?,?,COALESCE((SELECT created FROM loadouts WHERE id=?),?),?)",(iid,data.get("name") or "Untitled build",json.dumps(ids),data.get("notes",""),iid,now(),now()))
                return self.respond({"id":iid})
            if path=="/api/planned-build":
                slots=validate_planned_slots(data.get('slots') or {})
                name=str(data.get('name') or '').strip()
                if not name:raise ValueError('Build name required')
                identity=str(data.get('id') or uuid.uuid4().hex)
                with connect() as c:
                    existing=c.execute('SELECT 1 FROM planned_builds WHERE id=?',(identity,)).fetchone()
                    c.execute('REPLACE INTO planned_builds VALUES(?,?,?,?,COALESCE((SELECT created FROM planned_builds WHERE id=?),?),?)',(identity,name,json.dumps(slots),str(data.get('notes') or ''),identity,now(),now()))
                return self.respond({'id':identity,'updated':bool(existing)})
            if path=="/api/planned-analysis":
                slots=validate_planned_slots(data.get('slots') or {},allow_sourced_invalid_stars=True)
                result=planned_advisor.analyze(slots,data.get('assumptions') or {})
                with connect() as c:
                    result['selected_mod_source_rows']=build_source_rows.selected_rows(slots,c,inventory())
                return self.respond(result)
            if path=="/api/build-timed-readout":
                import build_timed_readout
                slots=validate_planned_slots(data.get('slots') or {})
                return self.respond(build_timed_readout.evaluate(
                    slots,data.get('reference') or {},data.get('timed') or {}))
            if path=="/api/mod-guidance":
                slots=validate_planned_slots(data.get('slots') or {})
                return self.respond(mod_guidance.suggest(catalog,inventory(),data.get('goal'),data.get('weapon_id'),slots,data.get('weapon_slot','primary')))
            if path=="/api/planned-compare":
                builds={row['id']:row for row in planned_builds()}
                left=builds.get(str(data.get('left_id') or ''))
                right=builds.get(str(data.get('right_id') or ''))
                if not left or not right:raise ValueError('Save both planned builds before comparing')
                if left['id']==right['id']:raise ValueError('Choose two different saved builds')
                validate_planned_slots(left['slots']);validate_planned_slots(right['slots'])
                result=planned_advisor.compare(left['slots'],right['slots'],data.get('assumptions') or {},data.get('outgoing_inputs'))
                result['builds']={'left':{'id':left['id'],'name':left['name']},'right':{'id':right['id'],'name':right['name']}}
                return self.respond(result)
            if path=="/api/accessory-ownership":
                identity=data.get('accessory_id');status=data.get('status')
                if identity not in accessories.ITEMS:raise ValueError('Unknown accessory')
                if status not in ('unlocked','unknown'):raise ValueError('Invalid accessory status')
                with connect() as c:
                    c.execute('REPLACE INTO catalog_ownership VALUES(?,?,?,?,?)',
                              (identity,status,None,now(),'manual accessory declaration'))
                return self.respond({'accessory_id':identity,'status':status})
            if path=="/api/catalog-ownership":
                identity=data.get('catalog_id');status=data.get('status')
                if identity not in catalog.ENTRIES or catalog.ENTRIES[identity]['kind'] not in ('mod','weapon','armor'):raise ValueError('Unknown catalog item')
                if catalog.ENTRIES[identity].get('family_only'):raise ValueError('This mod family has no verified selectable variant yet')
                if status not in ('unlocked','locked','unknown'):raise ValueError('Invalid ownership state')
                level=data.get('available_level')
                if level is not None and (not isinstance(level,int) or level<1 or level>(17 if catalog.ENTRIES[identity]['kind']=='mod' else 100)):raise ValueError('Invalid available level')
                if status!='unlocked':level=None
                with connect() as c:c.execute('REPLACE INTO catalog_ownership VALUES(?,?,?,?,?)',(identity,status,level,now(),'manual declaration'))
                return self.respond({'catalog_id':identity,'status':status,'available_level':level})
            if path=="/api/compare": return self.respond(engine.compare(loadouts(),inventory(),data,measurements()))
            if path=="/api/component-compare":
                import component_compare
                return self.respond(component_compare.compare(data.get('left'),data.get('right'),data.get('context'),data.get('runs')))
            if path=="/api/weapon-timeline-simulate":
                import weapon_timeline_api
                return self.respond(weapon_timeline_api.simulate(data))
            if path=="/api/mod-stateful-simulate":
                import mod_stateful_api
                return self.respond(mod_stateful_api.simulate(data))
            if path=="/api/component-compare-structured":
                import structured_compare
                return self.respond(structured_compare.compare(data,planned_builds()))
            if path=="/api/published-reference-compare":
                import published_reference_model
                return self.respond(published_reference_model.compare(data))
            if path=="/api/compare-selections":
                by_id={str(item['id']):item for item in inventory()}
                left=by_id.get(str(data.get('left_id')));right=by_id.get(str(data.get('right_id')))
                if not left or not right:raise ValueError('Select two confirmed inventory entries')
                return self.respond(engine.compare_catalog_selections(left,right,data.get('assumptions') or {}))
            if path=="/api/compare-catalog-selections":
                choices=[]
                for side in ('left','right'):
                    choice=data.get(side) or {}
                    item=catalog_item_data(choice['catalog_id'],int(choice['level']))
                    item['id']='catalog-example-'+side
                    choices.append(item)
                result=engine.compare_catalog_selections(*choices,data.get('assumptions') or {})
                result['selection_origin']='catalog example; ownership not asserted or saved'
                return self.respond(result)
            if path=="/api/outgoing-example":
                return self.respond(outgoing.run_example(data))
            if path=="/api/optimize": return self.respond(engine.optimize(inventory(),data.get("locked",[]),data.get("excluded",[]),data.get("assumptions",{})))
            if path=="/api/search": return self.respond(engine.search_loadouts(inventory(),data.get("locked",[]),data.get("excluded",[]),data.get("assumptions",{})))
            if path=="/api/measurement":
                build=next((b for b in loadouts() if b["id"]==data.get("build_id")),None)
                if not build:raise ValueError("Unknown build")
                target=str(data.get("target") or "").strip()
                if not target:raise ValueError("Target required for combat measurement")
                normal=float(data.get("normal_hit"))
                if normal<=0:raise ValueError("Normal hit must be positive")
                values=[]
                for key in ("crit_hit_damage","weakspot_hit_damage","crit_weakspot_hit_damage"):
                    value=data.get(key)
                    values.append(float(value) if value not in (None,"") else None)
                if any(v is not None and v<=0 for v in values):raise ValueError("Hit values must be positive")
                rpm=float(data.get("rpm"));magazine=int(data.get("magazine"));reload_seconds=float(data.get("reload_seconds"))
                if rpm<=0 or magazine<=0 or reload_seconds<0:raise ValueError("Measured timing values outside valid range")
                oid=data.get("source_observation") or None
                if oid and not any(o["id"]==oid for o in observations()):raise ValueError("Unknown source observation")
                mid=uuid.uuid4().hex
                by_id={i["id"]:i for i in inventory()}
                if any(item_id not in by_id for item_id in build["item_ids"]):raise ValueError("Build includes an unavailable item")
                fingerprint=engine.loadout_fingerprint([by_id[item_id] for item_id in build["item_ids"]])
                with connect() as c:c.execute("INSERT INTO measurements VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(mid,build["id"],json.dumps(build["item_ids"]),target,str(data.get("buffs") or ""),str(data.get("conditions") or ""),str(data.get("scenario") or "PvE"),normal,*values,rpm,magazine,reload_seconds,oid,str(data.get("note") or ""),now(),fingerprint))
                return self.respond({"id":mid})
            if path=="/api/preview-upgrade":
                build=next((b for b in loadouts() if b["id"]==data.get("build_id")),None)
                if not build:raise ValueError("Unknown build")
                return self.respond(engine.preview_upgrade(build,inventory(),data.get("item_id"),data.get("proposed_stats",{}),data.get("assumptions",{})))
            if path=="/api/build-gaps":
                build=next((b for b in loadouts() if b["id"]==data.get("build_id")),None)
                if not build:raise ValueError("Unknown build")
                return self.respond({"build_id":build["id"],"gaps":engine.build_gaps(build,inventory(),KNOWLEDGE.get("catalog",[]))})
            if path=="/api/upgrade":
                build=next((b for b in loadouts() if b["id"]==data.get("build_id")),None)
                if not build:raise ValueError("Unknown build")
                proposed=data.get("proposed_stats") or {}
                if not isinstance(proposed,dict):raise ValueError("Invalid proposed stats")
                target_name=data.get("target_name")
                if target_name:
                    gap=next((g for g in engine.build_gaps(build,inventory(),KNOWLEDGE.get("catalog",[])) if g["name"]==target_name),None)
                    if not gap:raise ValueError("Target is not a sourced gap for this build")
                    item_id="";title=data.get("title") or target_name;acquisition=gap.get("acquisition");source_id=gap["source"]
                    source_url=next((s["url"] for s in KNOWLEDGE["sources"] if s["id"]==source_id),None)
                else:
                    item_id=data.get("item_id")
                    if item_id not in build["item_ids"]:raise ValueError("Upgrade must target an item in the selected build")
                    if not proposed:raise ValueError("Proposed stats required")
                    title=data.get("title") or "Planned upgrade";acquisition=data.get("acquisition");source_url=data.get("source_url")
                uid=uuid.uuid4().hex
                with connect() as c:c.execute("INSERT INTO upgrades VALUES(?,?,?,?,?,?,?,?,?,?)",(uid,build["id"],item_id,title,json.dumps(proposed),json.dumps(data.get("cost") or {}),acquisition,source_url,"planned",now()))
                return self.respond({"id":uid})
            if path=="/api/activity":
                target=data.get("target_id")
                if not any(u["id"]==target for u in upgrades()):raise ValueError("Activity must target a planned upgrade")
                with connect() as c: c.execute("INSERT INTO activities(id,name,minutes,source_url,notes,created,target_id) VALUES(?,?,?,?,?,?,?)",(uuid.uuid4().hex,data["name"],float(data["minutes"]),data.get("source_url"),data.get("notes"),now(),target))
                return self.respond({"ok":True})
            if path=="/api/session-plan":
                targets={u["id"] for u in upgrades() if u["build_id"]==data.get("build_id") and u["status"]=="planned"}
                return self.respond(engine.plan_session(rows("activities"),targets,data.get("minutes",45)))
            if path=="/api/revision":
                with connect() as c: c.execute("INSERT INTO revisions VALUES(?,?,?,?,?)",(uuid.uuid4().hex,data["title"],data.get("source_url"),json.dumps(data.get("affected",[])),now()))
                return self.respond({"ok":True})
            if path=="/api/restore": restore(data); return self.respond({"ok":True})
            return self.respond({"error":"Not found"},404)
        except Exception as e: return self.respond({"error":str(e)},400)

if __name__=="__main__":
    a=argparse.ArgumentParser(); a.add_argument("--host",default="127.0.0.1"); a.add_argument("--port",type=int,default=8765); args=a.parse_args()
    init()
    def _warm():  # build the top-10 ladder in the background so the first answer is fast
        try:
            import forge; forge.startup()
            forge.optimize(forge.load_profile())  # the main page needs this first
            import forge_theory
            for sc in ("boss","abyss"): forge_theory.theory(sc)
        except Exception as e: print("ladder warmup failed:",e,flush=True)
    threading.Thread(target=_warm,daemon=True).start()
    try:
        import forge_appupdate; forge_appupdate.check_soon()  # asks GitHub once whether a newer version exists
    except Exception as e: print("update check skipped:",e,flush=True)
    server=ThreadingHTTPServer((args.host,args.port),Handler); print(f"Deviant Forge at http://{args.host}:{args.port}",flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
