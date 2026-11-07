"""Conservative, reproducible per-identity calculation requirements ledger.

Counts describe installed paths, not game certification or ownership. A requirement
is complete only if its source value and behavior both reach the shared model.
"""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

import catalog
import mod_core_packet
import mod_core_typed
import public_catalog_detail
import published_bonus_lines
import published_main_core
import published_calculator_adapter as adapter
import published_reference_identity
import weapon_timeline_api
import weapon_packet_timeline_api
import published_item_tier
import public_semantic_crosscheck
import published_reference_model
import resonance_suffix

ROOT = Path(__file__).parent
SET_PACKET = ROOT / 'evidence_packets/set-threshold-coverage-v1.json'
AUG_BASIS_AUDIT = ROOT / 'evidence_packets/aug-electron-cloud-basis-audit.json'


def _exact_level_scope(identity, level):
    """Audit one observed ordinary level, separately from all-level identity support."""
    rows, _, _ = public_catalog_detail.calculation_rows(identity, level)
    typed = mod_core_typed.evaluate(identity, level)
    missing = []
    if len(rows) != 4:
        missing.append(f'Only {len(rows)}/4 ordered bonus lines are available')
    resonance_rows = [row for row in rows if str(row.get('stat_type') or '').startswith('resonance_')]
    striving_scope = identity == published_main_core.POWER_STRIVING and level == 9
    bullet_scope = identity == published_main_core.BULLET and level == 12
    try:
        bound_resonance = resonance_suffix.bindings({'catalog_id': identity, 'level': level}) if resonance_rows else []
    except ValueError as error:
        bound_resonance = []
        missing.append(f'Resonance event binding: {error}')
    if len(bound_resonance) != len(resonance_rows):
        missing.append('Not every Resonance bonus line has an executable event binding')
    named_pools = (set(published_reference_model.DIRECT_POOLS) |
                   set(published_reference_model.PACKET_POOLS) |
                   set(published_reference_model.TARGET_POOLS) |
                   set(published_reference_model.UTILITY_LINES))
    for row in rows:
        if row.get('value_percent') is None or row.get('source_conflict'):
            missing.append(f"{row.get('name')}: exact numeric value or source identity missing")
        elif row not in resonance_rows and row.get('name') not in named_pools:
            missing.append(f"{row.get('name')}: no named outgoing or utility handler")
        elif row not in resonance_rows and row.get('condition') and not (
                striving_scope and row['condition'] == 'enemy below player, maximum at 5 meters') and not (
                bullet_scope and row['condition'] == 'aerial hit'):
            missing.append(f"{row.get('name')}: conditional activation needs a source-scoped scenario input")
    main_wired = (typed is not None and typed.get('status') == 'observed_typed_output'
                  and not typed.get('missing') and bool(typed.get('outputs')) and
                  all(output.get('type') == 'stat_pool_delta' and
                      output.get('stat') in ('weapon_damage_percent', 'status_damage_percent',
                          'elemental_damage_percent', 'all_damage_percent',
                          'crit_damage_percent', 'weakspot_damage_percent',
                          'fire_rate_percent', 'reload_efficiency_percent',
                          'power_surge_damage_percent') and
                      output.get('duration_seconds') is None and output.get('condition') is None
                      for output in typed['outputs']))
    no_hp_cost_scope = identity == published_main_core.AGAINST and level == 7
    if no_hp_cost_scope:
        exact = published_main_core.resolve(
            [{'catalog_id': identity, 'level': level}], {'core_no_hp_cost_events': True})
        no_hp_cost_scope = (typed is not None and typed.get('status') == 'observed_typed_output'
            and not exact['gaps'] and exact['handled'] == {identity}
            and exact['pools']['weapon'] == 10 and exact['pools']['status'] == 10
            and exact['applied'][0]['stack_model'] == 'no_hp_cost_events')
        main_wired = main_wired or no_hp_cost_scope
    if striving_scope:
        exact = published_main_core.resolve(
            [{'catalog_id': identity, 'level': level}],
            {'core_no_stamina_loss_events': True})
        striving_scope = (typed is not None and typed.get('status') == 'observed_typed_output'
            and not exact['gaps'] and exact['handled'] == {identity}
            and exact['pools']['weapon'] == 10 and exact['pools']['status'] == 10
            and exact['applied'][0]['stack_model'] == 'no_stamina_loss_events')
        main_wired = main_wired or striving_scope
    if bullet_scope:
        exact = published_main_core.resolve([{'catalog_id': identity, 'level': level}], {})
        bullet_scope = (not exact['gaps'] and exact['handled'] == {identity}
            and exact['pools']['weapon'] == 5 and
            exact['bullet_counter'] == {'every_bullets': 5, 'per_step_percent': 4.0,
                'maximum_percent': 20.0, 'reset': 'new_magazine',
                'source_sha256': mod_core_typed.EXACT[identity, level]['source_sha256']})
        main_wired = main_wired or bullet_scope
    if not main_wired:
        missing.append('Exact main effect is not a fully connected static outgoing pool at this level')
    return {'level': level, 'bonus_lines': len(rows),
            'numeric_lines': sum(row.get('value_percent') is not None and
                                 not row.get('source_conflict') for row in rows),
            'event_lines': len(resonance_rows),
            'main_effect_status': typed.get('status') if typed else 'missing',
            'status': 'conditional_model_path' if not missing else 'partial',
            'missing': missing,
            'scenario_inputs': (['Explicit ordered crit, weakspot and elemental outcomes; named stack expiry/cap model']
                                if resonance_rows else []) +
                               (['Explicit no HP-cost events; the timed extra stacks remain excluded']
                                if no_hp_cost_scope else []) +
                               (['Explicit no stamina-loss events and target-position endpoint (not below or below within 5 m); elevation curve remains excluded']
                                if striving_scope else []) +
                               (['Finite ordered bullet consumption, magazine reload boundaries and explicit aerial-hit fraction (0 or 1 endpoint)']
                                if bullet_scope else [])}


