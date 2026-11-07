"""Raw native category rows must not become named recommendations."""
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import aid_catalog


FIXTURE = Path(__file__).with_name('fixtures') / 'native_category_real_sample.json'


class AidCatalogTest(unittest.TestCase):
    def tearDown(self):
        aid_catalog.load.cache_clear()

    def packet(self, value):
        aid_catalog.load.cache_clear()
        with TemporaryDirectory() as temp:
            path = Path(temp) / 'aid.json'
            path.write_text(json.dumps(value))
            shutil.copy2(aid_catalog.PACKET.parent / 'native_named_pal_crate_sample.json',
                         path.parent / 'native_named_pal_crate_sample.json')
            shutil.copy2(aid_catalog.PACKET.parent / 'native_named_food_whim_samples.json',
                         path.parent / 'native_named_food_whim_samples.json')
            with patch.object(aid_catalog, 'PACKET', path):
                return aid_catalog.overview()

    def test_live_packet_has_source_named_membership_only_crates(self):
        result = aid_catalog.overview()
        self.assertEqual(result['status'], 'reviewed_named_items')
        self.assertEqual([row['id'] for row in result['categories']],
                         [*aid_catalog.KINDS, 'choice_containers', 'armor_previews'])
        self.assertEqual([row['ready_count'] for row in result['categories']],
                         [501, 12, 55, 0, 579, 1018])
        food = result['categories'][0]['ready_items'][0]
        whim = result['categories'][1]['ready_items'][0]
        self.assertEqual((food['name'], whim['name']), ('Gingerdrop', 'Utter Delight'))
        added = result['categories'][0]['ready_items'][1:12]
        self.assertEqual(len(added), 11)
        self.assertTrue(all(row['calculation_status'] == 'display_only' and
                            row['native_buff_nominal_seconds'] > 0 for row in added))
        self.assertTrue(all('腐败' not in row['effect_text'] for row in added),
                        'spoilage wording is never mistaken for a buff effect')
        source_only = result['categories'][0]['ready_items'][12:]
        self.assertEqual(489, len(source_only))
        self.assertTrue(all(row['calculation_status'] == 'display_only' and
                            row['typed_named_source_sha256'] and
                            row['availability'] == 'unknown' for row in source_only))
        self.assertEqual(12, len(result['categories'][1]['ready_items']))
        mint = next(row for row in added if 'Canned Minty Meat' in row['name'])
        self.assertTrue(mint['unresolved_secondary_buff_lifetime'])
        self.assertEqual((food['native_buff_nominal_seconds'], whim['native_buff_nominal_seconds']),
                         (1800, 7200))
        self.assertEqual(food['native_buff_duration_scope'],
                         'default_before_modifiers_not_applied_expiry')
        self.assertFalse(food['effect_description_only'])
        self.assertTrue(whim['effect_description_only'])
        self.assertTrue(all(row['calculation_status'] == 'display_only' for row in (food, whim)))
        crate = result['categories'][2]['ready_items'][0]
        self.assertEqual(crate['catalog_id'], 'aid:crate:37560018')
        self.assertEqual(crate['draw_mode'], 'unknown')
        self.assertTrue(crate['reward_membership_only'])
        self.assertEqual(len(crate['rewards']), 21)
        self.assertEqual(sum(row['pool_role'] == 'normal' for row in crate['rewards']), 18)
        self.assertEqual(sum(row['pool_role'] == 'rare' for row in crate['rewards']), 3)
        self.assertEqual(crate['availability'], 'current_obtainability_unknown')
        self.assertEqual(crate['source_guarantee']['max_opens'], 15)
        self.assertIn('reset rule', crate['source_guarantee']['unknown'])
        other_crates = result['categories'][2]['ready_items'][1:]
        self.assertEqual(len(other_crates), 54)
        self.assertTrue(all(row['reward_membership_only'] and
                            row['draw_mode'] == 'unknown' and
                            row['source_guarantee'] is None
                            for row in other_crates))
        self.assertEqual(result['formula_ready_items'], 0)
        self.assertFalse(result['crate_probabilities_calculated'])
        self.assertFalse(result['ownership_implied'])
        choices=result['categories'][4]['ready_items']
        self.assertEqual(5760, sum(row['option_count'] for row in choices))
        self.assertEqual(468, sum(row['mapped_option_count'] for row in choices))
        self.assertEqual(5760, sum(row['catalog_systems_option_count'] for row in choices))
        self.assertTrue(all(row['draw_mode']=='selectable_list_not_random_pool'
                            for row in choices))
        armor = result['categories'][5]['ready_items']
        self.assertEqual(4828, sum(len(row['star_previews']) for row in armor))
        self.assertTrue(all(row['equipped_hp_or_psi'] is None for row in armor))
        cake = next(row for row in result['categories'][0]['ready_items']
                    if row['name'] == 'Heavy Strike Azure Cake')
        self.assertEqual(0.1, cake['raw_bonus_evidence']['raw_attributes'][0]['raw_value'])
        self.assertEqual('unverified', cake['raw_bonus_evidence']['raw_attributes'][0]['application'])

    def test_nominal_duration_source_hash_is_required(self):
        aid_catalog._nominal_food_seconds.cache_clear()
        with TemporaryDirectory() as temp:
            bad = Path(temp) / 'food.json'
            bad.write_text('{}')
            with patch.object(aid_catalog, 'FOOD_BOUND', bad):
                with self.assertRaisesRegex(ValueError, 'hash conflict'):
                    aid_catalog._nominal_food_seconds()
        aid_catalog._nominal_food_seconds.cache_clear()

    def test_real_raw_rows_cannot_be_promoted_by_id_or_unreviewed_name(self):
        samples = json.loads(FIXTURE.read_text())['samples']
        packet = json.loads(aid_catalog.PACKET.read_text())
        for kind, source in (('food_drink', samples['food']),
                             ('crates', samples['crate']),
                             ('enemy_hp', samples['enemy'])):
            self.assertEqual(len(source['sha256']), 64)
            row = source['raw_record']
            packet['records'] = [{'category': kind,
                                  'catalog_id': 'aid:' + str(row.get('item_id', row.get('drop_id', row.get('index_key')))),
                                  'name': str(row.get('item_id', row.get('drop_id', row.get('index_key')))),
                                  'summary': 'Raw source ID', 'calculation_status': 'display_only'}]
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, 'Unreviewed|source and exact join'):
                self.packet(packet)
        self.assertEqual(aid_catalog.overview()['categories'][2]['ready_count'], 55)

    def test_reviewed_flag_does_not_skip_effect_or_crate_semantics(self):
        packet = json.loads(aid_catalog.PACKET.read_text())
        packet['status'] = 'reviewed_named_aid_records'
        source = {'build': packet['source_build'], 'record_sha256': 'a' * 64,
                  'join_sha256': 'b' * 64, 'native_record_id': '30100001',
                  'native_field': 'cuisine_type'}
        base = {'category': 'food_drink', 'catalog_id': 'aid:30100001',
                'name': 'Unreviewed cuisine', 'summary': 'Raw type only',
                'calculation_status': 'display_only', 'source': source}
        packet['records'] = [base]
        with self.assertRaisesRegex(ValueError, 'effect ID and text'):
            self.packet(packet)
        packet['records'] = [{**base, 'category': 'crates', 'draw_mode': 'random_pool',
                              'rewards': [{'native_item_id': '36000075', 'quantity': 1}]}]
        with self.assertRaisesRegex(ValueError, 'reward names'):
            self.packet(packet)
        packet['records'][0]['rewards'][0]['name'] = 'Unknown reward'
        packet['records'][0]['probability'] = 0.5
        with self.assertRaisesRegex(ValueError, 'no inferred odds'):
            self.packet(packet)

    def test_named_crate_must_keep_unknown_draw_and_no_reward_odds(self):
        packet = json.loads(aid_catalog.PACKET.read_text())
        crate = packet['records'][0]
        crate['draw_mode'] = 'random_pool'
        with self.assertRaisesRegex(ValueError, 'draw mode'):
            self.packet(packet)
        crate['draw_mode'] = 'unknown'
        crate['rewards'][0]['probability'] = 0.1
        with self.assertRaisesRegex(ValueError, 'no inferred odds'):
            self.packet(packet)
        del crate['rewards'][0]['probability']
        crate['availability'] = 'currently_obtainable'
        with self.assertRaisesRegex(ValueError, 'unknown availability'):
            self.packet(packet)

    def test_named_reward_identity_and_text_must_match_hashed_native_source(self):
        packet = json.loads(aid_catalog.PACKET.read_text())
        packet['records'][0]['rewards'][0]['name'] = 'Invented reward'
        with self.assertRaisesRegex(ValueError, 'reward/source record mismatch'):
            self.packet(packet)
        packet = json.loads(aid_catalog.PACKET.read_text())
        packet['categories']['crates']['source_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'source bytes/hash conflict'):
            self.packet(packet)

    def test_native_guarantee_threshold_cannot_be_invented_or_converted_to_odds(self):
        packet = json.loads(aid_catalog.PACKET.read_text())
        packet['records'][0]['source_guarantee']['max_opens'] = 10
        with self.assertRaisesRegex(ValueError, 'guarantee identity'):
            self.packet(packet)
        packet = json.loads(aid_catalog.PACKET.read_text())
        packet['records'][0]['source_guarantee']['probability'] = 1 / 15
        with self.assertRaisesRegex(ValueError, 'guarantee identity'):
            self.packet(packet)

    def test_named_food_and_whim_cannot_invent_buff_binding_or_formula(self):
        packet = json.loads(aid_catalog.PACKET.read_text())
        packet['records'][1]['effect_native_id'] = '999999'
        with self.assertRaisesRegex(ValueError, 'consumable identity/effect source mismatch'):
            self.packet(packet)
        packet = json.loads(aid_catalog.PACKET.read_text())
        packet['records'][2]['effect_native_id'] = '403137000'
        with self.assertRaisesRegex(ValueError, 'effect ID and text missing'):
            self.packet(packet)
        packet = json.loads(aid_catalog.PACKET.read_text())
        packet['records'][2]['formula_binding'] = {'duration_multiplier': 1.35}
        with self.assertRaisesRegex(ValueError, 'display-only scope'):
            self.packet(packet)


if __name__ == '__main__':
    unittest.main()
