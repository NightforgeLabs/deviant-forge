"""Cradle overrides by map (scenario).

Facts (with sources):
- Isles of Abyss has no Cradle (official Version 3.1.1 notes).
- "standard" catalog = the official Cradle override table for servers opened January 16, 2025
  (5 rows x 5 overrides). It is the newest official list found; later seasons may have changed values.
- "winter" catalog = Game8's Way of Winter list (updated Oct 22, 2024). Two overrides there have
  copy-paste errors in the source, so they are listed but not counted.

Assumptions (labeled in the app):
- One override per row (5 rows). The sources do not state the rule.
- "DMG +X%" with a weapon class is counted as a general DMG bonus (adds to Weapon DMG and Status DMG).
- Uptimes are estimates for sustained fire; stacking buffs are counted at about 90% of max stacks.
- Bonus damage against Super Anomalies, survival and utility effects are not counted.
"""
from __future__ import annotations

OFFICIAL_ABYSS = "https://www.oncehuman.game/banner/20261021/41906_1317280.html"
OFFICIAL_TABLE = "https://www.oncehuman.game/news/update/20250110/40780_1205980.html"
GAME8_WINTER = "https://game8.co/games/Once-Human/archives/481150"
GAME8_STANDARD = "https://game8.co/games/Once-Human/archives/468460"

MAPS = {
    "isles_of_abyss": {"label": "Isles of Abyss", "cradle": False, "catalog": None, "verified": True,
                       "source": OFFICIAL_ABYSS, "note": "No Cradle in this scenario (official 3.1.1 notes)."},
    "manibus": {"label": "Manibus (standard PvE)", "cradle": True, "catalog": "standard", "verified": True,
                "source": OFFICIAL_TABLE, "note": "Official override table from January 2025; values may have changed since."},
    "way_of_winter": {"label": "Way of Winter", "cradle": True, "catalog": "winter", "verified": False,
                      "source": GAME8_WINTER, "note": "Community list (Game8, October 2024), not official."},
    "other_cradle": {"label": "Other scenario with a Cradle", "cradle": True, "catalog": "standard", "verified": False,
                     "source": OFFICIAL_TABLE, "note": "Uses the standard list. Check the values against your in-game Cradle screen."},
    "other_none": {"label": "Other scenario without a Cradle", "cradle": False, "catalog": None, "verified": False,
                   "source": None, "note": "No Cradle counted."},
}

# Weapon groups the Cradle text uses.
def weapon_group(wtype: str | None) -> str:
    t = (wtype or "").lower()
    if "flamethrower" in t or "rocket" in t or t == "mgl" or "grenade" in t:
        return "heavy"
    if "crossbow" in t:
        return "crossbow"
    if "bow" in t:
        return "bow"
    if "shotgun" in t:
        return "shotgun"
    if "submachine" in t or "smg" in t:
        return "smg"
    if "machine gun" in t or "lmg" in t:
        return "lmg"
    if "pistol" in t:
        return "pistol"
    if "sniper" in t:
        return "sniper"
    if "melee" in t:
        return "melee"
    return "rifle"


def _o(name, row, text, stats=None, up=1.0, up_mobs=None, groups=None, kw=None, needs=None, approx=None,
       unmodeled=None, mobs_zero=False, tip=None):
    return {"tip": tip, "name": name, "row": row, "text": text, "stats": stats or {}, "uptime": up,
            "uptime_mobs": up if up_mobs is None else up_mobs, "groups": groups, "kw": kw, "needs": needs,
            "approx": approx, "unmodeled": unmodeled, "mobs_zero": mobs_zero}


PISTOL_LMG = ["pistol", "lmg", "melee"]
RIFLE_SG = ["rifle", "shotgun", "heavy"]
SNIPER_SMG = ["sniper", "smg", "crossbow"]
CONT = ["Burn", "Frost Vortex"]
INSTANT = ["Power Surge", "Unstable Bomber"]
BULLET = ["Bounce", "Shrapnel"]
BUFF_KW = ["Fortress Warfare", "Fast Gunner"]
EL = {"Power Surge": "Shock", "Burn": "Blaze", "Frost Vortex": "Frost", "Unstable Bomber": "Blast"}

