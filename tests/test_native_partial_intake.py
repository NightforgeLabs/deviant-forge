import copy
import json
import unittest

import catalog
import native_partial_intake as partial
import planned_advisor


class NativePartialIntakeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = json.loads(partial.PARTIAL.read_bytes())
        cls.anchors = json.loads(partial.ANCHORS.read_bytes())
        cls.captures = {name:(partial.RAW/f'{name}.literal_bytes.bin').read_bytes()
                        for name in cls.packet['source']['literal_sha256']}
        cls.prior = dict(planned_advisor.NATIVE_TIER_STAR_EVIDENCE['by_blueprint'])
        cls.prior.update({r['blueprint_id']:r for r in
            planned_advisor.NATIVE_EXPANDED_EVIDENCE['by_catalog'].values()})
        cls.prior.update({r['blueprint_id']:r for r in
            planned_advisor.NATIVE_REMAINING_EVIDENCE['by_catalog'].values()})

    def checked(self, packet=None, anchors=None, captures=None, entries=None):
        return partial.validate(packet if packet is not None else self.packet,
            anchors if anchors is not None else self.anchors,
            captures if captures is not None else self.captures,
            entries if entries is not None else catalog.ENTRIES, self.prior)

    def test_field_level_counts_and_previous_complete_records(self):
        result = self.checked()
        self.assertEqual({'prior_complete_records':33, 'new_native_blueprints':59,
            'new_tier_attack_fields':295, 'new_star_ratio_fields':231,
            'new_catalog_identity_bindings':2, 'new_unbound_blueprints':57,
            'formula_ready_fields':0}, result['counts'])
        self.assertEqual({3:25,4:14,5:20,6:33}, result['stored_star_distribution'])
        self.assertEqual(92,len(result['by_blueprint']))
        self.assertEqual(33,len(self.prior))

    def test_partial_star_keeps_tier_and_never_creates_damage(self):
        result = self.checked()
        r500 = partial.selected(result,'weapon:r500',1,4)
        self.assertEqual(122,r500['gun_preset_attack'])
        self.assertIsNone(r500['preset_attack_radio'])
        self.assertIn('exceeds the published maximum of 3★',r500['missing_star_reason'])
        self.assertEqual('exceeds_published_max_stars',r500['configuration_status'])
        self.assertFalse(r500['calculation_included'])
        goshawk = partial.selected(result,'weapon:de-50-goshawk',5,4)
        self.assertEqual(611,goshawk['gun_preset_attack'])
        self.assertIsNotNone(goshawk['preset_attack_radio'])
        self.assertIsNone(goshawk['missing_star_reason'])
        self.assertEqual('not_disproved_by_published_max',goshawk['configuration_status'])
        self.assertIsNone(partial.selected(result,'weapon:kam-crank',1,1))

    def test_missing_row_within_sourced_max_is_unknown_not_impossible(self):
        result=copy.deepcopy(self.checked())
        row=result['by_catalog']['weapon:r500']
        row['stars'].pop(3)
        row['stored_star_count']=2
        selected=partial.selected(result,'weapon:r500',1,3)
        self.assertEqual(122,selected['gun_preset_attack'])
        self.assertIsNone(selected['preset_attack_radio'])
        self.assertEqual('not_disproved_by_published_max',selected['configuration_status'])
        self.assertIn('No stored native star record',selected['missing_star_reason'])

    def test_wrong_public_identity_configuration_and_partial_record_rejected(self):
        bad = copy.deepcopy(self.anchors)
        bad['anchors'][0]['catalog_id'] = 'weapon:r500-memento'
        with self.assertRaisesRegex(ValueError,'public name'):
            self.checked(anchors=bad)
        bad = copy.deepcopy(self.anchors)
        bad['anchors'][2]['catalog_id'] = 'weapon:kam-crank'
        with self.assertRaisesRegex(ValueError,'must not inherit'):
            self.checked(anchors=bad)
        bad = copy.deepcopy(self.packet)
        row = next(r for r in bad['samples'] if r['blueprint_id']==13121101)
        row['tiers'][0]['native_blueprint_field']['value'] = 13421301
        with self.assertRaisesRegex(ValueError,'decoded value|identity field'):
            self.checked(packet=bad)
        bad = copy.deepcopy(self.packet)
        row = next(r for r in bad['samples'] if r['blueprint_id']==13121101)
        row['star_ratios'].pop(1)
        with self.assertRaisesRegex(ValueError,'sequence has a gap'):
            self.checked(packet=bad)
        captures = dict(self.captures)
        captures['equip_origin_data'] = b'X' + captures['equip_origin_data'][1:]
        with self.assertRaisesRegex(ValueError,'literal hash conflict'):
            self.checked(captures=captures)

    def test_normal_build_selected_and_saved_shape_never_uses_native_damage(self):
        for identity, tier, stars in [('weapon:r500',1,4),
                                      ('weapon:de-50-goshawk',5,4)]:
            with self.subTest(identity=identity):
                slots={'primary':{'catalog_id':identity,'tier':tier,'stars':stars}}
                output=planned_advisor.analyze(slots)
                timing=output['weapon_reference_timing']
                self.assertEqual('native_identity_only',timing['reference_status'])
                self.assertIsNone(timing['rpm'])
                self.assertIsNone(timing['magazine'])
                self.assertIsNone(output['matched_reference_component'])
                self.assertFalse(timing['native_selected_tier_star']['calculation_included'])
                self.assertEqual(timing,planned_advisor.analyze({'primary':dict(slots['primary'])})
                                 ['weapon_reference_timing'])


if __name__ == '__main__':
    unittest.main()
