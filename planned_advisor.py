"""Explain saved or unsaved catalog builds without asserting ownership or DPS.

Catalog values and current sourced rules are resolved on every request. A
planned selection never becomes an inventory instance or a measurement.
"""
from collections import Counter
from pathlib import Path
import json
import re

import catalog
import build_damage
import engine
import mechanics
import accessories
import component_compare
import published_item_tier
import native_gun_suffix
import native_tier_star
import native_tier_expanded
import native_tier_remaining
import native_partial_intake
import native_crosswalk_intake
import native_crosswalk_v2_intake
import aug_blueprint_preview
import native_weapon_attack
import native_attack_accumulator
import native_gear_preview
import native_weapon_interval_inputs
import native_weapon_interval_expanded
import native_direct_hit_graph
import native_armor_previews
import observed_character_panels
import historical_gear_tour

ROOT = Path(__file__).resolve().parent
RULES = json.loads((ROOT / 'rules.json').read_text())['rules']
SOURCES = {row['id']: row['url'] for row in json.loads((ROOT / 'knowledge.json').read_text())['sources']}
HISTORICAL_SET_SOURCE = 'https://github.com/lReDragol/OnceHuman_Tools/tree/d6b1d5b99f84cb6ddc6b8f85144ee067af2a4e45'
SLOT_LABELS = {'primary':'Primary weapon','secondary':'Secondary weapon','melee':'Melee weapon',
               'helmet':'Helmet','top':'Top','bottoms':'Bottoms','shoes':'Shoes','gloves':'Gloves','mask':'Mask'}
FAMILIES = ('power surge','shock','burn','frost vortex','shrapnel','unstable bomber',
            'fast gunner',"bull's eye",'fortress warfare','bounce')
OBSERVED_AUG_SOURCE = 'libfile_458a126cd8bc8191b6c0ed58b5669c12'
SHOCK_RAMPAGE_SOURCE = 'libfile_84a17de486208191951ea249c448e8c6'
NATIVE_GUN_EVIDENCE = native_gun_suffix.load_current(published_item_tier.ROWS)
NATIVE_TIER_STAR_EVIDENCE = native_tier_star.load_current(published_item_tier.ROWS)
NATIVE_EXPANDED_EVIDENCE = native_tier_expanded.load_current(catalog.ENTRIES)
NATIVE_REMAINING_EVIDENCE = native_tier_remaining.load_current(
    catalog.ENTRIES, NATIVE_TIER_STAR_EVIDENCE, NATIVE_EXPANDED_EVIDENCE)
NATIVE_PARTIAL_EVIDENCE = native_partial_intake.load_current(
    catalog.ENTRIES, NATIVE_TIER_STAR_EVIDENCE,
    NATIVE_EXPANDED_EVIDENCE, NATIVE_REMAINING_EVIDENCE)
NATIVE_INSTALLED_IDENTITIES = (
    set(NATIVE_PARTIAL_EVIDENCE['by_catalog']) |
    set(NATIVE_EXPANDED_EVIDENCE['by_catalog']) |
    set(NATIVE_REMAINING_EVIDENCE['by_catalog']) |
    {row['catalog_id'] for row in NATIVE_TIER_STAR_EVIDENCE['by_blueprint'].values()})
NATIVE_CROSSWALK_EVIDENCE = native_crosswalk_intake.load_current(
    catalog.ENTRIES, NATIVE_PARTIAL_EVIDENCE, NATIVE_INSTALLED_IDENTITIES)
NATIVE_CROSSWALK_V2_EVIDENCE = native_crosswalk_v2_intake.load_current(
    catalog.ENTRIES, NATIVE_PARTIAL_EVIDENCE,
    NATIVE_INSTALLED_IDENTITIES | set(NATIVE_CROSSWALK_EVIDENCE['by_catalog']))
AUG_BLUEPRINT_PREVIEW = aug_blueprint_preview.load_current(
    NATIVE_TIER_STAR_EVIDENCE['by_blueprint'][13451401])


