#!/usr/bin/env python3
"""Export source-checked Field Guide tooltip evidence without copying ownership.

Only exact variant, level and recording patch-context observations whose frame
hashes pass field_guide_profiles verification are exported. This reads the
database and media; it never writes them or changes profile progress.
"""
import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import field_guide_profiles as guide  # noqa: E402


def export(database):
    c = sqlite3.connect(f'file:{Path(database).resolve()}?mode=ro', uri=True)
    c.row_factory = sqlite3.Row
    try:
        keys = set()
        for row in c.execute("SELECT data FROM video_import_proposals WHERE status!='dismissed'"):
            data = json.loads(row['data'])
            if (isinstance(data.get('level'), int) and data.get('catalog_id') and
                    (data.get('source_audit') or {}).get('status', '').startswith('source_text_and_numbers_checked')):
                keys.add((data['catalog_id'], data['level'], data.get('shiny_status', 'unknown')))
        entries = {}
        conflicts = []
        for identity, level, shiny in sorted(keys):
            observed = guide._reviewed_exact_rows(c, identity, level, shiny)
            if not observed:
                continue
            if observed.get('conflict'):
                conflicts.append({'catalog_id': identity, 'level': level, 'shiny_status': shiny,
                                  'reason': observed['conflict']})
                continue
            frame = observed['source_frame']
            path = Path(database).resolve().parent / frame
            if not path.is_file():
                raise ValueError(f'Source frame disappeared: {frame}')
            source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            entries[f'{identity}:{level}:{shiny}'] = {
                'catalog_id': identity, 'level': level, 'shiny_status': shiny,
                'attributes': observed['known_attributes'],
                'main_effect_raw': observed['main_effect_raw'],
                'source_frame': frame, 'source_sha256': source_hash,
                'evidence_context': observed['evidence_context'],
                'recorded_at': observed['recorded_at'],
                'proposal_ids': observed['proposal_ids'],
                'evidence_status': 'source_text_and_numbers_checked; exact current Field Guide variant and level',
            }
        return {'schema_version': 1, 'entries': entries, 'conflicts': conflicts,
                'scope': 'catalog evidence only; no ownership, current equip or Tech activation inferred'}
    finally:
        c.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', required=True)
    parser.add_argument('--output', default=str(ROOT / 'catalog_reviewed_profiles.json'))
    args = parser.parse_args()
    result = export(args.database)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(f"Exported {len(result['entries'])} exact profiles; {len(result['conflicts'])} conflicts held")
