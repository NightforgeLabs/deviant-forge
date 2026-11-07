"""Evidence-gated bridge from the compiled main-mod packet to component rows."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import mod_core_adapter

ROOT = Path(__file__).parent
PACKET = json.loads((ROOT / 'evidence_packets/mod-core-v2.json').read_text())
DELTA = json.loads((ROOT / 'evidence_packets/mod-core-v3-delta.json').read_text())
if hashlib.sha256((ROOT / 'evidence_packets/mod-core-v2.json').read_bytes()).hexdigest() != DELTA['v2_packet_sha256']:
    raise ValueError('Main-mod v3 applicability is bound to a different v2 packet')
APPLICABILITY = {row['catalog_id']: row for row in DELTA['applicability_index']}
ENTRIES = {row['catalog_id']: row for row in PACKET['mods']}
if len(ENTRIES) != PACKET['statistics']['runtime_mods']:
    raise ValueError('Main-mod packet identity count mismatch')
if set(APPLICABILITY) != set(ENTRIES):
    raise ValueError('Main-mod applicability identity set mismatch')
for name, meta in PACKET['generated_from'].items():
    if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != meta['sha256']:
        raise ValueError(f'Main-mod packet source changed: {name}')

ROW_OPERATORS = {'static_modifier', 'base_plus_threshold', 'threshold_modifier',
                 'event_timed_modifier', 'event_timed_stack',
                 'state_conditional_modifier', 'target_conditional_modifier',
                 'proximity_conditional_modifier', 'event_modifier_duration_unknown',
                 'event_modifier_until_reset'}
BASE_ONLY_PARTIAL = {'base_plus_hp_cost_timed_stack_partial',
                     'base_plus_unknown_curve', 'base_plus_hp_threshold_partial'}


def _threshold(rule, context, prefix):
    resource = rule.get('resource')
    comparison = rule.get('comparison')
    target = rule.get('value')
    if resource not in ('hp_percent', 'target_hp_percent') or comparison not in ('above', 'below'):
        return None, f'{prefix}: threshold dimension or comparison unsupported'
    if isinstance(target, bool) or not isinstance(target, (int, float)) or not math.isfinite(target):
        return None, f'{prefix}: threshold value unresolved'
    actual = context.get(resource)
    if actual is None:
        return None, f'{prefix}: enter {resource} to resolve {comparison} {target:g}% activation'
    if isinstance(actual, bool) or not isinstance(actual, (int, float)) or not 0 <= actual <= 100:
        raise ValueError(f'{resource} must be 0–100')
    return (actual > target if comparison == 'above' else actual < target), None


def _gate(rule, context, prefix):
    operator = rule['operator']
    if operator == 'threshold_modifier':
        return _threshold(rule.get('threshold') or {}, context, prefix)
    if operator == 'base_plus_threshold':
        return True, None
    if operator == 'state_conditional_modifier':
        state = rule.get('state')
        states = context.get('states')
        if states is None:
            return None, f'{prefix}: active state {state} unentered'
        if not isinstance(states, list):
            raise ValueError('Active states must be a list')
        return state in states, None
    if operator == 'target_conditional_modifier':
        state = rule.get('target_state')
        states = context.get('target_states')
        if states is None:
            return None, f'{prefix}: target state {state} unentered'
        if not isinstance(states, list):
            raise ValueError('Target states must be a list')
        return state in states, None
    if operator == 'proximity_conditional_modifier':
        proximity = context.get('proximity') or {}
        if not isinstance(proximity, dict):
            raise ValueError('Proximity input must be an object')
        radius = rule.get('distance_meters')
        count = proximity.get('enemy_count')
        if count is None or proximity.get('radius_meters') != radius:
            return None, f'{prefix}: enter enemy count specifically within {radius:g}m'
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError('Nearby enemy count must be a nonnegative integer')
        return count == rule.get('enemy_count'), None
    return True, None


def _selected(entry, level, shiny, context):
    exact = next((obs for obs in entry['exact_observations']
                  if obs['level'] == level and obs.get('variant_kind', 'ordinary') == ('shiny' if shiny else 'ordinary')),
                 None)
    if exact and 'preview' not in str(exact.get('evidence_class') or '').lower():
        return exact, 'exact_observed', 'exact_level'
    if shiny:
        return None, None, None
    if context.get('core_candidate_opt_in') is True:
        return entry['primary'], 'explicit_candidate', 'unbound_level_candidate'
    return None, None, None


def rows_for(catalog_id, level, *, shiny=False, context=None):
    """Return (supported rows, blockers, binding) without inferring a level roll."""
    context = context or {}
    entry = ENTRIES.get(catalog_id)
    if entry is None:
        return [], [f'{catalog_id}: no compiled main-effect evidence'], None
    applicability = APPLICABILITY[catalog_id]['current_comparison_status']
    if applicability == 'blocked_legacy_superseded':
        return [], [f'{catalog_id}: historical main-effect text is superseded; current numeric rule withheld'], None
    if applicability == 'blocked_source_conflict':
        return [], [f'{catalog_id}: conflicting source strengths; current numeric rule withheld'], None
    if entry['coverage'] == 'conflicting_or_legacy':
        return [], [f'{catalog_id}: conflicting current and historical main-effect text; no magnitude selected'], None
    same_level = [obs for obs in entry['exact_observations'] if obs['level'] == level]
    if same_level and any('preview' in str(obs.get('evidence_class') or '').lower() for obs in same_level) and shiny:
        return [], [f'{catalog_id}: Shiny source is a preview, not a verified released exact-level binding'], None
    if same_level and any(obs.get('variant_kind') == 'unknown' for obs in same_level) and not shiny and context.get('core_candidate_opt_in') is not True:
        return [], [f'{catalog_id}: exact-level frame has unverified ordinary-versus-Shiny variant kind; no automatic binding'], None
    selected, evidence, numeric_scope = _selected(entry, level, shiny, context)
    if selected is None:
        return [], [f'{catalog_id}: no exact-level main-effect rule; community template requires core_candidate_opt_in'], None
    rule = selected.get('rule')
    if not rule:
        return [], [f'{catalog_id}: main-effect text has no safe typed rule'], {'evidence': evidence}
    source = (selected.get('source_image') or selected.get('source_url') or
              ('catalog.json#sha256=' + selected['sha256']))
    source_hash = selected.get('source_sha256') or selected.get('sha256')
    prefix = f'{catalog_id} {rule["operator"]}'
    binding = {'evidence': evidence, 'numeric_scope': numeric_scope,
               'operator': rule['operator'], 'source': source,
               'source_sha256': source_hash,
               'observed_level': level if evidence == 'exact_observed' else None,
               'game_build_version': selected.get('game_version') or 'unverified',
               'whole_dps_certified': False}
    if rule['operator'] not in ROW_OPERATORS | BASE_ONLY_PARTIAL:
        return [], [f'{prefix}: typed operator needs a separate event, resource, target or timing model'], binding
    base_only = rule['operator'] in BASE_ONLY_PARTIAL
    if rule.get('unresolved') and not base_only:
        return [], [f'{prefix}: unresolved typed parameters: {rule["unresolved"]}'], binding
    gate, gate_note = _gate(rule, context, prefix)
    missing = [gate_note] if gate_note else []
    if rule['operator'] in ('threshold_modifier', 'base_plus_threshold') and context.get('hp_percent') is not None:
        missing.append(f'{prefix}: entered HP is a snapshot; sustained threshold uptime remains unverified')
    if base_only:
        missing.append(f'{prefix}: only listed unconditional base modifiers are included; additional effect has unresolved {rule.get("unresolved")}')
    if evidence == 'explicit_candidate':
        missing.append(f'{prefix}: community main-effect strength is not bound to selected level or current game build; explicit assumption only')
    rows = []
    for index, node in enumerate(rule.get('nodes') or []):
        if node.get('op') not in ('stat_delta_percent', 'conditional_stat_delta_percent'):
            missing.append(f'{prefix}: {node.get("op") or "unknown"} node is not a component-pool modifier')
            continue
        stat = node.get('stat')
        if stat not in mod_core_adapter.STAT_LABELS:
            missing.append(f'{prefix}: {stat or "unknown"} has no mapped component pool or direct combat operator')
            continue
        base = {'catalog_id': catalog_id, 'rule_id': f'{catalog_id}:core:{index}',
                'source': source, 'numeric_scope': numeric_scope,
                'evidence_status': evidence, 'level': level,
                'stat_types': [stat], 'value_percent': node.get('value'),
                'evidence_context': f'compiled main effect; {binding["game_build_version"]}'}
        if node.get('op') == 'conditional_stat_delta_percent':
            active, note = _threshold(node.get('condition') or {}, context, prefix)
            if note: missing.append(note)
            base['operator'] = 'static'
        elif rule['operator'] == 'event_timed_stack':
            base.update(operator='stack', per_stack_percent=node.get('value'),
                        max_stacks=rule.get('max_stacks'), duration_seconds=rule.get('duration_seconds'))
            base.pop('value_percent')
            # A single stack counter is shared by all nodes of this effect.
            base['rule_id'] = catalog_id
        elif rule['operator'] == 'event_timed_modifier':
            base.update(operator='timed', condition=f'event:{rule.get("event")} active',
                        duration_seconds=rule.get('duration_seconds'))
        elif rule['operator'] in ('event_modifier_duration_unknown', 'event_modifier_until_reset'):
            base.update(operator='conditional', condition=f'event:{rule.get("event")} active')
            missing.append(f'{prefix}: event activation, expiry or reset timing unresolved')
        else:
            base['operator'] = 'static'
        compiled, notes = mod_core_adapter.evaluate(base, catalog_id=catalog_id, level=level, context=context)
        missing.extend(notes)
        if gate is False or (node.get('op') == 'conditional_stat_delta_percent' and active is False):
            for row in compiled:
                row.pop('value_percent', None)
                row['range_percent'] = [0, 0]
        elif gate is None or (node.get('op') == 'conditional_stat_delta_percent' and active is None):
            for row in compiled:
                value = row.pop('value_percent', None)
                if value is None:
                    missing.append(f'{prefix}: unresolved conditional stack interaction')
                    continue
                row['range_percent'] = [min(0, value), max(0, value)]
                row['condition'] = f'{prefix} activation'
        for row in compiled:
            row['source_sha256'] = source_hash
            if evidence == 'exact_observed':
                row['observed_level'] = level
        rows.extend(compiled)
    if rule['operator'] in ('event_timed_modifier', 'event_timed_stack') and rule.get('duration_seconds'):
        missing.append(f'{prefix}: event arrival, refresh and sustained uptime require a timeline')
    return rows, missing, binding


def coverage():
    exact_rows = [obs for entry in ENTRIES.values() for obs in entry['exact_observations']]
    opt_in_supported = sum(bool(rows_for(entry['catalog_id'], 10,
                                   context={'core_candidate_opt_in': True})[0])
                           and rows_for(entry['catalog_id'], 10,
                                        context={'core_candidate_opt_in': True})[2]['evidence'] == 'explicit_candidate'
                           for entry in ENTRIES.values())
    return {'catalog_identities_in_packet': len(ENTRIES),
            'v3_applicability_statuses': DELTA['statistics']['applicability'],
            'legacy_current_use_blocks': DELTA['statistics']['legacy_current_use_blocks'],
            'selectable_mod_identities': PACKET['statistics']['selectable_mods'],
            'typed_templates': PACKET['statistics']['coverage']['supported_operator'],
            'partial_templates': PACKET['statistics']['coverage']['partial_params'],
            'unknown_core_templates': PACKET['statistics']['coverage']['unknown_core'],
            'conflicting_templates': PACKET['statistics']['coverage']['conflicting_or_legacy'],
            'missing_effect_text': PACKET['statistics']['coverage']['missing_effect_text'],
            'exact_level_observations': PACKET['statistics']['exact_observations'],
            'ordinary_exact_observations': sum(obs.get('variant_kind') == 'ordinary' for obs in exact_rows),
            'variant_kind_unknown_observations': sum(obs.get('variant_kind') == 'unknown' for obs in exact_rows),
            'shiny_preview_observations': sum('preview' in str(obs.get('evidence_class') or '').lower() for obs in exact_rows),
            'opt_in_pool_template_scenarios_at_level_10': opt_in_supported,
            'candidate_strengths_without_level_binding': PACKET['statistics']['candidate_rows'],
            'whole_dps_certified': 0}
