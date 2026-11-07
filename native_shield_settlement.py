"""Bounded native held-shield HP branch with explicit post-attenuation input.

This is not outgoing bullet damage or final health loss. No active shield,
attenuation coefficient, overflow behavior, or target is inferred from gear.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).with_name('evidence_packets')
HASHES = {
    'native-shield-hit-settlement-v1.md': 'a551d2298ffb60f2d976c8ca4e52becb081a8471cb81c59c68a379b03583c550',
    'native-shield-synthetic-vectors-v1.json': '791075cf380be2d29bcf8f71f25a0daa76940086ef18b0118a1958eb7f106d58',
}
PLAYER_HASHES = {
    'native-player-hp-route-v1.md': '23aeea1ca6efcfe0a807bc7b28fb9e0cc6605104d4a32fa35f5e8c297269120d',
    'native-player-hp-path-manifest-v1.json': '027d3467744859e5939f03cb1b4fedd205fb3ac3513cf8dc78ae0ae31b0e591d',
}


@lru_cache(maxsize=1)
def proof():
    for name, digest in HASHES.items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Native shield settlement source hash conflict')
    packet = json.loads((ROOT / 'native-shield-synthetic-vectors-v1.json').read_text())
    vectors = packet['vectors']
    if (packet['game_code_executed'] is not False or
            [(row['shield_hp_after'], row['damage_hp_without_apply_return'],
              row['shield_crush_and_destroy_event']) for row in vectors] !=
            [(50, 30, False), (0, 35, True), (80, 40, False)]):
        raise ValueError('Native shield synthetic vector conflict')
    return {'build': '26267212', 'scope': 'recognized shield_hold object after damage attenuation',
            'source_sha256': HASHES['native-shield-hit-settlement-v1.md'],
            'vectors_sha256': HASHES['native-shield-synthetic-vectors-v1.json'],
            'methods': ['CompBeHitServer.get_damage_hp_without_apply',
                        'IBeHitServerWithPowerShield._process_shield',
                        'CompPowerShieldServer.reduce_shield_hp',
                        'CompPowerShieldServer._change_shield_hp']}


@lru_cache(maxsize=1)
def player_proof():
    for name, digest in PLAYER_HASHES.items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Native player HP route source hash conflict')
    manifest = json.loads((ROOT / 'native-player-hp-path-manifest-v1.json').read_text())
    known = {row['index']: row['pyc_sha256'] for row in manifest['rows']}
    if known != {
        4306: '68cd0d09c2b8ef3d1ffd83420e587bd58771d3b9174706a288cdc3acaf4704b1',
        59609: '963c9b27084862d413157367bbc09d4baa35acdb9015bf68ad78bc3f50c518d4',
        76687: '325659f19ca8c55bd82c925162e880db1a49ee12caed4fa6ec8aadbe6a6715f5'}:
        raise ValueError('Native player HP route manifest binding conflict')
    return {'build': '26267212', 'scope': 'CompBeHitPlayerServer recognized held-shield branch',
            'source_sha256': PLAYER_HASHES['native-player-hp-route-v1.md'],
            'manifest_sha256': PLAYER_HASHES['native-player-hp-path-manifest-v1.json'],
            'health_take_damage_skipped_on_recognized_shield': True,
            'other_health_guards_and_property_bounds_unresolved': True}


def _number(value, field):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f'{field} must be finite numeric input')
    if value < 0:
        raise ValueError(f'{field} must be nonnegative')
    return value


def _finite(value, field):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f'{field} must be finite numeric input')
    return value


def attenuate(inputs):
    """Pure obstruction step before application, with all operands supplied."""
    source = player_proof()
    if not isinstance(inputs, dict):
        raise ValueError('Attenuation inputs must be an object')
    required = ('damage_before_attenuation', 'attenuation_factor', 'obstruct_nums')
    missing = [name for name in required if name not in inputs]
    if missing:
        return {'status': 'missing_attenuation_inputs', 'post_attenuation_damage': None,
                'missing': missing, 'source_method': source, 'applied_hp_loss': None}
    damage = _finite(inputs['damage_before_attenuation'], 'damage_before_attenuation')
    factor = _finite(inputs['attenuation_factor'], 'attenuation_factor')
    count = inputs['obstruct_nums']
    if type(count) is not int or count < 0:
        raise ValueError('obstruct_nums must be a nonnegative integer')
    try:
        value = max(0, damage * (1 - factor) ** count)
    except OverflowError as error:
        raise ValueError('attenuation result exceeds a finite modeled value') from error
    if not math.isfinite(value):
        raise ValueError('attenuation result exceeds a finite modeled value')
    return {'status': 'native_obstruction_attenuation',
            'post_attenuation_damage': value,
            'equation': 'max(0, damage_before_attenuation * (1 - attenuation_factor) ** obstruct_nums)',
            'source_method': source, 'applied_hp_loss': None,
            'scope': 'Pre-application amount only; hit eligibility, shield and HP mutation are separate.'}


def _unknown(status, missing, source):
    return {'status': status, 'shield_hp_after': None,
            'shield_be_hit_event': None, 'shield_crush_and_destroy_event': None,
            'damage_hp_without_apply_return': None,
            'player_hit_result': None, 'real_damage_hp_event_amount': None,
            'health_take_damage_called': None,
            'applied_hp_loss': None, 'hp_change_value': None,
            'overflow_applied_to_hp': None,
            'missing': missing, 'source_method': source,
            'game_verified': False}


def evaluate(inputs):
    """Project one recognized held-shield hit from supplied numeric state.

    The damage value must already be post attenuation. The return from the
    enclosing native method is *not* proof of applied health damage.
    """
    source = proof()
    if not isinstance(inputs, dict):
        raise ValueError('Native shield branch inputs must be an object')
    if inputs.get('recognized_held_shield') is False or inputs.get('shield_state') not in (None, 'shield_hold'):
        return _unknown('shield_branch_not_applicable', ['recognized held shield in shield_hold state'], source)
    required = ('recognized_held_shield', 'shield_state', 'damage_is_post_attenuation',
                'post_attenuation_damage', 'current_shield_hp', 'maximum_shield_hp',
                'invincible_shield_type', 'shield_exists_after_change')
    missing = [field for field in required if field not in inputs]
    if inputs.get('recognized_held_shield') is not True:
        missing.append('recognized_held_shield=true')
    if inputs.get('shield_state') != 'shield_hold':
        missing.append('shield_state=shield_hold')
    if inputs.get('damage_is_post_attenuation') is not True:
        missing.append('damage_is_post_attenuation=true')
    if inputs.get('shield_exists_after_change') is not True:
        missing.append('shield_exists_after_change=true')
    if 'invincible_shield_type' in inputs and type(inputs['invincible_shield_type']) is not bool:
        raise ValueError('invincible_shield_type must be an explicit boolean')
    if missing:
        return _unknown('missing_shield_branch_inputs', list(dict.fromkeys(missing)), source)
    damage = _number(inputs['post_attenuation_damage'], 'post_attenuation_damage')
    before = _number(inputs['current_shield_hp'], 'current_shield_hp')
    maximum = _number(inputs['maximum_shield_hp'], 'maximum_shield_hp')
    if before > maximum:
        raise ValueError('current_shield_hp cannot exceed maximum_shield_hp in this bounded scenario')
    after = before if inputs['invincible_shield_type'] else min(max(before - damage, 0), maximum)
    for name in ('player_server_path_confirmed', 'isolated_hit_no_concurrent_hp_changes'):
        if name in inputs and type(inputs[name]) is not bool:
            raise ValueError(f'{name} must be an explicit boolean')
    player_isolated = (inputs.get('player_server_path_confirmed') is True and
                       inputs.get('isolated_hit_no_concurrent_hp_changes') is True)
    player_source = player_proof() if player_isolated else None
    return {'status': 'recognized_held_shield_branch',
            'shield_hp_before': before, 'shield_hp_after': after,
            'shield_maximum': maximum, 'post_attenuation_damage': damage,
            'shield_be_hit_event': True,
            'shield_crush_and_destroy_event': after <= 0,
            'damage_hp_without_apply_return': damage,
            'player_hit_result': 'HIT_SHIELD' if player_isolated else None,
            'real_damage_hp_event_amount': damage if player_isolated else None,
            'health_take_damage_called': False if player_isolated else None,
            'applied_hp_loss': 0 if player_isolated else None,
            'hp_change_value': 0 if player_isolated else None,
            'overflow_applied_to_hp': False if player_isolated else None,
            'missing': (['live hit eligibility, actual shield/holder state and authoritative server outcome']
                        if player_isolated else
                        ['player server shield branch confirmation and isolated no-concurrent-HP-change state',
                         'HP behavior for other hit paths and targets']),
            'source_method': source, 'player_source_method': player_source,
            'game_verified': False,
            'scope': ('Isolated recognized player held-shield hit: health take_damage is skipped, '
                      'so shield excess does not reach HP. real_damage_hp is not measured HP loss.'
                      if player_isolated else
                      'Shield HP and break events only; returned damage is not applied health loss or DPS.')}
