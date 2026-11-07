"""Read-only one-roll comparison on a shared planned encounter.

Catalog observations supply row values, never profile ownership or activation.
Both branches use the existing typed-modifier reducer and finite shot model.
"""
import math

import combat_formula
import field_guide_profiles
import mod_rolls

TYPES = frozenset(mod_rolls.SCENARIO_TYPES) - {'all_damage_boost_percent'}
KINDS = {'none', 'reviewed_row', 'entered_row'}


def _alternative(spec, connection):
    if not isinstance(spec, dict) or spec.get('kind') not in KINDS:
        raise ValueError('Choose no roll, a reviewed row, or an entered row')
    kind = spec['kind']
    if kind == 'none':
        return {'name': 'No added roll', 'row': None, 'source': 'Unsaved choice',
                'unknowns': [], 'kind': kind, 'stat_type': None, 'value_percent': None}
    if kind == 'reviewed_row':
        catalog_id, level, index = spec.get('catalog_id'), spec.get('level'), spec.get('row_index')
        if not isinstance(catalog_id, str) or isinstance(level, bool) or not isinstance(level, int) or not 1 <= level <= 17 or isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < 4:
            raise ValueError('Choose an exact catalog variant, level and row')
        if connection is None:
            raise ValueError('Reviewed catalog evidence is unavailable')
        # Blank profile is intentional: reviewed catalog facts are shared, but
        # a Personal level must never become New Player ownership.
        detail = field_guide_profiles.preview(connection, 'new_player', catalog_id, level, 'unknown')
        if detail.get('rank_derived'):
            raise ValueError('This target level has only a rank-derived value; choose an exact reviewed row or enter a qualified what-if')
        rows = detail['reviewed_exact_rows']
        row = next((item for item in rows if item.get('row_index') == index), None)
        if (row is None or row.get('confidence') != 'source_checked' or
                row.get('calculation_status') != 'assumption_scenario' or
                row.get('stat_type') not in TYPES or
                not isinstance(row.get('value'), (int, float)) or
                isinstance(row['value'], bool) or not math.isfinite(row['value'])):
            raise ValueError('That exact catalog row has no usable reviewed numeric value')
        value = float(row['value'])
        return {'name': f"{detail['name']} <{detail['variant']}> Lv{level} · row {index + 1}",
                'row': {**row, 'tech_activation': 'unknown'},
                'source': 'Reviewed current Field Guide source frame; exact variant, level and row',
                'source_frame': detail.get('reviewed_source_frame'),
                'source_reviewed_at': detail.get('evidence_recorded_at'),
                'unknowns': ['Other rows and the mod core are excluded from this one-roll comparison.',
                             'Tech and equipment-tier activation are not confirmed by the source row.'],
                'kind': kind, 'stat_type': row['stat_type'], 'value_percent': value,
                'catalog_id': catalog_id, 'level': level, 'row_index': index}
    stat = spec.get('stat_type')
    name = spec.get('name')
    note = spec.get('source_note')
    if not isinstance(name, str) or not name.strip() or len(name) > 90:
        raise ValueError('Name the entered alternative')
    if not isinstance(note, str) or not note.strip() or len(note) > 500:
        raise ValueError('Describe where the entered value came from')
    if stat not in TYPES | {'other_unmodeled'}:
        raise ValueError('Choose a supported typed stat or Unknown effect')
    value = spec.get('value_percent')
    if stat != 'other_unmodeled' and (isinstance(value, bool) or not isinstance(value, (int, float)) or
                                      not math.isfinite(value) or not 0 <= value <= 1000):
        raise ValueError('Enter a finite percentage from 0 to 1000')
    row = {'row_index': 0, 'stat_type': stat, 'value': float(value) if stat in TYPES else None,
           'raw_text': f'{name.strip()}: {stat} {value}%' if stat in TYPES else name.strip(),
           'confidence': 'user_entered_hypothetical' if stat in TYPES else 'user_entered_unmodeled',
           'calculation_status': 'assumption_scenario' if stat in TYPES else 'unmodeled',
           'tech_activation': 'unknown', 'evidence': {'source_kind': 'user_entered',
                                                    'source_note': note.strip()}}
    return {'name': name.strip(), 'row': row, 'source': 'User-entered unsaved observation: ' + note.strip(),
            'unknowns': ['The entered value and its source have not been independently checked.',
                         'Any other rows or core effect are excluded.'],
            'kind': kind, 'stat_type': stat, 'value_percent': float(value) if stat in TYPES else None}


