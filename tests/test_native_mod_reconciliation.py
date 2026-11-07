"""Exact current mod ID joins; identity evidence does not imply ownership or math."""
import hashlib
import json
from pathlib import Path
import unittest

import catalog
import native_mod_choice_english
import native_mod_identity


ROOT = Path(catalog.__file__).parent
PACKETS = ROOT / 'evidence_packets'
FAMILIES = {'Precision Load': ('pants_mod', 9321),
            'Turret Enhancement': ('gloves_mod', 9524)}


class NativeModReconciliationTests(unittest.TestCase):
    def test_exact_gear_ids_join_each_suffix_and_variant_without_ownership(self):
        rows = json.loads((PACKETS / 'native-missing-gear-mod-ids-v1.json').read_text())['rows']
        self.assertEqual(len(rows), 44)
        self.assertEqual(len({row['item_id'] for row in rows}), 44)
        systems_ids = [row['item_id'] for row in catalog.SYSTEMS['records']]
        self.assertEqual(len(systems_ids), len(set(systems_ids)))
        for family, (slot, main_entry) in FAMILIES.items():
            entries = [entry for entry in catalog.DATA['mods'] if entry['name'] == family]
            self.assertEqual(len(entries), 11)
            for entry in entries:
                self.assertEqual(entry['slot'], slot)
                self.assertEqual(entry['system_generation'], 'current_field_guide')
                links = entry['catalog_system_records']
                self.assertEqual(len(links), 2)
                self.assertEqual({x['is_shiny'] for x in links}, {False, True})
                native = native_mod_identity.for_catalog(entry['id'])
                self.assertEqual(native['native_family']['native_main_entry_no'], main_entry)
                self.assertEqual({native['normal']['item_id'], native['shiny']['item_id']},
                                 {x['item_id'] for x in links})
                self.assertFalse(native['calculation_included'])
                self.assertNotIn('ownership', entry)

    def test_weapon_slot_alias_joins_existing_ids_without_new_records(self):
        entries = [entry for entry in catalog.DATA['mods'] if entry['slot'] == 'weapon_mod']
        self.assertEqual(len(entries), 230)
        self.assertEqual(sum(bool(entry['catalog_system_records']) for entry in entries), 217)
        current = [row for entry in entries for row in entry['catalog_system_records']
                   if row['system'] == 'new']
        legacy = [row for entry in entries for row in entry['catalog_system_records']
                  if row['system'] == 'legacy']
        self.assertEqual((len(current), len(legacy)), (368, 45))
        self.assertEqual(len({row['item_id'] for row in current}), 368)
        self.assertEqual(catalog.SLOTS['All Weapons'], 'weapon_mod')

    def test_all_native_choice_options_now_link_exact_ids(self):
        choices = native_mod_choice_english.load()
        options = [option for row in choices.values() for option in row['options']]
        self.assertEqual(len(options), 5760)
        self.assertTrue(all(option['catalog_systems_id'] for option in options))
        for item in (19500824, 19500825):
            matching = [option for option in options if option['native_item_id'] == item]
            self.assertTrue(matching)
            self.assertTrue(all(option['canonical_catalog_id'] for option in matching))

    def test_source_packet_hashes_and_original_art_are_preserved(self):
        packet = json.loads((PACKETS / 'native-missing-gear-mod-ids-v1.json').read_text())
        for name, expected in packet['source_sha256'].items():
            source = (Path('~/Documents/Codex/2026-11-02/task') / name
                      if name == 'native_mod_property_records.json' else
                      Path('~/Documents/Codex/2026-11-02/task-5') / name)
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), expected)
        for family, slot in (('precision-load', 'pants_mod'),
                             ('turret-enhancement', 'gloves_mod')):
            art = ROOT / 'static' / 'artwork' / f'family__{slot}__{family}.png'
            self.assertTrue(art.is_file())


if __name__ == '__main__':
    unittest.main()
