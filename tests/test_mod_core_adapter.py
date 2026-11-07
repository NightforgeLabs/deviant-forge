import copy
import unittest

import mod_core_adapter
import component_compare


ID = 'mod:helmet_mod:example'
BASE = {'catalog_id':ID, 'rule_id':'example-core', 'source':'held-tooltip#t=10s',
        'numeric_scope':'exact_level', 'level':10, 'evidence_status':'exact_observed',
        'stat_types':['weapon_damage_percent','status_damage_percent']}


class ModCoreAdapterTests(unittest.TestCase):
    def check(self, changes=None, context=None, level=10):
        rule={**BASE, **(changes or {})}
        snapshot=copy.deepcopy(rule)
        result=mod_core_adapter.evaluate(rule,catalog_id=ID,level=level,context=context)
        self.assertEqual(rule,snapshot)
        return result

    def test_static_and_conditional_compile_to_pool_rows(self):
        rows,missing=self.check({'operator':'static','value_percent':10})
        self.assertFalse(missing)
        self.assertEqual([(row['name'],row['value_percent']) for row in rows],
                         [('Weapon DMG',10),('Status DMG',10)])
        self.assertIn('unverified current game build',rows[0]['source_status'])
        rows,missing=self.check({'operator':'conditional','condition':'shield positive','value_percent':10})
        self.assertFalse(missing)
        self.assertEqual(rows[0]['condition'],'shield positive')
        comparison=component_compare.compare({'attributes':[]},{'attributes':rows},
                                             {'condition_uptime':{'shield positive':1}})
        self.assertAlmostEqual(comparison['component_ratios']['normal']['min'],1.10)
        self.assertAlmostEqual(comparison['component_ratios']['status']['min'],1.10)
        self.assertFalse(comparison['game_winner_established'])

    def test_stack_cap_and_timing_remain_explicit(self):
        rule={'operator':'stack','per_stack_percent':5,'max_stacks':3,'duration_seconds':5}
        unknown,missing=self.check(rule)
        self.assertEqual(unknown[0]['range_percent'],[0,15])
        self.assertTrue(any('stack count unresolved' in note for note in missing))
        known,missing=self.check(rule,{'effect_stacks':{'example-core':2}})
        self.assertEqual(known[0]['range_percent'],[10,10])
        self.assertTrue(any('timeline' in note for note in missing))
        with self.assertRaisesRegex(ValueError,'outside cap'):
            self.check(rule,{'effect_stacks':{'example-core':4}})

    def test_timer_without_duration_or_uptime_is_never_passive(self):
        rule={'operator':'timed','condition':'after reload','value_percent':12,'duration_seconds':8}
        rows,missing=self.check(rule)
        self.assertEqual(rows[0]['condition'],'after reload')
        self.assertTrue(any('uptime and refresh unresolved' in note for note in missing))
        rows,missing=self.check(rule,{'condition_uptime':{'after reload':0.5}})
        self.assertFalse(missing)
        self.assertEqual(rows[0]['value_percent'],12)
        rows,missing=self.check({**rule,'duration_seconds':None})
        self.assertFalse(rows)
        self.assertTrue(any('duration unresolved' in note for note in missing))

    def test_event_and_unknown_magnitude_are_withheld(self):
        for rule in ({'operator':'event','stat_types':['power_surge_damage_percent'],'value_percent':20},
                     {'operator':'static','value_percent':None},
                     {'operator':'static','value_percent':10,'numeric_scope':'unknown'},
                     {'operator':'static','value_percent':10,'level':11},
                     {'operator':'static','value_percent':10,'stat_types':['unknown_stat']}):
            rows,missing=self.check(rule)
            self.assertFalse(rows)
            self.assertTrue(missing)
        rows,missing=self.check({'operator':'static','value_percent':10,
                                 'stat_types':['weapon_damage_percent','range_percent']})
        self.assertEqual([row['name'] for row in rows],['Weapon DMG'])
        self.assertTrue(any('range_percent' in note for note in missing))

    def test_candidate_requires_opt_in_and_level_invariance_evidence(self):
        candidate={'operator':'static','value_percent':8,'evidence_status':'explicit_candidate'}
        rows,missing=self.check(candidate)
        self.assertFalse(rows)
        self.assertIn('opt-in',missing[0])
        rows,missing=self.check(candidate,{'core_candidate_opt_in':True})
        self.assertEqual(rows[0]['value_percent'],8)
        unbound={**candidate,'numeric_scope':'unbound_level_candidate'}
        rows,missing=self.check(unbound)
        self.assertFalse(rows)
        self.assertIn('selected-level binding',missing[0])
        rows,missing=self.check(unbound,{'core_candidate_opt_in':True})
        self.assertEqual(rows[0]['value_percent'],8)
        self.assertIn('not bound to selected level',rows[0]['source_status'])
        invariant={'operator':'static','value_percent':8,'numeric_scope':'level_invariant',
                   'level_invariance_verified':False}
        rows,missing=self.check(invariant,level=15)
        self.assertFalse(rows)
        invariant['level_invariance_verified']=True
        rows,missing=self.check(invariant,level=15)
        self.assertEqual(rows[0]['value_percent'],8)


if __name__=='__main__':
    unittest.main()
