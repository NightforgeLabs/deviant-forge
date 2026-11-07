"""Read-only, per-selection explanation of what the component formula includes.

This deliberately does not turn catalog text, observed equipped values, or
historical set descriptions into numerical modifiers.
"""
from collections import Counter
from hashlib import sha256
from math import isfinite
from pathlib import Path

import mod_rolls


SLOTS = ('primary', 'secondary', 'melee', 'helmet', 'top', 'bottoms',
         'shoes', 'gloves', 'mask')
ARMOR_SLOTS = {'helmet', 'top', 'bottoms', 'shoes', 'gloves', 'mask'}
SHOCK17_SOURCE_REF = 'libfile_84a17de486208191951ea249c448e8c6'
SHOCK17_IMAGE_NAME = 'shock-rampage-power-surge-lv17-2d4bd6b5.png'
SHOCK17_IMAGE_SHA256 = '2d4bd6b5c0a9993759803ec593d85059f079d469e23f2d26d94992a47c589abe'


def _existing_source_image(source_ref):
    if source_ref != SHOCK17_SOURCE_REF:
        return None
    image = Path(__file__).resolve().parent / 'data' / 'media' / 'evidence' / SHOCK17_IMAGE_NAME
    if not image.is_file():
        return None
    with image.open('rb') as stream:
        if sha256(stream.read()).hexdigest() != SHOCK17_IMAGE_SHA256:
            return None
    return '/media/evidence/' + SHOCK17_IMAGE_NAME


def _observed_evidence_matches(owned, selection, stats, observed):
    """Do not borrow a tooltip after a level/variant edit or identity drift."""
    if not isinstance(observed, dict) or not observed.get('source_ref') or not isinstance(observed.get('attribute_lines'), list):
        return False
    level = owned.get('level')
    if not isinstance(level, int) or selection.get('mod_level') != level:
        return False
    for source_level in (stats.get('original_observed_level'),
                         (stats.get('screenshot_import') or {}).get('observed_level'),
                         observed.get('observed_level')):
        if source_level is not None and source_level != level:
            return False
    catalog_id = (owned.get('effects') or {}).get('catalog_id')
    if observed['source_ref'] == SHOCK17_SOURCE_REF:
        return (catalog_id == 'mod:weapon_mod:shock-rampage-power-surge' and
                owned.get('slot') == 'weapon_mod' and owned.get('variant') == 'Power Surge' and level == 17)
    return (observed.get('catalog_id') == catalog_id and observed.get('slot') == owned.get('slot')
            and observed.get('variant') == owned.get('variant') and observed.get('observed_level') == level)


def _row(text, status, *, stat_type=None, source=None, next_action=None,
         activation_status=None):
    return {'text': str(text or 'Effect details unknown'), 'status': status,
            'stat_type': stat_type, 'source': source, 'next_action': next_action,
            'activation_status': activation_status}


def _observed_lines(stats):
    return stats.get('observed_attribute_lines') or []


def _confirmed_manual_baseline(values):
    if not isinstance(values, dict) or values.get('confirmed_pre_mod') is not True:
        return None
    fields = ('damage', 'rpm', 'magazine')
    if not all(isinstance(values.get(key), (int, float)) and
               not isinstance(values[key], bool) and isfinite(values[key]) and
               values[key] > 0 for key in fields):
        return None
    return {key: values[key] for key in fields}


