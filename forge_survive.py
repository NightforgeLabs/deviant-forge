"""Deviant Forge survivability: how hard your build is to kill, and the toughest builds you can make
from what you own if you give up 5%, 10% or all of your damage.

Toughness = effective HP for one long fight:
    HP       = armor HP at your stars x (1 + HP% from mods and sets) + flat HP from sets
    shield   = shield you can count on once per fight (as % of Max HP)
    taken    = share of incoming damage that gets through after every damage reduction,
               each one weighted by how often it is active in a boss fight (estimates below)
    toughness = (HP + shield) / taken
Your character's own base HP, Deviations, food and healing are not counted; they are the same for every
build, or depend on how you play. Every number is a labeled estimate.
"""
from __future__ import annotations

import re

import forge as F
import forge_extras as fx

# How often each conditional damage reduction is active in a long boss fight (estimates).
UPTIME = {
    "when_hit": 0.5,      # "DMG Reduction When Hit": X% for 3s, cooldown 6s
    "deviant": 0.5,       # share of a dungeon's damage that comes from Deviants
    "lunar_dr": 0.25,     # Lunar DR vs Deviants scales with missing HP; Deviants share
    "front": 0.8,         # Mirror: damage from the front
    "far": 0.3,           # Wild: damage from beyond 15m
    "low_half": 0.5,      # "when HP is below 50%": protects half of your HP bar
    "low_30": 0.3,        # "when HP is below 30%"
    "head": 0.15,         # share of hits that land on your head / weakspot
    "torso": 0.6,         # share of hits that land on your torso
    "status": 0.3,        # share of boss damage that is status/elemental damage
    "weapon": 0.2,        # share of damage from enemies with guns
    "load": 0.5,          # Raid set: Load above 80
    "stacks_hit": 0.8,    # stacking DR from taking hits, average stacks held
    "close_one": 0.5,     # one boss within 5-7m
    "airborne": 0.05,
    "heal_shot": 0.05,    # 2s after a healing shot
}
UPTIME_TEXT = {
    "when_hit": "active about half the fight (3s on, 6s cooldown)",
    "deviant": "counted for half of the damage (the Deviant share of a dungeon, estimate)",
    "lunar_dr": "counted a quarter (it grows as your HP drops, and only vs Deviants)",
    "front": "counted 80% (bosses mostly hit you from the front)",
    "far": "counted 30% (time spent beyond 15m)",
    "low_half": "counted for the lower half of your HP bar",
    "low_30": "counted for the last 30% of your HP bar",
    "head": "counted for head hits (about 15% of hits)",
    "torso": "counted for torso hits (about 60% of hits)",
    "status": "counted for status / elemental damage (about 30% of a boss's damage)",
    "weapon": "counted for damage from enemies with guns (about 20%)",
    "load": "counted half the time (needs Load above 80)",
    "stacks_hit": "counted at 80% of max stacks while you're being hit",
    "close_one": "counted half the time (one boss up close)",
    "airborne": "counted 5% (time in the air)",
    "heal_shot": "counted 5% (2s after each healing shot)",
}
MAX_DR = 0.85
SURV_RE = re.compile(r"\bhp\b|dmg reduction|damage taken|dmg taken|shield|heal|recover|restor", re.I)


def _n(s, i=0):
    v = F._nums(s)
    return abs(v[i]) if len(v) > i else 0.0


