"""Bind structured catalog/plan selections to a published calculator scenario."""
from __future__ import annotations

import catalog
import published_reference_model
import published_timed_combat


def _number(value, default, label):
    if value is None or value == '':
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f'{label} must be a whole number')
    return value


def _build(selection, plans, options):
    if not isinstance(options, dict):
        raise ValueError('Published reference options must be an object')
    kind = selection.get('kind')
    gaps = []
    mods, armors, selected_weapons = [], [], []
    if kind == 'catalog':
        identity = selection['catalog_id']
        entry = catalog.ENTRIES[identity]
        if entry['kind'] == 'weapon':
            selected_weapons.append((identity, selection))
        elif entry['kind'] == 'mod':
            mods.append({'catalog_id': identity, 'level': selection['level'],
                         'shiny': selection.get('shiny', False)})
        elif entry['kind'] == 'armor':
            armors.append({'catalog_id': identity,
                           'stars': _number(options.get('armor_stars'), 1, 'armor stars'),
                           'tier': _number(options.get('armor_tier'), 1, 'armor tier'),
                           'calibration': _number(options.get('armor_calibration'), 0, 'armor calibration')})
    else:
        plan = next(row for row in plans if row['id'] == selection['planned_build_id'])
        for slot, item in (plan.get('slots') or {}).items():
            if not isinstance(item, dict):
                continue
            identity = item.get('catalog_id')
            entry = catalog.ENTRIES.get(identity)
            if entry and entry['kind'] == 'weapon':
                selected_weapons.append((identity, item))
            elif entry and entry['kind'] == 'armor':
                armors.append({'catalog_id': identity,
                               'stars': _number(item.get('stars'), 1, 'armor stars'),
                               'tier': _number(item.get('tier'), 1, 'armor tier'),
                               'calibration': _number(item.get('calibration'), 0, 'armor calibration')})
            mod_id = item.get('mod_id')
            if mod_id:
                level = item.get('mod_level')
                if isinstance(level, bool) or not isinstance(level, int) or not 1 <= level <= 17:
                    gaps.append(f'{mod_id}: saved plan has no valid exact mod level')
                elif mod_id not in catalog.ENTRIES:
                    gaps.append(f'{mod_id}: saved mod identity is outside the catalog')
                else:
                    mods.append({'catalog_id': mod_id, 'level': level,
                                 'shiny': bool(item.get('mod_shiny'))})
            if identity and not entry:
                gaps.append(f'{identity}: saved gear identity is outside the catalog')
    requested = options.get('weapon_id') or None
    if requested and (requested not in catalog.ENTRIES or
                      catalog.ENTRIES[requested]['kind'] != 'weapon'):
        raise ValueError('Choose a catalog reference weapon')
    if selected_weapons:
        if requested and requested not in [identity for identity, _ in selected_weapons]:
            raise ValueError('Reference weapon must match the selected item or saved plan')
        identity, gear = next(((i, row) for i, row in selected_weapons if i == requested),
                              selected_weapons[0])
        upgrade = {field: _number(gear.get(field),
                                  _number(options.get(field), default, field), field)
                   for field, default in (('stars', 1), ('tier', 1), ('calibration', 0))}
    elif requested:
        identity = requested
        upgrade = {field: _number(options.get(field), default, field)
                   for field, default in (('stars', 1), ('tier', 1), ('calibration', 0))}
        gaps.append('Reference weapon is an explicit independent scenario; it is not selected equipment')
    else:
        return None, ['Choose a reference weapon for a mod or armor-only selection'] + gaps
    page_scenario = options.get('item_page_scenario')
    if page_scenario is not None:
        if not isinstance(page_scenario, dict):
            raise ValueError('Item-page scenario must be an object')
        upgrade['item_page_scenario'] = page_scenario
    caller_scenario = options.get('caller_packet_scenario')
    if caller_scenario is not None:
        if not isinstance(caller_scenario, dict):
            raise ValueError('Entered direct-packet scenario must be an object')
        upgrade['caller_packet_scenario'] = caller_scenario
    return {'weapon': {'catalog_id': identity, **upgrade}, 'mods': mods,
            'armor': armors, 'condition_fractions': options.get('condition_fractions') or {}}, gaps


