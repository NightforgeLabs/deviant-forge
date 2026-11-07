"""Read-only component comparison for reviewed equipment rows.

The arithmetic is a sensitivity model. It never promotes a conditional model or
an observed damage total to a verified game-wide DPS winner.
"""
from __future__ import annotations

import math
import json
import copy
from pathlib import Path
from itertools import product

import catalog
import combat_projection
import evidence_registry
import suffix_candidates
import mod_core_packet
import mod_core_typed
import public_catalog_detail
import native_direct_hit_graph
import native_combat_labels

ROOT = Path(__file__).resolve().parent
MAIN_RULES = json.loads((ROOT / 'damage_rules.json').read_text())['mod_main_effects']
SET_RULES = [row for row in json.loads((ROOT / 'rules.json').read_text())['rules'] if row.get('system') == 'set']
SOURCE_URLS = {row['id']: row['url'] for row in json.loads((ROOT / 'knowledge.json').read_text())['sources']}

POOLS = {
    'Weapon DMG': 'weapon', 'Crit DMG': 'crit', 'Weakspot DMG': 'weakspot',
    'Elemental DMG': 'elemental', 'Status DMG': 'status',
    'Power Surge DMG': 'power_surge', 'Shock DMG': 'shock',
    'Unstable Bomber DMG': 'unstable_bomber',
    'All DMG Boost': 'all', 'All DMG': 'all',
    'Fire Rate': 'fire_rate', 'Magazine Capacity': 'magazine',
    'Reload Efficiency': 'reload',
}
BRANCHES = ('normal', 'crit', 'weakspot', 'crit_weakspot',
            'status', 'elemental_nonstatus', 'power_surge', 'shock', 'unstable_bomber')
TIMELINE_DAMAGE_POOLS = ('weapon', 'status', 'elemental', 'all', 'crit', 'weakspot')
TYPED_STAT_ROWS = {'weapon_damage_percent': 'Weapon DMG',
                   'status_damage_percent': 'Status DMG',
                   'elemental_damage_percent': 'Elemental DMG',
                   'power_surge_damage_percent': 'Power Surge DMG'}


def _expand_catalog(item, context=None):
    """Fill omitted rows from exact catalog evidence without changing caller data."""
    expanded = dict(item)
    if item.get('items') is not None:
        if not isinstance(item['items'], list):
            raise ValueError('Build items must be a list')
        expanded['items'] = [_expand_catalog(piece, context) if isinstance(piece, dict) else piece
                             for piece in item['items']]
    identity = item.get('catalog_id')
    if identity:
        resolved = catalog.resolve(identity, item.get('level'), shiny=bool(item.get('shiny')))
        entry = resolved['entry']
        expanded.setdefault('name', entry.get('display_name') or entry['name'])
        if entry['kind'] == 'mod' and 'attributes' not in item:
            observed_rows = resolved.get('known_attributes') or []
            public_rows, public_coverage, public_status = (None, None, 'blocked')
            if isinstance(item.get('level'), int) and not isinstance(item.get('level'), bool):
                import public_catalog_detail
                public_rows, public_coverage, public_status = public_catalog_detail.calculation_rows(
                    identity, item['level'], shiny=bool(item.get('shiny')), resolved=resolved)
            candidate = (suffix_candidates.candidate(identity, item.get('level'))
                         if context and context.get('suffix_candidate_opt_in') is True and not item.get('shiny')
                         and not any(row.get('value_percent') is not None for row in observed_rows)
                         else None)
            if candidate:
                expanded['attributes'] = suffix_candidates.attributes(candidate)
                expanded['numeric_coverage'] = 'derived_' + candidate['profile_status'].removeprefix('candidate_')
                expanded['suffix_candidate_profile'] = {'status': candidate['profile_status'],
                    'known_rows': candidate['known_row_count'], 'unknown_rows': len(candidate['rows'])-candidate['known_row_count'],
                    'game_build_version': 'unverified', 'level_obtainability': 'unverified',
                    'ownership_inferred': False}
            elif public_status != 'blocked':
                expanded['attributes'] = public_rows
                expanded['numeric_coverage'] = public_coverage
                expanded['published_bonus_profile'] = {'status': public_status,
                    'source_version': 'published THGL slot/suffix formula plus official level chart',
                    'identity_level_observed': bool(resolved.get('observed_profile') or
                                                    resolved.get('attribute_coverage') == 'complete')}
            else:
                expanded['attributes'] = [dict(row) for row in observed_rows]
                expanded.setdefault('numeric_coverage', resolved.get('attribute_coverage') or 'none')
        if not item.get('main_effect'):
            verified = resolved.get('verified_shiny_main_effect') if item.get('shiny') else None
            expanded['main_effect'] = (verified or {}).get('text') or resolved.get('primary_effect')
    return expanded


def _suffix_candidate_profiles(item):
    found = []
    for piece in [item, *(item.get('items') or [])]:
        if piece.get('suffix_candidate_profile'):
            found.append({'name': piece.get('name'), **piece['suffix_candidate_profile']})
    return found


def _number(value, label, lower=0, upper=1_000_000):
    if isinstance(value, bool):
        raise ValueError(f'{label} must be numeric')
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f'{label} must be numeric') from None
    if not math.isfinite(number) or not lower <= number <= upper:
        raise ValueError(f'{label} outside supported range')
    return number


def _activation(row, context):
    condition = str(row.get('condition') or '').strip().lower()
    if not condition:
        return (1.0, 1.0), 'passive'
    uptime = (context.get('condition_uptime') or {}).get(condition)
    if 'low hp' in condition:
        # Time active and magnitude at a given HP are separate unknowns. A
        # permanent low-HP state does not imply the listed maximum bonus.
        strength = (context.get('condition_strength') or {}).get(condition)
        if uptime is not None:
            uptime = _number(uptime, f'{condition} uptime', 0, 1)
        if strength is not None:
            strength = _number(strength, f'{condition} strength', 0, 1)
        if uptime == 0 or strength == 0:
            return (0.0, 0.0), 'entered inactive or zero-strength low-HP state'
        if uptime is not None and strength is not None:
            return (uptime * strength, uptime * strength), 'entered uptime and magnitude fraction'
        return (0.0, uptime if uptime is not None else strength if strength is not None else 1.0), 'low-HP magnitude or uptime unresolved'
    if uptime is not None:
        value = _number(uptime, f'{condition} uptime', 0, 1)
        return (value, value), 'entered uptime'
    hp = context.get('hp_percent')
    if hp is not None and 'below 30%' in condition:
        hp = _number(hp, 'HP percent', 0, 100)
        value = float(hp < 30)
        return (value, value), 'entered HP condition'
    return (0.0, 1.0), 'unknown uptime; 0–100% range'


def _all_rows(item):
    rows = []
    if len(item.get('items') or []) > 20:
        raise ValueError('At most 20 pieces per alternative')
    for piece in [item, *(item.get('items') or [])]:
        if not isinstance(piece, dict):
            raise ValueError('Build items must be objects')
        for row in piece.get('attributes') or []:
            if not isinstance(row, dict):
                raise ValueError('Reviewed rows must be objects')
            rows.append({'item': piece.get('name'), 'source': piece.get('source'), **row})
    return rows


def _core_effects(item):
    return sorted(str(piece.get('main_effect')) for piece in [item, *(item.get('items') or [])]
                  if piece.get('main_effect'))


def _typed_main_effects(item, context):
    results = []
    order = {'helmet_mod': 0, 'mask_mod': 1, 'gloves_mod': 2,
             'boots_mod': 3, 'chest_mod': 4, 'pants_mod': 5,
             'weapon_mod': 6}
    for piece in [item, *(item.get('items') or [])]:
        identity, level = piece.get('catalog_id'), piece.get('level')
        if identity in catalog.ENTRIES and catalog.ENTRIES[identity]['kind'] == 'mod' and level is not None:
            result = mod_core_typed.evaluate(identity, level,
                shiny=bool(piece.get('shiny')), context=context)
            if result is not None:
                result['slot'] = catalog.ENTRIES[identity]['slot']
                result['item_name'] = piece.get('name') or catalog.ENTRIES[identity]['name']
                results.append(result)
    results.sort(key=lambda row: (order.get(row['slot'], 99), row['catalog_id']))
    return results


