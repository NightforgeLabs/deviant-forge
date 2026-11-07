"""Evidence-bounded AUG Electron Cloud calibration comparison.

Only measured hit/cycle/proc inputs produce damage. Calibration and set tooltip
bonuses are displayed as evidence; their stacking buckets are not guessed.
"""
from __future__ import annotations
import math
import mod_rolls

CALIBRATIONS = {
    'energy': {
        'name': 'Energy Style · gold rifle blueprint',
        'source_ref': 'libfile_a52887f909c481918310b2bac02dc446',
        'observed_effects': [
            'Attack +10%', 'Weapon DMG +42.4%', 'Elemental DMG +17.5%',
            'After taking damage, automatically reload 1 bullet (0.3s cooldown).',
        ],
    },
    'rapid': {
        'name': 'Rapid Shot Style · gold rifle blueprint',
        'source_ref': 'libfile_2ddcabd50f60819187d35ddc0e411389',
        'observed_effects': [
            'Attack −10%', 'Fire Rate +20%', 'Reload Speed +10%',
            'Weapon DMG +40.9%', 'Crit Rate +14.6%',
        ],
    },
}

BASELINE = {
    'weapon': 'AUG - Electron Cloud', 'tier': 5,
    'source_ref': 'libfile_b01c1d5ded9081918892fbd7b7f674b7',
    'source_kind': 'uncalibrated crafting preview; not owned/equipped gun data',
    'visible_stars': 'five filled, one unfilled',
    'damage': 241.0, 'rpm': 720.0, 'magazine': 40,
    'crit_rate': 0.10, 'crit_damage_bonus': 0.25, 'weakspot_damage_bonus': 0.60,
    'plain_firing_dps': 241.0 * 720.0 / 60.0,
    'expected_body_firing_dps_if_crit_bonus': 241.0 * 720.0 / 60.0 * (1 + 0.10 * 0.25),
}

SET_NOTES = [
    '3 Savior, 2 Shelterer and Mayfly Goggles are common to both choices. Measure hits with the same active shield, buffs and target so common effects are already included.',
    'Current catalog describes 2 Shelterer as +8% Elemental DMG and 2 Savior as +10% Weapon/Status DMG while shielded, but these are a March 2026 community snapshot; no extra multiplier is applied.',
    'The Savior shield comes from hitting a target, not necessarily taking damage. Energy ammo return needs observed accepted returns or a measured shot count; cannon hits and shield absorption alone do not prove returns.',
    'Mayfly and AUG field/orb effects are not converted into damage without observed proc and orb rates. The official AUG rule gives a 7-second, 4 m field with at most one active; regeneration refreshes its duration and position, limiting simple trigger multiplication.',
    'Deviation Expert <Violent> Lv14 is not treated as a proven +20% status roll: the current catalog has multiple effect tiers and no verified Lv14 value for this owned instance.',
    'A single dodge fraction removes that share from active firing and reload time. If reload overlaps dodging, enter measured shots over the full fight; uniform ammo-return rate also ignores exact cannon-hit timing.',
]


def number(v, label, low=0, high=None, strict=False):
    if v in (None, ''):
        return None
    if isinstance(v, bool):
        raise ValueError(f'{label} must be a number')
    try:
        n = float(v)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{label} must be a number') from exc
    if not math.isfinite(n) or n < low or (strict and n == low) or (high is not None and n > high):
        raise ValueError(f'{label} is outside the supported range')
    return n


def finite_shots(active_seconds, rpm, magazine, reload_seconds, accepted_return_rate=0):
    """Continuous expected shots over a finite active-time magazine/reload cycle."""
    f = rpm / 60
    r = accepted_return_rate or 0
    if r >= f:
        raise ValueError('Accepted ammo return rate must be lower than firing rate')
    fire_time = magazine / (f - r)
    cycle = fire_time + reload_seconds
    full = math.floor(active_seconds / cycle)
    remaining = active_seconds - full * cycle
    return f * (full * fire_time + min(remaining, fire_time))