def text_effects(text: str) -> tuple[list[dict], bool]:
    """Survival effects in one game text. Returns (effects, recognized). effects: {kind, value, up, why}."""
    t = (text or "").strip()
    low = t.lower()
    E = []

    def dr(v, up, why=None):
        E.append({"kind": "dr", "value": v, "up": UPTIME.get(up, up) if isinstance(up, str) else up,
                  "why": why or UPTIME_TEXT.get(up, "always on")})
    if not t or not SURV_RE.search(t):
        return [], True
    if re.search(r"stamina", low) and not re.search(r"\bhp\b|dmg reduction|shield", low):
        return [], True  # stamina only
    if "reduces max hp" in low:
        return [], False
    if not re.search(r"\bhp \+|max hp \+|dmg reduction|damage taken|dmg taken|recover|restor|heal|shield equal|grants? .{0,20}shield|generates? a shield", low):
        return [], True  # HP / shield only as a condition for more damage
    if m := re.fullmatch(r"(?:max )?hp \+(\d+(?:\.\d+)?)%", low):
        return [{"kind": "hp_pct", "value": float(m.group(1)), "up": 1.0, "why": "always on"}], True
    if m := re.fullmatch(r"hp \+(\d+)", low):
        return [{"kind": "hp_flat", "value": float(m.group(1)), "up": 1.0, "why": "always on"}], True
    if "load exceeds 80" in low and "dmg taken" in low:
        dr(_n(t, 1), "load"); return E, True
    if m := re.match(r"head dmg reduction \+(\d+)%", low):
        dr(float(m.group(1)), "head"); return E, True
    if m := re.match(r"torso dmg reduction \+(\d+)%", low):
        dr(float(m.group(1)), "torso"); return E, True
    if m := re.match(r"status dmg reduction \+(\d+)%", low):
        dr(float(m.group(1)), "status"); return E, True
    if m := re.match(r"weapon dmg reduction \+(\d+)%", low):
        dr(float(m.group(1)), "weapon"); return E, True
    if "powered armor" in low and "dmg reduction" in low:
        dr(_n(t) * 6, "stacks_hit"); return E, True  # +4% x 6 stacks
    if low.startswith("within 5m, each enemy grants you dmg reduction"):
        dr(_n(t, 1), "close_one", "counted as one boss within 5m, half the time"); return E, True
    if "while airborne" in low and "dmg reduction" in low:
        dr(_n(t), "airborne"); return E, True
    if "shield equal to 30% of max hp when hp is below 40%" in low:
        return [{"kind": "shield_pct", "value": 30.0, "up": 1.0, "why": "counted once per fight (8s cooldown, needs low HP)"}], True
    if "healing shot" in low and "dmg reduction" in low:
        dr(_n(t), "heal_shot"); return E, True
    if "dmg reduction" in low and "below 30%" in low:
        dr(_n(t), "low_30"); return E, True
    if low.startswith("having enemies within 7 meters"):
        dr(_n(t) * 0.5 + _n(t, 2) * 0.2, 1.0, "half the time up close, plus the melee part 20% of the time"); return E, True
    if low.startswith("weakspot dmg reduction"):
        dr(_n(t) + _n(t, 1) * 0.4, "head", "counted for head hits; the extra part while HP is above 60% counted 40%"); return E, True
    if low.startswith("while the shield is active, you gain") and "dmg reduction" in low:
        E.append({"kind": "dr_shielded", "value": _n(t, 0), "up": 1.0, "why": "counted while you have a shield"}); return E, True
    return [], False


def line_effects(line: str, raw: str) -> tuple[list[dict], bool]:
    """Survival effects of one mod attribute line (game name + value text at your tier)."""
    low = line.lower()
    v = _n(raw)
    if not v:
        return [], True
    if low == "hp":
        return [{"kind": "hp_pct", "value": v, "up": 1.0, "why": "always on"}], True
    if low.startswith("dmg reduction when hit"):
        return [{"kind": "dr", "value": v, "up": UPTIME["when_hit"], "why": UPTIME_TEXT["when_hit"]}], True
    if low.startswith("deviant dmg reduction"):
        return [{"kind": "dr", "value": v, "up": UPTIME["deviant"], "why": UPTIME_TEXT["deviant"]}], True
    if "dmg reduction against deviants" in low:
        return [{"kind": "dr", "value": v, "up": UPTIME["lunar_dr"], "why": UPTIME_TEXT["lunar_dr"]}], True
    if "damage taken from the front" in low:
        return [{"kind": "dr", "value": v, "up": UPTIME["front"], "why": UPTIME_TEXT["front"]}], True
    if "damage taken from beyond 15m" in low:
        return [{"kind": "dr", "value": v, "up": UPTIME["far"], "why": UPTIME_TEXT["far"]}], True
    if "damage taken" in low and "below 50%" in low:
        return [{"kind": "dr", "value": v, "up": UPTIME["low_half"], "why": UPTIME_TEXT["low_half"]}], True
    if SURV_RE.search(line) and not re.search(r"\b(dmg|damage)\b.*\+x", low):
        return [], False
    return [], True


