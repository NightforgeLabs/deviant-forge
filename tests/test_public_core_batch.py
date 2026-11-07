from tests.explicit_reference_fixture import explicit_synthetic_reference
"""Source-text opt-in batch across static, condition, counter and partial classes."""
import json
from pathlib import Path
import unittest

import published_main_core as core
import published_reference_model
import published_timed_combat
import structured_compare

LEDGER = json.loads((Path(__file__).resolve().parent.parent /
                     'evidence_packets/public-core-operator-ledger-v1.json').read_text())


def run(identity, text, *, level=10, **options):
    build = published_reference_model.build({'weapon': {'catalog_id': 'weapon:kam'},
        'mods': [{'catalog_id': identity, 'level': level}]})
    return published_timed_combat.evaluate(build, {
        'duration_seconds': 1, 'published_item_core_opt_in': True,
        'core_effect_text': text, **options})


@explicit_synthetic_reference
class PublicCoreBatchTests(unittest.TestCase):
    def test_ledger_counts_and_exact_priority(self):
        self.assertEqual(LEDGER['counts']['opt_in_damage_scenario_supported'], 26)
        self.assertEqual(LEDGER['counts']['timed_counter_or_resource_partial'], 24)
        self.assertEqual(LEDGER['counts']['typed_utility_or_melee_partial'], 6)
        self.assertEqual(LEDGER['counts']['display_only_missing_effect_text'], 1)
        self.assertEqual(LEDGER['counts']['shiny_only_isolated'], 7)
        exact = core.resolve([{'catalog_id': core.BULLET, 'level': 12}], {
            'published_item_core_opt_in': True,
            'core_effect_text': 'Every 5 bullets consumed in the magazine grants +4% Weapon DMG, capped at 20%.'})
        self.assertEqual(exact['applied'][0]['source'], 'exact_current_field_guide_frame')
        self.assertEqual(exact['pools']['weapon'], 5)

    def test_static_crit_elemental_status_weakspot_and_weapon_families(self):
        cases = [
            ('mod:gloves_mod:crit-amplifier-aero', 'Crit Rate +10%, Crit DMG +15%.', 'crit', 15),
            ('mod:gloves_mod:crit-boost-aero-deviant-energy', 'Crit Rate +15%', None, 15),
            ('mod:gloves_mod:elemental-overload-aero', 'Element DMG (Blaze, Frost, Shock, Blast) +18%.', 'elemental', 18),
            ('mod:gloves_mod:status-enhancement-aero', 'Status DMG +20%', 'status', 20),
            ('mod:gloves_mod:weakspot-dmg-boost-aero', 'Weakspot DMG +10%', 'weakspot', 10),
            ('mod:gloves_mod:weapon-amplifier-aero', 'Weapon DMG +9%', 'weapon', 9),
        ]
        for identity, text, pool, value in cases:
            with self.subTest(identity=identity):
                result = run(identity, text, weakspot_share=.2, joint_share=0)
                applied = [row for row in result['typed_core_pools_applied']
                           if row.get('catalog_id') == identity]
                self.assertEqual(len(applied), 1)
                self.assertEqual(applied[0]['source_item_effect_level'], None)
                self.assertEqual(applied[0]['effect_text'], text)
                if pool:
                    self.assertEqual(applied[0]['static_pools_percent'][pool], value)
                else:
                    self.assertEqual(applied[0]['crit_rate_percentage_points'], value)
        plain = published_timed_combat.evaluate(
            published_reference_model.build({'weapon': {'catalog_id': 'weapon:kam'}}),
            {'duration_seconds': 1})
        weapon = run('mod:gloves_mod:weapon-amplifier-aero', 'Weapon DMG +9%')
        self.assertGreater(weapon['known_damage_subtotal'], plain['known_damage_subtotal'])

    def test_conditions_and_distance_are_explicit(self):
        identity = 'mod:boots_mod:secluded-strike-mirror'
        text = 'Having no enemies within 7 meters around you grants +15% Weapon and Status DMG.'
        unknown = run(identity, text)
        self.assertIsNone(unknown['modeled_total_damage'])
        self.assertTrue(any('named core condition' in gap for gap in unknown['unresolved']))
        active = run(identity, text, core_condition_active=True)
        inactive = run(identity, text, core_condition_active=False)
        self.assertEqual(active['effective_pools_percent']['weapon'] -
                         inactive['effective_pools_percent']['weapon'], 15)
        marked = run('mod:mask_mod:targeted-strike-the-bull-s-eye',
            'When hitting marked enemies, Crit Rate +4%, and Crit DMG +10%.',
            core_condition_active=True)
        self.assertEqual(marked['effective_pools_percent']['crit'], 10)
        distance_id = 'mod:pants_mod:distant-strike-aero'
        distance_text = ('Weakspot DMG +20% when a bullet hits a target more than 20 meters away. '
                         'For every additional 1 meter(s) away from the target, Weakspot DMG +1%, up to +20%.')
        close = run(distance_id, distance_text, core_target_distance_meters=20,
                    weakspot_share=.3, joint_share=0)
        far = run(distance_id, distance_text, core_target_distance_meters=25,
                  weakspot_share=.3, joint_share=0)
        self.assertEqual(far['effective_pools_percent']['weakspot'] -
                         close['effective_pools_percent']['weakspot'], 25)
        self.assertGreater(far['known_damage_subtotal'], close['known_damage_subtotal'])

    def test_counter_partial_utility_and_identity_guards(self):
        bullet = run('mod:pants_mod:bullet-siphon-aero',
            'Weapon DMG +5%. Every 5 bullets consumed in the magazine grants +4% Weapon DMG, capped at 20%.')
        self.assertEqual(bullet['typed_core_pools_applied'][0]
                         ['static_pools_percent']['weapon'], 5)
        self.assertEqual(bullet['bullet_counter_average_percent'], 2)
        utility = run('mod:gloves_mod:lifeforce-boost-aero', 'HP +8%')
        self.assertTrue(any('HP utility' in gap for gap in utility['unresolved']))
        timed = run('mod:pants_mod:abnormal-increase-aero',
            'When the magazine is empty, Status DMG +10% for 12s. Effect can stack up to 3 times.')
        self.assertEqual(timed['typed_core_pools_applied'][0]['operator'],
                         'empty_magazine_status_stacks')
        self.assertIsNone(timed['modeled_total_damage'])  # Target-specific suffix remains unresolved.
        with self.assertRaisesRegex(ValueError, 'not a held source variant'):
            run('mod:gloves_mod:weapon-amplifier-aero', 'Weapon DMG +999%')
        with self.assertRaisesRegex(ValueError, 'no ordinary source item'):
            core.resolve([{'catalog_id': 'mod:boots_mod:slow-and-steady-violent',
                           'level': 10}], {'published_item_core_opt_in': True,
                                          'core_effect_text': 'Weapon DMG +10%'})

    def test_structured_selection_changes_named_core_component(self):
        identity = 'mod:gloves_mod:weapon-amplifier-aero'
        request = {'left': {'kind': 'catalog', 'catalog_id': identity, 'level': 10},
                   'right': {'kind': 'catalog', 'catalog_id': identity, 'level': 10},
                   'context': {'core_candidate_opt_in': True,
                       'published_reference': {'enabled': True,
                           'left': {'weapon_id': 'weapon:kam'},
                           'right': {'weapon_id': 'weapon:kam'},
                           'timed': {'duration_seconds': 1, 'shared_target_confirmed': True,
                                     'left': {'core_effect_text': 'Weapon DMG +3%'},
                                     'right': {'core_effect_text': 'Weapon DMG +9%'}}}}}
        result = structured_compare.compare(request, [])['published_reference']
        left = result['timed_scenarios']['left']
        right = result['timed_scenarios']['right']
        self.assertEqual(right['effective_pools_percent']['weapon'] -
                         left['effective_pools_percent']['weapon'], 6)
        self.assertGreater(right['known_damage_subtotal'], left['known_damage_subtotal'])
        self.assertFalse(result['timed_comparison']['game_winner_established'])


if __name__ == '__main__':
    unittest.main()
