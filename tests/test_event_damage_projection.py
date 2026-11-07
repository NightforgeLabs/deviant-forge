import unittest

import component_compare
import weapon_timeline_api as timeline


def scenario(weapon, actions, damage_model, *, magazine=None, evidence='dated_release'):
    return {'weapon_id': weapon, 'actions': actions, 'damage_model': damage_model,
            'stream_id': 'projection-fixture', 'magazine': magazine,
            'evidence_mode': evidence, 'model_mode': 'explicit_assumptions'}


class EventDamageProjectionTests(unittest.TestCase):
    def test_direct_and_sourced_trigger_use_independent_class_and_element_pools(self):
        actions = [{'kind': 'hit', 'at': i / 10, 'target': 'dummy',
                    'rolls': {'power_surge': .99},
                    'conditions': {'target_affected_by_power_surge': True},
                    'input_id': f'h{i}'} for i in range(12)]
        model = {'basis_values': {'attack': 100, 'psi': 80},
                 'bonus_pools_percent': {'weapon': 20, 'status': 10, 'elemental': 30},
                 'direct': {'basis': 'attack', 'damage_class': 'weapon',
                            'coefficient_percent': 100, 'element': 'none'},
                 'packet_models': {'celestial_lightning': {'damage_class': 'status'}},
                 'duration_seconds': 2, 'burst_window': {'start_seconds': 0, 'end_seconds': 1}}
        request = scenario('weapon:mps7-outer-space', actions, model)
        result = timeline.simulate(request)
        projection = result['damage_projection']
        self.assertEqual(result['event_counts'], {'damage_trigger': 1})
        self.assertEqual(len(projection['packets']), 13)
        self.assertEqual(result['total_damage'], 2012)
        self.assertEqual(result['damage_per_second'], 1006)
        self.assertEqual(projection['burst']['modeled_damage'], 1200)
        lightning = next(row for row in projection['packets'] if row['event'] == 'celestial_lightning')
        self.assertEqual(lightning['damage_class'], 'status')
        self.assertEqual(lightning['element'], 'shock')
        self.assertAlmostEqual(lightning['damage'], 572)
        self.assertEqual(len({row['event_id'] for row in projection['packets']}), 13)
        other = {**request, 'stream_id': 'other', 'damage_model': {**model,
                 'packet_models': {'celestial_lightning': {'damage_class': 'weapon'}}}}
        self.assertEqual(timeline.simulate(other)['total_damage'], 2064)
        invariant = timeline.simulate({**request, 'stream_id': 'invariant',
            'damage_model': {**model, 'bonus_pools_percent': {}, 'packet_models': {}}})
        self.assertEqual(invariant['total_damage'], 1600)
        self.assertTrue(next(row for row in invariant['damage_projection']['packets']
                             if row['event'] == 'celestial_lightning')['class_invariant_under_entered_pools'])
        unresolved_class = timeline.simulate({**request, 'stream_id': 'class-gap',
            'damage_model': {**model, 'packet_models': {}}})
        self.assertIsNone(unresolved_class['total_damage'])
        self.assertEqual(unresolved_class['damage_projection']['known_damage_subtotal'], 1440)
        self.assertFalse(result['binding_missing'] == [])

    def test_periodic_ticks_are_once_per_trigger_and_replacement_is_explicit(self):
        actions = [{'kind': 'hit', 'at': i / 10, 'target': 'dummy',
                    'input_id': f'h{i}'} for i in range(7)]
        periodic = {'duration_seconds': 3, 'interval_seconds': 1,
                    'start_delay_seconds': 0, 'refresh_model': 'independent'}
        model = {'basis_values': {'attack': 100, 'psi': 50},
                 'direct': {'basis': 'attack', 'damage_class': 'weapon',
                            'coefficient_percent': 100, 'element': 'none'},
                 'packet_models': {'burn': {'basis': 'psi', 'damage_class': 'status',
                                            'element': 'blaze', 'coefficient_percent': 20,
                                            'periodic': periodic}},
                 'duration_seconds': 4}
        request = scenario('weapon:kam-crank', actions, model,
                           evidence='preview_simulation')
        result = timeline.simulate(request)
        self.assertEqual(result['total_damage'], 730)
        self.assertEqual(result['damage_projection']['known_damage_subtotal'], 730)
        self.assertEqual(sum(row['event'] == 'burn_tick' for row in result['damage_projection']['packets']), 3)
        # Two observed burn triggers on one target; replacement discards future
        # ticks from the first schedule and does not invent extra hit events.
        actions2 = [{'kind': 'hit', 'at': i / 10, 'target': 'dummy',
                     'input_id': f'h{i}'} for i in range(14)]
        independent = timeline.simulate({**request, 'actions': actions2})
        replacement = timeline.simulate({**request, 'actions': actions2,
            'damage_model': {**model, 'packet_models': {'burn': {
                **model['packet_models']['burn'], 'periodic': {**periodic,
                    'refresh_model': 'replace_per_target'}}}}})
        self.assertEqual(sum(row['event'] == 'burn_tick' for row in independent['damage_projection']['packets']), 6)
        self.assertEqual(sum(row['event'] == 'burn_tick' for row in replacement['damage_projection']['packets']), 4)

    def test_ammo_reload_blast_and_burst_include_entered_reload_time(self):
        actions = [{'kind': 'fire', 'at': 0, 'rounds': 4, 'input_id': 'fire'},
                   {'kind': 'hit', 'at': .1, 'target': 'dummy',
                    'rolls': {'unstable_bomber': .99}, 'input_id': 'hit'},
                   {'kind': 'reload', 'at': 1, 'input_id': 'reload'}]
        model = {'basis_values': {'attack': 100, 'psi': 100},
                 'direct': {'basis': 'attack', 'damage_class': 'weapon',
                            'coefficient_percent': 100, 'element': 'none'},
                 'packet_models': {'thrown_reload_blast': {'damage_class': 'weapon',
                                                            'target_count': 1}},
                 'reload_timing': {'base_seconds': 2, 'efficiency_percent': 0},
                 'duration_seconds': 4,
                 'burst_window': {'start_seconds': 0, 'end_seconds': .5}}
        request = scenario('weapon:g17-hazardous-object', actions, model, magazine=10)
        result = timeline.simulate(request)
        self.assertEqual(result['ammo']['rounds'], 0)
        self.assertEqual(result['total_damage'], 258)
        self.assertEqual(result['damage_per_second'], 64.5)
        self.assertEqual(result['damage_projection']['burst']['modeled_damage_per_second'], 200)
        with self.assertRaisesRegex(ValueError, 'before entered reload time ends'):
            timeline.simulate({**request, 'actions': actions + [{
                'kind': 'hit', 'at': 2, 'target': 'dummy',
                'rolls': {'unstable_bomber': .99}, 'input_id': 'too-early'}]})
        untimed = timeline.simulate({**request, 'damage_model': {k: v for k, v in model.items()
                                      if k != 'reload_timing'}})
        self.assertEqual(untimed['total_damage'], 258)
        self.assertIsNone(untimed['damage_per_second'])
        self.assertEqual(len(untimed['damage_projection']['unresolved_timing']), 1)
        self.assertEqual(untimed['damage_projection']['known_damage_subtotal'], 258)
        missing_targets = {**request, 'damage_model': {**model,
            'packet_models': {'thrown_reload_blast': {'damage_class': 'weapon'}}}}
        partial = timeline.simulate(missing_targets)
        self.assertEqual(partial['damage_projection']['known_damage_subtotal'], 100)
        self.assertIsNone(partial['total_damage'])
        self.assertTrue(any('target count missing' in x['reason']
                            for x in partial['damage_projection']['unresolved_damage_events']))
        zero_targets = timeline.simulate({**request, 'damage_model': {**model,
            'packet_models': {'thrown_reload_blast': {'damage_class': 'weapon',
                                                       'target_count': 0}}}})
        self.assertEqual(zero_targets['total_damage'], 100)
        three_targets = timeline.simulate({**request, 'damage_model': {**model,
            'packet_models': {'thrown_reload_blast': {'damage_class': 'weapon',
                                                       'target_count': 3}}}})
        self.assertEqual(three_targets['total_damage'], 574)

    def test_source_packet_tick_requires_preview_gate_and_named_reference(self):
        actions = [{'kind': 'hit', 'at': i / 10, 'target': 'dummy',
                    'input_id': f'h{i}'} for i in range(7)]
        periodic = {'duration_seconds': 3, 'interval_seconds': 1,
                    'start_delay_seconds': 0, 'refresh_model': 'independent'}
        model = {'basis_values': {'attack': 100},
                 'reference_values': {'burn_base': 50},
                 'direct': {'basis': 'attack', 'damage_class': 'weapon',
                            'coefficient_percent': 100, 'element': 'none'},
                 'packet_models': {'burn': {'source_packet_id': 'keyword:burn/burn_tick',
                                            'damage_class': 'status', 'periodic': periodic}},
                 'duration_seconds': 4}
        request = scenario('weapon:kam-crank', actions, model,
                           evidence='preview_simulation')
        result = timeline.simulate(request)
        self.assertEqual(result['total_damage'], 718)
        ticks = [row for row in result['damage_projection']['packets']
                 if row['event'] == 'burn_tick']
        self.assertEqual(len(ticks), 3)
        self.assertTrue(all('historical_official_preview' in row['source_status']
                            for row in ticks))
        missing_reference = timeline.simulate({**request, 'damage_model': {
            **model, 'reference_values': {}}})
        self.assertIsNone(missing_reference['total_damage'])
        self.assertEqual(missing_reference['damage_projection']['known_damage_subtotal'], 700)

    def test_unknown_proc_replay_and_classification_remain_explicit(self):
        hit = {'kind': 'hit', 'at': 0, 'target': 'dummy', 'input_id': 'same',
               'rolls': {'power_surge': .1},
               'conditions': {'target_affected_by_power_surge': False}}
        model = {'basis_values': {'attack': 100},
                 'direct': {'basis': 'attack', 'damage_class': 'weapon',
                            'coefficient_percent': 100, 'element': 'none'},
                 'duration_seconds': 1}
        request = scenario('weapon:mps7-outer-space', [hit, hit], model)
        result = timeline.simulate(request)
        self.assertEqual(result['damage_projection']['known_damage_subtotal'], 100)
        self.assertEqual(result['damage_projection']['replayed_direct_hits_suppressed'], 1)
        self.assertIsNone(result['total_damage'])
        self.assertEqual(len(result['damage_projection']['unresolved_damage_events']), 1)
        self.assertIn('power_surge', result['damage_projection']['unresolved_damage_events'][0]['reason'])
        resolved = timeline.simulate({**request, 'damage_model': {**model,
            'packet_models': {'power_surge': {'basis': 'psi', 'damage_class': 'status',
                'coefficient_percent': 100, 'element': 'shock', 'basis_value': 50,
                'resolved_hits': 1}}}})
        self.assertEqual(resolved['total_damage'], 150)
        unknown_element = timeline.simulate({**request, 'damage_model': {**model,
            'bonus_pools_percent': {'elemental': 100},
            'packet_models': {'power_surge': {'basis': 'psi', 'damage_class': 'status',
                'coefficient_percent': 100, 'basis_value': 50,
                'resolved_hits': 1}}}})
        self.assertIsNone(unknown_element['total_damage'])
        self.assertTrue(any('elemental pool applicability' in x['reason']
                            for x in unknown_element['damage_projection']['unresolved_damage_events']))
        compared = component_compare.compare({'attributes': []}, {'attributes': []},
            {'weapon_timeline': {'left': request, 'right': {**request, 'stream_id': 'right'}}})
        self.assertEqual(compared['component_ratios']['normal']['min'], 1)
        self.assertEqual(compared['weapon_timeline_scenarios']['left']['damage_projection']['known_damage_subtotal'], 100)
        self.assertFalse(compared['game_winner_established'])

    def test_crit_joint_model_and_state_modifier_guard(self):
        hit = {'kind': 'hit', 'at': 0, 'target': 'dummy', 'input_id': 'hit',
               'crit': True, 'weakspot': True, 'rolls': {'fast_gunner': .99}}
        model = {'basis_values': {'attack': 100},
                 'bonus_pools_percent': {'crit': 100, 'weakspot': 100},
                 'direct': {'basis': 'attack', 'damage_class': 'weapon',
                            'element': 'none', 'coefficient_percent': 100,
                            'crit_eligible': True, 'weakspot_eligible': True},
                 'duration_seconds': 1}
        request = scenario('weapon:mg4-predator', [hit], model)
        additive = timeline.simulate({**request, 'damage_model': {**model,
                            'crit_weakspot_joint': 'additive'}})
        self.assertEqual(additive['damage_projection']['known_damage_subtotal'], 300)
        self.assertIsNone(additive['total_damage'])
        self.assertTrue(any('state modifier' in x['reason']
                            for x in additive['damage_projection']['unresolved_damage_events']))
        with self.assertRaisesRegex(ValueError, 'damage_basis_value on every hit'):
            timeline.simulate({**request, 'damage_model': {**model,
                    'state_effects_accounted_for_by_input': True}})
        hit_with_state = {**hit, 'damage_basis_value': 100}
        explicit = timeline.simulate({**request, 'actions': [hit_with_state],
            'damage_model': {**model, 'state_effects_accounted_for_by_input': True,
                             'crit_weakspot_joint': 'additive',
                             'non_damage_events': ['fast_gunner']}})
        self.assertEqual(explicit['total_damage'], 300)
        self.assertEqual(explicit['damage_per_second'], 300)


if __name__ == '__main__':
    unittest.main()
