"""Evidence-bounded build calculations; no inferred game-wide damage formula."""
from itertools import product
from math import prod
from pathlib import Path
import json
import hashlib
import re
import catalog
import component_compare

RULES = json.loads((Path(__file__).with_name("rules.json")).read_text())["rules"]

SLOTS = ("primary", "secondary", "melee", "helmet", "mask", "chest", "gloves", "pants", "boots", "weapon_mod", "helmet_mod", "mask_mod", "chest_mod", "gloves_mod", "pants_mod", "boots_mod", "accessory")
EQUIPPABLE_KINDS={"instance","mod_unlock"}
GOALS = {"Sustained baseline": "reload_aware_rate", "Burst baseline": "burst_rate"}
UNSUPPORTED_GOALS = {"Boss damage": "Enemy defense, weak-spot behavior and boss-specific effects are not verified.", "Group clearing": "Area targets, proc rates and target geometry are not verified.", "Ease of use": "No validated execution or movement score is available."}
STAT_EFFECT_KEYS = ("effect", "effects", "set_effect", "proc", "status", "buff", "crit_rate", "crit_damage", "weakspot_rate", "weakspot_damage", "elemental_damage", "weapon_damage_bonus", "attack_bonus", "fire_rate_bonus")


def _import_semantic_uncertainties(item):
    stats=item.get('stats') or {}
    return ((stats.get('video_import') or {}).get('semantic_uncertainties') or [])

def recorded_effects(item):
    out=[]
    effects=item.get("effects") or {}
    if isinstance(effects,str): effects={"text":effects}
    if isinstance(effects,dict):
        for k,v in effects.items():
            if k in ("calculation_status","coverage_note","rule_ids","catalog_id","catalog_effects","catalog_source","catalog_unknowns"):continue
            if v not in (None,"",[],{}): out.append(f"effects.{k}: {str(v)[:180]}")
    elif effects: out.append("effects: " + str(effects)[:180])
    for k,v in (item.get("stats") or {}).items():
        if k in STAT_EFFECT_KEYS and v not in (None,"",[],{}): out.append(f"stats.{k}: {str(v)[:180]}")
    return out


def validate_loadout(items):
    slots=[i.get("slot") for i in items]
    issues=[]
    if any(s not in SLOTS for s in slots): issues.append("Unknown equipment slot")
    if len(slots)!=len(set(slots)): issues.append("Two items occupy the same slot")
    if len({str(i.get('id')) for i in items})!=len(items): issues.append("Same entry equipped twice")
    if any(i.get('kind','instance') not in EQUIPPABLE_KINDS for i in items):issues.append("Blueprint or account unlock is not a crafted or equippable item")
    return issues


def _num(value, name, minimum=None, maximum=None):
    x=float(value)
    if minimum is not None and x<minimum or maximum is not None and x>maximum: raise ValueError(f"{name} outside valid range")
    return x


