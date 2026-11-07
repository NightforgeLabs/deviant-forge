"""Evidence-gated outgoing comparison for selected saved catalog builds.

Every selected mod and reached set threshold is audited, including unchanged
gear. A result is a conditional primary-fire estimate using a named source
profile or explicitly hypothetical unbuffed inputs, never a personalized hit.
"""
from collections import Counter
from math import ceil, floor
import json
from pathlib import Path

import catalog
import mechanics

ROOT = Path(__file__).resolve().parent
RULES = json.loads((ROOT/'damage_rules.json').read_text())['mod_main_effects']
WEAPONS = json.loads((ROOT/'weapon_profiles.json').read_text())['profiles']
ARMOR = json.loads((ROOT/'armor_capabilities.json').read_text())['entries']
OFFICIAL_TIDES = 'https://www.oncehuman.game/news/update/20261009/40780_1314019.html'


def _number(value, name, lo=None, hi=None):
    try: result = float(value)
    except (ValueError, TypeError): raise ValueError(name+' is required') from None
    if lo is not None and result < lo or hi is not None and result > hi:
        raise ValueError(name+' is outside its allowed range')
    return result


def _shots(duration, rpm, magazine, reload_seconds):
    interval = 60.0/rpm
    cycle = magazine*interval+reload_seconds
    full = floor(duration/cycle)
    remainder = duration-full*cycle
    partial = min(magazine, max(0, ceil((remainder-1e-10)/interval)))
    return full*magazine+partial, cycle


def _condition(name, encounter):
    if name == 'aerial hit': return encounter.get('aerial_hit')
    if name == 'target lower than player within 5 meters': return encounter.get('target_below_within_5m')
    return None


def _mix(crit, weak):
    return {'normal':(1-crit)*(1-weak),'crit':crit*(1-weak),
            'weakspot':(1-crit)*weak,'crit_weakspot':crit*weak}


def _base_branches(profile, model):
    base = profile['damage_per_projectile']*profile['projectiles_per_shot']
    crit = profile['crit_damage_percent']/100
    weak = profile['weakspot_damage_percent']/100
    return {'normal':base,'crit':base*(1+crit),'weakspot':base*(1+weak),
            'crit_weakspot':base*(1+crit+weak if model=='additive' else (1+crit)*(1+weak))}


def _hit(branches, mix, values, model):
    weighted = {};hits = {}
    for branch, original in branches.items():
        all_bonus, weapon_bonus = values['all']/100, values['weapon']/100
        weak_bonus = values['weakspot']/100 if 'weakspot' in branch else 0
        crit_bonus = values['crit']/100 if 'crit' in branch else 0
        if model == 'additive': factor = 1+all_bonus+weapon_bonus+weak_bonus+crit_bonus
        else: factor = (1+all_bonus)*(1+weapon_bonus)*(1+weak_bonus)*(1+crit_bonus)
        hits[branch] = original*factor
        weighted[branch] = mix[branch]*hits[branch]
    return sum(weighted.values()),hits,weighted