def _weapon_reference_timing(slots, assumptions=None):
    """Named Tier I page timing facts, separate from crafted weapon readout."""
    selected = slots.get('primary') or {}
    identity = selected.get('catalog_id')
    row = published_item_tier.ROWS.get(identity)
    expanded = native_tier_expanded.selected(
        NATIVE_EXPANDED_EVIDENCE, identity, selected.get('tier'), selected.get('stars'))
    remaining = native_tier_remaining.selected(
        NATIVE_REMAINING_EVIDENCE, identity, selected.get('tier'), selected.get('stars'))
    partial = native_partial_intake.selected(
        NATIVE_PARTIAL_EVIDENCE, identity, selected.get('tier'), selected.get('stars'))
    crosswalk = native_crosswalk_intake.selected(
        NATIVE_CROSSWALK_EVIDENCE, identity, selected.get('tier'), selected.get('stars'))
    crosswalk_v2 = native_crosswalk_v2_intake.selected(
        NATIVE_CROSSWALK_V2_EVIDENCE, identity, selected.get('tier'), selected.get('stars'))
    blueprint_preview = aug_blueprint_preview.selected(
        AUG_BLUEPRINT_PREVIEW, identity, selected.get('tier'), selected.get('stars'))
    if not row and not expanded and not remaining and not partial and not crosswalk and not crosswalk_v2:
        return None
    if remaining is not None or partial is not None or crosswalk is not None or crosswalk_v2 is not None:
        evidence = next(x for x in (remaining,partial,crosswalk,crosswalk_v2) if x is not None)
        return {'reference_status':'native_identity_only',
                'rpm':None,'fire_rate_raw':None,
                'rpm_unit_status':'not_checked','magazine':None,
                'source_ref':evidence['public_blueprint_url'],
                'blueprint_ref':evidence['public_blueprint_url'],
                'native_evidence':None,
                'native_selected_tier_star':evidence,
                'native_attack_component':native_weapon_attack.selected(evidence),
                'native_attack_property':native_attack_accumulator.selected(
                    native_weapon_attack.selected(evidence),
                    (assumptions or {}).get('native_attack_affix_scenario')),
                'native_interval_inputs':(native_weapon_interval_expanded.selected(evidence) or
                                          native_weapon_interval_inputs.selected(evidence,NATIVE_TIER_STAR_EVIDENCE['by_blueprint'])),
                'blueprint_preview':blueprint_preview,
                'scope':'Named blueprint and source-native fields, with a tier/star base weapon Attack component when both typed fields exist. Current crafted Attack, RPM and final damage remain unknown.'}
    verified = published_item_tier.TIER1_TIMING.get(identity) or {}
    conditional = published_item_tier.TIER1_CONDITIONAL_TIMING.get(identity) or {}
    rpm_source = verified.get('fire_rate_rpm') or conditional.get('fire_rate_rpm')
    magazine_source = verified.get('magazine_capacity')
    fields = {record['native_field_identifier']: record['raw_value']
              for record in NATIVE_GUN_EVIDENCE['source_packet']['records']
              if record['catalog_id'] == identity}
    native_tier = native_tier_star.selected(
        NATIVE_TIER_STAR_EVIDENCE, identity, selected.get('tier'), selected.get('stars')) or expanded
    public_tier_one = expanded.get('public_tier_one') if expanded else None
    return {'rpm': rpm_source['value'] if rpm_source and
            rpm_source['unit_evidence']=='explicit_secondary_rpm_label' else None,
            'fire_rate_raw': rpm_source['raw_value'] if rpm_source else
                             str(public_tier_one['fire_rate_raw']) if public_tier_one else None,
            'rpm_unit_status': rpm_source['unit_evidence'] if rpm_source else
                               'public_fire_rate_unit_unverified',
            'magazine': magazine_source['value'] if magazine_source else
                        public_tier_one['magazine_capacity'] if public_tier_one else None,
            'source_ref': row['tiers']['1']['thgl_gear_url'] if row else public_tier_one['url'],
            'blueprint_ref': row['blueprint_url'] if row else public_tier_one['blueprint_url'],
            'native_evidence': {'weapon_rpm_affix_value': fields.get('weapon_rpm_affix_value'),
                                'weapon_rpm': fields.get('weapon_rpm'),
                                'magazine_affix_value': fields.get('weapon_magazine_size_affix_value'),
                                'status': 'evidence_only; field consumer and crafted scope unknown',
                                'steam_build_id': NATIVE_GUN_EVIDENCE['source_packet']['source']['steam_build_id']},
            'native_selected_tier_star': native_tier,
            'native_attack_component':native_weapon_attack.selected(native_tier),
            'native_attack_property':native_attack_accumulator.selected(
                native_weapon_attack.selected(native_tier),
                (assumptions or {}).get('native_attack_affix_scenario')),
            'native_interval_inputs':(native_weapon_interval_expanded.selected(native_tier) or
                                      native_weapon_interval_inputs.selected(native_tier,NATIVE_TIER_STAR_EVIDENCE['by_blueprint'])),
            'blueprint_preview':blueprint_preview,
            'scope': 'Tier I published item reference and source-native tier/star base weapon Attack component. Selected mods, calibration and accessories may change current Attack and final damage; RPM is separate.'}


