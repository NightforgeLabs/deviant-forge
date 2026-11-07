"""Narrow, source-gated core semantics for published timed reference scenarios.

Field Guide level identifies exact photographed cards. Community item effect
level is separate and never inferred from that Field Guide level.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import re

import catalog
import mod_core_typed

CANDIDATES = {row['catalog_id']: row for row in json.loads(
    (Path(__file__).parent / 'evidence_packets/published-main-core-v1.json').read_text())['candidates']}
PUBLIC = {row['catalog_id']: row for row in json.loads(
    (Path(__file__).parent / 'evidence_packets/public-core-crosswalk-v1.json').read_text())['records']}
BULLET = 'mod:pants_mod:bullet-siphon-aero-deviant-energy'
AGAINST = 'mod:boots_mod:against-all-odds-precision'
AGAINST_DEVIANT_ENERGY = 'mod:boots_mod:against-all-odds-deviant-energy'
POWER_STRIVING = 'mod:boots_mod:power-of-striving-downstar-deviant-energy'


def _community_text(identity, text, options):
    record = PUBLIC.get(identity)
    if not record or not record['normal_source_item_id']:
        raise ValueError(f'{identity}: no ordinary source item for community core text')
    if text not in record['effect_text_variants_unranked']:
        raise ValueError(f'{identity}: chosen core text is not a held source variant')
    result = {'pools': {}, 'crit_rate': 0.0, 'weakspot_disabled': False,
              'gaps': [], 'operator': None, 'bullet_counter': None, 'timed_rule': None}
    def pool(name, value):
        result['pools'][name] = float(value)
    def active():
        flag = options.get('core_condition_active')
        if not isinstance(flag, bool):
            result['gaps'].append(f'{identity}: enter whether the named core condition holds throughout this encounter')
            return False
        return flag
    if match := re.fullmatch(r'Cannot deal Weakspot DMG\. Crit Rate \+(\d+(?:\.\d+)?)% and Crit DMG \+(\d+(?:\.\d+)?)%\.', text):
        result['operator'] = 'crit_weakspot_tradeoff'
        result['crit_rate'] = float(match[1])
        pool('crit', match[2])
        result['weakspot_disabled'] = True
    elif match := re.fullmatch(r'Crit Rate \+(\d+(?:\.\d+)?)%, Crit DMG \+(\d+(?:\.\d+)?)%\.', text):
        result['operator'] = 'static_crit_pair'
        result['crit_rate'] = float(match[1])
        pool('crit', match[2])
    elif match := re.fullmatch(r'Crit Rate \+(\d+(?:\.\d+)?)%\.?', text):
        result['operator'] = 'static_crit_rate'
        result['crit_rate'] = float(match[1])
    elif match := re.fullmatch(r'Element DMG \(Blaze, Frost, Shock, Blast\) \+(\d+(?:\.\d+)?)%\.', text):
        result['operator'] = 'static_elemental'
        pool('elemental', match[1])
    elif match := re.fullmatch(r'(Weapon|Status|Weakspot) DMG \+(\d+(?:\.\d+)?)%\.?', text):
        result['operator'] = 'static_damage_pool'
        pool({'Weapon': 'weapon', 'Status': 'status', 'Weakspot': 'weakspot'}[match[1]], match[2])
    elif match := re.fullmatch(r'Having no enemies within 7 meters around you grants \+(\d+(?:\.\d+)?)% Weapon and Status DMG\.', text):
        result['operator'] = 'conditional_no_nearby_enemies'
        if active():
            pool('weapon', match[1]); pool('status', match[1])
    elif match := re.fullmatch(r'When hitting marked enemies, Crit Rate \+(\d+(?:\.\d+)?)%, and Crit DMG \+(\d+(?:\.\d+)?)%\.', text):
        result['operator'] = 'conditional_marked_target'
        if active():
            result['crit_rate'] = float(match[1]); pool('crit', match[2])
    elif match := re.fullmatch(r'Weakspot DMG \+(\d+(?:\.\d+)?)% when a bullet hits a target more than 20 meters away\. For every additional 1 meter\(s\) away from the target, Weakspot DMG \+1%, up to \+20%\.', text):
        result['operator'] = 'distance_gated_weakspot'
        distance = options.get('core_target_distance_meters')
        if isinstance(distance, bool) or not isinstance(distance, int) or not 0 <= distance <= 10000:
            result['gaps'].append(f'{identity}: enter whole-meter target distance for the named floor-distance model')
        elif distance > 20:
            pool('weakspot', float(match[1]) + min(20, math.floor(distance - 20)))
    elif match := re.fullmatch(r'(?:Weapon DMG \+(\d+(?:\.\d+)?)%\. )?Every (\d+) bullets consumed in the magazine grants \+(\d+(?:\.\d+)?)% Weapon DMG, capped at (\d+(?:\.\d+)?)%\.', text):
        result['operator'] = 'magazine_consumed_counter'
        if match[1]:
            pool('weapon', match[1])
        result['bullet_counter'] = {'every_bullets': int(match[2]),
                                    'per_step_percent': float(match[3]),
                                    'maximum_percent': float(match[4]),
                                    'reset': 'new_magazine',
                                    'source_url': record['normal_source_item_url']}
    elif match := re.fullmatch(r'When the magazine is empty, Crit DMG \+(\d+(?:\.\d+)?)% for 12s\. Stacks independently, up to 3 stack\(s\)\.', text):
        result['operator'] = 'empty_magazine_independent_crit_stacks'
        result['timed_rule'] = {'kind': result['operator'], 'pool': 'crit',
                                'value_percent': float(match[1]),
                                'duration_seconds': 12, 'max_stacks': 3}
    elif match := re.fullmatch(r'For the first three hits after reloading \(not exceeding 50% of magazine capacity\), Weakspot DMG \+(\d+(?:\.\d+)?)%\.', text):
        result['operator'] = 'post_reload_first_hits_weakspot'
        result['timed_rule'] = {'kind': result['operator'], 'pool': 'weakspot',
                                'value_percent': float(match[1]),
                                'hit_limit': 3, 'magazine_fraction_cap': .5}
    elif match := re.fullmatch(r'Each Crit Hit by non-melee weapons grants \+(\d+(?:\.\d+)?)% Crit DMG, up to (\d+(?:\.\d+)?)%\. The effect is removed upon the next reload\.', text):
        result['operator'] = 'crit_hit_stack_until_reload'
        result['timed_rule'] = {'kind': result['operator'], 'pool': 'crit',
                                'value_percent': float(match[1]),
                                'maximum_percent': float(match[2]),
                                'reset': 'reload'}
    elif match := re.fullmatch(r'When the magazine is empty, Status DMG \+(\d+(?:\.\d+)?)% for 12s\. Effect can stack up to 3 times\.', text):
        result['operator'] = 'empty_magazine_status_stacks'
        result['timed_rule'] = {'kind': result['operator'], 'pool': 'status',
                                'value_percent': float(match[1]),
                                'duration_seconds': 12, 'max_stacks': 3}
    elif match := re.fullmatch(r'For each instance of Elemental DMG dealt from the previous magazine, the next magazine gains Elemental DMG \+(\d+(?:\.\d+)?)% for 15s upon reloading, up to \+(\d+(?:\.\d+)?)%\.', text):
        result['operator'] = 'previous_magazine_elemental_instances'
        result['timed_rule'] = {'kind': result['operator'], 'pool': 'elemental',
                                'value_percent': float(match[1]),
                                'maximum_percent': float(match[2]),
                                'duration_seconds': 15}
    elif match := re.fullmatch(r'For every 10% Weakspot hit rate of the previous magazine, Elemental DMG \+(\d+(?:\.\d+)?)%, up to (\d+(?:\.\d+)?)%, lasting for 10s\. Reloading resets the calculation\.', text):
        result['operator'] = 'previous_magazine_weakspot_rate'
        result['timed_rule'] = {'kind': result['operator'], 'pool': 'elemental',
                                'value_percent': float(match[1]),
                                'maximum_percent': float(match[2]),
                                'duration_seconds': 10, 'per_rate_percent': 10}
    elif match := re.fullmatch(r'After killing an enemy, refill 2 bullets from reserves \(no more than 50% of the Magazine Capacity\)\. Weapon DMG and Status DMG \+(\d+(?:\.\d+)?)% until next reload\.', text):
        result['operator'] = 'kill_refill_and_damage_until_reload'
        result['timed_rule'] = {'kind': result['operator'],
                                'pools': ['weapon', 'status'],
                                'value_percent': float(match[1]),
                                'refill_bullets': 2, 'per_trigger_capacity_fraction': .5}
    elif re.fullmatch(r'Every time an enemy is marked, Attack \+\d+(?:\.\d+)?% for 8s\. Effect can stack up to 3 times\.', text):
        result['operator'] = 'marked_enemy_attack_stacks_unbound_basis'
        result['gaps'].append(f'{identity}: mark event times and a sourced Attack-to-published-damage conversion are required')
    elif re.fullmatch(r'HP \+\d+(?:\.\d+)?%\.?', text):
        result['operator'] = 'static_hp_utility'
        result['gaps'].append(f'{identity}: HP utility effect is not an outgoing damage pool')
    elif text.startswith('Melee DMG +'):
        result['operator'] = 'melee_or_utility'
        result['gaps'].append(f'{identity}: melee damage and stamina effects need a melee attack model')
    else:
        result['operator'] = 'unsupported_event_or_resource'
        result['gaps'].append(f'{identity}: selected source text needs a timed, counter, target or resource event operator')
    result['source_item_effect_level'] = (
        CANDIDATES[identity]['source_item_effect_level']
        if identity in CANDIDATES and text == CANDIDATES[identity]['effect_text'] else None)
    result['source_item_id'] = record['normal_source_item_id']
    result['source_url'] = record['normal_source_item_url']
    result['effect_text_source_url'] = (catalog.ENTRIES[identity].get('detail_source_urls') or
                                        [record['normal_source_item_url']])[0]
    return result


def resolve(selected_mods, options):
    pools = {'weapon': 0.0, 'status': 0.0, 'crit': 0.0}
    applied, gaps, handled = [], [], set()
    crit_rate_bonus = 0.0
    weakspot_disabled = False
    bullet_counter = None
    timed_rule = None
    for selected in selected_mods:
        identity, level = selected['catalog_id'], selected['level']
        shiny = selected.get('shiny') is True
        requested_texts = options.get('core_effect_texts') or {}
        if not isinstance(requested_texts, dict):
            raise ValueError('Core effect text choices must be keyed by catalog identity')
        chosen_text = requested_texts.get(identity)
        if chosen_text is None and len(selected_mods) == 1:
            chosen_text = options.get('core_effect_text')
        if identity == BULLET and level == 12 and not shiny:
            binding = mod_core_typed.EXACT[identity, level]
            rule = binding['rule']
            if rule['operator'] != 'base_plus_magazine_counter':
                raise ValueError('Bullet Siphon exact source operator changed')
            base, counter = rule['nodes']
            if base['stat'] != counter['stat'] or base['stat'] != 'weapon_damage_percent':
                raise ValueError('Bullet Siphon source no longer names the Weapon DMG pool')
            pools['weapon'] += base['value']
            bullet_counter = {'every_bullets': counter['per_bullets_consumed'],
                              'per_step_percent': counter['value_per_step'],
                              'maximum_percent': counter['max_bonus_percent'],
                              'reset': counter['reset'],
                              'source_sha256': binding['source_sha256']}
            applied.append({'catalog_id': identity, 'field_guide_level': level,
                            'source': 'exact_current_field_guide_frame',
                            'source_sha256': binding['source_sha256'],
                            'static_pools_percent': {'weapon': base['value']},
                            'dynamic_rule': bullet_counter})
            handled.add(identity)
        elif (identity, level) in ((AGAINST, 7), (AGAINST_DEVIANT_ENERGY, 12)) and not shiny:
            binding = mod_core_typed.EXACT[identity, level]
            rule = binding['rule']
            if rule['operator'] != 'base_plus_hp_cost_timed_stack_partial':
                raise ValueError('Against All Odds exact source operator changed')
            if identity == AGAINST_DEVIANT_ENERGY:
                observed = mod_core_typed.evaluate(identity, level, context={
                    'core_unknown_variant_opt_in': options.get('core_unknown_variant_opt_in') is True,
                    'core_unknown_build_opt_in': options.get('core_unknown_build_opt_in') is True,
                    'no_hp_cost_events': options.get('core_no_hp_cost_events') is True})
                if observed['status'] != 'observed_typed_output':
                    gaps.append(f'{identity}: exact held-video base requires explicit unknown-variant and unknown-build opt-ins')
                    handled.add(identity)
                    continue
            for node in rule['nodes']:
                if node['stat'] == 'weapon_damage_percent':
                    pools['weapon'] += node['value']
                elif node['stat'] == 'status_damage_percent':
                    pools['status'] += node['value']
                else:
                    raise ValueError('Against All Odds base stat pool changed')
            if options.get('core_no_hp_cost_events') is not True:
                gaps.append(f'{identity}: HP-cost stacks need event times, amounts and expiry model, or explicit no-HP-cost scenario')
            applied.append({'catalog_id': identity, 'field_guide_level': level,
                            'source': ('held_game_video_unknown_build_scenario'
                                       if identity == AGAINST_DEVIANT_ENERGY else
                                       'exact_current_field_guide_frame'),
                            'source_image': binding.get('source_image'),
                            'static_pools_percent': {'weapon': 10, 'status': 10},
                            'stack_model': 'no_hp_cost_events' if options.get('core_no_hp_cost_events') is True else 'unresolved'})
            handled.add(identity)
        elif identity == POWER_STRIVING and level == 9 and not shiny:
            binding = mod_core_typed.EXACT[identity, level]
            rule = binding['rule']
            if (rule['operator'] != 'base_plus_unknown_curve' or
                    {(node['stat'], node['value']) for node in rule['nodes']} !=
                    {('weapon_damage_percent', 10.0), ('status_damage_percent', 10.0)}):
                raise ValueError('Power of Striving exact source base changed')
            pools['weapon'] += 10
            pools['status'] += 10
            no_loss = options.get('core_no_stamina_loss_events') is True
            if not no_loss:
                gaps.append(f'{identity}: stamina-loss bonus needs event amounts and a sourced curve, or an explicit no-stamina-loss scenario')
            applied.append({'catalog_id': identity, 'field_guide_level': level,
                            'source': 'exact_current_field_guide_frame',
                            'source_image': binding.get('source_image'),
                            'static_pools_percent': {'weapon': 10, 'status': 10},
                            'stack_model': 'no_stamina_loss_events' if no_loss else 'unresolved'})
            handled.add(identity)
        elif chosen_text is not None and options.get('published_item_core_opt_in') is True:
            if shiny:
                gaps.append(f'{identity}: ordinary community core text cannot bind to Shiny')
                continue
            candidate = _community_text(identity, chosen_text, options)
            for name, value in candidate['pools'].items():
                pools[name] = pools.get(name, 0) + value
            crit_rate_bonus += candidate['crit_rate']
            weakspot_disabled = weakspot_disabled or candidate['weakspot_disabled']
            if candidate['bullet_counter']:
                bullet_counter = candidate['bullet_counter']
            if candidate['timed_rule']:
                if timed_rule is not None:
                    gaps.append('Multiple timed community core rules require combined event ordering')
                else:
                    timed_rule = candidate['timed_rule']
            gaps.extend(candidate['gaps'])
            applied.append({'catalog_id': identity, 'field_guide_level': level,
                            'source_item_effect_level': candidate['source_item_effect_level'],
                            'source_item_id': candidate['source_item_id'],
                            'source_url': candidate['source_url'],
                            'effect_text_source_url': candidate['effect_text_source_url'],
                            'source': 'community_selected_unranked_text_variant',
                            'operator': candidate['operator'],
                            'effect_text': chosen_text,
                            'static_pools_percent': candidate['pools'],
                            'dynamic_rule': candidate['bullet_counter'],
                            'timed_rule': candidate['timed_rule'],
                            'crit_rate_percentage_points': candidate['crit_rate'],
                            'weakspot_disabled': candidate['weakspot_disabled']})
            handled.add(identity)
        elif identity in CANDIDATES and not shiny:
            candidate = CANDIDATES[identity]
            if options.get('published_item_core_opt_in') is not True:
                continue
            pools['crit'] += candidate['crit_damage_percentage_points']
            crit_rate_bonus += candidate['crit_rate_percentage_points']
            weakspot_disabled = candidate['disable_weakspot_damage']
            applied.append({'catalog_id': identity, 'field_guide_level': level,
                            'source_item_effect_level': candidate['source_item_effect_level'],
                            'source_item_id': candidate['source_item_id'],
                            'source_url': candidate['source_url'],
                            'source': candidate['source_status'],
                            'static_pools_percent': {'crit': candidate['crit_damage_percentage_points']},
                            'crit_rate_percentage_points': candidate['crit_rate_percentage_points'],
                            'weakspot_disabled': weakspot_disabled})
            handled.add(identity)
    return {'pools': pools, 'applied': applied, 'gaps': gaps, 'handled': handled,
            'crit_rate_percentage_points': crit_rate_bonus,
            'weakspot_disabled': weakspot_disabled, 'bullet_counter': bullet_counter,
            'timed_rule': timed_rule}


def bullet_average_bonus(shot_events, counter):
    """Bonus for each shot based on bullets consumed BEFORE that shot."""
    if not counter or not shot_events:
        return 0.0
    spent, bonuses = 0, []
    for event in shot_events:
        if event['kind'] == 'reload':
            spent = 0
        elif event['kind'] == 'shot':
            bonuses.append(min(counter['maximum_percent'],
                               (spent // counter['every_bullets']) * counter['per_step_percent']))
            spent += 1
    return sum(bonuses) / len(bonuses) if bonuses else 0.0