CATALOGS = {
    "standard": {"label": "Standard Cradle (official table, Jan 2025)", "source": OFFICIAL_TABLE, "rows": 5, "overrides": [
        _o("Anti-Coherence", 1, "When using pistols, light machine guns, or melee weapons, DMG +15%, with an additional 100% DMG against Super Anomaly - Coherence.",
           {"dmg_boost": 15}, groups=PISTOL_LMG, approx="Super Anomaly bonus not counted"),
        _o("Anti-Void", 1, "When using rifles, shotguns, or heavy weapons, DMG +15%, with an additional 100% DMG against Super Anomaly - Void.",
           {"dmg_boost": 15}, groups=RIFLE_SG, approx="Super Anomaly bonus not counted"),
        _o("Anti-Phase", 1, "When using sniper rifles, SMGs, or crossbows, DMG +15%, with an additional 100% DMG against Super Anomaly - Phase.",
           {"dmg_boost": 15}, groups=SNIPER_SMG, approx="Super Anomaly bonus not counted"),
        _o("Resilience", 1, "When your Sanity is below 30%, DMG received from Deviants is reduced by 30%.", unmodeled="survival"),
        _o("Rapid Aid", 1, "Medicine usage cooldown -30%. When HP is below 40%, medicine usage speed +30% and medicine healing effect +15%.", unmodeled="healing"),
        _o("Tactical Combo", 2, "Weapon DMG +15% for 4s after switching weapons or reloading.", {"weapon_dmg": 15}, up=0.45,
           approx="up about 45% of the time (4s after each reload)"),
        _o("Status Enhancement", 2, "Status DMG +15% for 3s after hitting a weakspot.", {"status_dmg": 15}, up=0.85,
           approx="weakspot hits keep it up most of the time"),
        _o("Deviant Energy Defense", 2, "Summoning or handling Deviations grants a shield equal to 30% of max HP. While the shield is active, Weapon DMG Reduction and Status DMG Reduction +10%. Cooldown: 30s.", unmodeled="survival"),
        _o("Energy Surge", 2, "Every 8 seconds at night (9:00 PM-3:00 AM), Deviations recover 1 Deviant Power.", unmodeled="utility"),
        _o("Chaotic Thoughts", 2, "When you have a Whim due to low Sanity, DMG Reduction against Deviants +10%, and DMG against Deviants +10%.", unmodeled="needs low Sanity"),
        _o("Deadly Combo", 3, "After triggering bullet effects (Bounce and Shrapnel), bullet effect DMG +25% for 4s.",
           {"kw_dmg:@": 25}, up=0.95, kw=BULLET),
        _o("Elemental Sense", 3, "After dealing Elemental DMG, the corresponding Element's DMG +25% for 4s.",
           {"el:@": 25}, up=0.95, kw=list(EL), approx="counted for your keyword's element only"),
        _o("Steady Hand", 3, "When you have a buff (e.g. Fortress Warfare, Fast Gunner), Weapon DMG +10% and Weakspot DMG +25%.",
           {"weapon_dmg": 10, "weakspot_dmg": 25}, up=0.8, kw=BUFF_KW, approx="counted only with Fortress Warfare or Fast Gunner"),
        _o("Marked Strike", 3, "Weakspot DMG +20% against targets marked with The Bull's Eye.", {"weakspot_dmg": 20}, needs="marked"),
        _o("Robust", 3, "When you perform a Light Attack, Melee DMG +5%. When you perform a Heavy Attack, Melee DMG +10%. Each effect stacks up to 25% and lasts for 8s.", unmodeled="melee"),
        _o("Extreme Freezing", 4, "When dealing Frost Elemental DMG, Frost Vortex DMG +2.5% and inflict Deviants with 3% Slowdown for 8s, up to 10 stacks. Freezes targets when fully stacked, up to 1 time per target.",
           {"kw_dmg:Frost Vortex": 22.5}, kw=["Frost Vortex"], approx="10 stacks at about 90%", tip=2.5),
        _o("Blazing Detonation", 4, "When inflicting Burn on a unit that already has Burn, immediately deal one instance of Burn DMG (Cooldown: 3s) and gain Burn DMG +25% for 15s.",
           {"kw_dmg:Burn": 25}, up=0.95, kw=["Burn"], approx="extra Burn instance not counted"),
        _o("Invincible Strike", 4, "After dealing Weakspot DMG, Shrapnel DMG +2.5% and Shrapnel Crit DMG +3.5% for 6s, up to 10 stacks. When fully stacked, Shrapnel DMG loss due to distance -50%.",
           {"kw_dmg:Shrapnel": 22.5, "kw_crit_dmg:Shrapnel": 31.5}, up=0.9, kw=["Shrapnel"], approx="10 stacks at about 90%; distance part not counted", tip=2.5),
        _o("Bounce Rampage", 4, "After triggering a bounce, Bounce DMG +5% for 15s. Up to 5 stacks.", {"kw_dmg:Bounce": 22.5}, kw=["Bounce"],
           approx="5 stacks at about 90%", tip=5),
        _o("Explosives Bonus", 4, "After triggering Unstable Bomber, Unstable Bomber DMG +5% for 8s, up to 5 stacks.", {"kw_dmg:Unstable Bomber": 22.5},
           kw=["Unstable Bomber"], approx="5 stacks at about 90%", tip=5),
        _o("Heavy Strike", 5, "Fortress Warfare range +50%. After activating Fortress Warfare, Weapon DMG +25% for 8s. Effect is removed after switching weapons.",
           {"weapon_dmg": 25}, up=0.7, kw=["Fortress Warfare"], approx="up about 70% of the time"),
        _o("Transient Impact", 5, "Dealing Power Surge DMG grants Power Surge DMG +2.5% for 6s, up to 10 stacks.", {"kw_dmg:Power Surge": 22.5},
           kw=["Power Surge"], approx="10 stacks at about 90%", tip=2.5),
        _o("Bounty Hunter", 5, "Attack +2% upon initially marking a target and Weakspot DMG +5% upon renewing the mark for 8s, up to 5 stacks. Effect is removed after switching weapons.",
           {"attack": 2, "weakspot_dmg": 22.5}, kw=["The Bull's Eye"], approx="needs your own Bull's Eye gun; 5 stacks at about 90%"),
        _o("Fast Pursuit", 5, "Upon triggering Fast Gunner, gain one of the following effects at random: Attack +3%, Crit Rate +3%, or Crit DMG +8% for 12s. Up to 5 stacks. Effect is removed after switching weapons.",
           {"attack": 4.5, "crit_rate": 4.5, "crit_dmg": 12}, kw=["Fast Gunner"], approx="5 stacks split evenly across the three effects", tip=3),
        _o("Brawl Boost", 5, "After dealing Melee DMG, gain DMG Reduction +5% and Roll Speed +5% for 6s, up to 5 stacks. Effect ends when you switch weapons.", unmodeled="melee/survival"),
    ]},
    "winter": {"label": "Way of Winter Cradle (Game8, Oct 2024)", "source": GAME8_WINTER, "rows": 5, "overrides": [
        _o("Anti-Regen", 1, "When using pistols, light machine guns, or melee weapons, DMG + 15%, with an additional 100% DMG against Super Anomaly - Regen.",
           {"dmg_boost": 15}, groups=PISTOL_LMG, approx="Super Anomaly bonus not counted"),
        _o("Anti-Void", 1, "When using rifles, shotguns, or heavy weapons, DMG + 15%, with an additional 100% DMG against Super Anomaly - Void.",
           {"dmg_boost": 15}, groups=RIFLE_SG, approx="Super Anomaly bonus not counted"),
        _o("Anti-Phase", 1, "When using sniper rifles, SMGs, or crossbows, DMG + 15%, with an additional 100% DMG against Super Anomaly - Phase.",
           {"dmg_boost": 15}, groups=SNIPER_SMG, approx="Super Anomaly bonus not counted"),
        _o("Deviant Energy Defense", 1, "Summoning or handling Deviations grants a shield equal to 30% of max HP. While the shield is active, Weapon DMG Reduction and Status DMG Reduction +10%. Cooldown: 30s.", unmodeled="survival"),
        _o("Sky Operation", 1, "Jump and glide speed + 15%, and DMG Reduction + 10% while jumping and gliding.", unmodeled="movement"),
        _o("Tactical Combo", 2, "Weapon DMG +25% for 4s after switching weapons or reloading.", {"weapon_dmg": 25}, up=0.45,
           approx="up about 45% of the time (4s after each reload)"),
        _o("Status Enhancement", 2, "After hitting a weakspot, Status DMG +25% for 3s.", {"status_dmg": 25}, up=0.85,
           approx="weakspot hits keep it up most of the time"),
        _o("Deviation Master", 2, "While a Deviation is present, DMG against Great Ones (bosses) and elites +25%.", {"vs_enemies": 25},
           needs="deviation", mobs_zero=True, approx="bosses and elites only; needs a combat deviation out"),
        _o("Lone Walker", 2, "When fighting solo, medicine usage cooldown -30%; when HP is below 40%, medicine usage speed +30% and medicine's healing effect +15%.", unmodeled="healing"),
        _o("Side by Side", 2, "When fighting in the team, armor Durability loss speed -25%, and teammate rescue speed +35%.", unmodeled="team utility"),
        _o("Deadly Combo", 3, "After hitting a weakspot with bullet effects (Bounce and Shrapnel), bullet effect DMG +25% for 3s.",
           {"kw_dmg:@": 25}, up=0.8, kw=BULLET, approx="needs weakspot hits"),
        _o("Sustained Suppression", 3, "Continuous DMG +25% for 4s after Continuous DMG (Burn, Frost, Vortex).", {"kw_dmg:@": 25}, up=0.95, kw=CONT),
        _o("First Round Blast", 3, "After reloading, Instant DMG (Power Surge and Unstable Bomber) +25% for 4s.", {"kw_dmg:@": 25}, up=0.45, kw=INSTANT,
           approx="up about 45% of the time (4s after each reload)"),
        _o("Steady Hand", 3, "While in Fortress Warfare or Fast Gunner status, Weakspot DMG +40%, Weakspot DMG to the Bull's Eye +20%.",
           {"weakspot_dmg": 40}, up=0.8, kw=BUFF_KW, approx="Bull's Eye part not counted"),
        _o("Ammo Cascade", 3, "After performing a successful backstab/execution/impact, gain Melee DMG +30.0% and Movement Speed +10.0% for 10s.", unmodeled="melee"),
        _o("Frost Sense", 4, "Every time you summon Frost Vortex, Ice Crystal, or Ice Spike, Frost DMG+3% for 8s, stacking up to 12 times.",
           {"el:Frost": 25}, kw=["Frost Vortex"], approx="about 8 of 12 stacks; depends on how often vortexes spawn", tip=3),
        _o("Heat Agglutination", 4, "For every 1 stack of Burn triggered, Burn DMG +5% for 6s. Up to 6 stacks.", {"kw_dmg:Burn": 27}, kw=["Burn"],
           approx="6 stacks at about 90%", tip=5),
        _o("Tracking Bullet", 4, "Dealing Weakspot DMG grants +2.5% Shrapnel DMG, +3.5% Shrapnel Crit DMG for 6s, up to 10 stacks.",
           {"kw_dmg:Shrapnel": 22.5, "kw_crit_dmg:Shrapnel": 31.5}, up=0.9, kw=["Shrapnel"], approx="10 stacks at about 90%", tip=2.5),
        _o("Bounce Rampage", 4, "Effect text in the source is a copy error (it repeats Tracking Bullet).", unmodeled="real value unknown"),
        _o("Series Detonation", 4, "Effect text in the source is a copy error (it repeats Tracking Bullet).", unmodeled="real value unknown"),
        _o("Fortress Link", 5, "Fortress Warfare range +50% with an additional damage boost of 5%. After activating Fortress Warfare for 5s, Fortress Warfare will appear within 10 meters at a non-hostile target's location.",
           {"dmg_boost": 5}, up=0.8, kw=["Fortress Warfare"]),
        _o("Overload", 5, "Upon dealing Power Surge DMG, energy charges up to 10 stacks and each stack grants 2.5% Power Surge DMG. The boost lasts until the next reload.",
           {"kw_dmg:Power Surge": 15}, kw=["Power Surge"], approx="resets every reload; about 6 of 10 stacks on average", tip=2.5),
        _o("Bounty Hunter", 5, "Hitting a marked target grants +5% Weapon DMG for 8s, up to 6 stacks. Switching weapons removes half stacks.",
           {"weapon_dmg": 27}, needs="marked", approx="6 stacks at about 90%", tip=5),
        _o("Fast Pursuit", 5, "In Fast Gunner status, there is a chance to fire 1 extra bullet when firing (each stack adds 1%, up to a max of 20%).",
           {"fire_rate": 10}, kw=["Fast Gunner"], approx="extra bullets counted as about +10% fire rate"),
    ]},
}


