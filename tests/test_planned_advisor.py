import unittest

import planned_advisor


class PlannedAdvisorTests(unittest.TestCase):
    def test_aug_shock_rampage_one_stack_scenario_is_scoped(self):
        selection={'catalog_id':'weapon:aug-electron-cloud','tier':4,'stars':5,
                   'calibration_profile':{'style':'Vanguard Style'},
                   'weapon_readout':{'source_ref':planned_advisor.OBSERVED_AUG_SOURCE,'attack':213,'rpm':720},
                   'mod_id':'mod:weapon_mod:shock-rampage-power-surge','mod_level':17}
        scenario=planned_advisor.analyze({'primary':selection})['trigger_scenario']
        self.assertEqual((scenario['base_percent'],scenario['one_stack_percent'],scenario['change_percentage_points']),(30,31.5,1.5))
        self.assertNotIn('dps',scenario)
        six={**selection,'stars':6}
        self.assertIn('unobserved',planned_advisor.analyze({'primary':six})['trigger_scenario']['needs'])
        self.assertIn('unsaved what-if',planned_advisor.analyze({'primary':six})['trigger_scenario']['needs'])
        six['weapon_readout']={'base_trigger_chance_percent':24}
        manual=planned_advisor.analyze({'primary':six})['trigger_scenario']
        self.assertEqual((manual['one_stack_percent'],manual['change_percentage_points']),(25.2,1.2))
        self.assertIn('manually entered',manual['base_source'])
        self.assertIsNone(planned_advisor.analyze({'primary':{**selection,'mod_level':16}})['trigger_scenario'])
        self.assertIsNone(planned_advisor.analyze({'primary':{**selection,'mod_id':None}})['trigger_scenario'])

    def test_selected_levels_populate_stats_and_set_threshold_follows_hp(self):
        slots = {
            'primary': {'catalog_id':'weapon:kam-crank','level':10,'tier':3,'stars':2},
            'helmet': {'catalog_id':'armor:treacherous-tides-helmet','level':10,'tier':3,'stars':2},
            'shoes': {'catalog_id':'armor:treacherous-tides-shoes','level':10,'tier':3,'stars':2,
                      'mod_id':'mod:boots_mod:against-all-odds-precision','mod_level':7},
        }
        low = planned_advisor.analyze(slots, {'hp_fraction':0.5,'scenario':'PvE'})
        high = planned_advisor.analyze(slots, {'hp_fraction':0.8,'scenario':'PvE'})
        shoes = next(x for x in low['slots'] if x['slot']=='shoes')
        self.assertEqual(shoes['mod']['attribute_coverage'],'complete')
        self.assertEqual([(x['name'],x['value_percent']) for x in shoes['mod']['attributes']],
                         [('Weakspot DMG',3.6),('Weapon DMG',2.4),('Magazine Capacity',4.8),('All DMG Boost',1.5)])
        tide = next(x for x in low['sets'] if x['name']=='Treacherous Tides')
        self.assertEqual(tide['count'],2)
        threshold = next(x for x in tide['thresholds'] if x['pieces']==2)
        self.assertEqual(threshold['state'],'active')
        self.assertIn('Weapon and Status DMG',threshold['description'])
        self.assertIn('oncehuman.game',threshold['source'])
        self.assertEqual(next(x for x in high['sets'][0]['thresholds'] if x['pieces']==2)['state'],
                         'inactive at stated HP')
        unknown_mode=planned_advisor.analyze(slots,{'hp_fraction':0.5})
        self.assertIn('scenario applicability unresolved',
                      next(x for x in unknown_mode['sets'][0]['thresholds'] if x['pieces']==2)['state'])
        self.assertIn('Burn',low['weapon']['effect_families'])
        self.assertTrue(any('full effect calculation' in x for x in low['unresolved']))

    def test_saved_choice_comparison_reports_effects_components_and_no_full_winner(self):
        base = {'primary':{'catalog_id':'weapon:awm','level':10,'tier':3,'stars':2},
                'shoes':{'catalog_id':'armor:agent-shoes','level':10,'tier':3,'stars':2,
                         'mod_id':'mod:boots_mod:against-all-odds-precision','mod_level':7}}
        changed = {**base,'shoes':{**base['shoes'],
                    'mod_id':'mod:boots_mod:power-of-striving-downstar-deviant-energy','mod_level':9}}
        result = planned_advisor.compare(base,changed,{'conditions':'same elevation; no HP loss; no stamina spent'})
        self.assertEqual([(x['slot'],x['fields']) for x in result['changes']],
                         [('shoes',['mod_id','mod_level'])])
        mod = result['mod_comparisons'][0]['result']
        self.assertTrue(mod['main_effect_changed'])
        self.assertTrue(any(x['name']=='Weapon DMG' and x['meaning']=='direct weapon-hit branch'
                            for x in mod['attribute_changes']))
        self.assertTrue(any(x['name']=='Weakspot DMG' and x['meaning']=='weak-spot branch'
                            for x in mod['attribute_changes']))
        self.assertFalse(result['winner_established'])
        self.assertTrue(result['overall_blockers'])

    def test_saved_primary_family_uses_explicit_capabilities_and_reference_profile(self):
        base={'primary':{'catalog_id':'weapon:sn700'},
              'bottoms':{'catalog_id':'armor:hot-dog-shorts',
                         'mod_id':'mod:pants_mod:distant-strike-survival','mod_level':10}}
        changed={**base,'bottoms':{**base['bottoms'],
                 'mod_id':'mod:pants_mod:elemental-resonance-aero','mod_level':17}}
        inputs={'duration_seconds':40,'distance_meters':25,'crit_share':.02,'weakspot_share':.8,
                'aerial_hit':False,'same_elevation':True,'target_below_within_5m':False,'hp_consumed':False,
                'stamina_spent':False,'nearby_kills':0,'prior_magazine_elemental_events':0,
                'scenario':'PvE'}
        result=planned_advisor.compare(base,changed,{},inputs)
        self.assertFalse(result['winner_established'])
        scoped=result['scoped_outgoing']
        self.assertFalse(scoped['eligible'])
        self.assertFalse(scoped['winner_established'])
        self.assertEqual(scoped['rows'],[])
        self.assertTrue(any('No sourced, explicit-setting weapon reference' in gap
                            for gap in scoped['blockers']))
        burning={**base,'primary':{'catalog_id':'weapon:kam-crank'}}
        burning_changed={**changed,'primary':burning['primary']}
        blocked=planned_advisor.compare(burning,burning_changed,{},inputs)
        self.assertFalse(blocked['scoped_outgoing']['winner_established'])
        self.assertEqual(blocked['left']['weapon']['capabilities']['capabilities']['status_damage'],'present')
        self.assertEqual(blocked['left']['weapon']['capabilities']['capabilities']['triggered_damage'],'absent_in_record')

    def test_armor_swap_exposes_set_threshold_loss(self):
        left={'primary':{'catalog_id':'weapon:awm','level':10},
              'helmet':{'catalog_id':'armor:treacherous-tides-helmet','level':10},
              'shoes':{'catalog_id':'armor:treacherous-tides-shoes','level':10}}
        right={**left,'shoes':{'catalog_id':'armor:agent-shoes','level':10}}
        result=planned_advisor.compare(left,right,{'hp_fraction':0.5,'scenario':'PvE'})
        self.assertEqual(result['changes'][0]['slot'],'shoes')
        lost=next(x for x in result['set_changes'] if x['name']=='Treacherous Tides')
        self.assertEqual((lost['before']['count'],lost['after']['count']),(2,1))
        self.assertEqual(next(t for t in lost['before']['thresholds'] if t['pieces']==2)['state'],'active')
        self.assertEqual(next(t for t in lost['after']['thresholds'] if t['pieces']==2)['state'],'not reached')
        self.assertFalse(result['winner_established'])

    def test_attaching_mod_shows_listed_attributes_without_turning_absence_into_zero(self):
        left={'primary':{'catalog_id':'weapon:awm','level':10},
              'shoes':{'catalog_id':'armor:agent-shoes','level':10}}
        right={**left,'shoes':{**left['shoes'],
               'mod_id':'mod:boots_mod:against-all-odds-precision','mod_level':7}}
        result=planned_advisor.compare(left,right,{})
        self.assertEqual(result['mod_comparisons'],[])
        changes=result['changes'][0]['listed_attribute_changes']
        self.assertEqual(len(changes),4)
        weapon=next(x for x in changes if x['name']=='Weapon DMG')
        self.assertIsNone(weapon['before'])
        self.assertEqual(weapon['after']['value_percent'],2.4)
        self.assertIsNone(weapon['numeric_delta_percent'])
        self.assertFalse(result['winner_established'])

    def test_saved_level_swap_uses_existing_supported_first_hit_rule(self):
        left={'primary':{'catalog_id':'weapon:awm','level':10,
                         'mod_id':'mod:weapon_mod:shock-diffusion-survival','mod_level':10}}
        right={'primary':{**left['primary'],'mod_level':11}}
        result=planned_advisor.compare(left,right,{'incoming_monster_hit':100})
        metric=result['mod_comparisons'][0]['result']['selected_metric']
        self.assertIsNone(metric)  # Lv11 exact rank has no source-backed value
        self.assertFalse(result['winner_established'])


if __name__=='__main__':unittest.main()
