"""Source-scoped Attack property accumulator, separate from weapon base Attack.

Only D0100 (absolute Attack) and D0101 (rate Attack) are modeled.  A result
for the equipped property requires the complete active source map, which DV
does not yet possess.  Caller supplied rows are explicitly hypothetical.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).with_name('evidence_packets')
SOURCES = {
    'native-attack-accumulator-v1.json': '6793712ee2b0bcae6481743e7d08236d0fcbbe380f9a452df120bd2bc98e0459',
    'native-attack-affix-types-v1.json': 'f61ae124cecd57e8dfc796ddf8749f6aa5a55feeaccaf81d1b415731d7e4c976',
    'native-attack-attr-map-v1.json': 'a45580bf1d71592fa155308f409f3a685b50a9b9ee82bdf1a918f55330a4238e',
}
SCOPE_SOURCES = {
    'native-origin-attack-gap-v1.json': '935c8a9f94e11d2af8ae84970504e91ee07702529fb2032f08e0c84797b63ab2',
    'native-origin-affix-lists-480-v1.json': 'd58616398cdf46a569493c60552674498f6cc30de7d2016d1db8f20cb3d4a7b8',
    'native-affix-effect-enums-v1.json': '6343ce69b3c32acf5b91203c8cb608e2507582777a07494a5edcc6b7033c9e85',
    'native-calibration-producer-v1.json': '8c1ecda1ebbccde59a3eba27140eca78a23d8ca43975f18584e6988fa87f130d',
}


@lru_cache(maxsize=1)
def source():
    packets = {}
    for name, digest in SOURCES.items():
        raw = (ROOT / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError('Native Attack accumulator source hash conflict')
        packets[name] = json.loads(raw)
    trace, typed, names = packets.values()
    rows = typed['rows']
    fields = lambda key: {k: v['decoded_value'] for k, v in rows[key]['fields'].items()}
    if trace['installed_build_id'] != '26267212' or typed['installed_build_id'] != '26267212':
        raise ValueError('Native Attack accumulator build conflict')
    if (names['selected_controls']['D01']['property_name'] != 'attack' or
            names['selected_controls']['D11']['property_name'] != 'structure_attack' or
            tuple(fields('D0100')[k] for k in ('attr_id', 'effect_range', 'type')) != ('D01', 1, 1) or
            tuple(fields('D0101')[k] for k in ('attr_id', 'effect_range', 'type')) != ('D01', 1, 2) or
            fields('D0102')['effect_range'] != 2 or
            fields('D1100')['attr_id'] != 'D11' or
            fields('attack')['attr_id'] != 'D01' or
            trace['D0100']['typed_attack_property']['init'] != 0 or
            trace['D0100']['typed_attack_property']['min'] != 0 or
            trace['D0100']['typed_attack_property']['max'] != 130000 or
            not any('(init+ABS)*(1+RATE)' in line for line in trace['ordinary_abs_path'])):
        raise ValueError('Native Attack accumulator binding conflict')
    return {'build': typed['installed_build_id'], 'trace_sha256': SOURCES['native-attack-accumulator-v1.json'],
            'typed_sha256': SOURCES['native-attack-affix-types-v1.json'],
            'property_name': 'attack', 'absolute_affix': 'D0100', 'rate_affix': 'D0101'}


@lru_cache(maxsize=1)
def source_scope():
    packets = {}
    for name, digest in SCOPE_SOURCES.items():
        raw = (ROOT / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError('Native Attack producer scope source hash conflict')
        packets[name] = json.loads(raw)
    gap, origins, enums, calibration = packets.values()
    rows = origins['records']
    ids = {pair['affix_id'] for row in rows for pair in row['affix_pairs']}
    expected = {'O1100', 'O1000', 'O0500', 'D5100', 'D1100'}
    if (gap['build_id'] != source()['build'] or origins['installed_build_id'] != source()['build'] or
            enums['installed_build_id'] != source()['build'] or
            calibration['installed_build_id'] != source()['build'] or
            gap['origin_packet_sha256'] != SCOPE_SOURCES['native-origin-affix-lists-480-v1.json'] or
            gap['origin_gear_rows_checked'] != len(rows) or len(rows) != 480 or
            gap['rows_with_D0100'] != 0 or ids != expected or
            enums['D0100_source_relation']['effect_range_enum'] != 'AP_EFFECT_ALL' or
            enums['D0100_source_relation']['type_enum'] != 'AP_CALC_TYPE_ABS' or
            calibration['typed_calibration_affixes']['E4300']['property_name'] != 'attack_type_dam_add_rate_dot'):
        raise ValueError('Native Attack producer scope binding conflict')
    return {'origin_rows_checked': len(rows), 'ordinary_origin_D0100_rows': 0,
            'observed_gun_origin_helper_injects_given_only': True,
            'origin_affix_ids': sorted(ids),
            'calibration_roll_fields': ['term_id', 'term_index', 'affix_id', 'affix_val'],
            'calibration_generation_is_not_activation': True,
            'origin_packet_sha256': SCOPE_SOURCES['native-origin-affix-lists-480-v1.json']}


def _number(value, label):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f'{label} must be a finite number')
    return value


def project(scenario):
    """Evaluate explicit default-branch inputs; never infer the active build map.

    ``rate`` is a fraction (0.2 means +20%).  Unknown active sources and the
    SET/independent branches always withhold a complete property value.
    """
    proof = source()
    if not isinstance(scenario, dict):
        raise ValueError('Attack scenario must be an object')
    initial = scenario.get('initial_attack')
    if initial is not None:
        initial = _number(initial, 'initial_attack')
    changes = scenario.get('changes', [])
    if not isinstance(changes, list):
        raise ValueError('Attack changes must be a list')
    absolute = rate = 0
    seen = set()
    for row in changes:
        if not isinstance(row, dict) or row.get('affix_id') not in ('D0100', 'D0101'):
            raise ValueError('Only typed D0100/D0101 Attack affixes are supported')
        identity = row.get('source_id')
        if not isinstance(identity, str) or not identity or (identity, row['affix_id']) in seen:
            raise ValueError('Each Attack affix source and affix_id pair must be unique')
        seen.add((identity, row['affix_id']))
        value = _number(row.get('value'), 'Attack affix value')
        if row['affix_id'] == 'D0100':
            absolute += value
        else:
            rate += value
    missing = []
    if initial is None:
        missing.append('initial_attack')
    if scenario.get('all_active_sources_known') is not True:
        missing.append('complete active affix, calibration, buff and equipment source map')
    if scenario.get('set_override') is not False:
        missing.append('SET override absence')
    if scenario.get('independent_effect') is not False:
        missing.append('independent effect absence')
    if scenario.get('bound_override') is not False:
        missing.append('bound override absence')
    prebound = (initial + absolute) * (1 + rate) if initial is not None else None
    if prebound is not None and prebound < 0:
        missing.append('native lower-bound and rounding behavior for negative result')
    return {'status': 'explicit_default_branch_scenario' if not missing else 'partial_attack_property',
            'value_before_bounds': prebound if not missing else None,
            'known_absolute_sum': absolute, 'known_rate_sum': rate,
            'initial_attack': initial, 'conditional_prebound': prebound,
            'missing': missing, 'scenario_only': True, 'equipped_attack_verified': False,
            'source_method': proof,
            'not_included': ['final hit damage', 'critical/weakspot/status/proc damage', 'target mitigation']}


def selected(native_component, scenario=None):
    """Keep a known tier/star component distinct from equipped Attack."""
    proof = source()
    scope = source_scope()
    result = project(scenario) if scenario is not None else None
    return {'status': 'explicit_scenario' if result else 'active_source_map_unverified',
            'native_base_weapon_component': native_component.get('value') if native_component else None,
            'attack_property_scenario': result,
            'equipped_attack': None,
            'missing': ['active weapon/equipment/calibration affix map', 'other Attack sources and overrides'],
            'source_method': proof,
            'producer_scope': scope,
            'scope': 'D0100 absolute Attack and D0101 rate Attack feed the default property branch. The 480 ordinary origin rows have no D0100 and the recovered tier/star D0100 injection is GIVEN-item-only; weapon tier/star base is separate until its ordinary active affix join is proven.'}
