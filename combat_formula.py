"""Explicit conditional combat component model; no ownership or game mutation.

Every result distinguishes screenshot facts, user/illustrative inputs and assumptions.
No complete total is returned until bullet, Power Surge and orb streams are resolved.
"""
from __future__ import annotations
import math
from fractions import Fraction
import aug_compare, mod_rolls, native_direct_hit_graph

PREVIEW={
 'base_origin':'pre_mod_unbuffed','damage':241.0,'rpm':720.0,'magazine':40,
 'crit_rate':0.10,'crit_damage_bonus':0.25,'weakspot_damage_bonus':0.60,
 'source_ref':aug_compare.BASELINE['source_ref'],
 'source_kind':'Tier V uncalibrated crafting preview; not owned/equipped',
}

SET_REFERENCE={
 'damage':251.0,'rpm':720.0,'magazine':40,
 'crit_rate':0.10,'crit_damage_bonus':0.25,'weakspot_damage_bonus':0.60,
 'source_name':'OH Builds planner catalog, October 20, 2026 snapshot',
 'source_scope':'publisher-described Tier V six-star AUG screenshot estimate; original baseline image not independently verified',
}

def compare_reference_sets(data):
 """Unsaved two-piece A/B components with shared HP and shield conditions."""
 if not isinstance(data,dict):raise ValueError('Comparison inputs must be an object')
 baseline=data.get('baseline') or {}
 damage=number(baseline.get('damage'),'shared pre-set damage',required=True)
 crit=number(baseline.get('crit_rate'),'shared crit rate',required=True,maximum=1)
 crit_bonus=number(baseline.get('crit_damage_bonus'),'shared crit damage bonus',required=True)
 landed=number(data.get('landed_body_hits'),'landed body hits',required=True)
 if damage<=0 or landed<=0 or not landed.is_integer() or landed>10000:
  raise ValueError('Use positive damage and 1–10000 whole landed body hits')
 psi=number(data.get('psi_intensity'),'Psi intensity')
 collisions=number(data.get('orb_enemy_hits'),'orb enemy hits')
 if collisions is not None and (not collisions.is_integer() or collisions>100000):
  raise ValueError('Orb enemy hits must be a whole count')
 shield=data.get('savior_shield')
 if shield not in ('active','inactive','unknown'):raise ValueError('Choose Savior shield active, inactive or unknown')
 hp=number(data.get('hp_percent'),'shared HP percent',maximum=100)
 reload_base=number(data.get('pre_effect_reload_seconds'),'pre-effect reload seconds')
 pieces=data.get('pieces_per_alternative',2)
 if isinstance(pieces,bool) or pieces!=2:raise ValueError('Each alternative must have exactly two pieces')
 set_a=data.get('set_a','shelterer');set_b=data.get('set_b','savior')
 choices={'shelterer','savior','bastille','treacherous_tides'}
 if set_a not in choices or set_b not in choices:raise ValueError('Choose one of the four supported two-piece sets for A and B')
 elemental_model=data.get('elemental_model','shared_bucket')
 if elemental_model not in ('shared_bucket','separate_factors'):
  raise ValueError('Choose a supported elemental model sensitivity')
 base_hit=damage*(1+crit*crit_bonus)
 expected_roots=landed*.30
 def one(set_name,*,selected_hp=hp,selected_shield=shield):
  weapon=status=element=reload_eff=0.0
  unresolved=[];evidence=[]
  if set_name=='shelterer':
   element=8.0
   evidence.append('Shelterer 2: Elemental +8 percentage points; current-client catalog numeric claim, not official numeric proof.')
  elif set_name=='savior':
   evidence.append('Savior 2: shield condition is official September 2025; +10 Weapon and +10 Status are catalog/creator numeric claims. Two pieces do not create a shield.')
   if selected_shield=='active':weapon=status=10.0
   elif selected_shield=='unknown':weapon=status=None;unresolved.append('whether Savior shield is active')
  elif set_name=='bastille':
   reload_eff=15.0
   evidence.append('Bastille 1: Weapon +10 only above 70% HP, official December 2024. Bastille 2: Reload Efficiency +15%, official January 2026; older Reload Speed +20% is not reused.')
   if selected_hp is None:weapon=None;unresolved.append('whether HP is above 70% for Bastille Weapon DMG')
   elif selected_hp>70:weapon=10.0
  else:
   evidence.append('Treacherous Tides 2: Weapon and Status +12 only below 70% HP, official September 16, 2026 final adjustment.')
   if selected_hp is None:weapon=status=None;unresolved.append('whether HP is below 70% for Treacherous Tides')
   elif selected_hp<70:weapon=status=12.0
  elemental=(1+.30+element/100) if elemental_model=='shared_bucket' else (1+.30)*(1+element/100)
  direct=base_hit*(1+weapon/100)*landed if weapon is not None else None
  per_psi_ps=expected_roots*.5*elemental*(1+status/100) if status is not None else None
  per_psi_orb=.42*elemental*(1+status/100) if status is not None else None
  ps=per_psi_ps*psi if per_psi_ps is not None and psi is not None else None
  orb=per_psi_orb*psi*collisions if per_psi_orb is not None and psi is not None and collisions is not None else None
  return {'name':set_name.replace('_',' ').title()+' · two pieces',
   'set_id':set_name,'piece_count':2,'weapon_damage_percent':weapon,
   'status_damage_percent':status,'elemental_damage_percent':element,
   'reload_efficiency_percent':reload_eff,
   'reload_seconds_if_entered':reload_base/(1+reload_eff/100) if reload_base is not None else None,
   'unresolved_conditions':unresolved,'evidence':evidence,
   'known_bullet_component':base_hit*landed if direct is None else direct,
   'selected_bullet_component':direct,
   'expected_root_procs_under_independent_trials':expected_roots,
   'power_surge_damage_per_psi':per_psi_ps,
   'orb_damage_per_psi_per_enemy_hit':per_psi_orb,
   'power_surge_component':ps,'orb_component':orb,
   'modeled_components_sum':direct+ps+orb if None not in (direct,ps,orb) else None}
 selected_a=one(set_a);selected_b=one(set_b)
 shelterer=one('shelterer')
 savior_active=one('savior',selected_shield='active')
 savior_inactive=one('savior',selected_shield='inactive')
 selected=savior_active if shield=='active' else savior_inactive if shield=='inactive' else None
 a_bullet=selected_a['selected_bullet_component'];b_bullet=selected_b['selected_bullet_component']
 bullet_delta=b_bullet-a_bullet if None not in (a_bullet,b_bullet) else None
 a_total=selected_a['modeled_components_sum'];b_total=selected_b['modeled_components_sum']
 entered_delta=b_total-a_total if None not in (a_total,b_total) else None
 return require_finite_result({'baseline_source':baseline.get('source_ref','user-entered, unsaved pre-set baseline'),
         'baseline_reference':SET_REFERENCE,'landed_body_hits':int(landed),
         'psi_intensity':psi,'orb_enemy_hits':int(collisions) if collisions is not None else None,
         'savior_shield':shield,'hp_percent':hp,'pre_effect_reload_seconds':reload_base,
         'elemental_model':elemental_model,'set_a':set_a,'set_b':set_b,
         'a':selected_a,'b':selected_b,'delta_b_minus_a_bullets':bullet_delta,
         'delta_b_minus_a_entered_components':entered_delta,
         'identical_choice':set_a==set_b,
         'shelterer':shelterer,'savior_active':savior_active,'savior_inactive':savior_inactive,
         'selected_savior':selected,
         'complete_game_prediction':False,
         'missing':selected_a['unresolved_conditions']+selected_b['unresolved_conditions']+
                   (['Psi intensity for absolute Power Surge damage'] if psi is None else [])+
                   (['observed orb enemy-hit count for absolute orb damage'] if collisions is None else []),
         'assumptions':['Exactly two pieces of the chosen set; no three-piece effect.',
                        'Both alternatives use the same unsaved pre-set AUG reference, hit count and target.',
                        'Only landed body hits are counted; crit expectation uses the shared entered crit chance and bonus, with no weakspot hits.',
                        'AUG root chance 30% and independent trials are hypotheses; expected root count is not a measured proc count.',
                        'Each ordinary Power Surge is modeled as 0.5 × Psi and each actual orb enemy collision as 0.42 × Psi under the selected elemental-bucket hypothesis.',
                        'Orb enemy collisions are entered, not inferred from root procs, field uptime or maximum bounces.',
                        'Shared HP percent and shield status determine both alternatives. Exactly two pieces are modeled; neither three-piece effects nor set-created shields are inferred.',
                        'Bastille Reload Efficiency is a separate known modifier. A 40-landed-hit burst is not a sustained reload cycle; pre-effect reload is shown only when entered.',
                        'Damage buckets, shield uptime and catalog-only set magnitudes remain source-qualified model assumptions. Other gear, enemy mitigation, buffs and conditions are excluded.']})


