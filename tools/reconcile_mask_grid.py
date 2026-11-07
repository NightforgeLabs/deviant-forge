#!/usr/bin/env python3
"""Reconcile reviewed 2026-10-25 Mask grid levels into the personal Field Guide.

The grid proves numbered unlocks and dated padlocks, but no tooltip rolls.
Never changes physical inventory, saved builds, or later manual level edits.
"""
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('~/Projects/once-human-advisor')
sys.path.insert(0, str(ROOT))
import catalog
import field_guide_profiles as guide

MANIFEST = Path(__file__).with_name('mask_grid_evidence.json')
DB = ROOT / 'data/advisor.sqlite3'
FRAME_DIR = ROOT / 'data/media/evidence/mask-grid-20261025'

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda: f.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()

def run():
    manifest = json.loads(MANIFEST.read_text())
    video = Path(manifest['source_video'])
    if digest(video) != manifest['source_sha256']:
        raise ValueError('Original source recording hash changed')
    by_pair = {}
    for entry in catalog.ENTRIES.values():
        if entry.get('kind') == 'mod' and entry.get('slot') == 'mask_mod' and entry.get('variant'):
            by_pair.setdefault((entry['name'], entry['variant']), []).append(entry)
    reviewed = []
    for family, seconds, variants, levels in manifest['rows']:
        if len(variants) != len(levels):
            raise ValueError(f'Card count mismatch: {family}')
        frame = FRAME_DIR / f'{seconds}.png'
        if not frame.is_file():
            raise ValueError(f'Missing reviewed frame: {frame}')
        frame_hash = digest(frame)
        for variant, level in zip(variants, levels):
            matches = by_pair.get((family, variant), [])
            if len(matches) != 1:
                raise ValueError(f'Ambiguous catalog identity: {family} <{variant}>')
            entry = matches[0]
            if level is not None:
                guide._identity('personal', entry['id'])
                guide._level(level, 'unknown')
            reviewed.append((entry, level, seconds, frame_hash))
    if len(reviewed) != 92 or sum(level is not None for _, level, _, _ in reviewed) != 54:
        raise ValueError('Mask grid coverage is incomplete')
    stamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    inserted = []
    conflicts = []
    try:
        c.execute('BEGIN IMMEDIATE')
        inventory = {}
        for item in c.execute("SELECT id,level,stats,effects FROM inventory WHERE kind='mod_unlock' AND archived=0"):
            identity = json.loads(item['effects'] or '{}').get('catalog_id')
            if identity:
                inventory.setdefault(identity, []).append(item)
        for entry, level, seconds, frame_hash in reviewed:
            if level is None:
                continue  # Dated lock evidence stays in the manifest and UI source ledger.
            identity = entry['id']
            existing = c.execute('SELECT * FROM field_guide_levels WHERE profile_id=? AND catalog_id=?',
                                 ('personal', identity)).fetchone()
            manual = [item for item in inventory.get(identity, [])
                      if json.loads(item['stats'] or '{}').get('manual_level_override')]
            if manual or existing:
                conflicts.append({'catalog_id': identity, 'video_level': level,
                                  'reason': 'later manual inventory level' if manual else 'existing profile level',
                                  'current_level': manual[0]['level'] if manual else existing['level']})
                continue
            source = json.dumps({
                'video': str(video), 'sha256': manifest['source_sha256'],
                'timestamp_seconds': seconds,
                'frame': str(FRAME_DIR / f'{seconds}.png'), 'frame_sha256': frame_hash,
                'cue': 'numbered card in account Field Guide Mask grid',
                'attributes': 'not inspected', 'tech_activation': 'unknown'
            }, sort_keys=True)
            next_row = {'profile_id': 'personal', 'catalog_id': identity, 'level': level,
                        'shiny_status': 'unknown', 'source_kind': 'reviewed_video_grid',
                        'source_ref': source, 'updated': stamp}
            c.execute('INSERT INTO field_guide_levels VALUES(?,?,?,?,?,?,?)',
                      ('personal', identity, level, 'unknown', 'reviewed_video_grid', source, stamp))
            c.execute('INSERT INTO field_guide_level_events(profile_id,catalog_id,prior,next,source_kind,created) VALUES(?,?,?,?,?,?)',
                      ('personal', identity, None, json.dumps(next_row), 'reviewed_video_grid', stamp))
            inserted.append(identity)
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()
    print(json.dumps({'source_positions': 92, 'video_numbered': 54, 'video_locked': 38,
                      'profile_levels_added': len(inserted), 'conflicts_preserved': conflicts,
                      'inventory_unchanged': True}, indent=2))

if __name__ == '__main__':
    run()
