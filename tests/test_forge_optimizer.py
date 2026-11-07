import json
"""Tests for the Forge optimizer (forge.py / forge_effects.py)."""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import forge, forge_effects as fe


class ForgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gd = forge.gamedata()

    def w(self, name):
        return self.gd["weapons"][name]

    def test_gamedata_loaded(self):
        self.assertGreater(len(self.gd["weapons"]), 80)
        self.assertGreater(len(self.gd["mods"]), 80)
        self.assertGreater(len(self.gd["sets"]), 10)

    def test_substat_tiers(self):
        m = {"name": "Shock Diffusion", "variant": "Power Surge", "tiers": [3, 3, 3, 2]}
        s = forge.mod_substats(m)
        self.assertAlmostEqual(s["kw_dmg:Power Surge"], 3.6)
        self.assertAlmostEqual(s["kw_chance:Power Surge"], 3.6)
        self.assertAlmostEqual(s["el:Shock"], 3.6)
        self.assertAlmostEqual(s["vs_enemies"], 3.0)

    def test_keyword_gating(self):
        """A Shrapnel-only mod must do nothing on a Power Surge weapon."""
        w = self.w("AUG - Electron Cloud"); ws = {"stars": 6, "tier": 5}
        base = forge.evaluate(w, ws, [], {}, 600)["dps"]
        shr = {"name": "Shrapnel Carnage", "variant": "Survival", "level": 4, "tiers": [1, 1, 1, 1], "slot": "mask"}
        r = forge.evaluate(w, ws, [shr], {}, 600)
        self.assertLess(r["dps"], base * 1.02)
        self.assertTrue(any("only works with Shrapnel" in u for u in r["unmodeled"]))

    def test_more_psi_more_status_damage(self):
        w = self.w("KVD - Boom! Boom!"); ws = {"stars": 1, "tier": 5}
        lo = forge.evaluate(w, ws, [], {}, 300)["dps"]
        hi = forge.evaluate(w, ws, [], {}, 900)["dps"]
        self.assertGreater(hi, lo * 1.3)

    def test_stars_increase_dps(self):
        w = self.w("MPS7 - Outer Space")
        a = forge.evaluate(w, {"stars": 1}, [], {}, 600)["dps"]
        b = forge.evaluate(w, {"stars": 6}, [], {}, 600)["dps"]
        self.assertGreater(b, a)

    def test_all_legendary_weapons_sane(self):
        for name, w in self.gd["weapons"].items():
            d = forge.evaluate(w, {"stars": 1}, [], {}, 600)["dps"]
            self.assertGreater(d, 0, name)
            self.assertLess(d, 60000, name)

    def test_optimize_shape(self):
        r = forge.optimize(forge.load_profile())
        self.assertIn("best", r); self.assertIn("upgrades", r)
        if r["best"]:
            self.assertEqual(set(r["best"]["mods"]), set(forge.MOD_SLOTS))
            for u in r["upgrades"]:
                self.assertIn(u["kind"], {"mod", "weapon", "armor", "stars", "combo", "food", "deviation", "keyarmor", "calibration", "hide", "secondary"})
                self.assertGreaterEqual(u["cost_starchrom"], 0)

    def test_psi_partial_armor_not_tiny(self):
        psi, basis = forge.estimate_psi({"armor": {"Helmet": {"name": "Agent Helmet", "stars": 1}}})
        self.assertGreater(psi, 400)
        self.assertIn("1 of 6", basis)

    def test_conditional_uptime(self):
        scn = fe.SCENARIOS["boss"]
        up, why = fe.estimate_uptime("After switching weapons, Fire Rate +10%", scn, {"hits_per_s": 10, "reload_cycle_s": 6})
        self.assertLess(up, 0.3)


    # ---- build extras, keyword parsing, theory mode
    def test_socr_and_jaws_signatures(self):
        sc = fe.SCENARIOS["boss"]; ctx = {"hits_per_s": 8, "reload_cycle_s": 6, "crit_rate": 0.1, "kw_procs_per_s": 0}
        socr = forge.weapon_signature(self.gd["weapons"]["SOCR - The Last Valor"], sc, ctx)[0]
        self.assertAlmostEqual(socr["kw_base:Shrapnel"], 25.0)
        self.assertEqual(socr.get("_after_crit_extra"), 1.0)
        jaws = forge.weapon_signature(self.gd["weapons"]["DE.50 - Jaws"], sc, ctx)[0]
        self.assertEqual(jaws.get("kw_crit_rate:Unstable Bomber"), 35.0)
        self.assertNotIn("crit_rate", jaws)

    def test_keyword_substats_map(self):
        self.assertEqual(fe.stat_key("Shrapnel Crit"), "kw_crit_dmg:Shrapnel")
        self.assertEqual(fe.stat_key("Shrapnel Weakspot"), "kw_ws_dmg:Shrapnel")
        self.assertEqual(fe.stat_key("Power Surge Crit Rate"), "kw_crit_rate:Power Surge")

    def test_extras_raise_dps_and_gate(self):
        import forge_extras as fx
        w = self.gd["weapons"]["SOCR - The Last Valor"]
        base = forge.evaluate(w, {"stars": 6}, [], {}, 575)["dps"]
        ex = fx.build_extras({"key_armor": "Gas-tight Helmet", "deviation": "Lonewolf's Whisper", "food": "Shattered Bread"}, w["keyword"], "boss")
        self.assertGreater(forge.evaluate(w, {"stars": 6}, [], {}, 575, extras=ex)["dps"], base * 1.4)
        _, notes = fx.extra_sources({"key_armor": "Shaman Vulture Top"}, w["keyword"], "boss")
        self.assertTrue(any("only works with" in n for n in notes))
        _, notes = fx.extra_sources({"deviation": "Shattered Maiden"}, w["keyword"], "abyss")
        self.assertTrue(any("bosses" in n for n in notes))

    def test_abyss_scenario_exists(self):
        self.assertIn("abyss", fe.SCENARIOS)
        self.assertIn("no cradle", fe.SCENARIOS["abyss"]["label"])

    def test_key_armor_not_in_sets(self):
        prof = {"armor": {"Helmet": {"name": "Gas-tight Helmet", "stars": 1}}}
        self.assertEqual(forge.set_counts_from_profile(prof), {})

    def test_theory_ranks_community_meta(self):
        import forge_theory as T
        orig, orig_ws = T.psi_bonus, T.sniper_setting
        T.psi_bonus = lambda: 0.0   # profile-independent: your sheet's extra Psi reorders the ranking
        T.sniper_setting = lambda: None   # ...and so does your sniper weakspot setting
        try:
            r = T.theory("boss")
        finally:
            T.psi_bonus, T.sniper_setting = orig, orig_ws
        names = [b["weapon"]["name"] for b in r["builds"]]
        self.assertIn("SOCR - The Last Valor", names[:8])
        self.assertIn("SN700 - Finale", names[:5])   # community S-tier boss sniper once Reverb is counted
        socr = r["builds"][names.index("SOCR - The Last Valor")]
        self.assertEqual(socr["config"]["key_armor"]["name"], "Gas-tight Helmet")
        self.assertEqual(socr["sets"].get("Lonewolf"), 4)


    def test_quick_edits_apply(self):
        base = {"mods": [{"name": "Deviation Expert", "variant": "Violent", "level": 10}],
                "weapons": [{"name": "AUG - Electron Cloud", "stars": 2}]}
        inv = forge.inventory(base)
        self.assertTrue(any(m["name"] == "Deviation Expert" and m["variant"] == "Violent" for m in inv["mods"]))
        lv = dict(base, mod_edits={"deviation expert|violent": {"level": 15}},
                  weapon_edits={"AUG - Electron Cloud": {"stars": 5}})
        inv = forge.inventory(lv)
        m = [m for m in inv["mods"] if m["name"] == "Deviation Expert" and m["variant"] == "Violent"][0]
        self.assertEqual(m["level"], 15)
        self.assertEqual([w for w in inv["weapons"] if w["name"] == "AUG - Electron Cloud"][0]["stars"], 5)
        rm = dict(base, mod_edits={"deviation expert|violent": {"removed": True}},
                  weapon_edits={"AUG - Electron Cloud": {"removed": True}})
        inv = forge.inventory(rm)
        self.assertFalse(any(m["name"] == "Deviation Expert" and m["variant"] == "Violent" for m in inv["mods"]))
        self.assertFalse(any(w["name"] == "AUG - Electron Cloud" for w in inv["weapons"]))

    def test_icon_map_files_exist(self):
        im = forge.icon_map()
        self.assertGreater(len(im), 300)
        for n in ("Zapamander", "AUG - Electron Cloud", "Shattered Bread"):
            self.assertIn(n, im)
        for url in list(im.values())[:50]:
            self.assertTrue((forge.ROOT / "static" / url.lstrip("/")).exists(), url)

    def test_class_food_slots(self):
        fx = forge.fx
        # non-chef: one food and one drink; a food+drink dish fills both
        self.assertEqual(fx.fit_consumables(["Hearty Meat Stew", "Whimsical Drink"], "freelancer"), (["Hearty Meat Stew"], ["Whimsical Drink"]))
        self.assertEqual(fx.fit_consumables(["Shattered Bread", "Whimsical Drink"], None)[1], [])
        # chef: 2 + 2, the both-dish uses one of each
        kept, dropped = fx.fit_consumables(["Hearty Meat Stew", "Shattered Bread", "Whimsical Drink", "Stargazy Pie"], "chef")
        self.assertEqual(kept, ["Hearty Meat Stew", "Shattered Bread", "Whimsical Drink"])
        self.assertEqual(dropped, ["Stargazy Pie"])
        self.assertEqual(fx.CONSUMABLES["Sparkling Pumpkin Soup"]["slots"], ("drink",))
        self.assertIn("status_dmg", fx.CONSUMABLES["Whimsical Drink"]["stats"])
        # old profiles with food/drink strings still work
        self.assertEqual(fx.consumables_of({"food": "Shattered Bread", "drink": "Whimsical Drink"}), ["Shattered Bread", "Whimsical Drink"])

    def test_chef_beats_freelancer(self):
        w = self.w("AUG - Electron Cloud")
        st = {"name": w["name"], "stars": 6, "tier": 5}
        def dps(cls, names):
            ex = forge.fx.build_extras({"class": cls, "consumables": names}, w.get("keyword"), "boss")
            return forge.evaluate(w, st, [], {}, 600, "boss", extras=ex)["dps"]
        one = forge.fx.best_consumables(lambda n: dps("freelancer", n), "freelancer")
        two = forge.fx.best_consumables(lambda n: dps("chef", n), "chef")
        self.assertGreater(two[0], one[0])
        self.assertLessEqual(len(one[1]), 2)
        self.assertIn("Whimsical Drink", two[1])


