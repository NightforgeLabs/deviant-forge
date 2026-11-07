"""Read-only, status-gated catalog mechanic evidence.

These packets bind catalog identities to source claims. A binding is not a
complete damage profile, and preview, historical and candidate values are
never installed as calculator rules by this module.
"""
from __future__ import annotations

import json
import copy
import hashlib
from collections import Counter
from pathlib import Path

import catalog

ROOT = Path(__file__).with_name('evidence_packets')
PACKETS = {name: json.loads((ROOT / f'{name}.json').read_text())
           for name in ('weapons', 'weapons-v2-delta', 'weapon-rule-map-v2', 'weapon-reference-v3',
                        'weapon-reference-v4-delta', 'weapon-reference-v5-delta',
                        'armor_sets', 'suffixes', 'suffix-cross-slot-v2')}
if hashlib.sha256((ROOT / 'suffixes.json').read_bytes()).hexdigest() != PACKETS['suffix-cross-slot-v2']['parent_packet_sha256']:
    raise ValueError('Cross-slot evidence does not match its suffix parent packet')
CURRENT_RELEASE = {'official_release', 'partial_official_release'}


def weapon_entries():
    """Apply the v2 delta while retaining v1 and its superseded source history."""
    combined = copy.deepcopy(PACKETS['weapons']['entries'])
    delta = PACKETS['weapons-v2-delta']
    for identity, revision in delta['revisions'].items():
        row = combined[identity]
        for path, value in revision['patch'].items():
            parts = path.split('.')
            if parts[0] != 'events' or len(parts) < 4:
                raise ValueError(f'Unsupported weapon evidence patch: {path}')
            event = next(event for event in row['events'] if event['event'] == parts[1])
            target = event
            for part in parts[2:-1]:
                target = target[part]
            target[parts[-1]] = value
        row['sources'] = list(dict.fromkeys([*row['sources'], revision['replacement_source']]))
        row['status'] = revision['status_after_patch']
        row['revision_history'] = revision
    if set(combined) & set(delta['new_entries']):
        raise ValueError('Weapon delta duplicates existing catalog identity')
    combined.update(copy.deepcopy(delta['new_entries']))
    if len(combined) != delta['coverage']['combined_bound']:
        raise ValueError('Weapon evidence delta coverage mismatch')
    return combined


WEAPON_ENTRIES = weapon_entries()
WEAPON_PLAN = {row['catalog_id']: row for row in PACKETS['weapon-rule-map-v2']['rows']}


def weapon_reference_rows():
    """Keep third-party page transcriptions separate from crafted weapon stats."""
    rows = copy.deepcopy(PACKETS['weapon-reference-v3']['rows'])
    for version in ('weapon-reference-v4-delta', 'weapon-reference-v5-delta'):
        additions = PACKETS[version]['new_database_page_references']
        for identity, addition in additions.items():
            if identity not in rows or rows[identity].get('database_page_reference') is not None:
                raise ValueError(f'Overlapping weapon page reference: {identity}')
            rows[identity]['database_page_reference'] = addition['database_page_reference']
            rows[identity]['typed_field_discrepancies'] = addition['typed_field_discrepancies']
    # Unanchored historical/page numbers are archived outside the active app.
    # Exact blueprint-linked item/tier/star cells live in published_item_tier.
    if any(row.get('database_page_reference') is not None or
           row.get('historical_catalog_profile') is not None for row in rows.values()):
        raise ValueError('Unanchored weapon reference re-entered active evidence')
    return rows


WEAPON_REFERENCES = weapon_reference_rows()


