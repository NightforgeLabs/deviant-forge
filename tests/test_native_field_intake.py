import copy
import unittest

import native_field_intake


PACKET = {'schema_version': 1,
          'source': {'steam_build_id': 26267212,
                     'archive_entry': 'game_common\\data\\future_module.pyc',
                     'payload_sha256': 'a' * 64},
          'records': [{'blueprint_id': '13451401', 'gear_id': '10451401',
                       'native_field_identifier': 'unresolved_field_7',
                       'byte_offset': 42555, 'raw_value': 720,
                       'unit_label': None}]}


class NativeIntakeTests(unittest.TestCase):
    def test_numeric_native_record_is_archived_without_semantic_promotion(self):
        result = native_field_intake.inspect(PACKET)
        self.assertEqual({'source_records': 1, 'accepted_fields': 0,
                          'withheld_fields': 1}, result['counts'])
        row = result['withheld'][0]
        self.assertEqual('unresolved_field_7', row['native_field_identifier'])
        self.assertEqual(42555, row['byte_offset'])
        self.assertEqual(26267212, int(row['steam_build_id']))
        self.assertIn('unit and calculator binding', row['reason'])
        self.assertEqual(result, native_field_intake.inspect(PACKET))

    def test_missing_provenance_and_duplicate_locations_rejected(self):
        no_hash = copy.deepcopy(PACKET)
        no_hash['source']['payload_sha256'] = None
        with self.assertRaisesRegex(ValueError, 'payload hash'):
            native_field_intake.inspect(no_hash)
        duplicated = copy.deepcopy(PACKET)
        duplicated['records'].append(copy.deepcopy(duplicated['records'][0]))
        with self.assertRaisesRegex(ValueError, 'Duplicate native field location'):
            native_field_intake.inspect(duplicated)

    def test_conflicting_unit_cannot_activate_even_with_a_binding(self):
        key = ('26267212', 'game_common\\data\\future_module.pyc',
               'unresolved_field_7')
        binding = {key: {'field': 'fire_rate_rpm', 'unit': 'rounds_per_minute',
                         'calculation_binding': 'shot_scheduler.fire_rate'}}
        with self.assertRaisesRegex(ValueError, 'source unit conflict'):
            native_field_intake.inspect(PACKET, bindings=binding)

    def test_exact_identity_and_configuration_scope_required_for_future_binding(self):
        packet = copy.deepcopy(PACKET)
        packet['records'][0]['unit_label'] = 'synthetic_unit'
        packet['records'][0]['configuration_scope'] = 'gun_base_parameter'
        key = ('26267212', 'game_common\\data\\future_module.pyc',
               'unresolved_field_7')
        binding = {'field': 'synthetic_field', 'unit': 'synthetic_unit',
                   'calculation_binding': 'synthetic_test_handler',
                   'allowed_blueprint_gear_pairs': [['13451401', '10451401']],
                   'configuration_scope': 'gun_base_parameter'}
        self.assertEqual(1, native_field_intake.inspect(packet, bindings={key: binding})
                         ['counts']['accepted_fields'])
        wrong_pair = copy.deepcopy(packet)
        wrong_pair['records'][0]['gear_id'] = '10421304'
        with self.assertRaisesRegex(ValueError, 'outside approved item scope'):
            native_field_intake.inspect(wrong_pair, bindings={key: binding})
        wrong_scope = copy.deepcopy(packet)
        wrong_scope['records'][0]['configuration_scope'] = 'crafted_tier4'
        with self.assertRaisesRegex(ValueError, 'configuration scope conflict'):
            native_field_intake.inspect(wrong_scope, bindings={key: binding})
        no_scope = copy.deepcopy(binding)
        del no_scope['allowed_blueprint_gear_pairs']
        with self.assertRaisesRegex(ValueError, 'lacks exact item scope'):
            native_field_intake.inspect(packet, bindings={key: no_scope})


if __name__ == '__main__':
    unittest.main()
