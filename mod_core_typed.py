"""Evidence-gated typed main-mod outputs, kept separate from damage pools.

Exact observations use the v5 gate. Community templates are available only
under explicit candidate opt-in and never acquire a Field Guide level binding.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import mod_core_packet
from evaluate_template_v3 import UnknownCombatState
from exact_effect_adapter_v4 import execute as execute_raw
from exact_effect_adapter_v5 import EvidenceModeRequired, execute_binding
from partial_rule_adapter_v5 import EXECUTABLE as PARTIAL_OPERATORS
from partial_rule_adapter_v5 import execute_partial

ROOT = Path(__file__).parent
V5_EXACT = json.loads((ROOT / 'evidence_packets/mod-core-v5-exact.json').read_text())
V4_PARTIAL = json.loads((ROOT / 'evidence_packets/mod-core-v4-partial.json').read_text())
V5_PARTIAL = json.loads((ROOT / 'evidence_packets/mod-core-v5-partial.json').read_text())
V2_SHA = hashlib.sha256((ROOT / 'evidence_packets/mod-core-v2.json').read_bytes()).hexdigest()
for packet in (V5_EXACT, V4_PARTIAL, V5_PARTIAL):
    if packet['v2_packet_sha256'] != V2_SHA:
        raise ValueError('Typed main-mod packet does not match installed core evidence')
EXACT = {(row['catalog_id'], row['level']): row for row in V5_EXACT['bindings']}
if len(EXACT) != 54:
    raise ValueError('Expected 54 distinct exact main-effect observations')
PARTIAL = {row['catalog_id']: row for row in V4_PARTIAL['bindings']}
RESIDUAL = {row['catalog_id']: row for row in V5_PARTIAL['rows']}


def coverage():
    return {'exact_observations': len(EXACT),
            'exact_by_evidence': V5_EXACT['statistics'],
            'partial_rules': len(PARTIAL),
            'partial_known_component_operators': sum(row['operator'] in PARTIAL_OPERATORS
                                                      for row in PARTIAL.values()),
            'residual_partial_rules': len(RESIDUAL),
            'whole_dps_certified': 0}


def evaluate(catalog_id, level, *, shiny=False, context=None):
    """Return a typed output or an explicit evidence/context blocker."""
    context = context or {}
    if not isinstance(context, dict):
        raise ValueError('Typed main-effect context must be an object')
    binding = EXACT.get((catalog_id, level))
    if binding:
        status = binding['variant_kind']
        if status == 'unknown' and context.get('core_unknown_variant_opt_in') is not True:
            return {'catalog_id': catalog_id, 'level': level, 'status': 'variant_kind_unknown',
                    'outputs': [], 'missing': ['Observed card does not establish ordinary versus Shiny; use explicit unknown-variant scenario opt-in.'],
                    'evidence_class': binding['evidence_class'],
                    'source_sha256': binding['source_sha256'], 'whole_dps_certified': False}
        if status in ('ordinary', 'shiny') and (status == 'shiny') != bool(shiny):
            return {'catalog_id': catalog_id, 'level': level, 'status': 'variant_mismatch',
                    'outputs': [], 'missing': ['Observed main effect belongs to a different ordinary/Shiny variant.'],
                    'evidence_class': binding['evidence_class'],
                    'source_sha256': binding['source_sha256'], 'whole_dps_certified': False}
        try:
            answer = execute_binding(binding, context,
                allow_preview=context.get('core_preview_opt_in') is True,
                allow_unknown_game_build=context.get('core_unknown_build_opt_in') is True)
        except (EvidenceModeRequired, UnknownCombatState) as error:
            return {'catalog_id': catalog_id, 'level': level,
                    'status': ('evidence_opt_in_required' if isinstance(error, EvidenceModeRequired)
                               else 'combat_context_missing'),
                    'outputs': [], 'missing': [str(error)],
                    'evidence_class': binding['evidence_class'],
                    'source_sha256': binding['source_sha256'], 'whole_dps_certified': False}
        return {'status': 'observed_typed_output', **answer,
                'missing': list(answer.get('unresolved') or []),
                'source_image': binding.get('source_image')}
    if context.get('core_candidate_opt_in') is not True:
        return None
    entry = mod_core_packet.ENTRIES.get(catalog_id)
    if entry is None:
        return None
    applicability = mod_core_packet.APPLICABILITY[catalog_id]['current_comparison_status']
    if applicability in ('blocked_legacy_superseded', 'blocked_source_conflict'):
        return {'catalog_id': catalog_id, 'level': level, 'status': applicability,
                'outputs': [], 'missing': ['Historical or conflicting main-effect text cannot be used as a current numeric candidate.'],
                'whole_dps_certified': False}
    if shiny:
        return {'catalog_id': catalog_id, 'level': level, 'status': 'candidate_shiny_unbound',
                'outputs': [], 'missing': ['Community candidate has no exact Shiny level binding.'],
                'whole_dps_certified': False}
    residual = RESIDUAL.get(catalog_id)
    if residual and residual.get('current_listing_match') is False:
        return {'catalog_id': catalog_id, 'level': level,
                'status': 'historical_identity_unmatched', 'outputs': [],
                'missing': [residual['next_action']],
                'numeric_binding': 'historical_community_strength_unbound_to_level',
                'whole_dps_certified': False}
    primary = entry.get('primary') or {}
    rule = primary.get('rule')
    if not rule:
        return {'catalog_id': catalog_id, 'level': level, 'status': 'candidate_rule_missing',
                'outputs': [], 'missing': ['No typed primary main-effect rule for this identity.'],
                'whole_dps_certified': False}
    operator = rule['operator']
    try:
        answer = (execute_partial(rule, context) if operator in PARTIAL_OPERATORS
                  else execute_raw(rule, context))
    except UnknownCombatState as error:
        return {'catalog_id': catalog_id, 'level': level, 'status': 'candidate_context_missing',
                'operator': operator, 'outputs': [], 'missing': [str(error)],
                'numeric_binding': 'community_strength_unbound_to_selected_level',
                'source_sha256': primary.get('sha256'), 'whole_dps_certified': False}
    except NotImplementedError:
        return {'catalog_id': catalog_id, 'level': level, 'status': 'candidate_operator_unimplemented',
                'operator': operator, 'outputs': [],
                'missing': ['Typed operator requires an additional event or state evaluator.'],
                'numeric_binding': 'community_strength_unbound_to_selected_level',
                'source_sha256': primary.get('sha256'), 'whole_dps_certified': False}
    return {'catalog_id': catalog_id, 'level': level,
            'status': 'explicit_community_candidate_output',
            'operator': operator, 'outputs': answer['outputs'],
            'missing': list(answer.get('unresolved') or []),
            'numeric_binding': 'community_strength_unbound_to_selected_level',
            'source_warning': 'Explicit what-if; source magnitude is not bound to the selected Field Guide level or current game build.',
            'source_url': primary.get('source_url'), 'source_sha256': primary.get('sha256'),
            'whole_dps_certified': False}
