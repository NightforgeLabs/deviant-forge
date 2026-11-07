"""Mod crate advisor: "I have this crate, how do I spend it for the most power?"

Mod 2.0 rules (Jan 2026 onward):
  * mods drop at a fixed level 1-17; a higher copy of the same mod + suffix replaces the lower one,
    duplicates turn into Mod Dust (no enhancing).
  * a Lv 17 duplicate has a 30% chance to turn the mod Shiny; the 6th try is guaranteed.
  * weekly Lv 17 crate pity: about 1% around hit 80, guaranteed by hit 140, one per account per week (banks up to 5).
    The activity you finish decides which slot's crate you get. Purchased crates never count as pity hits.
  * a hidden counter gives a Lv 17 crate after roughly 1,000 eligible rolls (not a fixed guarantee).

Sources:
  https://www.oncehuman.game/news/devBlog/20251212/40781_1276354.html  (levels, dust, shiny)
  https://www.oncehuman.game/news/devBlog/20260123/40781_1283429.html  (drop levels by difficulty, shiny)
  https://www.oncehuman.game/news/update/20260709/40780_1307147.html   (scenario rating + collection rewards)
  https://www.oncehub.de/en/mods                                        (crate list, dust shop prices, pity numbers)
  https://wikily.gg/once-human/items/37169033/                          (Mod Selection Crate text)

Everything here is an estimate. The odds of each level inside a crate's range are not published, so every level in
the range is treated as equally likely, which is probably optimistic for the top levels.
"""
from __future__ import annotations

import forge

SRC_HUB = "https://www.oncehub.de/en/mods"
SRC_SEL = "https://wikily.gg/once-human/items/37169033/"
SRC_DEV = "https://www.oncehuman.game/news/devBlog/20251212/40781_1276354.html"
SRC_RATING = "https://www.oncehuman.game/news/update/20260709/40780_1307147.html"

ARMOR = ["helmet", "top", "gloves", "bottoms", "shoes"]
ALL_SLOTS = ["weapon", "mask"] + ARMOR
GROUPS = {
    "standard": "Violent, Precision, Survival, Deviant Energy, General",
    "keyword": "Keyword suffixes (Burn, Frost Vortex, Power Surge…)",
    "resonance": "Resonance",
    "resistance": "Resistance (Battle)",
    "vision": "Vision suffixes (Lunar, Crescent, Downstar, Aero, Mirror, Wild, Phantasmal)",
}
KEYWORDS = {"burn", "frost vortex", "shrapnel", "bounce", "unstable bomber", "the bull's eye", "power surge",
            "fortress warfare", "fast gunner"}
VISION = ("lunar", "crescent", "downstar", "aero", "mirror", "wild", "phantasmal")


def group_of(variant: str) -> str:
    v = (variant or "").lower()
    if v in KEYWORDS or v == "melee default":
        return "keyword"
    if v.startswith("resonan"):
        return "resonance"
    if v.startswith("battle"):
        return "resistance"
    if v.startswith(VISION):
        return "vision"
    return "standard"


def suffix_family(variant: str) -> str:
    """'Lunar Deviant Energy' -> 'Lunar'. Used for crates that roll one vision suffix."""
    v = variant or ""
    for f in VISION:
        if v.lower().startswith(f):
            return f.title()
    return v


