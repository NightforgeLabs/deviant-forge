"""Source-pinned generic native HP table bounds for controlled scenarios.

These are property-table limits, not an entity's live HP or effective bounds
when a maximum-attribute or entity-specific override is present.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).with_name('evidence_packets')
HASHES = {
    'native-hp-property-bounds-v1.json': '92d4a389e8e3c5cce983a9eae7a33cf4ee417108edd99e892efc95127772ac01',
    'native-hp-property-bounds-v1.md': '2fe8ddc4d948792c801c84b35053e5d025da9c0596642475b2392835677a9a49',
    'native-hp-property-bounds-v2.json': '72a43e9c45f0a8d9b6497fd9e1e5e74b7cb5a87db8ee4a80ee5d817596dda2b1',
    'native-hp-ceiling-v2.md': '15bae4af9db83b1c0a85312dc81e8cf01710cd186e7156890400be845cfafbc0',
    'native-hp-ceiling-v2-vectors.json': 'c1e42256911ac45903e0eb6b3979717a68ee7bded78918a6623cb27fd03e7ec8',
}


@lru_cache(maxsize=1)
def proof():
    for name, digest in HASHES.items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Native HP property bounds source hash conflict')
    packet = json.loads((ROOT / 'native-hp-property-bounds-v2.json').read_text())
    hp = packet['rows']['hp']['fields']
    maximum = packet['rows']['max_hp']['fields']
    real_maximum = packet['rows']['real_max_hp']['fields']
    controls = json.loads((ROOT / 'native-hp-ceiling-v2-vectors.json').read_text())['static_controls']
    if (packet['installed_build_id'] != '26267212' or
            hp['attr_id_string_index']['decoded'] != 'A00' or
            hp['min_val']['value'] != 0 or hp['max_val']['value'] != 999999999 or
            hp['val_type']['value'] != 1 or
            maximum['attr_id_string_index']['decoded'] != 'A02' or
            maximum['min_val']['value'] != 1 or
            maximum['max_val']['value'] != 999999999 or
            maximum['val_type']['value'] != 1 or
            real_maximum['attr_id_string_index']['decoded'] != 'A01' or
            real_maximum['min_val']['value'] != 0 or
            real_maximum['val_type']['value'] != 1 or
            controls['hardcoded_attr_mapping'].get('hp') != 'real_max_hp'):
        raise ValueError('Native HP property type or bounds conflict')
    return {'build': packet['installed_build_id'], 'hp_attribute_id': 'A00',
            'hp_table_min': 0, 'hp_table_max': 999999999,
            'max_hp_attribute_id': 'A02', 'max_hp_table_min': 1,
            'real_max_hp_attribute_id': 'A01',
            'source_sha256': HASHES['native-hp-property-bounds-v2.json'],
            'ceiling_source_sha256': HASHES['native-hp-ceiling-v2.md'],
            'scope': 'generic table; hp is capped first by holder real_max_hp when present'}


def resolve(values):
    """Return effective bounds only if explicitly supplied or safely attested.

    Returns (lower, upper, source, missing). Native mode requires an exact A00
    property match and explicit absence of both known override classes.
    """
    source = proof()
    mode = values.get('hp_property_mode', 'explicit_effective')
    if mode == 'explicit_effective':
        missing = [name for name in ('hp_property_min', 'hp_property_max') if name not in values]
        if missing:
            return None, None, None, missing
        lower, upper = values['hp_property_min'], values['hp_property_max']
        if type(lower) is not int or type(upper) is not int or lower > upper:
            raise ValueError('Explicit effective HP property bounds must be ordered integers')
        return lower, upper, 'caller_supplied_effective_bounds', []
    if mode not in ('native_table_no_overrides', 'native_table_with_real_max_hp'):
        raise ValueError('Unknown HP property bound mode')
    if 'hp_property_min' in values or 'hp_property_max' in values:
        raise ValueError('Native-table mode cannot silently replace explicit effective bounds')
    missing = []
    if values.get('hp_property_attr_id') != source['hp_attribute_id']:
        missing.append('matching hp_property_attr_id=A00')
    if values.get('property_source_build') != source['build']:
        missing.append('matching property_source_build=26267212')
    if values.get('entity_specific_bound_override_absent') is not True:
        missing.append('entity_specific_bound_override_absent=true')
    if values.get('hp_property_val_type_abs') is not True:
        missing.append('hp_property_val_type_abs=true')
    if values.get('hp_property_direct_mapping') is not True:
        missing.append('hp_property_direct_mapping=true')
    if mode == 'native_table_no_overrides':
        if values.get('holder_has_real_max_hp') is not False:
            missing.append('holder_has_real_max_hp=false')
        if values.get('maximum_attribute_override_absent') is not True:
            missing.append('maximum_attribute_override_absent=true')
        upper = source['hp_table_max']
        bound_source = 'native_A00_table_real_max_hp_absent'
    else:
        if values.get('holder_has_real_max_hp') is not True:
            missing.append('holder_has_real_max_hp=true')
        real_maximum = values.get('current_real_max_hp')
        if real_maximum is None:
            missing.append('current_real_max_hp')
        elif type(real_maximum) is not int or not 0 <= real_maximum <= source['hp_table_max']:
            raise ValueError('current_real_max_hp must be an integer within native table bounds')
        upper = min(source['hp_table_max'], real_maximum or 0)
        bound_source = 'native_A00_table_with_current_real_max_hp'
    if missing:
        return None, None, None, missing
    return source['hp_table_min'], upper, bound_source, []
