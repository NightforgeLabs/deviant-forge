"""Two source-linked raw food buff attributes; activation is unproven."""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
from pathlib import Path
import struct

PACKET = Path(__file__).with_name('evidence_packets') / 'named-food-bonus-reference-v1.json'
PACKET_SHA256 = 'a3062987f86ca6efc627b4f19e13b0b7d2ebc7dd1d1dd742b209346009cf7a4c'
EXPECTED = {30119705: (499008005, 4), 30119710: (499008010, 1)}


@lru_cache(maxsize=1)
def records():
    raw = PACKET.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PACKET_SHA256:
        raise ValueError('Native food bonus packet hash conflict')
    packet = json.loads(raw)
    if (packet.get('installed_build_id') != '26267212' or
            packet.get('game_code_executed') is not False or
            packet.get('installed_files_modified') is not False or
            len(packet.get('records') or []) != 2):
        raise ValueError('Native food bonus build or coverage conflict')
    result = {}
    for row in packet['records']:
        item_id, buff_id = row.get('item_id'), row.get('direct_buff_effect_list_id')
        attributes = row.get('graph', {}).get('attributes') or []
        if (item_id not in EXPECTED or buff_id != EXPECTED[item_id][0] or
                len(attributes) != EXPECTED[item_id][1] or item_id in result or
                row.get('graph_entry', {}).get('buff_id') != buff_id or
                row.get('graph', {}).get('graph_condition') !=
                'Entry NodeBuffNone directly targets NodeChangeAttr; no other condition node exists in this two-node graph.'):
            raise ValueError('Native food bonus identity or graph conflict')
        checked = []
        for attr in attributes:
            bytes_value = bytes.fromhex(attr['value_raw_hex'])
            if (len(bytes_value) != 8 or
                    struct.unpack('<d', bytes_value)[0] != attr['value_float64'] or
                    attr.get('value_type_raw') != 1 or
                    not attr.get('attribute') or not attr.get('native_attr_id_if_mapped')):
                raise ValueError('Native food raw attribute value conflict')
            checked.append({'native_attribute': attr['attribute'],
                            'native_attr_id': attr['native_attr_id_if_mapped'],
                            'raw_value': attr['value_float64'],
                            'source_value_offset': attr['value_byte_offset'],
                            'application': 'unverified'})
        result[item_id] = {'native_buff_id': buff_id,
                           'source_english_title': row['installed_english_item_title'],
                           'nominal_seconds': row['nominal_life_time_seconds'],
                           'raw_attributes': checked,
                           'source_packet_sha256': PACKET_SHA256,
                           'application': 'source_graph_fields_only_not_applied'}
    if set(result) != set(EXPECTED):
        raise ValueError('Native food bonus identity set conflict')
    return result
