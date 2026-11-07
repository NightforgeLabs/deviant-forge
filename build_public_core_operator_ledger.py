"""Reproducible capability audit for the 64 unranked current core identities."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

import catalog
import mod_core_typed
import published_main_core

ROOT = Path(__file__).parent
SUPPORTED = {'crit_weakspot_tradeoff', 'static_crit_pair', 'static_crit_rate',
             'static_elemental', 'static_damage_pool',
             'conditional_no_nearby_enemies', 'conditional_marked_target',
             'distance_gated_weakspot', 'magazine_consumed_counter'}
NEXT = {
    'Abnormal Increase': 'Resolve empty-magazine event order, three-stack refresh and expiry in the timed scheduler.',
    'Critical Surge': 'Resolve empty-magazine Crit DMG stack timing and independent expiry.',
    'Deadshot': 'Supply correlated crit outcomes and reset stacks on the next reload.',
    'Elemental Resonance': 'Count previous-magazine elemental damage instances and apply the timed next-magazine bonus.',
    'Most Wanted': 'Bind marked-enemy events, Attack basis feedback and 8-second stack expiry.',
    'Precision Charge': 'Compute previous-magazine weakspot rate and the next reload reset.',
    'Reload Rampage': 'Bind kill timing, finite reserve refill and until-reload Weapon/Status buff.',
    'Three Strikes': 'Resolve first-three-hit and 50%-magazine rounding semantics.',
    'Lifeforce Boost': 'Route HP utility output to survivability, not outgoing damage.',
    'Melee Amplifier': 'Use a melee attack packet and source-specific target rules.',
    'Melee Momentum': 'Use a melee attack packet and stamina recovery state.',
}


def build():
    rows = []
    for source in published_main_core.PUBLIC.values():
        identity = source['catalog_id']
        family = catalog.ENTRIES[identity]['tree']
        if not source['normal_source_item_id']:
            status, operator = 'shiny_only_isolated', None
            action = 'Find an ordinary source item or model the exact Shiny effect separately.'
        elif not source['effect_text_variants_unranked']:
            status, operator = 'display_only_missing_effect_text', None
            action = 'Read the exact normal item effect text and its source effect level.'
        else:
            operators = {published_main_core._community_text(identity, text,
                {'core_condition_active': True, 'core_target_distance_meters': 21})['operator']
                for text in source['effect_text_variants_unranked']}
            operator = next(iter(operators)) if len(operators) == 1 else None
            if operators <= SUPPORTED:
                status = 'opt_in_damage_scenario_supported'
                action = 'Confirm the chosen text and source item effect rank for a current default; Field Guide level remains independent.'
            elif operators <= {'static_hp_utility', 'melee_or_utility'}:
                status = 'typed_utility_or_melee_partial'
                action = NEXT[family]
            else:
                status = 'timed_counter_or_resource_partial'
                action = NEXT.get(family, 'Bind an explicit source event and named effect operator.')
        exact = [level for (candidate, level), binding in mod_core_typed.EXACT.items()
                 if candidate == identity and binding['variant_kind'] == 'ordinary']
        rows.append({'catalog_id': identity, 'family': family,
                     'normal_source_item_id': source['normal_source_item_id'],
                     'shiny_source_item_id': source['shiny_source_item_id'],
                     'community_operator': operator, 'calculation_status': status,
                     'exact_current_field_guide_levels': sorted(exact),
                     'effect_rank_to_field_guide_level': None,
                     'next_action': action})
    rows.sort(key=lambda row: row['catalog_id'])
    counts = dict(sorted(Counter(row['calculation_status'] for row in rows).items()))
    assert len(rows) == 64 and counts == {
        'display_only_missing_effect_text': 1,
        'opt_in_damage_scenario_supported': 26,
        'shiny_only_isolated': 7,
        'timed_counter_or_resource_partial': 24,
        'typed_utility_or_melee_partial': 6,
    }, counts
    return {'schema_version': 1, 'source': 'public-core-crosswalk-v1.json',
            'scope': 'current Field Guide identities with unranked public main-effect text',
            'counts': counts, 'records': rows}


if __name__ == '__main__':
    path = ROOT / 'evidence_packets/public-core-operator-ledger-v1.json'
    path.write_text(json.dumps(build(), indent=2, ensure_ascii=False) + '\n')
    print(path)
