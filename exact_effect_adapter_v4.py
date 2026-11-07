"""Typed output adapter for the 52 observed main-mod effects.

This evaluates one explicitly supplied combat state or event. It does not infer
event frequency, uptime, shield capacity, source-era applicability or DPS.
"""
from __future__ import annotations

from evaluate_template_v3 import UnknownCombatState


def need(context: dict, key: str):
    if key not in context or context[key] is None:
        raise UnknownCombatState(key)
    return context[key]


def stat(stat: str, amount: float, **extra):
    return {'type':'stat_pool_delta','stat':stat,'percentage_points':amount,**extra}


def execute(rule: dict, context: dict) -> dict:
    """Return typed outputs and unresolved mechanics; absence of context raises."""
    op=rule['operator'];n=rule['nodes'];out=[];pending=list(rule.get('unresolved',[]))
    if op=='static_modifier':
        for item in n:
            if item['op']!='stat_delta_percent':raise NotImplementedError(item['op'])
            if item['stat'].endswith('_status_duration_percent'):
                out.append({'type':'status_duration_delta','stat':item['stat'],
                            'percentage_points':item['value']})
            else:out.append(stat(item['stat'],item['value']))

    elif op=='threshold_modifier':
        threshold=rule['threshold'];value=need(context,threshold['resource'])
        active=value<threshold['value'] if threshold['comparison']=='below' else value>threshold['value']
        if active:out += [stat(x['stat'],x['value']) for x in n]

    elif op=='base_plus_threshold':
        for item in n:
            if item['op']=='stat_delta_percent':out.append(stat(item['stat'],item['value']))
            else:
                c=item['condition'];value=need(context,c['resource'])
                active=(value>c['value']) if c['comparison']=='above' else (value<c['value'])
                if active:
                    out.append(stat(item['stat'],item['value'],condition=c))

    elif op=='shield_state_and_nonpenetration':
        active=need(context,'shield_active')
        shield=need(context,'shield_points')
        if active:
            out.append(stat('damage_reduction_percent',n[0]['value'],condition={'shield_active':True}))
            if shield>n[1]['shield_points_above']:
                out.append({'type':'shield_nonpenetration_rule','single_damage_instance':True,
                            'shield_threshold_points':n[1]['shield_points_above'],
                            'damage_mitigation_amount':'not_computed'})

    elif op=='proximity_and_event_modifier':
        enemies=need(context,'enemies_within_distance')
        melee_buff=need(context,'received_melee_damage_buff_active')
        if enemies>=n[0]['condition']['minimum_count']:
            out.append(stat(n[0]['stat'],n[0]['value'],condition=n[0]['condition']))
        if melee_buff:
            out.append(stat(n[1]['stat'],n[1]['value'],event=n[1]['event'],
                            duration_seconds=n[1]['duration_seconds']))

    elif op=='periodic_stack_and_hit_decay':
        stacks=need(context,'active_stacks')
        if not isinstance(stacks,int) or not 0<=stacks<=rule['max_stacks']:
            raise ValueError('active_stacks outside known cap')
        out.append(stat(n[0]['stat'],n[0]['value']*stacks,active_stacks=stacks))
        out.append({'type':'stack_rule','condition':rule['condition'],
                    'interval_seconds':rule['interval_seconds'],'max_stacks':rule['max_stacks'],
                    'loss_event':rule['loss_event'],'stacks_lost':rule['stacks_lost']})

    elif op=='threshold_status_purge':
        hp=need(context,'hp_percent');ready=need(context,'cooldown_available')
        if hp<rule['threshold']['value'] and ready:
            out.append({'type':'status_purge','category':'deviated_states',
                        'cooldown_seconds':rule['cooldown_seconds']})

    elif op=='event_modifier_and_ammo_refill':
        fired=need(context,'healing_shot_used')
        if fired:
            current=need(context,'current_magazine_bullets')
            capacity=need(context,'magazine_capacity_bullets')
            inventory=need(context,'inventory_bullets')
            if not (0<=current<=capacity and inventory>=0):raise ValueError('invalid ammo state')
            transfer=min(capacity-current,inventory)
            out.append(stat(n[0]['stat'],n[0]['value'],duration_seconds=n[0]['duration_seconds'],event='healing_shot'))
            out.append({'type':'ammo_transfer','from':'inventory','to':'magazine',
                        'bullets':transfer,'magazine_after':current+transfer,
                        'inventory_after':inventory-transfer,'target_fill_percent':n[1]['value']})

    elif op=='conditional_heal_and_shield_conversion':
        killed=need(context,'enemy_defeated')
        if killed:
            max_hp=need(context,'max_hp_points');hp=need(context,'current_hp_points')
            shield=need(context,'shield_points');ready=need(context,'cooldown_available')
            if max_hp<=0 or not (0<=hp<=max_hp) or shield<0:raise ValueError('invalid HP/shield state')
            if ready and shield/max_hp*100>rule['condition']['value']:
                requested=max_hp*n[0]['value']/100
                healed=min(requested,max_hp-hp)
                excess=max(0,requested-healed)
                out.append({'type':'heal','basis':'max_hp','requested_points':requested,
                            'actual_hp_restored_points':healed,'hp_after':hp+healed,
                            'cooldown_seconds':rule['cooldown_seconds']})
                out.append({'type':'shield_generation_request','points':excess,
                            'basis':'excess_healing','duration_seconds':n[1]['duration_seconds'],
                            'actual_shield_applied_points':'requires_shield_capacity_rule'})

    elif op=='safe_haven_partial':
        triggered=need(context,'safe_haven_spend_event')
        if triggered:
            out.append({'type':'shield_generation_percent_unbound_basis','value_percent':n[0]['value'],
                        'duration_seconds':n[0]['duration_seconds']})

    elif op=='event_modifier_duration_unknown':
        triggered=need(context,'empty_reload_triggered')
        if triggered:out += [stat(x['stat'],x['value'],duration_seconds='unknown') for x in n]

    elif op=='event_timed_stack':
        stacks=need(context,'active_stacks')
        if not isinstance(stacks,int) or not 0<=stacks<=rule['max_stacks']:
            raise ValueError('active_stacks outside known cap')
        out += [stat(x['stat'],x['value']*stacks,active_stacks=stacks,
                    duration_seconds=rule['duration_seconds']) for x in n]

    elif op=='event_timed_modifier':
        active=need(context,'event_buff_active')
        if active:out += [stat(x['stat'],x['value'],duration_seconds=rule['duration_seconds'],
                               event=rule['event']) for x in n]

    elif op in ('base_plus_hp_cost_timed_stack_partial','base_plus_unknown_curve'):
        out += [stat(x['stat'],x['value']) for x in n]

    elif op=='distance_scaling_partial':
        distance=need(context,'bullet_hit_distance_meters')
        if distance>n[0]['threshold_meters']:
            out.append(stat(n[0]['stat'],n[0]['base_percent'],
                            condition={'distance_meters_above':n[0]['threshold_meters']}))

    else:raise NotImplementedError(op)
    return {'outputs':out,'unresolved':pending,'whole_dps_certified':False}
