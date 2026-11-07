"""Path to max: the quickest order of upgrades from your build now to the strongest build you can reach.

Each step re-runs the optimizer on a "future you" profile (a copy; nothing is saved), picks the next upgrade
with the best damage per effort, applies it, and repeats. All DPS numbers are estimates.
"""
from __future__ import annotations

import copy
import hashlib
import json
import threading
import time

import forge
import forge_extras as fx
import forge_live as fl

SLOTS = ["Helmet", "Mask", "Top", "Gloves", "Bottoms", "Shoes"]
MAX_STEPS = 10
MIN_GAIN = 1.5          # stop when the best next step adds less than this (%)
# Effort that isn't Starchrom, in Starchrom-equivalents. Only used to order the steps.
EFFORT = {"food": 0, "hide": 2000, "deviation": 3000, "mod": 4000, "calibration": 5000, "keyarmor": 0,
          "weapon": 0, "armor": 0, "combo": 0, "stars": 3000, "secondary": 0}
HOW = {"food": "cook", "hide": "breed / hunt", "deviation": "catch", "mod": "farm drops / crates",
       "calibration": "calibrate (luck)", "keyarmor": "Starchrom", "weapon": "Starchrom", "armor": "Starchrom",
       "combo": "Starchrom", "stars": "duplicates + Starchrom", "secondary": "Starchrom"}
WEAPON_LOCKED = {"calibration", "stars"}   # wasted if you change main weapon later
PLAN_FILE = fl.LIVE / "path_plan.json"

JOB: dict = {"running": False, "pct": 0, "msg": "", "error": None}
_LOCK = threading.Lock()


def fe_key(scen) -> str:
    import forge_effects as fe
    k = scen.get("key") if isinstance(scen, dict) else scen
    return k or "boss"


