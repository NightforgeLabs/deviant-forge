"""Unsaved normal-Build bridge to the same timed model used by Compare."""
from __future__ import annotations

import copy

import catalog
import structured_compare


def evaluate(slots, reference, timed):
    if not isinstance(slots, dict) or not isinstance(reference, dict) or not isinstance(timed, dict):
        raise ValueError('Build slots, reference and timed inputs must be objects')
    primary = slots.get('primary') or {}
    weapon_id = primary.get('catalog_id')
    if not weapon_id or weapon_id not in catalog.ENTRIES or catalog.ENTRIES[weapon_id]['kind'] != 'weapon':
        return {'status': 'needs_primary_weapon', 'missing': 'Select a primary weapon.'}
    if reference.get('weapon_id') not in (None, weapon_id):
        raise ValueError('Build reference weapon must match the selected primary weapon')
    tier = reference.get('tier', primary.get('tier', 1))
    stars = reference.get('stars', primary.get('stars', 1))
    if isinstance(tier, bool) or not isinstance(tier, int) or not 1 <= tier <= 5:
        raise ValueError('Reference tier must be 1–5')
    if isinstance(stars, bool) or not isinstance(stars, int) or not 1 <= stars <= 6:
        raise ValueError('Reference stars must be 1–6')
    page = reference.get('item_page_scenario')
    caller = reference.get('caller_packet_scenario')
    if page is not None and caller is not None:
        raise ValueError('Choose one weapon basis: item page or entered direct packet')
    if caller is None and (not isinstance(page, dict) or page.get('assume_displayed_damage_per_projectile') is not True):
        return {'status': 'needs_reference_inputs',
                'missing': 'Choose an exact item-page tier/star or enter a direct body-damage packet; projectile count, RPM, magazine and reload seconds remain explicit inputs.'}
    if caller is not None and (tier != primary.get('tier', 1) or stars != primary.get('stars', 1)):
        raise ValueError('Entered direct packet must describe the selected weapon tier and stars')
    scenario_slots = copy.deepcopy(slots)
    # A source-page hypothesis never inherits crafted readout/calibration
    # values from the user's selected weapon, especially on a tier override.
    scenario_primary = {key: value for key, value in primary.items()
                        if key not in ('weapon_readout', 'calibration_profile',
                                       'calibration_blueprint', 'calibration_bonus')}
    scenario_slots['primary'] = {**scenario_primary, 'tier': tier, 'stars': stars,
                                 'calibration': 0}
    plan = {'id': 'unsaved-normal-build-scenario', 'name': 'Unsaved Build scenario',
            'slots': scenario_slots}
    fractions = reference.get('condition_fractions') or {}
    if not isinstance(fractions, dict):
        raise ValueError('Condition fractions must be an object')
    ref = {'weapon_id': weapon_id, 'tier': tier, 'stars': stars,
           'condition_fractions': fractions,
           **({'caller_packet_scenario': caller} if caller is not None else
              {'item_page_scenario': page})}
    request = {'left': {'kind': 'planned_build', 'planned_build_id': plan['id']},
               'right': {'kind': 'planned_build', 'planned_build_id': plan['id']},
               'context': {'published_reference': {'enabled': True,
                   'left': ref, 'right': ref,
                   'timed': {'duration_seconds': timed.get('duration_seconds'),
                             'left': timed, 'right': timed}}}}
    output = structured_compare.compare(request, [plan])['published_reference']
    model = output['timed_scenarios']['left']
    selected = output['left']
    return {'status': model['status'], 'weapon_id': weapon_id,
            'selected_tier': primary.get('tier'), 'selected_stars': primary.get('stars'),
            'reference_tier': tier, 'reference_stars': stars,
            'reference_differs_from_selected': (tier != primary.get('tier', 1) or
                                                stars != primary.get('stars', 1)),
            'reference_kind': 'caller_entered_direct_packet' if caller is not None else 'item_page_hypothesis',
            'selected_readout_and_calibration_excluded': True,
            'source_baseline': selected['weapon_source_native_baseline'],
            'selected_mod_rows': selected['selected_mod_rows'],
            'model': model, 'game_verified': False,
            'saved_build_mutated': False}
