"""Named timed direct/crit/proc/set scenario from a published reference build.

This composes only packets whose basis, class, trigger count and timing are
entered or source-bound. Unknown packets remain separate from the known subtotal.
"""
from __future__ import annotations

from collections import Counter
import math

import catalog
import combat_projection
import published_calculator_adapter as calculator
import published_main_core
import published_core_packet_windows
import published_set_thresholds
import published_unique_armor
import published_item_tier
import resonance_suffix
from weapon_mechanics.damage_projection_v3 import load_damage_bindings, project_event


PACKETS = load_damage_bindings()['packets']
SET_RULES = {row['id']: row for row in __import__('json').loads(
    (__import__('pathlib').Path(__file__).parent / 'rules.json').read_text())['rules']
    if row.get('system') == 'set'}
MAX_SHOTS = 10000


def _number(value, label, minimum=0, maximum=1_000_000):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f'{label} must be a finite number from {minimum} to {maximum}')
    return float(value)


def _set_pools(build, mode, hp_fraction, evidence_mode='current_release', condition_inputs=None,
               stack_model=None):
    if stack_model not in (None, 'additive_named_pools'):
        raise ValueError('Choose the named additive set-bonus pool model')
    counts = Counter()
    for piece in build['armor_profiles']:
        entry = catalog.ENTRIES[piece['catalog_id']]
        if entry.get('set_id'):
            counts[entry['set_id']] += 1
    pools = {'weapon': 0.0, 'status': 0.0, 'reload_efficiency': 0.0}
    applied, unresolved = [], []
    extra_pools, extra_applied, extra_covered, extra_gaps = published_set_thresholds.evaluate(
        counts, mode, hp_fraction, evidence_mode, condition_inputs)
    for name, value in extra_pools.items():
        pools[name] = pools.get(name, 0) + value
    applied.extend(extra_applied)
    unresolved.extend(extra_gaps)
    for set_id, count in counts.items():
        matching = [rule for rule in SET_RULES.values()
                    if rule['set_name'].casefold().replace(' ', '_') + '_set' == set_id
                    and count >= rule['pieces']]
        set_entry = catalog.ENTRIES.get('set:' + set_id.replace('_', '-')) or {}
        covered_thresholds = {rule['pieces'] for rule in matching}
        covered_thresholds.update(required for identity, required in extra_covered if identity == set_id)
        for bonus in set_entry.get('bonuses') or []:
            required = bonus.get('required_items')
            if isinstance(required, int) and required <= count and required not in covered_thresholds:
                unresolved.append(f'{set_id}: {required}-piece historical threshold lacks a current executable rule')
        if not matching and not covered_thresholds and not set_entry.get('bonuses'):
            unresolved.append(f'{set_id}: earned set threshold has no current executable numeric rule')
        for rule in matching:
            if rule['id'] == 'bastille_two_reload_efficiency':
                if mode != 'pve_non_raidzone':
                    unresolved.append('Bastille 2-piece: non-RaidZone applicability needs an explicit encounter mode')
                else:
                    pools['reload_efficiency'] += rule['bonus_fraction'] * 100
                    applied.append({'rule_id': rule['id'], 'percentage_points': 15,
                                    'pool': 'reload_efficiency', 'source_status': rule['evidence_status']})
            elif rule['id'] == 'treacherous_tides_two_weapon':
                if mode != 'pve_non_raidzone' or hp_fraction is None:
                    unresolved.append('Treacherous Tides 2-piece: PvE non-RaidZone and HP fraction required')
                elif hp_fraction < rule['condition']['hp_fraction_below']:
                    for name in ('weapon', 'status'):
                        pools[name] += rule['bonus_fraction'] * 100
                    applied.append({'rule_id': rule['id'], 'percentage_points': 12,
                                    'pools': ['weapon', 'status'], 'source_status': rule['evidence_status']})
            elif rule['id'] == 'treacherous_tides_three':
                if mode != 'pve_non_raidzone' or hp_fraction is None:
                    unresolved.append('treacherous_tides_three: PvE non-RaidZone and HP fraction required')
                elif hp_fraction == 1:
                    for name in ('weapon', 'status'):
                        pools[name] += 8
                    applied.append({'rule_id': rule['id'], 'percentage_points': 8,
                                    'pools': ['weapon', 'status'],
                                    'source_status': rule['evidence_status'],
                                    'scope': 'official 100% HP endpoint; 2-piece condition inactive'})
                elif hp_fraction <= .6 and stack_model == 'additive_named_pools':
                    for name in ('weapon', 'status'):
                        pools[name] += 28
                    applied.append({'rule_id': rule['id'], 'percentage_points': 28,
                                    'pools': ['weapon', 'status'],
                                    'source_status': rule['evidence_status'],
                                    'scope': 'official low-HP endpoint; combination with 2-piece is an entered additive-pool hypothesis'})
                else:
                    unresolved.append('treacherous_tides_three: HP interpolation or combination with 2-piece unresolved; low-HP endpoint needs an explicit additive-pool hypothesis')
            else:
                unresolved.append(f"{rule['id']}: threshold reached but magnitude, activation or combination unresolved")
    return pools, applied, unresolved


def _shots(duration, timing):
    if timing['rpm'] is None or timing['magazine'] is None or timing['reload_seconds'] is None:
        return None
    at, rounds, shots, times = 0.0, 0, 0, []
    interval = 60 / timing['rpm']
    while at < duration - 1e-12:
        if shots >= MAX_SHOTS:
            return None
        times.append(at)
        shots += 1
        rounds += 1
        at += interval
        if rounds == timing['magazine']:
            at += timing['reload_seconds']
            rounds = 0
    return times


