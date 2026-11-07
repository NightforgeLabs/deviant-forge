"""Exact-ID, read-only V2 mod frame previews from build 26267212.

Configured lines are catalog facts. This module does not activate owned rolls,
server buffs, core effects, or combat arithmetic.
"""
from __future__ import annotations

from functools import lru_cache
import copy
import hashlib
import json
import math
from pathlib import Path
import re

import catalog


PACKET = Path(__file__).with_name('evidence_packets') / 'native-verified-mod-frame-catalog-v1.json'
SOURCE_MD = Path(__file__).with_name('evidence_packets') / 'native-verified-mod-frame-catalog-v1.md'
HASHES = {
    PACKET.name: 'a4ad0f5b761941d6ac5cdd6b0f630443f2e2ac19214905ecb61b141d48e91ae1',
    SOURCE_MD.name: '4d1139a4320d599a5e7dba2f356debe570fa9da186662243344da72c4eecd12d',
}


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@lru_cache(maxsize=1)
def _source():
    if any(_sha(path) != HASHES[path.name] for path in (PACKET, SOURCE_MD)):
        raise ValueError('Native mod frame catalog source hash conflict')
    packet = json.loads(PACKET.read_text())
    coverage = packet['coverage']
    if (packet['build_id'] != '26267212' or packet['game_code_executed'] is not False or
            packet['installed_files_modified'] is not False or
            (coverage['identity_linked_frames'], coverage['mod_identity_rows'],
             coverage['level_previews'], coverage['preview_lines'],
             coverage['configured_lines'], coverage['locked_lines'],
             coverage['unavailable_lines']) != (32, 1662, 544, 2176, 1984, 192, 0)):
        raise ValueError('Native mod frame catalog build or coverage conflict')
    frames = {row['frame_code']: row for row in packet['frames']}
    if len(frames) != 32:
        raise ValueError('Native mod frame identity conflict')
    identities = {}
    for row in packet['identities']:
        if row['item_no'] in identities or row['frame'] not in frames or \
                row['mod_code'] not in frames[row['frame']]['mod_codes']:
            raise ValueError('Native mod item/frame conflict')
        identities[row['item_no']] = row
    if len(identities) != 1662 or sum(not row['is_shiny_mod'] for row in identities.values()) != 831:
        raise ValueError('Native ordinary/Shiny identity count conflict')
    previews = {}
    configured = locked = 0
    for row in packet['frame_level_previews']:
        frame, level = row['frame_code'], row['total_level']
        key = (frame, level)
        if key in previews or frame not in frames or type(level) is not int or not 1 <= level <= 17 or \
                row['ordered_entry_levels'] != packet['level_vectors'][str(level)] or \
                len(row['ordered_lines']) != 4:
            raise ValueError('Native mod frame level/vector conflict')
        for position, line in enumerate(row['ordered_lines'], 1):
            entry = frames[frame]['ordered_entry_nos'][position - 1]
            entry_level = row['ordered_entry_levels'][position - 1]
            if (line['position'], line['entry_no'], line['entry_level']) != (position, entry, entry_level):
                raise ValueError('Native mod frame ordered entry conflict')
            if entry_level == 0:
                if line['state'] != 'locked':
                    raise ValueError('Native mod frame locked line conflict')
                locked += 1
                continue
            entry_key = f'{entry}:{entry_level}'
            source_entry = packet['entry_rows'].get(entry_key)
            if line['state'] != 'configured' or line['entry_key'] != entry_key or not source_entry or \
                    source_entry['kind'] != line['kind'] or not line.get('text'):
                raise ValueError('Native mod frame configured line conflict')
            if line['kind'] == 'direct_affix':
                value = line.get('configured_fraction')
                if (source_entry.get('affix_id') != line.get('affix_id') or
                        line.get('affix_id') not in packet['affix_prototypes'] or
                        type(value) not in (int, float) or not math.isfinite(value)):
                    raise ValueError('Native mod frame direct affix conflict')
            elif line['kind'] == 'buff_text':
                if (source_entry.get('buff_id') != line.get('buff_id') or
                        f"{line['buff_id']}:{entry_level}" not in packet['buff_level_rows']):
                    raise ValueError('Native mod frame buff row conflict')
            else:
                raise ValueError('Native mod frame line kind unavailable')
            configured += 1
        previews[key] = row
    if (len(previews), configured, locked) != (544, 1984, 192) or \
            set(previews) != {(frame, level) for frame in frames for level in range(1, 18)}:
        raise ValueError('Native mod frame level coverage conflict')
    return packet, identities, previews


