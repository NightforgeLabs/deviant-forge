from tests.explicit_reference_fixture import explicit_synthetic_reference
"""Main-effect item ranks and exact Field Guide levels stay separate."""
import math
import unittest

import published_main_core
import published_reference_model
import published_timed_combat
import structured_compare


def build(identity=None, level=None, shiny=False):
    request = {'weapon': {'catalog_id': 'weapon:kam'}}
    if identity:
        request['mods'] = [{'catalog_id': identity, 'level': level, 'shiny': shiny}]
    return published_reference_model.build(request)


@explicit_synthetic_reference
class PublishedMainCoreTests(unittest.TestCase):
    def test_exact_against_all_odds_base_once_and_hp_events_gate_total(self):
        base = published_timed_combat.evaluate(build(), {'duration_seconds': 1})
        selected = build(published_main_core.AGAINST, 7)
        partial = published_timed_combat.evaluate(selected, {'duration_seconds': 1})
        self.assertEqual(partial['effective_pools_percent']['weapon'], 12.4)
        self.assertEqual(partial['effective_pools_percent']['status'], 10)
        self.assertIsNone(partial['modeled_total_damage'])
        resolved = published_timed_combat.evaluate(selected, {
            'duration_seconds': 1, 'core_no_hp_cost_events': True})
        self.assertEqual(resolved['status'], 'conditional_modeled_total')
        self.assertGreater(resolved['known_damage_subtotal'], base['known_damage_subtotal'])
        self.assertEqual(len([x for x in resolved['typed_core_pools_applied']
                              if x.get('catalog_id') == published_main_core.AGAINST]), 1)
        other_level = published_timed_combat.evaluate(
            build(published_main_core.AGAINST, 8), {'duration_seconds': 1,
                                                     'core_no_hp_cost_events': True})
        self.assertTrue(any('main mod effect is not connected' in gap
                            for gap in other_level['unresolved']))

    def test_bullet_siphon_counter_uses_previous_bullets_and_resets_on_reload(self):
        counter = published_main_core.resolve(
            [{'catalog_id': published_main_core.BULLET, 'level': 12}], {})['bullet_counter']
        self.assertEqual(published_main_core.bullet_average_bonus(
            [{'kind': 'shot'}] * 10, counter), 2)
        self.assertEqual(published_main_core.bullet_average_bonus(
            [{'kind': 'shot'}] * 5 + [{'kind': 'reload'}] +
             [{'kind': 'shot'}] * 5, counter), 0)
        self.assertEqual(published_main_core.bullet_average_bonus(
            [{'kind': 'shot'}] * 30, counter),
            sum(min(20, (i // 5) * 4) for i in range(30)) / 30)
        missing_aerial = published_timed_combat.evaluate(
            build(published_main_core.BULLET, 12), {'duration_seconds': 1})
        self.assertEqual('partial_timed_total', missing_aerial['status'])
        self.assertTrue(any('aerial hit fraction' in gap for gap in missing_aerial['unresolved']))
        source = published_reference_model.build({
            'weapon': {'catalog_id': 'weapon:kam'},
            'mods': [{'catalog_id': published_main_core.BULLET, 'level': 12}],
            'condition_fractions': {'aerial hit': 0}})
        selected = published_timed_combat.evaluate(source, {'duration_seconds': 1})
        self.assertEqual(selected['effective_pools_percent']['weapon'], 5)
        self.assertEqual(selected['bullet_counter_average_percent'], 2)
        self.assertEqual(selected['status'], 'conditional_modeled_total')
        self.assertEqual([row['name'] for row in selected['utility_bonus_lines']], ['Max HP'])
        self.assertFalse(any('Max HP' in gap for gap in selected['unresolved']))

    def test_community_fortune_rank_is_opt_in_and_not_field_guide_level(self):
        identity = 'mod:helmet_mod:fortune-s-favor-general'
        selected = build(identity, 12)
        off = published_timed_combat.evaluate(selected, {'duration_seconds': 1})
        on = published_timed_combat.evaluate(selected, {
            'duration_seconds': 1, 'published_item_core_opt_in': True,
            'weakspot_share': .25, 'joint_share': .05})
        self.assertEqual(off['effective_pools_percent']['crit'], 0)
        self.assertEqual(on['effective_pools_percent']['crit'], 30)
        self.assertGreater(on['known_damage_subtotal'], off['known_damage_subtotal'])
        self.assertEqual(on['direct_expected']['components']['weakspot'], 0)
        self.assertEqual(on['direct_expected']['components']['crit_weakspot'], 0)
        applied = on['typed_core_pools_applied'][0]
        self.assertEqual(applied['field_guide_level'], 12)
        self.assertEqual(applied['source_item_effect_level'], 5)
        self.assertEqual(applied['source_item_id'], '19500042')
        self.assertIsNone(on['modeled_total_damage'])  # Other suffix lines still unresolved
        shiny = published_timed_combat.evaluate(build(identity, 17, shiny=True), {
            'duration_seconds': 1, 'published_item_core_opt_in': True})
        self.assertEqual(shiny['effective_pools_percent']['crit'], 0)

    def test_structured_selected_mod_scenario_passes_core_controls(self):
        identity = published_main_core.AGAINST
        request = {'left': {'kind': 'catalog', 'catalog_id': identity, 'level': 7},
                   'right': {'kind': 'catalog', 'catalog_id': identity, 'level': 7},
                   'context': {'published_reference': {'enabled': True,
                       'left': {'weapon_id': 'weapon:kam'},
                       'right': {'weapon_id': 'weapon:kam'},
                       'timed': {'duration_seconds': 1, 'shared_target_confirmed': True,
                                 'left': {'core_no_hp_cost_events': True},
                                 'right': {'core_no_hp_cost_events': True}}}}}
        result = structured_compare.compare(request, [])['published_reference']
        self.assertEqual(result['timed_scenarios']['left']['status'],
                         'conditional_modeled_total')
        self.assertTrue(math.isclose(result['timed_comparison']
                                     ['right_over_left_damage_per_second'], 1))
        self.assertFalse(result['timed_comparison']['game_winner_established'])


if __name__ == '__main__':
    unittest.main()
