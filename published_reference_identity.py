"""Source-scoped published reference aliases, separate from catalog/user data."""
from __future__ import annotations

import json
from pathlib import Path


PACKET = json.loads((Path(__file__).parent / 'evidence_packets' /
                     'published-reference-identity-v1.json').read_text())
WEAPON_ALIASES = PACKET['weapon_aliases']
ARMOR_RARITY = PACKET['armor_reference_rarity']


def weapon_binding(catalog_id):
    row = WEAPON_ALIASES.get(catalog_id)
    return (row['canonical_catalog_id'] if row else catalog_id), row


def armor_binding(catalog_id, catalog_rarity):
    row = ARMOR_RARITY.get(catalog_id)
    return row['rarity'] if row else catalog_rarity, row
