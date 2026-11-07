import json, os, tempfile, unittest, threading, urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import engine
import catalog, recognition
from PIL import Image, ImageDraw, ImageFont

class EngineTests(unittest.TestCase):
    def weapon(self,id,dmg,rpm,mag,reload): return {"id":id,"name":id,"slot":"primary","stats":{"damage":dmg,"rpm":rpm,"magazine":mag,"reload_seconds":reload,"damage_origin":"tooltip_base","base_component":"weapon","base_context":"unbuffed"},"effects":{"calculation_status":"verified_no_extra_damage"}}
    def test_reload_aware(self):
        x=engine.baseline(self.weapon("A",100,60,2,2),{"duration":6,"hit_rate":1})
        self.assertEqual(x["shots"],4)
        self.assertEqual(x["reload_aware_damage"],400)
    def test_unknown_not_zero(self):
        x=engine.baseline({"stats":{"damage":100,"rpm":60}},{});self.assertFalse(x["supported"]);self.assertIn("magazine",x["missing"])
    def test_illegal_slots(self):
        self.assertTrue(engine.validate_loadout([{"slot":"helmet"},{"slot":"helmet"}]))
    def test_exhaustive_rank(self):
        items=[self.weapon("A",100,60,2,2),self.weapon("B",70,120,4,2),self.weapon("C",90,60,1,5)]
        x=engine.optimize(items,assumptions={"duration":12,"hit_rate":1})
        manual=sorted(items,key=lambda i:engine.baseline(i,{"duration":12,"hit_rate":1})["reload_aware_rate"],reverse=True)
        self.assertEqual([r["item"]["id"] for r in x["supported"]],[i["id"] for i in manual])
    def test_unmodeled_effect_warning(self):
        x=self.weapon("A",100,60,2,2);x["stats"]["proc"]="shock"
        self.assertTrue(any("proc" in w for w in engine.baseline(x,{})["warnings"]))
    def test_saved_effect_field_flagged(self):
        x=self.weapon("A",100,60,2,2);x["effects"]={"text":"Burn on hit"}
        result=engine.score_loadout([x],{"goal":"Sustained baseline"})
        self.assertTrue(any("Burn on hit" in w for w in result["metric"]["warnings"]))
    def test_goals_have_different_winners(self):
        burst=self.weapon("burst",100,120,2,10)
        sustain=self.weapon("sustain",70,60,10,1)
        builds=[{"id":i["id"],"name":i["name"],"item_ids":[i["id"]]} for i in (burst,sustain)]
        self.assertEqual(engine.compare(builds,[burst,sustain],{"goal":"Burst baseline","duration":60})["results"][0]["id"],"burst")
        self.assertEqual(engine.compare(builds,[burst,sustain],{"goal":"Sustained baseline","duration":60})["results"][0]["id"],"sustain")
        with self.assertRaisesRegex(ValueError,"Enemy defense"):
            engine.compare(builds,[burst,sustain],{"goal":"Boss damage"})
    def test_duration_sensitivity_names_new_winner(self):
        early=self.weapon("early",500,60,5,20)
        long=self.weapon("long",100,120,10,1)
        builds=[{"id":i["id"],"name":i["name"],"item_ids":[i["id"]]} for i in (early,long)]
        result=engine.compare(builds,[early,long],{"goal":"Sustained baseline","duration":10})
        self.assertEqual(result["results"][0]["name"],"early")
        self.assertTrue(result["sensitivity"][1]["changes_winner"])
        self.assertEqual(result["sensitivity"][1]["winner"],"long")
    def test_measured_crit_weakspot_branches(self):
        x=self.weapon("A",100,60,10,0)
        x["stats"].update(crit_hit_damage=200,weakspot_hit_damage=150,crit_weakspot_hit_damage=300)
        r=engine.baseline(x,{"duration":10,"hit_rate":1,"crit_rate":.5,"weakspot_rate":.5})
        # Four equally likely branches: 100, 200, 150, 300 -> 187.5 per hit.
        self.assertEqual(r["reload_aware_damage"],1875)
        del x["stats"]["crit_weakspot_hit_damage"]
        self.assertFalse(engine.baseline(x,{"duration":10,"crit_rate":.5,"weakspot_rate":.5})["supported"])
    def test_search_legal_combinations_and_locks(self):
        a=self.weapon("A",100,60,2,2);b=self.weapon("B",80,60,2,2)
        h1={"id":"h1","name":"H1","slot":"helmet","stats":{},"effects":{"calculation_status":"verified_no_extra_damage"}}
        h2={"id":"h2","name":"H2","slot":"helmet","stats":{},"effects":{"calculation_status":"verified_no_extra_damage"}}
        result=engine.search_loadouts([a,b,h1,h2],locked=["h1"],assumptions={"goal":"Sustained baseline"})
        self.assertEqual(result["searched"],2)
        self.assertTrue(all("h1" in r["item_ids"] and "h2" not in r["item_ids"] for r in result["results"]))
        with self.assertRaisesRegex(ValueError,"conflict"):
            engine.search_loadouts([a,h1,h2],locked=["h1","h2"])
    def test_upgrade_preview_before_after(self):
        weapon=self.weapon("A",100,60,10,0)
        out=engine.preview_upgrade({"item_ids":["A"]},[weapon],"A",{"damage":120},{"goal":"Sustained baseline","duration":10,"hit_rate":1})
        self.assertEqual(out["before"]["score"],100)
        self.assertEqual(out["after"]["score"],120)
        self.assertEqual(out["delta"],20)
    def test_session_targets_not_shortest_unrelated(self):
        acts=[{"name":"unrelated","target_id":"z","minutes":5},{"name":"A slow","target_id":"a","minutes":30},{"name":"A fast","target_id":"a","minutes":12},{"name":"B","target_id":"b","minutes":25}]
        out=engine.plan_session(acts,{"a","b"},40)
        self.assertEqual({a["name"] for a in out["activities"]},{"A fast","B"})
        self.assertEqual(out["minutes_left"],3)
    def test_observed_proc_status_are_separate(self):
        x=self.weapon("A",100,60,10,0)
        x["stats"].update(proc_damage_per_event=40,proc_events_per_hit=.25,status_damage_per_second=5,status_uptime=.5)
        r=engine.baseline(x,{"duration":10,"hit_rate":1})
        self.assertEqual(r["components"]["direct_hit"],1000)
        self.assertEqual(r["components"]["proc"],100)
        self.assertEqual(r["components"]["status"],25)
        self.assertEqual(r["reload_aware_damage"],1000) # no implicit double count
    def test_sourced_set_threshold_and_synergy(self):
        weapon=self.weapon("A",100,60,10,0)
        pieces=[{"id":str(i),"name":f"Tide {i}","slot":slot,"stats":{"set_name":"Treacherous Tides"},"effects":{"calculation_status":"verified_rule_only","rule_ids":["treacherous_tides_two_weapon"]}} for i,slot in enumerate(("helmet","chest","pants"))]
        at_full=engine.score_loadout([weapon]+pieces[:2],{"hp_fraction":1,"goal":"Sustained baseline","duration":10,"hit_rate":1})
        at_low=engine.score_loadout([weapon]+pieces[:2],{"hp_fraction":.6,"goal":"Sustained baseline","duration":10,"hit_rate":1})
        self.assertTrue(any("inactive" in x["text"] for x in at_full["interactions"]))
        self.assertTrue(any("+12%" in x["text"] for x in at_low["interactions"]))
        self.assertEqual(at_full["score"],100)
        self.assertEqual(at_low["score"],112) # 10 shots * 100 * 1.12 / 10 seconds
        self.assertIsNone(engine.score_loadout([weapon]+pieces,{"hp_fraction":.6,"duration":10})["score"])
        weapon["stats"]["base_context"]="unknown"
        self.assertIsNone(engine.score_loadout([weapon]+pieces[:2],{"hp_fraction":.6,"duration":10})["score"])
    def test_inapplicable_rule_does_not_change_score(self):
        weapon=self.weapon("plain",100,60,10,0)
        cap={"id":"cap","name":"Wind Intepreter Cap","slot":"helmet","stats":{},"effects":{"calculation_status":"verified_rule_only","rule_ids":["wind_interpreter_bomber"],"text":"Unstable Bomber damage rate +25%"}}
        assumptions={"duration":10,"hit_rate":1}
        self.assertEqual(engine.score_loadout([weapon],assumptions)["score"],engine.score_loadout([weapon,cap],assumptions)["score"])
        weapon["name"]="Unstable Bomber weapon"
        self.assertIsNone(engine.score_loadout([weapon,cap],assumptions)["score"])
    def test_unresolved_gear_cannot_establish_winner(self):
        weapon=self.weapon("plain",100,60,10,0)
        mod={"id":"mod","name":"Unreviewed mod","slot":"weapon_mod","stats":{},"effects":{"text":"Crit Rate +8%"}}
        builds=[{"id":"plain","name":"Plain","item_ids":["plain"]},{"id":"modded","name":"Modded","item_ids":["plain","mod"]}]
        result=engine.compare(builds,[weapon,mod],{"duration":10,"hit_rate":1})
        self.assertFalse(result["winner_established"])
        self.assertIsNone(next(r for r in result["results"] if r["id"]=="modded")["score"])
        search=engine.search_loadouts([weapon,mod],assumptions={"duration":10,"hit_rate":1})
        self.assertEqual(search["ranked"],1)
        self.assertFalse(search["winner_established"])
    def test_every_recorded_effect_field_is_audited(self):
        weapon=self.weapon("plain",100,60,10,0)
        mod={"id":"mod","name":"Mod","slot":"weapon_mod","stats":{},"effects":{"calculation_status":"verified_no_extra_damage","attributes":["Crit Rate +8%"]}}
        result=engine.score_loadout([weapon,mod],{"duration":10,"hit_rate":1})
        self.assertIsNone(result["score"])
        self.assertTrue(any("effects.attributes" in x for x in result["metric"]["unresolved"]))
        mod["effects"]={"calculation_status":"verified_no_extra_damage"}
        mod["stats"]={"set_name":"Ghost Link"}
        self.assertIsNone(engine.score_loadout([weapon,mod],{"duration":10,"hit_rate":1})["score"])
    def test_measured_context_is_bound_to_exact_gear(self):
        weapon=self.weapon("w",100,60,10,0)
        helmet={"id":"h","name":"Helmet","slot":"helmet","stats":{},"effects":{"calculation_status":"verified_no_extra_damage"}}
        measurement={"id":"m","item_ids":["w","h"],"item_fingerprint":engine.loadout_fingerprint([weapon,helmet]),"target":"dummy","buffs":"none","conditions":"10m standing","scenario":"PvE","normal_hit":200,"rpm":60,"magazine":10,"reload_seconds":0}
        a={"comparison_mode":"measured_baseline","duration":10,"hit_rate":1,"target":"dummy","buffs":"none","conditions":"10m standing","scenario":"PvE"}
        self.assertEqual(engine.score_loadout([weapon,helmet],a,[measurement])["score"],200)
        self.assertIsNone(engine.score_loadout([weapon],a,[measurement])["score"])
        self.assertIsNone(engine.score_loadout([weapon,helmet],{**a,"target":"boss"},[measurement])["score"])
        helmet["stats"]["crit_rate"]=.08
        self.assertIsNone(engine.score_loadout([weapon,helmet],a,[measurement])["score"])
    def test_unmodeled_upgrade_benefit_unknown(self):
        weapon=self.weapon("w",100,60,10,0)
        helmet={"id":"h","name":"Helmet","slot":"helmet","stats":{},"effects":{"calculation_status":"verified_no_extra_damage"}}
        out=engine.preview_upgrade({"item_ids":["w","h"]},[weapon,helmet],"h",{"crit_rate":.08},{"duration":10,"hit_rate":1})
        self.assertIsNone(out["delta"])
        self.assertEqual(out["benefit_status"],"benefit unknown")
        primary_set=engine.preview_upgrade({"item_ids":["w"]},[weapon],"w",{"set_name":"Unknown"},{"duration":10,"hit_rate":1})
        self.assertIsNone(primary_set["delta"])
    def test_catalog_mod_effect_is_calculated_only_with_complete_attributes(self):
        weapon=self.weapon('w',100,60,10,0)
        cid='mod:gloves_mod:weapon-amplifier-resonance'
        mod={'id':'m','name':'Weapon Amplifier','kind':'mod_unlock','slot':'gloves_mod','level':10,'stats':{'attribute_coverage':'complete','catalog_attributes':['No other direct or status damage bonus verified']},'effects':{'catalog_id':cid,'calculation_status':'catalog_verified','catalog_unknowns':[]}}
        a={'duration':10,'hit_rate':1}
        self.assertEqual(engine.score_loadout([weapon],a)['score'],100)
        self.assertEqual(engine.score_loadout([weapon,mod],a)['score'],115) # 10 shots * 100 * 1.15 / 10
        mod['stats']['attribute_coverage']='unknown'
        self.assertIsNone(engine.score_loadout([weapon,mod],a)['score'])
    def test_catalog_name_level_lookup_without_tooltip_transcription(self):
        title='Shock Diffusion <Power Surge>\nWeapon Mods-All Weapons\ni 11 Power Surge\nF Equip'
        found=recognition.identify(title,kind_hint='mod')
        self.assertEqual(found['catalog_id'],'mod:weapon_mod:shock-diffusion-power-surge')
        self.assertEqual(found['ownership'],'unlocked')
        self.assertEqual(found['lookup']['level_profile'],[3,3,3,2])
        self.assertIn('When triggering Power Surge',found['lookup']['primary_effect'])
        self.assertEqual([a['value_percent'] for a in found['lookup']['known_attributes']],[3.6,3.6,3.6,3.0])
        locked=recognition.identify(title+'\nUnlock Cost 2000',kind_hint='mod')
        self.assertEqual(locked['ownership'],'locked')
    def test_numeric_field_guide_profiles_and_verified_shared_tiers(self):
        # Expected numbers were read from distinct native-resolution frames.
        examples=[
            ('mod:helmet_mod:overflow-general',8,[2.4,4.8,3.6,3.0]),
            ('mod:pants_mod:precision-charge-aero',8,[2.4,6.0,3.0,2.4]),
            ('mod:pants_mod:bullet-siphon-aero-deviant-energy',12,[4.8,4.8,4.5,2.4]),
            ('mod:gloves_mod:lifeforce-boost-precision',5,[3.6,1.2,2.4,1.5]),
            ('mod:weapon_mod:shock-diffusion-deviant-energy',13,[6.4,4.8,7.2,3.0]),
            ('mod:gloves_mod:elemental-overload-resonance',9,[0.6,0.8,3.0,4.8]),
        ]
        for catalog_id,level,expected in examples:
            with self.subTest(catalog_id=catalog_id):
                resolved=catalog.resolve(catalog_id,level)
                self.assertEqual(resolved['attribute_coverage'],'complete')
                self.assertEqual([a['value_percent'] for a in resolved['known_attributes']],expected)
        # Lv. 8 advances the fourth tier, but no exact-identity frame verifies
        # its magnitude. Values from other mods must not be borrowed.
        advanced=catalog.resolve('mod:chest_mod:resist-advantage-precision',8)
        self.assertEqual([a['value_percent'] for a in advanced['known_attributes']],[3.6,2.4,4.8,None])
        self.assertEqual(advanced['attribute_coverage'],'partial')
        aero17=catalog.resolve('mod:pants_mod:precision-charge-aero',17)
        self.assertEqual([a['value_percent'] for a in aero17['known_attributes']],[6.0,15.0,7.5,2.4])
        self.assertEqual(aero17['known_attributes'][0]['conditional_bonus_percent'],3.0)
        survival=catalog.resolve('mod:weapon_mod:shock-rampage-survival',10)
        self.assertEqual([a['value_percent'] for a in survival['known_attributes']],[None,4.8,None,3.0])
        self.assertEqual(survival['attribute_coverage'],'partial')
    def test_shared_survival_tiers_preserve_reduction_and_provenance(self):
        derived=[('shock-rampage',10),('shock-rampage',11),('shock-diffusion',11),('static-shock',10),('surge-amplifier',11)]
        for name,level in derived:
            with self.subTest(name=name,level=level):
                attr=catalog.resolve('mod:weapon_mod:'+name+'-survival',level)['known_attributes'][2]
                self.assertEqual(attr['direction'],'reduction')
                self.assertEqual(attr['unit'],'percent')
                self.assertEqual(attr['value_percent'],4.8 if (name,level)==('shock-rampage',11) else None)
                if attr['value_percent'] is None:
                    self.assertIsNone(attr.get('source'))
                    self.assertTrue(attr.get('semantic_source'))
                else:self.assertTrue(attr.get('source'))
        pants=catalog.resolve('mod:pants_mod:distant-strike-survival',11)['known_attributes'][2]
        self.assertEqual(pants['direction'],'reduction')
        conditional=catalog.resolve('mod:weapon_mod:shock-rampage-survival',10)['known_attributes'][1]
        self.assertIn('after taking damage',conditional['condition'])
        shiny=catalog.resolve('mod:weapon_mod:shock-rampage-survival',17,shiny=True)
        self.assertIn('Mod Collection Progress reward',shiny['shiny_acquisition']['paths'])
        self.assertEqual(shiny['shiny_acquisition']['entry_specific_eligibility'],'unverified')
    def test_tier_reconciliation_rejects_semantic_and_numeric_conflicts(self):
        base={'name':'Example','unit':'percent','direction':'reduction','value_percent':3.2,'source':'one'}
        compatible=[{'catalog_id':'a',**base},{'catalog_id':'b',**{**base,'source':'two'}}]
        shared,conflict=catalog.reconcile_tier_evidence(compatible)
        self.assertIsNone(conflict)
        self.assertEqual(shared['direction'],'reduction')
        self.assertEqual(shared['evidence_sources'],['one','two'])
        for changed in ({'direction':'increase'},{'value_percent':4.8},{'condition':'after hit'},{'unit':'percentage_points'}):
            other={'catalog_id':'b',**{**base,'source':'two',**changed}}
            shared,conflict=catalog.reconcile_tier_evidence([compatible[0],other])
            self.assertIsNone(shared)
            self.assertEqual(conflict['reason'],'numeric or semantic conflict')
        unresolved=catalog.resolve('mod:pants_mod:precision-charge-aero',9)
        self.assertEqual(unresolved['attribute_coverage'],'partial')
        self.assertIsNone(unresolved['known_attributes'][0]['value_percent'])
        self.assertGreater(catalog.coverage()['validated_shared_attribute_tiers'],0)
    def test_confirmed_same_slot_comparison_re_resolves_semantics(self):
        import server
        left=server.catalog_item_data('mod:weapon_mod:shock-diffusion-power-surge',11)
        right=server.catalog_item_data('mod:weapon_mod:shock-rampage-survival',12)
        left['id']='power';right['id']='survival'
        right['stats']['catalog_attributes'][2].pop('direction',None)  # stale saved snapshot
        result=engine.compare_catalog_selections(left,right,{'weapon_family':'Power Surge','conditions':'grounded; no incoming hits'})
        self.assertFalse(result['winner_established'])
        self.assertTrue(result['calculation_coverage']['numeric_profiles_complete'])
        self.assertTrue(result['main_effect_changed'])
        self.assertEqual(len(result['right']['attributes']),4)
        reduction=next(a for a in result['right']['attributes'] if a['name']=='Damage from monsters received')
        self.assertEqual(reduction['direction'],'reduction')
        self.assertEqual(reduction['outgoing_damage_status'],'proven inactive for outgoing damage')
        self.assertTrue(any(c['name']=='Damage from monsters received' for c in result['attribute_changes']))
        self.assertTrue(any('main effects differ' in b for b in result['blockers']))
        with self.assertRaises(ValueError):
            engine.compare_catalog_selections(left,{**right,'slot':'pants_mod'}, {})
        lower=server.catalog_item_data('mod:weapon_mod:shock-rampage-survival',10)
        lower['id']='lower'
        same_main=engine.compare_catalog_selections(lower,right,{'weapon_family':'Power Surge','conditions':'no incoming hits'})
        monster=next(c for c in same_main['attribute_changes'] if c['name']=='Damage from monsters received')
        self.assertIsNone(monster['numeric_delta_percent'])  # Lv11 exact tier remains unverified
        self.assertIsNone(monster['modifier_delta_percentage_points'])
        self.assertEqual(monster['outgoing_damage_status'],'proven inactive for outgoing damage')
        self.assertFalse(same_main['main_effect_changed'])
        self.assertFalse(same_main['winner_established'])
        self.assertFalse(any('+1.6 percentage points' in x for x in same_main['supported_findings']))
        relative=engine.compare_catalog_selections(left,right,{'weapon_family':'Power Surge','base_trigger_chance':0.30})['right']['relative_trigger_rule']
        self.assertEqual(relative['operator'],'relative_to_weapon_base_trigger_chance')
        self.assertEqual(relative['one_stack_chance'],0.315)  # 30% × (1 + 5%)
        self.assertEqual(relative['one_stack_change_percentage_points'],1.5)
        self.assertEqual(relative['max_stacks_text'],4)
        self.assertEqual(relative['stack_accumulation'],'unverified')
        self.assertIsNone(engine.compare_catalog_selections(left,right,{})['right']['relative_trigger_rule']['one_stack_chance'])
    def test_conditional_bonus_preserves_unconditional_base(self):
        import server
        aero=server.catalog_item_data('mod:pants_mod:precision-charge-aero',8);aero['id']='aero'
        other=server.catalog_item_data('mod:pants_mod:distant-strike-survival',10);other['id']='other'
        grounded=engine.compare_catalog_selections(aero,other,{'conditions':'grounded; no incoming hits','crit_rate':None,'weakspot_rate':None})['left']['attributes']
        weapon,crit=grounded[:2]
        self.assertEqual((weapon['base_value_percent'],weapon['conditional_value_percent'],weapon['effective_value_percent']),(2.4,1.2,2.4))
        self.assertIn('passive',weapon['base_activation_state'])
        self.assertIn('inactive',weapon['conditional_activation_state'])
        self.assertEqual((crit['base_value_percent'],crit['conditional_value_percent'],crit['effective_value_percent']),(6.0,3.0,6.0))
        self.assertNotIn('inactive',crit['base_activation_state'])
        explicit_zero=engine.compare_catalog_selections(aero,other,{'conditions':'grounded','crit_rate':0})['left']['attributes'][1]
        self.assertIn('explicit zero',explicit_zero['base_activation_state'])
        aerial=engine.compare_catalog_selections(aero,other,{'conditions':'aerial hit'})['left']['attributes']
        self.assertEqual((aerial[0]['effective_value_percent'],aerial[1]['effective_value_percent']),(3.6,9.0))
        downstar=server.catalog_item_data('mod:pants_mod:reload-rampage-downstar-deviant-energy',11);downstar['id']='downstar'
        same=engine.compare_catalog_selections(downstar,other,{'conditions':'same elevation'})['left']['attributes'][0]
        self.assertEqual(same['effective_value_percent'],4.8)
        self.assertIn('inactive',same['conditional_activation_state'])
        lower=engine.compare_catalog_selections(downstar,other,{'conditions':'enemy below player at 5m'})['left']['attributes'][0]
        self.assertEqual(lower['effective_value_percent'],7.2)
    def test_isolated_first_monster_hit_ranks_real_catalog_levels(self):
        import server
        left=server.catalog_item_data('mod:weapon_mod:shock-diffusion-survival',10);left['id']='example-10'
        right=server.catalog_item_data('mod:weapon_mod:shock-diffusion-survival',11);right['id']='example-11'
        hit=engine.compare_catalog_selections(left,right,{'incoming_monster_hit':100,'conditions':'first monster hit'})
        self.assertFalse(hit['winner_established'])
        self.assertIsNone(hit['selected_metric'])
        self.assertFalse(hit['calculation_coverage']['overall_damage_rank_supported'])
        self.assertTrue(hit['ranking_blockers'])
        no_hits=engine.compare_catalog_selections(left,right,{'incoming_monster_hit':0,'conditions':'no incoming hits'})
        self.assertFalse(no_hits['winner_established'])
        unresolved=engine.compare_catalog_selections(left,server.catalog_item_data('mod:weapon_mod:shock-rampage-survival',12),{'incoming_monster_hit':100})
        self.assertFalse(unresolved['winner_established'])
        self.assertIsNone(unresolved['selected_metric'])
        self.assertTrue(unresolved['ranking_blockers'])
        pants10=server.catalog_item_data('mod:pants_mod:distant-strike-survival',10);pants10['id']='pants-10'
        pants11=server.catalog_item_data('mod:pants_mod:distant-strike-survival',11);pants11['id']='pants-11'
        pants=engine.compare_catalog_selections(pants10,pants11,{'incoming_monster_hit':100})
        self.assertIsNone(pants['selected_metric'])
        self.assertFalse(pants['winner_established'])
    def test_structured_attributes_reach_prediction_without_false_winner(self):
        import server
        weapon=self.weapon('w',250,60,10,0)
        direct=server.catalog_item_data('mod:pants_mod:precision-charge-aero',8)
        direct['id']='direct'
        prediction=engine.score_loadout([weapon,direct],{'duration':10,'hit_rate':1})
        self.assertIsNone(prediction['score'])
        self.assertEqual(prediction['metric']['isolated_estimates'][0]['weapon_component_increment'],6.0)
        status=server.catalog_item_data('mod:pants_mod:bullet-siphon-aero-deviant-energy',12)
        status['id']='status'
        other=engine.score_loadout([weapon,status],{'duration':10,'hit_rate':1})
        self.assertIsNone(other['score'])
        self.assertEqual(other['metric']['isolated_estimates'],[])
    def test_detail_effects_do_not_invent_effect_level_mapping(self):
        entry=catalog.ENTRIES['mod:pants_mod:precision-charge-aero']
        self.assertIn('For every 10% Weakspot hit rate',entry['detail_effect_variants'][0])
        self.assertEqual(len(entry['detail_effect_variants']),2)
        self.assertTrue(entry['catalog_system_records'])
        self.assertTrue(any(record['is_shiny'] for record in entry['catalog_system_records']))
        old=catalog.resolve(entry['id'],8,system='legacy_random_roll')
        self.assertIsNone(old['known_attributes'])
        self.assertIn('instance-specific',old['unknowns'][0])
        shiny=catalog.resolve(entry['id'],17,shiny=True)
        self.assertTrue(any('Shiny main-effect' in issue for issue in shiny['unknowns']))
    def test_native_grid_badge_requires_tooltip_for_identity_and_ownership(self):
        source=Path(__file__).resolve().parents[1]/'data/media/b0aad7d457fd4e699605ae1f78d4ec51/frames/1b99d4a1dce94a8294f2459acf6303a7/0078.png'
        cards=recognition.scan_visible_grid(source)
        selected=[c for c in cards if c['selected']]
        self.assertEqual(selected[0]['level_badge'],11)
        self.assertEqual(selected[0]['ownership'],'unknown')
        self.assertEqual(selected[0]['identity'],'selected tooltip identity only')
        self.assertTrue(any(c['ownership']=='locked' and c['lock_match']>=.75 for c in cards))
        self.assertTrue(any(c['level_badge']==9 and c['ownership']=='unknown' for c in cards))
    def test_search_discloses_limit(self):
        weapon=self.weapon("A",100,60,10,0)
        gear=[{"id":str(i),"name":str(i),"slot":"helmet","stats":{}} for i in range(5)]
        r=engine.search_loadouts([weapon]+gear,assumptions={"goal":"Sustained baseline"},limit=3)
        self.assertFalse(r["complete"])
        self.assertEqual(r["space"],6)
    def test_build_gap_checks_owned_separately(self):
        weapon=self.weapon("w",100,60,10,0);weapon["name"]="SOCR - Cosmic Visitor"
        vest={"id":"v","name":"Snowline Elite Vest","slot":"chest","stats":{}}
        catalog=[{"name":"Snowline Elite Vest","acquisition":"Official mailbox"}]
        gap=engine.build_gaps({"item_ids":["w"]},[weapon,vest],catalog)[0]
        self.assertTrue(gap["owned"])
        self.assertEqual(gap["status"],"owned but not equipped")
        self.assertEqual(gap["acquisition"],"Official mailbox")
        self.assertEqual(engine.build_gaps({"item_ids":["w","v"]},[weapon,vest],catalog),[])
    def test_official_suffix_is_structured_but_unknown_magnitude_blocks_winner(self):
        weapon=self.weapon('w',100,60,10,0)
        mod={'id':'m','name':'Ardent Shield','kind':'mod_unlock','slot':'chest_mod','variant':'Mirror','stats':{'attribute_coverage':'complete'},'effects':{'catalog_id':'mod:chest_mod:ardent-shield-mirror','calculation_status':'catalog_verified'}}
        result=engine.score_loadout([weapon,mod],{'goal':'Sustained baseline','duration':10})
        self.assertFalse(result['rankable'])
        self.assertTrue(any('attacking from behind' in str(t) for t in result['metric']['trace']))
        self.assertTrue(any('suffix effect magnitudes' in x for x in result['metric']['unresolved']))
    def test_current_catalog_merges_icon_records_without_duplicate_identities(self):
        coverage=catalog.coverage()
        # The twelve additional Gloves card sightings extend the previously
        # verified 972 identities; none creates ownership or duplicates an ID.
        self.assertEqual(coverage['counts']['mods'],985)
        self.assertIn('mod:pants_mod:precision-charge-general', catalog.ENTRIES)
        self.assertIn('mod:pants_mod:elemental-resonance-deviant-energy-current', catalog.ENTRIES)
        self.assertEqual(len({key for key in catalog.ENTRIES if key.startswith(
            'mod:helmet_mod:mag-expansion-') and key != 'mod:helmet_mod:mag-expansion'}), 9)
        screenshot_ids={
            'mod:helmet_mod:mag-expansion-deviant-energy',
            'mod:helmet_mod:mag-expansion-precision',
            'mod:helmet_mod:mag-expansion-violent',
            'mod:helmet_mod:mag-expansion-survival',
            'mod:helmet_mod:mag-expansion-general',
            'mod:helmet_mod:elemental-havoc-violent',
        }
        self.assertEqual({entry['id'] for entry in catalog.DATA['mods'] if entry.get('source')=='user_supplied_game_screenshot_2026-10-25'},screenshot_ids)
        self.assertEqual(len({entry['id'] for entry in catalog.DATA['mods']}),coverage['counts']['mods'])
        self.assertEqual(coverage['current_mod_identities'],837)
        self.assertEqual(coverage['current_snapshot']['rejected_records'],6)
        self.assertEqual(len(catalog.ENTRIES),sum(coverage['counts'].values()))
        self.assertTrue(catalog.ENTRIES['mod:weapon_mod:shock-diffusion-power-surge']['image_url'].endswith('.png'))
        aero=catalog.resolve('mod:pants_mod:precision-charge-aero',8)
        self.assertEqual(aero['attribute_tiers'][0],{'name':'Weapon DMG (aerial bonus)','tier':2})
        self.assertTrue(any(x.get('condition')=='aerial state, including jumping' for x in aero['known_effects']))

