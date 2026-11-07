"""Native item links are catalog evidence, never a calculation or ownership input."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import native_mod_identity


class NativeModIdentityTest(unittest.TestCase):
    def setUp(self):
        native_mod_identity.load.cache_clear()
        native_mod_identity.families.cache_clear()
        native_mod_identity.precision_charge_aero_identity.cache_clear()
        native_mod_identity.aero_v2_entry_join.cache_clear()
        native_mod_identity.aero_level_source.cache_clear()
        native_mod_identity.aero_four_line_source.cache_clear()
        native_mod_identity.two_frame_source.cache_clear()
        native_mod_identity.aero_core_math_configuration.cache_clear()
        native_mod_identity.aero_core_lifecycle_source.cache_clear()
        native_mod_identity.aero_core_refresh_source.cache_clear()

    def tearDown(self):
        native_mod_identity.load.cache_clear()
        native_mod_identity.families.cache_clear()
        native_mod_identity.precision_charge_aero_identity.cache_clear()
        native_mod_identity.aero_v2_entry_join.cache_clear()
        native_mod_identity.aero_level_source.cache_clear()
        native_mod_identity.aero_four_line_source.cache_clear()
        native_mod_identity.two_frame_source.cache_clear()
        native_mod_identity.aero_core_math_configuration.cache_clear()
        native_mod_identity.aero_core_lifecycle_source.cache_clear()
        native_mod_identity.aero_core_refresh_source.cache_clear()

    def test_two_native_frames_all_levels_variant_and_calculation_bounds(self):
        import catalog
        import public_catalog_detail as detail
        identities = native_mod_identity.TWO_FRAME_IDENTITIES
        self.assertEqual(set(identities), {
            'mod:weapon_mod:shock-diffusion-survival',
            'mod:weapon_mod:shatter-them-all-shrapnel'})
        for identity in identities:
            for level in range(1, 18):
                preview = native_mod_identity.two_frame_preview(identity, level)
                self.assertEqual(preview['ordered_subentry_levels'],
                                 catalog.resolve(identity, level)['level_profile'])
                self.assertEqual(len(preview['ordered_lines']), 4)
                self.assertFalse(preview['owned_roll_inferred'])
                self.assertFalse(preview['runtime_damage_included'])
                page = detail.detail(identity, level)
                self.assertEqual(page['published_formula_status'],
                                 'exact_native_catalog_configuration')
                self.assertEqual(page['coverage']['native_configured_numeric_lines'],
                                 sum(tier > 0 for tier in preview['ordered_subentry_levels']))
                self.assertEqual(page['coverage']['published_candidate_numeric_lines'], 0)
            normal = native_mod_identity.two_frame_preview(identity, 17)
            shiny = native_mod_identity.two_frame_preview(identity, 17, shiny=True)
            self.assertEqual(normal['ordered_lines'], shiny['ordered_lines'])
            self.assertFalse(shiny['shiny_separate_buff_inferred'])
            self.assertIn('Shiny item identity', detail.detail(identity, 17, shiny=True)['missing'][-1])
            with self.assertRaisesRegex(ValueError, 'Shiny native preview requires level 17'):
                native_mod_identity.two_frame_preview(identity, 8, shiny=True)
        shock = 'mod:weapon_mod:shock-diffusion-survival'
        shatter = 'mod:weapon_mod:shatter-them-all-shrapnel'
        self.assertEqual([row['value_percent'] for row in detail.detail(shock, 8)['bonus_lines']],
                         [2.4, 3.2, 3.2, 3])
        self.assertEqual([row['value_percent'] for row in detail.detail(shatter, 8)['bonus_lines']],
                         [2.4, 10, 6, 3])
        held = detail.detail(shock, 10)
        self.assertEqual(held['coverage']['observed_numeric_lines'], 4)
        self.assertEqual(held['bonus_lines'][3]['recorded_english_label'], 'All DMG Boost')
        self.assertEqual(held['bonus_lines'][3]['native_corroboration']['status'],
                         'numeric_agrees_label_differs')
        self.assertEqual(detail.detail(shock, 8)['coverage']['observed_numeric_lines'], 0)
        for identity in identities:
            rows, status, _ = detail.calculation_rows(identity, 8)
            self.assertEqual(status, 'partial')
            self.assertIsNone(rows[3]['value_percent'])
            self.assertIn('not generic All DMG Boost', rows[3]['calculation_exclusion_reason'])

    def test_two_frame_source_hash_and_aero_core_rank_boundary(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / native_mod_identity.TWO_FRAME_PACKET.name
            path.write_bytes(native_mod_identity.TWO_FRAME_PACKET.read_bytes() + b' ')
            with patch.object(native_mod_identity, 'TWO_FRAME_PACKET', path):
                with self.assertRaisesRegex(ValueError, 'hash conflict'):
                    native_mod_identity.two_frame_source()
        core = native_mod_identity.aero_core_math_configuration()
        self.assertEqual(core['family_main_entry_no'], 9318)
        self.assertFalse(core['field_guide_total_level_to_core_rank_proven'])
        self.assertTrue(core['standard_server_cap_if_cast_proven'])
        self.assertEqual(core['standard_server_cap_if_cast'], 6)
        self.assertEqual(core['configured_initial_lifetime_seconds'], 10)
        self.assertFalse(core['actual_cast_and_application_proven'])
        self.assertFalse(core['refresh_cast_dispatch_and_prior_dispel_order_proven'])
        self.assertFalse(core['runtime_damage_included'])

    def test_aero_core_controlled_cap_lifetime_and_named_elements(self):
        calculate = native_mod_identity.aero_core_conditional_scenario
        base = {'magazine_size': 10, 'qualifying_weak_remote_events': 3,
                'reload_post_event_clip_left': 10, 'secondary_level': 4}
        three = calculate(**base)
        self.assertEqual((three['requested_stacks'], three['standard_new_buff_stacks_if_cast']), (3, 3))
        self.assertEqual(three['configured_initial_lifetime_seconds'], 10)
        self.assertEqual(three['bonus_percent_per_named_element_if_cast'], {
            'Blaze DMG Bonus': 9, 'Frost DMG Bonus': 9,
            'Shock DMG Bonus': 9, 'Blast DMG Bonus': 9})
        nine = calculate(**{**base, 'qualifying_weak_remote_events': 9})
        self.assertEqual((nine['requested_stacks'], nine['standard_new_buff_stacks_if_cast']), (9, 6))
        self.assertEqual(set(nine['bonus_percent_per_named_element_if_cast'].values()), {18})
        top = calculate(**{**base, 'qualifying_weak_remote_events': 9, 'secondary_level': 5})
        self.assertEqual(set(top['bonus_percent_per_named_element_if_cast'].values()), {24})
        short = calculate(**{**base, 'reload_post_event_clip_left': 9})
        self.assertEqual(short['status'], 'configured_full_reload_condition_not_met')
        self.assertIsNone(short['bonus_percent_per_named_element_if_cast'])
        self.assertFalse(top['actual_cast_and_application_proven'])
        self.assertFalse(top['runtime_damage_included'])
        self.assertEqual(top['buff_component_branch'], 'new_buff_init_if_cast_only')
        for field, value in (('magazine_size', 0), ('qualifying_weak_remote_events', -1),
                             ('secondary_level', 17), ('magazine_size', True)):
            with self.assertRaises(ValueError):
                calculate(**{**base, field: value})
        with TemporaryDirectory() as temp:
            path = Path(temp) / native_mod_identity.AERO_LIFECYCLE_PACKET.name
            path.write_bytes(native_mod_identity.AERO_LIFECYCLE_PACKET.read_bytes() + b' ')
            with patch.object(native_mod_identity, 'AERO_LIFECYCLE_PACKET', path):
                native_mod_identity.aero_core_lifecycle_source.cache_clear()
                with self.assertRaisesRegex(ValueError, 'hash conflict'):
                    native_mod_identity.aero_core_lifecycle_source()

    def test_aero_refresh_is_explicit_add_then_cap_without_renewal_claim(self):
        refresh = native_mod_identity.aero_core_conditional_refresh
        four_plus_three = refresh(existing_buff_stacks=4, incoming_stacks=3)
        self.assertEqual(four_plus_three['standard_refreshed_stacks_if_invoked'], 6)
        self.assertEqual(refresh(existing_buff_stacks=2, incoming_stacks=1)
                         ['standard_refreshed_stacks_if_invoked'], 3)
        self.assertEqual(four_plus_three['configured_life_time_seconds'], 10)
        self.assertFalse(four_plus_three['exact_lifetime_renewal_proven'])
        self.assertFalse(four_plus_three['prior_dispel_or_replacement_proven'])
        self.assertFalse(four_plus_three['reload_cast_dispatch_proven'])
        self.assertFalse(four_plus_three['runtime_damage_included'])
        for existing, incoming in ((0, 1), (7, 1), (2, -1), (True, 1)):
            with self.assertRaises(ValueError):
                refresh(existing_buff_stacks=existing, incoming_stacks=incoming)
        with TemporaryDirectory() as temp:
            path = Path(temp) / native_mod_identity.AERO_REFRESH_PACKET.name
            path.write_bytes(native_mod_identity.AERO_REFRESH_PACKET.read_bytes() + b' ')
            with patch.object(native_mod_identity, 'AERO_REFRESH_PACKET', path):
                native_mod_identity.aero_core_refresh_source.cache_clear()
                with self.assertRaisesRegex(ValueError, 'hash conflict'):
                    native_mod_identity.aero_core_refresh_source()

    def test_aero_native_catalog_first_line_levels_and_recorded_crosscheck(self):
        import catalog
        cases = ((1, [1, 0, 0, 0], 1, 1.2, .6),
                 (8, [2, 2, 2, 2], 2, 2.4, 1.2),
                 (17, [5, 5, 5, 2], 5, 6, 3))
        for total, levels, first, base, extra in cases:
            preview = native_mod_identity.precision_charge_aero_preview(total)
            self.assertEqual(preview['status'], 'exact_native_catalog_tooltip_configuration')
            self.assertEqual(preview['ordered_subentry_levels'], levels)
            self.assertEqual(preview['first_entry_key'], [2601, first])
            self.assertEqual((preview['base_percent'], preview['aerial_extra_percent']),
                             (base, extra))
            self.assertEqual(preview['native_property_id'], 'E42')
            self.assertFalse(preview['effect_activated'])
            self.assertFalse(preview['runtime_damage_included'])
        recorded = catalog.resolve('mod:pants_mod:precision-charge-aero', 8)['known_attributes'][0]
        level8 = native_mod_identity.precision_charge_aero_preview(8)
        self.assertEqual((recorded['value_percent'], recorded['conditional_bonus_percent']),
                         (level8['base_percent'], level8['aerial_extra_percent']))
        self.assertEqual(native_mod_identity.precision_charge_aero_preview(9)['base_percent'], 3.6)
        self.assertEqual(native_mod_identity.precision_charge_aero_preview(9)['status'],
                         'exact_native_catalog_tooltip_configuration')
        self.assertIsNone(native_mod_identity.precision_charge_aero_preview(17, shiny=True)['base_percent'])

    def test_aero_all_levels_unlocks_values_and_label_scope(self):
        import public_catalog_detail
        import catalog
        identity = 'mod:pants_mod:precision-charge-aero'
        for level in range(1, 18):
            native = native_mod_identity.aero_four_line_preview(level)
            self.assertEqual(native['ordered_subentry_levels'], catalog.resolve(identity, level)['level_profile'])
            self.assertEqual(len(native['ordered_lines']), 4)
            self.assertEqual([row['entry_no'] for row in native['ordered_lines']],
                             [2601, 2602, 7405, 5101])
            self.assertEqual([row['locked'] for row in native['ordered_lines']],
                             [tier == 0 for tier in native['ordered_subentry_levels']])
            detail = public_catalog_detail.detail(identity, level)
            self.assertEqual(detail['coverage']['native_configured_numeric_lines'],
                             sum(tier > 0 for tier in native['ordered_subentry_levels']))
            self.assertEqual(detail['published_formula_status'], 'exact_native_catalog_configuration')
            self.assertEqual(detail['coverage']['published_candidate_numeric_lines'], 0)
        level8 = public_catalog_detail.detail(identity, 8)
        self.assertEqual([line['value_percent'] for line in level8['bonus_lines']], [2.4, 6, 3, 2.4])
        self.assertEqual([line['conditional_bonus_percent'] for line in level8['bonus_lines']],
                         [1.2, 3, None, None])
        self.assertEqual(level8['coverage']['observed_numeric_lines'], 4)
        self.assertEqual(level8['bonus_lines'][2]['name'], 'Damage to all monsters')
        self.assertEqual(level8['bonus_lines'][2]['recorded_english_label'], 'All DMG Boost')
        self.assertEqual(level8['bonus_lines'][2]['native_corroboration']['status'],
                         'numeric_agrees_label_differs')
        self.assertEqual(public_catalog_detail.detail(identity, 9)['coverage']['observed_numeric_lines'], 0)
        self.assertEqual(public_catalog_detail.detail(identity, 17)['coverage']['observed_numeric_lines'], 0)
        rows = public_catalog_detail.calculation_rows(identity, 8)
        self.assertIsNone(rows[0][2]['value_percent'])
        self.assertIn('not generic All DMG Boost', rows[0][2]['calculation_exclusion_reason'])
        self.assertEqual(native_mod_identity.aero_four_line_preview(17, shiny=True)['ordered_lines'], [])

    def test_aero_native_preview_api_read_only(self):
        import hashlib
        from http.server import ThreadingHTTPServer
        import threading
        from urllib.request import urlopen
        import server
        with TemporaryDirectory() as temp:
            db = Path(temp) / 'advisor.sqlite3'
            db.write_bytes(b'unchanged sentinel')
            before = hashlib.sha256(db.read_bytes()).hexdigest()
            with patch.object(server, 'DB', db):
                http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
                worker = threading.Thread(target=http.serve_forever, daemon=True)
                worker.start()
                try:
                    from urllib.parse import quote
                    path = '/api/public-mod-detail/' + quote('mod:pants_mod:precision-charge-aero', safe='')
                    with urlopen(f'http://127.0.0.1:{http.server_address[1]}{path}?level=8') as response:
                        detail = json.load(response)
                    first = detail['bonus_lines'][0]
                    self.assertEqual(first['native_corroboration']['status'],
                                     'recorded_card_value_agrees')
                    self.assertEqual(first['native_corroboration']['property_id'], 'E42')
                    self.assertEqual(detail['native_first_line_preview']['first_entry_key'], [2601, 2])
                    self.assertEqual(len(detail['native_four_line_preview']['ordered_lines']), 4)
                    self.assertTrue(detail['native_core_math_configuration']['standard_server_cap_if_cast_proven'])
                    self.assertFalse(detail['native_core_math_configuration']['actual_cast_and_application_proven'])
                    self.assertFalse(detail['native_first_line_preview']['effect_activated'])
                    from urllib.request import Request
                    scenario = Request(f'http://127.0.0.1:{http.server_address[1]}/api/native-aero-core-scenario',
                                       data=json.dumps({'magazine_size': 10,
                                           'qualifying_weak_remote_events': 9,
                                           'reload_post_event_clip_left': 10,
                                           'secondary_level': 5}).encode(),
                                       headers={'Content-Type': 'application/json'})
                    with urlopen(scenario) as response:
                        controlled = json.load(response)
                    self.assertEqual(controlled['standard_new_buff_stacks_if_cast'], 6)
                    self.assertEqual(controlled['bonus_percent_per_named_element_if_cast']['Shock DMG Bonus'], 24)
                    refresh_request = Request(
                        f'http://127.0.0.1:{http.server_address[1]}/api/native-aero-buff-refresh-scenario',
                        data=json.dumps({'existing_buff_stacks': 2, 'incoming_stacks': 1}).encode(),
                        headers={'Content-Type': 'application/json'})
                    with urlopen(refresh_request) as response:
                        controlled_refresh = json.load(response)
                    self.assertEqual(controlled_refresh['standard_refreshed_stacks_if_invoked'], 3)
                    self.assertFalse(controlled_refresh['exact_lifetime_renewal_proven'])
                    for identity in native_mod_identity.TWO_FRAME_IDENTITIES:
                        frame_path = '/api/public-mod-detail/' + quote(identity, safe='')
                        with urlopen(f'http://127.0.0.1:{http.server_address[1]}{frame_path}?level=8') as response:
                            frame = json.load(response)
                        self.assertEqual(frame['native_four_line_preview']['source_build'], '26267212')
                        self.assertEqual(len(frame['native_four_line_preview']['ordered_lines']), 4)
                        self.assertFalse(frame['native_four_line_preview']['runtime_damage_included'])
                        with urlopen(f'http://127.0.0.1:{http.server_address[1]}{frame_path}?level=17&shiny=1') as response:
                            shiny_frame = json.load(response)
                        self.assertEqual(shiny_frame['bonus_lines'][3]['value_percent'], 3)
                        self.assertFalse(shiny_frame['native_four_line_preview']['shiny_separate_buff_inferred'])
                    with urlopen(f'http://127.0.0.1:{http.server_address[1]}{path}?level=17&shiny=1') as response:
                        shiny = json.load(response)
                    self.assertEqual(shiny['native_first_line_preview']['status'], 'ordinary_variant_only')
                finally:
                    http.shutdown()
                    worker.join()
                    http.server_close()
            self.assertEqual(before, hashlib.sha256(db.read_bytes()).hexdigest())

    def test_precision_charge_aero_frame_is_identity_not_level_or_buff(self):
        import catalog
        import server
        row = native_mod_identity.for_catalog('mod:pants_mod:precision-charge-aero')
        exact = row['exact_native_layout_identity']
        self.assertEqual((row['normal']['item_id'], row['normal']['mod_code']),
                         ('19500811', 2400811))
        self.assertEqual((exact['native_main_entry_family'], exact['native_layout_frame_code']),
                         (9318, 26))
        self.assertEqual(exact['frame_meaning'], 'Aero visual/subattribute layout, not level or rank')
        self.assertFalse(exact['field_guide_level_inferred'])
        self.assertFalse(exact['core_rank_inferred'])
        self.assertIsNone(exact['selected_native_affix_ids'])
        self.assertIsNone(exact['active_main_entry_id'])
        self.assertFalse(exact['main_effect_activated'])
        self.assertFalse(exact['calculation_included'])
        join = exact['native_v2_entry_join']
        self.assertEqual(join['ordered_subentry_keys'], [2601, 2602, 7405, 5101])
        self.assertEqual(join['available_main_entry_composite_keys'], [[9318, 4], [9318, 5]])
        self.assertIsNone(join['active_main_entry_composite_key'])
        self.assertEqual((join['first_subentry_key'], join['first_subentry_serialized_property_id']),
                         (2601, 'E42'))
        self.assertIsNone(join['first_subentry_selected_value'])
        self.assertFalse(join['field_guide_level_to_entry_level_proven'])
        self.assertEqual(join['old_scalar_entry_ids_are_pointers'], [19289, 58166])
        recorded = catalog.resolve('mod:pants_mod:precision-charge-aero', 8)
        self.assertAlmostEqual(recorded['known_attributes'][0]['value_percent'], 2.4)
        self.assertEqual(recorded['known_attributes'][0]['condition'], 'aerial hit')
        with TemporaryDirectory() as temp:
            folder = Path(temp)
            with patch.object(server, 'DATA', folder), patch.object(server, 'MEDIA', folder/'media'), patch.object(server, 'DB', folder/'test.sqlite3'):
                server.init()
                entries = {entry['id']: entry for entry in server.builder_catalog()['entries']}
        self.assertEqual(entries['mod:pants_mod:precision-charge-aero']
                         ['native_mod_identity']['exact_native_layout_identity'], exact)

    def test_precision_identity_source_tamper_rejected(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / native_mod_identity.PRECISION_PACKET.name
            path.write_bytes(native_mod_identity.PRECISION_PACKET.read_bytes() + b' ')
            with patch.object(native_mod_identity, 'PRECISION_PACKET', path):
                with self.assertRaisesRegex(ValueError, 'hash conflict'):
                    native_mod_identity.precision_charge_aero_identity()

    def test_aero_composite_join_tamper_rejected(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / native_mod_identity.AERO_JOIN_PACKET.name
            path.write_bytes(native_mod_identity.AERO_JOIN_PACKET.read_bytes() + b' ')
            with patch.object(native_mod_identity, 'AERO_JOIN_PACKET', path):
                with self.assertRaisesRegex(ValueError, 'hash conflict'):
                    native_mod_identity.aero_v2_entry_join()

    def test_exact_normal_to_shiny_link_and_limits(self):
        source, linked = native_mod_identity.load()
        self.assertEqual(len(linked), 86)
        self.assertEqual(sum(map(len, linked.values())), 165)
        row = native_mod_identity.for_catalog('mod:boots_mod:secluded-strike-mirror')
        self.assertEqual((row['normal']['item_id'], row['shiny']['item_id']),
                         ('19500738', '19505768'))
        self.assertTrue(row['normal_to_shiny_link_verified'])
        self.assertTrue(row['native_family']['family_membership_verified'])
        self.assertFalse(row['native_family']['effect_formula_inferred'])
        self.assertEqual(row['steam_build_id'], '26267212')
        self.assertFalse(row['calculation_included'])
        self.assertTrue(row['image_bytes_available'])
        self.assertEqual(row['native_artwork_path'],
                         '/artwork/native_mod__icon_mods_cbt2_hj2.png')
        self.assertFalse(row['ownership_implied'])
        self.assertFalse(row['field_guide_level_rule_inferred'])
        self.assertEqual(len(source['archive_sha256']), 64)

    def test_shiny_only_crosswalk_does_not_infer_ordinary_or_formula(self):
        row = native_mod_identity.for_catalog('mod:boots_mod:slow-and-steady-deviant-energy')
        self.assertIsNone(row['normal'])
        self.assertFalse(row['normal_to_shiny_link_verified'])
        self.assertIsNotNone(row['shiny'])
        self.assertFalse(row['calculation_included'])
        self.assertIsNone(native_mod_identity.for_catalog('mod:weapon_mod:flame-resonance-general'))

    def test_source_native_family_groups_match_all_exact_linked_variants(self):
        groups = native_mod_identity.families()
        self.assertEqual(len(groups), 86)
        self.assertEqual(len({row['native_main_entry_no'] for row in groups.values()}), 25)
        _, pairs = native_mod_identity.load()
        for catalog_id, pair in pairs.items():
            expected = groups[catalog_id]['native_main_entry_no']
            self.assertTrue(all(row['native_main_entry_no'] == expected for row in pair.values()))

    def test_cross_family_or_group_claim_is_rejected(self):
        packet = json.loads(native_mod_identity.FAMILY_PACKET.read_text())
        packet['families'][0]['native_main_entry_no'] = 99999999
        with TemporaryDirectory() as temp:
            path = Path(temp) / 'family.json'
            path.write_text(json.dumps(packet))
            with patch.object(native_mod_identity, 'FAMILY_PACKET', path):
                with self.assertRaisesRegex(ValueError, 'family and exact-ID'):
                    native_mod_identity.families()

    def test_wrong_replacement_direction_rejected(self):
        packet = json.loads(native_mod_identity.PACKET.read_text())
        normal = next(x for x in packet['links'] if x['catalog_id'] ==
                      'mod:boots_mod:secluded-strike-mirror' and x['variant_kind'] == 'normal')
        normal['native_shiny_replacement_mod_code'] = 0
        with TemporaryDirectory() as temp:
            path = Path(temp) / 'packet.json'
            path.write_text(json.dumps(packet))
            with patch.object(native_mod_identity, 'PACKET', path):
                with self.assertRaisesRegex(ValueError, 'replacement conflict'):
                    native_mod_identity.load()

    def test_duplicate_native_item_id_rejected(self):
        packet = json.loads(native_mod_identity.PACKET.read_text())
        packet['links'][1]['native_item_no'] = packet['links'][0]['native_item_no']
        with TemporaryDirectory() as temp:
            path = Path(temp) / 'packet.json'
            path.write_text(json.dumps(packet))
            with patch.object(native_mod_identity, 'PACKET', path):
                with self.assertRaisesRegex(ValueError, 'more than one'):
                    native_mod_identity.load()

    def test_native_icons_have_exact_bytes_and_do_not_overwrite_existing_art(self):
        icons = native_mod_identity.icons()
        self.assertEqual(len(icons), 32)
        for row in icons.values():
            self.assertTrue(row['path'].startswith('/artwork/native_mod__'))
            self.assertEqual(len(row['png_sha256']), 64)
        import server
        import tempfile
        from unittest.mock import patch as mock_patch
        with tempfile.TemporaryDirectory() as temp:
            with mock_patch.object(server, 'DATA', Path(temp)), mock_patch.object(server, 'MEDIA', Path(temp)/'media'), mock_patch.object(server, 'DB', Path(temp)/'test.sqlite3'):
                server.init()
                entries = {e['id']: e for e in server.builder_catalog()['entries']}
        missing = entries['mod:pants_mod:elemental-resonance-deviant-energy-current']
        self.assertTrue(missing['artwork'].startswith('/artwork/native_mod__'))
        self.assertFalse(missing['image_missing'])
        existing = entries['mod:boots_mod:secluded-strike-mirror']
        self.assertFalse(existing['artwork'].startswith('/artwork/native_mod__'))


if __name__ == '__main__':
    unittest.main()
