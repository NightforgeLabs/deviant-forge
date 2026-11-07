#!/usr/bin/env python3
"""Snapshot Once Human game-file data published by oncehuman.th.gl.

th.gl states its database values come from the current game files. This
importer reads (never writes) their public pages and stores a dated JSON
snapshot at gamedata/thgl_snapshot.json for the optimizer.

Usage:  python3 tools/import_thgl_gamedata.py [--limit N] [--delay 0.35]
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

BASE = "https://oncehuman.th.gl"
UA = "Mozilla/5.0 (DeviantForge local advisor; read-only snapshot)"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "gamedata" / "thgl_snapshot.json"


def get(url: str, retries: int = 3) -> str:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            if attempt == retries - 1:
                raise
            time.sleep(1.5 * (attempt + 1))
    return ""


def flight_payload(page: str) -> str:
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', page, re.S)
    return "".join(chunks).replace('\\"', '"').replace("\\\\", "\\")


def text_lines(page: str) -> list[str]:
    page = re.sub(r"<script[^>]*>.*?</script>", "", page, flags=re.S)
    page = re.sub(r"<[^>]+>", "\n", page)
    lines = [html.unescape(x).strip() for x in page.split("\n")]
    return [re.sub(r"\s+", " ", x) for x in lines if x.strip()]


def num(value: str):
    m = re.search(r"-?\d+(?:\.\d+)?", value.replace(",", ""))
    return float(m.group()) if m else None


# ---------------------------------------------------------------- indexes
def gear_index() -> list[dict]:
    payload = flight_payload(get(f"{BASE}/db/gear"))
    rows = re.findall(r'\{"id":"(\d+)","name":"([^"]+)","groupId":"([^"]+)","text":"([^"]*)"', payload)
    return [dict(id=a, name=b, group=c, text=d) for a, b, c, d in rows]


def mod_index() -> list[tuple[str, str]]:
    payload = flight_payload(get(f"{BASE}/db/mods"))
    rows = re.findall(r'"name":"([^"]+)","url":"https://oncehuman.th.gl/db/mods/(mod_\d+)"', payload)
    seen, out = set(), []
    for name, mid in rows:
        if mid not in seen:
            seen.add(mid)
            out.append((name, mid))
    return out + probe_missing_mods(out)


def probe_missing_mods(known: list[tuple[str, str]], ahead: int = 8, delay: float = 0.2) -> list[tuple[str, str]]:
    """th.gl's /db/mods index only lists the first 100 mods. Mod IDs come in runs per slot/family
    (Bottoms 9311.., Fast Gunner 10901..), so check the gaps and a few IDs past the end of each run."""
    ids = {int(m[4:]) for _, m in known}
    runs: dict[int, list[int]] = {}
    for i in ids:
        runs.setdefault(i // 100, []).append(i)
    found = []
    for g, v in sorted(runs.items()):
        for i in range(g * 100 + 1, max(v) + ahead + 1):
            if i in ids:
                continue
            try:
                page = get(f"{BASE}/db/mods/mod_{i}", retries=1)
            except Exception:  # noqa: BLE001 - a missing ID is a 404
                continue
            m = re.search(r"<title>([^<]+?) \u2013 Mod", page) or re.search(r"<title>([^<]+?) – Mod", page)
            if m:
                found.append((html.unescape(m.group(1)).strip(), f"mod_{i}"))
            time.sleep(delay)
    return found


def highest_tiers(index: list[dict], group: str) -> list[dict]:
    best: dict[str, tuple[int, dict]] = {}
    for row in index:
        if row["group"] != group:
            continue
        m = re.match(r"(.*) \(Tier (\d)\)$", row["name"])
        base, tier = (m.group(1), int(m.group(2))) if m else (row["name"], 0)
        if base not in best or tier > best[base][0]:
            best[base] = (tier, row)
    return [dict(row, base_name=base, tier=tier) for base, (tier, row) in best.items()]


# ---------------------------------------------------------------- parsers
def block_after(lines: list[str], title: str) -> list[str]:
    idx = [i for i, x in enumerate(lines) if x == title]
    return lines[idx[1] + 1:] if len(idx) > 1 else (lines[idx[0] + 1:] if idx else [])


def kv(lines: list[str], key: str, stop: int = 80):
    for i, x in enumerate(lines[:stop]):
        if x == key and i + 1 < len(lines):
            return lines[i + 1]
    return None


END_MARKERS = {"Drop Chances", "Choose one", "Recipe", "Ingredients", "Used in", "Sold by", "Related"}


def parse_weapon(lines: list[str], row: dict) -> dict:
    b = block_after(lines, row["name"])
    stats = {}
    for key in ["Weapon Type", "DMG", "Crit Rate", "Crit DMG", "Weakspot DMG", "Fire Rate", "Magazine Capacity",
                "Reload Speed", "Range", "Stability", "Accuracy", "Mobility", "Ammo", "Build", "Melee Type"]:
        v = kv(b, key, 90)
        if v is not None:
            stats[key] = v
    per_star = {}
    for i, x in enumerate(b[:200]):
        m = re.fullmatch(r"([1-6])★", x)
        if m and i + 1 < len(b) and re.fullmatch(r"[\d,.]+", b[i + 1]):
            per_star[int(m.group(1))] = num(b[i + 1])
    effect_name, effect_lines = None, []
    if "Weapon Effect" in b:
        j = b.index("Weapon Effect")
        effect_name = b[j + 1] if j + 1 < len(b) else None
        for x in b[j + 2:j + 30]:
            if x in END_MARKERS or x.endswith("recipe & materials calculator"):
                break
            effect_lines.append(x)
    return {
        "id": row["id"], "name": row["base_name"], "tier": row["tier"], "group": row["group"],
        "source_url": f"{BASE}/db/gear/{row['id']}",
        "type": stats.get("Weapon Type") or stats.get("Melee Type"),
        "build": stats.get("Build"),
        "ammo": stats.get("Ammo"),
        "dmg": num(stats.get("DMG", "")),
        "dmg_per_star": per_star,
        "crit_rate_pct": num(stats.get("Crit Rate", "")),
        "crit_dmg_pct": num(stats.get("Crit DMG", "")),
        "weakspot_dmg_pct": num(stats.get("Weakspot DMG", "")),
        "fire_rate_rpm": num(stats.get("Fire Rate", "")),
        "magazine": num(stats.get("Magazine Capacity", "")),
        "reload_speed": num(stats.get("Reload Speed", "")),
        "effect_name": effect_name,
        "effect_text": " ".join(effect_lines).strip(),
    }


def parse_armor(lines: list[str], row: dict) -> dict:
    b = block_after(lines, row["name"])
    slot = (row.get("text") or "").split(" · ")[0] or (b[0] if b else None)
    per_star = {}
    if "Stats per star" in b:
        j = b.index("Stats per star")
        header = []
        k = j + 2  # skip "★"
        while k < len(b) and not re.fullmatch(r"[1-6]★", b[k]):
            header.append(b[k]); k += 1
        while k < len(b) and re.fullmatch(r"[1-6]★", b[k]):
            star = int(b[k][0]); vals = b[k + 1:k + 1 + len(header)]
            per_star[star] = {h: num(v) for h, v in zip(header, vals)}
            k += 1 + len(header)
    set_effects = {}
    if "Set Effect" in b:
        j = b.index("Set Effect") + 1
        while j < len(b):
            m = re.fullmatch(r"\((\d) pieces?\)", b[j])
            if not m:
                break
            set_effects[int(m.group(1))] = b[j + 1] if j + 1 < len(b) else ""
            j += 2
    psi = num(kv(b, "Psi Intensity", 20) or "")
    return {
        "id": row["id"], "name": row["base_name"], "tier": row["tier"],
        "source_url": f"{BASE}/db/gear/{row['id']}",
        "slot": slot, "hp": num(kv(b, "HP", 20) or ""), "psi_intensity": psi,
        "stats_per_star": per_star, "set_effects": set_effects,
    }


ROMAN = {"Ⅰ": 1, "Ⅱ": 2, "Ⅲ": 3, "Ⅳ": 4, "Ⅴ": 5, "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5}


def parse_mod(lines: list[str], name: str, mid: str) -> dict:
    b = block_after(lines, name)
    slot = kv(b, "Slot", 10)
    core = {}
    if "Core effect per level" in b:
        j = b.index("Core effect per level") + 3  # skip Level / Effect headers
        while j + 1 < len(b) and b[j] in ROMAN:
            core[ROMAN[b[j]]] = b[j + 1]
            j += 2
    variants = {}
    if "Sub-stat sets" in b:
        j = b.index("Sub-stat sets") + 1
        while j + 1 < len(b) and not b[j].startswith("Sub-stats per level"):
            variants[b[j]] = [s.strip() for s in b[j + 1].split(";")]
            j += 2
    per_level = {}
    if any(x.startswith("Sub-stats per level") for x in b):
        j = next(i for i, x in enumerate(b) if x.startswith("Sub-stats per level")) + 1
        while j + 1 < len(b) and " / " in b[j + 1]:
            per_level[b[j]] = [s.strip() for s in b[j + 1].split(" / ")]
            j += 2
    return {
        "id": mid, "name": name, "slot": slot, "source_url": f"{BASE}/db/mods/{mid}",
        "summary": b[1] if len(b) > 1 else "",
        "core_effect_by_level": core, "variant_substats": variants, "substat_values_by_tier": per_level,
    }


# ---------------------------------------------------------------- main
def build_snapshot(limit: int = 0, delay: float = 0.35, progress=None) -> dict:
    """Read the whole th.gl database into one snapshot dict. progress(done, total, msg) is optional."""
    idx = gear_index()
    weapons = highest_tiers(idx, "oh_group_weapons") + highest_tiers(idx, "oh_group_melee_weapons")
    armor = highest_tiers(idx, "oh_group_armor")
    mods = mod_index()
    if limit:
        weapons, armor, mods = weapons[:limit], armor[:limit], mods[:limit]
    out = {"source": BASE, "source_note": "th.gl states values come from current Once Human game files",
           "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "weapons": [], "armor": [], "mods": [], "errors": []}
    jobs = [("weapons", w) for w in weapons] + [("armor", a) for a in armor] + [("mods", m) for m in mods]
    if progress:
        progress(0, len(jobs), f"{len(weapons)} weapons, {len(armor)} armor, {len(mods)} mods listed")
    for n, (kind, item) in enumerate(jobs, 1):
        try:
            if kind == "mods":
                name, mid = item
                out["mods"].append(parse_mod(text_lines(get(f"{BASE}/db/mods/{mid}")), name, mid))
            else:
                lines = text_lines(get(f"{BASE}/db/gear/{item['id']}"))
                out[kind].append(parse_weapon(lines, item) if kind == "weapons" else parse_armor(lines, item))
        except Exception as exc:  # noqa: BLE001
            out["errors"].append({"kind": kind, "item": str(item)[:120], "error": str(exc)[:200]})
        if progress:
            progress(n, len(jobs), f"reading {kind}")
        time.sleep(delay)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--delay", type=float, default=0.35)
    args = ap.parse_args()

    def prog(n, total, msg):
        if n == 0 or n % 25 == 0:
            print(f"  {n}/{total} {msg}", file=sys.stderr)
    out = build_snapshot(args.limit, args.delay, prog)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"wrote {OUT} ({len(out['weapons'])} weapons, {len(out['armor'])} armor, {len(out['mods'])} mods, "
          f"{len(out['errors'])} errors)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
