"""Eight more exact buff graph target joins, with runtime value paths gated."""
from __future__ import annotations

from functools import lru_cache
import copy
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PACKET = ROOT / 'evidence_packets/native-mod-buff-batch2-v1.json'
SOURCE_MD = ROOT / 'evidence_packets/native-mod-buff-batch2-v1.md'
HASHES = {PACKET.name: '7c428b59c6a6e4f9511413855b3c2ec45e450c12b14acb174fbc68cf07f131d4',
          SOURCE_MD.name: '5d290cbc2e79eb75f55acdf8f0506da83faac4501ee902eaa8ed22f29f90f4a9'}
EXPECTED_BUFFS = {589720000, 582003000, 582005000, 582603000,
                  582604000, 587364000, 587365000, 587366000}
UNBOUND_CONSTANT_LINKS = {589720000, 582003000, 582603000, 582604000}
FORTRESS = {587364000, 587365000, 587366000}
AERO = {582603000, 582604000}
LUNAR = {582003000, 582005000}


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@lru_cache(maxsize=1)
def _source():
    if any(_sha(path) != HASHES[path.name] for path in (PACKET, SOURCE_MD)):
        raise ValueError('Native mod buff batch 2 source hash conflict')
    packet = json.loads(PACKET.read_text())
    import native_mod_frame_catalog
    import native_priority_mod_buff
    native, _, previews = native_mod_frame_catalog._source()
    _, priority = native_priority_mod_buff._source()
    coverage = packet['coverage']
    if (packet['installed_build_id'] != native['build_id'] or
            packet['sources']['catalog_packet_sha256'] !=
            native_mod_frame_catalog.HASHES[native_mod_frame_catalog.PACKET.name] or
            packet['game_code_executed'] is not False or
            packet['installed_files_modified'] is not False or
            set(priority) != native_priority_mod_buff.EXPECTED_BUFFS or
            (coverage['buff_ids_total'], coverage['previously_typed_target_ids'],
             coverage['new_typed_target_ids'], coverage['typed_target_ids_total'],
             coverage['remaining_graph_target_ids'],
             coverage['newly_target_classified_preview_lines']) != (49, 9, 8, 17, 32, 131)):
        raise ValueError('Native mod buff batch 2 build/coverage conflict')
    rows = {row['buff_id']: row for row in packet['new_buffs']}
    ledger = {row['buff_id']: row for row in packet['all_49_buff_id_coverage_ledger']}
    if set(rows) != EXPECTED_BUFFS or len(ledger) != 49 or \
            len(packet['remaining_buff_ids']) != 32 or \
            sum(ledger[buff]['configured_preview_line_count'] for buff in rows) != 131:
        raise ValueError('Native mod buff batch 2 ID/line count conflict')
    for buff_id, row in rows.items():
        if (ledger[buff_id]['graph_target_status'] != 'typed_graph_target_batch2' or
                not row['graph_pyc_sha256'] or not row['graph_literal_sha256'] or
                not row['targets'] or row['executor_status'] != 'not proven'):
            raise ValueError('Native mod buff batch 2 target proof incomplete')
        targets = {(target['native_attr_id'], target['native_property'])
                   for target in row['targets']}
        if any(not attr or not prop for attr, prop in targets) or \
                {attr for attr, _ in targets} != set(ledger[buff_id]['native_target_attr_ids']):
            raise ValueError('Native mod buff batch 2 typed target conflict')
        if not any(line.get('buff_id') == buff_id for preview in previews.values()
                   for line in preview['ordered_lines']):
            raise ValueError('Native mod buff batch 2 target not used by a frame')
        if buff_id in FORTRESS:
            checker_tags = [entry['params']['check_buff_tag']['value']
                            for checker in row['checkers'] for condition in checker['checks']
                            for entry in condition.get('entries') or []
                            if entry.get('checker_type') == 'buff_tag_type_checker']
            if checker_tags != [305]:
                raise ValueError('Fortress Warfare checker tag conflict')
    return packet, rows


def annotate(preview):
    if preview is None:
        return None
    _, rows = _source()
    out = copy.deepcopy(preview)
    for line in out['ordered_lines']:
        buff_id = line.get('buff_id')
        row = rows.get(buff_id)
        if row is None:
            continue
        if line.get('attribute_status') != 'graph_attribute_unverified':
            raise ValueError('Native mod buff batch 2 overlaps a prior typed target')
        targets = {(target['native_attr_id'], target['native_property'])
                   for target in row['targets']}
        line['native_attributes'] = [{'attr_id': attr, 'property': prop}
                                     for attr, prop in sorted(targets)]
        line['attribute_status'] = 'typed_graph_target_verified_execution_unproven'
        line['graph_target_source_sha256'] = HASHES[PACKET.name]
        line['runtime_value_binding_proven'] = False
        line['server_application_proven'] = False
        line['unbound_level_constant_link'] = buff_id in UNBOUND_CONSTANT_LINKS
        line['checker_scope'] = ('tag_305_configured_producer_unverified' if buff_id in FORTRESS else
                                 'six_state_aerial_checker_server_unverified' if buff_id in AERO else
                                 'hp_related_curve_executor_unverified' if buff_id in LUNAR else
                                 'no_checker_in_captured_graph')
    out['batch2_graph_crosswalk_source_sha256'] = HASHES[PACKET.name]
    return out
