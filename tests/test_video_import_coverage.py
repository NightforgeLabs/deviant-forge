import sqlite3
import unittest
from pathlib import Path

import video_import_coverage as coverage


class CoverageReportTests(unittest.TestCase):
    def test_separates_duplicate_review_commit_and_reference(self):
        run = {"id": "r", "media_id": "m", "fingerprint": coverage.TOP_DETAIL_AUDIT["fingerprint"],
               "summary": {"duration": 338.98, "frames_scanned": 339,
                           "qa": {"source_text_and_numbers_checked": 2, "fully_semantic_checked": 1,
                                  "semantic_uncertain_fields": 1}}}
        rows = [
            {"run_id": "r", "status": "pending", "inventory_id": None,
             "data": {"catalog_id": "a", "ownership": "unlocked"}},
            {"run_id": "r", "status": "dismissed", "inventory_id": None,
             "data": {"catalog_id": "a", "ownership": "unknown"}},
            {"run_id": "r", "status": "pending", "inventory_id": None,
             "data": {"catalog_id": "b", "ownership": "locked"}},
        ]
        out = coverage.reports([run], rows, [{"id": "m", "name": "detail.mp4"}])["r"]
        self.assertEqual((out["proposal_rows"], out["actionable_rows"], out["unique_catalog_ids"]), (3, 2, 2))
        self.assertEqual(out["duplicate_catalog_ids"], {"a": 2})
        self.assertEqual((out["source_unlocked_candidates"], out["source_locked_observations"], out["ownership_unknown"]), (1, 1, 0))
        self.assertEqual((out["source_text_and_numbers_checked"], out["fully_semantic_checked"], out["semantic_uncertain_fields"]), (2, 1, 1))
        self.assertEqual(out["committed_rows"], 0)
        self.assertEqual(out["reference_audit"]["reference_grid_positions"], 140)
        self.assertEqual(out["reference_audit"]["grid_positions_without_proposal"], 138)

    def test_other_recording_has_no_reference_claim(self):
        run = {"id": "other", "media_id": "m", "fingerprint": "other", "summary": {}}
        out = coverage.reports([run], [], [{"id": "m", "name": "another.mp4"}])["other"]
        self.assertIsNone(out["reference_audit"])
        self.assertEqual(out["proposal_rows"], 0)

    def test_personal_repair_preview_matches_exact_level_without_writing(self):
        run = {"id": "r", "media_id": "m", "fingerprint": "other", "summary": {}}
        rows = [
            {"run_id": "r", "status": "pending", "data": {"catalog_id": "mod:a", "level": 7, "ownership": "unlocked",
                "attribute_rows": ["one", "two"], "typed_modifiers": [{"row_index": 0}],
                "source_audit": {"status": "source_text_and_numbers_checked"}}},
            {"run_id": "r", "status": "pending", "data": {"catalog_id": "mod:b", "level": 8, "ownership": "unlocked",
                "attribute_rows": ["one"], "typed_modifiers": []}},
            {"run_id": "r", "status": "pending", "data": {"catalog_id": "mod:c", "level": 9, "ownership": "unlocked",
                "attribute_rows": ["one"], "typed_modifiers": []}},
            {"run_id": "r", "status": "pending", "data": {"catalog_id": "mod:d", "level": None, "ownership": "locked",
                "attribute_rows": []}},
        ]
        owned = [
            {"id": "existing-a", "kind": "mod_unlock", "level": 7, "effects": {"catalog_id": "mod:a"}, "stats": {}},
            {"id": "existing-b", "kind": "mod_unlock", "level": 6, "effects": {"catalog_id": "mod:b"}, "stats": {}},
        ]
        before = repr((rows, owned))
        out = coverage.reports([run], rows, [{"id": "m", "name": "source.mp4"}], owned)["r"]["repair_preview"]
        self.assertEqual(out["exact_owned_instances"], 1)
        self.assertEqual(out["exact_owned_missing_typed_rows"], 1)
        self.assertEqual(out["same_variant_other_level"], 1)
        self.assertEqual(out["new_catalog_identities"], 1)
        self.assertEqual((out["raw_attribute_rows"], out["typed_attribute_rows"]), (4, 1))
        self.assertEqual((out["source_checked_candidates"], out["candidates_needing_source_review"]), (1, 2))
        self.assertEqual(repr((rows, owned)), before)

    def test_actual_review_read_only_reconciliation(self):
        db = Path(__file__).resolve().parents[1] / "data" / "advisor.sqlite3"
        if not db.exists():
            self.skipTest("Local source review DB unavailable")
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as con:
            con.row_factory = sqlite3.Row
            runs = []
            for row in con.execute("SELECT * FROM video_import_runs WHERE id='3eca1e237ab643989c03a1b9c767555d'"):
                import json
                run = dict(row)
                run["summary"] = json.loads(run["summary"])
                runs.append(run)
            if not runs:
                self.skipTest("Specific source review is unavailable")
            proposals = []
            for row in con.execute("SELECT * FROM video_import_proposals WHERE run_id=?", (runs[0]["id"],)):
                item = dict(row)
                item["data"] = json.loads(item["data"])
                proposals.append(item)
            media = [dict(row) for row in con.execute("SELECT * FROM media WHERE id=?", (runs[0]["media_id"],))]
        out = coverage.reports(runs, proposals, media)[runs[0]["id"]]
        self.assertEqual((out["proposal_rows"], out["unique_catalog_ids"], out["dismissed_rows"]), (122, 121, 1))
        self.assertEqual((out["source_unlocked_candidates"], out["source_locked_observations"], out["ownership_unknown"]), (43, 78, 0))
        self.assertEqual((out["committed_rows"], out["reference_audit"]["grid_positions_without_proposal"]), (0, 19))
        self.assertEqual(len(out["reference_audit"]["grid_only_no_tooltip"]), 5)


if __name__ == "__main__":
    unittest.main()