def _armor_hp(name: str, stars: int) -> float:
    a = F.gamedata()["armor"].get(name) or {}
    ps = a.get("stats_per_star") or {}
    if not ps:
        return float(a.get("hp") or 0)
    k = max((int(s) for s in ps if int(s) <= max(1, stars)), default=min(int(s) for s in ps))
    return float(ps[str(k)].get("HP") or a.get("hp") or 0)


_MOD_EFF: dict = {}
_LAY_EFF: dict = {}


def _mod_effects(m: dict) -> tuple[list, list]:
    k = (m["name"], m.get("variant") or "General", tuple(m.get("tiers") or ()))
    if k not in _MOD_EFF:
        gd = F.gamedata()
        counted, missed = [], []
        gm = gd["mods"].get(m["name"].lower()) or {}
        core = F._core_text(gm.get("name") or m["name"])
        effs, ok = text_effects(core)
        counted += [dict(e, src=f"{m['name']} (core)", text=core) for e in effs]
        if not ok:
            missed.append({"src": f"{m['name']} (core)", "text": core})
        names = None
        for vname, subs in (gm.get("variant_substats") or {}).items():
            if vname.lower() == (m.get("variant") or "General").lower():
                names = subs
        for ln in F.mod_lines_eval(gm, names or [], m.get("tiers") or []):
            if ln["tier"]:
                effs, ok = line_effects(ln["line"], ln["text"])
                src, txt = f"{m['name']} ({m['variant']})", f"{ln['line'].split(':')[0]} {ln['text']}".strip()
                counted += [dict(e, src=src, text=txt) for e in effs]
                if not ok:
                    missed.append({"src": src, "text": txt})
        _MOD_EFF[k] = (counted, missed)
    return _MOD_EFF[k]


def _layout_effects(layout: dict) -> tuple:
    k = tuple(((x or {}).get("name"), int((x or {}).get("stars") or 1)) for x in (layout.get(s) for s in F.ARMOR_SLOT_NAMES))
    if k not in _LAY_EFF:
        gd = F.gamedata()
        hp_base = sum(_armor_hp(x["name"], int(x.get("stars") or 1)) for x in layout.values() if x)
        counted, missed, counts = [], [], {}
        for x in layout.values():
            a = gd["armor"].get((x or {}).get("name") or "")
            if a and x["name"] not in fx.KEY_ARMOR and a.get("set") and len(a.get("set_effects") or {}) >= 2:
                counts[a["set"]] = counts.get(a["set"], 0) + 1
            ka = fx.KEY_ARMOR.get((x or {}).get("name") or "")
            if ka and SURV_RE.search(ka.get("text") or ""):
                effs, ok = text_effects(ka["text"])
                counted += [dict(e, src=x["name"], text=ka["text"]) for e in effs]
                if not ok:
                    missed.append({"src": x["name"], "text": ka["text"]})
        for st, n in counts.items():
            for kk, txt in sorted((gd["sets"].get(st) or {}).get("effects", {}).items()):
                if int(kk) <= n:
                    if st == "Savior" and kk == "3":
                        missed.append({"src": f"{st} {kk}pc", "text": "Shield made by spending 8% of your HP: treated as no net survival"})
                        continue
                    effs, ok = text_effects(txt)
                    counted += [dict(e, src=f"{st} {kk}pc", text=txt) for e in effs]
                    if not ok:
                        missed.append({"src": f"{st} {kk}pc", "text": txt})
        _LAY_EFF[k] = (hp_base, counted, missed, counts)
    return _LAY_EFF[k]


