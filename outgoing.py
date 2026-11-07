"""Scoped outgoing-damage comparison using current catalog values and explicit assumptions.

This module never reads or writes owned inventory. It only claims a winner across
the displayed sensitivity models when every effect relevant to the example is
calculated or proven inactive by its encounter inputs.
"""
from math import ceil, floor
import catalog

EXAMPLE={
    'label':'Illustrative direct-only primary against one stationary PvE target',
    'left':{'catalog_id':'mod:boots_mod:against-all-odds-precision','level':7},
    'right':{'catalog_id':'mod:boots_mod:power-of-striving-downstar-deviant-energy','level':9},
    'weapon':{'normal_hit':100.0,'crit_hit':150.0,'weakspot_hit':200.0,'crit_weakspot_hit':300.0,'rpm':600.0,'magazine':20,'reload_seconds':2.0,'proc_source':False,'status_source':False},
    'target':{'label':'one stationary PvE target; same defense and range for both choices','crit_share':0.2,'weakspot_share':0.2,'same_elevation':True,'stamina_spent':False,'hp_lost':False},
    'duration_seconds':40.0,
}
SOURCES={
    'against_official':'https://www.oncehuman.game/news/devBlog/20250922/40781_1260687.html',
    'striving_official':'https://www.oncehuman.game/news/update/20250110/40780_1205980.html',
    'downstar_official':'https://www.oncehuman.game/news/devBlog/20260522/40781_1301328.html',
    'field_guide_official':'https://www.oncehuman.game/news/devBlog/20251212/40781_1276354.html',
}

def _number(value,name,minimum=0,maximum=None):
    value=float(value)
    if value<minimum or maximum is not None and value>maximum:raise ValueError(f'{name} outside allowed range')
    return value

def _shots(duration,rpm,magazine,reload_seconds):
    """Example timing convention: first shot at t=0, cycle ends after mag/RPM + reload."""
    interval=60/rpm;cycle=magazine*interval+reload_seconds
    full=floor(duration/cycle)
    remainder=duration-full*cycle
    # A shot exactly at t=duration belongs to the next interval.
    partial=min(magazine,max(0,ceil((remainder-1e-10)/interval)))
    return full*magazine+partial,cycle

def _resolved(choice):
    result=catalog.resolve(choice['catalog_id'],int(choice['level']))
    return result

def _effects(result,context,weapon):
    entry=result['entry'];identity=entry['id'];blockers=[];trace=[]
    if result.get('attribute_coverage')!='complete':blockers.append('Four numeric attributes are not fully resolved for '+identity)
    verified_main=result.get('verified_main_effect')
    if not verified_main:blockers.append('Main effect has no same-level native-frame verification for '+identity)
    structured=result.get('known_effects') or []
    main=[x for x in structured if x.get('type')=='increase_stat']
    main_by_stat={x.get('stat'):x.get('value') for x in main}
    if main_by_stat!={'weapon_damage_percent':10.0,'status_damage_percent':10.0}:
        blockers.append('Main effect is not the verified +10% Weapon/Status baseline')
    else:
        trace.append({'kind':'game_rule','component':'direct_weapon','value_percent':10.0,'source':verified_main['source_image'] if verified_main else entry.get('source_url'),'corroboration':SOURCES['against_official'] if 'against-all-odds' in identity else SOURCES['striving_official'],'reason':'This exact Field Guide level shows +10% Weapon DMG; Status DMG branch is absent from this example weapon.'})
    if 'against-all-odds' in identity:
        if context['hp_lost']:blockers.append('Against All Odds extra buff after HP loss has unresolved stack timing and uptime.')
        else:trace.append({'kind':'proven_inactive','component':'after_hp_loss','source':SOURCES['against_official'],'reason':'No HP was lost during the example encounter.'})
    elif 'power-of-striving' in identity:
        if context['stamina_spent']:blockers.append('Power of Striving extra buff from stamina loss has unresolved magnitude and uptime.')
        else:trace.append({'kind':'proven_inactive','component':'after_stamina_loss','source':SOURCES['striving_official'],'reason':'No stamina was spent during the example encounter.'})
        if not context['same_elevation']:blockers.append('Downstar suffix magnitude and interaction at different elevations remain unresolved.')
        else:trace.append({'kind':'proven_inactive','component':'downstar_suffix','source':SOURCES['downstar_official'],'reason':'Target and player are at the same elevation.'})
    else:blockers.append('Main-effect condition has no supported example rule')
    if weapon['proc_source'] is None or weapon['status_source'] is None:
        blockers.append('Selected weapon triggered/status capability is unknown; a family label cannot prove absence.')
    if weapon['proc_source'] or weapon['status_source']:
        blockers.append('Proc/status event rates and damage are required for this weapon; elemental and status bonuses could change the winner.')
    elif weapon['proc_source'] is False and weapon['status_source'] is False:
        trace.append({'kind':'proven_inactive','component':'proc_and_status','source':'example weapon input','reason':'The explicitly defined illustrative weapon has no proc or status source; these components contribute zero.'})
    values={'weapon_damage':0.0,'weakspot_damage':0.0,'all_damage':0.0,'magazine_capacity':0.0}
    allowed={'Weapon DMG':'weapon_damage','Weakspot DMG':'weakspot_damage','All DMG Boost':'all_damage','Magazine Capacity':'magazine_capacity'}
    inactive={'Elemental DMG','Status DMG','Max HP'}
    for attr in result.get('known_attributes') or []:
        name=attr['name'];value=attr.get('value_percent');source=attr.get('source')
        if value is None or attr.get('unit')!='percent' or attr.get('direction')!='increase':
            blockers.append(name+' value, unit, or direction unresolved');continue
        if name in allowed:
            if attr.get('conditional_bonus_percent') is not None:blockers.append(name+' conditional bonus is not covered by this example')
            values[allowed[name]]+=value
            trace.append({'kind':'game_rule','component':allowed[name],'value_percent':value,'source':source,'reason':'Current Field Guide subattribute.'})
        elif name in inactive:
            if name=='Max HP' or not (weapon['proc_source'] or weapon['status_source']):
                trace.append({'kind':'proven_inactive','component':name,'value_percent':value,'conditional_bonus_percent':attr.get('conditional_bonus_percent'),'source':source,'reason':'Max HP does not alter outgoing damage' if name=='Max HP' else 'No elemental or status damage source in this example.'})
            else:blockers.append(name+' contribution needs proc/status event model')
        else:blockers.append(name+' has no supported outgoing calculation rule')
    return values,trace,blockers

