"""Read-only Nov 1 equipped tour; never a Nov 2 build or inventory import."""
from __future__ import annotations

from functools import lru_cache
import copy
import hashlib
import json
from pathlib import Path

import native_direct_hit_graph
import native_priority_mod_buff


ROOT = Path(__file__).resolve().parent
PACKET = ROOT / 'evidence_packets/historical-gear-tour-20261101-v1.json'
PACKET_SHA256 = '6cdcd31e0106e79df1a233bd5fa7ee2965be4e191b288bb7621ccf3d3c2750b4'
FRAMES = {
    'item_tooltip': ('historical-gear-tour-nov1-aug.png',
                     '4254ebb858b79ce54ca51aef0272d5881075b00ebf8b83cae4ff0f891ec0b150'),
    'gear_summary': ('historical-gear-tour-nov1-summary.png',
                     'abf572c1aefa573f0737e56f45d8e1a5564f72036b03a1e9bec1ab993528f0ca'),
}


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _frame_source(frame):
    second = frame['second']
    basename = f'historical-gear-tour-nov1-{second}.png'
    return {'second': second, 'url': '/artwork/' + basename,
            'sha256': frame['sha256']}


@lru_cache(maxsize=1)
def _verified():
    if _sha(PACKET) != PACKET_SHA256:
        raise ValueError('Historical gear-tour packet hash conflict')
    row = json.loads(PACKET.read_text())
    item = row['equipped_items_at_recording_time'][0]
    summary = row['temporal_gate']['historical_gear_summary']
    if (row['schema_version'] != 1 or row['source']['sha256'] !=
            '0f9a959921f8b42618751fd1191ed2bc621b62199b681ab2afe2d09774cf7298' or
            row['temporal_gate']['recording_date'] != '2026-11-01' or
            row['temporal_gate']['later_observations_date'] != '2026-11-02' or
            (item['name_visible'], item['tier'], item['stars_visible']) !=
            ('AUG – Electron Cloud', 5, 6) or
            item['tooltip_basic_stats'] != {'DMG': 400, 'Fire Rate': 720, 'MAG': 40} or
            (summary['primary_weapon_attack'], summary['fire_rate'], summary['magazine_capacity']) !=
            (456, 792, 60) or len(row['attached_mods_at_recording_time']) != 7):
        raise ValueError('Historical gear-tour source or temporal scope conflict')
    for basename, digest in FRAMES.values():
        if _sha(ROOT / 'static/artwork' / basename) != digest:
            raise ValueError('Historical gear-tour source frame changed')
    for item_row in (row['equipped_items_at_recording_time'] +
                     row['attached_mods_at_recording_time']):
        for frame in item_row.get('frames') or [item_row['frame']]:
            source = _frame_source(frame)
            if _sha(ROOT / 'static' / source['url'].lstrip('/')) != source['sha256']:
                raise ValueError('Historical gear-tour item frame changed')
    return row


