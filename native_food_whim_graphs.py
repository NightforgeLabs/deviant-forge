"""Exact named food/Whim graph descriptions; never active combat buffs."""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
from pathlib import Path

import native_named_catalog
import native_combat_labels


ROOT = Path(__file__).resolve().parent / 'evidence_packets'
FILES = {
    'native-food-whim-bonus-graphs-v1.json': '343d55004480e2d3dae1f4765e454d8727ebbd4e00e0069db37f78483dbb4157',
    'native-food-whim-combat-priority-v1.json': 'ae53a48a3220e899825ec8e13916874e0eeef23b60a71691fbb314f80a427e1f',
    'native-food-whim-graph-coverage-v1.md': 'ea63b08c2e7224dd960c2a7d16bf76c8d3d41f54b13ccabee5285173f7061768',
}
COUNTS = (521, 509, 12, 225, 265, 143, 142, 1, 27, 1, 171, 93, 33)


@lru_cache(maxsize=1)
def _source():
    if any(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest
           for name, digest in FILES.items()):
        raise ValueError('Native food/Whim graph source hash conflict')
    packet = json.loads((ROOT / 'native-food-whim-bonus-graphs-v1.json').read_text())
    priority = json.loads((ROOT / 'native-food-whim-combat-priority-v1.json').read_text())
    coverage = packet['coverage']
    keys = ('items', 'cuisine_items', 'whim_items', 'items_with_exact_buff_token',
            'direct_item_buff_references', 'distinct_item_linked_buff_ids',
            'typed_primary_graphs', 'missing_primary_archive_graphs',
            'typed_secondary_graphs', 'typed_tertiary_graphs',
            'all_graphs_in_ledger', 'graphs_with_native_attribute_targets',
            'items_with_combat_or_psi_target')
    if (packet['installed_build_id'] != '26267212' or
            priority['installed_build_id'] != packet['installed_build_id'] or
            priority['full_ledger_sha256'] != FILES['native-food-whim-bonus-graphs-v1.json'] or
            packet['game_code_executed'] is not False or
            packet['game_files_modified'] is not False or
            packet['forge_files_modified'] is not False or
            tuple(coverage[key] for key in keys) != COUNTS):
        raise ValueError('Native food/Whim graph build or coverage conflict')
    items = {row['item_id']: row for row in packet['items']}
    graphs = {row['buff_id']: row for row in packet['buff_graphs']}
    named = {int(row['catalog_id'].split(':')[-1]): row for row in native_named_catalog.records()}
    if (len(items) != 521 or len(graphs) != 171 or len(named) != 513 or
            set(named) != {item_id for item_id, row in items.items()
                           if row['installed_english_title']} or
            {row['item_id'] for row in priority['records']} !=
            set(packet['combat_or_psi_item_ids']) or len(priority['records']) != 33):
        raise ValueError('Native food/Whim item/graph identity conflict')
    for item_id, row in items.items():
        if (row['installed_english_title'] and
                (named[item_id]['name'] != row['installed_english_title'] or
                 named[item_id]['category'] !=
                 ('whims_deviations' if row['family'] == 'adjacent_whim' else 'food_drink'))):
            raise ValueError(f'Native food/Whim title/category conflict: {item_id}')
        links = {link['buff_id'] for link in row['exact_source_links']}
        if any(link['buff_id'] not in graphs or link['graph_status'] != graphs[link['buff_id']]['status']
               for link in row['configured_graph_reachability']):
            raise ValueError(f'Native food/Whim graph reachability conflict: {item_id}')
        if any(link['buff_id'] not in {edge['buff_id'] for edge in row['configured_graph_reachability']}
               for link in row['exact_source_links']):
            raise ValueError(f'Native food/Whim direct buff missing from graph ledger: {item_id}')
        if len(links) != len(row['exact_source_links']):
            raise ValueError(f'Duplicate direct food/Whim buff: {item_id}')
    if graphs[403152800]['status'] != 'archive_graph_missing':
        raise ValueError('Missing food buff graph was silently filled')
    return packet, priority, items, graphs


def records():
    """Only the 513 named items can be exposed in Aid; source graphs stay compact."""
    packet, priority, items, graphs = _source()
    priority_ids = {row['item_id'] for row in priority['records']}
    labels = {(row['attr_id'], row['native_property']): row['name']['english']
              for row in native_combat_labels.proof()['rows'].values()}
    out = {}
    for item_id, item in items.items():
        if not item['installed_english_title'] or not item['exact_source_links']:
            continue
        links = {row['buff_id']: row for row in item['exact_source_links']}
        summaries = []
        for reach in item['configured_graph_reachability']:
            graph = graphs[reach['buff_id']]
            targets = []
            for target in graph.get('native_attribute_targets') or []:
                prop = target['native_property']
                attr = target.get('native_attr_id_if_mapped')
                targets.append({
                    'native_property': prop, 'native_attr_id': attr,
                    'source_label': labels.get((attr, prop)),
                    'configured_expression': target.get('configured_numeric_input_expression_if_proven'),
                    'configured_raw_value': target.get('raw_value') if target.get('value_status') == 'typed_fixed_value' else None,
                    'value_status': target.get('value_status'),
                    'runtime_application_proven': False,
                })
            conditions = []
            for node in graph.get('condition_event_nodes') or []:
                checker_types = sorted({checker['checker_type'] for checker in node.get('trigger_checkers') or []})
                buff_ids = sorted({checker['fields']['buff_id']['value']
                                   for checker in node.get('trigger_checkers') or []
                                   if 'buff_id' in checker.get('fields', {})})
                conditions.append({'node_type': node['node_type'],
                                   'checker_types': checker_types,
                                   'referenced_buff_ids': buff_ids,
                                   'runtime_condition_truth_proven': False})
            direct = links.get(reach['buff_id'])
            summaries.append({
                'buff_id': reach['buff_id'], 'cast_depth': reach['cast_depth'],
                'graph_status': graph['status'],
                'nominal_lifetime_seconds': direct.get('nominal_lifetime_seconds') if direct else None,
                'target_properties': targets, 'configured_conditions': conditions,
                'source_pyc_sha256': graph.get('source_pyc_sha256'),
                'source_literal_sha256': graph.get('source_literal_sha256'),
                'active_on_selected_build': None,
            })
        out[item_id] = {
            'source_build': packet['installed_build_id'],
            'source_sha256': FILES['native-food-whim-bonus-graphs-v1.json'],
            'direct_buff_count': len(links), 'graphs': summaries,
            'combat_or_psi_target_from_source': item_id in priority_ids,
            'combat_calculation_included': False,
            'unknowns': ['item use and recipient', 'graph executor and condition truth',
                         'selected buff effect_rate', 'stacking and applied expiry'],
        }
    if len(out) != 225:
        raise ValueError('Named food/Whim source buff coverage changed')
    return out