def _branch_mix(crit_share,weakspot_share):
    return {'normal':(1-crit_share)*(1-weakspot_share),'crit':crit_share*(1-weakspot_share),'weakspot':(1-crit_share)*weakspot_share,'crit_weakspot':crit_share*weakspot_share}

def _per_hit(weapon,mix,values,model):
    base=weapon['normal_hit'];branches={};contributions={'normal':0.0,'crit':0.0,'weakspot':0.0,'crit_weakspot':0.0}
    for branch,share in mix.items():
        unbuffed=weapon[branch+'_hit'] if branch!='normal' else base
        main=.10;all_bonus=values['all_damage']/100;weapon_bonus=values['weapon_damage']/100
        weak_bonus=values['weakspot_damage']/100 if 'weakspot' in branch else 0
        if model=='additive':dam=unbuffed*(1+main+all_bonus+weapon_bonus+weak_bonus)
        elif model=='multiplicative':dam=unbuffed*(1+main)*(1+all_bonus)*(1+weapon_bonus)*(1+weak_bonus)
        elif model=='conservative_branch':
            # Deliberate lower-end sensitivity: unique Weapon DMG only on normal
            # body hits; Weakspot DMG only adds a normal-base amount on noncrit
            # weak-spot hits. This is an assumption, not a game formula.
            dam=unbuffed*(1+main+all_bonus)
            if branch=='normal':dam+=unbuffed*weapon_bonus
            if branch=='weakspot':dam+=base*weak_bonus
        else:raise ValueError('Unknown stacking model')
        branches[branch]=round(dam,6)
        contributions[branch]=round(share*dam,6)
    return round(sum(contributions.values()),6),branches,contributions

