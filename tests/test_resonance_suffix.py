"""Sourced, conditional Resonance operator and selected-build wiring."""
import copy
import unittest

import catalog
import component_compare
import integrated_event_model as model
import integration_ledger
import public_catalog_detail
import resonance_suffix
import structured_compare


IDENTITY = 'mod:gloves_mod:crit-amplifier-resonance-deviant-energy'
ASSUMPTIONS = {'scheduler': 'next_shot_interval',
               'fire_rate_conversion': 'rpm_times_one_plus_bonus',
               'pool_grouping': 'additive_within_named_pool_multiplicative_across_pools',
               'event_order': 'as_list'}
STACK_ASSUMPTIONS = {'trigger': 'explicit_resolved_packet_outcome',
                     'activation': 'after_packet', 'expiry': 'per_instance_half_open',
                     'cap': 'discard_excess_until_expiry'}
OUTCOME = {'base_crit_bonus_percent': 100, 'base_weakspot_bonus_percent': 100,
           'joint_multiplier': 'additive'}
POOLS = {pool: 0 for pool in component_compare.POOLS.values()}


def scenario(events, *, direct=None, duration=8):
    return {'model_assumptions': ASSUMPTIONS.copy(), 'resonance_assumptions': STACK_ASSUMPTIONS.copy(),
            'outcome_assumptions': OUTCOME.copy(), 'base_rpm': 600,
            'duration_seconds': duration, 'magazine_capacity': 100,
            'starting_magazine_bullets': 100, 'starting_reserve_bullets': 0,
            'magazine_capacity_is_final': True,
            'direct_packet': direct or {'basis_value': 100, 'coefficient_percent': 100,
                                         'damage_class': 'weapon', 'element': 'none'},
            'events': events}