def map_info(map_id: str | None) -> dict | None:
    return MAPS.get(map_id or "")


def overrides(map_id: str | None) -> list[dict]:
    m = map_info(map_id)
    if not m or not m["cradle"]:
        return []
    return CATALOGS[m["catalog"]]["overrides"]


def _find(map_id, name):
    for o in overrides(map_id):
        if o["name"].lower() == (name or "").lower():
            return o
    return None


def applies(o: dict, wtype: str | None, kw: str | None, cfg: dict, scenario: str) -> tuple[bool, str | None]:
    """Does this override add damage for this weapon/fight? (True, None) or (False, reason)."""
    if o.get("unmodeled"):
        return False, f"{o['unmodeled']} (not counted)"
    if o.get("groups") and weapon_group(wtype) not in o["groups"]:
        return False, "wrong weapon type for this override"
    if o.get("kw") and kw not in o["kw"]:
        return False, "only helps " + " / ".join(o["kw"])
    if o.get("needs") == "marked" and not (cfg.get("marked") or kw == "The Bull's Eye"):
        return False, "needs a Bull's Eye mark"
    if o.get("needs") == "deviation" and not cfg.get("deviation"):
        return False, "needs a combat deviation out"
    if o.get("mobs_zero") and (scenario or "").split("@")[0] == "mobs":
        return False, "bosses and elites only"
    return True, None


