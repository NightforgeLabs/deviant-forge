import json
import sqlite3
import unittest
from pathlib import Path

import video_import_plan


def proposal(pid, catalog_id, level, rows, frame, checked=True):
    data = {
        "catalog_id": catalog_id, "slot": "chest_mod", "variant": "General",
        "level": level, "ownership": "unlocked", "main_effect": "Observed effect",
        "attribute_rows": rows, "typed_modifiers": [
            {"row_index": i, "calculation_status": "excluded_ambiguous" if "−+" in text else "assumption_scenario",
             "raw_text": text, "tech_activation": "unknown"} for i, text in enumerate(rows)],
        "source": {"frame": frame, "timestamp": float(pid.strip("p")), "mod_system":"legacy_backpack"},
    }
    if checked:
        data["source_audit"] = {
            "status": "source_text_and_numbers_checked",
            "main_effect": {"source_text": data["main_effect"]},
            "attribute_rows": [{"source_text": text} for text in rows],
        }
    return {"id": pid, "run_id": "r", "status": "pending", "data": data}


class ImportPlanTests(unittest.TestCase):
    def test_field_guide_and_unknown_system_never_offer_physical_copies(self):
        current=proposal('p1','mod:a',9,['Weapon DMG + 5%'],'one.png')
        current['data']['source']['mod_system']='current_field_guide'
        unknown=proposal('p2','mod:b',9,['Weapon DMG + 5%'],'two.png')
        unknown['data']['source'].pop('mod_system')
        result=video_import_plan.plan('r',[current,unknown],[])
        self.assertEqual(result['counts']['field_guide_progression_needs_profile_review'],1)
        self.assertEqual(result['counts']['source_system_needs_review'],1)
        self.assertNotIn('new_owned_copy_candidate',result['counts'])

    def test_field_guide_repeated_higher_stale_shiny_and_conflicting_sources(self):
        rows=[proposal('p1','mod:a',9,['Weapon DMG + 5%'],'first.png'),
              proposal('p2','mod:a',9,['Weapon DMG + 5%'],'first.png'),
              proposal('p3','mod:a',10,['Weapon DMG + 6%'],'later.png')]
        for row in rows:row['data']['source']['mod_system']='current_field_guide'
        rows[1]['data']['source']['timestamp']=rows[0]['data']['source']['timestamp']
        first=video_import_plan.plan('r',rows,[])
        self.assertEqual(first['counts']['field_guide_duplicate_source'],2)
        self.assertEqual(first['counts']['field_guide_higher_level_candidate'],1)
        rows[1]['data']['attribute_rows']=['Weapon DMG + 4%']
        conflict=video_import_plan.plan('r',rows,[])
        self.assertEqual(conflict['counts']['field_guide_conflicting_observations'],2)
        rows[1]['data']['shiny_status']='shiny'
        shiny=video_import_plan.plan('r',rows,[])
        self.assertEqual(shiny['counts']['field_guide_shiny_identity_needs_review'],3)

    def test_legacy_ocr_rows_are_staged_without_activation_or_inventory_edit(self):
        observation = {"id": "o1", "media_id": "old", "state": "confirmed",
                       "timestamp": 12.0, "image": "media/frame.png",
                       "fields": {"identification": {"catalog_id": "mod:weapon_mod:test", "slot": "weapon_mod",
                                                  "variant": "General", "level": 9},
                                  "mod_roll_lines": {"value": ["Weapon DMG + 5%", "unknown value"]}}}
        owned = [{"id": "i1", "kind": "mod_unlock", "archived": 0,
                  "source_observation": "o1", "stats": {"observed_attribute_lines": ["Weapon DMG + 5%", "unknown value"]}}]
        before = json.dumps((observation, owned), sort_keys=True)
        staged = video_import_plan.legacy_observation_staging("old", [observation], owned)
        self.assertEqual(staged["counts"]["raw_attribute_rows"], 2)
        self.assertEqual(staged["counts"]["unparsed_attribute_rows"], 1)
        self.assertEqual(staged["entries"][0]["matching_owned_instance_ids"], ["i1"])
        self.assertEqual(staged["entries"][0]["typed_modifiers"][0]["confidence"], "ocr_unverified")
        self.assertEqual(staged["entries"][0]["typed_modifiers"][0]["tech_activation"], "unknown")
        self.assertEqual(json.dumps((observation, owned), sort_keys=True), before)

    def test_legacy_linked_ocr_line_survives_missing_observation_rows(self):
        observation = {"id": "o", "media_id": "old", "state": "confirmed", "fields": {
            "identification": {"catalog_id": "mod:weapon_mod:test"}, "mod_roll_lines": {"value": []}}}
        owned = [{"id": "i", "kind": "mod_unlock", "source_observation": "o",
                  "stats": {"observed_attribute_lines": ["Status DMG + 4.8%"]}}]
        staged = video_import_plan.legacy_observation_staging("old", [observation], owned)
        self.assertEqual(staged["entries"][0]["raw_origin"], "linked_owned_ocr")
        self.assertEqual(staged["counts"]["raw_attribute_rows"], 1)

    def test_distinct_copies_and_conflicting_source_are_not_collapsed(self):
        rows = [
            proposal("p1", "mod:a", 9, ["Weapon DMG + 5%"], "first.png"),
            proposal("p2", "mod:a", 9, ["Weapon DMG + 6%"], "second.png"),
            proposal("p3", "mod:b", 7, ["Damage from monsters −+ 3%"], "third.png"),
        ]
        owned = [{"id": "old", "kind": "mod_unlock", "level": 7,
                  "effects": {"catalog_id": "mod:b"}, "stats": {}}]
        before = json.dumps((rows, owned), sort_keys=True)
        result = video_import_plan.plan("r", rows, owned)
        self.assertEqual(result["counts"]["conflicting_source_or_distinct_copy_needs_review"], 2)
        self.assertEqual(result["counts"]["existing_identity_level_needs_evidence_review"], 1)
        self.assertEqual(result["counts"]["ambiguous_signed_rows"], 1)
        self.assertEqual(result["counts"]["typed_attribute_rows"], 3)
        self.assertTrue(all(entry["tech_activation"] == "unknown" for entry in result["entries"]))
        self.assertEqual(json.dumps((rows, owned), sort_keys=True), before)

    def test_exact_duplicate_frame_differs_from_same_rolls_on_distinct_hovers(self):
        duplicates=[proposal('p1','mod:a',9,['Weapon DMG + 5%'],'same.png'),
                    proposal('p2','mod:a',9,['Weapon DMG + 5%'],'same.png')]
        duplicates[1]['data']['source']['timestamp']=duplicates[0]['data']['source']['timestamp']
        same_frame=video_import_plan.plan('r',duplicates,[])
        self.assertEqual(same_frame['counts']['duplicate_source_observation'],2)
        duplicates[1]['data']['source']['frame']='later.png'
        duplicates[1]['data']['source']['timestamp']=2
        later=video_import_plan.plan('r',duplicates,[])
        self.assertEqual(later['counts']['repeated_hover_or_distinct_copy_needs_review'],2)

    def test_real_review_is_read_only_when_available(self):
        db = Path(__file__).resolve().parents[1] / "data" / "advisor.sqlite3"
        if not db.exists():
            self.skipTest("User's reviewed source is unavailable")
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as con:
            con.row_factory = sqlite3.Row
            rows = [dict(row) for row in con.execute("SELECT * FROM video_import_proposals")]
            owned = [dict(row) for row in con.execute(
                "SELECT id,kind,level,archived,source_observation,stats,effects FROM inventory")]
        for row in rows:
            row["data"] = json.loads(row["data"])
        for item in owned:
            item["stats"] = json.loads(item["stats"] or "{}")
            item["effects"] = json.loads(item["effects"] or "{}")
        result = video_import_plan.plan("3eca1e237ab643989c03a1b9c767555d", rows, owned)
        self.assertEqual(result["counts"]["field_guide_progression_needs_profile_review"], 43)
        self.assertEqual(result["counts"]["typed_attribute_rows"], 172)
        self.assertEqual(result["counts"]["ambiguous_signed_rows"], 7)
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as con:
            con.row_factory = sqlite3.Row
            media = con.execute("SELECT id FROM media WHERE name LIKE '%2026-10-22_15-15-01%'").fetchone()
            observations = []
            for source in con.execute("SELECT * FROM observations WHERE media_id=?", (media['id'],)):
                source = dict(source); source['fields'] = json.loads(source['fields']); observations.append(source)
        staged = video_import_plan.legacy_observation_staging(media['id'], observations, owned)
        self.assertEqual(staged['counts']['confirmed_mod_observations'], 16)
        self.assertEqual(staged['counts']['raw_attribute_rows'], 55)
        self.assertEqual(staged['counts']['linked_owned_instances'], 16)


if __name__ == "__main__":
    unittest.main()
