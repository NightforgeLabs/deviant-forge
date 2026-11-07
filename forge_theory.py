"""'Best in game' search: every weapon, mod, set, key armor, deviation, food,
drink and calibration at its best possible roll. This is a model estimate,
not a measured number; anything the engine can't model is listed per build.
"""
from __future__ import annotations

import time
from functools import lru_cache

import forge
import forge_effects as fe
import forge_extras as fx

MAX_STARS = 6


@lru_cache(maxsize=1)
def max_psi() -> float:
    gd = forge.gamedata()
    best: dict[str, float] = {}
    for a in gd["armor"].values():
        for d in (a.get("stats_per_star") or {}).values():
            best[a["slot"]] = max(best.get(a["slot"], 0), d.get("Psi Intensity", 0))
    return sum(best.values())


def psi_bonus() -> float:
    """Psi Intensity from outside armor (level, Cradle and so on): your character sheet minus your armor's Psi.

    Everyone who maxes out keeps that part, so the "best in the game" builds count it too. 0 without a sheet value."""
    try:
        prof = forge.load_profile()
        if not prof.get("psi_intensity"):
            return 0.0
        armor = dict(prof); armor.pop("psi_intensity", None)
        tot, how = forge.estimate_psi(armor, {})
        if not how.startswith("sum of your 6"):
            return 0.0
        return float(max(0, round((float(prof["psi_intensity"]) - tot) / 10) * 10))
    except Exception:  # noqa: BLE001
        return 0.0


def sniper_setting():
    """Your 'sniper weakspot hits' setting (0-100) or None for the default."""
    try:
        v = (forge.load_profile().get("extras") or {}).get("sniper_ws")
        return None if v in (None, "") else float(v)
    except Exception:  # noqa: BLE001
        return None


def theory_psi() -> float:
    return max_psi() + psi_bonus()


def all_mods_maxed() -> list[dict]:
    gd = forge.gamedata()
    out = []
    for gm in gd["mods"].values():
        if not gm.get("slot_key"):
            continue
        for v in (gm.get("variant_substats") or {"General": []}):
            out.append({"name": gm["name"], "variant": v, "slot": gm["slot_key"], "level": 17,
                        "tiers": forge.tiers_from_level(17), "owned": False})
    return out


def set_shapes(top_sets: list[str]) -> list[tuple[dict, bool]]:
    """(set counts, needs key armor) — six armor slots, at most one key piece."""
    gd = forge.gamedata()
    size = {n: len(gd["sets"][n]["pieces"]) for n in top_sets}
    shapes: list[tuple[dict, bool]] = []
    for a in top_sets:
        if size[a] >= 6:
            shapes.append(({a: 6}, False))
        if size[a] >= 5:
            shapes.append(({a: 5}, True))
        for b in top_sets:
            if a == b:
                continue
            if size[a] >= 4:
                shapes += [({a: 4, b: 2}, False), ({a: 4, b: 1}, True)]
            if a < b:
                shapes += [({a: 3, b: 3}, False)]
            shapes.append(({a: 3, b: 2}, True))
    seen, out = set(), []
    for c, k in shapes:
        key = (tuple(sorted(c.items())), k)
        if key not in seen:
            seen.add(key); out.append((c, k))
    return out


def _extras(cfg, kw, scenario):
    return fx.build_extras(cfg, kw, scenario)


def _key_candidates(kw, marked, weapon=None):
    out = [None]
    for n, k in fx.KEY_ARMOR.items():
        if k.get("unmodeled") or not k["stats"] or k.get("aka"):
            continue
        if not fx.key_armor_fits(n, kw, weapon):
            continue
        if k.get("needs_mark") and not (marked or kw == "The Bull's Eye"):
            continue
        out.append(n)
    return out