class ModTwoPointOhTests(unittest.TestCase):
    def test_level_17_tiers(self):
        import forge
        self.assertEqual(forge.tiers_from_level(17), [5, 5, 5, 2])
        self.assertEqual(forge.tiers_from_level(25), forge.tiers_from_level(17))

    def test_crate_catalog_ids(self):
        import forge_crates
        ids = {c["id"] for c in forge_crates.catalog()["crates"]}
        for need in ("sel_6000", "sel_17", "nonkw_sel", "slot_5000"):
            self.assertIn(need, ids)


class CalibrationStyleTests(unittest.TestCase):
    def test_seasonal_styles_present(self):
        import forge_extras as fx
        for fam, need in {"rifle": ["Vanguard", "Energy"], "smg": ["Vanguard", "Energy"], "lmg": ["Vanguard", "Overflow"],
                          "pistol": ["Boost", "Overflow", "Frugal"], "shotgun": ["Boost"], "sniper": ["Frugal"]}.items():
            for st in need:
                self.assertIn(st, fx.CAL_STYLES[fam])

    def test_old_names_resolve(self):
        import forge_extras as fx
        self.assertEqual(fx.cal_style_name("Energy Style", "rifle"), "Energy")
        self.assertEqual(fx.cal_style_name("Rapid", "rifle"), "Rapid Shot")
        e = fx.calibration_from_profile({"style": "Energy Style", "attack": 40}, "Assault Rifle")
        self.assertEqual(e["attack"], 55)


class HideTests(unittest.TestCase):
    def test_mask_hide_conditions(self):
        import forge_extras as fx
        self.assertEqual(fx.hide_stats("Golden Wool", [])[0], {"weapon_dmg": 6, "status_dmg": 6})
        self.assertEqual(fx.hide_stats("Squid Skin", [])[0], {})
        self.assertEqual(fx.hide_stats("Squid Skin", ["water"])[0], {"status_dmg": 8})
        self.assertEqual(fx.hide_stats("Deer Hide", [])[0], {})


class EffortTests(unittest.TestCase):
    def test_effort_keys(self):
        import forge_effects as fe
        self.assertEqual(fe.split_key("boss@easy"), ("boss", "easy"))
        self.assertEqual(fe.split_key("abyss"), ("abyss", "normal"))
        self.assertEqual(fe.scn("boss@easy")["airborne"], 0.0)
        self.assertGreater(fe.scn("boss@max")["weakspot_rate"], fe.scn("boss")["weakspot_rate"])

    def test_effort_compare_shape(self):
        import forge
        r = forge.effort_compare()
        if not r["builds"]:
            return
        for k in ("easy", "normal", "max"):
            self.assertIn(k, r["builds"])
        self.assertEqual(r["builds"]["max"]["pct_of_max"], 100.0)
        self.assertTrue(r["verdict"])


