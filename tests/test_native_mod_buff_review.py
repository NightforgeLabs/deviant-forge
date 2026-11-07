"""All 49 buff graphs are classified without promoting active damage."""
import unittest
from unittest.mock import patch

import native_mod_frame_catalog as frames
import native_mod_buff_review as review
import public_catalog_detail


class NativeModBuffReviewTests(unittest.TestCase):
    def test_49_id_ledger_and_all_1299_buff_preview_positions(self):
        packet, new, ledger = review._source()
        self.assertEqual((len(ledger), len(new)), (49, 32))
        self.assertEqual(review.coverage()['all_graphs_with_direct_or_indirect_attribute_target'], 46)
        self.assertEqual(review.coverage()['all_effect_only_graphs'], 3)
        statuses = {}
        for source_row in frames._source()[2].values():
            import native_priority_mod_buff as priority
            import native_mod_buff_batch2 as batch2
            annotated = review.annotate(batch2.annotate(priority.annotate(source_row)))
            for line in annotated['ordered_lines']:
                if line.get('buff_id') is not None:
                    statuses.setdefault(line['buff_id'], line['attribute_status'])
                    self.assertEqual(statuses[line['buff_id']], line['attribute_status'])
                    self.assertNotEqual(line['attribute_status'], 'graph_attribute_unverified')
        self.assertEqual(len(statuses), 49)
        self.assertEqual(sum(status == 'typed_effect_node_only_arithmetic_unverified'
                             for status in statuses.values()), 3)
        self.assertEqual(sum(status != 'typed_effect_node_only_arithmetic_unverified'
                             for status in statuses.values()), 46)
        self.assertEqual(packet['coverage']['primary_graphs_reviewed'], 49)

    def test_direct_secondary_and_effect_node_examples_keep_runtime_unknown(self):
        downstar = frames.preview('mod:pants_mod:bullet-siphon-downstar', 17)
        self.assertIsNotNone(downstar)
        self.assertEqual(downstar['ordered_lines'][0]['attribute_status'],
                         'typed_graph_target_verified_execution_unproven')
        resonance = frames.preview('mod:gloves_mod:crit-amplifier-resonance-deviant-energy', 17)
        self.assertEqual(resonance['ordered_lines'][0]['secondary_cast_buff_ids'], [581701100])
        self.assertFalse(resonance['ordered_lines'][0]['secondary_level_application_proven'])
        battle = frames.preview('mod:chest_mod:ardent-shield-battle', 17)
        self.assertEqual(battle['ordered_lines'][2]['effect_node_types'],
                         ['NodeGetFloatAttr', 'NodeHeal'])
        mirror = frames.preview('mod:chest_mod:ardent-shield-mirror', 17)
        wild = frames.preview('mod:chest_mod:ardent-shield-wild', 17)
        self.assertEqual(mirror['ordered_lines'][2]['effect_node_types'],
                         ['NodeHitAngleDamageReduce'])
        self.assertEqual(wild['ordered_lines'][2]['effect_node_types'],
                         ['NodeDistanceDamageReduce'])
        for scenario in (downstar, resonance, battle, mirror, wild):
            self.assertFalse(scenario['runtime_damage_included'])
            self.assertFalse(scenario['server_buff_execution_proven'])
        card = public_catalog_detail.detail('mod:chest_mod:ardent-shield-battle', 17)
        self.assertEqual(card['configured_bonus_lines'][2]['native_graph_review_status'],
                         'effect_node_only')
        self.assertNotEqual(card['bonus_lines'], card['configured_bonus_lines'])

    def test_hash_conflict_rejected(self):
        original = review._sha
        with patch.object(review, '_sha', side_effect=lambda path: (
                'invalid' if path == review.PACKET else original(path))):
            review._source.cache_clear()
            with self.assertRaisesRegex(ValueError, 'source hash conflict'):
                review._source()
        review._source.cache_clear()


if __name__ == '__main__':
    unittest.main()
