"""Catalog identity, evidence and selection contracts without production state."""
import unittest

import catalog
import component_compare
import mod_core_typed
import planned_advisor
import public_catalog_detail
import server
import structured_compare


class CatalogContracts(unittest.TestCase):
    def test_every_selectable_mod_level_resolves_without_false_complete_profile(self):
        mods = [entry for entry in catalog.ENTRIES.values()
                if entry['kind'] == 'mod' and not entry.get('family_only')]
        complete = 0
        for entry in mods:
            for level in range(1, 18):
                resolved = catalog.resolve(entry['id'], level)
                self.assertEqual((resolved['entry']['id'], resolved['level']),
                                 (entry['id'], level))
                rows = resolved.get('known_attributes') or []
                if resolved.get('attribute_coverage') == 'complete':
                    complete += 1
                    self.assertEqual(len(rows), 4, (entry['id'], level))
                    self.assertTrue(all(row.get('value_percent') is not None
                                        for row in rows), (entry['id'], level))
                else:
                    self.assertNotEqual(resolved.get('attribute_coverage'), 'complete')
            shiny = catalog.resolve(entry['id'], 17, shiny=True)
            self.assertTrue(shiny['shiny'])
            self.assertIsNotNone(shiny['shiny_acquisition'])
            legacy = catalog.resolve(entry['id'], 10, system='legacy_random_roll')
            self.assertIsNone(legacy['known_attributes'])
        self.assertEqual(complete, catalog.coverage()['exact_mod_level_profiles'])

    def test_all_equipment_identities_have_read_only_structured_selection(self):
        for entry in catalog.ENTRIES.values():
            identity = entry['id']
            if entry.get('family_only') or entry['kind'] == 'set':
                with self.assertRaises(ValueError):
                    structured_compare.compare({'left': {'kind': 'catalog',
                                                         'catalog_id': identity},
                                                'right': {'kind': 'catalog',
                                                          'catalog_id': identity}}, [])
                continue
            level = 10 if entry['kind'] == 'mod' else None
            selection = {'kind': 'catalog', 'catalog_id': identity,
                         **({'level': level} if level is not None else {})}
            response = structured_compare.compare({'left': selection,
                                                   'right': selection}, [])
            self.assertFalse(response['game_winner_established'])
            self.assertEqual(response['selection_metadata']['left']['catalog_id'], identity)
            self.assertEqual(response['selection_metadata']['right']['catalog_id'], identity)

    def test_mod_saved_plan_matches_direct_source_fields_and_shiny_scope(self):
        slot_by_mod = {value: key for key, value in server.MOD_SLOTS.items()
                       if key != 'secondary'}
        armor_by_slot = {slot: next(identity for identity, entry in catalog.ENTRIES.items()
                                    if entry['kind'] == 'armor' and entry.get('slot') == slot)
                         for slot in server.ARMOR_SLOTS.values()}
        ranged = next(identity for identity, entry in catalog.ENTRIES.items()
                      if entry['kind'] == 'weapon' and entry.get('family') != 'melee')
        for entry in catalog.ENTRIES.values():
            if entry['kind'] != 'mod' or entry.get('family_only'):
                continue
            identity = entry['id']
            slot = slot_by_mod[entry['slot']]
            gear = (ranged if slot == 'primary'
                    else armor_by_slot[server.ARMOR_SLOTS[slot]])
            for level, shiny in ((1, False), (10, False), (17, False), (17, True)):
                plan = {'id': 'isolated-contract', 'name': 'Isolated contract',
                        'slots': {slot: {'catalog_id': gear, 'mod_id': identity,
                                         'mod_level': level, 'mod_shiny': shiny}}}
                server.validate_planned_slots(plan['slots'])
                analysis = planned_advisor.analyze(plan['slots'], {})
                mod = next(part for part in analysis['slots'] if part['slot'] == slot)['mod']
                resolved = catalog.resolve(identity, level, shiny=shiny)
                self.assertEqual((mod['catalog_id'], mod['level'], mod['shiny']),
                                 (identity, level, shiny))
                expected, _, status = public_catalog_detail.calculation_rows(
                    identity, level, shiny=shiny, resolved=resolved)
                if status == 'blocked':
                    expected = resolved.get('known_attributes') or []
                self.assertEqual(len(mod['attributes']), len(expected))
                for plan_row, source_row in zip(mod['attributes'], expected):
                    self.assertTrue(all(plan_row.get(key) == value
                                        for key, value in source_row.items()),
                                    (identity, level, shiny))
                comparison = structured_compare.compare({
                    'left': {'kind': 'planned_build', 'planned_build_id': plan['id']},
                    'right': {'kind': 'catalog', 'catalog_id': identity,
                              'level': level, 'shiny': shiny}}, [plan])
                left = [row['status'] for row in comparison['left']['typed_main_effects']
                        if row['catalog_id'] == identity]
                right = [row['status'] for row in comparison['right']['typed_main_effects']
                         if row['catalog_id'] == identity]
                self.assertEqual(left, right, (identity, level, shiny))
                self.assertFalse(comparison['game_winner_established'])

    def test_candidate_core_evidence_never_becomes_certified_damage(self):
        for entry in catalog.ENTRIES.values():
            if entry['kind'] != 'mod' or entry.get('family_only'):
                continue
            result = mod_core_typed.evaluate(entry['id'], 10,
                                             context={'core_candidate_opt_in': True})
            if result is None:
                continue
            self.assertFalse(result.get('whole_dps_certified'))
            if result['status'] == 'explicit_community_candidate_output':
                self.assertTrue(result.get('source_warning'))
                self.assertEqual(result.get('numeric_binding'),
                                 'community_strength_unbound_to_selected_level')


if __name__ == '__main__':
    unittest.main()
