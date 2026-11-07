"""Unknown imported damage basis cannot become a plausible but false tier result."""
import unittest

import published_calculator_adapter as adapter
import published_reference_model as reference
import published_timed_combat as combat


class ProgressionQuarantineTests(unittest.TestCase):
    def test_unanchored_import_removed_from_active_numeric_source(self):
        with self.assertRaises(LookupError):
            adapter.load_published_weapon_baseline(adapter.PACKETS,'weapon:kam-crank')
        import json
        packet=json.loads((adapter.PACKETS/'weapon-baselines-published.json').read_text())
        self.assertEqual(packet['weapons'], {})
        self.assertEqual(packet['removed_count'],131)

    def test_reference_and_timed_totals_withheld_including_default(self):
        for tier in (1,4):
            with self.subTest(tier=tier):
                build=reference.build({'weapon':{'catalog_id':'weapon:kam-crank','tier':tier}})
                self.assertIsNone(build['direct_only']['reference_hit'])
                self.assertIsNone(build['direct_only']['firing_damage_per_second'])
                self.assertTrue(any('archived unanchored calculator values' in gap for gap in build['unresolved']))
                timed=combat.evaluate(build,{'duration_seconds':1})
                self.assertEqual(timed['status'],'partial_timed_total')
                self.assertIsNone(timed['modeled_total_damage'])
        pair=reference.compare({'left':{'weapon':{'catalog_id':'weapon:kam'}},
                                'right':{'weapon':{'catalog_id':'weapon:kam-crank','tier':4}}})
        self.assertTrue(all(value is None for value in pair['right_over_left_reference_ratios'].values()))
        hazardous=reference.build({'weapon':{'catalog_id':'weapon:g17-hazardous-object'}})
        partial=combat.evaluate(hazardous,{'duration_seconds':3,
            'source_timeline':{'reserve_bullets':0,'target_id':'dummy',
                'reload_after_shots':1,'roll_sequence':[.99],
                'damage_model':{'basis_values':{'psi':100},
                    'packet_models':{'thrown_reload_blast':{'damage_class':'weapon','target_count':2}}}}})
        self.assertEqual(partial['status'],'partial_timed_total')
        self.assertIsNone(partial['modeled_total_damage'])


if __name__=='__main__':unittest.main()
