"""Versioned public slot/suffix formulas, separate from ownership evidence."""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import catalog


ROOT = Path(__file__).parent / 'evidence_packets'
FACTS_PATH = ROOT / 'published-formula-facts-v1.json'
GRID_PATH = ROOT / 'published-identity-levels-v1.jsonl.gz'
SHINY_PATH = ROOT / 'published-shiny-suffix-v1.jsonl.gz'
REPORT = json.loads((ROOT / 'published-bonus-coverage-v1.json').read_text())
SHINY_REPORT = json.loads((ROOT / 'published-shiny-suffix-coverage-v1.json').read_text())
FACTS = json.loads(FACTS_PATH.read_text())
if hashlib.sha256(FACTS_PATH.read_bytes()).hexdigest() != REPORT['input_sha256']['published_formula_facts']:
    raise ValueError('Published bonus formula packet hash mismatch')
if FACTS['schema_version'] != 'published_suffix_formula_v1':
    raise ValueError('Unsupported published bonus formula schema')
if FACTS['official_level_row_tiers'] != catalog.DATA['official_rules']['mod_levels']['ordered_subattribute_tiers']:
    raise ValueError('Published formula level chart disagrees with official catalog chart')
if REPORT['exact_crosscheck']['mismatching_profiles'] or REPORT['corroborated_tier_crosscheck']['mismatches']:
    raise ValueError('Published formula packet has held numeric conflicts')

GRID = {}
with gzip.open(GRID_PATH, 'rt') as source:
    for line in source:
        row = json.loads(line)
        key = (row['catalog_id'], row['level'])
        if key in GRID:
            raise ValueError('Duplicate published identity-level profile')
        GRID[key] = row
if len(GRID) != REPORT['statistics']['theoretical_identity_levels']:
    raise ValueError('Incomplete published identity-level grid')
DELTA_PATH = ROOT / 'published-gap-resolution-v2.json'
BASE_REPORT_PATH = ROOT / 'published-bonus-line-coverage-base-v1.json'
DELTA = json.loads(DELTA_PATH.read_text())
if (DELTA['schema_version'] != 'bonus_line_gap_resolution_v2' or
        hashlib.sha256(BASE_REPORT_PATH.read_bytes()).hexdigest() != DELTA['base_sha256'] or
        DELTA['resolved_identity_count'] != 1 or DELTA['resolved_profile_count'] != 17):
    raise ValueError('Published gap resolution provenance mismatch')
for row in DELTA['profiles']:
    key = (row['catalog_id'], row['level'])
    prior = GRID.get(key)
    if (not prior or prior['status'] != 'blocked' or
            row['catalog_id'] != 'mod:helmet_mod:elemental-havoc-violence' or
            row['identity_resolution'] != 'exact_identity_family_bridge_candidate' or
            row['system_generation'] != 'current_field_guide'):
        raise ValueError('Published gap resolution exceeds one blocked current identity')
    GRID[key] = row
if SHINY_REPORT['ordinary_formula_sha256'] != hashlib.sha256(FACTS_PATH.read_bytes()).hexdigest():
    raise ValueError('Shiny suffix candidate uses a different ordinary formula packet')
SHINY = {}
with gzip.open(SHINY_PATH, 'rt') as source:
    for line in source:
        row = json.loads(line)
        if row['catalog_id'] in SHINY or row['level'] != 17 or row['shiny'] is not True:
            raise ValueError('Invalid duplicate or non-Lv17 Shiny candidate')
        SHINY[row['catalog_id']] = row
if len(SHINY) != SHINY_REPORT['statistics']['current_generation_identity_records']:
    raise ValueError('Incomplete conditional Shiny suffix index')

LABELS = {'crit_dmg': 'Crit DMG', 'weakspot_dmg': 'Weakspot DMG',
          'magazine_capacity': 'Magazine Capacity', 'reload_speed': 'Reload Speed',
          'weapon_dmg': 'Weapon DMG', 'status_dmg': 'Status DMG',
          'elemental_dmg': 'Elemental DMG', 'hp': 'Max HP',
          'dmg_boost': 'All DMG Boost', 'dmg_against_enemies': 'Damage against enemies',
          'deviant_dmg_reduction': 'Damage reduction against Deviants',
          'blaze': 'Blaze DMG', 'shock': 'Shock DMG', 'frost': 'Frost DMG',
          'explosive': 'Explosive DMG'}
PREFIXES = ('lunar_', 'crescent_', 'mirror_', 'wild_', 'phantasmal_',
            'downstar_', 'aero_', 'resonance_')
SLOTS = {'helmet_mod': 'helmet', 'chest_mod': 'chest', 'pants_mod': 'pants',
         'boots_mod': 'boots', 'gloves_mod': 'gloves', 'mask_mod': 'mask',
         'weapon_mod': 'weapon'}
LAYOUTS = {(row['slot'], row['suffix']): row for row in FACTS['slot_suffix_layouts']}


def _name(key):
    direct = LABELS.get(key)
    if direct:
        return direct
    for prefix in PREFIXES:
        if key.startswith(prefix):
            return LABELS.get(key[len(prefix):], key[len(prefix):].replace('_', ' ').title())
    return key.replace('_', ' ').title()