def override_stats(o: dict, kw: str | None, scenario: str, value: float | None = None) -> dict:
    """Counted stats (already times uptime). `value` replaces the main % if you typed your tooltip number."""
    mobs = (scenario or "").split("@")[0] == "mobs"
    up = o["uptime_mobs"] if mobs else o["uptime"]
    st = {}
    base = o.get("tip") or next(iter(o["stats"].values()), 0)
    factor = float(value) / base if (value is not None and base) else 1.0
    for k, v in o["stats"].items():
        if "@" in k:
            k = k.replace("@", EL.get(kw, kw) if k.startswith("el:") else (kw or ""))
        st[k] = round(v * factor * up, 3)
    return st


def picks_of(cfg: dict) -> list[dict]:
    """cfg['cradle'] may be a list of names, a list of {name, value} or 'auto'."""
    raw = cfg.get("cradle")
    if not isinstance(raw, list):
        return []
    out = []
    for p in raw:
        if isinstance(p, str):
            out.append({"name": p})
        elif isinstance(p, dict) and p.get("name"):
            out.append({"name": p["name"], "value": p.get("value")})
    return out


def sources(cfg: dict, wtype: str | None, kw: str | None, scenario: str) -> tuple[list, list[str]]:
    """Stat sources and notes for forge_extras.extra_sources()."""
    notes: list[str] = []
    map_id = cfg.get("map")
    m = map_info(map_id)
    if not m:
        return [], ["Cradle: pick your map in Class & settings to count Cradle overrides (not counted)."]
    if (scenario or "").split("@")[0] == "abyss":
        return [], ["Cradle: none in Abyss / Nightmare dungeon fights."]
    if not m["cradle"]:
        return [], [f"Cradle: {m['note']}"]
    picks = picks_of(cfg)
    if cfg.get("cradle") in (None, "auto") and not picks:
        picks = [{"name": n} for n in auto_pick(map_id, wtype, kw, cfg, scenario)]
        if picks:
            notes.append("Cradle: suggested overrides for this weapon (pick yours in Class & settings to count exactly what you run).")
    if cfg.get("cradle_auto") and picks:
        notes.append("Cradle: suggested overrides for this weapon: " + ", ".join(p["name"] for p in picks)
                     + " (pick yours in Class & settings to count exactly what you run).")
    out = []
    rows: dict = {}
    for p in picks:
        o = _find(map_id, p["name"])
        if not o:
            notes.append(f"Cradle: '{p['name']}' is not on the {m['label']} list (not counted)")
            continue
        rows.setdefault(o["row"], []).append(o["name"])
        ok, why = applies(o, wtype, kw, cfg, scenario)
        if not ok:
            notes.append(f"Cradle {o['name']}: {why}")
            continue
        out.append((f"{o['name']} (Cradle)", override_stats(o, kw, scenario, p.get("value"))))
        if o.get("approx"):
            notes.append(f"Cradle {o['name']}: estimate ({o['approx']})")
    for r, names in rows.items():
        if len(names) > 1:
            notes.append(f"Cradle row {r}: {', '.join(names)} share a row; the game may only allow one (all counted)")
    if not m["verified"]:
        notes.append(f"Cradle: {m['note']}")
    return out, notes


