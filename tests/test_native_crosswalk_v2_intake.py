import copy
import json
import unittest

import catalog
import planned_advisor as plan
import native_crosswalk_v2_intake as v2
import server


class NativeCrosswalkV2Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proposal = json.loads((v2.ROOT / v2.SOURCES['proposal'][0]).read_text())
        cls.native = json.loads((v2.ROOT / v2.SOURCES['native'][0]).read_text())
        cls.pages = json.loads((v2.ROOT / v2.SOURCES['pages'][0]).read_text())
        cls.prior = plan.NATIVE_INSTALLED_IDENTITIES | set(plan.NATIVE_CROSSWALK_EVIDENCE['by_catalog'])

    def check(self, proposal=None, native=None, pages=None):
        return v2.validate(proposal or self.proposal, native or self.native,
                           pages or self.pages, catalog.ENTRIES,
                           plan.NATIVE_PARTIAL_EVIDENCE, self.prior)

    def test_accepted_links_and_identity_only(self):
        report = self.check()
        self.assertEqual(10, report['counts']['new_accepted_catalog_links'])
        self.assertEqual(85, len(self.prior | set(report['by_catalog'])))
        self.assertEqual(52, len(server.sourced_native_star_rows()))
        self.assertEqual({'weapon:aa12'}, set(report['withheld']))
        self.assertNotIn('weapon:akm', report['by_catalog'])
        self.assertNotIn('weapon:flare-gun', report['by_catalog'])
        scar = v2.selected(report, 'weapon:scar', 1, 2)
        self.assertEqual(13411101, scar['blueprint_id'])
        self.assertEqual(41, scar['gun_preset_attack'])
        self.assertFalse(scar['calculation_included'])
        mps = v2.selected(report, 'weapon:mps7-chaos-domain', 1, 1)
        self.assertEqual(13332401, mps['blueprint_id'])
        self.assertIsNone(mps['gun_preset_attack'])
        self.assertIsNone(mps['preset_attack_radio'])
        self.assertEqual(6, mps['published_max_stars'])
        self.assertFalse(mps['calculation_included'])

    def test_source_identity_and_native_conflicts_rejected(self):
        pages = copy.deepcopy(self.pages)
        next(r for r in pages['records'] if r['blueprint_id'] == 13411101)['gear_title'] = 'KAM (Tier 1)'
        with self.assertRaises(ValueError): self.check(pages=pages)
        proposal = copy.deepcopy(self.proposal)
        next(r for r in proposal['rows'] if r['forge_id'] == 'weapon:scar')['proposed_tier_one_gear_id'] = 10421101
        with self.assertRaises(ValueError): self.check(proposal=proposal)
        native = copy.deepcopy(self.native)
        row = next(r for r in native['records'] if r['blueprint_id'] == 13332401)
        row['tiers'][0]['typed_equip_fields']['blueprint_no']['value'] = 1
        with self.assertRaises(ValueError): self.check(native=native)

    def test_selected_plan_does_not_mutate_saved_data(self):
        slot = {'catalog_id': 'weapon:mps7-chaos-domain', 'tier': 1, 'stars': 6}
        before = copy.deepcopy(slot)
        server.validate_planned_slots({'primary': slot})
        selected = plan._weapon_reference_timing({'primary': slot})['native_selected_tier_star']
        self.assertEqual(before, slot)
        self.assertIsNone(selected['gun_preset_attack'])
        with self.assertRaises(ValueError):
            server.validate_planned_slots({'primary': {**slot, 'stars': 7}})


if __name__ == '__main__': unittest.main()