def optimize_weapon(w, pool, psi, scenario, marked=False, rounds=2, map_id=None):
    kw = w.get("keyword")
    st = {"name": w["name"], "stars": MAX_STARS, "tier": 5, "calibration": None}
    sw = sniper_setting()
    if sw is not None:
        st["_sniper_ws"] = sw
    cals = fx.calibration_options(w.get("type"))
    cfg = {"deviation": None, "deviation_level": 5, "class": "chef", "consumables": [], "key_armor": None,
           "calibration": cals[0], "marked": marked, "vuln_amp": marked, "mask_hide": None, "weapon": w["name"],
           "map": map_id, "cradle": []}
    import forge_cradle as fc
    has_cradle = bool((fc.map_info(map_id) or {}).get("cradle")) and fe.split_key(scenario)[0] != "abyss"
    hides = [None] + [n for n, h in fx.MASK_HIDES.items() if not h.get("unmodeled")]
    sets: dict = {}
    chosen = forge.best_mods_for(w, st, pool, sets, psi, scenario, passes=2, extras=_extras(cfg, kw, scenario))

    def score(c, s, ch=None):
        mods = [m for m in (ch or chosen).values() if m]
        return forge.evaluate(w, st, mods, s, psi, scenario, extras=_extras(c, kw, scenario))["dps"]

    gd = forge.gamedata()
    for _ in range(rounds):
        # consumables, deviation, calibration
        if has_cradle:
            cfg["cradle"] = fc.auto_pick(map_id, w.get("type"), kw, cfg, scenario,
                                         score=lambda n: score(dict(cfg, cradle=n), sets))
        cfg["consumables"] = fx.best_consumables(lambda n: score(dict(cfg, consumables=n), sets), "chef")[1]
        for field, opts in (("calibration", cals), ("deviation", [None, *fx.DEVIATIONS]), ("mask_hide", hides)):
            best_v, best_o = -1, cfg[field]
            for o in opts:
                v = score(dict(cfg, **{field: o}), sets)
                if v > best_v:
                    best_v, best_o = v, o
            cfg[field] = best_o
        # armor: rank sets at 4pc, then try six-slot shapes with/without a key piece
        rank = sorted(((score(cfg, {n: 4}), n) for n, s in gd["sets"].items() if len(s["pieces"]) >= 4), reverse=True)
        top = [n for _, n in rank[:5]]
        best_v, best = score(cfg, sets), (sets, cfg["key_armor"])
        keys = _key_candidates(kw, marked, w["name"])
        for combo, needs_key in set_shapes(top):
            for k in (keys[1:] if needs_key else [None]):
                v = score(dict(cfg, key_armor=k), combo)
                if v > best_v:
                    best_v, best = v, (combo, k)
        sets, cfg["key_armor"] = best[0], best[1]
        chosen = forge.best_mods_for(w, st, pool, sets, psi, scenario, passes=2, extras=_extras(cfg, kw, scenario))
    summ = forge.build_summary(w, st, chosen, sets, psi, scenario, "Best possible in game (theory)",
                               extras=_extras(cfg, kw, scenario), config=_cfg_public(cfg))
    return summ


def _cradle_line(scenario, map_id):
    import forge_cradle as fc
    m = fc.map_info(map_id)
    if fe.split_key(scenario)[0] == "abyss":
        return "Abyss: no Cradle, as in your run."
    if not m:
        return "Cradle not counted (no map picked in Class & settings)."
    if not m["cradle"]:
        return f"{m['label']}: no Cradle."
    return f"{m['label']}: best Cradle override per row for each weapon (estimate; {m['note']})"


def _cfg_public(cfg):
    c = dict(cfg)
    cal = c.get("calibration")
    c["calibration"] = cal and {"label": cal["label"], "source": cal["source"]}
    for field, table in (("key_armor", fx.KEY_ARMOR), ("deviation", fx.DEVIATIONS)):
        n = c.get(field)
        c[field] = n and {"name": n, "text": table[n]["text"], "source": table[n]["source"],
                          "approx": table[n].get("approx")}
    c.update(forge.public_consumables(cfg))
    c.update(forge.public_cradle(cfg))
    return c


_CACHE: dict = {}
import threading as _th
_LOCK = _th.Lock()


_FROM_PROFILE = object()


def profile_map():
    try:
        return (forge.load_profile().get("extras") or {}).get("map") or None
    except Exception:
        return None


