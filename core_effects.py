"""Selected core-effect coverage and finite-count sensitivities.

These are conditional event counts, never a source of inferred damage.
"""
from __future__ import annotations
import math
import re

THUNDERCLAP = 'https://www.oncehumandb.com/mods/thunderclap-power-surge'
SHOCK_RAMPAGE = 'https://www.oncehumandb.com/mods/shock-rampage-power-surge'
SNAPSHOT_DATE = '2026-10-25'


def finite_counter(hits, chance, instances=1, start=0, armed=False, same_hit=False):
    if isinstance(hits, bool) or not isinstance(hits, int) or not 0 <= hits <= 2000:
        raise ValueError('Eligible landed hits must be an integer from 0 to 2000')
    if isinstance(chance, bool) or not isinstance(chance, (int, float)) or not math.isfinite(chance) or not 0 <= chance <= 1:
        raise ValueError('Root chance must be between 0 and 1')
    if instances not in (1, 2):
        raise ValueError('Emitted instances must be 1 or 2 in this sensitivity')
    if isinstance(start, bool) or not isinstance(start, int) or not 0 <= start < 20 or (armed and start):
        raise ValueError('Starting counter must be 0–19, or armed with counter 0')
    state = [0.0] * 21
    state[20 if armed else start] = 1.0
    resolved = 0.0
    for _ in range(hits):
        following = [0.0] * 21
        for count, weight in enumerate(state):
            if not weight:
                continue
            before = 0 if count == 20 else count
            if count == 20:
                resolved += weight
            following[before] += weight * (1 - chance)
            after = before + instances
            if same_hit and after >= 20:
                resolved += weight * chance
                following[0] += weight * chance
            else:
                following[min(20, after)] += weight * chance
        state = following
    return {'expected_resolutions': resolved, 'armed_probability': state[20],
            'steady_rate_shortcut': hits * chance * instances / 20}


def selected(slots, *, active_weapon_slot='primary', power_surge=None, counter=None):
    if active_weapon_slot not in ('primary', 'secondary', 'melee'):
        raise ValueError('Active weapon slot must be primary, secondary or melee')
    if not isinstance(slots, dict):
        raise ValueError('Saved build slots must be an object')
    entries = []
    weapon = slots.get(active_weapon_slot) or {}
    mask = slots.get('mask') or {}
    weapon_id = weapon.get('mod_id') if isinstance(weapon, dict) else None
    mask_id = mask.get('mod_id') if isinstance(mask, dict) else None
    spec = power_surge or {}
    if weapon_id and weapon_id.startswith('mod:weapon_mod:shock-rampage'):
        observed = (spec.get('rate_origin') == 'measured_selected_build'
                    and isinstance(spec.get('events_per_active_second'), (int, float))
                    and not isinstance(spec.get('events_per_active_second'), bool)
                    and math.isfinite(spec['events_per_active_second'])
                    and spec['events_per_active_second'] >= 0)
        entries.append({'slot': active_weapon_slot, 'mod_id': weapon_id, 'name': 'Shock Rampage',
                        'component': 'Power Surge event frequency',
                        'status': 'included_in_entered_observed_rate' if observed else 'unmodeled_core_effect',
                        'total_blocking': not observed,
                        'reason': ('The entered event rate is explicitly declared measured on this selected build; no second trigger bonus is applied.' if observed else
                                   'Core-trigger stacks can change event frequency. The entered rate has not been confirmed as measured on this exact build.'),
                        'needed': None if observed else 'Measure Power Surge events per active second on this selected build, or leave the complete total unknown.',
                        'source': SHOCK_RAMPAGE, 'source_retrieved': SNAPSHOT_DATE, 'source_publication_date': None})
    if mask_id and mask_id.startswith('mod:mask_mod:thunderclap'):
        preview = None
        if counter is not None:
            if not isinstance(counter, dict):
                raise ValueError('Finite counter inputs must be an object')
            hits = counter.get('eligible_landed_hits')
            chance = counter.get('root_trigger_chance')
            start = counter.get('starting_counter', 0)
            armed = counter.get('starting_armed', False)
            if not isinstance(armed, bool):
                raise ValueError('Starting armed state must be true or false')
            one = finite_counter(hits, chance, 1, start, armed)
            two = finite_counter(hits, chance, 2, start, armed)
            rival = finite_counter(hits, chance, 2, start, armed, True)
            preview = {'eligible_landed_hits': hits, 'entered_root_trigger_chance': chance,
                       'next_hit_one_instance': one, 'next_hit_two_instances': two,
                       'same_hit_two_instances': rival,
                       'assumptions': ['Constant independent root chance entered for this selected encounter.',
                                       'A child instance does not reroll the root; no cooldown, expiry or overflow carry is assumed.',
                                       'Eligibility and next-hit behavior remain competing interpretations, not measured rules.']}
        entries.append({'slot': 'mask', 'mod_id': mask_id, 'name': 'Thunderclap',
                        'component': 'Armed, next-hit Celestial Thunder event',
                        'status': 'event_count_hypothesis_damage_unknown' if preview else 'unmodeled_core_effect',
                        'total_blocking': True,
                        'reason': 'Its finite 20-trigger counter and damage are not in the average Power Surge or orb stream. Event count alone does not establish damage.',
                        'needed': 'Confirm eligible hit/proc counting and the exact selected-level damage; measured full-fight component is an alternative.',
                        'counter_preview': preview, 'source': THUNDERCLAP,
                        'source_retrieved': SNAPSHOT_DATE, 'source_publication_date': None})
    return entries

