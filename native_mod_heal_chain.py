"""Source-checked Battle heal graph input, without an HP-restoration claim."""
from __future__ import annotations

from functools import lru_cache
import copy
import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parent / 'evidence_packets'
PACKET = ROOT / 'native-battle-heal-secondary-v1.json'
SOURCE = ROOT / 'native-battle-heal-secondary-v1.md'
HASHES = {
    PACKET.name: '88ce92c3614f97eed4e99d88b8f9d292b6a9eaede15a46c292b8b71c8200e345',
    SOURCE.name: '8a4c4ed70ff366eb503b8caa34ad018cbfd7aa2edd28af030c529a92cb07260b',
}
PARENT_BUFF = 581902000


@lru_cache(maxsize=1)
def _source():
    if any(hashlib.sha256(path.read_bytes()).hexdigest() != HASHES[path.name]
           for path in (PACKET, SOURCE)):
        raise ValueError('Battle heal source hash conflict')
    packet = json.loads(PACKET.read_text())
    chain = packet['configured_chain']
    levels = chain['level_values']
    if (packet['installed_build_id'] != '26267212' or
            packet['game_code_executed'] is not False or
            packet['installed_files_modified'] is not False or
            packet['buff_id'] != 581902100 or
            (chain['parent_buff_id'], chain['secondary_buff_id']) != (PARENT_BUFF, 581902100) or
            chain['secondary_node_22_operation']['name'] != 'MUL' or
            chain['kill_event_target_type_raw_array']['values'] != [0] or
            [(row['entry_level'], row['configured_parent_factor']) for row in levels] !=
            [(1, .024), (2, .048), (3, .072), (4, .096), (5, .12)] or
            len(packet['nodes']) != 14):
        raise ValueError('Battle heal configured chain mismatch')
    for vector in chain['synthetic_configured_input_vectors']:
        if (vector['actual_hp_restored'] is not None or
                vector['explicit_max_hp'] * vector['explicit_stored_suck_it_all'] !=
                vector['computed_node22_heal_value_input']):
            raise ValueError('Battle heal source vector mismatch')
    return packet


def node_heal_input(*, explicit_max_hp, explicit_stored_fraction):
    """Compute only the configured NodeHeal input from explicit supplied values."""
    _source()
    if (type(explicit_max_hp) not in (int, float) or
            type(explicit_stored_fraction) not in (int, float) or
            not math.isfinite(explicit_max_hp) or not math.isfinite(explicit_stored_fraction) or
            explicit_max_hp < 0 or explicit_stored_fraction < 0):
        raise ValueError('Battle heal input requires finite nonnegative supplied values')
    return {'node_heal_value_input': explicit_max_hp * explicit_stored_fraction,
            'actual_hp_restored': None, 'target_eligibility_proven': False,
            'server_heal_mutation_proven': False}


def annotate(preview):
    if preview is None:
        return None
    packet = _source()
    out = copy.deepcopy(preview)
    level_values = {row['entry_level']: row['configured_parent_factor']
                    for row in packet['configured_chain']['level_values']}
    for line in out['ordered_lines']:
        if line.get('buff_id') != PARENT_BUFF:
            continue
        if line.get('attribute_status') != 'typed_effect_node_only_arithmetic_unverified':
            raise ValueError('Battle heal graph classification changed')
        level = line['entry_level']
        if level not in level_values:
            raise ValueError('Battle heal entry level unavailable')
        line['configured_heal_input'] = {
            'status': 'configured_node_input_only',
            'configured_parent_factor': level_values[level],
            'expression': 'explicit max_hp × explicit stored suck_it_all fraction',
            'secondary_buff_id': 581902100,
            'kill_target_type_raw': [0], 'kill_target_label_proven': False,
            'parent_save_cast_order_proven': False,
            'actual_hp_restored': None, 'server_heal_mutation_proven': False,
            'source_build': '26267212',
            'source_sha256': HASHES[PACKET.name],
        }
    return out
