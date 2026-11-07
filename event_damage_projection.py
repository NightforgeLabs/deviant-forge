"""Explicit-input damage projection for ordered weapon timeline events.

This bridge never supplies an unobserved Attack/Psi value, damage class, proc
coefficient, crit rule, or tick schedule. A partial scenario retains its known
subtotal while leaving the full total and rate unknown.
"""
from __future__ import annotations

from decimal import Decimal

import combat_projection
from weapon_mechanics.operators import D
from weapon_mechanics.damage_projection_v3 import load_damage_bindings, project_event

MAX_PACKETS = 10000
POOL_NAMES = {'weapon', 'status', 'elemental', 'all', 'crit', 'weakspot'}
DAMAGE_TYPES = {'keyword_trigger', 'damage_trigger', 'damage_packet'}
DAMAGE_BINDINGS = load_damage_bindings()['packets']


def _positive(value, label):
    return combat_projection.number(value, label, 0.000001)


def _finite(value, label, low=0, high=1_000_000):
    return combat_projection.number(value, label, low, high)


def _count(value, label):
    result = _finite(value, label, 1, 10000)
    if not result.is_integer():
        raise ValueError(f'{label} must be a whole number')
    return int(result)


def _nonnegative_count(value, label):
    result = _finite(value, label, 0, 10000)
    if not result.is_integer():
        raise ValueError(f'{label} must be a whole number')
    return int(result)


def _element(descriptor):
    element = descriptor.get('element')
    explicit = descriptor.get('elemental_pool_applies')
    if element is not None:
        if not isinstance(element, str) or element.lower() not in ('blaze', 'frost', 'shock', 'blast', 'none', 'non_elemental'):
            raise ValueError('Damage packet element must be Blaze, Frost, Shock, Blast or none')
        element = element.lower()
    if explicit is not None and not isinstance(explicit, bool):
        raise ValueError('elemental_pool_applies must be true or false')
    implied = element not in ('none', 'non_elemental') if element is not None else None
    if explicit is not None and implied is not None and explicit != implied:
        raise ValueError('Element tag conflicts with elemental pool applicability')
    return element, explicit if explicit is not None else implied