# mode: "select" = you pick the mod when you open it; "random" = the game picks.
# choose: what you decide before it rolls ("slot", "group", "family") for random crates with a sub-choice.
CRATES = [
    {"id": "sel_6000", "name": "Mod Selection Crate", "mode": "select", "slots": ALL_SLOTS,
     "groups": ["standard", "keyword", "resonance"], "lo": 9, "hi": 17, "menu": "dust_box",
     "armor_variants": ["Violent", "Precision", "Survival", "Deviant Energy"],
     "source": "Mod Dust shop, 6,000 dust, 10 per week. Also from collection progress.",
     "text": "Opens into two lists: first a box (Helmet, Upper Body, Gloves, Lower Body, Shoes, or a Non-Keyword / Keyword / "
             "Resonance suffix box for weapon and mask mods), then a suffix. Armor boxes offer Violent, Precise, Survival or "
             "Deviant Energy only (no General). Level rolls 9–17.", "src": SRC_SEL,
     "words": "selection select 6000 6k dust shop any slot pick choose 9-17"},
    {"id": "sel_17", "name": "Lv 17 Mod Selection Crate", "mode": "select", "slots": ALL_SLOTS,
     "groups": ["standard", "keyword", "resonance", "resistance", "vision"], "lo": 17, "hi": 17,
     "source": "Weekly Lv 17 pity, rare Master/Nightmare drop, scenario rating, collection progress.",
     "text": "Pick a mod at a fixed level 17. What you can pick depends on the crate's slot — choose the slot below.",
     "src": SRC_HUB, "choose_slot_filter": True,
     "words": "legendary lv17 17 level 17 pity guaranteed weekly selection select fixed"},
    {"id": "armor_17", "name": "Armor Mod Selection Crate – Legendary", "mode": "select", "slots": ARMOR,
     "groups": ["standard"], "lo": 17, "hi": 17, "source": "Rewards and events.",
     "text": "Pick 1 armor mod (Violent, Precise, Deviant Energy, Survival or General) at level 17.",
     "src": "https://wikily.gg/once-human/items/37169007/", "words": "armor legendary selection 17 select"},
    {"id": "island_17", "name": "Island Mod Selection Crate – Legendary", "mode": "select", "slots": ["gloves", "bottoms"],
     "groups": ["standard", "keyword", "resonance", "resistance", "vision"], "mods": ["Precision Load", "Turret Enhancement"],
     "lo": 17, "hi": 17,
     "source": "Isles of Abyss: the Sunken Lord, or spend Heart of the Ocean at the Sunken Lord / Calamity Tower reward stage.",
     "text": "Select 1 Island mod (Precision Load for Bottoms or Turret Enhancement for Gloves). Level fixed at 17. "
             "Which suffixes the crate offers isn't published, so every suffix those two mods have is shown.",
     "src": "https://www.oncehuman.game/banner/20261021/41906_1317280.html",
     "words": "island isles abyss legendary 17 selection select sunken lord calamity tower heart of the ocean precision load turret enhancement"},
    {"id": "nonkw_sel", "name": "Non-Keyword Suffix Mod Selection Crate", "mode": "select", "slots": ["weapon", "mask"],
     "groups": ["standard"], "lo": 9, "hi": 17, "source": "Rewards, Stellar Planula and Miss Memory shops (Vault II 8–17).",
     "text": "Pick 1 weapon or mask mod with a Violent, Precise, Deviant Energy, Survival or General suffix. Level 9–17.",
     "src": "https://wikily.gg/once-human/items/37169030/", "words": "non keyword non-keyword nonkeyword suffix selection weapon mask"},
    {"id": "kw_sel", "name": "Keyword Suffix Mod Selection Crate", "mode": "select", "slots": ["weapon", "mask"],
     "groups": ["keyword"], "lo": 9, "hi": 17, "source": "Rewards and events.",
     "text": "Pick 1 weapon or mask mod with a keyword suffix (Burn, Power Surge…). Level 9–17.",
     "src": "https://wikily.gg/once-human/items/37168561/", "words": "keyword suffix selection weapon mask burn surge frost"},
    {"id": "aero_sel", "name": "Downstar / Aero Selection Crate", "mode": "select", "slots": ALL_SLOTS,
     "groups": ["vision"], "families": ["Downstar", "Aero"], "lo": 9, "hi": 17,
     "source": "Visional shop, 1 Abyssal Essence, 100 per month (while the shop is open). Aerial Hunt, Gravity Integrator.",
     "text": "Pick a Downstar or Aero mod. Level 9–17.", "src": SRC_HUB,
     "words": "aero downstar aerial vision visional abyssal essence gravity selection"},
    {"id": "slot_pick", "name": "Selectable crate for one slot", "mode": "select", "slots": ALL_SLOTS,
     "groups": ["standard", "keyword", "resonance", "resistance", "vision"], "lo": 13, "hi": 13, "choose_slot_filter": True,
     "level_input": True, "source": "Events and rewards (for example 'Lv. 13 Gloves Selectable Mod Crate').",
     "text": "Pick 1 mod for a single slot at a fixed level. Set the slot and level below.",
     "src": "https://wikily.gg/once-human/items/37181181/", "words": "selectable gloves helmet shoes top pants slot select lv"},
    {"id": "slot_5000", "name": "Slot crate 9–17 (5,000 dust)", "mode": "random", "choose": "slot", "slots": ALL_SLOTS,
     "groups": ["standard", "keyword", "resonance", "resistance"], "lo": 9, "hi": 17,
     "source": "Mod Dust shop, 5,000 dust, 30 per week.", "text": "Choose a slot, get a random mod for it. Level 9–17.",
     "src": SRC_HUB, "words": "slot crate random 5000 5k dust 9-17"},
    {"id": "slot_800", "name": "Slot crate 8–17 (800 dust)", "mode": "random", "choose": "slot", "slots": ALL_SLOTS,
     "groups": ["standard", "keyword", "resonance", "resistance"], "lo": 8, "hi": 17,
     "source": "Mod Dust shop, 800 dust, 50 per week.", "text": "Choose a slot, get a random mod for it. Level 8–17.",
     "src": SRC_HUB, "words": "slot crate random 800 dust 8-17"},
    {"id": "slot_200", "name": "Slot crate 6–17 (200 dust)", "mode": "random", "choose": "slot", "slots": ALL_SLOTS,
     "groups": ["standard", "keyword", "resonance", "resistance"], "lo": 6, "hi": 17,
     "source": "Mod Dust shop, 200 dust, 100 per week.", "text": "Choose a slot, get a random mod for it. Level 6–17.",
     "src": SRC_HUB, "words": "slot crate random 200 dust 6-17 cheap"},
    {"id": "group_5000", "name": "Category crate 9–17 (5,000 dust)", "mode": "random", "choose": "group", "slots": ALL_SLOTS,
     "groups": ["keyword", "resonance", "resistance", "standard"], "lo": 9, "hi": 17,
     "source": "Mod Dust shop, 5,000 dust, 30 per week.", "text": "Choose Keyword, Resonance, Resistance or Non-Keyword; get a random mod from it. Level 9–17.",
     "src": SRC_HUB, "words": "keyword resonance resistance non-keyword category crate random 5000 dust"},
    {"id": "group_800", "name": "Category crate 8–17 (800 dust)", "mode": "random", "choose": "group", "slots": ALL_SLOTS,
     "groups": ["keyword", "resonance", "resistance", "standard"], "lo": 8, "hi": 17,
     "source": "Mod Dust shop, 800 dust, 50 per week.", "text": "Choose Keyword, Resonance, Resistance or Non-Keyword; get a random mod from it. Level 8–17.",
     "src": SRC_HUB, "words": "keyword resonance resistance category crate random 800 dust"},
    {"id": "vision_crate", "name": "Mirror / Wild / Phantasmal / Lunar / Crescent crate", "mode": "random", "choose": "family",
     "slots": ALL_SLOTS, "groups": ["vision"], "families": ["Mirror", "Wild", "Phantasmal", "Lunar", "Crescent"], "lo": 8, "hi": 17,
     "source": "Visional shop, 300 Gravity Crystal, 50 per week (while open). Lunar/Crescent only during Lunar Revelry.",
     "text": "Random mod with the chosen Vision suffix. Level 8–17.", "src": SRC_HUB,
     "words": "mirror wild phantasmal lunar crescent vision visional gravity crystal crate"},
    {"id": "silo_nm", "name": "Silo / dungeon crate (Nightmare)", "mode": "random", "choose": "slot", "slots": ALL_SLOTS,
     "groups": ["standard"], "lo": 9, "hi": 17, "source": "Nightmare Silos and dungeons. First clear: Lv 12–17.",
     "text": "Random mod for the Silo's slot. Level 9–17 (12–17 on the weekly first clear).", "src": SRC_HUB,
     "words": "silo dungeon nightmare boss kill drop first clear crate random"},
    {"id": "rand_1417", "name": "Random Mod Crate Lv 14–17", "mode": "random", "slots": ALL_SLOTS,
     "groups": ["standard", "keyword", "resonance", "resistance"], "lo": 14, "hi": 17,
     "source": "Collection progress (Lv 260), compensation chest.", "text": "Random mod from any slot. Level 14–17.",
     "src": SRC_RATING, "words": "random 14-17 compensation collection crate"},
    {"id": "rand_17_armor", "name": "Random Lv 17 Armor Mod Crate", "mode": "random", "slots": ARMOR,
     "groups": ["standard", "resonance", "resistance", "vision"], "lo": 17, "hi": 17,
     "source": "Scenario Honor rating, once every 30 days.", "text": "Random armor mod at level 17.", "src": SRC_RATING,
     "words": "random armor 17 scenario rating honor monthly"},
]
CRATE_BY_ID = {c["id"]: c for c in CRATES}

