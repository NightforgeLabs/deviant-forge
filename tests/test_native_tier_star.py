import copy
from decimal import Decimal, ROUND_HALF_UP
import json
import unittest

import native_tier_star
import planned_advisor
import published_item_tier


class NativeTierStarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tier = json.loads(native_tier_star.TIER_SAMPLE.read_text())
        cls.star = json.loads(native_tier_star.STAR_SAMPLE.read_text())
        cls.captures = {name: (native_tier_star.RAW /
            f'{name}.literal_bytes.bin').read_bytes()
            for name in native_tier_star.CAPTURE_NAMES}

    def check(self, tier=None, star=None, captures=None):
        return native_tier_star.validate(tier if tier is not None else self.tier,
            star if star is not None else self.star,
            captures if captures is not None else self.captures,
            published_item_tier.ROWS)

    def test_all_located_fields_are_evidence_only_and_exactly_bound(self):
        report = self.check()
        self.assertEqual({'blueprints':5, 'tier_rows':25, 'star_rows':30,
                          'formula_ready_fields':0}, report['counts'])
        self.assertTrue(all(tier['matches_public_display_number']
            for item in report['by_blueprint'].values() for tier in item['tiers'].values()))
        selected = native_tier_star.selected(report, 'weapon:aug-electron-cloud', 5, 5)
        self.assertEqual((13451401, 10451405, 201.0, 1.2),
            (selected['blueprint_id'], selected['gear_id'],
             selected['gun_preset_attack'], selected['preset_attack_radio']))
        self.assertFalse(selected['calculation_included'])
        self.assertIsNone(native_tier_star.selected(report, 'weapon:kam-crank', 5, 5))
        self.assertIsNone(native_tier_star.selected(report, 'weapon:aug-electron-cloud', None, 5)['gun_preset_attack'])

    def test_wrong_blueprint_tier_star_offset_and_capture_rejected(self):
        tier = copy.deepcopy(self.tier)
        tier['samples'][0]['tiers'][4]['blueprint_no']['value'] = 13413301
        with self.assertRaisesRegex(ValueError, 'decoded value|identity field'):
            self.check(tier=tier)
        tier = copy.deepcopy(self.tier)
        tier['samples'][0]['tiers'][4]['gear_id'] = 10413305
        with self.assertRaisesRegex(ValueError, 'identity conflicts'):
            self.check(tier=tier)
        star = copy.deepcopy(self.star)
        star['records'][0]['stars'][4]['value_byte_offset'] += 1
        with self.assertRaisesRegex(ValueError, 'terminal located field|raw byte location'):
            self.check(star=star)
        captures = dict(self.captures)
        captures['equip_origin_data'] = b'wrong' + captures['equip_origin_data'][5:]
        with self.assertRaisesRegex(ValueError, 'capture hash conflict'):
            self.check(captures=captures)

    def test_selected_build_exposes_native_fields_without_total_or_borrowing(self):
        selected = {'catalog_id':'weapon:aug-electron-cloud', 'tier':5, 'stars':5}
        analysis = planned_advisor.analyze({'primary':selected})
        native = analysis['weapon_reference_timing']['native_selected_tier_star']
        self.assertEqual((201.0,1.2),
            (native['gun_preset_attack'],native['preset_attack_radio']))
        self.assertFalse(native['calculation_included'])
        self.assertIsNone(analysis['matched_reference_component'])
        other = planned_advisor.analyze({'primary':{**selected, 'catalog_id':'weapon:socr-cosmic-visitor'}})
        self.assertEqual(264.0, other['weapon_reference_timing']['native_selected_tier_star']['gun_preset_attack'])
        self.assertIsNone(planned_advisor._weapon_reference_timing({
            'primary':{'catalog_id':'weapon:kam-crank', 'tier':5, 'stars':5}}))

    def test_published_counterexample_rejects_universal_star_product(self):
        artifact = json.loads((native_tier_star.ROOT /
            'native-star-rounding-counterexample-v1.json').read_text())
        self.assertEqual('evidence_only_no_universal_star_formula',artifact['status'])
        self.assertEqual((13122301,10122301),
                         (artifact['blueprint_id'],artifact['gear_id']))
        native=artifact['native_source']
        product=(Decimal(str(native['gun_preset_attack']['value'])) *
                 Decimal(str(native['preset_attack_radio_4star']['value'])))
        half_up=int(product.quantize(Decimal('1'),rounding=ROUND_HALF_UP))
        self.assertEqual(196,half_up)
        self.assertEqual(195,artifact['public_source']['displayed_four_star_dmg'])
        self.assertNotEqual(half_up,artifact['public_source']['displayed_four_star_dmg'])
        self.assertEqual(0,native_tier_star.load_current(published_item_tier.ROWS)
                         ['counts']['formula_ready_fields'])


if __name__ == '__main__':
    unittest.main()