def _one_stack_trigger_scenario(slots, parts):
    """One active Shock Rampage core stack, never average proc frequency or DPS."""
    primary = slots.get('primary') or {}
    if primary.get('catalog_id') != 'weapon:aug-electron-cloud' or primary.get('mod_id') != 'mod:weapon_mod:shock-rampage-power-surge' or primary.get('mod_level') != 17:
        return None
    readout = primary.get('weapon_readout') or {}
    base_percent = readout.get('base_trigger_chance_percent')
    source = 'manually entered for this weapon setup'
    if base_percent is None and (readout.get('source_ref') == OBSERVED_AUG_SOURCE and
                                 primary.get('tier') == 4 and primary.get('stars') == 5 and
                                 (primary.get('calibration_profile') or {}).get('style') == 'Vanguard Style'):
        base_percent, source = 30, OBSERVED_AUG_SOURCE
    if base_percent is None:
        return {'needs':'This setup’s base Power Surge trigger chance is unobserved. A different Tier IV Vanguard tooltip showed 30%; use it only as an unsaved what-if, not a current Energy-setup fact.',
                'mod_source':SHOCK_RAMPAGE_SOURCE}
    mod = next((part.get('mod') for part in parts if part['slot'] == 'primary'), None)
    rule = engine._relative_trigger_rule((mod or {}).get('effect'), {'base_trigger_chance':base_percent/100}, SHOCK_RAMPAGE_SOURCE)
    if not rule or rule['one_stack_chance'] is None:
        return {'needs':'The one-stack trigger factor cannot be resolved for this setup.', 'mod_source':SHOCK_RAMPAGE_SOURCE}
    return {'base_percent':base_percent,'one_stack_percent':round(rule['one_stack_chance']*100,4),
            'change_percentage_points':rule['one_stack_change_percentage_points'],
            'duration_seconds':rule['duration_seconds'],'max_stacks_text':rule['max_stacks_text'],
            'base_source':source,'mod_source':SHOCK_RAMPAGE_SOURCE,
            'limit':'Assumes the pictured +5% multiplies base chance as its wording suggests, with one active core-effect stack. Stack buildup, uptime, the separate +6% trigger attribute, proc damage and total DPS are unmodeled.'}


def _entry(catalog_id, level=None, context=None, *, shiny=False):
    if not catalog_id:
        return None
    resolved = catalog.resolve(catalog_id, level, shiny=shiny)
    entry = resolved['entry']
    attributes = []
    line_rows = resolved.get('known_attributes') or []
    numeric_coverage = resolved.get('attribute_coverage')
    if entry['kind'] == 'mod' and isinstance(level, int) and not isinstance(level, bool):
        import public_catalog_detail
        candidate_rows, candidate_coverage, candidate_status = public_catalog_detail.calculation_rows(
            catalog_id, level, shiny=shiny, resolved=resolved)
        if candidate_status != 'blocked':
            line_rows = candidate_rows
            numeric_coverage = candidate_coverage
    for attribute in line_rows:
        attributes.append({**attribute, **engine._attribute_context(attribute, context or {})})
    text = resolved.get('primary_effect') or entry.get('effect') or ''
    sourced_rule = build_damage.RULES.get(f'{catalog_id}:{level}')
    if not text and sourced_rule and sourced_rule['rule_id']=='elemental-resonance-prev-mag-lv17':
        text = ('Elemental damage in the previous magazine can grant a timed Elemental DMG buff after reload. '
                'The official Lv. 17 Shiny card shows +1% per event, up to +24%; ordinary main-effect strength is unresolved.')
    if sourced_rule and sourced_rule['rule_id']=='ferocious-charge-downstar-lv17':
        text = ('A kill within 10 meters can grant an eight-second Weapon/Status DMG buff. '
                'The official Lv. 17 Shiny card shows +20%; ordinary main-effect strength is unresolved.')
    return {
        'catalog_id': catalog_id, 'name': entry.get('display_name') or entry['name'],
        'base_name': entry['name'], 'variant': entry.get('variant'), 'kind': entry['kind'],
        'shiny': shiny,
        'slot': entry.get('slot'), 'level': level, 'rarity': entry.get('rarity'),
        'set_id': entry.get('set_id'), 'effect': text,
        'effect_source': sourced_rule.get('source_page') if sourced_rule and sourced_rule.get('source_page') else entry.get('source_url') or entry.get('source'),
        'effect_activation': engine._main_effect_requirements(text, entry.get('activation_conditions') or []),
        'effect_calculation': 'unresolved' if text else 'no current effect recorded',
        'effect_state': _effect_state(catalog_id, resolved, context or {}),
        'known_effects': resolved.get('known_effects') or [],
        'attributes': attributes,
        'attribute_coverage': numeric_coverage or ('not applicable' if entry['kind'] != 'mod' else 'unresolved'),
        'unknowns': resolved.get('unknowns') or [],
    }


