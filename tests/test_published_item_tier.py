import unittest
import json
import threading
import copy
import hashlib
import tempfile
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import published_item_tier
import published_reference_model
import server
import source_intake


class ItemTierTests(unittest.TestCase):
    def test_staged_raw_intake_accepts_timing_and_rejects_unknown_units(self):
        report = published_item_tier.TIER1_INTAKE
        self.assertEqual({'identities':5,'accepted_fields':8,
                          'accepted_explicit_rpm_labels':3,
                          'conditional_fields':2,
                          'rejected_fields':65},report['counts'])
        self.assertEqual({'fire_rate_rpm','magazine_capacity'},
                         {row['field'] for row in report['accepted']})
        self.assertEqual({'shot_scheduler.fire_rate','finite_ammo.magazine_capacity'},
                         {row['calculation_binding'] for row in report['accepted']})
        self.assertTrue(all(row['blueprint_id'] and row['gear_id'] and row['source_url'] and
                            row['raw_archive_sha256'] and row['capture_date_utc']
                            for row in report['accepted']+report['conditional']+report['rejected']))
        self.assertTrue(all(row['local_identity']['status']=='identity_only' and
                            row['local_identity']['steam_build_id']=='26267212'
                            for row in report['accepted']+report['conditional']+report['rejected']))
        aug=published_item_tier.TIER1_TIMING['weapon:aug-electron-cloud']
        conditional=published_item_tier.TIER1_CONDITIONAL_TIMING['weapon:aug-electron-cloud']
        self.assertNotIn('fire_rate_rpm',aug)
        self.assertEqual(720,conditional['fire_rate_rpm']['value'])
        self.assertEqual(40,aug['magazine_capacity']['value'])
        self.assertIn('Displayed DMG unit',next(row['reason'] for row in report['rejected']
            if row['catalog_id']=='weapon:aug-electron-cloud' and row['source_label']=='DMG'))
        self.assertIn('score',next(row['reason'] for row in report['rejected']
            if row['catalog_id']=='weapon:aug-electron-cloud' and row['source_label']=='Reload Speed'))
        with self.assertRaisesRegex(ValueError,'explicit Fire Rate-as-RPM hypothesis'):
            published_item_tier.explicit_page_scenario('weapon:aug-electron-cloud',1,
                projectiles_per_shot=1)
        baseline,_=published_item_tier.explicit_page_scenario('weapon:aug-electron-cloud',1,
            projectiles_per_shot=1,assume_fire_rate_as_rpm=True)
        self.assertEqual(720,baseline['stats']['fire_rate'])
        self.assertEqual(40,baseline['stats']['magazine_capacity'])
        self.assertEqual('Fire Rate',baseline['source_timing']['fire_rate_rpm']['source_label'])
        self.assertEqual('published_reference_rpm_interpretation',
                         baseline['source_timing']['fire_rate_rpm']['unit_evidence'])

    def test_staged_intake_repeat_conflict_and_rollback(self):
        raw=Path(published_item_tier.__file__).parent/'evidence_packets/five-weapon-tier1-raw-v1.json'
        local=Path(published_item_tier.__file__).parent/'evidence_packets/local-blueprint-identity-v1.json'
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'report.json'
            first=source_intake.write_report(raw,published_item_tier.ROWS,output,
                                             local_identity_path=local)
            before=output.read_bytes()
            self.assertEqual(hashlib.sha256(raw.read_bytes()).hexdigest(),
                             first['source_archive_sha256'])
            source_intake.write_report(raw,published_item_tier.ROWS,output,
                                       local_identity_path=local)
            self.assertEqual(before,output.read_bytes())
            corrupt=copy.deepcopy(published_item_tier.TIER1_RAW_BATCH)
            corrupt['rows'][0]['raw_fields']['Fire Rate']='999'
            bad=Path(directory)/'conflict.json'
            bad.write_text(json.dumps(corrupt))
            with self.assertRaisesRegex(ValueError,'timing source conflict'):
                source_intake.write_report(bad,published_item_tier.ROWS,output,
                                           local_identity_path=local)
            self.assertEqual(before,output.read_bytes(),'failed import must preserve prior report')
            self.assertFalse(output.with_name(output.name+'.tmp').exists())
            mixed=copy.deepcopy(published_item_tier.TIER1_RAW_BATCH)
            mixed['rows'][1]['gear_id']='10421304'
            with self.assertRaisesRegex(ValueError,'identity conflict'):
                source_intake.intake_tier1(mixed,published_item_tier.ROWS)
            local_conflict=copy.deepcopy(published_item_tier.LOCAL_IDENTITY_SAMPLE)
            local_conflict['first_decoded_identity']['gear_id']=10421304
            with self.assertRaisesRegex(ValueError,'Local blueprint/gear identity conflicts'):
                source_intake.intake_tier1(published_item_tier.TIER1_RAW_BATCH,
                    published_item_tier.ROWS,local_identity=local_conflict)
    def test_aug_raw_labels_bind_sampled_pages_without_unit_inference(self):
        checked=published_item_tier.AUG_RAW_VALIDATION
        self.assertEqual(['10451401','10451404'],checked['sampled_gear_pages'])
        self.assertEqual(12,checked['source_native_damage_cells'])
        self.assertFalse(checked['reload_seconds_supported'])
        self.assertFalse(checked['damage_per_projectile_supported'])
        conflicting=copy.deepcopy(published_item_tier.AUG_RAW_SAMPLE)
        conflicting['gear_pages'][1]['raw_star_values']['1★']='134'
        with self.assertRaisesRegex(ValueError,'DMG/star values conflict'):
            published_item_tier.validate_aug_raw_sample(conflicting)

    def test_five_raw_tier1_pages_preserve_blueprint_spelling_and_cells(self):
        checked=published_item_tier.TIER1_RAW_VALIDATION
        self.assertEqual(5,checked['named_tier1_families'])
        self.assertEqual(30,checked['source_native_star_cells'])
        self.assertFalse(checked['reload_seconds_supported'])
        self.assertFalse(checked['per_projectile_unit_supported'])
        source=next(row for row in published_item_tier.TIER1_RAW_BATCH['rows']
                    if row['catalog_id'].startswith('weapon:qbj97'))
        self.assertIn('Fiery',source['blueprint_title'])
        self.assertIn('Firey',source['gear_title'])
        conflict=copy.deepcopy(published_item_tier.TIER1_RAW_BATCH)
        conflict['rows'][0]['raw_star_damage']['1★']='46'
        with self.assertRaisesRegex(ValueError,'star-cell conflict'):
            published_item_tier.validate_tier1_raw_batch(conflict)

    def test_exact_named_tier_pages_do_not_interpolate_or_mix_kam_names(self):
        self.assertEqual(5,len(published_item_tier.ROWS))
        for weapon_id in published_item_tier.ROWS:
            self.assertEqual([1,2,3,4,5],sorted(int(t) for t in published_item_tier.ROWS[weapon_id]['tiers']))
            self.assertIsNotNone(published_item_tier.lookup(weapon_id,3)['displayed_damage'])
        self.assertEqual(130,published_item_tier.VALIDATION['star_cells'])
        self.assertIsNone(published_item_tier.lookup('weapon:kam-crank',4)['displayed_damage'])
        self.assertEqual('KAM - Burning Rage (Tier 4)',
                         published_item_tier.PACKET['rejected_mixed_identity_example']['tier_4']['title'])

    def test_blueprint_linked_tier_values_for_all_five_weapons(self):
        expected = {
            'weapon:socr-cosmic-visitor': ('13413301', [45,70,111,174,264]),
            'weapon:aug-electron-cloud': ('13451401', [34,53,84,132,201]),
            'weapon:compound-bow-the-burden-of-betrayal': ('13742201', [133,204,326,510,775]),
            'weapon:sn700-finale': ('13512301', [182,280,448,700,1064]),
            'weapon:qbj97-fiery-trees-and-silver-flowers': ('13641201', [35,54,86,134,204]),
        }
        for identity, (blueprint, damages) in expected.items():
            row = published_item_tier.ROWS[identity]
            self.assertEqual(blueprint, row['blueprint_id'])
            self.assertEqual(damages, [published_item_tier.lookup(identity,tier)['displayed_damage']
                                       for tier in range(1,6)])
            for tier in range(1,6):
                item = row['tiers'][str(tier)]
                self.assertIn(item['item_id'], row['blueprint_craft_item_ids'])
                self.assertEqual(f"{row['name']} (Tier {tier})", item['page_title'])

    def test_cross_weapon_title_craft_link_and_damage_conflicts_rejected(self):
        for mutation,pattern in (
            (lambda p:p['rows']['weapon:aug-electron-cloud']['tiers']['4'].update(page_title='KAM - Burning Rage (Tier 4)'),'title conflicts'),
            (lambda p:p['rows']['weapon:aug-electron-cloud']['blueprint_craft_item_ids'].remove('10451404'),'not in named blueprint'),
            (lambda p:p['rows']['weapon:aug-electron-cloud']['tiers']['4'].update(wikily_url='https://wikily.gg/once-human/items/10421304'),'conflicts with item ID'),
            (lambda p:p['rows']['weapon:aug-electron-cloud']['tiers']['4']['star_damage'].update({'1':134}),'one-star damage conflict'),
            (lambda p:p['rows']['weapon:aug-electron-cloud']['calibration_context'].update(official_removal_source='https://example.com/guess'),'calibration chronology')):
            packet=copy.deepcopy(published_item_tier.PACKET)
            mutation(packet)
            with self.assertRaisesRegex(ValueError,pattern):
                published_item_tier.validate_packet(packet)

    def test_aug_explicit_page_damage_unit_scenario_computes_only_supported_metrics(self):
        def build(tier):
            return published_reference_model.build({'weapon':{'catalog_id':'weapon:aug-electron-cloud',
                'tier':tier,'item_page_scenario':{'assume_displayed_damage_per_projectile':True,
                                                   'assume_fire_rate_as_rpm':True,
                                                   'projectiles_per_shot':1}}})
        low, high=build(1),build(4)
        self.assertEqual(34,low['direct_only']['reference_hit'])
        self.assertEqual(132,high['direct_only']['reference_hit'])
        self.assertEqual(408,low['direct_only']['firing_damage_per_second'])
        self.assertEqual(1584,high['direct_only']['firing_damage_per_second'])
        self.assertIsNone(low['direct_only']['reload_cycle_damage_per_second'])
        self.assertTrue(any('Classic calibration level removed' in gap for gap in low['unresolved']))
        self.assertTrue(any('per-projectile damage unit' in gap for gap in low['unresolved']))
        self.assertEqual('10451404',high['weapon_source_native_baseline']['source_item_id'])
        self.assertFalse(high['current_game_verified'])
        self.assertEqual('removed_before_weapon_release',
                         published_item_tier.ROWS['weapon:aug-electron-cloud']['calibration_context']['legacy_level'])

    def test_unknown_upgrade_unit_or_tier_cannot_be_filled(self):
        common={'catalog_id':'weapon:aug-electron-cloud','tier':4}
        with self.assertRaisesRegex(ValueError,'explicit'):
            published_reference_model.build({'weapon':{**common,'item_page_scenario':{}}})
        with self.assertRaisesRegex(ValueError,'calibration scaling'):
            published_reference_model.build({'weapon':{**common,'calibration':1,
                'item_page_scenario':{'assume_displayed_damage_per_projectile':True,'projectiles_per_shot':1}}})
        with self.assertRaisesRegex(ValueError,'exact item page damage'):
            published_reference_model.build({'weapon':{**common,'tier':5,'stars':2,
                'item_page_scenario':{'assume_displayed_damage_per_projectile':True,'projectiles_per_shot':1}}})
        with self.assertRaisesRegex(ValueError,'projectile count'):
            published_reference_model.build({'weapon':{**common,
                'item_page_scenario':{'assume_displayed_damage_per_projectile':True}}})
        supported=published_reference_model.build({'weapon':{**common,'stars':2,
            'item_page_scenario':{'assume_displayed_damage_per_projectile':True,'projectiles_per_shot':1}}})
        self.assertEqual(139,supported['direct_only']['reference_hit'])

    def test_selected_fixed_layout_mod_changes_explicit_item_page_result(self):
        weapon={'catalog_id':'weapon:aug-electron-cloud','tier':1,
                'item_page_scenario':{'assume_displayed_damage_per_projectile':True,
                                      'assume_fire_rate_as_rpm':True,
                                      'projectiles_per_shot':1}}
        plain=published_reference_model.build({'weapon':weapon})
        with_mod=published_reference_model.build({'weapon':weapon,
            'mods':[{'catalog_id':'mod:weapon_mod:flame-resonance-general','level':8}]})
        self.assertEqual(34,plain['direct_only']['reference_hit'])
        self.assertAlmostEqual(34,with_mod['direct_only']['reference_hit'])
        self.assertIn('explicit_item_page',with_mod['direct_only']['model'])
        self.assertTrue(any('exact native configured position' in gap for gap in with_mod['unresolved']))

    def test_api_catalog_and_conditional_page_comparison(self):
        http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        worker=threading.Thread(target=http.serve_forever,daemon=True);worker.start()
        try:
            base=f'http://127.0.0.1:{http.server_address[1]}'
            with urlopen(base+'/api/published-reference-weapons') as response:
                rows=json.load(response)['weapons']
            self.assertEqual(138,len(rows))
            aug=next(row for row in rows if row['catalog_id']=='weapon:aug-electron-cloud')
            self.assertEqual([1,2,3,4,5],aug['item_page_tiers'])
            self.assertFalse(aug['numeric'])
            def side(tier):
                return {'weapon':{'catalog_id':'weapon:aug-electron-cloud','tier':tier,
                    'item_page_scenario':{'assume_displayed_damage_per_projectile':True,
                                          'assume_fire_rate_as_rpm':True,
                                          'projectiles_per_shot':1}}}
            without_rpm=side(1)
            del without_rpm['weapon']['item_page_scenario']['assume_fire_rate_as_rpm']
            denied=Request(base+'/api/published-reference-compare',
                           json.dumps({'left':without_rpm,'right':side(4)}).encode(),
                           {'Content-Type':'application/json'},method='POST')
            with self.assertRaises(HTTPError) as blocked:
                urlopen(denied)
            self.assertEqual(400,blocked.exception.code)
            self.assertIn('explicit Fire Rate-as-RPM hypothesis',
                          blocked.exception.read().decode())
            payload=json.dumps({'left':side(1),'right':side(4)}).encode()
            request=Request(base+'/api/published-reference-compare',payload,
                            {'Content-Type':'application/json'},method='POST')
            with urlopen(request) as response:
                result=json.load(response)
            self.assertAlmostEqual(132/34,result['right_over_left_reference_ratios']['reference_hit'])
            self.assertIsNone(result['right_over_left_reference_ratios']['reload_cycle_damage_per_second'])
            self.assertFalse(result['game_winner_established'])
        finally:
            http.shutdown();http.server_close();worker.join(timeout=2)


if __name__=='__main__': unittest.main()