@lru_cache(maxsize=None)
def exact_identity(catalog_id, *, shiny=False):
    """Return an exact secondary-item-ID join, never a name/suffix guess."""
    entry = catalog.ENTRIES.get(catalog_id)
    if not entry or entry.get('kind') != 'mod' or entry.get('family_only') or type(shiny) is not bool:
        return None
    _, identities, _ = _source()
    matches = []
    for record in entry.get('catalog_system_records') or []:
        if record['system'] != 'new' or record['is_shiny'] is not shiny:
            continue
        native = identities.get(int(record['item_id']))
        if native and native['is_shiny_mod'] is shiny:
            matches.append(native)
    # Two exact item/mod-code links were proved from the earlier native
    # two-frame packet, although the secondary catalog lacks their rows.
    if not matches:
        import native_mod_identity
        prior = native_mod_identity.TWO_FRAME_IDENTITIES.get(catalog_id)
        if prior:
            item_no, mod_code = (prior[3], prior[4]) if shiny else (prior[1], prior[2])
            native = identities.get(item_no)
            if not native or (native['mod_code'], native['frame'], native['is_shiny_mod']) != (
                    mod_code, prior[6], shiny):
                raise ValueError('Prior exact native mod identity/frame conflict: ' + catalog_id)
            matches.append(native)
    if len(matches) > 1:
        raise ValueError('Multiple native item IDs for one catalog identity/variant: ' + catalog_id)
    return copy.deepcopy(matches[0]) if matches else None


def preview(catalog_id, total_level, *, shiny=False):
    if type(total_level) is not int or not 1 <= total_level <= 17 or type(shiny) is not bool or \
            shiny and total_level != 17:
        raise ValueError('Native mod preview needs level 1–17; Shiny requires level 17')
    identity = exact_identity(catalog_id, shiny=shiny)
    if identity is None:
        return None
    _, _, previews = _source()
    row = copy.deepcopy(previews[(identity['frame'], total_level)])
    result = {'status': 'exact_native_catalog_configuration',
            'catalog_id': catalog_id, 'native_item_no': identity['item_no'],
            'native_mod_code': identity['mod_code'], 'native_frame_code': identity['frame'],
            'shiny': shiny, 'total_level': total_level,
            'ordered_entry_levels': row['ordered_entry_levels'],
            'ordered_lines': row['ordered_lines'],
            'source_build': '26267212', 'source_sha256': HASHES[PACKET.name],
            'owned_roll_inferred': False, 'core_rank_inferred': False,
            'server_buff_execution_proven': False, 'runtime_damage_included': False}
    import native_priority_mod_buff
    import native_mod_buff_batch2
    import native_mod_buff_review
    import native_mod_heal_chain
    return native_mod_heal_chain.annotate(native_mod_buff_review.annotate(
        native_mod_buff_batch2.annotate(native_priority_mod_buff.annotate(result))))


def _normalized(text):
    text = re.sub(r'\d+(?:\.\d+)?', ' ', str(text or '').lower())
    return re.sub(r'[^a-z]+', ' ', text).strip()


def _same_held_line(recorded, line):
    observed = recorded.get('raw_text') or recorded.get('name')
    if _normalized(observed) != _normalized(line['text']):
        return False
    values = re.findall(r'\d+(?:\.\d+)?', str(observed))
    native = re.findall(r'\d+(?:\.\d+)?', line['text'])
    if values:
        return len(values) == len(native) and all(
            abs(float(a) - float(b)) < 1e-6 for a, b in zip(values, native))
    amount = recorded.get('value_percent')
    return amount is None or bool(native and abs(float(amount) - float(native[0])) < 1e-6)


@lru_cache(maxsize=None)
def exact_record_conflicts(catalog_id, shiny=False):
    """Quarantine whole positions where a held exact card disagrees with this build."""
    identity = exact_identity(catalog_id, shiny=shiny)
    if identity is None:
        return {}
    levels = set(catalog.REVIEWED_LEVELS.get(catalog_id) or [])
    levels.update(int(x) for x in (catalog.NUMERIC['profiles'].get(catalog_id) or {}))
    conflicts = {}
    for level in levels:
        if shiny and level != 17:
            continue
        resolved = catalog.resolve(catalog_id, level, shiny=shiny)
        rows = resolved.get('known_attributes') or []
        native = preview(catalog_id, level, shiny=shiny)
        for index, recorded in enumerate(rows[:4]):
            if recorded.get('observed_level') != level or native['ordered_lines'][index]['state'] != 'configured':
                continue
            line = native['ordered_lines'][index]
            if not _same_held_line(recorded, line):
                conflicts.setdefault(index, []).append({'level': level,
                    'recorded_text': recorded.get('raw_text') or recorded.get('name'),
                    'native_text': line['text'], 'recorded_source': recorded.get('source')})
    return conflicts


def linked_coverage():
    ordinary = {entry['id'] for entry in catalog.DATA['mods']
                if exact_identity(entry['id']) is not None}
    shiny = {entry['id'] for entry in catalog.DATA['mods']
             if exact_identity(entry['id'], shiny=True) is not None}
    return {'catalog_mod_identities': len(catalog.DATA['mods']),
            'exact_ordinary_catalog_links': len(ordinary),
            'exact_shiny_catalog_links': len(shiny),
            'native_identity_rows': 1662, 'native_frame_level_previews': 544,
            'unlinked_catalog_ids': sorted({entry['id'] for entry in catalog.DATA['mods']} - ordinary)}
