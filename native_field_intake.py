"""Quarantined intake contract for future source-native game-data fields.

Reading a native number does not establish its unit, game effect, or calculator
handler. This adapter defaults to zero active bindings. The acquisition lane may
submit records without modifying game files or this application's active data.
"""
from __future__ import annotations

import re

_HEX64 = re.compile(r'^[0-9a-f]{64}$')


def inspect(packet: dict, *, bindings: dict | None = None) -> dict:
    """Preserve located raw fields and admit only exact, typed approved bindings.

    Binding keys are (steam_build_id, archive_entry, native_field_identifier).
    A binding must name a source-native unit, an implemented calculator path,
    exact blueprint/gear pairs and a configuration scope.
    No binding is shipped until a field has independent semantic evidence.
    """
    if not isinstance(packet, dict) or packet.get('schema_version') != 1:
        raise ValueError('Unsupported native-field packet schema')
    src = packet.get('source') or {}
    build = str(src.get('steam_build_id') or '')
    archive = src.get('archive_entry')
    digest = src.get('payload_sha256')
    if (not build.isdecimal() or not archive or not isinstance(archive, str) or
            not isinstance(digest, str) or not _HEX64.fullmatch(digest)):
        raise ValueError('Native field lacks build, archive entry or payload hash')
    if not isinstance(packet.get('records'), list):
        raise ValueError('Native field records must be a list')
    bindings = bindings or {}
    accepted, withheld = [], []
    seen = set()
    for record in packet['records']:
        if not isinstance(record, dict):
            raise ValueError('Native field record must be an object')
        field_id = record.get('native_field_identifier')
        offset = record.get('byte_offset')
        if (not isinstance(field_id, str) or not field_id or
                not isinstance(offset, int) or isinstance(offset, bool) or offset < 0 or
                'raw_value' not in record):
            raise ValueError('Native field needs identifier, raw value and byte offset')
        location = (field_id, offset)
        if location in seen:
            raise ValueError('Duplicate native field location')
        seen.add(location)
        provenance = {'steam_build_id': build, 'archive_entry': archive,
                      'payload_sha256': digest, 'native_field_identifier': field_id,
                      'byte_offset': offset, 'raw_value': record['raw_value'],
                      'blueprint_id': record.get('blueprint_id'),
                      'gear_id': record.get('gear_id'),
                      'configuration_scope': record.get('configuration_scope')}
        binding = bindings.get((build, archive, field_id))
        if binding is None:
            withheld.append({**provenance, 'reason':
                'Native field unit and calculator binding have not been established'})
            continue
        if (not isinstance(binding, dict) or not binding.get('unit') or
                not binding.get('calculation_binding') or not binding.get('field') or
                binding.get('unit') != record.get('unit_label')):
            raise ValueError(f'{field_id}: approved binding or source unit conflict')
        if record.get('blueprint_id') is None or record.get('gear_id') is None:
            raise ValueError(f'{field_id}: active numeric binding requires exact item identity')
        pairs = binding.get('allowed_blueprint_gear_pairs')
        if (not isinstance(pairs, list) or not pairs or
                not all(isinstance(pair, list) and len(pair) == 2 for pair in pairs)):
            raise ValueError(f'{field_id}: approved binding lacks exact item scope')
        if [str(record['blueprint_id']), str(record['gear_id'])] not in [
                [str(value) for value in pair] for pair in pairs]:
            raise ValueError(f'{field_id}: source identity outside approved item scope')
        if not binding.get('configuration_scope') or \
                binding['configuration_scope'] != record.get('configuration_scope'):
            raise ValueError(f'{field_id}: configuration scope conflict')
        accepted.append({**provenance, 'field': binding['field'],
                         'unit': binding['unit'],
                         'calculation_binding': binding['calculation_binding']})
    return {'schema_version': 1, 'accepted': accepted, 'withheld': withheld,
            'counts': {'source_records': len(packet['records']),
                       'accepted_fields': len(accepted),
                       'withheld_fields': len(withheld)}}
