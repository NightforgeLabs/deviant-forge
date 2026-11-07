"""Validate bounded native gun-base suffix evidence without assigning game semantics.

Source captures are copied into evidence_packets/native_raw. The public catalog
is used only to validate blueprint/gear identity and compare published labels;
it never chooses or changes the native byte parse.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct

import native_field_intake

ROOT = Path(__file__).parent / 'evidence_packets'
SAMPLE_PATH = ROOT / 'native-gun-suffix-sample-v1.json'
MANIFEST_PATH = ROOT / 'native-gun-capture-manifest-v1.json'
RAW = ROOT / 'native_raw'


def _uvar(data: bytes, at: int) -> tuple[int, int]:
    value = shift = 0
    for end in range(at, min(at + 6, len(data))):
        byte = data[end]
        value |= (byte & 127) << shift
        if byte < 128:
            return value, end + 1
        shift += 7
    raise ValueError('Native unsigned varint is incomplete')


def _names(data: bytes) -> tuple[list[str], int]:
    count = struct.unpack_from('<I', data)[0]
    if not 0 < count < 10000:
        raise ValueError('Native string count out of bounds')
    offsets = struct.unpack_from(f'<{count + 1}I', data, 4)
    if offsets[0] or any(a > b for a, b in zip(offsets, offsets[1:])):
        raise ValueError('Native string offsets are invalid')
    start = 4 + 4 * (count + 1)
    if start + offsets[-1] > len(data):
        raise ValueError('Native string pool crosses payload')
    return [data[start + offsets[i]:start + offsets[i + 1]].decode()
            for i in range(count)], start + offsets[-1]


def _decode_field(raw: bytes, type_code: int, names: list[str]):
    if type_code in (1, 5):
        value, end = _uvar(raw, 0)
        if end != len(raw):
            raise ValueError('Native field has trailing bytes')
        if type_code == 5:
            if value >= len(names):
                raise ValueError('Native string index out of bounds')
            return names[value]
        return value
    if type_code == 18 and len(raw) == 4:
        return struct.unpack('<f', raw)[0]
    if type_code == 34 and len(raw) == 8:
        return struct.unpack('<d', raw)[0]
    raise ValueError('Native field type or width conflict')


def validate_and_stage(sample: dict, manifest: dict, captures: dict[str, bytes],
                       named_rows: dict) -> dict:
    """Return a native-field packet, still quarantined from calculator inputs."""
    if (sample.get('schema_version') != 1 or
            sample.get('status') != 'eleven native fields decoded from bounded typed suffix' or
            sample.get('steam_build_id') != manifest.get('steam_build_id')):
        raise ValueError('Native suffix schema/build conflict')
    entries = {entry['entry_name'].split('\\')[-1].removesuffix('.pyc'): entry
               for entry in manifest.get('entries', [])}
    for key in ('gun_base_params_data', 'item_to_gun_mapping_data'):
        if (key not in entries or key not in captures or
                sample['source_literal_sha256'].get(key) != entries[key]['literal_sha256'] or
                hashlib.sha256(captures[key]).hexdigest() != entries[key]['literal_sha256']):
            raise ValueError(f'{key}: source capture hash conflict')
    base, mapping = captures['gun_base_params_data'], captures['item_to_gun_mapping_data']
    names, _ = _names(base)
    map_names, map_string_end = _names(mapping)
    if map_names != ['gun_no']:
        raise ValueError('Item-to-gun mapping schema conflict')
    descriptor_at = sample['descriptor_offset']
    count, after_count = _uvar(base, descriptor_at)
    if count != 144 or base[after_count] != 68:
        raise ValueError('Gun-base field descriptor changed')
    pairs_at = after_count + 1
    pairs = [(base[pairs_at + 2 * i], base[pairs_at + 2 * i + 1])
             for i in range(count)]
    expected = [(field['name_index'], field['type_code'])
                for field in sample['suffix_descriptor_pairs']]
    if pairs[-11:] != expected or any(names[i] != field['name']
                                       for (i, _), field in zip(expected,
                                           sample['suffix_descriptor_pairs'])):
        raise ValueError('Gun-base typed suffix descriptor conflict')
    if sample.get('aug_native_field_record') != sample['five_public_value_cross_checks'][0]:
        raise ValueError('AUG native record conflicts with five-item sample')
    records, identities, source_conflicts = [], set(), []
    for checked in sample['five_public_value_cross_checks']:
        blueprint, gear = str(checked['blueprint_id']), str(checked['gear_id'])
        identity = next((catalog_id for catalog_id, row in named_rows.items()
                         if row['blueprint_id'] == blueprint and
                         row['tiers']['1']['item_id'] == gear), None)
        if identity is None or identity in identities:
            raise ValueError('Native suffix identity conflicts with exact item pages')
        identities.add(identity)
        if checked.get('public_fire_rate') != named_rows[identity]['rpm_reference']:
            source_conflicts.append({'catalog_id':identity,
                'field':'published_fire_rate','native_sample_public_value':checked.get('public_fire_rate'),
                'held_page_value':named_rows[identity]['rpm_reference']})
        idx = checked['item_to_gun_index_offset']
        indexed_gear, idx_end = _uvar(mapping, idx)
        relative, _ = _uvar(mapping, idx_end)
        value_at = checked['item_to_gun_value_offset']
        if indexed_gear != int(gear) or map_string_end + relative != value_at or \
                mapping[value_at:value_at + 2] != b'\x96\x05':
            raise ValueError('Native item-to-gun index/value conflict')
        gun_no, _ = _uvar(mapping, value_at + 2)
        if gun_no != checked['gun_no']:
            raise ValueError('Native item-to-gun number conflict')
        field_names = set()
        for field in checked['typed_suffix_fields']:
            name = field['native_field']
            if name in field_names or name not in [item['name']
                                                     for item in sample['suffix_descriptor_pairs']]:
                raise ValueError('Native field duplicate or unknown descriptor')
            field_names.add(name)
            at, width = field['byte_offset'], field['byte_length']
            if not (checked['typed_suffix_start_offset'] <= at < at + width <=
                    checked['typed_suffix_end_offset_exclusive'] <=
                    checked['gun_row_end_offset_exclusive']):
                raise ValueError('Native field leaves typed suffix or row')
            raw = bytes.fromhex(field['raw_hex'])
            if len(raw) != width or base[at:at + width] != raw or \
                    _decode_field(raw, field['type_code'], names) != field['value']:
                raise ValueError('Native field raw bytes/value conflict')
            descriptor = next(item for item in sample['suffix_descriptor_pairs']
                              if item['name'] == name)
            if (field['name_index'], field['type_code']) != (
                    descriptor['name_index'], descriptor['type_code']):
                raise ValueError('Native field name/type conflict')
            records.append({'catalog_id': identity, 'blueprint_id': blueprint,
                            'gear_id': gear, 'gun_no': gun_no,
                            'native_field_identifier': name,
                            'byte_offset': at, 'raw_value': field['value'],
                            'raw_hex': field['raw_hex'], 'type_code': field['type_code'],
                            'unit_label': None,
                            'configuration_scope': 'gun_base_row; crafted effects unknown'})
    if identities != set(named_rows):
        raise ValueError('Native sample does not cover the five named identities')
    packet = {'schema_version': 1,
              'source': {'steam_build_id': sample['steam_build_id'],
                         'archive_entry': entries['gun_base_params_data']['entry_name'],
                         'payload_sha256': entries['gun_base_params_data']['literal_sha256']},
              'records': records}
    result = native_field_intake.inspect(packet)
    if result['counts']['accepted_fields']:
        raise ValueError('Native evidence was unexpectedly promoted to calculation')
    return {'schema_version': 1, 'source_packet': packet,
            'intake': result,
            'source_conflicts':source_conflicts,
            'scope': 'decoded_native_fields_evidence_only; no crafted or damage semantics'}


def load_current(named_rows: dict) -> dict:
    sample = json.loads(SAMPLE_PATH.read_text())
    manifest = json.loads(MANIFEST_PATH.read_text())
    captures = {name: (RAW / f'{name}.literal_bytes.bin').read_bytes()
                for name in ('gun_base_params_data', 'item_to_gun_mapping_data')}
    return validate_and_stage(sample, manifest, captures, named_rows)
