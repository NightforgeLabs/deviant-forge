"""Exact food/Whim graph joins remain display-only in Aid."""
import unittest

import aid_catalog
import native_food_whim_graphs


class NativeFoodWhimGraphTests(unittest.TestCase):
    def test_all_source_joins_and_named_catalog_boundary(self):
        packet, priority, items, graphs = native_food_whim_graphs._source()
        summaries = native_food_whim_graphs.records()
        self.assertEqual((len(items), len(graphs), len(priority['records']), len(summaries)),
                         (521, 171, 33, 225))
        self.assertNotIn(30104005, summaries)
        self.assertEqual(len([row for row in items.values()
                              if not row['installed_english_title']]), 8)
        self.assertEqual(graphs[403152800]['status'], 'archive_graph_missing')
        aid = aid_catalog.overview()
        food, whims = aid['categories'][:2]
        self.assertEqual((food['ready_count'], whims['ready_count']), (501, 12))
        self.assertEqual(sum(bool(row.get('native_graph_evidence')) for row in food['ready_items']), 213)
        self.assertEqual(sum(bool(row.get('native_graph_evidence')) for row in whims['ready_items']), 12)
        self.assertEqual(aid['formula_ready_items'], 0)

    def test_source_targets_conditions_and_unknown_inputs(self):
        rows = native_food_whim_graphs.records()
        soup = rows[30110374]
        self.assertTrue(soup['combat_or_psi_target_from_source'])
        self.assertFalse(soup['combat_calculation_included'])
        graph = soup['graphs'][0]
        self.assertEqual((graph['buff_id'], graph['nominal_lifetime_seconds']),
                         (403136600, 1980))
        target = graph['target_properties'][0]
        self.assertEqual((target['native_attr_id'], target['source_label']),
                         ('E121', 'Power Surge DMG Bonus'))
        self.assertEqual(target['configured_expression'], '((buff.effect_rate + 1.0) * 0.1)')
        self.assertFalse(target['runtime_application_proven'])
        self.assertIsNone(graph['active_on_selected_build'])
        fries = rows[30110206]['graphs'][0]
        self.assertIn(110600100, [buff for checker in fries['configured_conditions']
                                  for buff in checker['referenced_buff_ids']])
        self.assertFalse(all(checker['runtime_condition_truth_proven']
                             for checker in fries['configured_conditions']))

    def test_noncombat_controls_and_absent_graph(self):
        rows = native_food_whim_graphs.records()
        ginger = rows[30110378]['graphs'][0]['target_properties'][0]
        self.assertEqual((ginger['native_attr_id'], ginger['native_property']),
                         ('L21', 'tag_buff_time_extend_add_rate_armed'))
        self.assertNotIn('defense', ginger['native_property'])
        delight = rows[30139002]['graphs'][0]['target_properties'][0]
        self.assertEqual((delight['native_attr_id'], delight['configured_raw_value']),
                         ('R37', .35))
        self.assertFalse(delight['runtime_application_proven'])
        missing = rows[30111176]['graphs'][0]
        self.assertEqual(missing['graph_status'], 'archive_graph_missing')
        self.assertEqual(missing['target_properties'], [])
        self.assertIsNone(missing['nominal_lifetime_seconds'])


if __name__ == '__main__':
    unittest.main()
