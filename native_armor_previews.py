"""Exact native gear-ID HP/Psi base previews; never equipped stat totals."""
from __future__ import annotations

from collections import defaultdict
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import re
import struct

PACKETS = Path(__file__).with_name('evidence_packets')
SOURCES = {
    'native-armor-base-preview-v1.json': ('2ff77ea7dcebe3c13b9d2017f72cf37d22e8f379617db378eef2c20718d62d12', 3932),
    'native-armor-optional-preview-v1.json': ('a294ebf956f1674e918686a6d35c62056bbde28580262e2192cde6cbdee6cd33', 147),
    'native-armor-four-affix-preview-v1.json': ('30f1e2c3a7748d52a51ab2dd1eabf7386a4b234e4921baca8277ae04025721dd', 749),
}
NAME_INDEX = ('native_armor_search_name_index.json', '2918547ab6cb43e3d9060a8fcb30d2b3ee2516fb6852a6143c10a7e3cd70ab71')
NAME_CROSSWALK = ('native_armor_english_id_crosswalk.json', 'ba94fff973d0a1145080b57512771ded0252eea87dd81e3a02ee7af61f3413f9')


def _attach_exact_names(result):
    name_raw = (PACKETS / NAME_INDEX[0]).read_bytes()
    crosswalk_raw = (PACKETS / NAME_CROSSWALK[0]).read_bytes()
    if hashlib.sha256(name_raw).hexdigest() != NAME_INDEX[1] or hashlib.sha256(crosswalk_raw).hexdigest() != NAME_CROSSWALK[1]:
        raise ValueError('Native armor name source hash conflict')
    index, crosswalk = json.loads(name_raw), json.loads(crosswalk_raw)
    if (index.get('installed_build_id') != '26267212' or index.get('source_packet', {}).get('sha256') != NAME_CROSSWALK[1] or
            index.get('game_code_executed') is not False or index.get('installed_files_modified') is not False or
            len(index.get('records', [])) != 1018 or len(crosswalk.get('gear_item_names', [])) != 1018):
        raise ValueError('Native armor name source scope or coverage conflict')
    catalog_raw = Path(__file__).with_name('catalog.json').read_bytes()
    art_raw = Path(__file__).with_name('artwork_manifest.json').read_bytes()
    if (hashlib.sha256(catalog_raw).hexdigest() != index['source_hashes']['forge_catalog_read_only_sha256'] or
            hashlib.sha256(art_raw).hexdigest() != index['source_hashes']['forge_artwork_manifest_read_only_sha256']):
        raise ValueError('Native armor name catalog/artwork source changed')
    catalog = {item['id']: item for item in json.loads(catalog_raw)['armor']}
    artwork = json.loads(art_raw)['records']
    by_id = {row['native_gear_id']: row for row in result}
    cross_by_id = {row['item_id']: row for row in crosswalk['gear_item_names']}
    if len(cross_by_id) != 1018:
        raise ValueError('Duplicate native armor name identity')
    families = defaultdict(list)
    anchors = {}
    for outside in crosswalk.get('forge_catalog_numeric_artwork_links_outside_preview', []):
        art_link, native = outside['artwork_link'], outside['native_item']
        catalog_id, gear_id = art_link['catalog_id'], art_link['numeric_artwork_entity_id']
        name = native['installed_english']['english_text']
        art = artwork.get(catalog_id, {})
        if (catalog_id not in catalog or (catalog[catalog_id].get('display_name') or catalog[catalog_id]['name']) != name or
                not art.get('image_url', '').endswith(f'/images/entities/{gear_id}.png') or
                native['item_id'] != gear_id or not isinstance(outside['exact_native_blueprint_id'], int)):
            raise ValueError('Outside-preview armor artwork anchor conflict')
        anchors[(outside['exact_native_blueprint_id'], name, catalog_id)] = gear_id
    linked = 0
    different_titles = 0
    for source in index['records']:
        gear_id, blueprint_id, tier = source['gear_id'], source['blueprint_id'], source['source_tier_art_lv']
        row, check = by_id.get(gear_id), cross_by_id.get(gear_id)
        name, blueprint_name = source['installed_english_name'], source['installed_blueprint_english_name']
        if (row is None or check is None or row['native_blueprint_id'] != blueprint_id or row['source_tier'] != tier or
                check['blueprint_id'] != blueprint_id or check['installed_english']['english_text'] != name or
                check['installed_blueprint_english_name'] != blueprint_name or
                check['native_name']['source_string'] != source['installed_native_name'] or
                not isinstance(name, str) or not name.strip() or not isinstance(blueprint_name, str) or not blueprint_name.strip() or
                any(type(source[field]) is not int or source[field] <= 0 for field in
                    ('gear_name_typed_field_byte_offset', 'gear_name_english_map_pair_byte_offset',
                     'blueprint_name_typed_field_byte_offset', 'blueprint_name_english_map_pair_byte_offset'))):
            raise ValueError('Native armor exact ID/name/offset conflict')
        direct = source['forge_catalog_id_with_exact_numeric_artwork_and_name']
        link = source['forge_catalog_id_with_exact_native_blueprint_anchor']
        status = source['forge_catalog_identity_status']
        if direct:
            entry, art = catalog.get(direct), artwork.get(direct, {})
            image = art.get('image_url', '')
            if (status != 'direct_numeric_artwork_entity_ID_plus_installed_English_name' or link != direct or
                    entry is None or (entry.get('display_name') or entry['name']) != name or
                    not image.endswith(f'/images/entities/{gear_id}.png')):
                raise ValueError('Direct armor Build link lacks exact numeric artwork and name')
            anchors[(blueprint_id, name, direct)] = gear_id
        elif link:
            if status != 'same_exact_native_blueprint_ID_and_installed_English_name_as_numeric_artwork_anchor' or link not in catalog:
                raise ValueError('Propagated armor Build link lacks an anchor')
        elif status != 'no_proven_numeric_artwork_blueprint_anchor':
            raise ValueError('Unlinked armor identity mislabeled')
        if link:
            linked += 1
        if source['gear_vs_blueprint_title_status'] == 'different_installed_titles_same_exact_native_BP_link':
            different_titles += 1
        row.update({'name': name, 'installed_native_name': source['installed_native_name'],
                    'installed_blueprint_name': blueprint_name, 'installed_blueprint_native_name': source['installed_blueprint_native_name'],
                    'forge_catalog_id': link, 'forge_catalog_identity_status': status,
                    'gear_vs_blueprint_title_status': source['gear_vs_blueprint_title_status'],
                    'name_source_packet_sha256': NAME_INDEX[1],
                    'name_source_offsets': {'gear_typed': source['gear_name_typed_field_byte_offset'],
                        'gear_english': source['gear_name_english_map_pair_byte_offset'],
                        'blueprint_typed': source['blueprint_name_typed_field_byte_offset'],
                        'blueprint_english': source['blueprint_name_english_map_pair_byte_offset']}})
        row['summary'] = f'Tier {tier} source base preview · {len(row["star_previews"])} supported star rows.'
        families[(blueprint_id, name)].append(row)
    if set(by_id) != set(cross_by_id) or linked != 801 or different_titles != 218:
        raise ValueError('Native armor name/link coverage conflict')
    for source in index['records']:
        if source['forge_catalog_id_with_exact_native_blueprint_anchor'] and not source['forge_catalog_id_with_exact_numeric_artwork_and_name']:
            if (source['blueprint_id'], source['installed_english_name'], source['forge_catalog_id_with_exact_native_blueprint_anchor']) not in anchors:
                raise ValueError('Same-blueprint armor Build link lacks exact direct anchor')
    for group in families.values():
        group.sort(key=lambda row: (row['source_tier'], row['native_gear_id']))
        if len({row['source_tier'] for row in group}) != len(group):
            raise ValueError('Same-name armor family has conflicting tier identities')
        choices = [{'tier': row['source_tier'], 'gear_id': row['native_gear_id'],
                    'star_count': len(row['star_previews'])} for row in group]
        for row in group:
            row['aid_search_representative'] = row is group[0]
            if len(group) > 1:
                row['tier_choices'] = choices
                row['named_family'] = row['name']
    return result


