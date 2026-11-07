"""Read-only published calculator reference build, separate from game DPS."""
from __future__ import annotations

import math

import catalog
import public_catalog_detail
import published_calculator_adapter as adapter
import published_reference_identity
import published_item_tier


DIRECT_POOLS = {'Weapon DMG': 'weapon', 'All DMG Boost': 'all',
                'Magazine Capacity': 'magazine', 'Fire Rate': 'fire_rate',
                'Reload Efficiency': 'reload_efficiency'}
TARGET_POOLS = {'Damage against enemies': 'enemy_damage'}
PACKET_POOLS = {'Crit DMG': 'crit', 'Weakspot DMG': 'weakspot',
                'Status DMG': 'status', 'Elemental DMG': 'elemental'}
UTILITY_LINES = {'Max HP', 'Nonplayer Front Damage Taken',
                 'Dmg Reduction Against Deviants', 'Dmg Reduction When Hit',
                 'Damage reduction against Deviants'}
ARMOR_SLOTS = {'helmet', 'mask', 'chest', 'gloves', 'pants', 'boots'}
PUBLISHED_ARMOR_SLOT = {'chest': 'top'}


def _upgrade(choice):
    result = {}
    for name, default in (('stars', 1), ('tier', 1), ('calibration', 0)):
        value = choice.get(name, default)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f'{name} must be a whole number')
        result[name] = value
    return result


def _caller_packet_scenario(weapon_id, entered):
    """Accept a named direct-packet hypothesis without importing a weapon baseline."""
    if not isinstance(entered, dict) or entered.get('assume_direct_body_damage_per_projectile') is not True:
        raise ValueError('Entered packet needs an explicit per-projectile damage hypothesis')
    scope = entered.get('baseline_bonus_scope')
    if scope not in ('before_selected_effects', 'after_selected_effects_direct_only'):
        raise ValueError('Entered direct damage, RPM, magazine and reload must be before selected weapon, gear, mod and set effects; already-buffed values would double count them')
    included = entered.get('included_effect_ids')
    if scope == 'after_selected_effects_direct_only':
        if (not isinstance(included, list) or not included or len(included) > 20 or
                any(not isinstance(value, str) or not value or len(value) > 160 for value in included) or
                len(set(included)) != len(included)):
            raise ValueError('Already-buffed direct-only replay needs a nonempty unique list of included selected item IDs')
    elif included is not None:
        raise ValueError('Pre-effect packet cannot declare already-included selected effects')
    def positive(name, maximum):
        value = entered.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 < value <= maximum:
            raise ValueError(f'Enter positive {name} at most {maximum}')
        return value
    damage = positive('direct_body_damage_per_projectile', 10000000)
    projectiles = positive('projectiles_per_shot', 100)
    magazine = positive('magazine_capacity', 1000000)
    if int(projectiles) != projectiles or int(magazine) != magazine:
        raise ValueError('Projectile and magazine counts must be whole numbers')
    stats = {'damage_per_projectile': damage,
             'projectiles_per_shot': int(projectiles),
             'fire_rate': positive('rpm', 100000),
             'magazine_capacity': int(magazine),
             'reload_time_seconds': positive('reload_seconds', 120),
             'crit_rate_percent': None, 'crit_damage_percent': None,
             'weakspot_damage_percent': None}
    baseline = {'weapon_id': weapon_id, 'canonical_catalog_id': weapon_id,
                'evidence': 'caller_entered_direct_packet_hypothesis',
                'baseline_bonus_scope': scope,
                'included_effect_ids': included if scope == 'after_selected_effects_direct_only' else [],
                'source_url': None, 'stats': stats,
                'name': catalog.ENTRIES[weapon_id]['name']}
    scaled = {'weapon_id': weapon_id, 'stats': dict(stats),
              'damage_multiplier': None,
              'model': 'caller_entered_direct_packet_hypothesis_no_game_basis_claim',
              'unresolved': ['Entered damage is an explicit direct-body per-projectile hypothesis, not current Attack or a sourced weapon page value']}
    return baseline, scaled