def compare(data, connection=None):
    if not isinstance(data, dict):
        raise ValueError('Comparison inputs must be an object')
    calibration = data.get('calibration')
    if calibration not in ('energy', 'rapid'):
        raise ValueError('Choose one calibration to hold constant')
    apply = data.get('assume_rows_active')
    if type(apply) is not bool:
        raise ValueError('Explicitly choose whether both rows are assumed active')
    baseline = data.get('baseline')
    encounter = data.get('encounter')
    if not isinstance(baseline, dict) or not isinstance(encounter, dict):
        raise ValueError('Enter one shared baseline and encounter')
    if baseline.get('base_origin') != 'pre_mod_unbuffed':
        raise ValueError('Use a pre-mod, unbuffed baseline so a roll is not applied twice')
    if encounter.get('tech_policy') not in (None, 'exclude_unknown'):
        raise ValueError('Tech activation for this roll must use the separate explicit assumption')
    shared = {**encounter, 'tech_policy': 'assume_active' if apply else 'exclude_unknown'}
    left = _alternative(data.get('a'), connection)
    right = _alternative(data.get('b'), connection)
    results = []
    for alt in (left, right):
        row = alt['row']
        if row and alt['kind'] == 'entered_row':
            row = {**row, 'external_hypothesis_confirmed': apply}
        result = combat_formula.compare(baseline, [row] if row else [], shared, {}, {})[calibration]
        duration = result['durations']['60']
        included = row is None or (apply and row in result['typed_modifiers_used'])
        unknown = row is not None and not included
        bullet = duration['bullet_damage_bounds']
        results.append({k: v for k, v in alt.items() if k != 'row'} | {
            'activation': 'assumed active for this unsaved comparison' if row and apply else
                          'not selected' if row is None else 'unknown; excluded',
            'included': included, 'unresolved_roll': unknown,
            'direct_body_hit': result['base_direct_hit_after_bonuses'],
            'expected_landed_hit': (result['hit_groups'] or {}).get('expected_landed_hit'),
            'bullet_60s_bounds': bullet,
            'reload_seconds': result['reload_seconds_scenario'],
            'magazine_bounds': result['magazine_bounds'],
            'max_hp_sensitivity': result['max_hp_sensitivity'],
            'missing': duration['missing'],
        })
    a, b = results
    a_bullet = a['bullet_60s_bounds']; b_bullet = b['bullet_60s_bounds']
    bullet_delta = (b_bullet['floor'] - a_bullet['floor'] if
                    a_bullet and b_bullet and a_bullet['floor'] == a_bullet['ceil'] and
                    b_bullet['floor'] == b_bullet['ceil'] and not (a['unresolved_roll'] or b['unresolved_roll'])
                    else None)
    direct_delta = (b['direct_body_hit'] - a['direct_body_hit'] if
                    not (a['unresolved_roll'] or b['unresolved_roll']) else None)
    # An elemental/status/HP row can leave bullets equal while changing a
    # component whose event/baseline evidence is not supplied here.
    unscored = {item['stat_type'] for item in (a, b) if item['stat_type'] in
                {'elemental_damage_percent', 'status_damage_percent', 'max_hp_percent',
                 'weakspot_damage_percent'}}
    return combat_formula.require_finite_result({
        'a': a, 'b': b, 'delta_b_minus_a_direct_hit': direct_delta,
        'delta_b_minus_a_bullet_60s': bullet_delta,
        'bullet_component_leader': (None if bullet_delta is None or unscored else
                                   'tie' if abs(bullet_delta) < 1e-9 else
                                   'b' if bullet_delta > 0 else 'a'),
        'unscored_component_types': sorted(unscored),
        'calibration': calibration, 'saved': False, 'ownership_required': False,
        'assume_rows_active': apply,
        'baseline_scope': baseline.get('source_kind') or 'unsaved pre-mod baseline',
        'complete_game_prediction': False,
        'scope': 'One typed roll at a time on the same pre-mod baseline, calibration and 60-second body-hit encounter (weakspot share 0). A Weakspot DMG row is not exercised here. Other rows, cores, buffs, Power Surge and orbs are not treated as zero.',
    })