def skipped(cfg: dict) -> dict:
    """{override name: why it isn't counted} for the weapon in cfg (for the settings screen)."""
    out = {}
    w = {}
    try:
        import forge
        w = forge.gamedata()["weapons"].get(cfg.get("weapon") or "") or {}
    except Exception:
        pass
    for p in picks_of(cfg):
        o = _find(cfg.get("map"), p["name"])
        if o:
            ok, why = applies(o, w.get("type"), w.get("keyword"), cfg, "boss")
            if not ok:
                out[o["name"]] = why
    return out


def _heuristic(o, kw, scenario) -> float:
    st = override_stats(o, kw, scenario)
    w = {"dmg_boost": 1.0, "weapon_dmg": 0.9, "vs_enemies": 1.0, "attack": 1.0, "fire_rate": 0.9,
         "status_dmg": 0.5, "weakspot_dmg": 0.35, "crit_rate": 1.2, "crit_dmg": 0.4}
    return sum(v * (0.7 if k.startswith(("kw_dmg:", "el:")) else 0.25 if k.startswith("kw_crit") else w.get(k, 0.3))
               for k, v in st.items())


def auto_pick(map_id, wtype, kw, cfg, scenario, score=None) -> list[str]:
    """Best override per row. With `score(names) -> dps` it compares real DPS; without, a quick heuristic."""
    ovs = overrides(map_id)
    if not ovs:
        return []
    rows: dict = {}
    for o in ovs:
        if applies(o, wtype, kw, cfg, scenario)[0]:
            rows.setdefault(o["row"], []).append(o)
    chosen: dict = {}
    for r in sorted(rows):
        chosen[r] = max(rows[r], key=lambda o: _heuristic(o, kw, scenario))["name"]
    if score:
        for r in sorted(rows):
            if len(rows[r]) < 2:
                continue
            best_v, best_n = -1.0, chosen[r]
            for o in rows[r]:
                v = score([n if rr != r else o["name"] for rr, n in sorted(chosen.items())])
                if v > best_v:
                    best_v, best_n = v, o["name"]
            chosen[r] = best_n
    return [chosen[r] for r in sorted(chosen)]


def catalog() -> dict:
    return {
        "maps": {k: dict(v) for k, v in MAPS.items()},
        "catalogs": {k: {"label": c["label"], "source": c["source"], "rows": c["rows"],
                         "overrides": [{"name": o["name"], "row": o["row"], "text": o["text"],
                                        "counted": not o.get("unmodeled"), "why_not": o.get("unmodeled"),
                                        "approx": o.get("approx"), "kw": o.get("kw"), "groups": o.get("groups"),
                                        "per_stack": bool(o.get("tip")) and o["name"] != "Fast Pursuit", "main_value": o.get("tip") or next(iter(o["stats"].values()), None)}
                                       for o in c["overrides"]]}
                     for k, c in CATALOGS.items()},
        "assumptions": ["One override per row (5 rows); the sources don't state the rule.",
                        "Uptimes are estimates for sustained fire.",
                        "Super Anomaly bonuses, survival and utility effects are not counted."],
    }
