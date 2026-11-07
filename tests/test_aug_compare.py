import math
import unittest
import aug_compare


class AUGComparisonTests(unittest.TestCase):
    def test_exact_screenshot_blueprint_values_and_no_made_up_total(self):
        e=aug_compare.CALIBRATIONS['energy']['observed_effects']
        r=aug_compare.CALIBRATIONS['rapid']['observed_effects']
        self.assertIn('Weapon DMG +42.4%',e)
        self.assertIn('Elemental DMG +17.5%',e)
        self.assertIn('Weapon DMG +40.9%',r)
        self.assertIn('Crit Rate +14.6%',r)
        result=aug_compare.compare({'energy':{},'rapid':{}})
        self.assertIsNone(result['known_delta_energy_minus_rapid'])
        self.assertIsNone(result['winner'])
        self.assertIsNone(result['energy']['total_dps'])

    def test_sustained_bullet_and_break_even_are_only_paired_components(self):
        # Hypothetical measured hits, not asserted as the user's Tier V values.
        result=aug_compare.compare({
            'common':{'hit_rate':0.8,'crit_rate':0,'weak_rate':0,'crit_weak_fraction':0},
            'energy':{'normal_hit':110,'rpm':720,'magazine':40,'reload_seconds':2},
            'rapid':{'normal_hit':100,'rpm':864,'magazine':40,'reload_seconds':1.8},
        })
        es=40/(40*60/720+2)
        rs=40/(40*60/864+1.8)
        self.assertAlmostEqual(result['energy']['bullet_dps'],0.8*es*110)
        self.assertAlmostEqual(result['rapid']['bullet_dps'],0.8*rs*100)
        self.assertEqual(result['paired_components'],['bullet_dps'])
        self.assertIsNone(result['winner'])
        self.assertIsNone(result['energy']['total_dps'])
        self.assertAlmostEqual(result['known_delta_energy_minus_rapid'],0.8*(es*110-rs*100))

    def test_four_hit_groups_and_full_measured_components(self):
        common={'hit_rate':0.9,'crit_rate':0.3,'weak_rate':0.2,'crit_weak_fraction':0.1}
        base={'normal_hit':100,'crit_hit':150,'weakspot_hit':120,'crit_weak_hit':190,
              'measured_shots_per_second':10,'proc_events_per_second':1,'proc_damage_per_event':50,
              'orb_events_per_second':0.5,'orb_damage_per_event':80}
        result=aug_compare.compare({'common':common,'energy':base,'rapid':base})
        expected=0.6*100+0.2*150+0.1*120+0.1*190
        self.assertAlmostEqual(result['energy']['bullet_dps'],0.9*10*expected)
        self.assertAlmostEqual(result['energy']['total_dps'],0.9*10*expected+50+40)
        self.assertEqual(result['sustained_winner'],'tie')
        self.assertIsNone(result['winner'])

    def test_energy_auto_return_never_fabricated_from_savior_shield(self):
        result=aug_compare.compare({'energy':{'normal_hit':100,'rpm':720,'magazine':40},'rapid':{}})
        self.assertEqual(result['energy']['shots_per_second'],12)
        self.assertIsNone(result['energy']['total_dps'])
        self.assertTrue(any('ammo return' in x for x in result['common_loadout_notes']))

    def test_accepted_energy_returns_are_explicit_and_capped(self):
        base={'normal_hit':100,'rpm':720,'magazine':40,'reload_seconds':2}
        no_return=aug_compare.compare({'energy':base})['energy']['shots_per_second']
        returned=aug_compare.compare({'energy':{**base,'accepted_return_rate':2}})['energy']['shots_per_second']
        expected=(720/60)*40/(40+2*((720/60)-2))
        self.assertGreater(returned,no_return)
        self.assertAlmostEqual(returned,expected)
        with self.assertRaises(ValueError):
            aug_compare.compare({'energy':{**base,'accepted_return_rate':3.4}})

    def test_five_minute_open_field_finite_cycle_and_dodge(self):
        common={'fight_seconds':300,'dodge_fraction':0.2,'hit_rate':0.8,
                'crit_rate':0,'weak_rate':0,'crit_weak_fraction':0}
        base={'normal_hit':100,'rpm':720,'magazine':40,'reload_seconds':2,
              'proc_events_in_fight':0,'proc_damage_per_event':0,
              'orb_events_in_fight':0,'orb_damage_per_event':0}
        d=aug_compare.compare({'common':common,'energy':{**base,'accepted_return_rate':1},'rapid':base})
        self.assertEqual(d['energy']['active_seconds'],240)
        self.assertGreater(d['energy']['shots_in_fight'],d['rapid']['shots_in_fight'])
        self.assertAlmostEqual(d['energy']['fight_average_dps'],d['energy']['fight_total_damage']/300)
        self.assertEqual(d['winner'],'energy')
        self.assertEqual(d['paired_fight_components'],['bullet_damage_in_fight','power_surge_damage_in_fight','orb_damage_in_fight'])

    def test_measured_full_fight_shots_override_uniform_return_model(self):
        common={'fight_seconds':300,'hit_rate':0.75,'crit_rate':0,'weak_rate':0,'crit_weak_fraction':0}
        energy={'normal_hit':100,'measured_shots_in_fight':1200,
                'proc_events_in_fight':0,'orb_events_in_fight':0}
        d=aug_compare.compare({'common':common,'energy':energy,'rapid':energy})
        self.assertEqual(d['energy']['shots_in_fight'],1200)
        self.assertEqual(d['energy']['fight_total_damage'],90000)
        self.assertEqual(d['energy']['fight_average_dps'],300)
        self.assertEqual(d['winner'],'tie')

    def test_modeled_ratio_is_marked_hypothetical_and_uses_screenshot_values(self):
        d=aug_compare.compare({'common':{},'energy':{},'rapid':{}})
        ratio=(1.10*1.424)/(.90*1.409*1.20)
        self.assertAlmostEqual(d['illustrative_model']['energy_to_rapid_bullet_stream_ratio'],ratio)
        self.assertAlmostEqual(d['illustrative_model']['rapid_sustained_shot_rate_ratio_needed_to_tie_bullet'],ratio*1.20)
        self.assertIn('Illustrative only',d['illustrative_model']['assumptions'][0])
        self.assertIsNone(d['winner'])

    def test_unknown_is_not_zero_and_energy_requires_return_evidence(self):
        empty=aug_compare.compare({'energy':{},'rapid':{}})
        self.assertIsNone(empty['energy']['known_component_sum'])
        self.assertIsNone(empty['energy']['known_fight_damage'])
        common={'fight_seconds':300,'dodge_fraction':0,'hit_rate':1,
                'crit_rate':0,'weak_rate':0,'crit_weak_fraction':0}
        measured={'normal_hit':100,'rpm':720,'magazine':40,'reload_seconds':2,
                  'proc_events_in_fight':0,'orb_events_in_fight':0}
        unknown=aug_compare.compare({'common':common,'energy':measured,'rapid':measured})
        self.assertFalse(unknown['energy']['fight_complete'])
        self.assertIsNone(unknown['winner'])
        zero=aug_compare.compare({'common':common,'energy':{**measured,'accepted_return_rate':0},'rapid':measured})
        self.assertTrue(zero['energy']['fight_complete'])
        self.assertEqual(zero['winner'],'tie')

    def test_finite_cycle_does_not_charge_trailing_reload(self):
        self.assertAlmostEqual(aug_compare.finite_shots(10,60,10,4),10)
        self.assertAlmostEqual(aug_compare.finite_shots(11,60,10,4),10)
        self.assertAlmostEqual(aug_compare.finite_shots(14,60,10,4),10)
        self.assertAlmostEqual(aug_compare.finite_shots(15,60,10,4),11)

    def test_return_rate_below_firing_rate_even_with_measured_override(self):
        with self.assertRaises(ValueError):
            aug_compare.compare({'energy':{'rpm':60,'measured_shots_per_second':1,
                                            'accepted_return_rate':1}})

    def test_calibration_algebra_does_not_change_empirical_damage(self):
        common={'fight_seconds':300,'dodge_fraction':0,'hit_rate':1,
                'crit_rate':0,'weak_rate':0,'crit_weak_fraction':0}
        values={'normal_hit':100,'rpm':720,'magazine':40,'reload_seconds':2,
                'proc_events_in_fight':0,'orb_events_in_fight':0}
        a=aug_compare.compare({'common':common,'energy':{**values,'accepted_return_rate':0},'rapid':values})
        b=aug_compare.compare({'common':{**common,'other_weapon_damage_percent':100,
                                         'base_crit_rate':.2,'crit_damage_bonus_percent':50},
                               'energy':{**values,'accepted_return_rate':0},'rapid':values})
        self.assertNotEqual(a['illustrative_model']['energy_to_rapid_bullet_stream_ratio'],
                            b['illustrative_model']['energy_to_rapid_bullet_stream_ratio'])
        self.assertEqual(a['energy']['fight_total_damage'],b['energy']['fight_total_damage'])
        self.assertEqual(a['rapid']['fight_total_damage'],b['rapid']['fight_total_damage'])

    def test_inconsistent_or_missing_hit_groups_rejected(self):
        with self.assertRaises(ValueError):
            aug_compare.compare({'common':{'crit_rate':0.7,'weak_rate':0.7,'crit_weak_fraction':0.1}})
        incomplete=aug_compare.compare({'common':{'crit_rate':0.2,'weak_rate':0.1,'crit_weak_fraction':0},
                                        'energy':{'normal_hit':100,'rpm':720,'crit_hit':150}})
        self.assertIsNone(incomplete['energy']['bullet_dps'])
        self.assertIsNone(incomplete['energy']['total_dps'])


if __name__=='__main__':unittest.main()