class UpdateButtonTests(unittest.TestCase):
    """The Update button: diff wording, data swap + undo, NEW! badges, typed items, custom fights.
    Runs against a temporary data/live folder; never touches the network."""

    def setUp(self):
        import copy, json, tempfile, forge_live as fl, forge_update as fu
        self.fl, self.fu, self.json, self.copy = fl, fu, json, copy
        self.tmp = Path(tempfile.mkdtemp())
        self.saved = {k: getattr(fl, k) for k in ("LIVE", "LIVE_SNAP", "HIST", "OVERRIDES", "SEEN", "NAMES", "NEWS", "LOG", "ICON_DIR", "ICON_INDEX", "MENTIONS")}
        fl.LIVE = self.tmp; fl.LIVE_SNAP = self.tmp / "thgl_snapshot.json"; fl.HIST = self.tmp / "history"
        fl.OVERRIDES = self.tmp / "overrides.json"; fl.SEEN = self.tmp / "seen.json"; fl.NAMES = self.tmp / "names.json"
        fl.NEWS = self.tmp / "news.json"; fl.LOG = self.tmp / "updates.jsonl"; fl.ICON_DIR = self.tmp / "icons"; fl.ICON_INDEX = self.tmp / "icons.json"
        fl.MENTIONS = self.tmp / "mentions.json"
        forge.reload_data()

    def tearDown(self):
        import shutil
        for k, v in self.saved.items():
            setattr(self.fl, k, v)
        forge.reload_data()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _old(self):
        return self.json.loads(self.fl.SHIPPED.read_text())

    def test_diff_plain_words(self):
        old = self._old(); new = self.copy.deepcopy(old)
        w = next(x for x in new["weapons"] if x["name"] == "MPS7")
        w["magazine"] -= 10
        new["weapons"].append({**new["weapons"][0], "name": "Test Gun - New", "id": "1"})
        d = self.fu.diff_snapshots(old, new)
        line = next(c for c in d["changes"] if c["name"] == "MPS7")["lines"][0]
        self.assertIn("10 fewer bullets", line)
        self.assertEqual([a["name"] for a in d["added"]], ["Test Gun - New"])
        self.assertTrue(self.fu.validate(old, new)[0])
        new["weapons"] = new["weapons"][:10]
        self.assertFalse(self.fu.validate(old, new)[0])

    def test_swap_new_badge_and_undo(self):
        self.fl.mark_seen(forge.gamedata())                     # first run = baseline, nothing NEW
        self.assertEqual(self.fl.new_marks(), {})
        new = self._old()
        new["retrieved_at"] = "2099-01-01T00:00:00+00:00"
        new["weapons"].append({**next(x for x in new["weapons"] if x["name"] == "MPS7"), "name": "MPS7 - Test Visitor", "id": "77"})
        self.fu.backup_and_swap(new); forge.reload_data()
        self.assertEqual(forge.gamedata()["retrieved_at"], "2099-01-01T00:00:00+00:00")
        added = self.fl.mark_seen(forge.gamedata())
        self.assertIn("weapon:MPS7 - Test Visitor", added)
        self.assertNotIn("weapon:MPS7 - Test Visitor", self.fl.new_marks())   # no patch note names it yet
        self.assertIn("weapon:MPS7 - Test Visitor", self.fl.classify()["data"])
        self._post("Test Visitor", "announced")
        self.assertIn("weapon:MPS7 - Test Visitor", self.fl.new_marks())
        self.fl.set_verdict("weapon:MPS7 - Test Visitor", "not_new")
        self.assertNotIn("weapon:MPS7 - Test Visitor", self.fl.new_marks())
        self.fu.rollback()
        self.assertNotEqual(forge.gamedata()["retrieved_at"], "2099-01-01T00:00:00+00:00")

    def _post(self, name, how="named", scenario=None, url="https://example.invalid/post1", title="Test patch notes"):
        import datetime as dt
        self.fl.add_mentions({"url": url, "title": title, "date": dt.date.today().isoformat(), "kind": "update", "scenario": scenario},
                             [{"name": name, "how": how, "scenario": scenario, "line": f"New: {name}"}])

    def test_first_read_of_a_list_is_baseline(self):
        self.fl.mark_seen(forge.gamedata())
        names = {"consumables": {"Old Soup": {"text": ""}, "Older Stew": {"text": ""}}, "deviations": {"Old Pal": {}}}
        self.assertEqual(self.fl.mark_seen(forge.gamedata(), "update button", names), [])   # first food list: nothing NEW
        self.assertEqual(self.fl.new_marks(), {})
        names["consumables"]["Brand New Chowder"] = {"text": ""}
        self.assertEqual(self.fl.mark_seen(forge.gamedata(), "update button", names), ["food:Brand New Chowder"])
        c = self.fl.classify()
        self.assertIn("food:Brand New Chowder", c["data"])        # on th.gl, but no post names it
        self.assertNotIn("food:Brand New Chowder", c["new"])
        self._post("Brand New Chowder", "named")
        m = self.fl.new_marks()["food:Brand New Chowder"]
        self.assertEqual(m["post"]["title"], "Test patch notes")
        self.assertEqual(m["dps"], "no numbers")

    def test_legacy_seen_is_repaired(self):
        self.fl.write_json(self.fl.SEEN, {"baseline_at": "2026-11-05T11:55:51+00:00", "verdicts": {}, "items": {
            "weapon:MPS7": {"first": "baseline", "via": "app"},
            "food:Steak": {"first": "2026-11-05", "via": "app"},
            "deviation:Chillet": {"first": "2026-11-05", "via": "app"},
            "weapon:MPS7 - Real New": {"first": "2026-11-05", "via": "update button"}}})
        s = self.fl.seen()
        self.assertEqual(s["items"]["food:Steak"]["first"], "baseline")
        self.assertEqual(s["items"]["deviation:Chillet"]["first"], "baseline")
        self.assertEqual(s["items"]["weapon:MPS7 - Real New"]["first"], "2026-11-05")
        self.assertEqual(s["repairs"][0]["fixed"], 2)
        self.assertIn("thgl:food", s["sources"])

    def test_scenario_post_labels_items(self):
        names = {"Mistcore Clarity Soup": "food", "Salt": "food", "SOCR - Cosmic Visitor": "weapon", "Cosmic Visitor": "weapon"}
        a = self.fu.analyse_post("Dev Blog | New Survival Scenario Isles of Abyss Launches Officially on October 21",
                                 ["Mist of Deceit: Mist Core Clarity Soup increases Cold Resist.", "New Deviation: Duet"], names)
        self.assertEqual(a["title_scenario"], "Isles of Abyss")
        soup = next(f for f in a["found"] if f["name"] == "Mistcore Clarity Soup")   # 'Mist Core' vs 'Mistcore'
        self.assertEqual(soup["scenario"], "Isles of Abyss")
        self.assertTrue(any(f["name"] == "Duet" and f["how"] == "announced" for f in a["found"]))
        b = self.fu.analyse_post("Version 3.1.2 Update Announcement (November 4)",
                                 ["1) New additions to Blueprints, Weapons, Gear, and Custom Weapons: Snowline Elite Vest and SOCR Cosmic Visitor.",
                                  "2) Isles of Abyss Scenario: new Custom Dungeon — Heart of the Sunken."], names, ["Isles of Abyss"])
        self.assertIsNone(b["title_scenario"])
        cv = next(f for f in b["found"] if f["name"] in ("Cosmic Visitor", "SOCR - Cosmic Visitor"))
        self.assertIsNone(cv["scenario"])                       # general patch note line: no Abyss label
        # baseline item named in the Abyss post: scenario label, but no NEW!
        self.fl.mark_seen(forge.gamedata(), "app", {"consumables": {"Mistcore Clarity Soup": {}}, "deviations": {}})
        self.fl.add_mentions({"url": "https://example.invalid/abyss", "title": "Isles of Abyss", "date": "2026-10-16", "scenario": "Isles of Abyss"}, a["found"])
        c = self.fl.classify()
        self.assertEqual(c["scenario"]["food:Mistcore Clarity Soup"]["scenario"], "Isles of Abyss")
        self.assertFalse(c["scenario"]["food:Mistcore Clarity Soup"]["new"])
        self.assertNotIn("food:Mistcore Clarity Soup", c["new"])

    def test_recent_announcement_marks_baseline_item_new(self):
        import datetime as dt
        self.fl.mark_seen(forge.gamedata())                       # MPS7 is baseline
        old = (dt.date.today() - dt.timedelta(days=30)).isoformat()
        self.fl.add_mentions({"url": "https://example.invalid/blog", "title": "Dev Blog | New Weapons Coming Soon", "date": old, "kind": "devBlog"},
                             [{"name": "MPS7", "how": "announced", "line": "New Weapon: MPS7"}])
        m = self.fl.new_marks()["weapon:MPS7"]                    # dev blog preview: 21 + 14 days
        self.assertEqual((m["via"], m["dps"]), ("announced", "gear"))
        self.fl.add_mentions({"url": "https://example.invalid/blog", "title": "Old notes", "date": old, "kind": "update"},
                             [{"name": "MPS7", "how": "announced", "line": "New Weapon: MPS7"}])
        self.assertNotIn("weapon:MPS7", self.fl.new_marks())     # patch note older than 21 days: not new any more

    def test_typed_food_counts(self):
        import forge_extras as fx
        self.fl.save_item("consumables", "Test Pie", {"slots": ["food"], "text": "Weapon DMG +40%"})
        self.assertIn("Test Pie", fx.FOODS)
        self.assertEqual(fx.CONSUMABLES["Test Pie"]["stats"], {"weapon_dmg": 40.0})
        self.fl.save_item("consumables", "Test Pie", None)
        self.assertNotIn("Test Pie", fx.FOODS)

    def test_custom_fight_buffs_raise_dps(self):
        self.fl.save_item("scenarios", self.fl.scenario_key("Test Isles"), {"name": "Test Isles", "base": "boss", "buff_text": "Weapon DMG +50%"})
        key = self.fl.scenario_key("Test Isles")
        self.assertIn(key, fe.SCENARIOS)
        self.assertEqual(fe.split_key(key + "@easy"), (key, "easy"))
        w = forge.gamedata()["weapons"]["AUG - Electron Cloud"] if "AUG - Electron Cloud" in forge.gamedata()["weapons"] else next(iter(forge.gamedata()["weapons"].values()))
        st = {"name": w["name"], "stars": 1, "tier": 5}
        plain = forge.evaluate(w, st, [], {}, 300, "boss", extras=forge.fx.build_extras({}, w.get("keyword"), "boss"))["dps"]
        buffed = forge.evaluate(w, st, [], {}, 300, key, extras=forge.fx.build_extras({}, w.get("keyword"), key))["dps"]
        self.assertGreater(buffed, plain * 1.2)

    def test_patch_note_reader(self):
        lines = ["Dear Metas,", "I. New Weapon", "KV-SBR - Star Test", "New Deviation: Bubble Pal",
                 "Reduced Shrapnel DMG from 50% to 40%.", "[Sunken Test] Scenario: new things"]
        a = self.fu.analyse_post("Dev Blog | Test", lines, {"Shrapnel": "keyword"})
        self.assertEqual([x["name"] for x in a["announced"]], ["KV-SBR - Star Test", "Bubble Pal"])
        self.assertIn("Sunken Test", a["scenarios"])
        self.assertTrue(any("balance" in h["tags"] for h in a["highlights"]))