def _mods(choices, condition_fractions):
    if not isinstance(choices, list) or len(choices) > 7:
        raise ValueError('Choose at most seven exact mod identities')
    if not isinstance(condition_fractions, dict):
        raise ValueError('Condition fractions must be an object')
    pools = {key: 0.0 for key in (*DIRECT_POOLS.values(), *PACKET_POOLS.values(), *TARGET_POOLS.values())}
    rows, unresolved, seen = [], [], set()
    for choice in choices:
        if not isinstance(choice, dict):
            raise ValueError('Selected mod must be an object')
        identity, level = choice.get('catalog_id'), choice.get('level')
        shiny = choice.get('shiny', False)
        entry = catalog.ENTRIES.get(identity)
        if not entry or entry['kind'] != 'mod' or entry.get('family_only'):
            raise ValueError('Choose an exact selectable mod identity')
        if isinstance(level, bool) or not isinstance(level, int) or not 1 <= level <= 17:
            raise ValueError('Choose each mod level from 1 to 17')
        if not isinstance(shiny, bool) or shiny and level != 17:
            raise ValueError('Shiny mod scenario requires level 17')
        slot = entry['slot']
        if slot in seen:
            raise ValueError(f'Duplicate selected mod slot {slot}')
        seen.add(slot)
        public_rows, coverage, formula_status = public_catalog_detail.calculation_rows(
            identity, level, shiny=shiny)
        if not public_rows:
            unresolved.append(f'{identity}: no source-backed fixed bonus lines for selected level/variant')
        for row in public_rows:
            record = {'catalog_id': identity, 'level': level, 'shiny': shiny,
                      'slot': slot, **row, 'applied_pool': None,
                      'applied_percentage_points': None}
            name = row.get('name') or f'bonus line {row.get("public_bonus_position", "unknown")}'
            pool = DIRECT_POOLS.get(name) or PACKET_POOLS.get(name) or TARGET_POOLS.get(name)
            value = row.get('value_percent')
            maximum = public_catalog_detail.low_hp_maximum(row)
            if maximum is not None:
                value = maximum
                record['model_maximum_percent'] = maximum
                record['model_condition'] = 'low hp'
                unresolved.append(f'{identity}: {name} uses only the published low-HP maximum; entered fraction is a scenario assumption, not a sourced HP curve')
            if name in UTILITY_LINES:
                record['outgoing_damage_role'] = 'defensive_or_hp_utility'
            elif pool is None or value is None or row.get('source_conflict'):
                reason = row.get('calculation_exclusion_reason')
                unresolved.append(f'{identity}: {name} — {reason}' if reason else
                                  f'{identity}: {name} has no supported direct-reference pool or scalar value')
            else:
                condition = 'low hp' if maximum is not None else str(row.get('condition') or '').strip().lower()
                components = row.get('components') or {}
                if (condition == 'attack from behind' and
                        'base_percent' in components and 'behind_extra_percent' in components):
                    fraction = condition_fractions.get(condition)
                    amount = float(components['base_percent'])
                    if fraction is None:
                        unresolved.append(f'{identity}: {name} extra behind-target component needs an entered activity fraction')
                    else:
                        if isinstance(fraction, bool) or not isinstance(fraction, (int, float)) or not math.isfinite(fraction) or not 0 <= fraction <= 1:
                            raise ValueError(f'{condition} fraction must be 0–1')
                        amount += float(components['behind_extra_percent']) * fraction
                elif row.get('conditional_bonus_percent') is not None:
                    fraction = condition_fractions.get(condition)
                    if fraction is None:
                        amount = float(value)
                        record['conditional_extra_unresolved'] = True
                        unresolved.append(f'{identity}: {row["name"]} conditional extra requires an entered {condition} fraction')
                    else:
                        if isinstance(fraction, bool) or not isinstance(fraction, (int, float)) or not math.isfinite(fraction) or not 0 <= fraction <= 1:
                            raise ValueError(f'{condition} fraction must be 0–1')
                        amount = float(value) + float(row['conditional_bonus_percent']) * fraction
                elif condition:
                    fraction = condition_fractions.get(condition)
                    if fraction is None:
                        amount = None
                        unresolved.append(f'{identity}: {row["name"]} requires an entered {condition} activity/magnitude fraction')
                    else:
                        if isinstance(fraction, bool) or not isinstance(fraction, (int, float)) or not math.isfinite(fraction) or not 0 <= fraction <= 1:
                            raise ValueError(f'{condition} fraction must be 0–1')
                        amount = float(value) * fraction
                else:
                    amount = float(value)
                if amount is not None:
                    pools[pool] += amount
                    record['applied_pool'] = pool
                    record['applied_percentage_points'] = amount
            rows.append(record)
        if formula_status == 'blocked' and not public_rows:
            unresolved.append(f'{identity}: fixed-layout formula blocked; legacy or source mapping unresolved')
        if coverage.startswith('published_candidate'):
            unresolved.append(f'{identity}: published slot/suffix value, not exact current-client identity-level observation')
    return pools, rows, list(dict.fromkeys(unresolved))


