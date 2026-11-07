"""Promote exact public/native identity links, never a weapon damage equation.

The title packet is a frozen source transcription. The native fields come only
from the separately hash-checked, byte-validated partial intake. A public Max
Stars page is a configuration limit; it does not fill a missing native row.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import native_partial_intake

ROOT = Path(__file__).parent / 'evidence_packets'
PROPOSED = ROOT / 'native-proposed-crosswalk-v1.json'
TITLES = ROOT / 'native-remaining-public-titles-v1.json'
NATIVE95 = ROOT / 'native-recovered-95-v1.json'
MAXIMA = ROOT / 'native-crosswalk-max-stars-v1.json'
PINNED_SHA256 = {
    'proposed':'9acd6051b79b569424e7a3e6061c6f3ae290242af929e69a79fb42feff8aebd1',
    'titles':'1e7a80f15a5f3b035eeca7365408efb75bc58120bdd25b4d844d3a3e2f15c3ee',
    'native95':'762247b96331af37e3fa47d3c94386b8d75afcabf02c8c864244f504bc35a226',
    'maxima':'1e8466b1d4a9683f50ecc256492666f5d72613b3a5c88dfce81243bf613e9ba4'}
PROPOSAL_KINDS = {'proposed_exact_public_blueprint_title',
                  'proposed_exact_gear_title_with_blueprint_alias'}


def validate(proposed:dict, titles:dict, native95:dict, maxima:dict,
             entries:dict, partial:dict, installed_ids:set[str]) -> dict:
    if (proposed.get('schema_version') != 1 or titles.get('schema_version') != 1 or
            native95.get('schema_version') != 1 or maxima.get('schema_version') != 1 or
            proposed.get('source_sha256',{}).get('remaining_public_titles') !=
            hashlib.sha256((json.dumps(titles,indent=2)+'\n').encode()).hexdigest() or
            proposed['source_sha256']['native_95'] !=
            hashlib.sha256((json.dumps(native95,indent=2)+'\n').encode()).hexdigest() or
            titles.get('native_source_sha256') !=
            proposed['source_sha256']['native_95']):
        raise ValueError('Frozen public/native crosswalk provenance conflict')
    rows=proposed.get('rows',[])
    weapon_ids={i for i,e in entries.items() if e['kind']=='weapon'}
    by_id={r['forge_id']:r for r in rows}
    if (len(rows)!=138 or len(by_id)!=138 or set(by_id)!=weapon_ids or
            proposed.get('coverage',{}).get('new_exact_blueprint_title_proposals')!=41 or
            proposed['coverage'].get('new_exact_gear_title_alias_proposals')!=2):
        raise ValueError('Frozen 138-weapon proposed classification changed')
    public={r['blueprint_id']:r for r in titles.get('records',[])}
    raw95={r['blueprint_id']:r for r in native95.get('samples',[])}
    star_pages={r['blueprint_id']:r for r in maxima.get('records',[])}
    if (len(public)!=59 or len(raw95)!=95 or len(star_pages)!=40 or
            len(titles['records'])!=59 or len(maxima['records'])!=40):
        raise ValueError('Frozen source title, native or Max Stars row count changed')
    if (native95.get('coverage') != {'blueprints':95,'tier_attack_rows':475,
                                    'star_ratio_rows':440} or
            titles.get('coverage',{}).get('exact_public_blueprint_titles')!=58):
        raise ValueError('Frozen native/public coverage changed')
    new, used_bp, skipped = {}, set(), {}
    for identity,row in by_id.items():
        classification=row['classification']
        if classification not in PROPOSAL_KINDS:
            continue
        bp=row['proposed_blueprint_id']
        if bp in used_bp or bp not in partial['by_blueprint'] or bp not in public or bp not in raw95:
            raise ValueError('Proposed blueprint is duplicate or not byte-validated')
        used_bp.add(bp)
        source=public[bp]
        native=partial['by_blueprint'][bp]
        raw=raw95[bp]
        if (entries[identity]['name']!=row['forge_name'] or
                row['proposed_tier_one_gear_id']!=native['tier_one_gear_id'] or
                source['tier_one_gear_id_from_native_bytes']!=native['tier_one_gear_id'] or
                raw['tier_one_gear_id']!=native['tier_one_gear_id'] or
                row['source_blueprint_title']!=source['public_blueprint_title'] or
                source['source_blueprint_url']!=f'https://oncehuman.th.gl/db/blueprints/{bp}' or
                source['stored_star_row_count']!=native['stored_star_count'] or
                len(raw['tiers'])!=5 or len(raw['star_ratios'])!=native['stored_star_count'] or
                any(r['gear_id']!=native['tiers'][r['tier']]['gear_id'] or
                    r['gun_preset_attack']['value']!=native['tiers'][r['tier']]['gun_preset_attack']
                    for r in raw['tiers']) or
                any(r['value']!=native['stars'][r['star']]['preset_attack_radio']
                    for r in raw['star_ratios'])):
            raise ValueError('Proposed identity or native field differs from frozen source')
        if identity in installed_ids:
            # R500 and Goshawk were installed before this proposed packet.
            if (identity not in {'weapon:r500','weapon:de-50-goshawk'} or
                    partial['by_catalog'][identity]['blueprint_id']!=bp):
                raise ValueError('Proposed identity conflicts with installed catalog link')
            continue
        if bp==13351101:
            # Exact cited page returned HTTP 404 on independent 2026-11-02 check.
            skipped[identity]='cited_exact_blueprint_page_http_404; source title unconfirmed independently'
            continue
        page=star_pages.get(bp)
        if (source['blueprint_title_status']!='exact public page title' or not page or
                page['source_url']!=source['source_blueprint_url'] or
                page['public_blueprint_title']!=source['public_blueprint_title'] or
                not native['stored_star_count']<=page['published_max_stars']<=6):
            raise ValueError('Proposed blueprint title or published Max Stars conflict')
        if classification=='proposed_exact_public_blueprint_title':
            if (row['forge_name']+' B.P.'!=source['public_blueprint_title'] or
                    row['source_identity_url']!=source['source_blueprint_url']):
                raise ValueError('Public blueprint title does not exactly name catalog weapon')
            proof='exact_public_blueprint_title_and_native_mapping'
        else:
            gear_title=source.get('public_tier_one_gear_title')
            gear_url=source.get('direct_gear_url')
            if (gear_title!=row['forge_name']+' (Tier 1)' or
                    gear_title!=row.get('source_tier_one_gear_title') or
                    gear_url!=f'https://oncehuman.th.gl/db/gear/{native["tier_one_gear_id"]}' or
                    row['source_identity_url']!=gear_url or
                    source['public_blueprint_title']==row['forge_name']+' B.P.'):
                raise ValueError('Tier I gear alias lacks exact source identity')
            proof='exact_public_tier_one_gear_title_and_native_mapping'
        new[identity]={**native,'catalog_id':identity,
            'public_blueprint_title':source['public_blueprint_title'],
            'public_blueprint_url':source['source_blueprint_url'],
            'public_tier_one_gear_title':source.get('public_tier_one_gear_title'),
            'public_tier_one_gear_url':source.get('direct_gear_url'),
            'published_max_stars':page['published_max_stars'],
            'identity_proof':proof,'source_access_date':source['access_date'],
            'source_game_build':source['source_build']}
    if (len(used_bp)!=43 or len(new)!=40 or skipped!={'weapon:nail-gun':
            'cited_exact_blueprint_page_http_404; source title unconfirmed independently'}):
        raise ValueError('Frozen proposal acceptance/withhold counts changed')
    return {'schema_version':1,'steam_build_id':partial['steam_build_id'],
        'by_catalog':new,'withheld':skipped,
        'counts':{'proposed':43,'previously_installed':2,
                  'new_exact_blueprint_titles':38,'new_exact_gear_title_aliases':2,
                  'new_accepted_catalog_links':40,'new_withheld':1,
                  'new_tier_attack_fields':0,'new_star_ratio_fields':0,
                  'new_formula_ready_fields':0},
        'scope':'Identity links and source-backed star maxima; native fields already validated, final damage remains unknown'}


def load_current(entries:dict, partial:dict, installed_ids:set[str])->dict:
    data={}
    for key,path in (('proposed',PROPOSED),('titles',TITLES),
                     ('native95',NATIVE95),('maxima',MAXIMA)):
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=PINNED_SHA256[key]:
            raise ValueError(f'{key}: frozen source artifact hash changed')
        data[key]=json.loads(raw)
    return validate(data['proposed'],data['titles'],data['native95'],
                    data['maxima'],entries,partial,installed_ids)


def selected(report:dict,catalog_id:str,tier:int|None,stars:int|None):
    return native_partial_intake.selected(report,catalog_id,tier,stars)