def _packet(descriptor, *, pools, bases, joint_model, event_id, at, name,
            source, action=None, packet_id=None, event=None, evidence_mode=None,
            weapon_id=None, references=None, instances=1):
    if not isinstance(descriptor, dict):
        raise ValueError(f'{name}: packet model must be an object')
    descriptor = dict(descriptor)
    source_binding = DAMAGE_BINDINGS.get(packet_id) if packet_id else None
    if packet_id and source_binding is None:
        raise ValueError(f'{name}: unknown source packet id')
    if source_binding:
        for key in ('basis', 'damage_class', 'element', 'crit_eligible', 'weakspot_eligible'):
            known = source_binding.get(key)
            if key == 'element' and known == 'variable_deviation':
                continue
            if known is not None:
                if key in descriptor and descriptor[key] != known:
                    raise ValueError(f'{name}: supplied {key} conflicts with source binding')
                descriptor[key] = known
    if event and event.get('coefficient') is not None:
        for key in ('basis', 'damage_class', 'element'):
            known = event.get(key)
            if known is not None:
                if key in descriptor and descriptor[key] != known:
                    raise ValueError(f'{name}: supplied {key} conflicts with generated event')
                descriptor[key] = known
        source_percent = float(D(event['coefficient']) * 100)
        if 'coefficient_percent' in descriptor and abs(float(descriptor['coefficient_percent']) - source_percent) > 1e-9:
            raise ValueError(f'{name}: supplied coefficient conflicts with generated event')
        descriptor['coefficient_percent'] = source_percent
    basis = descriptor.get('basis')
    damage_class = descriptor.get('damage_class')
    if basis not in ('attack', 'psi', 'reference_damage'):
        return None, f'{name}: Attack/Psi or named reference basis required'
    class_invariant = damage_class is None and pools['weapon'] == pools['status']
    if damage_class not in ('weapon', 'status') and not class_invariant:
        return None, f'{name}: Weapon/Status damage class unresolved and class pools differ'
    if not source_binding and descriptor.get('coefficient_percent') is None:
        return None, f'{name}: damage coefficient missing'
    references = references or {}
    basis_value = (action.get('damage_basis_value') if action and 'damage_basis_value' in action
                   else descriptor.get('basis_value',
                        references.get(source_binding.get('reference_key')) if basis == 'reference_damage' and source_binding
                        else bases.get(basis)))
    if basis_value is None:
        return None, f'{name}: {basis} basis value missing'
    basis_value = _finite(basis_value, f'{basis} basis value')
    element, elemental = _element(descriptor)
    if elemental is None and pools['elemental']:
        return None, f'{name}: elemental pool applicability unclassified'
    crit = action.get('crit', False) if action else descriptor.get('crit', False)
    weakspot = action.get('weakspot', False) if action else descriptor.get('weakspot', False)
    if not isinstance(crit, bool) or not isinstance(weakspot, bool):
        raise ValueError(f'{name}: crit and weakspot observations must be true or false')
    if crit and descriptor.get('crit_eligible') is not True:
        return None, f'{name}: crit eligibility unverified'
    if weakspot and descriptor.get('weakspot_eligible') is not True:
        return None, f'{name}: weakspot eligibility unverified'
    crit_bonus = pools['crit'] / 100 if crit else 0
    weak_bonus = pools['weakspot'] / 100 if weakspot else 0
    crit_weak = ((1 + crit_bonus) * (1 + weak_bonus) if joint_model == 'multiplicative'
                 else 1 + crit_bonus + weak_bonus)
    class_pool = pools['weapon'] if class_invariant else pools[damage_class]
    multiplier = (1 + pools['all'] / 100) * (1 + class_pool / 100)
    if elemental:
        multiplier *= 1 + pools['elemental'] / 100
    source_unresolved = []
    if source_binding:
        if source_binding.get('requires_target_count'):
            if descriptor.get('target_count') is None:
                return None, f'{name}: explicit target count missing for AoE blast'
            instances = _nonnegative_count(descriptor['target_count'], 'AoE target count')
        source_event = dict(event or {})
        source_event.update(event_id=event_id, event=source_binding['event'],
                            weapon_id=weapon_id, effect_type='damage_packet',
                            instances=instances)
        if source_binding.get('requires_target_count'):
            source_event['target_count'] = instances
        if source_binding['requires_resolved_hit']:
            source_event['resolved_hit'] = True
        source_result = project_event(packet_id, source_event,
            attack=basis_value if basis == 'attack' else None,
            psi=basis_value if basis == 'psi' else None,
            references=({source_binding['reference_key']: basis_value}
                        if basis == 'reference_damage' else None),
            evidence_mode=evidence_mode)
        coefficient = float(source_result.coefficient * 100)
        if ('coefficient_percent' in descriptor and
                abs(_finite(descriptor['coefficient_percent'], 'packet coefficient percent') - coefficient) > 1e-9):
            raise ValueError(f'{name}: supplied coefficient conflicts with source binding')
        raw = float(source_result.raw_damage)
        source = source_result.evidence_status + '; source packet ' + packet_id
        source_unresolved = list(source_result.unresolved)
    else:
        coefficient = _finite(descriptor['coefficient_percent'], 'packet coefficient percent')
        raw = basis_value * coefficient / 100 * instances
    damage = raw * multiplier * crit_weak
    return {'event_id': event_id, 'at': float(D(at)), 'event': name,
            'basis': basis, 'basis_value': basis_value,
            'damage_class': damage_class,
            'class_invariant_under_entered_pools': class_invariant,
            'element': element,
            'elemental_pool_applies': elemental,
            'coefficient_percent': coefficient, 'crit': crit,
            'weakspot': weakspot, 'instances': instances, 'damage': damage,
            'source_status': source, 'source_packet_id': packet_id,
            'source_unresolved': source_unresolved}, None


