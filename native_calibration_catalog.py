"""Read-only native calibration blueprint choices and potential term ranges.

Source item IDs and compatible-series wording are evidence. They do not prove a
selected owned blueprint, current roll, combat activation or final damage.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re

import catalog

PACKETS = Path(__file__).with_name('evidence_packets')
SOURCES = {
    'native-calibration-item-compatibility.json': '04919c428da95bbae6cfb6ac20637af9b58eaa589aea7cdeeea5fd01fd92e828',
    'native-calibration-term-stat-display.json': '2fd45615eb5b6c576a06d53209a7d48f1ac54c656ac4792dc88c92cceece7a15',
    'native-calibration-english-spotchecks.json': 'dfb34cf6b2b1ae02e51599982681311ef3186291c7def0a38dbbbe6629116d87',
    'native-gun-correct-print-styles.json': '70ba7203e5f90571194005e14116893e736d164bbf8b44a30b4110658ac756d4',
    'native-gun-correct-common-terms.json': 'c39cfbf939e79395b19623393b22dbf9337661f74dfc7d546befedb10cc91889',
}
# This link is limited to the literal series token present in BOTH the exact
# selected catalog name and source compatibility wording. It is not the native
# item-instance compatibility consumer.
SERIES_TOKENS = frozenset({'AUG', 'AKM', 'M416', 'SCAR', 'MG4', 'RPD',
                            'Glock', 'DP12', 'AA12', 'M870', 'AWM', 'M82A1'})
STYLE_GLOSSES = {'精准风格': 'Precision', '重型风格': 'Heavy',
                 '速射风格': 'Rapid', '先发风格': 'First action',
                 '转能风格': 'Energy conversion'}


def _plain(value):
    return value.split('_$S@', 1)[0]


@lru_cache(maxsize=1)
def _source():
    packets = {}
    for name, digest in SOURCES.items():
        raw = (PACKETS / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError('Native calibration source hash conflict: ' + name)
        packets[name] = json.loads(raw)
    links = packets['native-calibration-item-compatibility.json']
    terms = packets['native-calibration-term-stat-display.json']
    if (links['installed_build_id'] != '26267212' or terms['installed_build_id'] != '26267212' or
            links['source_hashes']['style_packet_sha256'] != SOURCES['native-gun-correct-print-styles.json'] or
            terms['source_hashes']['common_terms_packet_sha256'] != SOURCES['native-gun-correct-common-terms.json'] or
            len(links['records']) != 188 or len(terms['term_options']) != 59):
        raise ValueError('Native calibration packet count, build or source join conflict')
    by_term = {row['native_term_id']: row for row in terms['term_options']}
    if len(by_term) != 59:
        raise ValueError('Duplicate native calibration term ID')
    public = {row['item_id']: row for row in packets['native-calibration-english-spotchecks.json']['observations']}
    return links, by_term, public


def choices(weapon_id):
    entry = catalog.ENTRIES.get(weapon_id)
    if not entry or entry['kind'] != 'weapon':
        raise ValueError('Choose an exact weapon catalog identity')
    links, by_term, public = _source()
    series = entry['name'].split(' - ', 1)[0]
    if series not in SERIES_TOKENS or (entry['name'] != series and
                                       not entry['name'].startswith(series + ' - ')):
        return {'weapon_id': weapon_id, 'status': 'exact_series_bridge_missing',
                'choices': [], 'calculation_included': False,
                'missing': 'A source-backed exact weapon-series link is needed before filtering native calibration options.'}
    selected = []
    for row in links['records']:
        current = row['native_is_valid_token']['value'] == 1 and row['source_old_blueprint_notice'] is None
        if not current:
            continue
        source_words = row['compatibility_first_sentence']
        if re.search(r'(?<![A-Za-z0-9])' + re.escape(series) + r'(?![A-Za-z0-9])', source_words) is None:
            continue
        item_id = row['calibration_item_id']
        terms = []
        for token in row['available_common_term_ids']['values']:
            term_id = token['value']
            if term_id not in by_term:
                raise ValueError(f'Native calibration term {term_id} missing')
            terms.append({'native_term_id': term_id, 'options': [
                {'affix_codes': [affix['affix_id'] for affix in option['affix_codes']],
                 'property_names': option['resolved_property_names'],
                 'property_mapping_status': 'typed_property_names' if option['resolved_property_names'] else 'unresolved_native_affix_property',
                 'minimum_fraction': option['native_min_val']['value'],
                 'maximum_fraction': option['native_max_val']['value'],
                 'native_description': _plain(option['native_term_description']['source_string'])
                     if option['native_term_description'] else None}
                for option in by_term[term_id]['options']]})
        public_row = public.get(item_id)
        public_title = (public_row['public_exact_page_title'] if public_row and
                        public_row['identity_status'].endswith('semantic_title_agree') and
                        public_row['native_item_title_prefix'] == _plain(row['native_item_title']['source_string'])
                        else None)
        selected.append({'item_id': item_id,
                         'native_title': _plain(row['native_item_title']['source_string']),
                         'native_style': _plain(row['native_style_source_string']['source_string']),
                         'style_english_gloss': STYLE_GLOSSES.get(_plain(row['native_style_source_string']['source_string'])),
                         'gloss_status': 'literal_translation_not_exact_english_item_name',
                         'public_title': public_title,
                         'public_url': public_row['public_url'] if public_title else None,
                         'compatible_series_source_text': source_words,
                         'native_weapon_type_tokens': [x['value'] for x in row['native_weapon_type_tokens']['values']],
                         'available_terms': terms,
                         'source_status': 'installed_game_table_current_flag_and_series_text',
                         'ownership_inferred': False, 'selected_rolls_inferred': False,
                         'calculation_included': False})
    return {'weapon_id': weapon_id, 'status': 'source_series_text_candidates',
            'source_build': links['installed_build_id'],
            'series_token': series, 'choices': sorted(selected, key=lambda item: item['item_id']),
            'compatibility_scope': 'Native item text names this weapon series; exact instance consumer, tier and ownership remain unverified.',
            'calculation_included': False}
