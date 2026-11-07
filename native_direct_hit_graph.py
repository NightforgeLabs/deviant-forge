"""Version-13 native direct-hit graph components, not a complete hit solver.

The equipped combat `attack` leaf, outcome flags, target factors and final
rounding still need their own source bindings. The recovered graph establishes
the ordering and the additive crit/weakspot factor at its graph layer.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path

TRACE = Path(__file__).with_name('evidence_packets') / 'native-direct-hit-graph-v13.json'
TRACE_SHA256 = 'c848360a1e73127ee814bdd0a0c99212f674b3e450f3133970890495deb1054a'
GRAPH_SHA256 = 'aba2f1e8b66b3bf464bc169c2c30aed6aadd638153985e28dfc00e6bf8db0c9b'
SOURCE_SHA256 = '244bf28269e6b46ae9fafc164c14f33e95822616775abaf64484224c119117ee'
PLAYER_TRACE = TRACE.with_name('native-player-terminal-graph-v13.json')
PLAYER_TRACE_SHA256 = '8c60d993fa56db4ee2e587106437a5eb3d352e6bd2f9b2f2a72e26712b10d5f4'
TARGET_FACTOR_NODES = ('155', '144', '147', '289', '101', '124', '285', '307', '167')
TOOLTIP_TRACE_SHA256 = '939db955df8fbb847cca46f03b8ad0d084399e898550d76a1202c46a6a6bc20a'
TOOLTIP_TRACE = TRACE.with_name('native-weapon-tooltip-value-path.md')
ATTACK_ORIGINS = ('holder_combat_property', 'equipped_item_tooltip',
                  'blueprint_preview', 'caller_hypothesis_unspecified')
ADDITIONAL_INPUTS = ('final_skill_rate', 'final_keyword_damage_add_rate',
                     'unit_part_weak_dam_rate', 'crit_addition', 'weakspot_addition',
                     'final_element_type_dam_add_rate', 'other_dam_rate',
                     'final_field_dam_add_rate', 'dis_dam_rate', 'final_dam_add_rate',
                     'final_special_regulate_factor', 'crit', 'weakspot',
                     'use_final_dam_add_rate', 'use_final_ignore_dam_rate')


@lru_cache(maxsize=1)
def source():
    raw = TRACE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != TRACE_SHA256:
        raise ValueError('Native direct-hit graph trace hash conflict')
    packet = json.loads(raw)
    graph = packet.get('graph') or {}
    nodes = graph.get('selected_nodes') or {}
    expected = {
        '84': ['NameExpr', 'attack', -1],
        '85': ['NameExpr', 'base_attack', 84],
        '298': ['BinopListExpr', 284, '+', 297],
        '300': ['BinopListExpr', 1, '+', 299],
        '301': ['BinopListExpr', 142, '*', 250, '*', 14, '*', 300, '*',
                113, '*', 240, '*', 244, '*', 149, '*', 287],
        '312': ['BinopListExpr', 85, '*', 304, '*', 311, '*', 145],
        '313': ['FunctionExpr', 'max', 312, 0],
    }
    if (graph.get('version') != 13 or graph.get('node_count') != 314 or
            graph.get('final_attack_target_node') != 313 or
            graph.get('original_pyc_graph_tuple_sha256') != GRAPH_SHA256 or
            packet.get('source_pyc_sha256', {}).get('damage_formula.pyc') != SOURCE_SHA256 or
            any(nodes.get(key, {}).get('descriptor') != value for key, value in expected.items())):
        raise ValueError('Native direct-hit graph source or operations conflict')
    return {'version': 13, 'trace_sha256': TRACE_SHA256,
            'graph_tuple_sha256': GRAPH_SHA256, 'source_pyc_sha256': SOURCE_SHA256,
            'scope': 'direct-hit graph layer; equipped attack and final hit remain unbound'}


@lru_cache(maxsize=1)
def player_source():
    source()
    raw = PLAYER_TRACE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PLAYER_TRACE_SHA256:
        raise ValueError('Native player direct-hit trace hash conflict')
    packet = json.loads(raw)
    methods = {row['method']: row for row in packet['methods']}
    expected_methods = {
        'CompBeHitServer._pre_calc_damage': '390db163a1eec927ae33f695f054a710196ed5351f2795efb4cc4c19962cea85',
        'CompDamageFormula.get_formula_damage_result': 'e4bc8c28e3e042e3d98d26c9d8adf9f83dacd965e5ba4ad973fa19882614f0ca',
        'CompDamageFormula._get_final_attack': '4384a086a916bd4f8a428d4de92749e00e2f3e17600f6019a17ffd059e79f1cf',
    }
    if (packet.get('installed_build_id') != '26267212' or
            packet.get('native_graph_version') != 13 or
            packet.get('source_pyc_sha256', {}).get('damage_formula.pyc') != SOURCE_SHA256 or
            packet.get('mitigation_factor_nodes') != [int(key) for key in TARGET_FACTOR_NODES] or
            packet.get('additional_factor_nodes') != [142,250,14,300,113,240,244,149,287] or
            any(methods.get(name, {}).get('body_sha256') != digest
                for name, digest in expected_methods.items()) or
            packet.get('synthetic_intermediate_vector', {}).get('graph_final_attack') != 144):
        raise ValueError('Native player direct-hit branch binding conflict')
    return {'build': '26267212', 'trace_sha256': PLAYER_TRACE_SHA256,
            'ordinary_branch': 'CompBeHitServer._pre_calc_damage to version-13 direct graph',
            'target_factor_nodes': TARGET_FACTOR_NODES,
            'scope': 'ordinary player bullet formula before field, shield, level, DPS and invulnerability settlement'}


def _number(value, name):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f'{name} must be a finite number')
    return float(value)


def joint_factor(crit_addition, weakspot_addition, *, crit=False, weakspot=False):
    """Node 300: one plus applicable crit and weakspot additions."""
    source()
    if type(crit) is not bool or type(weakspot) is not bool:
        raise ValueError('Direct-hit outcome flags must be explicit booleans')
    crit_value = max(_number(crit_addition, 'critical addition'), 0) if crit else 0
    weak_value = max(_number(weakspot_addition, 'weakspot addition'), 0) if weakspot else 0
    return 1 + crit_value + weak_value


def graph_layer(*, base_attack, final_skill_rate, final_keyword_damage_add_rate,
                unit_part_weak_dam_rate, crit_addition, weakspot_addition,
                final_element_type_dam_add_rate, other_dam_rate,
                final_field_dam_add_rate, dis_dam_rate, final_dam_add_rate,
                attack_ignore_dam_rate, final_special_regulate_factor,
                crit=False, weakspot=False, use_final_dam_add_rate=True,
                use_final_ignore_dam_rate=True):
    """Nodes 301–313 with every leaf supplied; returns pre-wrapper value.

    The caller must bind every leaf and guard from a declared scenario. No
    default target mitigation, attack, PvP factor or final rounding is assumed.
    """
    source_ref = source()
    if type(use_final_dam_add_rate) is not bool or type(use_final_ignore_dam_rate) is not bool:
        raise ValueError('Native graph use flags must be explicit booleans')
    factors = [
        _number(final_skill_rate, 'final_skill_rate'),
        1 + _number(final_keyword_damage_add_rate, 'final_keyword_damage_add_rate'),
        _number(unit_part_weak_dam_rate, 'unit_part_weak_dam_rate'),
        joint_factor(crit_addition, weakspot_addition, crit=crit, weakspot=weakspot),
        _number(final_element_type_dam_add_rate, 'final_element_type_dam_add_rate'),
        1 + _number(other_dam_rate, 'other_dam_rate'),
        _number(final_field_dam_add_rate, 'final_field_dam_add_rate'),
        _number(dis_dam_rate, 'dis_dam_rate'),
        1 + _number(final_dam_add_rate, 'final_dam_add_rate'),
    ]
    additional = math.prod(factors) if use_final_dam_add_rate else 1
    ignore = _number(attack_ignore_dam_rate, 'attack_ignore_dam_rate') if use_final_ignore_dam_rate else 1
    result = max(_number(base_attack, 'base_attack') * additional * ignore *
                 _number(final_special_regulate_factor, 'final_special_regulate_factor'), 0)
    return {'pre_wrapper_final_attack': result, 'crit_weakspot_factor': factors[3],
            'additional_factor': additional, 'ignore_factor': ignore,
            'source': source_ref, 'final_hit_damage': None,
            'missing_for_final_hit': ['equipped attack leaf binding', 'outcome and target leaf bindings',
                                      'optional caller attack-type rates', 'wrapper rounding']}


def player_bullet_scenario(inputs):
    """Exact ordinary graph product from *explicit* leaves, never final HP loss.

    Target factors are keyed by native node ID. An unknown leaf withholds the
    product. The optional Python-round wrapper is an explicitly named model;
    post-formula field, shield and level settlement remain outside this path.
    """
    proof = player_source()
    if not isinstance(inputs, dict):
        raise ValueError('Player bullet scenario must be an object')
    if inputs.get('effect_scope') != 'ordinary_player_direct_bullet':
        raise ValueError('Native player branch applies only to an ordinary direct bullet')
    target = inputs.get('target_factor_nodes')
    if target is not None and (not isinstance(target, dict) or set(target) != set(TARGET_FACTOR_NODES)):
        raise ValueError('Provide all nine named native target factor nodes, without extra keys')
    missing = [key for key in ('attack', *ADDITIONAL_INPUTS) if key not in inputs]
    attack_evidence = inputs.get('attack_evidence')
    if attack_evidence not in ('verified_holder_property', 'caller_hypothesis'):
        missing.append('attack_evidence: verified_holder_property or caller_hypothesis')
    attack_origin = inputs.get('attack_value_origin', 'caller_hypothesis_unspecified')
    if attack_origin not in ATTACK_ORIGINS:
        raise ValueError('Attack value origin must identify holder property, equipped item tooltip, blueprint preview, or unspecified caller hypothesis')
    if attack_origin in ('equipped_item_tooltip', 'blueprint_preview') and hashlib.sha256(TOOLTIP_TRACE.read_bytes()).hexdigest() != TOOLTIP_TRACE_SHA256:
        raise ValueError('Native weapon tooltip source hash conflict')
    if attack_evidence == 'verified_holder_property' and attack_origin != 'holder_combat_property':
        raise ValueError('An item tooltip or blueprint preview is not a verified holder combat property')
    if attack_origin == 'holder_combat_property' and attack_evidence == 'caller_hypothesis':
        raise ValueError('A hypothetical Attack input cannot claim verified holder property origin')
    if target is None:
        missing.append('nine native target factor nodes')
    rate_state = inputs.get('rate_dictionary_state')
    if rate_state not in ('absent', 'present'):
        missing.append('rate_dictionary_state')
    if rate_state == 'present':
        missing.extend(key for key in ('rate', 'formula_attack_type_rate') if key not in inputs)
    elif rate_state == 'absent' and ('rate' in inputs or 'formula_attack_type_rate' in inputs):
        raise ValueError('Absent rate dictionary cannot include rate fields')
    if missing:
        return {'status': 'missing_player_bullet_inputs', 'missing': missing,
                'graph_final_attack': None, 'formula_damage_hp_before_settlement': None,
                'final_hp_loss': None, 'source': proof}
    if type(inputs['crit']) is not bool or type(inputs['weakspot']) is not bool:
        raise ValueError('Crit and weakspot outcomes must be explicit booleans')
    target_values = [_number(target[key], f'target node {key}') for key in TARGET_FACTOR_NODES]
    mitigation = math.prod(target_values)
    graph = graph_layer(
        base_attack=_number(inputs['attack'], 'verified or entered holder Attack'),
        attack_ignore_dam_rate=mitigation,
        **{key: inputs[key] for key in ADDITIONAL_INPUTS})
    rate = (1.0 if rate_state == 'absent' else
            _number(inputs['rate'], 'attack rate') *
            _number(inputs['formula_attack_type_rate'], 'formula attack-type rate'))
    adjusted = graph['pre_wrapper_final_attack'] * rate
    rounding = inputs.get('rounding_model')
    if rounding not in (None, 'python_builtin_expected'):
        raise ValueError('Choose the named Python built-in rounding expectation or leave it unknown')
    pre_settlement = (0 if adjusted <= 0 else max(round(adjusted), 1.0)) if rounding else None
    return {'status': 'conditional_player_bullet_formula',
            'graph_final_attack': graph['pre_wrapper_final_attack'],
            'additional_product': graph['additional_factor'],
            'target_product': graph['ignore_factor'],
            'crit_weakspot_factor': graph['crit_weakspot_factor'],
            'rate_adjusted_attack': adjusted,
            'formula_damage_hp_before_settlement': pre_settlement,
            'final_hp_loss': None, 'rounding_model': rounding,
            'source': proof, 'attack_evidence': attack_evidence,
            'attack_value_origin': attack_origin,
            'attack_input_scope': (
                {'includes': ['native weapon/star and applicable item accessory, random, and calibration Attack affixes'],
                 'excludes': ['attached mod effects', 'wearer armor, food, set, and temporary buffs'],
                 'must_not_reapply': ['native weapon/star Attack', 'already included item Attack affixes'],
                 'source_sha256': TOOLTIP_TRACE_SHA256,
                 'server_holder_equivalence_proven': False}
                if attack_origin == 'equipped_item_tooltip' else
                {'includes': ['native blueprint/star and synthetic item defaults'],
                 'excludes': ['owned item accessories, random and calibration affixes',
                              'attached mod effects', 'wearer buffs'],
                 'must_not_reapply': ['native blueprint/star Attack'],
                 'source_sha256': TOOLTIP_TRACE_SHA256,
                 'server_holder_equivalence_proven': False}
                if attack_origin == 'blueprint_preview' else
                {'includes': [], 'excludes': [], 'must_not_reapply': [],
                 'server_holder_equivalence_proven': attack_origin == 'holder_combat_property'}),
            'scenario_only': True, 'game_verified': False,
            'not_included': ['status ticks and procs', 'field adjustments', 'shield absorption',
                             'level and DPS rules', 'invulnerability and final HP loss']}
