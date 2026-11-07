"""Exact item-ID native mod relationships, separate from effects and ownership.

The pinned packet carries icon filenames, not decoded artwork bytes. Nothing in
this module contributes damage, a Field Guide level, or an owned item.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
from pathlib import Path

import catalog

PACKET = Path(__file__).with_name('evidence_packets') / 'native-mod-identity-v2.json'
ICON_PACKET = Path(__file__).with_name('evidence_packets') / 'native-mod-icons-v1.json'
FAMILY_PACKET = Path(__file__).with_name('evidence_packets') / 'native-mod-family-v2.json'
PRECISION_PACKET = Path(__file__).with_name('evidence_packets') / 'native-precision-charge-aero-v1.json'
PRECISION_MD = Path(__file__).with_name('evidence_packets') / 'native-precision-charge-aero-v1.md'
PRECISION_HASHES = {
    PRECISION_PACKET.name: 'ab7fb6c17c3221a872b87f651c2144697ae6da0d9e794c3c794cb5f4697e438b',
    PRECISION_MD.name: 'e92d20f5b97af2c65852090bf9cfc1ff5e366191a94a81386caa16cbe1785cc4',
}
AERO_JOIN_PACKET = Path(__file__).with_name('evidence_packets') / 'native-aero-mod-v2-display-join-v1.json'
AERO_JOIN_MD = Path(__file__).with_name('evidence_packets') / 'native-aero-mod-v2-display-join-v1.md'
AERO_JOIN_HASHES = {
    AERO_JOIN_PACKET.name: '457c3c097f3c8db90056df5cefb55ef3b1fdd4755c6c7634be108d58fd5cda94',
    AERO_JOIN_MD.name: '89f888c4eab806f68d90b32f5a4adaa842da6f98efde0c24b21bafb9eb3afaa5',
}
AERO_LEVEL_PACKET = Path(__file__).with_name('evidence_packets') / 'native-aero-level-buff-v1.json'
AERO_LEVEL_MD = Path(__file__).with_name('evidence_packets') / 'native-aero-level-buff-v1.md'
AERO_GRAPH_PACKET = Path(__file__).with_name('evidence_packets') / 'native-aero-buff-graph-v1.json'
AERO_LEVEL_HASHES = {
    AERO_LEVEL_PACKET.name: 'ccf1089f823d57f1c6d23765cabe3718f54c1ccba98bf687a7cc5d58eb3f8a05',
    AERO_LEVEL_MD.name: 'ff75a197a752265c7d5055145758156c7ef3912e097010e4147914dd7ccad490',
    AERO_GRAPH_PACKET.name: '4b8eb268893961a44eb333ec7eb382b6909e1b2b547961d2d6e4228b2cb799f0',
}
AERO_FOUR_PACKET = Path(__file__).with_name('evidence_packets') / 'native-aero-four-lines-v1.json'
AERO_FOUR_MD = Path(__file__).with_name('evidence_packets') / 'native-aero-four-lines-v1.md'
AERO_CHECKER_PACKET = Path(__file__).with_name('evidence_packets') / 'native-aero-client-checker-v1.json'
AERO_FOUR_HASHES = {
    AERO_FOUR_PACKET.name: 'afe902e1acb1b01607fc169b0f13073e705a52a404d8ece543ca04dc90472f1b',
    AERO_FOUR_MD.name: 'f74ee725f1a17a3049237d7a1f7db535ea907a3f334c534f4deffe536d7434ad',
    AERO_CHECKER_PACKET.name: '1e56091243e4b35dad6729dbf8e9d14c22f0a50b48a6587259e25906a4909999',
}
TWO_FRAME_PACKET = Path(__file__).with_name('evidence_packets') / 'native-two-frame-levels-v1.json'
TWO_FRAME_MD = Path(__file__).with_name('evidence_packets') / 'native-two-frame-levels-v1.md'
AERO_CORE_PACKET = Path(__file__).with_name('evidence_packets') / 'native-aero-core-graph-v1.json'
TWO_FRAME_HASHES = {
    TWO_FRAME_PACKET.name: '17a86d1f265c64413f4a950959ddc63a8277426d7958634f38359285fe21076d',
    TWO_FRAME_MD.name: '266aca2ccd7a50f658f01220e1413b72d3cf4d20cd649e1271ffb760fc6d38d3',
    AERO_CORE_PACKET.name: '502ee43dd9fec111524e06c9b8e4497f87e62b867ce2c3c718799f896ddc133a',
}
AERO_LIFECYCLE_PACKET = Path(__file__).with_name('evidence_packets') / 'native-aero-lifecycle-v1.json'
AERO_LIFECYCLE_MD = Path(__file__).with_name('evidence_packets') / 'native-aero-lifecycle-v1.md'
AERO_LIFECYCLE_HASHES = {
    AERO_LIFECYCLE_PACKET.name: 'b705c6a1360317ab6fa7efd1f194896120c9ef43e58bafb6d9d64b0a8b8b242b',
    AERO_LIFECYCLE_MD.name: 'aa98c7def65e59d18c31f893de8f5c2d9514d0010b8185345b5f47ee598d12ab',
}
AERO_REFRESH_PACKET = Path(__file__).with_name('evidence_packets') / 'native-aero-refresh-v1.json'
AERO_REFRESH_MD = Path(__file__).with_name('evidence_packets') / 'native-aero-refresh-v1.md'
AERO_REFRESH_HASHES = {
    AERO_REFRESH_PACKET.name: 'd9ab0dac386822afe09e01c7208f2608c0c773d8b06c797d05dc244ec3818e1d',
    AERO_REFRESH_MD.name: '3d7a68c8ecc9b66a5af6e74b3e0a5f1c42ffccc5a5da3bcb75d2dcd703467157',
}
TWO_FRAME_IDENTITIES = {
    'mod:weapon_mod:shock-diffusion-survival': ('Shock Diffusion <Survival>', 19500434, 2400434, 19505174, 2410174, 10302, 19, [5101, 7402, 7403, 7405]),
    'mod:weapon_mod:shatter-them-all-shrapnel': ('Shatter Them All <Shrapnel>', 19500304, 2400304, 19505109, 2410109, 10101, 1201, [7311, 7313, 7314, 7405]),
}


@lru_cache(maxsize=1)
def two_frame_source():
    for path in (TWO_FRAME_PACKET, TWO_FRAME_MD, AERO_CORE_PACKET):
        if hashlib.sha256(path.read_bytes()).hexdigest() != TWO_FRAME_HASHES[path.name]:
            raise ValueError('Native two-frame source hash conflict')
    packet = json.loads(TWO_FRAME_PACKET.read_text())
    if packet.get('build_id') != '26267212' or packet.get('game_code_executed') is not False:
        raise ValueError('Native two-frame source/build conflict')
    for identity, (label, normal_item, normal_mod, shiny_item, shiny_mod,
                   family, frame, entries) in TWO_FRAME_IDENTITIES.items():
        variant = packet['variants'][label]
        if (variant['family'], variant['frame'], variant['entry_ids']) != (family, frame, entries):
            raise ValueError(identity + ': native family/frame conflict')
        variants = {row['mode']: (row['item_id'], row['mod_code']) for row in variant['variants']}
        if variants != {'ordinary': (normal_item, normal_mod), 'shiny': (shiny_item, shiny_mod)}:
            raise ValueError(identity + ': native item/variant conflict')
        rows = packet['catalog_previews'][label]
        if len(rows) != 17 or [row['total_level'] for row in rows] != list(range(1, 18)):
            raise ValueError(identity + ': native level coverage conflict')
        for row in rows:
            if (len(row['ordered_lines']) != 4 or
                    [(line['position'], line['entry_no'], line['entry_level'])
                     for line in row['ordered_lines']] !=
                    [(index + 1, entry, row['frame_entry_levels'][index])
                     for index, entry in enumerate(entries)] or
                    any(line['state'] != ('configured' if line['entry_level'] else 'locked')
                        for line in row['ordered_lines'])):
                raise ValueError(identity + ': native row order/unlock conflict')
        if rows[0]['frame_entry_levels'] != [1, 0, 0, 0] or rows[7]['frame_entry_levels'] != [2, 2, 2, 2] or rows[16]['frame_entry_levels'] != [5, 5, 5, 2]:
            raise ValueError(identity + ': native level chart conflict')
    return packet


def two_frame_preview(catalog_id, total_level, *, shiny=False):
    if catalog_id not in TWO_FRAME_IDENTITIES:
        raise ValueError('Not a source-bound native frame identity')
    if isinstance(total_level, bool) or not isinstance(total_level, int) or not 1 <= total_level <= 17:
        raise ValueError('Native frame preview level must be 1–17')
    if not isinstance(shiny, bool) or shiny and total_level != 17:
        raise ValueError('Shiny native preview requires level 17')
    packet = two_frame_source()
    label = TWO_FRAME_IDENTITIES[catalog_id][0]
    row = packet['catalog_previews'][label][total_level - 1]
    return {'catalog_id': catalog_id, 'total_level': total_level, 'shiny': shiny,
            'status': 'exact_native_catalog_configuration',
            'native_frame_code': TWO_FRAME_IDENTITIES[catalog_id][6],
            'ordered_subentry_levels': row['frame_entry_levels'],
            'ordered_lines': row['ordered_lines'],
            'source_build': packet['build_id'], 'source_sha256': TWO_FRAME_HASHES.copy(),
            'owned_roll_inferred': False, 'shiny_separate_buff_inferred': False,
            'server_buff_execution_proven': False, 'runtime_damage_included': False}


@lru_cache(maxsize=1)
def aero_core_math_configuration():
    if hashlib.sha256(AERO_CORE_PACKET.read_bytes()).hexdigest() != TWO_FRAME_HASHES[AERO_CORE_PACKET.name]:
        raise ValueError('Native Aero core graph hash conflict')
    source = json.loads(AERO_CORE_PACKET.read_text())
    if (source['build_id'], source['family_main_entry_no'], source['core_buff_id'],
            source['secondary_buff_id']) != ('26267212', 9318, 589318000, 589318100):
        raise ValueError('Native Aero core graph identity conflict')
    lifecycle = aero_core_lifecycle_source()
    aero_core_refresh_source()
    properties = lifecycle['elemental_property_labels']['properties']
    return {'source_status': 'native_configured_graph_runtime_unverified',
            'source_sha256': TWO_FRAME_HASHES[AERO_CORE_PACKET.name],
            'lifecycle_source_sha256': AERO_LIFECYCLE_HASHES[AERO_LIFECYCLE_PACKET.name],
            'family_main_entry_no': 9318, 'core_buff_id': 589318000,
            'secondary_buff_id': 589318100,
            'configured_expression': source['configured_expression'],
            'buff_levels': source['buff_levels'], 'limits': source['limits'],
            'weak_remote_event_filter': lifecycle['weak_hit_filter'],
            'configured_full_reload_condition': 'reload_post_event_clip_left >= magazine_size',
            'standard_server_cap_if_cast': 6,
            'standard_server_cap_if_cast_proven': True,
            'standard_existing_buff_refresh_if_invoked': 'min(6, existing_stacks + incoming_stacks + 0)',
            'refresh_source_sha256': AERO_REFRESH_HASHES[AERO_REFRESH_PACKET.name],
            'refresh_cast_dispatch_and_prior_dispel_order_proven': False,
            'configured_initial_lifetime_seconds': 10,
            'refresh_expiry_proven': False,
            'named_element_properties': {key: {'native_property': row['native_property'],
                                               'installed_english_label': row['installed_english_label']}
                                         for key, row in properties.items()},
            'field_guide_total_level_to_core_rank_proven': False,
            'actual_cast_and_application_proven': False, 'runtime_damage_included': False}


@lru_cache(maxsize=1)
def aero_core_lifecycle_source():
    for path in (AERO_LIFECYCLE_PACKET, AERO_LIFECYCLE_MD):
        if hashlib.sha256(path.read_bytes()).hexdigest() != AERO_LIFECYCLE_HASHES[path.name]:
            raise ValueError('Native Aero lifecycle source hash conflict')
    row = json.loads(AERO_LIFECYCLE_PACKET.read_text())
    fields = {field['name']: field['value'] for field in
              row['buff_data']['selected']['589318100']['selected_fields']}
    properties = row['elemental_property_labels']['properties']
    if (row['build_id'] != '26267212' or row['game_code_executed'] is not False or
            (fields['buff_max_stack'], fields['life_time'], fields['refresh_buff_stack'],
             fields['refresh_rule']) != (6, 10.0, 0, 0) or
            row['weak_hit_filter']['formula_attack_type']['values'] != [2] or
            row['weak_hit_filter']['attack_damage_type']['values'] != [1] or
            {key: (value['affix_prototype_key'], value['installed_english_label'])
             for key, value in properties.items()} != {
                 'E32': ('E3200', 'Blaze DMG Bonus'),
                 'E33': ('E3300', 'Frost DMG Bonus'),
                 'E34': ('E3400', 'Shock DMG Bonus'),
                 'E38': ('E3800', 'Blast DMG Bonus')}):
        raise ValueError('Native Aero lifecycle cap or element binding conflict')
    return row


@lru_cache(maxsize=1)
def aero_core_refresh_source():
    for path in (AERO_REFRESH_PACKET, AERO_REFRESH_MD):
        if hashlib.sha256(path.read_bytes()).hexdigest() != AERO_REFRESH_HASHES[path.name]:
            raise ValueError('Native Aero refresh source hash conflict')
    row = json.loads(AERO_REFRESH_PACKET.read_text())
    config = row['generic_buff_component']['source_config']
    branch = row['reload_branch']
    if (row['build_id'] != '26267212' or row['game_code_executed'] is not False or
            row['core_graph_source_sha256'] != TWO_FRAME_HASHES[AERO_CORE_PACKET.name] or
            (config['buff_id'], config['buff_max_stack'], config['life_time'],
             config['refresh_buff_stack'], config['refresh_rule']) !=
            (589318100, 6, 10.0, 0, 0) or
            branch['cast_node'] != 61 or branch['cast_parameters']['reset'] != 0 or
            branch['runtime_sibling_order'] != 'unproven'):
        raise ValueError('Native Aero refresh/cast source conflict')
    return row


def aero_core_conditional_refresh(*, existing_buff_stacks, incoming_stacks):
    """Shared-component refresh if invoked; no reload/cast/expiry inference."""
    for name, value, low, high in (('existing_buff_stacks', existing_buff_stacks, 1, 6),
                                    ('incoming_stacks', incoming_stacks, 0, 1000000)):
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            raise ValueError(f'{name} must be a whole number from {low} to {high}')
    source = aero_core_refresh_source()
    config = source['generic_buff_component']['source_config']
    result = min(config['buff_max_stack'], existing_buff_stacks + incoming_stacks +
                 config['refresh_buff_stack'])
    return {'status': 'controlled_existing_buff_refresh_if_invoked',
            'source_sha256': AERO_REFRESH_HASHES[AERO_REFRESH_PACKET.name],
            'existing_buff_stacks': existing_buff_stacks,
            'incoming_stacks': incoming_stacks,
            'standard_refreshed_stacks_if_invoked': result,
            'configured_life_time_seconds': config['life_time'],
            'exact_lifetime_renewal_proven': False,
            'prior_dispel_or_replacement_proven': False,
            'reload_cast_dispatch_proven': False,
            'runtime_damage_included': False}


def aero_core_conditional_scenario(*, magazine_size, qualifying_weak_remote_events,
                                   reload_post_event_clip_left, secondary_level):
    """Controlled native configuration vector, never an owned active buff."""
    def whole(name, value, minimum, maximum):
        if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
            raise ValueError(f'{name} must be a whole number from {minimum} to {maximum}')
        return value
    magazine_size = whole('magazine_size', magazine_size, 1, 1000000)
    weak_events = whole('qualifying_weak_remote_events', qualifying_weak_remote_events, 0, 1000000)
    clip_left = whole('reload_post_event_clip_left', reload_post_event_clip_left, 0, 1000000)
    secondary_level = whole('secondary_level', secondary_level, 1, 5)
    config = aero_core_math_configuration()
    source = config['configured_expression']
    if clip_left < magazine_size:
        return {'status': 'configured_full_reload_condition_not_met',
                'source_status': config['source_status'], 'requested_stacks': None,
                'standard_new_buff_stacks_if_cast': None,
                'bonus_percent_per_named_element_if_cast': None,
                'actual_cast_and_application_proven': False,
                'runtime_damage_included': False,
                'buff_component_branch': 'new_buff_init_if_cast_only'}
    requested = (weak_events * 10) // magazine_size
    stacks = min(config['standard_server_cap_if_cast'], requested)
    rate = float(source['secondary_per_stack_by_level'][str(secondary_level)])
    percent = round(stacks * rate * 100, 9)
    return {'status': 'controlled_native_configuration_if_cast',
            'source_status': config['source_status'],
            'source_sha256': config['source_sha256'],
            'lifecycle_source_sha256': config['lifecycle_source_sha256'],
            'inputs': {'magazine_size': magazine_size,
                       'qualifying_weak_remote_events': weak_events,
                       'reload_post_event_clip_left': clip_left,
                       'secondary_level': secondary_level},
            'requested_stacks': requested,
            'standard_new_buff_stacks_if_cast': stacks,
            'buff_component_branch': 'new_buff_init_if_cast_only',
            'configured_initial_lifetime_seconds': config['configured_initial_lifetime_seconds'],
            'bonus_percent_per_named_element_if_cast': {
                row['installed_english_label']: percent
                for row in config['named_element_properties'].values()},
            'field_guide_total_level_to_core_rank_proven': False,
            'actual_cast_and_application_proven': False,
            'runtime_damage_included': False}


@lru_cache(maxsize=1)
def aero_four_line_source():
    for path in (AERO_FOUR_PACKET, AERO_FOUR_MD, AERO_CHECKER_PACKET):
        if hashlib.sha256(path.read_bytes()).hexdigest() != AERO_FOUR_HASHES[path.name]:
            raise ValueError('Aero four-line source hash conflict')
    packet = json.loads(AERO_FOUR_PACKET.read_text())
    checker = json.loads(AERO_CHECKER_PACKET.read_text())
    levels = packet['catalog_levels_1_through_17']
    if (packet['build_id'] != '26267212' or
            (packet['item_id'], packet['mod_code'], packet['frame']) != (19500811, 2400811, 26) or
            len(levels) != 17 or
            [row['total_level'] for row in levels] != list(range(1, 18)) or
            checker['build_id'] != '26267212' or checker['graph_sha256'] !=
            AERO_LEVEL_HASHES[AERO_GRAPH_PACKET.name] or
            checker['graph_trigger_op']['decoded'] != 'OR' or
            {row['state_code'] for row in checker['graph_states']} != {40, 2, 83, 110, 111, 95} or
            levels[0]['frame_entry_levels'] != [1, 0, 0, 0] or
            levels[7]['frame_entry_levels'] != [2, 2, 2, 2] or
            levels[16]['frame_entry_levels'] != [5, 5, 5, 2]):
        raise ValueError('Aero full catalog level or client checker source conflict')
    entries = (2601, 2602, 7405, 5101)
    native_attrs = ('E42', 'E02', ['E101', 'E99', 'E102', 'E100'], 'A0202 -> A02')
    for level in levels:
        rows = level['ordered_lines']
        if (len(rows) != 4 or
                [(row['position'], row['entry_no'], row['entry_level']) for row in rows] !=
                [(index + 1, entry, level['frame_entry_levels'][index])
                 for index, entry in enumerate(entries)]):
            raise ValueError('Aero full catalog line ordering conflict')
        for index, row in enumerate(rows):
            if row['state'] != ('configured' if row['entry_level'] else 'locked'):
                raise ValueError('Aero full catalog unlock conflict')
            if row['state'] == 'configured' and row['native_attribute'] != native_attrs[index]:
                raise ValueError('Aero full catalog property identity conflict')
    return packet, checker


def aero_four_line_preview(total_level, shiny=False):
    """All four configured catalog lines, with no owned or server-active claim."""
    if isinstance(total_level, bool) or not isinstance(total_level, int) or not 1 <= total_level <= 17:
        raise ValueError('Aero preview total level must be 1–17')
    packet, checker = aero_four_line_source()
    base = {'catalog_id': 'mod:pants_mod:precision-charge-aero',
            'total_level': total_level, 'native_frame_code': 26,
            'source_build': '26267212', 'source_sha256': AERO_FOUR_HASHES.copy(),
            'owned_roll_inferred': False, 'server_buff_execution_proven': False,
            'runtime_damage_included': False}
    if shiny:
        return {**base, 'status': 'ordinary_variant_only', 'ordered_lines': []}
    row = packet['catalog_levels_1_through_17'][total_level - 1]
    names = ('Weapon DMG', 'Crit DMG', 'Damage to all monsters', 'Max HP')
    lines = []
    for index, native in enumerate(row['ordered_lines']):
        line = {'position': index + 1, 'name': names[index],
                'entry_no': native['entry_no'], 'entry_level': native['entry_level'],
                'state': native['state'], 'locked': native['state'] == 'locked',
                'native_attribute': native.get('native_attribute'),
                'source_row_literal_offset': native.get('source_row_literal_offset'),
                'value_percent': None, 'conditional_bonus_percent': None,
                'effect_activated': False}
        if native['state'] == 'configured':
            line['value_percent'] = float(native['percent_values'][0])
            if len(native['percent_values']) == 2:
                line['conditional_bonus_percent'] = float(native['percent_values'][1])
            line['catalog_text'] = native['catalog_text']
        if index == 2:
            line['installed_english_label'] = 'Increases damage dealt to all DMG Boost by ...'
            line['source_warning'] = ('Installed English says DMG Boost; native source means '
                                      'damage to all monsters. Runtime target application is unverified.')
        lines.append(line)
    return {**base, 'status': 'exact_native_catalog_configuration',
            'ordered_subentry_levels': row['frame_entry_levels'],
            'ordered_lines': lines,
            'client_aerial_checker': {'combination': 'OR',
                'state_codes': [item['state_code'] for item in checker['graph_states']],
                'client_only': True, 'server_application_proven': False}}


@lru_cache(maxsize=1)
def aero_level_source():
    for path in (AERO_LEVEL_PACKET, AERO_LEVEL_MD, AERO_GRAPH_PACKET):
        if hashlib.sha256(path.read_bytes()).hexdigest() != AERO_LEVEL_HASHES[path.name]:
            raise ValueError('Aero level and buff source hash conflict')
    packet = json.loads(AERO_LEVEL_PACKET.read_text())
    graph = json.loads(AERO_GRAPH_PACKET.read_text())
    if (packet['build_id'] != '26267212' or graph['build_id'] != '26267212' or
            packet['aero_frame'] != {'mod_code': 2400811, 'frame': 26,
                'ordered_entry_numbers': [2601, 2602, 7405, 5101]} or
            packet['buff_level_map']['selected_max_level']['582601000'] != 5 or
            [(row['level'], row['display_values_percent']['strings'])
             for row in packet['buff_level_data']['buff_rows']] != [
                 (1, ['1.2', '0.6']), (2, ['2.4', '1.2']),
                 (3, ['3.6', '1.8']), (4, ['4.8', '2.4']), (5, ['6', '3'])] or
            {node['params']['fields']['attribute']['string'] for node in graph['nodes']
             if node['node_id'] in (20, 31)} != {'attack_type_dam_add_rate_remote'} or
            packet['total_level_8_configured_vector']['frame_entry_levels'] != [2, 2, 2, 2]):
        raise ValueError('Aero level, buff or E42 graph configuration conflict')
    for row in packet['buff_level_data']['buff_rows']:
        first, extra = map(float, row['display_values_percent']['strings'])
        params = row['runtime_params']['values']
        if abs(float(params['1']) * 100 - first) > 1e-9 or abs(float(params['2']) * 100 - extra) > 1e-9:
            raise ValueError('Aero displayed and configured values conflict')
    return packet


def precision_charge_aero_preview(total_level, shiny=False):
    """Compatibility view of the first native row at every total level."""
    full = aero_four_line_preview(total_level, shiny=shiny)
    common = {'catalog_id': 'mod:pants_mod:precision-charge-aero',
              'total_level': total_level, 'native_frame_code': 26,
              'native_property_id': 'E42',
              'native_property': 'attack_type_dam_add_rate_remote',
              'source_build': '26267212', 'source_sha256': AERO_FOUR_HASHES.copy(),
              'owned_roll_inferred': False, 'effect_activated': False,
              'runtime_damage_included': False}
    if shiny:
        return {**common, 'status': 'ordinary_variant_only', 'entry_level': None,
                'base_percent': None, 'aerial_extra_percent': None}
    first = full['ordered_lines'][0]
    first_level = first['entry_level']
    base, extra = first['value_percent'], first['conditional_bonus_percent']
    return {**common, 'status': 'exact_native_catalog_tooltip_configuration',
            'ordered_subentry_levels': full['ordered_subentry_levels'],
            'first_entry_key': [2601, first_level],
            'configured_buff_id': 582601000, 'entry_level': first_level,
            'base_percent': base, 'aerial_extra_percent': extra,
            'display_text': f'Weapon DMG +{base:g}%, additional +{extra:g}% for aerial hits',
            'aerial_runtime_condition_proven': False}


@lru_cache(maxsize=1)
def aero_v2_entry_join():
    """Exact composite keys and serialized E42 target, never an owned roll."""
    for path in (AERO_JOIN_PACKET, AERO_JOIN_MD):
        if hashlib.sha256(path.read_bytes()).hexdigest() != AERO_JOIN_HASHES[path.name]:
            raise ValueError('Aero V2 entry join source hash conflict')
    packet = json.loads(AERO_JOIN_PACKET.read_text())
    rows = packet['selected_composite_entries']
    group = {(row['entry_no'], row['entry_level']): row for row in rows}
    if (packet['installed_build_id'] != '26267212' or
            (packet['item_id'], packet['mod_code'], packet['main_entry_no'], packet['frame_code']) !=
            (19500811, 2400811, 9318, 26) or
            packet['entry_count_validated'] != 1262 or
            packet['ordered_frame_sub_entry_item_no'] != [2601, 2602, 7405, 5101] or
            len(group) != len(rows) or
            sorted(level for entry, level in group if entry == 9318) != [4, 5] or
            any(sorted(level for entry, level in group if entry == subentry) != list(range(1, 7))
                for subentry in (2601, 2602, 7405, 5101)) or
            {group[(9318, 4)]['key_pointer_body_relative'],
             group[(9318, 5)]['key_pointer_body_relative']} != {58166, 19289} or
            next(row for row in packet['graph_identifiers'] if row['buff_id'] == 582601000)
            ['property_name'] != 'attack_type_dam_add_rate_remote'):
        raise ValueError('Aero V2 entry join or pointer correction conflict')
    return {'ordered_subentry_keys': [2601, 2602, 7405, 5101],
            'available_main_entry_composite_keys': [[9318, 4], [9318, 5]],
            'active_main_entry_composite_key': None,
            'first_subentry_key': 2601,
            'first_subentry_serialized_property_id': 'E42',
            'first_subentry_serialized_property': 'attack_type_dam_add_rate_remote',
            'first_subentry_selected_level': None,
            'first_subentry_selected_value': None,
            'first_subentry_effect_activated': False,
            'old_scalar_entry_ids_are_pointers': [19289, 58166],
            'field_guide_level_to_entry_level_proven': False,
            'calculation_included': False,
            'source_sha256': AERO_JOIN_HASHES.copy()}


@lru_cache(maxsize=1)
def precision_charge_aero_identity():
    """Frame 26 is an Aero layout code, not Field Guide level or core rank."""
    for path in (PRECISION_PACKET, PRECISION_MD):
        if hashlib.sha256(path.read_bytes()).hexdigest() != PRECISION_HASHES[path.name]:
            raise ValueError('Precision Charge Aero source hash conflict')
    packet = json.loads(PRECISION_PACKET.read_text())
    fields = packet['mod_property_row']['selected_fields']
    if (packet['build_id'] != '26267212' or
            packet['item_link']['item_id'] != 19500811 or
            packet['item_link']['mod_code'] != 2400811 or
            packet['mod_property_row']['mod_code'] != 2400811 or
            fields != {'item_no': 19500811, 'main_entry_no': 9318,
                       'frame': 26, 'is_shiny_mod': 0,
                       'shiny_replace_mod_code': 2410208,
                       'mode_component_id': 19000027} or
            packet['main_entry_group']['key'] != 9318 or
            packet['main_entry_group']['member']['mod_code'] != 2400811 or
            packet['mod_property_row']['english_name']['english_text'] != 'Precision Charge <Aero>' or
            packet['weapon_label_collision']['D0102']['attr_id'] != 'D01' or
            packet['weapon_label_collision']['E4200']['attr_id'] != 'E42'):
        raise ValueError('Precision Charge Aero identity or ambiguity conflict')
    entry_join = aero_v2_entry_join()
    return {'native_item_id': '19500811', 'native_mod_code': 2400811,
            'native_main_entry_family': 9318, 'native_layout_frame_code': 26,
            'frame_meaning': 'Aero visual/subattribute layout, not level or rank',
            'native_shiny_replacement_mod_code': 2410208,
            'selected_native_affix_ids': None, 'active_main_entry_id': None,
            'native_v2_entry_join': entry_join,
            'field_guide_level_inferred': False, 'core_rank_inferred': False,
            'main_effect_activated': False, 'calculation_included': False,
            'source_build': '26267212',
            'source_sha256': PRECISION_HASHES.copy()}


@lru_cache(maxsize=1)
def families():
    packet = json.loads(FAMILY_PACKET.read_text())
    if packet.get('schema_version') != 1 or packet.get('status') != 'native_family_membership_identity_only' or \
            packet.get('source', {}).get('installed_build_id') != '26267212':
        raise ValueError('Native mod family packet source/build conflict')
    _, linked = load()
    by_catalog = {}
    for family in packet['families']:
        group = family['native_main_entry_no']
        for catalog_id in family['catalog_ids']:
            pair = linked.get(catalog_id)
            if pair is None or catalog_id in by_catalog or \
                    any(row['native_main_entry_no'] != group for row in pair.values()):
                raise ValueError('Native family and exact-ID crosswalk conflict')
            by_catalog[catalog_id] = {'catalog_family': family['catalog_family'],
                                      'slot': family['slot'], 'native_main_entry_no': group,
                                      'family_membership_verified': True,
                                      'effect_formula_inferred': False}
    if len(packet['families']) != 25 or len(by_catalog) != len(linked):
        raise ValueError('Native family crosswalk coverage mismatch')
    return by_catalog


@lru_cache(maxsize=1)
def icons():
    packet = json.loads(ICON_PACKET.read_text())
    source = json.loads(PACKET.read_text())
    if packet.get('schema_version') != 1 or packet.get('installed_build_id') != '26267212' or \
            packet.get('native_mod_records_sha256') != source['source']['native_packet_sha256']:
        raise ValueError('Native icon packet source/build conflict')
    found = {}
    for row in packet['assets']:
        filename = row['native_icon_filename']
        if not filename.startswith('icon_mods_') or not filename.endswith('.png') or \
                filename in found or '/' in filename or '\\' in filename:
            raise ValueError('Invalid or repeated native icon filename')
        path = Path(__file__).with_name('static') / 'artwork' / ('native_mod__' + filename)
        if hashlib.sha256(path.read_bytes()).hexdigest() != row['png_sha256']:
            raise ValueError(f'Native icon bytes conflict: {filename}')
        found[filename] = {'path': '/artwork/' + path.name,
                           'source_pack': row['source_pack'],
                           'source_entry_id': row['entry_id'],
                           'png_sha256': row['png_sha256']}
    if len(found) != 32:
        raise ValueError('Native icon set is incomplete')
    return found


@lru_cache(maxsize=1)
def load():
    packet = json.loads(PACKET.read_text())
    if packet.get('schema_version') != 1 or packet.get('status') != 'exact_item_id_identity_evidence_only':
        raise ValueError('Native mod identity packet is not a reviewed identity source')
    source = packet.get('source') or {}
    if source.get('steam_build_id') != '26267212' or source.get('archive_entry') != \
            'game_common\\data\\new_mod_property_data.pyc':
        raise ValueError('Native mod identity source/build conflict')
    grouped = {}
    native_ids = set()
    for link in packet.get('links') or []:
        identity, kind = link.get('catalog_id'), link.get('variant_kind')
        if identity not in catalog.ENTRIES or catalog.ENTRIES[identity]['kind'] != 'mod' or kind not in ('normal', 'shiny'):
            raise ValueError('Unknown mod identity or variant in native packet')
        if link.get('calculation_included') is not False or link.get('image_bytes_available') is not False:
            raise ValueError('Native identity packet must not claim formula or image bytes')
        if not isinstance(link.get('native_item_no'), str) or not link['native_item_no'].isdecimal():
            raise ValueError('Native mod item ID missing')
        if not isinstance(link.get('native_mod_code'), int) or not isinstance(link.get('native_icon_filename'), str):
            raise ValueError('Native mod code or icon filename missing')
        if link['native_item_no'] in native_ids:
            raise ValueError('Native item ID linked to more than one catalog identity')
        native_ids.add(link['native_item_no'])
        pair = grouped.setdefault(identity, {})
        if kind in pair:
            raise ValueError('Duplicate native variant identity')
        pair[kind] = link
    if len(grouped) != packet['coverage']['linked_catalog_identities'] or \
            sum(map(len, grouped.values())) != packet['coverage']['exact_item_id_links']:
        raise ValueError('Native mod identity coverage mismatch')
    for identity, pair in grouped.items():
        if 'normal' in pair and 'shiny' in pair and \
                pair['normal']['native_shiny_replacement_mod_code'] != pair['shiny']['native_mod_code']:
            raise ValueError(f'{identity}: normal-to-Shiny replacement conflict')
    return source, grouped


def for_catalog(catalog_id):
    source, grouped = load()
    icon_rows = icons()
    pair = grouped.get(catalog_id)
    if pair is None:
        return None
    def row(link):
        icon = icon_rows.get(link['native_icon_filename'])
        return {'item_id': link['native_item_no'], 'mod_code': link['native_mod_code'],
                'icon_filename': link['native_icon_filename'],
                'icon_artwork': icon,
                'source_url': link.get('public_source_url')}
    normal = row(pair['normal']) if 'normal' in pair else None
    shiny = row(pair['shiny']) if 'shiny' in pair else None
    artwork = (normal or shiny).get('icon_artwork') or {}
    family = families().get(catalog_id)
    return {'source_status': 'exact_native_item_id_identity_only',
            'steam_build_id': source['steam_build_id'],
            'archive_sha256': source['archive_sha256'],
            'normal': normal, 'shiny': shiny,
            'normal_to_shiny_link_verified': normal is not None and shiny is not None,
            'calculation_included': False,
            'image_bytes_available': bool(artwork),
            'native_artwork_path': artwork.get('path'),
            'native_family': family,
            'exact_native_layout_identity': (precision_charge_aero_identity()
                if catalog_id == 'mod:pants_mod:precision-charge-aero' else None),
            'ownership_implied': False,
            'field_guide_level_rule_inferred': False}