def number(value,label,*,minimum=0,maximum=None,required=False):
 if value in (None,''):
  if required:raise ValueError(label+' is required')
  return None
 if isinstance(value,bool):raise ValueError(label+' must be numeric')
 try:n=float(value)
 except (TypeError,ValueError):raise ValueError(label+' must be numeric') from None
 if not math.isfinite(n) or n<minimum or n>(1e15 if maximum is None else maximum):raise ValueError(label+' is outside the supported range')
 return n


def require_finite_result(value, label='modeled result'):
 if isinstance(value,float) and not math.isfinite(value):
  raise ValueError(label+' exceeds the supported numerical range')
 if isinstance(value,dict):
  for key, child in value.items():require_finite_result(child,label+'.'+str(key))
 elif isinstance(value,(list,tuple)):
  for index, child in enumerate(value):require_finite_result(child,label+'['+str(index)+']')
 return value


def finite_shots(seconds,rpm,magazine,reload_seconds,accepted_return_rate=0):
 """Count [0, T) shot opportunities, first shot at t=0, absent ammo returns.

 Each magazine fires at k/(RPM/60), k=0..M-1. The next magazine begins
 M/(RPM/60) + reload_seconds after the first shot. With an entered ammo-return
 rate, individual return times are unknown, so retain only the earlier
 continuous expected-shot exposure; it is not an integer event simulation.
 """
 f=rpm/60
 if seconds<0 or rpm<=0 or magazine<1 or int(magazine)!=magazine or reload_seconds<0 or accepted_return_rate<0:
  raise ValueError('Shot timing needs nonnegative time/reload/returns, positive RPM and integer magazine')
 if accepted_return_rate>=f:raise ValueError('Accepted return rate must be below firing rate')
 if accepted_return_rate==0:
  duration=Fraction(str(seconds));rate=Fraction(str(rpm))/60
  rounds=int(magazine);cycle=Fraction(rounds)/rate+Fraction(str(reload_seconds))
  full=duration//cycle;tail=duration-full*cycle
  partial=min(rounds,math.ceil(tail*rate)) if tail>0 else 0
  return full*rounds+partial
 fire_time=magazine/(f-accepted_return_rate)
 cycle=fire_time+reload_seconds
 full=math.floor(seconds/cycle)
 tail=seconds-full*cycle
 return f*(full*fire_time+min(tail,fire_time))


