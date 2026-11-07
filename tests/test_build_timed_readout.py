"""Normal Build uses the same unsaved timed evaluator as Compare."""
import copy
import hashlib
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import build_timed_readout
import server
import structured_compare


WEAPON = 'weapon:aug-electron-cloud'
MOD = 'mod:gloves_mod:elemental-overload-resonance'
SLOTS = {'primary': {'catalog_id': WEAPON, 'tier': 1, 'stars': 1},
         'gloves': {'catalog_id': 'armor:gilded-gauntlets',
                    'mod_id': MOD, 'mod_level': 9}}
REFERENCE = {'tier': 1, 'stars': 1,
             'item_page_scenario': {'assume_displayed_damage_per_projectile': True, 'assume_fire_rate_as_rpm': True,
                                    'projectiles_per_shot': 1, 'reload_seconds': 2.5}}
TIMED = {'duration_seconds': .18, 'exclude_unbound_weapon_effect': True,
         'crit_share': 0, 'weakspot_share': 0, 'joint_share': 0,
         'resonance_outcomes': {'crit_shot_indices': [],
                                'weakspot_shot_indices': [1],
                                'elemental_shot_indices': [0],
                                'element': 'shock', 'reserve_bullets': 0},
         'resonance_baseline': {'weakspot_bonus_percent': 100}}


