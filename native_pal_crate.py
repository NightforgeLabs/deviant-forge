"""Exact English reward identities for the named Pal crate; no draw model."""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent / 'evidence_packets'
PACKET = ROOT / 'native-pal-crate-37560018-crosswalk-v1.json'
PACKET_SHA256 = '9317f5d1f2313d86b6b7739e3fff556fc442c95f650f8dbfbffb261363ca04f8'
NAMED = ROOT / 'native_named_pal_crate_sample.json'
NAMED_SHA256 = '69c899fed69b606e93403c332fd0b1134c3df2085833e16ea568d7ba8b9aeb45'


@lru_cache(maxsize=1)
def records():
    if (hashlib.sha256(PACKET.read_bytes()).hexdigest() != PACKET_SHA256 or
            hashlib.sha256(NAMED.read_bytes()).hexdigest() != NAMED_SHA256):
        raise ValueError('Named Pal crate crosswalk source hash conflict')
    packet = json.loads(PACKET.read_text())
    named = json.loads(NAMED.read_text())
    counts = packet['counts']
    if (packet['schema_version'] != 1 or packet['installed_build_id'] != '26267212' or
            packet['crate_item_id'] != named['crate_item_id'] != 37560018 or
            packet['crate_installed_english_name'] != 'Random Pal Deviation' or
            packet['source_hashes']['named_pal_crate_packet_sha256'] != NAMED_SHA256 or
            (counts['pools'], counts['normal_pools'], counts['rare_pools'],
             counts['reward_item_variants']) != (4, 3, 1, 21) or
            packet['configured_rare_threshold'] != 15 or
            packet['game_code_executed'] is not False or
            packet['installed_files_modified'] is not False):
        raise ValueError('Named Pal crate identity or source scope conflict')
    old = {}
    for pool in named['reward_groups']:
        for reward in pool['rewards']:
            old[reward['item_id']] = (
                pool['drop_pool_id'], pool['role_from_native_crate_field'],
                reward['quantity_native_field']['value'],
                reward['rating_parsed_from_source_text']['skill'],
                reward['rating_parsed_from_source_text']['activity'])
    output = {}
    for pool in packet['pools']:
        for reward in pool['rewards']:
            item_id = reward['item_id']
            rating = (reward['skill_rating_from_source_text'],
                      reward['activity_rating_from_source_text'])
            if (item_id in output or old.get(item_id) !=
                    (pool['pool_id'], pool['role_from_crate_config'],
                     reward['quantity_configured'], *rating) or
                    reward['english_translation']['english_text'] != reward['installed_english_name'] or
                    not reward['rating_is_source_description_not_runtime_stat'] or
                    not reward['icon_field']['asset_name'].endswith('.png')):
                raise ValueError(f'Named Pal reward identity/rating conflict: {item_id}')
            output[item_id] = {
                'english_name': reward['installed_english_name'],
                'skill_rating_source_text': rating[0],
                'activity_rating_source_text': rating[1],
                'native_icon_token': reward['icon_field']['asset_name'],
                'local_icon_verified': False,
                'source_item_row_offset': reward['item_data_row_offset'],
            }
    if (len(output) != 21 or set(output) != set(old) or
            {row['english_name'] for row in output.values()} !=
            {'Cattiva', 'Chillet', 'Chillet Ignis'} or
            len({row['native_icon_token'] for row in output.values()}) != 3):
        raise ValueError('Named Pal crate English reward coverage conflict')
    return output
