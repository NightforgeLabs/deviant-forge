"""Read-only catalog and saved-plan selections for component comparison."""
from __future__ import annotations

import catalog
import component_compare
import planned_advisor
import suffix_candidates
import published_reference_selection

SLOT_ORDER = ('helmet', 'mask', 'gloves', 'shoes', 'top', 'bottoms',
              'primary', 'secondary', 'melee')


def _alternative(selection, plans, context):
    if not isinstance(selection, dict):
        raise ValueError('Choose an item or saved planned build for each side')
    kind = selection.get('kind')
    if kind == 'catalog':
        identity = selection.get('catalog_id')
        if (identity not in catalog.ENTRIES or catalog.ENTRIES[identity].get('family_only')
                or catalog.ENTRIES[identity]['kind'] not in ('weapon', 'armor', 'mod')):
            raise ValueError('Choose an exact selectable catalog item')
        entry = catalog.ENTRIES[identity]
        level = selection.get('level')
        shiny = selection.get('shiny', False)
        if not isinstance(shiny, bool) or (shiny and entry['kind'] != 'mod'):
            raise ValueError('Shiny selection must be true or false for a mod')
        if entry['kind'] == 'mod':
            if isinstance(level, bool) or not isinstance(level, int) or not 1 <= level <= 17:
                raise ValueError('Choose the exact mod level from 1 to 17')
        else:
            level = None
        label = entry.get('display_name') or entry['name']
        return ({'catalog_id': identity, 'level': level, 'name': label, 'shiny': shiny},
                {'kind': kind, 'label': label, 'catalog_id': identity, 'level': level,
                 'shiny': shiny,
                 'note': 'Single catalog item sensitivity; this is not a complete equipped build.'})
    if kind == 'planned_build':
        match = next((plan for plan in plans if plan['id'] == selection.get('planned_build_id')), None)
        if not match:
            raise ValueError('Choose an existing saved planned build')
        analysis = planned_advisor.analyze(match['slots'], context)
        items = []
        for part in sorted(analysis['slots'], key=lambda row: SLOT_ORDER.index(row['slot'])):
            for selected in (part.get('gear'), part.get('mod')):
                if selected:
                    item = {'name': selected['name'], 'catalog_id': selected['catalog_id'],
                                  'level': selected.get('level'), 'slot': part['slot'],
                                  'shiny': bool(selected.get('shiny')),
                                  'source': selected.get('effect_source'),
                                  'main_effect': selected.get('effect')}
                    known = selected.get('attributes') or []
                    exact_known = (catalog.resolve(selected['catalog_id'], selected.get('level'),
                                                   shiny=bool(selected.get('shiny'))).get('known_attributes') or []
                                   if selected['kind'] == 'mod' else [])
                    candidate = (suffix_candidates.candidate(selected['catalog_id'], selected.get('level'))
                                 if selected['kind'] == 'mod' and context.get('suffix_candidate_opt_in') is True
                                 and not any(row.get('value_percent') is not None for row in exact_known) else None)
                    if not candidate:
                        item['numeric_coverage'] = selected.get('attribute_coverage') if selected['kind'] == 'mod' else None
                        item['attributes'] = known
                    items.append(item)
        return ({'name': match['name'], 'items': items, 'sets': analysis['sets']},
                {'kind': kind, 'label': match['name'], 'planned_build_id': match['id'],
                 'item_count': len(items),
                 'note': 'Saved planned build is hypothetical; ownership and current equipment are not inferred. Tier, stars, calibration and unmodeled effects do not enter the component ratios.',
                 'blockers': analysis['unresolved']})
    raise ValueError('Selection kind must be catalog or planned_build')


def compare(request, plans):
    if not isinstance(request, dict) or not isinstance(plans, list):
        raise ValueError('Structured comparison needs selections and saved plan list')
    context = request.get('context') or {}
    if not isinstance(context, dict):
        raise ValueError('Comparison context must be an object')
    left, left_meta = _alternative(request.get('left'), plans, context)
    right, right_meta = _alternative(request.get('right'), plans, context)
    linkage = None
    if context.get('weapon_timeline') is not None:
        active_slot = context.get('weapon_timeline_active_slot', 'primary')
        if active_slot not in ('primary', 'secondary'):
            raise ValueError('Weapon timeline active slot must be primary or secondary')
        linkage = {}
        for side, item in (('left', left), ('right', right)):
            selected = None
            for piece in [item, *(item.get('items') or [])]:
                identity = piece.get('catalog_id')
                if (identity in catalog.ENTRIES and catalog.ENTRIES[identity]['kind'] == 'weapon'
                        and (piece is item or piece.get('slot') == active_slot)):
                    selected = identity
                    break
            scenario = (context['weapon_timeline'].get(side) or {}) if isinstance(context['weapon_timeline'], dict) else {}
            scenario_id = scenario.get('weapon_id') if isinstance(scenario, dict) else None
            linkage[side] = {'selected_weapon_id': selected, 'scenario_weapon_id': scenario_id,
                             'status': ('independent_weapon_scenario' if selected is None else
                                        'matched' if selected == scenario_id else 'mismatch')}
        if (context.get('weapon_timeline_pool_mode') == 'selected_reviewed_rows'
                and any(row['status'] == 'mismatch' for row in linkage.values())):
            raise ValueError('Selected-row weapon scenario disagrees with the selected active weapon')
    result = component_compare.compare(left, right, context)
    result['weapon_timeline_linkage'] = linkage
    if linkage and any(row['status'] == 'mismatch' for row in linkage.values()):
        result['missing'].append('Weapon timeline uses a different weapon from the selected catalog item or active planned-build slot; modeled rates are independent of that gear selection.')
    result['selection_metadata'] = {'left': left_meta, 'right': right_meta,
                                    'read_only': True}
    result['published_reference'] = published_reference_selection.evaluate(request, plans, result)
    return result
