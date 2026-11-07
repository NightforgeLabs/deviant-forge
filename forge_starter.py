"""New-player plan: what to build first when you own nothing yet.

Used when the profile has no weapons (a brand new character, or the fresh-start test).
It looks at the strongest builds in the game (forge_theory), checks how each of those
weapons does on day one (1 star, no mods, no armor set) and picks the one that is
strong right away AND keeps growing. Then it says what to spend Starchrom on, what is
free right now (food, deviation), and which mods to farm. Every number is an estimate.
"""
from __future__ import annotations

import forge
import forge_effects as fe

FIRST_WEIGHT = 0.4   # how much day-one damage counts vs. the ceiling when picking a first weapon


def plan(profile: dict, scenario: str, marked: bool = False) -> dict:
    import forge_theory
    gd = forge.gamedata()
    budget = int(profile.get("starchrom") or 0)
    psi, _ = forge.estimate_psi(profile, {})
    th = forge_theory.theory(scenario, marked)
    builds = th.get("builds") or []
    if not builds:
        return {"error": "No builds to compare yet."}
    rows = []
    for b in builds:
        name = b["weapon"]["name"]
        w = gd["weapons"].get(name)
        if not w:
            continue
        st = {"name": name, "stars": 1, "tier": 5, "calibration": None}
        day1 = forge.evaluate(w, st, [], {}, psi, scenario)["dps"]
        rows.append({"weapon": name, "keyword": w.get("keyword"), "type": w.get("type"), "day1": round(day1),
                     "ceiling": b["dps"], "build": b})
    m1 = max(r["day1"] for r in rows) or 1
    mc = max(r["ceiling"] for r in rows) or 1
    for r in rows:
        r["score"] = FIRST_WEIGHT * r["day1"] / m1 + (1 - FIRST_WEIGHT) * r["ceiling"] / mc
    rows.sort(key=lambda r: -r["score"])
    pick = rows[0]
    b = pick["build"]
    cfg = b.get("config") or {}
    wcost = forge.weapon_cost(1)
    piece = forge.armor_cost(1)
    sets = b.get("sets") or {}
    main_set = max(sets, key=sets.get) if sets else None

    steps = []
    # free things first: they cost no Starchrom
    foods = [c["name"] for c in cfg.get("consumables") or []]
    if foods:
        steps.append({"how": "free", "title": f"Eat {' + '.join(foods)} before fights",
                      "why": "Cooked food is the cheapest damage in the game. Cook it at a stove from farm crops and meat."})
    dev = (cfg.get("deviation") or {}).get("name")
    if dev:
        steps.append({"how": "free", "title": f"Catch {dev} as your combat deviation",
                      "why": "Deviations are caught in the world, not bought. Look for one with a high first number (Skill)."})
    if budget >= wcost:
        steps.append({"how": "sc", "title": f"Unlock {pick['weapon']} (1 star)", "cost": wcost,
                      "why": f"Your first legendary gun is the biggest jump. Est. {pick['day1']:,} DPS on day one."})
        left = budget - wcost
    else:
        steps.append({"how": "sc", "title": f"Save up, then unlock {pick['weapon']}", "cost": wcost,
                      "why": f"A legendary gun costs {wcost:,} Starchrom; you have {budget:,}. "
                             f"Save {wcost - budget:,} more. Don't spend it on armor first: the gun is the biggest jump. "
                             "Until then, use the best purple gun you find."})
        left = 0
    if main_set:
        n = sets[main_set]
        can = min(n, left // piece) if left else 0
        steps.append({"how": "sc", "title": f"Build up {n} pieces of {main_set} armor", "cost": n * piece,
                      "why": (f"You can afford {can} piece{'s' if can != 1 else ''} after the gun. " if left else "")
                             + f"{piece:,} Starchrom per legendary piece. Set bonuses start at 2 pieces."})
    mods = [(slot, m) for slot, m in (b.get("mods") or {}).items() if m]
    if mods:
        steps.append({"how": "farm", "title": "Farm these mods (any level to start)",
                      "why": "Mods drop from crates, bosses and silos; level them later.",
                      "mods": [{"slot": s, "name": m["name"], "variant": m["variant"]} for s, m in mods]})
    steps.append({"how": "free", "title": "Add what you get on the Weapons, Armor and Mods pages",
                  "why": "As soon as you own a gun, the main Best build, Upgrades and Path to max take over with real numbers."})
    return {
        "budget": budget, "psi": round(psi), "weapon_cost": wcost, "piece_cost": piece,
        "pick": {k: pick[k] for k in ("weapon", "keyword", "type", "day1", "ceiling")},
        "options": [{k: r[k] for k in ("weapon", "keyword", "type", "day1", "ceiling")} for r in rows[:5]],
        "steps": steps, "scenario": fe.scn(scenario).get("label", scenario),
        "note": "Day-one DPS = 1 star, no mods, no armor set, Psi assumed. Ceiling = the same gun fully built. "
                "The pick balances both, so it is good now and keeps growing.",
    }
