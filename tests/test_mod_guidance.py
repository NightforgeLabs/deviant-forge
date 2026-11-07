import unittest

import catalog
import mod_guidance


class ModGuidanceTests(unittest.TestCase):
    def test_nine_named_mechanic_categories_are_distinct(self):
        labels=[goal['label'] for goal in mod_guidance.GOALS.values()]
        self.assertEqual(labels,['Burn Mod','Power Surge Mod','Frost Vortex Mod','The Bullseye Mod',
                                 'Fortress Warfare Mod','Unstable Bomber Mod','Fast Gunner Mod',
                                 'Bounce Mod','Shrapnel Mod'])
        for key,goal in mod_guidance.GOALS.items():
            with self.subTest(key=key):
                result=mod_guidance.suggest(catalog,[],key)
                self.assertEqual(result['goal_label'],goal['label'])
                self.assertTrue(result['overall']['weapon'] or result['overall']['armor'])
                self.assertEqual(result['owned'],{'weapon':[],'armor':[]})

    def test_electric_matches_are_separate_from_owned_and_have_no_damage_score(self):
        mod_id = 'mod:weapon_mod:shock-diffusion-power-surge'
        glove_id = 'mod:gloves_mod:elemental-overload-resonance'
        inventory = [
            {'id': 'one', 'kind': 'mod_unlock', 'level': 11, 'effects': {'catalog_id': mod_id}},
            {'id': 'two', 'kind': 'mod_unlock', 'level': 9, 'effects': {'catalog_id': glove_id}},
            {'id': 'three', 'kind': 'weapon', 'effects': {'catalog_id': 'weapon:aug-electron-cloud'}},
        ]
        slots = {'primary': {'catalog_id': 'weapon:aug-electron-cloud'},
                 'gloves': {'catalog_id': next(e['id'] for e in catalog.ENTRIES.values() if e.get('kind') == 'armor' and e.get('slot') == 'gloves')}}
        before = repr(inventory), repr(slots)
        result = mod_guidance.suggest(catalog, inventory, 'electric', 'weapon:aug-electron-cloud', slots)
        self.assertEqual((repr(inventory), repr(slots)), before)
        self.assertTrue(result['weapon_family_match'])
        self.assertGreater(len(result['overall']['weapon']), len(result['owned']['weapon']))
        self.assertEqual({item['id'] for group in result['owned'].values() for item in group}, {mod_id, glove_id})
        self.assertTrue(any(item['match'] == 'broad elemental' for item in result['owned']['armor']))
        self.assertTrue(all('score' not in item and 'damage_estimate' not in item for group in result['overall'].values() for item in group))
        self.assertTrue(result['owned']['armor'][0]['can_equip_in_current_build'])
        self.assertTrue(any(item['source_url'] for item in result['owned']['weapon']))

    def test_missing_gear_stays_unavailable_and_invalid_goals_fail(self):
        result = mod_guidance.suggest(catalog, [], 'electric', None, {})
        self.assertFalse(result['weapon_family_match'])
        self.assertTrue(all(not item['can_equip_in_current_build'] for group in result['overall'].values() for item in group))
        with self.assertRaises(ValueError):
            mod_guidance.suggest(catalog, [], 'not-a-goal')


if __name__ == '__main__':
    unittest.main()
