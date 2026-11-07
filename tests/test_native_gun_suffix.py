import copy
import json
import unittest
import threading
from http.server import ThreadingHTTPServer
from urllib.request import urlopen

import native_gun_suffix
import published_item_tier
import server


class NativeGunSuffixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sample = json.loads(native_gun_suffix.SAMPLE_PATH.read_text())
        cls.manifest = json.loads(native_gun_suffix.MANIFEST_PATH.read_text())
        cls.captures = {name: (native_gun_suffix.RAW /
            f'{name}.literal_bytes.bin').read_bytes()
            for name in ('gun_base_params_data', 'item_to_gun_mapping_data')}

    def intake(self, sample=None, manifest=None, captures=None):
        return native_gun_suffix.validate_and_stage(
            sample or self.sample, manifest or self.manifest,
            captures or self.captures, published_item_tier.ROWS)

    def test_typed_suffix_is_traceable_evidence_without_calculator_promotion(self):
        result = self.intake()
        self.assertEqual({'source_records':23,'accepted_fields':0,
                          'withheld_fields':23}, result['intake']['counts'])
        aug = [row for row in result['source_packet']['records']
               if row['catalog_id']=='weapon:aug-electron-cloud']
        self.assertEqual(11,len(aug))
        values = {row['native_field_identifier']: row for row in aug}
        self.assertEqual(40,values['weapon_magazine_size_affix_value']['raw_value'])
        self.assertEqual(26,values['weapon_range_affix_value']['raw_value'])
        self.assertEqual(720,values['weapon_rpm_affix_value']['raw_value'])
        self.assertAlmostEqual(409.79407847556604,values['weapon_rpm']['raw_value'])
        self.assertEqual((123121,'71'),
                         (values['weapon_rpm_affix']['byte_offset'],
                          values['weapon_rpm_affix']['raw_hex']))
        self.assertEqual((123122,'d005'),
                         (values['weapon_rpm_affix_value']['byte_offset'],
                          values['weapon_rpm_affix_value']['raw_hex']))
        self.assertTrue(all(row['unit_label'] is None for row in result['source_packet']['records']))
        self.assertEqual([],result['source_conflicts'])
        self.assertEqual(result,self.intake())

    def test_tampered_raw_value_or_offsets_are_rejected(self):
        sample=copy.deepcopy(self.sample)
        sample['aug_native_field_record']['typed_suffix_fields'][-1]['raw_hex']='d105'
        # The full five-row array is the actual intake source.
        sample['five_public_value_cross_checks'][0]['typed_suffix_fields'][-1]['raw_hex']='d105'
        with self.assertRaisesRegex(ValueError,'raw bytes/value conflict'):
            self.intake(sample=sample)
        sample=copy.deepcopy(self.sample)
        sample['five_public_value_cross_checks'][0]['typed_suffix_fields'][-1]['byte_offset']=123121
        with self.assertRaisesRegex(ValueError,'AUG native record conflicts'):
            self.intake(sample=sample)

    def test_cross_weapon_and_descriptor_conflicts_are_rejected(self):
        sample=copy.deepcopy(self.sample)
        sample['five_public_value_cross_checks'][0]['gear_id']=10421304
        with self.assertRaisesRegex(ValueError,'AUG native record conflicts'):
            self.intake(sample=sample)
        sample=copy.deepcopy(self.sample)
        sample['suffix_descriptor_pairs'][-1]['type_code']=34
        with self.assertRaisesRegex(ValueError,'descriptor conflict'):
            self.intake(sample=sample)
        manifest=copy.deepcopy(self.manifest)
        next(row for row in manifest['entries'] if row['entry_name'].endswith('gun_base_params_data.pyc'))['literal_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'source capture hash conflict'):
            self.intake(manifest=manifest)
        sample=copy.deepcopy(self.sample)
        sample['five_public_value_cross_checks'][1]['public_fire_rate']=999
        conflict=self.intake(sample=sample)
        self.assertEqual('weapon:socr-cosmic-visitor',
                         conflict['source_conflicts'][0]['catalog_id'])
        self.assertEqual(0,conflict['intake']['counts']['accepted_fields'])

    def test_api_exposes_native_fields_as_evidence_without_damage_binding(self):
        http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        worker=threading.Thread(target=http.serve_forever,daemon=True)
        worker.start()
        try:
            base=f'http://127.0.0.1:{http.server_address[1]}'
            with urlopen(base+'/api/native-gun-suffix/weapon%3Aaug-electron-cloud') as response:
                result=json.load(response)
            self.assertEqual('decoded_native_fields_evidence_only',result['status'])
            self.assertFalse(result['calculation_included'])
            self.assertEqual(11,len(result['records']))
            self.assertEqual('7ba048990ee6da61bd37bd82b00e1a11aa8f4df792e429ebae5342a91f505212',
                             result['source']['payload_sha256'])
            with urlopen(base+'/api/native-gun-suffix/weapon%3Akam-crank') as response:
                other=json.load(response)
            self.assertEqual('not_in_bounded_sample',other['status'])
            self.assertEqual([],other['records'])
        finally:
            http.shutdown();http.server_close();worker.join(timeout=2)


if __name__=='__main__':
    unittest.main()
