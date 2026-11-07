import unittest
import mod_rolls, aug_compare

ROWS=['Element (Blaze, Frost, Shock, Blast) DMG + 3.2%','Status DMG + 2.4%',
      'Magazine Capacity + 4.8%','Increases damage dealt to all DMG Boost by + 3.0%']
AUDIT={'status':'source_text_and_numbers_checked','attribute_rows':[{'source_text':x} for x in ROWS]}
BASE={'base_origin':'pre_mod_unbuffed','base_direct_hit':241,'rpm':720,'magazine':40,'tech_policy':'assume_active',
      'all_damage_model':'independent_outgoing_multiplier'}

class ModRollTests(unittest.TestCase):
 def rows(self):return mod_rolls.parse_rows(ROWS,proposal_id='review-only',source={'timestamp':236},source_audit=AUDIT)
 def test_four_independent_values_and_evidence(self):
  got=self.rows()
  self.assertEqual([x['stat_type'] for x in got],['elemental_damage_percent','status_damage_percent','magazine_capacity_percent','all_damage_boost_percent'])
  self.assertEqual([x['value'] for x in got],[3.2,2.4,4.8,3.0])
  self.assertTrue(all(x['confidence']=='source_checked' and x['evidence']['timestamp']==236 for x in got))
 def test_unknown_tech_activation_requires_explicit_scenario(self):
  rows=self.rows()
  self.assertTrue(all(row['tech_activation']=='unknown' for row in rows))
  default=mod_rolls.aggregate(rows,all_damage_model='independent_outgoing_multiplier')
  self.assertEqual(len(default['used_rows']),0)
  self.assertEqual(len(default['tech_gated_rows']),4)
  self.assertEqual(mod_rolls.scenario(rows,{k:v for k,v in BASE.items() if k!='tech_policy'})['component_results']['direct_hit'],241)
  assumed=mod_rolls.aggregate(rows,tech_policy='assume_active',all_damage_model='independent_outgoing_multiplier')
  self.assertEqual(len(assumed['used_rows']),4)
  inactive={**rows[0],'tech_activation':'verified_inactive'}
  self.assertEqual(len(mod_rolls.aggregate([inactive],tech_policy='assume_active')['used_rows']),0)
 def test_each_independent_component(self):
  rows=self.rows();base=mod_rolls.scenario([],BASE)['component_results']
  e=mod_rolls.scenario([rows[0]],BASE)['component_results'];self.assertAlmostEqual(e['event_streams']['elemental']['factor'],1.032);self.assertEqual(e['direct_hit'],base['direct_hit'])
  s=mod_rolls.scenario([rows[1]],BASE)['component_results'];self.assertAlmostEqual(s['event_streams']['status']['factor'],1.024);self.assertEqual(s['direct_hit'],base['direct_hit'])
  m=mod_rolls.scenario([rows[2]],BASE)['component_results'];self.assertAlmostEqual(m['magazine_unrounded'],41.92);self.assertEqual(m['magazine_bounds'],{'floor':41,'ceil':42});self.assertEqual(m['direct_hit'],base['direct_hit'])
  a=mod_rolls.scenario([rows[3]],BASE)['component_results'];self.assertAlmostEqual(a['direct_hit'],248.23);self.assertEqual(a['magazine_bounds'],base['magazine_bounds'])
 def test_combined_and_unknown_sustained(self):
  r=mod_rolls.scenario(self.rows(),BASE)['component_results']
  self.assertAlmostEqual(r['direct_firing_dps'],2978.76);self.assertAlmostEqual(r['event_streams']['elemental']['factor'],1.03*1.032);self.assertAlmostEqual(r['event_streams']['status']['factor'],1.03*1.024)
  self.assertIsNone(r['sustained_direct_bounds']);self.assertIsNone(r['event_streams']['elemental']['dps'])
  with_reload=mod_rolls.scenario(self.rows(),{**BASE,'reload_seconds':2})['component_results']
  self.assertLess(with_reload['sustained_direct_bounds']['floor']['direct_dps'],with_reload['sustained_direct_bounds']['ceil']['direct_dps'])
 def test_source_checked_reload_efficiency_changes_only_reload_cycle(self):
  text='Reload Efficiency + 3.6%'
  row=mod_rolls.parse_rows([text],proposal_id='synthetic-reviewed-row',
       source_audit={'status':'source_text_and_numbers_checked','attribute_rows':[{'source_text':text}]})[0]
  self.assertEqual(row['stat_type'],'reload_efficiency_percent')
  self.assertEqual(row['calculation_status'],'assumption_scenario')
  inputs={**BASE,'reload_seconds':2}
  base=mod_rolls.scenario([],inputs)['component_results']
  gated=mod_rolls.scenario([row],{**inputs,'tech_policy':'exclude_unknown'})
  self.assertEqual(len(gated['modifiers']['tech_gated_rows']),1)
  self.assertEqual(gated['component_results']['reload_seconds_after_efficiency'],2)
  assumed=mod_rolls.scenario([row],inputs)
  result=assumed['component_results']
  self.assertAlmostEqual(result['reload_seconds_after_efficiency'],2/1.036)
  self.assertEqual(result['direct_hit'],base['direct_hit'])
  self.assertEqual(result['direct_firing_dps'],base['direct_firing_dps'])
  expected_rate=12*40/(40+12*(2/1.036))
  self.assertAlmostEqual(result['sustained_direct_bounds']['floor']['shots_per_second'],expected_rate)
  self.assertAlmostEqual(result['sustained_direct_bounds']['floor']['direct_dps'],241*expected_rate)
  self.assertGreater(result['sustained_direct_bounds']['floor']['direct_dps'],base['sustained_direct_bounds']['floor']['direct_dps'])
  self.assertIsNone(result['event_streams']['elemental']['dps'])
  self.assertTrue(any('total damage is withheld' in x for x in assumed['assumptions']))
  sensitivity=aug_compare.mod_calibration_sensitivity([row],{'tech_policy':'assume_active','reference_reload_seconds':2})
  self.assertAlmostEqual(sensitivity['calibrations']['energy']['reference_reload_seconds_assumption'],2/1.036)
  self.assertAlmostEqual(sensitivity['calibrations']['rapid']['reference_reload_seconds_assumption'],2/1.10/1.036)
  self.assertFalse(sensitivity['winner_established'])
  self.assertIsNone(sensitivity['total_dps'])
 def test_ambiguous_survival_and_ocr_are_excluded(self):
  bad=mod_rolls.parse_rows(['Damage from monsters −+ 4.8%'],source_audit={'status':'source_text_and_numbers_checked','attribute_rows':[{'source_text':'Damage from monsters −+ 4.8%'}]})[0]
  self.assertIsNone(bad['value']);self.assertEqual(bad['calculation_status'],'excluded_ambiguous')
  unverified=mod_rolls.parse_rows([ROWS[-1]])[0]
  self.assertEqual(unverified['confidence'],'ocr_unverified');self.assertEqual(unverified['calculation_status'],'unmodeled')
  self.assertEqual(mod_rolls.aggregate([bad,unverified])['percent_by_type']['all_damage_boost_percent'],0)
 def test_all_damage_amount_does_not_prove_independent_bucket(self):
  observed=self.rows()[3]
  self.assertEqual((observed['value'],observed['raw_text']),(3.0,ROWS[-1]))
  default=mod_rolls.scenario([observed],{**BASE,'base_direct_hit':100,'all_damage_model':'exclude_unverified'})
  self.assertEqual(default['component_results']['direct_hit'],100)
  self.assertEqual(default['modifiers']['used_rows'],[])
  self.assertIn('placement among target-category',default['modifiers']['unmodeled_rows'][0]['model_exclusion'])
  self.assertIn('All DMG Boost bucket placement',default['missing'])
  hypothetical=mod_rolls.scenario([observed],{**BASE,'base_direct_hit':100})
  self.assertAlmostEqual(hypothetical['component_results']['direct_hit'],103)
  self.assertEqual(hypothetical['modifiers']['all_damage_model'],'independent_outgoing_multiplier')
  self.assertIn('Hypothetical',hypothetical['modifiers']['stacking_assumption'])
  with self.assertRaisesRegex(ValueError,'Unknown All DMG Boost model'):
   mod_rolls.aggregate([observed],all_damage_model='verified_global')
 def test_short_all_damage_label_keeps_raw_source_and_ambiguity(self):
  short='All DMG Boost +3.0%'
  audited=mod_rolls.parse_rows([short],source_audit={'status':'source_text_and_numbers_checked','attribute_rows':[{'source_text':short}]})[0]
  self.assertEqual((audited['stat_type'],audited['value'],audited['raw_text'],audited['confidence']),
                   ('all_damage_boost_percent',3.0,short,'source_checked'))
  self.assertEqual(mod_rolls.aggregate([audited],tech_policy='assume_active')['used_rows'],[])
  self.assertEqual(mod_rolls.aggregate([audited],tech_policy='assume_active',all_damage_model='independent_outgoing_multiplier')['percent_by_type']['all_damage_boost_percent'],3.0)
  ambiguous=mod_rolls.parse_rows(['All DMG Boost −+3.0%'])[0]
  self.assertEqual(ambiguous['stat_type'],'unparsed')
  self.assertIsNone(ambiguous['value'])
 def test_shock_rampage_core_and_suffix_roll_are_not_merged(self):
  core='Inflicting Power Surge grants + 5.0% Power Surge Trigger Chance (based on weapon\'s Trigger Chance) for 5.0s, up to 4.0 stack(s).'
  suffix='Power Surge Trigger Chance + 6.0%'
  rows=mod_rolls.parse_rows([core,suffix],source_audit={'status':'source_text_and_numbers_checked','attribute_rows':[{'source_text':core},{'source_text':suffix}]})
  self.assertEqual([row['stat_type'] for row in rows],['unparsed','power_surge_trigger_chance_percent'])
  self.assertEqual(rows[1]['calculation_status'],'unmodeled')
  self.assertEqual(mod_rolls.aggregate(rows,tech_policy='assume_active')['used_rows'],[])
 def test_observed_pre_modified_baseline_guard(self):
  result=mod_rolls.scenario(self.rows(),{'base_origin':'observed_equipped','base_direct_hit':241,'rpm':720,'magazine':40})
  self.assertFalse(result['supported']);self.assertIsNone(result['component_results'])
 def test_equipped_build_aggregates_only_exact_owned_instances(self):
  mods=self.rows()
  base={'kind':'mod_unlock','effects':{'catalog_id':'mod:chest_mod:enduring-shield-deviant-energy'},'level':8,
        'stats':{'typed_modifiers':mods}}
  slots={'top':{'mod_id':'mod:chest_mod:enduring-shield-deviant-energy','mod_level':8}}
  resolved=mod_rolls.equipped_build_modifiers(slots,[{**base,'id':'one'}])
  self.assertEqual(len(resolved['modifiers']),4);self.assertEqual(resolved['resolved_slots'],['top'])
  self.assertAlmostEqual(mod_rolls.scenario(resolved['modifiers'],BASE)['component_results']['direct_hit'],248.23)
  ambiguous=mod_rolls.equipped_build_modifiers(slots,[{**base,'id':'one'},{**base,'id':'two'}])
  self.assertEqual(ambiguous['modifiers'],[]);self.assertEqual(ambiguous['unresolved'][0]['matching_instances'],2)
  exact=mod_rolls.equipped_build_modifiers({'top':{**slots['top'],'mod_inventory_id':'two'}},[{**base,'id':'one'},{**base,'id':'two'}])
  self.assertEqual(exact['modifiers'][0]['owned_instance_id'],'two')
  missing=mod_rolls.equipped_build_modifiers(slots,[{**base,'id':'one','stats':{}}])
  self.assertEqual(missing['modifiers'],[]);self.assertIn('no source-checked',missing['unresolved'][0]['reason'])
  self.assertEqual(missing['unresolved'][0]['code'],'owned_roll_evidence_missing')
  self.assertEqual(missing['unresolved'][0]['selected_level'],8)
  self.assertEqual(missing['unresolved'][0]['owned_instance_id'],'one')
  wrong_level=mod_rolls.equipped_build_modifiers(slots,[{**base,'id':'one','level':9}])
  self.assertEqual(wrong_level['unresolved'][0]['code'],'owned_level_mismatch')
  self.assertEqual(wrong_level['unresolved'][0]['available_levels'],[9])
 def test_weapon_damage_roll_changes_direct_hit_and_calibration_preview(self):
  row=mod_rolls.parse_rows(['Weapon DMG + 5%'],source_audit={'status':'source_text_and_numbers_checked','attribute_rows':[{'source_text':'Weapon DMG + 5%'}]})[0]
  before=mod_rolls.scenario([],BASE)['component_results']['direct_hit']
  after=mod_rolls.scenario([row],BASE)['component_results']
  self.assertAlmostEqual(after['direct_hit'],before*1.05)
  self.assertAlmostEqual(after['weapon_factor'],1.05)
  preview=aug_compare.mod_calibration_sensitivity([row],{'tech_policy':'assume_active'})
  self.assertAlmostEqual(preview['calibrations']['energy']['plain_direct_hit'],241*1.1*(1+.424+.05))
 def test_inactive_weapon_and_duplicate_instance_do_not_stack(self):
  row=self.rows()[3]
  def item(identity,i):return {'id':i,'kind':'mod_unlock','effects':{'catalog_id':identity},'level':8,
                               'stats':{'typed_modifiers':[row],'observed_attribute_lines':[row['raw_text']]}}
  weapon='mod:weapon_mod:shock-rampage-power-surge'
  armor='mod:chest_mod:enduring-shield-deviant-energy'
  slots={'primary':{'mod_id':weapon,'mod_level':8},'secondary':{'mod_id':weapon,'mod_level':8},
         'top':{'mod_id':armor,'mod_level':8},'bottoms':{'mod_id':armor,'mod_level':8}}
  resolved=mod_rolls.equipped_build_modifiers(slots,[item(weapon,'gun'),item(armor,'body')])
  self.assertEqual(resolved['ignored_weapon_slots'],['secondary'])
  self.assertEqual(len(resolved['modifiers']),1)
  self.assertEqual(resolved['resolved_slots'],['primary'])
  self.assertTrue(any('multiple active slots' in issue['reason'] for issue in resolved['unresolved']))
  primary=mod_rolls.equipped_build_modifiers({k:v for k,v in slots.items() if k in ('primary','secondary')},[item(weapon,'gun')])
  self.assertEqual(len(primary['modifiers']),1)
 def test_empty_ocr_and_level_mismatch_are_unresolved(self):
  catalog_id='mod:chest_mod:enduring-shield-deviant-energy';slots={'top':{'mod_id':catalog_id,'mod_level':9}}
  base={'id':'owned','kind':'mod_unlock','effects':{'catalog_id':catalog_id},'level':9}
  for stats in ({'typed_modifiers':[]}, {'typed_modifiers':[mod_rolls.parse_rows([ROWS[0]])[0]]},
                {'typed_modifiers':[self.rows()[0]],'original_observed_level':8}):
   got=mod_rolls.equipped_build_modifiers(slots,[{**base,'stats':stats}])
   self.assertEqual(got['modifiers'],[])
   self.assertTrue(got['unresolved'])
 def test_supported_offense_row_survives_unmodeled_defense_row(self):
  weapon=self.rows()[3]
  hp=mod_rolls.parse_rows(['Receive a DMG Reduction 4.8% for 3.0s after taking damage; cooldown: 6.0'],source_audit={'status':'source_text_and_numbers_checked','attribute_rows':[{'source_text':'Receive a DMG Reduction 4.8% for 3.0s after taking damage; cooldown: 6.0'}]})[0]
  catalog_id='mod:chest_mod:enduring-shield-deviant-energy'
  item={'id':'owned','kind':'mod_unlock','effects':{'catalog_id':catalog_id},'level':8,
        'stats':{'typed_modifiers':[weapon,hp],'observed_attribute_lines':[weapon['raw_text'],hp['raw_text']]}}
  got=mod_rolls.equipped_build_modifiers({'top':{'mod_id':catalog_id,'mod_level':8}},[item])
  self.assertEqual(len(got['modifiers']),1)
  self.assertEqual(got['modifiers'][0]['stat_type'],'all_damage_boost_percent')
  self.assertEqual(len(got['unresolved']),1)
  self.assertAlmostEqual(mod_rolls.scenario(got['modifiers'],BASE)['component_results']['direct_hit'],248.23)
 def test_max_hp_is_separate_confirmed_health_sensitivity(self):
  texts=['Max HP + 2.4%','Weapon DMG + 5%','Receive a DMG Reduction 4.8% for 3.0s after taking damage; cooldown: 6.0']
  rows=mod_rolls.parse_rows(texts,source_audit={'status':'source_text_and_numbers_checked','attribute_rows':[{'source_text':x} for x in texts]})
  self.assertEqual(rows[0]['calculation_status'],'assumption_scenario')
  self.assertEqual(rows[2]['calculation_status'],'unmodeled')
  inputs={**BASE,'pre_mod_max_hp':1000,'max_hp_excludes_selected_mods':True}
  result=mod_rolls.scenario(rows,inputs)
  health=result['component_results']['max_hp_sensitivity']
  self.assertAlmostEqual(health['after_unrounded'],1024)
  self.assertAlmostEqual(result['component_results']['direct_hit'],241*1.05)
  self.assertEqual(len(result['modifiers']['unmodeled_rows']),1)
  self.assertIsNone(mod_rolls.scenario(rows,BASE)['component_results']['max_hp_sensitivity']['after_unrounded'])
  self.assertEqual(mod_rolls.scenario(rows,BASE)['component_results']['max_hp_sensitivity']['missing'],['pre-mod Max HP'])
  gated=mod_rolls.scenario(rows,{**inputs,'tech_policy':'exclude_unknown'})
  self.assertEqual(gated['component_results']['max_hp_sensitivity']['after_unrounded'],1000)
  self.assertEqual(len(gated['modifiers']['tech_gated_rows']),2)
  with self.assertRaisesRegex(ValueError,'Confirm that Max HP'):
   mod_rolls.scenario(rows,{**inputs,'max_hp_excludes_selected_mods':False})
 def test_calibration_sensitivity_separate_from_empirical(self):
  m=self.rows();s=aug_compare.mod_calibration_sensitivity(m,{'tech_policy':'assume_active','all_damage_model':'independent_outgoing_multiplier'})
  self.assertFalse(s['winner_established']);self.assertIsNone(s['total_dps']);self.assertIsNone(s['calibrations']['energy']['sustained_plain_direct_dps_bounds'])
  self.assertAlmostEqual(s['calibrations']['energy']['plain_firing_dps'],4665.929664)
  self.assertAlmostEqual(s['calibrations']['rapid']['plain_firing_dps'],4532.8386672)
  excluded=aug_compare.mod_calibration_sensitivity(m,{'tech_policy':'assume_active'})
  self.assertLess(excluded['calibrations']['energy']['plain_firing_dps'],s['calibrations']['energy']['plain_firing_dps'])
  self.assertTrue(any(row.get('model_exclusion') for row in excluded['aggregate']['unmodeled_rows']))
  data={'common':{},'energy':{'normal_hit':500,'rpm':720},'rapid':{'normal_hit':400,'rpm':864},'typed_modifiers':m}
  compared=aug_compare.compare(data)
  self.assertEqual(compared['energy']['expected_bullet_hit'],500);self.assertEqual(compared['rapid']['expected_bullet_hit'],400)
  self.assertIsNotNone(compared['typed_mod_sensitivity'])
 def test_elemental_bucket_and_empirical_per_calibration_hit_mix(self):
  row=self.rows()[0]
  sensitivity=aug_compare.mod_calibration_sensitivity([row],{'tech_policy':'assume_active'})
  self.assertAlmostEqual(sensitivity['calibrations']['energy']['elemental_event_factor'],1+.032+.175)
  data={'common':{'hit_rate':1,'weak_rate':1,'crit_rate':.1,'crit_weak_fraction':.1},
        'energy':{'normal_hit':100,'weakspot_hit':100,'crit_weak_hit':120,'rpm':720,'crit_rate':.1,'crit_weak_fraction':.1},
        'rapid':{'normal_hit':100,'weakspot_hit':100,'crit_weak_hit':120,'rpm':720,'crit_rate':.246,'crit_weak_fraction':.246}}
  result=aug_compare.compare(data)
  self.assertAlmostEqual(result['energy']['expected_bullet_hit'],102)
  self.assertAlmostEqual(result['rapid']['expected_bullet_hit'],104.92)
  partial=aug_compare.compare({'common':{'hit_rate':1,'dodge_fraction':0},
      'energy':{'normal_hit':100,'rpm':720,'magazine':40,'reload_seconds':2,'accepted_return_rate':0,
                'proc_events_in_fight':0,'orb_events_in_fight':0},
      'rapid':{'normal_hit':100,'rpm':720,'magazine':40,'reload_seconds':2,
               'proc_events_in_fight':0,'orb_events_in_fight':0}})
  self.assertFalse(partial['energy']['fight_complete'])
  self.assertTrue(any('crit fraction' in reason for reason in partial['energy']['fight_missing']))

if __name__=='__main__':unittest.main()