def _audit_mod(identity, level, encounter, capabilities, range_end):
    resolved = catalog.resolve(identity, level)
    entry = resolved['entry']; trace = []; blockers = []
    values = {'all':0.0,'weapon':0.0,'weakspot':0.0,'crit':0.0,'magazine':0.0}
    source_ref = lambda attr: attr.get('source') or attr.get('source_image')
    if resolved.get('attribute_coverage') != 'complete':
        blockers.append(f"{entry['display_name']} Lv. {level}: fixed numeric subattributes incomplete")
    rule = RULES.get(f'{identity}:{level}')
    if rule is None:
        blockers.append(f"{entry['display_name']} Lv. {level}: main effect lacks an exact-level calculation rule; missing text is not zero")
    elif rule:
        rule_trace = {'rule_id':rule['rule_id'],'item':entry['display_name'],'kind':rule['kind'],
                      'component':rule['component'],'source':rule['source'],
                      'activation':None,'value_percent':None,'timing':rule.get('duration') or rule.get('duration_seconds')}
        if rule['rule_id']=='distant-strike-weakspot-lv10':
            if not resolved.get('verified_main_effect'):
                blockers.append('Distant Strike main effect has no exact-level visual verification')
            distance = encounter.get('distance_meters')
            if distance is None: blockers.append('Target distance is needed for Distant Strike activation')
            elif distance <= 20: rule_trace['activation']='inactive: target is not farther than 20 meters'
            else:
                values['weakspot'] += 20.0 + (20.0 if range_end=='upper' else 0.0)
                rule_trace.update(activation='active: target beyond 20 meters',value_percent=values['weakspot'],
                                  uncertainty=rule['uncertainty'])
        elif rule['rule_id']=='elemental-resonance-prev-mag-lv17':
            events = encounter.get('prior_magazine_elemental_events')
            if events == 0: rule_trace['activation']='inactive: zero elemental events in prior magazine'
            elif events is None: blockers.append('Prior-magazine elemental event count is required for Elemental Resonance')
            else: blockers.append('Elemental Resonance event timing and elemental/status damage remain unresolved')
        elif rule['rule_id']=='ferocious-charge-downstar-lv17':
            kills = encounter.get('nearby_kills')
            if kills == 0:rule_trace['activation']='inactive: no kill within 10 meters'
            elif kills is None:blockers.append('Nearby kill count is required for Ferocious Charge')
            else:blockers.append('Ferocious Charge eight-second buff uptime and stacking remain unresolved')
        elif rule['rule_id']=='against-all-odds-lv7':
            values['weapon'] += rule['base_percent']
            rule_trace.update(activation='base always listed; HP-consumption addition inactive' if encounter.get('hp_consumed') is False else
                              'base listed; HP-consumption condition unresolved',value_percent=rule['base_percent'])
            if encounter.get('hp_consumed') is not False:
                blockers.append('Against All Odds HP-consumption stacks need a no-consumption condition or event timeline')
        elif rule['rule_id']=='power-of-striving-lv9':
            values['weapon'] += rule['base_percent']
            rule_trace.update(activation='base always listed; stamina addition inactive' if encounter.get('stamina_spent') is False else
                              'base listed; stamina condition unresolved',value_percent=rule['base_percent'])
            if encounter.get('stamina_spent') is not False:
                blockers.append('Power of Striving stamina buff magnitude and uptime remain unresolved')
        trace.append(rule_trace)
    supported = {'All DMG Boost':'all','Weapon DMG':'weapon','Weakspot DMG':'weakspot',
                 'Crit DMG':'crit','Magazine Capacity':'magazine'}
    defensive = {'Max HP','Damage reduction after taking damage','Damage from monsters received'}
    elemental = {'Elemental DMG','Status DMG','Shock DMG','Power Surge DMG'}
    for attr in resolved.get('known_attributes') or []:
        name, value = attr['name'],attr.get('value_percent')
        row = {'rule_id':'field-guide-attribute','item':entry['display_name'],'component':name,
               'value_percent':value,'direction':attr.get('direction'),'unit':attr.get('unit'),
               'tier':attr.get('tier'),'source':source_ref(attr),'condition':attr.get('condition'),
               'conditional_bonus_percent':attr.get('conditional_bonus_percent')}
        if value is None or attr.get('unit')!='percent':
            blockers.append(f"{entry['display_name']}: {name} value or unit unresolved")
            row['activation']='unresolved';trace.append(row);continue
        if name in supported and attr.get('direction')=='increase':
            bonus=attr.get('conditional_bonus_percent')
            state=_condition(attr.get('condition'),encounter) if bonus is not None else False
            if bonus is not None and state is None:
                blockers.append(f"{entry['display_name']}: {name} conditional activation is unknown")
                row['activation']='base applied; conditional addition unresolved'
            else:
                row['activation']='base and condition applied' if state else 'unconditional base applied; condition inactive' if bonus is not None else 'unconditional'
            applied=value+(bonus if state is True else 0)
            values[supported[name]]+=applied
            row['applied_percent']=applied
        elif name in defensive:
            row['activation']='defensive only; no direct outgoing contribution'
        elif name in elemental:
            if capabilities['status_damage'] == 'absent_in_record' and capabilities['triggered_damage'] == 'absent_in_record' and encounter.get('prior_magazine_elemental_events')==0:
                row['activation']='no selected status/elemental damage source in defined encounter'
            else:
                blockers.append(f"{entry['display_name']}: {name} needs a status/elemental event model")
                row['activation']='unresolved event contribution'
        else:
            blockers.append(f"{entry['display_name']}: {name} has no supported outgoing rule")
            row['activation']='unresolved'
        trace.append(row)
    for effect in resolved.get('known_effects') or []:
        if effect.get('type')=='conditional_stat' and effect.get('stat')=='unknown_suffix_bonus':
            if entry.get('variant')=='Aero' and encounter.get('aerial_hit') is False:
                state='inactive: grounded';blocked=False
            elif 'Downstar' in str(entry.get('variant')) and encounter.get('same_elevation') is True:
                state='inactive: same elevation';blocked=False
            else:
                state='unresolved: condition or suffix magnitude could affect damage';blocked=True
            trace.append({'rule_id':'official-suffix-audit','item':entry['display_name'],
                          'component':effect.get('stat'),'activation':state,'source':effect.get('source')})
            if blocked:blockers.append(f"{entry['display_name']}: official suffix bonus magnitude or activation unresolved")
        elif effect.get('type')=='increase_stat' and effect.get('stat') in ('weapon_damage_percent','status_damage_percent') and rule:
            trace.append({'rule_id':'main-effect-structured-corroboration','item':entry['display_name'],
                          'component':effect['stat'],'activation':('covered by exact-level base rule; not counted twice' if rule['kind']=='base_plus_conditional_modifier' else
                              'candidate description; no value applied without active verified rule'),
                          'value_percent':effect.get('value'),'source':rule['source']})
        else:
            blockers.append(f"{entry['display_name']}: additional structured effect lacks an audited calculation rule")
    return values,trace,blockers


