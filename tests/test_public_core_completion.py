from tests.explicit_reference_fixture import explicit_synthetic_reference
"""Conditional completion must preserve target, utility and timed-event boundaries."""
import json
from pathlib import Path
import unittest

import published_main_core as core
import published_reference_model as reference
import published_timed_combat as timed


LEDGER = json.loads((Path(__file__).resolve().parent.parent /
                     'evidence_packets/public-core-operator-ledger-v1.json').read_text())


def selected(identity, *, fractions=None):
    return reference.build({'weapon': {'catalog_id': 'weapon:kam'},
                            'mods': [{'catalog_id': identity, 'level': 10}],
                            'condition_fractions': fractions or {}})


@explicit_synthetic_reference
class PublicCoreCompletionTests(unittest.TestCase):
    def assert_native_scope_partial(self, result):
        self.assertEqual(result['status'], 'partial_timed_total')
        self.assertIsNone(result['modeled_total_damage'])
        self.assertTrue(any('Native configured bonus targets four monster classes' in gap
                            for gap in result['unresolved']))

    def test_enemy_bucket_requires_target_activity_and_named_model(self):
        identity = 'mod:gloves_mod:weapon-amplifier-aero'
        text = 'Weapon DMG +9%'
        plain = timed.evaluate(selected(identity), {'duration_seconds': 1,
            'published_item_core_opt_in': True, 'core_effect_text': text})
        self.assertEqual(plain['status'], 'partial_timed_total')
        self.assertTrue(any('Damage against enemies' in gap for gap in plain['unresolved']))
        fractions = {'damage against enemies': 1, 'aerial hit for extra component': 0}
        build = selected(identity, fractions=fractions)
        without_bucket = timed.evaluate(build, {'duration_seconds': 1,
            'published_item_core_opt_in': True, 'core_effect_text': text})
        self.assertEqual(without_bucket['status'], 'partial_timed_total')
        self.assert_native_scope_partial(without_bucket)
        with_bucket = timed.evaluate(build, {'duration_seconds': 1,
            'published_item_core_opt_in': True, 'core_effect_text': text,
            'enemy_damage_bucket_model': 'independent_multiplicative'})
        self.assert_native_scope_partial(with_bucket)
        self.assertEqual(with_bucket['effective_pools_percent']['enemy_damage'], 0)
        self.assertEqual([x['name'] for x in with_bucket['utility_bonus_lines']], ['Max HP'])
        self.assertFalse(with_bucket['game_winner_established'])
        no_enemy = timed.evaluate(selected(identity, fractions={**fractions,
            'damage against enemies': 0}), {'duration_seconds': 1,
            'published_item_core_opt_in': True, 'core_effect_text': text})
        self.assert_native_scope_partial(no_enemy)
        self.assertAlmostEqual(with_bucket['known_damage_subtotal'],
                               no_enemy['known_damage_subtotal'])
        self.assertTrue(any('Damage against enemies' in line for line in build['unresolved']))

    def test_representative_ordinary_batch_withholds_conflicted_monster_scope(self):
        fractions = {'damage against enemies': 1,
                     'aerial hit for extra component': 0, 'aerial hit': 0,
                     'attack from behind': 0,
                     'shield threshold 40 percent;  threshold basis and extra curve unpublished': 0,
                     'scales with low hp;  curve unpublished': 0}
        complete, blocked = [], {}
        for row in LEDGER['records']:
            if row['calculation_status'] != 'opt_in_damage_scenario_supported':
                continue
            identity = row['catalog_id']
            text = core.PUBLIC[identity]['effect_text_variants_unranked'][0]
            result = timed.evaluate(selected(identity, fractions=fractions), {
                'duration_seconds': 1, 'published_item_core_opt_in': True,
                'core_effect_text': text,
                'core_condition_active': False,
                'core_target_distance_meters': 25,
                'enemy_damage_bucket_model': 'independent_multiplicative'})
            if result['status'] == 'conditional_modeled_total':
                complete.append(identity)
                self.assertIsNotNone(result['modeled_total_damage'])
            else:
                blocked[identity] = result['unresolved']
        self.assertEqual(len(complete), 0)
        self.assertEqual(len(blocked), 26)
        self.assertEqual(sum(any('Damage against enemies' in gap for gap in gaps)
                             for gaps in blocked.values()), 25)
        self.assertTrue(any('All DMG Boost magnitude or activation missing' in gap
                            for gap in blocked['mod:pants_mod:bullet-siphon-aero-deviant-energy']))
        self.assertTrue(any('Reload Speed' in gap for gaps in blocked.values()
                            for gap in gaps))

    def test_mirror_crit_keeps_base_and_adds_only_behind_component(self):
        identity = 'mod:boots_mod:secluded-strike-mirror'
        front = selected(identity, fractions={'attack from behind': 0})
        behind = selected(identity, fractions={'attack from behind': 1})
        self.assertEqual(front['selected_pools_percent']['crit'], 6)
        self.assertEqual(behind['selected_pools_percent']['crit'], 18)
        self.assertTrue(any('Firearm Damage' in gap for gap in front['unresolved']))

    def test_hp_utility_exclusion_does_not_erase_hp_sensitive_core_gap(self):
        identity = 'mod:gloves_mod:lifeforce-boost-aero'
        build = selected(identity, fractions={'damage against enemies': 0,
                                             'aerial hit for extra component': 0})
        result = timed.evaluate(build, {'duration_seconds': 1,
            'published_item_core_opt_in': True, 'core_effect_text': 'HP +8%'})
        self.assertEqual(result['status'], 'partial_timed_total')
        self.assertTrue(any('HP utility' in gap for gap in result['unresolved']))
        self.assertTrue(any(row['name'] == 'Max HP' for row in result['utility_bonus_lines']))

    def test_conflicted_enemy_bonus_cannot_be_restored_by_target_assumption(self):
        identity = 'mod:gloves_mod:weapon-amplifier-aero'
        build = reference.build({'weapon': {'catalog_id': 'weapon:mps7-outer-space'},
            'mods': [{'catalog_id': identity, 'level': 10}],
            'condition_fractions': {'damage against enemies': 1,
                                    'aerial hit for extra component': 0}})
        opts = {'duration_seconds': 1, 'published_item_core_opt_in': True,
                'core_effect_text': 'Weapon DMG +9%',
                'enemy_damage_bucket_model': 'independent_multiplicative',
                'proc': {'packet_id': 'weapon:mps7-outer-space/celestial_lightning',
                         'count': 1, 'psi': 100, 'damage_class': 'status'}}
        unknown = timed.evaluate(build, opts)
        self.assertEqual(unknown['status'], 'partial_timed_total')
        self.assert_native_scope_partial(unknown)
        scoped = timed.evaluate(build, {**opts, 'enemy_packet_target_model': 'all_enemies'})
        self.assert_native_scope_partial(scoped)
        self.assertAlmostEqual(scoped['source_proc']['damage'],
                               unknown['source_proc']['damage'])
        self.assertFalse(scoped['game_winner_established'])

    def test_magazine_empty_crit_stacks_have_post_shot_activation(self):
        identity = 'mod:pants_mod:critical-surge-aero'
        text = core.PUBLIC[identity]['effect_text_variants_unranked'][0]
        build = selected(identity, fractions={'damage against enemies': 0,
            'aerial hit for extra component': 0})
        options = {'duration_seconds': 8, 'published_item_core_opt_in': True,
                   'core_effect_text': text, 'weakspot_share': 0}
        with_rule = timed.evaluate(build, options)
        self.assert_native_scope_partial(with_rule)
        self.assertEqual(with_rule['direct_expected']['dynamic_breakdown'][0]['shots'], 40)
        self.assertEqual(with_rule['direct_expected']['dynamic_breakdown'][1]['shots'], 12)
        self.assertEqual(with_rule['direct_expected']['dynamic_breakdown'][1]['bonus_percent'], 3)
        without = timed.evaluate(reference.build({'weapon': {'catalog_id': 'weapon:kam'}}),
                                 {'duration_seconds': 8, 'weakspot_share': 0})
        self.assertGreater(with_rule['known_damage_subtotal'], without['modeled_total_damage'])
        profile = {'normal_damage_per_shot': 100, 'crit_bonus_percent': 50,
                   'weakspot_bonus_percent': 0, 'crit_share': 1,
                   'weakspot_share': 0, 'crit_weakspot_share': 0,
                   'joint_multiplier': 'multiplicative'}
        boundary = timed._timed_direct([0, 1, 12, 13], 2,
            {'kind': 'empty_magazine_independent_crit_stacks', 'pool': 'crit',
             'value_percent': 10, 'duration_seconds': 12, 'max_stacks': 3},
            profile, 14)
        self.assertEqual([(row['bonus_percent'], row['shots'])
                          for row in boundary['dynamic_breakdown']], [(0, 3), (10, 1)])

    def test_three_strikes_only_after_completed_reload(self):
        identity = 'mod:pants_mod:three-strikes-aero'
        text = core.PUBLIC[identity]['effect_text_variants_unranked'][0]
        build = selected(identity, fractions={'damage against enemies': 0,
            'aerial hit for extra component': 0})
        short = timed.evaluate(build, {'duration_seconds': 1,
            'published_item_core_opt_in': True, 'core_effect_text': text,
            'weakspot_share': .2, 'joint_share': 0})
        long = timed.evaluate(build, {'duration_seconds': 8,
            'published_item_core_opt_in': True, 'core_effect_text': text,
            'weakspot_share': .2, 'joint_share': 0})
        self.assertEqual(len(short['direct_expected']['dynamic_breakdown']), 1)
        self.assertEqual(short['direct_expected']['dynamic_breakdown'][0]['bonus_percent'], 0)
        self.assertEqual(short['direct_expected']['dynamic_breakdown'][0]['shots'], 10)
        self.assertAlmostEqual(short['direct_expected']['dynamic_breakdown'][0]['damage'],
                               short['known_damage_subtotal'])
        self.assertEqual(long['direct_expected']['dynamic_breakdown'][1]['shots'], 3)
        self.assertEqual(long['direct_expected']['dynamic_breakdown'][1]['bonus_percent'], 20)
        self.assert_native_scope_partial(long)

    def test_deadshot_uses_explicit_crit_outcomes_and_resets_on_reload(self):
        identity = 'mod:pants_mod:deadshot-aero'
        text = core.PUBLIC[identity]['effect_text_variants_unranked'][0]
        build = selected(identity, fractions={'damage against enemies': 0,
            'aerial hit for extra component': 0})
        base = {'duration_seconds': 8, 'published_item_core_opt_in': True,
                'core_effect_text': text, 'weakspot_share': 0}
        unknown = timed.evaluate(build, base)
        self.assertEqual(unknown['status'], 'partial_timed_total')
        no_crits = timed.evaluate(build, {**base, 'core_crit_hit_indices': []})
        crits = timed.evaluate(build, {**base, 'core_crit_hit_indices': [0, 1, 2, 40]})
        self.assert_native_scope_partial(crits)
        self.assertGreater(crits['known_damage_subtotal'], no_crits['known_damage_subtotal'])
        self.assertEqual(sum(row['shots'] for row in crits['direct_expected']['dynamic_breakdown']),
                         len(crits['shot_times']))
        self.assertEqual(sum(row['shots'] for row in crits['direct_expected']['dynamic_breakdown']
                             if row['crit_outcome']), 4)
        self.assertEqual(sum(row['shots'] for row in crits['direct_expected']['dynamic_breakdown']
                             if row['crit_outcome'] and row['bonus_percent'] == 0), 2)
        with self.assertRaisesRegex(ValueError, 'unique zero-based'):
            timed.evaluate(build, {**base, 'core_crit_hit_indices': [0, 0]})


if __name__ == '__main__':
    unittest.main()