def compare_catalog_outgoing(left_choice,right_choice,weapon,target,duration_seconds):
    """Compare two catalog choices for a direct-only example; no inventory write."""
    left=_resolved(left_choice);right=_resolved(right_choice)
    if left['entry']['slot']!=right['entry']['slot']:raise ValueError('Offensive choices must use the same slot')
    weapon={**weapon};target={**target}
    for key in ('normal_hit','crit_hit','weakspot_hit','crit_weakspot_hit','rpm','reload_seconds'):
        weapon[key]=_number(weapon[key],key,0 if key=='reload_seconds' else 0.000001)
    weapon['magazine']=int(_number(weapon['magazine'],'magazine',1))
    for key in ('crit_share','weakspot_share'):target[key]=_number(target[key],key,0,1)
    for key in ('same_elevation','stamina_spent','hp_lost'):target[key]=bool(target[key])
    duration=_number(duration_seconds,'duration seconds',0.000001)
    lv,lt,lb=_effects(left,target,weapon);rv,rt,rb=_effects(right,target,weapon)
    blockers=lb+rb
    mix=_branch_mix(target['crit_share'],target['weakspot_share'])
    rows=[]
    for model in ('additive','multiplicative','conservative_branch'):
        for rounding in ('floor','ceil'):
            sides=[]
            for resolved,values in ((left,lv),(right,rv)):
                raw_mag=weapon['magazine']*(1+values['magazine_capacity']/100)
                magazine=max(1,floor(raw_mag) if rounding=='floor' else ceil(raw_mag))
                per_hit,branch_hits,weighted=_per_hit(weapon,mix,values,model)
                shots,cycle=_shots(duration,weapon['rpm'],magazine,weapon['reload_seconds'])
                firing_window=magazine*60/weapon['rpm']
                contributions={}
                for key in ('all_damage','weapon_damage','weakspot_damage'):
                    without={**values,key:0.0}
                    without_hit=_per_hit(weapon,mix,without,model)[0]
                    contributions[key]={'modifier_percent':values[key],'per_hit_increment':round(per_hit-without_hit,6),'sustained_increment':round(shots*(per_hit-without_hit),4)}
                base_mag=weapon['magazine'];base_shots=_shots(duration,weapon['rpm'],base_mag,weapon['reload_seconds'])[0]
                contributions['magazine_capacity']={'modifier_percent':values['magazine_capacity'],'shot_increment':shots-base_shots,'raw_magazine':round(raw_mag,4)}
                sides.append({'catalog_id':resolved['entry']['id'],'name':resolved['entry'].get('display_name') or resolved['entry']['name'],'level':resolved['level'],'magazine':magazine,'raw_magazine':round(raw_mag,4),'cycle_seconds':round(cycle,4),'shots':shots,'first_magazine_seconds':round(firing_window,4),'branch_hit_damage':branch_hits,'weighted_branch_damage':weighted,'damage_per_hit':per_hit,'effect_contributions':contributions,'burst_damage':round(magazine*per_hit,4),'burst_dps':round(magazine*per_hit/firing_window,4),'sustained_damage':round(shots*per_hit,4),'sustained_dps':round(shots*per_hit/duration,4),'proc_damage':0,'status_damage':0})
            winner='left' if sides[0]['sustained_damage']>sides[1]['sustained_damage'] else 'right' if sides[1]['sustained_damage']>sides[0]['sustained_damage'] else 'tie'
            rows.append({'stacking_model':model,'magazine_rounding':rounding,'left':sides[0],'right':sides[1],'winner':winner,'burst_winner':'left' if sides[0]['burst_damage']>sides[1]['burst_damage'] else 'right' if sides[1]['burst_damage']>sides[0]['burst_damage'] else 'tie'})
    winners={r['winner'] for r in rows};burst_winners={r['burst_winner'] for r in rows}
    established=not blockers and len(winners)==1 and len(burst_winners)==1
    winner=next(iter(winners)) if established else None
    min_power_bonus=min((r['left']['sustained_damage']/r['right']['sustained_damage']-1)*100 for r in rows if r['right']['sustained_damage']>0)
    return {'selection_origin':'catalog example; ownership not asserted or saved','left_choice':left_choice,'right_choice':right_choice,'weapon':weapon,'target':target,'duration_seconds':duration,'branch_mix':mix,'source_rules':SOURCES,'model_assumptions':['Unbuffed branch-hit values and firing timing are illustrative encounter inputs, not weapon catalog statistics.','Crit and weak-spot shares are independent for this example; change either input to inspect sensitivity.','First shot occurs at t=0; reload begins after a full firing interval for the last magazine shot.','Listed percentage bonuses are evaluated under additive, multiplicative, and conservative branch-application models; their true game stacking order is unresolved.','Magazine capacity uses floor and ceil bounds because in-game rounding is unverified.','No other gear buffs, target vulnerabilities, proc events, status events, HP loss, or stamina expenditure apply.'],'trace':{'left':lt,'right':rt},'rows':rows,'blockers':blockers,'winner_established':established,'winner':winner,'burst_winner':next(iter(burst_winners)) if established else None,'winner_scope':'Conditional outgoing damage for this direct-only example across the displayed sensitivity models' if established else 'unresolved','unmodeled_power_bonus_to_reverse_percent':round(min_power_bonus,4),'unresolved_mechanics':['Exact cross-bucket damage stacking','Exact magazine rounding','Application of Weapon and Weakspot modifiers to critical branches','Real weapon and target behavior outside the illustrative inputs'],'numeric_coverage':{'left':left.get('attribute_coverage'),'right':right.get('attribute_coverage')}}

def run_example(overrides=None):
    overrides=overrides or {}
    target={**EXAMPLE['target'],**(overrides.get('target') or {})}
    weapon={**EXAMPLE['weapon'],**(overrides.get('weapon') or {})}
    duration=overrides.get('duration_seconds',EXAMPLE['duration_seconds'])
    result=compare_catalog_outgoing(EXAMPLE['left'],EXAMPLE['right'],weapon,target,duration)
    result['example_label']=EXAMPLE['label']
    return result