def one(label, data, common):
    normal = number(data.get('normal_hit'), f'{label} normal body hit', strict=True)
    rpm = number(data.get('rpm'), f'{label} RPM', strict=True)
    mag = number(data.get('magazine'), f'{label} magazine', strict=True)
    reload_seconds = number(data.get('reload_seconds'), f'{label} reload seconds')
    measured_sps = number(data.get('measured_shots_per_second'), f'{label} measured shots/s', strict=True)
    return_rate = number(data.get('accepted_return_rate'), f'{label} accepted ammo returns/s', 0, 1 / 0.3) if label == 'Energy' else None
    if return_rate is not None and rpm is not None and return_rate >= rpm / 60:
        raise ValueError('Accepted ammo return rate must be lower than the weapon firing rate')
    hit_rate_input = number(common.get('hit_rate'), 'Hit rate', 0, 1)
    hit_rate = hit_rate_input if hit_rate_input is not None else 1.0
    fight_input = common.get('fight_seconds')
    fight_seconds = number(300 if fight_input in (None, '') else fight_input, 'Fight seconds', strict=True)
    dodge_fraction = number(common.get('dodge_fraction'), 'Dodge downtime fraction', 0, 1)
    active_seconds = fight_seconds * (1 - dodge_fraction) if dodge_fraction is not None else None
    def distribution_value(key):
        chosen=data.get(key)
        return common.get(key) if chosen in (None,'') else chosen
    crit_rate = number(distribution_value('crit_rate'), 'Crit fraction', 0, 1)
    weak_rate = number(distribution_value('weak_rate'), 'Weakspot fraction', 0, 1)
    joint = number(distribution_value('crit_weak_fraction'), 'Crit and weakspot overlap', 0, 1)
    if normal is not None and rpm is None and measured_sps is None and data.get('measured_shots_in_fight') in (None, ''):
        raise ValueError(f'{label} needs RPM or measured shots/s for a damage rate')
    if measured_sps is not None:
        shots = measured_sps
        shot_source = 'measured firing-cycle shots/s; may include reload and auto-return'
    elif rpm is not None and mag is not None and reload_seconds is not None:
        firing_rate = rpm / 60
        accepted = return_rate or 0
        if accepted >= firing_rate:
            raise ValueError('Accepted ammo return rate must be lower than the weapon firing rate')
        shots = firing_rate * mag / (mag + reload_seconds * (firing_rate - accepted))
        shot_source = ('scenario with measured accepted ammo returns/s during firing' if accepted else
                       'modeled magazine cycle with entered reload; accepted returns assumed zero if unentered')
    elif rpm is not None:
        shots = rpm / 60
        shot_source = 'theoretical firing rate only; reload omitted'
    else:
        shots = None
        shot_source = 'shots/s missing'
    weighted = False
    expected_hit = normal
    if any(x is not None for x in (crit_rate, weak_rate, joint)):
        if crit_rate is None or weak_rate is None or joint is None:
            raise ValueError('Enter crit fraction, weakspot fraction and their overlap together')
        if joint < max(0, crit_rate + weak_rate - 1)-1e-9 or joint > min(crit_rate, weak_rate)+1e-9:
            raise ValueError('Crit and weakspot overlap is inconsistent with the entered fractions')
        crit = number(data.get('crit_hit'), f'{label} crit hit', strict=True) if crit_rate > joint else 0
        weak = number(data.get('weakspot_hit'), f'{label} weakspot hit', strict=True) if weak_rate > joint else 0
        both = number(data.get('crit_weak_hit'), f'{label} crit weakspot hit', strict=True) if joint > 0 else 0
        if None not in (normal, crit, weak, both):
            expected_hit = ((1 - crit_rate - weak_rate + joint) * normal
                            + (crit_rate - joint) * crit
                            + (weak_rate - joint) * weak
                            + joint * both)
            weighted = True
        elif normal is not None:
            expected_hit = None
    bullet = shots * hit_rate * expected_hit if shots is not None and expected_hit is not None else None
    proc_rate = number(data.get('proc_events_per_second'), f'{label} Power Surge events/s')
    proc_damage = number(data.get('proc_damage_per_event'), f'{label} Power Surge damage/event')
    orb_rate = number(data.get('orb_events_per_second'), f'{label} orb damage events/s')
    orb_damage = number(data.get('orb_damage_per_event'), f'{label} orb damage/event')
    surge = proc_rate * proc_damage if proc_rate is not None and proc_damage is not None else None
    orb = orb_rate * orb_damage if orb_rate is not None and orb_damage is not None else None
    known_values = [x for x in (bullet, surge, orb) if x is not None]
    known = sum(known_values) if known_values else None
    return_resolved = label != 'Energy' or return_rate is not None or measured_sps is not None or data.get('measured_shots_in_fight') not in (None, '')
    complete = weighted and hit_rate_input is not None and return_resolved and all(x is not None for x in (bullet, surge, orb)) and shot_source != 'theoretical firing rate only; reload omitted'
    missing = []
    if hit_rate_input is None:
        missing.append('observed hit rate; active-rate display currently assumes every shot hits')
    if bullet is None:
        missing.append('matched-target normal/crit/weakspot hit values and firing cycle')
    elif not weighted:
        missing.append('crit fraction, weakspot fraction and their overlap (enter zeroes if none)')
    if not return_resolved:
        missing.append('accepted Energy returns/s: enter observed 0 if none, or use measured shots')
    if shot_source == 'theoretical firing rate only; reload omitted':
        missing.append('reload seconds or measured shots/s for sustained damage')
    if surge is None:
        missing.append('observed Power Surge events/s and damage/event')
    if orb is None:
        missing.append('observed orb damage events/s and damage/event')
    measured_fight_shots = number(data.get('measured_shots_in_fight'), f'{label} measured shots in fight')
    if measured_fight_shots is not None:
        fight_shots = measured_fight_shots
        fight_shot_source = 'measured shots over the full fight, including dodge/reload/returns'
    elif active_seconds is not None and measured_sps is not None:
        fight_shots = measured_sps * active_seconds
        fight_shot_source = 'measured active-time shots/s × active seconds'
    elif active_seconds is not None and None not in (rpm, mag, reload_seconds):
        fight_shots = finite_shots(active_seconds, rpm, mag, reload_seconds, return_rate)
        fight_shot_source = 'continuous expected shot exposure over active-time magazine/reload cycles; fractional opportunities and accepted returns evenly averaged, not discrete events'
    else:
        fight_shots = None
        fight_shot_source = 'fight shot exposure unresolved'
    fight_bullet = fight_shots * hit_rate * expected_hit if fight_shots is not None and expected_hit is not None else None
    proc_count = number(data.get('proc_events_in_fight'), f'{label} Power Surge events in fight')
    orb_count = number(data.get('orb_events_in_fight'), f'{label} orb events in fight')
    fight_surge = (0.0 if proc_count == 0 else
                   (proc_count if proc_count is not None else proc_rate * active_seconds) * proc_damage
                   if proc_damage is not None and
                   (proc_count is not None or proc_rate is not None and active_seconds is not None) else None)
    fight_orb = (0.0 if orb_count == 0 else
                 (orb_count if orb_count is not None else orb_rate * active_seconds) * orb_damage
                 if orb_damage is not None and
                 (orb_count is not None or orb_rate is not None and active_seconds is not None) else None)
    fight_known_values = [x for x in (fight_bullet, fight_surge, fight_orb) if x is not None]
    fight_known = sum(fight_known_values) if fight_known_values else None
    fight_complete = weighted and hit_rate_input is not None and return_resolved and all(x is not None for x in (fight_bullet, fight_surge, fight_orb))
    fight_missing = []
    if fight_shots is None:fight_missing.append('dodge fraction and full firing cycle, or measured shots in the 300s fight')
    if fight_bullet is None:fight_missing.append('measured bullet hit values and full hit distribution')
    elif not weighted:fight_missing.append('crit fraction, weakspot fraction and their overlap (enter zeroes if none)')
    if fight_surge is None:fight_missing.append('Power Surge damage-event count or active-time rate, plus damage/event')
    if fight_orb is None:fight_missing.append('orb damage-event count or active-time rate, plus damage/event')
    if hit_rate_input is None:fight_missing.append('observed hit rate')
    if not return_resolved:fight_missing.append('accepted Energy returns/s: enter observed 0 if none, or measured full-fight shots')
    return {
        'fight_seconds': fight_seconds, 'active_seconds': active_seconds,
        'shots_in_fight': fight_shots, 'fight_shot_source': fight_shot_source,
        'bullet_damage_in_fight': fight_bullet, 'power_surge_damage_in_fight': fight_surge,
        'orb_damage_in_fight': fight_orb, 'known_fight_damage': fight_known,
        'fight_complete': fight_complete, 'fight_total_damage': fight_known if fight_complete else None,
        'fight_average_dps': fight_known / fight_seconds if fight_complete else None,
        'fight_missing': fight_missing,
        'shots_per_second': shots, 'shot_source': shot_source, 'accepted_return_rate': return_rate, 'return_resolved': return_resolved,
        'expected_bullet_hit': expected_hit, 'bullet_hit_mode': 'weighted measured hits' if weighted else 'normal body hit only' if expected_hit is not None else 'unknown',
        'bullet_dps': bullet, 'power_surge_dps': surge, 'orb_dps': orb,
        'known_component_sum': known, 'complete': complete,
        'total_dps': known if complete else None, 'missing': missing,
    }