def _effect_state(catalog_id, resolved, context):
    rule = build_damage.RULES.get(f"{catalog_id}:{resolved.get('level')}")
    if rule and rule['rule_id']=='distant-strike-weakspot-lv10':
        distance=context.get('distance_meters')
        return {'base':'listed weak-spot modifier beyond 20 meters',
                'conditional':'distance unknown' if distance is None else
                              'inactive at stated distance' if float(distance)<=20 else
                              'active; extra per-meter amount bounded in outgoing estimate'}
    if rule and rule['rule_id']=='elemental-resonance-prev-mag-lv17':
        events=context.get('prior_magazine_elemental_events')
        return {'base':'ordinary main magnitude unresolved; Shiny tooltip sourced',
                'conditional':'prior-magazine elemental events unknown' if events is None else
                              'inactive: zero prior-magazine elemental events' if int(events)==0 else
                              'active; event timing and ordinary magnitude unresolved'}
    if rule and rule['rule_id']=='ferocious-charge-downstar-lv17':
        kills=context.get('nearby_kills')
        return {'base':'ordinary main magnitude unresolved; Shiny tooltip sourced',
                'conditional':'nearby kills unknown' if kills is None else
                              'inactive: no kill within 10 meters' if int(kills)==0 else
                              'active for eight seconds; ordinary magnitude unresolved'}
    if not resolved.get('primary_effect'):
        return {'base':'not cataloged','conditional':'unknown; no current effect text'}
    if not resolved.get('verified_main_effect'):
        return {'base':'unverified at this level','conditional':'trigger and uptime unresolved'}
    if catalog_id == 'mod:boots_mod:against-all-odds-precision':
        condition = context.get('hp_consumed',context.get('hp_lost'))
        return {'base':'listed +10% Weapon and Status DMG',
                'conditional':'inactive: no HP lost' if condition is False else
                    'requires HP loss; magnitude and uptime unresolved' if condition is True else
                    'unknown: HP-loss condition not supplied'}
    if catalog_id == 'mod:boots_mod:power-of-striving-downstar-deviant-energy':
        stamina = context.get('stamina_spent')
        elevation = context.get('same_elevation')
        return {'base':'listed +10% Weapon and Status DMG',
                'conditional':('inactive stamina addition: no stamina spent' if stamina is False else
                               'stamina addition magnitude and uptime unresolved' if stamina is True else
                               'stamina condition unknown') + '; ' +
                              ('inactive Downstar elevation addition: same elevation' if elevation is True else
                               'Downstar elevation magnitude unresolved' if elevation is False else
                               'elevation condition unknown')}
    return {'base':'cataloged effect; exact activation unresolved',
            'conditional':'trigger, uptime, and stacking unresolved'}


def _weapon_context(slots, assumptions):
    primary = slots.get('primary') or {}
    weapon = catalog.ENTRIES.get(primary.get('catalog_id')) or {}
    signature = ' '.join((str(weapon.get('name') or ''), str(weapon.get('family') or ''),
                          str(weapon.get('effect') or ''), json.dumps(weapon.get('structured_effects') or []))).lower()
    return {'weapon': weapon, 'signature': signature,
            'context': {**assumptions, 'weapon_family': signature}}


