"""An already-buffed snapshot is useful for body-shot replay, never full DPS."""
import copy
import unittest

import build_timed_readout
import structured_compare

WEAPON = 'weapon:kam-crank'
MOD = 'mod:gloves_mod:elemental-overload-resonance'
SLOTS = {'primary': {'catalog_id': WEAPON, 'tier': 5, 'stars': 5},
         'gloves': {'catalog_id': 'armor:gilded-gauntlets', 'mod_id': MOD,
                    'mod_level': 9}}
PACKET = {'assume_direct_body_damage_per_projectile': True,
          'baseline_bonus_scope': 'after_selected_effects_direct_only',
          'included_effect_ids': [WEAPON, 'armor:gilded-gauntlets', MOD],
          'direct_body_damage_per_projectile': 100, 'projectiles_per_shot': 1,
          'rpm': 600, 'magazine_capacity': 2, 'reload_seconds': 1}
REFERENCE = {'tier': 5, 'stars': 5, 'caller_packet_scenario': PACKET}
TIMED = {'duration_seconds': .6}


class AlreadyBuffedReplayTests(unittest.TestCase):
    def test_direct_replay_does_not_reapply_mod_or_claim_total(self):
        saved = copy.deepcopy(SLOTS)
        run = build_timed_readout.evaluate(SLOTS, REFERENCE, TIMED)
        self.assertEqual(SLOTS, saved)
        self.assertEqual('partial_timed_total', run['status'])
        self.assertEqual(2, len(run['model']['shot_times']))
        self.assertEqual(200, run['model']['known_damage_subtotal'])
        self.assertEqual(100, run['source_baseline']['stats']['damage_per_projectile'])
        self.assertEqual({}, run['model']['effective_pools_percent'])
        self.assertIsNone(run['model']['modeled_total_damage'])
        self.assertIsNone(run['model']['conditional_damage_per_second'])
        self.assertFalse(run['model']['game_winner_established'])
        self.assertIn('body shots only', run['model']['unresolved'][0])
        self.assertEqual(PACKET['included_effect_ids'], run['model']['included_effect_ids'])
        self.assertEqual(100, run['source_baseline']['stats']['damage_per_projectile'])

    def test_compare_cannot_declare_direct_or_timed_winner(self):
        plan = {'id': 'entered', 'name': 'Entered snapshot', 'slots': SLOTS}
        side = {'weapon_id': WEAPON, **REFERENCE}
        output = structured_compare.compare({
            'left': {'kind': 'planned_build', 'planned_build_id': 'entered'},
            'right': {'kind': 'planned_build', 'planned_build_id': 'entered'},
            'context': {'published_reference': {'enabled': True,
                'left': side, 'right': side,
                'timed': {'duration_seconds': .6, 'shared_target_confirmed': True,
                          'left': {}, 'right': {}}}}}, [plan])['published_reference']
        self.assertFalse(output['direct_reference_complete']['left'])
        self.assertEqual('partial_or_unmatched', output['timed_comparison']['status'])
        self.assertIsNone(output['timed_comparison']['right_over_left_damage_per_second'])
        self.assertFalse(output['game_winner_established'])

    def test_ids_are_explicit_and_must_match_selected_items(self):
        bad = {**PACKET, 'included_effect_ids': [WEAPON, 'mod:helmet_mod:unknown']}
        with self.assertRaisesRegex(ValueError, 'must match selected'):
            build_timed_readout.evaluate(SLOTS, {**REFERENCE, 'caller_packet_scenario': bad}, TIMED)
        for included in (None, [], [WEAPON, WEAPON]):
            bad = {**PACKET, 'included_effect_ids': included}
            with self.assertRaisesRegex(ValueError, 'nonempty unique list'):
                build_timed_readout.evaluate(SLOTS, {**REFERENCE, 'caller_packet_scenario': bad}, TIMED)
        bad = {**PACKET, 'baseline_bonus_scope': 'before_selected_effects'}
        with self.assertRaisesRegex(ValueError, 'cannot declare already-included'):
            build_timed_readout.evaluate(SLOTS, {**REFERENCE, 'caller_packet_scenario': bad}, TIMED)
        bad = {**PACKET, 'baseline_bonus_scope': 'ambiguous'}
        with self.assertRaisesRegex(ValueError, 'double count'):
            build_timed_readout.evaluate(SLOTS, {**REFERENCE, 'caller_packet_scenario': bad}, TIMED)

    def test_pre_effect_model_and_post_effect_snapshot_are_distinct(self):
        pre = {**PACKET, 'baseline_bonus_scope': 'before_selected_effects'}
        pre.pop('included_effect_ids')
        pre_run = build_timed_readout.evaluate(SLOTS, {**REFERENCE,
            'caller_packet_scenario': pre}, {'duration_seconds': .6,
            'crit_share': 0, 'weakspot_share': 0, 'joint_share': 0,
            'exclude_unbound_weapon_effect': True})
        post_run = build_timed_readout.evaluate(SLOTS, REFERENCE, TIMED)
        self.assertNotEqual(pre_run['model']['effective_pools_percent'],
                            post_run['model']['effective_pools_percent'])
        self.assertEqual(200, post_run['model']['known_damage_subtotal'])


if __name__ == '__main__':
    unittest.main()
