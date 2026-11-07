"""Exact native combat affix identity, never bucket selection from English alone."""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).with_name('evidence_packets')
HASHES = {
    'native-combat-english-labels-v1.md': '361cad1d9bf9d0a83b43deb4b08495f548e443395a6d3a9dae080aa7a3183bd1',
    'native-combat-english-labels-v1.json': '945da0f3c6935f32e05bac91f9177017058ca44880625cf7f9a1f7930b9a5084',
}
EXPECTED = {'D0102': ('D01', 'attack', 'Weapon DMG Bonus'),
            'E4200': ('E42', 'attack_type_dam_add_rate_remote', 'Weapon DMG Bonus'),
            'E4300': ('E43', 'attack_type_dam_add_rate_dot', 'Status DMG Bonus'),
            'E3400': ('E34', 'element_type_dam_add_rate_lightning', 'Shock DMG Bonus'),
            'E12100': ('E121', 'keyword_proc_dam_add_rate_surge', 'Power Surge DMG Bonus'),
            'G4400': ('G44', 'element_type_ignore_dam_rate_lightning', 'Shock DMG Reduction'),
            'G5300': ('G53', 'attack_type_ignore_dam_rate_dot', 'Status DMG Reduction')}


@lru_cache(maxsize=1)
def proof():
    for name, digest in HASHES.items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Native combat English label source hash conflict')
    packet = json.loads((ROOT / 'native-combat-english-labels-v1.json').read_text())
    if packet['build_id'] != '26267212' or packet['full_affix_scan']['rejected_rows']:
        raise ValueError('Native combat English label packet conflict')
    rows = packet['selected_affixes']
    for affix, (property_id, property_name, english) in EXPECTED.items():
        row = rows[affix]
        if (row['attr_id'] != property_id or row['native_property'] != property_name or
                row['name']['english'] != english):
            raise ValueError('Native combat English affix binding conflict: ' + affix)
    if (rows['D0102']['format']['english'] != rows['E4200']['format']['english'] or
            packet['full_affix_scan']['elemental_dmg_label_hits']):
        raise ValueError('Native combat English ambiguity control conflict')
    return {'build': '26267212', 'source_sha256': HASHES.copy(),
            'rows': rows, 'scope': 'installed native affix labels and property IDs, not active effects'}


def resolve(label=None, affix_id=None, source_build=None):
    """Return an exact typed property only with pinned native affix identity."""
    source = proof()
    rows = source['rows']
    if affix_id is None or source_build != source['build']:
        candidates = sorted(key for key, row in rows.items()
                            if label in (row['name']['english'],
                                         row['format']['english'].split(' +{', 1)[0]))
        return {'status': 'ambiguous_native_label' if len(candidates) > 1 else
                          'native_affix_id_and_build_required',
                'label': label, 'candidate_affix_ids': candidates,
                'property_id': None, 'native_property': None,
                'calculation_included': False}
    if affix_id not in rows:
        return {'status': 'unsupported_native_affix_id', 'affix_id': affix_id,
                'property_id': None, 'native_property': None,
                'calculation_included': False}
    row = rows[affix_id]
    accepted_labels = (row['name']['english'], row['format']['english'].split(' +{', 1)[0])
    if label is not None and label not in accepted_labels:
        return {'status': 'native_label_id_conflict', 'affix_id': affix_id,
                'label': label, 'expected_labels': accepted_labels,
                'property_id': None, 'native_property': None,
                'calculation_included': False}
    return {'status': 'exact_native_affix_property', 'affix_id': affix_id,
            'property_id': row['attr_id'], 'native_property': row['native_property'],
            'english_label': row['name']['english'],
            'english_format': row['format']['english'],
            'source_build': source['build'], 'source_sha256': source['source_sha256'],
            'active_on_selected_item': None, 'calculation_included': False}