def event_stream(name,spec,*,active_seconds,psi,all_factor,elemental_factor,status_factor):
 spec=spec or {}
 rate=number(spec.get('events_per_active_second'),name+' event rate')
 damage=number(spec.get('pre_mod_damage_per_event'),name+' pre-mod damage')
 coefficient=number(spec.get('psi_coefficient'),name+' Psi coefficient')
 if damage is not None and coefficient is not None:raise ValueError(name+' uses damage/event OR Psi coefficient')
 if damage is None and coefficient is not None and psi is not None:damage=psi*coefficient
 if spec.get('already_modified_damage_per_event') not in (None,''):
  # Measured post-mod events are handled separately, never multiplied again.
  if damage is not None:raise ValueError(name+' cannot mix pre-mod and observed damage')
  damage=number(spec['already_modified_damage_per_event'],name+' observed damage')
  observed=True
 else:observed=False
 elemental=spec.get('elemental')
 status=spec.get('status')
 if elemental not in (None,True,False) or status not in (None,True,False):raise ValueError(name+' element/status flags must be true, false or unknown')
 field=spec.get('requires_field')
 if field not in (None,True,False):raise ValueError(name+' field flag must be true, false or unknown')
 field_uptime=number(spec.get('field_uptime_fraction'),name+' field uptime',maximum=1)
 rate_includes_field=spec.get('rate_includes_field_uptime')
 if rate_includes_field not in (None,True,False):raise ValueError(name+' rate scope must be true, false or unknown')
 if rate==0 and active_seconds is not None:
  return {'pre_mod_or_observed_damage_per_event':damage,
          'damage_origin':'observed_already_modified' if observed else 'pre_mod_unbuffed',
          'events_per_active_second':0,'rate_includes_field_uptime':rate_includes_field,
          'event_factor':None,'damage_per_event_after_mods':None,'damage':0.0,
          'average_dps':0.0,'missing':[],
          'source':'Explicit zero events for this encounter; no per-event damage or classification inferred.'}
 if field is None:effective_rate=None
 elif field is False:effective_rate=rate
 elif rate_includes_field is True:effective_rate=rate
 elif rate_includes_field is False and field_uptime is not None:effective_rate=rate*field_uptime if rate is not None else None
 else:effective_rate=None
 # Without classification, no confident typed modifier assignment to this stream.
 classified=elemental is not None and status is not None
 if damage is not None and effective_rate is not None and active_seconds is not None and (observed or classified):
  factor=1 if observed else all_factor*(elemental_factor if elemental else 1)*(status_factor if status else 1)
  after=damage*factor
  total=after*effective_rate*active_seconds
 else:
  factor=None;after=None;total=None
 missing=[]
 if active_seconds is None:missing.append('active fight time from dodge downtime')
 if rate is None:missing.append(name+' event rate')
 if damage is None:missing.append(name+' pre-mod event damage or Psi and coefficient')
 if field is None:missing.append(name+' field requirement classification')
 if field is True and rate_includes_field is None:missing.append(name+' whether entered rate already includes field uptime')
 if field is True and rate_includes_field is False and field_uptime is None:missing.append(name+' field uptime')
 if not observed and not classified:missing.append(name+' elemental/status classification')
 return {'pre_mod_or_observed_damage_per_event':damage,'damage_origin':'observed_already_modified' if observed else 'pre_mod_unbuffed',
         'events_per_active_second':effective_rate,'rate_includes_field_uptime':rate_includes_field,'event_factor':factor,'damage_per_event_after_mods':after,
         'damage':total,'average_dps':total/(active_seconds if active_seconds else 1) if total is not None else None,
         'missing':missing,'source':'entered assumption or measurement; no event rate inferred from weapon tooltip'}


