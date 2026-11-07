"""Conservative adapter from typed mod core rules to component rows.

This does not classify source evidence. A caller must bind a sourced rule to an
item; the adapter enforces that its numeric scope covers the selected level.
Unknown operators and missing magnitudes are returned as blockers, never zero.
"""
from __future__ import annotations

import math

STAT_LABELS = {
    'weapon_damage_percent': 'Weapon DMG',
    'status_damage_percent': 'Status DMG',
    'elemental_damage_percent': 'Elemental DMG',
    'crit_damage_percent': 'Crit DMG',
    'weakspot_damage_percent': 'Weakspot DMG',
    'power_surge_damage_percent': 'Power Surge DMG',
    'shock_damage_percent': 'Shock DMG',
    'magazine_capacity_percent': 'Magazine Capacity',
    'reload_efficiency_percent': 'Reload Efficiency',
    'fire_rate_percent': 'Fire Rate',
    'all_damage_boost_percent': 'All DMG Boost',
}


def _amount(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{label} must be a finite number')
    if not -100 <= value <= 1000:
        raise ValueError(f'{label} outside supported range')
    return float(value)


def evaluate(rule, *, catalog_id, level, context=None):
    """Return ``(rows, blockers)`` for one sourced typed core rule.

    Supported operators: static, conditional, stack, timed. Event, resource,
    target-count, trigger and unknown operators require a separate event model.
    Each output row keeps source and rule ID; the component engine handles pool
    arithmetic and correlated conditional endpoints.
    """
    context = context or {}
    if not isinstance(rule, dict) or not isinstance(context, dict):
        raise ValueError('Core rule and context must be objects')
    identity = rule.get('catalog_id')
    if identity != catalog_id:
        raise ValueError('Core rule identity does not match selected item')
    rule_id = rule.get('rule_id')
    if not isinstance(rule_id, str) or not rule_id:
        raise ValueError('Core rule needs a stable rule_id')
    prefix = f'{catalog_id} {rule_id}'
    source = rule.get('source')
    if not isinstance(source, str) or not source:
        return [], [f'{prefix}: source missing; rule withheld']
    numeric_scope = rule.get('numeric_scope')
    if numeric_scope == 'exact_level':
        if rule.get('level') != level:
            return [], [f'{prefix}: numeric magnitude is not sourced for selected level {level}']
    elif numeric_scope == 'level_invariant':
        if rule.get('level_invariance_verified') is not True:
            return [], [f'{prefix}: level invariance has no supporting evidence']
    elif numeric_scope == 'unbound_level_candidate':
        if context.get('core_candidate_opt_in') is not True or rule.get('evidence_status') != 'explicit_candidate':
            return [], [f'{prefix}: catalog strength has no selected-level binding; explicit candidate opt-in required']
    else:
        return [], [f'{prefix}: numeric level scope unresolved']
    evidence = rule.get('evidence_status')
    if evidence not in ('exact_observed', 'official_release'):
        if not (context.get('core_candidate_opt_in') is True and evidence == 'explicit_candidate'):
            return [], [f'{prefix}: {evidence or "unknown"} evidence requires explicit candidate opt-in']
    operator = rule.get('operator')
    if operator not in ('static', 'conditional', 'stack', 'timed'):
        return [], [f'{prefix}: {operator or "unknown"} operator needs an event or interaction model']
    stats = rule.get('stat_types')
    if not isinstance(stats, list) or not stats or len(stats) != len(set(stats)):
        raise ValueError('Core rule needs unique stat_types')
    names = [STAT_LABELS[stat] for stat in stats if stat in STAT_LABELS]
    missing = [f'{prefix}: {stat} has no mapped component pool or direct combat operator'
               for stat in stats if stat not in STAT_LABELS]
    if not names:
        return [], missing
    build_status = rule.get('game_build_status')
    quality = ('current build verified' if build_status == 'current_verified'
               else 'historical or unverified current game build')
    if numeric_scope == 'unbound_level_candidate':
        quality += '; magnitude is not bound to selected level'
    common = {'source': source, 'source_status': f'{evidence} core rule; {quality}; selected level scope {numeric_scope}',
              'rule_id': rule_id, 'evidence_context': rule.get('evidence_context') or ''}
    if operator in ('static', 'conditional', 'timed'):
        if rule.get('value_percent') is None:
            return [], [f'{prefix}: exact numeric magnitude missing']
        value = _amount(rule['value_percent'], 'core modifier')
        condition = rule.get('condition')
        if operator != 'static' and (not isinstance(condition, str) or not condition.strip()):
            return [], [f'{prefix}: activation condition missing']
        if operator == 'timed':
            seconds = rule.get('duration_seconds')
            if seconds is None or _amount(seconds, 'duration seconds') <= 0:
                return [], [f'{prefix}: timed duration unresolved']
            if condition.lower() not in (context.get('condition_uptime') or {}):
                missing.append(f'{prefix}: {seconds:g}s buff uptime and refresh unresolved')
        rows = [{'name': name, 'value_percent': value, **common,
                 **({'condition': condition} if operator != 'static' else {})}
                for name in names]
        return rows, missing
    if rule.get('per_stack_percent') is None or rule.get('max_stacks') is None:
        return [], [f'{prefix}: stack magnitude or cap missing']
    maximum = rule['max_stacks']
    if isinstance(maximum, bool) or not isinstance(maximum, int) or not 1 <= maximum <= 100:
        raise ValueError('Core stack cap must be an integer from 1 to 100')
    per_stack = _amount(rule['per_stack_percent'], 'per-stack modifier')
    count = (context.get('effect_stacks') or {}).get(rule_id)
    if count is None:
        values = [min(0.0, maximum * per_stack), max(0.0, maximum * per_stack)]
        missing.append(f'{prefix}: active stack count unresolved')
    else:
        if isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= maximum:
            raise ValueError('Entered core stack count outside cap')
        values = [count * per_stack] * 2
    if rule.get('duration_seconds') is not None:
        missing.append(f'{prefix}: stack expiry and uptime require a timeline for sustained damage')
    rows = [{'name': name, 'range_percent': values, 'condition': f'{rule_id} active stacks', **common}
            for name in names]
    return rows, missing