def baseline(item, assumptions):
    """Expected direct-hit events from observed per-hit values and firing cycle.

    A crit/weak-spot branch is used only if the user supplies measured hit values for
    that branch; percentages are not turned into game multipliers.
    """
    s=item.get("stats") or {}; warnings=[]
    needed=("damage","rpm","magazine","reload_seconds")
    missing=[k for k in needed if s.get(k) in (None,"")]
    if missing: return {"supported":False,"missing":missing,"warnings":["Direct-hit inputs missing: "+", ".join(missing)]+["Recorded but unmodeled: "+x for x in recorded_effects(item)]}
    try:
        dmg=_num(s["damage"],"damage",0.000001);rpm=_num(s["rpm"],"rpm",0.000001)
        mag=_num(s["magazine"],"magazine",1);reload=_num(s["reload_seconds"],"reload",0)
        hit=_num(assumptions.get("hit_rate",1),"hit rate",0,1);duration=_num(assumptions.get("duration",45),"duration",0.000001)
        weak=_num(assumptions.get("weakspot_rate",0),"weakspot rate",0,1)
        crit=_num(assumptions.get("crit_rate",0),"crit rate",0,1)
    except (ValueError,TypeError) as e: return {"supported":False,"missing":[],"warnings":[str(e)]}
    if mag!=int(mag): return {"supported":False,"missing":[],"warnings":["Magazine must be a whole number"]}
    # These are measured branch values, never a guessed crit or weak-spot formula.
    branches={"normal":dmg}
    for key,required in (("crit_hit_damage",crit>0),("weakspot_hit_damage",weak>0),("crit_weakspot_hit_damage",crit>0 and weak>0)):
        if required and s.get(key) in (None,""): missing.append(key)
        elif s.get(key) not in (None,""):
            try: branches[key]=_num(s[key],key,0)
            except (ValueError,TypeError): missing.append(key)
    if missing: return {"supported":False,"missing":missing,"warnings":["Measured hit values are required for selected crit/weak-spot assumptions; no multiplier was invented."]}
    if crit>0 and weak>0:warnings.append("The entered crit share is assumed equal on normal and weak-spot hits; change the share if observed behavior differs.")
    shot_time=60/rpm; firing=int(mag)*shot_time;cycle=firing+reload
    full=int(duration//cycle);remaining=duration-full*cycle
    shots=full*int(mag)+min(int(mag),int(remaining/shot_time+1e-9))
    expected=(1-weak)*((1-crit)*dmg+crit*branches.get("crit_hit_damage",dmg))+weak*((1-crit)*branches.get("weakspot_hit_damage",dmg)+crit*branches.get("crit_weakspot_hit_damage",dmg))
    direct=shots*hit*expected
    burst_shots=min(int(mag),int(firing/shot_time+1e-9))
    burst_damage=burst_shots*hit*expected
    components={"direct_hit":round(direct,2),"critical_branch":round(shots*hit*crit*((1-weak)*branches.get("crit_hit_damage",dmg)+weak*branches.get("crit_weakspot_hit_damage",dmg)),2) if crit else 0,"weakspot_branch":round(shots*hit*weak*((1-crit)*branches.get("weakspot_hit_damage",dmg)+crit*branches.get("crit_weakspot_hit_damage",dmg)),2) if weak else 0,"proc":None,"status":None}
    if s.get("proc_damage_per_event") is not None and s.get("proc_events_per_hit") is not None:
        try:components["proc"]=round(shots*hit*_num(s["proc_events_per_hit"],"proc events per hit",0)*_num(s["proc_damage_per_event"],"proc damage",0),2)
        except (ValueError,TypeError):warnings.append("Observed proc inputs are invalid; proc estimate omitted")
    elif any(s.get(k) is not None for k in ("proc_damage_per_event","proc_events_per_hit")):warnings.append("Proc event damage and observed events per hit are both needed")
    if s.get("status_damage_per_second") is not None and s.get("status_uptime") is not None:
        try:components["status"]=round(duration*_num(s["status_uptime"],"status uptime",0,1)*_num(s["status_damage_per_second"],"status damage rate",0),2)
        except (ValueError,TypeError):warnings.append("Observed status inputs are invalid; status estimate omitted")
    elif any(s.get(k) is not None for k in ("status_damage_per_second","status_uptime")):warnings.append("Status damage rate and observed uptime are both needed")
    for e in recorded_effects(item): warnings.append("Recorded but unmodeled: "+e)
    warnings.append("Proc/status estimates, when supplied, are separate user observations and do not alter the direct-hit ranking. Enemy defense, distance and cross-item stacking remain outside it.")
    return {"supported":True,"direct_hit_damage":dmg,"rpm":rpm,"magazine":int(mag),"reload_seconds":reload,"hit_rate":hit,"duration":duration,"shots":shots,"components":components,"reload_aware_damage":round(direct,2),"reload_aware_rate":round(direct/duration,2),"burst_damage":round(burst_damage,2),"burst_rate":round(burst_damage/firing,2),"warnings":warnings,"scope":"Measured direct-hit branches only; incomplete build comparison"}


def sourced_interactions(items, assumptions):
    """Qualitative and threshold rules supported by official patch text."""
    names={i.get("name","").lower() for i in items};set_counts={}
    for i in items:
        set_name=(i.get("stats") or {}).get("set_name")
        if set_name:set_counts[set_name.lower()]=set_counts.get(set_name.lower(),0)+1
    notes=[]
    def add(text,source,kind="interaction"):notes.append({"text":text,"source":source,"kind":kind})
    if any("cosmic visitor" in n for n in names):
        add("Cosmic Visitor guarantees a Frost Vortex on the first hit after reload; spear counts and damage still need a tooltip.","patch311")
        if any("snowline elite vest" in n for n in names):add("Snowline Elite Vest repeats Vortex-triggered effects once, without generating another Vortex; numeric gain is unknown.","patch311")
    if any("electron cloud" in n for n in names):add("Electron Cloud's field refreshes position and duration when generated again; orb Shock is a separate status component.","maybalance")
    if any("burden of betrayal" in n for n in names):add("Burden of Betrayal's Echo uses Bounce and full-charge Crit Rate; PvP Echo and Bounce were reduced in May. These effects are not included in baseline.","maybalance")
    if any("pyroclasm starter" in n for n in names):
        add("Charged Pyroclasm rounds are Blaze Status DMG, not ordinary Weapon DMG, per February change.","febbalance")
        if any("gilded gauntlets" in n for n in names):add("Gilded Gauntlets enable Burn to crit; this does not imply every status can crit.","febbalance")
    if any("pathfinder" in n for n in names):add("Pathfinder charged ice spike is Frost Status DMG and remains crit/weak-spot eligible; numeric proc damage needs current tooltip inputs.","febbalance")
    if any("additional rules" in n for n in names):add("Additional Rules' charged elemental bullets are Status DMG and remain crit/weak-spot eligible.","febbalance")
    if any("finale" in n for n in names):add("Finale guarantees Shrapnel on weak-spot hits; Reverb stacks reset on reload or switch.","julygear")
    if any("fiery trees" in n for n in names) and any("wind intepreter cap" in n for n in names):add("Wind Intepreter Cap reloads a bullet when Unstable Bomber explodes; the +25% Bomber damage rate is separate from direct hits.","julygear")
    ghost=set_counts.get("ghost link",0)
    if ghost>=3:add("Ghost Link 3-piece can stack Synchronize up to 10 for 10s; chance and per-stack value remain unknown.","julygear")
    tide=set_counts.get("treacherous tides",0)
    if tide>=2:
        hp=assumptions.get("hp_fraction")
        if hp is None:add("Treacherous Tides 2-piece grants +12% Weapon and Status DMG below 70% HP; current HP assumption missing.","septbalance","conditional")
        elif float(hp)<.7:add("Treacherous Tides 2-piece is active: +12% Weapon and Status DMG below 70% HP. Stacking with other bonuses is not modeled.","septbalance","active")
        else:add("Treacherous Tides 2-piece is inactive at this HP.","septbalance","inactive")
    if tide>=3:add("Treacherous Tides 3-piece grants 8% to 28% Weapon and Status DMG from 100% to 60% HP; interpolation and stacking are unverified.","septbalance","conditional")
    for i in items:
        variant=str(i.get("variant") or "").lower()
        if variant=="aero":add("Aero suffix requires an aerial state, including jumping; uptime and damage amount need current tooltip evidence.","aeromod","conditional")
        if variant=="downstar":add("Downstar suffix is tied to elevation difference; activation depends on encounter geometry.","aeromod","conditional")
    return notes


def build_gaps(build, inventory, catalog):
    """Sourced synergy opportunities, never an invented numeric upgrade benefit."""
    by_id={str(i["id"]):i for i in inventory}
    chosen=[by_id[str(x)] for x in build.get("item_ids",[]) if str(x) in by_id]
    names={i.get("name","").lower() for i in chosen}
    rules=[("cosmic visitor","Snowline Elite Vest","patch311","Repeats Vortex-triggered effects, without another Vortex"),("pyroclasm starter","Gilded Gauntlets","febbalance","Enables Burn critical hits"),("fiery trees","Wind Intepreter Cap","julygear","Reloads one bullet when Unstable Bomber explodes")]
    gaps=[]
    for trigger,target,source,reason in rules:
        if any(trigger in n for n in names) and target.lower() not in names:
            entry=next((x for x in catalog if x["name"]==target),{})
            owned=next((x for x in inventory if x.get("name","").lower()==target.lower()),None)
            gaps.append({"name":target,"reason":reason,"source":source,"owned":bool(owned),"owned_id":owned.get("id") if owned else None,"acquisition":entry.get("acquisition"),"cost":None,"status":"owned but not equipped" if owned else "ownership unknown or missing"})
    return gaps


def _measurement_for(items, assumptions, measurements):
    wanted=sorted(str(i["id"]) for i in items)
    fingerprint=loadout_fingerprint(items)
    context={k:str(assumptions.get(k) or "").strip().lower() for k in ("target","buffs","conditions","scenario")}
    for m in measurements or []:
        ids=m.get("item_ids") or []
        if isinstance(ids,str):
            try:ids=json.loads(ids)
            except ValueError:continue
        if sorted(map(str,ids))!=wanted:continue
        if m.get("item_fingerprint")!=fingerprint:continue
        if any(str(m.get(k) or "").strip().lower()!=v for k,v in context.items()):continue
        return m
    return None


def loadout_fingerprint(items):
    """Bind combat evidence to the recorded gear state, including later edits."""
    fields=("id","name","slot","family","variant","level","stars","stats","effects")
    snapshot=[{k:i.get(k) for k in fields} for i in items]
    snapshot.sort(key=lambda i:str(i.get("id")))
    return hashlib.sha256(json.dumps(snapshot,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()


def _predicted_score(items, assumptions):
    weapon=next((i for i in items if i.get("slot")=="primary"),None)
    if not weapon:return {"supported":False,"missing":["primary weapon"],"warnings":[],"trace":[],"unresolved":[]}
    stats=weapon.get("stats") or {}
    missing=[];unresolved=[];trace=[];isolated_estimates=[]
    if stats.get("damage_origin")!="tooltip_base":missing.append("weapon tooltip/base damage origin")
    if assumptions.get("crit_rate",0) or assumptions.get("weakspot_rate",0):
        unresolved.append("Crit and weak-spot combat-hit branches cannot be transferred into a tooltip-base prediction; use same-context measurements.")
    mode=assumptions.get("scenario","PvE")
    armor_slots={"helmet","mask","chest","gloves","pants","boots"}
    set_count=sum(1 for i in items if i.get("slot") in armor_slots and str((i.get("stats") or {}).get("set_name") or "").lower()=="treacherous tides")
    hp=assumptions.get("hp_fraction")
    bonus=0
    catalog_bonuses=[]
    if set_count>=2:
        rule=next(r for r in RULES if r["id"]=="treacherous_tides_two_weapon")
        if mode!="PvE":unresolved.append("Treacherous Tides mode applicability needs confirmation for "+str(mode))
        elif hp is None:unresolved.append("Treacherous Tides needs a current HP fraction")
        else:
            try: hp_value=_num(hp,"HP fraction",0,1)
            except (ValueError,TypeError):unresolved.append("Invalid HP fraction");hp_value=None
            if hp_value is not None and hp_value<rule["condition"]["hp_fraction_below"]:
                if stats.get("base_component")!="weapon":
                    unresolved.append("Treacherous Tides Weapon DMG bonus needs a weapon-component tooltip base")
                elif stats.get("base_context")!="unbuffed":
                    unresolved.append("Treacherous Tides needs an unbuffed tooltip base so its bonus is not counted twice")
                else:
                    bonus=rule["bonus_fraction"]
                    trace.append({"rule_id":rule["id"],"source":rule["source"],"component":rule["component"],"bonus_fraction":bonus,"reason":"Two Treacherous Tides pieces and HP below 70%"})
            elif hp_value is not None:trace.append({"rule_id":rule["id"],"source":rule["source"],"component":rule["component"],"bonus_fraction":0,"reason":"Inactive at current HP"})
    if set_count>=3:unresolved.append("Treacherous Tides three-piece interpolation and stacking with two-piece are unverified")
    for i in items:
        set_name=str((i.get("stats") or {}).get("set_name") or "").strip()
        if set_name and set_name.lower()!="treacherous tides":
            unresolved.append(i.get("name","Item")+": "+set_name+" set effect has no verified calculation rule")
    weapon_family=(str(weapon.get("family") or "")+" "+str(weapon.get("name") or "")+" "+str((weapon.get("effects") or {}).get("text") or "")).lower()
    for i in items:
        effects=i.get("effects") or {}
        if not isinstance(effects,dict):effects={"text":str(effects)}
        coverage=effects.get("calculation_status")
        catalog_id=effects.get('catalog_id')
        catalog_entry=catalog.ENTRIES.get(catalog_id) if catalog_id else None
        catalog_rule=None
        if catalog_id:
            if not catalog_entry:unresolved.append(i.get('name','Item')+': catalog entry no longer resolves')
            else:
                ambiguities=_import_semantic_uncertainties(i)
                if ambiguities:
                    unresolved.append(i.get('name','Mod')+': imported attribute direction is ambiguous in the source; no numeric contribution from this mod is allowed')
                attributes=[] if ambiguities else (i.get('stats') or {}).get('catalog_attributes') or []
                for attribute in (a for a in attributes if isinstance(a,dict)) if isinstance(attributes,list) else []:
                    if attribute.get('value_percent') is not None:
                        trace.append({'rule_id':catalog_id+':attribute:'+attribute['name'],'source':attribute.get('source_image') or attribute.get('source'),'component':attribute['name'],'value_percent':attribute['value_percent'],'tier':attribute.get('tier'),'condition':attribute.get('condition'),'conditional_bonus_percent':attribute.get('conditional_bonus_percent'),'reason':'Structured Field Guide attribute; included in coverage audit, numeric contribution requires verified stacking and context'})
                        if attribute['name']=='Weapon DMG' and stats.get('base_component')=='weapon' and stats.get('base_context')=='unbuffed' and isinstance(stats.get('damage'),(int,float)):
                            isolated_estimates.append({'item':i.get('name'),'attribute':'Weapon DMG','source':attribute.get('source_image') or attribute.get('source'),'base_percent':attribute['value_percent'],'weapon_component_increment':round(stats['damage']*attribute['value_percent']/100,4),'scope':'isolated weapon component only; no stacking, other effects, or total build rank inferred'})
                    else:unresolved.append(i.get('name','Mod')+': '+attribute['name']+' tier '+str(attribute.get('tier'))+' numeric value unresolved')
                structured=catalog_entry.get('structured_effects') or []
                if catalog_entry.get('effect_parse_complete') and len(structured)==1 and structured[0].get('type')=='increase_stat' and structured[0].get('stat')=='weapon_damage_percent' and isinstance(structured[0].get('value'),(int,float)):
                    catalog_rule=structured[0]
                    catalog_bonuses.append((i,catalog_rule))
                    trace.append({'rule_id':catalog_id,'source':catalog_entry.get('source_url') or catalog_entry.get('source'),'component':'weapon_damage','bonus_fraction':catalog_rule['value']/100,'reason':'Catalog main effect: '+str(catalog_rule['value'])+'% Weapon DMG; complete variant attributes and stacking still require review'})
                else:unresolved.append(i.get('name','Mod')+': catalog effect has no isolated direct-hit calculation rule')
                suffix_effects=catalog_entry.get('structured_suffix_effects') or []
                if suffix_effects:
                    trace.append({'rule_id':catalog_id+':suffix','source':suffix_effects[0]['source'],'component':'conditional_suffix','reason':catalog_entry.get('variant','Suffix')+' affects '+', '.join(x['stat'] for x in suffix_effects)+'; activation: '+suffix_effects[0]['condition']})
                    unresolved.append(i.get('name','Mod')+': official suffix effect magnitudes and stacking are unknown')
                if coverage!='catalog_verified' or (i.get('stats') or {}).get('attribute_coverage')!='complete':
                    unresolved.append(i.get('name','Mod')+': catalog core effect is known, but level attributes or current applicability are not fully verified')
        named_rule=next((r for r in RULES if r.get("item_name","").lower()==i.get("name","").lower()),None)
        allowed_ids={"treacherous_tides_two_weapon"} if i.get("slot") in armor_slots and str((i.get("stats") or {}).get("set_name") or "").lower()=="treacherous tides" else set()
        if named_rule:allowed_ids.add(named_rule["id"])
        covered_rule=coverage=="verified_rule_only" and set(effects.get("rule_ids") or [])==allowed_ids and bool(allowed_ids)
        if coverage not in ("verified_no_extra_damage","catalog_verified") and not covered_rule:
            unresolved.append(i.get("name","Item")+": effect coverage is unresolved; review its tooltip and mark only if no other damage effect applies")
        if effects.get("text") and not covered_rule and not catalog_id:
            unresolved.append(i.get("name","Item")+": recorded effect text has no complete calculation rule: "+str(effects["text"])[:100])
        for k,v in effects.items():
            if k not in ("text","calculation_status","coverage_note","rule_ids","catalog_id","catalog_effects","catalog_effect_candidates","catalog_source","catalog_unknowns") and v not in (None,"",[],{},0):
                unresolved.append(i.get("name","Item")+": recorded effects."+k+" has no verified calculation rule")
        for k in STAT_EFFECT_KEYS:
            if (i.get("stats") or {}).get(k) not in (None,"",0):
                unresolved.append(i.get("name","Item")+": "+k+" interaction has no verified calculation rule")
        known_stats={"damage","rpm","magazine","reload_seconds","damage_origin","base_component","base_context","set_name","proc_damage_per_event","proc_events_per_hit","status_damage_per_second","status_uptime","crit_hit_damage","weakspot_hit_damage","crit_weakspot_hit_damage","catalog_level_profile","catalog_attribute_tiers","catalog_attributes","attribute_coverage","observed_attribute_lines","observed_attribute_ocr_status","roll_evidence_observation"}
        for k,v in (i.get("stats") or {}).items():
            if k not in known_stats and k not in STAT_EFFECT_KEYS and v not in (None,"",0):
                unresolved.append(i.get("name","Item")+": stat "+k+" has no verified calculation rule")
            if i is not weapon and k in {"damage","rpm","magazine","reload_seconds","proc_damage_per_event","proc_events_per_hit","status_damage_per_second","status_uptime","crit_hit_damage","weakspot_hit_damage","crit_weakspot_hit_damage"} and v not in (None,"",0):
                unresolved.append(i.get("name","Item")+": gear stat "+k+" is not incorporated into the weapon proxy")
            if i is weapon and k in {"proc_damage_per_event","proc_events_per_hit","status_damage_per_second","status_uptime","crit_hit_damage","weakspot_hit_damage","crit_weakspot_hit_damage"} and v not in (None,"",0):
                unresolved.append(i.get("name","Weapon")+": recorded "+k+" needs contextual measurement, not tooltip-base prediction")
        if str(i.get("variant") or "").lower() in ("aero","downstar"):
            unresolved.append(i.get("name","Mod")+": suffix activation and numeric bonus need current tooltip conditions")
        name=i.get("name","").lower()
        for r in RULES:
            if r.get("item_name","").lower()==name:
                trigger={"wind_interpreter_bomber":"unstable bomber","gilded_gauntlets_burn_crit":"burn","snowline_vortex_repeat":"frost vortex"}.get(r["id"])
                if trigger and trigger not in weapon_family:
                    trace.append({"rule_id":r["id"],"source":r["source"],"component":r["component"],"reason":"Inactive: no "+trigger+" source in selected primary weapon"})
                else:
                    unresolved.append(i.get("name","Item")+": "+r["calculation"])
                    trace.append({"rule_id":r["id"],"source":r["source"],"component":r["component"],"reason":r["activation"]})
    # A single official +12% modifier has clear isolated arithmetic. Any other
    # active or unknown damage bonus prevents treating this proxy as a prediction.
    if len(catalog_bonuses)>1 or (bonus and catalog_bonuses):unresolved.append('Multiple Weapon DMG bonuses have no verified stacking rule')
    if len(catalog_bonuses)==1 and not bonus:
        if stats.get('base_component')!='weapon' or stats.get('base_context')!='unbuffed':unresolved.append('Catalog Weapon DMG effect needs an unbuffed weapon-component tooltip base')
        else:bonus=catalog_bonuses[0][1]['value']/100
    if bonus and unresolved:unresolved.append("Treacherous Tides +12% cannot establish a build score alongside unresolved effects")
    if missing or unresolved:
        return {"supported":False,"missing":missing,"warnings":unresolved,"unresolved":unresolved,"trace":trace,"isolated_estimates":isolated_estimates,"basis":"predicted_equipment","score_kind":"unresolved","evidence_needed":_evidence_needed(unresolved,missing)}
    shifted={**weapon,"stats":{**stats,"damage":float(stats["damage"])*(1+bonus)}}
    metric=baseline(shifted,{**assumptions,"crit_rate":0,"weakspot_rate":0})
    metric.update({"trace":trace,"unresolved":[],"basis":"predicted_equipment","score_kind":"tooltip-base relative throughput index","source_damage":stats["damage"],"factor":round(1+bonus,4),"evidence_needed":[]})
    return metric


def _evidence_needed(unresolved, missing):
    needed=[]
    if missing:needed.append("Record the weapon tooltip Damage, RPM, magazine and reload, and label the damage origin as tooltip/base.")
    for text in unresolved:
        if "coverage" in text:needed.append("Capture the full item tooltip and confirm whether its other damage effects are absent or separately modeled.")
        elif "HP fraction" in text:needed.append("Enter current HP fraction or record buff uptime below 70% HP.")
        elif "three-piece" in text:needed.append("Measure three-piece damage at several HP points and test stacking with two-piece on the same target.")
        elif "suffix" in text:needed.append("Record mod attribute values and activation state during the encounter.")
        elif "trigger" in text or "Burn" in text:needed.append("Record proc/status event damage and rate with and without this gear on the same target.")
        elif "unbuffed" in text:needed.append("Capture the weapon tooltip before the set activates, or establish whether the displayed Damage already includes the set bonus.")
        elif "mode applicability" in text:needed.append("Confirm this set effect in the selected scenario with a current tooltip or matched combat test.")
        elif "effect" in text or "stat" in text or "gear" in text:needed.append("Capture the complete gear tooltip and compare matched target hits with and without this effect.")
    return list(dict.fromkeys(needed))


def score_loadout(items, assumptions, measurements=None):
    goal=assumptions.get("goal","Sustained baseline")
    if goal not in GOALS: raise ValueError(UNSUPPORTED_GOALS.get(goal,"Unsupported goal"))
    issues=validate_loadout(items)
    weapon=next((i for i in items if i.get("slot")=="primary"),None)
    if not weapon:issues.append("No primary weapon")
    mode=assumptions.get("comparison_mode","predicted_equipment")
    if mode=="measured_baseline":
        m=_measurement_for(items,assumptions,measurements)
        if not m:metric={"supported":False,"missing":["same-gear-state, same-target combat-hit measurement"],"warnings":["Measured hits are bound to exact item IDs and their saved attributes, target, buffs, conditions and scenario; they cannot be carried into another gear state."],"basis":"measured_baseline","score_kind":"unresolved","trace":[],"evidence_needed":["Record normal hit damage and timing for this exact gear state against the selected target with the selected buffs and conditions."]}
        else:
            if any(m.get(k) is None for k in ("rpm","magazine","reload_seconds")):
                metric={"supported":False,"missing":["loadout-specific firing and reload timing"],"warnings":["This older measurement lacks timing recorded with its exact loadout."],"basis":"measured_baseline","score_kind":"unresolved","trace":[],"evidence_needed":["Record cadence, magazine and reload with this exact loadout."]}
                interactions=sourced_interactions(items,assumptions)
                return {"issues":issues,"metric":metric,"interactions":interactions,"rankable":False,"score":None}
            s={k:v for k,v in (weapon.get("stats") or {}).items() if k not in ("proc_damage_per_event","proc_events_per_hit","status_damage_per_second","status_uptime")}
            s.update({"damage":m["normal_hit"],"rpm":m["rpm"],"magazine":m["magazine"],"reload_seconds":m["reload_seconds"]})
            for key in ("crit_hit_damage","weakspot_hit_damage","crit_weakspot_hit_damage"):
                if m.get(key) is not None:s[key]=m[key]
            metric=baseline({**weapon,"stats":s},assumptions)
            metric.update({"basis":"measured_baseline","score_kind":"observed direct-hit damage rate","trace":[{"measurement_id":m.get("id"),"reason":"Exact loadout and context matched","source_observation":m.get("source_observation")}],"measurement_context":{k:m.get(k) for k in ("target","buffs","conditions","scenario")},"unresolved":[],"evidence_needed":[]})
    elif mode=="predicted_equipment":metric=_predicted_score(items,assumptions)
    else:raise ValueError("Unknown comparison mode")
    interactions=sourced_interactions(items,assumptions)
    return {"issues":issues,"metric":metric,"interactions":interactions,"rankable":not issues and metric.get("supported",False),"score":metric.get(GOALS[goal]) if not issues and metric.get("supported") else None}


def compare(loadouts, inventory, assumptions, measurements=None):
    by_id={str(i["id"]):i for i in inventory};out=[]
    for b in loadouts:
        chosen=[by_id[str(x)] for x in b.get("item_ids",[]) if str(x) in by_id]
        result=score_loadout(chosen,assumptions,measurements)
        out.append({"id":b.get("id"),"name":b.get("name"),"items":chosen,**result})
    out.sort(key=lambda r:(r["rankable"],r["score"] if r["score"] is not None else -1),reverse=True)
    ranked=[r for r in out if r["rankable"]]
    margin=round(ranked[0]["score"]-ranked[1]["score"],2) if len(ranked)>1 else None
    basis=assumptions.get("comparison_mode","predicted_equipment")
    sensitivity=[]
    if basis=="predicted_equipment":
        for duration in (10,120):
            shifted={**assumptions,"duration":duration}
            scores=[(score_loadout(r["items"],shifted,measurements)["score"],r["name"]) for r in ranked]
            if scores:
                winner=max(scores,key=lambda x:x[0])[1]
                sensitivity.append({"duration":duration,"winner":winner,"changes_winner":winner!=ranked[0]["name"]})
    claim=("Measured direct-hit comparison for exact loadouts under identical target, buffs, conditions and scenario." if basis=="measured_baseline" else "Predicted equipment comparison on a tooltip-base relative index using only isolated sourced rules. This is not combat DPS.")
    if len(ranked)<len(out):claim+=" Unresolved builds are unranked; no global winner is established."
    return {"results":out,"margin_to_next":margin,"sensitivity":sensitivity,"claim":claim,"assumptions":assumptions,"comparison_mode":basis,"winner_established":len(ranked)==len(out) and bool(ranked) and (len(ranked)==1 or ranked[0]["score"]>ranked[1]["score"])}


def _attribute_context(attribute, assumptions):
    name=attribute.get('name','').lower();condition=(attribute.get('condition') or '').lower()
    conditions=str(assumptions.get('conditions') or '').lower()
    family=str(assumptions.get('weapon_family') or '').lower()
    if attribute.get('direction')=='reduction' or 'damage reduction' in name:component='incoming damage / survival'
    elif 'hp' in name:component='survival'
    elif 'magazine' in name or 'reload' in name:component='firing cycle'
    elif 'trigger chance' in name:component='proc frequency; percentage-point versus relative change unresolved'
    elif 'crit' in name:component='critical-hit branch'
    elif 'weakspot' in name:component='weak-spot branch'
    elif 'all dmg' in name:component='outgoing damage across components; stacking unresolved'
    elif 'weapon dmg' in name:component='direct weapon-hit branch'
    elif 'status' in name or 'element' in name or 'shock' in name or 'surge' in name:component='proc / status branch'
    else:component='direct-hit or general damage; stacking unresolved'
    base_state='passive; component applicability depends on encounter'
    if 'after taking damage' in condition and attribute.get('conditional_bonus_percent') is None:
        base_state='inactive when no incoming hits occur' if 'no incoming hits' in conditions else 'requires prior damage and cooldown verification'
    if 'crit' in name and assumptions.get('crit_rate') is not None:
        if _num(assumptions['crit_rate'],'critical-hit share',0,1)==0:base_state='inactive for explicit zero critical-hit share'
    if 'weakspot' in name and assumptions.get('weakspot_rate') is not None:
        if _num(assumptions['weakspot_rate'],'weak-spot share',0,1)==0:base_state='inactive for explicit zero weak-spot share'
    conditional_state=None
    if attribute.get('conditional_bonus_percent') is not None:
        conditional_state='unknown; encounter condition or uptime required'
        if 'aerial' in condition:
            if any(x in conditions for x in ('grounded','no aerial','on ground')):conditional_state='inactive for stated grounded encounter'
            elif any(x in conditions for x in ('aerial','airborne','jumping')):conditional_state='active for stated aerial hit'
        elif 'enemy below player' in condition:
            if 'same elevation' in conditions:conditional_state='inactive for stated same-elevation encounter'
            elif 'enemy below player' in conditions and any(x in conditions for x in ('5m','5 meters','5 metres')):conditional_state='active at stated maximum elevation difference'
        if base_state.startswith('inactive'):conditional_state='inactive because affected hit branch has zero share'
    state=base_state if conditional_state is None else f'base: {base_state}; additional bonus: {conditional_state}'
    family_note=''
    if family:
        if 'surge' in name or 'shock' in name:family_note='Power Surge / Shock source relevant' if any(x in family for x in ('surge','shock')) else 'selected weapon family does not establish a Power Surge source'
        elif component=='proc / status branch':family_note='verify this damage type occurs in the selected weapon and encounter'
    # Tooltip percentages identify the affected bucket. They do not establish
    # whether several bonuses add, multiply, or apply before another effect.
    operator='percentage-point chance change unresolved' if 'trigger chance' in name else 'percent reduction; mitigation stacking unresolved' if attribute.get('direction')=='reduction' else 'percent bonus; stacking order unresolved'
    if attribute.get('conditional_bonus_percent') is not None:operator+='; base and additional conditional bonus are separate'
    if 'incoming damage' in component or component=='survival':outgoing='proven inactive for outgoing damage'
    elif base_state.startswith('inactive'):outgoing='proven inactive under stated conditions'
    else:outgoing='affected component identified; total contribution unresolved'
    base=attribute.get('value_percent');conditional=attribute.get('conditional_bonus_percent')
    effective=round(base+conditional,4) if isinstance(base,(int,float)) and isinstance(conditional,(int,float)) and conditional_state.startswith('active') else base if isinstance(base,(int,float)) and (conditional is None or conditional_state.startswith('inactive')) else None
    return {'component':component,'activation_state':state,'base_activation_state':base_state,'conditional_activation_state':conditional_state,'base_value_percent':base,'conditional_value_percent':conditional,'effective_value_percent':effective,'weapon_family_note':family_note,'operator':operator,'outgoing_damage_status':outgoing}


def _main_effect_requirements(text, structured):
    if structured:return structured
    text=str(text or '').strip()
    # This is a literal condition excerpt, never a probability or uptime model.
    for prefix in ('When triggering ', 'Upon triggering ', 'After triggering ', 'Inflicting ', 'After inflicting ', 'On hitting ', 'When hitting ', 'After reloading ', 'Upon reloading '):
        if text.startswith(prefix):
            clause=text.split(',',1)[0]
            return [clause[:180]+' (condition in effect text; uptime unverified)']
    return []


def _relative_trigger_rule(text, assumptions, source):
    """Literal one-stack chance factor; no proc-rate or multi-stack inference."""
    match=re.search(r'\+(\d+(?:\.\d+)?)%\s+(.+?) Trigger Chance \(based on weapon\'s Trigger Chance\) for (\d+(?:\.\d+)?)s, up to (\d+) stack',str(text or ''),re.I)
    if not match:return None
    bonus=float(match.group(1))/100
    rule={'effect_family':match.group(2),'operator':'relative_to_weapon_base_trigger_chance','bonus_per_stack_fraction':bonus,'duration_seconds':float(match.group(3)),'max_stacks_text':int(match.group(4)),'source':source,'corroborating_source':'https://www.oncehuman.game/news/update/20250521/40780_1235763.html','stack_accumulation':'unverified','uptime':'unverified','one_stack_chance':None,'one_stack_change_percentage_points':None}
    base=assumptions.get('base_trigger_chance')
    if base is not None:
        base=_num(base,'base trigger chance',0,1)
        if base*(1+bonus)<=1:
            rule['one_stack_chance']=round(base*(1+bonus),6)
            rule['one_stack_change_percentage_points']=round(base*bonus*100,4)
        else:rule['cap_behavior']='unknown; raw factor exceeds 100%'
    return rule


def _isolated_incoming_hit(snapshot, raw_hit):
    """One PvE monster hit before prior-hit buffs, with no other mitigation.

    This ranks only received hit damage. It makes no claim about DPS, HP,
    armor mitigation, or repeated-hit survival.
    """
    if snapshot['numeric_coverage']!='complete':return {'supported':False,'reason':'Numeric attribute profile incomplete'}
    main=snapshot['main_effect']
    inactive_main_rules=(
        (r'^When triggering Power Surge, apply the Power Surge Status to \d+ enemy','shock_diffusion_outgoing_status','https://www.oncehuman.game/news/update/20241218/40780_1200958.html'),
        (r'^Weakspot DMG \+20% when a bullet hits a target more than 20 meters away','distant_strike_outgoing_weakspot',snapshot.get('main_effect_source')),
    )
    inactive_main=next(((rule,source) for pattern,rule,source in inactive_main_rules if re.match(pattern,main)),None)
    if not inactive_main:
        return {'supported':False,'reason':'Main-effect effect on the incoming hit is not verified inactive'}
    trace=[{'rule':inactive_main[0],'status':'inactive for first incoming monster hit','source':inactive_main[1]}]
    reductions=[]
    outgoing={'All DMG Boost','Weapon DMG','Crit DMG','Weakspot DMG','Status DMG','Elemental DMG','Power Surge DMG','Shock DMG','Power Surge Trigger Chance'}
    for attr in snapshot['attributes']:
        name=attr.get('name')
        if name=='Damage from monsters received':
            if attr.get('direction')!='reduction' or attr.get('unit')!='percent' or attr.get('effective_value_percent') is None:
                return {'supported':False,'reason':'Monster damage reduction direction, unit, or condition unresolved'}
            reductions.append(attr)
        elif name=='Damage reduction after taking damage':
            trace.append({'rule':'prior_damage_required','status':'inactive for first hit','source':attr.get('source')})
        elif name=='Max HP':
            trace.append({'rule':'hp_not_hit_damage','status':'inactive for hit amount; affects survival margin','source':attr.get('source')})
        elif name in outgoing:
            trace.append({'rule':'outgoing_stat','status':'inactive for incoming hit','source':attr.get('source'),'attribute':name})
        else:return {'supported':False,'reason':f'{name} has unverified interaction with incoming monster hit'}
    if len(reductions)!=1:return {'supported':False,'reason':'Exactly one verified monster-damage reduction is required; stacking unresolved'}
    reduction=reductions[0]
    value=reduction['effective_value_percent']
    if not 0<=value<=100:return {'supported':False,'reason':'Reduction outside verified range'}
    damage=round(raw_hit*(1-value/100),4)
    trace.append({'rule':'isolated_monster_damage_reduction','formula':f'{raw_hit} × (1 − {value}/100) = {damage}','source':reduction.get('source'),'attribute':reduction['name'],'base_percent':reduction['base_value_percent'],'conditional_percent':reduction['conditional_value_percent'],'conditional_activation':reduction['conditional_activation_state']})
    return {'supported':True,'damage_taken':damage,'reduction_percent':value,'trace':trace}


def compare_catalog_selections(left, right, assumptions=None):
    """Explain a legal same-slot choice even when no personal weapon is known."""
    assumptions=assumptions or {}
    if left.get('slot')!=right.get('slot'):raise ValueError('Choose alternatives for the same equipment slot')
    if validate_loadout([left]) or validate_loadout([right]):raise ValueError('A selection is not equippable')
    def snapshot(item):
        catalog_id=(item.get('effects') or {}).get('catalog_id')
        resolved=catalog.resolve(catalog_id,item.get('level')) if catalog_id else None
        # Re-resolve current catalog evidence; persisted snapshots can predate a
        # semantic correction while their source observations remain unchanged.
        ambiguities=_import_semantic_uncertainties(item)
        attributes=[] if ambiguities else (resolved or {}).get('known_attributes') or (item.get('stats') or {}).get('catalog_attributes') or []
        main=(item.get('effects') or {}).get('text') or (resolved or {}).get('primary_effect') or ''
        structured_activation=(resolved or {}).get('entry',{}).get('activation_conditions') or []
        source=(resolved or {}).get('entry',{}).get('source_url')
        return {'id':item.get('id'),'name':item.get('name'),'variant':item.get('variant'),'level':item.get('level'),'slot':item.get('slot'),'catalog_id':catalog_id,'main_effect':main,'main_effect_source':source,'main_effect_activation':_main_effect_requirements(main,structured_activation),'main_effect_stacking':(resolved or {}).get('entry',{}).get('stacking_rule') or 'unknown','relative_trigger_rule':_relative_trigger_rule(main,assumptions,source),'attributes':[{**a,**_attribute_context(a,assumptions)} for a in attributes if isinstance(a,dict)],'numeric_coverage':'source_direction_ambiguous' if ambiguities else (resolved or {}).get('attribute_coverage') or (item.get('stats') or {}).get('attribute_coverage') or 'unresolved','unknowns':((resolved or {}).get('unknowns') or [])+(['Imported attribute direction is ambiguous in the source; numeric attributes excluded from comparison.'] if ambiguities else []),'evidence':item.get('evidence') or []}
    a=snapshot(left);b=snapshot(right)
    def key(attribute):return (attribute.get('name'),attribute.get('unit','percent'),attribute.get('direction','increase'),attribute.get('condition'),attribute.get('conditional_bonus_percent'))
    before={key(x):x for x in a['attributes']};after={key(x):x for x in b['attributes']}
    changes=[]
    for semantic_key in sorted(set(before)|set(after),key=str):
        x=before.get(semantic_key);y=after.get(semantic_key)
        if x==y:continue
        vx=x.get('value_percent') if x else None;vy=y.get('value_percent') if y else None
        delta=round(vy-vx,4) if isinstance(vx,(int,float)) and isinstance(vy,(int,float)) else None
        changes.append({'name':semantic_key[0],'from':x,'to':y,'numeric_delta_percent':delta,'modifier_delta_percentage_points':delta if (y or x).get('unit')=='percent' else None,'meaning':(y or x).get('component'),'activation':(y or x).get('activation_state'),'weapon_family_note':(y or x).get('weapon_family_note'),'operator':(y or x).get('operator'),'outgoing_damage_status':(y or x).get('outgoing_damage_status')})
    blockers=[]
    if not assumptions.get('weapon_family'):blockers.append('Selected weapon family or equipped primary weapon is unknown.')
    if a['main_effect']!=b['main_effect']:blockers.append('The main effects differ; their trigger rates, uptime, and interaction with the selected weapon are not fully modeled.')
    if changes:blockers.append('Stacking and component formulas for changed attributes are not verified as a complete damage model.')
    if a['numeric_coverage']!='complete' or b['numeric_coverage']!='complete':blockers.append('At least one numeric attribute profile is incomplete.')
    evidence_needed=[]
    if not assumptions.get('weapon_family'):evidence_needed.append('Equipped primary weapon identity and its damage/proc family.')
    if a['main_effect']!=b['main_effect']:evidence_needed.append('Current main-effect trigger rate, event damage, duration, stack cap, and uptime for this weapon and target.')
    if any('trigger chance' in c['name'].lower() for c in changes):evidence_needed.append('Base trigger chance and whether each tooltip chance bonus is relative or in percentage points.')
    if any(c['activation']=='requires verification' for c in changes):evidence_needed.append('Encounter state and condition uptime for changed conditional attributes.')
    if changes:evidence_needed.append('Damage-bucket stacking order and any active buffs that share those buckets.')
    findings=[]
    for change in changes:
        delta=change['modifier_delta_percentage_points']
        if delta is not None and delta!=0:
            findings.append(f"{change['name']}: alternative has {delta:+g} percentage points of the listed modifier; {change['outgoing_damage_status']}.")
    if a['main_effect']==b['main_effect'] and all(c['outgoing_damage_status'].startswith('proven inactive') or c['numeric_delta_percent']==0 for c in changes):
        findings.append('The resolved attributes and main-effect text show no changed outgoing damage modifier under the stated conditions; unmodeled level-dependent effects or stacking can still matter.')
    selected_metric=None;winner=None;winner_established=False;ranking_blockers=[]
    raw_hit=assumptions.get('incoming_monster_hit')
    if raw_hit is not None:
        raw_hit=_num(raw_hit,'first incoming monster hit',0)
        if raw_hit>0 and 'no incoming hits' in str(assumptions.get('conditions') or '').lower():
            ranking_blockers.append('A positive incoming hit conflicts with the stated no-incoming-hits condition.')
        elif a['catalog_id']!=b['catalog_id'] or a['main_effect']!=b['main_effect']:
            ranking_blockers.append('Isolated first-hit ranking requires the same verified main effect on both selections.')
        else:
            left_metric=_isolated_incoming_hit(a,raw_hit);right_metric=_isolated_incoming_hit(b,raw_hit)
            if left_metric['supported'] and right_metric['supported']:
                winner='left' if left_metric['damage_taken']<right_metric['damage_taken'] else 'right' if right_metric['damage_taken']<left_metric['damage_taken'] else 'tie'
                winner_established=True
                selected_metric={'name':'isolated first incoming monster hit','unit':'damage taken','left':left_metric,'right':right_metric,'winner':winner,'scope':'Same illustrative primary weapon and all other gear held fixed; PvE monster hit before prior-damage buffs; no other mitigation; lower damage is better; DPS and repeated-hit survival remain unranked'}
            else:ranking_blockers.extend(x['reason'] for x in (left_metric,right_metric) if not x['supported'])
    component_analysis=component_compare.compare(a,b,assumptions)
    return {'left':a,'right':b,'main_effect_changed':a['main_effect']!=b['main_effect'],'attribute_changes':changes,'supported_findings':findings,'component_analysis':component_analysis,'selected_metric':selected_metric,'ranking_blockers':ranking_blockers,'winner':winner,'calculation_coverage':{'numeric_profiles_complete':a['numeric_coverage']=='complete' and b['numeric_coverage']=='complete','selected_metric_rank_supported':winner_established,'overall_damage_rank_supported':False,'supported_comparison':'attribute values, directions, conditions, source-linked differences, isolated modifier component ratios, and isolated first-hit mitigation when validated'},'winner_established':winner_established,'blockers':blockers,'evidence_needed':evidence_needed,'assumptions':assumptions}


def optimize(items,locked=(),excluded=(),assumptions=None):
    assumptions=assumptions or {};locked=set(map(str,locked));excluded=set(map(str,excluded))
    if assumptions.get("goal","Sustained baseline") not in GOALS:raise ValueError(UNSUPPORTED_GOALS.get(assumptions.get("goal"),"Unsupported goal"))
    candidates=[i for i in items if i.get("slot")=="primary" and i.get('kind','instance') in EQUIPPABLE_KINDS and str(i["id"]) not in excluded]
    if locked:candidates=[i for i in candidates if str(i["id"]) in locked]
    scored=[{"item":i,"metric":_predicted_score([i],assumptions)} for i in candidates]
    key=GOALS[assumptions.get("goal","Sustained baseline")]
    supported=[x for x in scored if x["metric"].get("supported")]
    supported.sort(key=lambda x:x["metric"][key],reverse=True)
    return {"supported":supported,"unsupported":[x for x in scored if not x["metric"].get("supported")],"searched":len(candidates),"method":"exhaustive tooltip-base weapon proxy only; unresolved effects remain unranked"}


def search_loadouts(items,locked=(),excluded=(),assumptions=None,limit=50000):
    """Enumerate legal entered combinations. Rank only by modeled direct-hit score."""
    assumptions=assumptions or {};locked=set(map(str,locked));excluded=set(map(str,excluded))
    if assumptions.get("comparison_mode","predicted_equipment")!="predicted_equipment":raise ValueError("Equipment search requires predicted mode; measured hits are bound to exact saved loadouts")
    available=[i for i in items if str(i.get("id")) not in excluded and i.get("slot") in SLOTS and i.get('kind','instance') in EQUIPPABLE_KINDS]
    by_id={str(i.get("id")):i for i in available}
    if locked-set(by_id):raise ValueError("Locked item missing or excluded")
    locked_items=[by_id[x] for x in locked]
    if validate_loadout(locked_items):raise ValueError("Locked items conflict in equipment slots")
    groups=[]
    for slot in SLOTS:
        options=[i for i in available if i.get("slot")==slot]
        pinned=[i for i in options if str(i["id"]) in locked]
        if pinned:groups.append(pinned)
        elif slot=="primary":groups.append(options)
        elif options:groups.append([None]+options)
    count=prod(len(g) for g in groups) if groups else 0
    if count>limit:return {"results":[],"searched":0,"space":count,"complete":False,"reason":f"{count} legal combinations exceed the {limit} exhaustive limit. Narrow with locks or exclusions."}
    results=[];unsupported=0
    for combo in product(*groups):
        chosen=[x for x in combo if x is not None]
        r=score_loadout(chosen,assumptions)
        if r["rankable"]:results.append({"item_ids":[x["id"] for x in chosen],"items":chosen,**r})
        else:unsupported+=1
    results.sort(key=lambda r:r["score"],reverse=True)
    # Ties remain ties; unresolved gear is never ordered by note count or slots.
    return {"results":results[:12],"searched":count,"space":count,"complete":True,"unsupported":unsupported,"ranked":len(results),"winner_established":unsupported==0 and bool(results) and (len(results)==1 or results[0]["score"]>results[1]["score"]),"margin_to_next":round(results[0]["score"]-results[1]["score"],2) if len(results)>1 else None,"method":"exhaustive entered-slot combinations using only predicted tooltip-base proxy; unresolved gear is unranked and equal scores remain tied"}


def preview_upgrade(build, items, item_id, proposed_stats, assumptions):
    by_id={str(i["id"]):i for i in items};chosen=[by_id[str(x)] for x in build.get("item_ids",[]) if str(x) in by_id]
    if str(item_id) not in {str(i["id"]) for i in chosen}:raise ValueError("Selected item is not in this build")
    before=score_loadout(chosen,assumptions)
    after_items=[]
    for i in chosen:
        if str(i["id"])==str(item_id):
            modified={**i,"stats":{**(i.get("stats") or {}),**proposed_stats}}
            after_items.append(modified)
        else:after_items.append(i)
    after=score_loadout(after_items,assumptions)
    modeled_keys={"damage","rpm","magazine","reload_seconds","set_name"}
    changed={k for k,v in proposed_stats.items() if (next(i for i in chosen if str(i["id"])==str(item_id)).get("stats") or {}).get(k)!=v}
    selected=next(i for i in chosen if str(i["id"])==str(item_id))
    direct_keys={"damage","rpm","magazine","reload_seconds"}
    armor_slots={"helmet","mask","chest","gloves","pants","boots"}
    supported_change=bool(changed) and changed<=modeled_keys and (selected.get("slot")=="primary" and changed<=direct_keys or selected.get("slot") in armor_slots and changed=={"set_name"})
    delta=round(after["score"]-before["score"],2) if supported_change and before["score"] is not None and after["score"] is not None else None
    return {"before":before,"after":after,"delta":delta,"benefit_status":"modeled_proxy_change" if delta is not None else "benefit unknown","changed_fields":sorted(changed),"scope":"A result is shown only when the changed stat affects the supported model. Other changes require new tooltip or same-context combat evidence."}


def plan_session(activities, targets, minutes):
    """Only activities tied to missing targets; exact 0/1 time budget selection."""
    minutes=float(minutes)
    relevant=[a for a in activities if a.get("target_id") in targets and float(a.get("minutes") or 0)>0]
    best=[];best_score=(-1,float('-inf'))
    if len(relevant)>18:return {"activities":[],"minutes_used":0,"minutes_left":minutes,"eligible":len(relevant),"complete":False,"reason":"More than 18 linked activities; narrow the target set for an exhaustive plan."}
    for mask in range(1<<len(relevant)):
        chosen=[a for i,a in enumerate(relevant) if mask>>i&1]
        if len({a["target_id"] for a in chosen})!=len(chosen):continue
        spent=sum(float(a["minutes"]) for a in chosen)
        if spent>minutes:continue
        covered=len({a["target_id"] for a in chosen})
        score=(covered,-spent)
        if score>best_score:best,best_score=chosen,score
    return {"activities":best,"minutes_used":sum(float(a["minutes"]) for a in best),"minutes_left":minutes-sum(float(a["minutes"]) for a in best),"eligible":len(relevant),"complete":True,"method":"exhaustive target coverage over user-entered activity times; rewards and drop rates unknown"}