def illustrative_calibration_ratio(common):
    """A clearly hypothetical bucket sensitivity, never a measured DPS claim."""
    x = number(common.get('other_weapon_damage_percent'), 'Other Weapon DMG bonus %')
    base_crit = number(common.get('base_crit_rate'), 'Base crit rate', 0, 1)
    crit_damage = number(common.get('crit_damage_bonus_percent'), 'Crit damage bonus %')
    if (base_crit is None) != (crit_damage is None):
        raise ValueError('Enter both current crit rate and crit damage, or leave both blank to use the crafting preview only')
    shield_input = number(common.get('shield_uptime_fraction'), 'Shield uptime fraction', 0, 1)
    shield = 0 if shield_input is None else shield_input
    elemental_other = number(common.get('other_elemental_damage_percent'), 'Other Elemental DMG bonus %')
    elemental_other = 0 if elemental_other is None else elemental_other / 100
    other = 0 if x is None else x / 100
    # This algebra is an optional assumption, not a verified game stacking rule.
    e = 1.10 * (1 + other + .424 + .10 * shield)
    r = .90 * (1 + other + .409 + .10 * shield)
    crit_used = base_crit is not None and crit_damage is not None
    if crit_used:
        d = crit_damage / 100
        e *= 1 + base_crit * d
        r *= 1 + min(1, base_crit + .146) * d
    per_hit_ratio = e / r
    # A second preview-crit sensitivity uses the screenshot's 10% / 25% when
    # the user has not entered current equipped crit values. It remains hypothetical.
    preview_crit_rate = BASELINE['crit_rate'] if base_crit is None else base_crit
    preview_crit_damage = BASELINE['crit_damage_bonus'] if crit_damage is None else crit_damage / 100
    preview_e = 1.10 * (1 + other + .424 + .10 * shield) * (1 + preview_crit_rate * preview_crit_damage)
    preview_r = .90 * (1 + other + .409 + .10 * shield) * 1.20 * (1 + min(1, preview_crit_rate + .146) * preview_crit_damage)
    return {
        'base_reference': BASELINE,
        'shield_uptime_used_for_illustration': shield_input,
        'savior_two_piece_source_status': 'March 2026 community catalog, current tooltip not verified',
        'shelterer_two_piece_source_status': 'March 2026 community catalog, current tooltip not verified',
        'energy_illustrative_hit': BASELINE['damage'] * 1.10 * (1 + other + .424 + .10 * shield),
        'rapid_illustrative_hit': BASELINE['damage'] * .90 * (1 + other + .409 + .10 * shield),
        'energy_fully_shielded_hit_scenario': BASELINE['damage'] * 1.10 * (1 + other + .424 + .10),
        'rapid_fully_shielded_hit_scenario': BASELINE['damage'] * .90 * (1 + other + .409 + .10),
        'energy_shock_elemental_factor_scenario': 1 + elemental_other + .08 + .175,
        'rapid_shock_elemental_factor_scenario': 1 + elemental_other + .08,
        'energy_to_rapid_elemental_factor_ratio_scenario': (1 + elemental_other + .08 + .175) / (1 + elemental_other + .08),
        'energy_illustrative_rpm': BASELINE['rpm'],
        'rapid_illustrative_rpm': BASELINE['rpm'] * 1.20,
        'energy_illustrative_plain_fire_dps': BASELINE['damage'] * 1.10 * (1 + other + .424 + .10 * shield) * BASELINE['rpm'] / 60,
        'rapid_illustrative_plain_fire_dps': BASELINE['damage'] * .90 * (1 + other + .409 + .10 * shield) * BASELINE['rpm'] * 1.20 / 60,
        'energy_illustrative_crit_body_fire_dps': BASELINE['damage'] * BASELINE['rpm'] / 60 * preview_e,
        'rapid_illustrative_crit_body_fire_dps': BASELINE['damage'] * BASELINE['rpm'] / 60 * preview_r,
        'crit_scenario_source': 'Tier V uncalibrated crafting preview 10% crit / 25% crit damage unless both values explicitly overridden',
        'energy_to_rapid_per_hit_ratio': per_hit_ratio,
        'rapid_sustained_shot_rate_ratio_needed_to_tie_bullet': per_hit_ratio,
        'energy_to_rapid_bullet_stream_ratio': per_hit_ratio / 1.20,
        'energy_relative_percent': (per_hit_ratio / 1.20 - 1) * 100,
        'other_weapon_damage_percent': x,
        'crit_sensitivity_applied': crit_used,
        'assumptions': [
            'Illustrative only: Attack and Weapon DMG multiply as separate buckets; other Weapon DMG adds to the same bucket; Rapid +20% fire rate applies uncapped.',
            'When other Weapon DMG or shield uptime is blank, zero is used only for this algebraic example, not asserted as the real build value.',
            'Optional 2 Savior +10% Weapon/Status while shielded is treated as a shared additive Weapon DMG bonus scaled by entered shield uptime. The current set tooltip and uptime are unverified.',
            'Optional 2 Shelterer +8% Elemental and Energy +17.5% Elemental are combined in one assumed elemental bucket; their factor ratio is not Power Surge DPS without proc damage and timing.',
            'Crit uses 1 + rate × bonus only if both base rate and bonus are entered; Rapid receives +14.6 percentage points, subject to a 100% cap.',
            'The 241 DMG and 720 RPM base are from an uncalibrated Tier V crafting preview with five filled stars; they are not an equipped live build.',
            'No reload, Energy ammo return, Power Surge, orb, Mayfly, shield uptime, weakspot, target mitigation or 300s timing is included.',
        ],
    }


