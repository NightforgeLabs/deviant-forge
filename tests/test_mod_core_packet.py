import copy
import unittest

import catalog
import component_compare
import mod_core_packet


class MainModPacketTests(unittest.TestCase):
    def test_v3_blocks_superseded_legacy_rules_even_with_opt_in(self):
        for identity in ('mod:chest_mod:rejuvenating', 'mod:chest_mod:head-guard',
                         'mod:mask_mod:retrusion-explosion', 'mod:mask_mod:gunslinger',
                         'mod:mask_mod:first-electrocution'):
            rows, notes, binding = mod_core_packet.rows_for(
                identity, 10, context={'core_candidate_opt_in': True})
            self.assertEqual(rows, [], identity)
            self.assertIsNone(binding, identity)
            self.assertTrue(any('superseded' in note for note in notes), identity)
        statuses = mod_core_packet.coverage()['v3_applicability_statuses']
        self.assertEqual(statuses['blocked_legacy_superseded'], 5)
        self.assertEqual(statuses['blocked_source_conflict'], 5)

    def test_packet_coverage_is_not_current_numeric_coverage(self):
        counts = mod_core_packet.coverage()
        self.assertEqual((counts['catalog_identities_in_packet'], counts['typed_templates'],
                          counts['partial_templates'], counts['unknown_core_templates'],
                          counts['conflicting_templates'], counts['missing_effect_text']),
                         (985, 652, 198, 38, 5, 92))
        self.assertEqual(counts['selectable_mod_identities'],984)
        self.assertEqual((counts['exact_level_observations'], counts['ordinary_exact_observations'],
                          counts['variant_kind_unknown_observations'], counts['shiny_preview_observations']),
                         (52, 7, 44, 1))
        self.assertEqual(counts['opt_in_pool_template_scenarios_at_level_10'], 225)
        self.assertEqual(counts['whole_dps_certified'], 0)
        self.assertEqual(catalog.coverage()['selectable_mod_variants'], counts['selectable_mod_identities'])

    def test_community_primary_strength_is_opt_in_and_unbound_to_level(self):
        item={'catalog_id':'mod:helmet_mod:elemental-havoc-lunar','level':10}
        snapshot=copy.deepcopy(item)
        default=component_compare.compare({'attributes':[]},item)
        opted=component_compare.compare({'attributes':[]},item,{'core_candidate_opt_in':True})
        self.assertEqual(item,snapshot)
        self.assertFalse(any(row.get('rule_id','').endswith(':core:0') for row in default['right']['trace']))
        core=[row for row in opted['right']['trace'] if ':core:' in str(row.get('rule_id'))]
        self.assertEqual(len(core),2)
        self.assertEqual(core[0]['applied_range_percent'],[10,10])
        self.assertEqual(core[1]['applied_range_percent'],[0,10])
        self.assertTrue(any('not bound to selected level' in note for note in opted['missing']))
        self.assertFalse(opted['game_winner_established'])
        hp=component_compare.compare({'attributes':[]},item,
                        {'core_candidate_opt_in':True,'hp_percent':95})
        hp_core=[row for row in hp['right']['trace'] if ':core:' in str(row.get('rule_id'))]
        self.assertEqual(hp_core[1]['applied_range_percent'],[10,10])
        self.assertTrue(any('HP is a snapshot' in note for note in hp['missing']))

    def test_unknown_timing_and_unmapped_stat_do_not_become_passive(self):
        rows,notes,binding=mod_core_packet.rows_for('mod:helmet_mod:first-move-advantage-crescent',10,
                            context={'core_candidate_opt_in':True})
        self.assertEqual(binding['operator'],'event_timed_modifier')
        self.assertEqual([row['name'] for row in rows],['Crit DMG'])
        self.assertEqual(rows[0]['condition'],'event:reload active')
        self.assertTrue(any('crit_rate_percent' in note for note in notes))
        self.assertTrue(any('timeline' in note for note in notes))
        rows,notes,_=mod_core_packet.rows_for('mod:helmet_mod:precise-strike-crescent',10,
                            context={'core_candidate_opt_in':True})
        self.assertEqual(rows[0]['range_percent'],[0,36])
        self.assertTrue(any('stack count unresolved' in note for note in notes))

    def test_exact_existing_rule_not_double_counted_and_preview_withheld(self):
        item={'catalog_id':'mod:gloves_mod:elemental-overload-resonance','level':9}
        result=component_compare.compare({'attributes':[]},item)
        main=[row for row in result['right']['trace'] if row.get('rule_id') == 'elemental-overload-resonance-lv9']
        self.assertEqual(len(main),1)
        self.assertEqual(main[0]['applied_range_percent'],[18,18])
        rows,notes,_=mod_core_packet.rows_for('mod:boots_mod:ferocious-charge-downstar',17,shiny=True)
        self.assertFalse(rows)
        self.assertTrue(any('preview' in note for note in notes))
        rows,notes,_=mod_core_packet.rows_for('mod:chest_mod:critical-rescue-battle',12)
        self.assertFalse(rows)
        self.assertTrue(any('variant kind' in note for note in notes))

    def test_unsupported_event_operator_and_bad_opt_in_are_explicit(self):
        with self.assertRaisesRegex(ValueError,'Core candidate opt-in'):
            component_compare.compare({}, {}, {'core_candidate_opt_in':'yes'})
        rows,notes,binding=mod_core_packet.rows_for('mod:weapon_mod:shattering-ice-deviant-energy',10,
                           context={'core_candidate_opt_in':True})
        self.assertFalse(rows)
        self.assertIsNotNone(binding)
        self.assertTrue(any('separate event' in note for note in notes))
        rows,notes,_=mod_core_packet.rows_for('mod:weapon_mod:shield-breaker-general',10,
                           context={'core_candidate_opt_in':True})
        self.assertFalse(rows)
        self.assertTrue(any('conflicting' in note for note in notes))

    def test_proximity_count_requires_matching_rule_radius(self):
        identity='mod:boots_mod:against-all-odds-general'
        # Select a compiled proximity rule directly, independent of this named item's suffix.
        entry=next(row for row in mod_core_packet.ENTRIES.values()
                   if (row['primary'].get('rule') or {}).get('operator')=='proximity_conditional_modifier')
        identity=entry['catalog_id']
        radius=entry['primary']['rule']['distance_meters']
        rows,notes,_=mod_core_packet.rows_for(identity,10,context={
            'core_candidate_opt_in':True,'enemies_within_distance':0})
        self.assertTrue(rows)
        self.assertTrue(any('specifically within' in note for note in notes))
        rows,notes,_=mod_core_packet.rows_for(identity,10,context={
            'core_candidate_opt_in':True,'proximity':{'radius_meters':radius,'enemy_count':0}})
        self.assertFalse(any('specifically within' in note for note in notes))

    def test_unentered_state_is_distinct_from_explicit_inactive(self):
        identity='mod:helmet_mod:mag-expansion'
        unknown,notes,_=mod_core_packet.rows_for(identity,10,
                            context={'core_candidate_opt_in':True})
        inactive,_,_=mod_core_packet.rows_for(identity,10,
                            context={'core_candidate_opt_in':True,'states':[]})
        active,_,_=mod_core_packet.rows_for(identity,10,
                            context={'core_candidate_opt_in':True,'states':['magazine_empty']})
        self.assertEqual(unknown[0]['range_percent'],[0,30])
        self.assertTrue(any('unentered' in note for note in notes))
        self.assertEqual(inactive[0]['range_percent'],[0,0])
        self.assertEqual(active[0]['value_percent'],30)

    def test_exact_held_partial_preserves_base_without_assuming_stacks(self):
        identity='mod:boots_mod:against-all-odds-deviant-energy'
        rows,notes,_=mod_core_packet.rows_for(identity,12)
        self.assertFalse(rows)
        self.assertTrue(any('variant kind' in note for note in notes))
        candidate,notes,binding=mod_core_packet.rows_for(identity,12,
                            context={'core_candidate_opt_in':True})
        self.assertEqual([row['name'] for row in candidate],['Weapon DMG','Status DMG'])
        self.assertEqual([row['value_percent'] for row in candidate],[10,10])
        self.assertEqual(binding['numeric_scope'],'unbound_level_candidate')
        self.assertTrue(any('additional effect' in note for note in notes))


if __name__=='__main__':
    unittest.main()
