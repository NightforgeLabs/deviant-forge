"""Four source-typed buff graph targets and seven historical identity candidates.

Graph target IDs are evidence about configuration, not proof of server equip,
executor behavior, owned variant, or an active combat magnitude.
"""
from __future__ import annotations

from functools import lru_cache
import copy
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PACKET = ROOT / 'evidence_packets/native-priority-mod-buff-crosswalk-v1.json'
SOURCE_MD = ROOT / 'evidence_packets/native-priority-mod-buff-crosswalk-v1.md'
HASHES = {PACKET.name: '2e22b2a3a9d9fd6ce703337a438172cfbfd8303d63430347ca493ba8ef97cd3f',
          SOURCE_MD.name: '40ad5aabd5be9bf1f0c5a206850b5484de1030a434f7c2eba78cb75442eed103'}
EXPECTED_BUFFS = {581110000, 582001000, 582004000, 582006000}


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@lru_cache(maxsize=1)
def _source():
    if any(_sha(path) != HASHES[path.name] for path in (PACKET, SOURCE_MD)):
        raise ValueError('Priority mod buff graph source hash conflict')
    packet = json.loads(PACKET.read_text())
    import native_mod_frame_catalog
    native, identities, previews = native_mod_frame_catalog._source()
    if (packet['installed_build_id'] != native['build_id'] or
            packet['sources']['catalog_packet_sha256'] !=
            native_mod_frame_catalog.HASHES[native_mod_frame_catalog.PACKET.name] or
            packet['game_code_executed'] is not False or
            packet['installed_files_modified'] is not False or
            set(packet['new_graph_buff_ids']) != EXPECTED_BUFFS or
            {row['buff_id'] for row in packet['buff_crosswalk']} != EXPECTED_BUFFS or
            len(packet['historical_seven']) != 7):
        raise ValueError('Priority mod buff graph identity/build conflict')
    graph = {}
    for row in packet['buff_crosswalk']:
        buff_id = row['buff_id']
        if not row['graph_targets'] or not row['graph_pyc_sha256'] or not row['graph_literal_sha256']:
            raise ValueError('Priority buff target proof incomplete')
        for target in row['graph_targets']:
            if not target['native_attr_id'] or not target['native_property']:
                raise ValueError('Priority buff target lacks typed attribute')
        if not any(line.get('buff_id') == buff_id for preview in previews.values()
                   for line in preview['ordered_lines']):
            raise ValueError('Priority buff not referenced by native preview')
        graph[buff_id] = row
    seen = set()
    for row in packet['historical_seven']:
        key = (row['observed_name_suffix'], row['observed_total_level'])
        if key in seen or len(row['candidate_native_identities']) != 2:
            raise ValueError('Historical mod candidate duplicate or missing variant')
        seen.add(key)
        for identity in row['candidate_native_identities']:
            native_identity = identities.get(identity['item_no'])
            if not native_identity or (identity['mod_code'], identity['frame'],
                    identity['is_shiny_mod']) != (
                    native_identity['mod_code'], native_identity['frame'],
                    native_identity['is_shiny_mod']) or identity['frame'] != row['configured_frame']:
                raise ValueError('Historical candidate native item/frame conflict')
    return packet, graph


def annotate(preview):
    """Attach typed graph targets to copied preview lines; leave values unchanged."""
    if preview is None:
        return None
    _, graph = _source()
    out = copy.deepcopy(preview)
    for line in out['ordered_lines']:
        row = graph.get(line.get('buff_id'))
        if row is None:
            continue
        if line.get('attribute_status') != 'graph_attribute_unverified':
            raise ValueError('Priority buff target was already typed by a different source')
        targets = {(target['native_attr_id'], target['native_property'])
                   for target in row['graph_targets']}
        line['attribute_status'] = 'typed_graph_target_verified_execution_unproven'
        line['native_attributes'] = [{'attr_id': attr, 'property': prop}
                                     for attr, prop in sorted(targets)]
        line['graph_target_source_sha256'] = HASHES[PACKET.name]
        line['server_application_proven'] = False
    out['priority_graph_crosswalk_source_sha256'] = HASHES[PACKET.name]
    return out


def historical_candidate(card):
    """Name/suffix and level match only; never identify the owned variant."""
    packet, _ = _source()
    key = (f"{card['name_visible']} <{card['suffix_visible']}>", card['level_visible'])
    matched = [row for row in packet['historical_seven']
               if (row['observed_name_suffix'], row['observed_total_level']) == key]
    if len(matched) != 1:
        return None
    row = matched[0]
    if row['observed_roll_text'] != card['rolls_visible']:
        raise ValueError('Historical mod card/source roll mismatch')
    import native_mod_frame_catalog
    _, _, previews = native_mod_frame_catalog._source()
    configured = annotate(previews[(row['configured_frame'], row['observed_total_level'])])
    typed = [{'position': line['position'], 'text': line['text'],
              'native_attributes': line['native_attributes']}
             for line in configured['ordered_lines']
             if line.get('attribute_status') ==
             'typed_graph_target_verified_execution_unproven']
    return {'status': 'normal_or_shiny_native_identity_candidate',
            'native_frame_code': row['configured_frame'],
            'candidate_native_item_nos': [identity['item_no']
                                          for identity in row['candidate_native_identities']],
            'observed_total_level': row['observed_total_level'],
            'newly_typed_graph_targets': typed,
            'candidate_variant_proven': False, 'server_application_proven': False,
            'source_sha256': HASHES[PACKET.name]}