def coverage():
    import suffix_candidates
    import mod_core_packet
    import mod_core_typed
    import mod_stateful_api
    import weapon_timeline_api
    weapons, armor, suffixes = (PACKETS[key] for key in ('weapons', 'armor_sets', 'suffixes'))
    weapon_status = Counter(row['status'] for row in WEAPON_ENTRIES.values())
    threshold_status = Counter(row['binding_status'] for group in armor['sets']
                               for row in group['thresholds'])
    gear_status = Counter(row['binding_status'] for row in armor['unique_gear'])
    return {
        'catalog_coverage': __import__('catalog_coverage_extended').coverage(),
        'weapon_catalog': weapons['catalog_coverage']['catalog_weapon_count'],
        'weapon_bound_partial': len(WEAPON_ENTRIES),
        'weapon_unbound': weapons['catalog_coverage']['catalog_weapon_count'] - len(WEAPON_ENTRIES),
        'weapon_status': dict(weapon_status),
        'fully_parameterized_current_weapons': 0,
        'weapon_historical_stat_references': PACKETS['weapon-reference-v3']['counts']['historical_profile_records'],
        'weapon_direct_database_stat_references': sum(row.get('database_page_reference') is not None for row in WEAPON_REFERENCES.values()),
        'weapon_reference_conflicts': sum(bool(row.get('typed_field_discrepancies')) for row in WEAPON_REFERENCES.values()),
        'armor_set_count': len(armor['sets']),
        'armor_thresholds': sum(len(group['thresholds']) for group in armor['sets']),
        'armor_threshold_status': dict(threshold_status),
        'unique_gear_bindings': len(armor['unique_gear']),
        'unique_gear_status': dict(gear_status),
        'suffix_exact_profiles': len(suffix_candidates.EXACT),
        'suffix_complete_exact_profiles': len(suffix_candidates.EXACT) - suffixes['counts']['partial_exact_profiles'],
        'suffix_partial_exact_profiles': suffixes['counts']['partial_exact_profiles'],
        'suffix_layout_candidates': len(suffixes['layout_candidates']),
        'suffix_tier_candidates': len(suffixes['tier_candidates']),
        'suffix_cross_slot_layouts_fully_corroborated': PACKETS['suffix-cross-slot-v2']['counts']['original_layouts_full'],
        'suffix_cross_slot_tier_candidates_corroborated': PACKETS['suffix-cross-slot-v2']['counts']['original_tier_candidates_cross_validated'],
        'suffix_candidates_executable': 0,
        'suffix_derived_opt_in_profiles': len(suffix_candidates.CANDIDATES),
        'suffix_v3': suffix_candidates.coverage(),
        'mod_core': mod_core_packet.coverage(),
        'mod_core_typed': mod_core_typed.coverage(),
        'mod_stateful_candidate_operators': mod_stateful_api.coverage(),
        'weapon_event_timeline': weapon_timeline_api.coverage(),
        'scope': 'Evidence bindings, not fully simulated gear or a game-verified DPS ranking.',
    }


