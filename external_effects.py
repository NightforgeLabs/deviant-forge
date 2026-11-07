"""Unsaved, user-entered effect hypotheses for an existing component formula.

Names and amounts are observations supplied by a user, not catalog mechanics.
No effect is treated as active without an explicit interval and baseline claim.
"""
from math import isfinite

import mod_rolls


SOURCES = {'gear', 'deviation', 'food', 'drink', 'injection', 'other'}
SUPPORTED = {
    'weapon_damage_percent', 'crit_damage_percent', 'weakspot_damage_percent',
    'elemental_damage_percent', 'status_damage_percent',
    'magazine_capacity_percent', 'reload_efficiency_percent', 'max_hp_percent',
}
UNSUPPORTED = {'healing_or_shield_unmodeled', 'weapon_vulnerability_unmodeled',
               'status_vulnerability_unmodeled', 'other_unmodeled'}
ACTIVATION = {'unknown', 'inactive', 'observed_active'}


def resolve(spec, selected_rows):
    """Return one typed row plus disclosure, without editing gear or evidence."""
    if spec in (None, {}):
        return {'row': None, 'detail': None, 'blocking': False}
    if not isinstance(spec, dict) or set(spec) - {
        'source_kind', 'name', 'stat_type', 'value_percent', 'source_note',
        'activation', 'apply_hypothesis', 'baseline_excludes_effect',
        'active_for_interval',
    }:
        raise ValueError('External effect has unsupported fields')
    kind, name = spec.get('source_kind'), spec.get('name')
    stat_type, activation = spec.get('stat_type'), spec.get('activation', 'unknown')
    note = spec.get('source_note')
    if kind not in SOURCES or not isinstance(name, str) or not name.strip() or len(name) > 80:
        raise ValueError('Name the external effect and choose its source kind')
    if not isinstance(note, str) or not note.strip() or len(note) > 500:
        raise ValueError('Record a short source note for this external effect')
    if stat_type not in SUPPORTED | UNSUPPORTED or activation not in ACTIVATION:
        raise ValueError('Choose an available external stat type and activation state')
    for key in ('apply_hypothesis', 'baseline_excludes_effect', 'active_for_interval'):
        if type(spec.get(key, False)) is not bool:
            raise ValueError(key.replace('_', ' ') + ' must be explicit')
    magnitude = spec.get('value_percent')
    if stat_type in SUPPORTED:
        if isinstance(magnitude, bool) or not isinstance(magnitude, (int, float)) or not isfinite(magnitude) or not 0 <= magnitude <= 1000:
            raise ValueError('Enter a finite observed percentage for this supported stat')
    elif magnitude not in (None, '') and (isinstance(magnitude, bool) or
            not isinstance(magnitude, (int, float)) or not isfinite(magnitude) or
            not 0 <= magnitude <= 1000):
        raise ValueError('Observed unsupported amount must be a finite percentage')
    apply = spec.get('apply_hypothesis') is True
    if apply and activation != 'observed_active':
        raise ValueError('Confirm the external effect was observed active before applying its hypothetical amount')
    if apply and (not spec.get('baseline_excludes_effect') or not spec.get('active_for_interval')):
        raise ValueError('Confirm the baseline excludes this effect and assume it lasts through the modeled interval')
    conflict = stat_type in SUPPORTED and any(row.get('stat_type') == stat_type for row in selected_rows)
    supported = stat_type in SUPPORTED
    modeled = supported and apply and not conflict
    reason = ('inactive, excluded' if activation == 'inactive' else
              'unsupported mechanic, retained without a damage bucket' if not supported else
              'same stat type already selected; stacking unknown, excluded' if conflict else
              'included only in an explicit interval and baseline what-if' if modeled else
              'activation or application assumption not confirmed, excluded')
    row = None
    if activation != 'inactive':
        row = {'row_index': 0, 'stat_type': stat_type, 'value': magnitude if supported else None,
               'visible_magnitude': magnitude,
               'unit': 'percent' if magnitude is not None else 'unknown',
               'direction': 'increase' if supported else 'unknown',
               'condition': 'user-entered interval hypothesis' if modeled else 'unknown',
               'applicability': mod_rolls.APPLICABILITY.get(stat_type, []),
               'calculation_status': 'assumption_scenario' if modeled else 'unmodeled',
               'tech_activation': 'external_interval_hypothesis' if modeled else 'unknown',
               'confidence': 'user_entered_hypothetical' if modeled else 'user_entered_unmodeled',
               'external_hypothesis_confirmed': modeled,
               'raw_text': f'{name}: {stat_type} {magnitude:g}%' if magnitude is not None else f'{name}: {stat_type}',
               'evidence': {'source_kind': kind, 'source_note': note.strip()},
               'model_exclusion': reason if not modeled else None}
    return {'row': row, 'detail': {
        'source_kind': kind, 'name': name.strip(), 'stat_type': stat_type,
        'value_percent': magnitude, 'source_note': note.strip(),
        'activation': activation, 'applied': modeled, 'reason': reason,
        'baseline_excludes_effect': spec.get('baseline_excludes_effect') is True,
        'active_for_interval': spec.get('active_for_interval') is True,
    }, 'blocking': bool(row and mod_rolls.may_affect_offense(row) and not modeled)}


