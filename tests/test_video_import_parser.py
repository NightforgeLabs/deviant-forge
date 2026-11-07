import unittest
import video_import


def line(text, y):
    return {'text': text, 'x': 0, 'y': y, 'w': 300, 'h': 24, 'confidence': 90}


class VideoTooltipParserTests(unittest.TestCase):
    def test_icon_prefix_does_not_hide_owned_level(self):
        rows = [line('Quick Comeback <Battle>', 0), line('Armor Mods–Top', 30),
                line('Quick Comeback', 60), line('Using a healing shot gives speed.', 90),
                line('W 10 Battle', 200), line('Max HP + 2.4%', 300),
                line('Weapon DMG + 3.6%', 400), line('Magazine Capacity + 4.8%', 500),
                line('All DMG Boost + 3.0%', 600), line('Equip', 700)]
        found = video_import.parse_tooltip(rows, 'mod:chest_mod:quick-comeback-battle')
        self.assertEqual((found['ownership'], found['level'], found['slot']), ('unlocked', 10, 'chest_mod'))
        self.assertEqual(len(found['attribute_rows']), 4)

    def test_wrapped_locked_variant_keeps_main_effect_separate(self):
        rows = [line('Ardent Shield <Phantasmal Deviant', 0), line('Energy>', 40),
                line('Armor Mods–Top', 80), line('Locked', 120), line('Ardent Shield', 160),
                line('While the shield is active, gain DMG Reduction.', 200),
                line('Phantasmal Deviant Energy', 300), line('Locked', 330),
                line('Status DMG + 2.0%', 410)]
        found = video_import.parse_tooltip(rows, 'mod:chest_mod:ardent-shield-phantasmal-deviant-energy')
        self.assertEqual(found['ownership'], 'locked')
        self.assertIsNone(found['level'])
        self.assertNotIn('Phantasmal Deviant Energy', found['main_effect'])
        self.assertIn('shield is active', found['main_effect'])


if __name__ == '__main__':
    unittest.main()
