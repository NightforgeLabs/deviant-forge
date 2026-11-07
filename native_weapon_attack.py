"""Source-native tier/star weapon Attack component, never final hit damage.

Only exact, byte-validated native tier and star inputs may enter this method.
The copied build's recovered get_gun_omg_value method multiplies the two
fields and does not round. Calibration, mods and target damage live elsewhere.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path

TRACE = Path(__file__).with_name('evidence_packets') / 'native-weapon-attack-method-v1.json'
TRACE_SHA256 = 'e1f9d4ff36dd0e990e22e14227510d7ba947180c743d67bd17b4c827ae29e80e'
SOURCE_PYC_SHA256 = '891bbda57741ffa7c4dd27e13d58c0a65534b29621838e9c4b86d95e1f1fa1b5'
BODY_SHA256 = 'eeddb4ebfaf8e46161c3b3e21770add1cac8b1353bdd1954dbd1f68ff4cd8b07'
BUILD = '26267212'


@lru_cache(maxsize=1)
def method_source():
    raw = TRACE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != TRACE_SHA256:
        raise ValueError('Native weapon Attack method trace hash conflict')
    packet = json.loads(raw)
    cases = [row for row in packet.get('cases', []) if row.get('method') == 'get_gun_omg_value']
    if len(cases) != 1:
        raise ValueError('Native weapon Attack method identity missing')
    case = cases[0]
    if (case.get('pyc_sha256') != SOURCE_PYC_SHA256 or
            case.get('body_sha256') != BODY_SHA256 or
            case.get('return_expression') != '(preset_attack * attack_radio)' or
            "preset_attack = gun_params.get('gun_preset_attack', 0)" not in case.get('statements', []) or
            "attack_radio = blueprint_params.get('preset_attack_radio', 0)" not in case.get('statements', [])):
        raise ValueError('Native weapon Attack field or operation conflict')
    return {'method': case['method'], 'first_line': case['first_line'],
            'pyc_sha256': SOURCE_PYC_SHA256, 'body_sha256': BODY_SHA256,
            'trace_sha256': TRACE_SHA256, 'build': BUILD}


def selected(evidence):
    """Return a component or a precise missing-input result for one selection."""
    method = method_source()
    if evidence is None:
        return None
    if evidence.get('steam_build_id') != BUILD:
        raise ValueError('Native weapon Attack input build conflict')
    if evidence.get('configuration_status') == 'exceeds_published_max_stars':
        return {'status': 'invalid_selected_stars', 'value': None,
                'missing': [evidence.get('missing_star_reason') or 'Selected stars exceed the exact blueprint maximum'],
                'source_method': method, 'calculation_included': False}
    attack = evidence.get('gun_preset_attack')
    ratio = evidence.get('preset_attack_radio')
    missing = [key for key, value in (('gun_preset_attack', attack),
                                      ('preset_attack_radio', ratio)) if value is None]
    if missing:
        return {'status': 'missing_native_fields', 'value': None, 'missing': missing,
                'source_method': method, 'calculation_included': False}
    if (not all(type(x) in (int, float) and math.isfinite(x) and x > 0 for x in (attack, ratio)) or
            type(evidence.get('gear_id')) is not int or
            type(evidence.get('blueprint_id')) is not int or
            type(evidence.get('selected_tier')) is not int or
            type(evidence.get('selected_stars')) is not int or
            not all(type(evidence.get('source_offsets', {}).get(k)) is int
                    for k in ('origin_attack', 'blueprint_star'))):
        raise ValueError('Native weapon Attack typed identity/offset/value conflict')
    return {'status': 'source_native_base_weapon_attack_component',
            'value': attack * ratio, 'gun_preset_attack': attack,
            'preset_attack_radio': ratio, 'rounding': 'none_in_this_method',
            'gear_id': evidence['gear_id'], 'blueprint_id': evidence['blueprint_id'],
            'tier': evidence['selected_tier'], 'stars': evidence['selected_stars'],
            'source_offsets': evidence['source_offsets'], 'source_method': method,
            'calculation_included': True,
            'not_included': ['calibration', 'mods', 'character Attack', 'projectile count',
                             'critical/weakspot/status/proc damage', 'target mitigation', 'final hit damage']}