FACTS = [
    {"t": "Higher copy replaces lower", "d": "A new copy of the same mod and suffix only helps if its level is higher. Lower or equal copies turn into Mod Dust.", "src": SRC_DEV},
    {"t": "Shiny at level 17", "d": "When you already own a mod at Lv 17, each new Lv 17 copy has a 30% chance to make it Shiny, and the 6th try is guaranteed. Shiny raises the main stat a little (not counted in DPS).", "src": SRC_HUB},
    {"t": "Weekly Lv 17 pity", "d": "Eligible Pro/Nightmare clears count up. About 1% around hit 80, guaranteed by hit 140, one per week (banks up to 5). The activity that triggers it decides the slot, so finish the pity on the Silo for the slot you want. Bought crates don't count.", "src": SRC_HUB},
    {"t": "The ~1,000 counter", "d": "Many sources also have a hidden counter that gives a Lv 17 crate after roughly 1,000 eligible rolls. It's not a fixed guarantee.", "src": SRC_HUB},
    {"t": "Collection progress", "d": "Summed levels of every version of a slot's mods unlock one-time selection crates at levels 10, 13, 15 and 17, then a Shiny crate. Owning more different mods counts.", "src": SRC_RATING},
    {"t": "Monthly scenario rating", "d": "Every 30 days: a Lv 17 crate and a random armor Shiny crate at the scenario's rating (for example Manibus 350 / 500).", "src": SRC_RATING},
    {"t": "Best use of Mod Dust", "d": "The 6,000-dust Mod Selection Crate (10 per week) is the only dust crate that lets you choose the mod. Spend dust there first.", "src": SRC_HUB},
]


