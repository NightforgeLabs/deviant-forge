"""Independently checked v2 identity links; never infer weapon damage."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import native_partial_intake
import native_tier_star as native

ROOT = Path(__file__).parent / 'evidence_packets'
SOURCES = {
    'proposal': ('native-crosswalk-v2-proposals.json', '2ac4e14c5121aa94fec09c3d7fcc82a50c34db453cfc54cddd5ab239b7973746'),
    'native': ('native-133-field-coverage.json', 'e043f1331886c702057bf472001bbba79fdef6b6bf0da1dd1941413111bc6f8d'),
    'pages': ('native-v2-independent-pages.json', 'db6ed93e89c05639403ed3ed1e1e7ec7026617b2ec0750d63d9cccb83ec70b18'),
}


def validate(proposal, native133, pages, entries, partial, prior_ids):
    if (proposal['schema_version'] != 1 or native133['schema_version'] != 1 or
            pages.get('schema_version') != 1 or
            proposal['source_sha256']['native_133_field_coverage'] != SOURCES['native'][1] or
            proposal['source_sha256']['prior_proposed_crosswalk'] !=
            '9acd6051b79b569424e7a3e6061c6f3ae290242af929e69a79fb42feff8aebd1' or
            native133['source_build'] != partial['steam_build_id'] or
            len(proposal['rows']) != 138 or len(native133['records']) != 133 or
            len(pages['records']) != 11):
        raise ValueError('V2 packet source, schema or coverage conflict')
    by_id = {r['forge_id']: r for r in proposal['rows']}
    if len(by_id) != 138 or set(by_id) != {i for i, e in entries.items() if e['kind'] == 'weapon'}:
        raise ValueError('V2 catalog identity set changed')
    by_page = {r['blueprint_id']: r for r in pages['records']}
    by_native = {r['blueprint_id']: r for r in native133['records']}
    if len(by_page) != 11 or len(by_native) != 133:
        raise ValueError('Duplicate source blueprint')
    new, withheld, used = {}, {}, set()
    for identity, row in by_id.items():
        kind = row['classification']
        if kind not in ('proposed_exact_tier_one_gear_title_alias',
                        'proposed_exact_public_blueprint_title_partial_native'):
            continue
        bp = row['proposed_blueprint_id']
        page = by_page.get(bp)
        if (not page or bp in used or identity in prior_ids or
                entries[identity]['name'] != row['forge_name'] or
                page['blueprint_url'] != f'https://oncehuman.th.gl/db/blueprints/{bp}' or
                page['gear_url'] != f'https://oncehuman.th.gl/db/gear/{row["proposed_tier_one_gear_id"]}' or
                page['tier_one_gear_id'] != row['proposed_tier_one_gear_id']):
            raise ValueError('V2 identity or exact source URL conflict')
        used.add(bp)
        if bp == 13231101:
            if page['blueprint_page_status'] != 'unavailable' or page['gear_title'] != 'AA12 (Tier 1)':
                raise ValueError('AA12 withhold evidence changed')
            withheld[identity] = 'Exact blueprint page unavailable; gear title alone is insufficient for this alias'
            continue
        if (page['blueprint_page_status'] != 'read' or
                page['blueprint_title'] != row['source_blueprint_title'] or
                page['blueprint_title'] != row['source_blueprint_title'] or
                page['published_max_stars'] not in range(1, 7)):
            raise ValueError('V2 public blueprint title/max-star conflict')
        if kind == 'proposed_exact_tier_one_gear_title_alias':
            native_row = partial['by_blueprint'].get(bp)
            if (page['gear_page_status'] != 'read' or
                    page['gear_title'] != row['forge_name'] + ' (Tier 1)' or
                    page['gear_title'] != row['source_tier_one_gear_title'] or
                    not native_row or native_row['tier_one_gear_id'] != page['tier_one_gear_id'] or
                    native_row['stored_star_count'] > page['published_max_stars'] or
                    bp in {r['blueprint_id'] for r in new.values()}):
                raise ValueError('V2 alias native or public gear identity conflict')
            new[identity] = {**native_row, 'catalog_id': identity,
                'public_blueprint_title': page['blueprint_title'],
                'public_blueprint_url': page['blueprint_url'],
                'public_tier_one_gear_title': page['gear_title'],
                'public_tier_one_gear_url': page['gear_url'],
                'published_max_stars': page['published_max_stars'],
                'identity_proof': 'exact_public_tier_one_gear_title_and_native_mapping',
                'source_access_date': pages['access_date']}
            continue
        if (identity != 'weapon:mps7-chaos-domain' or bp != 13332401 or
                page['blueprint_title'] != row['forge_name'] + ' B.P.' or
                page['blueprint_crafts_tier_one_title'] != row['source_tier_one_gear_title'] or
                page['published_max_stars'] != 6 or bp in partial['by_blueprint']):
            raise ValueError('MPS7 identity-only source changed')
        candidate = by_native[bp]
        if candidate['tier_one_gear_id'] != page['tier_one_gear_id']:
            raise ValueError('MPS7 native blueprint mapping changed')
        captures = {name: (ROOT / 'native_raw' / f'{name}.literal_bytes.bin').read_bytes()
                    for name in native133['source_literal_sha256']}
        for name, expected in native133['source_literal_sha256'].items():
            if hashlib.sha256(captures[name]).hexdigest() != expected:
                raise ValueError('MPS7 native literal hash changed')
        blueprint = captures['gun_blueprint_data']
        at = candidate['gear_to_blueprint_pair_offset']
        gear, following = native._uvar(blueprint, at)
        mapped, end = native._uvar(blueprint, following)
        if (gear != page['tier_one_gear_id'] or mapped != bp or
                blueprint[at:end].hex() != candidate['gear_to_blueprint_pair_hex'] or
                len(candidate['tiers']) != 5):
            raise ValueError('MPS7 native pair bytes changed')
        gun_map = native._item_to_gun(captures['item_to_gun_mapping_data'])
        for number, tier in enumerate(candidate['tiers'], 1):
            fields = tier['typed_equip_fields']
            if (tier['candidate_tier'] != number or
                    tier['candidate_gear_id'] != fields['equip_origin_id']['value'] or
                    fields['blueprint_no']['value'] != bp or
                    fields['art_lv']['value'] != number or
                    tier['native_gun_preset_attack'] is not None or
                    tier['origin_attack_parse_status'] != 'origin_row_shape_unresolved' or
                    gun_map.get(tier['candidate_gear_id']) != fields['gun_no']['value']):
                raise ValueError('MPS7 typed tier identity or unknown attack changed')
            for key in ('equip_origin_id', 'blueprint_no', 'art_lv', 'gun_no'):
                if native._native_value(captures['equip_data'], fields[key], 'integer') != fields[key]['value']:
                    raise ValueError('MPS7 byte-level tier identity changed')
        new[identity] = {'catalog_id': identity, 'blueprint_id': bp,
            'tier_one_gear_id': gear, 'tiers': {}, 'stars': {},
            'stored_star_count': 0, 'published_max_stars': 6,
            'public_blueprint_title': page['blueprint_title'],
            'public_blueprint_url': page['blueprint_url'],
            'public_tier_one_gear_title': page['blueprint_crafts_tier_one_title'],
            'public_tier_one_gear_url': page['gear_url'],
            'identity_proof': 'exact_public_blueprint_title_crafts_link_and_native_mapping',
            'identity_only_reason': 'Native origin attack is unresolved; star records are not promoted from this partial capture',
            'source_access_date': pages['access_date']}
    if (len(new) != 10 or sum(bool(r.get('identity_only_reason')) for r in new.values()) != 1 or
            withheld != {'weapon:aa12': withheld.get('weapon:aa12')}):
        raise ValueError('V2 bounded acceptance set changed')
    if len(set(prior_ids) | set(new)) != len(prior_ids) + len(new):
        raise ValueError('V2 linked identity duplicates previous catalog link')
    return {'by_catalog': new, 'withheld': withheld, 'steam_build_id': native133['source_build'],
        'counts': {'new_accepted_catalog_links': 10, 'new_numeric_native_links': 9,
                   'new_identity_only_links': 1, 'new_withheld': 1,
                   'new_formula_ready_fields': 0}}


def load_current(entries, partial, prior_ids):
    data = {}
    for name, (file, digest) in SOURCES.items():
        raw = (ROOT / file).read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError(f'V2 {name} source hash changed')
        data[name] = json.loads(raw)
    return validate(data['proposal'], data['native'], data['pages'], entries, partial, prior_ids)


def selected(report, catalog_id, tier, stars):
    row = report['by_catalog'].get(catalog_id)
    if row is None:
        return None
    if not row.get('identity_only_reason'):
        return native_partial_intake.selected(report, catalog_id, tier, stars)
    invalid = type(stars) is int and stars > row['published_max_stars']
    return {'catalog_id': catalog_id, 'blueprint_id': row['blueprint_id'],
        'selected_tier': tier, 'selected_stars': stars, 'gun_preset_attack': None,
        'preset_attack_radio': None, 'gear_id': row['tier_one_gear_id'] if tier == 1 else None,
        'stored_star_count': 0, 'published_max_stars': row['published_max_stars'],
        'configuration_status': 'exceeds_published_max_stars' if invalid else 'not_disproved_by_published_max',
        'missing_star_reason': f'Selected {stars}★ exceeds published maximum 6★' if invalid else
        'No native star ratio promoted for this identity-only mapping',
        'public_blueprint_title': row['public_blueprint_title'],
        'public_blueprint_url': row['public_blueprint_url'],
        'public_tier_one_gear_title': row['public_tier_one_gear_title'],
        'identity_only_reason': row['identity_only_reason'],
        'steam_build_id': report['steam_build_id'], 'calculation_included': False}