def mod_calibration_sensitivity(modifiers, common=None):
    """Illustrative comparison from the uncalibrated Tier V crafting preview.

    Typed mod rolls enter distinct components. This never re-applies rolls to
    measured, already-equipped hit values and cannot establish a total winner.
    """
    common=common or {}
    if not modifiers:return None
    reference_reload=number(common.get('reference_reload_seconds'),'pre-mod reference reload seconds')
    preview=mod_rolls.scenario(modifiers,{
        'base_origin':'pre_mod_unbuffed','base_direct_hit':BASELINE['damage'],
        'tech_policy':common.get('tech_policy','exclude_unknown'),
        'all_damage_model':common.get('all_damage_model','exclude_unverified'),
        'rpm':BASELINE['rpm'],'magazine':BASELINE['magazine'],
        'reload_seconds':reference_reload,
        'elemental_event_damage':common.get('pre_mod_elemental_event_damage'),
        'status_event_damage':common.get('pre_mod_status_event_damage'),
        'elemental_events_per_second':common.get('elemental_events_per_second'),
        'status_events_per_second':common.get('status_events_per_second')})
    p=preview['modifiers']['percent_by_type']
    all_factor=1+p['all_damage_boost_percent']/100
    bounds=preview['component_results']['magazine_bounds']
    rows={}
    for name,attack,weapon,fire_rate,elemental,reload_speed in (
        ('energy',1.10,.424,1.0,.175,1.0),('rapid',.90,.409,1.20,0.0,1.10)):
        hit=BASELINE['damage']*attack*(1+weapon+p['weapon_damage_percent']/100)*all_factor
        rpm=BASELINE['rpm']*fire_rate
        reload_time=(reference_reload/reload_speed)/(1+p['reload_efficiency_percent']/100) if reference_reload is not None else None
        sustained=None
        if reload_time is not None:
            sustained={policy:hit*(rpm/60)*mag/(mag+(rpm/60)*reload_time)
                       for policy,mag in bounds.items()}
        rows[name]={'plain_direct_hit':hit,'rpm_assumption':rpm,'magazine_bounds':bounds,
                    'plain_firing_dps':hit*rpm/60,'reference_reload_seconds_assumption':reload_time,
                    'reload_efficiency_roll_percent':p['reload_efficiency_percent'],
                    'sustained_plain_direct_dps_bounds':sustained,
                    'elemental_event_factor':all_factor*(1+p['elemental_damage_percent']/100+elemental),
                    'status_event_factor_without_set_or_calibration':all_factor*(1+p['status_damage_percent']/100)}
    return {'tier_v_source':BASELINE['source_ref'],'source_kind':BASELINE['source_kind'],
            'typed_modifiers':modifiers,'aggregate':preview['modifiers'],
            'pre_calibration_component_scenario':preview,'calibrations':rows,
            'winner_established':False,'total_dps':None,
            'assumptions':[preview['modifiers']['stacking_assumption']+' Attack and Weapon DMG placement remains a model assumption.',
                           'Energy Elemental +17.5% and typed Elemental DMG sum in one assumed elemental bucket for an isolated event scenario; proc rate, Psi and orb damage are not inferred.',
                           'Rapid +20% Fire Rate is applied uncapped for this scenario. Crit Rate +14.6 points is excluded from plain noncrit bullet results.',
                           'If reload is entered, Rapid +10% Reload Speed is modeled as time divided by 1.10. The official May 2025 formula applies that division to Reload Efficiency, while the photographed roll says Reload Speed; this label equivalence is unverified. Source: https://www.oncehuman.game/news/update/20250521/40780_1235763.html',
                           'A source-checked Reload Efficiency mod roll divides modeled final reload time by (1 + roll fraction) under that official May 2025 rule; this is distinct from the Rapid Reload Speed label.',
                           'Magazine rounding is bounded by floor and ceil. Missing reload means sustained direct DPS remains unknown.',
                           'Measured hit values in the main comparison already include equipped effects and are never multiplied by these rolls again.',
                           'No total winner follows without set, shield, Power Surge, orb, status event, target and timing evidence.']}


