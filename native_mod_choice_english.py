"""Exact English choice text and dual-key mod links; no ownership or grant claim."""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
from pathlib import Path

import native_mod_identity

ROOT = Path(__file__).parent
PACKET = ROOT / 'evidence_packets/native-mod-choice-english-crosswalk-v2.json'
PACKET_SHA256 = '7e78cb5779ac0843df1bd15800a57a08850232e29ca5666883cbd3a95a383930'
CHOICES = ROOT / 'evidence_packets/native-mod-choice-containers-v1.json'
CHOICES_SHA256 = 'd986c92964c78dfeae694c38537982179962408a41958a58a5150440cf895e40'
CATALOG = ROOT / 'catalog_systems.json'
CATALOG_SHA256 = '18f123fdd94b7618e3a34681eed4a5f369003ac64e3aace4041ed9ed62904829'
IDENTITY = ROOT / 'evidence_packets/native-mod-identity-v2.json'
IDENTITY_SHA256 = '68d70819129ea725dcbec65421dc587ece3339822995be89ba495c7fa7e8ecb9'


def _read(path, expected):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f'{path.name}: source hash conflict')
    return json.loads(raw)


def _core(source):
    return source.split('_$S@', 1)[0].strip()


def _english(field, native):
    if (field.get('status') != 'exact_installed_english_key' or
            field.get('source_string') != native or
            field.get('source_core_text') != _core(native) or
            field.get('key_match_mode') not in ('exact_source_text_without_tid_suffix', 'exact_full_source_key') or
            field.get('translation_key') != (native if field.get('key_match_mode') == 'exact_full_source_key' else _core(native)) or
            type(field.get('map_pair_byte_offset')) is not int or
            not field.get('english_text')):
        raise ValueError('Native mod choice English translation lacks exact key')
    return field['english_text']