def requirement(name, state, evidence, wired_path=None, missing=None, action=None, owner=None, source=None):
    return {'name': name, 'state': state, 'evidence': evidence,
            'wired_path': wired_path, 'missing': missing, 'next_action': action,
            'owner': owner, 'source': source}


def _mod(entry):
    identity = entry['id']
    grid = [published_bonus_lines.GRID.get((identity, level)) for level in range(1, 18)]
    available = sum(bool(profile and profile['status'].startswith('published_formula_candidate'))
                    for profile in grid)
    rows10, status10, _ = public_catalog_detail.calculation_rows(identity, 10)
    numeric10 = sum(row.get('value_percent') is not None and not row.get('source_conflict') for row in rows10)
    semantic_conflicts = public_semantic_crosscheck.layout_conflicts(identity)
    withheld_levels = []
    if semantic_conflicts:
        for checked_level in range(1, 18):
            checked_rows, _, _ = public_catalog_detail.calculation_rows(identity, checked_level)
            if any(row.get('published_layout_conflict') and row.get('value_percent') is None
                   for row in checked_rows):
                withheld_levels.append(checked_level)
    packet = mod_core_packet.ENTRIES[identity]
    applicability = mod_core_packet.APPLICABILITY[identity]['current_comparison_status']
    exact_levels = sorted(level for (item, level) in mod_core_typed.EXACT if item == identity)
    exact_level_scope = [_exact_level_scope(identity, level) for level in exact_levels]
    scoped_ready = [row['level'] for row in exact_level_scope
                    if row['status'] == 'conditional_model_path']
    public_core = published_main_core.PUBLIC.get(identity)
    core_text = entry.get('primary_effect') or ''
    req = [requirement('four ordered bonus lines, level 1–17',
                       'candidate_numeric_at_lv10' if numeric10 == len(rows10) and rows10 else 'partial_or_missing',
                       'published_formula_candidate' if available else 'catalog_or_observed_only',
                       'public_catalog_detail.calculation_rows → published_reference_model._mods' if rows10 else None,
                       None if available == 17 and numeric10 == len(rows10) and rows10 else
                       f'{17-available} levels lack fixed-layout candidates; Lv10 has {numeric10}/{len(rows10)} numeric active rows',
                       'Resolve the exact identity layout or remaining stat conversion; keep legacy individual rolls separate',
                       'mod source and formula', source=rows10[0].get('source') if rows10 else None)]
    if semantic_conflicts:
        differences = '; '.join(
            f"line {index + 1}: held {details[0]['observed_name']} vs published "
            f"{details[0]['published_name']} ({', '.join(details[0]['reasons'])})"
            for index, details in sorted(semantic_conflicts.items()))
        held_sources = sorted({detail['observed_source'] for details in semantic_conflicts.values()
                               for detail in details if detail.get('observed_source')})
        published_sources = sorted({detail['published_source'] for details in semantic_conflicts.values()
                                    for detail in details if detail.get('published_source')})
        req[0].update(state='held_semantic_layout_conflict_partial',
                      evidence='held_exact_identity_lines_vs_published_slot_suffix_layout',
                      source=held_sources[0] if held_sources else None,
                      held_source_refs=held_sources,
                      published_source_refs=published_sources,
                      missing=(f'{differences}; '
                               f'published candidates are withheld at levels {withheld_levels} where no held numeric value covers them. '
                               'Held exact values remain available at their observed tiers.'),
                      next_action='Acquire the source-native stat ID/localization key or exact current identity wording for the disputed layout; verify bucket, condition and tier progression before restoring unobserved candidates')
    lunar_rows = [row for row in rows10 if public_catalog_detail.low_hp_maximum(row) is not None]
    resonance_rows = [row for row in rows10 if row.get('value_percent') is None and
                      str(row.get('stat_type') or '').startswith('resonance_') and
                      (row.get('components') or {}).get('per_stack_percent') is not None]
    observed_lunar_rows = [row for row in rows10 if row.get('value_percent') is not None and
                           'low hp' in str(row.get('condition') or '').lower()]
    non_scalar_class = ('published_lunar_low_hp_maximum' if lunar_rows else
                        'published_resonance_event_stack' if resonance_rows else
                        'observed_lunar_maximum_curve_unknown' if observed_lunar_rows else None)
    def non_scalar_requirement(state, wired_path, missing, action):
        if semantic_conflicts:
            # A supported stack or bound must not erase an independent held
            # tooltip conflict on another bonus line.
            req.append(requirement('non-scalar bonus behavior', state,
                                   'published_formula_candidate_or_held_observation',
                                   wired_path, missing, action, 'mod mechanics'))
        else:
            req[0].update(state=state, wired_path=wired_path,
                          missing=missing, next_action=action)
    if lunar_rows:
        maxima = ', '.join(f"{row['name']} up to {row['components']['max_bonus_percent']}%" for row in lunar_rows)
        non_scalar_requirement('candidate_bounded_low_hp',
            'component_compare._rows [0, maximum] / published_reference_model._mods entered fraction',
            f'Lv10 sourced maxima: {maxima}. HP scaling curve and uptime are not published; a specific HP percentage does not fix the magnitude. Defensive reduction is not an outgoing-damage pool.',
            'Source the HP-to-bonus curve for exact game values; until then use an explicitly entered magnitude and uptime or the sourced 0-to-maximum bound')
    elif resonance_rows:
        rules = ', '.join(f"{row['name']}: +{row['components']['per_stack_percent']}% per qualifying instance, "
                          f"cap {row['components']['max_stacks']}, {row['components']['duration_seconds']}s"
                          for row in resonance_rows)
        non_scalar_requirement('candidate_timed_operator_guided_and_advanced',
            'published_reference_selection → published_timed_combat → published_timed_scheduler / component_compare.integrated_combat → integrated_event_model.evaluate → resonance_suffix',
            f'Lv10 timed rules are sourced ({rules}). Guided and advanced scenarios require explicit packet outcomes; current-game stack refresh/overflow and crit/weakspot bucket semantics are not established.',
            'Validate stack refresh, overflow, and crit/weakspot buckets with a controlled same-target contrast; retain the explicit conditional model meanwhile')
    elif observed_lunar_rows:
        non_scalar_requirement('exact_maximum_curve_unknown', None,
            'Exact photographed Lv10 maxima are known, but the HP-to-bonus curve and uptime remain unpublished.',
            'Use an explicit magnitude/uptime or sourced endpoint bound; obtain the HP curve before claiming a specific HP value produces the maximum')
    if exact_levels:
        core_state = 'exact_level_typed_partial'
        core_path = 'mod_core_typed.evaluate; published_main_core / published_timed_combat where operator supported'
        core_missing = f'Exact photographed main effects cover only levels {exact_levels}; unobserved levels and variable triggers are not inferred'
        evidence = 'exact_observed_level_scoped'
        if identity == 'mod:boots_mod:against-all-odds-deviant-energy':
            core_state = 'exact_lv12_base_guided_opt_in_partial'
            core_path = 'mod_core_typed Lv12 source gate → published_main_core.resolve → published_timed_combat'
            core_missing = ('Held-video Lv12 base +10% Weapon/Status is connected once only with unknown-variant and '
                            'unknown-build opt-ins; HP-cost stack ordering/expiry and other Field Guide levels remain unresolved')
            evidence = 'held_game_video_unknown_variant_and_build'
        elif identity == 'mod:weapon_mod:static-shock-survival':
            core_state = 'exact_lv11_instant_bonus_and_status_expiry_conditional'
            core_path = 'mod_core_typed.evaluate → published_timed_combat._typed_pools → sourced_proc_timed_adapter [keyword damage] / published_timed_scheduler._status_duration_model [target status expiry]'
            core_missing = ('Exact Lv11 +20% Power Surge damage applies to explicitly tagged packets and -50% '
                            'changes a separately modeled target status lifetime, not damage tick count. The '
                            'current source does not establish a universal status base lifetime, refresh behavior '
                            'or downstream condition eligibility; other Field Guide levels remain unbound. '
                            'Critical Pulse orb pulses retain their independent weapon schedule.')
        elif identity == 'mod:gloves_mod:elemental-overload-resonance':
            core_state = 'exact_lv9_static_guided_connected_partial_levels'
            core_path = 'mod_core_typed.evaluate → published_timed_combat._typed_pools [Elemental DMG]'
            core_missing = 'Exact Lv9 +18% Elemental DMG is connected; other Field Guide main-effect levels are not source-bound'
    elif public_core and public_core.get('normal_source_item_id'):
        core_state = 'community_candidate_partial'
        core_path = 'published_main_core._community_text → published_timed_combat'
        core_missing = 'Community effect rank is not mapped to Field Guide level; source text/activation must be chosen explicitly'
        evidence = 'community_item_unranked'
    elif packet['coverage'] == 'supported_operator' and applicability not in ('blocked_legacy_superseded', 'blocked_source_conflict'):
        core_state = 'typed_template_level_unbound'
        core_path = 'mod_core_packet.evaluate / mod_core_typed.evaluate under explicit candidate mode'
        core_missing = 'Current item and level magnitude or effect version not bound to typed template'
        evidence = packet['primary'].get('evidence_class') or 'community_snapshot'
    else:
        core_state = 'missing_or_conflicting'
        core_path = None
        core_missing = f"{packet['coverage']}; {applicability}; no complete current level-bound effect rule"
        evidence = packet['primary'].get('evidence_class') or 'unknown'
    req.append(requirement('main effect, condition, duration and stacks', core_state, evidence,
                           core_path, core_missing,
                           ('Validate the Lv12 HP-cost stack recipient, ordering and expiry with one controlled HP-cost contrast; source other levels separately'
                            if identity == 'mod:boots_mod:against-all-odds-deviant-energy' else
                            'Verify current Power Surge target-status lifetime and refresh/condition ordering from an exact source or one controlled proc-and-expiry contrast; bind other Field Guide levels separately'
                            if identity == 'mod:weapon_mod:static-shock-survival' else
                            'Source the exact main-effect strength at another Field Guide level before extending the Lv9 static binding'
                            if identity == 'mod:gloves_mod:elemental-overload-resonance' else
                            'Source current exact effect wording and bind its value, trigger and level independently of four-line progression'),
                           'mod mechanics', source=(public_core or {}).get('normal_source_item_url') or packet['primary'].get('source_url')))
    # Whole-identity completion is derived from every level. A working level
    # scenario remains visible even when other levels or mechanics are blocked.
    complete = (len(exact_levels) == 17 and len(scoped_ready) == 17 and
                not any(row.get('source_conflict') for level in range(1, 18)
                        for row in public_catalog_detail.calculation_rows(identity, level)[0]))
    connected = bool(numeric10 or exact_levels or (public_core and public_core.get('normal_source_item_id')) or (packet['primary'].get('rule') and
                     applicability not in ('blocked_legacy_superseded', 'blocked_source_conflict')))
    return _record(entry, 'mod', req, 'partial' if connected else 'display_only', complete,
                   {'fixed_layout_candidate_levels': available, 'lv10_numeric_active_rows': numeric10,
                    'lv10_active_rows': len(rows10), 'exact_main_effect_levels': exact_levels,
                    'scoped_exact_level_paths': exact_level_scope,
                    'scoped_exact_level_model_ready': scoped_ready,
                    'non_scalar_bonus_class':non_scalar_class,
                    'core_template_coverage': packet['coverage'], 'core_applicability': applicability,
                    'main_effect_text':core_text,
                    'bonus_lines_lv10':[{'name':r.get('name'),'value_percent':r.get('value_percent'),
                                         'condition':r.get('condition'),'source_status':r.get('source_status'),
                                         'source_conflict':bool(r.get('source_conflict')),
                                         'structured_components':r.get('components') if r.get('value_percent') is None else None}
                                        for r in rows10]})