def _set_summary(slots, assumptions):
    counts = Counter()
    for slot in ('helmet','top','bottoms','shoes','gloves','mask'):
        gear = catalog.ENTRIES.get((slots.get(slot) or {}).get('catalog_id')) or {}
        if gear.get('set_id'):
            counts[gear['set_id']] += 1
    groups = []
    for set_id, count in sorted(counts.items()):
        item = catalog.ENTRIES.get('set:' + set_id.replace('_','-')) or {}
        name = re.sub(r'\s+Set$', '', item.get('name') or set_id.replace('_',' ').title())
        thresholds = []
        current = [rule for rule in RULES if rule.get('system') == 'set' and rule.get('set_name','').casefold() == name.casefold()]
        for rule in current:
            required = rule['pieces']
            state = 'not reached' if count < required else 'unknown activation'
            mode_supported = str(assumptions.get('scenario') or '').casefold() in ('pve','pve non-raidzone')
            if count >= required and rule['id'] == 'bastille_two_reload_efficiency':
                state = 'active in stated non-RaidZone scenario' if mode_supported else 'threshold reached; scenario applicability unresolved'
            if count >= required and rule['id'] == 'treacherous_tides_two_weapon':
                hp = assumptions.get('hp_fraction')
                scenario = str(assumptions.get('scenario') or '').casefold()
                state = 'unknown: enter HP fraction' if hp is None else 'inactive at stated HP' if float(hp) >= .7 else (
                    'active' if scenario in ('pve','pve non-raidzone') else
                    'HP condition met; scenario applicability unresolved')
            if count >= required and rule['id'] == 'treacherous_tides_three':
                hp = assumptions.get('hp_fraction')
                state = 'threshold reached; scenario applicability unresolved' if not mode_supported else 'active; HP needed for magnitude' if hp is None else (
                    'active; sourced 8% endpoint' if float(hp) >= 1 else
                    'active; sourced 28% endpoint' if float(hp) <= .6 else
                    'active; exact interpolation unresolved')
            if count >= required and rule['id'] == 'treacherous_tides_four_shield':
                state = 'threshold reached; current shield trigger, amount and cooldown unverified (preview values only)'
            thresholds.append({'pieces':required,'state':state,'description':_rule_description(rule),
                               'source':SOURCES.get(rule.get('source')),'evidence_status':rule.get('evidence_status'),
                               'calculation':rule.get('calculation')})
        if not current:
            for bonus in item.get('bonuses') or []:
                thresholds.append({'pieces':bonus['required_items'],
                                   'state':'historical threshold reached; current effect unverified' if count >= bonus['required_items'] else 'not reached',
                                   'description':bonus.get('description') or 'Effect not recorded',
                                   'source':HISTORICAL_SET_SOURCE,'evidence_status':'March 2026 community snapshot; current effect unverified',
                                   'calculation':'unresolved'})
        groups.append({'set_id':set_id,'name':name,'count':count,'thresholds':sorted(thresholds,key=lambda x:x['pieces']),
                       'conflicting_historical_record':bool(current and item.get('bonuses'))})
    return groups


def _rule_description(rule):
    if rule['id'] == 'bastille_two_reload_efficiency':
        return '+15% Reload Efficiency (replaces old Reload Speed effect); actual reload time requires base seconds.'
    if rule['id'] == 'treacherous_tides_two_weapon':
        return '+12% Weapon and Status DMG below 70% HP (PvE non-RaidZone).'
    if rule['id'] == 'treacherous_tides_three':
        return '8–28% Weapon and Status DMG from 100% to 60% HP; interpolation unresolved.'
    if rule['id'] == 'treacherous_tides_four_shield':
        return 'Shield enhancement confirmed; 30% Max HP below 40% HP and 8s cooldown are preview-only test values.'
    return rule.get('calculation') or rule['id']