class HideAndWordingTests(unittest.TestCase):
    def test_page_boilerplate_is_not_a_change(self):
        import forge_update as fu
        a = "Inflicts Burn. Crafted In Advanced Gear Workbench Details Obtain Craft at Camp"
        b = "Inflicts Burn. Crafted In Advanced Gear Workbench Unlock Torch B.P. Details Obtain Craft at Camp"
        self.assertEqual(fu.text_change("Weapon effect", a, b), [])
        self.assertTrue(fu.text_change("Weapon effect", "Burn DMG +20%.", "Burn DMG +15%."))

    def test_every_mask_hide_says_where_it_comes_from(self):
        import forge_extras as fx
        self.assertEqual([n for n in fx.MASK_HIDES if n not in fx.HIDE_ORIGIN], [])
        self.assertEqual(fx.HIDE_ORIGIN["Golden Wool"][1], "Golden Sheep Bloodline")
        self.assertIn("water", fx.HIDE_ORIGIN["Bay Crocodile Skin"][2])


class DeviationGuideTests(unittest.TestCase):
    def test_every_deviation_has_a_plain_words_entry(self):
        import forge_devguide as dg
        names = forge.ui_catalog()["all_deviations"]
        self.assertEqual([n for n in names if n not in dg.G], [])
        for n, g in dg.G.items():
            self.assertTrue(g["job"] and g["tier"] in dg.TIER_LABEL and g["tag"] in dg.TAG_LABEL, n)

    def test_keep_or_toss(self):
        import forge_devguide as dg
        digby = next(n for n in dg.G if "Digby" in n)
        lone = next(n for n in dg.G if "Lonewolf" in n)
        grow = next(n for n in dg.G if "Growshroom" in n)
        self.assertEqual(dg.keep_verdict(digby, 4, 4)["keep"], "keep")
        self.assertEqual(dg.keep_verdict(digby, 4, 1)["keep"], "toss")
        self.assertEqual(dg.keep_verdict(lone, 5, 1)["keep"], "keep")
        self.assertEqual(dg.keep_verdict(grow, 5, 2)["keep"], "toss")
        self.assertEqual(dg.keep_verdict(grow, 2, 5)["keep"], "keep")


class FreshStartTests(unittest.TestCase):
    def setUp(self):   # temp copy of the database, so the installer's test run never touches the real profile
        import shutil, tempfile
        self.saved_db, self.tmp = forge.DB, Path(tempfile.mkdtemp())
        if Path(forge.DB).exists():
            shutil.copy(forge.DB, self.tmp / "t.sqlite3")
        forge.DB = self.tmp / "t.sqlite3"

    def tearDown(self):
        import shutil
        forge.DB = self.saved_db
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_fresh_start_and_restore_round_trip(self):
        before = forge.load_profile()
        if before.get("fresh"):
            self.skipTest("profile already in fresh mode")
        inv_before = forge.inventory(before)
        try:
            p = forge.start_fresh(5000)
            self.assertTrue(p["fresh"]); self.assertEqual(p["starchrom"], 5000)
            self.assertEqual(forge.inventory(p), {"mods": [], "weapons": []})
            s = __import__("forge_starter").plan(p, "boss")
            self.assertIn("weapon", s["pick"])
            self.assertTrue(any("Save" in st["title"] for st in s["steps"]))   # 5,000 < one legendary gun
        finally:
            back = forge.restore_profile()
        self.assertFalse(back["fresh"])
        self.assertEqual(forge.inventory(back), inv_before)


class ProfileSlotTests(unittest.TestCase):
    """Three named profiles. Runs on a temporary copy of the database, never the real one."""

    def setUp(self):
        import shutil, tempfile
        self.saved_db = forge.DB
        self.tmp = Path(tempfile.mkdtemp())
        if Path(forge.DB).exists():
            shutil.copy(forge.DB, self.tmp / "t.sqlite3")
        forge.DB = self.tmp / "t.sqlite3"
        with forge.db(False) as con:
            for t in ("forge_profile_slots", "forge_profile_meta", "forge_profile"):
                con.execute(f"drop table if exists {t}")
        forge.ensure_profile_table()
        forge.save_profile({"starchrom": 111, "fresh": False})

    def tearDown(self):
        import shutil
        forge.DB = self.saved_db
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_three_named_slots_round_trip(self):
        S = forge.profile_slots()
        self.assertEqual([s["slot"] for s in S["slots"]], [1, 2, 3])
        self.assertEqual((S["active"], S["slots"][0]["name"], S["slots"][1]["empty"]), (1, "My profile", True))
        forge.slot_action("rename", 1, "  Main   chef ")
        forge.slot_action("rename", 2, "")                        # blank name falls back to a default
        S = forge.profile_slots()
        self.assertEqual((S["slots"][0]["name"], S["slots"][1]["name"]), ("Main chef", "Profile 2"))
        forge.slot_action("save", 2, "Abyss alt")                 # copy into slot 2; slot 2 is now in use
        forge.save_profile({"starchrom": 222})                   # edits go to the slot in use
        p = forge.slot_action("load", 1)
        self.assertEqual(p["starchrom"], 111)
        p = forge.slot_action("load", 2)
        self.assertEqual(p["starchrom"], 222)
        with self.assertRaises(ValueError):
            forge.slot_action("clear", 2)                         # can't empty the one in use
        with self.assertRaises(ValueError):
            forge.slot_action("load", 3)                          # empty slot
        with self.assertRaises(ValueError):
            forge.slot_action("load", 4)
        forge.slot_action("clear", 1)
        self.assertTrue(forge.profile_slots()["slots"][0]["empty"])
        self.assertTrue(any("cleared slot 1" in s["label"] for s in forge.profile_saves()))   # backup kept

    def test_switching_back_and_forth_is_lossless(self):
        forge.profile_slots()
        main = forge.load_profile()
        forge.slot_action("save", 2, "New player test")
        forge.start_fresh(5000)
        forge.slot_action("save", 2)                              # slot 2 = a fresh-start profile
        test = forge.load_profile()
        for _ in range(3):
            self.assertEqual(forge.slot_action("load", 1), main)
            self.assertEqual(forge.load_profile(), main)
            self.assertEqual(forge.slot_action("load", 2), test)
            self.assertEqual(forge.load_profile(), test)
        S = forge.profile_slots()["slots"]
        self.assertEqual((S[0]["fresh"], S[1]["fresh"]), (False, True))   # each slot keeps its own setting

    def test_fresh_start_leaves_slot_alone(self):
        forge.profile_slots()
        p = forge.start_fresh(5000)
        self.assertTrue(p["fresh"])
        S = forge.profile_slots()
        self.assertIsNone(S["active"])
        self.assertFalse(S["slots"][0]["fresh"])                  # slot 1 still holds the real profile
        self.assertEqual(forge.slot_action("load", 1)["starchrom"], 111)


