"""Controlled configured Soup input, never an applied food or damage bonus."""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path

import native_named_catalog
import native_food_whim_graphs


SOURCE = Path(__file__).resolve().parent / 'evidence_packets/native-sparkling-pumpkin-rate-v1.json'
SOURCE_SHA256 = '87c68fb947b639b9a9084f26ef2fe39b5c0a1dbcae4e7c4f6aacafd50e02c475'


@lru_cache(maxsize=1)
def proof():
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError('Sparkling Pumpkin source packet changed')
    packet = json.loads(SOURCE.read_text())
    named = next(row for row in native_named_catalog.records()
                 if row['catalog_id'] == 'aid:consumable:30110374')
    graph = native_food_whim_graphs.records()[30110374]['graphs'][0]
    target = graph['target_properties'][0]
    if (packet['installed_build_id'] != '26267212' or
            packet['item_id'] != 30110374 or packet['item_name'] != named['name'] or
            packet['configured_buff_id'] != graph['buff_id'] or
            packet['nominal_buff_lifetime_seconds'] != named['native_buff_nominal_seconds'] or
            packet['meme_mastery_buff_enhance_type'] != 4010 or
            packet['target_native_attr_id'] != target['native_attr_id'] or
            packet['target_native_property'] != target['native_property'] or
            target['configured_expression'] != '((buff.effect_rate + 1.0) * 0.1)' or
            packet['game_code_executed'] is not False or
            packet['installed_game_modified'] is not False):
        raise ValueError('Sparkling Pumpkin item, graph, or source scope conflict')
    return packet


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Enhancement inputs must be finite numbers')
    return float(value)


def configured_input(data):
    """Preview the graph input from explicit 4010 first-values only."""
    packet = proof()
    if not isinstance(data, dict) or set(data) != {'item_4010_first_value', 'pal_4010_first_values'}:
        raise ValueError('Supply only the item 4010 first-value and Pal 4010 first-values')
    item = data['item_4010_first_value']
    pal = data['pal_4010_first_values']
    if item is not None:
        item = _number(item)
    if not isinstance(pal, list) or len(pal) > 128:
        raise ValueError('Pal 4010 first-values must be a list of at most 128 numbers')
    values = [_number(value) for value in pal]
    rate = math.fsum(([item] if item is not None else []) + values)
    if not math.isfinite(rate):
        raise ValueError('Combined enhancement rate must be finite')
    node_input = (1.0 + rate) * 0.1
    if not math.isfinite(node_input):
        raise ValueError('Configured node input must be finite')
    return {
        'source_build': packet['installed_build_id'],
        'item_id': packet['item_id'], 'buff_id': packet['configured_buff_id'],
        'native_attr_id': 'E121', 'source_packet_sha256': SOURCE_SHA256,
        'item_4010_first_value': item, 'pal_4010_first_values': values,
        'effect_rate_if_helper_called': rate,
        'helper_emits_effect_rate_key': rate != 0.0,
        'constructor_default_if_key_absent': 0.0 if rate == 0.0 else None,
        'configured_E121_node_input_if_reached': node_input,
        'nominal_buff_lifetime_seconds': packet['nominal_buff_lifetime_seconds'],
        'scope': 'controlled_source_graph_input_only',
        'item_use_transfer_proven': False, 'active_buff_proven': False,
        'actual_power_surge_damage_bonus': None, 'actual_aug_damage': None,
    }
