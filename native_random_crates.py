"""Configured crate contents with exact item IDs; availability and odds unknown."""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
from pathlib import Path

import native_pal_crate


PACKET = Path(__file__).resolve().parent / 'evidence_packets/native-random-crate-contents-v1.json'
PACKET_SHA256 = '99a6a00a3d3422ac20c05e7928de3a2af1616c2c789ca7470e02d2759b3dfc8a'
EXCLUDED_UNDESCRIBED_TEST_ID = 37560004


@lru_cache(maxsize=1)
def records():
    if hashlib.sha256(PACKET.read_bytes()).hexdigest() != PACKET_SHA256:
        raise ValueError('Native crate contents source hash conflict')
    packet = json.loads(PACKET.read_text())
    counts = packet['counts']
    if (packet['schema_version'] != 1 or packet['installed_build_id'] != '26267212' or
            packet['source_hashes']['crate_reward_slots_packet'] !=
            '92e8deb5030133e640a42aa40d64fe67542b77967e641f7a8cff9ad7b6d3d01f' or
            (counts['crate_configs'], counts['installed_item_rows'],
             counts['english_crate_names'], counts['english_crate_descriptions'],
             counts['linked_pool_refs'], counts['resolved_pool_refs'],
             counts['reward_references'], counts['unique_reward_item_ids']) !=
            (56, 56, 56, 55, 142, 142, 1277, 533) or
            packet['game_code_executed'] is not False or
            packet['installed_files_modified'] is not False):
        raise ValueError('Native crate source build or coverage conflict')
    output = []
    seen_crates, unique_rewards = set(), set()
    pool_count = reward_count = named_count = 0
    pal_ids = set()
    for source in packet['records']:
        crate_id = source['crate_config_id']
        item = source['crate_item']
        if (crate_id in seen_crates or item['item_id'] != crate_id or
                item['status'] != 'typed_item_row' or not item['name_english'] or
                source['item_use_function'] != 'junxuxiang_open'):
            raise ValueError(f'Native crate item/use identity conflict: {crate_id}')
        seen_crates.add(crate_id)
        pools = source['linked_pools']
        pool_ids = set()
        rewards = []
        for pool in pools:
            pool_id = pool['pool_id']
            if (pool_id in pool_ids or pool['status'] != 'typed_pool_resolved' or
                    pool['role'] not in ('normal', 'rare')):
                raise ValueError(f'Native crate pool conflict: {crate_id}/{pool_id}')
            pool_ids.add(pool_id)
            pool_count += 1
            for reward in pool['rewards']:
                reward_id = reward['reward_item_id']
                detail = reward['reward_item']
                quantity = reward['quantity_token']['value']
                if (detail['item_id'] != reward_id or
                        detail['status'] not in ('typed_item_row', 'no_indexed_item_data_row') or
                        not isinstance(quantity, int) or quantity < 1 or
                        (detail['status'] == 'typed_item_row' and not detail['name_english'])):
                    raise ValueError(f'Native crate reward identity conflict: {crate_id}/{reward_id}')
                unique_rewards.add(reward_id)
                reward_count += 1
                named_count += detail['status'] == 'typed_item_row'
                rewards.append({
                    'native_item_id': str(reward_id),
                    'name': detail.get('name_english') or f'Unlabeled item ID {reward_id}',
                    'english_name': detail.get('name_english'),
                    'quantity': quantity, 'pool_id': str(pool_id),
                    'pool_role': pool['role'],
                    'native_icon_token': (detail.get('native_icon') or {}).get('asset_name'),
                    'local_icon_verified': False,
                    'source_identity_status': detail['status'],
                })
        if crate_id == 37560018:
            pal_ids = {int(reward['native_item_id']) for reward in rewards}
        if crate_id == EXCLUDED_UNDESCRIBED_TEST_ID:
            if item['name_english'] != 'New Crate Config Test 1' or item['short_desc_english']:
                raise ValueError('Undescribed test crate exclusion changed')
            continue
        if not item['short_desc_english']:
            raise ValueError(f'Named crate has no source description: {crate_id}')
        if crate_id != 37560018:
            output.append({
                'catalog_id': f'aid:crate:{crate_id}', 'category': 'crates',
                'name': item['name_english'],
                'summary': (f'Configured possible contents: {len(rewards)} reward references '
                            f'across {len(pools)} source pools. Availability and odds unknown.'),
                'calculation_status': 'display_only', 'source_url': None,
                'source_title_original': item['name_source']['source_string'],
                'source_description_original': item['short_desc_source']['source_string'],
                'english_description': item['short_desc_english'],
                'source_use_function': source['item_use_function'],
                'reward_membership_only': True, 'draw_mode': 'unknown',
                'availability': 'current_obtainability_unknown',
                'source_guarantee': None, 'rewards': rewards,
                'native_reward_crosswalk_sha256': PACKET_SHA256,
            })
    if ((len(seen_crates), pool_count, reward_count, len(unique_rewards),
          named_count, len(output)) != (56, 142, 1277, 533, 1072, 54) or
            pal_ids != set(native_pal_crate.records())):
        raise ValueError('Native crate reward coverage or Random Pal control conflict')
    return output