@lru_cache(maxsize=1)
def load():
    packet = _read(PACKET, PACKET_SHA256)
    native = _read(CHOICES, CHOICES_SHA256)
    catalog = _read(CATALOG, CATALOG_SHA256)
    _read(IDENTITY, IDENTITY_SHA256)
    cov = packet.get('coverage') or {}
    if (packet.get('build') != '26267212' or
            packet.get('game_code_executed') is not False or
            packet.get('installed_files_modified') is not False or
            cov.get('containers') != 579 or cov.get('option_positions') != 5760 or
            cov.get('unique_native_option_items') != 1640 or
            cov.get('exact_catalog_systems_unique_items') != 1640 or
            cov.get('catalog_systems_unmatched_unique_items') != 0 or
            cov.get('exact_canonical_catalog_link_unique_items') != 143 or
            len(packet.get('containers') or []) != 579 or
            len(packet.get('unique_options') or []) != 1640):
        raise ValueError('Native mod choice English build or coverage conflict')
    source_hashes = packet.get('source_sha256') or {}
    expected_sources = {
        '~/Documents/Codex/2026-11-02/task-5/native_mod_choice_container_options.json': CHOICES_SHA256,
        '~/Projects/once-human-advisor/catalog_systems.json': CATALOG_SHA256,
        '~/Projects/once-human-advisor/evidence_packets/native-mod-identity-v2.json': IDENTITY_SHA256,
    }
    if any(source_hashes.get(path) != digest for path, digest in expected_sources.items()):
        raise ValueError('Native mod choice English input provenance conflict')
    catalog_by_keys = {(row['item_id'], row['id']): row for row in catalog['records']}
    if len(catalog_by_keys) != len(catalog['records']):
        raise ValueError('Catalog system item/mod dual keys conflict')
    _, canonical = native_mod_identity.load()
    canonical_by_item = {}
    for catalog_id, variants in canonical.items():
        for variant, source in variants.items():
            item_id = int(source['native_item_no'])
            if item_id in canonical_by_item:
                raise ValueError('Canonical mod native item duplicated')
            canonical_by_item[item_id] = (catalog_id, variant, source['native_mod_code'])
    unique = {}
    matched = unmatched = canonical_count = 0
    for row in packet['unique_options']:
        item_id, mod_code = row['item_no'], row['mod_code']
        if type(item_id) is not int or type(mod_code) is not int or item_id in unique:
            raise ValueError('Native English option identity conflict')
        english = _english(row['installed_english_mod_name'], row['native_mod_name'])
        source_catalog = row['catalog_systems_exact_dual_key']
        actual_catalog = catalog_by_keys.get((str(item_id), str(mod_code)))
        if ((source_catalog is None) != (actual_catalog is None) or
                (source_catalog and any(actual_catalog.get(key) != value
                                        for key, value in source_catalog.items())) or
                (actual_catalog and (actual_catalog['name'] != english or
                                     actual_catalog['is_shiny'] != bool(row['is_shiny_mod'])))):
            raise ValueError(f'Native option {item_id}: catalog dual-key/name/variant conflict')
        matched += bool(actual_catalog)
        unmatched += not bool(actual_catalog)
        source_canonical = row['canonical_catalog_id_exact_native_link']
        actual_canonical = canonical_by_item.get(item_id)
        if source_canonical != (actual_canonical[0] if actual_canonical else None) or (
                actual_canonical and (actual_canonical[2] != mod_code or
                                      (actual_canonical[1] == 'shiny') != bool(row['is_shiny_mod']))):
            raise ValueError(f'Native option {item_id}: canonical variant conflict')
        canonical_count += bool(source_canonical)
        unique[item_id] = {'english_name': english,
                           'catalog_systems_id': actual_catalog['id'] if actual_catalog else None,
                           'catalog_systems_slot': actual_catalog['apply_range_desc'] if actual_catalog else None,
                           'catalog_systems_suffix': actual_catalog['family'] if actual_catalog else None,
                           'canonical_catalog_id': source_canonical,
                           'native_item_id': item_id, 'native_mod_code': mod_code,
                           'native_family_id': row['main_entry_no'],
                           'shiny': bool(row['is_shiny_mod'])}
    if (matched, unmatched, canonical_count) != (1640, 0, 143):
        raise ValueError('Native English option link totals conflict')
    native_by_id = {row['container_item_no']: row for row in native['records']}
    if len(native_by_id) != 579:
        raise ValueError('Native container ID conflict')
    containers = {}
    systems_positions = canonical_positions = 0
    for row in packet['containers']:
        item_id = row['container_item_no']
        source = native_by_id.get(item_id)
        if not source or item_id in containers:
            raise ValueError('Native English container identity conflict')
        typed = row['typed_item_data']
        title = _english(typed['english_name'], typed['native_name']['source_string'])
        description = _english(typed['english_short_desc'], typed['native_short_desc']['source_string'])
        localized = {x['source_string'] for x in source['native_item_localized_strings']}
        if (typed['native_name']['source_string'] not in localized or
                typed['native_short_desc']['source_string'] not in localized or
                row['configured_option_count'] != len(source['choices']) or
                len(row['choices_exact_ids']) != len(source['choices'])):
            raise ValueError(f'Native English container {item_id} source list/text conflict')
        options = []
        for position, choice in enumerate(row['choices_exact_ids']):
            original = source['choices'][position]
            indexed = unique.get(choice['item_no'])
            if (choice['position'] != position or not indexed or
                    any(choice[key] != original[key] for key in
                        ('item_no', 'mod_code', 'main_entry_no', 'is_shiny_mod')) or
                    choice['catalog_systems_id'] != indexed['catalog_systems_id'] or
                    choice['canonical_catalog_id'] != indexed['canonical_catalog_id']):
                raise ValueError(f'Native English container {item_id} option source conflict')
            systems_positions += bool(indexed['catalog_systems_id'])
            canonical_positions += bool(indexed['canonical_catalog_id'])
            options.append(indexed)
        containers[item_id] = {'english_title': title,
                               'english_description': description,
                               'native_title': _core(typed['native_name']['source_string']),
                               'native_description': _core(typed['native_short_desc']['source_string']),
                               'options': options, 'source_packet_sha256': PACKET_SHA256}
    if (len(containers), systems_positions, canonical_positions) != (579, 5760, 468):
        raise ValueError('Native English container/position coverage conflict')
    return containers
