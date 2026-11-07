import unittest

import component_compare
import weapon_timeline_api as timeline


def request(weapon, actions, *, evidence='dated_release', model='explicit_assumptions', magazine=None):
    return {'weapon_id':weapon, 'evidence_mode':evidence, 'model_mode':model,
            'magazine':magazine, 'stream_id':'isolated-golden', 'actions':actions}


def hit(index, **extra):
    return {'kind':'hit','at':index,'target':'dummy','input_id':f'hit-{index}',**extra}


class WeaponTimelineApiTests(unittest.TestCase):
    def test_all_nine_keyword_family_scenarios_execute_without_damage_claim(self):
        cases = [
            ('weapon:mps7-outer-space', [hit(0,rolls={'power_surge':'0.1'},
                                            conditions={'target_affected_by_power_surge':False})], 'Power Surge'),
            ('weapon:mg4-conflicting-memories',[hit(i) for i in range(12)],'Shrapnel'),
            ('weapon:kam-crank',[hit(i) for i in range(7)],'Burn'),
            ('weapon:kam-abyss-glance',[hit(i,weakspot=True) for i in range(7)],'Frost Vortex'),
            ('weapon:g17-hazardous-object',[{'kind':'fire','at':0,'rounds':2,'input_id':'fire'},
                                             {'kind':'reload','at':1,'refund_roll':'0.2',
                                              'refund_rounding':'floor','input_id':'reload'}], 'Unstable Bomber'),
            ('weapon:mps5-blue-tiger',[hit(0,rolls={'bounce':'0.2'})], 'Bounce'),
            ('weapon:mg4-predator',[hit(0,rolls={'fast_gunner':'0.9'}),
                                    {'kind':'observe_stacks','at':1,'keyword':'fast_gunner',
                                     'count':5,'input_id':'stacks'}], 'Fast Gunner'),
            ('weapon:tec9-additional-rules',[hit(0)],'Fortress Warfare'),
            ('weapon:dbsg-doombringer',[hit(0,distance=8,rolls={'bullseye':'0.7'},
                                         conditions={'all_pellets_hit_non_meta_human':True})],"Bull's Eye"),
        ]
        self.assertEqual(len(cases),9)
        for weapon,actions,family in cases:
            with self.subTest(family=family):
                preview=weapon in ('weapon:kam-crank','weapon:tec9-additional-rules')
                magazine=20 if weapon=='weapon:g17-hazardous-object' else 100 if weapon=='weapon:mg4-predator' else None
                result=timeline.simulate(request(weapon,actions,
                    evidence='historical_release' if weapon=='weapon:mg4-conflicting-memories' else
                             'preview_simulation' if preview else 'dated_release',magazine=magazine))
                self.assertEqual(result['family'],family)
                self.assertIsNone(result['total_damage'])
                self.assertIsNone(result['damage_per_second'])
                self.assertTrue(result['sources'])
                self.assertTrue(result['binding_missing'])
                self.assertEqual(len({event['event_id'] for event in result['events']}),len(result['events']))
        self.assertEqual(timeline.coverage()['executable_representative_weapons'],9)

    def test_reload_ammo_and_replayed_input_are_idempotent(self):
        fire={'kind':'fire','at':0,'rounds':2,'input_id':'shot-1'}
        reload={'kind':'reload','at':1,'loaded_rounds':2,'input_id':'reload-1'}
        result=timeline.simulate(request('weapon:mg4-predator',
            [fire,fire,reload,reload],magazine=10))
        self.assertEqual(result['ammo']['rounds'],10)
        self.assertEqual(result['replayed_events_suppressed'],2)
        self.assertEqual(len(result['events']),2)
        self.assertEqual(result['events'][0]['rounds'],2)
        self.assertEqual(result['events'][1]['rounds'],2)
        self.assertEqual(result['events'][1]['event'],'ammo_loaded')
        with self.assertRaisesRegex(ValueError,'caller-supplied loaded_rounds'):
            timeline.simulate(request('weapon:mg4-predator',
                [{'kind':'reload','at':0,'input_id':'no-ammo'}],magazine=10))
        with self.assertRaisesRegex(ValueError,'different payload'):
            timeline.simulate(request('weapon:mg4-predator',
                [fire,{**fire,'rounds':3}],magazine=10))

    def test_preview_model_and_missing_inputs_are_gated(self):
        with self.assertRaisesRegex(ValueError,'preview_simulation'):
            timeline.simulate(request('weapon:kam-crank',[hit(0)]))
        with self.assertRaisesRegex(ValueError,'explicit_assumptions'):
            timeline.simulate(request('weapon:mg4-conflicting-memories',[hit(0)],
                                      evidence='historical_release',model='verified_only'))
        with self.assertRaisesRegex(ValueError,'roll required'):
            timeline.simulate(request('weapon:mps5-blue-tiger',[hit(0)]))
        with self.assertRaisesRegex(ValueError,'condition .* required'):
            timeline.simulate(request('weapon:mps7-outer-space',
                [hit(0,rolls={'power_surge':'0.1'})]))
        with self.assertRaisesRegex(ValueError,'derived events cannot be fed back'):
            timeline.simulate(request('weapon:mps5-blue-tiger',
                [{'kind':'keyword_trigger','at':0,'input_id':'bad'}]))
        with self.assertRaisesRegex(ValueError,'time order'):
            timeline.simulate(request('weapon:mps5-blue-tiger',
                [hit(1,rolls={'bounce':'0.1'}),hit(0,rolls={'bounce':'0.1'})]))

    def test_conflicting_memories_current_rule_is_blocked_and_old_counter_is_opt_in(self):
        weapon='weapon:mg4-conflicting-memories'
        six=[hit(i) for i in range(6)]
        twelve=[hit(i) for i in range(12)]
        for actions in (six,twelve):
            with self.assertRaisesRegex(ValueError,'Current Conflicting Memories proc rule is unresolved'):
                timeline.simulate(request(weapon,actions))
            with self.assertRaisesRegex(ValueError,'historical_release'):
                timeline.simulate(request(weapon,actions,evidence='preview_simulation'))
        older_six=timeline.simulate(request(weapon,six,evidence='historical_release'))
        older_twelve=timeline.simulate(request(weapon,twelve,evidence='historical_release'))
        self.assertEqual(older_six['event_counts'].get('keyword_trigger',0),0)
        self.assertEqual(older_twelve['event_counts'].get('keyword_trigger',0),1)
        self.assertIn('historical_release_only',older_twelve['version_scope'])
        self.assertIn('sep26_rework_release',older_twelve['sources'])
        self.assertIn(weapon,timeline.coverage()['historical_only_weapons'])

    def test_comparison_api_keeps_events_separate_from_damage(self):
        scenario=request('weapon:mps5-blue-tiger',[hit(0,rolls={'bounce':'0.1'})])
        right={**scenario,'stream_id':'right-build'}
        result=component_compare.compare({'attributes':[]},{'attributes':[]},
            {'weapon_timeline':{'left':scenario,'right':right}})
        self.assertEqual(result['component_ratios']['normal']['min'],1)
        self.assertIsNone(result['conditional_combat_projection'])
        self.assertEqual(result['weapon_timeline_scenarios']['left']['event_counts']['keyword_trigger'],1)
        self.assertTrue(any('not added to component damage' in note for note in result['missing']))
        self.assertFalse(result['game_winner_established'])


if __name__=='__main__':
    unittest.main()
