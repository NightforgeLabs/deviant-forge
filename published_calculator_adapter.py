"""Source-labelled adapter for published Once Human calculator reference data.

This module does not claim that third-party numbers match a crafted live item.
It never executes code from the upstream calculator.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

import published_reference_identity

PACKETS = Path(__file__).parent / 'evidence_packets'


def load_published_armor_table(path: str | Path | None = None) -> dict[str, Any]:
    """Load the date-stamped Apache-2.0 source table bundled with this packet."""
    if path is None:
        path = PACKETS / "armor-table-published.json"
    return json.loads(Path(path).read_text())


def _number(value: Any, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    value = float(value)
    if not math.isfinite(value) or (positive and value <= 0):
        raise ValueError(f"{name} must be {'positive' if positive else 'finite'}")
    return value


def load_weapon_reference(packet_dir: str | Path, weapon_id: str) -> dict[str, Any]:
    """Resolve the newest held direct-page row, falling back to historical data.

    Damage here is a displayed source reference, never inferred character Attack.
    """
    packet_dir = Path(packet_dir)
    base = json.loads((packet_dir / "weapon-reference-v3.json").read_text())
    row = base["rows"].get(weapon_id)
    if row is None:
        raise KeyError(weapon_id)
    page = row.get("database_page_reference")
    conflicts = dict(row.get("typed_field_discrepancies", {}))
    for layer, key in (("weapon-reference-v4-delta.json", "new_database_page_references"),
                       ("weapon-reference-v5-delta.json", "new_database_page_references")):
        delta = json.loads((packet_dir / layer).read_text())
        if weapon_id in delta[key]:
            page = delta[key][weapon_id]["database_page_reference"]
            conflicts.update(delta[key][weapon_id].get("typed_field_discrepancies", {}))
    if page:
        stats = {
            "displayed_damage": page.get("displayed_damage"),
            "rpm": page.get("rpm"),
            "magazine": page.get("magazine"),
            "reload_seconds": page.get("displayed_reload_seconds"),
            "reload_score": page.get("reload_score"),
            "crit_rate_percent": page.get("crit_rate_percent"),
            "crit_damage_percent": page.get("crit_damage_percent"),
            "weakspot_damage_percent": page.get("weakspot_damage_percent"),
            "projectiles_per_shot": page.get("explicit_projectiles_per_shot"),
        }
        evidence = "third_party_page_unlabeled_tier"
        url = page["source_url"]
        date = page["accessed_date"]
    else:
        old = row.get("historical_catalog_profile")
        if not old:
            return {"weapon_id": weapon_id, "name": row["name"], "stats": {},
                    "evidence": "no_numeric_reference", "source_url": None,
                    "snapshot_date": None, "conflicts": conflicts,
                    "crafted_scale_known": False}
        raw = old["stats"]
        stats = {"displayed_damage": raw.get("damage_per_projectile"),
                 "rpm": raw.get("rpm"), "magazine": raw.get("magazine"),
                 "reload_seconds": raw.get("reload_time_seconds"),
                 "reload_score": raw.get("reload_speed_points"),
                 "crit_rate_percent": raw.get("crit_rate_percent"),
                 "crit_damage_percent": raw.get("crit_damage_percent"),
                 "weakspot_damage_percent": raw.get("weakspot_damage_percent"),
                 "projectiles_per_shot": raw.get("projectiles_per_shot")}
        evidence = "historical_community_unlabeled_tier"
        url = old["source_url"]
        date = old["source_snapshot_date"]
    return {"weapon_id": weapon_id, "name": row["name"], "stats": stats,
            "evidence": evidence, "source_url": url, "snapshot_date": date,
            "conflicts": conflicts,
            "crafted_scale_known": False}


def load_published_weapon_baseline(packet_dir: str | Path, weapon_id: str) -> dict[str, Any]:
    """Match a catalog ID to its source-native calculator baseline by name.

    The held source has 131 canonical entries. Two additional catalog short
    names have exact blueprint/official identity bindings to those entries.
    This baseline is the input to the *published model* progression formula.
    """
    packet_dir = Path(packet_dir)
    catalog = json.loads((packet_dir / "weapon-reference-v3.json").read_text())["rows"]
    if weapon_id not in catalog:
        raise KeyError(weapon_id)
    canonical_id, alias = published_reference_identity.weapon_binding(weapon_id)
    if canonical_id not in catalog:
        raise LookupError(f'alias canonical catalog identity missing for {weapon_id}')
    published = json.loads((PACKETS / "weapon-baselines-published.json").read_text())
    normalize = lambda name: re.sub(r"[^a-z0-9]", "", name.lower())
    name = normalize(catalog[canonical_id]["name"])
    matches = [(key, row) for key, row in published["weapons"].items()
               if normalize(row["name"]) == name]
    if len(matches) != 1:
        raise LookupError(f"published baseline match count for {weapon_id}: {len(matches)}")
    upstream_id, row = matches[0]
    if alias and upstream_id != alias['published_upstream_id']:
        raise LookupError(f'published alias source identity changed for {weapon_id}')
    return {"weapon_id": weapon_id, "upstream_id": upstream_id,
            "canonical_catalog_id": canonical_id,
            "identity_evidence": alias,
            "name": row["name"], "rarity": row["rarity"],
            "stats": dict(row["base_stats"]),
            "source_url": published["source_url"],
            "snapshot_date": published["fetched_date"],
            "evidence": "published_calculator_source_baseline_unverified_game_basis",
            "model_default": {"stars": 1, "tier": 1, "calibration": 0}}


def derive_published_weapon_progression(baseline: dict[str, Any], *, stars: int,
                                        tier: int, calibration: int) -> dict[str, Any]:
    """Apply the upstream Weapon.calculate_stats multipliers to damage only.

    This is not a verified mapping from a live weapon tooltip to tier-1 damage.
    The caller must supply a source-native baseline, not an arbitrary display
    damage or measured Attack/Psi value.
    """
    for name, value, maximum in (("stars", stars, 6), ("tier", tier, 5)):
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
            raise ValueError(f"{name} must be an integer from 1 to {maximum}")
    if isinstance(calibration, bool) or not isinstance(calibration, int) or not 0 <= calibration <= 6:
        raise ValueError("calibration must be an integer from 0 to 6")
    if baseline.get("evidence") != "published_calculator_source_baseline_unverified_game_basis":
        raise ValueError("source-native published calculator baseline required")
    damage = baseline["stats"].get("damage_per_projectile")
    multiplier = (1 + 0.1 * (stars - 1)) * (1 + 0.05 * (tier - 1)) * (1 + 0.02 * calibration)
    stats = dict(baseline["stats"])
    # The imported weapon_list damage is not anchored to a tier/star/calibration
    # item ID. Treat the upstream progression as an unexecuted hypothesis:
    # A prior KAM comparison mixed Crank Tier 1 with Burning Rage Tier 4;
    # that mismatch itself forbids an item-specific inferred curve. AUG
    # Electron Cloud's matching Tier 1/4 item pages refute a generic 1.15x
    # Tier 4 scaling from Tier 1.
    stats["damage_per_projectile"] = None
    return {"weapon_id": baseline["weapon_id"], "upstream_id": baseline["upstream_id"],
            "stars": stars, "tier": tier, "calibration": calibration,
            "damage_multiplier": None, "candidate_multiplier_not_applied": multiplier,
            "raw_source_damage_unanchored": damage, "stats": stats,
            "unresolved": ["Imported weapon damage has no item-ID-anchored tier/star/calibration basis; a prior KAM contrast mixed Crank Tier 1 with Burning Rage Tier 4, and matching AUG Electron Cloud tier pages refute the generic multiplier"],
            "model": "unanchored_published_damage_quarantined",
            "source_basis_status": "unknown_and_conflicting_with_tier_item_pages",
            "source_conflict_examples": [
                {"weapon": "KAM - Crank / KAM - Burning Rage identity mismatch", "imported_damage": 134,
                 "tier_1_item_damage": 35, "tier_4_item_damage": 134,
                 "tier_1_title": "KAM - Crank (Tier 1)",
                 "tier_4_title": "KAM - Burning Rage (Tier 4)",
                 "tier_1_url": "https://wikily.gg/once-human/items/10421301",
                 "tier_4_url": "https://wikily.gg/once-human/items/10421304"},
                {"weapon": "AUG - Electron Cloud", "tier_1_item_damage": 34,
                 "tier_4_item_damage": 132,
                 "tier_1_url": "https://wikily.gg/once-human/items/10451401",
                 "tier_4_url": "https://wikily.gg/once-human/items/10451404"}],
            "game_verified": False, "source_url": baseline["source_url"]}


def derive_timing(reference: dict[str, Any], *, fire_rate_percent: float = 0,
                  magazine_percent: float = 0,
                  reload_efficiency_percent: float = 0) -> dict[str, Any]:
    """Published calculator RPM/mag model plus official final reload efficiency.

    Reload speed *score* has no known seconds conversion. Rounding magazine to
    nearest integer follows OnceHuman_Tools, not a verified game rounding rule.
    """
    fire = _number(fire_rate_percent, "fire_rate_percent")
    mag = _number(magazine_percent, "magazine_percent")
    reload = _number(reload_efficiency_percent, "reload_efficiency_percent")
    if min(1 + fire / 100, 1 + mag / 100, 1 + reload / 100) <= 0:
        raise ValueError("derived timing multiplier must stay positive")
    stats = reference["stats"]
    rpm = stats.get("rpm", stats.get("fire_rate"))
    magazine = stats.get("magazine", stats.get("magazine_capacity"))
    seconds = stats.get("reload_seconds", stats.get("reload_time_seconds"))
    out = {"rpm": None, "magazine": None, "reload_seconds": None,
           "base_reload_seconds": None, "reload_formula_source_url": None,
           "seconds_per_shot": None, "cycle_seconds": None,
           "unresolved": [], "model": "published_reference_timing"}
    if rpm is not None:
        out["rpm"] = _number(rpm, "rpm", positive=True) * (1 + fire / 100)
        out["seconds_per_shot"] = 60 / out["rpm"]
    else:
        out["unresolved"].append("reference RPM")
    if magazine is not None:
        out["magazine"] = round(_number(magazine, "magazine", positive=True) * (1 + mag / 100))
        if out["magazine"] <= 0:
            raise ValueError("derived magazine must be positive")
    else:
        out["unresolved"].append("reference magazine")
    if seconds is not None:
        out["base_reload_seconds"] = _number(seconds, "reload_seconds", positive=True)
        out["reload_seconds"] = out["base_reload_seconds"] / (1 + reload / 100)
        out["reload_formula_source_url"] = "https://www.oncehuman.game/news/update/20250521/40780_1235763.html"
    else:
        out["unresolved"].append("reference reload seconds; reload score cannot be converted")
    if all(out[k] is not None for k in ("seconds_per_shot", "magazine", "reload_seconds")):
        out["cycle_seconds"] = out["magazine"] * out["seconds_per_shot"] + out["reload_seconds"]
    return out


def armor_stats(table: dict[str, Any], *, slot: str, rarity: str, stars: int,
                tier: int, calibration: int = 0) -> dict[str, Any]:
    """Read an exact published armor row; reject its zero placeholders.

    The upstream calculator labels tiers as levels. HP/Psi calibration uses
    exact table coefficients; pollution resistance has no calibration series
    in the source and remains unchanged.
    """
    if not isinstance(stars, int) or isinstance(stars, bool) or stars < 1:
        raise ValueError("stars must be a positive integer")
    if not isinstance(tier, int) or isinstance(tier, bool) or tier < 1:
        raise ValueError("tier must be a positive integer")
    if not isinstance(calibration, int) or isinstance(calibration, bool) or not 0 <= calibration <= 6:
        raise ValueError("calibration must be an integer from 0 to 6")
    try:
        row = table["items"][slot][rarity]["stars"][str(stars)]["levels"][str(tier)]
    except KeyError as exc:
        raise LookupError(f"no published armor row: {slot}/{rarity}/{stars}★/tier {tier}") from exc
    stats = {}
    unresolved = []
    for field in ("hp", "psi_intensity", "pollution_resist"):
        value = row.get(field)
        if value is None or _number(value, field) == 0:
            stats[field] = None
            unresolved.append(f"{field}: source zero/missing placeholder")
            continue
        if value < 0:
            raise ValueError(f"{field}: negative source armor stat")
        if calibration:
            field_bonuses = table.get("calibration_bonuses", {}).get(field)
            # Upstream Item.get_stats defaults absent per-stat calibration to
            # zero. Pollution resistance has no calibration row at all.
            if field_bonuses is None and field == "pollution_resist":
                stats[field] = value
                continue
            factor = (field_bonuses or {}).get(str(calibration))
            if factor is None:
                stats[field] = None
                unresolved.append(f"{field}: calibration {calibration} coefficient absent")
                continue
            factor = _number(factor, field + " calibration factor")
            value = round(value * (1 + factor))
        stats[field] = value
    return {"slot": slot, "rarity": rarity, "stars": stars, "tier": tier,
            "calibration": calibration, "stats": stats, "unresolved": unresolved,
            "model": "OnceHuman_Tools_armor_table", "game_verified": False}


def sum_armor_psi(profiles: list[dict[str, Any]]) -> dict[str, Any]:
    """Sum only fully resolved Psi contributions; never fill missing slots as 0."""
    total = 0.0
    missing = []
    seen = set()
    for profile in profiles:
        slot = profile["slot"]
        if slot in seen:
            raise ValueError(f"duplicate armor slot {slot}")
        seen.add(slot)
        psi = profile["stats"].get("psi_intensity")
        if psi is None:
            missing.append(slot)
        else:
            total += _number(psi, f"{slot} Psi", positive=True)
    return {"known_psi_total": total, "complete_for_supplied_slots": not missing,
            "missing_slots": missing, "slots_supplied": sorted(seen)}