def catalog() -> dict:
    return {"crates": [{k: v for k, v in c.items() if k != "words"} | {"words": c["words"]} for c in CRATES],
            "groups": GROUPS, "facts": FACTS, "slots": ALL_SLOTS}


def candidates(crate: dict, slot: str | None = None, group: str | None = None, family: str | None = None) -> list[tuple]:
    gd = forge.gamedata()
    fams = [f.lower() for f in crate.get("families") or []]
    only = {n.lower() for n in crate.get("mods") or []}
    out = []
    for gm in gd["mods"].values():
        if only and gm["name"].lower() not in only:
            continue
        s = gm.get("slot_key")
        if s not in crate["slots"] or (slot and s != slot):
            continue
        for v in (gm.get("variant_substats") or {"General": []}):
            if s in ARMOR and crate.get("armor_variants") and v not in crate["armor_variants"]:
                continue
            g = group_of(v)
            if g not in crate["groups"] or (group and g != group):
                continue
            if fams and not v.lower().startswith(tuple(fams)):
                continue
            if family and not v.lower().startswith(family.lower()):
                continue
            out.append((gm["name"], v, s))
    return out


class _Lens:
    """One build to measure gains against (your best build now, or your top upgrade)."""

    @classmethod
    def target(cls, profile, build, pool, label, rank):
        """A top build from the ranking, filled with the best mods YOU own for it (your levels).
        Gains then show which crate pick moves you toward that build."""
        gd = forge.gamedata()
        w = gd["weapons"][build["weapon"]["name"]]
        ws = {"name": w["name"], "stars": 6, "tier": 5, "calibration": build["weapon"].get("calibration")}
        sets = dict(build.get("sets") or {})
        scn = profile.get("scenario") or "boss"
        psi, _ = forge.estimate_psi(profile, sets)
        ex = forge.owned_extras(profile, w, scn)
        chosen = forge.best_mods_for(w, ws, pool, sets, psi, scn, passes=2, extras=ex)
        summ = {"weapon": dict(build["weapon"], stars=6), "sets": sets,
                "mods": {sl: m for sl, m in (chosen or {}).items() if m}}
        lens = cls(profile, summ, pool, label)
        lens.rank = rank
        lens.lineup = {sl: (m["name"], m.get("variant")) for sl, m in (build.get("mods") or {}).items() if m}
        return lens

    def __init__(self, profile, summary, pool, label):
        gd = forge.gamedata()
        self.label = label
        self.w = gd["weapons"][summary["weapon"]["name"]]
        self.ws = {"name": self.w["name"], "stars": summary["weapon"].get("stars") or 1, "tier": 5,
                   "calibration": summary["weapon"].get("calibration")}
        self.sets = dict(summary.get("sets") or {})
        self.scn = profile.get("scenario") or "boss"
        self.psi, _ = forge.estimate_psi(profile, self.sets)
        self.ex = forge.owned_extras(profile, self.w, self.scn)
        self.mods = {}
        for s, m in (summary.get("mods") or {}).items():
            if m:
                pm = next((x for x in pool if x["name"].lower() == m["name"].lower() and x["variant"].lower() == m["variant"].lower()), None)
                self.mods[s] = pm or {"name": m["name"], "variant": m["variant"], "slot": s, "level": m.get("level") or 10,
                                      "tiers": forge.tiers_from_level(m.get("level") or 10)}
        self.base = self.dps(self.mods)
        self.weapon = self.w["name"]

    def dps(self, mods):
        return forge.evaluate(self.w, self.ws, list(mods.values()), self.sets, self.psi, self.scn, extras=self.ex)["dps"]

    def gain(self, name, variant, slot, level):
        trial = dict(self.mods)
        trial[slot] = {"name": name, "variant": variant, "slot": slot, "level": level, "tiers": forge.tiers_from_level(level)}
        return max(0.0, self.dps(trial) / (self.base or 1) - 1)