def _weapon(entry):
    identity = entry['id']
    try:
        baseline = adapter.load_published_weapon_baseline(adapter.PACKETS, identity)
    except LookupError:
        baseline = None
    event = weapon_timeline_api.WEAPONS.get(identity)
    packet = weapon_packet_timeline_api.BINDINGS.get(identity)
    page_row=published_item_tier.ROWS.get(identity) or {}
    page_tiers=sorted(int(t) for t in page_row.get('tiers',{}))
    star_cells={str(tier):sorted(int(star) for star in page_row['tiers'][str(tier)]['star_damage'])
                for tier in page_tiers}
    req = [requirement('item-ID-anchored damage by tier, stars and calibration', 'tier_page_candidate_partial' if page_tiers else 'blocked',
                       'exact_named_item_tier_pages_with_explicit_unit_hypothesis' if page_tiers else
                       'unanchored_calculator_import_or_no_matched_item_page',
                       'published_reference_model.build explicit item_page_scenario' if page_tiers else
                       'published_calculator_adapter.derive_published_weapon_progression (quarantined)' if baseline else None,
                       'Exact Tier '+','.join(map(str,page_tiers))+' item pages and '+str(sum(map(len,star_cells.values())))+' sourced star cells exist; missing cells, calibration and damage unit remain unresolved' if page_tiers else
                       'Imported damage has no proven tier/star basis; the KAM pages previously compared are different named weapons, and matching AUG tier pages refute the generic multiplier.',
                       'Bind exact named item tier pages and source star/calibration/unit; do not treat imported weapon_list damage as T1',
                       'weapon numeric source', source=(published_item_tier.ROWS[identity]['tiers'][str(page_tiers[0])]['wikily_url'] if page_tiers else
                                                        'https://wikily.gg/once-human/items/10451401'))]
    stats = (baseline or {}).get('stats') or {}
    timing = {'rpm': page_row.get('rpm_reference') or stats.get('rpm',stats.get('fire_rate')),
              'magazine': page_row.get('magazine_reference') or stats.get('magazine',stats.get('magazine_capacity')),
              'reload_seconds':stats.get('reload_seconds',stats.get('reload_time_seconds')),
              'projectiles_per_shot':stats.get('projectiles_per_shot')}
    missing_timing = [key for key,value in timing.items() if value is None]
    req.append(requirement('fire rate, magazine, reload seconds and projectiles',
                           'candidate_partial' if page_row or baseline else 'missing',
                           'community_exact_item_page_rpm_magazine' if page_row else
                           'published_calculator_reference_unverified_basis' if baseline else 'community_item_page_unbound',
                           'published_item_tier.explicit_page_scenario / published_calculator_adapter.derive_timing' if page_row else
                           'published_calculator_adapter.derive_timing / published_timed_scheduler' if baseline else None,
                           ', '.join(missing_timing) if page_row or baseline else 'No matched item page or calculator baseline for timing',
                           'Source exact reload seconds and projectile unit for the named item/tier; do not convert reload score to seconds',
                           'weapon numeric source', source=page_row.get('tiers',{}).get('1',{}).get('wikily_url') or (baseline or {}).get('source_url')))
    req.append(requirement('unique damage/proc effects and event ordering',
                           'representative_timeline_partial' if event or packet else 'unbound',
                           (packet or event or {}).get('evidence_status','catalog_description'),
                           'weapon_timeline_api / weapon_packet_timeline_api → published_timed_scheduler' if event or packet else None,
                           'Caller inputs, packet eligibility, target and PRNG semantics remain scoped' if event or packet else
                           'No source-linked executable weapon timeline binding',
                           'Bind exact current effect to event hooks; supply target and trigger inputs without inventing them',
                           'weapon mechanics', source=(packet or event or {}).get('source')))
    if identity == 'weapon:mg4-conflicting-memories':
        req[-1]['missing'] = ('The older 12-hit/32-round/cap-5 rule predates the confirmed September 2026 rework. '
                              'The current hit threshold, Memory Storm behavior and final coefficients are not sourced; '
                              'only an explicitly selected historical_release scenario can run.')
        req[-1]['next_action'] = ('Obtain the shipped current MG4 tooltip or an exact official final rule; '
                                   'implement and test that version separately from the historical binding.')
        req[-1]['evidence'] = 'historical_release_only_current_rework_unresolved'
    if identity == 'weapon:aug-electron-cloud':
        req[0]['name'] = 'item-ID-anchored damage by tier/stars and applicable blueprint attributes'
        req[0]['missing'] = ('Tier 5 stars 2–6 lack an exact item-page table; displayed damage unit and chosen '
                             'calibration blueprint attributes are unresolved. Classic calibration level was removed before AUG release.')
        req[0]['next_action'] = ('Source named Tier 5 star cells and separately model selected calibration blueprint '
                                  'attributes; use one controlled direct-hit contrast for page damage unit')
        req[1]['missing'] = ('Exact item pages supply 720 RPM and 40 rounds. Base reload seconds and damage-per-shot '
                             'projectile count are unanchored; OnceHumanDB 2.3 seconds/score 47 has unknown tier and configuration.')
        req[1]['next_action'] = ('Source exact crafted AUG base reload seconds or use an explicit scenario time; '
                                  'do not convert score 47 to seconds. Confirm projectile count for damage unit.')
    return _record(entry, 'weapon', req, 'partial' if baseline or event or packet or page_tiers else 'display_only', False,
                   {'name_matched_calculator_baseline': bool(baseline),
                    'damage_basis_anchored': False, 'timing_fields_present': [key for key in timing if timing[key] is not None],
                    'timeline_binding': bool(event or packet),'unique_effect_text':entry.get('effect'),
                    'exact_named_item_tiers':page_tiers,
                    'exact_named_item_star_cells':star_cells,
                    'source_basis_audit':str(AUG_BASIS_AUDIT.relative_to(ROOT)) if identity == 'weapon:aug-electron-cloud' else None})