def _source_float(hex_value, expected, label):
    raw = bytes.fromhex(hex_value)
    fmt = {4: '<f', 8: '<d'}.get(len(raw))
    if fmt is None or struct.unpack(fmt, raw)[0] != expected:
        raise ValueError(f'{label}: source numeric bytes/value conflict')


@lru_cache(maxsize=1)
def records():
    grouped = defaultdict(list)
    packets = {}
    seen = set()
    for filename, (digest, count) in SOURCES.items():
        raw = (PACKETS / filename).read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError(f'{filename}: source hash conflict')
        packet = json.loads(raw)
        packets[filename] = packet
        rows = packet.get('records', packet.get('preview_records'))
        if (packet.get('installed_build_id') != '26267212' or
                packet.get('game_code_executed') is not False or
                packet.get('installed_files_modified') is not False or
                not isinstance(rows, list) or len(rows) != count):
            raise ValueError(f'{filename}: source build or coverage conflict')
        for source in rows:
            gear_id, blueprint_id, tier, star = (source.get('gear_id'),
                source.get('blueprint_id'), source.get('source_tier_art_lv'), source.get('star'))
            if (any(type(value) is not int for value in (gear_id, blueprint_id, tier, star)) or
                    not 1 <= tier <= 5 or not 1 <= star <= 6 or
                    (gear_id, star) in seen):
                raise ValueError('Native armor gear/star identity conflict')
            seen.add((gear_id, star))
            values = source.get('source_values') or {}
            if set(values) != {'A0200', 'D4100'}:
                raise ValueError(f'{gear_id}: HP/Psi source fields missing')
            preview = {}
            for code, label in (('A0200', 'hp'), ('D4100', 'psi_intensity')):
                item = values[code]
                origin = item['origin_value']
                ratio = item.get('star_ratio', item.get('ratio'))
                _source_float(item.get('origin_value_raw_hex', item.get('origin_raw_hex')),
                         origin, f'{gear_id}/{code} origin')
                _source_float(item.get('star_ratio_raw_hex', item.get('ratio_raw_hex')),
                         ratio, f'{gear_id}/{code} ratio')
                product = origin * ratio
                if (not math.isfinite(product) or product < 0 or
                        not math.isclose(product, item['client_product'], rel_tol=1e-12, abs_tol=1e-9) or
                        int(format(product, '.0f')) != item['client_formatted_integer']):
                    raise ValueError(f'{gear_id}/{code}: base-preview arithmetic conflict')
                preview[label] = item['client_formatted_integer']
            grouped[gear_id].append({'star': star, **preview,
                                     'source_packet_sha256': digest,
                                     'source_packet': filename,
                                     'origin_and_ratio_raw_fields_retained': True,
                                     'blueprint_id': blueprint_id,
                                     'tier': tier})
    if len(seen) != 4828 or len(grouped) != 1018:
        raise ValueError('Native armor preview aggregate coverage conflict')
    result = []
    for gear_id, stars in sorted(grouped.items()):
        blueprint_ids = {row['blueprint_id'] for row in stars}
        tiers = {row['tier'] for row in stars}
        if len(blueprint_ids) != 1 or len(tiers) != 1 or len(stars) != len({row['star'] for row in stars}):
            raise ValueError(f'{gear_id}: source blueprint/tier/star conflict')
        blueprint_id, tier = blueprint_ids.pop(), tiers.pop()
        result.append({'catalog_id': f'aid:armor_preview:{gear_id}',
                       'native_gear_id': gear_id, 'native_blueprint_id': blueprint_id,
                       'source_tier': tier, 'category': 'armor_previews',
                       'name': f'Armor gear ID {gear_id}',
                       'summary': f'Tier {tier} source base preview · {len(stars)} supported star rows.',
                       'star_previews': sorted(stars, key=lambda row: row['star']),
                       'calculation_status': 'base_preview_only_not_equipped',
                       'source_build': '26267212', 'catalog_identity_status': 'native_gear_id_only',
                       'equipped_hp_or_psi': None})
    by_id = {row['native_gear_id']: row for row in result}
    controls = [*packets['native-armor-optional-preview-v1.json']['public_exact_id_controls'],
                packets['native-armor-four-affix-preview-v1.json']['public_exact_id_control']]
    for control in controls:
        anchor = by_id.get(control['gear_id'])
        title = control.get('observed_title', control.get('title'))
        observed = control.get('hp_psi_by_star', control.get('observed_hp_psi_by_star'))
        if (not anchor or not title or not re.search(r'\(Tier [1-5]\)$', title) or
                control.get('page_build_unverified') is not True or
                [[row['hp'], row['psi_intensity']] for row in anchor['star_previews']] != observed):
            raise ValueError('Named public armor control conflicts with native exact gear ID')
        family = re.sub(r'\s*\(Tier [1-5]\)$', '', title)
        related = sorted((row for row in result if row['native_blueprint_id'] == anchor['native_blueprint_id']),
                         key=lambda row: row['source_tier'])
        if len(related) != 5 or [row['source_tier'] for row in related] != [1, 2, 3, 4, 5]:
            raise ValueError('Named armor blueprint has ambiguous tier identities')
        anchor['name'] = family
        anchor['named_family'] = family
        anchor['source_anchor_gear_id'] = control['gear_id']
        anchor['source_anchor_title'] = title
        anchor['source_anchor_url'] = control['url']
        anchor['tier_choices'] = [{'tier': row['source_tier'], 'gear_id': row['native_gear_id'],
                                   'star_count': len(row['star_previews'])} for row in related]
        anchor['catalog_identity_status'] = 'source_named_anchor_with_same_blueprint_tier_choices'
        anchor['summary'] = (f'Exact named Tier {anchor["source_tier"]} source anchor; '
                             'choose a same-blueprint tier and supported star for HP/Psi base preview.')
    return _attach_exact_names(result)


