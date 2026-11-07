"""Opt-in suffix hypotheses, kept separate from observed catalog profiles."""
import json
from pathlib import Path

PACKET = json.loads((Path(__file__).parent / 'evidence_packets/suffix-candidate-v3.json').read_text())
if PACKET['ownership_inferred'] or not PACKET['requires_explicit_opt_in']:
    raise ValueError('Suffix packet must remain an opt-in, non-ownership hypothesis')
if PACKET['layout_conflicts'] or PACKET['tier_conflicts']:
    raise ValueError('Conflicting suffix candidate packet')
CANDIDATES = {(row['catalog_id'], row['level']): row for row in PACKET['candidate_profiles']}
EXACT = {(row['catalog_id'], row['level']): row for row in PACKET['exact_observations']}
if set(CANDIDATES) & set(EXACT):
    raise ValueError('Derived suffix profile overlaps direct observation')
if len(CANDIDATES) != PACKET['counts']['candidate_identity_levels'] or len(EXACT) != PACKET['counts']['source_exact_identity_levels']:
    raise ValueError('Suffix packet count mismatch')


def candidate(catalog_id, level):
    return CANDIDATES.get((catalog_id, level))


def attributes(profile):
    """Expose only present candidate values; unknown rows remain null."""
    import catalog
    result = []
    for raw in profile['rows']:
        condition = raw.get('condition')
        row = {'name': catalog.OBSERVED_ATTRIBUTE_NAMES.get(raw['stat_type'], raw['stat_type']),
               'stat_type': raw['stat_type'], 'tier': raw['tier'],
               'value_percent': raw.get('value_percent') if raw['status'] == 'derived_candidate' else None,
               'unit': 'percent', 'direction': 'increase',
               'source': 'evidence_packets/suffix-candidate-v3.json',
               'source_status': 'derived candidate opt-in; game build and target level obtainability unverified',
               'evidence_context': ', '.join(raw.get('evidence_profile_ids') or profile['layout_source_profile_ids']),
               'candidate_row_status': raw['status']}
        if condition and condition != 'unconditional':
            row['condition'] = 'low HP' if condition == 'scales_with_low_hp' else condition
        if raw.get('conditional_bonus_percent') is not None:
            row['conditional_bonus_percent'] = raw['conditional_bonus_percent']
        result.append(row)
    return result


def coverage():
    return {'exact_observed_identity_levels': len(EXACT),
            'derived_complete_identity_levels': PACKET['counts']['candidate_complete'],
            'derived_partial_identity_levels': PACKET['counts']['candidate_partial'],
            'derived_total_identity_levels': len(CANDIDATES),
            'ownership_inferred': False, 'game_build_version_verified': False,
            'level_obtainability_verified': False}