def _armor(entry):
    identity = entry['id']
    rarity, alias = published_reference_identity.armor_binding(identity, entry.get('rarity'))
    slot = {'chest':'top'}.get(entry['slot'],entry['slot'])
    table = adapter.load_published_armor_table()
    try:
        profile = adapter.armor_stats(table,slot=slot,rarity=rarity,stars=1,tier=1)
    except (LookupError, KeyError, TypeError):
        profile = None
    stats = (profile or {}).get('stats') or {}
    known = [key for key in ('hp','psi_intensity','pollution_resist') if stats.get(key) is not None]
    effect = entry.get('effect') or entry.get('unique_effect') or ''
    wind_supported = identity == 'armor:wind-intepreter-cap'
    gilded_supported = identity == 'armor:gilded-gauntlets'
    req = [requirement('base HP, Psi and pollution resistance',
                       'published_candidate_partial' if known else 'missing',
                       'published_armor_table_slot_rarity_candidate' if known else 'no_nonzero_published_row',
                       'published_calculator_adapter.armor_stats → published_reference_model' if known else None,
                       ', '.join(key for key in ('hp','psi_intensity','pollution_resist') if key not in known) or
                       'Item-specific rarity/upgrade match is a source candidate, not proven current values',
                       'Verify item rarity and nonzero table row; retain catalog rarity conflicts separately',
                       'armor numeric source', source=entry.get('source_url'))]
    req.append(requirement('unique effect and set membership',
                           'current_official_conditional' if wind_supported or gilded_supported else
                           'selected_set_candidate' if entry.get('set_id') else 'unique_effect_unresolved',
                           'official_release' if wind_supported or gilded_supported else 'community_catalog_or_dated_release',
                           'published_unique_armor.wind_intepreter → published_timed_combat' if wind_supported else
                           'published_timed_scheduler → sourced_proc_timed_adapter → integrated_event_model [Burn crit eligibility]' if gilded_supported else
                           'published_set_thresholds via selected set count' if entry.get('set_id') else None,
                           'Wind bullet source and reload retention require an explicit named scenario' if wind_supported else
                           'Burn crit outcome, crit bonus and source packet damage/timing remain explicit scenario inputs; no universal Status crit rule' if gilded_supported else
                           'Set threshold effect currentness and any unique item trigger are independently scoped',
                           'Resolve Wind ammo source/retention from a current tooltip or controlled test' if wind_supported else
                           'Source exact Burn packet coefficient, crit chance and crit bonus for the selected weapon; validate crit outcome in a bounded parse' if gilded_supported else
                           'Bind current unique effect and source-backed threshold rule; do not infer from matching base table',
                           'armor/set mechanics', source='https://www.oncehuman.game/news/update/20260709/40780_1307147.html' if wind_supported else
                           'https://www.oncehuman.game/news/update/20260121/40780_1282991.html' if gilded_supported else entry.get('source_url')))
    return _record(entry,'armor',req,'partial' if known or entry.get('set_id') or wind_supported or gilded_supported else 'display_only',False,
                   {'published_reference_stats_present':known,'reference_rarity':rarity,
                    'rarity_identity_evidence':alias,'set_id':entry.get('set_id'),
                    'unique_effect_text':effect})


