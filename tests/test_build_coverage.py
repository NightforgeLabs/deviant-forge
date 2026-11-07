import copy
import unittest
from unittest.mock import patch

import build_coverage
import mod_rolls


MOD = 'mod:chest_mod:enduring-shield-deviant-energy'
WEAPON = 'weapon:aug-electron-cloud'
ARMOR = 'armor:shelterer-top'


def owned(rows, item_id='mod-one', level=8):
    parsed = mod_rolls.parse_rows(
        rows, source_audit={'status': 'source_text_and_numbers_checked',
                            'attribute_rows': [{'source_text': x} for x in rows]})
    return {'id': item_id, 'name': 'Enduring Shield', 'kind': 'mod_unlock',
            'level': level, 'effects': {'catalog_id': MOD},
            'stats': {'typed_modifiers': parsed, 'observed_attribute_lines': rows}}


ENTRIES = {
    WEAPON: {'name': 'AUG Electron Cloud', 'kind': 'weapon'},
    ARMOR: {'name': 'Shelterer Top', 'kind': 'armor', 'set_id': 'shelterer_set'},
    MOD: {'name': 'Enduring Shield', 'kind': 'mod', 'primary_effect': 'Conditional shield effect'},
}


class BuildCoverageTests(unittest.TestCase):
    def test_existing_tooltip_routes_to_read_only_typed_preview_without_borrowing_another_level(self):
        mod_id = 'mod:weapon_mod:shock-rampage-power-surge'
        entry = {**ENTRIES, mod_id: {'name': 'Shock Rampage', 'kind': 'mod'}}
        item = {'id': 'shock17', 'name': 'Shock Rampage', 'kind': 'mod_unlock',
                'slot': 'weapon_mod', 'variant': 'Power Surge',
                'level': 17, 'effects': {'catalog_id': mod_id},
                'stats': {'observed_tooltip': {'source_ref': 'libfile_84a17de486208191951ea249c448e8c6',
                          'core_effect': 'Trigger +5% for 5s, max 4',
                          'attribute_lines': ['Power Surge DMG +6%', 'Power Surge Trigger Chance +6%',
                                              'Shock DMG +6%', 'All DMG Boost +3%']}}}
        slots = {'primary': {'catalog_id': WEAPON, 'mod_id': mod_id,
                             'mod_level': 17, 'mod_inventory_id': 'shock17'}}
        snapshot = copy.deepcopy((slots, item))
        result = build_coverage.report(slots, [item], entry, {})
        mod = next(x for x in result['items'] if x['kind'] == 'mod')
        self.assertEqual(result['next_action_kind'], 'review_existing_evidence')
        self.assertEqual(result['missing_mod_items'], 1)
        self.assertEqual(result['row_counts']['missing_typed_evidence'], 4)
        self.assertEqual(mod['existing_evidence']['image_url'],
                         '/media/evidence/shock-rampage-power-surge-lv17-2d4bd6b5.png')
        self.assertIn('abbreviates', mod['existing_evidence']['transcription_note'])
        self.assertEqual([row['stat_type'] for row in mod['existing_evidence']['typed_preview']],
                         ['power_surge_damage_percent', 'power_surge_trigger_chance_percent',
                          'shock_damage_percent', 'all_damage_boost_percent'])
        self.assertTrue(all(row['calculation_status'] == 'unmodeled' for row in mod['existing_evidence']['typed_preview']))
        self.assertTrue(all(row['tech_activation'] == 'unknown' for row in mod['existing_evidence']['typed_preview']))
        self.assertEqual((slots, item), snapshot)
        mismatch = build_coverage.report({**slots, 'primary': {**slots['primary'], 'mod_level': 16}}, [item], entry, {})
        self.assertNotIn('existing_evidence', next(x for x in mismatch['items'] if x['kind'] == 'mod'))
        older = copy.deepcopy(item)
        older['stats']['original_observed_level'] = 16
        mismatch = build_coverage.report(slots, [older], entry, {})
        older_mod = next(x for x in mismatch['items'] if x['kind'] == 'mod')
        self.assertNotIn('existing_evidence', older_mod)
        self.assertIn('does not prove', mismatch['next_action'])

    def test_equivalent_recorded_rows_count_once_without_collapsing_distinct_rolls(self):
        mod_id = 'mod:weapon_mod:shock-rampage-power-surge'
        lines = ['Power Surge DMG +6%', 'Shock DMG +6%']
        item = {'id': 'shock17', 'name': 'Shock Rampage', 'kind': 'mod_unlock',
                'slot': 'weapon_mod', 'variant': 'Power Surge', 'level': 17,
                'effects': {'catalog_id': mod_id},
                'stats': {'observed_attribute_lines': lines,
                          'observed_tooltip': {'source_ref': 'libfile_84a17de486208191951ea249c448e8c6',
                                               'attribute_lines': list(lines)}}}
        slots = {'primary': {'catalog_id': WEAPON, 'mod_id': mod_id, 'mod_level': 17}}
        entry = {**ENTRIES, mod_id: {'name': 'Shock Rampage', 'kind': 'mod'}}
        result = build_coverage.report(slots, [item], entry, {})
        self.assertEqual(result['row_counts']['missing_typed_evidence'], 2)
        item['stats']['observed_tooltip']['attribute_lines'] = ['Power Surge DMG +6%', 'Shock DMG +7%']
        distinct = build_coverage.report(slots, [item], entry, {})
        self.assertEqual(distinct['row_counts']['missing_typed_evidence'], 3)
        item['stats']['observed_attribute_lines'] = ['Shock DMG +6%', 'Shock DMG +6%']
        item['stats']['observed_tooltip']['attribute_lines'] = ['Shock DMG +6%', 'Shock DMG +6%']
        repeated = build_coverage.report(slots, [item], entry, {})
        self.assertEqual(repeated['row_counts']['missing_typed_evidence'], 2,
                         'identical text in two distinct row positions remains two rolls')
        item['stats']['observed_attribute_lines'] = list(lines)
        item['stats']['observed_tooltip']['attribute_lines'] = list(reversed(lines))
        reversed_result = build_coverage.report(slots, [item], entry, {})
        reversed_mod = next(x for x in reversed_result['items'] if x['kind'] == 'mod')
        self.assertEqual(reversed_result['row_counts']['missing_typed_evidence'], 2)
        conflict = reversed_mod['row_order_discrepancy']
        self.assertEqual(conflict['unique_content_count'], 2)
        self.assertEqual(conflict['observed_attribute_lines'], lines)
        self.assertEqual(conflict['tooltip_attribute_lines'], list(reversed(lines)))
        self.assertTrue(conflict['application_blocked'])
        self.assertIn('blocked until reconciled', reversed_result['next_action'])

        item['stats']['observed_tooltip']['attribute_lines'] = ['Power Surge DMG +6%', 'Shock DMG +7%']
        changed = build_coverage.report(slots, [item], entry, {})
        changed_mod = next(x for x in changed['items'] if x['kind'] == 'mod')
        self.assertEqual(changed['row_counts']['missing_typed_evidence'], 3)
        self.assertEqual(changed_mod['row_order_discrepancy']['unique_content_count'], 3)
        self.assertEqual(changed_mod['status'], 'missing_evidence')
        self.assertIn('blocked until reconciled', changed['next_action'])

        item['stats']['observed_tooltip']['attribute_lines'] = ['Power Surge DMG +6%']
        shortened = build_coverage.report(slots, [item], entry, {})
        shortened_mod = next(x for x in shortened['items'] if x['kind'] == 'mod')
        self.assertEqual(shortened_mod['row_order_discrepancy']['unique_content_count'], 2)
        self.assertIn('blocked until reconciled', shortened['next_action'])

    def test_order_conflict_withholds_source_checked_typed_rolls(self):
        rows = ['Weapon DMG +5%', 'Max HP +2.4%']
        item = owned(rows)
        item['slot'] = 'chest_mod'
        item['variant'] = 'Deviant Energy'
        item['stats']['observed_tooltip'] = {
            'source_ref': 'media/older-tooltip.png', 'catalog_id': MOD,
            'slot': 'chest_mod', 'variant': 'Deviant Energy', 'observed_level': 8,
            'attribute_lines': list(reversed(rows))}
        slots = {'top': {'catalog_id': ARMOR, 'mod_id': MOD, 'mod_level': 8}}
        resolved = mod_rolls.equipped_build_modifiers(slots, [item])
        self.assertEqual(resolved['modifiers'], [])
        self.assertEqual(resolved['unresolved'][0]['code'], 'source_row_order_conflict')
        report = build_coverage.report(slots, [item], ENTRIES, {})
        self.assertEqual(report['row_counts'].get('included_what_if', 0), 0)
        mod = next(x for x in report['items'] if x['kind'] == 'mod')
        self.assertEqual(mod['status'], 'missing_evidence')
        self.assertEqual(mod['row_order_discrepancy']['unique_content_count'], 2)

    def test_generic_one_row_preview_uses_its_own_identity_and_source(self):
        generic = {'id': 'hp-one', 'name': 'Health Guard', 'kind': 'mod_unlock',
                   'slot': 'helmet_mod', 'variant': 'General', 'level': 9,
                   'effects': {'catalog_id': 'mod:helmet_mod:health-guard-general'},
                   'stats': {'observed_tooltip': {'source_ref': 'media/local-hp.png',
                            'catalog_id': 'mod:helmet_mod:health-guard-general',
                            'slot': 'helmet_mod', 'variant': 'General', 'observed_level': 9,
                            'attribute_lines': ['Max HP +2.4%']}}}
        slots = {'helmet': {'catalog_id': ARMOR, 'mod_id': generic['effects']['catalog_id'], 'mod_level': 9}}
        result = build_coverage.report(slots, [generic], {**ENTRIES,
            generic['effects']['catalog_id']: {'name': 'Health Guard', 'kind': 'mod'}}, {})
        mod = next(x for x in result['items'] if x['kind'] == 'mod')
        self.assertEqual(len(mod['existing_evidence']['typed_preview']), 1)
        self.assertIsNone(mod['existing_evidence']['image_url'])
        self.assertEqual(mod['existing_evidence']['typed_preview'][0]['stat_type'], 'max_hp_percent')

    def test_plan_without_any_mod_guides_mod_selection(self):
        result = build_coverage.report({'primary': {'catalog_id': WEAPON}}, [], ENTRIES, {})
        self.assertEqual(result['next_action_kind'], 'select_mod')
        self.assertIn('Select an owned mod', result['next_action'])

    def test_api_handler_returns_read_only_per_item_report(self):
        import server
        lines = ['Weapon DMG +5%', 'Unknown proc +7%']
        selected = {'top': {'catalog_id': ARMOR, 'mod_id': MOD, 'mod_level': 8}}
        fake = object.__new__(server.Handler)
        fake.path = '/api/build-contribution-coverage'
        fake.body = lambda _max: {'build_id': 'synthetic', 'tech_policy': 'assume_active'}
        fake.respond = lambda payload, status=200: (status, payload)
        with patch.object(server, 'planned_builds', return_value=[
                {'id': 'synthetic', 'name': 'Synthetic plan', 'slots': selected}]), \
             patch.object(server, 'inventory', return_value=[owned(lines)]), \
             patch.object(server.catalog, 'ENTRIES', ENTRIES), \
             patch.object(server.planned_advisor, '_set_summary', return_value=[]):
            status, payload = server.Handler.do_POST(fake)
        self.assertEqual(status, 200)
        self.assertEqual(payload['row_counts'], {'included_what_if': 1, 'unmodeled': 1})
        self.assertEqual(payload['build_name'], 'Synthetic plan')
        self.assertEqual(payload['items'][-1]['status'], 'partial')

    def test_mixed_rows_are_counted_individually_not_as_a_complete_item(self):
        lines = ['Weapon DMG +5%', 'Max HP +2.4%', 'Unknown proc +7%']
        inventory = [owned(lines)]
        slots = {'primary': {'catalog_id': WEAPON, 'tier': 5, 'stars': 5},
                 'top': {'catalog_id': ARMOR, 'mod_id': MOD, 'mod_level': 8}}
        original = copy.deepcopy((slots, inventory))
        result = build_coverage.report(slots, inventory, ENTRIES, {}, baseline_mode='tier_v_preview',
                                       tech_policy='assume_active')
        self.assertEqual(result['row_counts'], {'included_what_if': 2, 'unmodeled': 1})
        mod = next(x for x in result['items'] if x['kind'] == 'mod')
        self.assertEqual(mod['status'], 'partial')
        self.assertEqual([r['status'] for r in mod['rows']],
                         ['included_what_if', 'included_what_if', 'unmodeled', 'core_unmodeled'])
        self.assertEqual(mod['rows'][2]['text'], lines[2])
        self.assertEqual(next(x for x in result['items'] if x['kind'] == 'weapon')['rows'][0]['status'],
                         'included_reference')
        self.assertEqual((slots, inventory), original)

    def test_tech_unknown_and_missing_instance_are_not_zero_or_calculated(self):
        lines = ['Weapon DMG +5%', 'Max HP +2.4%']
        slots = {'primary': {'catalog_id': WEAPON},
                 'top': {'catalog_id': ARMOR, 'mod_id': MOD, 'mod_level': 8}}
        gated = build_coverage.report(slots, [owned(lines)], ENTRIES, {})
        self.assertEqual(gated['row_counts'], {'tech_gated': 2})
        self.assertEqual(next(x for x in gated['items'] if x['kind'] == 'mod')['status'], 'tech_gated')
        missing = build_coverage.report(slots, [], ENTRIES, {})
        self.assertEqual(missing['row_counts'], {})
        self.assertEqual(missing['missing_mod_items'], 1)
        self.assertIn('exact mod', missing['next_action'])

    def test_verified_active_assumed_active_and_verified_inactive_are_distinct(self):
        lines = ['Weapon DMG +5%', 'Magazine Capacity +4.8%', 'Max HP +2.4%']
        instance = owned(lines)
        rows = instance['stats']['typed_modifiers']
        rows[0]['tech_activation'] = 'verified_active'
        rows[0]['tech_activation_evidence'] = 'current Tech screenshot'
        rows[2]['tech_activation'] = 'verified_inactive'
        slots = {'top': {'catalog_id': ARMOR, 'mod_id': MOD, 'mod_level': 8}}
        result = build_coverage.report(slots, [instance], ENTRIES, {}, tech_policy='assume_active')
        mod = next(x for x in result['items'] if x['kind'] == 'mod')
        self.assertEqual([r['activation_status'] for r in mod['rows'][:3]],
                         ['verified_active', 'assumed_active', 'verified_inactive'])
        self.assertEqual([r['status'] for r in mod['rows'][:3]],
                         ['included_what_if', 'included_what_if', 'tech_verified_inactive'])
        self.assertEqual(result['activation_counts'], {'verified_active': 1, 'assumed_active': 1})
        self.assertEqual(result['row_counts']['tech_verified_inactive'], 1)
        self.assertIn('confirm', mod['rows'][1]['next_action'].lower())
        self.assertIn('verified inactive', mod['rows'][2]['next_action'])
        excluded = build_coverage.report(slots, [instance], ENTRIES, {})
        self.assertEqual(excluded['row_counts']['tech_gated'], 1)
        self.assertEqual(excluded['row_counts']['tech_verified_inactive'], 1)
        self.assertEqual(excluded['activation_counts'], {'verified_active': 1})
        inactive_bucket = owned(['All DMG Boost +3%'])
        inactive_bucket['stats']['typed_modifiers'][0]['tech_activation'] = 'verified_inactive'
        bucket_report = build_coverage.report(slots, [inactive_bucket], ENTRIES, {},
                                               tech_policy='assume_active')
        bucket_row = next(x for x in bucket_report['items'] if x['kind'] == 'mod')['rows'][0]
        self.assertEqual(bucket_row['status'], 'tech_verified_inactive',
                         'inactive Tech state takes precedence even when the damage bucket is unverified')

    def test_observed_text_without_typed_rows_is_missing_numeric_evidence(self):
        item = owned(['Weapon DMG +5%'])
        item['stats']['typed_modifiers'] = []
        slots = {'top': {'catalog_id': ARMOR, 'mod_id': MOD, 'mod_level': 8}}
        result = build_coverage.report(slots, [item], ENTRIES, {})
        mod = next(x for x in result['items'] if x['kind'] == 'mod')
        self.assertEqual(result['missing_mod_items'], 1)
        self.assertEqual(result['row_counts'], {'missing_typed_evidence': 1})
        self.assertEqual(mod['rows'][0]['text'], 'Weapon DMG +5%')
        self.assertEqual(mod['status'], 'missing_evidence')

    def test_confirmed_manual_baseline_is_shown_as_unsaved_what_if(self):
        slots = {'primary': {'catalog_id': WEAPON, 'tier': 4, 'stars': 5}}
        values = {'damage': 213, 'rpm': 720, 'magazine': 40, 'confirmed_pre_mod': True}
        result = build_coverage.report(slots, [], ENTRIES, {}, manual_baseline=values)
        weapon = next(x for x in result['items'] if x['kind'] == 'weapon')
        self.assertEqual(weapon['rows'][0]['status'], 'manual_what_if')
        self.assertIn('213 damage, 720 RPM, 40 magazine', weapon['rows'][0]['text'])
        self.assertIn('not source-verified or saved', weapon['rows'][0]['source'])
        unconfirmed = build_coverage.report(slots, [], ENTRIES, {},
            manual_baseline={**values, 'confirmed_pre_mod': False})
        self.assertEqual(unconfirmed['items'][0]['rows'][0]['status'], 'missing_baseline')
        incomplete = build_coverage.report(slots, [], ENTRIES, {},
            manual_baseline={**values, 'rpm': None})
        self.assertEqual(incomplete['items'][0]['rows'][0]['status'], 'missing_baseline')

    def test_api_reflects_current_confirmed_manual_inputs_without_saving(self):
        import server
        slots = {'primary': {'catalog_id': WEAPON, 'tier': 4, 'stars': 5}}
        body = {'build_id': 'manual-plan', 'baseline_mode': 'manual',
                'manual_baseline': {'damage': 213, 'rpm': 720, 'magazine': 40,
                                    'confirmed_pre_mod': True}}
        fake = object.__new__(server.Handler)
        fake.path = '/api/build-contribution-coverage'
        fake.body = lambda _max: body
        fake.respond = lambda payload, status=200: (status, payload)
        with patch.object(server, 'planned_builds', return_value=[
                {'id': 'manual-plan', 'name': 'Manual test', 'slots': slots}]), \
             patch.object(server, 'inventory', return_value=[]), \
             patch.object(server.catalog, 'ENTRIES', ENTRIES), \
             patch.object(server.planned_advisor, '_set_summary', return_value=[]):
            status, payload = server.Handler.do_POST(fake)
        self.assertEqual(status, 200)
        self.assertEqual(payload['items'][0]['rows'][0]['status'], 'manual_what_if')
        self.assertIn('213 damage', payload['items'][0]['rows'][0]['text'])

    def test_duplicate_instance_and_inactive_weapon_do_not_contribute(self):
        line = 'Weapon DMG +5%'
        slot = {'catalog_id': WEAPON, 'mod_id': MOD, 'mod_level': 8, 'mod_inventory_id': 'same'}
        slots = {'primary': slot, 'secondary': copy.deepcopy(slot)}
        report = build_coverage.report(slots, [owned([line], 'same')], ENTRIES, {},
                                       active_weapon_slot='primary', tech_policy='assume_active')
        self.assertEqual(report['row_counts'], {'included_what_if': 1})
        inactive = next(x for x in report['items'] if x['kind'] == 'mod' and x['slot'] == 'secondary')
        self.assertEqual(inactive['status'], 'inactive_weapon')
        self.assertEqual(report['ignored_weapon_slots'], ['secondary'])
        # Reusing one physical instance in two *active* equipment slots excludes it.
        slots = {'primary': slot, 'top': {'catalog_id': ARMOR, 'mod_id': MOD, 'mod_level': 8,
                                         'mod_inventory_id': 'same'}}
        duplicate = build_coverage.report(slots, [owned([line], 'same')], ENTRIES, {},
                                          tech_policy='assume_active')
        self.assertEqual(duplicate['row_counts'].get('included_what_if', 0), 0)
        self.assertEqual(duplicate['row_counts']['excluded_unresolved'], 2)

    def test_accessory_calibration_and_set_are_visible_but_not_applied(self):
        slots = {'primary': {'catalog_id': WEAPON, 'tier': 4, 'stars': 6,
                             'calibration_profile': {'blueprint_name': 'Rapid Shot',
                                                     'fixed_effects': 'Fire Rate +15%',
                                                     'rolls': [{'stat': 'Weapon DMG', 'value_percent': 29.6}],
                                                     'source_ref': 'game-shot'},
                             'accessories': {'muzzle': 'accessory:suppressor'}},
                 'top': {'catalog_id': ARMOR}}
        set_groups = [{'set_id': 'shelterer_set', 'name': 'Shelterer', 'count': 2,
                       'thresholds': [{'pieces': 2, 'description': 'Elemental bonus while condition holds',
                                       'source': 'official-example'}]}]
        acc = {'accessory:suppressor': {'name': 'Tactical Suppressor',
                                       'effects': [('Range', 20)], 'source_ref': 'accessory-shot'}}
        report = build_coverage.report(slots, [], ENTRIES, acc, set_groups=set_groups)
        by_kind = {x['kind']: x for x in report['items']}
        self.assertEqual(by_kind['calibration']['rows'][0]['status'], 'not_modeled')
        self.assertEqual(by_kind['accessory']['rows'][0]['status'], 'not_modeled')
        self.assertEqual(by_kind['set_bonus']['rows'][0]['status'], 'condition_unknown')
        self.assertEqual(report['row_counts'], {})
        self.assertEqual(by_kind['weapon']['rows'][0]['status'], 'missing_baseline')


if __name__ == '__main__':
    unittest.main()
