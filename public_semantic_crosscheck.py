"""Compare held exact mod lines with published layouts by meaning, not magnitude."""
from __future__ import annotations

from functools import lru_cache
from collections import Counter
import re

import catalog
import published_bonus_lines


# These are the direct normalization of the held tooltip parser's named stats.
# Generic DMG, Reload Efficiency and All DMG Boost deliberately do not alias
# All DMG Boost, Reload Speed and Damage against enemies, respectively.
STAT_KEYS = {
    'crit_damage_percent': 'crit_dmg',
    'weakspot_damage_percent': 'weakspot_dmg',
    'magazine_capacity_percent': 'magazine_capacity',
    'weapon_damage_percent': 'weapon_dmg',
    'status_damage_percent': 'status_dmg',
    'elemental_damage_percent': 'elemental_dmg',
    'max_hp_percent': 'hp',
    'all_damage_boost_percent': 'dmg_boost',
    'power_surge_damage_percent': 'power_surge_dmg',
    'shock_damage_percent': 'shock',
    'reload_efficiency_percent': 'reload_efficiency',
    'generic_damage_percent': 'generic_damage',
    'monster_damage_direction_ambiguous': 'ambiguous_monster_damage',
}


def _text(value):
    return re.sub(r'[^a-z0-9]+', ' ', str(value or '').lower()).strip()


def _candidate_key(value):
    key = str(value or '')
    for prefix in published_bonus_lines.PREFIXES:
        if key.startswith(prefix):
            return key[len(prefix):]
    return key


def _observed_resonance_key(source, candidate):
    """Recognize the two photographed event descriptions only with matching mechanics."""
    observed = {
        'elemental dmg on weakspot hit': ('resonance_weakspot_dmg_to_elemental_dmg',
                                         'weakspot'),
        'weakspot dmg on elemental hit': ('resonance_elemental_dmg_to_weakspot_dmg',
                                         'elemental'),
    }.get(_text(source.get('name')))
    if not observed or candidate.get('stat_type') != observed[0]:
        return False
    condition = re.fullmatch(
        rf'per {observed[1]} damage instance; up to (\d+) stacks for (\d+) seconds',
        str(source.get('condition') or '').lower())
    parts = candidate.get('components') or {}
    return bool(condition and parts.get('trigger_instances') == 1 and
                parts.get('max_stacks') == int(condition.group(1)) and
                parts.get('duration_seconds') == int(condition.group(2)) and
                parts.get('per_stack_percent') == source.get('value_percent'))


def _aerial_extra_wording_matches(source, candidate):
    """Match only identical named base/extra values from an exact Aero line."""
    if (_text(source.get('condition')) != 'aerial hit' or
            _text(candidate.get('condition')) != 'aerial hit for extra component' or
            _text(source.get('name')) != _text(candidate.get('name'))):
        return False
    parts = candidate.get('components') or {}
    base, extra = source.get('value_percent'), source.get('conditional_bonus_percent')
    return (isinstance(base, (int, float)) and not isinstance(base, bool) and
            isinstance(extra, (int, float)) and not isinstance(extra, bool) and
            parts.get('base_percent') == base and parts.get('aerial_extra_percent') == extra)


def semantic_conflicts(source, candidate, *, expected_slot=None):
    """Return independently actionable discrepancies; equal numbers prove nothing."""
    if not source or not candidate:
        return []
    reasons = []
    known_type = source.get('stat_type')
    candidate_key = _candidate_key(candidate.get('stat_type'))
    sourced_resonance = _observed_resonance_key(source, candidate)
    if sourced_resonance:
        pass
    elif known_type in STAT_KEYS:
        if STAT_KEYS[known_type] != candidate_key:
            reasons.append('stat_identity')
    elif _text(source.get('name')) != _text(candidate.get('name')):
        reasons.append('stat_identity')
    source_unit = source.get('unit') or 'percent'
    candidate_unit = candidate.get('unit') or 'percent'
    if _text(source_unit) != _text(candidate_unit):
        reasons.append('unit')
    source_condition = _text(source.get('condition'))
    candidate_condition = _text(candidate.get('condition'))
    low_hp_match = (source_condition == 'low hp' and
                    candidate_condition.startswith('low hp'))
    aerial_match = _aerial_extra_wording_matches(source, candidate)
    if (source_condition != candidate_condition and not low_hp_match and
            not sourced_resonance and not aerial_match):
        reasons.append('condition')
    direction = source.get('direction')
    value = candidate.get('value_percent')
    if direction == 'ambiguous' or (value is not None and
            ((direction == 'increase' and value < 0) or
             (direction == 'decrease' and value > 0))):
        reasons.append('direction')
    if expected_slot is not None and candidate.get('layout_slot') != expected_slot:
        reasons.append('slot')
    observed_value = source.get('value_percent')
    if (observed_value is not None and value is not None and
            abs(abs(observed_value) - abs(value)) > 1e-6):
        reasons.append('magnitude')
    return reasons


