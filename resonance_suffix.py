"""Sourced Resonance suffix stacks for explicit, ordered damage outcomes."""
from __future__ import annotations

import math

import public_catalog_detail

TRIGGERS = {'elemental_dmg': 'elemental', 'crit_dmg': 'crit',
            'weakspot_dmg': 'weakspot'}
TARGETS = {'elemental_dmg': 'elemental', 'crit_dmg': 'crit',
           'weakspot_dmg': 'weakspot'}
MODEL_ASSUMPTIONS = {'trigger': 'explicit_resolved_packet_outcome',
                     'activation': 'after_packet', 'expiry': 'per_instance_half_open',
                     'cap': 'discard_excess_until_expiry'}


def bindings(choice):
    identity, level = choice['catalog_id'], choice['level']
    if choice.get('shiny') is True:
        raise ValueError('Published ordinary Resonance layout does not establish a Shiny binding')
    rows, _, _ = public_catalog_detail.calculation_rows(identity, level)
    found = []
    for row in rows:
        key = row.get('stat_type') or ''
        if not key.startswith('resonance_'):
            continue
        halves = key.removeprefix('resonance_').split('_to_')
        if len(halves) != 2 or halves[0] not in TRIGGERS or halves[1] not in TARGETS:
            raise ValueError('Unknown Resonance trigger or destination')
        parts = row.get('components') or {}
        corroborated = row.get('published_structured_corroboration')
        if row.get('source_conflict') or not (corroborated or
                str(row.get('source_status', '')).startswith('published_formula_candidate')):
            raise ValueError('Resonance rule lacks a nonconflicting published formula')
        count, cap = parts.get('trigger_instances'), parts.get('max_stacks')
        amount, seconds = parts.get('per_stack_percent'), parts.get('duration_seconds')
        if not all(isinstance(value, (int, float)) and not isinstance(value, bool) and
                   math.isfinite(value) and value > 0 for value in (count, cap, amount, seconds)):
            raise ValueError('Resonance rule has incomplete trigger, stack, cap or duration')
        if int(count) != count or int(cap) != cap:
            raise ValueError('Resonance instance count and cap must be whole numbers')
        found.append({'catalog_id': identity, 'level': level,
                      'bonus_position': row['public_bonus_position'],
                      'trigger': TRIGGERS[halves[0]], 'pool': TARGETS[halves[1]],
                      'trigger_instances': int(count), 'max_stacks': int(cap),
                      'per_stack_percent': float(amount), 'duration_seconds': float(seconds),
                      'source': corroborated or row['source'],
                      'observed_source': row['source'] if corroborated else None,
                      'source_status': row['source_status'],
                      'stacks': [], 'pending_hits': 0})
    if not found:
        raise ValueError('Selected identity and level have no sourced Resonance suffix rows')
    return found


def selected_choices(build):
    """Identify ordinary selected mods with unlocked Resonance lines."""
    selected = []
    for choice in build.get('selected_mods') or []:
        if choice.get('shiny') is True:
            continue
        rows, _, _ = public_catalog_detail.calculation_rows(choice['catalog_id'], choice['level'])
        if any(str(row.get('stat_type') or '').startswith('resonance_') for row in rows):
            selected.append({'catalog_id': choice['catalog_id'], 'level': choice['level']})
    return selected


def guided_shot_outcomes(events, entered):
    """Attach entered positive and negative outcomes to every scheduled shot."""
    if not isinstance(entered, dict):
        raise ValueError('Resonance needs explicit per-shot crit, weakspot and elemental outcome lists')
    shots = [event for event in events if event['kind'] == 'shot']
    found = {}
    for key in ('crit_shot_indices', 'weakspot_shot_indices', 'elemental_shot_indices'):
        values = entered.get(key)
        if not isinstance(values, list) or any(isinstance(index, bool) or not isinstance(index, int) or
                                              not 0 <= index < len(shots) for index in values) or len(set(values)) != len(values):
            raise ValueError(f'{key}: enter unique zero-based indices within the scheduled shots, or an empty list')
        found[key] = set(values)
    element = entered.get('element')
    if found['elemental_shot_indices'] and element not in ('shock', 'blaze', 'frost', 'blast'):
        raise ValueError('Named elemental direct-hit hypothesis required for elemental shot indices')
    if not found['elemental_shot_indices'] and element not in (None, 'none'):
        raise ValueError('An elemental direct-hit hypothesis needs selected shot indices')
    for index, event in enumerate(shots):
        event['packet_outcome'] = {
            'crit': index in found['crit_shot_indices'],
            'weakspot': index in found['weakspot_shot_indices'],
            'element': element if index in found['elemental_shot_indices'] else 'none'}
    return len(shots)


def active_pools(nodes, at):
    out = {'crit': 0., 'weakspot': 0., 'elemental': 0.}
    for node in nodes:
        node['stacks'] = [expiry for expiry in node['stacks'] if at < expiry]
        out[node['pool']] += len(node['stacks']) * node['per_stack_percent']
    return out


def complete_packet(nodes, packet, at):
    """A packet earns stacks only after its own damage was calculated."""
    outcomes = {'elemental': packet['element'] not in ('none', 'non_elemental'),
                'crit': packet['crit'], 'weakspot': packet['weakspot']}
    activated = []
    for node in nodes:
        if not outcomes[node['trigger']]:
            continue
        node['pending_hits'] += packet['resolved_hits']
        grants, node['pending_hits'] = divmod(node['pending_hits'], node['trigger_instances'])
        for _ in range(grants):
            if len(node['stacks']) >= node['max_stacks']:
                break
            node['stacks'].append(at + node['duration_seconds'])
            activated.append({'catalog_id': node['catalog_id'], 'bonus_position': node['bonus_position'],
                              'pool': node['pool'], 'percentage_points': node['per_stack_percent'],
                              'expires_at': at + node['duration_seconds'],
                              'source': node['source']})
    return activated
