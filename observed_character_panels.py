"""Hash-checked, unlinked player panel observations; never selected-item stats."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PACKET = ROOT / 'evidence_packets/observed-character-panels-20261102-v1.json'
PACKET_SHA256 = '234bb37651461f063071925e37b9eb270bbcc80aa54b00671252969e41aa2afa'
BINDING = ROOT / 'evidence_packets/gear-panel-stat-bindings-v1.md'
BINDING_SHA256 = 'e4169d334d367d0f24c09965f6201f818858ccb5b09ace728b235f212f10cd41'
PREVIEW_TRACE = ROOT / 'evidence_packets/gear-selected-weapon-preview-trace-v1.md'
PREVIEW_TRACE_SHA256 = '02ac865138d8da8f44ecda0fae06bd15a7c65a0b746b2ef3f55894735138dcbc'
EXPECTED_IMAGES = {
    'overview': ('observed-character-panel-20261102-overview.png', 'c0a5071c5eb534ef3eb33f4d944e9197e68891f0fd1daf90475fbfdbaaffba23'),
    'expanded': ('observed-character-panel-20261102-expanded.png', 'b1447d8d38524720fd2f0191e460d2d528ebac9aa7d02536f5cc80a4b7efa3ec'),
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def observation() -> dict:
    if _sha(PACKET) != PACKET_SHA256:
        raise ValueError('Character-panel observation packet changed')
    if _sha(BINDING) != BINDING_SHA256:
        raise ValueError('Character-panel native binding trace changed')
    if _sha(PREVIEW_TRACE) != PREVIEW_TRACE_SHA256:
        raise ValueError('Character-panel selected-weapon preview trace changed')
    data = json.loads(PACKET.read_bytes())
    sources = data['sources']
    if (data['schema_version'] != 1 or len(sources) != 2 or
            data['calculation_included'] is not False or
            any(value is not None for value in data['identity'].values()) or
            data['observed']['primary_weapon_panel'] != {'attack': 422, 'fire_rate_display': 720, 'magazine_capacity': 58} or
            data['observed']['expanded_basic_stats']['attack'] != 20 or
            data['observed']['expanded_basic_stats']['psi_intensity'] != 793 or
            data['observed']['expanded_battle_stats'] != {'crit_rate_percent': 0.0, 'crit_damage_percent': 5.4, 'weakspot_damage_percent': 0.0}):
        raise ValueError('Character-panel scope or values changed')
    for source in sources:
        panel = source['panel']
        if panel not in EXPECTED_IMAGES:
            raise ValueError('Unknown character-panel source')
        basename, digest = EXPECTED_IMAGES[panel]
        path = ROOT / source['local_image']
        if (path != ROOT / 'static/artwork' / basename or source['sha256'] != digest or
                _sha(path) != digest):
            raise ValueError('Character-panel source image changed')
        source['image_url'] = '/artwork/' + basename
    data['native_display_bindings'] = {
        'installed_build_id': '26267212',
        'source_sha256': BINDING_SHA256,
        'primary_weapon_attack': 'holder_attack_if_same_weapon_else_selected_weapon_replacement_preview',
        'primary_weapon_rpm': 'weapon_context_with_rate_adjustment_if_same_weapon',
        'basic_attack': 'current_holder_D01_attack',
        'crit_rate': 'current_holder_E01_rate',
        'crit_damage': 'current_holder_E02_rate',
        'weakspot_damage': 'current_holder_E03_rate',
        'selected_vs_held_weapon_branch': 'unknown_in_uploaded_images',
        'replacement_preview_source_sha256': PREVIEW_TRACE_SHA256,
        'replacement_preview_scope': 'holder_changes_minus_held_weapon_plus_selected_weapon_affixes_then_property_recalculation; nonzero_holder_value_may_precede_preview_in_one_branch',
        'basic_attack_is_free_addition_to_weapon_attack': False,
        'server_holder_or_final_damage_established': False,
    }
    return data