def _timed_direct(times, magazine, rule, direct_profile, duration, crit_hit_indices=None):
    """Group landed direct shots by a source-text timed bonus.

    Empty-magazine activation is post-shot and expiry is half-open. A reload
    finishes before the next shot in the existing published shot scheduler.
    """
    if not isinstance(magazine, int) or magazine < 1:
        raise ValueError('A finite magazine is required for timed core effects')
    groups = Counter()
    empty_times = []
    crit_hits = None
    if rule['kind'] == 'crit_hit_stack_until_reload':
        if not isinstance(crit_hit_indices, list) or any(
                isinstance(index, bool) or not isinstance(index, int) or
                not 0 <= index < len(times) for index in crit_hit_indices) or len(set(crit_hit_indices)) != len(crit_hit_indices):
            raise ValueError('Enter unique zero-based crit-hit shot indices within the encounter')
        crit_hits = set(crit_hit_indices)
    stack = 0.0
    for index, at in enumerate(times):
        crit_outcome = None
        if rule['kind'] == 'empty_magazine_independent_crit_stacks':
            active = sum(start <= at < start + rule['duration_seconds']
                         for start in empty_times[-rule['max_stacks']:])
            bonus = active * rule['value_percent']
            if (index + 1) % magazine == 0:
                empty_times.append(at)
        elif rule['kind'] == 'post_reload_first_hits_weakspot':
            cap = min(rule['hit_limit'], math.floor(magazine * rule['magazine_fraction_cap']))
            bonus = rule['value_percent'] if index >= magazine and index % magazine < cap else 0.0
        elif rule['kind'] == 'crit_hit_stack_until_reload':
            if index and index % magazine == 0:
                stack = 0.0
            bonus = stack
            crit_outcome = index in crit_hits
            if crit_outcome:
                stack = min(rule['maximum_percent'], stack + rule['value_percent'])
        else:
            raise ValueError('Unsupported timed core rule')
        groups[bonus, crit_outcome] += 1
    total = 0.0
    components = Counter()
    breakdown = []
    for (bonus, crit_outcome), count in sorted(groups.items()):
        profile = dict(direct_profile)
        key = 'crit_bonus_percent' if rule['pool'] == 'crit' else 'weakspot_bonus_percent'
        profile[key] += bonus
        if crit_outcome is not None:
            profile['crit_share'] = float(crit_outcome)
            profile['crit_weakspot_share'] = 0.0
        part = combat_projection.components({'shots': count, 'direct': profile,
                                             'duration_seconds': duration})
        total += part['total_damage']
        components.update(part['components'])
        breakdown.append({'bonus_percent': bonus, 'shots': count,
                          'crit_outcome': crit_outcome, 'damage': part['total_damage']})
    return {'total_damage': total, 'damage_per_second': total / duration,
            'components': dict(components), 'dynamic_breakdown': breakdown,
            'duration_seconds': duration,
            'assumptions': ['Timed source text applies after the triggering shot; expiry is half-open.',
                            'All scheduled direct shots are modeled as landed hits.']}


def _packet_direct(connected, direct_profile, adjustments, enemy_factor, duration):
    """Keep finite-ammo shot order when a kill changes later Weapon DMG."""
    direct_ids = {event['event_id'] for event in connected['events']
                  if event['kind'] == 'shot'}
    extra = {row['event_id']: row['damage_delta'] for row in adjustments}
    total = 0.0
    components = Counter()
    shot_count = 0
    for packet in connected['scheduler']['packets']:
        if packet['event_id'] not in direct_ids:
            continue
        profile = {**direct_profile,
                   'normal_damage_per_shot': (packet['damage'] +
                                               extra.get(packet['event_id'], 0)) * enemy_factor}
        one = combat_projection.components({'shots': 1, 'direct': profile,
                                            'duration_seconds': duration})
        total += one['total_damage']
        components.update(one['components'])
        shot_count += 1
    if shot_count != connected['shot_count']:
        raise ValueError('Kill-refill direct packets do not match scheduled shots')
    return {'total_damage': total, 'damage_per_second': total / duration,
            'components': dict(components), 'duration_seconds': duration,
            'dynamic_shot_adjustments': adjustments,
            'assumptions': ['A kill occurs after its indexed landed shot; its bonus begins on later packets and ends at reload.']}


def _typed_pools(typed):
    pools = {'weapon': 0.0, 'status': 0.0, 'elemental': 0.0, 'all': 0.0,
             'crit': 0.0, 'weakspot': 0.0, 'fire_rate': 0.0, 'reload_efficiency': 0.0}
    names = {'weapon_damage_percent': 'weapon', 'status_damage_percent': 'status',
             'elemental_damage_percent': 'elemental', 'all_damage_percent': 'all',
             'crit_damage_percent': 'crit', 'weakspot_damage_percent': 'weakspot',
             'fire_rate_percent': 'fire_rate', 'reload_efficiency_percent': 'reload_efficiency',
             'power_surge_damage_percent': 'power_surge'}
    pools['power_surge'] = 0.0
    applied, unresolved, duration_rules = [], [], []
    for item in typed:
        if item.get('status') != 'observed_typed_output':
            if item.get('missing'):
                unresolved.extend(f"{item.get('item_name')}: {gap}" for gap in item['missing'])
            continue
        unresolved.extend(f"{item.get('item_name')}: {gap}" for gap in item.get('missing') or [])
        for output in item.get('outputs') or []:
            if output.get('type') == 'status_duration_delta':
                if (output.get('stat') == 'power_surge_status_duration_percent'
                        and output.get('percentage_points') is not None):
                    duration_rules.append({'keyword': 'power_surge',
                        'percentage_points': _number(output['percentage_points'],
                            'Power Surge status duration change', -99, 1000),
                        'item_name': item.get('item_name'),
                        'catalog_id': item.get('catalog_id'),
                        'evidence_class': item.get('evidence_class')})
                else:
                    unresolved.append(f"{item.get('item_name')}: status duration target or magnitude missing")
                continue
            if output.get('type') != 'stat_pool_delta':
                continue  # healing, shield, ammo and utility retain their own typed output.
            pool = names.get(output.get('stat'))
            if pool is None or output.get('duration_seconds') is not None:
                unresolved.append(f"{item.get('item_name')}: timed or unbound stat output needs an event window")
                continue
            value = output.get('percentage_points')
            if value is None:
                unresolved.append(f"{item.get('item_name')}: stat magnitude missing")
                continue
            pools[pool] += _number(value, 'typed stat percentage', -99, 1000)
            applied.append({'item_name': item.get('item_name'), 'pool': pool,
                            'percentage_points': value, 'evidence_class': item.get('evidence_class')})
    return pools, applied, unresolved, duration_rules