def toughness(layout: dict, mods: list[dict], weapon: dict | None = None, detail: bool = True) -> dict:
    """layout: {Slot: {name, stars} | None}; mods: owned-mod dicts. Returns the toughness breakdown."""
    hp_base, lc, lm, counts = _layout_effects(layout)
    counted, missed = list(lc), list(lm)
    for m in mods:
        c, mm = _mod_effects(m)
        counted += c; missed += mm
    if weapon and SURV_RE.search(weapon.get("effect_text") or ""):
        missed.append({"src": weapon["name"], "text": "Weapon healing / HP effects"})
    hp_pct = hp_flat = shield_pct = 0.0
    for e in counted:
        if e["kind"] == "hp_pct": hp_pct += e["value"]
        elif e["kind"] == "hp_flat": hp_flat += e["value"]
        elif e["kind"] == "shield_pct": shield_pct += e["value"]
    hp = hp_base * (1 + hp_pct / 100) + hp_flat
    shield_up = 1.0 if shield_pct else (F.SAVIOR_SHIELD_UPTIME if counts.get("Savior", 0) >= 3 else 0.0)
    taken = 1.0
    for e in counted:
        if e["kind"] == "dr":
            taken *= 1 - min(0.95, e["value"] / 100 * e["up"])
        elif e["kind"] == "dr_shielded":
            taken *= 1 - min(0.95, e["value"] / 100 * shield_up)
    taken = max(1 - MAX_DR, taken)
    shield = hp * shield_pct / 100
    out = {"toughness": round((hp + shield) / taken)}
    if not detail:
        return out
    for i, e in enumerate(counted):
        if e["kind"] == "dr_shielded":
            counted[i] = dict(e, up=shield_up, why=f"counted {int(round(shield_up * 100))}% (time you have a shield)")
    out.update({"hp": round(hp), "hp_armor": round(hp_base), "hp_pct": round(hp_pct, 1), "hp_flat": round(hp_flat),
                "shield": round(shield), "dr_pct": round((1 - taken) * 100, 1), "counted": counted,
                "not_counted": missed, "sets": counts})
    return out


# ------------------------------------------------------------------ search
def _layout_sig(lay):
    return tuple((lay.get(s) or {}).get("name") for s in F.ARMOR_SLOT_NAMES)


class _Ctx:
    def __init__(self, profile, scenario, pool, weapons):
        self.profile, self.scenario, self.pool, self.weapons = profile, scenario, pool, weapons
        self.gd = F.gamedata()
        ex = dict(profile.get("extras") or {})
        if "vuln_amp" not in ex:  # saves an owned_mods() call per layout
            ex["vuln_amp"] = any(m.get("name") == "Vulnerability Amplifier" for m in pool)
        self.extras = ex
        self._lay = {}
        self._dps = {}
        self._t = {}

    def lay_ctx(self, lay, w):
        k = (_layout_sig(lay), w["name"])
        if k not in self._lay:
            arm = {s: {"name": x["name"], "stars": x["stars"], "tier": 5} for s, x in lay.items() if x}
            p2 = dict(self.profile, armor=arm, extras=self.extras)
            sc = F.set_counts_from_profile(p2)
            psi, _ = F.estimate_psi(p2, sc)
            self._lay[k] = (p2, sc, psi, F.owned_extras(p2, w, self.scenario))
        return self._lay[k]

    def dps(self, w, lay, mods):
        k = (w["name"], _layout_sig(lay), tuple(sorted((s, (m["name"], m["variant"])) for s, m in mods.items() if m)))
        if k not in self._dps:
            p2, sc, psi, ex = self.lay_ctx(lay, w)
            ws = next(x for x in self.weapons if x["name"] == w["name"])
            self._dps[k] = F.evaluate(w, ws, [m for m in mods.values() if m], sc, psi, self.scenario, extras=ex)["dps"]
        return self._dps[k]

    def tough(self, lay, mods):
        k = (_layout_sig(lay), tuple(sorted((s, (m["name"], m["variant"])) for s, m in mods.items() if m)))
        if k not in self._t:
            self._t[k] = toughness(lay, [m for m in mods.values() if m], detail=False)["toughness"]
        return self._t[k]


