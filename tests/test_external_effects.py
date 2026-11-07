import unittest

import external_effects
import mod_rolls


def effect(**changes):
    value = {'source_kind': 'food', 'name': 'Observed food',
             'stat_type': 'weapon_damage_percent', 'value_percent': 10,
             'source_note': 'Synthetic test observation', 'activation': 'observed_active',
             'apply_hypothesis': True, 'baseline_excludes_effect': True,
             'active_for_interval': True}
    value.update(changes)
    return value


class ExternalEffectsTests(unittest.TestCase):
    def test_multiple_distinct_types_are_order_independent_and_deduplicated(self):
        weapon=effect(name='Meal', stat_type='weapon_damage_percent',value_percent=10)
        status=effect(source_kind='deviation',name='Companion',stat_type='status_damage_percent',value_percent=20)
        first=external_effects.resolve_many([weapon,status],[],assume_compatible_sources=True)
        reversed_result=external_effects.resolve_many([status,weapon],[],assume_compatible_sources=True)
        self.assertEqual(first['rows'],reversed_result['rows'])
        self.assertEqual(len(first['rows']),2)
        self.assertEqual(len([d for d in external_effects.resolve_many([weapon,status,weapon],[],assume_compatible_sources=True)['details'] if d['applied']]),2)
        self.assertEqual(mod_rolls.aggregate(first['rows'])['percent_by_type']['weapon_damage_percent'],10)
        self.assertEqual(mod_rolls.aggregate(first['rows'])['percent_by_type']['status_damage_percent'],20)
        with self.assertRaisesRegex(ValueError,'Conflicting readings'):
            external_effects.resolve_many([weapon,{**weapon,'value_percent':11}],[])

    def test_multiple_sources_and_same_bucket_require_separate_opt_ins(self):
        food=effect(name='Meal')
        drink=effect(source_kind='drink',name='Drink',value_percent=5)
        conflict=external_effects.resolve_many([food,drink],[])
        self.assertFalse(any(d['applied'] for d in conflict['details']))
        self.assertTrue(conflict['blocking'])
        same_bucket=external_effects.resolve_many([food,drink],[],assume_compatible_sources=True)
        self.assertFalse(any(d['applied'] for d in same_bucket['details']))
        both=external_effects.resolve_many([food,drink],[],assume_compatible_sources=True,assume_same_stat_additive=True)
        self.assertEqual(mod_rolls.aggregate(both['rows'])['percent_by_type']['weapon_damage_percent'],15)
        selected=external_effects.resolve_many([food],[{'stat_type':'weapon_damage_percent'}])
        self.assertFalse(selected['details'][0]['applied'])
        inactive=external_effects.resolve_many([effect(activation='inactive',apply_hypothesis=False)],[])
        self.assertEqual(inactive['rows'],[])
        unknown=external_effects.resolve_many([effect(activation='unknown',apply_hypothesis=False)],[])
        self.assertFalse(unknown['details'][0]['applied'])

    def test_unsupported_defense_does_not_erase_known_offense(self):
        weapon=effect(name='Meal',stat_type='weapon_damage_percent',value_percent=10)
        healing=effect(source_kind='deviation',name='Support companion',
                       stat_type='healing_or_shield_unmodeled',value_percent=20)
        result=external_effects.resolve_many([weapon,healing],[])
        self.assertEqual(len(result['rows']),2)
        self.assertEqual(sum(detail['applied'] for detail in result['details']),1)
        self.assertEqual(mod_rolls.aggregate(result['rows'])['percent_by_type']['weapon_damage_percent'],10)
        self.assertFalse(result['blocking'])
        self.assertTrue(any('unsupported mechanic' in detail['reason'] for detail in result['details']))
        with self.assertRaisesRegex(ValueError,'one to three'):
            external_effects.resolve_many([weapon,healing,effect(name='Third'),effect(name='Fourth')],[])

    def test_empty_or_partial_rows_are_validation_errors(self):
        for rows in ([{}], [None], [effect(), {}], [{'source_kind':'food','name':'Incomplete'}]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                external_effects.resolve_many(rows, [])

    def test_explicit_numeric_effect_uses_only_existing_bucket(self):
        result = external_effects.resolve(effect(), [])
        self.assertTrue(result['detail']['applied'])
        self.assertEqual(result['row']['confidence'], 'user_entered_hypothetical')
        self.assertEqual(result['row']['tech_activation'], 'external_interval_hypothesis')
        aggregate = mod_rolls.aggregate([result['row']])
        self.assertEqual(aggregate['percent_by_type']['weapon_damage_percent'], 10)
        self.assertEqual(aggregate['percent_by_type']['status_damage_percent'], 0)

    def test_unknown_inactive_and_same_type_conflict_never_apply(self):
        unknown = external_effects.resolve(effect(activation='unknown', apply_hypothesis=False), [])
        self.assertFalse(unknown['detail']['applied'])
        self.assertTrue(unknown['blocking'])
        self.assertEqual(mod_rolls.aggregate([unknown['row']])['percent_by_type']['weapon_damage_percent'], 0)
        inactive = external_effects.resolve(effect(activation='inactive', apply_hypothesis=False), [])
        self.assertIsNone(inactive['row'])
        self.assertFalse(inactive['blocking'])
        conflict = external_effects.resolve(effect(), [{'stat_type': 'weapon_damage_percent'}])
        self.assertFalse(conflict['detail']['applied'])
        self.assertIn('stacking unknown', conflict['detail']['reason'])

    def test_apply_requires_observed_active_even_with_other_confirmations(self):
        for activation in ('unknown', 'inactive'):
            with self.subTest(activation=activation), self.assertRaisesRegex(ValueError, 'observed active'):
                external_effects.resolve(effect(activation=activation), [])
        self.assertTrue(external_effects.resolve(effect(activation='observed_active'), [])['detail']['applied'])
        with self.assertRaisesRegex(ValueError, 'activation state'):
            external_effects.resolve(effect(activation='assumed_active'), [])

    def test_baseline_and_full_interval_are_required_for_any_application(self):
        for key in ('baseline_excludes_effect', 'active_for_interval'):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'baseline excludes'):
                external_effects.resolve(effect(**{key: False}), [])

    def test_vulnerability_and_healing_keep_observed_amount_without_damage_bucket(self):
        for stat in ('weapon_vulnerability_unmodeled', 'status_vulnerability_unmodeled'):
            row = external_effects.resolve(effect(stat_type=stat, value_percent=40), [])
            self.assertFalse(row['detail']['applied'])
            self.assertEqual(row['row']['visible_magnitude'], 40)
            self.assertTrue(row['blocking'])
            self.assertTrue(all(value == 0 for value in mod_rolls.aggregate([row['row']])['percent_by_type'].values()))
        healing = external_effects.resolve(effect(stat_type='healing_or_shield_unmodeled', value_percent=20), [])
        self.assertFalse(healing['blocking'])
        self.assertFalse(healing['detail']['applied'])
        self.assertEqual(healing['detail']['value_percent'], 20)

    def test_no_source_claim_or_empty_effect_is_silently_applied(self):
        self.assertIsNone(external_effects.resolve(None, [])['row'])
        with self.assertRaisesRegex(ValueError, 'source note'):
            external_effects.resolve(effect(source_note=''), [])
        with self.assertRaisesRegex(ValueError, 'observed percentage'):
            external_effects.resolve(effect(value_percent=float('nan')), [])


if __name__ == '__main__':
    unittest.main()
