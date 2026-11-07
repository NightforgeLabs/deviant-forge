"""Exact native food crafting configurations, without unlock or effect claims."""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
from pathlib import Path

import native_named_catalog


ROOT = Path(__file__).resolve().parent / 'evidence_packets'
SOURCES = {
    'native-food-combat-crafting-v1.json': '13572728fa534ca11f21132b65a419161ee092342e926a18c87a5465afd54954',
    'native-food-4010-choices-v1.json': '7df49a410c48d2fd5d04e5086c7b7fe89a9df89615487ba60f62747ca6e92e9f',
    'native-soup-forge-variant-selection-v1.json': '8363b2f29e0fb7972f1e168669d2d9e672b3429e8faa53d799b35df4fd0c3873',
    'native-food-forge-variant-ledger-v1.json': '04887676bc16881196886c837ddb1594bb25759e3d359bb517d0e91ea2b81e79',
}


@lru_cache(maxsize=1)
def records():
    if any(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest
           for name, digest in SOURCES.items()):
        raise ValueError('Native food crafting source hash conflict')
    packet = json.loads((ROOT / 'native-food-combat-crafting-v1.json').read_text())
    choices = json.loads((ROOT / 'native-food-4010-choices-v1.json').read_text())
    named = {int(row['catalog_id'].split(':')[-1]): row
             for row in native_named_catalog.records()
             if row['category'] in ('food_drink', 'whims_deviations')}
    coverage = packet['coverage']
    if (packet['installed_build_id'] != '26267212' or
            choices['installed_build_id'] != packet['installed_build_id'] or
            packet['schema_version'] != choices['schema_version'] != 1 or
            (coverage['combat_priority_item_ids'], coverage['with_typed_craft_configuration'],
             coverage['configuration_rows'], coverage['configurations_per_item']) !=
            (33, 33, 77, {'3': 15, '2': 14, '1': 4}) or
            choices['buff_enhance_type'] != 4010 or
            choices['configured_ingredient_choice_source_item_ids'] != 5 or
            packet['game_code_executed'] is not False or
            choices['game_code_executed'] is not False or
            packet['installed_files_modified'] is not False or
            choices['installed_files_modified'] is not False):
        raise ValueError('Native food crafting build or coverage conflict')
    seen_items, seen_offsets, output = set(), set(), {}
    for row in packet['records']:
        item_id = row['item_id']
        if item_id in seen_items or item_id not in named or \
                row['installed_english_title'] != named[item_id]['name']:
            raise ValueError(f'Native food recipe identity conflict: {item_id}')
        seen_items.add(item_id)
        variants = []
        for variant in row['craft_configurations']:
            offset = variant['forge_record_byte_offset']
            ingredients = variant['ingredients']
            machines = variant['machines']
            if (offset in seen_offsets or variant['output_item_id'] != item_id or
                    variant['output_quantity'] != 1 or
                    not isinstance(variant['configured_seconds'], int) or
                    variant['configured_seconds'] <= 0 or
                    not ingredients or not machines or
                    [i['item_id'] for i in ingredients] != variant['ingredient_ids']['values'] or
                    [i['quantity'] for i in ingredients] != variant['quantities']['values'] or
                    [m['method_id'] for m in machines] != variant['machine_method_ids']['values'] or
                    any(not isinstance(i['quantity'], int) or i['quantity'] <= 0 or
                        (i['installed_english_name'] is None and
                         i['name_status'] != 'no_indexed_item_data_row')
                        for i in ingredients) or
                    any(not m['installed_english_name'] for m in machines)):
                raise ValueError(f'Native food recipe field conflict: {item_id}/{offset}')
            seen_offsets.add(offset)
            variants.append({
                'source_record_byte_offset': offset,
                'configured_seconds': variant['configured_seconds'],
                'ingredients': [{'item_id': i['item_id'],
                                 'name': i['installed_english_name'],
                                 'quantity': i['quantity'],
                                 'name_status': i['name_status']} for i in ingredients],
                'stations': [{'method_id': m['method_id'],
                              'name': m['installed_english_name']}
                             for m in machines],
            })
        output[item_id] = {'source_build': packet['installed_build_id'],
                           'source_sha256': SOURCES['native-food-combat-crafting-v1.json'],
                           'configurations': variants,
                           'availability': 'unknown', 'unlock': 'unknown',
                           'active_food_effect': 'not_inferred'}
    if len(output) != 33 or len(seen_offsets) != 77:
        raise ValueError('Native food recipe item/configuration count conflict')
    source_choices = choices['configured_ingredient_choice_sources']
    choice_ids = {row['item_id'] for row in source_choices}
    if len(source_choices) != 5 or len(choice_ids) != 5 or \
            set(choices['soup_recipe_ingredient_ids']) & choice_ids:
        raise ValueError('Soup recipe and 4010 choice sources unexpectedly overlap')
    soup_ingredients = {i['item_id'] for variant in output[30110374]['configurations']
                        for i in variant['ingredients']}
    if soup_ingredients != set(choices['soup_recipe_ingredient_ids']):
        raise ValueError('Soup ingredient list differs from separate 4010 source ledger')
    output[30110374]['separate_4010_choices'] = [
        {'item_id': row['item_id'], 'name': row['installed_english_name'],
         'configured_value': row['configured_4010_value']}
        for row in source_choices]
    output[30110374]['separate_4010_choices_are_recipe_ingredients'] = False
    selection = json.loads((ROOT / 'native-soup-forge-variant-selection-v1.json').read_text())
    soup = output[30110374]
    expected_keys = [1200379, [1200379, 1], [1200379, 222]]
    rows = selection['soup_configured_rows']
    examples = selection['synthetic_selection_examples']
    if (selection['schema_version'] != 1 or
            selection['installed_build_id'] != packet['installed_build_id'] or
            selection['forge_data_pyc_sha256'] != packet['source_sha256']['forge_data_pyc'] or
            selection['soup_item_id'] != 30110374 or
            selection['soup_base_forge_no'] != 1200379 or
            selection['item_to_forge_dict']['ordered_soup_forge_keys'] != expected_keys or
            len(rows) != 3 or
            [example['supplied_server_forge_season_no_list'] for example in examples] !=
            [[0], [0, 1], [0, 222]] or
            [example['expected_selected_key'] for example in examples] != expected_keys or
            selection['game_code_executed'] is not False or
            selection['installed_files_modified'] is not False):
        raise ValueError('Soup forge season key source conflict')
    for variant, source_row, key in zip(soup['configurations'], rows, expected_keys):
        if (source_row['forge_record_byte_offset'] != variant['source_record_byte_offset'] or
                source_row['configured_seconds'] != variant['configured_seconds'] or
                source_row['station_method_ids'] !=
                [station['method_id'] for station in variant['stations']] or
                [(i['item_id'], i['quantity']) for i in source_row['configured_ingredients']] !=
                [(i['item_id'], i['quantity']) for i in variant['ingredients']] or
                (source_row['key']['value'] if source_row['key']['key_type'] == 'scalar'
                 else source_row['key']['values']) != key):
            raise ValueError('Soup forge key does not point to its decoded recipe row')
        variant['forge_no'] = 1200379
        variant['forge_season_selector'] = None if isinstance(key, int) else key[1]
        variant['forge_key_scope'] = 'source_bound_soup_only'
    soup['forge_variant_selection'] = {
        'source_sha256': SOURCES['native-soup-forge-variant-selection-v1.json'],
        'season_list_examples': examples,
        'example_scope': selection['synthetic_selection_scope'],
        'current_server_season': 'unknown',
        'disabled_time_visibility_unlock_gates': 'unknown',
    }
    soup['ingredient_933_role'] = 'typed_required_item_number_resource_name_unbound'
    ledger = json.loads((ROOT / 'native-food-forge-variant-ledger-v1.json').read_text())
    counts = ledger['coverage']
    if (ledger['schema_version'] != 1 or
            ledger['installed_build_id'] != packet['installed_build_id'] or
            ledger['prior_recipe_packet_sha256'] != SOURCES['native-food-combat-crafting-v1.json'] or
            ledger['forge_data_pyc_sha256'] != packet['source_sha256']['forge_data_pyc'] or
            (counts['food_item_ids'], counts['distinct_typed_recipe_rows'],
             counts['native_forge_keys'], counts['rows_with_multiple_alias_keys']) !=
            (33, 77, 82, 5) or
            counts['season_selector_key_counts'] != {'1': 22, '11': 1, '222': 26, '223': 1} or
            counts['rows_with_empty_valid_time'] != 77 or
            counts['rows_with_forge_display_zero_or_default'] != 77 or
            counts['rows_with_localized_unlock_tip'] != 7 or
            counts['rows_with_is_diy_true'] != 6 or
            ledger['game_code_executed'] is not False or
            ledger['installed_files_modified'] is not False):
        raise ValueError('Native food forge key coverage or source conflict')
    if len(ledger['records']) != 33:
        raise ValueError('Native food forge item count conflict')
    seen_items, seen_keys, aliases, unlocks, diy = set(), set(), 0, 0, 0
    for row in ledger['records']:
        item_id = row['item_id']
        recipe = output.get(item_id)
        if (recipe is None or item_id in seen_items or
                row['installed_english_title'] != named[item_id]['name']):
            raise ValueError(f'Native forge item identity conflict: {item_id}')
        seen_items.add(item_id)
        variants = {v['source_record_byte_offset']: v for v in recipe['configurations']}
        source_keys = []
        if len(row['configuration_rows']) != len(variants):
            raise ValueError(f'Native forge row count conflict: {item_id}')
        for source_row in row['configuration_rows']:
            variant = variants.get(source_row['forge_record_byte_offset'])
            gates = source_row['configured_gate_fields']
            if (variant is None or source_row['configured_seconds'] != variant['configured_seconds'] or
                    [(i['item_id'], i['quantity']) for i in source_row['ingredients']] !=
                    [(i['item_id'], i['quantity']) for i in variant['ingredients']] or
                    [m['method_id'] for m in source_row['station_methods']] !=
                    [m['method_id'] for m in variant['stations']] or
                    gates['valid_time']['kind'] != 'empty_object' or
                    gates['forge_display'] not in (None, 0) or
                    gates['season_no_field_present'] or gates['can_invent_field_present'] or
                    gates['invent_tech_ids_field_present']):
                raise ValueError(f'Native forge key/recipe/gate conflict: {item_id}')
            keys = []
            for native_key in source_row['forge_keys']:
                raw = native_key['key']
                if isinstance(raw, int) and native_key['key_type'] == 1:
                    forge_no, selector = raw, None
                elif (isinstance(raw, list) and len(raw) == 2 and
                      all(isinstance(value, int) for value in raw) and
                      native_key['key_type'] == 11 and raw[1] in (1, 11, 222, 223)):
                    forge_no, selector = raw
                else:
                    raise ValueError(f'Unsupported native forge key: {item_id}')
                key_token = (forge_no, selector)
                if key_token in seen_keys:
                    raise ValueError(f'Duplicate native forge key: {key_token}')
                seen_keys.add(key_token)
                source_keys.append(raw)
                keys.append({'forge_no': forge_no, 'season_selector': selector})
            if not 1 <= len(keys) <= 2:
                raise ValueError(f'Unexpected native forge aliases: {item_id}')
            aliases += len(keys) == 2
            unlock_tip = gates['unlock_tip']
            unlocks += unlock_tip is not None
            diy += gates['is_diy'] == 1
            variant['forge_keys'] = keys
            variant['configured_gates'] = {
                'empty_valid_time': True,
                'forge_display_zero_or_default': True,
                'is_diy': gates['is_diy'] == 1,
                'build_level': gates['build_lv'],
                'unlock_tip': unlock_tip['installed_english_text'] if unlock_tip else None,
                'current_unlock': 'unknown',
            }
            if item_id == 30110374 and (len(keys) != 1 or
                    keys[0]['forge_no'] != variant['forge_no'] or
                    keys[0]['season_selector'] != variant['forge_season_selector']):
                raise ValueError('Soup full ledger conflicts with independent forge key proof')
        def token(raw):
            return (raw, None) if isinstance(raw, int) else tuple(raw)
        reverse_keys = row['native_item_to_forge_list']['ordered_keys']
        if (len(reverse_keys) != len(source_keys) or
                {token(key) for key in reverse_keys} !=
                {token(key) for key in source_keys}):
            raise ValueError(f'Native item-to-forge reverse list conflict: {item_id}')
        recipe['forge_key_source_sha256'] = SOURCES['native-food-forge-variant-ledger-v1.json']
        recipe['current_server_selection'] = 'unknown'
    if (len(seen_items), len(seen_keys), aliases, unlocks, diy) != (33, 82, 5, 7, 6):
        raise ValueError('Native food forge keys or gate totals conflict')
    return output