def _synergies(parts, weapon_signature):
    out = []
    weapon_families = [family for family in FAMILIES if family in weapon_signature]
    for part in parts:
        for item in (part.get('gear'), part.get('mod')):
            if not item:
                continue
            text = (item['effect'] + ' ' + json.dumps(item['known_effects'])).lower()
            for family in weapon_families:
                if family in text and item['kind'] != 'weapon':
                    out.append({'item':item['name'],'family':family.title(),
                                'text':f"{item['name']} mentions {family.title()}, which also appears in the selected primary weapon's catalog effect. Trigger, uptime, and stacking still need verification.",
                                'source':item['effect_source'],'status':'potential; damage not calculated'})
    return out


def _next_step(parts, sets, slots):
    if not (slots.get('primary') or {}).get('catalog_id'):
        return {'text':'Choose a primary weapon to connect mod effects to a damage family.', 'kind':'complete build'}
    primary = (catalog.ENTRIES.get(slots['primary']['catalog_id']) or {}).get('name','').lower()
    selected = {(part['gear'] or {}).get('catalog_id') for part in parts}
    for trigger, target, slot, source, reason in (
        ('cosmic visitor','armor:snowline-elite-vest','top','patch311',
         'Its official rule repeats Vortex-triggered effects, but event damage and uptime remain unresolved.'),
        ('fiery trees','armor:wind-intepreter-cap','helmet','julygear',
         'Its official rule reloads a bullet after Unstable Bomber explosions, but total damage benefit remains unresolved.')):
        if trigger in primary and target not in selected and target in catalog.ENTRIES:
            return {'text':f"Compare {catalog.ENTRIES[target]['name']} in the {SLOT_LABELS[slot].lower()} slot. {reason} Replacing current gear may lose other effects.",
                    'kind':'sourced interaction','slot':slot,'catalog_id':target,'source':SOURCES.get(source)}
    for part in parts:
        if not part['gear']:
            return {'text':f"Choose {part['label'].lower()} gear so its set contribution and compatible mod can be reviewed.", 'kind':'complete build','slot':part['slot']}
        if part['slot'] != 'melee' and not part['mod']:
            return {'text':f"Attach a {part['label'].lower()} mod. Its known attributes will appear here; damage benefit remains unranked until its effects are modeled.", 'kind':'fill mod','slot':part['slot']}
    for group in sets:
        if any(t['pieces'] == group['count']+1 and t['evidence_status'] == 'official live update' for t in group['thresholds']):
            return {'text':f"Inspect a {group['name']} piece for the {group['count']+1}-piece sourced threshold. Replacing current armor may lose other effects, so compare both builds first.",
                    'kind':'set opportunity','set_id':group['set_id']}
    return {'text':'Duplicate this build and change one piece, then compare the listed effects. Enter same-target hit and firing inputs only for a supported scoped damage estimate.',
            'kind':'compare'}


