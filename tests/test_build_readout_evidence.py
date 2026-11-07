import unittest
from unittest.mock import patch

import build_source_rows
import planned_advisor


SHOCK = 'mod:weapon_mod:shock-rampage-power-surge'
TOP = 'mod:chest_mod:rejuvenating-violent'


class BuildReadoutEvidenceTests(unittest.TestCase):
    def test_exact_existing_tooltip_is_text_only_and_never_borrows_another_level(self):
        inventory = [{'level': 17, 'effects': {'catalog_id': SHOCK},
                      'stats': {'screenshot_import': {'observed_level': 17},
                                'observed_tooltip': {'source_ref': 'full-frame.png',
                                                     'attribute_lines': ['Power Surge DMG +6.0%',
                                                                         'Shock DMG +6.0%']}}}]
        with patch.object(build_source_rows.field_guide_profiles, 'preview', return_value={}):
            exact = build_source_rows.selected_rows({'primary': {'mod_id': SHOCK, 'mod_level': 17}},
                                                     object(), inventory)[0]
            wrong = build_source_rows.selected_rows({'primary': {'mod_id': SHOCK, 'mod_level': 16}},
                                                     object(), inventory)[0]
        self.assertEqual(exact['status'], 'existing_record_tooltip')
        self.assertEqual(len(exact['rows']), 2)
        self.assertFalse(exact['calculation_included'])
        self.assertEqual(exact['activation'], 'unknown')
        self.assertEqual(wrong['rows'], [])

    def test_rank_matched_rows_retain_partial_value_and_source_level(self):
        rows = [{'row_index': 0, 'raw_text': 'Crit DMG +12%',
                 'stat_type': 'crit_damage_percent', 'value': 12,
                 'confidence': 'source_checked',
                 'evidence': {'observed_level': 13, 'source_frame': 'frame-38.png'}},
                {'row_index': 1, 'raw_text': 'Row 2, rank 4: numerical value not observed',
                 'stat_type': 'unparsed', 'value': None, 'confidence': 'rank_not_observed'}]
        with patch.object(build_source_rows.field_guide_profiles, 'preview', return_value={
                'rank_derived': True, 'reviewed_exact_rows': rows}):
            result = build_source_rows.selected_rows({'top': {'mod_id': TOP, 'mod_level': 14}},
                                                     object(), [])[0]
        self.assertEqual(result['status'], 'reviewed_same_rank')
        self.assertEqual(result['rows'][0]['source_level'], 13)
        self.assertEqual(result['rows'][0]['value'], 12)
        self.assertIsNone(result['rows'][1]['value'])
        self.assertFalse(result['calculation_included'])

    def test_conflicting_copies_and_mismatched_observation_are_not_used(self):
        record = {'level': 17, 'effects': {'catalog_id': SHOCK},
                  'stats': {'screenshot_import': {'observed_level': 16},
                            'observed_tooltip': {'source_ref': 'old.png',
                                                 'attribute_lines': ['Weapon DMG +5%']}}}
        with patch.object(build_source_rows.field_guide_profiles, 'preview', return_value={}):
            mismatch = build_source_rows.selected_rows({'primary': {'mod_id': SHOCK, 'mod_level': 17}},
                                                        object(), [record])[0]
            ambiguous = build_source_rows.selected_rows({'primary': {'mod_id': SHOCK, 'mod_level': 17}},
                                                         object(), [record, record])[0]
        self.assertEqual(mismatch['status'], 'source_level_mismatch')
        self.assertEqual(mismatch['rows'], [])
        self.assertEqual(ambiguous['status'], 'ambiguous_records')
        self.assertEqual(ambiguous['rows'], [])

    def test_unanchored_reference_damage_is_withheld_but_blueprint_timing_is_shown(self):
        profile = {'style': 'Energy Style',
                   'fixed_effects': 'After taking damage, automatically reload 1 bullet (cooldown: 0.3s). Attack +10%.',
                   'source_ref': 'libfile_a194f3bfeaf081918ba9f3ea67ebb09e',
                   'rolls': [{'stat': 'Weapon DMG', 'value_percent': 42.4},
                             {'stat': 'Elemental DMG (Blaze, Frost, Shock, Blast)', 'value_percent': 17.5}]}
        selected = {'catalog_id': 'weapon:aug-electron-cloud', 'tier': 5, 'stars': 5,
                    'calibration_profile': profile}
        analysis = planned_advisor.analyze({'primary': selected})
        self.assertIsNone(analysis['matched_reference_component'])
        self.assertIsNone(analysis['weapon_reference_timing']['rpm'])
        self.assertEqual('720',analysis['weapon_reference_timing']['fire_rate_raw'])
        self.assertEqual('published_reference_rpm_interpretation',
                         analysis['weapon_reference_timing']['rpm_unit_status'])
        self.assertEqual(analysis['weapon_reference_timing']['magazine'], 40)
        self.assertIn('gear/10451401', analysis['weapon_reference_timing']['source_ref'])
        self.assertIn('blueprints/13451401', analysis['weapon_reference_timing']['blueprint_ref'])
        self.assertEqual(720,analysis['weapon_reference_timing']['native_evidence']['weapon_rpm_affix_value'])
        self.assertAlmostEqual(409.79407847556604,
            analysis['weapon_reference_timing']['native_evidence']['weapon_rpm'])
        native=analysis['weapon_reference_timing']['native_selected_tier_star']
        self.assertEqual((201.0,1.2,10451405),
                         (native['gun_preset_attack'],native['preset_attack_radio'],native['gear_id']))
        self.assertFalse(native['calculation_included'])
        self.assertIn('Selected mods, calibration and accessories may change current Attack and final damage', analysis['weapon_reference_timing']['scope'])
        self.assertIsNone(planned_advisor.analyze({'primary': {**selected, 'stars': 6}})['matched_reference_component'])
        self.assertIsNone(planned_advisor.analyze({'primary': {**selected,
            'calibration_profile': {**profile, 'rolls': profile['rolls'] +
                [{'stat': 'Crit Rate', 'value_percent': 5}]}}})['matched_reference_component'])
        self.assertIsNone(planned_advisor.analyze({'primary': {**selected,
            'accessories': {'muzzle': 'accessory:some-muzzle'}}})['matched_reference_component'])
        self.assertIsNone(planned_advisor.analyze({'primary': {**selected,
            'calibration_bonus': 'Weapon DMG +5%'}})['matched_reference_component'])
        self.assertIsNone(planned_advisor.analyze({'primary': {**selected,
            'calibration_profile': {**profile, 'extra_bonus_percent': 5}}})['matched_reference_component'])


if __name__ == '__main__':
    unittest.main()