def build(choice):
    if not isinstance(choice, dict):
        raise ValueError('Published reference build must be an object')
    weapon = choice.get('weapon')
    if not isinstance(weapon, dict):
        raise ValueError('Select a weapon catalog identity')
    weapon_id = weapon.get('catalog_id')
    entry = catalog.ENTRIES.get(weapon_id)
    if not entry or entry['kind'] != 'weapon':
        raise ValueError('Choose one catalog weapon')
    upgrade = _upgrade(weapon)
    mechanics_id, identity_evidence = published_reference_identity.weapon_binding(weapon_id)
    unresolved = []
    page_scenario = weapon.get('item_page_scenario')
    caller_scenario = weapon.get('caller_packet_scenario')
    if page_scenario is not None and caller_scenario is not None:
        raise ValueError('Choose either a sourced item page or an entered direct packet')
    if caller_scenario is not None:
        if upgrade['calibration'] != 0:
            raise ValueError('Entered packet already includes the chosen crafted state; do not scale calibration again')
        baseline, scaled = _caller_packet_scenario(weapon_id, caller_scenario)
        unresolved.extend(scaled['unresolved'])
    elif page_scenario is not None:
        if not isinstance(page_scenario, dict) or page_scenario.get('assume_displayed_damage_per_projectile') is not True:
            raise ValueError('Item-page calculation requires an explicit displayed-damage-per-projectile hypothesis')
        if upgrade['calibration'] != 0:
            raise ValueError('Item-page damage has no sourced calibration scaling')
        baseline, scaled = published_item_tier.explicit_page_scenario(
            weapon_id, upgrade['tier'], stars=upgrade['stars'],
            projectiles_per_shot=page_scenario.get('projectiles_per_shot'),
            reload_seconds=page_scenario.get('reload_seconds'),
            assume_fire_rate_as_rpm=page_scenario.get('assume_fire_rate_as_rpm') is True)
        baseline['baseline_bonus_scope'] = 'source_page_without_selected_build_modifiers'
        unresolved.extend(scaled['unresolved'])
    else:
        try:
            baseline = adapter.load_published_weapon_baseline(adapter.PACKETS, weapon_id)
            scaled = adapter.derive_published_weapon_progression(baseline, **upgrade)
            unresolved.extend(scaled['unresolved'])
        except LookupError:
            baseline = None
            scaled = None
            unresolved.append(f'{weapon_id}: no exact item-ID/tier/star numeric source selected; archived unanchored calculator values are unavailable to the active model')
    pools, mod_rows, mod_gaps = _mods(choice.get('mods') or [],
                                     choice.get('condition_fractions') or {})
    unresolved.extend(mod_gaps)
    if pools['enemy_damage']:
        unresolved.append('Damage against enemies is excluded from this direct-only reference; the timed model requires a named target bucket assumption')
    after_effects = bool(baseline and baseline.get('baseline_bonus_scope') == 'after_selected_effects_direct_only')
    timing = (adapter.derive_timing({'stats': {'rpm': baseline['stats'].get('fire_rate'),
                                               'magazine': baseline['stats'].get('magazine_capacity'),
                                               'reload_seconds': baseline['stats'].get('reload_time_seconds')}},
                                    fire_rate_percent=0 if after_effects else pools['fire_rate'],
                                    magazine_percent=0 if after_effects else pools['magazine'],
                                    reload_efficiency_percent=0 if after_effects else pools['reload_efficiency'])
              if baseline else None)
    if timing:
        unresolved.extend(timing['unresolved'])
    damage = scaled['stats'].get('damage_per_projectile') if scaled else None
    projectiles = baseline['stats'].get('projectiles_per_shot') if baseline else None
    direct_hit = None
    if damage is not None and projectiles is not None:
        direct_hit = (damage * projectiles if after_effects else
                      damage * projectiles * (1 + pools['weapon']/100) * (1 + pools['all']/100))
    else:
        unresolved.append('Published base damage or explicit projectiles per shot is missing')
    direct_firing = (direct_hit * timing['rpm'] / 60
                     if direct_hit is not None and timing and timing['rpm'] is not None else None)
    direct_sustained = (direct_hit * timing['magazine'] / timing['cycle_seconds']
                        if direct_hit is not None and timing and timing['cycle_seconds'] is not None else None)
    table = adapter.load_published_armor_table()
    armors = choice.get('armor') or []
    if not isinstance(armors, list) or len(armors) > 6:
        raise ValueError('Choose at most six armor pieces')
    armor_profiles, armor_seen = [], set()
    for selected in armors:
        if not isinstance(selected, dict):
            raise ValueError('Armor selection must be an object')
        armor_id = selected.get('catalog_id')
        gear = catalog.ENTRIES.get(armor_id)
        if not gear or gear['kind'] != 'armor' or gear.get('slot') not in ARMOR_SLOTS:
            raise ValueError('Choose an exact armor catalog identity and slot')
        if gear['slot'] in armor_seen:
            raise ValueError('Duplicate armor slot')
        armor_seen.add(gear['slot'])
        reference_rarity, rarity_evidence = published_reference_identity.armor_binding(
            armor_id, gear.get('rarity'))
        armor_upgrade = _upgrade(selected)
        if not reference_rarity:
            unresolved.append(f'{armor_id}: rarity missing; published armor row unavailable')
            armor_profiles.append({'catalog_id': armor_id, 'slot': gear['slot'],
                                   'stats': {'hp': None, 'psi_intensity': None,
                                             'pollution_resist': None},
                                   'unresolved': ['rarity missing']})
            continue
        try:
            profile = adapter.armor_stats(table, slot=PUBLISHED_ARMOR_SLOT.get(gear['slot'], gear['slot']),
                                          rarity=reference_rarity, **armor_upgrade)
        except LookupError as error:
            unresolved.append(f'{armor_id}: {error}')
            profile = {'slot': gear['slot'], 'stats': {'hp': None, 'psi_intensity': None,
                                                       'pollution_resist': None},
                       'unresolved': [str(error)]}
        profile['published_table_slot'] = profile['slot']
        profile['slot'] = gear['slot']
        profile['catalog_id'] = armor_id
        profile['catalog_rarity'] = gear.get('rarity')
        profile['published_reference_rarity'] = reference_rarity
        profile['rarity_conflict'] = gear.get('rarity') != reference_rarity
        profile['rarity_evidence'] = rarity_evidence
        profile['reference_scope'] = ('exact blueprint identity; only directly recorded Tier 1 pollution is retained until raw item HP/Psi is reimported'
                                      if rarity_evidence else 'catalog rarity only; generic slot/rarity numbers were removed')
        if rarity_evidence:
            profile['pollution_source_conflict'] = rarity_evidence['pollution_note']
            profile['stats']['pollution_resist'] = (
                rarity_evidence['tier1_pollution_resist']
                if armor_upgrade == {'stars': 1, 'tier': 1, 'calibration': 0} else None)
            if profile['stats']['pollution_resist'] is None:
                profile['unresolved'].append('higher-upgrade pollution resistance conflicts with the exact blueprint Tier 1 page')
        armor_profiles.append(profile)
        unresolved.extend(f'{armor_id}: {note}' for note in profile['unresolved'])
    armor_psi = adapter.sum_armor_psi(armor_profiles)
    armor_hp = (sum(row['stats']['hp'] for row in armor_profiles)
                if armor_profiles and all(row['stats']['hp'] is not None for row in armor_profiles)
                else None)
    if after_effects:
        selected_ids = {weapon_id} | {row['catalog_id'] for row in choice.get('mods') or []} | {row['catalog_id'] for row in armors}
        unknown_ids = set(baseline['included_effect_ids']) - selected_ids
        if unknown_ids:
            raise ValueError('Included-effect IDs must match selected weapon, mod or armor identities: ' + ', '.join(sorted(unknown_ids)))
    return {'scope': ('Entered after-effect direct-body packet: selected effect state is asserted by the caller and no selected modifiers are applied again; not full build damage'
                      if after_effects else
                      'Exact item-page tier display under explicit damage-unit hypothesis; not owned, equipped or game-verified'
                      if page_scenario is not None else
                      'Published calculator reference scenario; selected catalog items are hypothetical, not owned or equipped'),
            'weapon_id': weapon_id,
            'weapon_mechanics_id': mechanics_id if identity_evidence else weapon_id,
            'weapon_source_native_baseline': baseline,
            'weapon_scaled_reference': scaled, 'timing': timing,
            'selected_mods': [{'catalog_id': row['catalog_id'], 'level': row['level'],
                               'shiny': row.get('shiny', False)}
                              for row in choice.get('mods') or []],
            'selected_mod_rows': mod_rows, 'selected_pools_percent': pools,
            'direct_only': {'reference_hit': direct_hit,
                            'firing_damage_per_second': direct_firing,
                            'reload_cycle_damage_per_second': direct_sustained,
                            'model': ('entered_post_effect_direct_only_no_selected_effect_reapplication' if after_effects else
                                      'explicit_item_page_displayed_damage_per_projectile_hypothesis' if page_scenario is not None else
                                      'published_source_native_damage_per_projectile_times_explicit_projectiles_quarantined_unless_anchored') +
                                     '; no crit, weakspot, status, target or proc'},
            'armor_profiles': armor_profiles,
            'armor_hp_for_supplied_slots': armor_hp,
            'armor_psi': {**armor_psi,
                          'complete_six_slot_build': armor_psi['complete_for_supplied_slots'] and armor_seen == ARMOR_SLOTS},
            'unresolved': list(dict.fromkeys(unresolved)),
            'current_game_verified': False, 'game_winner_established': False,
            'source_notice': ('Entered direct-body snapshot includes the declared selected effect state; direct shots can be replayed without reapplying gear, but crit, procs and full DPS remain unknown'
                              if after_effects else
                              'Exact named item/tier/star page under caller-selected damage-unit and projectile hypothesis; selected blueprint attributes, missing star cells and current-game damage remain unresolved'
                              if page_scenario is not None else
                              'Unanchored calculator values were removed from active numeric data; select an exact item page or enter a named direct-packet scenario')}


def compare(request):
    if not isinstance(request, dict) or set(request) != {'left', 'right'}:
        raise ValueError('Published reference comparison requires left and right builds')
    left, right = build(request['left']), build(request['right'])
    ratios = {}
    for key in ('reference_hit', 'firing_damage_per_second', 'reload_cycle_damage_per_second'):
        old, new = left['direct_only'][key], right['direct_only'][key]
        ratios[key] = new / old if old is not None and new is not None and old > 0 else None
    return {'left': left, 'right': right, 'right_over_left_reference_ratios': ratios,
            'game_winner_established': False,
            'scope': 'Conditional published source-native direct-only comparison; not full weapon, mod, set, status, proc, crit or target DPS'}
