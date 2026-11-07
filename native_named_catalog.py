"""Typed native food and adjacent Whim names, without inferred activation."""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
from pathlib import Path

PACKET = Path(__file__).with_name('evidence_packets') / 'native-typed-named-food-whim-v1.json'
PACKET_SHA256 = 'b32e99abd8a18a6c1fea660e3f003ba0efd9ff9aa2644d90835019ae1ee1de9c'
ENGLISH_PACKET = PACKET.with_name('native-english-food-whim-v1.json')
ENGLISH_SHA256 = 'bb5a8355e1b294c3c5d082709a988200a6da8c02a678290b21aaa85ab4955dcd'
EXPECTED_BUILD = '26267212'
TYPED_FIELDS = {'source_title': 'name',
                'source_short_description': 'short_desc',
                'source_item_type_name': 'item_type_name'}


def _text(value):
    return value.split('_$S@', 1)[0].strip()


@lru_cache(maxsize=1)
def records():
    raw = PACKET.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PACKET_SHA256:
        raise ValueError('Typed native named catalog hash conflict')
    packet = json.loads(raw)
    english_raw = ENGLISH_PACKET.read_bytes()
    if hashlib.sha256(english_raw).hexdigest() != ENGLISH_SHA256:
        raise ValueError('Native English consumable source hash conflict')
    english = json.loads(english_raw)
    english_by_id = {row['item_id']: row for row in english['records']}
    if (packet.get('installed_build_id') != EXPECTED_BUILD or
            english.get('installed_build_id') != EXPECTED_BUILD or
            english.get('coverage', {}).get('typed_native_rows_with_exact_english_matches') != 513 or
            len(english_by_id) != 521 or
            packet.get('coverage', {}).get('typed_item_data_rows') != 513 or
            len(packet.get('records') or []) != 521 or
            len(packet.get('prior_candidate_disagreements') or []) != 9 or
            packet.get('game_code_executed') is not False or
            packet.get('installed_files_modified') is not False):
        raise ValueError('Typed native named catalog build or coverage conflict')
    result = []
    seen = set()
    counts = {'cuisine': 0, 'adjacent_whim': 0, 'no_indexed_item_data_row': 0}
    for row in packet['records']:
        item_id = row.get('item_id')
        if type(item_id) is not int or item_id in seen:
            raise ValueError('Typed native item identity conflict')
        seen.add(item_id)
        if row.get('status') == 'no_indexed_item_data_row':
            if row.get('family') != 'cuisine':
                raise ValueError('Missing typed item row has wrong family')
            counts['no_indexed_item_data_row'] += 1
            continue
        family = row.get('family')
        if row.get('status') != 'typed_item_data_row' or family not in ('cuisine', 'adjacent_whim'):
            raise ValueError('Unsupported typed item record')
        counts[family] += 1
        bounds = row.get('item_data_row_bounds') or []
        if len(bounds) != 2 or bounds[0] != row['typed_record'].get('record_offset'):
            raise ValueError(f'Item {item_id} lacks bound native row offsets')
        for key, field in TYPED_FIELDS.items():
            typed = row.get(key) or {}
            token = typed.get('typed_token') or {}
            if (typed.get('binding') != 'typed_field_to_validated_localization_object' or
                    token.get('field') != field or
                    type(token.get('slot')) is not int or
                    not 0 <= token['slot'] < row['typed_record']['descriptor_field_count'] or
                    token.get('type_code') != 11 or
                    token.get('value') != typed.get('pointer_body_relative') or
                    token.get('byte_offset') != typed.get('pointer_byte_offset') or
                    not bounds[0] <= token.get('byte_offset', -1) < bounds[1] or
                    not _text(typed.get('source_string') or '')):
                raise ValueError(f'Item {item_id} lacks typed {field} text')
        category = _text(row['source_item_type_name']['source_string'])
        translated = english_by_id.get(item_id) or {}
        if translated.get('status') != 'typed_item_data_row' or translated.get('family') != family:
            raise ValueError(f'Item {item_id} has no exact English source row')
        localized = {}
        for english_key, native_key in (('english_title', 'source_title'),
                                        ('english_short_description', 'source_short_description'),
                                        ('english_item_type_name', 'source_item_type_name')):
            english_field = translated.get(english_key) or {}
            if (english_field.get('source_string') != row[native_key]['source_string'] or
                    english_field.get('source_core_text') != _text(row[native_key]['source_string']) or
                    english_field.get('key_match_mode') not in
                        ('exact_source_text_without_tid_suffix', 'exact_full_source_key') or
                    type(english_field.get('map_pair_byte_offset')) is not int or
                    not english_field.get('english_text')):
                raise ValueError(f'Item {item_id} English field lacks exact native key binding')
            localized[english_key] = english_field['english_text']
        if row.get('availability') != 'unknown; installed archive presence only':
            raise ValueError('Typed item availability changed')
        buffs = row.get('direct_buff_links') or []
        if family == 'adjacent_whim':
            link = row.get('get_image_token_link') or {}
            if (row.get('whim_taxonomy_status') is None or buffs or
                    (link.get('buff_id_token') != (link.get('value_token') or {}).get('value')) or
                    link.get('same_id_typed_buff_nominal_life_time_seconds') != 7200 or
                    link.get('runtime_application_status') != 'unverified'):
                raise ValueError(f'Whim candidate {item_id} has unbound token or duration')
            buff_rows = [{'buff_id': link['buff_id_token'], 'nominal_seconds': 7200,
                          'status': 'typed_same_id_candidate_not_applied'}]
        else:
            if row.get('item_use_related_func') not in ('food', 'gift_open', None) or not isinstance(buffs, list):
                raise ValueError(f'Cuisine {item_id} has unsupported use or buff list')
            if row.get('item_use_related_func') != 'food' and buffs:
                raise ValueError(f'Cuisine {item_id} has an unproven non-food buff link')
            buff_rows = []
            for buff in buffs:
                buff_id, seconds, status = (buff.get('buff_id'),
                                            buff.get('nominal_life_time_seconds'),
                                            buff.get('nominal_life_time_status'))
                if (type(buff_id) is not int or buff_id <= 0 or
                        (status == 'typed' and (type(seconds) not in (int, float) or seconds <= 0)) or
                        (status == 'typed_zero_unresolved' and seconds != 0) or
                        (status == 'buff_record_missing' and seconds is not None) or
                        status not in ('typed', 'typed_zero_unresolved', 'buff_record_missing')):
                    raise ValueError(f'Cuisine {item_id} has unbound buff lifetime')
                buff_rows.append({'buff_id': buff_id,
                                  'nominal_seconds': seconds if status == 'typed' else None,
                                  'status': status})
        single_duration = (buff_rows[0]['nominal_seconds'] if len(buff_rows) == 1
                           and buff_rows[0]['nominal_seconds'] is not None else None)
        result.append({
            'catalog_id': f'aid:consumable:{item_id}',
            'category': 'food_drink' if family == 'cuisine' else 'whims_deviations',
            'name': localized['english_title'],
            'english_description': localized['english_short_description'],
            'english_category': localized['english_item_type_name'],
            'source_title_original': row['source_title']['source_string'],
            'source_description_original': row['source_short_description']['source_string'],
            'source_category_original': row['source_item_type_name']['source_string'],
            'source_category_label': category,
            'summary': (('Typed food-use item; availability and applied effect unknown.'
                         if row.get('item_use_related_func') == 'food' else
                         'Named source item in the cuisine ID group; no food-use buff is established.')
                        if family == 'cuisine' else
                        'Adjacent Whim candidate; taxonomy and activation unverified.'),
            'effect_text': None,
            'effect_description_only': True,
            'calculation_status': 'display_only',
            'native_buff_nominal_seconds': single_duration,
            'native_buff_rows': buff_rows,
            'unresolved_secondary_buff_lifetime': any(
                x['status'] in ('typed_zero_unresolved', 'buff_record_missing')
                for x in buff_rows),
            'native_buff_duration_scope': 'typed_default_before_modifiers_not_applied_expiry',
            'availability': 'unknown',
            'source_use_function': row.get('item_use_related_func'),
            'source_packet_sha256': PACKET_SHA256,
            'english_packet_sha256': ENGLISH_SHA256,
            'source': {'build': EXPECTED_BUILD, 'native_record_id': str(item_id),
                       'native_record_offset': row['typed_record']['record_offset'],
                       'native_field': 'item_data.name/short_desc/item_type_name',
                       'source_hashes': packet['source_hashes']},
        })
    if counts != {'cuisine': 501, 'adjacent_whim': 12,
                  'no_indexed_item_data_row': 8}:
        raise ValueError('Typed native named catalog family counts conflict')
    return result