def _seeds(by_slot, worn_layout, best_layout, gd):
    """Starting armor layouts: what you wear, the best-DPS armor, most HP per slot, and each owned set at 4 (or 2-3) pieces."""
    seeds = [worn_layout]
    if best_layout:
        seeds.append(best_layout)
    hp_lay = {s: (max(v, key=lambda x: _armor_hp(x["name"], x["stars"])) if v else None) for s, v in by_slot.items()}
    seeds.append(hp_lay)
    sets = {}
    for s, v in by_slot.items():
        for x in v:
            if x.get("set"):
                sets.setdefault(x["set"], {})[s] = x
    for name, slots in sets.items():
        if len(slots) < 2:
            continue
        base = dict(hp_lay)
        order = sorted(slots, key=lambda s: -_armor_hp(slots[s]["name"], slots[s]["stars"]))[:4]
        for s in order:
            base[s] = slots[s]
        seeds.append(base)
    out, seen = [], set()
    for L in seeds:
        sig = _layout_sig(L)
        if sig not in seen:
            seen.add(sig); out.append(dict(L))
    return out


def survive(profile: dict | None = None, result: dict | None = None) -> dict:
    profile = profile or F.load_profile()
    result = result or F.optimize(profile)
    best = result.get("best")
    if not best:
        return {"error": "Add a weapon you own first. Survivability starts from a build you own."}
    gd = F.gamedata()
    scenario = result["scenario"]["key"]
    pool = F.owned_mods(profile)
    weapons = F.owned_weapons(profile)
    C = _Ctx(profile, scenario, pool, weapons)
    oa = F.owned_armor(profile)
    by_slot = {s: [] for s in F.ARMOR_SLOT_NAMES}
    for n, o in oa.items():
        if o.get("slot") in by_slot:
            by_slot[o["slot"]].append({"name": n, "stars": o["stars"], "set": o.get("set"), "key": n in fx.KEY_ARMOR})
    worn = {s: (p or {}).get("name") for s, p in (profile.get("armor") or {}).items()}
    worn_layout = {s: next((x for x in by_slot[s] if x["name"] == worn.get(s)), None) for s in F.ARMOR_SLOT_NAMES}
    BA = result.get("best_armor") if isinstance(result.get("best_armor"), dict) and not result["best_armor"].get("error") else None
    best_layout = None
    if BA:
        best_layout = {s: (next((x for x in by_slot[s] if x["name"] == (BA["armor"].get(s) or {}).get("name")), None)) for s in F.ARMOR_SLOT_NAMES}
    mods_by = {s: [m for m in pool if m["slot"] == s] for s in F.MOD_SLOTS}
    guns = [gd["weapons"][b["weapon"]["name"]] for b in [best] + (result.get("alternatives") or [])[:1]]
    seeds = _seeds(by_slot, worn_layout, best_layout, gd)

    def start_mods(w, lay):
        p2, sc, psi, ex = C.lay_ctx(lay, w)
        ws = next(x for x in weapons if x["name"] == w["name"])
        return F.best_mods_for(w, ws, pool, sc, psi, scenario, extras=ex)

    # reference: the best DPS over every seed (normally the Best build page's number)
    cands = []
    for w in guns:
        for lay in seeds[:2] if len(seeds) > 1 else seeds:
            mods = start_mods(w, lay)
            cands.append((w, dict(lay), dict(mods)))
    D0 = max(C.dps(w, l, m) for w, l, m in cands)
    w0, l0, m0 = max(cands, key=lambda c: C.dps(*c))
    T0 = C.tough(l0, m0) or 1

    # keep, per slot, the mods that matter: best for damage, best for toughness, best mix (swapped into the top build)
    cand_by = {}
    for s in F.MOD_SLOTS:
        rows = []
        for m in mods_by[s]:
            mm = dict(m0, **{s: m})
            rows.append((C.dps(w0, l0, mm) / D0, C.tough(l0, mm) / T0, m))
        keep = {id(r[2]): r[2] for r in sorted(rows, key=lambda r: -r[0])[:10]}
        keep.update({id(r[2]): r[2] for r in sorted(rows, key=lambda r: -r[1])[:8]})
        keep.update({id(r[2]): r[2] for r in sorted(rows, key=lambda r: -(r[0] + r[1]))[:6]})
        if m0.get(s):
            keep[id(m0[s])] = m0[s]
        cand_by[s] = list(keep.values())

    def moves(w, lay, mods):
        for s in F.MOD_SLOTS:
            for m in cand_by[s]:
                if not mods.get(s) or (m["name"], m["variant"]) != (mods[s]["name"], mods[s]["variant"]):
                    yield lay, dict(mods, **{s: m})
        for s in F.ARMOR_SLOT_NAMES:
            for x in by_slot[s]:
                if not lay.get(s) or x["name"] != lay[s]["name"]:
                    yield dict(lay, **{s: x}), mods

    def climb(w, lay, mods, lam, floor):
        """Hill-climb score = dps/D0 + lam * toughness/T0, never dropping below floor x D0."""
        def sc(l, m):
            d = C.dps(w, l, m)
            return (-1e9 if d < floor * D0 else d / D0 + lam * C.tough(l, m) / T0), d
        cur, _ = sc(lay, mods)
        for _ in range(30):
            bestmv = None
            for l2, m2 in moves(w, lay, mods):
                v, _ = sc(l2, m2)
                if v > cur + 1e-7 and (not bestmv or v > bestmv[0]):
                    bestmv = (v, l2, m2)
            if not bestmv:
                break
            cur, lay, mods = bestmv
        return lay, mods

    finals = [(w, l, m) for w, l, m in cands]
    for lay in seeds:
        mods = start_mods(w0, lay)
        for lam in (0.3, 2.0, 1000.0):
            finals.append((w0,) + climb(w0, dict(lay), dict(mods), lam, 0.0))
    for w in guns[1:]:
        finals.append((w,) + climb(w, dict(l0), dict(start_mods(w, l0)), 1000.0, 0.0))
    # constrained toughening for each target, from every candidate that already meets the floor
    TARGETS = [("free", "Free toughness", 0.995), ("t5", "Give up 5% DPS", 0.95), ("t10", "Give up 10% DPS", 0.90),
               ("immortal", "Immortal", 0.0)]
    picks = {}
    pts = [(C.dps(*f), C.tough(f[1], f[2]), f) for f in finals]
    for key, label, floor in TARGETS:
        ok = sorted([p for p in pts if p[0] >= floor * D0], key=lambda p: (-p[1], -p[0]))[:3]
        res = []
        for d, t, (w, l, m) in ok:
            lam = 1000.0
            l2, m2 = climb(w, dict(l), dict(m), lam, floor)
            # then win back DPS without losing toughness
            l2, m2 = _regain(C, w, l2, m2, moves, D0, floor)
            res.append((C.tough(l2, m2), C.dps(w, l2, m2), w, l2, m2))
        if res:
            picks[key] = max(res, key=lambda r: (r[0], r[1]))
    ref = _card(C, "best", "Most DPS", w0, l0, m0, D0, T0, worn_layout, profile, result)
    out = {"reference": ref, "builds": [], "D0": D0, "T0": T0,
           "uptimes": [{"what": k, "how": UPTIME_TEXT[k]} for k in UPTIME_TEXT],
           "note": ("Toughness is effective HP: how much boss damage you can take before you die, with no healing. "
                    "It counts armor HP at your stars, HP% and damage reduction from mods and sets, and shields you can count on. "
                    "Conditional reductions are weighted by how often they're active (estimates).")}
    for key, label, floor in TARGETS:
        if key not in picks:
            continue
        t, d, w, l, m = picks[key]
        if key == "free" and t <= T0 * 1.01:
            out["free_none"] = True
            continue
        out["builds"].append(_card(C, key, label, w, l, m, D0, T0, worn_layout, profile, result, floor=floor))
    W = result.get("wearing")
    if W and W.get("build") and W.get("dps"):
        eq = (profile.get("extras") or {}).get("equipped") or {}
        wm = {s: None for s in F.MOD_SLOTS}
        by = {(m["name"].lower(), m["variant"].lower()): m for m in pool}
        for s, e in eq.items():
            m = by.get((str(e.get("name", "")).lower(), str(e.get("variant") or "General").lower()))
            if m and m["slot"] == s.lower():
                wm[s.lower()] = m
        tw = C.tough(worn_layout, wm)
        out["wearing"] = {"dps": W["dps"], "toughness": tw, "x": round(tw / T0, 2)}
        for b in out["builds"] + [ref]:
            b["beats_wearing"] = b["dps"] >= W["dps"] and b["toughness"] > tw * 1.01
    return out