def evaluate(request, plans, component_result):
    options = (request.get('context') or {}).get('published_reference')
    if not isinstance(options, dict) or options.get('enabled') is not True:
        return None
    sides, gaps = {}, {}
    for side in ('left', 'right'):
        sides[side], gaps[side] = _build(request[side], plans, options.get(side) or {})
    if any(sides[side] is None for side in sides):
        return {'status': 'needs_reference_weapon', 'selection_gaps': gaps,
                'game_winner_established': False}
    result = published_reference_model.compare(sides)
    direct_complete = {}
    metric_complete = {}
    safe_omissions = set(published_reference_model.PACKET_POOLS) | published_reference_model.UTILITY_LINES
    for side in ('left', 'right'):
        row = result[side]
        lost_selection = any('no valid exact mod level' in gap or 'outside the catalog' in gap
                             for gap in gaps[side])
        missing_hit = missing_firing = missing_reload = False
        for bonus in row['selected_mod_rows']:
            name = bonus.get('name')
            if name in published_reference_model.TARGET_POOLS and bonus.get('applied_percentage_points') != 0:
                missing_hit = missing_firing = missing_reload = True
            elif bonus.get('applied_pool') is None and name not in safe_omissions:
                if name == 'Reload Speed':
                    missing_reload = True
                elif name == 'Fire Rate':
                    missing_firing = missing_reload = True
                elif name in ('Magazine Capacity', 'Reload Efficiency'):
                    missing_reload = True
                else:
                    missing_hit = missing_firing = missing_reload = True
        direct = row['direct_only']
        already_buffed = ((row.get('weapon_source_native_baseline') or {}).get('baseline_bonus_scope') ==
                          'after_selected_effects_direct_only')
        metric_complete[side] = {
            'reference_hit': not (already_buffed or missing_hit or lost_selection) and direct['reference_hit'] is not None,
            'firing_damage_per_second': not (already_buffed or missing_hit or missing_firing or lost_selection) and direct['firing_damage_per_second'] is not None,
            'reload_cycle_damage_per_second': not (already_buffed or missing_hit or missing_firing or missing_reload or lost_selection) and direct['reload_cycle_damage_per_second'] is not None,
        }
        direct_complete[side] = all(metric_complete[side].values())
    result['direct_reference_complete'] = direct_complete
    result['direct_reference_metric_complete'] = metric_complete
    result['status'] = ('conditional_direct_only' if all(direct_complete.values())
                        else 'partial_reference')
    result['right_over_left_reference_ratios'] = {
        key: value if metric_complete['left'][key] and metric_complete['right'][key] else None
        for key, value in result['right_over_left_reference_ratios'].items()}
    result['selection_gaps'] = gaps
    result['selection_builds'] = sides
    result['not_combined_mechanics'] = {
        'crit_weakspot': 'Existing component sensitivity uses entered baseline pools and branch assumptions; not compounded into reference hit',
        'status_proc': 'Existing typed weapon timelines require source actions, target and class inputs; not added to direct-only rate',
        'mod_core_and_sets': 'Selected main effects and earned set thresholds are audited in component results; activation and magnitude are not silently applied to this reference rate',
    }
    result['component_sensitivity_available'] = bool(component_result.get('component_ratios'))
    component_keys = ('normal', 'crit', 'weakspot', 'crit_weakspot', 'status',
                      'power_surge', 'shock', 'unstable_bomber')
    result['linked_typed_sensitivity'] = {
        key: component_result['component_ratios'].get(key)
        for key in component_keys if key in component_result.get('component_ratios', {})}
    result['linked_main_effects'] = {
        side: [{'item_name': item.get('item_name'), 'status': item.get('status'),
                'output_types': [output.get('type') for output in item.get('outputs') or []],
                'missing': item.get('missing') or []}
               for item in component_result[side].get('typed_main_effects') or []]
        for side in ('left', 'right')}
    result['linked_set_thresholds'] = {
        side: [{'catalog_id': item.get('catalog_id'),
                'required_items': item.get('required_items'),
                'binding_status': item.get('binding_status')}
               for item in (component_result[side].get('evidence_audit') or {}).get('earned_set_thresholds') or []]
        for side in ('left', 'right')}
    timelines = component_result.get('weapon_timeline_scenarios') or {}
    result['linked_weapon_timeline'] = {
        side: {'conditional_damage_per_second': (timelines.get(side) or {}).get('damage_per_second'),
               'unresolved_packet_count': len(((timelines.get(side) or {}).get('damage_projection') or {}).get('unresolved_damage_events') or [])}
        for side in ('left', 'right')} if timelines else None
    timed = options.get('timed')
    if timed is not None:
        if not isinstance(timed, dict):
            raise ValueError('Published timed scenario must be an object')
        runs = {}
        for side in ('left', 'right'):
            one = timed.get(side) or {}
            if not isinstance(one, dict):
                raise ValueError('Each timed side must be an object')
            one = {**{key: timed[key] for key in ('duration_seconds', 'scenario_mode')
                      if key in timed}, **one}
            one['published_item_core_opt_in'] = (
                (request.get('context') or {}).get('core_candidate_opt_in') is True)
            one['core_unknown_variant_opt_in'] = (
                (request.get('context') or {}).get('core_unknown_variant_opt_in') is True)
            one['core_unknown_build_opt_in'] = (
                (request.get('context') or {}).get('core_unknown_build_opt_in') is True)
            runs[side] = published_timed_combat.evaluate(
                result[side], one,
                typed_main_effects=component_result[side].get('typed_main_effects') or [])
        source_targets = [((timed.get(side) or {}).get('source_timeline') or {}).get('target_id')
                          for side in ('left', 'right')]
        # A direct-only side has no packet target field. The explicit shared
        # target confirmation covers that side; populated packet targets must
        # still agree with each other.
        same_source_target = len(set(target for target in source_targets if target)) <= 1
        comparable = (all(row['status'] == 'conditional_modeled_total' for row in runs.values())
                      and runs['left']['duration_seconds'] == runs['right']['duration_seconds']
                      and timed.get('shared_target_confirmed') is True
                      and same_source_target)
        result['timed_scenarios'] = runs
        result['timed_comparison'] = {
            'status': 'conditional_model_comparable' if comparable else 'partial_or_unmatched',
            'right_over_left_damage_per_second': (
                runs['right']['conditional_damage_per_second'] /
                runs['left']['conditional_damage_per_second']
                if comparable and runs['left']['conditional_damage_per_second'] > 0 else None),
            'shared_target_confirmed': timed.get('shared_target_confirmed') is True,
            'source_target_identity_matched': same_source_target,
            'game_winner_established': False}
    result['typed_main_effects_count'] = {side: len(component_result[side].get('typed_main_effects') or [])
                                          for side in ('left', 'right')}
    result['set_thresholds_count'] = {side: len((component_result[side].get('evidence_audit') or {}).get('earned_set_thresholds') or [])
                                      for side in ('left', 'right')}
    return result
