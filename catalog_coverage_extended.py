"""Runtime coverage definitions layered over hash-pinned source catalog data."""
from __future__ import annotations

import catalog
import public_catalog_detail
import published_bonus_lines


def coverage():
    report = catalog.coverage()
    selectable = [row for row in catalog.DATA['mods'] if not row.get('family_only')]
    level10 = [public_catalog_detail.calculation_rows(row['id'], 10)[1] for row in selectable]
    numeric = sum(status in ('complete', 'published_candidate_complete') for status in level10)
    published = published_bonus_lines.coverage()
    return {**report,
            'mod_grouping': {
                'distinct_names': len({row['name'] for row in selectable}),
                'distinct_name_slot_pairs': len({(row['name'], row['slot']) for row in selectable}),
                'distinct_tree_or_name_labels': len({row.get('tree') or row['name'] for row in selectable}),
                'note': 'Tree labels are categories or exceptional variants, not base mod names.'},
            'published_fixed_layout_identities': sum(
                published_bonus_lines.GRID[(row['id'], 10)]['status'].startswith('published_formula_candidate')
                for row in selectable),
            'level10_four_numeric_bonus_identities': numeric,
            'level10_partial_bonus_identities': len(selectable) - numeric,
            'published_formula_candidate_profiles': (
                published['identity_level_statuses']['published_formula_candidate_current_generation'] +
                published['identity_level_statuses']['published_formula_candidate_generation_unverified']),
            'published_formula_blocked_profiles': published['identity_level_statuses']['blocked'],
            'level_grid_note': 'Fixed layouts are identity-level candidates; numeric Lv10 coverage is lower where scaling or conversion is unresolved.'}
