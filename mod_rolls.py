"""Source-linked mod-roll variables and assumption-labelled component math.

This module never infers ownership or game stacking. It parses visible Field Guide
rows into independent variables; unsupported rows retain their raw text.
"""
from __future__ import annotations
from collections import Counter
from math import ceil, floor, isfinite
import re


def observed_row_order_conflict(stats):
    """Two presented source lists must agree exactly before either can be activated.

    Different values, missing rows and changed order all leave the source truth
    unresolved.  A single source list is still allowed on its own.
    """
    if not isinstance(stats, dict):
        return False
    observed = stats.get('observed_attribute_lines')
    tooltip = (stats.get('observed_tooltip') or {}).get('attribute_lines')
    return (isinstance(observed, list) and isinstance(tooltip, list)
            and observed != tooltip)

PERCENT=re.compile(r'([0-9]+(?:\.[0-9]+)?)\s*%')
KINDS=(
 ('power_surge_damage_percent',r'^Power Surge DMG\s*\+'),
 ('power_surge_trigger_chance_percent',r'^Power Surge Trigger Chance\s*\+'),
 ('shock_damage_percent',r'^Shock DMG\s*\+'),
 ('elemental_damage_percent',r'^Element \(Blaze, Frost, Shock, Blast\) DMG\s*\+'),
 ('status_damage_percent',r'^Status DMG\s*\+'),
 ('magazine_capacity_percent',r'^Magazine Capacity\s*\+'),
 ('all_damage_boost_percent',r'^Increases damage dealt to all DMG Boost by\s*\+'),
 ('all_damage_boost_percent',r'^All DMG Boost\s*\+'),
 ('weapon_damage_percent',r'^Weapon DMG\s*\+'),
 ('weakspot_damage_percent',r'^Weakspot DMG\s*\+'),
 ('crit_damage_percent',r'^Crit DMG\s*\+'),
 ('max_hp_percent',r'^Max HP\s*\+'),
 ('generic_damage_percent',r'^DMG\s*\+\+'),
 ('reload_efficiency_percent',r'^Reload Efficiency\s*\+'),
 ('after_hit_damage_reduction_percent',r'^Additional damage inflicted after hitting a unit is reduced by'),
 ('after_damage_reduction_percent',r'^Receive a DMG Reduction'),
 ('metas_kill_heal_percent',r'^Defeating Metas recovers'),
 ('monster_damage_direction_ambiguous',r'^Damage from monsters'),
)
APPLICABILITY={
 'power_surge_damage_percent':['Power Surge event; scaling unverified'],
 'power_surge_trigger_chance_percent':['Power Surge trigger; relative versus points unverified'],
 'shock_damage_percent':['Shock damage; event and bucket unverified'],
 'elemental_damage_percent':['Blaze','Frost','Shock','Blast'],
 'status_damage_percent':['status_damage'], 'magazine_capacity_percent':['magazine'],
 'all_damage_boost_percent':['outgoing_damage'], 'weapon_damage_percent':['weapon_damage'],
 'weakspot_damage_percent':['weakspot_hit'], 'crit_damage_percent':['critical_hit'],
 'max_hp_percent':['health'], 'generic_damage_percent':['unknown_damage_bucket'],
 'reload_efficiency_percent':['final_reload_time'],
 'after_hit_damage_reduction_percent':['incoming_damage_conditional'],
 'after_damage_reduction_percent':['incoming_damage_conditional'],
 'metas_kill_heal_percent':['health_on_metas_kill'],
 'monster_damage_direction_ambiguous':['incoming_monster_damage'],
}
SCENARIO_TYPES={'elemental_damage_percent','status_damage_percent','magazine_capacity_percent','all_damage_boost_percent','weapon_damage_percent','crit_damage_percent','weakspot_damage_percent','reload_efficiency_percent','max_hp_percent'}
ALL_DAMAGE_MODELS={'exclude_unverified','independent_outgoing_multiplier'}
NON_OFFENSIVE_TYPES={'max_hp_percent','after_damage_reduction_percent',
                     'metas_kill_heal_percent','monster_damage_direction_ambiguous',
                     'healing_or_shield_unmodeled'}


def may_affect_offense(row):
    """Conservative scope guard: only explicitly defensive/health rows leave damage intact."""
    return row.get('stat_type') not in NON_OFFENSIVE_TYPES


def _percent(text):
    match=PERCENT.search(text)
    return float(match.group(1)) if match else None