def compare(data):
    if not isinstance(data, dict):
        raise ValueError('Comparison input must be an object')
    common = data.get('common') or {}
    if not isinstance(common, dict):
        raise ValueError('Common encounter inputs must be an object')
    energy = data.get('energy') or {}
    rapid = data.get('rapid') or {}
    if not isinstance(energy, dict) or not isinstance(rapid, dict):
        raise ValueError('Calibration inputs must be objects')
    e = one('Energy', energy, common)
    r = one('Rapid Shot', rapid, common)
    paired = [k for k in ('bullet_dps', 'power_surge_dps', 'orb_dps')
              if e[k] is not None and r[k] is not None]
    delta = sum(e[k] - r[k] for k in paired) if paired else None
    both_complete = e['complete'] and r['complete']
    paired_fight = [k for k in ('bullet_damage_in_fight', 'power_surge_damage_in_fight', 'orb_damage_in_fight')
                    if e[k] is not None and r[k] is not None]
    fight_delta = sum(e[k] - r[k] for k in paired_fight) if paired_fight else None
    both_fight_complete = e['fight_complete'] and r['fight_complete']
    return {
        'calibrations': CALIBRATIONS, 'tier_v_uncalibrated_reference': BASELINE, 'common_loadout_notes': SET_NOTES,
        'illustrative_model': illustrative_calibration_ratio(common),
        'typed_mod_sensitivity':mod_calibration_sensitivity(data.get('typed_modifiers') or [],common),
        'available_evidence': ['Energy and Rapid Shot blueprint percentages from two game screenshots', 'Tier V uncalibrated AUG crafting preview: 241 DMG, 720 RPM, 40 MAG, 10% crit, 25% crit damage', '3 Savior / 2 Shelterer / Mayfly loadout description', 'AUG field refresh/max-one rule in official May 2026 developer note'],
        'missing_for_verified_tier_v_prediction': ['resulting equipped Tier V damage/RPM/reload under each calibration and actual shield/buff context', 'current crit and weakspot probabilities and damage by target', 'validated Attack/Weapon DMG/Elemental stacking buckets with the set and mod', 'observed accepted Energy ammo returns during incoming cannon fire', 'Power Surge and orb event frequency and damage under the 7-second field'],
        'energy': e, 'rapid': r,
        'paired_components': paired, 'known_delta_energy_minus_rapid': delta,
        'sustained_winner': ('energy' if delta > 0 else 'rapid' if delta < 0 else 'tie') if both_complete else None,
        'paired_fight_components': paired_fight, 'known_fight_delta_energy_minus_rapid': fight_delta,
        'winner': ('energy' if fight_delta > 0 else 'rapid' if fight_delta < 0 else 'tie') if both_fight_complete else None,
        'fight_break_even': {
            'energy_extra_damage_to_tie_rapid': max(0.0, -fight_delta) if fight_delta is not None else None,
            'rapid_extra_damage_to_tie_energy': max(0.0, fight_delta) if fight_delta is not None else None,
        },
        'break_even': {
            'energy_extra_dps_to_tie_rapid_known': max(0.0, -delta) if delta is not None else None,
            'rapid_extra_dps_to_tie_energy_known': max(0.0, delta) if delta is not None else None,
            'meaning': 'Additional DPS needed to tie the paired measured components; not a claimed total winner.',
        },
        'equations': {
            'shots_per_second': 'measured shots/s, or f × M / [M + R × (f − r)], where f=RPM/60, M=magazine, R=reload seconds and r=observed accepted ammo returns/s while firing (Energy only; blank=0)',
            'bullet': 'hit rate × shots/s × weighted measured hit; four disjoint hit groups if crit/weakspot shares are entered',
            'power_surge': 'observed Power Surge damage events/s × measured damage/event',
            'orb': 'observed orb damage events/s × measured damage/event',
            'finite_shots': 'For active time T, f=RPM/60 and accepted returns r: fire interval=M/(f-r), cycle=fire interval+reload; count complete cycles and the partial last firing interval.',
            'fight_average': '(finite bullet damage + finite Power Surge damage + finite orb damage) / fight seconds, only when all components are supplied for both choices',
            'total': 'bullet + Power Surge + orb, only when all three are measured for both choices',
        },
    }
