"""Public catalog detail requires no personal Field Guide or ownership state."""
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.parse import quote
from urllib.request import urlopen

import public_catalog_detail
import published_bonus_lines
import catalog
import server
import structured_compare
import planned_advisor


FLAME = 'mod:weapon_mod:flame-resonance-general'
LUNAR = 'mod:helmet_mod:deviation-expert-lunar'


class PublicModDetailTests(unittest.TestCase):
    def test_flame_general_ordered_levels_and_core_without_profile(self):
        level8 = public_catalog_detail.detail(FLAME, 8)
        self.assertEqual(level8['preview_level'], 8)
        self.assertEqual(level8['core_effect']['text'], 'Max Burn stack +2, Burn duration -20%')
        self.assertEqual(len(level8['bonus_lines']), 4)
        self.assertEqual([line['tier'] for line in level8['bonus_lines']], [2, 2, 2, 2])
        self.assertEqual([line['value_percent'] for line in level8['bonus_lines']],
                         [2.4, 4.8, 3.6, 3.0])
        self.assertEqual(level8['coverage']['published_candidate_numeric_lines'], 4)
        self.assertEqual(level8['published_formula_status'],
                         'published_formula_candidate_generation_unverified')
        self.assertEqual(len(level8['progression']), 17)
        self.assertEqual([line['locked'] for line in level8['progression'][0]['bonus_lines']],
                         [False, True, True, True])
        self.assertEqual([line['tier'] for line in level8['progression'][16]['bonus_lines']],
                         [5, 5, 5, 2])
        self.assertEqual([line['value_percent'] for line in level8['progression'][16]['bonus_lines']],
                         [6, 12, 9, 3])
        self.assertEqual(level8['progression'][0]['bonus_lines'][0]['value_percent'], 1.2)
        self.assertEqual(level8['progression'][0]['bonus_lines'][1]['name'],
                         'Magazine Capacity')
        for line in level8['bonus_lines']:
            if line['status'] == 'value_unavailable':
                self.assertIsNone(line['value_percent'])

    def test_held_lunar_exact_line_values_and_conditions(self):
        result = public_catalog_detail.detail(LUNAR, 10)
        self.assertEqual([line['value_percent'] for line in result['bonus_lines']],
                         [18, 7.2, 4.8, 3])
        self.assertEqual([line['condition'] for line in result['bonus_lines'][:3]],
                         ['low HP'] * 3)
        self.assertTrue(all(line['source_sha256'] for line in result['bonus_lines']))
        self.assertEqual(result['coverage']['known_numeric_lines'], 4)
        self.assertEqual(result['coverage']['observed_numeric_lines'], 4)
        self.assertEqual(result['bonus_lines'][0]['components'], None)

    def test_scoped_violence_bridge_adds_17_candidates_without_global_alias(self):
        identity = 'mod:helmet_mod:elemental-havoc-violence'
        level8 = public_catalog_detail.detail(identity, 8)
        self.assertEqual(level8['published_formula_status'],
                         'published_formula_candidate_current_generation')
        self.assertEqual([row['value_percent'] for row in level8['bonus_lines']],
                         [6, 2.4, 4.8, 3.0])
        for level in range(1, 18):
            self.assertEqual(len(published_bonus_lines.profile(identity, level)['lines']), 4)
        self.assertEqual(published_bonus_lines.profile(
            'mod:weapon_mod:bombardier-souvenir-violence', 8)['status'], 'blocked')
        self.assertEqual(published_bonus_lines.profile(
            'mod:boots_mod:steady-hand-resistance', 8)['status'], 'blocked')
        report = published_bonus_lines.coverage()
        self.assertEqual(report['identity_level_statuses']['blocked'], 1751)
        self.assertEqual(report['gap_resolution_v2']['legacy_random_roll_profiles_requiring_actual_rolls'], 714)

    def test_generated_grid_identity_and_observation_crosscheck(self):
        self.assertEqual(len(published_bonus_lines.GRID), 984 * 17)
        self.assertEqual(published_bonus_lines.REPORT['exact_crosscheck']['mismatching_profiles'], 0)
        self.assertEqual(published_bonus_lines.REPORT['exact_crosscheck']['matching_profiles'], 75)
        self.assertEqual(published_bonus_lines.REPORT['corroborated_tier_crosscheck']['matching_comparisons'], 126)
        for (identity, level), raw in published_bonus_lines.GRID.items():
            self.assertIn(identity, catalog.ENTRIES)
            self.assertEqual(raw['level'], level)
            generated = published_bonus_lines.profile(identity, level)
            if raw['status'] == 'blocked':
                self.assertEqual(generated['lines'], [])
            else:
                self.assertEqual(len(generated['lines']), 4)
                self.assertEqual([line['tier'] for line in generated['lines']],
                                 catalog.DATA['official_rules']['mod_levels']['ordered_subattribute_tiers'][str(level)])

    def test_variant_and_level_guards(self):
        with self.assertRaisesRegex(ValueError, 'level 17'):
            public_catalog_detail.detail(FLAME, 8, shiny=True)
        with self.assertRaisesRegex(ValueError, 'whole number'):
            public_catalog_detail.detail(FLAME, True)
        with self.assertRaisesRegex(ValueError, 'exact selectable'):
            public_catalog_detail.detail('set:agent', 8)

    def test_resonance_name_bridge_keeps_transfer_scope(self):
        result = public_catalog_detail.detail(
            'mod:gloves_mod:crit-amplifier-resonance-deviant-energy', 17)
        self.assertEqual(result['published_formula_alias_status'], 'anchored_terminology_transfer_candidate')
        self.assertEqual(len(result['published_formula_alias_sources']), 3)
        self.assertIn('transfer to this identity remains', ' '.join(result['missing']))
        self.assertTrue(any('identity-level transfer candidate' in
                            str(row['source_status']) for row in result['bonus_lines']))

    def test_shiny_suffix_only_scope_and_conditional_maximum(self):
        self.assertEqual(len(published_bonus_lines.SHINY), 632)
        lunar = public_catalog_detail.detail(LUNAR, 17, shiny=True)
        self.assertEqual(lunar['shiny_suffix_scope'], 'if_this_identity_has_a_Shiny_Lv17_version')
        self.assertEqual(lunar['shiny_availability_for_identity'], 'unverified')
        self.assertEqual(lunar['core_effect']['status'], 'shiny_core_effect_unverified')
        self.assertEqual(lunar['bonus_lines'][0]['display_value'], 'up to +30%')
        self.assertIsNone(lunar['bonus_lines'][0]['value_percent'])
        self.assertIn('curve unpublished', lunar['bonus_lines'][0]['condition'])
        mixed = public_catalog_detail.detail(FLAME, 17, shiny=True)
        self.assertEqual(mixed['published_formula_status'], 'blocked')
        self.assertEqual(mixed['coverage']['known_numeric_lines'], 0)

    def test_source_core_variants_are_visible_without_false_level_mapping(self):
        missing = [entry for entry in catalog.DATA['mods']
                   if entry.get('system_generation') == 'current_field_guide'
                   and not entry.get('family_only') and not entry.get('primary_effect')]
        self.assertEqual(len(missing), 65)
        for entry in missing:
            preview = public_catalog_detail.detail(entry['id'], 8)
            core = preview['core_effect']
            self.assertIsNone(core['text'])
            self.assertEqual(core['status'], 'published_variants_level_unmapped')
            evidence = (entry.get('detail_effect_variants') or
                        public_catalog_detail.PUBLIC_CORE[entry['id']]['detail_effect_variants'])
            sources = (entry.get('detail_source_urls') or
                       public_catalog_detail.PUBLIC_CORE[entry['id']]['detail_source_urls'])
            self.assertEqual([row['text'] for row in core['unbound_variants']],
                             evidence)
            self.assertTrue(all(row['source_ref'] in sources
                                for row in core['unbound_variants']))
            self.assertTrue(all(row['text'] for row in core['unbound_variants']))
        for identity in ('mod:boots_mod:steady-hand-resistance',
                         'mod:boots_mod:slow-and-steady-resistance'):
            result = public_catalog_detail.detail(identity, 8)
            self.assertEqual(result['published_formula_status'], 'blocked')
            self.assertEqual(result['coverage']['known_numeric_lines'], 0)
        slow = public_catalog_detail.detail('mod:boots_mod:slow-and-steady-resistance', 8)
        self.assertEqual(len(slow['core_effect']['unbound_variants']), 5)
        self.assertFalse(slow['core_effect']['text'])
        steady = public_catalog_detail.detail('mod:boots_mod:steady-hand-resistance', 8)
        self.assertEqual(steady['core_effect']['status'],
                         'catalog_text_level_strength_unconfirmed')
        resonance = public_catalog_detail.detail(
            'mod:pants_mod:elemental-resonance-deviant-energy-current', 17)
        self.assertEqual(len(resonance['core_effect']['unbound_variants']), 5)
        self.assertEqual(resonance['core_effect']['source_ref'],
                         'https://www.oncehumandb.com/mods/elemental-resonance-deviant-energy')
        self.assertIn('previous magazine', resonance['core_effect']['unbound_variants'][0]['text'])

    def test_shiny_does_not_inherit_unmapped_ordinary_core_variants(self):
        result = public_catalog_detail.detail(
            'mod:boots_mod:steady-hand-resistance', 17, shiny=True)
        self.assertEqual(result['core_effect']['status'], 'shiny_core_effect_unverified')
        self.assertEqual(result['core_effect']['unbound_variants'], [])

    def test_unbound_public_core_variants_do_not_enter_comparison_arithmetic(self):
        resonance = 'mod:pants_mod:elemental-resonance-deviant-energy-current'
        slow = 'mod:boots_mod:slow-and-steady-resistance'
        compared = structured_compare.compare({
            'left': {'kind': 'catalog', 'catalog_id': resonance, 'level': 17},
            'right': {'kind': 'catalog', 'catalog_id': slow, 'level': 17},
            'context': {'base_pools': {'all': 0, 'weapon': 0, 'status': 0,
                                       'elemental': 0, 'magazine': 0}}}, [])
        self.assertFalse(compared['game_winner_established'])
        self.assertFalse(compared['main_effect_same'])
        self.assertTrue(any('no exact-level main-effect rule' in row
                            for row in compared['missing']))

    def test_published_lines_feed_direct_and_hypothetical_compare_once(self):
        left = {'kind': 'catalog', 'catalog_id': FLAME, 'level': 8}
        right = {'kind': 'catalog', 'catalog_id': FLAME, 'level': 17}
        compared = structured_compare.compare({'left': left, 'right': right,
            'context': {'base_pools': {'all': 0, 'magazine': 0}}}, [])
        self.assertAlmostEqual(compared['component_ratios']['normal']['min'], 1)
        self.assertEqual(compared['component_ratios']['normal']['min'],
                         compared['component_ratios']['normal']['max'])
        self.assertFalse(compared['game_winner_established'])
        self.assertTrue(any('exact native configured position' in gap for gap in compared['missing']))
        self.assertTrue(any(row['name'] == 'Reload Speed' and
                            row.get('state', '').startswith('excluded')
                            for row in compared['left']['trace']))
        plan = {'id': 'synthetic-public-formula', 'name': 'Synthetic',
                'slots': {'primary': {'catalog_id': 'weapon:mps5-blue-tiger',
                                      'mod_id': FLAME, 'mod_level': 8}}}
        part = next(row for row in planned_advisor.analyze(plan['slots'], {})['slots']
                    if row['slot'] == 'primary')
        self.assertEqual([row['value_percent'] for row in part['mod']['attributes']],
                         [None, 4.8, None, None])
        self.assertEqual(part['mod']['attribute_coverage'], 'published_candidate_partial')

    def test_exact_native_line_blocks_different_published_stat_even_with_same_number(self):
        rows, coverage, _ = public_catalog_detail.calculation_rows(FLAME, 8)
        self.assertEqual(coverage, 'published_candidate_partial')
        self.assertEqual([row['value_percent'] for row in rows], [None, 4.8, None, None])
        self.assertEqual(rows[0]['native_configured_candidate'], 'DMG +2.4%')
        self.assertEqual(rows[2]['native_configured_candidate'], 'Reload Efficiency +3.6%')
        self.assertEqual(rows[3]['native_configured_candidate'], 'Damage to all monsters +3%')
        self.assertTrue(all(rows[index]['source_conflict'] for index in (0, 2, 3)))
        self.assertFalse(rows[1].get('source_conflict'))
        exact, _, _ = public_catalog_detail.calculation_rows(
            'mod:gloves_mod:elemental-overload-resonance', 9)
        self.assertEqual(exact[2]['value_percent'], 3.0)
        self.assertIn('Field Guide frame', exact[2]['source_status'])

    def test_exact_native_conflicts_are_visible_as_excluded_candidates(self):
        for identity in (FLAME, 'mod:pants_mod:precision-load-general'):
            detail = public_catalog_detail.detail(identity, 8)
            conflicts = detail['published_candidate_conflicts']
            self.assertEqual([row['position'] for row in conflicts], [1, 3, 4])
            self.assertEqual([row['published_name'] for row in conflicts],
                             ['All DMG Boost', 'Reload Speed', 'Damage against enemies'])
            self.assertEqual([row['native_configured_text'] for row in conflicts],
                             ['DMG +2.4%', 'Reload Efficiency +3.6%',
                              'Damage to all monsters +3%'])
            self.assertTrue(all(row['calculation_status'] == 'excluded_native_source_conflict'
                                and row['published_source_ref'] and row['native_source_sha256']
                                for row in conflicts))
            self.assertEqual(detail['bonus_lines'][1]['name'], 'Magazine Capacity')
            self.assertEqual(detail['bonus_lines'][1]['value_percent'], 4.8)
            self.assertEqual([row['position'] for row in
                              public_catalog_detail.detail(identity, 1)['published_candidate_conflicts']], [1])
            self.assertEqual(public_catalog_detail.detail(identity, 17, shiny=True)
                             ['published_candidate_conflicts'], [])

    def test_native_monster_classes_do_not_become_generic_enemy_damage(self):
        for identity, position in (
                ('mod:helmet_mod:deviation-expert-violent', 4),
                ('mod:gloves_mod:crit-amplifier-resonance', 3)):
            rows, status, _ = public_catalog_detail.calculation_rows(identity, 8)
            monster = rows[position - 1]
            self.assertEqual(monster['name'], 'Damage against enemies')
            self.assertIsNone(monster['value_percent'])
            self.assertIn('native_monster_scope_not_published_enemy_scope',
                          monster['published_conflict_reasons'])
            self.assertEqual(monster['native_configured_candidate'],
                             'Damage to all monsters +3%')
            self.assertEqual(status, 'published_candidate_partial')
            detail = public_catalog_detail.detail(identity, 8)
            self.assertEqual(detail['published_candidate_conflicts'][0]['position'], position)
            self.assertEqual(detail['published_candidate_conflicts'][0]['calculation_status'],
                             'excluded_native_source_conflict')
        self.assertEqual(public_catalog_detail.calculation_rows(
            'mod:helmet_mod:deviation-expert-violent', 8)[0][0]['value_percent'], 6)

    def test_native_general_remote_and_dot_targets_do_not_become_all_damage(self):
        identity = 'mod:helmet_mod:deviation-expert-general'
        rows, coverage, _ = public_catalog_detail.calculation_rows(identity, 8)
        self.assertEqual(coverage, 'published_candidate_partial')
        self.assertEqual([row['value_percent'] for row in rows], [None, 4.8, 3.6, None])
        self.assertEqual(rows[0]['native_configured_candidate'], 'DMG +2.4%')
        self.assertIn('native_remote_dot_scope_not_all_damage',
                      rows[0]['published_conflict_reasons'])
        self.assertIn('remote and damage-over-time properties',
                      rows[0]['calculation_exclusion_reason'])
        detail = public_catalog_detail.detail(identity, 8)
        self.assertEqual([row['position'] for row in detail['published_candidate_conflicts']],
                         [1, 4])
        self.assertEqual([row['position'] for row in public_catalog_detail.detail(
            identity, 1)['published_candidate_conflicts']], [1])
        self.assertEqual(public_catalog_detail.detail(identity, 17, shiny=True)
                         ['published_candidate_conflicts'], [])

    def test_http_path_returns_same_public_contract(self):
        http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        try:
            path = '/api/public-mod-detail/' + quote(FLAME, safe='') + '?level=8'
            with urlopen(f'http://127.0.0.1:{http.server_port}{path}') as response:
                payload = json.load(response)
            self.assertEqual(payload['catalog_id'], FLAME)
            self.assertEqual(payload['coverage']['total_lines'], 4)
            self.assertEqual(len(payload['progression']), 17)
            compact_path = path + '&compact=1'
            with urlopen(f'http://127.0.0.1:{http.server_port}{compact_path}') as response:
                compact = json.load(response)
            self.assertEqual(compact['response_scope'], 'catalog_ui_compact')
            self.assertEqual([row['tier'] for row in compact['bonus_lines']],
                             [row['tier'] for row in payload['bonus_lines']])
            self.assertEqual(len(compact['progression']), 17)
            self.assertEqual(compact['progression'][0]['tiers'], [1, 0, 0, 0])
            self.assertNotIn('native_frame_catalog_preview', compact)
            self.assertLess(len(json.dumps(compact)), len(json.dumps(payload)) / 2)
        finally:
            http.shutdown()
            http.server_close()
            thread.join(timeout=2)


if __name__ == '__main__':
    unittest.main()