def analyze(slots, assumptions=None):
    assumptions = assumptions or {}
    preview_scenario = assumptions.get('synthetic_gear_preview_scenario')
    preview_result = (native_gear_preview.project(
        preview_scenario, (slots.get('primary') or {}).get('catalog_id'))
        if preview_scenario is not None else None)
    bullet_scenario = assumptions.get('native_player_bullet_scenario')
    bullet_result = None
    if bullet_scenario is not None:
        if not isinstance(bullet_scenario, dict) or bullet_scenario.get('weapon_id') != (slots.get('primary') or {}).get('catalog_id'):
            raise ValueError('Explicit native player bullet scenario must match the selected primary weapon')
        bullet_result = native_direct_hit_graph.player_bullet_scenario(bullet_scenario)
    weapon = _weapon_context(slots, assumptions)
    parts = []
    blockers = []
    for slot, label in SLOT_LABELS.items():
        selected = slots.get(slot) or {}
        gear = _entry(selected.get('catalog_id'), selected.get('level'), weapon['context'])
        mod = _entry(selected.get('mod_id'), selected.get('mod_level'), weapon['context'],
                     shiny=selected.get('mod_shiny') is True)
        armor_preview = (native_armor_previews.for_catalog_configuration(selected['catalog_id'],
                         selected.get('tier'), selected.get('stars'))
                         if slot in ('helmet','mask','top','gloves','bottoms','shoes') and gear else None)
        parts.append({'slot':slot,'label':label,'gear':gear,'mod':mod,
                      'native_armor_base_preview':armor_preview,
                      'settings':{key:selected.get(key) for key in ('level','tier','stars','mod_level','calibration_blueprint','calibration_bonus','calibration_profile','calibration_upgrade_level','legacy_enhancement','accessories') if selected.get(key) is not None},
                      'accessories':[accessories.ITEMS[item_id] for item_id in (selected.get('accessories') or {}).values() if item_id in accessories.ITEMS]})
        if gear and any(selected.get(key) is not None for key in ('tier','stars','calibration_blueprint','calibration_bonus','calibration_profile','calibration_upgrade_level','legacy_enhancement')):
            blockers.append(f"{label}: selected tier, blueprint stars, calibration-blueprint rolls, and legacy enhancement are saved but their resulting damage and defenses are not calculated.")
        if selected.get('accessories'):
            blockers.append(f"{label}: accessory effects are listed but their combat stacking and resulting DPS are not calculated.")
        for item in (gear, mod):
            if not item:
                continue
            if item['effect']:
                blockers.append(f"{label} {item['name']}: full effect calculation is unresolved")
            if item['kind'] == 'mod' and item['attribute_coverage'] != 'complete':
                blockers.append(f"{label} {item['name']} Lv {item['level']}: exact attribute profile incomplete")
            if item['unknowns']:
                blockers.extend(f"{label} {item['name']}: {unknown}" for unknown in item['unknowns'])
    sets = _set_summary(slots, assumptions)
    for group in sets:
        for threshold in group['thresholds']:
            if group['count'] >= threshold['pieces'] and threshold['calculation'] != 'isolated single active weapon-damage bonus on a tooltip-base proxy':
                blockers.append(f"{group['name']} {threshold['pieces']}-piece: {threshold['calculation']}")
    return {'slots':parts,'sets':sets,'synergies':_synergies(parts,weapon['signature']),
            'unlinked_character_panel_observation':observed_character_panels.observation(),
            'historical_gear_tour_snapshot':(
                {'observation': historical_gear_tour.snapshot(),
                 'controlled_one_bullet_example': historical_gear_tour.controlled_one_bullet_example()}
                if (slots.get('primary') or {}).get('catalog_id') == 'weapon:aug-electron-cloud' else None),
            'matched_reference_component':None,
            'weapon_reference_timing':_weapon_reference_timing(slots, assumptions),
            'native_player_bullet_scenario':bullet_result,
            'synthetic_gear_preview_scenario':preview_result,
            'trigger_scenario':_one_stack_trigger_scenario(slots,parts),
            'weapon':{'name':weapon['weapon'].get('name'),'family':weapon['weapon'].get('family'),
                      'effect_families':[family.title() for family in FAMILIES if family in weapon['signature']],
                      'capabilities':mechanics.weapon_capabilities((slots.get('primary') or {}).get('catalog_id')),
                      'reference_profile':build_damage.WEAPONS.get((slots.get('primary') or {}).get('catalog_id'))},
            'next_step':_next_step(parts,sets,slots),
            'compatibility':'All selected gear and mods fit their equipment slots; empty slots remain optional in a plan.',
            'unresolved':list(dict.fromkeys(blockers)),
            'scope':'Catalog identities and selected levels, independent of owned inventory; no overall DPS estimate.'}


def _listed_attribute_changes(before, after):
    def keyed(part):
        mod = part.get('mod') or {}
        return {(x.get('name'),x.get('unit'),x.get('direction'),x.get('condition'),
                 x.get('conditional_bonus_percent')):x for x in mod.get('attributes') or []}
    old, new = keyed(before), keyed(after)
    rows = []
    for key in sorted(old.keys() | new.keys(),key=str):
        a,b=old.get(key),new.get(key)
        if a == b:
            continue
        rows.append({'name':key[0],'before':a,'after':b,
                     'component':(b or a).get('component'),
                     'meaning':'listed modifier for this mod slot; total build stacking unresolved',
                     'numeric_delta_percent':round(b['value_percent']-a['value_percent'],4)
                         if a and b and isinstance(a.get('value_percent'),(int,float)) and isinstance(b.get('value_percent'),(int,float)) else None})
    return rows


