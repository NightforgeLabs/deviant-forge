"""Explicit, read-only gear-pool and stateful-mod packet sequence model.

Every trigger, target, basis and selected level is caller-supplied. This is a
named additive-pool scheduler model, not a verified current-game DPS formula.
"""
from __future__ import annotations

import json
import math
from copy import deepcopy

import mod_stateful_api
import mod_core_typed
import resonance_suffix
import catalog
import native_direct_hit_graph
from stateful_candidate_adapter_v7_1 import initial_state, execute_candidate

DAMAGE_POOLS = ('weapon', 'status', 'elemental', 'all', 'crit', 'weakspot')
KEYWORD_POOLS = ('power_surge', 'shock', 'unstable_bomber')
SUPPORTED_KEYWORDS = KEYWORD_POOLS + ('burn',)
TIMING_POOLS = ('fire_rate', 'reload')
SUPPORTED_POOLS = DAMAGE_POOLS + KEYWORD_POOLS + TIMING_POOLS
STAT_TO_POOL = {'weapon_damage_percent': 'weapon',
                'status_damage_percent': 'status',
                'elemental_damage_percent': 'elemental',
                'fire_rate_percent': 'fire_rate'}
ELEMENTS = ('none', 'non_elemental', 'shock', 'blaze', 'frost', 'blast')
MAX_EVENTS = 500


def _number(value, label, *, minimum=0, maximum=1_000_000):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{label} must be a finite number')
    if not minimum <= value <= maximum:
        raise ValueError(f'{label} outside supported range')
    return float(value)


def _integer(value, label, *, minimum=0, maximum=1_000_000):
    number = _number(value, label, minimum=minimum, maximum=maximum)
    if not number.is_integer():
        raise ValueError(f'{label} must be a whole number')
    return int(number)


GILDED_BURN_SOURCE = 'https://www.oncehuman.game/news/update/20260121/40780_1282991.html'


def _packet(spec, pools, *, at, event_id, source, outcome_assumptions=None,
            gilded_burn_crit=False):
    if not isinstance(spec, dict):
        raise ValueError('Damage packet must be an object')
    basis = _number(spec.get('basis_value'), 'packet basis value')
    coefficient = _number(spec.get('coefficient_percent'), 'packet coefficient percent')
    damage_class = spec.get('damage_class')
    if damage_class not in ('weapon', 'status'):
        raise ValueError('Explicit Weapon or Status packet class required')
    element = spec.get('element')
    if element not in ELEMENTS:
        raise ValueError('Explicit packet element or none required')
    keyword = spec.get('keyword')
    if keyword is not None and keyword not in SUPPORTED_KEYWORDS:
        raise ValueError('Keyword must be a named supported damage keyword')
    crit, weakspot = spec.get('crit', False), spec.get('weakspot', False)
    if not isinstance(crit, bool) or not isinstance(weakspot, bool):
        raise ValueError('Crit and weakspot outcomes must be explicit booleans')
    if crit or weakspot:
        if damage_class != 'weapon' and not (
                crit and not weakspot and damage_class == 'status' and
                keyword == 'burn' and element == 'blaze' and gilded_burn_crit):
            raise ValueError('Status crit/weakspot eligibility is effect-specific: requires selected Gilded Gauntlets, Burn, Blaze and PvE non-RaidZone')
        if not isinstance(outcome_assumptions, dict) or outcome_assumptions.get('joint_multiplier') not in ('additive', 'multiplicative'):
            raise ValueError('Crit/weakspot outcomes need named additive or multiplicative joint model')
        for name, landed in (('crit', crit), ('weakspot', weakspot)):
            if landed:
                _number(outcome_assumptions.get('base_' + name + '_bonus_percent'),
                        'explicit base ' + name + ' bonus', maximum=1000)
    count = _integer(spec.get('resolved_hits', 1), 'resolved packet hits', maximum=1000)
    applied = {'all': pools['all'], damage_class: pools[damage_class]}
    factor = (1 + pools['all'] / 100) * (1 + pools[damage_class] / 100)
    if element not in ('none', 'non_elemental'):
        factor *= 1 + pools['elemental'] / 100
        applied['elemental'] = pools['elemental']
    if keyword:
        keyword_bonus = pools.get(keyword, 0)
        factor *= 1 + keyword_bonus / 100
        applied[keyword] = keyword_bonus
    if crit or weakspot:
        crit_bonus = ((outcome_assumptions['base_crit_bonus_percent'] + pools['crit'])
                      if crit else 0)
        weak_bonus = ((outcome_assumptions['base_weakspot_bonus_percent'] + pools['weakspot'])
                      if weakspot else 0)
        if outcome_assumptions['joint_multiplier'] == 'additive':
            outcome_factor = (native_direct_hit_graph.joint_factor(
                crit_bonus / 100, weak_bonus / 100, crit=crit, weakspot=weakspot)
                if damage_class == 'weapon' else
                1 + (crit_bonus if crit else 0) / 100 + (weak_bonus if weakspot else 0) / 100)
        else:
            outcome_factor = (1 + crit_bonus / 100 if crit else 1) * (1 + weak_bonus / 100 if weakspot else 1)
        if outcome_factor <= 0:
            raise ValueError('Crit/weakspot outcome factor must remain positive')
        factor *= outcome_factor
        if crit:
            applied['crit'] = pools['crit']
        if weakspot:
            applied['weakspot'] = pools['weakspot']
    damage = basis * coefficient / 100 * count * factor
    return {'event_id': event_id, 'at': at, 'damage': damage,
            'basis_value': basis, 'coefficient_percent': coefficient,
            'resolved_hits': count, 'damage_class': damage_class,
            'element': element, 'keyword': keyword, 'crit': crit, 'weakspot': weakspot,
            'applied_pools_percent': applied,
            'source_status': source,
            **({'crit_eligibility_source': GILDED_BURN_SOURCE}
               if crit and damage_class == 'status' else {})}