def _audit_side(slots, encounter, capabilities, range_end):
    values={'all':0.0,'weapon':0.0,'weakspot':0.0,'crit':0.0,'magazine':0.0}
    trace=[];blockers=[];sets=Counter()
    for slot,selection in slots.items():
        if not isinstance(selection,dict):continue
        gear=catalog.ENTRIES.get(selection.get('catalog_id'))
        if gear and gear['kind']=='armor':
            if gear.get('set_id'):sets[gear['set_id']]+=1
            armor_rule=ARMOR.get(gear['id'])
            if armor_rule and armor_rule['component']=='bounce_triggered_damage' and capabilities['triggered_damage']=='absent_in_record':
                trace.append({'rule_id':'armor-bounce-inactive','item':gear['name'],'component':armor_rule['component'],
                              'activation':'inactive for this direct-only source profile','source':armor_rule['source'],
                              'evidence_status':armor_rule['evidence_status']})
            else:
                blockers.append(f"{gear['name']}: standalone armor effect is not fully audited for this primary weapon")
        identity=selection.get('mod_id')
        if not identity:continue
        part,t,b=_audit_mod(identity,selection.get('mod_level'),encounter,capabilities,range_end)
        for key in values:values[key]+=part[key]
        trace.extend(t);blockers.extend(b)
    for set_id,count in sets.items():
        if set_id=='treacherous_tides_set' and count>=2:
            if count>=3:blockers.append('Treacherous Tides 3-piece stacking and HP interpolation unresolved')
            if encounter.get('scenario')!='PvE':blockers.append('Treacherous Tides PvE applicability not established for this scenario')
            hp=encounter.get('hp_fraction')
            if hp is None:blockers.append('HP fraction needed for Treacherous Tides')
            elif hp<.7:
                values['weapon']+=12
                trace.append({'rule_id':'treacherous_tides_two_weapon','component':'weapon_and_status_damage',
                              'value_percent':12,'activation':'active below 70% HP','source':OFFICIAL_TIDES})
            else:trace.append({'rule_id':'treacherous_tides_two_weapon','component':'weapon_and_status_damage',
                               'value_percent':0,'activation':'inactive at 70% HP or above','source':OFFICIAL_TIDES})
        else:
            set_record=catalog.ENTRIES.get('set:'+set_id.replace('_','-')) or {}
            for threshold in set_record.get('bonuses') or []:
                if count>=threshold['required_items']:
                    blockers.append(f"{set_record.get('name',set_id)} {threshold['required_items']}-piece current effect and interaction unverified")
    return values,trace,blockers


