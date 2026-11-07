"""Blueprint-linked item/tier/star display values, separate from imported damage."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

import catalog
import source_intake

PACKET = json.loads((Path(__file__).parent / 'evidence_packets/weapon-item-tier-pages-v1.json').read_text())
ROWS = PACKET['rows']
AUG_RAW_SAMPLE = json.loads((Path(__file__).parent /
    'evidence_packets/aug-raw-page-sample-v1.json').read_text())
TIER1_RAW_BATCH = json.loads((Path(__file__).parent /
    'evidence_packets/five-weapon-tier1-raw-v1.json').read_text())
LOCAL_IDENTITY_SAMPLE = json.loads((Path(__file__).parent /
    'evidence_packets/local-blueprint-identity-v1.json').read_text())


def validate_packet(packet):
    """Reject mixed item identities, forged URL/ID joins and conflicting cells."""
    seen = set()
    for catalog_id,row in packet['rows'].items():
        entry = catalog.ENTRIES.get(catalog_id)
        if not entry or entry['kind'] != 'weapon':
            raise ValueError(f'{catalog_id}: unknown weapon identity')
        if set(row['tiers']) != {'1','2','3','4','5'}:
            raise ValueError(f'{catalog_id}: expected five explicitly sourced tiers')
        if set(row['blueprint_craft_item_ids']) != {tier['item_id'] for tier in row['tiers'].values()}:
            raise ValueError(f'{catalog_id}: tier item not in named blueprint Crafts links')
        if not row['blueprint_url'].endswith('/'+row['blueprint_id']):
            raise ValueError(f'{catalog_id}: blueprint URL/ID conflict')
        calibration_context = row.get('calibration_context') or {}
        if calibration_context.get('legacy_level') == 'removed_before_weapon_release' and not (
                calibration_context.get('official_removal_source','').startswith('https://www.oncehuman.game/news/update/20260121/') and
                calibration_context.get('official_weapon_release_source','').startswith('https://www.oncehuman.game/m/news/official/20260513/')):
            raise ValueError(f'{catalog_id}: calibration chronology lacks its official sources')
        for level,item in row['tiers'].items():
            item_id = item['item_id']
            if item_id in seen:
                raise ValueError(f'{catalog_id}: tier item ID reused across weapon identities')
            seen.add(item_id)
            if item['page_title'] != f"{row['name']} (Tier {level})":
                raise ValueError(f'{catalog_id}: item page title conflicts with named weapon/tier')
            for key in ('wikily_url','thgl_gear_url'):
                if not urlparse(item[key]).path.endswith('/'+item_id):
                    raise ValueError(f'{catalog_id}: {key} conflicts with item ID')
            stars=item['star_damage']
            if not stars or stars.get('1') != item['damage']:
                raise ValueError(f'{catalog_id}: one-star damage conflict')
            if any(not str(star).isdigit() or not 1 <= int(star) <= 6 or
                   isinstance(value,bool) or not isinstance(value,(int,float)) or value <= 0
                   for star,value in stars.items()):
                raise ValueError(f'{catalog_id}: invalid sourced star damage')
    return {'identities':len(packet['rows']),'tier_rows':len(seen),
            'star_cells':sum(len(tier['star_damage']) for row in packet['rows'].values()
                              for tier in row['tiers'].values())}


VALIDATION=validate_packet(PACKET)


def validate_aug_raw_sample(sample=AUG_RAW_SAMPLE, rows=ROWS):
    """Bind independently captured source labels to the exact AUG item pages.

    This checks the sampled pages only. DMG remains a displayed unit; Reload
    Speed 47 is a score, not seconds or a crafted-weapon reload time.
    """
    row=rows['weapon:aug-electron-cloud']
    identity=sample['identity']
    if identity['blueprint_id'] != row['blueprint_id'] or \
            identity['raw_blueprint_title'] != row['name'] + ' B.P.':
        raise ValueError('AUG raw blueprint identity conflicts with active item pages')
    linked={entry['gear_id'] for entry in identity['crafts_links_checked']}
    checked=[]
    for page in sample['gear_pages']:
        tier=str(page['tier'])
        expected=row['tiers'].get(tier)
        if expected is None or page['gear_id'] != expected['item_id'] or \
                page['gear_id'] not in linked or page['raw_title'] != expected['page_title'] or \
                page['url'] != expected['thgl_gear_url']:
            raise ValueError('AUG raw gear page is not the named blueprint/tier item')
        fields={field['label']:field['raw_value'] for field in page['raw_fields']}
        if fields.get('DMG') != str(expected['damage']) or \
                {star+'★':str(value) for star,value in expected['star_damage'].items()} != page['raw_star_values']:
            raise ValueError('AUG raw DMG/star values conflict with active item cells')
        if fields.get('Fire Rate') != str(row['rpm_reference']) or \
                fields.get('Magazine Capacity') != str(row['magazine_reference']):
            raise ValueError('AUG raw timing labels conflict with active reference')
        if fields.get('Reload Speed') != '47':
            raise ValueError('AUG raw Reload Speed source label changed')
        checked.append(page['gear_id'])
    return {'sampled_gear_pages':checked, 'source_native_damage_cells':sum(
        len(page['raw_star_values']) for page in sample['gear_pages']),
        'reload_seconds_supported':False, 'damage_per_projectile_supported':False}


AUG_RAW_VALIDATION=validate_aug_raw_sample()


def validate_tier1_raw_batch(batch=TIER1_RAW_BATCH, rows=ROWS):
    """Check captured labels and IDs before accepting Tier 1 source cells."""
    checked=set()
    for source in batch['rows']:
        identity=source['catalog_id']
        if identity in checked or identity not in rows:
            raise ValueError('Duplicate or unknown Tier 1 weapon source identity')
        checked.add(identity)
        row=rows[identity]
        item=row['tiers']['1']
        blueprint_title=('QBJ97 - Fiery Trees and Silver Flowers B.P.'
                         if identity == 'weapon:qbj97-fiery-trees-and-silver-flowers'
                         else row['name']+' B.P.')
        if (source['tier'] != 1 or source['blueprint_id'] != row['blueprint_id'] or
                source['blueprint_title'] != blueprint_title or
                source['gear_id'] != item['item_id'] or
                source['gear_title'] != item['page_title'] or
                source['gear_url'] != item['thgl_gear_url'] or
                source['raw_star_table_label'] != 'DMG per star'):
            raise ValueError(f'{identity}: Tier 1 source identity or label conflict')
        fields=source['raw_fields']
        if (fields.get('DMG') != str(item['damage']) or
                fields.get('Fire Rate') != str(row['rpm_reference']) or
                fields.get('Magazine Capacity') != str(row['magazine_reference']) or
                source['raw_star_damage'] != {
                    star+'★':str(value) for star,value in item['star_damage'].items()}):
            raise ValueError(f'{identity}: Tier 1 source stat or star-cell conflict')
        if not fields.get('Reload Speed'):
            raise ValueError(f'{identity}: raw reload score label missing')
    if checked != set(rows):
        raise ValueError('Tier 1 batch does not cover each named item family once')
    return {'named_tier1_families':len(checked), 'source_native_star_cells':sum(
        len(source['raw_star_damage']) for source in batch['rows']),
        'reload_seconds_supported':False, 'per_projectile_unit_supported':False}


TIER1_RAW_VALIDATION=validate_tier1_raw_batch()
TIER1_INTAKE = source_intake.intake_tier1(
    TIER1_RAW_BATCH, ROWS,
    archive_sha256=hashlib.sha256((Path(__file__).parent /
        'evidence_packets/five-weapon-tier1-raw-v1.json').read_bytes()).hexdigest(),
    local_identity=LOCAL_IDENTITY_SAMPLE)
TIER1_TIMING = {
    identity: {record['field']: record for record in TIER1_INTAKE['accepted']
               if record['catalog_id'] == identity}
    for identity in ROWS
}
TIER1_CONDITIONAL_TIMING = {
    identity: {record['field']: record for record in TIER1_INTAKE['conditional']
               if record['catalog_id'] == identity}
    for identity in ROWS
}


def lookup(catalog_id, tier, *, stars=1):
    if catalog_id not in catalog.ENTRIES or catalog.ENTRIES[catalog_id]['kind'] != 'weapon':
        raise ValueError('Choose an exact catalog weapon identity')
    if isinstance(tier,bool) or not isinstance(tier,int) or not 1 <= tier <= 5:
        raise ValueError('Tier must be an integer 1–5')
    if isinstance(stars,bool) or not isinstance(stars,int) or not 1 <= stars <= 6:
        raise ValueError('Stars must be an integer 1–6')
    row = ROWS.get(catalog_id)
    source = (row or {}).get('tiers',{}).get(str(tier))
    value = (source or {}).get('star_damage',{}).get(str(stars))
    if value is None:
        return {'catalog_id':catalog_id,'tier':tier,'stars':stars,'displayed_damage':None,
                'status':'item_tier_or_star_unavailable','source_url':None,
                'unresolved':['No exact identity/tier/star damage cell is bound; do not interpolate neighboring tiers or stars']}
    calibration_note = ('Classic calibration levels were removed before this weapon released; selected calibration blueprint attributes are separate inputs'
                        if row.get('calibration_context',{}).get('legacy_level') == 'removed_before_weapon_release'
                        else 'Calibration basis unspecified')
    return {'catalog_id':catalog_id,'tier':tier,'stars':stars,'item_id':source['item_id'],
            'blueprint_id':row['blueprint_id'],'displayed_damage':value,
            'status':'community_named_item_tier_star_exact',
            'source_url':source['thgl_gear_url'] if stars>1 else source['wikily_url'],
            'corroborating_source_url':source['wikily_url'] if stars>1 else source['thgl_gear_url'],
            'source_title':source['page_title'],
            'calibration_context':row.get('calibration_context'),
            'unresolved':[calibration_note,'Damage per projectile unspecified',
                          'Reload seconds and effect interactions remain separate']}


def explicit_page_scenario(catalog_id, tier, *, stars=1, projectiles_per_shot,
                           reload_seconds=None, assume_fire_rate_as_rpm=False):
    """Use exact displayed damage in a caller-named projectile-unit hypothesis."""
    page = lookup(catalog_id,tier,stars=stars)
    if page['displayed_damage'] is None:
        raise ValueError('Chosen identity/tier/star has no exact item page damage')
    if isinstance(projectiles_per_shot,bool) or not isinstance(projectiles_per_shot,int) or not 1 <= projectiles_per_shot <= 100:
        raise ValueError('Enter an explicit whole projectile count from 1–100')
    if reload_seconds is not None:
        if isinstance(reload_seconds,bool) or not isinstance(reload_seconds,(int,float)) or not 0 < reload_seconds <= 120:
            raise ValueError('Entered reload seconds must be positive and at most 120')
    meta = ROWS[catalog_id]
    timing = TIER1_TIMING.get(catalog_id, {}) if tier == 1 else {}
    conditional_timing = TIER1_CONDITIONAL_TIMING.get(catalog_id, {}) if tier == 1 else {}
    if tier == 1 and 'fire_rate_rpm' not in timing:
        if not conditional_timing or assume_fire_rate_as_rpm is not True:
            raise ValueError('This item page says Fire Rate without an RPM unit; choose the explicit Fire Rate-as-RPM hypothesis or enter current RPM')
        timing = {**timing, **conditional_timing}
    stats = {'damage_per_projectile':page['displayed_damage'],
             'projectiles_per_shot':projectiles_per_shot,
             'fire_rate':timing['fire_rate_rpm']['value'] if timing else meta['rpm_reference'],
             'magazine_capacity':timing['magazine_capacity']['value'] if timing else meta['magazine_reference'],
             'reload_time_seconds':reload_seconds,
             'crit_rate_percent':None,'crit_damage_percent':None,'weakspot_damage_percent':None}
    baseline = {'weapon_id':catalog_id,'canonical_catalog_id':catalog_id,
                'evidence':'explicit_item_page_damage_unit_hypothesis',
                'source_url':page['source_url'],'source_item_id':page['item_id'],
                'source_blueprint_id':page['blueprint_id'],
                'source_timing':timing or None,
                'stats':stats,'name':meta['name']}
    calibration_note = ('Classic calibration level removed before this weapon release; selected calibration blueprint attributes are not included'
                        if meta.get('calibration_context',{}).get('legacy_level') == 'removed_before_weapon_release'
                        else 'Item page does not establish calibration scaling')
    scaled = {'weapon_id':catalog_id,'stars':stars,'tier':tier,'calibration':None,
              'stats':dict(stats),'damage_multiplier':None,
              'model':'exact_item_tier_star_display_under_explicit_per_projectile_hypothesis',
              'source_url':page['source_url'],
              'calibration_context':meta.get('calibration_context'),
              'unresolved':[calibration_note,
                            'Item page does not establish per-projectile damage unit; displayed damage is treated as per projectile only by explicit caller hypothesis'] +
                            (['Item page lacks an explicit RPM unit; Fire Rate is treated as RPM only by explicit caller hypothesis']
                             if conditional_timing and tier == 1 else [])}
    return baseline,scaled