def resolve_many(specs, selected_rows, *, assume_compatible_sources=False,
                 assume_same_stat_additive=False):
    """Resolve up to three unsaved observations without order-dependent stacking.

    One source may have several different typed rows. Distinct sources require
    an explicit compatibility hypothesis; repeated stat types additionally
    require an additive-bucket hypothesis. Neither is a verified game rule.
    """
    if specs in (None, []):
        return {'rows': [], 'details': [], 'blocking': False,
                'assumptions': []}
    if not isinstance(specs, list) or not 1 <= len(specs) <= 3:
        raise ValueError('Enter one to three external-effect rows')
    if type(assume_compatible_sources) is not bool or type(assume_same_stat_additive) is not bool:
        raise ValueError('External stacking assumptions must be explicit')
    if assume_same_stat_additive and not assume_compatible_sources:
        raise ValueError('Confirm source compatibility before assuming additive same-stat stacking')
    unique = {}
    duplicate_details = []
    for spec in specs:
        if not isinstance(spec, dict) or not spec:
            raise ValueError('Each external effect must be a nonempty object with a named source and stat')
        # Validate the original intent before a stacking rule changes whether
        # it can be included; an unknown activation cannot become acceptable
        # merely because another source also conflicts.
        resolve(spec, [])
        key = (str(spec.get('source_kind', '')).strip().casefold(),
               str(spec.get('name', '')).strip().casefold(),
               str(spec.get('stat_type', '')).strip())
        if key in unique:
            previous = unique[key]
            comparison = ('value_percent','activation','apply_hypothesis',
                          'baseline_excludes_effect','active_for_interval')
            if any(previous.get(field) != spec.get(field) for field in comparison):
                raise ValueError('Conflicting readings for the same external source and stat; reconcile them before calculation')
            duplicate_details.append({'source_kind':spec.get('source_kind'),
                                      'name':spec.get('name'),'stat_type':spec.get('stat_type'),
                                      'applied':False,
                                      'reason':'duplicate source and stat observation; counted once',
                                      'source_note':spec.get('source_note')})
            continue
        unique[key] = spec
    ordered = [unique[key] for key in sorted(unique)]
    # An observed but unsupported healing/vulnerability mechanic never enters a
    # typed bucket. Retain it as unmodeled evidence without excluding an
    # otherwise usable numeric component from another source.
    requested = [item for item in ordered if item.get('apply_hypothesis') is True
                 and item.get('stat_type') in SUPPORTED]
    sources = {(item.get('source_kind'),str(item.get('name','')).strip().casefold())
               for item in requested}
    source_conflict = len(sources) > 1 and not assume_compatible_sources
    counts = {}
    for item in requested:
        stat = item.get('stat_type')
        if stat in SUPPORTED:
            counts[stat] = counts.get(stat,0)+1
    rows,details=[],[]
    for item in ordered:
        stat = item.get('stat_type')
        same_type = item.get('apply_hypothesis') is True and counts.get(stat,0)>1
        type_conflict = same_type and not assume_same_stat_additive
        forced_reason = ('Multiple named sources may not coexist or stack; check the explicit compatibility what-if' if source_conflict and item in requested else
                         'Repeated stat type has unverified stacking; check the explicit additive-bucket what-if' if type_conflict else None)
        effective = {**item,'apply_hypothesis':False} if forced_reason else item
        selected = [] if assume_same_stat_additive else selected_rows
        result = resolve(effective,selected)
        if forced_reason:
            result['detail']['reason']=forced_reason
            result['detail']['applied']=False
            if result['row']:
                result['row']['model_exclusion']=forced_reason
        if result['row']:
            result['row']['evidence']['external_source_name']=item['name'].strip()
            rows.append(result['row'])
        details.append(result['detail'])
    details.extend(duplicate_details)
    assumptions = []
    if assume_compatible_sources:
        assumptions.append('Named external sources and selected gear are assumed compatible for this unsaved scenario; game rules not verified.')
    if assume_same_stat_additive:
        assumptions.append('Repeated supported stat types, including selected gear rows, are assumed additive within their existing typed bucket; game stacking not verified.')
    return {'rows':rows,'details':details,
            'blocking':any(row and mod_rolls.may_affect_offense(row) and row.get('model_exclusion') for row in rows),
            'assumptions':assumptions}