class ResonanceSuffixTests(unittest.TestCase):
    def test_all_45_published_ordinary_identities_have_complete_timed_bindings(self):
        identities = []
        for identity, entry in catalog.ENTRIES.items():
            if entry.get('kind') != 'mod' or entry.get('family_only'):
                continue
            rows, _, _ = public_catalog_detail.calculation_rows(identity, 10)
            if any(str(row.get('stat_type') or '').startswith('resonance_') for row in rows):
                identities.append(identity)
                rules = resonance_suffix.bindings({'catalog_id': identity, 'level': 10})
                self.assertGreaterEqual(len(rules), 1, identity)
                self.assertTrue(all(rule['source'].startswith('https://') for rule in rules))
        self.assertEqual(45, len(identities))
        with self.assertRaisesRegex(ValueError, 'Shiny'):
            resonance_suffix.bindings({'catalog_id': IDENTITY, 'level': 17, 'shiny': True})

    def test_after_packet_activation_crit_elemental_expiry_and_no_passive_bonus(self):
        events = [{'kind': 'shot', 'event_id': 'plain', 'at': 0},
                  {'kind': 'shot', 'event_id': 'elemental', 'at': .1,
                   'packet_outcome': {'element': 'shock'}},
                  {'kind': 'shot', 'event_id': 'critical', 'at': .2,
                   'packet_outcome': {'crit': True}},
                  {'kind': 'shot', 'event_id': 'elemental2', 'at': .3,
                   'packet_outcome': {'element': 'shock'}},
                  {'kind': 'shot', 'event_id': 'expired', 'at': 6.4,
                   'packet_outcome': {'crit': True}}]
        before = scenario(events)
        original = copy.deepcopy(before)
        compared = component_compare.compare({'attributes': []},
            {'catalog_id': IDENTITY, 'level': 10},
            {'base_pools': POOLS, 'integrated_combat': {'left': before, 'right': before}})
        right = compared['integrated_event_scenarios']['right']
        self.assertEqual(original, before)
        self.assertEqual(2, len(right['resonance_sources']))
        self.assertEqual(0, right['selected_row_pools_percent']['crit'])
        self.assertEqual(0, right['selected_row_pools_percent']['elemental'])
        self.assertEqual([100, 100, 202.4, 100.6, 200],
                         [round(p['damage'], 4) for p in right['packets']])
        self.assertEqual(200, compared['integrated_event_scenarios']['left']['packets'][-1]['damage'])
        self.assertFalse(compared['game_winner_established'])

    def test_cap_same_timestamp_multi_hit_and_replay(self):
        events = [{'kind': 'triggered_packet', 'event_id': 'burst', 'at': 0,
                   'packet': {'basis_value': 100, 'coefficient_percent': 100,
                              'damage_class': 'weapon', 'element': 'shock',
                              'resolved_hits': 9}},
                  {'kind': 'triggered_packet', 'event_id': 'burst', 'at': 0,
                   'packet': {'basis_value': 100, 'coefficient_percent': 100,
                              'damage_class': 'weapon', 'element': 'shock',
                              'resolved_hits': 9}},
                  {'kind': 'shot', 'event_id': 'critical', 'at': 0,
                   'packet_outcome': {'crit': True}}]
        result = model.evaluate({**scenario(events),
                                 'resonance_suffixes': [{'catalog_id': IDENTITY, 'level': 10}]},
                                static_pools={pool: 0 for pool in model.SUPPORTED_POOLS})
        self.assertEqual(result['replayed_events_suppressed'], 1)
        self.assertEqual(5, sum(o['type'] == 'resonance_stack_activation'
                                for o in result['event_trace'][0]['candidate_outputs']))
        self.assertAlmostEqual(212, result['packets'][-1]['damage'])

    def test_weakspot_to_elemental_is_scoped_and_expires(self):
        ordinary = 'mod:gloves_mod:crit-amplifier-resonance'
        events = [{'kind': 'shot', 'event_id': 'weak', 'at': 0,
                   'packet_outcome': {'weakspot': True}},
                  {'kind': 'shot', 'event_id': 'elemental', 'at': .1,
                   'packet_outcome': {'element': 'shock'}},
                  {'kind': 'shot', 'event_id': 'normal', 'at': .2},
                  {'kind': 'shot', 'event_id': 'late_elemental', 'at': 6.1,
                   'packet_outcome': {'element': 'shock'}}]
        result = model.evaluate({**scenario(events),
                                 'resonance_suffixes': [{'catalog_id': ordinary, 'level': 10}]},
                                static_pools={pool: 0 for pool in model.SUPPORTED_POOLS})
        self.assertEqual([200, 100.6, 100, 100],
                         [round(packet['damage'], 4) for packet in result['packets']])
        self.assertEqual(2, len(result['resonance_sources']))

    def test_missing_outcome_and_status_crit_are_rejected(self):
        events = [{'kind': 'shot', 'event_id': 's1', 'packet_outcome': {'crit': True}}]
        bad = {**scenario(events), 'resonance_suffixes': [{'catalog_id': IDENTITY, 'level': 10}]}
        del bad['outcome_assumptions']
        with self.assertRaisesRegex(ValueError, 'joint model'):
            model.evaluate(bad, static_pools={pool: 0 for pool in model.SUPPORTED_POOLS})
        bad = {**scenario(events, direct={'basis_value': 100, 'coefficient_percent': 100,
                                          'damage_class': 'status', 'element': 'none'}),
               'resonance_suffixes': [{'catalog_id': IDENTITY, 'level': 10}]}
        with self.assertRaisesRegex(ValueError, 'effect-specific'):
            model.evaluate(bad, static_pools={pool: 0 for pool in model.SUPPORTED_POOLS})

    def test_planned_build_matches_single_selected_identity(self):
        events = [{'kind': 'shot', 'event_id': 'e', 'packet_outcome': {'element': 'shock'}},
                  {'kind': 'shot', 'event_id': 'c', 'packet_outcome': {'crit': True}}]
        req = scenario(events)
        plan = {'id': 'synthetic-resonance', 'name': 'Synthetic Resonance',
                'slots': {'gloves': {'mod_id': IDENTITY, 'mod_level': 10}}}
        selected = structured_compare.compare({
            'left': {'kind': 'catalog', 'catalog_id': IDENTITY, 'level': 10},
            'right': {'kind': 'planned_build', 'planned_build_id': plan['id']},
            'context': {'base_pools': POOLS,
                        'integrated_combat': {'left': req, 'right': req}}}, [plan])
        outputs = selected['comparison']['integrated_event_scenarios'] if 'comparison' in selected else selected['integrated_event_scenarios']
        self.assertEqual(outputs['left']['total_damage'], outputs['right']['total_damage'])
        self.assertEqual(2, len(outputs['right']['resonance_sources']))

    def test_ledger_counts_operator_connected_without_full_item_claim(self):
        ledger = integration_ledger.build()
        self.assertEqual(45, ledger['non_scalar_bonus_lv10']['published_resonance_event_stack'])
        rows = [r for r in ledger['records'] if r['kind'] == 'mod' and
                r['non_scalar_bonus_class'] == 'published_resonance_event_stack']
        self.assertEqual(45, len(rows))
        self.assertTrue(all(any(req['state'] == 'candidate_timed_operator_guided_and_advanced'
                                for req in r['requirements']) and r['category'] != 'complete'
                            for r in rows))
        conflicted = next(r for r in rows if r['catalog_id'] ==
                          'mod:gloves_mod:elemental-overload-resonance')
        self.assertEqual('held_semantic_layout_conflict_partial',
                         conflicted['requirements'][0]['state'])


if __name__ == '__main__':
    unittest.main()
