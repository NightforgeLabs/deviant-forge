"""Connect published reference timing to the sourced, finite-ammo event scheduler.

The reference supplies only direct-hit damage and a firing cycle. Target,
outcome rolls, status packets, reserve ammo and early reloads remain explicit
scenario inputs. No proc event is inferred from a published weapon name alone.
"""
from __future__ import annotations

import math

import integrated_event_model
import resonance_suffix
import packet_family_timed_adapter
import published_packet_recipe
import sourced_proc_timed_adapter
import weapon_packet_timeline_api
import weapon_timeline_api

MAX_EVENTS = integrated_event_model.MAX_EVENTS
ASSUMPTIONS = {'scheduler': 'next_shot_interval',
               'fire_rate_conversion': 'rpm_times_one_plus_bonus',
               'pool_grouping': 'additive_within_named_pool_multiplicative_across_pools',
               'event_order': 'as_list'}


def _status_duration_model(answer, model, rules):
    """Track target status expiry; never change damage or periodic packet times."""
    if not rules:
        return [], []
    if not isinstance(rules, list):
        raise ValueError('Status duration rules must be exact typed outputs')
    if model is None:
        return [], ['Power Surge status base lifetime and refresh order need an explicit named model']
    if not isinstance(model, dict):
        raise ValueError('Power Surge status model must be an object')
    base = model.get('base_duration_seconds')
    if isinstance(base, bool) or not isinstance(base, (int, float)) or not math.isfinite(base) or base <= 0:
        raise ValueError('Power Surge base status duration must be positive seconds')
    if model.get('refresh_model') != 'replace_per_target' or model.get('event_order') != 'after_landing_hit':
        raise ValueError('Power Surge status needs explicit replace-per-target and after-landing-hit assumptions')
    actions = {row.get('input_id'): row for row in answer.get('source_actions') or []
               if row.get('kind') == 'hit'}
    transforms = []
    unresolved = []
    for rule in rules:
        if rule.get('keyword') != 'power_surge':
            raise ValueError('Unsupported status duration keyword')
        delta = rule.get('percentage_points')
        if isinstance(delta, bool) or not isinstance(delta, (int, float)) or not math.isfinite(delta) or delta <= -100:
            raise ValueError('Power Surge duration change must be a finite percentage above -100')
        effective = base * (1 + delta / 100)
        windows = []
        activations = [row for row in answer.get('source_events') or []
                       if row.get('event') == 'power_surge' and
                       row.get('keyword') == 'power_surge' and
                       row.get('effect_type') == 'keyword_trigger']
        for event in sorted(activations, key=lambda row: (float(row['at']), row['event_id'])):
            source_id = str(event.get('source_event_id') or '').removeprefix('input-')
            hit = actions.get(source_id)
            target = hit.get('target') if hit else None
            if not target:
                unresolved.append(f"{event['event_id']}: Power Surge status target is unknown")
                continue
            at = float(event['at'])
            for prior in windows:
                if prior['target'] == target and prior['end_seconds'] > at:
                    prior['end_seconds'] = at
                    prior['refreshed_by'] = event['event_id']
            windows.append({'event_id': event['event_id'], 'target': target,
                            'start_seconds': at, 'end_seconds': at + effective})
        for hit in actions.values():
            observed = (hit.get('conditions') or {}).get('target_affected_by_power_surge')
            if observed is None:
                unresolved.append(f"{hit['input_id']}: downstream Power Surge status eligibility not entered")
                continue
            at = float(hit['at'])
            active = any(row['target'] == hit.get('target') and
                         row['start_seconds'] < at < row['end_seconds'] for row in windows)
            if observed is not active:
                unresolved.append(f"{hit['input_id']}: entered Power Surge condition conflicts with modeled status expiry")
        transforms.append({'catalog_id': rule.get('catalog_id'), 'keyword': 'power_surge',
                           'base_duration_seconds': base, 'duration_delta_percent': delta,
                           'effective_duration_seconds': effective,
                           'status_windows': windows, 'damage_packet_count_changed': False,
                           'source': rule.get('evidence_class'),
                           'status_model_source': 'caller_explicit_lifetime_and_refresh_assumptions'})
    return transforms, unresolved


