import copy
import json
import unittest

import catalog
import native_crosswalk_intake as crosswalk
import planned_advisor
import server


class NativeCrosswalkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proposed=json.loads(crosswalk.PROPOSED.read_bytes())
        cls.titles=json.loads(crosswalk.TITLES.read_bytes())
        cls.native95=json.loads(crosswalk.NATIVE95.read_bytes())
        cls.maxima=json.loads(crosswalk.MAXIMA.read_bytes())
        cls.partial=planned_advisor.NATIVE_PARTIAL_EVIDENCE
        cls.installed=planned_advisor.NATIVE_INSTALLED_IDENTITIES

    def checked(self,proposed=None,titles=None,native95=None,maxima=None):
        return crosswalk.validate(proposed or self.proposed,titles or self.titles,
            native95 or self.native95,maxima or self.maxima,
            catalog.ENTRIES,self.partial,self.installed)

    def test_exact_source_link_coverage_and_whitelist(self):
        report=self.checked()
        self.assertEqual({'proposed':43,'previously_installed':2,
            'new_exact_blueprint_titles':38,'new_exact_gear_title_aliases':2,
            'new_accepted_catalog_links':40,'new_withheld':1,
            'new_tier_attack_fields':0,'new_star_ratio_fields':0,
            'new_formula_ready_fields':0},report['counts'])
        self.assertEqual({'weapon:nail-gun'},set(report['withheld']))
        self.assertEqual(40,len(report['by_catalog']))
        self.assertFalse(set(report['by_catalog']) & self.installed)
        for withheld in ('weapon:kam-crank','weapon:dual-fury','weapon:old-huntsman',
                         'weapon:pyroclasm-starter','weapon:pathfinder',
                         'weapon:mg4-mr-squid','weapon:mps7-focus',
                         'weapon:sr2000-jungle-camouflage'):
            self.assertNotIn(withheld,report['by_catalog'])
        self.assertEqual(52,len(server.sourced_native_star_rows()))

    def test_named_page_alias_and_partial_star_are_not_conflated(self):
        report=self.checked()
        hunter=report['by_catalog']['weapon:r500-hunter']
        self.assertEqual('R500 - Hunter 500 B.P.',hunter['public_blueprint_title'])
        self.assertEqual('R500 - Hunter (Tier 1)',hunter['public_tier_one_gear_title'])
        self.assertEqual(4,hunter['published_max_stars'])
        self.assertEqual('exact_public_tier_one_gear_title_and_native_mapping',
                         hunter['identity_proof'])
        pioneer=crosswalk.selected(report,'weapon:kam-pioneer',3,4)
        self.assertEqual(77,pioneer['gun_preset_attack'])
        self.assertIsNone(pioneer['preset_attack_radio'])
        self.assertEqual('not_disproved_by_published_max',pioneer['configuration_status'])
        self.assertIn('within the published maximum 4★',pioneer['missing_star_reason'])
        self.assertFalse(pioneer['calculation_included'])
        self.assertIsNone(crosswalk.selected(report,'weapon:nail-gun',1,1))

    def test_source_conflicts_and_wrong_native_rows_are_rejected(self):
        bad=copy.deepcopy(self.proposed)
        row=next(r for r in bad['rows'] if r['forge_id']=='weapon:kam')
        row['proposed_blueprint_id']=13421301  # Burning Rage, not KAM.
        with self.assertRaisesRegex(ValueError,'duplicate|identity|differs'):
            self.checked(proposed=bad)
        bad=copy.deepcopy(self.proposed)
        row=next(r for r in bad['rows'] if r['forge_id']=='weapon:r500-hunter')
        row['source_tier_one_gear_title']='R500 - Hunter 500 (Tier 1)'
        with self.assertRaisesRegex(ValueError,'gear alias'):
            self.checked(proposed=bad)
        bad=copy.deepcopy(self.maxima)
        row=next(r for r in bad['records'] if r['blueprint_id']==13421201)
        row['public_blueprint_title']='KAM - Crank B.P.'
        with self.assertRaisesRegex(ValueError,'Max Stars conflict'):
            self.checked(maxima=bad)

    def test_normal_build_changes_source_evidence_without_final_damage(self):
        for identity,tier,star in [('weapon:kam',3,3),
                                   ('weapon:kam-pioneer',3,4),
                                   ('weapon:r500-hunter',1,4),
                                   ('weapon:dbsg-dual-fury',5,5)]:
            with self.subTest(identity=identity):
                selected={'catalog_id':identity,'tier':tier,'stars':star}
                direct=planned_advisor.analyze({'primary':selected})
                copied=planned_advisor.analyze({'primary':dict(selected)})
                self.assertEqual(direct['weapon_reference_timing'],
                                 copied['weapon_reference_timing'])
                native=direct['weapon_reference_timing']['native_selected_tier_star']
                self.assertFalse(native['calculation_included'])
                self.assertIsNone(direct['matched_reference_component'])
                self.assertIsNone(direct['weapon_reference_timing']['rpm'])


if __name__=='__main__':
    unittest.main()