def theory(scenario: str = "boss", marked: bool = False, keep: int = 25, top_n: int = 10, map_id=_FROM_PROFILE) -> dict:
    """Map defaults to the one in your profile, so the ladder counts a Cradle only where your map has one."""
    if map_id is _FROM_PROFILE:
        map_id = profile_map()
    with _LOCK:
        return _theory(scenario, marked, keep, top_n, map_id)


def _theory(scenario, marked, keep, top_n, map_id=None):
    bonus = psi_bonus()
    ck = (scenario, marked, forge.gamedata()["retrieved_at"], bonus, sniper_setting(), map_id)
    if ck in _CACHE:
        return _CACHE[ck]
    t0 = time.time()
    gd = forge.gamedata()
    pool = all_mods_maxed()
    psi = max_psi() + bonus
    # stage 1: cheap prescreen (best mods, full consumables, no sets)
    pre = []
    for w in gd["weapons"].values():
        if not w.get("legendary"):
            continue
        st = {"name": w["name"], "stars": MAX_STARS, "tier": 5}
        cfg = {"deviation": "Lonewolf's Whisper", "class": "chef",
               "consumables": ["Shattered Bread", "Stargazy Pie", "Whimsical Drink"],
               "calibration": fx.calibration_options(w.get("type"))[0], "marked": marked, "mask_hide": "Golden Wool",
               "weapon": w["name"], "map": map_id}
        ex = _extras(cfg, w.get("keyword"), scenario)
        ch = forge.best_mods_for(w, st, pool, {}, psi, scenario, passes=1, extras=ex)
        pre.append((forge.evaluate(w, st, [m for m in ch.values() if m], {}, psi, scenario, extras=ex)["dps"], w["name"]))
    pre.sort(reverse=True)
    builds = [optimize_weapon(gd["weapons"][n], pool, psi, scenario, marked, map_id=map_id) for _, n in pre[:keep]]
    builds.sort(key=lambda b: -b["dps"])
    out = {
        "scenario": {"key": scenario, **{k: v for k, v in fe.scn(scenario).items() if k != "vision"}},
        "psi": {"value": round(psi), "basis": "max-star armor in every slot" + (
            f" + {bonus:g} Psi from outside armor (your character sheet minus your armor)" if bonus else "")},
        "marked_support": marked,
        "assumptions": [
            "Every weapon at 6 stars; every mod at level 17 (the Mod 2.0 cap: three lines at grade 5, one at grade 2).",
            "Legendary calibration at its maximum roll (Attack +50% plus one bonus line).",
            "Chef class: 2 food + 2 drink effects (a food + drink dish uses one of each); the combat deviation at skill level 5.",
            "At most one key armor piece; key pieces do not count toward a set.",
            _cradle_line(scenario, map_id)
            if not fe.scn(scenario).get("custom") else
            f"Custom fight: {fe.scn(scenario).get('label')} (buffs: {fe.scn(scenario).get('buff_text') or 'none'}).",
            "Bull's Eye mark held by a support weapon or teammate, with a Vulnerability Amplifier on it." if marked else "Solo: no Bull's Eye mark unless the weapon makes its own.",
        ],
        "builds": builds[:top_n],
        "ranking": [{"weapon": b["weapon"]["name"], "dps": b["dps"]} for b in builds],
        "seconds": round(time.time() - t0, 1),
    }
    _CACHE[ck] = out
    return out


if __name__ == "__main__":
    import sys
    r = theory(sys.argv[1] if len(sys.argv) > 1 else "boss", marked="--marked" in sys.argv)
    print("psi", r["psi"], "time", r["seconds"])
    for b in r["builds"]:
        c = b["config"]
        print(f"{b['dps']:>9,}  {b['weapon']['name']:<32} {b['weapon']['keyword'] or '':<16} sets={b['sets']} key={c['key_armor'] and c['key_armor']['name']} "
              f"dev={c['deviation'] and c['deviation']['name']} food={c['food'] and c['food']['name']} cal={c['calibration']['label'][:30]}")
        print("     crit", b["result"]["derived"]["crit_rate"], "cdmg", b["result"]["derived"]["crit_dmg"],
              {k: round(v) for k, v in b["result"]["breakdown"].items()})