def _exact_levels(identity, shiny):
    levels = set()
    if not shiny:
        levels.update(int(value) for value in (catalog.NUMERIC['profiles'].get(identity) or {}))
    for row in catalog.OBSERVED.values():
        if row['catalog_id'] == identity and bool(row.get('shiny')) == shiny:
            levels.add(row['level'])
    return sorted(levels)


@lru_cache(maxsize=None)
def layout_conflicts(identity, shiny=False):
    """Identity-wide conflicting positions, grounded only in exact held levels."""
    result = {}
    expected_slot = published_bonus_lines.SLOTS[catalog.ENTRIES[identity]['slot']]
    for level in _exact_levels(identity, shiny):
        resolved = catalog.resolve(identity, level, shiny=shiny)
        observed = resolved.get('known_attributes') or []
        candidate = published_bonus_lines.profile(identity, level, shiny=shiny)
        if candidate['status'] == 'blocked':
            continue
        for index, (source, offered) in enumerate(zip(observed, candidate['lines'])):
            reasons = semantic_conflicts(source, offered, expected_slot=expected_slot)
            if reasons:
                result.setdefault(index, []).append({
                    'level': level, 'reasons': reasons,
                    'observed_name': source.get('name'),
                    'observed_condition': source.get('condition'),
                    'observed_unit': source.get('unit') or 'percent',
                    'published_name': offered.get('name'),
                    'observed_source': source.get('source') or
                        (resolved.get('observed_profile') or {}).get('source_frame'),
                    'published_source': offered.get('layout_source_ref')})
    return result


@lru_cache(maxsize=1)
def coverage():
    identities = {}
    for entry in catalog.DATA['mods']:
        if entry.get('family_only'):
            continue
        identity = entry['id']
        conflicts = layout_conflicts(identity)
        if conflicts:
            identities[identity] = conflicts
    exact_pairs = {(identity, row['level'], index + 1)
                   for identity, positions in identities.items()
                   for index, details in positions.items() for row in details}
    blocked_candidate_rows = 0
    blocked_candidate_profiles = set()
    for identity, positions in identities.items():
        for level in range(1, 18):
            resolved = catalog.resolve(identity, level)
            offered = published_bonus_lines.profile(identity, level)
            if offered['status'] == 'blocked':
                continue
            observed = resolved.get('known_attributes') or []
            for index in positions:
                if (index < len(offered['lines']) and offered['lines'][index].get('tier') and
                        offered['lines'][index].get('value_percent') is not None and
                        not (index < len(observed) and observed[index].get('value_percent') is not None)):
                    blocked_candidate_rows += 1
                    blocked_candidate_profiles.add((identity, level))
    import public_catalog_detail
    calculation = Counter(public_catalog_detail.calculation_rows(identity, level)[1]
                          for identity, level in published_bonus_lines.GRID)
    return {'exact_semantic_conflict_identities': len(identities),
            'exact_semantic_conflict_positions': sum(map(len, identities.values())),
            'exact_semantic_conflict_level_positions': len(exact_pairs),
            'withheld_unobserved_candidate_rows': blocked_candidate_rows,
            'profiles_with_at_least_one_withheld_candidate': len(blocked_candidate_profiles),
            'effective_profile_calculation_statuses': dict(calculation),
            'identities': identities}