def binding(catalog_id, level=None):
    """Return a source-labeled binding without promoting it to a live rule."""
    weapons, armor, suffixes = (PACKETS[key] for key in ('weapons', 'armor_sets', 'suffixes'))
    packet_set = next((row for row in armor['sets'] if row['catalog_id'] == catalog_id), None)
    if catalog_id not in catalog.ENTRIES and not packet_set:
        raise ValueError('Unknown catalog item')
    kind = catalog.ENTRIES[catalog_id]['kind'] if catalog_id in catalog.ENTRIES else 'set'
    if kind == 'weapon':
        row = WEAPON_ENTRIES.get(catalog_id)
        legend = {**weapons['source_legend'], **PACKETS['weapons-v2-delta']['sources']}
        source_ids = set(row.get('sources', [])) if row else set()
        if row:
            source_ids.update(event.get('source') for event in row.get('events', []) if event.get('source'))
        return {'catalog_id': catalog_id, 'kind': kind,
                'binding_status': row['status'] if row else 'unbound',
                'current_numeric_profile_complete': False,
                'evidence': row, 'sources': {key: legend[key] for key in source_ids if key in legend},
                'catalog_rule_plan': WEAPON_PLAN.get(catalog_id),
                'stat_references': WEAPON_REFERENCES[catalog_id],
                'execution_gate': weapons['execution_gate']}
    if kind == 'armor':
        row = next((row for row in armor['unique_gear'] if row['catalog_id'] == catalog_id), None)
        member = next((row for row in armor['membership_overrides'] if row['catalog_id'] == catalog_id), None)
        return {'catalog_id': catalog_id, 'kind': kind,
                'binding_status': row['binding_status'] if row else 'unbound',
                'evidence': row, 'candidate_set_membership': member,
                'sources': {key: armor['sources'][key] for key in row.get('source_ids', [])} if row else {}}
    if kind == 'set':
        row = packet_set
        return {'catalog_id': catalog_id, 'kind': kind, 'binding_status': 'threshold_evidence' if row else 'unbound',
                'evidence': row, 'sources': armor['sources'] if row else {}}
    key = f'{catalog_id}:{level}' if level is not None else None
    import mod_core_packet
    core_entry = mod_core_packet.ENTRIES.get(catalog_id)
    row = suffixes['exact_profiles'].get(key)
    import suffix_candidates
    v3_exact = suffix_candidates.EXACT.get((catalog_id, level))
    derived = suffix_candidates.candidate(catalog_id, level)
    resolved = catalog.resolve(catalog_id, level) if level is not None else {}
    observed = resolved.get('observed_profile')
    exact_catalog = resolved.get('attribute_coverage') == 'complete' and bool(observed)
    return {'catalog_id': catalog_id, 'kind': kind, 'level': level,
            'binding_status': row['evidence_class'] if row else 'verified_exact_catalog_profile' if exact_catalog else 'no_exact_profile',
            'evidence': row or observed, 'exact_profile_in_catalog': exact_catalog,
            'exact_profile_in_suffix_packet': bool(row or v3_exact),
            'v3_direct_observation': bool(v3_exact),
            'derived_candidate_available': derived['profile_status'] if derived else None,
            'main_core_packet': ({'coverage': core_entry['coverage'],
                                  'current_comparison_status': mod_core_packet.APPLICABILITY[catalog_id]['current_comparison_status'],
                                  'primary_operator': (core_entry['primary'].get('rule') or {}).get('operator'),
                                  'primary_numeric_binding': core_entry['primary'].get('numeric_binding'),
                                  'exact_observed_levels': [{'level': obs['level'], 'variant_kind': obs.get('variant_kind'),
                                                             'evidence_class': obs['evidence_class']}
                                                            for obs in core_entry['exact_observations']]}
                                 if core_entry else None),
            'candidate_transfer_allowed': False,
            'note': 'Exact profile is observational evidence; layout and tier candidates are not transferred across families.'}


def audit_alternative(item):
    """Identify bound and missing mechanics in one arbitrary comparison side."""
    if not isinstance(item, dict):
        raise ValueError('Alternative must be an object')
    armor = PACKETS['armor_sets']
    pieces = [item, *(item.get('items') or [])]
    bound, missing = [], []
    for piece in pieces:
        identity = piece.get('catalog_id') if isinstance(piece, dict) else None
        if not identity:
            continue
        info = binding(identity, piece.get('level'))
        row = {'catalog_id': identity, 'kind': info['kind'], 'binding_status': info['binding_status']}
        if info['kind'] == 'mod':
            row['level'] = piece.get('level')
            row['exact_profile_in_packet'] = info['exact_profile_in_suffix_packet']
            row['exact_profile_in_catalog'] = info['exact_profile_in_catalog']
        elif info['kind'] == 'weapon':
            row['event_count'] = len((info['evidence'] or {}).get('events', []))
            row['unknowns'] = (info['evidence'] or {}).get('unknowns', [])
            plan = WEAPON_PLAN.get(identity)
            if plan:
                row['next_evidence'] = plan.get('next_evidence')
            missing.append(f'{identity}: current weapon fire loop and unique effects are not fully parameterized; {info["binding_status"]}')
        elif info['kind'] == 'armor' and info['evidence']:
            row['effect_kinds'] = [effect['kind'] for effect in info['evidence'].get('descriptors', [])]
            if row['binding_status'] not in CURRENT_RELEASE:
                missing.append(f'{identity}: {row["binding_status"]} armor effect is not a current executable rule')
        bound.append(row)
    set_audit = []
    for selected in item.get('sets') or []:
        name, count = selected.get('name'), selected.get('count', 0)
        normalized = str(name or '').casefold().removesuffix(' set')
        group = next((group for group in armor['sets'] if group['catalog_id'] == name or
                      group['name'].casefold().removesuffix(' set') == normalized), None)
        if not group:
            continue
        for threshold in group['thresholds']:
            if count >= threshold['required_items']:
                status = threshold['binding_status']
                set_audit.append({'catalog_id': group['catalog_id'], 'required_items': threshold['required_items'],
                                  'binding_status': status,
                                  'effect_kinds': [effect['kind'] for effect in threshold.get('descriptors', [])]})
                if status not in CURRENT_RELEASE:
                    missing.append(f'{group["name"]} {threshold["required_items"]}-piece: {status} is not a current executable rule')
    return {'items': bound, 'earned_set_thresholds': set_audit, 'missing_mechanics': missing}