def one_calibration(calibration,baseline,modifiers,encounter,proc,orb):
 """Compute one Energy or Rapid result for 60 and 300 seconds."""
 if baseline.get('base_origin')!='pre_mod_unbuffed':
  raise ValueError('A pre-mod, uncalibrated, unbuffed baseline is required; observed aggregate stats can already include calibration, gear, food or deviation bonuses')
 # The AUG field gates orb creation when Power Surge is applied inside it;
 # ordinary Power Surge events themselves are not field-gated. Keep the
 # two streams distinct so field uptime never discounts both.
 if proc.get('requires_field') is True:
  raise ValueError('Ordinary Power Surge is not gated by the AUG field; model field-dependent orbs separately')
 proc={**proc,'requires_field':False,'rate_includes_field_uptime':None,'field_uptime_fraction':None}
 damage=number(baseline.get('damage'),'baseline damage',required=True)
 rpm=number(baseline.get('rpm'),'baseline RPM',required=True)
 magazine=number(baseline.get('magazine'),'baseline magazine',required=True)
 if min(damage,rpm,magazine)<=0:raise ValueError('Baseline damage, RPM and magazine must be positive')
 crit_rate=number(baseline.get('crit_rate'),'baseline crit rate',maximum=1)
 crit_bonus=number(baseline.get('crit_damage_bonus'),'baseline crit damage bonus')
 weak_bonus=number(baseline.get('weakspot_damage_bonus'),'baseline weakspot damage bonus')
 reload_time=number(encounter.get('pre_mod_reload_seconds'),'pre-mod reload seconds')
 dodge=number(encounter.get('dodge_fraction'),'dodge fraction',maximum=1)
 hit=number(encounter.get('hit_rate'),'hit rate',maximum=1)
 weak_fraction=number(encounter.get('weakspot_fraction'),'weakspot fraction',maximum=1)
 overlap_key=f'{calibration}_crit_weak_overlap'
 overlap_input=encounter.get(overlap_key)
 if overlap_input in (None,''):overlap_input=encounter.get('crit_weak_overlap')
 overlap=number(overlap_input,'crit/weakspot overlap',maximum=1)
 returns=number(encounter.get('accepted_energy_returns_per_second'),'accepted Energy returns',maximum=1/.3) if calibration=='energy' else 0
 psi=number(encounter.get('psi_intensity'),'Psi intensity')
 scenario=encounter.get('scenario','other_unknown')
 if scenario not in ('isles_of_abyss','other_unknown'):
  raise ValueError('Unknown scenario rules')
 values=mod_rolls.aggregate(modifiers,tech_policy=encounter.get('tech_policy','exclude_unknown'),
                           all_damage_model=encounter.get('all_damage_model','exclude_unverified'));p=values['percent_by_type']
 all_damage_unresolved=any(row.get('stat_type')=='all_damage_boost_percent' for row in values['unmodeled_rows'])
 offense_unresolved=any(mod_rolls.may_affect_offense(row) for row in values['unmodeled_rows']+values['tech_gated_rows'])
 health=mod_rolls.max_hp_sensitivity(values,encounter.get('pre_mod_max_hp'),
                                     confirmed_pre_mod=encounter.get('max_hp_excludes_selected_mods') is True)
 # Each placement is a model assumption, not a verified game bucket law.
 attack=1.10 if calibration=='energy' else .90
 weapon=1.424 if calibration=='energy' else 1.409
 weapon+=p.get('weapon_damage_percent',0)/100
 all_factor=1+p['all_damage_boost_percent']/100
 elemental_factor=1+p['elemental_damage_percent']/100+(.175 if calibration=='energy' else 0)
 status_factor=1+p['status_damage_percent']/100
 f_rpm=rpm*(1 if calibration=='energy' else 1.20)
 # Apply the source-checked Reload Efficiency roll to final reload time.
 # Rapid's photographed "Reload Speed" is an older, separate model assumption
 # above this divisor; no label is silently reclassified as a typed roll.
 f_reload=(reload_time/(1 if calibration=='energy' else 1.10))/(1+p['reload_efficiency_percent']/100) if reload_time is not None else None
 mag_raw=magazine*(1+p['magazine_capacity_percent']/100)
 require_finite_result({'rpm':f_rpm,'reload':f_reload,'magazine':mag_raw,'bullet_base':damage*attack*weapon*all_factor},'intermediate calculation')
 mag_choices={'floor':max(1,math.floor(mag_raw)),'ceil':max(1,math.ceil(mag_raw))}
 f_crit=min(1,crit_rate+(.146 if calibration=='rapid' else 0)) if crit_rate is not None else None
 f_crit_bonus=crit_bonus+p.get('crit_damage_percent',0)/100 if crit_bonus is not None else None
 f_weak_bonus=weak_bonus+p.get('weakspot_damage_percent',0)/100 if weak_bonus is not None else None
 bullet_base=damage*attack*weapon*all_factor
 expected_hit=None;hit_groups=None
 if None not in (f_crit,f_crit_bonus,f_weak_bonus,weak_fraction,overlap):
  if overlap<max(0,f_crit+weak_fraction-1)-1e-9 or overlap>min(f_crit,weak_fraction)+1e-9:
   raise ValueError('Crit/weakspot overlap inconsistent with fractions')
  weights={'normal':1-f_crit-weak_fraction+overlap,'crit':f_crit-overlap,'weakspot':weak_fraction-overlap,'both':overlap}
  hits={'normal':bullet_base,'crit':bullet_base*(1+f_crit_bonus),
        'weakspot':bullet_base*(1+f_weak_bonus),
        'both':bullet_base*native_direct_hit_graph.joint_factor(
            f_crit_bonus,f_weak_bonus,crit=True,weakspot=True)}
  expected_hit=sum(weights[k]*hits[k] for k in weights)
  hit_groups={'weights':weights,'damage':hits,'expected_landed_hit':expected_hit,
              'joint_factor_source':native_direct_hit_graph.source()}
 results={}
 for duration in (60,300):
  active=duration*(1-dodge) if dodge is not None else None
  shot_bounds={}
  if active is not None and f_reload is not None and (calibration!='energy' or returns is not None):
   for label,mag in mag_choices.items():shot_bounds[label]=finite_shots(active,f_rpm,mag,f_reload,returns or 0)
  bullet_bounds={label:count*hit*expected_hit for label,count in shot_bounds.items()} if hit is not None and expected_hit is not None else None
  firing_only_bullet=(active*f_rpm/60*hit*expected_hit
                      if active is not None and hit is not None and expected_hit is not None else None)
  surge=event_stream('Power Surge',proc,active_seconds=active,psi=psi,all_factor=all_factor,
                      elemental_factor=elemental_factor,status_factor=status_factor)
  orb_result=event_stream('orb',orb,active_seconds=active,psi=psi,all_factor=all_factor,
                          elemental_factor=elemental_factor,status_factor=status_factor)
  complete=not offense_unresolved and bool(bullet_bounds) and surge is not None and orb_result is not None and surge['damage'] is not None and orb_result['damage'] is not None
  total_bounds={k:bullet_bounds[k]+surge['damage']+orb_result['damage'] for k in shot_bounds} if complete else None
  missing=[]
  if dodge is None:missing.append('dodge downtime fraction')
  if f_reload is None:missing.append('pre-mod reload seconds')
  if calibration=='energy' and returns is None:missing.append('accepted Energy ammo returns/s; enter observed zero if none')
  if hit is None:missing.append('hit rate')
  if expected_hit is None:missing.append('crit rate/damage, weakspot bonus/fraction and overlap')
  if all_damage_unresolved:missing.append('All DMG Boost bucket placement; select the explicitly hypothetical independent multiplier or leave the complete total withheld')
  if offense_unresolved and not all_damage_unresolved:missing.append('selected offensive roll activation, evidence or calculation rule')
  if surge:missing.extend(surge['missing'])
  else:missing.append('Power Surge stream and active time')
  if orb_result:missing.extend(orb_result['missing'])
  else:missing.append('orb stream and active time')
  results[str(duration)]={'duration_seconds':duration,'active_seconds':active,'shots_bounds':shot_bounds or None,
   'shot_count_model':('discrete_first_shot_at_zero_half_open' if returns==0 else
                       'continuous_expected_ammo_return_exposure' if shot_bounds else None),
   'bullet_damage_bounds':bullet_bounds,'firing_only_bullet_damage':firing_only_bullet,
   'power_surge':surge,'orb':orb_result,'total_damage_bounds':total_bounds,
   'average_dps_bounds':{k:v/duration for k,v in total_bounds.items()} if total_bounds else None,
   'complete_under_entered_assumptions':complete,'missing':missing}
 return {'calibration':calibration,'calibration_source':aug_compare.CALIBRATIONS[calibration]['source_ref'],
  'calibration_observed_effects':aug_compare.CALIBRATIONS[calibration]['observed_effects'],
  'baseline_source':baseline.get('source_ref'),'baseline_source_kind':baseline.get('source_kind','user-entered pre-mod baseline'),
  'base_direct_hit_after_bonuses':bullet_base,
  'rpm_scenario':f_rpm,'reload_seconds_scenario':f_reload,'reload_efficiency_roll_percent':p['reload_efficiency_percent'],
  'reload_efficiency_rule_source':'https://www.oncehuman.game/news/update/20250521/40780_1235763.html',
  'magazine_unrounded':mag_raw,'magazine_bounds':mag_choices,
  'max_hp_sensitivity':health,
  'hit_groups':hit_groups,'typed_modifiers_used':values['used_rows'],'typed_modifiers_unmodeled':values['unmodeled_rows'],
  'typed_modifiers_tech_gated':values['tech_gated_rows'],'tech_activation_policy':values['tech_policy'],
  'all_damage_model':values['all_damage_model'],
  'durations':results,'assumptions':[('Isles of Abyss PvE: Cradle unavailable per official October 2026 update; no Cradle effects included.' if scenario=='isles_of_abyss' else 'Scenario mechanics unknown; no Cradle effects included or assumed.'),values['tech_activation_assumption'],
    values['stacking_assumption']+' Attack and Weapon DMG are still model bucket assumptions, not a verified game order.',
    'A bullet that both crits and hits a weakspot uses one plus the two additions in the recovered version-13 direct-hit graph; enter the outcome overlap explicitly. This does not verify the other modeled damage buckets.',
    'Rapid +20% RPM is modeled without a verified cap. Official May 2025 rules define final reload time as base time / (1 + Reload Efficiency bonus), but the photographed Rapid roll says Reload Speed +10%; treating those labels as equivalent here is an unverified interpretation. Source: https://www.oncehuman.game/news/update/20250521/40780_1235763.html',
    'A source-checked Reload Efficiency mod roll divides modeled final reload time by (1 + roll fraction), using the official May 2025 rule. It is separate from the photographed Rapid Reload Speed label.',
    'Elemental and status bonuses are added within each assumed bucket and only applied to classified streams.',
    'Magazine capacity rounding uses floor/ceil bounds because the game rule is unknown.',
    'Without ammo returns, firing opportunities are integer shots: first at t=0, half-open [0, active time), next magazine starts M/(RPM/60)+reload after the prior first shot. Expected bullet damage may still be fractional because hit and crit rates are probabilities.',
    'Accepted Energy returns are entered, not inferred from cannon hits or Savior shield. A positive return rate yields fractional continuous shot exposure, not exact discrete firing events.',
    'No out-of-combat Safe Haven gain or other conditional core effect is applied during boss combat.',
    'Ordinary Power Surge is not discounted by AUG field uptime. Orb creation is a separate field-eligible event. Official May 13, 2026 release: https://www.oncehuman.game/news/official/20260513/40779_1300125.html',
    'Power Surge/orb rate, Psi coefficient, orb field uptime and elemental/status identity must be supplied or remain unknown.']}