class WearingNowTests(unittest.TestCase):
    def test_mods_on_gear_right_now(self):
        p = json.loads(json.dumps(forge.load_profile()))
        if p.get("fresh") or not forge.owned_weapons(p):
            self.skipTest("needs a profile with a gun")
        gun = forge.owned_weapons(p)[0]["name"]
        p.setdefault("extras", {})["equipped"] = {"helmet": {"name": "Momentum Up", "variant": "Violent", "level": 9}}
        p["extras"]["equipped_weapon"] = gun
        r = forge.optimize(p)
        w = r["wearing"]
        self.assertEqual(w["weapon"], gun)
        self.assertEqual(w["slots"]["helmet"]["name"], "Momentum Up")
        self.assertIn("mask", w["empty"])
        self.assertGreater(w["dps"], 0)
        self.assertLessEqual(w["dps"], r["best"]["dps"] + 1)   # best with what you own can't be worse
        # the mod on your helmet counts as owned even if it wasn't recorded
        self.assertTrue(any(m["name"] == "Momentum Up" and m["variant"] == "Violent" for m in forge.owned_mods(p)))


class OwnedArmorTests(unittest.TestCase):
    def _set_pieces(self, n=4):
        gd = forge.gamedata()
        for name, st in gd["sets"].items():
            ps = [a for a in gd["armor"].values() if forge.set_key(a) == name and a["name"] not in forge.fx.KEY_ARMOR]
            if len({a["slot"] for a in ps}) >= n:
                by = {}
                for a in ps:
                    by.setdefault(a["slot"], a["name"])
                return name, list(by.items())
        self.skipTest("no set with enough pieces")

    def test_two_helmets_from_different_sets(self):
        gd = forge.gamedata()
        helmets = {}
        for a in gd["armor"].values():
            if a.get("slot") == "Helmet" and a["name"] not in forge.fx.KEY_ARMOR:
                helmets.setdefault(forge.set_key(a), a["name"])
        h1, h2 = list(helmets.values())[:2]
        p = {"armor": {"Helmet": {"name": h1, "stars": 3}}, "armor_owned": {h2: {"stars": 2}}}
        o = forge.owned_armor(p)
        self.assertEqual(set(o), {h1, h2})
        self.assertTrue(o[h1]["worn"]); self.assertFalse(o[h2]["worn"])
        self.assertEqual(o[h1]["stars"], 3); self.assertEqual(o[h2]["stars"], 2)

    def test_owned_pieces_cost_nothing(self):
        name, pieces = self._set_pieces()
        p = {"armor": {}, "armor_owned": {n: {"stars": 1} for _, n in pieces[:4]}}
        self.assertEqual(forge.pieces_to_get(p, {name: 4})[0], 0)
        p2 = {"armor": {}, "armor_owned": {pieces[0][1]: {"stars": 1}}}
        self.assertEqual(forge.pieces_to_get(p2, {name: 4})[0], 3)
        self.assertEqual(forge.pieces_to_get({"armor": {}}, {name: 4})[0], 4)
        # two sets can't share one slot
        self.assertEqual(forge.pieces_to_get(p, {name: 4, "No Such Set": 2})[0], 2)


if __name__ == "__main__":
    unittest.main()


class ModScreenArtTests(unittest.TestCase):
    def test_every_variant_has_game_glyph_and_game_order(self):
        import forge_modart as ma
        c = forge.ui_catalog()
        art = c["mod_art"]
        for m in c["mods"]:
            for v in (m["variants"] or ["General"]):
                self.assertIn(f"{m['slot']}|{m['name']}|{v}".lower(), art["tiles"], (m["name"], v))
        self.assertEqual(art["slots"], ["weapon", "helmet", "top", "bottoms", "shoes", "gloves", "mask"])
        self.assertLess(art["order"]["helmet|precise strike"], art["order"]["helmet|deviation expert"])
        locked = sorted(["Crescent Deviant Energy", "Lunar", "General", "Crescent", "Lunar Deviant Energy"], key=ma.variant_rank)
        self.assertEqual(locked, ["General", "Lunar", "Crescent", "Lunar Deviant Energy", "Crescent Deviant Energy"])


class ModInfoTests(unittest.TestCase):
    def test_tooltip_matches_game_card_and_lines_feed_dps(self):
        # in-game card: First-Move Advantage <General> Lv 8 = DMG +2.4%, Mag +4.8%, Reload +3.6%, all DMG +3.0%
        I = forge.mod_info("First-Move Advantage", "General", 8)
        self.assertEqual([l["text"] for l in I["lines"]], ["+2.4%", "+4.8%", "+3.6%", "+3%"])
        self.assertTrue(all(l["counted"] for l in I["lines"]))
        st = forge.mod_substats({"name": "First-Move Advantage", "variant": "General", "tiers": forge.tiers_from_level(8)})
        self.assertEqual(st, {"dmg_boost": 2.4, "magazine": 4.8, "reload_speed": 3.6, "vs_enemies": 3.0})

    def test_mirror_and_wild_firearm_lines_now_count(self):
        m = forge.mod_substats({"name": "Healing Fortification", "variant": "Mirror", "tiers": forge.tiers_from_level(16)})
        w = forge.mod_substats({"name": "Healing Fortification", "variant": "Wild", "tiers": forge.tiers_from_level(16)})
        self.assertGreater(m.get("weapon_dmg", 0), 4)
        self.assertGreater(w.get("weapon_dmg", 0), 3)
        hp = [l for l in forge.mod_info("Healing Fortification", "Mirror", 16)["lines"] if "taken" in l["line"]]
        self.assertFalse(hp[0]["counted"])


class FourthLineConfirmedTests(unittest.TestCase):
    def test_in_game_tooltips(self):
        # screenshots 2026-11-05: Rejuvenating <Violent> Lv15, Shock Rampage <Power Surge> Lv17
        a = [l["text"] for l in forge.mod_info("Rejuvenating", "Violent", 15)["lines"]]
        b = [l["text"] for l in forge.mod_info("Shock Rampage", "Power Surge", 17)["lines"]]
        self.assertEqual(a, ["+15%", "+4.8%", "+9.6%", "+3%"])
        self.assertEqual(b, ["+6%", "+6%", "+6%", "+3%"])


class BestOwnedArmorTests(unittest.TestCase):
    def test_set_effect_wording_parses(self):
        sc = forge.fe.scn(list(forge.fe.SCENARIOS)[0])
        a = forge.fe.merge(forge.fe.parse_effect("Element DMG (Blaze, Frost, Shock, Blast) +8%", sc, {}).contributions)
        self.assertEqual(a.get("el:Shock"), 8.0)
        b = forge.fe.parse_effect("While shielded, Weapon DMG and Status DMG dealt increases by +10%.", sc, {"shield_uptime": 0.9})
        self.assertAlmostEqual(forge.fe.merge(b.contributions)["weapon_dmg"], 9.0)

    def test_finds_better_owned_piece_and_keeps_good_armor(self):
        prof = forge.load_profile()
        if not prof.get("armor") or not forge.owned_weapons(prof):
            self.skipTest("needs a profile with armor and a weapon")
        r = forge.optimize(prof)
        self.assertIn("best_armor", r)
        A = r["best_armor"]
        self.assertTrue(A is None or "error" not in A)
        if A:
            self.assertGreaterEqual(A["dps"], r["best"]["dps"] - 1)