def _condition(kind, text):
    if kind=='after_hit_damage_reduction_percent':return 'after hitting a unit, for the stated duration'
    if kind=='after_damage_reduction_percent':return 'after taking damage; duration and cooldown as displayed'
    if kind=='metas_kill_heal_percent':return 'after defeating a Meta'
    if kind=='monster_damage_direction_ambiguous':return 'when receiving monster damage; sign unresolved'
    return 'unconditional listed roll'


def parse_rows(rows, *, proposal_id=None, source=None, source_audit=None):
    if not isinstance(rows,list):raise ValueError('Attribute rows must be a list')
    audit=source_audit or {};verified=str(audit.get('status') or '').startswith('source_text_and_numbers_checked')
    audited=[x.get('source_text') for x in audit.get('attribute_rows') or []]
    output=[]
    for index,original in enumerate(rows):
        if not isinstance(original,str):raise ValueError('Attribute row must be text')
        text=original.strip();kind=next((name for name,pattern in KINDS if re.search(pattern,text,re.I)), 'unparsed')
        magnitude=_percent(text)
        ambiguous=kind=='monster_damage_direction_ambiguous' and any(mark in text for mark in ('−+','—+','-+'))
        if kind=='monster_damage_direction_ambiguous':ambiguous=True
        direction='ambiguous' if ambiguous else 'reduction' if kind in ('after_hit_damage_reduction_percent','after_damage_reduction_percent') else 'increase' if kind!='unparsed' else 'unknown'
        confidence='source_checked' if verified and len(audited)>index and audited[index]==text else 'ocr_unverified'
        supported=kind in SCENARIO_TYPES and magnitude is not None and direction=='increase' and confidence=='source_checked'
        output.append({'row_index':index,'stat_type':kind,
                       'value':None if ambiguous or kind=='unparsed' else magnitude,
                       'visible_magnitude':magnitude,'unit':'percent' if magnitude is not None else 'unknown',
                       'direction':direction,'condition':_condition(kind,text),
                       'applicability':APPLICABILITY.get(kind,[]),
                       'calculation_status':'assumption_scenario' if supported else 'excluded_ambiguous' if ambiguous else 'unmodeled',
                       # Source-checked text and magnitude do not establish whether
                       # the row is active at this scenario's Tech level.
                       'tech_activation':'unknown',
                       'confidence':confidence,'raw_text':text,
                       'evidence':{'proposal_id':proposal_id,'source_frame':(source or {}).get('frame'),
                                   'source_tooltip':(source or {}).get('tooltip'),'timestamp':(source or {}).get('timestamp')}})
    return output


def proposal_modifiers(data, proposal_id=None):
    return parse_rows(data.get('attribute_rows') or [],proposal_id=proposal_id,
                      source=data.get('source'),source_audit=data.get('source_audit'))


def _number(value,name,positive=False):
    if value is None or value=='':return None
    if isinstance(value,bool):raise ValueError(name+' must be numeric')
    try:n=float(value)
    except (ValueError,TypeError):raise ValueError(name+' must be numeric') from None
    if not isfinite(n) or n<0 or positive and n==0:raise ValueError(name+' is outside the supported range')
    return n