def evaluate(build, options, *, typed_main_effects=()):
    if not isinstance(options, dict):
        raise ValueError('Timed scenario options must be an object')
    duration = _number(options.get('duration_seconds'), 'encounter duration', .000001, 3600)
    mode = options.get('scenario_mode') or 'unknown'
    if mode not in ('unknown', 'pve_non_raidzone', 'raidzone'):
        raise ValueError('Choose unknown, PvE non-RaidZone or RaidZone encounter mode')
    hp = options.get('hp_fraction')
    if hp is not None:
        hp = _number(hp, 'HP fraction', 0, 1)
    baseline = build.get('weapon_source_native_baseline') or {}
    if baseline.get('baseline_bonus_scope') == 'after_selected_effects_direct_only':
        # The supplied snapshot already reflects its declared selected effects.
        # Replaying shots is useful, but no selected static, timed, set or proc
        # modifier can be applied again without an inclusion/activation transform.
        stats = baseline['stats']
        timing = calculator.derive_timing(
            {'stats': {'rpm': stats.get('fire_rate'),
                       'magazine': stats.get('magazine_capacity'),
                       'reload_seconds': stats.get('reload_time_seconds')}},
            fire_rate_percent=0, magazine_percent=0, reload_efficiency_percent=0)
        times = _shots(duration, timing)
        damage = stats.get('damage_per_projectile')
        projectiles = stats.get('projectiles_per_shot')
        known = (damage * projectiles * len(times)
                 if times is not None and damage is not None and projectiles is not None else 0)
        gaps = ['Already-buffed packet replay covers direct body shots only; crit, weakspot, status, procs, timed effects and target settlement are not included']
        gaps.extend(timing['unresolved'])
        if options.get('source_timeline') is not None:
            gaps.append('Entered weapon source timeline was not combined with the already-buffed direct-only replay')
        if times is None:
            gaps.append('Shot schedule missing entered RPM, magazine or reload')
        return {'status': 'partial_timed_total', 'duration_seconds': duration,
                'shot_times': times, 'timing': timing,
                'direct_expected': {'total_damage': known, 'components': {'normal': known},
                                    'shot_count': len(times) if times is not None else None},
                'source_proc': None, 'source_timeline': None,
                'effective_pools_percent': {}, 'typed_core_pools_applied': [],
                'set_rules_applied': [], 'utility_bonus_lines': [],
                'known_damage_subtotal': known, 'modeled_total_damage': None,
                'conditional_damage_per_second': None,
                'included_effect_ids': list(baseline['included_effect_ids']),
                'unresolved': gaps,
                'assumptions': ['The caller asserts the entered direct-body damage, RPM, magazine and reload describe the selected effect state; no selected effect is applied again.',
                                'Only scheduled body shots are replayed. The subtotal is not full build damage or measured DPS.'],
                'game_winner_established': False}
    set_pools, set_applied, set_gaps = _set_pools(
        build, mode, hp, options.get('set_evidence_mode', 'current_release'),
        options.get('set_condition_inputs'), options.get('set_stack_model'))
    core = published_main_core.resolve(build.get('selected_mods') or [], options)
    remaining_typed = [row for row in typed_main_effects
                       if row.get('catalog_id') not in core['handled']]
    typed_pools, typed_applied, typed_gaps, duration_rules = _typed_pools(remaining_typed)
    pools = {key: (build['selected_pools_percent'].get(key, 0) + set_pools.get(key, 0)
                   + typed_pools.get(key, 0) + core['pools'].get(key, 0))
             for key in set(build['selected_pools_percent']) | set(set_pools) |
             set(typed_pools) | set(core['pools'])}
    gaps = list(set_gaps) + list(typed_gaps) + list(core['gaps'])
    for row in build.get('selected_mod_rows') or []:
        if row.get('conditional_extra_unresolved'):
            gaps.append(f"{row['catalog_id']}: {row['name']} conditional extra needs an explicit {row.get('condition') or 'trigger'} fraction")
    resonance_choices = resonance_suffix.selected_choices(build)
    resonance_entered = options.get('resonance_outcomes')
    if resonance_choices and resonance_entered is not None and not isinstance(resonance_entered, dict):
        raise ValueError('Resonance outcomes must be explicit per-shot index lists')
    if resonance_choices and resonance_entered is None:
        gaps.append('Selected Resonance needs explicit crit, weakspot and elemental shot-outcome indices, including empty lists for no outcomes')
    enemy_model = options.get('enemy_damage_bucket_model')
    if enemy_model not in (None, 'independent_multiplicative'):
        raise ValueError('Choose the named independent enemy-damage bucket model')
    enemy_percent = pools.get('enemy_damage', 0)
    if enemy_percent and enemy_model is None:
        gaps.append('Damage against enemies bucket grouping requires an explicit named model')
    enemy_factor = 1 + enemy_percent / 100 if enemy_model else 1.0
    packet_enemy_model = options.get('enemy_packet_target_model')
    if packet_enemy_model not in (None, 'all_enemies'):
        raise ValueError('Choose a named enemy-target scope for sourced packets')
    packet_enemy_factor = enemy_factor if packet_enemy_model == 'all_enemies' else 1.0
    utility_lines = []
    typed_by_id = {row.get('catalog_id'): row for row in typed_main_effects
                   if isinstance(row, dict) and row.get('catalog_id')}
    for selected in build.get('selected_mods') or []:
        identity = selected['catalog_id']
        if identity in core['handled']:
            continue
        typed = typed_by_id.get(identity)
        if typed is None:
            gaps.append(f'{identity}: selected main mod effect is not connected to this timed model')
        elif typed.get('status') != 'observed_typed_output' or typed.get('missing'):
            gaps.append(f'{identity}: selected main mod effect has unresolved source or activation')
        elif not typed.get('outputs') or any(
                not (output.get('type') == 'status_duration_delta' and
                     output.get('stat') == 'power_surge_status_duration_percent' and
                     output.get('percentage_points') is not None) and (
                output.get('type') != 'stat_pool_delta' or
                output.get('stat') not in ('weapon_damage_percent', 'status_damage_percent',
                    'elemental_damage_percent', 'all_damage_percent',
                    'crit_damage_percent', 'weakspot_damage_percent',
                    'fire_rate_percent', 'reload_efficiency_percent',
                    'power_surge_damage_percent') or
                output.get('duration_seconds') is not None or
                output.get('condition') is not None or
                output.get('percentage_points') is None)
                for output in typed['outputs']):
            gaps.append(f'{identity}: main mod includes utility, timing or conditional outputs outside the static timed pools')
    baseline = build['weapon_source_native_baseline']
    scaled = build['weapon_scaled_reference']
    if baseline is None or scaled is None:
        return {'status': 'partial_timed_total', 'known_damage_subtotal': 0,
                'modeled_total_damage': None, 'conditional_damage_per_second': None,
                'unresolved': gaps + ['Source-native weapon baseline missing']}
    timing = calculator.derive_timing({'stats': {'rpm': baseline['stats'].get('fire_rate'),
                                                'magazine': baseline['stats'].get('magazine_capacity'),
                                                'reload_seconds': baseline['stats'].get('reload_time_seconds')}},
                                      fire_rate_percent=pools['fire_rate'],
                                      magazine_percent=pools['magazine'],
                                      reload_efficiency_percent=pools['reload_efficiency'])
    gaps.extend(timing['unresolved'])
    times = _shots(duration, timing)
    if times is None:
        gaps.append('Shot schedule missing source RPM/magazine/reload or exceeds 10,000 shots')
    bullet_average = 0.0
    if times and core['bullet_counter']:
        sequence = []
        for index in range(len(times)):
            if index and index % timing['magazine'] == 0:
                sequence.append({'kind': 'reload'})
            sequence.append({'kind': 'shot'})
        bullet_average = published_main_core.bullet_average_bonus(
            sequence, core['bullet_counter'])
    damage = scaled['stats'].get('damage_per_projectile')
    pellets = baseline['stats'].get('projectiles_per_shot')
    normal = (damage * pellets * (1 + (pools['weapon'] + bullet_average) / 100) * (1 + pools['all'] / 100) * enemy_factor
              if damage is not None and pellets is not None else None)
    if normal is None:
        gaps.append('Published direct body-hit damage or projectile count missing')
    crit_share = options.get('crit_share')
    if crit_share is None:
        crit_share = baseline['stats'].get('crit_rate_percent')
        if crit_share is None:
            gaps.append('Crit share missing; enter a scenario value')
        else:
            crit_share = crit_share / 100
    else:
        crit_share = _number(crit_share, 'crit hit share', 0, 1)
    crit_share = (min(1.0, crit_share + (core['crit_rate_percentage_points'] +
                  pools.get('crit_rate', 0)) / 100) if crit_share is not None else None)
    weak_share = _number(options.get('weakspot_share', 0), 'weakspot hit share', 0, 1)
    if core['weakspot_disabled']:
        weak_share = 0.0
    joint = options.get('joint_share')
    if joint is None:
        joint = 0 if weak_share == 0 else None
    if core['weakspot_disabled']:
        joint = 0
    if joint is None:
        gaps.append('Crit and weakspot joint share required when weakspot hits occur')
    else:
        joint = _number(joint, 'crit and weakspot joint share', 0, 1)
    joint_model = options.get('joint_model', 'additive')
    if joint_model not in ('multiplicative', 'additive'):
        raise ValueError('Choose additive or multiplicative joint branch model')
    crit_bonus = baseline['stats'].get('crit_damage_percent')
    weak_bonus = baseline['stats'].get('weakspot_damage_percent')
    if resonance_choices and resonance_entered is not None:
        entered_baseline = options.get('resonance_baseline') or {}
        if not isinstance(entered_baseline, dict):
            raise ValueError('Resonance baseline must be an explicit source or scenario object')
        for key, sourced in (('crit_bonus_percent', crit_bonus),
                             ('weakspot_bonus_percent', weak_bonus)):
            entered = entered_baseline.get(key)
            if sourced is not None and entered is not None and not math.isclose(
                    _number(entered, key, 0, 1000), sourced, abs_tol=1e-9):
                raise ValueError(f'{key}: entered Resonance baseline conflicts with the selected weapon source')
            if key == 'crit_bonus_percent' and sourced is None and entered is not None:
                crit_bonus = _number(entered, key, 0, 1000)
            if key == 'weakspot_bonus_percent' and sourced is None and entered is not None:
                weak_bonus = _number(entered, key, 0, 1000)
        if crit_bonus is None and not resonance_entered.get('crit_shot_indices'):
            crit_bonus = 0.0
        if weak_bonus is None and not resonance_entered.get('weakspot_shot_indices'):
            weak_bonus = 0.0
        if crit_bonus is None or weak_bonus is None:
            gaps.append('Source-native bonus missing for a selected Resonance crit or weakspot outcome; enter that bonus as a named scenario input')
    else:
        if crit_bonus is None and crit_share == 0 and joint == 0:
            crit_bonus = 0.0
        if weak_bonus is None and weak_share == 0 and joint == 0:
            weak_bonus = 0.0
    if crit_bonus is None or weak_bonus is None:
        gaps.append('Published crit or weakspot damage baseline missing for a modeled outcome')
    direct = None
    if times and normal is not None and crit_share is not None and joint is not None and crit_bonus is not None and weak_bonus is not None:
        direct_profile = {
            'normal_damage_per_shot': normal, 'crit_bonus_percent': crit_bonus + pools['crit'],
            'weakspot_bonus_percent': weak_bonus + pools['weakspot'],
            'crit_share': crit_share, 'weakspot_share': weak_share,
            'crit_weakspot_share': joint, 'joint_multiplier': joint_model}
        if core['timed_rule'] and core['timed_rule']['kind'] not in published_core_packet_windows.PACKET_RULES:
            crit_indices = options.get('core_crit_hit_indices')
            if core['timed_rule']['kind'] == 'crit_hit_stack_until_reload' and (
                    crit_indices is None or weak_share != 0):
                gaps.append('Deadshot requires explicit crit-hit shot indices and a body-only weakspot scenario')
                direct = combat_projection.components({'shots': len(times), 'direct': direct_profile,
                                                       'duration_seconds': duration})
            else:
                direct = _timed_direct(times, timing['magazine'], core['timed_rule'],
                                       direct_profile, duration, crit_indices)
        else:
            direct = combat_projection.components({'shots': len(times), 'direct': direct_profile,
                                                   'duration_seconds': duration})
    # Missing fixed lines that could enter a modeled branch are unknown, not zero.
    # Every unknown bonus line may affect a timed build. Keep the subtotal,
    # but do not call it a complete timed total by silently dropping a line.
    for row in build['selected_mod_rows']:
        if row.get('applied_pool') is None:
            if str(row.get('stat_type') or '').startswith('resonance_'):
                continue  # Its timed contribution is modeled once by the shared packet scheduler.
            if row.get('outgoing_damage_role') == 'defensive_or_hp_utility':
                utility_lines.append(row)
            else:
                reason = row.get('calculation_exclusion_reason')
                gaps.append(f"{row['catalog_id']}: {row.get('name') or 'unknown bonus line'} — {reason}"
                            if reason else
                            f"{row['catalog_id']}: {row.get('name') or 'unknown bonus line'} magnitude or activation missing")
    known = direct['total_damage'] if direct else 0.0
    proc = None
    resonance_timeline = None
    resonance_outcome_assumptions = {
        'base_crit_bonus_percent': crit_bonus,
        'base_weakspot_bonus_percent': weak_bonus,
        'joint_multiplier': joint_model}
    if resonance_choices and resonance_entered is not None and options.get('source_timeline') is None:
        if normal is None or crit_bonus is None or weak_bonus is None:
            gaps.append('Guided Resonance needs source-native damage, projectiles and crit/weakspot baselines')
        elif core['timed_rule'] or core['bullet_counter']:
            gaps.append('Selected timed main effect or Bullet Siphon must be composed with Resonance packet state before a complete total')
        else:
            import published_timed_scheduler
            resonance_timeline = published_timed_scheduler.evaluate_direct_resonance(
                build, timing=timing, pools=pools, duration=duration,
                outcomes=resonance_entered,
                outcome_assumptions=resonance_outcome_assumptions)
            direct = {'total_damage': resonance_timeline['total_damage'] * enemy_factor,
                      'mode': 'explicit_ordered_resonance_outcomes',
                      'shot_count': len(resonance_timeline['shot_times'])}
            known = direct['total_damage']
            times = resonance_timeline['shot_times']
            gaps = [gap for gap in gaps if not gap.startswith(('Crit share missing;',
                     'Crit and weakspot joint share required'))]
    source_uncertainties = []
    proc_choice = options.get('proc')
    timeline_choice = options.get('source_timeline')
    if core['timed_rule'] and core['timed_rule']['kind'] == 'kill_refill_and_damage_until_reload' and \
            timeline_choice is None:
        kills = options.get('core_kill_shot_indices')
        if kills is None:
            gaps.append('Reload Rampage needs explicit kill shot indices or an explicit no-kills scenario')
        elif kills:
            gaps.append('Reload Rampage kill refill and later damage need a finite-ammo sourced timeline')
    if timeline_choice is not None and proc_choice is not None:
        raise ValueError('Choose either an automatic sourced timeline or a manually counted packet')
    if duration_rules and timeline_choice is None:
        gaps.append('Static Shock changes the target Power Surge status lifetime; a linked status application and baseline lifetime are required. It does not change the number of damage ticks or direct shots.')
    mechanics_weapon_id = build.get('weapon_mechanics_id', build['weapon_id'])
    source_ids = [key for key, binding in PACKETS.items() if binding.get('weapon_id') == mechanics_weapon_id]
    omitted_unique_effect = (not source_ids and
        bool(catalog.ENTRIES[build['weapon_id']].get('effect') or
             build['weapon_id'] in published_item_tier.ROWS))
    if options.get('exclude_unbound_weapon_effect') not in (None, False, True):
        raise ValueError('Exclude unbound weapon effect must be an explicit boolean')
    if omitted_unique_effect and options.get('exclude_unbound_weapon_effect') is not True:
        gaps.append(f"{build['weapon_id']}: selected weapon unique effect has no linked source event binding; direct body-hit damage remains a subtotal")
    connected = None
    timed_packet = None
    unique_armor = None
    if timeline_choice is not None:
        if core['timed_rule'] and core['timed_rule']['kind'] not in published_core_packet_windows.PACKET_RULES:
            gaps.append('Timed community core needs packet-by-packet source timeline composition')
        if (normal is None or crit_bonus is None or weak_bonus is None or
                (not (resonance_choices and resonance_entered is not None) and
                 (crit_share is None or joint is None))):
            gaps.append('Sourced timeline needs complete direct-hit and crit/weakspot reference inputs')
        elif timing['rpm'] is None or timing['magazine'] is None or timing['reload_seconds'] is None:
            gaps.append('Sourced timeline needs published RPM, magazine and reload seconds')
        else:
            import published_timed_scheduler
            source_options = timeline_choice
            source_damage = source_options.get('damage_model') or {}
            burn_model = (source_damage.get('packet_models') or {}).get('burn') if isinstance(source_damage, dict) and isinstance(source_damage.get('packet_models') or {}, dict) else None
            if (any(row.get('catalog_id') == 'armor:gilded-gauntlets'
                    for row in build.get('armor_profiles') or []) and
                    isinstance(burn_model, dict) and burn_model.get('crit') is True):
                source_options = {**source_options,
                    'packet_outcome_assumptions': {
                        'base_crit_bonus_percent': crit_bonus,
                        'base_weakspot_bonus_percent': weak_bonus,
                        'joint_multiplier': joint_model}}
            if resonance_choices and resonance_entered is not None:
                source_options = {**source_options,
                    'resonance_outcomes': resonance_entered,
                    'resonance_outcome_assumptions': resonance_outcome_assumptions}
            if duration_rules:
                source_options = {**source_options,
                    'status_duration_rules': duration_rules,
                    'power_surge_status_model': options.get('power_surge_status_model')}
            kill_rule = core['timed_rule'] if core['timed_rule'] and \
                core['timed_rule']['kind'] == 'kill_refill_and_damage_until_reload' else None
            if kill_rule:
                kills = options.get('core_kill_shot_indices')
                if not isinstance(kills, list):
                    gaps.append('Reload Rampage needs explicit zero-based kill shot indices, including an empty list for no kills')
                elif kills and options.get('core_refill_cap_model') != 'per_trigger':
                    gaps.append('Reload Rampage refill cap needs an explicit per-trigger 50%-of-capacity hypothesis')
                else:
                    source_options = {**source_options,
                                      'core_kill_refill_rule': kill_rule,
                                      'core_kill_shot_indices': kills}
            connected = published_timed_scheduler.evaluate(
                {**build, 'weapon_id': mechanics_weapon_id}, timing=timing, pools=pools,
                duration=duration, options=source_options, encounter_mode=mode)
            gaps.extend(connected['status_duration_unresolved'])
            if resonance_choices and resonance_entered is not None:
                resonance_timeline = connected['scheduler']
                gaps = [gap for gap in gaps if not gap.startswith(('Crit share missing;',
                         'Crit and weakspot joint share required'))]
            if core['timed_rule'] and core['timed_rule']['kind'] in published_core_packet_windows.PACKET_RULES:
                timed_packet = published_core_packet_windows.apply(
                    core['timed_rule'], connected, timing, options)
                gaps.extend(timed_packet['unresolved'])
                if core['timed_rule']['kind'] == 'previous_magazine_weakspot_rate':
                    counted = sum(window.get('previous_weakspot_hits', 0)
                                  for window in timed_packet['windows'])
                    if counted and (options.get('weakspot_share') is None or
                                    weak_share * connected['shot_count'] < counted - 1e-9):
                        gaps.append('Precision Charge counted weakspot hits need a consistent overall direct weakspot share')
            if enemy_percent and connected['extra_packet_damage'] and packet_enemy_model is None:
                gaps.append('Sourced packet targets need an explicit all-enemies target-scope model')
            shot_count = connected['shot_count']
            times = connected['scheduler']['shot_times']
            if core['bullet_counter']:
                bullet_average = published_main_core.bullet_average_bonus(
                    connected['events'], core['bullet_counter'])
                if connected['source_packets']:
                    gaps.append('Bullet Siphon magazine counter on extra source packets needs packet timing and Weapon-class scope')
            timeline_profile = {
                'normal_damage_per_shot': (connected['direct_body_damage'] / shot_count) *
                    (1 + (pools['weapon'] + bullet_average) / 100) /
                    (1 + pools['weapon'] / 100) * enemy_factor,
                'crit_bonus_percent': crit_bonus + pools['crit'],
                'weakspot_bonus_percent': weak_bonus + pools['weakspot'],
                'crit_share': crit_share, 'weakspot_share': weak_share,
                'crit_weakspot_share': joint, 'joint_multiplier': joint_model}
            if resonance_timeline is not None:
                if core['bullet_counter'] or timed_packet is not None:
                    gaps.append('Resonance interaction with Bullet Siphon or timed main-effect packets is not jointly modeled')
                direct = {'total_damage': connected['direct_body_damage'] * enemy_factor,
                          'mode': 'explicit_ordered_resonance_outcomes',
                          'shot_count': shot_count}
            elif kill_rule and timed_packet is not None:
                direct = _packet_direct(connected, timeline_profile,
                                        timed_packet.get('direct_packet_adjustments') or [],
                                        enemy_factor, duration)
            else:
                direct = combat_projection.components({'shots': shot_count, 'direct': timeline_profile,
                                                       'duration_seconds': duration})
            source_total = connected['extra_packet_damage'] + (timed_packet['damage_delta'] if timed_packet else 0)
            known = direct['total_damage'] + source_total * packet_enemy_factor
            unique_armor = published_unique_armor.wind_intepreter(
                build, mode, connected['source_packets'], connected['scheduler']['packets'],
                ammo_scenario=connected['wind_ammo_scenario'],
                ammo_trace=connected['wind_ammo_trace'])
            known += unique_armor['known_bonus_damage'] * packet_enemy_factor
            gaps.extend(unique_armor['unresolved'])
            proc = {'mode': 'source_event_timeline',
                    'damage': (source_total + unique_armor['known_bonus_damage']) * packet_enemy_factor,
                    'packets': connected['source_packets'],
                    'shot_count': shot_count,
                    'final_ammo': connected['scheduler']['final_ammo']}
            source_uncertainties.extend(connected['source_uncertainties'])
            gaps.extend(str(row.get('reason') or row) for row in connected['source_unresolved'])
    elif proc_choice is None and source_ids:
        gaps.append('Weapon has sourced extra packets; enter a proc count/outcome to compose one')
    if proc_choice is not None:
        if core['timed_rule'] and proc_choice.get('count'):
            gaps.append('Timed community core on manually counted packets needs event times and eligibility')
        if not isinstance(proc_choice, dict):
            raise ValueError('Proc scenario must be an object')
        if resonance_timeline is not None and proc_choice.get('count'):
            gaps.append('Manually counted proc packets need event times to interact with Resonance stacks')
        if core['bullet_counter'] and proc_choice.get('count'):
            gaps.append('Bullet Siphon magazine counter on manually counted packets needs event timing')
        packet_id = proc_choice.get('packet_id')
        spec = PACKETS.get(packet_id)
        if spec is None or spec.get('weapon_id') not in (None, mechanics_weapon_id):
            raise ValueError('Selected source packet does not match the weapon')
        count = proc_choice.get('count')
        if isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= 10000:
            raise ValueError('Proc count must be a whole number from 0 to 10000')
        if count:
            if enemy_percent and packet_enemy_model is None:
                gaps.append('Sourced packet targets need an explicit all-enemies target-scope model')
            if spec['coefficient']['kind'] != 'constant':
                gaps.append(f'{packet_id}: source packet requires linked event or ammo state')
            elif spec.get('requires_target_count') and proc_choice.get('target_count') is None:
                gaps.append(f'{packet_id}: explicit target count required')
            else:
                basis = spec['basis']
                value = (proc_choice.get('attack') if basis == 'attack' else
                         proc_choice.get('psi') if basis == 'psi' else
                         proc_choice.get('reference_damage'))
                if value is None and basis == 'psi' and build['armor_psi']['complete_six_slot_build']:
                    value = build['armor_psi']['known_psi_total']
                if value is None:
                    gaps.append(f'{packet_id}: {basis} basis value missing')
                else:
                    value = _number(value, basis + ' value')
                    damage_class = spec.get('damage_class') or proc_choice.get('damage_class')
                    element = spec.get('element') or proc_choice.get('element')
                    if damage_class not in ('weapon', 'status') or element not in ('none', 'non_elemental', 'shock', 'blaze', 'frost', 'blast'):
                        gaps.append(f'{packet_id}: damage class or elemental eligibility unresolved')
                    elif spec.get('damage_class') and proc_choice.get('damage_class') not in (None, spec['damage_class']):
                        raise ValueError('Proc damage class conflicts with source binding')
                    elif spec.get('element') and proc_choice.get('element') not in (None, spec['element']):
                        raise ValueError('Proc element conflicts with source binding')
                    else:
                        event = {'event': spec['event'], 'weapon_id': mechanics_weapon_id,
                                 'event_id': 'published-timed-proc', 'effect_type': 'damage_packet',
                                 'resolved_hit': True, 'instances': 1}
                        if spec.get('requires_target_count'):
                            targets = proc_choice['target_count']
                            if isinstance(targets, bool) or not isinstance(targets, int) or not 0 <= targets <= 10000:
                                raise ValueError('Proc target count must be a whole number from 0 to 10000')
                            event['target_count'] = targets
                            event['instances'] = targets
                        projection = project_event(packet_id, event,
                            attack=value if basis == 'attack' else None,
                            psi=value if basis == 'psi' else None,
                            references={spec['reference_key']: value} if basis == 'reference_damage' else None,
                            evidence_mode=proc_choice.get('evidence_mode', 'dated_release'),
                            include_intrinsic_bonus=spec.get('intrinsic_bonus_fraction') is not None)
                        multiplier = ((1 + pools['all'] / 100) * (1 + pools[damage_class] / 100) * packet_enemy_factor *
                                      ((1 + pools['elemental'] / 100) if element not in ('none', 'non_elemental') else 1))
                        proc_damage = float(projection.source_only_total) * count * multiplier
                        proc = {'packet_id': packet_id, 'count': count,
                                'basis': basis, 'basis_value': value,
                                'coefficient': float(projection.coefficient),
                                'damage_class': damage_class, 'element': element,
                                'damage': proc_damage,
                                'source_status': projection.evidence_status,
                                'source_unresolved': list(projection.unresolved),
                                'pool_grouping': 'additive_within_named_pool_multiplicative_across_pools'}
                        source_uncertainties.extend(projection.unresolved)
                        known += proc_damage
    if source_ids and proc_choice:
        uncovered = [key for key in source_ids if key != proc_choice.get('packet_id')]
        if uncovered:
            gaps.append('Other sourced weapon packets remain unmodeled: ' + ', '.join(uncovered))
    if unique_armor is None:
        unique_armor = published_unique_armor.wind_intepreter(build, mode, [], [])
        gaps.extend(unique_armor['unresolved'])
    complete = not gaps and direct is not None
    return {'unique_armor': unique_armor,
            'status': 'conditional_modeled_total' if complete else 'partial_timed_total',
            'duration_seconds': duration, 'shot_times': times,
            'direct_expected': direct, 'source_proc': proc,
            'source_timeline': (None if connected is None else {
                'events': connected['events'],
                'source_packets': connected['source_packets'],
                'unresolved_source_packets': connected['source_unresolved'],
                'status_duration_transforms': connected['status_duration_transforms'],
                'status_duration_unresolved': connected['status_duration_unresolved'],
                'final_ammo': connected['scheduler']['final_ammo'],
                'wind_ammo_trace': connected['wind_ammo_trace'],
                'shot_times': connected['scheduler']['shot_times'],
                'direct_body_damage': connected['direct_body_damage']}),
            'timed_core_packet_windows': timed_packet,
            'resonance_timeline': (None if resonance_timeline is None else {
                'shot_times': resonance_timeline['shot_times'],
                'packets': resonance_timeline['packets'],
                'event_trace': resonance_timeline['event_trace'],
                'resonance_sources': resonance_timeline['resonance_sources'],
                'mode': 'explicit_ordered_outcomes_source_scenario'}),
            'set_rules_applied': set_applied,
            'set_evidence_mode': options.get('set_evidence_mode', 'current_release'),
            'typed_core_pools_applied': typed_applied + core['applied'],
            'typed_status_duration_rules': duration_rules,
            'bullet_counter_average_percent': bullet_average,
            'effective_pools_percent': pools, 'timing': timing,
            'utility_bonus_lines': utility_lines,
            'known_damage_subtotal': known,
            'source_uncertainties': list(dict.fromkeys(source_uncertainties)),
            'explicitly_excluded_unbound_weapon_effect': (
                build['weapon_id'] if omitted_unique_effect and
                options.get('exclude_unbound_weapon_effect') is True else None),
            'modeled_total_damage': known if complete else None,
            'conditional_damage_per_second': known / duration if complete else None,
            'unresolved': list(dict.fromkeys(gaps)),
            'assumptions': [('Entered direct body damage per projectile is a caller hypothesis, not a conversion from Attack or a sourced weapon page.'
                             if baseline.get('evidence') == 'caller_entered_direct_packet_hypothesis' else
                             'Published source-native damage is a direct body-hit reference, not verified current Attack.'),
                            ('Entered damage, RPM, magazine and reload are asserted to exclude selected weapon, gear, mod and set effects before those effects are applied.'
                             if baseline.get('baseline_bonus_scope') == 'before_selected_effects' else
                             'The named item page is a reference without this selected build’s modifiers; intrinsic weapon effects remain subject to the source model.'),
                            'The simple direct-shot schedule assumes unlimited reserve ammunition and completed reloads; use a sourced timeline for finite reserves.',
                            'Source crit rate is used as hit share unless a scenario share is entered; blank weakspot share is a named body-only scenario.',
                            'A selected proc count is an explicit outcome, not an inferred random trigger rate.',
                            'No target defense, resistance, falloff or undocumented proc is included.',
                            'Set and main-effect modifiers use additive named pools under this conditional model.'] +
                           ([f"{build['weapon_id']}: unbound unique weapon effect was explicitly excluded; this is a direct-body-only scenario, not full item damage."]
                            if omitted_unique_effect and options.get('exclude_unbound_weapon_effect') is True else []) +
                           (['Wind Intepreter Cap bullet source and retention after the reload transaction are entered scenario hypotheses; the official effect text does not establish either ordering or reserve use.']
                            if unique_armor.get('ammo_scenario') else []) +
                           (['Selected short weapon name uses an exact identity binding to its full catalog weapon for sourced packet eligibility; published damage values remain a reference model.']
                            if mechanics_weapon_id != build['weapon_id'] else []) +
                           (['Set values from the March 2026 community snapshot are an opted-in source scenario; their current-game applicability is unverified.']
                            if any(row.get('source_status') == 'community_snapshot_candidate' for row in set_applied) else []) +
                           (['Bastille one/three-piece values use an opted-in 2024 official rule; current applicability is unverified.']
                            if any(row.get('source_status') == 'historical_official_release' for row in set_applied) else []) +
                           (['Treacherous Tides two- and three-piece bonuses are combined as additive named pools; this is an explicit stacking hypothesis.']
                            if any(row.get('rule_id') == 'treacherous_tides_three' and row.get('percentage_points') == 28
                                   for row in set_applied) else []) +
                           (['DMG against Enemies is modeled as an independent multiplicative target pool; this bucket is an explicit scenario hypothesis, not a verified game equation.']
                            if enemy_percent and enemy_model else []) +
                           (['Every modeled sourced packet target is assumed to be an enemy.']
                            if enemy_percent and packet_enemy_model else []) +
                           (['Community kill-refill is modeled as a post-shot kill event: up to two bullets transfer from finite reserves, capped at half a magazine per trigger; the bonus is nonstacking until reload.']
                            if core['timed_rule'] and core['timed_rule']['kind'] == 'kill_refill_and_damage_until_reload' and options.get('core_kill_shot_indices') else []) +
                           (['Max HP and incoming-damage lines are reported as utility; the outgoing-damage model assumes no HP-dependent damage feedback.']
                            if utility_lines else []),
            'game_winner_established': False}