def profile_hash(profile: dict) -> str:
    keep = {k: v for k, v in profile.items() if k not in ("updated_at",)}
    keep["_data"] = forge.data_info().get("retrieved_at") if hasattr(forge, "data_info") else ""
    return hashlib.sha1(json.dumps(keep, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _assign_set(prof: dict, set_name: str, combo: dict) -> None:
    gd = forge.gamedata()
    armor = prof.setdefault("armor", {})
    pieces = {a["slot"]: a["name"] for a in gd["armor"].values() if forge.set_key(a) == set_name and a.get("slot") in SLOTS}
    locked = set()
    for slot, p in armor.items():  # keep key armor and up to N pieces of each other kept set
        if p.get("name") in fx.KEY_ARMOR:
            locked.add(slot)
    for other, n in combo.items():
        if other == set_name:
            continue
        mine = [s for s, p in armor.items() if forge.set_key(gd["armor"].get(p.get("name"), {"name": p.get("name", "")})) == other]
        locked |= set(mine[:n])
    have = sum(1 for s, p in armor.items() if p.get("name") in pieces.values())
    need = max(0, combo.get(set_name, 4) - have)
    owned = forge.owned_armor(prof)
    # pieces you already own first, then empty slots
    for slot in sorted(pieces, key=lambda s: (pieces[s] not in owned, s in armor, SLOTS.index(s))):
        if need <= 0:
            break
        if slot in locked or armor.get(slot, {}).get("name") == pieces[slot]:
            continue
        armor[slot] = {"name": pieces[slot], "stars": (owned.get(pieces[slot]) or {}).get("stars", 1), "tier": 5}
        prof.setdefault("armor_owned", {}).setdefault(pieces[slot], {"stars": armor[slot]["stars"]})
        need -= 1


def apply_action(prof: dict, act: dict) -> None:
    if act.get("weapon") and not any(w.get("name") == act["weapon"] for w in prof.get("weapons") or []):
        prof.setdefault("weapons", []).append({"name": act["weapon"], "stars": 1, "tier": 5})
    if act.get("set"):
        _assign_set(prof, act["set"], act.get("combo") or {act["set"]: 4})
    if act.get("mod"):
        prof.setdefault("mods", []).append(dict(act["mod"]))
    if act.get("extras"):
        prof.setdefault("extras", {}).update(act["extras"])
    for slot, name in (act.get("armor") or {}).items():
        prof.setdefault("armor", {})[slot] = {"name": name, "stars": 1, "tier": 5}
    if act.get("stars"):
        prof.setdefault("weapon_edits", {}).setdefault(act["stars"], {})["stars"] = 6
    if act.get("calibration"):
        name, cal = act["calibration"]
        prof.setdefault("weapon_edits", {}).setdefault(name, {})["calibration"] = cal


def _score(u: dict) -> float:
    cost = (u.get("cost_starchrom") or 0) + EFFORT.get(u["kind"], 3000)
    return u["gain_pct"] / (cost / 10000 + 0.25)


def _pick(upgrades: list, done: set) -> dict | None:
    cands = [u for u in upgrades if u.get("action") and not u["action"].get("needs_team")
             and u["gain_pct"] >= MIN_GAIN and u["title"] not in done]
    if not cands:
        return None
    # Settle the main weapon before spending luck on stars/calibration for the current one.
    switch = [u for u in cands if u["kind"] in ("weapon", "combo") and u["gain_pct"] >= 10]
    if switch:
        cands = [u for u in cands if u["kind"] not in WEAPON_LOCKED]
    return max(cands, key=_score)


def share(dps: float, team_rest: float | None) -> float | None:
    if not team_rest:
        return None
    return round(dps / (dps + team_rest) * 100, 1)


def _ceilings(scenario: str, marked: bool, final_w: str) -> tuple[dict, float | None]:
    """Theory #1 build and the maxed-out number for the plan's final weapon, under the same mark assumption."""
    import forge_theory as ft
    th = ft.theory(scenario, marked)
    top = th["ranking"][0] if th.get("ranking") else {}
    maxed = next((x["dps"] for x in th.get("ranking") or [] if x["weapon"] == final_w), None)
    if maxed is None:
        w = forge.gamedata()["weapons"].get(final_w)
        if w:
            try:
                maxed = ft.optimize_weapon(w, ft.all_mods_maxed(), ft.theory_psi(), scenario, marked)["dps"]
            except Exception:  # noqa: BLE001
                maxed = None
    return top, maxed


ROUTE_STEPS = 6
ROUTES = 2


def _commit(prof: dict, target: str) -> None:
    """Future you mains only `target`: add it if missing and set every other gun aside."""
    apply_action(prof, {"weapon": target})
    prof["weapons"] = [w for w in prof.get("weapons") or [] if w.get("name") == target]
    edits = prof.setdefault("weapon_edits", {})
    for w in forge.owned_weapons(prof):
        if w["name"] != target:
            edits.setdefault(w["name"], {})["removed"] = True


def route_to(base_prof: dict, target: str, maxed: float | None, start: float, ceiling: float,
             weapon_cost: int | None, steps: int = ROUTE_STEPS) -> dict | None:
    """Same greedy planner, but locked to one weapon from the top of the ranking."""
    prof = copy.deepcopy(base_prof)
    _commit(prof, target)
    r = forge.optimize(prof)
    if not r.get("best") or r["best"]["weapon"]["name"] != target:
        return None
    first = cur = r["best"]["dps"]
    rows, done, spent = [], set(), weapon_cost or 0
    for _ in range(steps):
        ups = [u for u in r["upgrades"] if not (u.get("action") or {}).get("weapon")
               or u["action"]["weapon"] == target]
        u = _pick(ups, done)
        if not u:
            break
        done.add(u["title"])
        apply_action(prof, u["action"])
        r2 = forge.optimize(prof)
        new = r2["best"]["dps"] if r2.get("best") else cur
        if new < cur * 1.01:
            r = r2
            continue
        spent += u.get("cost_starchrom") or 0
        rows.append({"kind": u["kind"], "title": u["title"], "how": HOW.get(u["kind"], ""),
                     "cost": u.get("cost_starchrom") or 0, "dps": round(new), "gain_pct": round((new / cur - 1) * 100, 1)})
        cur, r = new, r2
    return {"weapon": target, "first": round(first), "first_vs_now_pct": round((first / start - 1) * 100, 1),
            "weapon_cost": weapon_cost, "owned": weapon_cost == 0, "steps": rows, "end": round(cur), "spent": spent,
            "end_pct_of_top": round(cur / ceiling * 100, 1) if ceiling else None,
            "maxed": round(maxed) if maxed else None,
            "maxed_pct_of_top": round(maxed / ceiling * 100, 1) if ceiling and maxed else None}


def _weapon_cost(r0: dict, name: str, owned: set) -> int | None:
    if name in owned:
        return 0
    costs = [u.get("cost_starchrom") for u in r0.get("upgrades") or []
             if (u.get("action") or {}).get("weapon") == name and u.get("cost_starchrom")]
    return min(costs) if costs else None


def plan(profile: dict | None = None, progress=None, steps: int = MAX_STEPS) -> dict:
    progress = progress or (lambda p, m: None)
    base_prof = copy.deepcopy(profile or forge.load_profile())
    prof = copy.deepcopy(base_prof)
    t0 = time.time()
    progress(2, "working out your build now")
    r = forge.optimize(prof)
    if not r.get("best"):
        return {"error": "Add a weapon you own first.", "steps": []}
    start = r["best"]["dps"]
    start_w = r["best"]["weapon"]["name"]
    r0 = r
    ex = base_prof.get("extras") or {}
    g = ex.get("group_share") or {}
    team_rest = None
    if g.get("pct") and g.get("dps") and 0 < float(g["pct"]) < 100:
        team_rest = float(g["dps"]) * (100 - float(g["pct"])) / float(g["pct"])
    budget = base_prof.get("starchrom")
    rows, done, spent, cur = [], set(), 0, start
    for i in range(steps):
        u = _pick(r["upgrades"], done)
        if not u:
            break
        done.add(u["title"])
        apply_action(prof, u["action"])
        progress(5 + int(85 * (i + 1) / steps), f"step {i + 1}: {u['title'][:60]}")
        r2 = forge.optimize(prof)
        new = r2["best"]["dps"] if r2.get("best") else cur
        if new < cur * 1.01:   # under 1%: the model barely moved (overlap with an earlier step)
            r = r2
            continue
        spent += u.get("cost_starchrom") or 0
        rows.append({
            "n": len(rows) + 1, "kind": u["kind"], "title": u["title"], "detail": u.get("detail", ""),
            "how": HOW.get(u["kind"], ""), "cost": u.get("cost_starchrom") or 0, "spent": spent,
            "over_budget": budget is not None and spent > budget,
            "dps": round(new), "gain_pct": round((new / cur - 1) * 100, 1), "x_start": round(new / start, 2),
            "share": share(new, team_rest), "weapon": r2["best"]["weapon"]["name"],
        })
        cur, r = new, r2
    final_w = r["best"]["weapon"]["name"]
    scen = r.get("scenario") or base_prof.get("scenario") or "boss"
    marked = bool((prof.get("extras") or {}).get("marked"))
    progress(93, "comparing with the best builds in the game")
    top, maxed = _ceilings(fe_key(scen), marked, final_w)
    ceiling = top.get("dps") or 0
    for x in rows:
        x["pct_of_top"] = round(x["dps"] / ceiling * 100, 1) if ceiling else None
    grind = None
    if maxed and maxed > cur * 1.02:
        grind = {"weapon": final_w, "dps": round(maxed), "pct_of_top": round(maxed / ceiling * 100, 1) if ceiling else None,
                 "share": share(maxed, team_rest), "gain_pct": round((maxed / cur - 1) * 100, 1),
                 "text": f"Max out {final_w}: 6★, every mod at level 17, best calibration roll, best food and deviation. "
                         "This is grinding and luck (duplicates, mod rolls, calibration), not Starchrom."}
    # Routes that commit to a gun near the top of the ranking. The main plan is greedy (best gain per effort
    # with the mods you own now), so it can settle on a gun whose maxed-out number is far below #1.
    routes = []
    try:
        import forge_theory as ft
        th = ft.theory(fe_key(scen), marked)
        owned = {w["name"] for w in forge.owned_weapons(base_prof)}
        mine = maxed or cur
        cands = [x for x in th.get("ranking") or [] if x["weapon"] != final_w and x["dps"] > mine * 1.05][:ROUTES]
        for i, x in enumerate(cands):
            progress(94 + i * 2, f"route to {x['weapon'][:40]}")
            rt = route_to(base_prof, x["weapon"], x["dps"], start, ceiling, _weapon_cost(r0, x["weapon"], owned))
            if rt:
                rt["why_not_main"] = (
                    f"With the mods you own today it starts at {rt['first']:,} DPS ({rt['first_vs_now_pct']:+.1f}% vs now), "
                    f"so the step-by-step plan prefers cheaper wins. Its maxed-out number is {rt['maxed']:,} "
                    f"vs {round(mine):,} for {final_w}.")
                routes.append(rt)
    except Exception as e:  # noqa: BLE001 - never lose the main plan over the extra routes
        routes = [{"error": str(e)}]
    targets = {}
    if team_rest:
        for pct in (25, 33, 50):
            need = team_rest * pct / (100 - pct)
            hit = next((x["n"] for x in rows if x["dps"] >= need), None)
            targets[str(pct)] = {"dps": round(need), "step": hit, "start": start >= need,
                                 "grind": bool(grind and grind["dps"] >= need and hit is None)}
    # where it stops being worth it: last step that still adds >= 5%
    knee = max([x["n"] for x in rows if x["gain_pct"] >= 5] or [0]) or None
    out = {
        "made_at": fl.now(), "seconds": round(time.time() - t0, 1), "hash": profile_hash(base_prof),
        "scenario": fe_key(scen), "start": {"dps": round(start),
            "weapon": start_w,
            "pct_of_top": round(start / ceiling * 100, 1) if ceiling else None, "share": share(start, team_rest)},
        "top": {"weapon": top.get("weapon"), "dps": ceiling, "marked": marked}, "steps": rows, "grind": grind, "routes": routes,
        "end": {"dps": round(cur), "x_start": round(cur / start, 2), "spent": spent,
                "pct_of_top": round(cur / ceiling * 100, 1) if ceiling else None, "share": share(cur, team_rest)},
        "group": {"pct": g.get("pct"), "dps": g.get("dps"), "team_rest": round(team_rest) if team_rest else None,
                  "targets": targets},
        "knee": knee, "budget": budget,
        "notes": [
            "Estimates for your fight type. Each step re-runs the optimizer on a copy of your profile with that upgrade added.",
            "Order = most damage per effort. Non-Starchrom effort is weighted roughly: cooking free, hides 2k, "
            "deviations 3k, farming a mod 4k, a calibration roll 5k Starchrom-equivalent.",
            "Calibration and star steps assume top rolls; real rolls are lower.",
            "Group share assumes your teammates stay the same as on the run you typed in, and that the damage meter "
            "counts the same things the model does. Mob-heavy dungeons favour area damage.",
        ],
    }
    out["not_counted"] = sorted({n for n in (r["best"].get("not_counted") or [])})[:12] if isinstance(r["best"].get("not_counted"), list) else []
    return out


def start(profile: dict | None = None) -> dict:
    with _LOCK:
        if JOB["running"]:
            return dict(JOB)
        JOB.update({"running": True, "pct": 0, "msg": "starting", "error": None})
    prof = copy.deepcopy(profile or forge.load_profile())

    def work():
        try:
            res = plan(prof, lambda p, m: JOB.update({"pct": p, "msg": m}))
            fl.write_json(PLAN_FILE, res)
            JOB.update({"pct": 100, "msg": "done"})
        except Exception as exc:  # noqa: BLE001
            import traceback
            JOB.update({"error": str(exc), "msg": "failed"})
            print(traceback.format_exc())
        finally:
            JOB["running"] = False
    threading.Thread(target=work, daemon=True).start()
    return dict(JOB)


def status() -> dict:
    out = dict(JOB)
    out["plan"] = fl.read_json(PLAN_FILE, None)
    if out["plan"]:
        try:
            out["stale"] = out["plan"].get("hash") != profile_hash(forge.load_profile())
        except Exception:  # noqa: BLE001
            out["stale"] = None
    return out