def aggregate(modifiers, *, tech_policy='exclude_unknown', all_damage_model='exclude_unverified'):
    """Sum eligible rows; Tech and All DMG bucket placement need separate opt-ins."""
    if tech_policy not in ('exclude_unknown','assume_active'):
        raise ValueError('Tech activation policy must exclude unknown rows or assume them active')
    if all_damage_model not in ALL_DAMAGE_MODELS:
        raise ValueError('Unknown All DMG Boost model')
    values={kind:0.0 for kind in SCENARIO_TYPES};unmodeled=[];used=[];tech_gated=[]
    for row in modifiers:
        if row.get('stat_type')=='all_damage_boost_percent' and all_damage_model=='exclude_unverified':
            unmodeled.append({**row,'model_exclusion':'Observed magnitude retained; placement among target-category and other damage buckets is unverified.'})
            continue
        magnitude=row.get('value')
        numeric=isinstance(magnitude,(int,float)) and not isinstance(magnitude,bool) and isfinite(magnitude) and magnitude>=0
        checked=(row.get('confidence')=='source_checked' or
                 row.get('confidence')=='user_entered_hypothetical' and
                 row.get('external_hypothesis_confirmed') is True)
        if (row.get('calculation_status')=='assumption_scenario' and checked
                and row.get('stat_type') in values and numeric):
            activation=row.get('tech_activation','unknown')
            if row.get('external_hypothesis_confirmed') is True:
                values[row['stat_type']]+=row['value'];used.append(row)
            elif activation=='verified_active' and row.get('tech_activation_evidence'):
                values[row['stat_type']]+=row['value'];used.append(row)
            elif activation!='verified_inactive' and tech_policy=='assume_active':
                values[row['stat_type']]+=row['value'];used.append(row)
            else:tech_gated.append(row)
        else:unmodeled.append(row)
    return {'percent_by_type':values,'used_rows':used,'unmodeled_rows':unmodeled,
            'tech_gated_rows':tech_gated,'tech_policy':tech_policy,'all_damage_model':all_damage_model,
            'tech_activation_assumption':'Unknown Tech-level rows were assumed active for this what-if only.' if tech_policy=='assume_active' else 'Unknown Tech-level rows were excluded; zero here does not mean the roll is absent.',
            'stacking_assumption':('All DMG Boost is excluded until an explicit independent-outgoing-multiplier hypothetical is selected. Its observed value is not a verified stacking rule.' if all_damage_model=='exclude_unverified' else
                                   'Hypothetical: All DMG Boost is an independent outgoing multiplier. Its interaction with target-category bonuses and actual game bucket order is unverified.')}


def max_hp_sensitivity(values, baseline=None, *, confirmed_pre_mod=False):
    """Isolated health what-if, never an inferred damage or survivability total."""
    bonus=values['percent_by_type']['max_hp_percent']
    selected=any(row.get('stat_type')=='max_hp_percent' for row in values['used_rows']+values['tech_gated_rows']+values['unmodeled_rows'])
    base=_number(baseline,'pre-mod Max HP',True)
    if base is not None and confirmed_pre_mod is not True:
        raise ValueError('Confirm that Max HP is measured before selected mod rolls')
    return {'pre_mod_max_hp':base,'after_unrounded':base*(1+bonus/100) if base is not None else None,
            'bonus_percent':bonus,'has_selected_max_hp_roll':selected,
            'missing':['pre-mod Max HP'] if selected and base is None else [],
            'assumption':'Same-type Max HP percentages sum in this isolated sensitivity; game stacking and HP rounding are unverified. No damage reduction, healing, shield or DPS effect is inferred.',
            'tech_policy':values['tech_policy']}