def _score(lens, owned, cands, lo, hi):
    rows = []
    for name, v, s in cands:
        have = owned.get((name.lower(), v.lower()), 0)
        top = lens.gain(name, v, s, hi) if hi > have else 0.0
        if top <= 0.0005:
            rows.append({"name": name, "variant": v, "slot": s, "have": have, "exp": 0.0, "top": 0.0, "p": 0.0})
            continue
        gains = [lens.gain(name, v, s, L) if L > have else 0.0 for L in range(lo, hi + 1)]
        exp = sum(gains) / len(gains)
        p = sum(1 for g in gains if g > 0.002) / len(gains)
        rows.append({"name": name, "variant": v, "slot": s, "have": have, "exp": exp, "top": top, "p": p})
    rows.sort(key=lambda r: (r["exp"], r["top"]), reverse=True)
    return rows


def advise(crate_id: str, profile: dict | None = None, slot: str | None = None, level: int | None = None,
           count: int = 1, aim: str | None = None) -> dict:
    """aim: None/'mine' = your best build now; 'rank:N' = build #N of the Top 10 ranking (theory)."""
    profile = profile or forge.load_profile()
    crate = CRATE_BY_ID.get(crate_id)
    if not crate:
        raise ValueError("Unknown crate")
    lo, hi = crate["lo"], crate["hi"]
    if crate.get("level_input") and level:
        lo = hi = max(1, min(forge.MAX_MOD_LEVEL, int(level)))
    res = forge.optimize(profile)
    best = res.get("best")
    if not best:
        return {"error": "Add a weapon you own first, so there's a build to improve."}
    pool = forge.owned_mods(profile)
    owned = {(m["name"].lower(), m["variant"].lower()): m["level"] for m in pool}
    lenses = [_Lens(profile, best, pool, f"your best build ({best['weapon']['name']})")]
    nxt = next((u for u in res.get("upgrades") or [] if u.get("build") and u["kind"] in ("weapon", "combo")
                and u["build"]["weapon"]["name"] != best["weapon"]["name"]), None)
    if nxt:
        lenses.append(_Lens(profile, nxt["build"], pool, f"your top upgrade ({nxt['build']['weapon']['name']})"))
    aim_info = None
    if aim and aim.startswith("rank:"):
        import forge_theory
        th = forge_theory.theory(profile.get("scenario") or "boss", bool((profile.get("extras") or {}).get("marked")))
        n = max(1, min(len(th["builds"]), int(aim.split(":", 1)[1] or 1)))
        tb = th["builds"][n - 1]
        tl = _Lens.target(profile, tb, pool, f"build #{n} in the game ({tb['weapon']['name']})", n)
        own_w = any(w.get("name") == tb["weapon"]["name"] for w in forge.owned_weapons(profile)) \
            if hasattr(forge, "owned_weapons") else None
        aim_info = {"rank": n, "weapon": tb["weapon"]["name"], "dps": tb["dps"], "own_weapon": own_w,
                    "lineup": [{"slot": sl, "name": nm, "variant": v, "have": owned.get((nm.lower(), (v or "").lower()), 0)}
                               for sl, (nm, v) in tl.lineup.items()]}
        lenses = [tl] + lenses[:1]
    use_slot = slot if (crate.get("choose_slot_filter") or crate.get("choose") == "slot") else None

    out = {"crate": {k: v for k, v in crate.items() if k != "words"}, "levels": [lo, hi], "base_dps": round(lenses[0].base),
           "lenses": [l.label for l in lenses], "count": count, "aim": aim_info}
    if crate["mode"] == "select":
        cands = candidates(crate, slot=use_slot)
        rows = _score(lenses[0], owned, cands, lo, hi)
        picks = [r for r in rows if r["exp"] > 0.001][:8]
        alt = [] if aim_info else (_score(lenses[1], owned, cands, lo, hi)[:3] if len(lenses) > 1 else [])
        if aim_info:
            # the exact mods build #N runs come first when this crate can give them and you don't have them maxed
            want = {(x["name"].lower(), (x["variant"] or "").lower()) for x in aim_info["lineup"]}
            exact = [r for r in rows if (r["name"].lower(), r["variant"].lower()) in want and r["have"] < hi]
            gain_exact = [r for r in exact if r["exp"] > 0.001]
            # a build mod you don't own at all is still worth taking (it's a piece you're missing), even at +0% today
            missing_exact = [r for r in exact if r["exp"] <= 0.001 and not r["have"]]
            # best gain on that build first (a different variant can beat the ranking's pick at your levels);
            # the ranking's own mods keep an "in build #N" badge
            picks = sorted(gain_exact + [r for r in picks if r not in gain_exact],
                           key=lambda r: (r["exp"], r["top"]), reverse=True) + missing_exact
            picks = picks[:8]
        out["picks"] = [_pub(r, lenses[0], crate) | ({"in_target": (r["name"].lower(), r["variant"].lower()) in want} if aim_info else {})
                        for r in picks]
        out["future"] = [_pub(r, lenses[1], crate) for r in alt if r["exp"] > 0.001]
        if not picks:
            missing = [c for c in cands if (c[0].lower(), c[1].lower()) not in owned]
            out["fallback"] = _fallback(missing, lenses)
            out["suggest_aim"] = not aim_info
    else:
        options = []
        choose = crate.get("choose")
        keys = (crate["slots"] if choose == "slot" else crate["groups"] if choose == "group"
                else crate.get("families") or [] if choose == "family" else [None])
        for k in keys:
            cands = candidates(crate, slot=k if choose == "slot" else None, group=k if choose == "group" else None,
                               family=k if choose == "family" else None)
            if not cands:
                continue
            rows = _score(lenses[0], owned, cands, lo, hi)
            n = len(rows)
            exp = sum(r["exp"] for r in rows) / n
            hit = sum(r["p"] for r in rows) / n
            good = [r for r in rows if r["exp"] > 0.001][:3]
            options.append({"key": k, "label": (GROUPS.get(k, k) if choose == "group" else (k or "Any")).split(" (")[0],
                            "exp_pct": round(100 * exp, 2), "hit_pct": round(100 * hit, 1), "pool": n,
                            "best": [_pub(r, lenses[0]) for r in good]})
        options.sort(key=lambda o: o["exp_pct"], reverse=True)
        out["options"] = options
        if not options or options[0]["exp_pct"] < 0.05:
            out["fallback"] = _fallback([], lenses, random=True)
            out["suggest_aim"] = not aim_info
    if aim_info:
        out["notes_aim"] = (f"Aiming at build #{aim_info['rank']} ({aim_info['weapon']}): gains are measured on that weapon (6 stars, as in the ranking) "
                            "with the best mods you own for it. Its exact mods are listed first when this crate can give them.")
    out["notes"] = [
        "Level odds inside a crate's range aren't published, so every level is treated as equally likely (likely optimistic for 15–17).",
        "Gains are measured by swapping the new mod into your current best build. Mods the model can't count (Shiny bonus, some Vision conditions) aren't valued.",
    ]
    return out


