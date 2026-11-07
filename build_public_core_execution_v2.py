"""Rebuild executable community-core coverage from the held crosswalk and parser."""
from __future__ import annotations

import json
from pathlib import Path

import published_main_core

ROOT = Path(__file__).parent
LEDGER = ROOT / 'evidence_packets/public-core-operator-ledger-v1.json'
OUTPUT = ROOT / 'evidence_packets/public-core-execution-v2.json'


def build():
    records = []
    for row in json.loads(LEDGER.read_text())['records']:
        if row['calculation_status'] != 'timed_counter_or_resource_partial':
            continue
        identity = row['catalog_id']
        texts = published_main_core.PUBLIC[identity]['effect_text_variants_unranked']
        operators = {published_main_core._community_text(identity, text, {})['operator']
                     for text in texts}
        if len(operators) != 1:
            raise ValueError(f'{identity}: source variants disagree on event operator')
        operator = operators.pop()
        status = ('blocked_attack_basis_and_mark_events'
                  if operator == 'marked_enemy_attack_stacks_unbound_basis'
                  else 'conditional_direct_timeline'
                  if operator in {'empty_magazine_independent_crit_stacks',
                                  'post_reload_first_hits_weakspot',
                                  'crit_hit_stack_until_reload'}
                  else 'conditional_sourced_packet_timeline')
        records.append({'catalog_id': identity, 'family': row['family'],
                        'normal_source_item_id': row['normal_source_item_id'],
                        'operator': operator, 'execution_status': status,
                        'source_item_effect_level_to_field_guide_level': None})
    counts = {status: sum(row['execution_status'] == status for row in records)
              for status in sorted({row['execution_status'] for row in records})}
    return {'schema_version': 2, 'scope': '24 formerly partial timed or resource ordinary identities',
            'source_ledger': LEDGER.name, 'counts': counts, 'records': records,
            'note': 'Execution is conditional on selected unranked source text, exact suffix inputs and named event assumptions; no current-game rank mapping is inferred.'}


if __name__ == '__main__':
    OUTPUT.write_text(json.dumps(build(), indent=2) + '\n')
    print(OUTPUT, build()['counts'])
