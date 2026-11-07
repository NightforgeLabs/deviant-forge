"""One observed AUG blueprint preview, scoped to its exact tier/star cell."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parent
SOURCE_ROOT = Path(__file__).resolve().parent
PACKET = ROOT / 'evidence_packets/aug-blueprint-preview-frame-v1.json'
PACKET_SHA256 = '2be9cd2e917fbfccdd1b67a57c7f7e23aba769d42030896c9e38f3c2d6b315f5'


def load_current(native_aug):
    raw = PACKET.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PACKET_SHA256:
        raise ValueError('AUG blueprint preview evidence packet changed')
    packet = json.loads(raw)
    frame = packet['source']['frame_path_read_only']
    # The frame is the original player's recording; other installs (shared zips) don't have it.
    have_frame = Path(frame).is_file()
    if have_frame and hashlib.sha256(Path(frame).read_bytes()).hexdigest() != packet['source']['frame_sha256']:
        raise ValueError('AUG source frame hash changed')
    facts = packet['visible_frame_facts']
    if (facts['blueprint_id_via_exact_native_public_crosswalk'] != 13451401 or
            native_aug['blueprint_id'] != 13451401 or
            facts['tier_number'] != 5 or facts['star_number'] != 4 or
            facts['raw_stat_label'] != 'DMG' or facts['raw_stat_value'] != 231 or
            [(r['raw_label'], r['raw_value']) for r in facts['controls']] !=
            [('Fire Rate', 720), ('MAG', 40)] or
            facts['crafted_or_equipped_weapon_tooltip_visible'] or
            packet['native_comparison']['tier_five']['gun_preset_attack']['value'] !=
            native_aug['tiers'][5]['gun_preset_attack'] or
            packet['native_comparison']['four_star']['value'] !=
            native_aug['stars'][4]['preset_attack_radio']):
        raise ValueError('AUG preview source/configuration conflict')
    return {'catalog_id': 'weapon:aug-electron-cloud', 'blueprint_id': 13451401,
        'tier': 5, 'stars': 4, 'context': 'blueprint_preview',
        'raw_stats': {'DMG': 231, 'Fire Rate': 720, 'MAG': 40},
        'frame_url': '/' + str(Path(frame).relative_to(SOURCE_ROOT / 'data')) if have_frame else None,
        'frame_sha256': packet['source']['frame_sha256'],
        'recorded_video_sha256': packet['source']['video_sha256'],
        'recording_capture_build': packet['source']['recording_capture_build'],
        'calculation_included': False,
        'scope': 'Observed weapon blueprint preview only; no equipped weapon, calibration, crafted Attack, or final damage verified.'}


def selected(preview, catalog_id, tier, stars):
    if catalog_id == preview['catalog_id'] and tier == preview['tier'] and stars == preview['stars']:
        return dict(preview)
    return None