class ArmorTabOrderTests(unittest.TestCase):
    def test_armor_tabs_follow_game_id_order(self):
        o = forge.ui_catalog()["mod_art"]["order"]
        rows = lambda sl: [k.split("|", 1)[1] for k, v in sorted(o.items(), key=lambda kv: kv[1]) if k.startswith(sl + "|")]
        self.assertEqual(rows("bottoms")[:6], ["reload rampage", "three strikes", "bullet siphon", "deadshot", "abnormal increase", "melee momentum"])
        self.assertEqual(rows("bottoms")[-2:], ["critical surge", "precision load"])
        self.assertEqual(rows("shoes")[0], "covered advance")
        self.assertEqual(rows("gloves")[0], "crit boost")


class FastGunnerFamilyTests(unittest.TestCase):
    def test_all_four_fast_gunner_mods_present(self):
        names = {m["name"] for m in forge.ui_catalog()["mods"] if m.get("slot") == "weapon"}
        for n in ("Shoot Out", "Precision Rush", "Shooting Blitz", "Cowboy"):
            self.assertIn(n, names)


class SurvivabilityTests(unittest.TestCase):
    def test_text_effects(self):
        import forge_survive as S
        self.assertEqual(S.text_effects("Max HP +10%")[0][0]["kind"], "hp_pct")
        self.assertEqual(S.text_effects("While shielded, Weapon DMG and Status DMG dealt increases by +10%."), ([], True))
        self.assertEqual(S.text_effects("Generates a shield equal to 30% of Max HP when HP is below 40% of the Max. Cooldown: 8s.")[0][0]["value"], 30.0)

    def test_toughness_counts_armor_hp(self):
        import forge_survive as S
        lay = {"Top": {"name": "Shelterer Top", "stars": 6}}
        t = S.toughness(lay, [])
        self.assertEqual(t["hp_armor"], 2405)
        self.assertGreaterEqual(t["toughness"], 2405)

    def test_island_crate(self):
        import forge_crates as C
        names = {n for n, v, s in C.candidates(C.CRATE_BY_ID["island_17"])}
        self.assertEqual(names, {"Precision Load", "Turret Enhancement"})


class DustCrateMenuTests(unittest.TestCase):
    def test_no_general_armor_and_menu_path(self):
        import forge_crates as C
        cr = C.CRATE_BY_ID["sel_6000"]
        armor = [(n, v) for n, v, s in C.candidates(cr) if s in C.ARMOR]
        self.assertTrue(armor)
        self.assertFalse([1 for n, v in armor if v == "General"])
        m = C.menu_path(cr, "Abnormal Increase", "Deviant Energy", "bottoms")
        self.assertEqual(m["steps"], ["Lower Body Module Selection Box", "Lower Body – Deviant Energy", "Abnormal Increase"])


class MagazineChoiceTests(unittest.TestCase):
    def setUp(self):
        self.w = forge.gamedata()["weapons"]["AUG - Electron Cloud"]
        self.ws = {"name": self.w["name"], "stars": 6, "tier": 5,
                   "calibration": {"style": "Rapid Shot", "attack": 40, "sub": "crit_rate", "sub_value": 14}}

    def test_extended_mag_adds_rounds_and_slows_reload(self):
        a = forge.evaluate(self.w, self.ws, [], {}, 800)["derived"]
        b = forge.evaluate(self.w, dict(self.ws, magazine_acc="extended_rifle"), [], {}, 800)["derived"]
        self.assertEqual(b["magazine"], a["magazine"] + 10)
        self.assertAlmostEqual(b["reload_s"], a["reload_s"] * 1.10 / 1.01, places=1)

    def test_zone_uptime_drops_when_cycle_is_longer_than_zone(self):
        r = forge.evaluate(self.w, dict(self.ws, reload_s=6.0, magazine_acc="extended_rifle"), [], {}, 800)["derived"]
        self.assertGreater(r["cycle_s"], 7)
        self.assertLess(r["zone_uptime"], 1)

    def test_choice_rows_cover_every_rifle_mag(self):
        mc = forge.magazine_choice(self.w, self.ws, [], {}, 800, "boss", None, ["amended_rifle"])
        ids = {r["id"] for r in mc["rows"]}
        self.assertTrue({None, "amended_rifle", "extended_rifle"} <= ids)
        self.assertNotIn("large_lmg_drum", ids)
        self.assertEqual(mc["best_owned"] in (None, "amended_rifle"), True)

    def test_recorded_calibration_rolls_are_counted(self):
        cal = {"style": "Energy Style", "fixed_effects": "After taking damage, automatically reload 1 bullet. Attack +10%.",
               "rolls": [{"stat": "Weapon DMG", "value_percent": 42.4}, {"stat": "Elemental DMG (Blaze)", "value_percent": 17.5}]}
        st = forge.calibration_stats(cal, "Assault Rifle")
        self.assertAlmostEqual(st["attack"], 52.4)
        self.assertAlmostEqual(st["elemental_dmg"], 17.5)


class TheoryCeilingTests(unittest.TestCase):
    def test_psi_from_outside_armor_is_counted(self):
        import forge_theory as T
        orig = forge.load_profile
        prof = {"armor": {s: {"name": n, "stars": 6, "tier": 5} for s, n in
                          (("helmet", "Mayfly Goggles"), ("mask", "Shelterer Mask"), ("top", "Shelterer Top"),
                           ("gloves", "Savior Gloves"), ("bottoms", "Savior Pants"), ("shoes", "Savior Shoes"))},
                "psi_intensity": 912}
        try:
            forge.load_profile = lambda *a, **k: dict(prof)
            armor = forge.estimate_psi({"armor": prof["armor"]}, {})[0]
            self.assertAlmostEqual(T.psi_bonus(), round((912 - armor) / 10) * 10)
            self.assertGreater(T.theory_psi(), T.max_psi())
        finally:
            forge.load_profile = orig

    def test_route_commit_keeps_only_target(self):
        import forge_path as FP
        prof = {"fresh": True, "weapons": [{"name": "AUG - Electron Cloud", "stars": 6, "tier": 5}], "mods": []}
        FP._commit(prof, "PDW90 - Holographic Resonance")
        self.assertEqual([w["name"] for w in forge.owned_weapons(prof)], ["PDW90 - Holographic Resonance"])


class ReverbSniperTests(unittest.TestCase):
    FINALE = {"name": "SN700 - Finale", "effect_text": "[Reverb] Hits have 40% probability to trigger Shrapnel; "
              "a weakspot always triggers it. Stacks up to a maximum of 4 stacks."}

    def test_sniper_rate_default_and_setting(self):
        self.assertAlmostEqual(forge.sniper_weakspot_rate(0.35), 0.70)
        self.assertAlmostEqual(forge.sniper_weakspot_rate(0.6), 0.90)
        self.assertAlmostEqual(forge.sniper_weakspot_rate(0.35, 50), 0.50)
        self.assertAlmostEqual(forge.sniper_weakspot_rate(0.35, ""), 0.70)

    def test_reverb_trigger_and_parts(self):
        self.assertIsNone(forge.reverb_model({"effect_text": "nothing"}, 10, 0.7, 1, {}))
        r = forge.reverb_model(self.FINALE, 10, 0.5, 1, {})
        self.assertAlmostEqual(r["p_trigger"], 0.5 + 0.5 * 0.4)
        self.assertGreater(r["parts_per_trigger"], 1)
        self.assertGreater(r["last_bullet_bonus"], 0)
        big = forge.reverb_model(self.FINALE, 20, 0.5, 1, {})
        # more bullets = more Shrapnel per magazine (the per-trigger average can dip: last-bullet burst is spread thinner)
        self.assertGreater(big["parts_per_trigger"] * 20, r["parts_per_trigger"] * 10)
        self.assertLessEqual(big["parts_per_trigger"], 1 + 4 + 4 * 5)
        single = forge.reverb_model(self.FINALE, 10, 0.5, 1, {"_shrapnel_single": True})
        self.assertLess(single["parts_per_trigger"], r["parts_per_trigger"])

    def test_finale_dps_rises_with_weakspot_setting(self):
        prof = {"fresh": True, "weapons": [{"name": "SN700 - Finale", "stars": 6, "tier": 5}], "mods": [],
                "extras": {"sniper_ws": 35}}
        low = forge.optimize(json.loads(json.dumps(prof)))["best"]["dps"]
        prof["extras"]["sniper_ws"] = 90
        high = forge.optimize(prof)["best"]["dps"]
        self.assertGreater(high, low * 1.3)