def community_candidate_rows(item, context):
    """Return only explicitly opted-in, typed set candidate modifiers.

    The result is an assumption scenario. It never changes the official rule
    binding or claims a current tooltip match.
    """
    if context.get('community_candidate_opt_in') is not True:
        return [], []
    stat_names = {'weapon_damage': 'Weapon DMG', 'status_damage': 'Status DMG',
                  'weakspot_damage': 'Weakspot DMG', 'critical_damage': 'Crit DMG',
                  'magazine_capacity': 'Magazine Capacity',
                  'reload_efficiency': 'Reload Efficiency',
                  'elemental_damage': 'Elemental DMG'}
    armor = PACKETS['armor_sets']
    rows, missing = [], []
    for selected in item.get('sets') or []:
        name, count = selected.get('name'), selected.get('count', 0)
        normalized = str(name or '').casefold().removesuffix(' set')
        group = next((group for group in armor['sets'] if group['catalog_id'] == name or
                      group['name'].casefold().removesuffix(' set') == normalized), None)
        if not group:
            continue
        for threshold in group['thresholds']:
            required = threshold['required_items']
            if count < required:
                continue
            candidates = []
            if threshold['binding_status'] == 'community_snapshot_candidate':
                candidates.append(threshold)
            numeric = threshold.get('numeric_candidate')
            if numeric and not (group['catalog_id'] == 'set:bastille-set' and required == 2):
                candidates.append(numeric)
            for candidate in candidates:
                source_id = (candidate.get('source_ids') or ['catalog'])[0]
                source_record = armor['sources'][source_id]
                source = source_record.get('url') or source_record.get('upstream_repository') or source_record.get('path')
                status = candidate.get('binding_status', 'community_snapshot_candidate')
                for descriptor in candidate.get('descriptors') or []:
                    kind = descriptor.get('kind')
                    if kind not in ('modifier', 'conditional_modifier'):
                        continue
                    values = descriptor.get('stats') if isinstance(descriptor.get('stats'), list) else None
                    if values is None:
                        values = [descriptor]
                    for value in values:
                        if not isinstance(value, dict):
                            continue
                        stat = value.get('stat')
                        name = stat_names.get(stat)
                        amount = value.get('value_percent', value.get('value') if value.get('unit') == 'percent' else None)
                        if name is None or amount is None:
                            continue
                        if stat == 'elemental_damage' and context.get('element') not in descriptor.get('elements', []):
                            missing.append(f'{group["name"]} {required}-piece: choose a listed element for this community candidate')
                            continue
                        rows.append({'name': name, 'value_percent': amount,
                                     'condition': descriptor.get('trigger') if kind == 'conditional_modifier' else None,
                                     'source': source, 'source_status': status + '; explicit assumption scenario, current game version unverified',
                                     'item': group['name'],
                                     'rule_id': f'community_candidate:{group["catalog_id"]}:{required}:{stat}'})
                missing.append(f'{group["name"]} {required}-piece: community candidate included only as an explicit assumption; current effect and stacking unverified')
    return rows, missing