def _regain(C, w, lay, mods, moves, D0, floor):
    t0 = C.tough(lay, mods)
    for _ in range(20):
        d0 = C.dps(w, lay, mods)
        bestmv = None
        for l2, m2 in moves(w, lay, mods):
            if C.tough(l2, m2) >= t0 - 1e-6:
                d = C.dps(w, l2, m2)
                if d > d0 * 1.0005 and (not bestmv or d > bestmv[0]):
                    bestmv = (d, l2, m2)
        if not bestmv:
            break
        _, lay, mods = bestmv
        t0 = C.tough(lay, mods)
    return lay, mods


def _card(C, key, label, w, lay, mods, D0, T0, worn_layout, profile, result, floor=None):
    ws = next(x for x in C.weapons if x["name"] == w["name"])
    p2, sc, psi, ex = C.lay_ctx(lay, w)
    b = F.build_summary(w, ws, mods, sc, psi, C.scenario, label, extras=ex, config=F._public_cfg(F.auto_cfg(p2, w, C.scenario)))
    T = toughness(lay, [m for m in mods.values() if m], w)
    worn = {s: (worn_layout.get(s) or {}).get("name") for s in F.ARMOR_SLOT_NAMES}
    changes = [{"slot": s, "now": worn.get(s), "to": (lay.get(s) or {}).get("name")} for s in F.ARMOR_SLOT_NAMES
               if (lay.get(s) or {}).get("name") != worn.get(s)]
    return {"key": key, "label": label, "floor_pct": None if floor is None else round(floor * 100, 1),
            "dps": b["dps"], "dps_pct": round(b["dps"] / D0 * 100, 1), "toughness": T["toughness"],
            "x": round(T["toughness"] / T0, 2), "hp": T["hp"], "hp_armor": T["hp_armor"], "hp_pct": T["hp_pct"],
            "hp_flat": T["hp_flat"], "shield": T["shield"], "dr_pct": T["dr_pct"],
            "counted": [{"src": e["src"], "text": e["text"], "kind": e["kind"], "value": e["value"],
                         "up": round(e["up"], 2), "why": e["why"]} for e in T["counted"]],
            "not_counted": T["not_counted"],
            "armor": {s: ({"name": x["name"], "stars": x["stars"], "set": x.get("set")} if x else None) for s, x in lay.items()},
            "armor_changes": changes, "build": b}


_CACHE: dict = {}


def survive_cached(profile: dict) -> dict:
    """Same answer for the same profile and game data (the search takes a few seconds)."""
    import json as _j
    import forge_live as _fl
    try:
        mt = _fl.active_snapshot().stat().st_mtime
    except Exception:
        mt = 0
    k = (_j.dumps(profile, sort_keys=True, default=str), mt)
    if k not in _CACHE:
        _CACHE.clear()
        _CACHE[k] = survive(profile)
    return _CACHE[k]
