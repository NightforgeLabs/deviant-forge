"""Controlled accepted-hit DOT/lightning graph and target reduction order.

All leaves are supplied; this does not create an AUG event or certify HP loss.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).with_name('evidence_packets')
HASHES = {
    'native-lightning-dot-factors-v1.md': '9a2662dc125d4c432a655105a98a0c8d42ec395f248f49af90fdaeb9989fa95d',
    'native-lightning-dot-factors-v1.json': 'b52606091ab32e35b94caefa1d827d8c7c969769703957b328d7cce4fddc9d74',
}
LEAVES = ('attack', 'dot_add_rate', 'lightning_add_rate',
          'target_lightning_ignore_dam_rate', 'target_dot_ignore_dam_rate',
          'target_lightning_ignore_dam')


@lru_cache(maxsize=1)
def proof():
    for name, digest in HASHES.items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Native lightning DOT factor evidence hash conflict')
    packet = json.loads((ROOT / 'native-lightning-dot-factors-v1.json').read_text())
    if packet['build_id'] != '26267212':
        raise ValueError('Native lightning DOT factor build conflict')
    expected = {'E34': 'element_type_dam_add_rate_lightning',
                'E42': 'attack_type_dam_add_rate_remote',
                'E43': 'attack_type_dam_add_rate_dot',
                'G44': 'element_type_ignore_dam_rate_lightning',
                'G53': 'attack_type_ignore_dam_rate_dot',
                'G104': 'element_type_ignore_dam_lightning'}
    if any(packet['property_ids'].get(key) != name for key, name in expected.items()):
        raise ValueError('Native lightning DOT typed property conflict')
    if [(row['graph_pre_round'], row['positive_wrapper_result'])
            for row in packet['synthetic_explicit_leaf_vectors']] != [(99, 99), (44.46, 44)]:
        raise ValueError('Native lightning DOT source vector conflict')
    return {'build': '26267212', 'source_sha256': HASHES.copy(),
            'scope': 'accepted hit with all graph leaves supplied; not proc generation or HP loss'}


def calculate(values):
    source = proof()
    if not isinstance(values, dict):
        raise ValueError('Lightning DOT hit scenario must be an object')
    missing = []
    if values.get('property_source_build') != source['build']:
        missing.append('property_source_build=26267212')
    if values.get('formula_attack_type') != 4 or values.get('element_type_leaf') != 3:
        missing.append('explicit Dot=4 and lightning element_type leaf=3')
    if values.get('leaves_source') not in ('explicit_synthetic', 'confirmed_hit_info'):
        missing.append('explicit leaves_source')
    if values.get('all_other_graph_factors_unity') is not True:
        missing.append('all other graph factors explicitly unity')
    if values.get('final_damage_switch') != 1 or values.get('final_ignore_switch') != 1:
        missing.append('both final graph switches=1')
    for name in LEAVES:
        if name not in values:
            missing.append(name)
    if missing:
        return {'status': 'missing_controlled_hit_inputs', 'graph_pre_round': None,
                'positive_wrapper_result': None, 'actual_hp_loss': None,
                'actual_proc_damage': None, 'full_build_dps': None,
                'missing': missing, 'source_method': source, 'game_verified': False}
    for name in LEAVES:
        number = values[name]
        if type(number) not in (int, float) or not math.isfinite(number):
            raise ValueError(name + ' must be a finite supplied graph leaf')
    if values['attack'] < 0:
        raise ValueError('attack must be nonnegative')
    dot = 1 + values['dot_add_rate']
    element = max(1 + values['lightning_add_rate'], 0)
    reductions = [1 - values['target_lightning_ignore_dam_rate'],
                  1 - values['target_dot_ignore_dam_rate'],
                  1 - values['target_lightning_ignore_dam']]
    pre = max(values['attack'] * dot * element * math.prod(reductions), 0)
    wrapper = 0 if pre <= 0 else max(round(pre), 1)
    return {'status': 'controlled_accepted_lightning_dot_hit',
            'dot_factor_E43': dot, 'lightning_factor_E34': element,
            'target_reduction_factors_G44_G53_G104': reductions,
            'graph_pre_round': pre, 'positive_wrapper_result': wrapper,
            'remote_attack_type_E42_applied': False,
            'surge_keyword_E121_applied': False,
            'actual_hp_loss': None, 'actual_proc_damage': None, 'full_build_dps': None,
            'source_method': source, 'game_verified': False,
            'scope': 'Supplied accepted-hit leaves with other factors unity; not actual AUG proc, target HP loss, or DPS.'}
