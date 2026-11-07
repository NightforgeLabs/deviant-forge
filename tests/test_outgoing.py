import unittest
import outgoing
import catalog


class OutgoingCatalogExampleTests(unittest.TestCase):
    def test_real_boot_swap_burst_and_sustained_independent_arithmetic(self):
        result=outgoing.run_example()
        self.assertTrue(result['winner_established'])
        self.assertEqual((result['winner'],result['burst_winner']),('left','left'))
        self.assertEqual(result['numeric_coverage'],{'left':'complete','right':'complete'})
        for identity,level in (('mod:boots_mod:against-all-odds-precision',7),('mod:boots_mod:power-of-striving-downstar-deviant-energy',9)):
            verified=catalog.resolve(identity,level)['verified_main_effect']
            self.assertIn('+10%',verified['text'])
            self.assertTrue(verified['source_image'].endswith('.png'))
        row=next(r for r in result['rows'] if r['stacking_model']=='additive' and r['magazine_rounding']=='floor')
        # Joint branch shares are 64/16/16/4%. Against: +10 main,
        # +1.5 all, +2.4 weapon, and +3.6 on weak-spot branches.
        against=.64*(100*1.139)+.16*(150*1.139)+.16*(200*1.175)+.04*(300*1.175)
        striving=.64*(100*1.13)+.16*(150*1.13)+.16*(200*1.13)+.04*(300*1.13)
        self.assertAlmostEqual(against,151.932)
        self.assertAlmostEqual(striving,149.16)
        self.assertEqual((row['left']['damage_per_hit'],row['right']['damage_per_hit']),(against,round(striving,6)))
        self.assertEqual((row['left']['burst_damage'],row['right']['burst_damage']),(3038.64,2983.2))
        # 20 shots / 600 RPM = 2 seconds firing, then 2 seconds reload.
        # Ten cycles in 40 seconds give 200 shots per choice with floor rounding.
        self.assertEqual((row['left']['cycle_seconds'],row['left']['shots'],row['right']['shots']),(4.0,200,200))
        self.assertEqual((row['left']['sustained_damage'],row['right']['sustained_damage']),(30386.4,29832.0))
        self.assertEqual((row['left']['proc_damage'],row['right']['status_damage']),(0,0))
        self.assertTrue(all(r['winner']=='left' and r['burst_winner']=='left' for r in result['rows']))
        self.assertEqual(result['selection_origin'],'catalog example; ownership not asserted or saved')

    def test_weakspot_encounter_changes_only_relevant_contribution(self):
        usual=outgoing.run_example()
        body=outgoing.run_example({'target':{'weakspot_share':0}})
        find=lambda d:next(r for r in d['rows'] if r['stacking_model']=='additive' and r['magazine_rounding']=='floor')
        self.assertGreater(find(usual)['left']['effect_contributions']['weakspot_damage']['per_hit_increment'],0)
        self.assertEqual(find(body)['left']['effect_contributions']['weakspot_damage']['per_hit_increment'],0)
        self.assertEqual(find(body)['left']['burst_damage'],2505.8)
        self.assertTrue(body['winner_established'])

    def test_material_unresolved_effect_blocks_winner(self):
        for override,needle in (
            ({'target':{'stamina_spent':True}},'stamina'),
            ({'target':{'hp_lost':True}},'HP loss'),
            ({'target':{'same_elevation':False}},'Downstar'),
            ({'weapon':{'status_source':True}},'Proc/status'),
        ):
            with self.subTest(override=override):
                result=outgoing.run_example(override)
                self.assertFalse(result['winner_established'])
                self.assertIsNone(result['winner'])
                self.assertTrue(any(needle.lower() in x.lower() for x in result['blockers']))
                self.assertGreater(len(result['rows']),0)  # sensitivity is shown without a rank claim
        self.assertLess(outgoing.run_example()['unmodeled_power_bonus_to_reverse_percent'],1)


if __name__=='__main__':unittest.main()