class RifleMagShopTests(unittest.TestCase):
    def test_assault_rifle_gets_only_shop_mags(self):
        import forge_accessories as A
        self.assertEqual(set(A.compatible({"type": "Assault Rifle"})), {"extended_rifle", "light_rifle", "amended_rifle"})
        self.assertNotIn("quick", A.MAGAZINES)
        self.assertNotIn("expanded", A.MAGAZINES)


class GearCoverageTests(unittest.TestCase):
    """Every armor piece / set / mod the game has should be pickable and counted."""

    def setUp(self):
        import forge as F
        self.F = F
        self.g = F.gamedata()

    def test_every_non_set_armor_piece_has_a_key_armor_entry(self):
        import forge_extras as fx
        missing = [n for n, a in self.g["armor"].items()
                   if not a.get("set") and not a.get("set_effects") and n not in fx.KEY_ARMOR]
        self.assertEqual(missing, [])

    def test_supplement_sets_exist_and_base_blackstone_is_intact(self):
        sets = self.g["sets"]
        for s in ("Blackstone Heat", "Blackstone Cold", "Snowland Rustic"):
            self.assertIn(s, sets)
        base = [n for n, a in self.g["armor"].items() if a.get("set") == "Blackstone"]
        self.assertEqual(len(base), 6)
        heat = [n for n, a in self.g["armor"].items() if a.get("set") == "Blackstone Heat"]
        self.assertEqual(len(heat), 6)

    def test_new_weapon_mods_parse(self):
        import forge_effects as fe
        want = {"Munitions Amplifier": {"weapon_dmg": 9}, "Crit Rate Enhancement": {"crit_rate": 9},
                "Crit DMG Enhancement": {"crit_rate": 2, "crit_dmg": 12}, "Status Enhancement": {"status_dmg": 12}}
        for name, stats in want.items():
            p = fe.parse_effect(self.F._core_text(name), fe.scn("boss"), {})
            self.assertEqual(fe.merge(p.contributions), stats, name)

    def test_mod_aliases_resolve_but_are_not_listed_twice(self):
        m = self.g["mods"]
        self.assertEqual(m["unstoppable"]["name"], "Distant Strike")
        self.assertEqual(m.get("fateful strike")["name"], "Fortune's Favor")
        self.assertIn("overflow", m)
        self.assertNotIn("unstoppable", list(m))

    def test_snowdrift_top_only_fits_sks_pathfinder(self):
        import forge_extras as fx
        self.assertTrue(fx.key_armor_fits("Snowdrift Top", "Frost Vortex", "SKS - Pathfinder"))
        self.assertFalse(fx.key_armor_fits("Snowdrift Top", "Frost Vortex", "KAM - Abyss Glance"))

    def test_old_key_armor_names_still_map(self):
        import forge_extras as fx
        self.assertEqual(fx.KEY_ARMOR_ALIASES["Dust Mask"], "Desert Dust Mask")
        self.assertIn(fx.KEY_ARMOR_ALIASES["Dust Mask"], fx.KEY_ARMOR)

    def test_new_items_show_in_pickers(self):
        import json
        s = json.dumps(self.F.ui_catalog())
        for n in ("Blackstone Hood - Heat", "Snowland Rustic Jacket", "Munitions Amplifier", "Snowdrift Top"):
            self.assertIn(n, s)


class SharingAndSpeedTests(unittest.TestCase):
    def test_optimize_cache_returns_copies_and_tracks_inputs(self):
        import copy, forge as F
        if not F.DB.exists():
            self.skipTest("no database in this copy (the server creates it on start)")
        prof = copy.deepcopy(F.DEFAULT_PROFILE); prof["fresh"] = True
        a = F.optimize(copy.deepcopy(prof)); a["junk"] = 1
        self.assertNotIn("junk", F.optimize(copy.deepcopy(prof)))
        prof["starchrom"] = 12345
        F.optimize(copy.deepcopy(prof))
        self.assertTrue(any(json.loads(k[0]).get("starchrom") == 12345 for k in F._OPT_CACHE))

    def test_data_folder_can_live_outside_the_app(self):
        import os, subprocess, sys, tempfile
        with tempfile.TemporaryDirectory() as d:
            out = subprocess.run([sys.executable, "-c", "import forge,forge_live;print(forge.DB);print(forge_live.LIVE)"],
                                 env={**os.environ, "OH_ADVISOR_DATA": d}, capture_output=True, text=True, cwd=str(Path(__file__).resolve().parents[1]))
            lines = out.stdout.split()
            self.assertTrue(lines[0].startswith(str(Path(d).resolve())), out.stderr)
            self.assertTrue(lines[1].startswith(str(Path(d).resolve())))

    def test_app_loads_without_the_original_recording(self):
        import aug_blueprint_preview as A
        from unittest import mock
        with mock.patch.object(A.Path, "is_file", return_value=False):
            import planned_advisor as P
            prev = A.load_current(P.NATIVE_TIER_STAR_EVIDENCE["by_blueprint"][13451401])
        self.assertIsNone(prev["frame_url"])