GAME_BOX = {"helmet": ("Helmet Mod Selection Box", "Helmet"), "top": ("Upper Body Mod Selection Box", "Upper Body"),
            "gloves": ("Gloves Mod Selection Box", "Gloves"), "bottoms": ("Lower Body Module Selection Box", "Lower Body"),
            "shoes": ("Shoes Mod Selection Crate", "Shoes")}
GAME_SUFFIX = {"Precision": "Precise"}
SUFFIX_BOX = {"standard": "Non-Keyword Suffix Mod Selection Crate", "keyword": "Keyword Suffix Mod Selection Crate",
              "resonance": "Resonance Suffix Mod Selection Crate"}


def menu_path(crate: dict, name: str, variant: str, slot: str) -> dict | None:
    """The clicks in the game's crate menu, using the game's own names (from in-game screenshots)."""
    if crate.get("menu") != "dust_box":
        return None
    if slot in GAME_BOX:
        box, pre = GAME_BOX[slot]
        return {"steps": [box, f"{pre} \u2013 {GAME_SUFFIX.get(variant, variant)}", name], "sure": True}
    box = SUFFIX_BOX.get(group_of(variant))
    if not box:
        return None
    return {"steps": [box, f"the {'Weapon' if slot == 'weapon' else 'Mask'} {GAME_SUFFIX.get(variant, variant)} option", name],
            "sure": False}