class BuildTimedReadoutTests(unittest.TestCase):
    def test_selected_level_matches_compare_without_mutating_slots(self):
        slots = copy.deepcopy(SLOTS)
        result = build_timed_readout.evaluate(slots, REFERENCE, TIMED)
        self.assertEqual(SLOTS, slots)
        self.assertEqual('conditional_modeled_total', result['status'])
        self.assertAlmostEqual(146.66376, result['model']['modeled_total_damage'])
        self.assertEqual(18, result['model']['effective_pools_percent']['elemental'])
        self.assertEqual(4, len(result['selected_mod_rows']))
        self.assertEqual('source_page_without_selected_build_modifiers',
                         result['source_baseline']['baseline_bonus_scope'])
        self.assertFalse(result['game_verified'])
        self.assertFalse(result['reference_differs_from_selected'])
        plan = {'id': 'same-selected-build', 'name': 'same', 'slots': slots}
        request = {'left': {'kind': 'planned_build', 'planned_build_id': plan['id']},
                   'right': {'kind': 'planned_build', 'planned_build_id': plan['id']},
                   'context': {'published_reference': {'enabled': True,
                       'left': {'weapon_id': WEAPON, **REFERENCE},
                       'right': {'weapon_id': WEAPON, **REFERENCE},
                       'timed': {'duration_seconds': .18,
                                 'left': TIMED, 'right': TIMED}}}}
        compared = structured_compare.compare(request, [plan])['published_reference']
        self.assertEqual(result['model']['modeled_total_damage'],
                         compared['timed_scenarios']['left']['modeled_total_damage'])

    def test_reference_override_is_labeled_and_unknown_weapon_stays_unknown(self):
        selected = copy.deepcopy(SLOTS)
        selected['primary'].update(tier=5, stars=5)
        selected['primary']['weapon_readout'] = {'attack': 999, 'rpm': 999}
        selected['primary']['calibration_profile'] = {'fixed_effects': 'Attack +99%'}
        with self.assertRaisesRegex(ValueError, 'no exact item page damage'):
            build_timed_readout.evaluate(selected, {**REFERENCE, 'tier': 5, 'stars': 5}, TIMED)
        hypothetical = build_timed_readout.evaluate(selected, REFERENCE, TIMED)
        self.assertTrue(hypothetical['reference_differs_from_selected'])
        self.assertEqual((5, 5),
                         (hypothetical['selected_tier'], hypothetical['selected_stars']))
        self.assertEqual(34, hypothetical['source_baseline']['stats']['damage_per_projectile'])
        self.assertTrue(hypothetical['selected_readout_and_calibration_excluded'])
        self.assertAlmostEqual(146.66376,
                               hypothetical['model']['modeled_total_damage'])
        self.assertEqual(999, selected['primary']['weapon_readout']['attack'])
        self.assertEqual(selected['primary']['tier'], 5)
        missing = build_timed_readout.evaluate(selected, {}, TIMED)
        self.assertEqual('needs_reference_inputs', missing['status'])

    def test_entered_packet_models_other_selected_weapons_without_imported_damage(self):
        slots = {'primary': {'catalog_id': 'weapon:kam-crank', 'tier': 5, 'stars': 5}}
        caller = {'tier': 5, 'stars': 5, 'caller_packet_scenario': {
            'assume_direct_body_damage_per_projectile': True, 'baseline_bonus_scope':'before_selected_effects',
            'direct_body_damage_per_projectile': 100,
            'projectiles_per_shot': 1, 'rpm': 600,
            'magazine_capacity': 10, 'reload_seconds': 2}}
        run = build_timed_readout.evaluate(slots, caller, {
            'duration_seconds': .2, 'crit_share': 0, 'weakspot_share': 0,
            'joint_share': 0, 'exclude_unbound_weapon_effect': True})
        self.assertEqual('caller_entered_direct_packet', run['reference_kind'])
        self.assertEqual('before_selected_effects', run['source_baseline']['baseline_bonus_scope'])
        self.assertTrue(any('exclude selected weapon, gear, mod and set effects' in line
                            for line in run['model']['assumptions']))
        self.assertEqual('conditional_modeled_total', run['status'])
        self.assertEqual(200, run['model']['modeled_total_damage'])
        self.assertIn('caller hypothesis', run['model']['assumptions'][0])
        self.assertEqual(SLOTS['primary']['catalog_id'], WEAPON)  # unrelated plan untouched
        with self.assertRaisesRegex(ValueError, 'already-buffed values would double count'):
            build_timed_readout.evaluate(slots, {**caller,
                'caller_packet_scenario': {**caller['caller_packet_scenario'],
                                           'baseline_bonus_scope': 'already_includes_selected_effects'}},
                {'duration_seconds': .2})
        with self.assertRaisesRegex(ValueError, 'already-buffed values would double count'):
            build_timed_readout.evaluate(slots, {**caller,
                'caller_packet_scenario': {key: value for key, value in caller['caller_packet_scenario'].items()
                                           if key != 'baseline_bonus_scope'}}, {'duration_seconds': .2})
        with self.assertRaisesRegex(ValueError, 'selected weapon tier and stars'):
            build_timed_readout.evaluate(slots, {**caller, 'tier': 1},
                                         {'duration_seconds': .2})
        with self.assertRaisesRegex(ValueError, 'positive direct_body_damage'):
            build_timed_readout.evaluate(slots, {**caller,
                'caller_packet_scenario': {**caller['caller_packet_scenario'],
                                           'direct_body_damage_per_projectile': 0}},
                {'duration_seconds': .2})

    def test_exact_against_all_odds_level7_no_hp_cost_build_compare_parity(self):
        slots = {'primary': {'catalog_id': 'weapon:kam-crank', 'tier': 5, 'stars': 5},
                 'shoes': {'catalog_id': 'armor:earthly-boots',
                           'mod_id': 'mod:boots_mod:against-all-odds-precision',
                           'mod_level': 7}}
        original = copy.deepcopy(slots)
        reference = {'tier': 5, 'stars': 5, 'caller_packet_scenario': {
            'assume_direct_body_damage_per_projectile': True, 'baseline_bonus_scope':'before_selected_effects',
            'direct_body_damage_per_projectile': 100, 'projectiles_per_shot': 1,
            'rpm': 600, 'magazine_capacity': 10, 'reload_seconds': 2}}
        timed = {'duration_seconds': .2, 'crit_share': 0, 'weakspot_share': 0,
                 'joint_share': 0, 'exclude_unbound_weapon_effect': True}
        blocked = build_timed_readout.evaluate(slots, reference, timed)
        self.assertIsNone(blocked['model']['modeled_total_damage'])
        self.assertTrue(any('HP-cost stacks need event times' in gap
                            for gap in blocked['model']['unresolved']))
        no_cost = {**timed, 'core_no_hp_cost_events': True}
        selected = build_timed_readout.evaluate(slots, reference, no_cost)
        self.assertEqual('conditional_modeled_total', selected['status'])
        self.assertAlmostEqual(228.172, selected['model']['modeled_total_damage'])
        self.assertEqual(12.4, selected['model']['effective_pools_percent']['weapon'])
        self.assertEqual(10, selected['model']['effective_pools_percent']['status'])
        self.assertEqual('no_hp_cost_events', selected['model']['typed_core_pools_applied'][0]['stack_model'])
        self.assertEqual(original, slots)
        plan = {'id': 'against-lv7', 'name': 'Exact source scenario', 'slots': slots}
        compared = structured_compare.compare({
            'left': {'kind': 'planned_build', 'planned_build_id': plan['id']},
            'right': {'kind': 'planned_build', 'planned_build_id': plan['id']},
            'context': {'published_reference': {'enabled': True,
                'left': {'weapon_id': 'weapon:kam-crank', **reference},
                'right': {'weapon_id': 'weapon:kam-crank', **reference},
                'timed': {'duration_seconds': .2,
                          'left': no_cost, 'right': no_cost}}}}, [plan])['published_reference']
        self.assertAlmostEqual(228.172, compared['timed_scenarios']['left']['modeled_total_damage'])

    def test_exact_striving_and_bullet_siphon_conditional_endpoints(self):
        slots = {'primary': {'catalog_id': 'weapon:kam-crank', 'tier': 5, 'stars': 5},
                 'shoes': {'catalog_id': 'armor:earthly-boots',
                           'mod_id': 'mod:boots_mod:power-of-striving-downstar-deviant-energy',
                           'mod_level': 9}}
        original = copy.deepcopy(slots)
        base = {'tier': 5, 'stars': 5, 'caller_packet_scenario': {
            'assume_direct_body_damage_per_projectile': True, 'baseline_bonus_scope':'before_selected_effects',
            'direct_body_damage_per_projectile': 100, 'projectiles_per_shot': 1,
            'rpm': 600, 'magazine_capacity': 10, 'reload_seconds': 2}}
        timed = {'duration_seconds': .2, 'crit_share': 0, 'weakspot_share': 0,
                 'joint_share': 0, 'exclude_unbound_weapon_effect': True}
        unknown = build_timed_readout.evaluate(slots, base, timed)
        self.assertIsNone(unknown['model']['modeled_total_damage'])
        self.assertTrue(any('stamina-loss bonus' in x for x in unknown['model']['unresolved']))
        no_stamina = {**timed, 'core_no_stamina_loss_events': True}
        unknown_position = build_timed_readout.evaluate(slots, base, no_stamina)
        self.assertIsNone(unknown_position['model']['modeled_total_damage'])
        self.assertTrue(any('conditional extra' in x for x in unknown_position['model']['unresolved']))
        inactive = {**base, 'condition_fractions': {
            'enemy below player, maximum at 5 meters': 0}}
        active = {**base, 'condition_fractions': {
            'enemy below player, maximum at 5 meters': 1}}
        for reference, status_pool in ((inactive, 12.4), (active, 13.6)):
            result = build_timed_readout.evaluate(slots, reference, no_stamina)
            self.assertEqual('conditional_modeled_total', result['status'])
            self.assertAlmostEqual(226.6, result['model']['modeled_total_damage'])
            self.assertEqual(status_pool, result['model']['effective_pools_percent']['status'])
            self.assertEqual('no_stamina_loss_events', result['model']['typed_core_pools_applied'][0]['stack_model'])
        self.assertEqual(original, slots)
        slots['bottoms'] = {'catalog_id': 'armor:hot-dog-shorts',
            'mod_id': 'mod:pants_mod:bullet-siphon-aero-deviant-energy', 'mod_level': 12}
        six = {**no_stamina, 'duration_seconds': .6}
        missing_aerial = build_timed_readout.evaluate(slots, inactive, six)
        self.assertIsNone(missing_aerial['model']['modeled_total_damage'])
        self.assertTrue(any('aerial hit fraction' in x for x in missing_aerial['model']['unresolved']))
        both = {**inactive, 'condition_fractions': {
            **inactive['condition_fractions'], 'aerial hit': 0}}
        selected = build_timed_readout.evaluate(slots, both, six)
        self.assertEqual('conditional_modeled_total', selected['status'])
        self.assertAlmostEqual(746.05, selected['model']['modeled_total_damage'])
        self.assertAlmostEqual(2/3, selected['model']['bullet_counter_average_percent'])
        self.assertEqual(2, len(selected['model']['typed_core_pools_applied']))
        plan = {'id': 'exact-batch', 'name': 'Exact observed mods', 'slots': copy.deepcopy(slots)}
        compared = structured_compare.compare({
            'left': {'kind': 'planned_build', 'planned_build_id': plan['id']},
            'right': {'kind': 'planned_build', 'planned_build_id': plan['id']},
            'context': {'published_reference': {'enabled': True,
                'left': {'weapon_id': 'weapon:kam-crank', **both},
                'right': {'weapon_id': 'weapon:kam-crank', **both},
                'timed': {'duration_seconds': .6, 'left': six, 'right': six}}}}, [plan])['published_reference']
        self.assertAlmostEqual(746.05, compared['timed_scenarios']['left']['modeled_total_damage'])

    def test_selected_outer_space_proc_and_mod_use_same_compare_model(self):
        slots = {'primary': {'catalog_id': 'weapon:mps7-outer-space', 'tier': 5,
                             'stars': 5}}
        reference = {'tier': 5, 'stars': 5, 'caller_packet_scenario': {
            'assume_direct_body_damage_per_projectile': True, 'baseline_bonus_scope':'before_selected_effects',
            'direct_body_damage_per_projectile': 100, 'projectiles_per_shot': 1,
            'rpm': 900, 'magazine_capacity': 35, 'reload_seconds': 3}}
        timed = {'duration_seconds': .8, 'crit_share': 0, 'weakspot_share': 0,
                 'joint_share': 0, 'source_timeline': {
                     'reserve_bullets': 0, 'target_id': 'dummy',
                     'roll_sequence': [.99] * 12,
                     'condition_sequences': {
                         'target_affected_by_power_surge': [True] * 12},
                     'damage_model': {'basis_values': {'psi': 80},
                                      'packet_models': {'celestial_lightning': {
                                          'damage_class': 'status'}}}}}
        run = build_timed_readout.evaluate(slots, reference, timed)
        self.assertEqual('conditional_modeled_total', run['status'])
        self.assertEqual(1600, run['model']['modeled_total_damage'])
        self.assertEqual(1200, run['model']['direct_expected']['total_damage'])
        self.assertEqual(400, run['model']['source_proc']['damage'])
        self.assertEqual({'magazine': 23, 'reserve': 0},
                         run['model']['source_timeline']['final_ammo'])
        plan = {'id': 'outer-space-plan', 'name': 'same', 'slots': slots}
        request = {'left': {'kind': 'planned_build', 'planned_build_id': plan['id']},
                   'right': {'kind': 'planned_build', 'planned_build_id': plan['id']},
                   'context': {'published_reference': {'enabled': True,
                       'left': {'weapon_id': slots['primary']['catalog_id'], **reference},
                       'right': {'weapon_id': slots['primary']['catalog_id'], **reference},
                       'timed': {'duration_seconds': .8,
                                 'left': timed, 'right': timed}}}}
        compared = structured_compare.compare(request, [plan])['published_reference']
        self.assertEqual(run['model']['modeled_total_damage'],
                         compared['timed_scenarios']['left']['modeled_total_damage'])
        no_counter = copy.deepcopy(timed)
        no_counter['source_timeline']['condition_sequences'] = {
            'target_affected_by_power_surge': [False] * 12}
        self.assertEqual(1200, build_timed_readout.evaluate(
            slots, reference, no_counter)['model']['modeled_total_damage'])
        other = {'primary': {'catalog_id': 'weapon:kam-crank', 'tier': 5, 'stars': 5}}
        with self.assertRaisesRegex(ValueError, 'match the selected'):
            build_timed_readout.evaluate(other, {
                **reference, 'weapon_id': slots['primary']['catalog_id']}, timed)

    def test_selected_hazardous_reload_blast_uses_finite_ammo(self):
        slots = {'primary': {'catalog_id': 'weapon:g17-hazardous-object',
                             'tier': 5, 'stars': 5}}
        reference = {'tier': 5, 'stars': 5, 'caller_packet_scenario': {
            'assume_direct_body_damage_per_projectile': True, 'baseline_bonus_scope':'before_selected_effects',
            'direct_body_damage_per_projectile': 100,
            'projectiles_per_shot': 1, 'rpm': 600,
            'magazine_capacity': 2, 'reload_seconds': 2}}
        controls = {'reserve_bullets': 0, 'target_id': 'dummy',
                    'reload_after_shots': 1, 'roll_sequence': [.99],
                    'damage_model': {'basis_values': {'psi': 100},
                                     'packet_models': {'thrown_reload_blast': {
                                         'damage_class': 'weapon', 'target_count': 2}}}}
        timed = {'duration_seconds': 3, 'crit_share': 0, 'weakspot_share': 0,
                 'joint_share': 0, 'source_timeline': controls}
        run = build_timed_readout.evaluate(slots, reference, timed)
        self.assertEqual('conditional_modeled_total', run['status'])
        self.assertEqual(0, run['model']['source_timeline']['events'][1]['loaded_rounds'])
        self.assertEqual({'magazine': 0, 'reserve': 0},
                         run['model']['source_timeline']['final_ammo'])
        self.assertGreater(run['model']['source_proc']['damage'], 0)
        missing = copy.deepcopy(timed)
        del missing['source_timeline']['damage_model']['packet_models'][
            'thrown_reload_blast']['target_count']
        partial = build_timed_readout.evaluate(slots, reference, missing)
        self.assertEqual('partial_timed_total', partial['status'])
        self.assertIsNone(partial['model']['modeled_total_damage'])

    def test_http_uses_unsaved_slots_and_preserves_database(self):
        with tempfile.TemporaryDirectory() as temp:
            old = server.DATA, server.MEDIA, server.DB
            server.DATA = Path(temp)
            server.MEDIA = server.DATA / 'media'
            server.DB = server.DATA / 'advisor.sqlite3'
            try:
                server.init()
                before = hashlib.sha256(server.DB.read_bytes()).hexdigest()
                http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
                worker = threading.Thread(target=http.serve_forever, daemon=True)
                worker.start()
                try:
                    base = f'http://127.0.0.1:{http.server_port}/api/build-timed-readout'
                    def post(slots, reference=REFERENCE):
                        request = Request(base, json.dumps({'slots': slots,
                            'reference': reference, 'timed': TIMED}).encode(),
                            {'Content-Type': 'application/json'})
                        with urlopen(request) as response:
                            return json.load(response)
                    result = post(SLOTS)
                    self.assertAlmostEqual(146.66376,
                                           result['model']['modeled_total_damage'])
                    bare = copy.deepcopy(SLOTS)
                    del bare['gloves']['mod_id'];del bare['gloves']['mod_level']
                    without = post(bare)
                    self.assertLess(without['model']['known_damage_subtotal'],
                                    result['model']['known_damage_subtotal'])
                    with self.assertRaises(HTTPError):
                        post({**SLOTS, 'primary': {**SLOTS['primary'],
                            'catalog_id': 'weapon:kam-crank'}})
                finally:
                    http.shutdown();http.server_close();worker.join(timeout=2)
                self.assertEqual(before, hashlib.sha256(server.DB.read_bytes()).hexdigest())
            finally:
                server.DATA, server.MEDIA, server.DB = old