def report(slots, owned_inventory, entries, accessory_items, *, active_weapon_slot='primary',
           tech_policy='exclude_unknown', all_damage_model='exclude_unverified',
           baseline_mode='manual', manual_baseline=None, set_groups=None):
    """Explain selected gear and individual rows without changing build state."""
    if not isinstance(slots, dict):
        raise ValueError('Saved build slots must be an object')
    resolved = mod_rolls.equipped_build_modifiers(
        slots, owned_inventory, active_weapon_slot=active_weapon_slot)
    aggregate = mod_rolls.aggregate(resolved['modifiers'], tech_policy=tech_policy,
                                    all_damage_model=all_damage_model)
    used = {(r.get('owned_instance_id'), r.get('row_index')) for r in aggregate['used_rows']}
    gated = {(r.get('owned_instance_id'), r.get('row_index')) for r in aggregate['tech_gated_rows']}
    excluded = {(r.get('owned_instance_id'), r.get('row_index')) for r in aggregate['unmodeled_rows']}
    issues = {}
    for issue in resolved['unresolved']:
        issues.setdefault(issue['slot'], []).append(issue)
    items = []
    counts = Counter()
    activation_counts = Counter()
    missing_items = 0
    for slot in SLOTS:
        selection = slots.get(slot) or {}
        identity = selection.get('catalog_id')
        if not identity:
            continue
        entry = entries.get(identity) or {}
        inactive = slot in ('primary', 'secondary', 'melee') and slot != active_weapon_slot
        gear = {'kind': 'weapon' if slot in ('primary', 'secondary', 'melee') else 'armor',
                'slot': slot, 'name': entry.get('display_name') or entry.get('name') or identity,
                'catalog_id': identity, 'status': 'inactive_weapon' if inactive else 'not_modeled',
                'rows': [], 'next_action': None}
        if inactive:
            gear['rows'].append(_row('Inactive weapon: its modifiers do not enter this comparison.',
                                     'inactive_weapon'))
        elif slot in ('primary', 'secondary', 'melee'):
            preview = (baseline_mode == 'tier_v_preview' and identity == 'weapon:aug-electron-cloud'
                       and selection.get('tier') == 5 and selection.get('stars') == 5)
            manual = (_confirmed_manual_baseline(manual_baseline)
                      if baseline_mode == 'manual' else None)
            gear['status'] = 'partial' if preview else 'manual_what_if' if manual else 'missing_baseline'
            if not preview and not manual:
                gear['next_action'] = 'Record this exact weapon’s damage, fire rate and magazine before selected effects.'
            gear['rows'].append(_row(
                'Five-star Tier V AUG crafting values used as an illustrative pre-mod baseline.'
                if preview else
                f"Manually entered pre-mod baseline: {manual['damage']:g} damage, {manual['rpm']:g} RPM, {manual['magazine']:g} magazine."
                if manual else 'This saved weapon needs its own confirmed pre-mod baseline.',
                'included_reference' if preview else 'manual_what_if' if manual else 'missing_baseline',
                source='libfile_b01c1d5ded9081918892fbd7b7f674b7' if preview else
                       'User-confirmed Compare form; not source-verified or saved' if manual else None,
                next_action=None if preview or manual else 'Enter and confirm pre-mod damage, rate and magazine for this exact weapon.'))
            gear['rows'].append(_row('Weapon keyword, Power Surge and orb behavior are not inferred from item identity.',
                                     'not_modeled',
                                     next_action='Record event rate, damage and field conditions before modeling them.'))
            if selection.get('weapon_readout'):
                gear['rows'].append(_row('Saved equipped readout is observed after gear effects; it is not a pre-mod baseline.',
                                         'observed_only', source=(selection['weapon_readout'] or {}).get('source_ref')))
        else:
            gear['rows'].append(_row('Armor base stats and any unique effect are not included in this damage formula.',
                                     'not_modeled', source=entry.get('source_url'),
                                     next_action='Verify the current item effect and applicable calculation rule.'))
        effect = entry.get('primary_effect') or entry.get('effect')
        if effect:
            gear['rows'].append(_row(effect, 'not_modeled', source=entry.get('source_url'),
                                     next_action='Verify the effect condition and calculation rule.'))
        items.append(gear)

        if slot in ('primary', 'secondary', 'melee'):
            profile = selection.get('calibration_profile') or {}
            if profile or selection.get('calibration_blueprint') or selection.get('calibration_bonus'):
                name = profile.get('blueprint_name') or selection.get('calibration_blueprint') or 'Calibration'
                calibration = {'kind': 'calibration', 'slot': slot, 'name': name,
                               'status': 'inactive_weapon' if inactive else 'not_modeled',
                               'rows': [], 'next_action': 'Compare this exact saved calibration separately; the Energy/Rapid branches do not apply the saved choice automatically.'}
                fixed = profile.get('fixed_effects') or selection.get('calibration_bonus')
                if fixed:
                    calibration['rows'].append(_row(fixed, 'inactive_weapon' if inactive else 'not_modeled',
                                                     source=profile.get('source_ref')))
                for roll in profile.get('rolls') or []:
                    calibration['rows'].append(_row(f"{roll.get('stat', 'Unknown roll')} {roll.get('value_percent', '?')}%",
                                                     'inactive_weapon' if inactive else 'not_modeled',
                                                     source=profile.get('source_ref')))
                if not calibration['rows']:
                    calibration['rows'].append(_row('Calibration effects or rolls have not been recorded.',
                                                     'missing_evidence', source=profile.get('source_ref')))
                items.append(calibration)
            for attachment_slot, accessory_id in (selection.get('accessories') or {}).items():
                accessory = accessory_items.get(accessory_id) or {}
                accessory_rows = [_row(f'{label} {value:+g}%', 'inactive_weapon' if inactive else 'not_modeled',
                                       source=accessory.get('source_ref'))
                                  for label, value in accessory.get('effects') or []]
                items.append({'kind': 'accessory', 'slot': slot, 'attachment_slot': attachment_slot,
                              'name': accessory.get('name') or accessory_id, 'status': 'inactive_weapon' if inactive else 'not_modeled',
                              'rows': accessory_rows or [_row('Accessory effect details unknown.', 'missing_evidence')],
                              'next_action': 'Accessory handling and combat stacking need a verified rule.'})

        mod_id = selection.get('mod_id')
        if not mod_id:
            continue
        mod_entry = entries.get(mod_id) or {}
        mod = {'kind': 'mod', 'slot': slot,
               'name': mod_entry.get('display_name') or mod_entry.get('name') or mod_id,
               'catalog_id': mod_id, 'level': selection.get('mod_level'),
               'status': 'inactive_weapon' if inactive else 'missing_evidence',
               'rows': [], 'next_action': None}
        if inactive:
            mod['rows'].append(_row('Selected on an inactive weapon; excluded from this comparison.',
                                     'inactive_weapon'))
            items.append(mod)
            continue
        slot_issues = issues.get(slot) or []
        candidates = [item for item in owned_inventory if item.get('kind') == 'mod_unlock'
                      and (item.get('effects') or {}).get('catalog_id') == mod_id
                      and (selection.get('mod_level') is None or item.get('level') == selection['mod_level'])
                      and (selection.get('mod_inventory_id') is None or item.get('id') == selection['mod_inventory_id'])]
        owned = candidates[0] if len(candidates) == 1 else None
        if owned:
            mod['owned_instance_id'] = owned['id']
            stats = owned.get('stats') or {}
            observed = stats.get('observed_tooltip') or {}
            if mod_rolls.observed_row_order_conflict(stats):
                mod['row_order_discrepancy'] = {
                    'observed_attribute_lines': list(stats['observed_attribute_lines']),
                    'tooltip_attribute_lines': list(observed['attribute_lines']),
                    'observed_source': owned.get('source_observation'),
                    'tooltip_source': observed.get('source_ref'),
                    'unique_content_count': sum((Counter(stats['observed_attribute_lines']) |
                                                 Counter(observed['attribute_lines'])).values()),
                    'application_blocked': True,
                }
            if _observed_evidence_matches(owned, selection, stats, observed):
                staged_rows = mod_rolls.parse_rows(observed['attribute_lines'],
                                                   source={'frame': observed['source_ref']})
                mod['existing_evidence'] = {
                    'source_ref': observed['source_ref'],
                    'source_name': 'image(20261024-114335).png' if observed['source_ref'] == 'libfile_84a17de486208191951ea249c448e8c6' else None,
                    'image_url': _existing_source_image(observed['source_ref']),
                    'core_effect': observed.get('core_effect'),
                    'attribute_lines': [str(line) for line in observed['attribute_lines']],
                    'transcription_note': ('The saved fourth line abbreviates the full tooltip wording; compare it with the original image before any formal attachment.'
                                           if observed['source_ref'] == SHOCK17_SOURCE_REF else None),
                    'typed_preview': [{'raw_text': row['raw_text'], 'stat_type': row['stat_type'],
                                       'visible_magnitude': row['visible_magnitude'],
                                       'unit': row['unit'], 'calculation_status': row['calculation_status'],
                                       'tech_activation': row['tech_activation'],
                                       'confidence': row['confidence']} for row in staged_rows],
                    'status': 'Recorded tooltip; rows are not attached as typed numerical evidence.',
                }
            elif isinstance(observed, dict) and observed.get('source_ref'):
                mod['evidence_mismatch'] = 'The stored tooltip does not prove this selected mod identity, suffix and level; review its provenance before using it.'
            typed = stats.get('typed_modifiers') or []
            if typed:
                for index, typed_row in enumerate(typed):
                    key = (owned['id'], typed_row.get('row_index', index))
                    activation = typed_row.get('tech_activation', 'unknown')
                    status = ('tech_verified_inactive' if activation == 'verified_inactive' else
                              'included_what_if' if key in used else
                              'tech_gated' if key in gated
                              else 'unmodeled' if key in excluded or
                              typed_row.get('calculation_status') != 'assumption_scenario'
                              else 'excluded_unresolved')
                    activation_status = ('verified_active' if key in used and activation == 'verified_active'
                                         and typed_row.get('tech_activation_evidence') else
                                         'assumed_active' if key in used else activation)
                    raw = typed_row.get('raw_text') or (
                        _observed_lines(stats)[index] if index < len(_observed_lines(stats)) else None)
                    evidence = typed_row.get('evidence') or {}
                    mod['rows'].append(_row(raw, status, stat_type=typed_row.get('stat_type'),
                                             source=evidence.get('source_frame') or owned.get('source_observation'),
                                             activation_status=activation_status,
                                             next_action=('Confirm this row is active at the current Tech level before treating this what-if as the actual build.'
                                                          if activation_status == 'assumed_active' else
                                                          'This row is verified inactive at this Tech level; confirm a new activation state before including it.'
                                                          if status == 'tech_verified_inactive' else
                                                          'Confirm this row is active at the current Tech level.'
                                                          if status == 'tech_gated' else
                                                          'Verify the missing formula, sign, condition or row evidence.'
                                                          if status in ('unmodeled', 'excluded_unresolved') else None)))
                    counts[status] += 1
                    if key in used:
                        activation_counts[activation_status] += 1
            else:
                missing_items += 1
                observed_lines = _observed_lines(stats)
                tooltip_lines = mod.get('existing_evidence', {}).get('attribute_lines') or []
                for index, line in enumerate(observed_lines):
                    mod['rows'].append(_row(line, 'missing_typed_evidence',
                                             source=owned.get('source_observation'),
                                             next_action='Review and attach source-checked typed evidence for this exact mod and level.'))
                    counts['missing_typed_evidence'] += 1
                if mod.get('existing_evidence'):
                    remaining = Counter(observed_lines)
                    for index, line in enumerate(tooltip_lines):
                        if remaining[line] > 0:
                            remaining[line] -= 1
                            continue
                        mod['rows'].append(_row(line, 'missing_typed_evidence',
                                                 source=mod['existing_evidence']['source_ref'],
                                                 next_action='Review the existing tooltip and staged rows; no new screenshot is needed.'))
                        counts['missing_typed_evidence'] += 1
        if not mod['rows']:
            if not owned or typed:
                missing_items += 1
            mod['rows'].append(_row('No exact owned numerical roll evidence is available.',
                                     'missing_evidence',
                                     next_action='Capture this exact mod variant and level, then review and attach its rows.'))
        core = mod_entry.get('primary_effect') or mod_entry.get('effect')
        if core:
            mod['rows'].append(_row(core, 'core_unmodeled', source=mod_entry.get('source_url'),
                                     next_action='Verify trigger, duration, scaling and condition before modeling the core effect.'))
        mod['status'] = ('partial' if any(r['status'] == 'included_what_if' for r in mod['rows'])
                         else 'tech_gated' if any(r['status'] == 'tech_gated' for r in mod['rows'])
                         else 'tech_verified_inactive' if any(r['status'] == 'tech_verified_inactive' for r in mod['rows'])
                         else 'missing_evidence' if any(r['status'].startswith('missing') for r in mod['rows'])
                         else 'not_modeled')
        if slot_issues:
            mod['issues'] = [issue['reason'] for issue in slot_issues]
            mod['next_action'] = slot_issues[0].get('next_step') or next(
                (r['next_action'] for r in mod['rows'] if r.get('next_action')),
                'Confirm this exact owned instance and level.')
        elif mod['status'] != 'partial':
            mod['next_action'] = next((r['next_action'] for r in mod['rows'] if r.get('next_action')), None)
        if mod.get('existing_evidence') and mod['status'] == 'missing_evidence':
            mod['next_action'] = 'Review existing evidence for this exact owned mod and level. Its rows still need explicit source checking and a separate Apply step before calculations.'
        elif mod.get('evidence_mismatch') and mod['status'] == 'missing_evidence':
            mod['next_action'] = mod['evidence_mismatch']
        if mod.get('row_order_discrepancy'):
            mod['status'] = 'missing_evidence'
            mod['issues'] = (mod.get('issues') or []) + [
                'The two recorded sources disagree in value, count, or order. Do not Apply or activate either version until both are reconciled against the original image.']
            mod['next_action'] = 'Review both recorded source lists against the original image; Apply and Tech activation are blocked until reconciled.'
        items.append(mod)

    groups = set_groups or []
    for group in groups:
        reached = [t for t in group.get('thresholds') or [] if group.get('count', 0) >= t.get('pieces', 999)]
        if not reached:
            continue
        items.append({'kind': 'set_bonus', 'slot': 'armor set', 'name': group.get('name') or group.get('set_id'),
                      'status': 'condition_unknown', 'piece_count': group.get('count'),
                      'rows': [_row(t.get('description') or f"{t['pieces']}-piece effect", 'condition_unknown',
                                    source=t.get('source'),
                                    next_action='Confirm current scenario, active pieces and effect conditions.')
                               for t in reached],
                      'next_action': 'Set threshold reached in the plan; activation and numerical contribution are not established here.'})
    active_selection = slots.get(active_weapon_slot) or {}
    no_active_mod = (bool(active_selection.get('catalog_id')) and
                     not any((selection or {}).get('mod_id') for selection in slots.values()
                             if isinstance(selection, dict)))
    priority = next((i for i in items if i['kind'] == 'mod' and i['status'] == 'missing_evidence'), None)
    if priority is None:
        priority = next((i for i in items if i.get('next_action')), None)
    target = ({'owned_instance_id': priority['owned_instance_id'], 'slot': priority['slot'],
               'catalog_id': priority['catalog_id'], 'level': priority['level'],
               'source_ref': priority['existing_evidence']['source_ref']}
              if priority and priority.get('existing_evidence') else None)
    return {'items': items, 'row_counts': dict(counts), 'activation_counts': dict(activation_counts),
            'missing_mod_items': missing_items,
            'ignored_weapon_slots': resolved['ignored_weapon_slots'],
            'next_action': ('Select an owned mod for the active weapon in the build editor; no mod tooltip is missing from this plan.' if no_active_mod else priority.get('next_action')) if priority or no_active_mod else
                           'Compare only the supported partial components; the full build remains unverified.',
            'next_action_kind': 'select_mod' if no_active_mod else 'review_existing_evidence' if priority and priority.get('existing_evidence') else None,
            'next_action_target': target,
            'scope': 'Selected planned gear only. Included rolls are hypothetical formula contributions under the chosen Tech and stacking assumptions; item effects, armor, sets and accessories are not silently applied.'}