class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();os.environ["OH_ADVISOR_DATA"]=self.tmp.name
        import server
        server.DATA=Path(self.tmp.name);server.MEDIA=server.DATA/"media";server.DB=server.DATA/"advisor.sqlite3";server.init();self.server=server
    def tearDown(self):self.tmp.cleanup()
    def test_backup_roundtrip_and_partial_inventory(self):
        s=self.server
        with s.connect() as c:
            c.execute("INSERT INTO inventory VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",("x","Owned weapon","instance","primary",None,None,1,None,json.dumps({"damage":10}),"{}",None,"[]",s.now(),s.now(),0))
            c.execute("INSERT INTO media(id,name,type,size,created) VALUES(?,?,?,?,?)",("m","partial.png","image",0,s.now()))
        before=s.inventory();self.assertEqual(len(before),1)
        b=s.backup()
        with s.connect() as c:c.execute("DELETE FROM inventory")
        s.restore(b);self.assertEqual(s.inventory()[0]["name"],"Owned weapon")
        self.assertEqual(len(s.inventory()),1)
        with s.connect() as c:self.assertEqual(c.execute("SELECT version FROM schema_version").fetchone()[0],6)
    def test_backup_path_rejected(self):
        b=self.server.backup();b["files"]={"media/../../escape.png":"aGVsbG8="}
        with self.assertRaises(ValueError):self.server.restore(b)
    def test_legacy_backup_restores_with_activity_target_migration(self):
        s=self.server
        with s.connect() as c:c.execute("INSERT INTO activities(id,name,minutes,source_url,notes,created,target_id) VALUES(?,?,?,?,?,?,?)",("a","Old activity",15,None,None,s.now(),None))
        b=s.backup();b["version"]=1
        for table in ("upgrades","measurements","planned_builds","catalog_ownership","video_import_runs","video_import_proposals","field_guide_levels","field_guide_level_events","undo"):b["tables"].pop(table)
        for a in b["tables"]["activities"]:a.pop("target_id")
        s.restore(b)
        self.assertEqual(s.rows("activities")[0]["name"],"Old activity")
        self.assertIsNone(s.rows("activities")[0]["target_id"])
    def test_backup_roundtrip_preserves_field_guide_and_undo(self):
        s=self.server
        with s.connect() as c:
            c.execute("INSERT INTO field_guide_levels VALUES(?,?,?,?,?,?,?)",('personal','mod:helmet_mod:deviation-expert-lunar',10,'ordinary','user','screen-ref',s.now()))
            c.execute("INSERT INTO field_guide_level_events(profile_id,catalog_id,prior,next,source_kind,created) VALUES(?,?,?,?,?,?)",('personal','mod:helmet_mod:deviation-expert-lunar',None,'{"level":10}','user',s.now()))
            c.execute("INSERT INTO undo(entity,entity_id,prior,created) VALUES(?,?,?,?)",('inventory','example',None,s.now()))
        before={t:s.rows(t) for t in ('field_guide_levels','field_guide_level_events','undo')}
        saved=s.backup();self.assertEqual(saved['version'],8)
        with s.connect() as c:
            for table in before:c.execute(f'DELETE FROM {table}')
        s.restore(saved)
        self.assertEqual({t:s.rows(t) for t in before},before)
        legacy=json.loads(json.dumps(saved));legacy['version']=7
        for table in before:legacy['tables'].pop(table)
        s.restore(legacy)
        self.assertEqual({t:s.rows(t) for t in before},before)
    def test_uncertain_ocr(self):
        x=self.server.parse_ocr("Test Rifle\nDamage 123\nFire Rate 600")
        self.assertEqual(x["damage"]["value"],123)
        self.assertEqual(x["name"]["confidence"],"low")
    def test_mod_attribute_ocr_preserved(self):
        x=self.server.parse_ocr("Test Mod\nWeapon Mod\nCrit Rate +8%\nWhen shooting hits a target, trigger Burn")
        self.assertEqual(x["slot"]["value"],"weapon_mod")
        self.assertIn("Crit Rate +8%",x["attributes"]["value"])
        self.assertIn("trigger Burn",x["effect_text"]["value"])
    def test_field_guide_ocr_triplet_and_variant_attributes(self):
        s=self.server
        weapon=s.parse_ocr('AUG - Electron Cloud B.P.\nBasic Stats\nDMG Fire Rate MAG\n231 | 720 | 40\nCrit DMG 25%')
        self.assertEqual([weapon[k]['value'] for k in ('damage','rpm','magazine')],[231,720,40])
        mod=s.parse_ocr('Shock Diffusion <Power Surge>\nWeapon Mods-All Weapons\ni 11 Power Surge\nPower Surge DMG + 3.6%\nShock DMG + 3.6%')
        self.assertIn('Power Surge DMG + 3.6%',mod['attributes']['value'])
        self.assertNotIn('damage',mod)
    def test_catalog_lookup_populates_mod_without_tooltip_submission(self):
        s=self.server
        item=s.enrich_catalog_item({'name':'Shock Diffusion','kind':'mod_unlock','slot':'weapon_mod','level':11,'stats':{},'effects':{}},'mod:weapon_mod:shock-diffusion-power-surge')
        self.assertEqual(item['stats']['catalog_level_profile'],[3,3,3,2])
        self.assertEqual(item['stats']['catalog_attribute_tiers'][0],{'name':'Power Surge DMG','tier':3})
        self.assertEqual(item['stats']['catalog_attribute_tiers'][3],{'name':'All DMG Boost','tier':2})
        self.assertEqual(catalog.resolve('mod:weapon_mod:shock-diffusion-power-surge',11)['possible_crate_difficulties'],['normal','hard','master','nightmare'])
        self.assertIn('When triggering Power Surge',item['effects']['text'])
        self.assertEqual(item['effects']['catalog_id'],'mod:weapon_mod:shock-diffusion-power-surge')
        self.assertEqual([a['value_percent'] for a in item['stats']['catalog_attributes']],[3.6,3.6,3.6,3.0])
        self.assertEqual(item['stats']['attribute_coverage'],'complete')
        self.assertGreaterEqual(s.catalog_search('Shock Diffusion','mod')['total'],1)
    def test_catalog_auto_confirm_requires_unlocked_level_and_keeps_rolls_uncertain(self):
        s=self.server;mid='guide';folder=s.MEDIA/mid;folder.mkdir()
        Image.new('RGB',(1000,1000),(0,0,0)).save(folder/'view.png')
        with s.connect() as c:c.execute('INSERT INTO media(id,name,type,size,created) VALUES(?,?,?,?,?)',(mid,'view.png','image',0,s.now()))
        raw='Shock Diffusion <Power Surge>\nWeapon Mods-All Weapons\ni 11 Power Surge\nPower Surge DMG + 3.6%\nF Equip'
        for oid,ocr in [('a',raw),('b',raw+'\nLocked\nUnlock Cost 3')]:
            fields=s.parse_ocr(ocr);fields['identification']=recognition.identify(ocr)
            with s.connect() as c:c.execute('INSERT INTO observations VALUES(?,?,?,?,?,?,?,?,?)',(oid,mid,'media/guide/view.png',180,ocr,json.dumps(fields),90,'pending',s.now()))
        self.assertTrue(s.auto_confirm_catalog_mod('a'))
        self.assertFalse(s.auto_confirm_catalog_mod('b'))
        self.assertEqual(len(s.inventory()),1)
        item=s.inventory()[0]
        self.assertEqual(item['level'],11)
        self.assertEqual(item['effects']['text'],catalog.ENTRIES['mod:weapon_mod:shock-diffusion-power-surge']['primary_effect'])
        self.assertEqual(item['stats']['catalog_level_profile'],[3,3,3,2])
        self.assertEqual(item['stats']['attribute_coverage'],'complete')
        self.assertEqual(item['stats']['observed_attribute_ocr_status'],'unverified_ocr')
        self.assertEqual(item['stats']['observed_attribute_lines'],['Power Surge DMG + 3.6%'])
    def test_roll_extraction_excludes_main_effect_and_joins_wrapped_line(self):
        raw='Overflow <General>\nWhen reloading an empty magazine, Magazine Capacity + 30.0%.\n% 8 General\nDMG ++ 2.4%\nIncreases damage dealt to all DMG Boost by +\n3.0%\nLevel 5 and above\nEquip'
        lines=self.server.parse_ocr(raw)['mod_roll_lines']['value']
        self.assertEqual(lines,['DMG ++ 2.4%','Increases damage dealt to all DMG Boost by + 3.0%'])
        self.assertNotIn('Magazine Capacity + 30.0%',lines)
    def test_real_local_extraction(self):
        s=self.server;mid="fixture";folder=s.MEDIA/mid;folder.mkdir()
        im=Image.new("RGB",(1100,650),(245,245,245));draw=ImageDraw.Draw(im)
        font=ImageFont.truetype("/usr/share/fonts/liberation/LiberationSans-Regular.ttf",46)
        draw.text((80,70),"TEST RIFLE",fill=(5,5,5),font=font)
        draw.text((80,160),"Damage 123",fill=(5,5,5),font=font)
        draw.text((80,250),"RPM 600",fill=(5,5,5),font=font)
        im.save(folder/"fixture.png")
        with s.connect() as c:c.execute("INSERT INTO media(id,name,type,size,created) VALUES(?,?,?,?,?)",(mid,"fixture.png","image",(folder/"fixture.png").stat().st_size,s.now()))
        s.jobs["j"]={"state":"queued","progress":0,"cancel":False}
        s.process("j",mid,{})
        self.assertEqual(s.jobs["j"]["state"],"done")
        self.assertEqual(len(s.observations()),1)
        self.assertEqual(s.observations()[0]["fields"]["damage"]["value"],123)
        self.assertEqual(len(s.inventory()),0)
        http=ThreadingHTTPServer(("127.0.0.1",0),s.Handler)
        thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        def post(path,data):
            request=urllib.request.Request(f"http://127.0.0.1:{http.server_port}/api/{path}",json.dumps(data).encode(),{"Content-Type":"application/json"})
            with urllib.request.urlopen(request) as response:return json.load(response)
        try:
            oid=s.observations()[0]["id"]
            saved=post("confirm",{"observation_id":oid,"item":{"name":"TEST RIFLE","kind":"instance","slot":"primary","stats":{"damage":123,"rpm":600,"magazine":30,"reload_seconds":2,"damage_origin":"tooltip_base","base_component":"weapon","base_context":"unbuffed"},"effects":{"calculation_status":"verified_no_extra_damage"}}})
            self.assertEqual(s.inventory()[0]["source_observation"],oid)
            self.assertEqual(len(s.inventory()[0]["evidence"]),1)
            post("loadout",{"name":"Reviewed rifle","item_ids":[saved["id"]]})
            compared=post("compare",{"duration":3,"hit_rate":1,"goal":"Sustained baseline","comparison_mode":"predicted_equipment"})
            self.assertEqual(compared["results"][0]["score"],1230) # 30 shots in 3s, 3690 / 3
            self.assertTrue(compared["winner_established"])
            self.assertEqual(compared["results"][0]["items"][0]["evidence"][0]["observation_id"],oid)
        finally:
            http.shutdown();http.server_close();thread.join()

if __name__=="__main__":unittest.main()