def scenario(modifiers, inputs):
    """Compute component sensitivities from a confirmed pre-mod baseline.

    Elemental and status streams stay separate: callers must not add them
    together unless their measured events are disjoint.
    """
    if not isinstance(inputs,dict):raise ValueError('Scenario inputs must be an object')
    origin=inputs.get('base_origin')
    if origin!='pre_mod_unbuffed':
        return {'supported':False,'reason':'A pre-mod unbuffed component baseline is required; observed equipped values may already include these rolls.',
                'modifiers':aggregate(modifiers,tech_policy=inputs.get('tech_policy','exclude_unknown'),all_damage_model=inputs.get('all_damage_model','exclude_unverified')),'component_results':None}
    values=aggregate(modifiers,tech_policy=inputs.get('tech_policy','exclude_unknown'),all_damage_model=inputs.get('all_damage_model','exclude_unverified'));p=values['percent_by_type']
    health=max_hp_sensitivity(values,inputs.get('pre_mod_max_hp'),confirmed_pre_mod=inputs.get('max_hp_excludes_selected_mods') is True)
    hit=_number(inputs.get('base_direct_hit'),'base direct hit',True)
    rpm=_number(inputs.get('rpm'),'RPM',True)
    magazine=_number(inputs.get('magazine'),'magazine',True)
    reload_seconds=_number(inputs.get('reload_seconds'),'reload seconds')
    final_reload_seconds=reload_seconds/(1+p['reload_efficiency_percent']/100) if reload_seconds is not None else None
    elemental=_number(inputs.get('elemental_event_damage'),'elemental event damage')
    status=_number(inputs.get('status_event_damage'),'status event damage')
    elemental_rate=_number(inputs.get('elemental_events_per_second'),'elemental events/s')
    status_rate=_number(inputs.get('status_events_per_second'),'status events/s')
    all_factor=1+p['all_damage_boost_percent']/100
    elemental_factor=all_factor*(1+p['elemental_damage_percent']/100)
    status_factor=all_factor*(1+p['status_damage_percent']/100)
    raw_mag=magazine*(1+p['magazine_capacity_percent']/100) if magazine is not None else None
    mag_bounds={'floor':max(1,floor(raw_mag)),'ceil':max(1,ceil(raw_mag))} if raw_mag is not None else None
    base_firing=rpm/60 if rpm is not None else None
    # Weapon DMG is a separate assumed bucket from All DMG in this isolated
    # scenario, mirroring the explicit placement in combat_formula.
    weapon_factor=1+p['weapon_damage_percent']/100
    direct_hit=hit*weapon_factor*all_factor if hit is not None else None
    direct_firing_dps=direct_hit*base_firing if direct_hit is not None and base_firing is not None else None
    base_firing_dps=hit*base_firing if hit is not None and base_firing is not None else None
    sustained={}
    if None not in (hit,rpm,magazine,reload_seconds):
        for policy,mag in mag_bounds.items():
            rate=(rpm/60)*mag/(mag+(rpm/60)*final_reload_seconds)
            baseline_rate=(rpm/60)*magazine/(magazine+(rpm/60)*reload_seconds)
            sustained[policy]={'magazine':mag,'shots_per_second':rate,'direct_dps':direct_hit*rate,
                               'baseline_direct_dps':hit*baseline_rate}
    event_results={
      'elemental':{'factor':elemental_factor,'base_damage':elemental,'after_damage':elemental*elemental_factor if elemental is not None else None,
                   'dps':elemental*elemental_factor*elemental_rate if elemental is not None and elemental_rate is not None else None},
      'status':{'factor':status_factor,'base_damage':status,'after_damage':status*status_factor if status is not None else None,
                'dps':status*status_factor*status_rate if status is not None and status_rate is not None else None},
    }
    return {'supported':True,'modifiers':values,'component_results':{
        'direct_hit':direct_hit,'baseline_direct_hit':hit,'weapon_factor':weapon_factor,'direct_firing_dps':direct_firing_dps,
        'baseline_firing_dps':base_firing_dps,'magazine_unrounded':raw_mag,'magazine_bounds':mag_bounds,
        'reload_seconds_before_efficiency':reload_seconds,'reload_seconds_after_efficiency':final_reload_seconds,
        'sustained_direct_bounds':sustained or None,'event_streams':event_results,'max_hp_sensitivity':health},
        'missing':(['All DMG Boost bucket placement' for row in values['unmodeled_rows'] if row.get('model_exclusion')]+[name for name,value in [('pre-mod direct hit',hit),('RPM',rpm),('magazine',magazine),('reload seconds',reload_seconds),
                   ('elemental event damage and rate',elemental if elemental_rate is not None else None),
                   ('status event damage and rate',status if status_rate is not None else None)] if value is None]),
        'assumptions':[values['stacking_assumption']+' Weapon DMG affects direct hits; elemental and status bonuses affect only their classified event streams.',
                       values['tech_activation_assumption'],
                       'This is an isolated incremental scenario, not a verified Once Human stacking formula or measured DPS.',
                       'Magazine rounding is shown as floor and ceil because the game rounding rule is unverified.',
                       'Source-checked Reload Efficiency divides final reload time by (1 + bonus); the entered reload time is before this roll. Official May 2025 rule: https://www.oncehuman.game/news/update/20250521/40780_1235763.html . Reload Speed is a distinct label and is not inferred from this row.',
                       'Event streams are separate; total damage is withheld unless overlap, proc frequency and other effects are established.',
                       'Already-modified observed damage must not be used as a pre-mod input.']}


