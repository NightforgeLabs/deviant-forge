"""Read-only coverage accounting for video proposals and separate reference grids."""

from collections import Counter


# A source audit, not inventory or importer output. The 04:01:49 recording is
# separate from the 02:20:31 detail recording represented by this fingerprint.
TOP_DETAIL_AUDIT = {
    "fingerprint": "6fbc7d188b53b9a71bbefdcedb1ea877aa7fd060c29b673ed6adf151ec5ed09e",
    "reference_recording": "screenrecording-2026-10-25_04-01-49.mp4",
    "reference_grid_positions": 140,
    "reference_grid_level_badges": 48,
    "reference_grid_lock_cues": 92,
    "not_shown_in_detail": {"Healing Fortification": 14},
    "grid_only_no_tooltip": [
        "mod:chest_mod:critical-rescue-phantasmal",
        "mod:chest_mod:enduring-shield-battle",
        "mod:chest_mod:head-on-conflict-mirror",
        "mod:chest_mod:quick-comeback-phantasmal",
        "mod:chest_mod:rejuvenating-lunar-deviant-energy",
    ],
}


def reports(runs, proposals, media, inventory=()):
    """Return counts from persisted rows without changing status or ownership."""
    media_by_id = {item["id"]: item for item in media}
    owned_by_catalog = {}
    for item in inventory:
        if item.get("kind") != "mod_unlock" or item.get("archived"):
            continue
        catalog_id = (item.get("effects") or {}).get("catalog_id")
        if catalog_id:
            owned_by_catalog.setdefault(catalog_id, []).append(item)
    by_run = {}
    for proposal in proposals:
        by_run.setdefault(proposal["run_id"], []).append(proposal)
    result = {}
    for run in runs:
        rows = by_run.get(run["id"], [])
        active = [p for p in rows if p["status"] != "dismissed"]
        ids = [p.get("data", {}).get("catalog_id") for p in rows if p.get("data", {}).get("catalog_id")]
        repeated = {key: count for key, count in Counter(ids).items() if count > 1}
        summary = run.get("summary") or {}
        qa = summary.get("qa") or {}
        source = media_by_id.get(run.get("media_id"), {})
        repair = Counter()
        for proposal in active:
            data = proposal.get("data") or {}
            if data.get("ownership") != "unlocked":
                continue
            repair["raw_attribute_rows"] += len(data.get("attribute_rows") or [])
            repair["typed_attribute_rows"] += len(data.get("typed_modifiers") or [])
            matches = owned_by_catalog.get(data.get("catalog_id"), [])
            exact = [item for item in matches if item.get("level") == data.get("level")]
            if exact:
                repair["exact_owned_instances"] += 1
                if not any((item.get("stats") or {}).get("typed_modifiers") for item in exact):
                    repair["exact_owned_missing_typed_rows"] += 1
            elif matches:
                repair["same_variant_other_level"] += 1
            else:
                repair["new_catalog_identities"] += 1
            if (data.get("source_audit") or {}).get("status", "").startswith("source_text_and_numbers_checked"):
                repair["source_checked_candidates"] += 1
            else:
                repair["candidates_needing_source_review"] += 1
        report = {
            "source_recording": source.get("name", "Source name unavailable"),
            "duration_seconds": summary.get("duration"),
            "frames_scanned": summary.get("frames_scanned"),
            "proposal_rows": len(rows),
            "actionable_rows": len(active),
            "unique_catalog_ids": len(set(ids)),
            "duplicate_catalog_ids": repeated,
            "dismissed_rows": sum(p["status"] == "dismissed" for p in rows),
            "source_unlocked_candidates": sum(p.get("data", {}).get("ownership") == "unlocked" for p in active),
            "source_locked_observations": sum(p.get("data", {}).get("ownership") == "locked" for p in active),
            "ownership_unknown": sum(p.get("data", {}).get("ownership") == "unknown" for p in active),
            "source_text_and_numbers_checked": qa.get("source_text_and_numbers_checked", 0),
            "fully_semantic_checked": qa.get("fully_semantic_checked", 0),
            "semantic_uncertain_fields": qa.get("semantic_uncertain_fields", 0),
            "committed_rows": sum(p["status"] == "committed" and p.get("inventory_id") for p in rows),
            "repair_preview": dict(repair),
            "reference_audit": None,
        }
        if run.get("fingerprint") == TOP_DETAIL_AUDIT["fingerprint"]:
            audit = {key: value for key, value in TOP_DETAIL_AUDIT.items() if key != "fingerprint"}
            audit["grid_only_no_tooltip"] = [key for key in audit["grid_only_no_tooltip"] if key not in ids]
            audit["grid_positions_without_proposal"] = audit["reference_grid_positions"] - len(set(ids))
            report["reference_audit"] = audit
        result[run["id"]] = report
    return result
