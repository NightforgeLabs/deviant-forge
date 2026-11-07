"""Read-only source-gated Food, Whim, crate and enemy aid catalog.

Raw decoded IDs are deliberately absent from user recommendations. A record
must have an exact named item/effect join before it can enter this catalog.
Nothing here writes ownership or contributes a combat formula.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import native_cuisine
import native_named_catalog
import native_mod_choices
import native_mod_choice_english
import native_armor_previews
import native_food_bonus
import native_food_whim_graphs
import native_food_recipes
import native_pal_crate
import native_random_crates

PACKET = Path(__file__).with_name('evidence_packets') / 'aid-catalog-v1.json'
PITY = PACKET.parent / 'native-pal-crate-pity-v1.json'
PITY_SHA256 = '408a6c77c987a7ed0cb61aa3ac678360ad5b63df384621ce5de3ca539f281fb5'
REWARD_SLOTS = PACKET.parent / 'native_crate_reward_slots-v2.json'
REWARD_SLOTS_SHA256 = '92e8deb5030133e640a42aa40d64fe67542b77967e641f7a8cff9ad7b6d3d01f'
FOOD_BOUND = PACKET.parent / 'native-food-whim-bound-v1.json'
FOOD_BOUND_SHA256 = '867c57b79214bceb05d780e57853124d941a205338a07b0588847da57a0d2007'
FOOD_RUNTIME = PACKET.parent / 'native-food-runtime-boundary-v1.json'
FOOD_RUNTIME_SHA256 = 'cf981e1a042917c4b4609180d79e942a29b905f66824bbaf611cb70a5ea38876'
KINDS = ('food_drink', 'whims_deviations', 'crates', 'enemy_hp')
LABELS = {
    'food_drink': ('Food & drink', 'Item names and their buff effects are not linked yet.'),
    'whims_deviations': ('Whims & Deviations', 'Named Whim effects are not linked to the level rows yet.'),
    'crates': ('Crates', 'A named crate and its complete reward rule are not linked yet.'),
    'enemy_hp': ('Enemy health', 'The HP rows are not linked to an enemy and encounter yet.'),
}
HEX64 = re.compile(r'[0-9a-f]{64}\Z')
def digest(value):
    return isinstance(value, str) and bool(HEX64.fullmatch(value))


@lru_cache(maxsize=1)
def _nominal_food_seconds():
    for path, expected in ((FOOD_BOUND, FOOD_BOUND_SHA256),
                           (FOOD_RUNTIME, FOOD_RUNTIME_SHA256)):
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Native food duration source hash conflict')
    bound = json.loads(FOOD_BOUND.read_text())
    runtime = json.loads(FOOD_RUNTIME.read_text())
    if (bound['installed_build_id'] != '26267212' or
            runtime['installed_build_id'] != '26267212' or
            runtime['timing']['nominal_life_time_unit'] != 'seconds'):
        raise ValueError('Native food duration source scope conflict')
    expected = {30110378: (403137000, 1800), 30139002: (530001300, 7200)}
    rows = {row['item_id']: row for row in bound['buff_rows']}
    if set(rows) != set(expected):
        raise ValueError('Named food duration rows changed')
    for item_id, (buff, seconds) in expected.items():
        row = rows[item_id]
        fields = [field for field in row['present_prefix_fields'] if field['name'] == 'life_time']
        if (row['buff_id'] != buff or row['life_time_native_value'] != seconds or
                len(fields) != 1 or fields[0]['value'] != seconds):
            raise ValueError('Named food duration field binding changed')
    return {str(item_id): seconds for item_id, (_, seconds) in expected.items()}


@lru_cache(maxsize=1)
def load():
    packet = json.loads(PACKET.read_text())
    if packet.get('schema_version') != 1 or packet.get('source_build') != '26267212' or \
            packet.get('status') not in ('named_aid_catalog_empty_pending_exact_join',
                                         'reviewed_named_aid_records') or \
            set(packet.get('categories', {})) != set(KINDS):
        raise ValueError('Aid catalog source build or schema conflict')
    for key, row in packet['categories'].items():
        allowed = {'source_rows_not_named_item_effect_join'}
        if key == 'crates':
            allowed.add('named_reward_membership_draw_unknown')
        if key in ('food_drink', 'whims_deviations'):
            allowed.add('named_effect_description_calculation_unknown')
        if row.get('status') not in allowed or \
                not digest(row.get('source_sha256')) or \
                not row.get('source_packet') or not row.get('missing_join'):
            raise ValueError(f'{key}: incomplete raw evidence source gate')
        if row['status'] != 'source_rows_not_named_item_effect_join':
            source_path = PACKET.parent / row['source_packet']
            if source_path.parent != PACKET.parent or not source_path.is_file() or \
                    hashlib.sha256(source_path.read_bytes()).hexdigest() != row['source_sha256']:
                raise ValueError('Named crate source bytes/hash conflict')
    records = packet.get('records')
    if not isinstance(records, list) or (records and packet['status'] != 'reviewed_named_aid_records'):
        raise ValueError('Unreviewed named aid rows cannot be admitted')
    seen = set()
    for row in records:
        if not isinstance(row, dict) or row.get('category') not in KINDS or \
                not isinstance(row.get('catalog_id'), str) or not row['catalog_id'].startswith('aid:') or \
                row['catalog_id'] in seen or not isinstance(row.get('name'), str) or not row['name'].strip() or \
                not isinstance(row.get('summary'), str) or not row['summary'].strip() or \
                row.get('calculation_status') != 'display_only' or 'formula_binding' in row:
            raise ValueError('Named aid needs exact identity, source text and display-only scope')
        seen.add(row['catalog_id'])
        source = row.get('source') or {}
        if source.get('build') != packet['source_build'] or \
                not digest(source.get('record_sha256')) or \
                not digest(source.get('join_sha256')) or \
                not source.get('native_record_id') or not source.get('native_field'):
            raise ValueError('Named aid source and exact join provenance missing')
        if row['category'] == 'crates':
            membership_only = row.get('reward_membership_only') is True
            if (membership_only and row.get('draw_mode') != 'unknown') or \
                    (not membership_only and row.get('draw_mode') not in ('guaranteed', 'select_one', 'random_pool')) or \
                    not isinstance(row.get('rewards'), list) or not row['rewards'] or \
                    any(not isinstance(reward.get('name'), str) or not reward['name'].strip() or
                        not str(reward.get('native_item_id', '')).isdecimal() or
                        type(reward.get('quantity')) is not int or reward['quantity'] < 1 or
                        'probability' in reward
                        for reward in row['rewards']) or 'probability' in row:
                raise ValueError('Named crate needs complete draw mode and sourced reward names; no inferred odds')
            if membership_only and (row.get('availability') != 'current_obtainability_unknown' or
                                    any(not str(reward.get('pool_id', '')).isdecimal() or
                                        reward.get('pool_role') not in ('normal', 'rare') or
                                        type(reward.get('skill_rating_text_value')) is not int or
                                        type(reward.get('activity_rating_text_value')) is not int
                                        for reward in row['rewards'])):
                raise ValueError('Crate reward membership needs bounded source pools and unknown availability')
            if membership_only:
                source_row = packet['categories']['crates']
                source = json.loads((PACKET.parent / source_row['source_packet']).read_text())
                if str(source.get('crate_item_id')) != row['source']['native_record_id'] or \
                        source.get('installed_build_id') != packet['source_build'] or \
                        row['source']['join_sha256'] != source_row['source_sha256']:
                    raise ValueError('Named crate identity/build/join conflict')
                expected = {}
                for group in source['reward_groups']:
                    for item in group['rewards']:
                        rating = item['rating_parsed_from_source_text']
                        expected[str(item['item_id'])] = (
                            item['item_name_source_string']['source_string'].split('_$S@TIDS$', 1)[0],
                            item['quantity_native_field']['value'], str(group['drop_pool_id']),
                            group['role_from_native_crate_field'], rating['skill'], rating['activity'])
                actual = {reward['native_item_id']: (
                    reward['name'], reward['quantity'], reward['pool_id'], reward['pool_role'],
                    reward['skill_rating_text_value'], reward['activity_rating_text_value'])
                    for reward in row['rewards']}
                if len(actual) != len(row['rewards']) or actual != expected:
                    raise ValueError('Named crate reward/source record mismatch')
                guarantee = row.get('source_guarantee')
                if guarantee is not None:
                    if (hashlib.sha256(PITY.read_bytes()).hexdigest() != PITY_SHA256 or
                            hashlib.sha256(REWARD_SLOTS.read_bytes()).hexdigest() != REWARD_SLOTS_SHA256):
                        raise ValueError('Native crate guarantee source hash conflict')
                    pity = json.loads(PITY.read_text())
                    field = pity['typed_field_tokens']['must_rare_reward_loot_times']
                    group = pity['typed_field_tokens']['group_id']
                    description = pity['source_description_crosscheck']
                    if (pity.get('installed_build_id') != packet['source_build'] or
                            pity.get('crate_item_id') != int(row['source']['native_record_id']) or
                            pity.get('named_crate_packet_sha256') != source_row['source_sha256'] or
                            pity.get('verified_reward_slot_packet_sha256') != REWARD_SLOTS_SHA256 or
                            group.get('value') != int(row['source']['native_record_id']) or
                            field.get('value') != 15 or field.get('type_code') != 1 or
                            description.get('native_description_mentions_15_attempt_guarantee') is not True or
                            description.get('source_item_description', {}).get('source_string') != row['source_description_original'] or
                            guarantee.get('max_opens') != field['value'] or
                            guarantee.get('unknown') != ['current progress', 'reset rule', 'draw order', 'odds'] or
                            'probability' in guarantee):
                        raise ValueError('Native crate guarantee identity, wording or unknowns conflict')
        elif row['category'] in ('food_drink', 'whims_deviations'):
            if not row.get('effect_text') or row.get('availability') != 'current_obtainability_unknown' or \
                    (row['category'] == 'food_drink' and not row.get('effect_native_id')) or \
                    (row['category'] == 'whims_deviations' and
                     (row.get('effect_native_id') is not None or row.get('effect_description_only') is not True)):
                raise ValueError('Named aid effect ID and text missing')
            source_row = packet['categories'][row['category']]
            source = json.loads((PACKET.parent / source_row['source_packet']).read_text())
            matched = [native for native in source['records']
                       if str(native['item_id']) == row['source']['native_record_id']]
            if len(matched) != 1 or source.get('installed_build_id') != packet['source_build'] or \
                    row['source']['join_sha256'] != source_row['source_sha256'] or \
                    row.get('source_name_original') != matched[0]['source_item_name']['source_string'] or \
                    row.get('source_description_original') != matched[0]['source_description_effect_line']['source_string'] or \
                    [str(item['value']) for item in matched[0]['buff_effect_list']['values']] != \
                    ([row['effect_native_id']] if row.get('effect_native_id') else []):
                raise ValueError('Named consumable identity/effect source mismatch')
        elif row['category'] == 'enemy_hp':
            if not all(row.get(key) is not None for key in ('scenario', 'difficulty', 'level', 'max_hp')) or \
                    row.get('hp_unit') != 'HP':
                raise ValueError('Enemy HP needs exact encounter, level, difficulty and unit')
    return packet


def overview():
    packet = load()
    food_seconds = _nominal_food_seconds()
    records = [dict(row) for row in [*packet['records'], *native_cuisine.records(),
                                    *native_random_crates.records()]]
    typed = native_named_catalog.records()
    typed_by_id = {row['catalog_id']: row for row in typed}
    prior_ids = {row['catalog_id'] for row in records}
    for row in records:
        named = typed_by_id.get(row['catalog_id'])
        if named and row['category'] in ('food_drink', 'whims_deviations'):
            if (row.get('source_name_original') != named['source_title_original'] or
                    row.get('source_description_original') != named['source_description_original']):
                raise ValueError('Typed native title or description conflicts with installed named item: ' + row['catalog_id'])
            if row['name'] != named['name']:
                row['prior_gloss'] = row['name']
            row['name'] = named['name']
            row['english_description'] = named['english_description']
            row['source_category_label'] = named['english_category']
            row['source_category_original'] = named['source_category_original']
            row['source_use_function'] = named['source_use_function']
            row['native_buff_rows'] = named['native_buff_rows']
            row['typed_named_source_sha256'] = named['source_packet_sha256']
            row['english_packet_sha256'] = named['english_packet_sha256']
    records.extend(row for row in typed if row['catalog_id'] not in prior_ids)
    raw_food = native_food_bonus.records()
    by_id = {row['catalog_id']: row for row in records}
    crate = by_id.get('aid:crate:37560018')
    rewards = native_pal_crate.records()
    if (crate is None or crate['name'] != 'Random Pal Deviation' or
            {int(reward['native_item_id']) for reward in crate['rewards']} != set(rewards)):
        raise ValueError('Named Pal crate has no exact English reward crosswalk')
    for reward in crate['rewards']:
        proof = rewards[int(reward['native_item_id'])]
        if (reward['skill_rating_text_value'] != proof['skill_rating_source_text'] or
                reward['activity_rating_text_value'] != proof['activity_rating_source_text']):
            raise ValueError('Named Pal crate source rating conflict')
        reward.update(proof)
    crate['native_reward_crosswalk_sha256'] = native_pal_crate.PACKET_SHA256
    for item_id, bonus in raw_food.items():
        row = by_id.get(f'aid:consumable:{item_id}')
        buffs = row.get('native_buff_rows') if row else None
        if (not row or row['name'] != bonus['source_english_title'] or
                len(buffs or []) != 1 or buffs[0]['buff_id'] != bonus['native_buff_id'] or
                buffs[0]['nominal_seconds'] != bonus['nominal_seconds']):
            raise ValueError(f'Food bonus source/item/buff conflict: {item_id}')
        row['raw_bonus_evidence'] = bonus
    graph_evidence = native_food_whim_graphs.records()
    for item_id, evidence in graph_evidence.items():
        row = by_id.get(f'aid:consumable:{item_id}')
        if row is None or row['category'] not in ('food_drink', 'whims_deviations'):
            raise ValueError(f'Food/Whim graph has no named Aid identity: {item_id}')
        direct = {graph['buff_id'] for graph in evidence['graphs']
                  if graph['cast_depth'] == 0}
        if direct != {buff['buff_id'] for buff in row.get('native_buff_rows') or []}:
            raise ValueError(f'Food/Whim buff graph disagrees with named duration rows: {item_id}')
        row['native_graph_evidence'] = evidence
    for item_id, recipe in native_food_recipes.records().items():
        row = by_id.get(f'aid:consumable:{item_id}')
        if row is None or row['category'] not in ('food_drink', 'whims_deviations'):
            raise ValueError(f'Native crafting configuration has no named Aid identity: {item_id}')
        row['native_recipe_evidence'] = recipe
    for row in records:
        if row.get('english_category'):
            row['source_category_label'] = row['english_category']
    if len({row['catalog_id'] for row in records}) != len(records):
        raise ValueError('Named aid identity duplicated across source packets')
    return {'source_build': packet['source_build'],
            'status': 'reviewed_named_items' if packet['records'] else 'no_exact_named_item_effect_join_yet',
            'categories': [
                {'id': key, 'title': LABELS[key][0],
                 'ready_items': [{'catalog_id': row['catalog_id'], 'category': key, 'name': row['name'],
                                  'summary': ('Source-described defense; amount and applied buff duration unknown.'
                                              if row['catalog_id'] == 'aid:consumable:30110378' else
                                              'Source-described Whim duration bonus; activation and applied expiry unknown.'
                                              if row['catalog_id'] == 'aid:consumable:30139002' else row['summary']),
                                  'calculation_status': row['calculation_status'],
                                  'source_url': row.get('source_url'),
                                 'source_category_label': row.get('source_category_label'),
                                 'english_description': row.get('english_description'),
                                 'prior_gloss': row.get('prior_gloss'),
                                 'source_title_original': row.get('source_title_original') or row.get('source_name_original'),
                                 'source_description_original': row.get('source_description_original'),
                                 'source_use_function': row.get('source_use_function'),
                                 'native_buff_rows': row.get('native_buff_rows') or [],
                                 'availability': row.get('availability', 'unknown'),
                                 'typed_named_source_sha256': row.get('typed_named_source_sha256') or row.get('source_packet_sha256'),
                                 'english_packet_sha256': row.get('english_packet_sha256'),
                                 'raw_bonus_evidence': row.get('raw_bonus_evidence'),
                                 'native_graph_evidence': row.get('native_graph_evidence'),
                                 'native_recipe_evidence': row.get('native_recipe_evidence'),
                                  **({'effect_text': row['effect_text'],
                                      'effect_description_only': row.get('effect_description_only', False),
                                      'native_buff_nominal_seconds': (food_seconds.get(row['source']['native_record_id'])
                                                                      or row.get('native_buff_nominal_seconds')),
                                      'unresolved_secondary_buff_lifetime': row.get('unresolved_secondary_buff_lifetime', False),
                                      'native_buff_duration_scope': 'default_before_modifiers_not_applied_expiry'
                                          if (row['source']['native_record_id'] in food_seconds or
                                              row.get('native_buff_nominal_seconds')) else None}
                                     if key in ('food_drink', 'whims_deviations') else {}),
                                  **({'rewards': row['rewards'], 'draw_mode': row['draw_mode'],
                                      'reward_membership_only': row.get('reward_membership_only', False),
                                      'availability': row.get('availability'),
                                      'source_guarantee': row.get('source_guarantee'),
                                      'native_reward_crosswalk_sha256': row.get('native_reward_crosswalk_sha256')}
                                     if key == 'crates' else {})}
                                 for row in records if row['category'] == key],
                 'ready_count': sum(row['category'] == key for row in records),
                 'plain_missing': LABELS[key][1],
                 'source_packet': (packet['categories'][key]['source_packet'] +
                                   ' + native-typed-named-food-whim-v1.json + native-english-food-whim-v1.json'
                                   + ' + native-food-whim-bonus-graphs-v1.json'
                                   if key in ('food_drink', 'whims_deviations') else
                                   packet['categories'][key]['source_packet'] +
                                   ' + native-random-crate-contents-v1.json'
                                   if key == 'crates' else packet['categories'][key]['source_packet']),
                 'source_sha256': packet['categories'][key]['source_sha256'],
                 'technical_missing_join': (
                     'Names are typed source fields; current availability, effect activation and stacking remain unknown. Eight cuisine IDs lack an indexed item row.'
                     if key == 'food_drink' else
                     'Twelve adjacent Whim candidates have typed names and same-ID nominal lifetime; complete Whim taxonomy and activation remain unproven.'
                     if key == 'whims_deviations' else
                     ('55 described crate configurations have source-linked possible contents; one undescribed test crate is withheld. '
                      'Draw order, odds, counter reset and current obtainability remain unknown.'
                      if key == 'crates' else packet['categories'][key]['missing_join']))}
                for key in KINDS] + [
                {'id': 'choice_containers', 'title': 'Mod choice containers',
                 'ready_items': native_mod_choices.records(),
                 'ready_count': 579,
                 'plain_missing': 'No source-bound mod choice lists are available.',
                 'source_packet': 'native-mod-choice-containers-v1.json + native-mod-choice-english-crosswalk-v1.json',
                 'source_sha256': [native_mod_choices.PACKET_SHA256,
                                   native_mod_choice_english.PACKET_SHA256],
                 'technical_missing_join': ('579 configured choice lists with 5,760 option positions; '
                                            'all 579 titles and 1,640 unique option names have exact installed English keys. '
                                            '5,738 positions match catalog_systems by item ID plus mod code; '
                                            '446 positions match canonical Forge mod IDs. Current availability, cost, '
                                            'grant validation and mod level are unknown. These are not '
                                            'random reward pools.')},
                {'id': 'armor_previews', 'title': 'Armor base previews',
                 'ready_items': native_armor_previews.records(),
                 'ready_count': 1018,
                 'plain_missing': 'No exact native gear-ID previews are available.',
                 'source_packet': 'native-armor-base-preview-v1.json + native-armor-optional-preview-v1.json + native-armor-four-affix-preview-v1.json',
                 'source_sha256': [source[0] for source in native_armor_previews.SOURCES.values()],
                 'technical_missing_join': ('4,828 HP/Psi base-preview gear/star pairs across 1,018 exact native gear IDs. '
                                            'A similar catalog name is not an identity link. Equipped state, materials, '
                                            'calibration, set effects and final player totals are not included.')}],
            'ownership_implied': False, 'formula_ready_items': 0,
            'crate_probabilities_calculated': False}
