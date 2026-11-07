"""Conservative current-release unique armor packet modifiers.

The explicit packet source ID is required. A generic blast or unidentified
packet is never assumed to be an Unstable Bomber explosion.
"""
from __future__ import annotations

import math

from weapon_mechanics.damage_projection_v3 import load_damage_bindings

PACKETS = load_damage_bindings()['packets']
WIND = 'armor:wind-intepreter-cap'
WIND_SOURCE = 'https://www.oncehuman.game/news/update/20260709/40780_1307147.html'


def wind_intepreter(build, encounter_mode, source_packets, projected_packets,
                    *, ammo_scenario=None, ammo_trace=()):
    selected = any(row.get('catalog_id') == WIND for row in build.get('armor_profiles') or [])
    result = {'selected': selected, 'source_status': 'current_official_release',
              'source_url': WIND_SOURCE, 'applied': [], 'known_bonus_damage': 0.0,
              'ammo_scenario': ammo_scenario, 'ammo_trace': list(ammo_trace),
              'unresolved': []}
    if not selected or encounter_mode == 'raidzone':
        return result
    if encounter_mode != 'pve_non_raidzone':
        result['unresolved'].append('Wind Intepreter Cap needs explicit PvE non-RaidZone encounter mode')
        return result
    indexed = {row['event_id']: row for row in source_packets}
    for packet in projected_packets:
        source = indexed.get(packet.get('event_id'))
        if source is None:
            continue
        spec = PACKETS.get(source.get('source_packet_id'))
        if not spec or spec.get('family') != 'Unstable Bomber':
            continue
        damage = packet.get('damage')
        prior = (packet.get('applied_pools_percent') or {}).get('unstable_bomber', 0)
        if (isinstance(damage, bool) or not isinstance(damage, (int, float)) or
                not math.isfinite(damage) or damage < 0 or
                isinstance(prior, bool) or not isinstance(prior, (int, float)) or
                not math.isfinite(prior) or prior <= -100):
            result['unresolved'].append('Wind Intepreter Cap packet bonus needs a finite bomber packet and known keyword pool')
            continue
        # Named additive keyword pool: the source gives +25% Bomber DMG Rate,
        # but does not establish universal bucket stacking with other buffs.
        delta = damage * 25 / (100 + prior)
        result['known_bonus_damage'] += delta
        result['applied'].append({'event_id': packet['event_id'],
                                  'source_packet_id': source['source_packet_id'],
                                  'bonus_damage': delta,
                                  'model': 'additive_unstable_bomber_keyword_pool',
                                  'source_status': 'current_official_release'})
    if result['applied']:
        supported = all(row['source_packet_id'] ==
                        'weapon:g17-hazardous-object/thrown_reload_blast'
                        for row in result['applied'])
        if ammo_scenario is None:
            result['unresolved'].append(
                'Wind bullet source and retention during reload are unspecified; choose a named finite-ammo scenario')
        elif not supported or len(ammo_trace) != len(result['applied']):
            result['unresolved'].append(
                'Wind ammo timing is modeled only for one sourced Hazardous Object explosion per reload')
        else:
            result['ammo_model_status'] = 'conditional_explicit_source_and_reload_order'
    else:
        result['unresolved'].append(
            'Wind Intepreter Cap requires source-linked Unstable Bomber explosion events to evaluate its damage and ammo effects')
    return result