def compare(left, right, assumptions=None, outgoing_inputs=None):
    assumptions = assumptions or {}
    context = {**assumptions, **(outgoing_inputs or {})}
    if context.get('same_elevation') is True:
        context['conditions'] = str(context.get('conditions') or '') + '; same elevation'
    a = analyze(left, context)
    b = analyze(right, context)
    def reviewed_build(analysis):
        items = []
        for part in analysis['slots']:
            for selected in (part.get('gear'), part.get('mod')):
                if selected:
                    items.append({'name': selected['name'], 'catalog_id': selected.get('catalog_id'),
                                  'level': selected.get('level'), 'source': selected.get('effect_source'),
                                  'main_effect': selected.get('effect'),
                                  'numeric_coverage': selected.get('attribute_coverage') if selected['kind'] == 'mod' else None,
                                  'attributes': selected.get('attributes') or []})
        return {'name': 'Saved planned build', 'items': items, 'sets': analysis['sets']}
    component_analysis = component_compare.compare(reviewed_build(a), reviewed_build(b), context)
    changes = []
    mod_comparisons = []
    for slot, label in SLOT_LABELS.items():
        old, new = left.get(slot) or {}, right.get(slot) or {}
        if old == new:
            continue
        changed_fields = [key for key in ('catalog_id','level','tier','stars','calibration_blueprint','calibration_bonus','calibration_profile','calibration_upgrade_level','legacy_enhancement','accessories','mod_id','mod_level') if old.get(key) != new.get(key)]
        before, after = next(p for p in a['slots'] if p['slot'] == slot), next(p for p in b['slots'] if p['slot'] == slot)
        changes.append({'slot':slot,'label':label,'fields':changed_fields,'before':before,'after':after,
                        'listed_attribute_changes':_listed_attribute_changes(before,after)})
        if old.get('mod_id') and new.get('mod_id') and ('mod_id' in changed_fields or 'mod_level' in changed_fields):
            items = []
            for side, selected in (('left',old),('right',new)):
                resolved = catalog.resolve(selected['mod_id'], selected['mod_level'])
                items.append({'id':f'planned-{side}-{slot}','name':resolved['entry']['name'],
                              'kind':'mod_unlock','slot':resolved['entry']['slot'],'level':selected['mod_level'],
                              'effects':{'catalog_id':selected['mod_id'],'text':resolved['primary_effect'] or ''}})
            mod_comparisons.append({'slot':slot,'result':engine.compare_catalog_selections(items[0],items[1],
                {**assumptions,'weapon_family':_weapon_context(left,assumptions)['signature']})})
    set_changes = []
    before_sets = {item['set_id']:item for item in a['sets']}
    after_sets = {item['set_id']:item for item in b['sets']}
    for identity in sorted(before_sets.keys() | after_sets.keys()):
        x, y = before_sets.get(identity), after_sets.get(identity)
        if (x or {}).get('count',0) != (y or {}).get('count',0):
            set_changes.append({'set_id':identity,'name':(y or x)['name'],'before':x,'after':y})
    blockers = []
    if changes:
        blockers.append('Cross-item damage stacking and unresolved main effects prevent an overall DPS winner.')
    for change in changes:
        if any(field in change['fields'] for field in ('level','tier','stars','calibration_blueprint','calibration_bonus','calibration_profile','calibration_upgrade_level','legacy_enhancement')):
            blockers.append(f"{change['label']}: tier, blueprint stars, calibration-blueprint rolls, or retained legacy enhancement lack a validated damage formula.")
        for side in ('before','after'):
            for item in (change[side]['gear'],change[side]['mod']):
                if item and item['effect']:
                    blockers.append(f"{change['label']} {item['name']}: trigger and stacking may affect damage.")
                if item and item['kind']=='mod' and item['attribute_coverage']!='complete':
                    blockers.append(f"{change['label']} {item['name']}: numeric profile incomplete at selected level.")
    for group in set_changes:
        blockers.append(f"{group['name']}: set threshold activation or interaction changes with piece count.")
    scoped = None
    if outgoing_inputs:
        scoped=build_damage.compare_saved(left,right,outgoing_inputs)
        blockers.extend(scoped.get('blockers') or [])
    return {'left':a,'right':b,'changes':changes,'mod_comparisons':mod_comparisons,
            'component_analysis':component_analysis,
            'set_changes':set_changes,'scoped_outgoing':scoped,'winner_established':False,
            'overall_blockers':list(dict.fromkeys(blockers)),
            'scope':'Known catalog differences and optional direct-only scoped estimate; no unsupported full-build winner.'}
