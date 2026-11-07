"""Held tooltip meanings take precedence over equal-looking published numbers."""
import unittest
import hashlib
import json
from pathlib import Path

import catalog
import integration_ledger
import public_catalog_detail
import public_semantic_crosscheck
import published_bonus_lines
import published_reference_model
import resonance_suffix
import structured_compare


OVERFLOW = 'mod:helmet_mod:overflow-general'
FRAME = 'data/media/b0aad7d457fd4e699605ae1f78d4ec51/frames/1b99d4a1dce94a8294f2459acf6303a7/0033.png'
ROOT = Path(__file__).resolve().parent.parent


class PublicSemanticCrosscheckTests(unittest.TestCase):
    def test_equal_numbers_do_not_corroborate_different_stats(self):
        exact = public_catalog_detail.detail(OVERFLOW, 8)
        rows = exact['bonus_lines']
        self.assertEqual([row['name'] for row in rows],
                         ['DMG', 'Magazine Capacity', 'Reload Efficiency', 'All DMG Boost'])
        self.assertEqual([row['value_percent'] for row in rows], [2.4, 4.8, 3.6, 3.0])
        self.assertEqual([row['published_layout_conflict'] for row in rows],
                         [True, False, True, True])
        self.assertEqual([row['status'] for row in rows],
                         ['observed_value_published_conflict', 'value_available',
                          'observed_value_published_conflict', 'observed_value_published_conflict'])
        self.assertEqual(exact['coverage']['observed_numeric_lines'], 4)
        selected, status, _ = public_catalog_detail.calculation_rows(OVERFLOW, 8)
        self.assertEqual(status, 'complete')
        self.assertEqual([row['name'] for row in selected], [row['name'] for row in rows])
        self.assertTrue(all(row['source'] == FRAME for row in selected))
        self.assertTrue(all('published_corroboration' not in row
                            for row in (selected[0], selected[2], selected[3])))
        self.assertFalse(any(row.get('source_conflict') for row in selected))

    def test_unobserved_levels_withhold_only_conflicting_positions(self):
        level7 = public_catalog_detail.detail(OVERFLOW, 7)
        self.assertEqual(level7['bonus_lines'][3]['name'], 'All DMG Boost')
        self.assertIsNone(level7['bonus_lines'][3]['value_percent'])
        self.assertNotIn('Damage against enemies',
                         [row['name'] for row in level7['bonus_lines']])
        level9 = public_catalog_detail.detail(OVERFLOW, 9)
        self.assertEqual(level9['bonus_lines'][0]['name'], 'DMG')
        self.assertIsNone(level9['bonus_lines'][0]['value_percent'])
        self.assertEqual(level9['bonus_lines'][1]['value_percent'], 4.8)
        self.assertEqual(level9['bonus_lines'][2]['name'], 'Reload Efficiency')
        self.assertEqual(level9['bonus_lines'][2]['value_percent'], 3.6)
        self.assertEqual(level9['bonus_lines'][3]['name'], 'All DMG Boost')
        self.assertEqual(level9['bonus_lines'][3]['value_percent'], 3.0)
        self.assertIn('published layout conflicts', ' '.join(level9['missing']).lower())
        self.assertEqual(public_catalog_detail.calculation_rows(OVERFLOW, 9)[1],
                         'published_candidate_partial')

    def test_stat_unit_condition_and_slot_identity_are_checked(self):
        same = {'name': 'All DMG Boost', 'stat_type': 'all_damage_boost_percent',
                'value_percent': 3, 'unit': 'percent', 'direction': 'increase'}
        candidate = {'name': 'All DMG Boost', 'stat_type': 'dmg_boost',
                     'value_percent': 3, 'unit': 'percent', 'layout_slot': 'helmet'}
        self.assertEqual(public_semantic_crosscheck.semantic_conflicts(
            same, candidate, expected_slot='helmet'), [])
        self.assertIn('stat_identity', public_semantic_crosscheck.semantic_conflicts(
            {'name': 'Reload Efficiency', 'stat_type': 'reload_efficiency_percent',
             'value_percent': 3.6},
            {'name': 'Reload Speed', 'stat_type': 'reload_speed', 'value_percent': 3.6,
             'layout_slot': 'helmet'}, expected_slot='helmet'))
        self.assertEqual(set(public_semantic_crosscheck.semantic_conflicts(
            {**same, 'unit': 'seconds', 'condition': 'after reload'},
            {**candidate, 'condition': 'damage against enemies', 'layout_slot': 'boots'},
            expected_slot='helmet')), {'unit', 'condition', 'slot'})
        self.assertEqual(public_semantic_crosscheck.semantic_conflicts(
            {'name': 'Crit DMG', 'stat_type': 'crit_damage_percent',
             'value_percent': 9, 'condition': 'low HP'},
            {'name': 'Crit DMG', 'stat_type': 'lunar_crit_dmg',
             'value_percent': 9, 'condition': 'low hp; curve unpublished',
             'layout_slot': 'helmet'}, expected_slot='helmet'), [])

    def test_photographed_resonance_wording_matches_only_the_same_event_rule(self):
        identity = 'mod:gloves_mod:elemental-overload-resonance'
        self.assertNotIn(0, public_semantic_crosscheck.layout_conflicts(identity))
        self.assertNotIn(1, public_semantic_crosscheck.layout_conflicts(identity))
        rules = resonance_suffix.bindings({'catalog_id': identity, 'level': 9})
        self.assertEqual([rule['per_stack_percent'] for rule in rules], [.6, .8])
        self.assertTrue(all(rule['observed_source'].endswith('/0097.png') for rule in rules))
        observed = {'name': 'Elemental DMG on weakspot hit', 'value_percent': .6,
                    'condition': 'per weakspot damage instance; up to 8 stacks for 6 seconds'}
        candidate = {'name': 'Weakspot Dmg To Elemental Dmg',
                     'stat_type': 'resonance_weakspot_dmg_to_elemental_dmg',
                     'components': {'trigger_instances': 1, 'per_stack_percent': .6,
                                    'max_stacks': 7, 'duration_seconds': 6},
                     'layout_slot': 'gloves'}
        self.assertIn('stat_identity', public_semantic_crosscheck.semantic_conflicts(
            observed, candidate, expected_slot='gloves'))

    def test_exact_aero_base_and_extra_wording_requires_both_values(self):
        for identity, level in (
                ('mod:pants_mod:elemental-resonance-aero', 17),
                ('mod:pants_mod:precision-charge-aero', 8),
                ('mod:pants_mod:bullet-siphon-aero-deviant-energy', 12)):
            with self.subTest(identity=identity):
                observed = catalog.resolve(identity, level)['known_attributes']
                candidate = published_bonus_lines.profile(identity, level)['lines']
                for index in (0, 1):
                    self.assertEqual(public_semantic_crosscheck.semantic_conflicts(
                        observed[index], candidate[index], expected_slot='pants'), [])
                    changed = {**candidate[index], 'components':
                               {**candidate[index]['components'], 'aerial_extra_percent':
                                candidate[index]['components']['aerial_extra_percent'] + 1}}
                    self.assertIn('condition', public_semantic_crosscheck.semantic_conflicts(
                        observed[index], changed, expected_slot='pants'))
                    self.assertNotIn(index, public_semantic_crosscheck.layout_conflicts(identity))
        ordinary = 'mod:pants_mod:elemental-resonance-aero'
        rows, status, _ = public_catalog_detail.calculation_rows(ordinary, 10)
        self.assertEqual(status, 'published_candidate_partial')
        self.assertEqual([(row['value_percent'], row['conditional_bonus_percent'])
                          for row in rows[:2]], [(3.6, 1.8), (9, 4.5)])
        self.assertIsNone(rows[2]['value_percent'])
        pools, _, _ = published_reference_model._mods(
            [{'catalog_id': ordinary, 'level': 10}],
            {'aerial hit for extra component': 1})
        self.assertEqual((pools['weapon'], pools['crit'], pools['enemy_damage']),
                         (5.4, 13.5, 0))

    def test_ordinary_selection_and_saved_plan_use_same_exact_rows(self):
        choice = published_reference_model.build({'weapon': {'catalog_id': 'weapon:kam'},
            'mods': [{'catalog_id': OVERFLOW, 'level': 8}]})
        self.assertEqual([row['name'] for row in choice['selected_mod_rows']],
                         ['DMG', 'Magazine Capacity', 'Reload Efficiency', 'All DMG Boost'])
        self.assertFalse(any(row['name'] == 'Damage against enemies'
                             for row in choice['selected_mod_rows']))
        plan = {'id': 'semantic-example', 'name': 'Semantic example',
                'slots': {'primary': {'catalog_id': 'weapon:kam'},
                          'helmet': {'mod_id': OVERFLOW, 'mod_level': 8}}}
        request = {'left': {'kind': 'catalog', 'catalog_id': OVERFLOW, 'level': 8},
                   'right': {'kind': 'planned_build', 'planned_build_id': plan['id']},
                   'context': {'published_reference': {'enabled': True,
                       'left': {'weapon_id': 'weapon:kam'},
                       'right': {'weapon_id': 'weapon:kam'}}}}
        result = structured_compare.compare(request, [plan])['published_reference']
        left = result['left']['selected_mod_rows']
        right = result['right']['selected_mod_rows']
        self.assertEqual([(row['name'], row['value_percent']) for row in left],
                         [(row['name'], row['value_percent']) for row in right])

    def test_official_lv17_cards_anchor_exact_meaning_without_enemy_bucket(self):
        cards = json.loads((ROOT / 'research/official_mod_cards.json').read_text())
        self.assertEqual(hashlib.sha256((ROOT / cards['local_image']).read_bytes()).hexdigest(),
                         cards['sha256'])
        ledger = {row['catalog_id']: row for row in integration_ledger.build()['records']}
        for card in cards['cards']:
            with self.subTest(identity=card['catalog_id']):
                identity = card['catalog_id']
                rows = public_catalog_detail.detail(identity, 17)['bonus_lines']
                self.assertEqual([(row['name'], row['value_percent']) for row in rows],
                                 [(row['name'], row['value_percent']) for row in card['attributes']])
                self.assertTrue(all(row['source_ref'] == cards['local_image'] for row in rows))
                self.assertTrue(rows[2]['published_layout_conflict'])
                pools, selected, _ = published_reference_model._mods(
                    [{'catalog_id': identity, 'level': 17}], {'aerial hit': 0,
                    'target lower than player within 5 meters': 0})
                self.assertEqual(pools['all'], 7.5)
                self.assertEqual(pools['enemy_damage'], 0)
                self.assertEqual(selected[2]['name'], 'All DMG Boost')
                slot = catalog.ENTRIES[identity]['slot'].removesuffix('_mod')
                plan = {'id': 'official-' + slot, 'name': 'Official card scenario',
                        'slots': {'primary': {'catalog_id': 'weapon:kam'},
                                  slot: {'mod_id': identity, 'mod_level': 17}}}
                comparison = structured_compare.compare({
                    'left': {'kind': 'catalog', 'catalog_id': identity, 'level': 17},
                    'right': {'kind': 'planned_build', 'planned_build_id': plan['id']},
                    'context': {'published_reference': {'enabled': True,
                        'left': {'weapon_id': 'weapon:kam', 'condition_fractions':
                                 {'aerial hit': 0, 'target lower than player within 5 meters': 0}},
                        'right': {'weapon_id': 'weapon:kam', 'condition_fractions':
                                  {'aerial hit': 0, 'target lower than player within 5 meters': 0}}}}},
                    [plan])['published_reference']
                self.assertEqual(comparison['left']['selected_pools_percent'],
                                 comparison['right']['selected_pools_percent'])
                self.assertEqual(comparison['left']['selected_pools_percent']['enemy_damage'], 0)
                requirement = ledger[identity]['requirements'][0]
                self.assertIn(cards['local_image'], requirement['held_source_refs'])
                self.assertIn('stat ID/localization key', requirement['next_action'])
                level10 = public_catalog_detail.detail(identity, 10)['bonus_lines'][2]
                self.assertEqual(level10['name'], 'All DMG Boost')
                self.assertIsNone(level10['value_percent'])

    def test_all_held_all_damage_disagreements_withhold_enemy_only_candidates(self):
        checked = 0
        for identity, positions in public_semantic_crosscheck.coverage()['identities'].items():
            disputed = {position for position, details in positions.items()
                        if any(detail['observed_name'] == 'All DMG Boost' and
                               detail['published_name'] == 'Damage against enemies'
                               for detail in details)}
            if not disputed:
                continue
            checked += 1
            for level in range(1, 18):
                rows = public_catalog_detail.detail(identity, level)['bonus_lines']
                for position in disputed:
                    row = rows[position]
                    if row['locked']:
                        continue
                    if ((identity == 'mod:pants_mod:precision-charge-aero' and position == 2) or
                            (identity == 'mod:weapon_mod:shock-diffusion-survival' and position == 3)):
                        self.assertEqual(row['name'], 'Damage to all monsters')
                        self.assertEqual(row['status'], 'exact_native_catalog_configuration')
                        self.assertEqual(row['native_corroboration']['status'],
                                         'numeric_agrees_label_differs' if level ==
                                         (8 if position == 2 else 10) else 'native_config_only')
                        continue
                    self.assertEqual(row['name'], 'All DMG Boost')
                    if row['value_percent'] is None:
                        self.assertTrue(row['published_layout_conflict'])
            pools, _, _ = published_reference_model._mods(
                [{'catalog_id': identity, 'level': 10}], {})
            self.assertEqual(pools['enemy_damage'], 0, identity)
        self.assertEqual(checked, 64)

    def test_sweep_and_coverage_count_reconciled(self):
        checked = public_semantic_crosscheck.coverage()
        self.assertEqual(72, checked['exact_semantic_conflict_identities'])
        self.assertEqual(149, checked['exact_semantic_conflict_positions'])
        self.assertEqual(1836, checked['withheld_unobserved_candidate_rows'])
        self.assertEqual(1013, checked['profiles_with_at_least_one_withheld_candidate'])
        self.assertEqual({'published_candidate_complete': 2699,
                          'published_candidate_partial': 12155,
                          'partial': 1801, 'complete': 73},
                         checked['effective_profile_calculation_statuses'])
        self.assertEqual(checked['effective_profile_calculation_statuses'],
                         published_bonus_lines.coverage()['held_semantic_crosscheck']
                         ['effective_profile_calculation_statuses'])


if __name__ == '__main__':
    unittest.main()