def _tick_times(trigger_at, periodic, encounter_end):
    if not isinstance(periodic, dict):
        raise ValueError('Periodic schedule must be an object')
    duration = _positive(periodic.get('duration_seconds'), 'periodic duration')
    interval = _positive(periodic.get('interval_seconds'), 'periodic interval')
    delay = _finite(periodic.get('start_delay_seconds'), 'periodic start delay')
    endpoint = periodic.get('include_endpoint', False)
    if not isinstance(endpoint, bool):
        raise ValueError('Periodic endpoint policy must be true or false')
    policy = periodic.get('refresh_model')
    if policy not in ('independent', 'replace_per_target'):
        raise ValueError('Periodic refresh model must be independent or replace_per_target')
    count = combat_projection.periodic_tick_count(duration, interval, delay, endpoint)
    if count > MAX_PACKETS:
        raise ValueError('Periodic packet limit exceeded')
    start = D(trigger_at) + D(delay)
    return [start + n * D(interval) for n in range(count)
            if encounter_end is None or start + n * D(interval) <= encounter_end]


def project(actions, events, binding, model, *, stream_id, weapon_id,
            evidence_mode):
    """Project explicit packets; never turn an unknown component into zero."""
    if not isinstance(model, dict):
        raise ValueError('Damage model must be an object')
    bases = model.get('basis_values') or {}
    pools_input = model.get('bonus_pools_percent') or {}
    packet_models = model.get('packet_models') or {}
    references = model.get('reference_values') or {}
    for label, value in (('basis_values', bases), ('bonus_pools_percent', pools_input),
                         ('packet_models', packet_models), ('reference_values', references)):
        if not isinstance(value, dict):
            raise ValueError(f'{label} must be an object')
    if set(bases) - {'attack', 'psi'} or set(pools_input) - POOL_NAMES:
        raise ValueError('Unknown damage basis or bonus pool')
    pools = {name: _finite(pools_input.get(name, 0), name + ' pool percent', -99, 1000)
             for name in POOL_NAMES}
    for name, value in bases.items():
        _finite(value, name + ' basis value')
    for name, value in references.items():
        if not isinstance(name, str) or not name:
            raise ValueError('Reference damage names must be nonempty strings')
        _finite(value, name + ' reference damage')
    joint_model = model.get('crit_weakspot_joint', 'multiplicative')
    if joint_model not in ('additive', 'multiplicative'):
        raise ValueError('Crit and weakspot joint model must be additive or multiplicative')
    non_damage = model.get('non_damage_events') or []
    if not isinstance(non_damage, list) or any(not isinstance(x, str) for x in non_damage):
        raise ValueError('non_damage_events must be a list of event names')
    if set(non_damage) & set(packet_models):
        raise ValueError('An event cannot be both a damage packet and non-damage')
    state_accounted = model.get('state_effects_accounted_for_by_input', False)
    if not isinstance(state_accounted, bool):
        raise ValueError('state_effects_accounted_for_by_input must be true or false')
    has_state_stat = any(event.get('effect_type') == 'state_change' and event.get('stat')
                         for event in events)
    if has_state_stat and state_accounted and any(
            action['kind'] == 'hit' and 'damage_basis_value' not in action
            for action in actions):
        raise ValueError('State accounted mode needs damage_basis_value on every hit')
    duration = model.get('duration_seconds')
    encounter_end = D(_positive(duration, 'encounter duration')) if duration is not None else None
    reload_input = model.get('reload_timing')
    reload_duration = None
    if reload_input is not None:
        if not isinstance(reload_input, dict):
            raise ValueError('Reload timing must be an object')
        reload_duration = D(combat_projection.reload_seconds(
            reload_input.get('base_seconds'), reload_input.get('efficiency_percent', 0)))
    direct = model.get('direct')
    if direct is not None and not isinstance(direct, dict):
        raise ValueError('Direct packet must be an object')
    known = []
    unresolved = []
    timing_unresolved = []
    seen_hits = set()
    hit_targets = {}
    replayed_hits = 0
    blocked_until = D(-1)
    for action in actions:
        at = D(action['at'])
        if encounter_end is not None and at > encounter_end:
            raise ValueError('Source action occurs after encounter duration')
        if action['kind'] in ('hit', 'fire', 'reload') and at < blocked_until:
            raise ValueError('Hit, fire or reload occurs before entered reload time ends')
        if action['kind'] == 'reload':
            if reload_duration is not None:
                blocked_until = at + reload_duration
                if encounter_end is not None and blocked_until > encounter_end:
                    raise ValueError('Encounter duration ends during entered reload time')
            else:
                timing_unresolved.append({'event_id': 'reload:' + action['input_id'], 'at': float(at),
                                          'reason': 'Reload duration missing; sustained rate unresolved'})
        if action['kind'] != 'hit':
            continue
        hit_targets[action['input_id']] = action.get('target')
        if action['input_id'] in seen_hits:
            replayed_hits += 1
            continue
        seen_hits.add(action['input_id'])
        identifier = f'{stream_id}/{weapon_id}/hit/input-{action["input_id"]}/landed'
        if direct is None:
            unresolved.append({'event_id': identifier, 'at': float(at),
                               'reason': 'Direct hit magnitude and class missing'})
            continue
        packet, reason = _packet(direct, pools=pools, bases=bases, joint_model=joint_model,
                                 event_id=identifier, at=at, name='direct_hit',
                                 source='caller_explicit_direct_packet', action=action)
        if reason:
            unresolved.append({'event_id': identifier, 'at': float(at), 'reason': reason})
        else:
            known.append(packet)
    next_replacement = {}
    upcoming_by_target = {}
    for event in reversed(events):
        descriptor = packet_models.get(event.get('event')) or {}
        periodic = descriptor.get('periodic') if isinstance(descriptor, dict) else None
        if (event.get('effect_type') in DAMAGE_TYPES and isinstance(periodic, dict)
                and periodic.get('refresh_model') == 'replace_per_target'):
            target = hit_targets.get(event.get('source_event_id', '').removeprefix('input-'))
            key = (event['event'], target)
            next_replacement[event['event_id']] = upcoming_by_target.get(key)
            upcoming_by_target[key] = D(event['at'])
    seen_ids = set()
    for event in events:
        if event['effect_type'] == 'state_change' and event.get('stat') and not state_accounted:
            unresolved.append({'event_id': event['event_id'], 'at': float(D(event['at'])),
                               'reason': f'{event["event"]}: state modifier not applied to entered packet values'})
        if event['effect_type'] not in DAMAGE_TYPES:
            continue
        identifier = event['event_id']
        if identifier in seen_ids:
            continue
        seen_ids.add(identifier)
        at = D(event['at'])
        name = event['event']
        if name in non_damage:
            if event['effect_type'] in ('damage_trigger', 'damage_packet'):
                raise ValueError(f'{name}: a source-labeled damage event cannot be marked non-damage')
            continue
        descriptor = packet_models.get(name, {})
        if not isinstance(descriptor, dict):
            raise ValueError(f'{name}: packet model must be an object')
        auto_ids = [key for key, spec in DAMAGE_BINDINGS.items()
                    if spec['weapon_id'] == weapon_id and spec['event'] == name]
        if len(auto_ids) > 1:
            raise ValueError(f'{name}: ambiguous source packet binding')
        packet_id = descriptor.get('source_packet_id') or (
            auto_ids[0] if auto_ids and event['effect_type'] in ('damage_trigger', 'damage_packet') else None)
        if packet_id:
            spec = DAMAGE_BINDINGS.get(packet_id)
            if spec is None:
                raise ValueError(f'{name}: unknown source packet id')
            if spec['family'] != binding['family'] or spec['weapon_id'] not in (None, weapon_id):
                raise ValueError(f'{name}: source packet does not match weapon family and identity')
            if spec['event'] != name and event['effect_type'] != 'keyword_trigger':
                raise ValueError(f'{name}: source packet does not match emitted event')
        if not descriptor and not packet_id and event.get('coefficient') is None:
            unresolved.append({'event_id': identifier, 'at': float(at),
                               'reason': f'{name}: packet semantics and magnitude unknown'})
            continue
        source = ('dated_binding_with_explicit_inputs' if packet_id or event.get('coefficient') is not None
                  else 'caller_explicit_packet_assumption')
        periodic = descriptor.get('periodic')
        if periodic is not None:
            if not isinstance(periodic, dict):
                raise ValueError('Periodic schedule must be an object')
            target = hit_targets.get(event.get('source_event_id', '').removeprefix('input-'))
            if periodic.get('refresh_model') == 'replace_per_target' and not target:
                unresolved.append({'event_id': identifier, 'at': float(at),
                                   'reason': f'{name}: target identity missing for periodic replacement'})
                continue
            for index, tick_at in enumerate(_tick_times(at, periodic, encounter_end)):
                next_at = next_replacement.get(identifier)
                if next_at is not None and tick_at >= next_at:
                    continue
                tick_id = f'{identifier}/tick/{index}'
                packet, reason = _packet(descriptor, pools=pools, bases=bases,
                    joint_model=joint_model, event_id=tick_id, at=tick_at,
                    name=name + '_tick', source=source,
                    packet_id=packet_id, event=event,
                    evidence_mode=evidence_mode, weapon_id=weapon_id,
                    references=references)
                if reason:
                    unresolved.append({'event_id': tick_id, 'at': float(tick_at), 'reason': reason})
                else:
                    packet['trigger_event_id'] = identifier
                    known.append(packet)
        else:
            if event['effect_type'] == 'keyword_trigger':
                if descriptor.get('resolved_hits') is None:
                    unresolved.append({'event_id': identifier, 'at': float(at),
                                       'reason': f'{name}: keyword proc needs explicitly resolved hit count before damage'})
                    continue
                instances = _count(descriptor['resolved_hits'], 'resolved hit count')
            else:
                instances = _count(descriptor.get('resolved_hits', 1), 'resolved hit count')
            packet, reason = _packet(descriptor, pools=pools, bases=bases,
                joint_model=joint_model, event_id=identifier, at=at,
                name=name, source=source, packet_id=packet_id, event=event,
                evidence_mode=evidence_mode, weapon_id=weapon_id,
                references=references, instances=instances)
            if reason:
                unresolved.append({'event_id': identifier, 'at': float(at), 'reason': reason})
            else:
                known.append(packet)
    if len(known) + len(unresolved) > MAX_PACKETS:
        raise ValueError('Damage packet limit exceeded')
    known.sort(key=lambda row: (row['at'], row['event_id']))
    unresolved.sort(key=lambda row: (row['at'], row['event_id']))
    subtotal = sum(row['damage'] for row in known)
    duration_number = float(encounter_end) if encounter_end is not None else None
    burst = None
    if model.get('burst_window') is not None:
        window = model['burst_window']
        if not isinstance(window, dict):
            raise ValueError('Burst window must be an object')
        start = _finite(window.get('start_seconds'), 'burst start')
        end = _positive(window.get('end_seconds'), 'burst end')
        if end <= start or encounter_end is not None and end > encounter_end:
            raise ValueError('Burst window must have positive duration within encounter')
        subtotal_burst = sum(row['damage'] for row in known if start <= row['at'] < end)
        unknown_burst = [row for row in unresolved if start <= row['at'] < end]
        timing_gap_in_burst = any(row['at'] < end for row in timing_unresolved)
        burst = {'start_seconds': start, 'end_seconds': end,
                 'known_damage_subtotal': subtotal_burst,
                 'modeled_damage': None if unknown_burst else subtotal_burst,
                 'modeled_damage_per_second': None if unknown_burst or timing_gap_in_burst else subtotal_burst / (end - start),
                 'unresolved_events': len(unknown_burst),
                 'timing_unresolved': timing_gap_in_burst}
    rate_blocked = bool(timing_unresolved)
    complete = not unresolved
    return {'scope': 'explicit-input scenario, not a verified current-game build or DPS',
            'known_damage_subtotal': subtotal,
            'total_damage': subtotal if complete else None,
            'duration_seconds': duration_number,
            'known_damage_per_second': subtotal / duration_number if duration_number and not rate_blocked else None,
            'damage_per_second': (subtotal / duration_number if duration_number and complete and not rate_blocked else None),
            'burst': burst,
            'packets': known,
            'unresolved_damage_events': unresolved,
            'unresolved_timing': timing_unresolved,
            'replayed_direct_hits_suppressed': replayed_hits,
            'assumed_non_damage_events': sorted(set(non_damage)),
            'assumptions': ['Attack/Psi basis and Weapon/Status class were entered or source bound independently.',
                            'Elemental bonuses require an explicit element or applicability tag.',
                            'Each entered hit is a landed hit; fire and reload actions do not create hits.',
                            'Periodic refresh and crit/weakspot combination follow the named input models.',
                            'An explicitly listed non-damage keyword event is a caller assumption.',
                            'State modifiers require per-hit inputs that account for state or remain unresolved.',
                            'All totals exclude enemy mitigation and unentered damage mechanisms.']}