def _pub(r, lens, crate=None):
    return {"menu": menu_path(crate or {}, r["name"], r["variant"], r["slot"]),"name": r["name"], "variant": r["variant"], "slot": r["slot"], "have": r["have"],
            "exp_pct": round(100 * r["exp"], 2), "top_pct": round(100 * r["top"], 2), "hit_pct": round(100 * r["p"], 1),
            "for": lens.weapon}


def _fallback(missing, lenses, random=False):
    if random:
        return {"text": "None of the choices is likely to raise your current build. Save your dust for the 6,000-dust Mod Selection Crate, where you pick the mod.",
                "mods": []}
    return {"text": "Nothing here beats what your build already uses. Least-bad use: take a mod you don't own yet. It raises collection progress "
                    "(one-time selection crates at levels 10, 13, 15 and 17) and may matter after a future patch or a weapon change.",
            "mods": [{"name": n, "variant": v, "slot": s} for n, v, s in missing[:6]]}


def dust_plan(dust: int, bought_this_week: int = 0, profile: dict | None = None) -> dict:
    """How to spend a Mod Dust balance: selection crates first, then the best slot crate."""
    dust = max(0, int(dust or 0))
    sel = min(max(0, 10 - int(bought_this_week or 0)), dust // 6000)
    left = dust - sel * 6000
    plan = {"selection": sel, "left": left}
    if sel:
        plan["selection_advice"] = advise("sel_6000", profile)
    if left >= 5000:
        a = advise("slot_5000", profile)
        top = (a.get("options") or [{}])[0]
        plan["leftover"] = {"crate": "Slot crate 9–17 (5,000 dust)", "n": min(30, left // 5000), "slot": top.get("key"),
                            "exp_pct": top.get("exp_pct")}
    return plan
