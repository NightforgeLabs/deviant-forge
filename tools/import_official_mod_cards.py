#!/usr/bin/env python3
"""Rebuild exact current Field Guide numeric records from checked official cards.

The transcription is reviewable in research/official_mod_cards.json. This
importer checks the downloaded image hash, exact catalog identity, ordering,
official tier chart, and conflicts. It never maps effect strengths to another
level or turns a pictured Shiny Flash bonus into an ordinary mod bonus.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import catalog


def import_cards(manifest, numeric, catalog_data, image_bytes):
    if hashlib.sha256(image_bytes).hexdigest() != manifest['sha256']:
        raise ValueError('Official image hash changed; review the card again')
    entries = catalog.ENTRIES
    tiers = catalog_data['official_rules']['mod_levels']['ordered_subattribute_tiers']
    output = json.loads(json.dumps(numeric))
    added = []
    for card in manifest['cards']:
        identity, level = card['catalog_id'], str(card['level'])
        entry = entries.get(identity)
        if not entry or entry['slot'] != card['slot'] or entry['name'] != card['display_name'].split(' <')[0] or entry['variant'] != card['display_name'].split('<')[1].rstrip('>'):
            raise ValueError('Official card identity does not exactly match catalog: ' + identity)
        if level not in tiers or len(card['attributes']) != len(tiers[level]) or any(x.get('unit') != 'percent' or x.get('direction') != 'increase' for x in card['attributes']):
            raise ValueError('Unsupported level or attribute semantics: ' + identity)
        profile = {
            'source_image': manifest['local_image'], 'source_url': manifest['source_page'],
            'source_image_url': manifest['source_image_url'], 'source_sha256': manifest['sha256'],
            'game_version': manifest['game_version'], 'observed_system': manifest['card_system'],
            'source_status': 'official pictured Shiny Lv. 17; ordinary Lv. 17 shares subattributes by official Field Guide rule',
            'attributes': card['attributes'],
            'verified_shiny_main_effect': {
                'text': card['shown_main_effect'], 'flash_effect': card['shown_flash_effect'],
                'source_image': manifest['local_image'], 'source_url': manifest['source_page']
            }
        }
        previous = output['profiles'].setdefault(identity, {}).get(level)
        if previous and previous != profile:
            raise ValueError('Conflicting numeric evidence: ' + identity + ' Lv. ' + level)
        if not previous:
            output['profiles'][identity][level] = profile
            added.append(identity + ':' + level)
    return output, added


def import_native_main_effects(manifest, numeric):
    output = json.loads(json.dumps(numeric))
    added = []
    for card in manifest['cards']:
        entry = catalog.ENTRIES.get(card['catalog_id'])
        profile = output['profiles'].get(card['catalog_id'], {}).get(str(card['level']))
        if not entry or not profile or profile.get('source_image') != card['source_image']:
            raise ValueError('Main-effect card lacks the matching exact-level numeric frame')
        if entry.get('primary_effect') and entry['primary_effect'] != card['text']:
            raise ValueError('Native main effect conflicts with current catalog text')
        image = ROOT / card['source_image']
        if not image.is_file():
            raise ValueError('Native evidence image is missing')
        image_hash = hashlib.sha256(image.read_bytes()).hexdigest()
        if image_hash != card['sha256']:
            raise ValueError('Native evidence image hash changed; review the card again')
        evidence = {'text': card['text'], 'source_image': card['source_image'],
                    'source_sha256': image_hash,
                    'game_version': card['game_version'],
                    'source_status': 'visually checked current Field Guide tooltip at this exact level'}
        previous = profile.get('verified_main_effect')
        if previous and previous != evidence:
            raise ValueError('Main-effect evidence conflict')
        if not previous:
            profile['verified_main_effect'] = evidence
            added.append(card['catalog_id'] + ':' + str(card['level']))
    return output, added


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true', help='validate and report without writing')
    args = parser.parse_args()
    manifest = json.loads((ROOT/'research/official_mod_cards.json').read_text())
    path = ROOT/'catalog_numeric.json'
    numeric = json.loads(path.read_text())
    catalog_data = json.loads((ROOT/'catalog.json').read_text())
    updated, added = import_cards(manifest, numeric, catalog_data, (ROOT/manifest['local_image']).read_bytes())
    native = json.loads((ROOT/'research/native_main_effects.json').read_text())
    updated, main_added = import_native_main_effects(native, updated)
    if not args.check and (added or main_added):
        path.write_text(json.dumps(updated, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'new_exact_profiles':added, 'new_verified_main_effects':main_added,
                      'total_exact_evidence_records':sum(len(x) for x in updated['profiles'].values()),
                      'check_only':args.check}))