def _main_effect_rows(item, context):
    rows, missing = [], []
    for piece in [item, *(item.get('items') or [])]:
        identity, level = piece.get('catalog_id'), piece.get('level')
        if identity in context.get('_exclude_exact_timed_ids', ()):
            continue
        rule = MAIN_RULES.get(f'{identity}:{level}') if identity and level is not None else None
        if not rule:
            if identity in catalog.ENTRIES and catalog.ENTRIES[identity]['kind'] == 'mod' and level is not None:
                compiled, blockers, _binding = mod_core_packet.rows_for(identity, level,
                    shiny=bool(piece.get('shiny')), context=context)
                rows.extend(compiled)
                missing.extend(blockers)
                # Exact typed observations can supply a main-effect stat when
                # the older pool compiler has no binding. Never merge two
                # representations of the same main effect.
                if not compiled:
                    typed = mod_core_typed.evaluate(identity, level,
                        shiny=bool(piece.get('shiny')), context=context)
                    if typed and typed.get('status') == 'observed_typed_output':
                        mapped_typed_stat = False
                        source = (typed.get('source_url') or
                                  'source SHA-256 ' + str(typed.get('source_sha256') or 'unknown'))
                        for index, output in enumerate(typed.get('outputs') or []):
                            name = TYPED_STAT_ROWS.get(output.get('stat')) if output.get('type') == 'stat_pool_delta' else None
                            if (name and output.get('percentage_points') is not None
                                    and not any(output.get(key) is not None for key in
                                                ('event', 'duration_seconds', 'condition', 'stacks'))):
                                rows.append({'name': name,
                                             'value_percent': output['percentage_points'],
                                             'source': source, 'source_sha256': typed.get('source_sha256'),
                                             'source_status': 'unverified_' + str(typed.get('evidence_class')),
                                             'observed_level': typed.get('observed_level'),
                                             'item': piece.get('name'),
                                             'rule_id': f'{identity}:{level}:typed:{index}'})
                                mapped_typed_stat = True
                            elif name and output.get('percentage_points') is not None:
                                missing.append(f'{identity}: timed or conditional typed stat output '
                                               'requires event state before arithmetic')
                        if mapped_typed_stat:
                            missing[:] = [note for note in missing if not note.startswith(
                                f'{identity}: exact-level frame has unverified ordinary-versus-Shiny variant kind; no automatic binding')]
                        missing.extend(f'{identity}: {note}' for note in typed.get('missing') or [])
                        if typed.get('source_warning'):
                            missing.append(f'{identity}: {typed["source_warning"]}')
            elif piece.get('main_effect'):
                missing.append(f'{piece.get("name") or identity}: main-effect arithmetic has no exact-level reviewed rule')
            continue
        shiny = bool(piece.get('shiny'))
        resolved = catalog.resolve(identity, level, shiny=shiny)
        verified = resolved.get('verified_shiny_main_effect' if shiny else 'verified_main_effect')
        if not verified:
            missing.append(f'{piece.get("name") or identity}: main-effect rule is not verified for this {"Shiny" if shiny else "ordinary"} exact level')
            continue
        source = rule.get('source') or rule.get('source_page')
        components = {'weapon_and_status_damage': ('Weapon DMG', 'Status DMG'),
                      'weakspot_direct_hit': ('Weakspot DMG',),
                      'elemental_damage': ('Elemental DMG',),
                      'power_surge_damage': ('Power Surge DMG',),
                      'magazine_capacity': ('Magazine Capacity',),
                      'weapon_damage': ('Weapon DMG',)}.get(rule.get('component'))
        if not components:
            missing.append(f'{identity}: main-effect component is not mapped')
            continue
        if rule.get('kind') in ('flat', 'flat_plus_duration_change'):
            for name in components:
                rows.append({'name': name, 'value_percent': rule['value_percent'],
                             'source': source, 'item': piece.get('name'), 'rule_id': rule['rule_id']})
            if rule['kind'] == 'flat_plus_duration_change':
                missing.append(f'{identity}: status duration changes by {100*(rule["status_duration_multiplier"]-1):g}%; event uptime and refresh are not modeled')
            elif rule.get('uncertainty'):
                missing.append(f'{identity}: {rule["uncertainty"]}')
        elif rule.get('kind') == 'conditional_stacks':
            stacks = (context.get('effect_stacks') or {}).get(identity)
            if stacks is None:
                amount = [0, rule['bonus_per_stack_percent'] * rule['max_stacks']]
                missing.append(f'{identity}: Power Surge stack count and {rule["duration_seconds"]:g}s uptime unresolved')
            else:
                stacks = _number(stacks, 'entered main-effect stacks', 0, rule['max_stacks'])
                if not stacks.is_integer():
                    raise ValueError('Entered main-effect stacks must be whole numbers')
                amount = [stacks * rule['bonus_per_stack_percent']] * 2
            for name in components:
                rows.append({'name': name, 'range_percent': amount,
                             'condition': f'{identity} active stacks', 'source': source,
                             'item': piece.get('name'), 'rule_id': rule['rule_id']})
        elif rule.get('kind') == 'base_plus_counter_modifier':
            for name in components:
                rows.append({'name': name, 'value_percent': rule['base_percent'],
                             'source': source, 'item': piece.get('name'), 'rule_id': rule['rule_id']})
            consumed = context.get('bullets_consumed_in_magazine')
            if consumed is None:
                amount = [0, rule['max_bonus_percent']]
                missing.append(f'{identity}: bullets consumed in current magazine are needed to resolve the rising bonus')
            else:
                consumed = _number(consumed, 'bullets consumed in magazine')
                if not consumed.is_integer():
                    raise ValueError('Bullets consumed in magazine must be whole numbers')
                bonus = min(rule['max_bonus_percent'],
                            int(consumed // rule['bullets_per_step']) * rule['bonus_per_step_percent'])
                amount = [bonus, bonus]
            for name in components:
                rows.append({'name': name, 'range_percent': amount,
                             'condition': 'bullets consumed in current magazine',
                             'source': source, 'item': piece.get('name'), 'rule_id': rule['rule_id']})
            missing.append(f'{identity}: per-shot within-magazine weighting and buff reset are not modeled')
        elif rule.get('kind') == 'conditional_modifier' and (rule.get('condition') or {}).get('after_empty_reload'):
            state = context.get('after_empty_reload')
            if state is not None and not isinstance(state, bool):
                raise ValueError('After-empty-reload state must be true or false')
            if state is None:
                for name in components:
                    rows.append({'name': name, 'value_percent': rule['value_percent'],
                                 'condition': 'after empty reload', 'source': source,
                                 'item': piece.get('name'), 'rule_id': rule['rule_id']})
                if 'after empty reload' not in (context.get('condition_uptime') or {}):
                    missing.append(f'{identity}: empty-reload activation and uptime unresolved')
            else:
                for name in components:
                    rows.append({'name': name, 'range_percent': [rule['value_percent'] * int(state)] * 2,
                                 'condition': 'after empty reload', 'source': source,
                                 'item': piece.get('name'), 'rule_id': rule['rule_id']})
        elif rule.get('kind') == 'base_plus_conditional_modifier':
            for name in components:
                rows.append({'name': name, 'value_percent': rule['base_percent'],
                             'source': source, 'item': piece.get('name'), 'rule_id': rule['rule_id']})
            condition = rule.get('conditional') or {}
            if 'hp_consumed_per_stack_percent' in condition:
                stacks = (context.get('effect_stacks') or {}).get(identity)
                if stacks is not None:
                    stacks = _number(stacks, 'entered main-effect stacks', 0, condition['max_stacks'])
                    if not stacks.is_integer():
                        raise ValueError('Entered main-effect stacks must be whole numbers')
                    if context.get('hp_consumed_percent') == 0 and stacks:
                        raise ValueError('Positive HP-consumption stacks conflict with zero HP consumed')
                    extra = [stacks * condition['bonus_per_stack_percent']] * 2
                elif context.get('hp_consumed_percent') == 0:
                    extra = [0, 0]
                else:
                    extra = [0, condition['bonus_per_stack_percent'] * condition['max_stacks']]
                    missing.append(f'{identity}: HP consumption, {condition["duration_seconds"]}s stack timing and uptime unresolved')
                for name in components:
                    rows.append({'name': name, 'range_percent': extra,
                                 'condition': 'HP-consumption stacks', 'source': source,
                                 'item': piece.get('name'), 'rule_id': rule['rule_id']})
            elif condition:
                missing.append(f'{identity}: conditional main-effect magnitude or uptime unresolved')
        elif rule.get('kind') == 'conditional_modifier' and 'distance_meters_gt' in (rule.get('condition') or {}):
            threshold = rule['condition']['distance_meters_gt']
            distance = context.get('distance_meters')
            if distance is None:
                amount = [0, rule['minimum_percent'] + rule['additional_percent_range'][1]]
                missing.append(f'{identity}: target distance required; additional distance scaling unverified')
            elif _number(distance, 'distance meters') <= threshold:
                amount = [0, 0]
            else:
                amount = [rule['minimum_percent'] + rule['additional_percent_range'][0],
                          rule['minimum_percent'] + rule['additional_percent_range'][1]]
                missing.append(f'{identity}: additional distance scaling unverified')
            for name in components:
                rows.append({'name': name, 'range_percent': amount,
                             'condition': f'target beyond {threshold:g} meters',
                             'source': source, 'item': piece.get('name'), 'rule_id': rule['rule_id']})
        elif rule.get('kind') == 'conditional_modifier' and 'kill_within_meters' in (rule.get('condition') or {}):
            condition = f'kill within {rule["condition"]["kill_within_meters"]:g}m in previous {rule["duration_seconds"]:g}s'
            for name in components:
                rows.append({'name': name, 'value_percent': rule['value_percent'],
                             'condition': condition, 'source': source,
                             'item': piece.get('name'), 'rule_id': rule['rule_id']})
            if condition not in (context.get('condition_uptime') or {}):
                missing.append(f'{identity}: qualifying kill and {rule["duration_seconds"]:g}s buff uptime unresolved')
        elif rule.get('kind') == 'triggered_conditional_modifier' and 'prior_magazine_elemental_events_gt' in (rule.get('condition') or {}):
            events = context.get('prior_magazine_elemental_events')
            seconds = context.get('seconds_since_reload')
            cap = rule['limit_percent']
            if events is None:
                amount = [0, cap]
                missing.append(f'{identity}: previous-magazine Elemental DMG event count unresolved')
            else:
                events = _number(events, 'previous-magazine Elemental DMG events', 0)
                if not events.is_integer():
                    raise ValueError('Previous-magazine Elemental DMG events must be whole numbers')
                value = min(cap, events * rule['value_per_event_percent'])
                amount = [value, value]
            if seconds is None and amount[1]:
                amount[0] = 0
                missing.append(f'{identity}: {rule["duration_seconds"]:g}s reload buff timing unresolved')
            elif seconds is not None and _number(seconds, 'seconds since reload') >= rule['duration_seconds']:
                amount = [0, 0]
            for name in components:
                rows.append({'name': name, 'range_percent': amount,
                             'condition': 'previous-magazine elemental events and reload timing',
                             'source': source, 'item': piece.get('name'), 'rule_id': rule['rule_id']})
            missing.append(f'{identity}: event counting, refresh behavior and Elemental DMG application to status remain unverified')
        else:
            missing.append(f'{identity}: exact-level main effect has no implemented operator')
    return rows, missing


def _set_rows(item, context):
    rows, missing = [], []
    for selected in item.get('sets') or []:
        name, count = selected.get('name'), selected.get('count', 0)
        if not isinstance(count, int) or count < 0:
            raise ValueError('Set piece count must be a nonnegative integer')
        reached = [rule for rule in SET_RULES if rule.get('set_name') == name and count >= rule.get('pieces', 999)]
        if not reached and count:
            missing.append(f'{name}: set threshold and effects not modeled')
        for rule in reached:
            if rule['id'] == 'bastille_two_reload_efficiency':
                scenario = str(context.get('scenario') or '').lower()
                amount = [15, 15] if scenario == 'pve non-raidzone' else [0, 15]
                if scenario != 'pve non-raidzone':
                    missing.append('Bastille 2-piece: non-RaidZone applicability is not established for the entered scenario')
                rows.append({'name': 'Reload Efficiency', 'range_percent': amount,
                             'condition': 'Bastille 2-piece non-RaidZone',
                             'source': SOURCE_URLS[rule['source']], 'item': name, 'rule_id': rule['id']})
                continue
            if rule['id'] == 'treacherous_tides_three':
                scenario = str(context.get('scenario') or '').lower()
                hp = context.get('hp_percent')
                if scenario != 'pve non-raidzone':
                    active = [0, 28]
                    missing.append(f'{name} 3-piece: enter PvE non-RaidZone scenario to resolve applicability')
                elif hp is None:
                    active = [8, 28]
                    missing.append(f'{name} 3-piece: HP percentage is needed to narrow the official 8–28% endpoints')
                elif hp <= 60:
                    active = [28, 28]
                elif hp == 100:
                    active = [8, 8]
                else:
                    active = [8, 28]
                    missing.append(f'{name} 3-piece: the HP scaling curve between 60% and 100% is not published')
                for stat in ('Weapon DMG', 'Status DMG'):
                    rows.append({'name': stat, 'range_percent': active,
                                 'condition': f'{name} 3-piece HP scaling',
                                 'source': SOURCE_URLS.get(rule.get('source'), rule.get('source')),
                                 'item': name, 'rule_id': rule['id']})
                missing.append(f'{name} 3-piece: stacking with its 2-piece bonus and other damage pools is an additive sensitivity assumption')
                continue
            if rule.get('bonus_fraction') is None or rule.get('component') != 'weapon_and_status_damage':
                missing.append(f'{name} {rule["pieces"]}-piece: {rule.get("calculation", "effect not modeled")}')
                continue
            amount = 100 * rule['bonus_fraction']
            scenario = str(context.get('scenario') or '').lower()
            if scenario != 'pve non-raidzone':
                active = [0, amount]
                missing.append(f'{name} {rule["pieces"]}-piece: enter PvE non-RaidZone scenario to resolve applicability')
            elif context.get('hp_percent') is None:
                active = [0, amount]
                missing.append(f'{name} {rule["pieces"]}-piece: HP percentage is needed')
            else:
                threshold = rule['condition']['hp_fraction_below'] * 100
                active = [amount, amount] if context['hp_percent'] < threshold else [0, 0]
            for stat in ('Weapon DMG', 'Status DMG'):
                rows.append({'name': stat, 'range_percent': active, 'condition': f'{name} {rule["pieces"]}-piece below {threshold:g}% HP' if context.get('hp_percent') is not None and scenario == 'pve non-raidzone' else f'{name} {rule["pieces"]}-piece condition',
                             'source': SOURCE_URLS.get(rule.get('source'), rule.get('source')),
                             'item': name, 'rule_id': rule['id']})
    return rows, missing


def _armor_rows(item, context):
    rows, missing = [], []
    for piece in [item, *(item.get('items') or [])]:
        if piece.get('catalog_id') != 'armor:wind-intepreter-cap':
            continue
        scenario = str(context.get('scenario') or '').lower()
        if 'non-raidzone' in scenario:
            amount = [25, 25]
        elif 'raidzone' in scenario:
            amount = [0, 0]
        else:
            amount = [0, 25]
            missing.append('Wind Intepreter Cap: enter non-RaidZone or RaidZone scenario for applicability')
        rows.append({'name': 'Unstable Bomber DMG', 'range_percent': amount,
                     'condition': 'Wind Intepreter Cap non-RaidZone',
                     'source': SOURCE_URLS['julygear'], 'item': piece.get('name'),
                     'rule_id': 'wind_interpreter_bomber'})
        missing.append('Wind Intepreter Cap: explosion reload, Bomber trigger count and damage-rate stacking are not modeled')
    return rows, missing


def _rows(item, context):
    pools = [{key: 0.0 for key in set(POOLS.values())} for _ in range(2)]
    unresolved = []
    trace = []
    contributions = []
    main_rows, main_missing = _main_effect_rows(item, context)
    set_rows, set_missing = _set_rows(item, context)
    armor_rows, armor_missing = _armor_rows(item, context)
    candidate_rows, candidate_missing = evidence_registry.community_candidate_rows(item, context)
    rows = _all_rows(item) + main_rows + set_rows + armor_rows + candidate_rows
    unresolved.extend(main_missing + set_missing + armor_missing + candidate_missing)
    for piece in [item, *(item.get('items') or [])]:
        coverage = piece.get('numeric_coverage')
        if coverage == 'derived_complete':
            unresolved.append(f'{piece.get("name") or "Item"}: complete derived suffix profile; unverified target values')
        elif coverage not in (None, 'complete'):
            unresolved.append(f'{piece.get("name") or "Item"}: numeric profile {coverage}')
        if not piece.get('attributes') and not piece.get('items') and coverage != 'complete':
            unresolved.append(f'{piece.get("name") or "Item"}: no reviewed numeric rows')
    if len(rows) > 100:
        raise ValueError('At most 100 reviewed rows per alternative')
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Reviewed rows must be objects')
        name = row.get('name')
        if row.get('source_kind') == 'installed_native_affix' or 'native_affix_id' in row:
            binding = native_combat_labels.resolve(
                name, row.get('native_affix_id'), row.get('source_build'))
            trace.append({'name': name, 'item': row.get('item'),
                          'state': 'excluded: native affix needs its typed property calculation path',
                          'native_binding': binding, 'source': row.get('source')})
            unresolved.append(f'{name or "Native affix"}: {binding["status"]}; '
                              'native affix label alone cannot select the Attack or Remote damage property')
            continue
        provenance = {key:row[key] for key in ('source_status','source_sha256','evidence_context',
                                              'observed_level','raw_text') if key in row}
        source_status = str(row.get('source_status') or '').lower()
        if source_status and any(mark in source_status for mark in ('unverified', 'candidate', 'preview', 'historical', 'guess')):
            unresolved.append(f'{name or "Unnamed row"}: source status {row["source_status"]}; included only as an explicit input assumption')
        elif not source_status and not row.get('rule_id'):
            unresolved.append(f'{name or "Unnamed row"}: row source quality is unspecified; value is an explicit input assumption')
        if name not in POOLS:
            trace.append({'name': name, 'state': 'excluded: component or operator not modeled',
                          'source': row.get('source'), **provenance})
            unresolved.append(f'{name or "Unnamed row"}: component or operator not modeled')
            continue
        maximum = public_catalog_detail.low_hp_maximum(row)
        if maximum is not None:
            row = {**row, 'value_percent': maximum, 'direction': 'increase',
                   'condition': 'low hp', 'model_maximum_percent': maximum}
            unresolved.append(f'{name}: only the published low-HP maximum is known; the HP scaling curve is unpublished')
        if row.get('direction', 'increase') != 'increase' or row.get('unit', 'percent') != 'percent':
            unresolved.append(f'{name}: unit or direction not modeled')
            continue
        if row.get('range_percent') is not None:
            bounds = row['range_percent']
            if not isinstance(bounds, (list, tuple)) or len(bounds) != 2:
                raise ValueError(f'{name}: range must have two endpoints')
            applied = [_number(value, name + ' range', -100, 1000) for value in bounds]
            if applied[0] > applied[1]:
                raise ValueError(f'{name}: range endpoints are reversed')
            if not row.get('source'):
                unresolved.append(f'{name}: row source unspecified')
            for index in (0, 1):
                pools[index][POOLS[name]] += applied[index]
            contributions.append({'pool': POOLS[name], 'values': applied,
                                  'key': str(row.get('condition') or row.get('rule_id') or name).lower() if applied[0] != applied[1] else None})
            trace.append({'name': name, 'item': row.get('item'), 'pool': POOLS[name],
                          'rule_id': row.get('rule_id'), 'condition': row.get('condition'),
                          'applied_range_percent': applied, 'source': row.get('source'), **provenance})
            if applied[0] != applied[1]:
                unresolved.append(f'{name}: {row.get("condition") or "rule"} value or activation is unresolved')
            continue
        value = row.get('value_percent')
        if value is None:
            reason = row.get('calculation_exclusion_reason')
            unresolved.append(f'{name}: exact magnitude missing' +
                              (f' — {reason}' if reason else ''))
            trace.append({'name': name, 'state': 'excluded: exact magnitude missing',
                          'source': row.get('source'),
                          'calculation_exclusion_reason': reason, **provenance})
            continue
        value = _number(value, name, -100, 1000)
        if not row.get('source'):
            unresolved.append(f'{name}: row source unspecified')
        conditional_bonus = row.get('conditional_bonus_percent')
        if conditional_bonus is not None:
            conditional_bonus = _number(conditional_bonus, name + ' conditional bonus', -100, 1000)
            (low, high), state = _activation({'condition': row.get('condition')}, context)
            applied = [value + conditional_bonus * low, value + conditional_bonus * high]
        else:
            (low, high), state = _activation(row, context)
            applied = [value * low, value * high]
        if low != high:
            unresolved.append(f'{name}: {row.get("condition")} strength or uptime is unresolved')
        pool = POOLS[name]
        pools[0][pool] += applied[0]
        pools[1][pool] += applied[1]
        contributions.append({'pool': pool, 'values': applied,
                              'key': str(row.get('condition') or row.get('rule_id') or name).lower() if applied[0] != applied[1] else None})
        trace.append({'name': name, 'pool': pool, 'value_percent': value,
                      'item': row.get('item'),
                      'rule_id': row.get('rule_id') or '',
                      'conditional_bonus_percent': conditional_bonus,
                      'condition': row.get('condition'), 'activation': state,
                      'applied_range_percent': applied,
                      'source': row.get('source'), **provenance})
    return pools, trace, unresolved, contributions


def _scenario_pools(contributions, states):
    pools = {key: 0.0 for key in set(POOLS.values())}
    for row in contributions:
        endpoint = states[row['key']] if row['key'] is not None else 0
        pools[row['pool']] += row['values'][endpoint]
    return pools


def _factor(pool, additions):
    total = pool + additions
    if total <= -100:
        raise ValueError('A damage pool reaches zero or negative under the additive hypothesis')
    return 1 + total / 100


def _branch_ratio(left, right, base, joint_model='additive'):
    def ratio(pool):
        return _factor(base.get(pool, 0), right[pool]) / _factor(base.get(pool, 0), left[pool])
    shared = ratio('all')
    direct = shared * ratio('weapon')
    status = shared * ratio('elemental') * ratio('status')
    if joint_model == 'additive':
        def joint(pools):
            value = native_direct_hit_graph.joint_factor(
                (base['crit'] + pools['crit']) / 100,
                (base['weakspot'] + pools['weakspot']) / 100,
                crit=True, weakspot=True)
            if value <= 0:
                raise ValueError('Additive joint crit/weakspot factor must be positive')
            return value
        joint_ratio = joint(right) / joint(left)
    elif joint_model == 'multiplicative':
        joint_ratio = ratio('crit') * ratio('weakspot')
    else:
        raise ValueError('Joint multiplier must be additive or multiplicative')
    return {
        'normal': direct,
        'crit': direct * (native_direct_hit_graph.joint_factor((base['crit'] + right['crit']) / 100, 0, crit=True) /
                          native_direct_hit_graph.joint_factor((base['crit'] + left['crit']) / 100, 0, crit=True)),
        'weakspot': direct * (native_direct_hit_graph.joint_factor(0, (base['weakspot'] + right['weakspot']) / 100, weakspot=True) /
                              native_direct_hit_graph.joint_factor(0, (base['weakspot'] + left['weakspot']) / 100, weakspot=True)),
        'crit_weakspot': direct * joint_ratio,
        'status': status,
        'elemental_nonstatus': shared * ratio('elemental'),
        'power_surge': status * ratio('power_surge'),
        'shock': status * ratio('shock'),
        'unstable_bomber': shared * ratio('unstable_bomber'),
    }


def _packet_ratio(packet, pools, base, joint_model):
    """Apply an event's declared damage class before keyword modifiers."""
    zero = {key: 0.0 for key in base}
    branch = packet['branch']
    if packet['kind'] == 'direct':
        return _branch_ratio(zero, pools, base, joint_model)[branch]
    def ratio(pool):
        return _factor(base[pool], pools[pool]) / _factor(base[pool], 0)
    factor = ratio('all') * ratio(packet['damage_class'])
    elemental = packet['elemental_pool_applies']
    # Unknown event element is never promoted from Status class or keyword.
    # The caller withholds the combined projection if this distinction matters.
    if elemental:
        factor *= ratio('elemental')
    if branch in ('power_surge', 'shock', 'unstable_bomber'):
        factor *= ratio(branch)
    if branch in ('crit', 'weakspot', 'crit_weakspot'):
        direct = _branch_ratio(zero, pools, base, joint_model)
        factor *= direct[branch] / direct['normal']
    return factor


def _empirical(runs):
    if not runs:
        return None
    if not isinstance(runs, dict):
        raise ValueError('Measured runs must be an object with left and right lists')
    result = {}
    warnings = []
    for side in ('left', 'right'):
        items = runs.get(side) or []
        if len(items) > 100:
            raise ValueError('At most 100 measured runs per alternative')
        checked = []
        for run in items:
            if not isinstance(run, dict):
                raise ValueError('Measured runs must be objects')
            rounds = _number(run.get('rounds'), 'measured rounds', 1)
            if not rounds.is_integer():
                raise ValueError('Measured rounds must be whole numbers')
            checked.append({'damage': _number(run.get('damage'), 'measured damage'),
                            'rounds': rounds,
                            'duration_seconds': _number(run['duration_seconds'], 'measured duration', .000001) if run.get('duration_seconds') is not None else None,
                            'target': str(run.get('target') or ''),
                            'buffs': str(run.get('buffs') or ''),
                            'conditions': str(run.get('conditions') or ''),
                            'source': str(run.get('source') or '')})
        total = sum(r['damage'] for r in checked)
        rounds = sum(r['rounds'] for r in checked)
        result[side] = {'runs': checked, 'run_count': len(checked), 'total_damage': total,
                        'total_rounds': rounds, 'damage_per_round': total / rounds if rounds else None,
                        'damage_per_second': (total / sum(r['duration_seconds'] for r in checked)) if checked and all(r['duration_seconds'] is not None for r in checked) else None}
    left, right = result['left'], result['right']
    if not left['runs'] or not right['runs']:
        warnings.append('Both alternatives need measured runs for a comparison.')
    if left['total_rounds'] != right['total_rounds']:
        warnings.append('Unequal round counts; damage totals are not matched.')
    for key in ('target', 'buffs', 'conditions'):
        values = {run[key] for side in result.values() for run in side['runs']}
        if len(values) != 1 or not next(iter(values), ''):
            warnings.append(f'{key.capitalize()} are missing or differ across runs.')
    if any(run['duration_seconds'] is None for side in result.values() for run in side['runs']):
        warnings.append('Durations absent; total damage is not sustained DPS.')
    if any(not run['source'] for side in result.values() for run in side['runs']):
        warnings.append('One or more measured runs lack a source.')
    result['damage_delta_right_minus_left'] = right['total_damage'] - left['total_damage']
    result['warnings'] = warnings
    result['winner_established'] = False
    result['scope'] = 'Observed damage only; sample variability and causal attribution are not established.'
    return result


def _firing_cycle(pairs, base, context):
    timing = context.get('timing')
    if timing is None:
        return None
    if not isinstance(timing, dict):
        raise ValueError('Timing must be an object')
    rpm = _number(timing.get('rpm'), 'RPM', .000001)
    magazine = _number(timing.get('magazine'), 'magazine', 1)
    reload_seconds = _number(timing.get('reload_seconds'), 'reload seconds')
    if not magazine.is_integer():
        raise ValueError('Magazine must be a whole number')
    candidates = []
    for a, b in pairs:
        pair = []
        for pools in (a, b):
            rate = rpm * _factor(base['fire_rate'], pools['fire_rate'])
            raw_magazine = magazine * _factor(base['magazine'], pools['magazine'])
            if raw_magazine < 1:
                raise ValueError('Modeled magazine falls below one round')
            reload_time = combat_projection.reload_seconds(reload_seconds, base['reload'] + pools['reload'])
            pair.append({'rpm': rate, 'magazine_floor': math.floor(raw_magazine),
                         'magazine_ceil': math.ceil(raw_magazine),
                         'reload_seconds': reload_time,
                         'sustained_shots_per_second_floor': math.floor(raw_magazine) / (math.floor(raw_magazine) * 60 / rate + reload_time),
                         'sustained_shots_per_second_ceil': math.ceil(raw_magazine) / (math.ceil(raw_magazine) * 60 / rate + reload_time)})
        candidates.append(pair)
    return {'left': candidates[0][0], 'right': candidates[0][1],
            'throughput_ratio_floor_range': [min(pair[1]['sustained_shots_per_second_floor'] / pair[0]['sustained_shots_per_second_floor'] for pair in candidates),
                                             max(pair[1]['sustained_shots_per_second_floor'] / pair[0]['sustained_shots_per_second_floor'] for pair in candidates)],
            'throughput_ratio_ceil_range': [min(pair[1]['sustained_shots_per_second_ceil'] / pair[0]['sustained_shots_per_second_ceil'] for pair in candidates),
                                            max(pair[1]['sustained_shots_per_second_ceil'] / pair[0]['sustained_shots_per_second_ceil'] for pair in candidates)],
            'scope': 'Illustrative long-run shot throughput; assumes additive Fire Rate/Magazine/Reload Efficiency pools and reload/(1+efficiency). No proc timing or ammo returns.'}


def compare(left, right, context=None, runs=None):
    """Compare any two reviewed row sets without requiring ownership or saving.

    ``base_pools`` excludes the two candidate alternatives. Every ratio is
    conditional on additive bonuses within each named pool and multiplicative
    pools. The game stacking order is not asserted by this model.
    """
    context = context or {}
    if not isinstance(left, dict) or not isinstance(right, dict) or not isinstance(context, dict):
        raise ValueError('Alternatives and context must be objects')
    if context.get('suffix_candidate_opt_in') is not None and not isinstance(context['suffix_candidate_opt_in'], bool):
        raise ValueError('Suffix candidate opt-in must be true or false')
    if context.get('core_candidate_opt_in') is not None and not isinstance(context['core_candidate_opt_in'], bool):
        raise ValueError('Core candidate opt-in must be true or false')
    pool_mode = context.get('weapon_timeline_pool_mode')
    if pool_mode not in (None, 'selected_reviewed_rows'):
        raise ValueError('Weapon timeline pool mode must be selected_reviewed_rows')
    for key in ('core_preview_opt_in', 'core_unknown_build_opt_in', 'core_unknown_variant_opt_in'):
        if context.get(key) is not None and not isinstance(context[key], bool):
            raise ValueError(f'{key} must be true or false')
    left, right = _expand_catalog(left, context), _expand_catalog(right, context)
    if context.get('base_pools') is not None and not isinstance(context['base_pools'], dict):
        raise ValueError('Base pools must be an object')
    if context.get('condition_uptime') is not None and not isinstance(context['condition_uptime'], dict):
        raise ValueError('Condition fractions must be an object')
    if context.get('condition_strength') is not None and not isinstance(context['condition_strength'], dict):
        raise ValueError('Condition strengths must be an object')
    if context.get('community_candidate_opt_in') is not None and not isinstance(context['community_candidate_opt_in'], bool):
        raise ValueError('Community candidate opt-in must be true or false')
    if context.get('effect_stacks') is not None and not isinstance(context['effect_stacks'], dict):
        raise ValueError('Main-effect stack counts must be an object')
    if context.get('hp_consumed_percent') is not None:
        _number(context['hp_consumed_percent'], 'HP consumed percent')
    if context.get('hp_percent') is not None:
        _number(context['hp_percent'], 'HP percent', 0, 100)
    entered_pools = dict(context.get('base_pools') or {})
    base = {pool: _number(entered_pools.get(pool, 0), f'base {pool} pool', -99, 1000)
            for pool in set(POOLS.values())}
    profile_direct = (context.get('combat_profile') or {}).get('direct') if isinstance(context.get('combat_profile') or {}, dict) else None
    derived_pools = {}
    if isinstance(profile_direct, dict):
        for pool, field in (('crit', 'crit_bonus_percent'), ('weakspot', 'weakspot_bonus_percent')):
            if field not in profile_direct:
                continue
            value = _number(profile_direct[field], field, 0, 1000)
            if pool in entered_pools and not math.isclose(base[pool], value, abs_tol=1e-9):
                raise ValueError(f'Combat profile {field} disagrees with base_pools.{pool}')
            if pool not in entered_pools:
                base[pool] = value
                derived_pools[pool] = value
    profile_joint = ((context.get('combat_profile') or {}).get('direct') or {}).get('joint_multiplier') if isinstance(context.get('combat_profile') or {}, dict) else None
    joint_model = context.get('joint_multiplier') or profile_joint or 'additive'
    if joint_model not in ('additive', 'multiplicative') or (profile_joint and context.get('joint_multiplier') and profile_joint != context['joint_multiplier']):
        raise ValueError('Joint multiplier must consistently be additive or multiplicative')
    left_pools, left_trace, left_missing, left_contributions = _rows(left, context)
    right_pools, right_trace, right_missing, right_contributions = _rows(right, context)
    left_evidence = evidence_registry.audit_alternative(left)
    right_evidence = evidence_registry.audit_alternative(right)
    core_left = _core_effects(left)
    core_right = _core_effects(right)
    core_same = bool(core_left) and core_left == core_right
    uncertainty_keys = sorted({row['key'] for row in left_contributions + right_contributions if row['key'] is not None})
    if len(uncertainty_keys) > 12:
        raise ValueError('More than 12 unresolved shared conditions; enter condition fractions to narrow the comparison')
    pairs = [(_scenario_pools(left_contributions, states), _scenario_pools(right_contributions, states))
             for choices in product((0, 1), repeat=len(uncertainty_keys))
             for states in [dict(zip(uncertainty_keys, choices))]]
    scenario_ratios = [_branch_ratio(a, b, base, joint_model) for a, b in pairs]
    ratios = {}
    for branch in BRANCHES:
        candidates = [result[branch] for result in scenario_ratios]
        ratios[branch] = {'min': min(candidates), 'max': max(candidates),
                          'delta_percent_range': [100 * (min(candidates) - 1), 100 * (max(candidates) - 1)]}
    weights = context.get('old_damage_shares')
    weighted = None
    if weights is not None:
        if not isinstance(weights, dict) or set(weights) - set(BRANCHES):
            raise ValueError('Damage shares must use named component branches')
        checked = {branch: _number(weights.get(branch, 0), branch + ' share', 0, 1) for branch in BRANCHES}
        if not math.isclose(sum(checked.values()), 1, abs_tol=1e-6):
            raise ValueError('Old damage shares must sum to one')
        weighted_candidates = [sum(checked[b] * result[b] for b in BRANCHES) for result in scenario_ratios]
        weighted = {'min': min(weighted_candidates),
                    'max': max(weighted_candidates),
                    'shares': checked}
    combat_budget = None
    projection_missing = []
    if context.get('combat_profile') is not None:
        baseline = combat_projection.components(context['combat_profile'])
        if baseline['total_damage'] <= 0:
            raise ValueError('Combat profile needs positive modeled damage for comparison')
        snowline_active = context.get('snowline_rule_active')
        if snowline_active is not None and not isinstance(snowline_active, bool):
            raise ValueError('Snowline rule activation must be true or false')
        has_snowline = [any(piece.get('catalog_id') == 'armor:snowline-elite-vest'
                            for piece in [item, *(item.get('items') or [])]) for item in (left, right)]
        frost_events = any(event.get('trigger_family') == 'frost_vortex' and event.get('triggered_effect') is True
                           for event in context['combat_profile'].get('events') or [])
        if any(has_snowline) and not frost_events:
            projection_missing.append('Snowline Elite Vest: enter a tagged Frost Vortex triggered-effect packet; the Vortex packet itself is not duplicated')
        if any(has_snowline) and snowline_active is None:
            projection_missing.append('Snowline Elite Vest: scenario applicability was not entered; triggered-effect repetition is excluded')
        budgets = [combat_projection.components(context['combat_profile'], {'frost_vortex': 1}
                   if has_snowline[index] and snowline_active is True else None)
                   for index in range(2)]
        unknown_element = any(packet['kind'] == 'event' and packet['elemental_pool_applies'] is None
                              for budget in budgets for packet in budget['packets'])
        element_changes_projection = any(pools['elemental'] != 0 for pair in pairs for pools in pair)
        if unknown_element and element_changes_projection:
            projection_missing.append('Event element classification or elemental pool applicability is unknown; combined combat damage and DPS are withheld. Enter each event element or explicit elemental_pool_applies true/false.')
        else:
            projected = []
            for a, b in pairs:
                amounts = []
                for index, pools in enumerate((a, b)):
                    total = sum(packet['damage'] * _packet_ratio(packet, pools, base, joint_model)
                                for packet in budgets[index]['packets'])
                    amounts.append(total)
                projected.append(amounts)
            duration = baseline['duration_seconds']
            combat_budget = {'baseline': baseline,
                         'left_damage_range': [min(row[0] for row in projected), max(row[0] for row in projected)],
                         'right_damage_range': [min(row[1] for row in projected), max(row[1] for row in projected)],
                         'right_over_left_range': [min(row[1] / row[0] for row in projected),
                                                   max(row[1] / row[0] for row in projected)],
                         'left_dps_range': ([min(row[0] for row in projected) / duration,
                                             max(row[0] for row in projected) / duration] if duration else None),
                         'right_dps_range': ([min(row[1] for row in projected) / duration,
                                              max(row[1] for row in projected) / duration] if duration else None),
                         'scope': 'Explicit-input expectation under the named pool and trigger hypotheses; event damage class is applied before keyword pools; no game winner established.'}
    threshold = None
    direct = ratios['normal']; status = ratios['status']
    if direct['min'] == direct['max'] and status['min'] == status['max'] and direct['min'] < 1 < status['min']:
        threshold = (1 - direct['min']) / (status['min'] - direct['min'])
    missing = left_missing + right_missing + projection_missing + left_evidence['missing_mechanics'] + right_evidence['missing_mechanics']
    changed_pools = {pool for pool in base if any(a[pool] != b[pool] for a, b in pairs)}
    missing_base_pools = sorted(changed_pools - set(entered_pools) - set(derived_pools))
    if missing_base_pools:
        missing.append('Other active bonus pools not entered (' + ', '.join(missing_base_pools) + '); zero is used only for sensitivity, not asserted as the current build.')
    if not core_same:
        missing.append('Main effects differ or are missing; only explicitly reviewed operators are included, and other interactions remain unresolved.')
    if weights is None:
        missing.append('Enter old component damage shares for an illustrative combined result.')
    weapon_timeline_scenarios = None
    weapon_timeline_pool_application = None
    if context.get('weapon_timeline') is not None:
        plans = context['weapon_timeline']
        if not isinstance(plans, dict) or set(plans) != {'left', 'right'}:
            raise ValueError('Weapon timeline comparison needs left and right scenario requests')
        requests = plans
        if pool_mode == 'selected_reviewed_rows':
            absent = sorted(set(TIMELINE_DAMAGE_POOLS) - set(entered_pools))
            if absent:
                raise ValueError('Enter common baseline pools excluding selected alternatives: '
                                 + ', '.join(absent))
            requests = copy.deepcopy(plans)
            applications = {}
            for side, pool_bounds, trace, unresolved in (
                    ('left', left_pools, left_trace, left_missing),
                    ('right', right_pools, right_trace, right_missing)):
                request = requests[side]
                if not isinstance(request, dict) or not isinstance(request.get('damage_model'), dict):
                    raise ValueError(f'{side}: selected-row pool mode needs a damage_model object')
                import weapon_packet_timeline_api
                if request.get('weapon_id') in weapon_packet_timeline_api.BINDINGS:
                    raise ValueError(f'{side}: packet-only weapon timelines cannot apply selected damage pools until packet class and bonus routing are bound')
                model = request['damage_model']
                if 'bonus_pools_percent' in model:
                    raise ValueError(f'{side}: remove manual bonus_pools_percent when applying selected rows')
                varying = [pool for pool in TIMELINE_DAMAGE_POOLS
                           if not math.isclose(pool_bounds[0][pool], pool_bounds[1][pool], abs_tol=1e-9)]
                if varying:
                    raise ValueError(f'{side}: selected row activation or strength is unresolved for '
                                     + ', '.join(varying) + '; enter explicit condition inputs')
                final = {pool: base[pool] + pool_bounds[0][pool] for pool in TIMELINE_DAMAGE_POOLS}
                model['bonus_pools_percent'] = final
                unsupported = {pool: value for pool, value in pool_bounds[0].items()
                               if pool not in TIMELINE_DAMAGE_POOLS and not math.isclose(value, 0, abs_tol=1e-9)}
                applications[side] = {
                    'common_baseline_pools_percent': {pool: base[pool] for pool in TIMELINE_DAMAGE_POOLS},
                    'selected_reviewed_row_pools_percent': {pool: pool_bounds[0][pool] for pool in TIMELINE_DAMAGE_POOLS},
                    'applied_damage_pools_percent': final,
                    'unapplied_component_pools_percent': unsupported,
                    'reviewed_row_sources': sorted({str(row['source']) for row in trace
                                                   if row.get('pool') in TIMELINE_DAMAGE_POOLS and row.get('source')}),
                    'unresolved_equipment': unresolved,
                }
            weapon_timeline_pool_application = {
                'mode': pool_mode, 'sides': applications,
                'scope': 'Conditional additive pool scenario from common entered baseline plus selected reviewed rows. '
                         'Unreviewed rows, typed core outputs, keyword pools and timing modifiers are not applied; '
                         'this is not a complete game build.'}
        import weapon_timeline_api
        weapon_timeline_scenarios = {side:weapon_timeline_api.simulate(requests[side])
                                     for side in ('left', 'right')}
        missing.append('Weapon timeline damage, when explicitly modeled, is a separate scenario; it is not added to component damage or treated as measured game DPS.')
    mod_stateful_scenarios = None
    if context.get('mod_stateful') is not None:
        scenarios = context['mod_stateful']
        if not isinstance(scenarios, dict) or set(scenarios) != {'left', 'right'}:
            raise ValueError('Stateful mod comparison needs left and right scenario requests')
        import mod_stateful_api
        mod_stateful_scenarios = {}
        for side, item in (('left', left), ('right', right)):
            scenario = scenarios[side]
            if not isinstance(scenario, dict):
                raise ValueError(f'{side}: stateful mod scenario must be an object')
            selected = {(piece.get('catalog_id'), piece.get('level'))
                        for piece in [item, *(item.get('items') or [])]}
            if (scenario.get('catalog_id'), scenario.get('level')) not in selected:
                raise ValueError(f'{side}: stateful mod identity and level must match selected gear or plan')
            mod_stateful_scenarios[side] = mod_stateful_api.simulate(scenario)
        missing.append('Stateful mod outputs are community, level-unbound candidates; they are separate from component multipliers and weapon packet totals.')
    integrated_event_scenarios = None
    if context.get('integrated_combat') is not None:
        plans = context['integrated_combat']
        if not isinstance(plans, dict) or set(plans) != {'left', 'right'}:
            raise ValueError('Integrated combat comparison needs left and right scenarios')
        import integrated_event_model
        required = set(integrated_event_model.SUPPORTED_POOLS) | {'crit', 'weakspot'}
        absent = sorted(required - set(entered_pools))
        if absent:
            raise ValueError('Integrated combat needs explicitly entered common baseline pools: '
                             + ', '.join(absent))
        integrated_event_scenarios = {}
        for side, item, pool_bounds, trace, unresolved in (
                ('left', left, left_pools, left_trace, left_missing),
                ('right', right, right_pools, right_trace, right_missing)):
            scenario = plans[side]
            if not isinstance(scenario, dict):
                raise ValueError(f'{side}: integrated combat scenario must be an object')
            scenario = dict(scenario)
            import public_catalog_detail
            selected_resonance = []
            for piece in [item, *(item.get('items') or [])]:
                identity, level = piece.get('catalog_id'), piece.get('level')
                if not identity or not isinstance(level, int) or isinstance(level, bool) or piece.get('shiny') is True:
                    continue
                entry = catalog.ENTRIES.get(identity)
                if not entry or entry.get('kind') != 'mod':
                    continue
                rows, _, _ = public_catalog_detail.calculation_rows(identity, level)
                if any(str(row.get('stat_type') or '').startswith('resonance_') for row in rows):
                    selected_resonance.append({'catalog_id': identity, 'level': level})
            if scenario.get('resonance_suffixes') not in (None, selected_resonance):
                raise ValueError(f'{side}: Resonance suffixes must match selected ordinary gear and levels')
            if selected_resonance:
                scenario['resonance_suffixes'] = selected_resonance
                resonance_names = {str(row.get('name')) for piece in [item, *(item.get('items') or [])]
                                   for row in piece.get('attributes') or []
                                   if str(row.get('stat_type') or '').startswith('resonance_')}
                unresolved = [gap for gap in unresolved
                              if not ('component or operator not modeled' in gap and
                                      any(gap.startswith(name + ':') for name in resonance_names))]
                unresolved.append(f'{side}: selected Resonance suffix runs as a sourced, explicit-outcome event-stack scenario; current-game expiry and bucket semantics remain unverified')
            selected = {(piece.get('catalog_id'), piece.get('level'))
                        for piece in [item, *(item.get('items') or [])]}
            candidate_ids = {(row.get('catalog_id'), row.get('level'))
                             for row in scenario.get('candidate_mods') or [] if isinstance(row, dict)}
            if not candidate_ids <= selected:
                raise ValueError(f'{side}: candidate mod identity and level must match selected gear or plan')
            shiny_selected = {(piece.get('catalog_id'), piece.get('level'))
                              for piece in [item, *(item.get('items') or [])]
                              if piece.get('shiny') is True}
            if candidate_ids & shiny_selected:
                raise ValueError(f'{side}: ordinary stateful candidate is not bound to the selected Shiny variant')
            exact_timed = scenario.get('exact_timed_mods') or []
            if not isinstance(exact_timed, list):
                raise ValueError(f'{side}: exact timed mods must be a list')
            selected_variants = {(piece.get('catalog_id'), piece.get('level'),
                                  piece.get('shiny') is True)
                                 for piece in [item, *(item.get('items') or [])]}
            for row in exact_timed:
                if (not isinstance(row, dict) or
                    (row.get('catalog_id'), row.get('level'), row.get('shiny') is True)
                        not in selected_variants):
                    raise ValueError(f'{side}: exact timed mod identity, level and Shiny variant must match selected gear or plan')
            if exact_timed:
                excluded = {row['catalog_id'] for row in exact_timed}
                pool_bounds, trace, timed_missing, _ = _rows(item, {
                    **context, '_exclude_exact_timed_ids': excluded})
                unresolved = list(unresolved) + timed_missing
                unresolved.append(f'{side}: selected exact timed main effects are applied only by the event scheduler, never as static pool rows')
            if candidate_ids and context.get('core_candidate_opt_in') is True:
                raise ValueError(f'{side}: disable separate candidate main-effect pool rows to avoid double counting stateful candidates')
            varying = [pool for pool in integrated_event_model.SUPPORTED_POOLS
                       if not math.isclose(pool_bounds[0][pool], pool_bounds[1][pool], abs_tol=1e-9)]
            if varying:
                raise ValueError(f'{side}: selected stat activation unresolved for '
                                 + ', '.join(varying) + '; enter explicit condition inputs')
            if (not math.isclose(base['magazine'] + pool_bounds[0]['magazine'], 0, abs_tol=1e-9)
                    and scenario.get('magazine_capacity_is_final') is not True):
                raise ValueError(f'{side}: magazine bonus changes shot timing; enter the final magazine capacity and set magazine_capacity_is_final=true')
            static = {pool: base[pool] + pool_bounds[0][pool]
                      for pool in integrated_event_model.SUPPORTED_POOLS}
            sources = sorted({str(row['source']) for row in trace if row.get('source')})
            if scenario.get('weapon_proc') is not None:
                if exact_timed:
                    raise ValueError(f'{side}: weapon proc plus exact timed core feedback is not connected; separate the scenarios to avoid silently omitting timed effects')
                import sourced_proc_timed_adapter
                proc = scenario['weapon_proc']
                if not isinstance(proc, dict):
                    raise ValueError(f'{side}: weapon_proc must be an object')
                selected_weapons = {piece.get('catalog_id') for piece in
                                    [item, *(item.get('items') or [])]
                                    if str(piece.get('catalog_id') or '').startswith('weapon:')}
                if selected_weapons and proc.get('weapon_id') not in selected_weapons:
                    raise ValueError(f'{side}: sourced weapon identity disagrees with selected gear')
                if not selected_weapons and proc.get('independent_weapon_scenario') is not True:
                    raise ValueError(f'{side}: select the weapon or mark the sourced proc scenario independent')
                import weapon_packet_timeline_api
                if proc.get('weapon_id') in weapon_packet_timeline_api.BINDINGS:
                    import packet_family_timed_adapter
                    output = packet_family_timed_adapter.evaluate(scenario, static_pools=static,
                                                                  static_sources=sources)
                else:
                    output = sourced_proc_timed_adapter.evaluate(scenario, static_pools=static,
                                                                 static_sources=sources)
                if not selected_weapons:
                    unresolved.append('Independent weapon scenario: weapon identity is not selected in this gear alternative.')
            else:
                output = integrated_event_model.evaluate(scenario, static_pools=static,
                                                          static_sources=sources)
            output['selected_row_gaps'] = unresolved
            output['selected_row_pools_percent'] = {pool: pool_bounds[0][pool]
                                                    for pool in integrated_event_model.SUPPORTED_POOLS}
            output['magazine_capacity_basis'] = ('caller_entered_final_capacity_with_selected_bonus'
                                                  if scenario.get('magazine_capacity_is_final') is True
                                                  else 'caller_entered_capacity_no_selected_magazine_bonus')
            integrated_event_scenarios[side] = output
        missing.append('Integrated combat is a named scheduler and pool scenario with level-unbound candidate state; it is not current-game certified DPS.')
    uncertain_conditions = sorted({str(row.get('condition')) for row in left_trace + right_trace
                                   if row.get('condition') and row.get('applied_range_percent') and
                                   row['applied_range_percent'][0] != row['applied_range_percent'][1]})
    shared = []
    right_rows = {(row.get('name'), row.get('value_percent'), row.get('conditional_bonus_percent'), row.get('condition'), row.get('direction', 'increase'))
                  for row in _all_rows(right)}
    for row in _all_rows(left):
        if isinstance(row, dict) and (row.get('name'), row.get('value_percent'), row.get('conditional_bonus_percent'), row.get('condition'), row.get('direction', 'increase')) in right_rows:
            shared.append({'name': row.get('name'), 'value_percent': row.get('value_percent'),
                           'condition': row.get('condition'), 'direction': row.get('direction', 'increase')})
    return {'scope': 'unsaved, read-only reviewed-row sensitivity', 'left': {'name': left.get('name'), 'trace': left_trace, 'evidence_audit': left_evidence, 'suffix_candidate_profile': left.get('suffix_candidate_profile'), 'suffix_candidate_profiles': _suffix_candidate_profiles(left), 'numeric_coverage': left.get('numeric_coverage'), 'typed_main_effects': _typed_main_effects(left, context)},
            'right': {'name': right.get('name'), 'trace': right_trace, 'evidence_audit': right_evidence, 'suffix_candidate_profile': right.get('suffix_candidate_profile'), 'suffix_candidate_profiles': _suffix_candidate_profiles(right), 'numeric_coverage': right.get('numeric_coverage'), 'typed_main_effects': _typed_main_effects(right, context)},
            'main_effect_same': core_same, 'main_effect': '; '.join(core_left) if core_same else None,
            'shared_rows': shared,
            'uncertain_conditions': uncertain_conditions,
            'base_pools_percent': base, 'base_pools_entered': not missing_base_pools,
            'base_pools_derived_from_profile': derived_pools,
            'missing_base_pools': missing_base_pools,
            'component_ratios': ratios,
            'conditional_weighted_ratio': weighted, 'status_share_break_even_for_normal_bullets': threshold,
            'conditional_combat_projection': combat_budget,
            'weapon_timeline_scenarios': weapon_timeline_scenarios,
            'weapon_timeline_pool_application': weapon_timeline_pool_application,
            'mod_stateful_scenarios': mod_stateful_scenarios,
            'integrated_event_scenarios': integrated_event_scenarios,
            'joint_multiplier_model': joint_model,
            'joint_multiplier_evidence': (native_direct_hit_graph.source() if joint_model == 'additive'
                                          else 'explicit_multiplicative_what_if'),
            'firing_cycle': _firing_cycle(pairs, base, context),
            'empirical': _empirical(runs), 'missing': missing,
            'assumptions': ['Additive bonuses inside each named pool; separate pools multiply.',
                            ('Direct Weapon crit and weakspot additions share one factor in the copied version-13 native graph.'
                             if joint_model == 'additive' else
                             'Multiplicative crit × weakspot is an explicit what-if; the copied version-13 direct-hit graph uses one additive factor.'),
                            'Status, Power Surge and Shock branches are assumed to receive both Elemental and Status pools; type-specific pools affect only their matching branch. Confirm applicability for the actual proc.',
                            'Crit and weak-spot branch bases use explicit base pools or matching combat-profile bonuses; mismatches are rejected.',
                            'Event Weapon or Status class selects its matching pool independently of Attack/Psi basis. An event receives the Elemental pool only with an explicit elemental tag or applicability input.',
                            'Unknown shared conditions use the same endpoint state on both alternatives. Endpoint scenarios are sensitivity samples; an interior maximum is not ruled out.',
                            'Ratios isolate listed modifiers; main effects, other changed gear, proc counts, enemy mitigation and timing are not inferred.'],
            'game_winner_established': False}
