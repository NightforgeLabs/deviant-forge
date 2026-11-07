"""AUG Electron Cloud configured durative attack-value input, not hit DPS."""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path

import native_skill_power
import native_dot_modifier_buckets


ROOT = Path(__file__).with_name('evidence_packets')
SOURCE_NAME = 'native-aug-configured-input-v1.md'
SOURCE_SHA256 = '9296bac2a8dda581a11918d78ca16a00cf916021497dc928562ec6d6b4c1a194'
DOWNSTREAM_MD = 'native-aug-dot-downstream-v1.md'
DOWNSTREAM_JSON = 'native-aug-dot-downstream-v1.json'
DOWNSTREAM_HASHES = {
    DOWNSTREAM_MD: '6db6987ef882028ace371006f0953b4f13d4a3ce934ca5c8b65547bf789890fa',
    DOWNSTREAM_JSON: 'e8e892b6e70a09370d94174c6d4b8fb7c9973c9498d987f84d87bb2d91bc86c2',
}


@lru_cache(maxsize=1)
def proof():
    native_dot_modifier_buckets.proof()
    if hashlib.sha256((ROOT / SOURCE_NAME).read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError('Native AUG configured-input source hash conflict')
    for name, digest in DOWNSTREAM_HASHES.items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Native AUG downstream source hash conflict')
    packet = json.loads((ROOT / DOWNSTREAM_JSON).read_text())
    nodes = packet['selected_aug_nodes']
    if (set(nodes) != {'129', '215'} or
            packet['formula_attack_type_4_name'] != 'Dot' or
            packet['verified_downstream']['weak_body_part_flag_set_for_Dot'] is not False or
            any(node['config']['formula_attack_type'] != 4 or
                node['config']['keyword'] != 302 or
                node['config']['element_type'] != 3 or
                node['config']['is_buff_damage'] != 1
                for node in nodes.values()) or
            not packet['missing_bridge']):
        raise ValueError('Native AUG downstream category or bridge conflict')
    return {'build': '26267212', 'weapon_blueprint_id': 13451401,
            'fixed_skill_id': 'WS15704', 'source_sha256': SOURCE_SHA256,
            'downstream_source_sha256': DOWNSTREAM_HASHES[DOWNSTREAM_MD],
            'tag_lookup_source_sha256': native_dot_modifier_buckets.HASHES['native-dot-tag-lookup-v1.md'],
            'scope': 'configured node attack_value input only, server executor unresolved'}


def _unknown(missing, source):
    return {'status': 'missing_controlled_AUG_graph_inputs',
            'configured_attack_value': None, 'actual_proc_damage': None,
            'damage_packets': None, 'proc_rate': None, 'full_build_dps': None,
            'missing': list(dict.fromkeys(missing)), 'source_method': source,
            'game_verified': False}


def calculate(values):
    source = proof()
    if not isinstance(values, dict):
        raise ValueError('AUG configured-input scenario must be an object')
    missing = []
    if values.get('property_source_build') != source['build']:
        missing.append('property_source_build=26267212')
    if values.get('weapon_blueprint_id') != source['weapon_blueprint_id']:
        missing.append('exact AUG weapon_blueprint_id=13451401')
    if values.get('fixed_skill_id') != source['fixed_skill_id']:
        missing.append('fixed_skill_id=WS15704')
    if values.get('graph_branch') not in ('node129', 'node215'):
        missing.append('graph_branch=node129 or node215')
    if values.get('graph_inputs_explicit') is not True:
        missing.append('graph_inputs_explicit=true')
    for name in ('skill_dam_base_dam_surge', 'dam_up', 'pvp_ratio'):
        if name not in values:
            missing.append(name)
    if ('skill_power_inputs' in values) == ('skill_power' in values):
        missing.append('exactly one skill_power or skill_power_inputs')
    if 'skill_power' in values and values.get('skill_power_origin') not in (
            'explicit_synthetic', 'confirmed_holder_D41'):
        missing.append('explicit skill_power_origin')
    if missing:
        return _unknown(missing, source)
    if 'skill_power_inputs' in values:
        skill = native_skill_power.calculate(values['skill_power_inputs'])
        if skill['stored_skill_power'] is None:
            return _unknown(['skill_power_inputs.' + name for name in skill['missing']],
                            source)
        power = skill['stored_skill_power']
        power_source = {'origin': 'controlled_D41_aggregation',
                        'source_method': skill['source_method']}
    else:
        power = values['skill_power']
        if type(power) not in (int, float) or not math.isfinite(power) or not 0 <= power <= 9999:
            raise ValueError('skill_power must be a finite stored D41 value within 0..9999')
        power_source = {'origin': values['skill_power_origin']}
    for name in ('skill_dam_base_dam_surge', 'dam_up', 'pvp_ratio'):
        value = values[name]
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError(f'{name} must be finite numeric input')
    if values['skill_dam_base_dam_surge'] < 0 or values['pvp_ratio'] < 0:
        raise ValueError('Coefficient and PvP ratio must be nonnegative in this controlled scenario')
    configured = (power * values['skill_dam_base_dam_surge'] *
                  (1 + values['dam_up']) * values['pvp_ratio'])
    return {'status': 'controlled_AUG_configured_attack_value',
            'configured_attack_value': configured,
            'skill_power_input': power, 'skill_power_source': power_source,
            'graph_branch': values['graph_branch'],
            'configured_formula_attack_type_code': 4,
            'configured_formula_attack_type': 'Dot',
            'configured_keyword_code': 302,
            'configured_element_type_code': 3,
            'element_label': 'lightning',
            'configured_keyword_label': 'surge',
            'keyword_type_leaf_established': False,
            'automatic_weak_body_flag_for_dot': False,
            'weakspot_eligibility': None,
            'crit_eligibility': None,
            'damage_class': None,
            'attack_value_to_hit_info_bridge_established': False,
            'actual_proc_damage': None, 'damage_packets': None,
            'proc_rate': None, 'full_build_dps': None,
            'source_method': source, 'game_verified': False,
            'scope': 'Configured graph input; authoritative server executor and hit settlement unresolved.'}
