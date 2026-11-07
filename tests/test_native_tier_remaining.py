import copy
import hashlib
import json
import unittest

import catalog
import native_tier_remaining
import planned_advisor


class RemainingNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.static=json.loads(native_tier_remaining.STATIC.read_text())
        cls.names=json.loads(native_tier_remaining.NAMES.read_text())
        cls.captures={key:(native_tier_remaining.RAW/f'{key}.literal_bytes.bin').read_bytes()
                      for key in cls.static['source']['literal_sha256']}
        cls.five=planned_advisor.NATIVE_TIER_STAR_EVIDENCE
        cls.ten=planned_advisor.NATIVE_EXPANDED_EVIDENCE

    def checked(self,static=None,names=None,captures=None):
        return native_tier_remaining.validate(
            static if static is not None else self.static,
            names if names is not None else self.names,
            captures if captures is not None else self.captures,
            catalog.ENTRIES,prior_five=self.five,prior_ten=self.ten)

    def test_all_18_new_blueprint_identities_are_located_evidence_only(self):
        result=self.checked()
        self.assertEqual({'prior_accepted':15,'new_accepted':18,'new_rejected':0,
            'total_accepted_blueprints':33,'new_tier_rows':90,'new_star_rows':108,
            'new_direct_tier_one_names':8,'new_blueprint_only_names':10,
            'formula_ready_fields':0},result['counts'])
        self.assertEqual(18,len(result['by_catalog']))
        self.assertFalse(set(result['by_catalog']) & {
            row['catalog_id'] for row in self.five['by_blueprint'].values()})
        self.assertFalse(set(result['by_catalog']) & set(self.ten['by_catalog']))
        self.assertTrue(all(row['public_page_build'] is None
                            for row in result['by_catalog'].values()))

    def test_fp9_rename_is_explicit_and_not_the_base_tec9(self):
        result=self.checked()
        row=result['by_catalog']['weapon:tec9-additional-rules']
        self.assertEqual('FP9 - Additional Rules B.P.',row['public_blueprint_title'])
        self.assertEqual('Previously listed as TEC9 - Additional Rules.',
                         row['name_bridge']['source_statement'])
        self.assertIn('oncehumandb.com/weapons/tec9-additional-rules',
                      row['name_bridge']['source_url'])
        self.assertNotIn('weapon:tec9',result['by_catalog'])
        self.assertEqual('native_blueprint_and_named_blueprint_page',row['identity_proof'])

    def test_public_gear_names_do_not_imply_numeric_page_data(self):
        result=self.checked()
        direct=result['by_catalog']['weapon:g17-cash-only']
        only=result['by_catalog']['weapon:mg4-conflicting-memories']
        self.assertEqual('native_blueprint_and_direct_gear_page',direct['identity_proof'])
        self.assertEqual('native_blueprint_and_named_blueprint_page',only['identity_proof'])
        self.assertIsNone(only['public_tier_one_gear_title'])
        selected=native_tier_remaining.selected(result,'weapon:g17-cash-only',5,5)
        self.assertIsNone(selected['public_tier_one']['star_damage'])
        self.assertFalse(selected['calculation_included'])

    def test_tampered_blueprint_id_native_offset_or_capture_is_rejected(self):
        bad=copy.deepcopy(self.names)
        bad['records'][0]['blueprint_id']=99999999
        with self.assertRaisesRegex(ValueError,'lacks a native row'):
            self.checked(names=bad)
        bad=copy.deepcopy(self.static)
        new=next(row for row in bad['samples'] if row['blueprint_id']==13131301)
        new['tiers'][0]['native_blueprint_field']['value']=13451401
        linked=copy.deepcopy(self.names)
        linked['native_catalog_sha256']=hashlib.sha256(
            (json.dumps(bad,indent=2)+'\n').encode()).hexdigest()
        with self.assertRaisesRegex(ValueError,'decoded value|identity field'):
            self.checked(static=bad,names=linked)
        captures=dict(self.captures)
        captures['equip_origin_data']=b'bad'+captures['equip_origin_data'][3:]
        with self.assertRaisesRegex(ValueError,'capture hash conflict'):
            self.checked(captures=captures)

    def test_normal_build_selection_changes_evidence_without_damage_total(self):
        for identity,expected in [('weapon:g17-cash-only',167),
                                  ('weapon:tec9-additional-rules',359),
                                  ('weapon:mg4-conflicting-memories',188)]:
            with self.subTest(identity=identity):
                selected={'catalog_id':identity,'tier':5,'stars':5}
                analysis=planned_advisor.analyze({'primary':selected})
                timing=analysis['weapon_reference_timing']
                self.assertEqual('native_identity_only',timing['reference_status'])
                self.assertEqual(expected,
                    timing['native_selected_tier_star']['gun_preset_attack'])
                self.assertIsNone(timing['fire_rate_raw'])
                self.assertIsNone(timing['rpm'])
                self.assertFalse(timing['native_selected_tier_star']['calculation_included'])
                self.assertIsNone(analysis['matched_reference_component'])
                self.assertEqual(timing,planned_advisor.analyze({'primary':dict(selected)})
                                 ['weapon_reference_timing'])


if __name__=='__main__':
    unittest.main()