def evaluate_direct_resonance(build, *, timing, pools, duration, outcomes,
                              outcome_assumptions):
    """Run guided direct outcomes through the same finite-ammo event scheduler."""
    choices = resonance_suffix.selected_choices(build)
    if not choices:
        raise ValueError('No selected ordinary Resonance suffix has an unlocked rule')
    baseline, scaled = build['weapon_source_native_baseline'], build['weapon_scaled_reference']
    if baseline is None or scaled is None:
        raise ValueError('Source-native weapon damage is required for guided Resonance')
    damage = scaled['stats'].get('damage_per_projectile')
    projectiles = baseline['stats'].get('projectiles_per_shot')
    if damage is None or projectiles is None:
        raise ValueError('Source-native damage and explicit projectile count are required')
    if timing.get('seconds_per_shot') is None or timing.get('magazine') is None:
        raise ValueError('Source RPM and magazine capacity are required')
    reserve = _integer(outcomes.get('reserve_bullets'), 'Resonance starting reserve bullets')
    if reserve and (timing.get('reload_seconds') is None or
                    baseline['stats'].get('reload_time_seconds') is None):
        raise ValueError('Reserve-backed Resonance schedule needs sourced or explicitly entered reload seconds')
    events, shot_ids = _events(timing, duration, reserve, None, False,
                               baseline['stats'].get('reload_time_seconds'))
    if not shot_ids:
        raise ValueError('Resonance schedule has no shots')
    resonance_suffix.guided_shot_outcomes(events, outcomes)
    static = {pool: float(pools.get(pool, 0)) for pool in integrated_event_model.SUPPORTED_POOLS}
    static['reload'] = float(pools.get('reload_efficiency', 0))
    scenario = {'model_assumptions': ASSUMPTIONS.copy(),
                'resonance_assumptions': resonance_suffix.MODEL_ASSUMPTIONS.copy(),
                'resonance_suffixes': choices,
                'outcome_assumptions': outcome_assumptions,
                'base_rpm': float(baseline['stats']['fire_rate']),
                'duration_seconds': duration, 'magazine_capacity': timing['magazine'],
                'starting_magazine_bullets': timing['magazine'],
                'starting_reserve_bullets': reserve,
                'direct_packet': {'basis_value': damage * projectiles,
                                  'coefficient_percent': 100,
                                  'damage_class': 'weapon', 'element': 'none'},
                'events': events}
    return integrated_event_model.evaluate(scenario, static_pools=static,
                                           static_sources=[baseline['source_url']])


def _integer(value, name, *, minimum=0, maximum=1_000_000):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f'{name} must be a whole number from {minimum} to {maximum}')
    return value


def _events(timing, duration, reserve, early_reload_after, has_reload_blast,
            base_reload_seconds, kill_shot_indices=(), kill_refill_rule=None,
            wind_ammo_scenario=None):
    capacity = timing['magazine']
    interval = timing['seconds_per_shot']
    reload_seconds = timing['reload_seconds']
    at, magazine, shots_in_magazine, events, shot_ids = 0.0, capacity, 0, [], []
    remaining = reserve
    reload_index = 0
    while at < duration - 1e-12:
        if len(events) >= MAX_EVENTS:
            raise ValueError('Sourced published timeline exceeds 500 events; shorten the encounter')
        early = early_reload_after is not None and shots_in_magazine >= early_reload_after
        if magazine == 0 or early:
            if remaining == 0 and not (has_reload_blast and magazine > 0):
                break
            consumed_for_blast = magazine if has_reload_blast else 0
            retained = 0 if has_reload_blast else magazine
            loaded = min(capacity - retained, remaining)
            if loaded == 0 and not (has_reload_blast and magazine > 0):
                break
            event = {'kind': 'reload', 'event_id': f'published-reload-{reload_index}',
                     'at': at, 'loaded_rounds': loaded,
                     'base_reload_seconds': base_reload_seconds}
            if has_reload_blast:
                event.update(consume_remaining_magazine_for_blast=True,
                             refund_outcome='none')
            events.append(event)
            magazine = retained + loaded
            remaining -= loaded
            if wind_ammo_scenario is not None and has_reload_blast and consumed_for_blast > 0:
                # One source explosion per reload, regardless of resolved target count.
                # The option states whether its bullet survives this transaction
                # and whether it is created or transferred from finite reserve.
                if wind_ammo_scenario == 'created_after_reload':
                    granted = min(1, capacity - magazine)
                elif wind_ammo_scenario == 'reserve_transfer_after_reload':
                    granted = min(1, capacity - magazine, remaining)
                    remaining -= granted
                else:
                    granted = 0
                events.append({'kind': 'ammo_load',
                               'event_id': f'wind-load-{reload_index}',
                               'at': at, 'rounds': 1,
                               'source_effect': 'wind_intepreter_cap',
                               'linked_reload_event_id': event['event_id'],
                               'source_model': wind_ammo_scenario})
                magazine += granted
            reload_index += 1
            shots_in_magazine = 0
            at += reload_seconds
            if magazine == 0:
                break
            continue
        shot_index = len(shot_ids)
        shot_id = f'published-shot-{shot_index}'
        shot_at = at
        events.append({'kind': 'shot', 'event_id': shot_id, 'at': shot_at})
        shot_ids.append(shot_id)
        magazine -= 1
        shots_in_magazine += 1
        if shot_index in kill_shot_indices:
            cap = math.floor(capacity * kill_refill_rule['per_trigger_capacity_fraction'])
            transfer = min(kill_refill_rule['refill_bullets'], cap,
                           capacity - magazine, remaining)
            events.append({'kind': 'kill_enemy', 'event_id': f'published-kill-{shot_index}',
                           'at': shot_at, 'ammo_transfer_rounds': transfer,
                           'ammo_transfer_cap_rounds': cap,
                           'core_context': {'source': 'selected_community_core_text'}})
            magazine += transfer
            remaining -= transfer
        at += interval
    return events, shot_ids