SHOCK17_FRAME = 'libfile_84a17de486208191951ea249c448e8c6'
RAPID_OFFICIAL = 'https://www.oncehuman.game/news/update/20250521/40780_1235763.html'
VANGUARD_SOURCE = 'https://www.oncehuman.game/news/devBlog/20241123/40781_1195665.html'
FIELD_SOURCE = 'https://www.oncehuman.game/news/official/20260513/40779_1300125.html'


def _finite_roots(hits, chances, *, first_guaranteed=False):
    """Exact state propagation for independent root trials within one burst."""
    weights = [1.0, 0.0, 0.0, 0.0, 0.0]
    expected = first = 0.0
    for hit in range(hits):
        following = [0.0] * 5
        for stacks, weight in enumerate(weights):
            chance = 1.0 if hit == 0 and first_guaranteed else chances[stacks]
            if hit == 0:
                first += weight * chance
            expected += weight * chance
            following[stacks] += weight * (1 - chance)
            following[min(stacks + 1, 4)] += weight * chance
        weights = following
    return expected, first


def selected_magazine(slots, *, active_weapon_slot='primary', base_chance=None,
                      landed_hits=40, use_unlinked_shock17=False):
    """Selected-plan event sensitivity, never a damage or owned-row contribution."""
    if active_weapon_slot not in ('primary', 'secondary', 'melee'):
        raise ValueError('Invalid active weapon slot')
    weapon = slots.get(active_weapon_slot) or {}
    if weapon.get('catalog_id') != 'weapon:aug-electron-cloud':
        return None
    if isinstance(landed_hits, bool) or not isinstance(landed_hits, int) or not 1 <= landed_hits <= 200:
        raise ValueError('Magazine preview needs 1–200 landed hits')
    profile = weapon.get('calibration_profile') or {}
    style = profile.get('style') or ''
    shock = (weapon.get('mod_id') == 'mod:weapon_mod:shock-rampage-power-surge'
             and weapon.get('mod_level') == 17)
    if not shock and style != 'Vanguard Style':
        return None
    if not isinstance(use_unlinked_shock17, bool):
        raise ValueError('Source activation assumption must be true or false')
    summary = {
        'weapon': weapon.get('catalog_id'), 'tier': weapon.get('tier'),
        'stars': weapon.get('stars'), 'active_weapon_slot': active_weapon_slot,
        'mod_id': weapon.get('mod_id'), 'mod_level': weapon.get('mod_level'),
        'calibration_style': style, 'calibration_source': profile.get('source_ref'),
        'calibration_observed_effects': profile.get('fixed_effects'),
        'landed_hits': landed_hits, 'saved_effective_rows_added': 0,
        'full_damage_or_dps': None, 'status': 'enter_base_chance',
        'sources': {'shock17_frame': SHOCK17_FRAME if shock else None,
                    'shock_core': SHOCK_RAMPAGE if shock else None,
                    'rapid_official_2025': RAPID_OFFICIAL if style == 'Rapid Shot Style' else None,
                    'vanguard_documentary': VANGUARD_SOURCE if style == 'Vanguard Style' else None,
                    'aug_field': FIELD_SOURCE},
        'warnings': ['Independent Bernoulli root trials, one landed eligible hit per trial, one orb spawned per eligible root and no Mayfly are hypothetical. Current RNG and orb collisions are unknown.',
                     'Ordinary Power Surge is not multiplied by AUG field uptime. Spawned orbs are not damage or DPS.']}
    if style == 'Rapid Shot Style':
        # Source-specific crafting proposals, not a universal style default or
        # proof that either blueprint was installed on this saved weapon.
        observed = str(profile.get('fixed_effects') or '')
        found = re.search(r'Fire Rate\s*\+\s*(\d+(?:\.\d+)?)%', observed, re.I)
        saved_percent = float(found.group(1)) if found else None
        if saved_percent is not None and 0 <= saved_percent <= 200:
            base_rpm, illustrative_mag = 720.0, 40
            saved_rpm = base_rpm * (1 + saved_percent / 100)
            proposed_rpm = base_rpm * 1.20
            summary['rapid_style_evidence'] = {
                'saved_fire_rate_percent': saved_percent,
                'saved_effects_raw': observed,
                'saved_blueprint_rarity': profile.get('rarity'),
                'standalone_blueprint_rarity': 'gold',
                'both_are_candidate_blueprints': True,
                'saved_source_ref': profile.get('source_ref'),
                'saved_source_is_oct24_screenshot': profile.get('source_ref') == 'libfile_5e9d7ef914648191bd61b1bd3caa68ec',
                'saved_source_image': 'image(20261024-105529).png' if profile.get('source_ref') == 'libfile_5e9d7ef914648191bd61b1bd3caa68ec' else None,
                'standalone_blueprint_source_ref': 'libfile_2ddcabd50f60819187d35ddc0e411389',
                'standalone_source_image': 'image(20261025-080153).png',
                'standalone_installed_on_saved_weapon': False,
                'official_release_source': RAPID_OFFICIAL,
                'official_release_date': '2025-05-21',
                'illustrative_uncalibrated_source': 'libfile_b01c1d5ded9081918892fbd7b7f674b7',
                'illustrative_uncalibrated_tier_and_stars': 'Tier V, five filled stars; not the selected Tier IV six-star weapon',
                'illustrative_base_rpm': base_rpm,
                'illustrative_magazine': illustrative_mag,
                'saved_scenario_rpm': saved_rpm,
                'standalone_20_percent_scenario_rpm': proposed_rpm,
                'saved_first_to_last_seconds': (illustrative_mag - 1) / (saved_rpm / 60),
                'standalone_first_to_last_seconds': (illustrative_mag - 1) / (proposed_rpm / 60),
                'conflict': abs(saved_percent - 20) > 1e-9,
                'saved_profile_changed': False,
            }
    if shock and not use_unlinked_shock17:
        summary['status'] = 'unlinked_source_requires_opt_in'
        summary['warnings'].append('The Lv17 screenshot is not linked to Personal progress. Its +6% trigger row and +5% stack core are excluded until expressly previewed.')
        return summary
    if base_chance is None:
        return summary
    if isinstance(base_chance, bool) or not isinstance(base_chance, (int, float)) or not math.isfinite(base_chance) or not 0 <= base_chance <= 1:
        raise ValueError('Enter an assumed base Power Surge chance from 0 to 1')
    if shock:
        chances = [min(1.0, base_chance * (1 + .06 + .05 * s)) for s in range(5)]
        cold, first = _finite_roots(landed_hits, chances)
        warm = landed_hits * chances[4]
        summary.update(status='conditional_unlinked_source',
            cold_expected_roots=cold, warm_four_stacks_expected_roots=warm,
            first_hit_root_probability=first,
            cold_per_stack_chances=chances,
            cold_orbs_field_before_first_ps=cold,
            cold_orbs_ps_before_field=cold-first,
            warm_orbs_field_before_first_ps=warm,
            warm_orbs_ps_before_field=warm-chances[4])
        summary['warnings'].append('Cold starts at zero stacks; each successful root adds one stack after its roll. Warm assumes four stacks for every hit. No stack expiry during this burst is a sensitivity assumption, not a guaranteed bound.')
        summary['warnings'].append('The observed +6% trigger row is assumed active and relative-additive with the core; Tech, bucket order and Shiny status are unverified. Screenshot values remain outside saved effective rows.')
        if style == 'Vanguard Style':
            # Empty-reload guarantee replaces the first root roll. A successful
            # root then advances the Shock stack after that hit in this branch.
            armed_cold, armed_first = _finite_roots(landed_hits, chances, first_guaranteed=True)
            armed_warm = 1 + (landed_hits - 1) * chances[4]
            summary.update(status='conditional_unlinked_source_plus_vanguard',
                armed_cold_expected_roots=armed_cold,
                armed_warm_four_stacks_expected_roots=armed_warm,
                armed_cold_orbs_field_before_first_ps=armed_cold,
                armed_cold_orbs_ps_before_field=armed_cold-armed_first)
            summary['warnings'].append('Combined Vanguard + Shock branch assumes an observed empty reload before the burst. The guaranteed first root replaces its ordinary chance and adds one Shock stack after its roll; the actual cross-effect order is unverified.')
    else:
        chances = [base_chance] * 5
        unarmed, first = _finite_roots(landed_hits, chances)
        armed, armed_first = _finite_roots(landed_hits, chances, first_guaranteed=True)
        summary.update(status='conditional_saved_calibration',
            unarmed_expected_roots=unarmed, armed_after_empty_reload_expected_roots=armed,
            unarmed_orbs_field_before_first_ps=unarmed,
            unarmed_orbs_ps_before_field=unarmed-first,
            armed_orbs_field_before_first_ps=armed,
            armed_orbs_ps_before_field=armed-armed_first)
        summary['warnings'].append('An empty reload must be observed before using the armed branch. The guaranteed next shot replaces, rather than adds to, its ordinary root chance; initial full magazine is not proof of arming.')
    summary['base_chance_assumed'] = base_chance
    return summary