def evaluate(request, *, static_pools, static_sources=None):
    if not isinstance(request, dict) or not isinstance(static_pools, dict):
        raise ValueError('Integrated event request and selected pools must be objects')
    assumptions = request.get('model_assumptions') or {}
    if assumptions != {'scheduler': 'next_shot_interval',
                       'fire_rate_conversion': 'rpm_times_one_plus_bonus',
                       'pool_grouping': 'additive_within_named_pool_multiplicative_across_pools',
                       'event_order': 'as_list'}:
        raise ValueError('Enter all four named scheduler, fire-rate, pool and event-order assumptions')
    pools = {name: _number(static_pools.get(name, 0) if name in ('crit', 'weakspot') else static_pools[name], f'{name} static pool', minimum=-99, maximum=1000)
             for name in SUPPORTED_POOLS}
    selected_armor = request.get('selected_armor_ids') or []
    if not isinstance(selected_armor, list) or any(
            not isinstance(identity, str) or
            (catalog.ENTRIES.get(identity) or {}).get('kind') != 'armor'
            for identity in selected_armor) or len(set(selected_armor)) != len(selected_armor):
        raise ValueError('Selected armor IDs must be distinct catalog armor identities')
    gilded_burn_crit = ('armor:gilded-gauntlets' in selected_armor and
                        request.get('encounter_mode') == 'pve_non_raidzone')
    resonance_choices = request.get('resonance_suffixes') or []
    if not isinstance(resonance_choices, list) or len(resonance_choices) > 6:
        raise ValueError('At most six selected Resonance suffixes may be modeled')
    if resonance_choices and request.get('resonance_assumptions') != resonance_suffix.MODEL_ASSUMPTIONS:
        raise ValueError('Resonance needs named outcome, activation, expiry and cap assumptions')
    resonance = []
    for choice in resonance_choices:
        if not isinstance(choice, dict) or any(node['catalog_id'] == choice.get('catalog_id') for node in resonance):
            raise ValueError('Resonance selections must be distinct catalog identities')
        resonance.extend(resonance_suffix.bindings(choice))
    rpm = _number(request.get('base_rpm'), 'base RPM', minimum=.000001)
    duration = _number(request.get('duration_seconds'), 'duration', minimum=.000001)
    capacity = _integer(request.get('magazine_capacity'), 'magazine capacity', minimum=1, maximum=1000)
    magazine = _integer(request.get('starting_magazine_bullets'), 'starting magazine bullets', maximum=capacity)
    reserve = _integer(request.get('starting_reserve_bullets'), 'starting reserve bullets')
    direct = request.get('direct_packet')
    if not isinstance(direct, dict):
        raise ValueError('Enter an explicit direct packet')
    mods = request.get('candidate_mods') or []
    events = request.get('events')
    if not isinstance(mods, list) or len(mods) > 6 or not isinstance(events, list) or not 1 <= len(events) <= MAX_EVENTS:
        raise ValueError('Supply at most six candidate mods and 1–500 ordered events')
    active = []
    exact_timed = []
    exact_gaps = []
    if request.get('exact_timed_mods') and request.get('exact_timed_assumptions') != {
            'activation': 'event_completion', 'expiry': 'half_open',
            'overlap': 'reject_unresolved'}:
        raise ValueError('Exact timed effects need named event completion, half-open expiry and unresolved-overlap assumptions')
    for choice in request.get('exact_timed_mods') or []:
        if not isinstance(choice, dict):
            raise ValueError('Exact timed mod choice must be an object')
        identity = choice.get('catalog_id')
        level = _integer(choice.get('level'), 'exact timed mod level', minimum=1, maximum=17)
        binding = mod_core_typed.EXACT.get((identity, level))
        if not binding or binding['rule']['operator'] not in (
                'previous_magazine_event_counter', 'event_timed_modifier'):
            raise ValueError('Selected exact observation has no supported timed stat operator')
        if binding['variant_kind'] not in ('ordinary', 'shiny') or (
                binding['variant_kind'] == 'shiny') != (choice.get('shiny') is True):
            raise ValueError('Exact timed mod ordinary/Shiny variant mismatch')
        if any(node['catalog_id'] == identity for node in exact_timed):
            raise ValueError('Duplicate exact timed mod identity')
        if len(exact_timed) >= 6:
            raise ValueError('At most six exact timed mods supported')
        if binding['evidence_class'] == 'official_preview_card' and choice.get('allow_preview') is not True:
            raise ValueError('Official preview timed effect needs explicit preview opt-in')
        exact_timed.append({'catalog_id': identity, 'level': level,
                            'shiny': choice.get('shiny') is True,
                            'binding': binding, 'allow_preview': choice.get('allow_preview') is True,
                            'windows': []})
    seen_mods = set()
    seen_trees = set()
    for choice in mods:
        if not isinstance(choice, dict):
            raise ValueError('Candidate mod choice must be an object')
        identity = choice.get('catalog_id')
        binding = mod_stateful_api.BINDINGS.get(identity)
        if binding is None or identity in seen_mods:
            raise ValueError('Choose unique supported stateful candidate mod identities')
        if binding['tree'] in seen_trees:
            raise ValueError('Duplicate candidate effect family cannot be stacked without a sourced rule')
        seen_mods.add(identity)
        seen_trees.add(binding['tree'])
        level = _integer(choice.get('level'), 'candidate mod level', minimum=1, maximum=17)
        if choice.get('allow_candidate') is not True:
            raise ValueError('Level-unbound community mod requires allow_candidate=true')
        rule_assumptions = choice.get('assumptions') or {}
        if not isinstance(rule_assumptions, dict):
            raise ValueError('Candidate semantic assumptions must be an object')
        op = binding['operator']
        if op == 'inactivity_timed_modifier':
            initial = {'start_time_seconds': request.get('start_time_seconds')}
        elif op == 'magazine_phase_modifier':
            if magazine != capacity:
                raise ValueError('Momentum Up requires an explicitly full starting magazine')
            initial = {'full_magazine': True, 'magazine_capacity': capacity, 'magazine_id': 'initial'}
        else:
            initial = {'magazine_capacity': capacity, 'magazine_bullets': magazine,
                       'reserve_bullets': reserve}
        active.append({'binding': binding, 'state': initial_state(binding, **initial),
                       'assumptions': rule_assumptions, 'selected_level': level})
    packets, state_trace, seen_events = [], [], {}
    cursor = 0.0
    next_shot_at = 0.0
    blocked_until = 0.0
    shot_times = []
    replayed = 0
    def step(node, event):
        result = execute_candidate(node['binding'], node['state'], event,
                                   allow_candidate=True, assumptions=node['assumptions'])
        node['state'] = result['state']
        return result['outputs'], result['unresolved']
    def state_at(now, kind='tick', event_id=None):
        deltas = {}
        unresolved = []
        for node in active:
            if node['binding']['operator'] != 'inactivity_timed_modifier':
                continue
            event = {'type': kind, 'time_seconds': now}
            if event_id is not None:
                event['event_id'] = event_id
            outputs, gaps = step(node, event)
            unresolved.extend(gaps)
            for output in outputs:
                pool = STAT_TO_POOL.get(output.get('stat'))
                if pool:
                    deltas[pool] = deltas.get(pool, 0) + output['percentage_points']
        return deltas, unresolved
    def momentum_phase():
        deltas = {}
        for node in active:
            if node['binding']['operator'] == 'magazine_phase_modifier':
                outputs, _ = step(node, {'type': 'inspect'})
                for output in outputs:
                    pool = STAT_TO_POOL.get(output.get('stat'))
                    if pool:
                        deltas[pool] = deltas.get(pool, 0) + output['percentage_points']
        return deltas
    def reaper_sync(event_id):
        for node in active:
            if node['binding']['operator'] == 'counter_ammo_refill':
                step(node, {'type': 'ammo_state_update', 'event_id': event_id,
                            'magazine_bullets': magazine, 'reserve_bullets': reserve})
    def exact_pools(now):
        deltas = {}
        for node in exact_timed:
            for window in node['windows']:
                if window['start'] <= now < window['end']:
                    deltas[window['pool']] = deltas.get(window['pool'], 0) + window['percentage_points']
        return deltas
    def packet_pools(now, base_pools):
        effective = dict(base_pools)
        for pool, value in resonance_suffix.active_pools(resonance, now).items():
            effective[pool] += value
        return effective
    def activate_exact(kind, event, start):
        activations = []
        for node in exact_timed:
            rule = node['binding']['rule']
            if (rule.get('apply_event') or rule.get('event')) != kind:
                continue
            if not isinstance(event.get('core_context') or {}, dict):
                raise ValueError('Exact timed effect event context must be an object')
            context = dict(event.get('core_context') or {})
            context['core_preview_opt_in'] = node['allow_preview']
            if rule['operator'] == 'previous_magazine_event_counter':
                context['just_reloaded'] = True
            elif rule['operator'] == 'event_timed_modifier':
                if rule.get('max_distance_meters') is not None:
                    distance = _number(context.get('target_distance_meters'), 'kill target distance')
                    if distance > rule['max_distance_meters']:
                        continue
                context['event_buff_active'] = True
            answer = mod_core_typed.evaluate(node['catalog_id'], node['level'],
                                             shiny=node['shiny'], context=context)
            if answer['status'] != 'observed_typed_output':
                raise ValueError('Exact timed effect unresolved: ' + '; '.join(answer['missing']))
            if any(window['start'] <= start < window['end'] for window in node['windows']):
                raise ValueError('Exact timed effect retrigger overlaps an active window; replacement or stacking rule unresolved')
            for output in answer['outputs']:
                pool = STAT_TO_POOL.get(output.get('stat'))
                if output.get('type') != 'stat_pool_delta' or pool not in DAMAGE_POOLS:
                    exact_gaps.append(f"{node['catalog_id']}: {output.get('stat') or output.get('type')} is outside supported packet damage pools")
                    continue
                duration_seconds = _number(output.get('duration_seconds'), 'timed effect duration', minimum=.000001)
                window = {'catalog_id': node['catalog_id'], 'pool': pool,
                          'percentage_points': _number(output['percentage_points'], 'timed effect bonus'),
                          'start': start, 'end': start + duration_seconds,
                          'source_warning': answer.get('source_warning'),
                          'evidence_class': answer.get('evidence_class')}
                node['windows'].append(window)
                activations.append(window)
        return activations
    wind_reload_links = {}
    wind_loaded_links = set()
    for index, event in enumerate(events):
        if not isinstance(event, dict) or event.get('kind') not in ('shot', 'wait', 'damage_taken', 'kill_enemy', 'reload', 'triggered_packet', 'ammo_load'):
            raise ValueError(f'Event {index} has unsupported kind')
        kind = event['kind']
        identity = event.get('event_id')
        if kind != 'wait' and (not isinstance(identity, str) or not identity):
            raise ValueError('Mutating event needs a stable event_id')
        fingerprint = json.dumps(event, sort_keys=True)
        if identity in seen_events:
            if seen_events[identity] != fingerprint:
                raise ValueError('Event ID reused with changed payload')
            replayed += 1
            continue
        if identity:
            seen_events[identity] = fingerprint
        entered_at = event.get('at')
        if kind == 'shot':
            if entered_at is not None:
                minimum_at = _number(entered_at, 'shot earliest time')
                if minimum_at < cursor - 1e-9:
                    raise ValueError('Shot earliest time is before previous event')
            else:
                minimum_at = cursor
            now = max(minimum_at, cursor, next_shot_at, blocked_until)
        else:
            now = _number(entered_at, f'{kind} time')
            if now < cursor - 1e-9:
                raise ValueError('Events must be ordered by time')
        if now >= duration + 1e-9:
            raise ValueError('Event occurs after scenario duration')
        cursor = now
        gaps = []
        outputs = []
        if kind == 'shot':
            if magazine < 1:
                raise ValueError('No magazine bullet for scheduled shot; enter a reload or sourced refill')
            covered, gaps = state_at(now)
            momentum = momentum_phase()
            dynamic = {pool: covered.get(pool, 0) + momentum.get(pool, 0)
                       for pool in SUPPORTED_POOLS}
            effective = {pool: pools[pool] + dynamic[pool] for pool in SUPPORTED_POOLS}
            for pool, value in exact_pools(now).items():
                effective[pool] += value
            for pool in effective:
                if not -99 < effective[pool] <= 1000:
                    raise ValueError(f'{pool} effective pool is outside supported range')
            effective = packet_pools(now, effective)
            outcome = event.get('packet_outcome') or {}
            if not isinstance(outcome, dict) or set(outcome) - {'crit', 'weakspot', 'element'}:
                raise ValueError('Shot outcome may specify only crit, weakspot and element')
            shot_spec = {**direct, **outcome}
            packet = _packet(shot_spec, effective, at=now, event_id=identity,
                             source='caller_direct_packet_plus_opted_candidate_state',
                             outcome_assumptions=request.get('outcome_assumptions'),
                             gilded_burn_crit=gilded_burn_crit)
            packets.append(packet)
            outputs.extend({'type': 'resonance_stack_activation', **row}
                           for row in resonance_suffix.complete_packet(resonance, packet, now))
            shot_times.append(now)
            magazine -= 1
            reaper_sync('sync-shot-' + identity)
            for node in active:
                if node['binding']['operator'] == 'magazine_phase_modifier':
                    step(node, {'type': 'consume', 'event_id': 'consume-' + identity,
                                'bullets': 1})
            next_momentum = momentum_phase()
            fire_rate = pools['fire_rate'] + next_momentum.get('fire_rate', 0)
            if fire_rate <= -100:
                raise ValueError('Fire rate makes next-shot interval undefined')
            next_shot_at = now + 60 / (rpm * (1 + fire_rate / 100))
        elif kind == 'triggered_packet':
            covered, gaps = state_at(now)
            momentum = momentum_phase()
            effective = {pool: pools[pool] + covered.get(pool, 0) + momentum.get(pool, 0)
                         for pool in SUPPORTED_POOLS}
            for pool, value in exact_pools(now).items():
                effective[pool] += value
            effective = packet_pools(now, effective)
            packet = _packet(event.get('packet'), effective, at=now,
                             event_id=identity, source='caller_explicit_triggered_packet',
                             outcome_assumptions=request.get('outcome_assumptions'),
                             gilded_burn_crit=gilded_burn_crit)
            packets.append(packet)
            outputs.extend({'type': 'resonance_stack_activation', **row}
                           for row in resonance_suffix.complete_packet(resonance, packet, now))
        elif kind == 'ammo_load':
            if event.get('source_effect') != 'wind_intepreter_cap':
                raise ValueError('Ammo load needs a supported source effect')
            linked = event.get('linked_reload_event_id')
            if linked not in wind_reload_links or abs(now - wind_reload_links[linked]) > 1e-9:
                raise ValueError('Wind bullet load must follow its linked blast reload transaction at the same time')
            if linked in wind_loaded_links:
                raise ValueError('One Wind bullet load per linked Unstable Bomber explosion')
            wind_loaded_links.add(linked)
            if event.get('rounds') != 1 or isinstance(event.get('rounds'), bool):
                raise ValueError('Wind Intepreter source grants exactly one bullet per explosion')
            model = event.get('source_model')
            if model not in ('created_after_reload', 'reserve_transfer_after_reload',
                             'not_retained_during_reload'):
                raise ValueError('Choose a named Wind bullet source and reload retention scenario')
            available = capacity - magazine
            if model == 'created_after_reload':
                applied = min(1, available)
            elif model == 'reserve_transfer_after_reload':
                applied = min(1, available, reserve)
                reserve -= applied
            else:
                applied = 0
            magazine += applied
            outputs.append({'type': 'wind_unstable_bomber_bullet_load',
                            'rounds_requested': 1, 'rounds_loaded': applied,
                            'rounds_not_retained': 1 - applied,
                            'source_model': model, 'destination': 'current_magazine',
                            'magazine_after': magazine, 'reserve_after': reserve,
                            'source_status': 'official_release_effect_with_explicit_order_and_source_hypothesis'})
        elif kind == 'damage_taken':
            deltas, gaps = state_at(now, 'damage_taken', identity)
            outputs = [{'type': 'active_stat_delta', 'pool': pool,
                        'percentage_points': value} for pool, value in deltas.items()]
        elif kind == 'wait':
            deltas, gaps = state_at(now)
            outputs = [{'type': 'active_stat_delta', 'pool': pool,
                        'percentage_points': value} for pool, value in deltas.items()]
        elif kind == 'kill_enemy':
            explicit_refill = _integer(event.get('ammo_transfer_rounds', 0),
                                       'explicit kill ammo transfer', maximum=capacity)
            if explicit_refill:
                if any(node['binding']['operator'] == 'counter_ammo_refill' for node in active):
                    raise ValueError('Explicit kill refill cannot combine with another candidate kill refill')
                cap = _integer(event.get('ammo_transfer_cap_rounds'),
                               'explicit kill refill cap', minimum=1, maximum=capacity)
                if explicit_refill > cap or explicit_refill > reserve or magazine + explicit_refill > capacity:
                    raise ValueError('Kill refill must fit its cap, finite reserve and magazine')
                magazine += explicit_refill
                reserve -= explicit_refill
                outputs.append({'type': 'finite_ammo_transfer_from_reserve',
                                'rounds': explicit_refill,
                                'magazine_after': magazine, 'reserve_after': reserve})
            for node in active:
                if node['binding']['operator'] == 'counter_ammo_refill':
                    found, issues = step(node, {'type': 'kill_enemy', 'event_id': identity})
                    outputs.extend(found)
                    gaps.extend(issues)
                    magazine = node['state']['magazine']
                    reserve = node['state']['reserve']
            outputs.extend({'type': 'exact_timed_activation', **row}
                           for row in activate_exact(kind, event, now))
        elif kind == 'reload':
            if now < blocked_until - 1e-9:
                raise ValueError('Reload starts before previous reload completes')
            loaded = _integer(event.get('loaded_rounds'), 'loaded rounds', maximum=capacity)
            consume_for_blast = event.get('consume_remaining_magazine_for_blast', False)
            if not isinstance(consume_for_blast, bool):
                raise ValueError('consume_remaining_magazine_for_blast must be true or false')
            consumed_for_blast = magazine if consume_for_blast else 0
            retained = 0 if consume_for_blast else magazine
            if loaded > reserve or retained + loaded > capacity:
                raise ValueError('Reload must use finite reserve and fit magazine')
            base_seconds = _number(event.get('base_reload_seconds'), 'base reload seconds')
            final_seconds = base_seconds / (1 + pools['reload'] / 100)
            magazine = retained + loaded
            reserve -= loaded
            blocked_until = now + final_seconds
            next_shot_at = max(next_shot_at, blocked_until)
            reaper_sync('sync-reload-' + identity)
            for node in active:
                if node['binding']['operator'] == 'magazine_phase_modifier':
                    found, issues = step(node, {'type': 'reload', 'event_id': identity,
                                                'magazine_id': identity,
                                                'magazine_capacity': capacity,
                                                'full_magazine': magazine == capacity})
                    outputs.extend(found)
                    gaps.extend(issues)
            outputs.append({'type': 'reload_completed_at', 'seconds': blocked_until,
                            'model': 'base_seconds/(1+reload_efficiency_percent/100)'})
            outputs.extend({'type': 'exact_timed_activation', **row}
                           for row in activate_exact(kind, event, blocked_until))
            if consume_for_blast:
                if consumed_for_blast > 0:
                    wind_reload_links[identity] = now
                outputs.append({'type': 'magazine_rounds_consumed_by_reload_effect',
                                'rounds': consumed_for_blast})
        state_trace.append({'event_id': identity, 'kind': kind, 'at': now,
                            'candidate_outputs': outputs, 'unresolved': gaps,
                            **({'consumed_magazine_rounds': consumed_for_blast}
                               if kind == 'reload' else {}),
                            'magazine_after': magazine, 'reserve_after': reserve})
    total = sum(packet['damage'] for packet in packets)
    return {'scope': 'Explicit-input conditional scheduler and additive named-pool model; not current-game certified DPS',
            'total_damage': total, 'conditional_damage_per_second': total / duration,
            'duration_seconds': duration, 'packets': packets, 'shot_times': shot_times,
            'event_trace': state_trace, 'final_ammo': {'magazine': magazine, 'reserve': reserve},
            'replayed_events_suppressed': replayed,
            'static_pools_percent': pools, 'static_sources': static_sources or [],
            'candidate_sources': [{'catalog_id': node['binding']['catalog_id'],
                                   'selected_level': node['selected_level'],
                                   'source_text_sha256': node['binding']['candidate_text_sha256'],
                                   'evidence_mode': 'community_level_unbound_candidate'}
                                  for node in active],
            'exact_timed_sources': [{'catalog_id': node['catalog_id'],
                                     'level': node['level'], 'shiny': node['shiny'],
                                     'evidence_class': node['binding']['evidence_class'],
                                     'source_url': node['binding'].get('source_url'),
                                     'source_text_sha256': node['binding'].get('source_text_sha256'),
                                     'windows': node['windows']} for node in exact_timed],
            'resonance_sources': [{'catalog_id': node['catalog_id'], 'level': node['level'],
                                   'bonus_position': node['bonus_position'],
                                   'trigger': node['trigger'], 'pool': node['pool'],
                                   'trigger_instances': node['trigger_instances'],
                                   'per_stack_percent': node['per_stack_percent'],
                                   'max_stacks': node['max_stacks'],
                                   'duration_seconds': node['duration_seconds'],
                                   'source': node['source'], 'source_status': node['source_status']}
                                  for node in resonance],
            'current_level_certified': False if active or exact_timed or resonance else None,
            'game_winner_established': False,
            'unresolved': (['Current-game bucket grouping and all unmodeled weapon/target effects remain unverified.']
                           + exact_gaps
                           + (['Resonance uses a published ordinary-layout candidate and explicit packet outcomes; per-instance expiry, overflow and damage buckets are scenario assumptions, not current-game certified.'] if resonance else [])
                           + [f"{node['catalog_id']}: {node['binding']['evidence_class']} is an opt-in source scenario, not a current-game effect certification."
                              for node in exact_timed])}
