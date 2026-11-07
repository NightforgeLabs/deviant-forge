"""Pinned named native cuisine facts, with no inferred active combat effects."""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
from pathlib import Path

PACKETS = Path(__file__).with_name('evidence_packets')
CUISINE_NAME = 'native-expanded-cuisine-v1.json'
CUISINE_SHA = '11d15d350a46b86cc0bfaa667305077886dd8a749ace85a2d60dbce66675644c'
TAG_NAME = 'native-duration-tag-path-v1.json'
TAG_SHA = '7b81282b039981aa3a6c3da72a72640adeea4d59d1212b278150011ca6bb8aa2'
GLOSSES = {
    30110323: 'Bacon Patty Burger', 30110343: 'Miracle Tea',
    30110346: 'Safety Sandwich', 30110375: 'Popping Popcorn',
    30110376: 'Blazing Egg Tart', 30110377: 'Honey Egg Candy',
    30110379: 'Mint Meat Can', 30110380: 'Spicy Meat Hotpot',
    30110404: 'Mist Vision Soup', 30119702: 'Mining Potato Salad',
    30119705: 'Heavy Strike Blue Cake',
}


def _pinned(name, digest):
    raw = (PACKETS / name).read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError('Native cuisine source hash conflict: ' + name)
    return json.loads(raw)


@lru_cache(maxsize=1)
def records():
    cuisine = _pinned(CUISINE_NAME, CUISINE_SHA)
    tags = _pinned(TAG_NAME, TAG_SHA)
    if (cuisine['installed_build_id'] != '26267212' or
            tags['installed_build_id'] != '26267212' or
            not cuisine['nominal_time_unit'].startswith('seconds') or
            tags['conditional_duration_component']['not_a_mutation_time_extend_consumer'] is not True):
        raise ValueError('Native cuisine build, unit or effect scope conflict')
    armed = [row for row in tags['typed_tag_maps'] if row['tag_key'] == 305]
    if (len(armed) != 1 or armed[0]['time_extend_add_rate']['attribute'] !=
            'tag_buff_time_extend_add_rate_armed'):
        raise ValueError('Native cuisine duration tag binding changed')
    rows = cuisine['records']
    if len(rows) != 11 or {row['item_id'] for row in rows} != set(GLOSSES):
        raise ValueError('Native cuisine exact item coverage changed')
    result = []
    for row in rows:
        item_id = row['item_id']
        if (row['item_use_related_func']['source_string'] != 'food' or
                row['item_use_related_func']['type_code'] != 5 or
                row['effect_numeric_claim'] != 'none inferred from description' or
                not row['source_name']['source_string'] or not row['source_description']['source_string']):
            raise ValueError('Native cuisine identity or claim changed')
        buffs = row['buffs']
        if not buffs or len(buffs) > 2:
            raise ValueError('Native cuisine buff link missing')
        lifetimes = []
        for buff in buffs:
            token = buff['item_use_buff_token']
            native = buff['native_buff_record']
            life = native['life_time']
            if (token['buff_id'] != native['buff_id'] or life['name'] != 'life_time' or
                    life['type_code'] != 18 or not isinstance(life['value'], (int, float)) or
                    life['value'] < 0):
                raise ValueError('Native cuisine buff duration field mismatch')
            lifetimes.append(life['value'])
        if (lifetimes.count(0) != (1 if item_id == 30110379 else 0) or
                not any(value > 0 for value in lifetimes)):
            raise ValueError('Native cuisine unresolved secondary duration changed')
        native_name = row['source_name']['source_string'].split('_$S@', 1)[0]
        description = row['source_description']['source_string'].split('_$S@', 1)[0]
        effect_text = description.split('\n#cd1356a', 1)[0]
        result.append({
            'category': 'food_drink', 'catalog_id': f'aid:consumable:{item_id}',
            'name': f'{GLOSSES[item_id]} (translation) · {native_name}',
            'source_name_original': row['source_name']['source_string'],
            'source_description_original': row['source_description']['source_string'],
            'summary': 'Named source item; effect strength and current availability are unknown.',
            'effect_text': effect_text,
            'effect_description_only': True,
            'calculation_status': 'display_only',
            'native_buff_nominal_seconds': next(value for value in lifetimes if value > 0),
            'unresolved_secondary_buff_lifetime': 0 in lifetimes,
            'native_buff_duration_scope': 'default_before_modifiers_not_applied_expiry',
            'source': {'build': cuisine['installed_build_id'],
                       'record_sha256': cuisine['source_hashes']['item'],
                       'join_sha256': cuisine['source_hashes']['links'],
                       'native_record_id': str(item_id),
                       'native_field': 'item_data.name/description; item_use_para.food/buff_effect_list; buff_params.life_time'},
            'source_packet_sha256': CUISINE_SHA,
            'duration_tag_model_applied': False,
        })
    return result
