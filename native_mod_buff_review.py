"""Complete static review ledger for 49 V2 frame buff graph IDs.

Attribute targets and effect-node classes describe captured configuration.
Nothing here certifies owned activation, executor arithmetic, or damage.
"""
from __future__ import annotations

from functools import lru_cache
import copy
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PACKET = ROOT / 'evidence_packets/native-all-mod-buff-review-v1.json'
SOURCE_MD = ROOT / 'evidence_packets/native-all-mod-buff-review-v1.md'
HASHES = {PACKET.name: 'f25828d5b6c0c1ff2802c2a9669cd0b9c73e80cef9bba5c1ecf4ef8cca296f12',
          SOURCE_MD.name: '2ccc4296228ada0f67ecedf7040db5e34a810a61d3a7ea0735926c9193b946f8'}
EFFECT_ONLY = {581902000, 582303000, 582403000}


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@lru_cache(maxsize=1)
def _source():
    if any(_sha(path) != HASHES[path.name] for path in (PACKET, SOURCE_MD)):
        raise ValueError('Native mod buff full review source hash conflict')
    packet = json.loads(PACKET.read_text())
    import native_mod_frame_catalog
    import native_mod_buff_batch2
    native, _, previews = native_mod_frame_catalog._source()
    prior, _ = native_mod_buff_batch2._source()
    coverage = packet['coverage']
    if (packet['installed_build_id'] != native['build_id'] or
            packet['sources']['catalog_sha256'] !=
            native_mod_frame_catalog.HASHES[native_mod_frame_catalog.PACKET.name] or
            packet['game_code_executed'] is not False or
            packet['installed_files_modified'] is not False or
            (coverage['catalog_buff_ids'], coverage['primary_graphs_reviewed'],
             coverage['previously_reviewed'], coverage['new_primary_graphs_reviewed'],
             coverage['new_direct_target_graphs'],
             coverage['new_indirect_secondary_target_graphs'],
             coverage['new_effect_only_graphs'],
             coverage['all_graphs_with_direct_or_indirect_attribute_target'],
             coverage['all_effect_only_graphs']) != (49, 49, 17, 32, 24, 5, 3, 46, 3) or
            prior['coverage']['typed_target_ids_total'] != 17):
        raise ValueError('Native mod buff full review build/coverage conflict')
    catalog_ids = {line['buff_id'] for row in previews.values()
                   for line in row['ordered_lines'] if line.get('buff_id') is not None}
    ledger = {row['buff_id']: row for row in packet['all_49_coverage_ledger']}
    reviews = {row['buff_id']: row for row in packet['new_primary_graph_reviews']}
    if (catalog_ids != set(ledger) or len(ledger) != 49 or len(reviews) != 32 or
            sum(row['target_status'] == 'direct_attribute_target' for row in reviews.values()) != 24 or
            sum(row['target_status'] == 'indirect_secondary_attribute_target' for row in reviews.values()) != 5 or
            {row['buff_id'] for row in reviews.values()
             if row['target_status'] == 'effect_node_only'} != EFFECT_ONLY):
        raise ValueError('Native mod buff full review ID/class conflict')
    for buff_id, row in reviews.items():
        evidence = ledger[buff_id]
        if (row['server_activation_proven'] is not False or
                row['target_status'] != evidence['graph_target_status'] or
                not row['graph_pyc_sha256'] or not row['graph_literal_sha256'] or
                evidence['reviewed'] is not True):
            raise ValueError('Native mod buff full review provenance conflict')
        if row['target_status'] == 'direct_attribute_target':
            attrs = {node['native_attr_id'] for node in row['direct_target_nodes']}
        elif row['target_status'] == 'indirect_secondary_attribute_target':
            attrs = {attr for edge in row['indirect_cast_targets']
                     for attr in edge['secondary_attr_ids']}
            for edge in row['indirect_cast_targets']:
                secondary = packet['secondary_graphs'].get(str(edge['secondary_buff_id']))
                if secondary and {node['native_attr_id'] for node in secondary['target_nodes']} != \
                        set(edge['secondary_attr_ids']):
                    raise ValueError('Native secondary buff target mismatch')
        else:
            attrs = set()
            if row['direct_target_nodes'] or row['indirect_cast_targets']:
                raise ValueError('Effect-only buff has an attribute target')
        if attrs != set(evidence['native_target_attr_ids']):
            raise ValueError('Native mod buff target IDs disagree with ledger')
    return packet, reviews, ledger


def annotate(preview):
    if preview is None:
        return None
    packet, reviews, _ = _source()
    out = copy.deepcopy(preview)
    for line in out['ordered_lines']:
        row = reviews.get(line.get('buff_id'))
        if row is None:
            continue
        if line.get('attribute_status') != 'graph_attribute_unverified':
            raise ValueError('Full mod review overlaps a prior graph target')
        line['graph_review_status'] = row['target_status']
        line['graph_review_source_sha256'] = HASHES[PACKET.name]
        line['server_application_proven'] = False
        line['runtime_value_binding_proven'] = False
        if row['target_status'] == 'direct_attribute_target':
            targets = {(node['native_attr_id'], node['native_property'])
                       for node in row['direct_target_nodes']}
            line['native_attributes'] = [{'attr_id': attr, 'property': prop}
                                         for attr, prop in sorted(targets)]
            line['attribute_status'] = 'typed_graph_target_verified_execution_unproven'
        elif row['target_status'] == 'indirect_secondary_attribute_target':
            targets = {}
            for edge in row['indirect_cast_targets']:
                secondary = packet['secondary_graphs'].get(str(edge['secondary_buff_id']))
                if secondary:
                    targets.update({node['native_attr_id']: node['native_property']
                                    for node in secondary['target_nodes']})
                else:
                    targets.update({attr: None for attr in edge['secondary_attr_ids']})
            line['native_attributes'] = [{'attr_id': attr, 'property': prop}
                                         for attr, prop in sorted(targets.items())]
            line['secondary_cast_buff_ids'] = [edge['secondary_buff_id']
                                               for edge in row['indirect_cast_targets']]
            line['secondary_level_application_proven'] = False
            line['attribute_status'] = 'typed_secondary_graph_target_level_unverified'
        else:
            nodes = (packet['secondary_581902100_schema_boundary']['nodes']
                     if row['buff_id'] == 581902000 else row['other_nodes'])
            line['effect_node_types'] = sorted({node['node_type'] for node in nodes
                                                if node['node_type'] in (
                                                    'NodeHeal', 'NodeGetFloatAttr',
                                                    'NodeHitAngleDamageReduce',
                                                    'NodeDistanceDamageReduce')})
            line['native_attributes'] = None
            line['attribute_status'] = 'typed_effect_node_only_arithmetic_unverified'
    out['all_buff_review_source_sha256'] = HASHES[PACKET.name]
    return out


def coverage():
    packet, _, _ = _source()
    return copy.deepcopy(packet['coverage'])