def _condition(raw):
    condition = raw.get('condition')
    if not condition or condition == 'generic_damage_boost' or condition.startswith('unconditional_or_keyword_specific'):
        return None
    return condition.replace('_', ' ').replace(';', '; ')


def profile(catalog_id, level, *, shiny=False):
    """Return four line candidates, including locked rows, or an explicit block."""
    if shiny and level != 17:
        raise ValueError('Shiny suffix candidate requires level 17')
    raw = (SHINY.get(catalog_id) if shiny else GRID.get((catalog_id, level)))
    if shiny and raw is None:
        return {'status': 'blocked', 'reason': 'no_conditional_shiny_suffix_source_for_identity',
                'lines': [], 'shiny_availability_for_identity': 'unverified'}
    if raw is None:
        raise ValueError('No generated public bonus profile for identity and level')
    if raw['status'] == 'blocked':
        return {'status': 'blocked', 'reason': raw['reason'], 'lines': [],
                'shiny_availability_for_identity': 'unverified' if shiny else None}
    by_index = {row['index']: row for row in raw['rows']}
    entry = catalog.ENTRIES[catalog_id]
    alias_transfer = raw.get('terminology_alias_applied') is True
    suffix = (raw.get('published_layout_suffix_term')
              if raw.get('identity_resolution') == 'exact_identity_family_bridge_candidate'
              else 'Resonant Deviant Energy' if entry.get('variant') == 'Resonance Deviant Energy'
              else entry.get('variant'))
    layout = LAYOUTS.get((SLOTS[entry['slot']], suffix))
    if layout is None:
        raise ValueError('Published profile lacks its source layout')
    tiers = FACTS['official_level_row_tiers'][str(level)]
    lines = []
    for index, tier in enumerate(tiers):
        formula = by_index.get(index)
        if tier == 0:
            key = layout['rows'][index]
            lines.append({'position': index + 1, 'tier': 0,
                          'name': _name(key), 'stat_type': key,
                          'layout_slot': layout['slot'],
                          'layout_source_ref': layout['source_url'],
                          'status': 'locked_at_this_level'})
            continue
        if not formula or formula['tier'] != tier:
            raise ValueError('Published row tier/index mismatch')
        components = formula['components']
        primary = components.get('value_percent', components.get('base_percent'))
        lines.append({'position': index + 1, 'name': _name(formula['stat_key']),
                      'stat_type': formula['stat_key'], 'tier': tier,
                      'layout_slot': layout['slot'], 'unit': 'percent',
                      'value_percent': primary, 'components': components,
                      'condition': _condition(formula),
                      'source_ref': formula['formula_source_url'],
                      'layout_source_ref': raw['layout_source_url'],
                      'source_status': (raw['status'] + '; sourced Resonance/Resonant naming bridge, identity-level transfer candidate'
                                        if alias_transfer else raw['status']),
                      'status': (('published_formula_candidate_alias_transfer' if alias_transfer else raw['status'])
                                 if primary is not None else
                                 'published_structured_candidate_requires_event_state'),
                      'alias_status': 'anchored_terminology_transfer_candidate' if alias_transfer else None,
                      'alias_source_urls': raw.get('terminology_alias_source_urls') or [],
                      'generation_status': raw['system_generation'],
                      'identity_level_directly_observed': False})
    return {'status': raw['status'], 'reason': None, 'lines': lines,
            'alias_status': 'anchored_terminology_transfer_candidate' if alias_transfer else None,
            'alias_source_urls': raw.get('terminology_alias_source_urls') or [],
            'source_class': raw.get('source_class'),
            'current_game_build_verified': False,
            'shiny_suffix_scope': raw.get('candidate_scope') if shiny else None,
            'shiny_availability_for_identity': raw.get('shiny_availability_for_identity') if shiny else None,
            'shiny_core_effect_status': raw.get('shiny_core_effect_status') if shiny else None,
            'level_obtainability_verified': False}


def coverage():
    import public_semantic_crosscheck
    statistics = dict(REPORT['statistics'])
    statistics['identity_level_statuses'] = dict(statistics['identity_level_statuses'])
    statistics['identity_level_statuses']['blocked'] -= 17
    statistics['identity_level_statuses']['published_formula_candidate_current_generation'] += 17
    statistics['generated_bonus_line_rows'] = dict(statistics['generated_bonus_line_rows'])
    statistics['generated_bonus_line_rows']['published_formula_candidate_current_generation'] += 62
    statistics['blocked_reasons'] = dict(statistics['blocked_reasons'])
    statistics['blocked_reasons']['no_named_suffix_or_fixed_layout'] -= 17
    statistics['gap_resolution_v2'] = {'scoped_identity': 'mod:helmet_mod:elemental-havoc-violence',
                                       'candidate_levels_added': 17,
                                       'blocked_profiles_remaining': 1751,
                                       'legacy_random_roll_profiles_requiring_actual_rolls': 714,
                                       'mixed_generation_profiles_requiring_identity_mapping': 1003,
                                       'current_resistance_profiles_requiring_layout': 34}
    semantic = public_semantic_crosscheck.coverage()
    statistics['held_semantic_crosscheck'] = {
        key: value for key, value in semantic.items() if key != 'identities'}
    statistics['generated_candidate_profiles_are_raw_before_semantic_reconciliation'] = True
    return statistics
