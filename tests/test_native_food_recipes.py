import unittest

import aid_catalog
import native_food_recipes


class NativeFoodRecipesTests(unittest.TestCase):
    def test_exact_named_coverage_and_no_active_effect(self):
        recipes = native_food_recipes.records()
        self.assertEqual(len(recipes), 33)
        self.assertEqual(sum(len(row['configurations']) for row in recipes.values()), 77)
        self.assertEqual(sum(len(variant['forge_keys']) for row in recipes.values()
                             for variant in row['configurations']), 82)
        self.assertEqual(sum(len(variant['forge_keys']) == 2 for row in recipes.values()
                             for variant in row['configurations']), 5)
        self.assertEqual(sum(bool(variant['configured_gates']['unlock_tip'])
                             for row in recipes.values() for variant in row['configurations']), 7)
        self.assertEqual(sum(variant['configured_gates']['is_diy']
                             for row in recipes.values() for variant in row['configurations']), 6)
        self.assertTrue(all(row['current_server_selection'] == 'unknown'
                            for row in recipes.values()))
        self.assertTrue(all(row['availability'] == 'unknown' and
                            row['unlock'] == 'unknown' and
                            row['active_food_effect'] == 'not_inferred'
                            for row in recipes.values()))
        overview = aid_catalog.overview()
        rows = [row for category in overview['categories'][:2]
                for row in category['ready_items'] if row['native_recipe_evidence']]
        self.assertEqual(len(rows), 33)
        self.assertEqual(len([row for row in rows if row['category'] == 'whims_deviations']), 1)
        self.assertEqual(overview['formula_ready_items'], 0)

    def test_soup_three_distinct_configurations_and_unknown_933(self):
        soup = native_food_recipes.records()[30110374]
        variants = soup['configurations']
        self.assertEqual([row['source_record_byte_offset'] for row in variants],
                         [480109, 1243417, 1243554])
        self.assertEqual([(row['forge_no'], row['forge_season_selector']) for row in variants],
                         [(1200379, None), (1200379, 1), (1200379, 222)])
        self.assertEqual([row['expected_selected_key'] for row in
                          soup['forge_variant_selection']['season_list_examples']],
                         [1200379, [1200379, 1], [1200379, 222]])
        self.assertEqual(soup['forge_variant_selection']['current_server_season'], 'unknown')
        self.assertEqual([row['configured_seconds'] for row in variants], [5, 5, 20])
        self.assertEqual([(i['item_id'], i['quantity']) for i in variants[0]['ingredients']],
                         [(30102922, 1), (30102007, 2), (30102011, 2), (933, 3)])
        self.assertIsNone(variants[0]['ingredients'][-1]['name'])
        self.assertEqual(soup['ingredient_933_role'],
                         'typed_required_item_number_resource_name_unbound')
        self.assertEqual([row['method_id'] for row in variants[1]['stations']],
                         [52, 514, 609, 53, 515, 71])
        self.assertEqual([row['method_id'] for row in variants[2]['stations']],
                         [53, 515, 609])

    def test_4010_choices_are_not_soup_ingredients(self):
        soup = native_food_recipes.records()[30110374]
        choices = soup['separate_4010_choices']
        self.assertEqual([(row['item_id'], row['configured_value']) for row in choices],
                         [(30104008, '0.3'), (30104009, '0.3'),
                          (30104010, '-0.5'), (30104014, '0.4'),
                          (30104906, '0.5')])
        self.assertFalse(soup['separate_4010_choices_are_recipe_ingredients'])
        ingredient_ids = {row['item_id'] for variant in soup['configurations']
                          for row in variant['ingredients']}
        self.assertFalse(ingredient_ids & {row['item_id'] for row in choices})

    def test_full_source_keys_and_alias_not_extra_recipe(self):
        recipes = native_food_recipes.records()
        french = recipes[30110206]
        aliases = [variant for variant in french['configurations']
                   if len(variant['forge_keys']) == 2]
        self.assertEqual(len(aliases), 1)
        self.assertEqual(aliases[0]['source_record_byte_offset'], 564377)
        self.assertEqual(aliases[0]['forge_keys'],
                         [{'forge_no': 1200125, 'season_selector': None},
                          {'forge_no': 1200125, 'season_selector': 1}])
        self.assertEqual(sum(len(v['forge_keys']) for v in recipes[30110374]['configurations']), 3)


if __name__ == '__main__':
    unittest.main()