def equipped_build_modifiers(slots, owned_inventory, *, active_weapon_slot='primary'):
    """Resolve saved mod selections to owned instances without guessing duplicates.

    A catalog+level match is safe only if it is unique. Future selections can
    carry mod_inventory_id to disambiguate same-identity instances.
    """
    if not isinstance(slots,dict) or not isinstance(owned_inventory,list):
        raise ValueError('Saved build slots and owned inventory are required')
    if active_weapon_slot not in ('primary','secondary','melee'):
        raise ValueError('Active weapon slot must be primary, secondary or melee')
    selected=[];issues=[];ignored_slots=[];instance_slots={}
    for slot,selection in slots.items():
        if not isinstance(selection,dict) or not selection.get('mod_id'):continue
        if slot in ('primary','secondary','melee') and slot!=active_weapon_slot:
            ignored_slots.append(slot)
            continue
        catalog_id=selection['mod_id'];level=selection.get('mod_level')
        instance_id=selection.get('mod_inventory_id')
        catalog_matches=[item for item in owned_inventory if item.get('kind')=='mod_unlock'
                    and (item.get('effects') or {}).get('catalog_id')==catalog_id]
        candidates=[item for item in catalog_matches
                    if (level is None or item.get('level')==level)
                    and (instance_id is None or item.get('id')==instance_id)]
        if len(candidates)!=1:
            level_mismatch=not candidates and bool(catalog_matches) and level is not None and all(item.get('level')!=level for item in catalog_matches)
            issues.append({'slot':slot,'mod_id':catalog_id,
                           'reason':'owned instance level does not match saved mod level' if level_mismatch else 'owned instance missing' if not candidates else 'multiple owned instances; select exact instance',
                           'code':'owned_level_mismatch' if level_mismatch else 'owned_instance_missing' if not candidates else 'multiple_owned_instances',
                           'selected_level':level,'available_levels':sorted({item['level'] for item in catalog_matches if isinstance(item.get('level'),int)}),
                           'matching_instances':len(candidates)})
            continue
        item=candidates[0];stats=item.get('stats') or {};mods=stats.get('typed_modifiers')
        if item['id'] in instance_slots:
            prior=instance_slots[item['id']]
            selected=[m for m in selected if m['owned_instance_id']!=item['id']]
            issues.extend(({'slot':prior,'mod_id':catalog_id,'reason':'one owned instance is selected in multiple active slots'},
                           {'slot':slot,'mod_id':catalog_id,'reason':'one owned instance is selected in multiple active slots'}))
            continue
        instance_slots[item['id']]=slot
        if observed_row_order_conflict(stats):
            issues.append({'slot':slot,'mod_id':catalog_id,
                           'reason':'recorded source rows disagree in value, count, or order; reconcile both sources before Tech activation',
                           'code':'source_row_order_conflict','owned_instance_id':item['id'],
                           'offense_blocking':True,'selected_level':item.get('level')})
            continue
        if not isinstance(mods,list) or not mods:
            issues.append({'slot':slot,'mod_id':catalog_id,'reason':'owned instance has no source-checked typed rolls',
                           'code':'owned_roll_evidence_missing','mod_name':item.get('name') or catalog_id,
                           'selected_level':item.get('level'),'owned_instance_id':item['id'],
                           'observed_attribute_lines':len(stats.get('observed_attribute_lines') or []),
                           'next_step':'Capture a readable tooltip for this exact owned mod and level. In Import & review, inspect the matched source rows and explicitly Apply evidence to this owned instance.',
                           'matching_instances':1})
            continue
        if stats.get('original_observed_level') is not None and item.get('level')!=stats['original_observed_level']:
            issues.append({'slot':slot,'mod_id':catalog_id,'reason':'observed roll values belong to a different Field Guide level',
                           'code':'roll_level_mismatch','selected_level':item.get('level'),
                           'observed_level':stats['original_observed_level']})
            continue
        expected=stats.get('observed_attribute_lines')
        if isinstance(expected,list) and len(expected)!=len(mods):
            issues.append({'slot':slot,'mod_id':catalog_id,'reason':'typed roll count differs from observed attribute rows'})
            continue
        eligible=[m for m in mods if m.get('confidence')=='source_checked' and m.get('calculation_status')=='assumption_scenario'
                  and isinstance(m.get('value'),(int,float)) and not isinstance(m.get('value'),bool)
                  and isfinite(m['value']) and m['value']>=0]
        if len(eligible)!=len(mods):
            excluded=[m for m in mods if m not in eligible]
            issues.append({'slot':slot,'mod_id':catalog_id,'reason':'one or more roll rows are OCR-only, ambiguous or unmodeled',
                           'offense_blocking':any(may_affect_offense(m) for m in excluded),
                           'excluded_stat_types':[m.get('stat_type') for m in excluded]})
        selected.extend({**m,'equipped_slot':slot,'owned_instance_id':item['id']} for m in eligible)
    return {'modifiers':selected,'unresolved':issues,'resolved_slots':sorted({x['equipped_slot'] for x in selected}),
            'active_weapon_slot':active_weapon_slot,'ignored_weapon_slots':sorted(ignored_slots)}
