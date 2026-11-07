import copy
import hashlib
import json
import unittest

import catalog
import native_tier_expanded
import planned_advisor


class NativeExpandedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.static = json.loads(native_tier_expanded.STATIC.read_text())
        cls.public = json.loads(native_tier_expanded.PUBLIC.read_text())
        cls.captures = {name:(native_tier_expanded.RAW/f'{name}.literal_bytes.bin').read_bytes()
                        for name in cls.static['source']['literal_sha256']}

    def checked(self, static=None, public=None, captures=None):
        return native_tier_expanded.validate(
            static if static is not None else self.static,
            public if public is not None else self.public,
            captures if captures is not None else self.captures,
            catalog.ENTRIES)

    def test_ten_exact_identities_have_located_fields_but_no_formula_binding(self):
        result=self.checked()
        self.assertEqual({'weapons':10,'native_tier_rows':50,'native_star_rows':60,
                          'public_tier_one_named_pages':10,'public_star_tables':9,
                          'formula_ready_fields':0},result['counts'])
        self.assertEqual(set(result['by_catalog']),{
            'weapon:critical-pulse','weapon:mg4-predator','weapon:mps5-primal-rage',
            'weapon:mps7-outer-space','weapon:de-50-jaws','weapon:g17-hazardous-object',
            'weapon:dbsg-format','weapon:r500-memento','weapon:dbsg-doombringer',
            'weapon:db12-raining-cash'})
        r500=native_tier_expanded.selected(result,'weapon:r500-memento',1,4)
        self.assertEqual((170,1.15,195),
            (r500['gun_preset_attack'],r500['preset_attack_radio'],
             r500['public_tier_one']['star_damage'][3]))
        self.assertFalse(r500['calculation_included'])
        self.assertIsNone(native_tier_expanded.selected(result,'weapon:aug-electron-cloud',5,5))

    def test_format_missing_public_star_table_is_not_inferred(self):
        result=self.checked()
        selected=native_tier_expanded.selected(result,'weapon:dbsg-format',5,5)
        self.assertIsNotNone(selected['preset_attack_radio'])
        self.assertIsNone(selected['public_tier_one']['star_damage'])
        self.assertEqual('not present on inspected gear page',
                         selected['public_tier_one']['star_table_status'])

    def test_wrong_source_or_cross_weapon_mapping_is_rejected(self):
        bad=copy.deepcopy(self.static)
        bad['samples'][0]['tiers'][0]['native_blueprint_field']['value']=13622301
        linked=copy.deepcopy(self.public)
        linked['static_artifact_sha256']=hashlib.sha256(
            (json.dumps(bad,indent=2)+'\n').encode()).hexdigest()
        with self.assertRaisesRegex(ValueError,'decoded value|identity field'):
            self.checked(static=bad,public=linked)
        bad=copy.deepcopy(self.public)
        bad['records'][0]['public_tier_one_gear_title']='MG4 - Predator (Tier 1)'
        with self.assertRaisesRegex(ValueError,'source identity conflict'):
            self.checked(public=bad)
        captures=dict(self.captures)
        captures['gun_blueprint_data']=b'bad'+captures['gun_blueprint_data'][3:]
        with self.assertRaisesRegex(ValueError,'capture hash conflict'):
            self.checked(captures=captures)

    def test_normal_build_shows_selected_native_fields_without_damage_result(self):
        for identity,tier,stars in [('weapon:r500-memento',1,4),
                                     ('weapon:dbsg-format',5,5),
                                     ('weapon:critical-pulse',5,6)]:
            with self.subTest(identity=identity):
                analysis=planned_advisor.analyze({'primary':{'catalog_id':identity,
                                                               'tier':tier,'stars':stars}})
                selected=analysis['weapon_reference_timing']['native_selected_tier_star']
                self.assertEqual(identity,selected['catalog_id'])
                self.assertIsNotNone(selected['gun_preset_attack'])
                self.assertIsNotNone(selected['preset_attack_radio'])
                self.assertFalse(selected['calculation_included'])
                self.assertIsNone(analysis['matched_reference_component'])


if __name__=='__main__':
    unittest.main()