def by_exact_gear_id(gear_id: int, star: int):
    if type(gear_id) is not int or type(star) is not int:
        raise ValueError('Exact numeric native gear ID and star are required')
    row = next((item for item in records() if item['native_gear_id'] == gear_id), None)
    if row is None:
        return None
    return next((item for item in row['star_previews'] if item['star'] == star), None)


def for_catalog_configuration(catalog_id: str, tier: int | None, stars: int | None):
    """Return one exact source base preview, never an equipped armor total."""
    matches = [row for row in records() if row['forge_catalog_id'] == catalog_id]
    if not matches:
        return {'status': 'no_exact_native_identity', 'catalog_id': catalog_id}
    if type(tier) is not int or type(stars) is not int:
        return {'status': 'tier_or_stars_not_selected', 'catalog_id': catalog_id}
    choices = [row for row in matches if row['source_tier'] == tier]
    if len(choices) != 1:
        return {'status': 'source_tier_unavailable', 'catalog_id': catalog_id, 'tier': tier}
    match = choices[0]
    preview = [row for row in match['star_previews'] if row['star'] == stars]
    if len(preview) != 1:
        return {'status': 'source_star_unavailable', 'catalog_id': catalog_id, 'tier': tier, 'stars': stars}
    return {'status': 'source_base_preview_only', 'catalog_id': catalog_id,
            'native_gear_id': match['native_gear_id'], 'native_blueprint_id': match['native_blueprint_id'],
            'name': match['name'], 'tier': tier, 'stars': stars,
            'hp': preview[0]['hp'], 'psi_intensity': preview[0]['psi_intensity'],
            'source_packet_sha256': preview[0]['source_packet_sha256'],
            'name_packet_sha256': match['name_source_packet_sha256'],
            'equipped_stats': None}
