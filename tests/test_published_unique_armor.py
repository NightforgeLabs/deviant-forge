from tests.explicit_reference_fixture import explicit_synthetic_reference
"""Current-release unique armor is packet-scoped and never claims full ammo timing."""
import unittest

import published_reference_model as reference
import published_timed_combat as combat
import published_unique_armor as armor


@explicit_synthetic_reference
class PublishedUniqueArmorTests(unittest.TestCase):
    def test_wind_bonus_only_on_sourced_bomber_packets(self):
        build = {'armor_profiles': [{'catalog_id': armor.WIND}]}
        source = [{'event_id': 'blast', 'source_packet_id':
                   'weapon:g17-hazardous-object/thrown_reload_blast'},
                  {'event_id': 'shock', 'source_packet_id':
                   'weapon:critical-pulse/lightning_orb_tick'}]
        packets = [{'event_id': 'blast', 'damage': 200,
                    'applied_pools_percent': {'unstable_bomber': 25}},
                   {'event_id': 'shock', 'damage': 100},
                   {'event_id': 'direct', 'damage': 300}]
        result = armor.wind_intepreter(build, 'pve_non_raidzone', source, packets)
        self.assertEqual(result['known_bonus_damage'], 40)
        self.assertEqual(len(result['applied']), 1)
        self.assertEqual(result['applied'][0]['event_id'], 'blast')
        self.assertTrue(any('bullet source and retention' in gap for gap in result['unresolved']))
        self.assertEqual(armor.wind_intepreter(build, 'raidzone', source, packets)['known_bonus_damage'], 0)
        self.assertEqual(armor.wind_intepreter({'armor_profiles': []},
                         'pve_non_raidzone', source, packets)['known_bonus_damage'], 0)
        unknown = armor.wind_intepreter(build, 'unknown', source, packets)
        self.assertEqual(unknown['known_bonus_damage'], 0)
        self.assertTrue(any('non-RaidZone' in gap for gap in unknown['unresolved']))

    def test_selected_cap_changes_sourced_blast_subtotal_but_not_complete_verdict(self):
        plain = reference.build({'weapon': {'catalog_id': 'weapon:g17-hazardous-object'}})
        equipped = reference.build({'weapon': {'catalog_id': 'weapon:g17-hazardous-object'},
                                    'armor': [{'catalog_id': armor.WIND}]})
        controls = {'duration_seconds': 3, 'scenario_mode': 'pve_non_raidzone',
            'source_timeline': {'reserve_bullets': 0, 'target_id': 'dummy',
                'reload_after_shots': 1, 'roll_sequence': [.99],
                'damage_model': {'basis_values': {'psi': 100},
                    'packet_models': {'thrown_reload_blast': {
                        'damage_class': 'weapon', 'target_count': 2}}}}}
        base = combat.evaluate(plain, controls)
        cap = combat.evaluate(equipped, controls)
        self.assertAlmostEqual(cap['known_damage_subtotal'] - base['known_damage_subtotal'], 133)
        self.assertEqual(cap['unique_armor']['known_bonus_damage'], 133)
        self.assertEqual(cap['source_timeline']['final_ammo'], base['source_timeline']['final_ammo'])
        self.assertEqual(cap['status'], 'partial_timed_total')
        self.assertIsNone(cap['modeled_total_damage'])
        self.assertTrue(any('bullet source and retention' in gap for gap in cap['unresolved']))
        self.assertEqual(base['status'], 'conditional_modeled_total')


if __name__ == '__main__':
    unittest.main()