def compare_saved(left, right, encounter):
    """Return a conditional scoped recommendation for arbitrary supported mod swaps."""
    primary_left=(left.get('primary') or {}).get('catalog_id')
    primary_right=(right.get('primary') or {}).get('catalog_id')
    if not primary_left or primary_left!=primary_right:
        return {'eligible':False,'winner_established':False,'winner':None,'rows':[],
                'blockers':['Both builds must use the same selected primary weapon for a primary-fire swap estimate.']}
    profile=WEAPONS.get(primary_left)
    if not profile:
        return {'eligible':False,'winner_established':False,'winner':None,'rows':[],
                'blockers':['No sourced, explicit-setting weapon reference profile for '+primary_left],
                'capabilities':mechanics.weapon_capabilities(primary_left)}
    duration=_number(encounter.get('duration_seconds'),'duration_seconds',0.000001)
    distance=_number(encounter.get('distance_meters'),'distance_meters',0)
    crit=_number(encounter.get('crit_share',profile['crit_rate_percent']/100),'crit_share',0,1)
    weak=_number(encounter.get('weakspot_share'),'weakspot_share',0,1)
    context={**encounter,'distance_meters':distance}
    capability=mechanics.weapon_capabilities(primary_left)
    components=capability['capabilities']
    blockers=[]
    if components['direct_hit']!='present':
        blockers.append('Selected primary direct-hit capability is not established for this reference model.')
    if components['triggered_damage']=='present' or components['status_damage']=='present':
        blockers.append('Selected primary has sourced triggered/status damage; event rates and damage are not modeled.')
    if components['triggered_damage']=='unknown' or components['status_damage']=='unknown':
        blockers.append('Selected primary triggered/status damage capability is unknown; no family-name inference is allowed.')
    for capability_name in ('debuff','conditional_buff','firing_reload'):
        if components[capability_name] != 'absent_in_record':
            blockers.append(f"Selected primary {capability_name.replace('_',' ')} capability is not proven inactive or modeled.")
    if (left.get('primary') or {}) != (right.get('primary') or {}):
        blockers.append('Selected primary settings differ; equipment scaling is not modeled.')
    for side_name,slots in (('Left',left),('Right',right)):
        for slot,selection in slots.items():
            if not isinstance(selection,dict) or not selection.get('catalog_id'):continue
            if selection.get('legacy_enhancement') is not None or any(selection.get(key) not in (None,'',0) for key in
                   ('tier','stars','calibration_blueprint','calibration_bonus')):
                blockers.append(f'{side_name} {slot}: selected craft tier, blueprint stars, calibration roll, or legacy enhancement cannot be mapped to the unlabeled weapon reference profile.')
    if distance>profile['full_damage_range_meters']:
        blockers.append('Target is beyond the sourced full-damage range; falloff is not modeled.')
    if context.get('same_elevation') is True and context.get('target_below_within_5m') is True:
        raise ValueError('Target cannot be at the same elevation and lower within five meters')
    rows=[];left_trace=[];right_trace=[]
    mix=_mix(crit,weak)
    for base_model in ('additive','multiplicative'):
        branches=_base_branches(profile,base_model)
        for stacking in ('additive','multiplicative'):
            for rounding in ('floor','ceil'):
                for distant_bound in ('lower','upper'):
                    sides=[]
                    for slots in (left,right):
                        values,trace,side_blockers=_audit_side(slots,context,components,distant_bound)
                        blockers.extend(side_blockers)
                        if slots is left:left_trace=trace
                        else:right_trace=trace
                        per_hit,hits,weighted=_hit(branches,mix,values,stacking)
                        raw_mag=profile['magazine']*(1+values['magazine']/100)
                        magazine=max(1,floor(raw_mag) if rounding=='floor' else ceil(raw_mag))
                        shots,cycle=_shots(duration,profile['rpm'],magazine,profile['reload_seconds'])
                        burst=magazine*per_hit
                        sides.append({'modifiers_percent':values,'branch_hit_damage':{k:round(v,4) for k,v in hits.items()},
                                      'weighted_branch_damage':{k:round(v,4) for k,v in weighted.items()},
                                      'damage_per_hit':round(per_hit,4),'magazine':magazine,'cycle_seconds':round(cycle,4),
                                      'shots':shots,'burst_damage':round(burst,4),
                                      'burst_dps':round(burst/(magazine*60/profile['rpm']),4),
                                      'sustained_damage':round(shots*per_hit,4),
                                      'sustained_dps':round(shots*per_hit/duration,4),
                                      'triggered_damage':0 if components['triggered_damage']=='absent_in_record' else None,
                                      'status_damage':0 if components['status_damage']=='absent_in_record' else None})
                    winner=lambda metric:'left' if sides[0][metric]>sides[1][metric]+1e-8 else 'right' if sides[1][metric]>sides[0][metric]+1e-8 else 'tie'
                    rows.append({'base_crit_weak_model':base_model,'stacking_model':stacking,
                                 'magazine_rounding':rounding,'distant_extra_bound':distant_bound,
                                 'left':sides[0],'right':sides[1],
                                 'winner':winner('sustained_damage'),'burst_winner':winner('burst_damage')})
    blockers=list(dict.fromkeys(blockers))
    winners={row['winner'] for row in rows};burst_winners={row['burst_winner'] for row in rows}
    established=not blockers and len(winners)==1 and len(burst_winners)==1
    winner=next(iter(winners)) if established else None
    return {'eligible':True,'selection_origin':'two saved catalog builds; ownership not asserted',
            'selected_primary':profile['name'],'weapon_profile':profile,'capabilities':capability,
            'target':context,'duration_seconds':duration,'branch_mix':mix,
            'rows':rows,'winner_established':established,'winner':winner,
            'burst_winner':next(iter(burst_winners)) if established else None,
            'winner_scope':'conditional reference-profile primary outgoing; full-build winner unresolved' if established else 'unresolved',
            'recommendation':('Use the '+('left' if winner=='left' else 'right')+' saved mod selection for this stated encounter and reference profile.' if winner in ('left','right') else
                              'The selected choices tie within every evaluated row.' if winner=='tie' else None),
            'blockers':blockers,'trace':{'left':left_trace,'right':right_trace},
            'model_assumptions':['Weapon damage and crit/weak statistics are from a current client-derived reference profile whose gear tier and calibration are unlabeled; this is not the player\'s crafted weapon damage.',
                                 'Both saved builds use the same primary and target. No unrecorded passive, calibration, cradle, food, or teammate effect changes between versions.',
                                 'Crit and weak-spot shares are independent encounter inputs. Combined-hit and modifier stacking are evaluated under additive and multiplicative models.',
                                 'First shot at t=0; a full magazine consumes magazine × 60/RPM seconds before reload. Magazine percentage rounding is bounded by floor and ceil.',
                                 'The official Shiny screenshots supply Lv. 17 subattributes. Their Flash bonuses are excluded from ordinary planned mods.',
                                 'No current effect is inferred from a historical set bonus or an empty catalog effect field.'],
            'unresolved_mechanics':['Absolute target defense and weapon tier/calibration scaling','Exact modifier stacking and magazine rounding','SN700 undocumented proc/status behavior or changes to the historical Hot Dog Shorts Bounce-only effect could reverse a full-build result','Unrecorded passive interactions from other equipment']}
