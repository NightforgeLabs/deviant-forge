"""Source-backed native mod effect *display* evidence, separate from damage math.

Native effect ranks 1–5 are not Field Guide levels 1–17. The graph's runtime
arithmetic and the selected mod instance remain outside this projection.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
from pathlib import Path

import catalog

PACKETS = Path(__file__).with_name('evidence_packets')
TRACE_NAME = 'native-mod-10101-main-effect-trace.json'
TRACE_SHA = '510aad5fbcd7d6c6613210d84948f756cc64f5c4f359c62c15c0a3066900ce48'
GROUP_NAME = 'native-mod-main-entry-groups.json'
GROUP_SHA = '4db0d4055d941439f79cd8581aa6dfdf30c1a93ada18f63f6b47b3036cb3f46c'
COMPOSITE_NAME = 'native-mod-entry-composite-v2.json'
COMPOSITE_SHA = '54625460815939687844aff1691a5d059847dd48ff2cb85e5db309f662e20aea'
LEVEL_NAME = 'native-mod-v2-level-selection-v1.json'
LEVEL_SHA = '368c561d0f2354f57933f0dcc7186d4dc9313d860962b81b364cbe4f77a3666b'
VARIANTS = {
    'mod:weapon_mod:shatter-them-all-general': 'General',
    'mod:weapon_mod:shatter-them-all-precision': 'Precision',
    'mod:weapon_mod:shatter-them-all-shrapnel': 'Shrapnel',
    'mod:weapon_mod:shatter-them-all-survival': 'Survival',
    'mod:weapon_mod:shatter-them-all-violent': 'Violent',
}


def _pinned(name: str, expected: str) -> dict:
    raw = (PACKETS / name).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('Native mod source hash conflict: ' + name)
    return json.loads(raw)


@lru_cache(maxsize=1)
def _source() -> tuple[dict, dict, dict, dict]:
    trace = _pinned(TRACE_NAME, TRACE_SHA)
    groups = _pinned(GROUP_NAME, GROUP_SHA)
    composite = _pinned(COMPOSITE_NAME, COMPOSITE_SHA)
    level_selection = _pinned(LEVEL_NAME, LEVEL_SHA)
    if (trace['build'] != '26267212' or groups['installed_build_id'] != '26267212' or
            composite['installed_build_id'] != '26267212' or level_selection['build'] != '26267212'):
        raise ValueError('Native mod source build mismatch')
    records = composite['records']
    keys = [(row['entry_no'], row['entry_level']) for row in records]
    if (len(records) != 1262 or len(set(keys)) != 1262 or
            any(not row['composite_key_raw_hex'].startswith('270102') for row in records)):
        raise ValueError('Native mod composite key schema changed')
    family_records = {row['entry_level']: row for row in records if row['entry_no'] == 10101}
    if (set(family_records) != {4, 5} or
            [(rank, family_records[rank]['row_literal_offset']) for rank in (4, 5)] !=
            [(4, 114943), (5, 115023)] or
            level_selection['family_10101_available_native_entry_ranks'] != [4, 5]):
        raise ValueError('Native mod 10101 entry ranks changed')
    level_rows = level_selection['global_total_level_to_entry_rank']
    if [(row['total_level'], row['main_entry_rank']) for row in level_rows] != [
            (total, min(5, (total + 1) // 2)) for total in range(1, 18)]:
        raise ValueError('Native mod generated-level mapping changed')
    family = [row for row in groups['groups'] if row['main_entry_no'] == 10101]
    if len(family) != 1:
        raise ValueError('Native mod 10101 family missing or repeated')
    codes = {row['mod_code'] for row in family[0]['members']}
    if len(codes) != 10:
        raise ValueError('Native mod 10101 membership changed')
    ranks = trace['ordinary_effect_display_levels']
    if [(row['effect_level'], row['per_part_percent'], row['cap_percent'])
            for row in ranks] != [(1, 3, 9), (2, 6, 18), (3, 9, 27),
                                  (4, 12, 36), (5, 15, 45)]:
        raise ValueError('Native mod rank vector changed')
    if '碎弹伤害+5%' not in trace['shiny_buff_level_row']['buff_desc']['string']:
        raise ValueError('Native Shiny effect text changed')
    by_code = {}
    for row in catalog.SYSTEMS['records']:
        if row.get('system') != 'new' or row.get('base_name') != 'Shatter Them All':
            continue
        code = int(row['id'])
        if code in by_code or code not in codes:
            raise ValueError('Shatter Them All source identity conflict')
        by_code[code] = row
    if set(by_code) != codes:
        raise ValueError('Shatter Them All source identity incomplete')
    by_variant = {}
    for identity, variant in VARIANTS.items():
        entry = catalog.ENTRIES[identity]
        if entry['name'] != 'Shatter Them All' or entry['slot'] != 'weapon_mod' or entry['variant'] != variant:
            raise ValueError('Catalog variant does not match native source')
        pair = [row for row in by_code.values() if row['family'] == variant]
        if len(pair) != 2 or {row['is_shiny'] for row in pair} != {False, True}:
            raise ValueError('Native normal/Shiny variant pair missing')
        by_variant[identity] = {bool(row['is_shiny']): row for row in pair}
    return trace, groups, by_variant, level_selection


def for_catalog(catalog_id: str, *, shiny: bool = False) -> dict | None:
    if catalog_id not in VARIANTS:
        return None
    trace, groups, pairs, level_selection = _source()
    pair = pairs[catalog_id]
    return {
        'source_status': 'native_effect_rank_display_only',
        'installed_build_id': trace['build'],
        'family_entry_no': 10101,
        'normal_item_id': pair[False]['item_id'],
        'shiny_item_id': pair[True]['item_id'],
        'preview_shiny': shiny,
        'effect_ranks': [
            {'effect_rank': row['effect_level'],
             'shrapnel_damage_per_body_part_percent': row['per_part_percent'],
             'cap_percent': row['cap_percent']}
            for row in trace['ordinary_effect_display_levels']
        ],
        'standard_tooltip_effect_rank': 5,
        'native_generated_total_level_to_rank': [
            {'native_total_level': row['total_level'],
             'effect_rank': row['main_entry_rank'],
             'family_entry_row_available': row['main_entry_rank'] in (4, 5)}
            for row in level_selection['global_total_level_to_entry_rank']
        ],
        'generated_level_scope': 'native_mod_v2_generation_only_not_field_guide_badge',
        'native_family_available_entry_ranks': [4, 5],
        'shiny_separate_effect': {'shrapnel_damage_percent': 5,
                                  'native_text': trace['shiny_buff_level_row']['buff_desc']['string'].split('_$S@', 1)[0]},
        'field_guide_level_mapping': None,
        'selected_rank_inferred': False,
        'runtime_graph_arithmetic_verified': False,
        'calculation_included': False,
        'source_trace_sha256': TRACE_SHA,
        'source_group_sha256': GROUP_SHA,
        'source_composite_sha256': COMPOSITE_SHA,
        'source_level_selection_sha256': LEVEL_SHA,
        'source_mod_property_sha256': groups['native_mod_property_records_sha256'],
    }
