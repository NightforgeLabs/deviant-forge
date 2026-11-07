"""Deterministic field-level intake for blueprint-linked Tier I weapon pages.

The raw transcription remains the archive. Only fields with an explicit unit and
calculation binding enter the active timing model. This module has no write path
to personal records or the source archive.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


FIELD_BINDINGS = {
    'Fire Rate': ('fire_rate_rpm', 'rounds_per_minute', 'shot_scheduler.fire_rate'),
    'Magazine Capacity': ('magazine_capacity', 'rounds', 'finite_ammo.magazine_capacity'),
}
UNBOUND_REASONS = {
    'DMG': 'Displayed DMG unit is not established as damage per projectile or current Attack',
    'Reload Speed': 'Reload Speed is a score; no sourced conversion to seconds',
}
BLUEPRINT_TITLE_EXCEPTIONS = {
    'weapon:qbj97-fiery-trees-and-silver-flowers':
        'QBJ97 - Fiery Trees and Silver Flowers B.P.',
}


def _positive_integer(value, label, limit):
    if not isinstance(value, str) or not value.isdecimal():
        raise ValueError(f'{label}: expected source-native integer text')
    parsed = int(value)
    if not 0 < parsed <= limit:
        raise ValueError(f'{label}: out of supported timing range')
    return parsed


def _local_identity_map(packet: dict | None, named_rows: dict) -> dict:
    if packet is None:
        return {}
    source = packet.get('source') or {}
    if (packet.get('schema_version') != 1 or
            packet.get('status') != 'bounded_identity_mapping_decoded; remaining row fields undecoded' or
            source.get('archive_entry') != 'game_common\\data\\gun_blueprint_data.pyc' or
            len(source.get('sha256', '')) != 64 or not source.get('steam_build_id')):
        raise ValueError('Local identity evidence lacks bounded archive provenance')
    entries = [packet['first_decoded_identity'], *packet['other_public_identity_cross_checks']]
    by_pair = {}
    for entry in entries:
        pair = (str(entry['blueprint_id']), str(entry['gear_id']))
        if pair in by_pair or not isinstance(entry.get('mapping_pair_absolute_offset'), int):
            raise ValueError('Duplicate or unlocated local blueprint/gear pair')
        by_pair[pair] = {'status': 'identity_only',
                         'archive_entry': source['archive_entry'],
                         'archive_sha256': source['sha256'],
                         'steam_build_id': source['steam_build_id'],
                         'mapping_pair_absolute_offset': entry['mapping_pair_absolute_offset']}
    expected = {(row['blueprint_id'], row['tiers']['1']['item_id'])
                for row in named_rows.values()}
    if set(by_pair) != expected:
        raise ValueError('Local blueprint/gear identity conflicts with raw public batch')
    return by_pair


def intake_tier1(batch: dict, named_rows: dict, *, archive_sha256: str | None = None,
                 local_identity: dict | None = None) -> dict:
    """Validate exact identity and field bindings, returning an auditable report.

    A mismatch rejects the whole import. No partial timing record is emitted for
    a conflicting source. Repeated runs with the same input are byte-stable.
    """
    if batch.get('schema_version') != 1 or not isinstance(batch.get('rows'), list):
        raise ValueError('Unsupported raw source schema')
    if not batch.get('capture_date_utc') or not batch.get('capture_method'):
        raise ValueError('Missing source capture provenance')
    archive_sha256 = archive_sha256 or hashlib.sha256(
        json.dumps(batch, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    accepted, conditional, rejected = [], [], []
    local_pairs = _local_identity_map(local_identity, named_rows)
    seen = set()
    for source in sorted(batch['rows'], key=lambda row: row['catalog_id']):
        identity = source['catalog_id']
        if identity in seen or identity not in named_rows:
            raise ValueError(f'{identity}: duplicate or unknown catalog identity')
        seen.add(identity)
        named = named_rows[identity]
        item = named['tiers']['1']
        if (source.get('tier') != 1 or source.get('blueprint_id') != named['blueprint_id'] or
                source.get('blueprint_url') != named['blueprint_url'] or
                source.get('gear_id') != item['item_id'] or
                source.get('gear_title') != item['page_title'] or
                source.get('gear_url') != item['thgl_gear_url'] or
                source.get('raw_star_table_label') != 'DMG per star'):
            raise ValueError(f'{identity}: blueprint/gear/tier/source identity conflict')
        if source.get('blueprint_title') != BLUEPRINT_TITLE_EXCEPTIONS.get(
                identity, named['blueprint_title']):
            raise ValueError(f'{identity}: blueprint title conflict')
        if source.get('raw_star_damage') != {
                f'{star}★': str(value) for star, value in item['star_damage'].items()}:
            raise ValueError(f'{identity}: source star-cell conflict')
        fields = source.get('raw_fields')
        if not isinstance(fields, dict) or set(FIELD_BINDINGS) - fields.keys():
            raise ValueError(f'{identity}: missing source timing fields')
        if fields.get('DMG') != str(item['damage']):
            raise ValueError(f'{identity}: displayed DMG source conflict')
        if fields.get('Fire Rate') != str(named['rpm_reference']) or \
                fields.get('Magazine Capacity') != str(named['magazine_reference']):
            raise ValueError(f'{identity}: timing source conflict')
        secondary = source.get('secondary_source') or {}
        secondary_fields = secondary.get('raw_fields') or {}
        if (secondary.get('raw_title') != source['gear_title'] or
                not secondary.get('url', '').rstrip('/').endswith('/'+source['gear_id']) or
                secondary_fields.get('Magazine Size') != fields['Magazine Capacity'] or
                secondary_fields.get('Fire Rate (RPM)', secondary_fields.get('Fire Rate'))
                != fields['Fire Rate']):
            raise ValueError(f'{identity}: secondary timing source conflict')
        source_ref = {'catalog_id': identity, 'blueprint_id': source['blueprint_id'],
                      'gear_id': source['gear_id'], 'tier': 1,
                      'source_url': source['gear_url'],
                      'source_title': source['gear_title'],
                      'capture_date_utc': batch['capture_date_utc'],
                      'game_build': batch.get('game_build'),
                      'raw_archive_sha256': archive_sha256,
                      'local_identity': local_pairs.get((source['blueprint_id'],
                                                         source['gear_id']))}
        for label in sorted(fields):
            raw = fields[label]
            if label in FIELD_BINDINGS:
                field, unit, binding = FIELD_BINDINGS[label]
                value = _positive_integer(raw, label, 3000 if label == 'Fire Rate' else 1000)
                record = {**source_ref, 'source_label': label,
                          'raw_value': raw, 'field': field, 'value': value,
                          'unit': unit, 'calculation_binding': binding,
                          'unit_evidence': ('explicit_secondary_rpm_label'
                              if label == 'Fire Rate' and 'Fire Rate (RPM)' in secondary_fields
                              else 'published_reference_rpm_interpretation'
                              if label == 'Fire Rate' else 'matching_magazine_labels'),
                          'corroborating_source_url': secondary['url']}
                if record['unit_evidence'] == 'published_reference_rpm_interpretation':
                    record['required_hypothesis'] = 'assume_fire_rate_as_rpm'
                    conditional.append(record)
                else:
                    accepted.append(record)
            else:
                rejected.append({**source_ref, 'source_label': label,
                                 'raw_value': raw,
                                 'reason': UNBOUND_REASONS.get(label,
                                     'No typed calculation binding for this source field')})
        for star, raw in sorted(source['raw_star_damage'].items()):
            rejected.append({**source_ref, 'source_label': f'DMG per star {star}',
                             'raw_value': raw,
                             'reason': UNBOUND_REASONS['DMG']})
    if seen != set(named_rows):
        raise ValueError('Raw batch does not cover all named Tier I identities')
    return {'schema_version': 1, 'source_archive_sha256': archive_sha256,
            'accepted': accepted, 'conditional': conditional, 'rejected': rejected,
            'counts': {'identities': len(seen), 'accepted_fields': len(accepted),
                       'accepted_explicit_rpm_labels': sum(row['unit_evidence'] ==
                           'explicit_secondary_rpm_label' for row in accepted),
                       'conditional_fields': len(conditional),
                       'rejected_fields': len(rejected)}}


def write_report(raw_path: Path, named_rows: dict, output_path: Path,
                 *, local_identity_path: Path | None = None) -> dict:
    raw = raw_path.read_bytes()
    report = intake_tier1(json.loads(raw), named_rows,
                          archive_sha256=hashlib.sha256(raw).hexdigest(),
                          local_identity=json.loads(local_identity_path.read_bytes())
                          if local_identity_path else None)
    payload = json.dumps(report, indent=2, ensure_ascii=False) + '\n'
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic replacement keeps the prior valid report if writing fails.
    temporary = output_path.with_name(output_path.name + '.tmp')
    temporary.write_text(payload)
    temporary.replace(output_path)
    return report