def snapshot():
    """A detached observation with no ownership/draft/calculation side effect."""
    row = copy.deepcopy(_verified())
    item = row['equipped_items_at_recording_time'][0]
    equipped = row['equipped_items_at_recording_time']
    mods = row['attached_mods_at_recording_time']
    for observed in equipped + mods:
        frame = (observed.get('frames') or [observed['frame']])[0]
        observed['source_frame'] = _frame_source(frame)
        observed['catalog_identity_status'] = 'observed_name_unlinked_to_native_item_id'
    for observed in mods:
        observed['native_frame_candidate'] = native_priority_mod_buff.historical_candidate(observed)
    return {'status': 'historical_recorded_equipped_tour',
            'recorded_date': '2026-11-01', 'current_build_inferred': False,
            'ownership_mutated': False, 'calculation_included': False,
            'packet_sha256': PACKET_SHA256,
            'video_sha256': row['source']['sha256'],
            'recorded_weapon': {'name': item['name_visible'], 'tier': item['tier'],
                                'stars': item['stars_visible'],
                                'item_tooltip': item['tooltip_basic_stats'],
                                'item_tooltip_affixes_may_already_include_calibration': True,
                                'calibration_option_not_visible': True},
            'recorded_gear_summary': row['temporal_gate']['historical_gear_summary'],
            'later_nov2_summary': row['temporal_gate']['later_screenshot_summary'],
            'equipped_items': equipped,
            'attached_mods': mods,
            'source_frames': {key: {'url': '/artwork/' + basename, 'sha256': digest}
                              for key, (basename, digest) in FRAMES.items()},
            'mod_application': {
                'visible_attachment_recorded': True,
                'server_buff_application_proven': False,
                'historical_damage_effects_applied': False,
                'source_scope': 'Build 26267212 client equip request and displayed attached-code reader; server equip handler/application edge unverified.',
                'source_sha256': '98d9ed3d7dafb39ad5c42f13999461d6c5695926b68402fdcf600050845fc812',
                'required_for_complete_replay': [
                    'Equipment item_no and unique item_id for each historical instance',
                    'Normal mod_code and second_mod_code attached to each instance',
                    'Historical mod_bag_v2[mod_code].total_level for each attached V2 mod',
                    'Historical main-entry/core rank, variant and effect-specific state',
                    'Verified server equip acceptance and buff/affix application to holder components',
                    'Relevant historical combat events and target state',
                ],
            },
            'limitations': ['The Nov 1 item tooltip DMG 400 and gear summary Attack 456 are distinct rows.',
                            'Nov 2 Attack 422 / magazine 58 is a later setup; no item identity or calibration transfer is inferred.',
                            'Armor and mod names are frame observations; native item IDs are not proven by these frames.',
                            'Visible attached-mod cues do not prove server buff or affix application.',
                            'The seven recorded mod cards are historical instance facts, not an automatic current-build selection.']}


def controlled_one_bullet_example():
    """Use the recorded tooltip only as an explicit neutral graph hypothesis."""
    observed = snapshot()
    tooltip = observed['recorded_weapon']['item_tooltip']
    attack = tooltip['DMG']
    inputs = {'effect_scope': 'ordinary_player_direct_bullet',
              'attack': attack, 'attack_evidence': 'caller_hypothesis',
              'attack_value_origin': 'equipped_item_tooltip',
              'final_skill_rate': 1, 'final_keyword_damage_add_rate': 0,
              'unit_part_weak_dam_rate': 1, 'crit_addition': 0,
              'weakspot_addition': 0, 'final_element_type_dam_add_rate': 1,
              'other_dam_rate': 0, 'final_field_dam_add_rate': 1,
              'dis_dam_rate': 1, 'final_dam_add_rate': 0,
              'final_special_regulate_factor': 1, 'crit': False,
              'weakspot': False, 'use_final_dam_add_rate': True,
              'use_final_ignore_dam_rate': True,
              'target_factor_nodes': {key: 1 for key in native_direct_hit_graph.TARGET_FACTOR_NODES},
              'rate_dictionary_state': 'absent', 'rounding_model': None}
    result = native_direct_hit_graph.player_bullet_scenario(inputs)
    if result['status'] != 'conditional_player_bullet_formula' or result['graph_final_attack'] != attack:
        raise ValueError('Historical neutral direct-hit graph unexpectedly changed')
    return {'status': 'historical_controlled_item_tooltip_hypothesis',
            'recorded_item_tooltip_dmg': attack,
            'neutral_graph_value': result['graph_final_attack'],
            'source_frame': observed['source_frames']['item_tooltip'],
            'native_base_attack_added': False,
            'calibration_or_item_affix_added_again': False,
            'attached_mods_added': False,
            'holder_attack_equivalence_proven': False,
            'final_hp_loss': None, 'current_build_damage': None,
            'graph_status': result['status'],
            'scope': 'Nov 1 recorded item tooltip as the Attack leaf for one neutral, noncrit, nonweak direct bullet; not actual holder Attack or final damage.'}
