import unittest
from fractions import Fraction
import combat_formula,external_effects,mod_rolls
ROWS=['Element (Blaze, Frost, Shock, Blast) DMG + 3.2%','Status DMG + 2.4%','Magazine Capacity + 4.8%','Increases damage dealt to all DMG Boost by + 3.0%']
AUDIT={'status':'source_text_and_numbers_checked','attribute_rows':[{'source_text':x} for x in ROWS]}
MODS=mod_rolls.parse_rows(ROWS,source_audit=AUDIT)
ENCOUNTER={'pre_mod_reload_seconds':2,'dodge_fraction':.2,'hit_rate':.85,'weakspot_fraction':.2,'crit_weak_overlap':.02,'accepted_energy_returns_per_second':0,'psi_intensity':100,'tech_policy':'assume_active','all_damage_model':'independent_outgoing_multiplier'}
SURGE={'events_per_active_second':1.5,'psi_coefficient':.5,'elemental':True,'status':True,'requires_field':False}
ORB={'events_per_active_second':.6,'psi_coefficient':.42,'elemental':True,'status':False,'requires_field':True,'rate_includes_field_uptime':False,'field_uptime_fraction':.75}
class CombatFormulaTests(unittest.TestCase):
 def test_nonfinite_inputs_and_results_cannot_be_complete(self):
  baseline={**combat_formula.PREVIEW,'damage':1e308}
  with self.assertRaisesRegex(ValueError,'supported range'):
   combat_formula.compare(baseline,[],{'pre_mod_reload_seconds':2,'dodge_fraction':0,'hit_rate':1,
     'weakspot_fraction':0,'crit_weak_overlap':0,'accepted_energy_returns_per_second':0},
     {'events_per_active_second':0},{'events_per_active_second':0})
  for field in ('crit_damage_bonus','weakspot_damage_bonus'):
   with self.subTest(field=field),self.assertRaisesRegex(ValueError,'supported range'):
    combat_formula.compare({**combat_formula.PREVIEW,field:1e308},[],
      {'pre_mod_reload_seconds':2,'dodge_fraction':0,'hit_rate':1,
       'weakspot_fraction':0,'crit_weak_overlap':0,'accepted_energy_returns_per_second':0},
      {'events_per_active_second':0},{'events_per_active_second':0})
  with self.assertRaisesRegex(ValueError,'supported numerical range'):
   combat_formula.require_finite_result({'complete_under_entered_assumptions':True,'damage':float('nan')})

 def test_planned_calibration_event_sensitivity_keeps_candidates_distinct(self):
  encounter={'pre_mod_reload_seconds':2,'dodge_fraction':0,'hit_rate':1,
             'weakspot_fraction':0,'crit_weak_overlap':0,
             'accepted_energy_returns_per_second':0}
  result=combat_formula.compare(combat_formula.PREVIEW,[],encounter)
  blank=combat_formula.planned_calibration_sensitivity(result,encounter,{'elemental_model':'shared_bucket'})
  energy,rapid=blank['energy'],blank['rapid']
  self.assertEqual((energy['integer_shot_opportunities'],rapid['integer_shot_opportunities']),(456,524))
  self.assertAlmostEqual(energy['known_bullet_component'],176444.62176)
  self.assertAlmostEqual(rapid['known_bullet_component'],169989.3959346)
  self.assertAlmostEqual(energy['expected_roots_independent_trials'],136.8)
  self.assertAlmostEqual(rapid['expected_roots_independent_trials'],157.2)
  self.assertAlmostEqual(energy['power_surge_per_psi'],100.89)
  self.assertAlmostEqual(rapid['power_surge_per_psi'],102.18)
  self.assertAlmostEqual(energy['orb_per_psi_per_enemy_hit'],.6195)
  self.assertAlmostEqual(rapid['orb_per_psi_per_enemy_hit'],.546)
  self.assertIsNone(energy['power_surge_component'])
  self.assertIsNone(energy['orb_component'])
  self.assertIsNone(energy['included_components_sum'])
  entered=combat_formula.planned_calibration_sensitivity(result,encounter,{
   'psi_intensity':1000,'energy_orb_enemy_hits':2,'rapid_orb_enemy_hits':3,
   'elemental_model':'shared_bucket'})
  self.assertAlmostEqual(entered['energy']['included_components_sum'],176444.62176+100890+1239)
  self.assertAlmostEqual(entered['rapid']['included_components_sum'],169989.3959346+102180+1638)
  self.assertFalse(entered['complete_game_prediction'])
  zero=combat_formula.planned_calibration_sensitivity(result,encounter,{
   'psi_intensity':0,'energy_orb_enemy_hits':0,'rapid_orb_enemy_hits':0})
  self.assertEqual(zero['energy']['power_surge_component'],0)
  self.assertEqual(zero['rapid']['orb_component'],0)
  self.assertEqual(zero['energy']['included_components_sum'],energy['known_bullet_component'])
  separate=combat_formula.planned_calibration_sensitivity(result,encounter,{'elemental_model':'separate_factors'})
  self.assertAlmostEqual(separate['energy']['power_surge_per_psi'],104.481)
  self.assertAlmostEqual(separate['energy']['orb_per_psi_per_enemy_hit'],.64155)
  self.assertAlmostEqual(separate['rapid']['power_surge_per_psi'],102.18)
  half=combat_formula.planned_calibration_sensitivity(result,{**encounter,'hit_rate':.5}, {})
  self.assertAlmostEqual(half['energy']['expected_roots_independent_trials'],68.4)
  dodged_encounter={**encounter,'dodge_fraction':.5}
  dodged=combat_formula.planned_calibration_sensitivity(
   combat_formula.compare(combat_formula.PREVIEW,[],dodged_encounter),dodged_encounter,{})
  self.assertLess(dodged['energy']['expected_roots_independent_trials'],energy['expected_roots_independent_trials'])
  changed=combat_formula.planned_calibration_sensitivity(
   combat_formula.compare({**combat_formula.PREVIEW,'damage':500},[],encounter),encounter,{})
  self.assertEqual(changed['energy']['power_surge_per_psi'],energy['power_surge_per_psi'])
  no_reload={**encounter,'pre_mod_reload_seconds':None}
  unknown=combat_formula.planned_calibration_sensitivity(
   combat_formula.compare(combat_formula.PREVIEW,[],no_reload),no_reload,{})
  self.assertIsNone(unknown['energy']['expected_roots_independent_trials'])
  with self.assertRaisesRegex(ValueError,'whole count'):
   combat_formula.planned_calibration_sensitivity(result,encounter,{'energy_orb_enemy_hits':1.5})

 def test_external_weapon_bonus_joins_existing_bucket_from_unbuffed_base(self):
  baseline={**combat_formula.PREVIEW,'damage':100,'source_ref':'synthetic unbuffed base'}
  effect=external_effects.resolve({
   'source_kind':'food','name':'Synthetic effect','stat_type':'weapon_damage_percent',
   'value_percent':10,'source_note':'isolated arithmetic fixture',
   'activation':'observed_active','apply_hypothesis':True,
   'baseline_excludes_effect':True,'active_for_interval':True},[])['row']
  plain=combat_formula.compare(baseline,[])['rapid']['base_direct_hit_after_bonuses']
  added=combat_formula.compare(baseline,[effect])['rapid']['base_direct_hit_after_bonuses']
  self.assertAlmostEqual(plain,100*.90*1.409)
  self.assertAlmostEqual(added,100*.90*1.509)
  self.assertAlmostEqual(added/plain,1.509/1.409)
  self.assertNotAlmostEqual(added,plain*1.10)
  with self.assertRaisesRegex(ValueError,'unbuffed baseline'):
   combat_formula.compare({**baseline,'base_origin':'observed_equipped'},[effect])
 def test_no_reload_bullet_sensitivity_respects_landed_hits_and_dodge(self):
  encounter={'scenario':'other_unknown','pre_mod_reload_seconds':None,
             'accepted_energy_returns_per_second':0,'weakspot_fraction':0,
             'crit_weak_overlap':0,'hit_rate':1,'dodge_fraction':0}
  full=combat_formula.compare(combat_formula.PREVIEW,[],encounter)
  energy=full['energy']['durations']['60']
  self.assertAlmostEqual(energy['firing_only_bullet_damage'],
                         60*12*full['energy']['hit_groups']['expected_landed_hit'])
  self.assertFalse(energy['bullet_damage_bounds'])
  self.assertIsNone(energy['total_damage_bounds'])
  for changed in ({'hit_rate':0},{'dodge_fraction':1}):
   scenario=combat_formula.compare(combat_formula.PREVIEW,[],{**encounter,**changed})
   for choice in ('energy','rapid'):
    self.assertEqual(scenario[choice]['durations']['60']['firing_only_bullet_damage'],0)
  partial=combat_formula.compare(combat_formula.PREVIEW,[],{**encounter,'hit_rate':.5,'dodge_fraction':.25})
  self.assertAlmostEqual(partial['energy']['durations']['60']['firing_only_bullet_damage'],
                         energy['firing_only_bullet_damage']*.5*.75)
  finite=combat_formula.compare(combat_formula.PREVIEW,[],{**encounter,'pre_mod_reload_seconds':2})
  self.assertIsNotNone(finite['energy']['durations']['60']['bullet_damage_bounds'])
  self.assertGreater(finite['energy']['durations']['60']['firing_only_bullet_damage'],
                     finite['energy']['durations']['60']['bullet_damage_bounds']['floor'])
 def test_two_piece_set_reference_keeps_known_bullets_and_unknown_streams_separate(self):
  inputs={'baseline':{'damage':251,'crit_rate':.10,'crit_damage_bonus':.25,
                      'source_ref':'dated catalog estimate'},
          'landed_body_hits':40,'psi_intensity':None,'orb_enemy_hits':None,
          'savior_shield':'active','elemental_model':'shared_bucket'}
  result=combat_formula.compare_reference_sets(inputs)
  self.assertAlmostEqual(result['shelterer']['known_bullet_component'],10291)
  self.assertAlmostEqual(result['savior_active']['known_bullet_component'],11320.1)
  self.assertAlmostEqual(result['shelterer']['expected_root_procs_under_independent_trials'],12)
  self.assertAlmostEqual(result['shelterer']['power_surge_damage_per_psi'],8.28)
  self.assertAlmostEqual(result['shelterer']['orb_damage_per_psi_per_enemy_hit'],.5796)
  self.assertAlmostEqual(result['savior_active']['power_surge_damage_per_psi'],8.58)
  self.assertAlmostEqual(result['savior_active']['orb_damage_per_psi_per_enemy_hit'],.6006)
  self.assertIsNone(result['shelterer']['modeled_components_sum'])
  self.assertFalse(result['complete_game_prediction'])
  with_values=combat_formula.compare_reference_sets({**inputs,'psi_intensity':100,'orb_enemy_hits':3})
  self.assertAlmostEqual(with_values['shelterer']['modeled_components_sum'],10291+828+173.88)
  self.assertAlmostEqual(with_values['savior_active']['modeled_components_sum'],11320.1+858+180.18)
  self.assertAlmostEqual(with_values['savior_inactive']['known_bullet_component'],10291)
  separate=combat_formula.compare_reference_sets({**inputs,'elemental_model':'separate_factors'})
  self.assertAlmostEqual(separate['shelterer']['power_surge_damage_per_psi'],8.424)
  self.assertAlmostEqual(separate['shelterer']['orb_damage_per_psi_per_enemy_hit'],.58968)
  unknown=combat_formula.compare_reference_sets({**inputs,'savior_shield':'unknown'})
  self.assertIsNone(unknown['selected_savior'])
  with self.assertRaisesRegex(ValueError,'whole landed body hits'):
   combat_formula.compare_reference_sets({**inputs,'landed_body_hits':2.5})
 def test_max_hp_preview_is_independent_of_damage(self):
  text='Max HP + 2.4%'
  row=mod_rolls.parse_rows([text],source_audit={'status':'source_text_and_numbers_checked','attribute_rows':[{'source_text':text}]})[0]
  encounter={**ENCOUNTER,'pre_mod_max_hp':1000,'max_hp_excludes_selected_mods':True}
  before=combat_formula.compare(combat_formula.PREVIEW,[],encounter,SURGE,ORB)
  after=combat_formula.compare(combat_formula.PREVIEW,[row],encounter,SURGE,ORB)
  for calibration in ('energy','rapid'):
   health=after[calibration]['max_hp_sensitivity']
   self.assertEqual(health['pre_mod_max_hp'],1000)
   self.assertAlmostEqual(health['after_unrounded'],1024)
   self.assertEqual(after[calibration]['durations']['300']['total_damage_bounds'],before[calibration]['durations']['300']['total_damage_bounds'])
  missing=combat_formula.compare(combat_formula.PREVIEW,[row],ENCOUNTER,SURGE,ORB)['energy']['max_hp_sensitivity']
  self.assertIsNone(missing['after_unrounded'])
  self.assertEqual(missing['missing'],['pre-mod Max HP'])
  gated=combat_formula.compare(combat_formula.PREVIEW,[row],{**encounter,'tech_policy':'exclude_unknown'},SURGE,ORB)['energy']
  self.assertEqual(gated['max_hp_sensitivity']['after_unrounded'],1000)
  with self.assertRaisesRegex(ValueError,'Confirm that Max HP'):
   combat_formula.compare(combat_formula.PREVIEW,[row],{**encounter,'max_hp_excludes_selected_mods':False},SURGE,ORB)
 def test_unknown_tech_rows_not_applied_by_default(self):
  default=combat_formula.compare(combat_formula.PREVIEW,MODS,{k:v for k,v in ENCOUNTER.items() if k!='tech_policy'},SURGE,ORB)['energy']
  assumed=combat_formula.compare(combat_formula.PREVIEW,MODS,ENCOUNTER,SURGE,ORB)['energy']
  self.assertEqual(default['typed_modifiers_used'],[])
  self.assertEqual(len(default['typed_modifiers_tech_gated']),4)
  self.assertEqual(default['magazine_bounds'],{'floor':40,'ceil':40})
  self.assertEqual(len(assumed['typed_modifiers_used']),4)
 def test_isles_scenario_excludes_cradle_and_unknown_scenarios_fail(self):
  isles=combat_formula.compare(combat_formula.PREVIEW,[],{**ENCOUNTER,'scenario':'isles_of_abyss'},SURGE,ORB)['energy']
  self.assertTrue(any('Cradle unavailable' in x for x in isles['assumptions']))
  with self.assertRaisesRegex(ValueError,'Unknown scenario'):
   combat_formula.compare(combat_formula.PREVIEW,[],{**ENCOUNTER,'scenario':'invented'},SURGE,ORB)
 def test_real_preview_and_rolls_both_durations_and_before_after(self):
  before=combat_formula.compare(combat_formula.PREVIEW,[],ENCOUNTER,SURGE,ORB)
  after=combat_formula.compare(combat_formula.PREVIEW,MODS,ENCOUNTER,SURGE,ORB)
  self.assertEqual((combat_formula.PREVIEW['damage'],combat_formula.PREVIEW['rpm'],combat_formula.PREVIEW['magazine']),(241,720,40))
  self.assertEqual(after['energy']['baseline_source'],combat_formula.PREVIEW['source_ref'])
  self.assertEqual(after['energy']['calibration_source'],'libfile_a52887f909c481918310b2bac02dc446')
  self.assertEqual(after['rapid']['calibration_source'],'libfile_2ddcabd50f60819187d35ddc0e411389')
  self.assertIn('Weapon DMG +42.4%',after['energy']['calibration_observed_effects'])
  self.assertIn('Weapon DMG +40.9%',after['rapid']['calibration_observed_effects'])
  self.assertIn('not owned/equipped',after['energy']['baseline_source_kind'])
  self.assertEqual(after['energy']['magazine_bounds'],{'floor':41,'ceil':42})
  self.assertGreater(after['energy']['durations']['60']['total_damage_bounds']['floor'],before['energy']['durations']['60']['total_damage_bounds']['floor'])
  self.assertGreater(after['rapid']['durations']['300']['total_damage_bounds']['floor'],before['rapid']['durations']['300']['total_damage_bounds']['floor'])
  self.assertAlmostEqual(after['energy']['durations']['60']['total_damage_bounds']['floor'],145350.12785475605)
  self.assertAlmostEqual(after['rapid']['durations']['300']['total_damage_bounds']['ceil'],701556.2774647143)
  self.assertEqual(after['energy']['durations']['60']['power_surge']['events_per_active_second'],1.5)
  self.assertAlmostEqual(after['energy']['durations']['60']['orb']['events_per_active_second'],.45)
  self.assertFalse(after['complete_game_prediction'])
 def test_four_modifiers_affect_matching_terms_only(self):
  base=combat_formula.compare(combat_formula.PREVIEW,[],ENCOUNTER,SURGE,ORB)['energy']
  e=combat_formula.compare(combat_formula.PREVIEW,[MODS[0]],ENCOUNTER,SURGE,ORB)['energy']
  self.assertEqual(e['base_direct_hit_after_bonuses'],base['base_direct_hit_after_bonuses'])
  self.assertGreater(e['durations']['60']['power_surge']['damage'],base['durations']['60']['power_surge']['damage'])
  self.assertEqual(e['durations']['60']['shots_bounds'],base['durations']['60']['shots_bounds'])
  s=combat_formula.compare(combat_formula.PREVIEW,[MODS[1]],ENCOUNTER,SURGE,ORB)['energy']
  self.assertGreater(s['durations']['60']['power_surge']['damage'],base['durations']['60']['power_surge']['damage'])
  self.assertEqual(s['durations']['60']['orb']['damage'],base['durations']['60']['orb']['damage'])
  m=combat_formula.compare(combat_formula.PREVIEW,[MODS[2]],ENCOUNTER,SURGE,ORB)['energy']
  self.assertEqual(m['base_direct_hit_after_bonuses'],base['base_direct_hit_after_bonuses'])
  self.assertGreater(m['durations']['300']['shots_bounds']['floor'],base['durations']['300']['shots_bounds']['floor'])
  a=combat_formula.compare(combat_formula.PREVIEW,[MODS[3]],ENCOUNTER,SURGE,ORB)['energy']
  self.assertGreater(a['base_direct_hit_after_bonuses'],base['base_direct_hit_after_bonuses'])
  self.assertEqual(a['magazine_bounds'],base['magazine_bounds'])
 def test_all_damage_without_model_or_with_existing_target_bonus_withholds_total(self):
  row=MODS[3]
  excluded=combat_formula.compare(combat_formula.PREVIEW,[row],{**ENCOUNTER,'all_damage_model':'exclude_unverified'},SURGE,ORB)
  self.assertEqual(excluded['energy']['base_direct_hit_after_bonuses'],combat_formula.compare(combat_formula.PREVIEW,[],ENCOUNTER,SURGE,ORB)['energy']['base_direct_hit_after_bonuses'])
  self.assertIsNone(excluded['energy']['durations']['60']['total_damage_bounds'])
  self.assertIsNone(excluded['comparison']['60']['winner'])
  self.assertTrue(any('All DMG Boost bucket' in item for item in excluded['energy']['durations']['60']['missing']))
  opt_in=combat_formula.compare(combat_formula.PREVIEW,[row],ENCOUNTER,SURGE,ORB)
  self.assertAlmostEqual(opt_in['energy']['base_direct_hit_after_bonuses']/excluded['energy']['base_direct_hit_after_bonuses'],1.03)
  self.assertIsNotNone(opt_in['energy']['durations']['60']['total_damage_bounds'])
  # A target-category bonus whose bucket is unknown cannot be folded into
  # that opt-in factor, even though the isolated 100 -> 103 arithmetic works.
  target_bonus={'stat_type':'boss_damage_percent','value':5.0,'raw_text':'Damage to bosses +5%','confidence':'source_checked','calculation_status':'unmodeled'}
  mixed=combat_formula.compare(combat_formula.PREVIEW,[row,target_bonus],ENCOUNTER,SURGE,ORB)
  self.assertIsNone(mixed['energy']['durations']['60']['total_damage_bounds'])
  self.assertIsNone(mixed['comparison']['60']['winner'])
  self.assertEqual(len(mixed['energy']['typed_modifiers_unmodeled']),1)
 def test_reload_efficiency_row_changes_finite_bullets_not_hit_or_proc(self):
  text='Reload Efficiency + 3.6%'
  row=mod_rolls.parse_rows([text],source_audit={'status':'source_text_and_numbers_checked',
      'attribute_rows':[{'source_text':text}]})[0]
  before=combat_formula.compare(combat_formula.PREVIEW,[],ENCOUNTER,SURGE,ORB)
  after=combat_formula.compare(combat_formula.PREVIEW,[row],ENCOUNTER,SURGE,ORB)
  for calibration in ('energy','rapid'):
   original=before[calibration];changed=after[calibration]
   self.assertAlmostEqual(changed['reload_seconds_scenario'],original['reload_seconds_scenario']/1.036)
   self.assertAlmostEqual(changed['reload_seconds_scenario'],2/(1 if calibration=='energy' else 1.10)/1.036)
   self.assertEqual(changed['base_direct_hit_after_bonuses'],original['base_direct_hit_after_bonuses'])
   self.assertGreater(changed['durations']['300']['shots_bounds']['floor'],original['durations']['300']['shots_bounds']['floor'])
   self.assertEqual(changed['durations']['300']['power_surge']['damage'],original['durations']['300']['power_surge']['damage'])
   self.assertEqual(changed['durations']['300']['orb']['damage'],original['durations']['300']['orb']['damage'])
   self.assertEqual(changed['reload_efficiency_roll_percent'],3.6)
  gated=combat_formula.compare(combat_formula.PREVIEW,[row],{**ENCOUNTER,'tech_policy':'exclude_unknown'},SURGE,ORB)
  self.assertEqual(gated['energy']['reload_seconds_scenario'],before['energy']['reload_seconds_scenario'])
  self.assertEqual(len(gated['energy']['typed_modifiers_tech_gated']),1)
  missing=combat_formula.compare(combat_formula.PREVIEW,[row],{'tech_policy':'assume_active'}, {}, {})
  self.assertIsNone(missing['energy']['durations']['300']['total_damage_bounds'])
 def test_unknowns_are_not_zero_or_complete(self):
  d=combat_formula.compare(combat_formula.PREVIEW,MODS,{}, {},{})
  self.assertIsNone(d['energy']['durations']['300']['total_damage_bounds'])
  self.assertIsNone(d['comparison']['300']['winner'])
  self.assertIn('Power Surge event rate',d['energy']['durations']['300']['missing'])
  self.assertIn('accepted Energy ammo returns/s; enter observed zero if none',d['energy']['durations']['300']['missing'])
 def test_observed_values_not_doubled_and_safe_haven_not_applied(self):
  with self.assertRaisesRegex(ValueError,'pre-mod'):
   combat_formula.compare({**combat_formula.PREVIEW,'base_origin':'observed_equipped'},MODS,ENCOUNTER,SURGE,ORB)
  observed={**SURGE,'psi_coefficient':None,'already_modified_damage_per_event':50}
  r=combat_formula.compare(combat_formula.PREVIEW,MODS,ENCOUNTER,observed,ORB)['energy']['durations']['60']['power_surge']
  self.assertEqual(r['event_factor'],1)
  self.assertAlmostEqual(r['damage'],50*1.5*48)
  d=combat_formula.compare(combat_formula.PREVIEW,MODS,ENCOUNTER,SURGE,ORB)
  self.assertTrue(any('Safe Haven' in x for x in d['energy']['assumptions']))
 def test_field_rate_already_includes_uptime_is_not_gated_twice(self):
  raw=combat_formula.compare(combat_formula.PREVIEW,MODS,ENCOUNTER,SURGE,ORB)['energy']['durations']['60']['orb']['damage']
  already={**ORB,'events_per_active_second':ORB['events_per_active_second']*.75,'rate_includes_field_uptime':True}
  measured=combat_formula.compare(combat_formula.PREVIEW,MODS,ENCOUNTER,SURGE,already)['energy']['durations']['60']['orb']['damage']
  self.assertAlmostEqual(raw,measured)
  unknown={**ORB,'rate_includes_field_uptime':None}
  result=combat_formula.compare(combat_formula.PREVIEW,MODS,ENCOUNTER,SURGE,unknown)['energy']['durations']['60']
  self.assertIsNone(result['total_damage_bounds'])
  self.assertTrue(any('already includes field uptime' in x for x in result['missing']))
  with self.assertRaisesRegex(ValueError,'Ordinary Power Surge is not gated'):
   combat_formula.compare(combat_formula.PREVIEW,MODS,ENCOUNTER,{**SURGE,'requires_field':True},ORB)
 def test_finite_cycle_no_trailing_reload_and_rate_guard(self):
  self.assertEqual(combat_formula.finite_shots(10,60,10,4),10)
  self.assertEqual(combat_formula.finite_shots(11,60,10,4),10)
  self.assertEqual(combat_formula.finite_shots(15,60,10,4),11)
  with self.assertRaisesRegex(ValueError,'below firing rate'):
   combat_formula.finite_shots(60,60,10,4,1)
 def test_discrete_shots_match_enumerated_half_open_events(self):
  def enumerate_events(seconds,rpm,magazine,reload):
   horizon=Fraction(str(seconds));rate=Fraction(str(rpm))/60
   cycle=Fraction(magazine)/rate+Fraction(str(reload))
   count=0;start=Fraction(0)
   while start<horizon:
    for index in range(magazine):
     if start+Fraction(index)/rate<horizon:count+=1
    start+=cycle
   return count
  for seconds,rpm,magazine,reload in (
      (0,60,10,4),(.001,60,10,4),(1,60,10,4),
      (1.001,60,10,4),(14,60,10,4),(14.001,60,10,4),
      (60,720,40,2),(60,864,40,2/1.1),
      (5.7,97,4,.8),(60,1800,1,.3)):
   with self.subTest(seconds=seconds,rpm=rpm,magazine=magazine,reload=reload):
    self.assertEqual(combat_formula.finite_shots(seconds,rpm,magazine,reload),
                     enumerate_events(seconds,rpm,magazine,reload))
  self.assertEqual(combat_formula.finite_shots(60,720,40,2),456)
  self.assertEqual(combat_formula.finite_shots(60,864,40,2/1.1),524)
  self.assertEqual(combat_formula.finite_shots(14,60,10,4),10)
  self.assertEqual(combat_formula.finite_shots(14.001,60,10,4),11)
  expected=combat_formula.finite_shots(4,720,40,2,1)
  self.assertNotEqual(expected,int(expected),'positive ammo-return rate remains fractional expected exposure')
  scenario=combat_formula.compare(combat_formula.PREVIEW,[],{
   'pre_mod_reload_seconds':2,'dodge_fraction':0,'hit_rate':1,
   'weakspot_fraction':0,'crit_weak_overlap':0,'accepted_energy_returns_per_second':0})
  self.assertEqual(scenario['energy']['durations']['60']['shot_count_model'],'discrete_first_shot_at_zero_half_open')
  self.assertEqual(scenario['energy']['durations']['60']['shots_bounds']['floor'],456)
  with_returns=combat_formula.compare(combat_formula.PREVIEW,[],{
   'pre_mod_reload_seconds':2,'dodge_fraction':0,'hit_rate':1,
   'weakspot_fraction':0,'crit_weak_overlap':0,'accepted_energy_returns_per_second':1})
  self.assertEqual(with_returns['energy']['durations']['60']['shot_count_model'],'continuous_expected_ammo_return_exposure')
 def test_crit_and_weakspot_distribution_and_typed_weapon_rows(self):
  texts=['Weapon DMG + 5%','Crit DMG + 6%','Weakspot DMG + 7%']
  mods=mod_rolls.parse_rows(texts,source_audit={'status':'source_text_and_numbers_checked','attribute_rows':[{'source_text':x} for x in texts]})
  d=combat_formula.compare(combat_formula.PREVIEW,mods,ENCOUNTER,SURGE,ORB)['energy']
  self.assertGreater(d['base_direct_hit_after_bonuses'],combat_formula.compare(combat_formula.PREVIEW,[],ENCOUNTER,SURGE,ORB)['energy']['base_direct_hit_after_bonuses'])
  self.assertEqual(len(d['typed_modifiers_used']),3)
  self.assertAlmostEqual(sum(d['hit_groups']['weights'].values()),1)
  with self.assertRaisesRegex(ValueError,'overlap'):
   combat_formula.compare(combat_formula.PREVIEW,[],{**ENCOUNTER,'crit_weak_overlap':.9},SURGE,ORB)
 def test_joint_crit_weakspot_uses_native_additions_not_product(self):
  encounter={**ENCOUNTER,'crit_weak_overlap':.05}
  result=combat_formula.compare(combat_formula.PREVIEW,[],encounter,SURGE,ORB)['energy']
  base=result['base_direct_hit_after_bonuses']
  groups=result['hit_groups']
  self.assertAlmostEqual(groups['damage']['both'],base*(1+.25+.60))
  self.assertNotAlmostEqual(groups['damage']['both'],base*(1+.25)*(1+.60))
  self.assertEqual(groups['joint_factor_source']['version'],13)
  self.assertAlmostEqual(groups['expected_landed_hit'],sum(
   groups['weights'][name]*value for name,value in groups['damage'].items()))
 def test_per_calibration_overlap_and_float_boundary(self):
  encounter={**ENCOUNTER,'weakspot_fraction':1,'crit_weak_overlap':None,
             'energy_crit_weak_overlap':.1,'rapid_crit_weak_overlap':.246}
  result=combat_formula.compare(combat_formula.PREVIEW,[],encounter,SURGE,ORB)
  self.assertAlmostEqual(result['energy']['hit_groups']['weights']['both'],.1)
  self.assertAlmostEqual(result['rapid']['hit_groups']['weights']['both'],.246)
  self.assertAlmostEqual(sum(result['rapid']['hit_groups']['weights'].values()),1)
 def test_explicit_zero_event_rate_resolves_zero_damage(self):
  stream=combat_formula.event_stream('orb',{'events_per_active_second':0,'requires_field':False},
      active_seconds=60,psi=None,all_factor=1,elemental_factor=1,status_factor=1)
  self.assertEqual(stream['damage'],0)
  self.assertEqual(stream['missing'],[])
if __name__=='__main__':unittest.main()