class CradleMapTests(unittest.TestCase):
    def _src(self, cfg, weapon="AUG - Electron Cloud", scenario="boss"):
        import forge_extras as fx
        w = forge.gamedata()["weapons"][weapon]
        srcs, notes = fx.extra_sources(dict(cfg, weapon=weapon), w.get("keyword"), scenario)
        return [n for n, _ in srcs if n.endswith("(Cradle)")], notes

    def test_isles_of_abyss_has_no_cradle(self):
        names, notes = self._src({"map": "isles_of_abyss", "cradle": ["Anti-Void"]})
        self.assertEqual(names, [])
        self.assertTrue(any("No Cradle" in n for n in notes))

    def test_no_map_keeps_old_behaviour(self):
        self.assertEqual(self._src({})[0], [])

    def test_weapon_class_and_keyword_rules(self):
        # AUG is an assault rifle with Power Surge: Anti-Void counts, Anti-Phase and Burn overrides don't
        names, notes = self._src({"map": "manibus", "cradle": ["Anti-Phase", "Anti-Void", "Blazing Detonation", "Transient Impact"]})
        self.assertEqual(names, ["Anti-Void (Cradle)", "Transient Impact (Cradle)"])
        self.assertTrue(any("Anti-Phase" in n and "wrong weapon type" in n for n in notes))
        self.assertTrue(any("share a row" in n for n in notes))

    def test_abyss_fight_never_counts_cradle(self):
        self.assertEqual(self._src({"map": "manibus", "cradle": ["Anti-Void"]}, scenario="abyss")[0], [])

    def test_tooltip_value_replaces_list_value(self):
        import forge_extras as fx
        w = forge.gamedata()["weapons"]["AUG - Electron Cloud"]
        srcs, _ = fx.extra_sources({"map": "manibus", "cradle": [{"name": "Anti-Void", "value": 20}], "weapon": w["name"]}, w["keyword"], "boss")
        self.assertEqual(dict(srcs)["Anti-Void (Cradle)"], {"dmg_boost": 20.0})

    def test_suggestions_pick_one_per_row_and_raise_dps(self):
        import copy
        prof = copy.deepcopy(forge.DEFAULT_PROFILE)
        w = forge.gamedata()["weapons"]["AUG - Electron Cloud"]
        base = forge.auto_cfg(prof, w, "boss")
        prof["extras"] = {"map": "manibus"}
        cfg = forge.auto_cfg(prof, w, "boss")
        self.assertTrue(cfg.get("cradle_auto"))
        import forge_cradle as fc
        rows = [next(o["row"] for o in fc.overrides("manibus") if o["name"] == n) for n in cfg["cradle"]]
        self.assertEqual(len(rows), len(set(rows)))
        st = {"name": w["name"], "stars": 6, "tier": 5}
        import forge_extras as fx
        d0 = forge.evaluate(w, st, [], {}, 600, "boss", extras=fx.build_extras(base, w["keyword"], "boss"))["dps"]
        d1 = forge.evaluate(w, st, [], {}, 600, "boss", extras=fx.build_extras(cfg, w["keyword"], "boss"))["dps"]
        self.assertGreater(d1, d0)

    def test_ui_catalog_lists_maps(self):
        c = forge.ui_catalog()["cradle"]
        self.assertFalse(c["maps"]["isles_of_abyss"]["cradle"])
        self.assertTrue(c["maps"]["manibus"]["cradle"])
        self.assertIn("winter", c["catalogs"])

    def test_per_stack_tooltip_value_scales_all_stacks(self):
        import forge_cradle as fc
        o = fc._find("manibus", "Transient Impact")
        self.assertEqual(fc.override_stats(o, "Power Surge", "boss", 2.5), fc.override_stats(o, "Power Surge", "boss"))
        self.assertAlmostEqual(fc.override_stats(o, "Power Surge", "boss", 5)["kw_dmg:Power Surge"], 45.0)


@unittest.skipUnless(forge.DB.exists(), "needs the mod database (owned_mods reads it)")
class ShinyModTests(unittest.TestCase):
    def _prof(self, edit):
        import copy
        p = copy.deepcopy(forge.DEFAULT_PROFILE)
        p["mods"] = [{"name": "Precise Strike", "variant": "General", "level": 17}]
        mods = forge.owned_mods(p)
        p["mod_edits"] = {f"{mods[0]['name']}|{mods[0]['variant']}".lower(): edit}
        return p

    def test_shiny_needs_level_17(self):
        m = forge.owned_mods(self._prof({"level": 16, "shiny": True}))[0]
        self.assertFalse(m.get("shiny"))
        m = forge.owned_mods(self._prof({"level": 17, "shiny": True}))[0]
        self.assertTrue(m.get("shiny"))

    def test_shiny_text_is_counted(self):
        m = forge.owned_mods(self._prof({"level": 17, "shiny": True, "shiny_extra": "Weapon DMG +5%"}))[0]
        self.assertEqual(m.get("shiny_extra"), "Weapon DMG +5%")
        w = forge.gamedata()["weapons"]["AUG - Electron Cloud"]
        st = {"name": w["name"], "stars": 6, "tier": 5}
        plain = dict(m, shiny=False, shiny_extra=None)
        d0 = forge.evaluate(w, st, [plain], {}, 600, "boss")["dps"]
        d1 = forge.evaluate(w, st, [m], {}, 600, "boss")["dps"]
        self.assertGreater(d1, d0)

    def test_shiny_without_text_is_a_labeled_level_17(self):
        m = forge.owned_mods(self._prof({"level": 17, "shiny": True}))[0]
        w = forge.gamedata()["weapons"]["AUG - Electron Cloud"]
        r = forge.evaluate(w, {"name": w["name"], "stars": 6, "tier": 5}, [m], {}, 600, "boss")
        self.assertTrue(any("Shiny bonus not counted" in u for u in r["unmodeled"]))


@unittest.skipUnless(forge.DB.exists(), "needs the mod database")
class CrateAimTests(unittest.TestCase):
    def test_aim_at_top_build(self):
        import forge_crates as fc
        r = fc.advise("slot_pick", level=13, aim="rank:1")
        if r.get("error"):
            self.skipTest("needs a profile with a weapon")
        self.assertEqual(r["aim"]["rank"], 1)
        self.assertEqual(len(r["aim"]["lineup"]), 7)
        self.assertIn("build #1", r["lenses"][0])
        self.assertNotIn("suggest_aim", r)
        gains = [p["exp_pct"] for p in r["picks"] if p["exp_pct"] > 0]
        self.assertEqual(gains, sorted(gains, reverse=True))


class VersionTests(unittest.TestCase):
    def test_one_version_everywhere(self):
        import forge_live
        v = (Path(forge.__file__).resolve().parent / "VERSION").read_text().strip()
        self.assertEqual(forge_live.APP_VERSION, v)

    def test_installer_never_copies_data(self):
        import tempfile, forge_install
        with tempfile.TemporaryDirectory() as t:
            src, dst = Path(t) / "src", Path(t) / "dst"
            (src / "data").mkdir(parents=True); (src / "data" / "advisor.sqlite3").write_text("x")
            (src / "static").mkdir(); (src / "static" / "a.js").write_text("y"); (src / "server.py").write_text("")
            forge_install.copy_app(src, dst)
            self.assertFalse((dst / "data").exists())
            self.assertTrue((dst / "static" / "a.js").exists())


class AppUpdateTests(unittest.TestCase):
    def test_version_order(self):
        import forge_appupdate as au
        self.assertTrue(au.newer("2026.11.06.08", "2026.11.06.07"))
        self.assertTrue(au.newer("2026.12.01.01", "2026.11.30.09"))
        self.assertFalse(au.newer("2026.11.06.07", "2026.11.06.07"))
        self.assertFalse(au.newer("2026.11.06.06", "2026.11.06.07"))
        self.assertTrue(au.newer("2026.11.06.07", "unknown"))

    def test_sums_and_assets(self):
        import forge_appupdate as au
        h = "a" * 64
        self.assertEqual(au.parse_sums(f"{h}  Deviant-Forge-1-windows.zip\n{'b'*64} *x.tgz\njunk"),
                         {"Deviant-Forge-1-windows.zip": h, "x.tgz": "b" * 64})
        rel = {"assets": [{"name": "SHA256SUMS.txt"}, {"name": "Deviant-Forge-1-windows.zip"}, {"name": "deviant-forge-1-linux.tgz"}]}
        self.assertEqual(au.pick_asset(rel, "windows")["name"], "Deviant-Forge-1-windows.zip")
        self.assertEqual(au.pick_asset(rel, "linux")["name"], "deviant-forge-1-linux.tgz")

    def test_unzip_refuses_data_and_escapes(self):
        import tempfile, zipfile, forge_appupdate as au
        with tempfile.TemporaryDirectory() as t:
            for bad in ("Deviant Forge/app/data/advisor.sqlite3", "../evil.txt", "/abs.txt"):
                z = Path(t) / "u.zip"
                with zipfile.ZipFile(z, "w") as zf:
                    zf.writestr("Deviant Forge/app/server.py", "")
                    zf.writestr(bad, "x")
                with self.assertRaises(ValueError):
                    au.safe_extract(z, Path(t) / "out")
            z = Path(t) / "ok.zip"
            with zipfile.ZipFile(z, "w") as zf:
                zf.writestr("Deviant Forge/app/server.py", ""); zf.writestr("Deviant Forge/app/forge_install.py", "")
                zf.writestr("Deviant Forge/app/gamedata/x.json", "{}")
            au.safe_extract(z, Path(t) / "ok")
            self.assertTrue(str(au.find_installer(Path(t) / "ok")).endswith("app/forge_install.py"))