def planned_calibration_sensitivity(result, encounter, options):
 """Unsaved 60s AUG component sensitivity on the same entered encounter.

 Root frequency, Power Surge/Psi and orb/Psi coefficients are source-qualified
 hypotheses. Orb enemy hits are distinct entered observations for each style.
 """
 if not isinstance(options,dict):raise ValueError('Planned sensitivity must be an object')
 if set(options)-{'psi_intensity','energy_orb_enemy_hits','rapid_orb_enemy_hits','elemental_model'}:
  raise ValueError('Planned sensitivity has unsupported fields')
 psi=number(options.get('psi_intensity'),'planned Psi intensity')
 orb_hits={}
 for name in ('energy','rapid'):
  value=number(options.get(name+'_orb_enemy_hits'),name+' orb enemy hits')
  if value is not None and (not value.is_integer() or value>100000):
   raise ValueError(name+' orb enemy hits must be a whole count from 0 to 100000')
  orb_hits[name]=int(value) if value is not None else None
 model=options.get('elemental_model','shared_bucket')
 if model not in ('shared_bucket','separate_factors'):
  raise ValueError('Choose shared or separate Element/Shock sensitivity')
 hit=number(encounter.get('hit_rate'),'hit rate',maximum=1)
 choices={}
 for name in ('energy','rapid'):
  branch=result[name]['durations']['60']
  shots=branch['shots_bounds']
  exact_shots=(shots['floor'] if shots and shots['floor']==shots['ceil'] and
               branch['shot_count_model']=='discrete_first_shot_at_zero_half_open' else None)
  roots=exact_shots*hit*.30 if exact_shots is not None and hit is not None else None
  # Ordinary Power Surge remains distinct from field-eligible orb collisions.
  element=(1+.30+(.175 if name=='energy' else 0)) if model=='shared_bucket' else (1+.30)*(1+(.175 if name=='energy' else 0))
  ps_per_psi=roots*.5*element if roots is not None else None
  orb_per_psi_hit=.42*element
  ps=ps_per_psi*psi if ps_per_psi is not None and psi is not None else None
  orb=orb_per_psi_hit*psi*orb_hits[name] if psi is not None and orb_hits[name] is not None else None
  bullets=branch['bullet_damage_bounds']
  bullet=(bullets['floor'] if bullets and bullets['floor']==bullets['ceil'] else None)
  included=bullet+ps+orb if None not in (bullet,ps,orb) else None
  choices[name]={'integer_shot_opportunities':exact_shots,
   'expected_landed_hits':exact_shots*hit if exact_shots is not None and hit is not None else None,
   'expected_roots_independent_trials':roots,'power_surge_per_psi':ps_per_psi,
   'power_surge_component':ps,'orb_per_psi_per_enemy_hit':orb_per_psi_hit,
   'orb_enemy_hits':orb_hits[name],'orb_component':orb,
   'known_bullet_component':bullet,'included_components_sum':included}
 return require_finite_result({'duration_seconds':60,'elemental_model':model,
  'psi_intensity':psi,'energy':choices['energy'],'rapid':choices['rapid'],
  'complete_game_prediction':False,
  'source_scope':'Photographed Energy and Rapid calibration candidates on one unsaved AUG baseline; neither is confirmed equipped.',
  'assumptions':['First shot at t=0; [0,60) shot opportunities with magazine cycle M/(RPM/60)+pre-effect reload.',
   'Independent 30% root trials per eligible landed hit; no Mayfly, mods, ammo returns or extra streams.',
   'Ordinary Power Surge uses 0.5 × Psi; an actual orb enemy hit uses 0.42 × Psi. Innate Shock +30% and Energy Elemental +17.5% use the selected bucket hypothesis.',
   'Entered orb enemy-hit counts are candidate-specific collisions, not spawned orb counts, field uptime or maximum bounces.',
   'Style Attack and random Weapon DMG are separate assumed buckets; a shared additive model can reverse bullet leadership.']})


def compare(baseline,modifiers,encounter=None,proc=None,orb=None):
 encounter=encounter or {};proc=proc or {};orb=orb or {}
 energy=one_calibration('energy',baseline,modifiers,encounter,proc,orb)
 rapid=one_calibration('rapid',baseline,modifiers,encounter,proc,orb)
 comparisons={}
 for duration in ('60','300'):
  e=energy['durations'][duration]['total_damage_bounds'];r=rapid['durations'][duration]['total_damage_bounds']
  comparisons[duration]={'delta_energy_minus_rapid_bounds':{'low':e['floor']-r['ceil'],'high':e['ceil']-r['floor']} if e and r else None,
                         'winner':'energy' if e and r and e['floor']>r['ceil'] else 'rapid' if e and r and r['floor']>e['ceil'] else 'tie_or_rounding_overlap' if e and r else None}
 return require_finite_result({'energy':energy,'rapid':rapid,'comparison':comparisons,'complete_game_prediction':False,
         'note':'Any numeric totals are conditional on entered stream rates/damage and explicitly listed stacking assumptions; they are not verified game DPS.'})
