"""Copied native interval and RPM operations with explicit, source-typed inputs.

The table-row binding for a selected weapon has not yet been established. This
module therefore executes only a caller-supplied named scenario; it never
converts a displayed Fire Rate or weapon_rpm field into an interval.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).with_name('evidence_packets')
TRACE_FILES = {
    'interval': ('native-base-interval-method-v1.json',
                 '256d85d132d1be92dd7d1c2d2a2037d65b7ccc73e1943a749b1f228bb7c93d39',
                 'da982bdaac2c77ac163dc460417585c18cc4e530d89c4011be70f17a3adaa453'),
    'rpm': ('native-rpm-method-v1.json',
            '079f0c6feac378f3833e370e996b7c87295864002b2ffd8f77b663f827a58fd0',
            '6f5e025ae6109a17a46bfcc5aa9dbacabdb3e65720a45caa03fa59681963809b'),
}
PYC_SHA256 = '891bbda57741ffa7c4dd27e13d58c0a65534b29621838e9c4b86d95e1f1fa1b5'


@lru_cache(maxsize=1)
def method_source():
    result = {}
    for kind, (name, expected_file_hash, expected_body_hash) in TRACE_FILES.items():
        raw = (ROOT / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected_file_hash:
            raise ValueError(f'Native {kind} trace hash conflict')
        packet = json.loads(raw)
        if (packet.get('source_pyc_sha256') != PYC_SHA256 or
                packet.get('body_sha256') != expected_body_hash or
                (kind == 'interval' and packet.get('method') != 'get_gun_shoot_interval') or
                (kind == 'rpm' and 'get_gun_shoot_interval' not in packet.get('names', []))):
            raise ValueError(f'Native {kind} method identity conflict')
        result[kind] = {'source_pyc_sha256': PYC_SHA256,
                        'body_sha256': expected_body_hash,
                        'trace_sha256': expected_file_hash}
    return result


def _number(value, label, *, zero=True):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0 or (not zero and value == 0):
        raise ValueError(f'{label} must be a finite {"nonnegative" if zero else "positive"} number')
    return float(value)


def _required(fields, name):
    if name not in fields or fields[name] is None:
        raise KeyError(name)
    return fields[name]


def project(fields, weapon_rpm_add_rate=0):
    """Return the round-call argument and a scoped built-in-round expectation.

    ``fields`` is an explicit gun_base_params_data scenario with a named
    ShootMode. A missing selected-weapon table join must remain missing at the
    caller; it must not be filled from a public Fire Rate label. The copied
    module has no top-level assignment to ``round``. Half ties stay unresolved
    because runtime global rebinding has not been observed or excluded.
    """
    source = method_source()
    if not isinstance(fields, dict):
        raise ValueError('Native interval inputs must be a field mapping')
    if type(weapon_rpm_add_rate) not in (int, float) or not math.isfinite(weapon_rpm_add_rate) or weapon_rpm_add_rate <= -1:
        raise ValueError('weapon_rpm_add_rate must be finite and greater than -1')
    mode = fields.get('default_shoot_mode')
    if mode is None:
        return {'status': 'missing_native_interval_fields', 'missing': ['default_shoot_mode'],
                'round_call_argument': None, 'source_method': source}
    if mode not in ('SINGLE', 'BURST', 'AUTO'):
        return {'status': 'unsupported_native_shoot_mode', 'mode': mode,
                'round_call_argument': None, 'source_method': source}
    required = {'SINGLE': ['single_time_interval'],
                'BURST': ['burst_bullet_interval', 'burst_bullet_num', 'single_time_interval'],
                'AUTO': ['auto_time_interval']}[mode]
    plug_count = fields.get('shoot_time_to_trigger_plug', 0)
    if mode == 'SINGLE' and plug_count is not None and type(plug_count) in (int, float) and plug_count > 0:
        required.append('plug_time')
    missing = [name for name in required if fields.get(name) is None]
    if missing:
        return {'status': 'missing_native_interval_fields', 'missing': missing,
                'mode': mode, 'round_call_argument': None, 'source_method': source}
    if mode == 'SINGLE':
        interval = _number(_required(fields, 'single_time_interval'), 'single_time_interval')
        if plug_count is None:
            plug_count = 0
        plug_count = _number(plug_count, 'shoot_time_to_trigger_plug')
        if plug_count > 0:
            interval += _number(_required(fields, 'plug_time'), 'plug_time') / plug_count
    elif mode == 'BURST':
        count = _required(fields, 'burst_bullet_num')
        if type(count) is not int or count <= 0:
            raise ValueError('burst_bullet_num must be a positive integer')
        interval = (_number(_required(fields, 'burst_bullet_interval'), 'burst_bullet_interval') * count +
                    _number(_required(fields, 'single_time_interval'), 'single_time_interval'))
    else:
        interval = _number(_required(fields, 'auto_time_interval'), 'auto_time_interval')
    if interval == 0:
        return {'status': 'native_zero_interval_return', 'mode': mode, 'base_interval_seconds': 0.0,
                'adjusted_interval_seconds': None, 'round_call_argument': None,
                'native_return': 0, 'source_method': source,
                'scope': 'Caller-supplied interval fields; no selected-weapon source binding'}
    adjusted = interval / (1.0 + weapon_rpm_add_rate)
    argument = (60.0 / adjusted) * (fields['burst_bullet_num'] if mode == 'BURST' else 1)
    if not math.isfinite(argument):
        raise ValueError('Native fire-rate round argument is not finite')
    half_tie = math.isclose(argument % 1, .5, rel_tol=0, abs_tol=1e-10)
    return {'status': 'parameterized_native_round_argument', 'mode': mode,
            'base_interval_seconds': interval, 'adjusted_interval_seconds': adjusted,
            'weapon_rpm_add_rate': weapon_rpm_add_rate,
            'round_call_argument': argument, 'native_return': None,
            'native_return_expected': None if half_tie else round(argument),
            'round_binding': ('half_tie_unresolved' if half_tie else
                              'builtin_expected_no_module_assignment'),
            'source_method': source,
            'scope': 'Caller-supplied interval fields; no selected-weapon source binding'}
