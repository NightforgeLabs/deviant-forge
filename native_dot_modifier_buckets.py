"""Source-bound DOT property arithmetic for supplied active affixes.

This is a controlled graph component, not an AUG proc or an equipped build.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).with_name('evidence_packets')
HASHES = {
    'native-dot-modifier-buckets-v1.md': 'cc96efb8a291ddb3caf110603a8250388076f934d2916218403de5854b9c9950',
    'native-dot-modifier-buckets-v1.json': '75417c44194ddf9257f1f3293c461f222687aa3a8ccd9dc699f71c291e883e04',
    'native-dot-tag-lookup-v1.md': '8403bc764392c0c2a6955d51c1a50607505b852991a49face893662d52fdeead',
    'native-dot-tag-lookup-v1.json': '25d29bca50fee565b78bb01c7320c4fc11c87ce03d56e8a1b481299ef2f1bf23',
}
AFFIX = {'E4300': ('E43', 'dot_attack_type'),
         'E3400': ('E34', 'lightning_element'),
         'E12100': ('E121', 'surge_keyword')}
PROPERTY = {'E43': 'attack_type_dam_add_rate_dot',
            'E34': 'element_type_dam_add_rate_lightning',
            'E121': 'keyword_proc_dam_add_rate_surge'}


@lru_cache(maxsize=1)
def proof():
    for name, digest in HASHES.items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Native DOT bucket evidence hash conflict')
    packet = json.loads((ROOT / 'native-dot-modifier-buckets-v1.json').read_text())
    if packet['build_id'] != '26267212':
        raise ValueError('Native DOT bucket build conflict')
    for affix, (attr, _) in AFFIX.items():
        fields = packet['affix_rows'][affix]['fields']
        prop = packet['property_rows'][PROPERTY[attr]]['fields']
        if (fields['attr_id'] != attr or fields['effect_range'] != 1 or
                fields['type'] != 1 or prop['attr_id'] != attr or
                prop['calc_type'] != 0 or prop['init_val'] != 0 or
                prop['val_type'] != 2 or prop['min_val'] != -0.9 or
                prop['max_val'] != 10):
            raise ValueError('Native DOT bucket typed row conflict')
    tags = json.loads((ROOT / 'native-dot-tag-lookup-v1.json').read_text())
    if (tags['build_id'] != '26267212' or
            tags['element']['key'] != 3 or tags['element']['suffix_string'] != 'lightning' or
            tags['keyword']['key'] != 302 or tags['keyword']['suffix_string'] != 'surge' or
            tags['is_keyword_damage']['configured_aug_value'] != 0 or
            tags['is_keyword_damage']['exact_keyword_type_leaf_assignment_proven'] is not False):
        raise ValueError('Native DOT tag lookup conflict')
    return {'build': '26267212', 'source_sha256': HASHES.copy(),
            'scope': 'source typed property accumulation and controlled graph factors'}


def calculate(values):
    source = proof()
    if not isinstance(values, dict):
        raise ValueError('DOT scenario must be an object')
    missing = []
    if values.get('property_source_build') != source['build']:
        missing.append('property_source_build=26267212')
    if values.get('active_affixes_complete') is not True:
        missing.append('complete explicitly active affix list')
    if values.get('other_property_contributions_zero') is not True:
        missing.append('other property contributions explicitly zero or separately modeled')
    if values.get('formula_attack_type') != 4 or values.get('attack_is_buff') is not True:
        missing.append('configured DOT buff graph branch')
    rows = values.get('active_affixes')
    if not isinstance(rows, list):
        missing.append('active_affixes list')
    if missing:
        return _unknown(missing, source)
    totals = {key: 0.0 for _, key in AFFIX.values()}
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or row.get('affix_id') not in AFFIX:
            raise ValueError('Each active affix needs a known exact typed affix ID')
        identifier = row.get('source_id')
        if not isinstance(identifier, str) or not identifier or identifier in seen:
            raise ValueError('Active affixes need unique nonempty source IDs')
        seen.add(identifier)
        if row.get('active') is not True:
            return _unknown(['active state for ' + identifier], source)
        number = row.get('value')
        if type(number) not in (int, float) or not math.isfinite(number):
            raise ValueError('Active affix value must be a finite fractional number')
        totals[AFFIX[row['affix_id']][1]] += number
    for key, value in totals.items():
        if not -.9 <= value <= 10:
            raise ValueError(key + ' property exceeds typed native bounds')
    # AffixUtils combines absolute values for the same property before graph use.
    factor = 1 + totals['dot_attack_type']
    element_leaf = values.get('event_element_type_leaf')
    element_source = values.get('event_element_type_leaf_source')
    if element_leaf is None:
        if element_source is not None:
            raise ValueError('Element leaf source requires an explicit event leaf')
        element_applied = False
    elif element_leaf == 3 and element_source in ('explicit_synthetic', 'confirmed_hit_info'):
        element_applied = True
    else:
        raise ValueError('Only explicitly sourced element_type leaf 3 is supported')
    element_factor = max(1 + totals['lightning_element'], 0) if element_applied else None
    base = values.get('controlled_graph_base')
    if base is not None and (type(base) not in (int, float) or
                             not math.isfinite(base) or base < 0):
        raise ValueError('controlled_graph_base must be finite and nonnegative')
    return {
        'status': 'controlled_dot_property_component',
        'typed_property_additions': totals,
        'dot_attack_type_factor': factor,
        'controlled_base_after_dot_factor_pre_round': None if base is None else base * factor,
        'controlled_base_after_dot_and_element_pre_round': (
            None if base is None or not element_applied else base * factor * element_factor),
        'lightning_element_factor_applied': element_applied,
        'lightning_element_factor': element_factor,
        'surge_keyword_factor_applied': False,
        'excluded_conditionally_typed_additions': {
            'lightning_element': totals['lightning_element'],
            'surge_keyword': totals['surge_keyword'],
        },
        'native_tag_names': {'element_type_3': 'lightning', 'keyword_302': 'surge'},
        'missing_joins': ([] if element_applied else ['event element_type leaf assignment and active E34 values']) +
                         ['event keyword_type leaf assignment and keyword damage enablement'],
        'actual_proc_damage': None, 'proc_rate': None, 'full_build_dps': None,
        'source_method': source, 'game_verified': False,
        'scope': 'Source-typed active-affix scenario; conditional DOT and lightning factors before other graph factors and rounding.'
    }


def _unknown(missing, source):
    return {'status': 'missing_controlled_dot_inputs',
            'typed_property_additions': None, 'dot_attack_type_factor': None,
            'controlled_base_after_dot_factor_pre_round': None,
            'actual_proc_damage': None, 'proc_rate': None, 'full_build_dps': None,
            'missing': missing, 'source_method': source, 'game_verified': False}