def _record(entry,kind,requirements,category,complete,extra):
    return {'catalog_id':entry['id'],'kind':kind,'name':entry['name'],
            'slot':entry.get('slot'),'category':'complete' if complete else category,
            'scenario_scope':'explicit source-labelled published what-if; not game-verified complete DPS',
            'requirements':requirements,'known_missing':[r['missing'] for r in requirements if r['missing']],
            'unknown_requirements':['Unlisted or patch-changed interactions may exist'],
            'next_owner_actions':[{'owner':r['owner'],'action':r['next_action']} for r in requirements if r['missing']],
            **extra}


def build():
    records = []
    for entry in catalog.DATA['mods']:
        if not entry.get('family_only'):
            records.append(_mod(entry))
    for entry in catalog.DATA['weapons']:
        records.append(_weapon(entry))
    for entry in catalog.DATA['armor']:
        records.append(_armor(entry))
    threshold_rows = json.loads(SET_PACKET.read_text())['records']
    for row in threshold_rows:
        entry = next(item for item in catalog.DATA['sets'] if item['id']==row['catalog_set_id'])
        state = row['execution']
        complete = state == 'current_official_conditional'
        missing = (None if complete else row.get('remaining_action') or
                   'Current effect, combination, or event/condition inputs are not completely source-bound')
        req = [requirement('equipped piece count and threshold behavior',
                           state,row['source_status'],
                           'published_timed_combat._set_pools' if complete or state=='current_official_endpoint_only' else
                           'published_set_thresholds.evaluate → published_timed_combat' if state != 'unresolved' else None,
                           missing,
                           row.get('remaining_action') or 'Resolve current wording, value and trigger from an item-specific source',
                           'set mechanics',source=(row.get('source_refs') or [None])[0])]
        records.append({'catalog_id':entry['id']+'#'+str(row['required_items']),
                        'kind':'set_threshold','name':entry['name'],'required_items':row['required_items'],
                        'catalog_description':row['catalog_description'],
                        'catalog_description_currentness':row['catalog_description_currentness'],
                        'category':'complete' if complete else 'partial' if state!='unresolved' else 'display_only',
                        'scenario_scope':'selected equipped pieces; dated official or explicit community what-if',
                        'requirements':req,'known_missing':[req[0]['missing']] if req[0]['missing'] else [],
                        'unknown_requirements':['Later patch changes may supersede this threshold'],
                        'next_owner_actions':[{'owner':'set mechanics','action':req[0]['next_action']}] if missing else [],
                        'execution':state})
    counts={kind:dict(Counter(r['category'] for r in records if r['kind']==kind))
            for kind in ('mod','weapon','armor','set_threshold')}
    non_scalar_counts=dict(Counter(r['non_scalar_bonus_class'] for r in records
                                   if r['kind']=='mod' and r['non_scalar_bonus_class']))
    scoped_ready_levels = sum(len(r['scoped_exact_level_model_ready']) for r in records
                              if r['kind'] == 'mod')
    scoped_ready_identities = sum(bool(r['scoped_exact_level_model_ready']) for r in records
                                  if r['kind'] == 'mod')
    return {'schema_version':1,'definition':
            'Complete means all item-specific required stats and known applicable effects wired for explicit supported scenarios across the relevant levels. Partial means at least one numeric or behavioral path exists but a known item requirement remains. Display-only means no usable path established. Global game damage validation is a separate blocker.',
            'global_damage_blocker':'Unanchored imported weapon numbers were removed from active sources. Five blueprint-linked item-page families support explicit display-unit scenarios; exact selected damage units, projectile counts, reload seconds, calibration and remaining weapons need source binding or caller inputs.',
            'counts':counts,'non_scalar_bonus_lv10':non_scalar_counts,
            'scoped_exact_level_model_ready': {'levels': scoped_ready_levels,
                                               'identities': scoped_ready_identities,
                                               'meaning': 'All four exact lines and the scoped exact main effect have a connected conditional model path at that observed level; required event and encounter inputs remain explicit, and global game validation is separate.'},
            'total_records':len(records),'records':records}


if __name__ == '__main__':
    print(json.dumps(build(),indent=2))