def evaluate(build, *, timing, pools, duration, options, encounter_mode='unknown'):
    """Return the connected source scheduler result or an explicit input error."""
    if not isinstance(options, dict):
        raise ValueError('Sourced timeline controls must be an object')
    weapon_id = build['weapon_id']
    binding = weapon_timeline_api.WEAPONS.get(weapon_id)
    packet_binding = weapon_packet_timeline_api.BINDINGS.get(weapon_id)
    if binding is None and packet_binding is None:
        raise ValueError('Selected reference weapon has no supported sourced event timeline')
    if any(timing.get(key) is None for key in ('magazine', 'seconds_per_shot', 'reload_seconds')):
        raise ValueError('Published RPM, magazine and reload seconds are required for sourced timing')
    reserve = _integer(options.get('reserve_bullets'), 'Starting reserve bullets')
    target = options.get('target_id')
    if not isinstance(target, str) or not target.strip():
        raise ValueError('Enter a target identity for every sourced hit')
    early = options.get('reload_after_shots')
    if early is not None:
        early = _integer(early, 'Early reload after shots', minimum=1,
                         maximum=timing['magazine'] - 1)
    has_blast = bool(binding and any(rule['kind'] == 'reload_blast' for rule in binding['rules']))
    wind_selected = any(row.get('catalog_id') == 'armor:wind-intepreter-cap'
                        for row in build.get('armor_profiles') or [])
    wind_ammo_scenario = options.get('wind_ammo_scenario')
    if wind_ammo_scenario is not None:
        if wind_ammo_scenario not in ('created_after_reload',
                                     'reserve_transfer_after_reload',
                                     'not_retained_during_reload'):
            raise ValueError('Choose a named Wind bullet source and reload retention scenario')
        if not wind_selected or encounter_mode != 'pve_non_raidzone' or not has_blast:
            raise ValueError('Wind ammo scenario requires selected cap, PvE non-RaidZone and sourced reload blast')
    if has_blast and early is None:
        raise ValueError('Reload blast needs an explicit early reload shot count')
    if not has_blast and early is not None:
        raise ValueError('Early reload is supported here only for a sourced reload-blast weapon')
    baseline = build['weapon_source_native_baseline']
    base_reload_seconds = baseline['stats'].get('reload_time_seconds') if baseline else None
    if base_reload_seconds is None:
        raise ValueError('Published base reload seconds are required')
    kill_rule = options.get('core_kill_refill_rule')
    kill_indices = options.get('core_kill_shot_indices')
    if kill_rule is not None:
        if not isinstance(kill_rule, dict) or kill_rule.get('kind') != 'kill_refill_and_damage_until_reload' or \
                kill_rule.get('refill_bullets') != 2 or kill_rule.get('per_trigger_capacity_fraction') != .5:
            raise ValueError('Selected community kill-refill rule is invalid')
        if not isinstance(kill_indices, list) or any(isinstance(index, bool) or not isinstance(index, int) or index < 0 for index in kill_indices) or len(set(kill_indices)) != len(kill_indices):
            raise ValueError('Enter unique zero-based kill shot indices')
    elif kill_indices is not None:
        raise ValueError('Kill shot indices need a selected source-backed core rule')
    events, shot_ids = _events(timing, duration, reserve, early, has_blast,
                               base_reload_seconds, set(kill_indices or ()), kill_rule,
                               wind_ammo_scenario)
    if kill_indices and max(kill_indices) >= len(shot_ids):
        raise ValueError('Kill shot index exceeds the modeled shot schedule')
    if not shot_ids:
        raise ValueError('Sourced timeline has no scheduled shots')
    resonance_choices = (resonance_suffix.selected_choices(build)
                         if options.get('resonance_outcomes') is not None else [])
    if resonance_choices:
        resonance_outcomes = options.get('resonance_outcomes')
        if not isinstance(resonance_outcomes, dict):
            raise ValueError('Selected Resonance needs explicit per-shot outcome lists')
        if resonance_outcomes.get('reserve_bullets') not in (None, reserve):
            raise ValueError('Resonance reserve bullets disagree with the sourced timeline reserve')
        if resonance_outcomes.get('weakspot_shot_indices'):
            raise ValueError('Sourced weapon timeline cannot correlate Weakspot Resonance outcomes with its hit hooks; use the direct-only guided outcome scenario')
        resonance_suffix.guided_shot_outcomes(events, resonance_outcomes)
    outcomes = options.get('hit_outcomes')
    if binding is not None and outcomes is None:
        proc_names = [rule['name'] for rule in binding['rules']
                      if rule['kind'] == 'proc']
        if proc_names:
            if len(proc_names) != 1:
                raise ValueError('Multiple chance rules need explicit per-hit outcomes')
            rolls = options.get('roll_sequence')
            if not isinstance(rolls, list) or len(rolls) != len(shot_ids):
                raise ValueError(f'Enter one explicit {proc_names[0]} roll for each of {len(shot_ids)} shots')
            if any(isinstance(roll, bool) or not isinstance(roll, (int, float))
                   or not math.isfinite(roll) or not 0 <= roll < 1 for roll in rolls):
                raise ValueError('Chance rolls must be finite numbers from 0 to below 1')
            outcomes = [{'rolls': {proc_names[0]: roll}} for roll in rolls]
        else:
            outcomes = [{} for _ in shot_ids]
        requirements = ({rule['requires_condition'] for rule in binding['rules']
                         if rule.get('requires_condition')} |
                        {rule['condition'] for rule in binding['rules']
                         if rule['kind'] == 'conditional_stack'})
        entered_conditions = options.get('condition_sequences') or {}
        if not isinstance(entered_conditions, dict):
            raise ValueError('Condition sequences must be keyed by source condition')
        if requirements - set(entered_conditions):
            raise ValueError('Enter per-hit values for sourced conditions: '
                             + ', '.join(sorted(requirements - set(entered_conditions))))
        for condition, values in entered_conditions.items():
            if condition not in requirements or not isinstance(values, list) or len(values) != len(shot_ids) or any(not isinstance(value, bool) for value in values):
                raise ValueError(f'{condition}: enter one true/false value for every scheduled shot')
            for index, value in enumerate(values):
                outcomes[index].setdefault('conditions', {})[condition] = value
    hit_inputs = []
    if binding is not None:
        if not isinstance(outcomes, list) or len(outcomes) != len(shot_ids):
            raise ValueError(f'Enter one hit outcome for each of {len(shot_ids)} scheduled shots')
        for shot_id, outcome in zip(shot_ids, outcomes, strict=True):
            if not isinstance(outcome, dict):
                raise ValueError('Each hit outcome must be an object')
            if outcome.get('target') not in (None, target):
                raise ValueError('Hit outcome target differs from the named shared target')
            if outcome.get('weakspot') is True:
                raise ValueError('Weakspot-trigger correlation is not supported in this guided timeline')
            hit_inputs.append({'shot_event_id': shot_id, 'target': target,
                               'rolls': outcome.get('rolls') or {},
                               'conditions': outcome.get('conditions') or {},
                               **({'distance': outcome['distance']} if 'distance' in outcome else
                                  {'distance': options['target_distance_meters']}
                                  if 'target_distance_meters' in options else {})})
    source_model = options.get('damage_model') or {}
    if not isinstance(source_model, dict):
        raise ValueError('Sourced damage model must be an object')
    packet_models = source_model.get('packet_models') or {}
    if not isinstance(packet_models, dict):
        raise ValueError('Sourced packet models must be an object')
    selected_armor_ids = [row['catalog_id'] for row in build.get('armor_profiles') or []]
    if ('armor:gilded-gauntlets' in selected_armor_ids and
            encounter_mode == 'pve_non_raidzone'):
        burn = packet_models.get('burn')
        if isinstance(burn, dict) and burn.get('crit') is True and burn.get('crit_eligible') is None:
            # The release grants eligibility, not an observed crit outcome or
            # the later testing-preview +20% crit values.
            source_model = {**source_model, 'packet_models': {
                **packet_models,
                'burn': {**burn, 'crit_eligible': True}}}
    scaled = build['weapon_scaled_reference']
    damage = scaled['stats'].get('damage_per_projectile') if scaled else None
    projectiles = baseline['stats'].get('projectiles_per_shot') if baseline else None
    if damage is None or projectiles is None:
        raise ValueError('Published direct damage and projectile count are required')
    static = {pool: float(pools.get(pool, 0)) for pool in integrated_event_model.SUPPORTED_POOLS}
    static['reload'] = float(pools.get('reload_efficiency', 0))
    scenario = {'model_assumptions': ASSUMPTIONS.copy(),
                'selected_armor_ids': selected_armor_ids,
                'encounter_mode': encounter_mode,
                'outcome_assumptions': options.get('packet_outcome_assumptions'),
                'base_rpm': float(baseline['stats']['fire_rate']),
                'duration_seconds': duration, 'magazine_capacity': timing['magazine'],
                'starting_magazine_bullets': timing['magazine'],
                'starting_reserve_bullets': reserve,
                'direct_packet': {'basis_value': damage * projectiles,
                                  'coefficient_percent': 100,
                                  'damage_class': 'weapon', 'element': 'none',
                                  'basis_kind': 'reference_damage'},
                'events': events,
                'weapon_proc': {'weapon_id': weapon_id,
                                'evidence_mode': options.get('evidence_mode', 'dated_release'),
                                'model_mode': options.get('model_mode', 'explicit_assumptions'),
                                'stream_id': options.get('stream_id', 'published-reference'),
                                'damage_model': source_model}}
    if resonance_choices:
        scenario.update(resonance_suffixes=resonance_choices,
                        resonance_assumptions=resonance_suffix.MODEL_ASSUMPTIONS.copy(),
                        outcome_assumptions=options.get('resonance_outcome_assumptions'))
    if binding is not None:
        scenario['weapon_proc'].update(hit_inputs=hit_inputs,
            weapon_state_order='after_direct_hit_before_triggered_packet')
        adapter = sourced_proc_timed_adapter
    else:
        actions, exclusions, resources = published_packet_recipe.build(
            weapon_id, events, options.get('packet_recipe'), target, duration)
        scenario['weapon_proc'].update(source_actions=actions, ineligible_shots=exclusions,
            packet_hypotheses=options.get('packet_hypotheses') or {}, **resources)
        adapter = packet_family_timed_adapter
    answer = adapter.evaluate(scenario, static_pools=static,
                              static_sources=['published reference', baseline['source_url']])
    duration_transforms, status_duration_unresolved = _status_duration_model(
        answer, options.get('power_surge_status_model'), options.get('status_duration_rules'))
    direct_ids = set(shot_ids)
    direct_packets = [row for row in answer['packets'] if row['event_id'] in direct_ids]
    if len(direct_packets) != len(shot_ids):
        raise ValueError('Sourced scheduler did not retain exactly one direct packet per shot')
    direct_damage = sum(row['damage'] for row in direct_packets)
    extra_damage = answer['known_damage_subtotal'] - direct_damage
    if extra_damage < -1e-8 or not math.isfinite(extra_damage):
        raise ValueError('Sourced packet subtotal is inconsistent with the direct schedule')
    wind_trace = [row for row in answer['event_trace'] if row['kind'] == 'ammo_load'
                  and any(output.get('type') == 'wind_unstable_bomber_bullet_load'
                          for output in row['candidate_outputs'])]
    return {'scheduler': answer, 'wind_ammo_scenario': wind_ammo_scenario,
            'status_duration_transforms': duration_transforms,
            'status_duration_unresolved': status_duration_unresolved,
            'wind_ammo_trace': wind_trace,
            'direct_body_damage': direct_damage,
            'extra_packet_damage': extra_damage,
            'shot_count': len(shot_ids),
            'source_packets': answer['source_packets'],
            'source_unresolved': answer['unresolved_source_packets'],
            'source_uncertainties': [gap for row in answer['source_packets']
                                     for gap in row.get('source_unresolved') or []],
            'events': events,
            'game_winner_established': False}
