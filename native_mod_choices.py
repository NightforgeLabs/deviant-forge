"""Configured native mod choice lists, distinct from random reward pools."""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
from pathlib import Path

import native_mod_identity
import native_mod_choice_english
import catalog

PACKET = Path(__file__).with_name('evidence_packets') / 'native-mod-choice-containers-v1.json'
PACKET_SHA256 = 'd986c92964c78dfeae694c38537982179962408a41958a58a5150440cf895e40'
EXPECTED_NAMED = {37167141: 10, 37167208: 16, 37181192: 10}


def _text(value):
    return value.split('_$S@', 1)[0].strip()


@lru_cache(maxsize=1)
def records():
    raw = PACKET.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PACKET_SHA256:
        raise ValueError('Native mod choice container packet hash conflict')
    packet = json.loads(raw)
    coverage = packet.get('coverage') or {}
    if (packet.get('build') != '26267212' or
            coverage.get('all_mod_choice_containers') != 579 or
            coverage.get('all_mod_choice_options') != 5760 or
            coverage.get('mixed_rows') != 0 or
            len(packet.get('records') or []) != 579 or
            packet.get('game_code_executed') is not False or
            packet.get('installed_files_modified') is not False):
        raise ValueError('Native mod choice build or coverage conflict')
    _, linked = native_mod_identity.load()
    english_by_container = native_mod_choice_english.load()
    exact_by_item = {}
    for catalog_id, variants in linked.items():
        for variant, source in variants.items():
            item = int(source['native_item_no'])
            if item in exact_by_item:
                raise ValueError('Native mod choice crosswalk has duplicate item ID')
            exact_by_item[item] = (catalog_id, variant, source['native_mod_code'])
    result = []
    used = set()
    option_total = linked_total = 0
    for row in packet['records']:
        item_id = row.get('container_item_no')
        if type(item_id) is not int or item_id in used:
            raise ValueError('Native mod choice container identity conflict')
        used.add(item_id)
        if (row.get('item_use_hook') or {}).get('string') != 'gift_open':
            raise ValueError(f'Container {item_id} has no gift_open binding')
        english_container = english_by_container.get(item_id)
        if not english_container:
            raise ValueError(f'Container {item_id} lacks exact English source identity')
        source_arrays = row.get('arrays_by_native_field') or {}
        choices = row.get('choices') or []
        if len(choices) < 2 or any(len((source_arrays.get(key) or {}).get('values') or []) != len(choices)
                                   for key in ('item_no_list', 'item_num_list', 'item_bind_list', 'item_detail_list')):
            raise ValueError(f'Container {item_id} has unaligned source option arrays')
        parsed = []
        for position, choice in enumerate(choices):
            if (choice.get('position') != position or
                    choice.get('item_no') != source_arrays['item_no_list']['values'][position]['value'] or
                    choice.get('quantity') != source_arrays['item_num_list']['values'][position]['value'] or
                    choice.get('bind_flag') != source_arrays['item_bind_list']['values'][position]['value'] or
                    choice.get('item_detail_value') != source_arrays['item_detail_list']['values'][position]['value'] or
                    type(choice.get('mod_code')) is not int or
                    type(choice.get('main_entry_no')) is not int or
                    choice.get('is_shiny_mod') not in (0, 1) or
                    not choice.get('native_entry_rank_keys_present') or
                    not _text(choice.get('native_mod_name') or '')):
                raise ValueError(f'Container {item_id} option {position} has unbound source identity')
            matched = exact_by_item.get(choice['item_no'])
            if matched and (matched[2] != choice['mod_code'] or
                            (matched[1] == 'shiny') != bool(choice['is_shiny_mod'])):
                raise ValueError(f'Container {item_id} option {position} conflicts with exact Forge mod identity')
            if matched:
                linked_total += 1
            english_option = english_container['options'][position]
            if (english_option['native_item_id'] != choice['item_no'] or
                    english_option['native_mod_code'] != choice['mod_code'] or
                    english_option['native_family_id'] != choice['main_entry_no'] or
                    english_option['shiny'] != bool(choice['is_shiny_mod']) or
                    english_option['canonical_catalog_id'] != (matched[0] if matched else None)):
                raise ValueError(f'Container {item_id} option {position} English/catalog identity conflict')
            parsed.append({'position': position, 'native_item_id': choice['item_no'],
                           'native_mod_code': choice['mod_code'],
                           'native_family_id': choice['main_entry_no'],
                           'native_name': _text(choice['native_mod_name']),
                           'english_name': english_option['english_name'],
                           'shiny': bool(choice['is_shiny_mod']),
                           'configured_quantity': choice['quantity'],
                           'source_bind_flag': choice['bind_flag'],
                           'source_item_detail_value': choice['item_detail_value'],
                           'native_entry_rank_keys_present': choice['native_entry_rank_keys_present'],
                           'forge_catalog_id': matched[0] if matched else None,
                           'forge_name': (catalog.ENTRIES[matched[0]].get('display_name') or
                                          catalog.ENTRIES[matched[0]]['name']) if matched else None,
                           'forge_variant': matched[1] if matched else None,
                           'catalog_systems_id': english_option['catalog_systems_id'],
                           'catalog_systems_slot': english_option['catalog_systems_slot'],
                           'catalog_systems_suffix': english_option['catalog_systems_suffix'],
                           'identity_status': 'exact_item_id_crosswalk' if matched else 'native_option_only'})
        option_total += len(parsed)
        sample = row.get('named_sample')
        if sample:
            if item_id not in EXPECTED_NAMED or len(parsed) != EXPECTED_NAMED[item_id] or \
                    not _text(sample.get('source_name') or '') or \
                    not _text(sample.get('source_description') or '') or \
                    {sample['source_name'],sample['source_description']} - \
                    {x['source_string'] for x in row['native_item_localized_strings']}:
                raise ValueError(f'Container {item_id} named sample source conflict')
            if (english_container['native_title'] != _text(sample['source_name']) or
                    english_container['native_description'] != _text(sample['source_description'])):
                raise ValueError(f'Container {item_id} native/English title source conflict')
        else:
            pass
        name = english_container['english_title']
        desc = english_container['native_description']
        title_status = 'exact_installed_english_key'
        result.append({'catalog_id': f'aid:choice_container:{item_id}',
                       'native_container_id': item_id,
                       'category': 'choice_containers', 'name': name,
                       'native_description': desc,
                       'native_title': english_container['native_title'],
                       'english_description': english_container['english_description'],
                       'title_status': title_status,
                       'summary': f'Configured selection list: {len(parsed)} options. Availability and grant rules unknown.',
                       'option_count': len(parsed), 'options': parsed,
                       'mapped_option_count': sum(bool(x['forge_catalog_id']) for x in parsed),
                       'catalog_systems_option_count': sum(bool(x['catalog_systems_id']) for x in parsed),
                       'calculation_status': 'informational_selection_list',
                       'draw_mode': 'selectable_list_not_random_pool',
                       'availability': 'unknown',
                       'source_packet_sha256': PACKET_SHA256,
                       'english_packet_sha256': native_mod_choice_english.PACKET_SHA256})
    if (option_total != 5760 or linked_total != 468 or
            sum(row['catalog_systems_option_count'] for row in result) != 5760 or
            any(row['title_status'] != 'exact_installed_english_key' for row in result)):
        raise ValueError('Native mod choice option or exact crosswalk coverage conflict')
    return sorted(result, key=lambda row: (row['title_status'] != 'source_named_sample', row['native_container_id']))
