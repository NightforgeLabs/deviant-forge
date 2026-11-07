import copy
import json
from pathlib import Path
import unittest

import build_damage
import catalog
import mechanics
from tools.import_official_mod_cards import import_cards, import_native_main_effects
from tools.audit_detail_magnitudes import audit

ROOT=Path(__file__).resolve().parents[1]


class BuildDamageTests(unittest.TestCase):
    def setUp(self):
        self.left={'primary':{'catalog_id':'weapon:sn700'},
                   'bottoms':{'catalog_id':'armor:hot-dog-shorts',
                              'mod_id':'mod:pants_mod:distant-strike-survival','mod_level':10}}
        self.right=copy.deepcopy(self.left)
        self.right['bottoms']['mod_id']='mod:pants_mod:elemental-resonance-aero'
        self.right['bottoms']['mod_level']=17
        self.encounter={'duration_seconds':40,'distance_meters':25,'crit_share':.02,
                        'weakspot_share':.8,'aerial_hit':False,'same_elevation':True,'target_below_within_5m':False,
                        'hp_consumed':False,'stamina_spent':False,'nearby_kills':0,
                        'prior_magazine_elemental_events':0,'scenario':'PvE'}

    def test_official_importer_is_idempotent_and_detects_conflict(self):
        manifest=json.loads((ROOT/'research/official_mod_cards.json').read_text())
        numeric=json.loads((ROOT/'catalog_numeric.json').read_text())
        base=json.loads((ROOT/'catalog.json').read_text())
        current,added=import_cards(manifest,numeric,base,(ROOT/manifest['local_image']).read_bytes())
        self.assertEqual(added,[])
        self.assertEqual(current,numeric)
        native=json.loads((ROOT/'research/native_main_effects.json').read_text())
        self.assertEqual(import_native_main_effects(native,numeric)[1],[])
        changed_native=copy.deepcopy(native)
        changed_native['cards'][0]['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'image hash changed'):
            import_native_main_effects(changed_native,numeric)
        wrong=copy.deepcopy(numeric)
        wrong['profiles']['mod:pants_mod:elemental-resonance-aero']['17']['attributes'][0]['value_percent']=6.1
        with self.assertRaisesRegex(ValueError,'Conflicting numeric evidence'):
            import_cards(manifest,wrong,base,(ROOT/manifest['local_image']).read_bytes())
        self.assertGreater(audit()['candidate_rows'],0,'source audit remains reproducible')
        self.assertEqual(json.loads((ROOT/'catalog_effect_magnitudes.json').read_text())['candidate_rows'],0)
        self.assertEqual(catalog.resolve('mod:pants_mod:elemental-resonance-aero',17)['effect_magnitude_candidates'],[])

    def test_new_profiles_keep_shiny_main_separate_and_semantics_exact(self):
        aero=catalog.resolve('mod:pants_mod:elemental-resonance-aero',17)
        down=catalog.resolve('mod:boots_mod:ferocious-charge-downstar',17)
        self.assertEqual(aero['attribute_coverage'],down['attribute_coverage'])
        self.assertEqual(aero['attribute_coverage'],'complete')
        self.assertEqual([(a['value_percent'],a.get('conditional_bonus_percent')) for a in aero['known_attributes']],
                         [(6,3),(15,7.5),(7.5,None),(2.4,None)])
        self.assertEqual(aero['known_attributes'][0]['condition'],'aerial hit')
        self.assertEqual(down['known_attributes'][0]['condition'],'target lower than player within 5 meters')
        self.assertIsNone(aero['verified_main_effect'])
        self.assertIsNone(aero['verified_shiny_main_effect'])
        shiny=catalog.resolve('mod:pants_mod:elemental-resonance-aero',17,shiny=True)
        self.assertEqual(shiny['verified_shiny_main_effect']['flash_effect'],'Elemental DMG +2%')
        self.assertEqual(catalog.coverage()['exact_mod_level_profiles'],68)

    def test_capabilities_are_exact_identity_and_separate_components(self):
        crank=mechanics.weapon_capabilities('weapon:kam-crank')['capabilities']
        self.assertEqual(crank['status_damage'],'present')
        self.assertEqual(crank['triggered_damage'],'absent_in_record')
        boom=mechanics.weapon_capabilities('weapon:kvd-boom-boom')['capabilities']
        self.assertEqual((boom['triggered_damage'],boom['status_damage']),('present','present'))
        unknown=mechanics.weapon_capabilities('weapon:awm')['capabilities']
        self.assertEqual((unknown['triggered_damage'],unknown['status_damage']),('unknown','unknown'))

    def test_real_saved_mod_swap_independent_damage_arithmetic_and_range_flip(self):
        far=build_damage.compare_saved(self.left,self.right,self.encounter)
        self.assertFalse(far['eligible'])
        self.assertFalse(far['winner_established'])
        self.assertEqual(far['rows'],[])
        self.assertTrue(any('No sourced, explicit-setting weapon reference' in x
                            for x in far['blockers']))
        near=build_damage.compare_saved(self.left,self.right,{**self.encounter,'distance_meters':10})
        self.assertFalse(near['winner_established'])
        self.assertEqual(near['rows'],[])

    def test_common_mod_interaction_and_unresolved_events_block(self):
        common={'catalog_id':'armor:agent-shoes','mod_id':'mod:boots_mod:against-all-odds-precision','mod_level':7}
        left={**self.left,'shoes':common};right={**self.right,'shoes':common}
        result=build_damage.compare_saved(left,right,self.encounter)
        self.assertFalse(result['eligible'])
        self.assertFalse(result['winner_established'])
        self.assertEqual(result['rows'],[])
        elemental=build_damage.compare_saved(self.left,self.right,{**self.encounter,'prior_magazine_elemental_events':2})
        self.assertFalse(elemental['winner_established'])
        self.assertEqual(elemental['rows'],[])
        aerial=build_damage.compare_saved(self.left,self.right,{**self.encounter,'aerial_hit':True})
        self.assertFalse(aerial['winner_established'])  # official Aero suffix magnitude is unresolved
        self.assertEqual(aerial['rows'],[])

    def test_actual_craft_settings_do_not_inherit_unlabeled_reference_numbers(self):
        left=copy.deepcopy(self.left);right=copy.deepcopy(self.right)
        left['primary'].update(tier=5,stars=3,calibration_blueprint='Rapid Sniper Rifle',
                               calibration_bonus='Attack +40%')
        right['primary']=copy.deepcopy(left['primary'])
        result=build_damage.compare_saved(left,right,self.encounter)
        self.assertFalse(result['winner_established'])
        self.assertTrue(any('No sourced, explicit-setting weapon reference' in reason
                            for reason in result['blockers']))


if __name__=='__main__':unittest.main()
