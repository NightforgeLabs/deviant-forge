"""Deviant Forge optimizer.

Answers two questions from the player's own collection:
  1. What is the best sustained-DPS build I can make right now?
  2. What is the next big jump (weapon, armor set, mods, stars), how much
     stronger is it, and what does it cost in Starchrom?

Data sources
  * gamedata/thgl_snapshot.json  - weapons, armor, sets and mods from
    oncehuman.th.gl, which publishes values read from the game files.
  * data/advisor.sqlite3         - the player's recorded mods (Field Guide
    levels + per-stat tiers), weapons and the forge profile.

All numbers are model estimates for a stated scenario. Effects the model
cannot parse are listed per build as "not counted".
"""
from __future__ import annotations

import itertools
import json
import os
import math
import re
import sqlite3
from functools import lru_cache
from pathlib import Path

import forge_effects as fe
import forge_accessories
import forge_extras as fx
import forge_live as fl

ROOT = Path(__file__).resolve().parent
SNAPSHOT = ROOT / "gamedata" / "thgl_snapshot.json"
CATALOG = ROOT / "catalog.json"
# OH_ADVISOR_DATA moves player data out of the app folder (the Windows launcher uses %LOCALAPPDATA%), same as server.py
DATA_DIR = Path(os.environ.get("OH_ADVISOR_DATA", ROOT / "data")).resolve()
DB = DATA_DIR / "advisor.sqlite3"

ARMOR_SLOTS = ["helmet", "mask", "top", "gloves", "bottoms", "shoes"]
MOD_SLOTS = ARMOR_SLOTS + ["weapon"]
SLOT_ALIASES = {
    "helmet": "helmet", "helmet_mod": "helmet", "hat": "helmet", "hood": "helmet",
    "mask": "mask", "mask_mod": "mask",
    "top": "top", "chest": "top", "chest_mod": "top", "tops": "top", "jacket": "top",
    "gloves": "gloves", "gloves_mod": "gloves",
    "bottoms": "bottoms", "pants": "bottoms", "pants_mod": "bottoms", "pants_mods": "bottoms",
    "shoes": "shoes", "boots": "shoes", "boots_mod": "shoes", "footwear": "shoes",
    "weapon": "weapon", "weapon_mod": "weapon", "weapons": "weapon", "all weapons": "weapon",
}

# Starchrom prices read from oncehuman.th.gl/blueprints (game-file values).
STARCHROM = {
    "weapon_legendary_unlock": 8000,
    "weapon_legendary_stars": {2: 3000, 3: 6000, 4: 9000, 5: 12000, 6: 15000},
    "armor_legendary_unlock": 2000,
    "armor_legendary_stars": {2: 750, 3: 1500, 4: 2250, 5: 3000, 6: 3750},
}

RELOAD_SECONDS = {  # approximate full reload time by weapon family
    "Pistol": 1.6, "Submachine Gun": 2.0, "Assault Rifle": 2.4, "Shotgun": 3.2, "Light Machine Gun": 4.6,
    "Sniper Rifle": 2.8, "Bolt-Action Sniper Rifle": 3.0, "Semi-Auto Sniper Rifle": 2.6, "Crossbow": 2.2,
    "Compound Bow": 1.0, "Bow": 1.0,
}
PELLETS = {"Shotgun": 6}
# Pellets per shot (Game8 weapon table https://game8.co/games/Once-Human/archives/Weapons,
# oncehumanwiki.com/weapons). ACS12 / DB12 / AA12 fire 5, double-barrels and pumps fire 6.
PELLETS_BY_PREFIX = {"ACS12": 5, "DB12": 5, "AA12": 5, "DBSG": 6, "S870": 6, "Old Huntsman": 6, "Dual Fury": 6}
# Share of a shotgun's pellets that land on a moving boss and the weakspot share of those (estimate).
SHOTGUN_PELLET_HIT = 0.75
SHOTGUN_WS_FACTOR = 0.6


SNIPER_TYPES = {"Sniper Rifle", "Bolt-Action Sniper Rifle", "Semi-Auto Sniper Rifle"}


def sniper_weakspot_rate(spray_rate: float, setting=None) -> float:
    """Share of sniper shots that land on a weakspot. Your setting (0-100) wins; otherwise twice the
    spray rate for this fight, capped at 90% (boss: 35% -> 70%)."""
    if setting not in (None, ""):
        return max(0.0, min(1.0, float(setting) / 100))
    return min(0.9, spray_rate * 2)


def reverb_model(weapon: dict, mag: float, ws_rate: float, acc: float, stats: dict) -> dict | None:
    """SN700 - Finale's [Reverb], worked out shot by shot over one magazine.

    Text: 40% chance to trigger Shrapnel on hit, always on a weakspot hit; Shrapnel no longer excludes hit
    parts. Each trigger adds a Reverb stack (max 4, cleared on reload); each stack = +1 Shrapnel hit part and
    +5% damage on the last bullet. With 3+ stacks, a last bullet that triggers Shrapnel triggers it again once
    per stack."""
    text = (weapon.get("effect_text") or "").lower()
    if "[reverb]" not in text:
        return None
    base = re.search(r"(\d+(?:\.\d+)?)% probability to trigger shrapnel", text)
    chance = pct(float(base.group(1))) if base else 0.4
    chance *= 1 + pct(stats.get("kw_chance:Shrapnel"))
    p_t = min(1.0, ws_rate + (1 - ws_rate) * chance) if "weakspot always triggers" in text else min(1.0, chance)
    m = re.search(r"maximum of (\d+) stacks", text)
    cap = int(m.group(1)) if m else 4
    extra = stats.get("_shrapnel_parts", 0)
    single = bool(stats.get("_shrapnel_single"))   # Gas-tight Helmet: max 1 Shrapnel part, overrides Reverb parts
    q = acc * p_t
    n = max(1, int(round(mag)))
    dist = [1.0] + [0.0] * cap
    part_hits = last_bonus = 0.0
    for k in range(n):
        last = k == n - 1
        for st, pr in enumerate(dist):
            part_hits += pr * q * (1 if single else 1 + st + extra)
            if last:
                last_bonus += pr * 0.05 * st
                if st >= 3:
                    part_hits += pr * q * st * (1 if single else 1 + st + extra)
        new = [0.0] * (cap + 1)
        for st, pr in enumerate(dist):
            new[min(cap, st + 1)] += pr * q
            new[st] += pr * (1 - q)
        dist = new
    return {"p_trigger": p_t, "parts_per_trigger": part_hits / (n * q) if q else 1.0,
            "last_bullet_bonus": last_bonus / n}


def pellets_of(weapon: dict) -> int:
    for pre, n in PELLETS_BY_PREFIX.items():
        if weapon.get("name", "").startswith(pre):
            return n
    return PELLETS.get(weapon.get("type") or "", 1)


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def pct(x) -> float:
    return float(x or 0) / 100.0


# ===================================================================== data
class ModTable(dict):
    """name.lower() -> mod. .get()/[]/in also accept other sites' names for the same mod; iteration does not."""
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.aliases: dict = {}

    def _k(self, key):
        return key if dict.__contains__(self, key) else self.aliases.get(key, key)

    def get(self, key, default=None):
        return dict.get(self, self._k(key), default)

    def __getitem__(self, key):
        return dict.__getitem__(self, self._k(key))

    def __contains__(self, key):
        return dict.__contains__(self, self._k(key))


# Set bonuses the text parser can't read. (set, pieces) -> (stats, why)
_BS_NOTE = ("assumes a normal 20°C zone: the 4pc shifts it 20°C, so the 3pc bonus is about 15% and is doubled to about 30%; "
            "hotter/colder zones give up to 40%")
SET_TEXT_OVERRIDES = {
    ("Blackstone Heat", "3"): ({}, "needs a zone above 30°C on its own; counted with the 4pc"),
    ("Blackstone Cold", "3"): ({}, "needs a zone below 10°C on its own; counted with the 4pc"),
    ("Blackstone Heat", "4"): ({"elemental_dmg": 30}, _BS_NOTE),
    ("Blackstone Cold", "4"): ({"elemental_dmg": 30}, _BS_NOTE),
}


SUPPLEMENT = Path(__file__).resolve().parent / "gamedata" / "supplement.json"


def _merge_supplement(data: dict) -> dict:
    """Add items the game has but th.gl doesn't list (gamedata/supplement.json). Never overrides th.gl."""
    try:
        sup = json.loads(SUPPLEMENT.read_text())
    except Exception:  # noqa: BLE001
        return data
    for kind in ("weapons", "armor", "mods"):
        have = {x["name"].lower() for x in data.get(kind) or []}
        for x in sup.get(kind) or []:
            if x["name"].lower() not in have:
                data.setdefault(kind, []).append(dict(x))
    data["aliases"] = sup.get("aliases") or {}
    return data


@lru_cache(maxsize=1)
def gamedata() -> dict:
    data = _merge_supplement(json.loads(fl.active_snapshot().read_text()))
    weapons = {}
    for w in data["weapons"]:
        if w.get("group") == "oh_group_melee_weapons" or not w.get("dmg"):
            continue
        w["keyword"] = detect_keyword(w)
        w["legendary"] = bool(w.get("effect_name")) and len(w.get("dmg_per_star") or {}) >= 5
        weapons[w["name"]] = w
    armor, sets = {}, {}
    for a in data["armor"]:
        a["slot_key"] = SLOT_ALIASES.get((a.get("slot") or "").lower())
        if not a["slot_key"]:
            continue
        armor[a["name"]] = a
        if len(a.get("set_effects") or {}) >= 2:
            sig = json.dumps(a["set_effects"], sort_keys=True)
            s = sets.setdefault(sig, {"pieces": {}, "effects": a["set_effects"], "names": []})
            s["pieces"][a["slot_key"]] = a["name"]
            s["names"].append(a["name"])
            if a.get("set_name"):
                s["set_name"] = a["set_name"]
    named = {}
    for sig, s in sets.items():
        name = s.get("set_name") or common_prefix(s["names"]) or s["names"][0].split(" ")[0]
        if name in named:   # two sets share a prefix (e.g. "Blackstone Hood - Heat"): never overwrite one with the other
            tail = {n.rsplit(" - ", 1)[-1] for n in s["names"] if " - " in n}
            name = f"{name} {tail.pop()}" if len(tail) == 1 else f"{name} ({s['names'][0]})"
        s["name"] = name
        named[name] = s
        for n in s["names"]:
            armor[n]["set"] = name
    sets = named
    mods = {}
    for m in data["mods"]:
        m["slot_key"] = SLOT_ALIASES.get((m.get("slot") or "").lower())
        mods[m["name"].lower()] = m
    mods = ModTable(mods)
    for old, new in ((data.get("aliases") or {}).get("mods") or {}).items():
        if new.lower() in mods and old.lower() not in mods:
            mods.aliases[old.lower()] = new.lower()   # other sites' names for the same mod (lookups only, never listed twice)
    return {"weapons": weapons, "armor": armor, "sets": sets, "mods": mods,
            "retrieved_at": data.get("retrieved_at"), "source": data.get("source")}


def common_prefix(names: list[str]) -> str:
    words = [n.split(" ") for n in names]
    out = []
    for parts in zip(*words):
        if len(set(parts)) == 1:
            out.append(parts[0])
        else:
            break
    return " ".join(out)


def set_key(a: dict) -> str:
    return a.get("set") or a["name"].split(" ")[0]


def detect_keyword(w: dict) -> str | None:
    b = (w.get("build") or "").strip()
    for k in fe.KEYWORDS:
        if b.lower() == k.lower() or b.lower() == k.lower().replace("the ", ""):
            return k
    text = (w.get("effect_text") or "").lower()
    for k in fe.KEYWORDS:
        if k.lower() in text:
            return k
    return b or None


@lru_cache(maxsize=None)
def _core_text(name: str) -> str:
    gm = gamedata()["mods"].get(name.lower()) or {}
    core = gm.get("core_effect_by_level") or {}
    if core:
        return core.get("5") or core.get(5) or list(core.values())[-1]
    return gm.get("summary") or ""


@lru_cache(maxsize=1)
def catalog_mod_names() -> dict:
    """catalog_id -> (mod name, variant) from the app's existing catalog."""
    out = {}
    try:
        cat = json.loads(CATALOG.read_text())
        for m in cat.get("mods", []):
            out[m["id"]] = (m.get("name"), m.get("variant"), m.get("slot"))
    except Exception:  # noqa: BLE001
        pass
    return out


def db(readonly: bool = True):
    if readonly:
        # as_uri() percent-encodes spaces/#/% and handles Windows drive letters (C:\Users\...)
        con = sqlite3.connect(f"{DB.resolve().as_uri()}?mode=ro", uri=True)
    else:
        con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def ensure_profile_table():
    with db(False) as con:
        con.execute("create table if not exists forge_profile (key text primary key, value text, updated text)")


DEFAULT_PROFILE = {
    "starchrom": None,
    "psi_intensity": None,     # from the character sheet; estimated from armor if missing
    "armor": {},               # slot -> {"name": "Shelterer Hat", "stars": 5, "tier": 5}  (what you WEAR)
    "armor_owned": {},         # piece name -> {"stars": n}  (every piece/blueprint you OWN, several per slot)
    "weapons": [],             # extra weapons the player owns: {"name":..., "stars":..., "tier":...}
    "scenario": "boss",
    "mods": [],                # mods added by hand here: {"name":..., "variant":..., "level":...}
    # deviation, deviation_level, food, drink, marked (Bull's Eye support). Key armor comes from "armor".
    "extras": {},
    # quick edits from the gear screen; they win over recorded data
    "mod_edits": {},           # "name|variant" -> {"level": n} or {"removed": true}
    "weapon_edits": {},        # weapon name -> {"stars": n, "magazine": id, "reload_s": s} or {"removed": true}
    "accessories_owned": [],   # magazine ids from forge_accessories.MAGAZINES you have unlocked
    "accessory_values": {},    # magazine id -> your tooltip numbers {"reload_speed": %, "magazine_flat": n}
    # fresh-start test: ignore everything recorded from the game; only what is typed here counts
    "fresh": False,
}


def _profile_saves_table(con):
    con.execute("create table if not exists forge_profile_saves (id integer primary key autoincrement, "
                "label text, saved text, value text)")


def start_fresh(starchrom=None) -> dict:
    """Put the current profile aside (kept in forge_profile_saves) and start an empty one.
    Nothing recorded from the game is deleted; fresh mode just ignores it until restore."""
    import datetime as dt
    ensure_profile_table()
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    cur = load_profile()
    with db(False) as con:
        _profile_saves_table(con)
        if not cur.get("fresh"):   # don't overwrite your real profile with a test one
            con.execute("insert into forge_profile_saves(label,saved,value) values(?,?,?)",
                        ("before fresh start", now, json.dumps(cur)))
        _slots_table(con)
        _seed_slots(con)
        _set_meta(con, "active", None)   # the slot you left keeps your profile; the test isn't in a slot yet
        con.execute("delete from forge_profile")
    blank = json.loads(json.dumps(DEFAULT_PROFILE))
    blank.update(fresh=True, starchrom=int(starchrom) if starchrom not in (None, "") else None)
    return save_profile(blank)


def profile_saves() -> list:
    try:
        with db() as con:
            _profile_saves_table(con)
            return [{"id": r["id"], "label": r["label"], "saved": r["saved"]}
                    for r in con.execute("select id,label,saved from forge_profile_saves order by id desc limit 10")]
    except sqlite3.OperationalError:
        return []


def restore_profile(save_id=None) -> dict:
    with db(False) as con:
        _profile_saves_table(con)
        row = (con.execute("select * from forge_profile_saves where id=?", (int(save_id),)).fetchone() if save_id
               else con.execute("select * from forge_profile_saves order by id desc limit 1").fetchone())
        if not row:
            raise ValueError("No saved profile to restore")
        con.execute("delete from forge_profile")
    data = json.loads(row["value"])
    data["fresh"] = False
    return save_profile(data)


def load_profile() -> dict:
    prof = json.loads(json.dumps(DEFAULT_PROFILE))
    try:
        with db() as con:
            for row in con.execute("select key, value from forge_profile"):
                prof[row["key"]] = json.loads(row["value"])
    except sqlite3.OperationalError:
        pass
    return prof


def save_profile(update: dict) -> dict:
    ensure_profile_table()
    allowed = set(DEFAULT_PROFILE)
    import datetime as dt
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    with db(False) as con:
        for k, v in update.items():
            if k in allowed:
                con.execute("insert into forge_profile(key,value,updated) values(?,?,?) "
                            "on conflict(key) do update set value=excluded.value, updated=excluded.updated",
                            (k, json.dumps(v), now))
    prof = load_profile()
    _sync_active_slot(prof)
    return prof


def _sync_active_slot(prof: dict) -> None:
    """The slot in use always holds the latest copy of the profile."""
    try:
        with db(False) as con:
            _slots_table(con)
            active = _meta(con, "active")
            if active:
                con.execute("update forge_profile_slots set value=?, saved=? where slot=?", (json.dumps(prof), _now(), int(active)))
    except sqlite3.OperationalError:
        pass


# ============================================================ named profile slots
# Three named slots. The profile you're using lives in forge_profile as before; a slot is a saved
# copy of it. Switching saves the profile you're leaving into its own slot (and into the backup list
# forge_profile_saves), so nothing is ever lost. Recorded game data (inventory, field guide) is
# shared; a slot with a fresh-start profile keeps ignoring it.
PROFILE_SLOTS = 3


def _slots_table(con):
    con.execute("create table if not exists forge_profile_slots (slot integer primary key, name text, saved text, value text)")
    con.execute("create table if not exists forge_profile_meta (key text primary key, value text)")


def _now() -> str:
    import datetime as dt
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _meta(con, key, default=None):
    r = con.execute("select value from forge_profile_meta where key=?", (key,)).fetchone()
    return json.loads(r["value"]) if r else default


def _set_meta(con, key, value):
    con.execute("insert into forge_profile_meta(key,value) values(?,?) on conflict(key) do update set value=excluded.value",
                (key, json.dumps(value)))


def _slot_no(slot) -> int:
    try:
        n = int(slot)
    except (TypeError, ValueError):
        raise ValueError("Pick slot 1, 2 or 3")
    if not 1 <= n <= PROFILE_SLOTS:
        raise ValueError("Pick slot 1, 2 or 3")
    return n


def _clean_name(name, n: int) -> str:
    s = " ".join(str(name or "").split())[:40]
    return s or f"Profile {n}"


def _seed_slots(con) -> None:
    """First use: slot 1 = your real profile, slot 2 = the fresh-start test if you're in one."""
    if _meta(con, "seeded"):
        return
    _profile_saves_table(con)
    cur = load_profile()
    t = _now()
    if cur.get("fresh"):
        real = con.execute("select * from forge_profile_saves order by id desc limit 1").fetchone()
        if real:
            v = json.loads(real["value"]); v["fresh"] = False
            con.execute("insert or ignore into forge_profile_slots values(1,?,?,?)", ("My profile", real["saved"], json.dumps(v)))
            con.execute("insert or ignore into forge_profile_slots values(2,?,?,?)", ("Fresh start test", t, json.dumps(cur)))
            _set_meta(con, "active", 2)
        else:
            con.execute("insert or ignore into forge_profile_slots values(1,?,?,?)", ("Fresh start test", t, json.dumps(cur)))
            _set_meta(con, "active", 1)
    else:
        con.execute("insert or ignore into forge_profile_slots values(1,?,?,?)", ("My profile", t, json.dumps(cur)))
        _set_meta(con, "active", 1)
    _set_meta(con, "seeded", t)


def _slot_summary(v: dict) -> str:
    ex = v.get("extras") or {}
    bits = []
    if v.get("fresh"):
        bits.append("fresh-start test")
    if ex.get("class"):
        bits.append(str(ex["class"]).replace("_", " "))
    if ex.get("deviation"):
        bits.append(str(ex["deviation"]))
    if v.get("starchrom") not in (None, ""):
        bits.append(f"{int(v['starchrom']):,} Starchrom")
    nw = len(v.get("weapons") or [])
    if nw:
        bits.append(f"{nw} gun{'s' if nw != 1 else ''} added by hand")
    return " · ".join(bits) or "recorded game data"


def profile_slots() -> dict:
    """{'active': n|None, 'slots': [{slot, name, saved, empty, fresh, summary}]}"""
    ensure_profile_table()
    with db(False) as con:
        _slots_table(con)
        _seed_slots(con)
        rows = {r["slot"]: r for r in con.execute("select * from forge_profile_slots")}
        active = _meta(con, "active")
        names = _meta(con, "names", {})
    out = []
    for n in range(1, PROFILE_SLOTS + 1):
        r = rows.get(n)
        if r and r["value"]:
            v = json.loads(r["value"])
            out.append({"slot": n, "name": r["name"], "saved": r["saved"], "empty": False,
                        "fresh": bool(v.get("fresh")), "summary": _slot_summary(v)})
        else:
            out.append({"slot": n, "name": (r["name"] if r else None) or names.get(str(n)) or f"Profile {n}",
                        "saved": None, "empty": True, "fresh": False, "summary": "empty"})
    return {"active": active, "slots": out}


def _store_current(con, n: int, name: str | None = None) -> None:
    cur = load_profile()
    old = con.execute("select name from forge_profile_slots where slot=?", (n,)).fetchone()
    nm = _clean_name(name if name is not None else (old["name"] if old else None), n)
    con.execute("insert into forge_profile_slots(slot,name,saved,value) values(?,?,?,?) on conflict(slot) do update set "
                "name=excluded.name, saved=excluded.saved, value=excluded.value", (n, nm, _now(), json.dumps(cur)))


def slot_action(action: str, slot=None, name=None) -> dict:
    """save: store the profile you're using in a slot (it becomes the active one)
    load: switch to a slot (the profile you're leaving is saved to its slot and to the backup list first)
    rename: change a slot's name · clear: empty a slot that isn't in use. Returns the profile now in use."""
    n = _slot_no(slot)
    ensure_profile_table()
    with db(False) as con:
        _slots_table(con)
        _seed_slots(con)
        _profile_saves_table(con)
        active = _meta(con, "active")
        row = con.execute("select * from forge_profile_slots where slot=?", (n,)).fetchone()
        if action == "save":
            _store_current(con, n, name)
            _set_meta(con, "active", n)
        elif action == "rename":
            nm = _clean_name(name, n)
            if row:
                con.execute("update forge_profile_slots set name=? where slot=?", (nm, n))
            else:
                names = _meta(con, "names", {}); names[str(n)] = nm; _set_meta(con, "names", names)
        elif action == "clear":
            if active == n:
                raise ValueError("That profile is in use. Load another profile first.")
            if row and row["value"]:
                con.execute("insert into forge_profile_saves(label,saved,value) values(?,?,?)",
                            (f"cleared slot {n}: {row['name']}", _now(), row["value"]))
            con.execute("update forge_profile_slots set value=null, saved=null where slot=?", (n,))
        elif action == "load":
            if not row or not row["value"]:
                raise ValueError("That slot is empty. Press Save on it first.")
            cur = load_profile()
            con.execute("insert into forge_profile_saves(label,saved,value) values(?,?,?)",
                        (f"before switching to {row['name']}", _now(), json.dumps(cur)))
            if active and active != n:
                _store_current(con, int(active))
            con.execute("delete from forge_profile")
            _set_meta(con, "active", n)
            data = json.loads(row["value"])
        else:
            raise ValueError(f"Unknown action {action}")
    if action == "load":
        return save_profile(data)
    return load_profile()


# ============================================================ owned items
# Mod 2.0 (Jan 2026): mod level = sum of the four sub-attribute levels, max 17.
# Official table: https://www.oncehuman.game/news/devBlog/20251212/40781_1276354.html
MOD_LEVEL_TIERS = {1: [1, 0, 0, 0], 2: [1, 1, 0, 0], 3: [1, 1, 1, 0], 4: [1, 1, 1, 1], 5: [2, 1, 1, 1], 6: [2, 2, 1, 1],
                   7: [2, 2, 2, 1], 8: [2, 2, 2, 2], 9: [3, 2, 2, 2], 10: [3, 3, 2, 2], 11: [3, 3, 3, 2], 12: [4, 3, 3, 2],
                   13: [4, 4, 3, 2], 14: [4, 4, 4, 2], 15: [5, 4, 4, 2], 16: [5, 5, 4, 2], 17: [5, 5, 5, 2]}
MAX_MOD_LEVEL = 17


def tiers_from_level(level: int) -> list[int]:
    """Sub-attribute levels for a mod level. The 4th line (all DMG Boost) caps at tier 2 -- confirmed against in-game tooltips."""
    level = max(0, min(MAX_MOD_LEVEL, int(level or 0)))
    return list(MOD_LEVEL_TIERS.get(level, [0, 0, 0, 0]))


def owned_mods(profile: dict | None = None) -> list[dict]:
    """Every (mod, variant) the player has recorded, with best known level and stat tiers."""
    gd = gamedata()
    names = catalog_mod_names()
    best: dict[tuple, dict] = {}
    with db() as con:
        rows = []
        try:
            for r in ([] if (profile or {}).get("fresh") else con.execute("select catalog_id, level from field_guide_levels")):
                rows.append({"catalog_id": r["catalog_id"], "level": r["level"], "tiers": None, "lines": None})
        except sqlite3.OperationalError:
            pass
        for r in ([] if (profile or {}).get("fresh") else con.execute("select name, variant, slot, level, stats, effects from inventory "
                             "where kind='mod_unlock' and coalesce(archived,0)=0")):
            stats = json.loads(r["stats"] or "{}")
            eff = json.loads(r["effects"] or "{}")
            rows.append({"catalog_id": eff.get("catalog_id"), "name": r["name"], "variant": r["variant"],
                         "slot": r["slot"], "level": r["level"],
                         "tiers": stats.get("catalog_level_profile"),
                         "lines": stats.get("observed_attribute_lines")})
    # mods you said are on a piece right now count as owned too
    eq_mods = [dict(m) for m in (((profile or {}).get("extras") or {}).get("equipped") or {}).values()
               if isinstance(m, dict)]
    for m in ((profile or {}).get("mods") or []) + eq_mods:
        if m.get("name"):
            rows.append({"catalog_id": None, "name": m["name"], "variant": m.get("variant") or "General",
                         "slot": None, "level": m.get("level") or 10, "tiers": None, "lines": None})
    for r in rows:
        name, variant, slot = r.get("name"), r.get("variant"), r.get("slot")
        if r.get("catalog_id") in names:
            n2, v2, s2 = names[r["catalog_id"]]
            name, variant, slot = name or n2, variant or v2, slot or s2
        if not name:
            continue
        gm = gd["mods"].get(name.lower())
        if not gm:
            continue
        key = (name.lower(), (variant or "").lower())
        lvl = min(MAX_MOD_LEVEL, int(r.get("level") or 0))  # old-system levels above 17 count as 17
        cur = best.get(key)
        if cur and cur["level"] > lvl and not (r.get("tiers") and not cur.get("tiers_observed")):
            continue
        tiers = r.get("tiers") or (cur or {}).get("tiers") if cur and cur["level"] == lvl else r.get("tiers")
        best[key] = {
            "name": gm["name"], "variant": variant or "General", "slot": gm.get("slot_key") or SLOT_ALIASES.get(slot or ""),
            "level": lvl, "tiers": tiers or tiers_from_level(lvl), "tiers_observed": bool(tiers),
            "observed_lines": r.get("lines"), "owned": True,
        }
    edits = (profile or {}).get("mod_edits") or {}
    out = []
    for key, m in best.items():
        e = edits.get(f"{m['name']}|{m['variant']}".lower()) or {}
        if e.get("removed"):
            continue
        if e.get("level") and int(e["level"]) != m["level"]:
            m = dict(m, level=max(1, min(MAX_MOD_LEVEL, int(e["level"]))))
            m["tiers"] = tiers_from_level(m["level"]); m["tiers_observed"] = False
        if e.get("shiny") and m["level"] == MAX_MOD_LEVEL:
            # Shiny = a level 17 with a slightly higher main effect and an extra Shiny effect (official dev blog).
            # Values differ per mod and aren't in any data source, so we count what you type from the tooltip.
            m = dict(m, shiny=True, shiny_main=(e.get("shiny_main") or "").strip() or None,
                     shiny_extra=(e.get("shiny_extra") or "").strip() or None)
        if m["slot"]:
            out.append(m)
    return out


def owned_weapons(profile: dict) -> list[dict]:
    gd = gamedata()
    out = []
    with db() as con:
        for r in ([] if profile.get("fresh") else con.execute("select name, slot, stars, stats from inventory where kind='instance' "
                             "and coalesce(archived,0)=0")):
            stats = json.loads(r["stats"] or "{}")
            w = match_weapon(r["name"])
            if not w:
                continue
            out.append({"name": w["name"], "stars": int(r["stars"] or 1), "tier": int(stats.get("craft_tier") or 5),
                        "calibration": stats.get("calibration_profile"), "source": "recorded"})
    for extra in profile.get("weapons") or []:
        w = match_weapon(extra.get("name", ""))
        if w and not any(o["name"] == w["name"] for o in out):
            out.append({"name": w["name"], "stars": int(extra.get("stars") or 1), "tier": int(extra.get("tier") or 5),
                        "calibration": extra.get("calibration"), "source": "profile",
                        "magazine_acc": extra.get("magazine") or None, "reload_s": extra.get("reload_s")})
    edits = profile.get("weapon_edits") or {}
    final = []
    for o in out:
        e = edits.get(o["name"]) or {}
        if e.get("removed"):
            continue
        if e.get("stars"):
            o = dict(o, stars=max(1, min(6, int(e["stars"]))))
        if e.get("calibration") is not None:
            o = dict(o, calibration=e["calibration"] or None)
        if e.get("magazine") is not None:
            o = dict(o, magazine_acc=e["magazine"] or None)
        if e.get("reload_s"):
            o = dict(o, reload_s=max(0.3, min(10.0, float(e["reload_s"]))))
        sw = (profile.get("extras") or {}).get("sniper_ws")
        if sw not in (None, ""):
            o = dict(o, _sniper_ws=sw)
        if profile.get("accessory_values"):
            o = dict(o, _acc_overrides=profile["accessory_values"])
        final.append(o)
    return final


def match_weapon(name: str) -> dict | None:
    gd = gamedata()["weapons"]
    if name in gd:
        return gd[name]
    s = slug(name)
    for k, w in gd.items():
        if slug(k) == s:
            return w
    for k, w in gd.items():
        if s and (s in slug(k) or slug(k) in s):
            return w
    return None


# ============================================================ mod stats
def mod_substats(mod: dict, scenario: str = "boss") -> dict[str, float]:
    return dict(_mod_substats(mod["name"], mod.get("variant") or "General", tuple(mod.get("tiers") or ()),
                              tuple(sorted(fe.scn(scenario)["vision"].items()))))


@lru_cache(maxsize=None)
def _mod_substats(name: str, variant: str, tiers: tuple, vision: tuple = ()) -> tuple:
    return tuple(_mod_substats_impl({"name": name, "variant": variant, "tiers": list(tiers)}, dict(vision) or fe.VISION_UPTIME).items())


def _mod_substats_impl(mod: dict, vision: dict | None = None) -> dict[str, float]:
    gm = gamedata()["mods"].get(mod["name"].lower())
    out: dict[str, float] = {}
    if not gm:
        return out
    variant = mod.get("variant") or "General"
    names = None
    for vname, subs in (gm.get("variant_substats") or {}).items():
        if vname.lower() == variant.lower():
            names = subs
    if names is None:
        # Keyword weapon-mod variants (e.g. "Power Surge") are named after the keyword.
        for vname, subs in (gm.get("variant_substats") or {}).items():
            if variant.lower() in vname.lower():
                names = subs
    if names is None:
        return out
    for ln in mod_lines_eval(gm, names, mod.get("tiers") or [], vision):
        if ln["key"] and ln["value"]:
            out[ln["key"]] = out.get(ln["key"], 0.0) + ln["value"]
    return out


# Position-based suffix lines on Top mods (estimates, single boss): how often you hit from behind,
# how often you're within 15m, and how far into the "closer = more" range you sit on average.
MIRROR_BEHIND = 0.1
WILD_NEAR = 0.7
WILD_CLOSE_SHARE = 0.4
SURVIVAL_WORDS = ("hp", "dmg reduction", "damage taken", "reduces the target's dmg", "recovers", "shield")


def _nums(s: str) -> list[float]:
    return [float(x) for x in re.findall(r"[+-]?\d+(?:\.\d+)?", s or "")]


def mod_lines_eval(gm: dict, names: list[str], tiers: list[int], vision: dict | None = None) -> list[dict]:
    """One entry per attribute line: the game text value, the stat it feeds, and whether DPS counts it."""
    table = gm.get("substat_values_by_tier") or {}
    vis = vision or fe.VISION_UPTIME
    out = []
    for name, tier in zip(names, list(tiers) + [0] * (len(names) - len(tiers))):
        vals = table.get(name) or []
        raw = vals[tier - 1] if tier and len(vals) >= tier else ""
        nums = _nums(raw)
        val = nums[0] if nums else (default_tier_value(name) * tier if tier else 0.0)
        label = name.split(":")[0] if ":" in name else None
        key, uptime, note, counted = None, 1.0, "", True
        low = name.lower()
        if not tier:
            counted, note = False, "Unlocks at a higher mod level"
        elif label in ("Mirror", "Wild") and re.search(r":\s*[A-Za-z' ]+?\s*\+X", name) and not any(w in low for w in ("taken",)) and label == "Mirror":
            st = re.search(r":\s*([A-Za-z' ]+?)\s*\+X", name).group(1)
            key = "weapon_dmg" if "firearm" in st.lower() else fe.stat_key(st); extra = nums[1] if len(nums) > 1 else 0.0
            val = val + extra * MIRROR_BEHIND
            note = f"Always-on part counted; the from-behind part counted {int(MIRROR_BEHIND * 100)}% of the time (estimate)"
        elif label == "Wild" and re.search(r"15 ?m", low) and "taken" not in low:
            st = re.search(r"15 ?m(?:eters)?,\s*([A-Za-z' ]+?)\s*\+X", name)
            st = st.group(1) if st else "firearm damage"
            key = "weapon_dmg" if "firearm" in st.lower() else fe.stat_key(st); top = nums[2] if len(nums) > 2 else val
            val = WILD_NEAR * (val + (top - val) * WILD_CLOSE_SHARE)
            note = f"Counted for being within 15m {int(WILD_NEAR * 100)}% of the time (estimate)"
        elif label in {"Lunar", "Crescent", "Downstar", "Aero", "Resonance"}:
            m = re.search(r":\s*(?:The lower your HP, the higher your )?([A-Za-z' ]+?)(?: \+X%|,| up to)", name)
            key = fe.stat_key(m.group(1)) if m else None
            uptime = vis.get(label, 0.0)
            note = f"{label} condition, counted {int(round(uptime * 100))}% of the time (your effort setting)"
        elif low == "explosive":
            key = "kw_dmg:Unstable Bomber"; note = "Counts only on Unstable Bomber weapons"
        else:
            key = fe.stat_key(name)
            if key and key.startswith(("kw_", "el:")):
                note = "Counts only when your weapon has that keyword/element"
        if tier and not key:
            counted = False
            note = ("Survival stat, doesn't change DPS" if any(w in low for w in SURVIVAL_WORDS)
                    else "Not in the damage math yet (no single-target DPS effect, or not modeled)")
        out.append({"line": name, "text": raw or "", "tier": tier, "key": key, "value": round(val * uptime, 3) if key else 0.0,
                    "counted": counted and bool(key), "note": note})
    return out


def mod_info(name: str, variant: str, level: int, scenario: str = "boss") -> dict:
    """What the game's mod tooltip shows, plus how each line enters the damage math."""
    gm = gamedata()["mods"].get((name or "").lower())
    if not gm:
        return {"error": "unknown mod"}
    names = None
    for vname, subs in (gm.get("variant_substats") or {}).items():
        if vname.lower() == (variant or "").lower():
            names = subs
    if names is None:
        names = next((subs for vname, subs in (gm.get("variant_substats") or {}).items() if (variant or "").lower() in vname.lower()), [])
    lv = max(0, min(MAX_MOD_LEVEL, int(level or 0)))
    tiers = tiers_from_level(lv) if lv else [0, 0, 0, 0]
    vision = fe.scn(scenario)["vision"]
    lines = mod_lines_eval(gm, names, tiers, vision)
    core = _core_text(gm["name"])
    p = cached_parse(core, scenario, {"hits_per_s": 8, "reload_cycle_s": 6, "crit_rate": 0.3, "kw_procs_per_s": 0})
    mk = fe.mentioned_keywords(core)
    return {"name": gm["name"], "variant": variant, "slot": gm.get("slot"), "level": lv, "tiers": tiers,
            "core": core, "core_counted": bool(p.contributions) and not p.unmodeled,
            "core_partial": bool(p.contributions) and bool(p.unmodeled),
            "core_keywords": sorted(mk) if mk else [],
            "lines": lines,
            "level_note": "The 4th line (all DMG Boost) stops at level 2 on every mod; the other three climb to 5. Confirmed against in-game tooltips."}


def default_tier_value(name: str) -> float:
    n = name.lower()
    if "crit dmg" in n:
        return 3.0
    if "magazine" in n:
        return 2.4
    if "elemental" in n:
        return 1.6
    if "weakspot" in n or "reload" in n:
        return 1.8
    if "dmg boost" in n or "all dmg" in n:
        return 1.5
    return 1.2


def mod_core_text(mod: dict) -> str:
    if mod.get("shiny") and mod.get("shiny_main"):
        return mod["shiny_main"]
    return _core_text(mod["name"])


def _unused_core(mod: dict) -> str:
    gm = gamedata()["mods"].get(mod["name"].lower()) or {}
    core = gm.get("core_effect_by_level") or {}
    if core:
        return core.get("5") or core.get(5) or list(core.values())[-1]
    return gm.get("summary") or ""


# ============================================================ damage model
def weapon_damage(w: dict, stars: int) -> float:
    ps = w.get("dmg_per_star") or {}
    ps = {int(k): v for k, v in ps.items()}
    if stars in ps:
        return ps[stars]
    if ps:
        return ps[max(k for k in ps if k <= stars)] if any(k <= stars for k in ps) else min(ps.values())
    return w.get("dmg") or 0


def calibration_stats(cal: dict | None, wtype: str = "") -> dict[str, float]:
    out: dict[str, float] = {}
    if not cal:
        return out
    if cal.get("style") and cal.get("rolls") and cal.get("attack") is None:
        # recorded from the game: the 33-50% roll is the blueprint's attack line, the other roll is the bonus line
        norm = {"style": cal["style"]}
        for r in cal["rolls"]:
            stat = (r.get("stat") or "").lower(); v = float(r.get("value_percent") or 0)
            if stat.startswith(("weapon dmg", "attack")) and "attack" not in norm:
                norm["attack"] = v
            else:
                key = "elemental_dmg" if stat.startswith("elemental") else fe.stat_key(r.get("stat") or "")
                if key in fx.CAL_SUB_MAX and "sub" not in norm:
                    norm["sub"], norm["sub_value"] = key, v
        m = re.search(r"Attack \+(\d+(?:\.\d+)?)%", cal.get("fixed_effects") or "")
        ent = fx.cal_style(fx.weapon_family(wtype), cal["style"])
        if m and ent and (ent.get("var") or {}).get("key") == "attack":
            norm["style_value"] = float(m.group(1))
        return fx.calibration_from_profile(norm, wtype)
    if cal.get("style"):
        return fx.calibration_from_profile(cal, wtype)
    for r in cal.get("rolls") or []:
        stat = r.get("stat") or ""
        key = "elemental_dmg" if stat.lower().startswith("elemental") else fe.stat_key(stat)
        if key:
            out[key] = out.get(key, 0) + float(r.get("value_percent") or 0)
    for m in re.finditer(r"([A-Z][A-Za-z ]+?) \+(\d+(?:\.\d+)?)%", cal.get("fixed_effects") or ""):
        key = fe.stat_key(m.group(1))
        if key:
            out[key] = out.get(key, 0) + float(m.group(2))
    return out


def weapon_signature(w: dict, scn: dict, ctx: dict) -> tuple[dict[str, float], list[dict], list[str]]:
    """Parse a weapon's own effect text: keyword chance, flat bonuses and extra procs."""
    text = w.get("effect_text") or ""
    stats: dict[str, float] = {}
    procs: list[dict] = []
    notes: list[str] = []
    kw = w.get("keyword")
    m = re.search(r"(\d+(?:\.\d+)?)% chance to (?:trigger|apply|inflict|cause)\s+" + re.escape(kw or "@@"), text, re.I)
    every_kw = re.search(r"every (\d+) weapon hits trigger|hitting (\d+) times with the weapon triggers", text, re.I)
    if every_kw:
        stats[f"kw_base:{kw}"] = 100.0 / int(every_kw.group(1) or every_kw.group(2))
        if re.search(r"crit(?:s| hit)?,? it counts as 2 hits", text, re.I):
            stats["_crit_counts_double"] = 1
        if m:
            stats["_extra_crit_chance"] = float(m.group(1))
        m = None
    elif m:
        stats[f"kw_base:{kw}"] = float(m.group(1))
        if "weakspot" in text[:m.start()].lower()[-60:]:
            stats["_chance_on_weakspot"] = 1
        if "crit" in text[:m.start()].lower()[-40:]:
            stats["_chance_on_crit"] = 1
    elif not every_kw and re.search(r"(?:trigger|apply|triggers|applies) " + re.escape(kw or "@@"), text or "", re.I):
        cd = re.search(r"cooldown of (\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*s cooldown", text)
        stats[f"kw_base:{kw}"] = 100.0
        n_hits = re.search(r"every (\d+) weapon hits trigger", text, re.I)
        if n_hits:
            stats[f"kw_base:{kw}"] = 100.0 / int(n_hits.group(1))
        if cd:
            stats["_kw_cooldown"] = float(cd.group(1) or cd.group(2))
    ac = re.search(r"after a crit hit, triggering [a-z' ]+ will additionally trigger (\d+) times?, lasting (\d+(?:\.\d+)?)s", text, re.I)
    if ac:
        stats["_after_crit_extra"] = float(ac.group(1)); stats["_after_crit_window"] = float(ac.group(2))
    # Generic flat bonuses inside the weapon text (e.g. "Shock Elemental DMG +30%.")
    for sentence in re.split(r"(?<=[.])\s+", text):
        if ac and ac.group(0).lower() in sentence.lower():
            continue
        if re.search(r"hitting \d+ times with the weapon triggers|counts as 2 hits", sentence, re.I):
            continue
        cc = (re.search(r"crit capability for [A-Za-z' ]+?, increasing its crit rate by \+?(\d+(?:\.\d+)?)%", sentence, re.I)
              or (re.search(r"unlocks the ability for [A-Za-z' ]+ to deal crit", sentence, re.I)
                  and re.search(r"crit rate \+?(\d+(?:\.\d+)?)%", sentence, re.I)))
        if cc:
            stats[f"kw_crit_rate:{kw}"] = stats.get(f"kw_crit_rate:{kw}", 0) + float(cc.group(1))
            continue
        if re.search(r"chance to|deal(?:s|ing)? .*% (?:psi intensity|attack)", sentence, re.I):
            pass
        parsed = fe.parse_effect(sentence, scn, ctx)
        for c in parsed.contributions:
            if c.stat.startswith("kw_chance") and re.search(r"\d+% chance to", sentence):
                continue
            if c.stat == "proc_note":
                continue
            stats[c.stat] = stats.get(c.stat, 0) + c.value
    # Extra damage instances: "... deals Shock Elemental DMG of 42% Psi Intensity"
    for m in re.finditer(r"([^.]*?)(?:deal(?:s|ing)?|dealt)[^.%]*?(\d+(?:\.\d+)?)%[^.%]{0,45}?(Psi Intensity|Intensity|attack)([^.]*)(?:\.|$)", text, re.I):
        before, coef, basis, after = m.group(1), float(m.group(2)), m.group(3), m.group(4)
        sentence = (before + " " + after).lower()
        sents = re.split(r"(?<=[.])\s+", text[:m.end()])
        sent_full = " ".join(sents[-3:]).lower()
        rate, how = proc_rate(sent_full, ctx, scn)
        bounces = re.search(r"bounces? up to (\d+) times", text.lower())
        mult_hits = 1.0
        if bounces and "orb" in sentence:
            mult_hits = min(int(bounces.group(1)), 1 + 2 * scn["enemies_hit"]) if scn["enemies_hit"] > 1 else 1.5
        up = re.search(r"increasing the damage multiplier from (\d+)% to (\d+)%", text, re.I)
        if up and abs(float(up.group(1)) - coef) < 0.01:
            coef = (float(up.group(1)) + float(up.group(2))) / 2  # assume half are shattered early
        procs.append({"coef": coef / 100.0, "basis": "psi" if "intensity" in basis.lower() else "attack",
                      "rate": rate * mult_hits, "how": how, "element": element_of(m.group(0), w),
                      "uses_keyword_bonus": bool(re.search(r"benefits from|as frost vortex|" + re.escape((kw or "@@").lower()) + r" (?:damage|dmg)", m.group(0).lower())),
                      "text": m.group(0).strip()[:160], "sentence": sent_full})
    if not text:
        notes.append("Weapon effect text missing")
    return stats, procs, notes


def element_of(text: str, w: dict) -> str | None:
    for el in fe.ELEMENTS:
        if el.lower() in text.lower():
            return el
    return fe.KEYWORD_ELEMENT.get(w.get("keyword") or "")


def proc_rate(text: str, ctx: dict, scn: dict) -> tuple[float, str]:
    """Rate (per second) of a weapon side-effect described by `text` (its own sentence first)."""
    hits = ctx["hits_per_s"]
    kwps = ctx.get("kw_procs_per_s", 0)
    m = re.search(r"cooldown(?: of)?:? (\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*s(?:econds?)? cooldown", text)
    cd = float(m.group(1) or m.group(2)) if m else 0.0
    every = re.search(r"every (\d+) (?:weapon )?hits", text)
    n = re.search(r"(?:hitting|hit) (?:a target affected by [a-z' ]+ |a target )?(\d+) times?", text)
    chance = re.search(r"(\d+(?:\.\d+)?)% chance to (?:launch|summon|fire|trigger an?|create|deal|generate)", text)
    if every:
        rate = hits / float(every.group(1)); how = f"every {every.group(1)} hits"
    elif n:
        rate = hits / float(n.group(1)); how = f"every {n.group(1)} hits"
    elif re.search(r"after triggering [a-z' ]+ (\d+) times", text):
        k = int(re.search(r"after triggering [a-z' ]+ (\d+) times", text).group(1))
        rate = kwps / k; how = f"every {k} keyword procs"
    elif chance:
        rate = hits * float(chance.group(1)) / 100; how = f"{chance.group(1)}% of hits"
    elif "first hit after reload" in text or "after reloading" in text:
        rate = 1.0 / ctx["reload_cycle_s"]; how = "once per reload"
    elif re.search(r"when triggering|upon triggering|each time .* triggers", text):
        rate = kwps; how = "per keyword proc"
    elif "expire" in text or "shatter" in text:
        rate = 1.0 / max(cd, 1.5); how = "on crystal shatter"
    else:
        rate = hits; how = "per hit"
    if cd:
        rate = min(rate, 1.0 / cd); how += f", {cd:g}s cooldown"
    return rate, how


_PARSE_CACHE: dict = {}


def cached_parse(text: str, scenario: str, ctx: dict):
    key = (text, scenario, round(ctx["hits_per_s"], 1), round(ctx["reload_cycle_s"], 1), round(ctx.get("crit_rate", 0), 2), ctx.get("kw_procs_per_s", 0), ctx.get("shield_uptime"))
    hit = _PARSE_CACHE.get(key)
    if hit is None:
        hit = _PARSE_CACHE[key] = fe.parse_effect(text, fe.scn(scenario), ctx)
    return hit


_SIG_CACHE: dict = {}


def evaluate(weapon: dict, wstate: dict, mods: list[dict], set_counts: dict[str, int], psi: float,
             scenario: str = "boss", extra_stats: dict | None = None,
             extras: list | None = None) -> dict:
    """Sustained DPS for one weapon + mods + armor set counts (+ key armor, deviation, food, calibration)."""
    gd = gamedata()
    scn = fe.scn(scenario)
    kw = weapon.get("keyword")
    family = weapon.get("type") or ""
    pellets = pellets_of(weapon)
    acc = SHOTGUN_PELLET_HIT if pellets > 1 else 0.9
    fire_rate = (weapon.get("fire_rate_rpm") or 300) / 60.0
    mag = weapon.get("magazine") or 30
    reload_s = float(wstate.get("reload_s") or RELOAD_SECONDS.get(family, 2.4))
    cal_st = calibration_stats(wstate.get("calibration"), weapon.get("type") or "")
    mag_id = wstate.get("magazine_acc")
    acc_st = forge_accessories.stats_for(mag_id, wstate.get("_acc_overrides")) if mag_id and forge_accessories.fits(mag_id, weapon) else {}

    stats: dict[str, float] = {}
    unmodeled: list[str] = []
    sources: list[dict] = []

    def add(src: str, d: dict[str, float]):
        for k, v in d.items():
            stats[k] = stats.get(k, 0.0) + v
        if d:
            sources.append({"source": src, "stats": {k: round(v, 2) for k, v in d.items() if not k.startswith("_")}})

    # first pass context (needed for uptime of timed buffs)
    # calibration and magazine are known up front, so "once per reload" effects see the real reload cycle
    pre = {k: cal_st.get(k, 0) + acc_st.get(k, 0) for k in ("fire_rate", "magazine", "magazine_flat", "reload_speed")}
    fr0 = fire_rate * (1 + pct(pre["fire_rate"]))
    mag0 = mag * (1 + pct(pre["magazine"])) + pre["magazine_flat"]
    ctx = {"hits_per_s": fr0 * pellets * acc, "reload_cycle_s": mag0 / fr0 + reload_s / max(0.2, 1 + pct(pre["reload_speed"])),
           "crit_rate": pct(weapon.get("crit_rate_pct")), "kw_procs_per_s": 0}

    add("Calibration", cal_st)
    if acc_st:
        add(f"Magazine: {forge_accessories.MAGAZINES[mag_id]['name']}", acc_st)
    sk = (weapon["name"], scenario)
    if sk not in _SIG_CACHE:
        _SIG_CACHE[sk] = weapon_signature(weapon, scn, ctx)
    sig_stats, procs, notes = _SIG_CACHE[sk]
    # rough keyword trigger rate for keyword-triggered buffs (refined numbers come later)
    base = pct(sig_stats.get(f"kw_base:{kw}"))
    if base:
        cr0 = 0.5  # typical endgame crit rate for crit-linked triggers
        ctx["kw_procs_per_s"] = round(ctx["hits_per_s"] * 0.8 * min(1, base) * (1 + (cr0 if sig_stats.get("_crit_counts_double") else 0))
                                      * (1 + 0.5 * sig_stats.get("_after_crit_extra", 0)), 1)
    add(f"{weapon['name']} effect", {k: v for k, v in sig_stats.items()})
    unmodeled += notes

    for mod in mods:
        add(f"{mod['name']} ({mod['variant']}) stats", dict(_mod_substats(mod["name"], mod.get("variant") or "General", tuple(mod.get("tiers") or ()),
                                                                          tuple(sorted(scn["vision"].items())))))
        core = mod_core_text(mod)
        mk = fe.mentioned_keywords(core)
        if mk and kw not in mk:
            unmodeled.append(f"{mod['name']}: only works with {', '.join(sorted(mk))} (this weapon is {kw or 'no keyword'})")
            continue
        p = cached_parse(core, scenario, ctx)
        add(f"{mod['name']} core" + (" (Shiny)" if mod.get("shiny_main") else ""), fe.merge(p.contributions))
        if p.unmodeled:
            unmodeled.append(f"{mod['name']}: {core[:110]}")
        if mod.get("shiny"):
            if mod.get("shiny_extra"):
                px = cached_parse(mod["shiny_extra"], scenario, ctx)
                add(f"{mod['name']} Shiny effect", fe.merge(px.contributions))
                if px.unmodeled:
                    unmodeled.append(f"{mod['name']} Shiny effect: {mod['shiny_extra'][:110]}")
            if not (mod.get("shiny_main") or mod.get("shiny_extra")):
                unmodeled.append(f"{mod['name']}: Shiny bonus not counted (type the Shiny lines from your tooltip in My gear > Mods)")
        for c in p.contributions:
            if c.stat == "proc_note":
                unmodeled.append(f"{mod['name']}: extra-hit effect ({c.note}) not counted")

    if set_counts.get("Savior", 0) >= 3:   # Savior 3pc keeps a shield up on every hit (0.5s cooldown)
        ctx["shield_uptime"] = SAVIOR_SHIELD_UPTIME
    for set_name, count in set_counts.items():
        s = gd["sets"].get(set_name)
        if not s:
            continue
        for need, text in s["effects"].items():
            if int(need) <= count:
                ov = SET_TEXT_OVERRIDES.get((set_name, str(need)))
                if ov:
                    add(f"{set_name} {need}pc", dict(ov[0]))
                    unmodeled.append(f"{set_name} {need}pc: estimate ({ov[1]})")
                    continue
                mk = fe.mentioned_keywords(text)
                if mk and kw not in mk:
                    unmodeled.append(f"{set_name} {need}pc: only works with {', '.join(sorted(mk))}")
                    continue
                p = cached_parse(text, scenario, ctx)
                add(f"{set_name} {need}pc", fe.merge(p.contributions))
                if p.unmodeled:
                    unmodeled.append(f"{set_name} {need}pc: {text[:110]}")
    if extra_stats:
        add("Other", extra_stats)
    for label, d in extras or []:
        if label == "_notes":
            unmodeled += list(d)
        else:
            add(label, d)

    # per-stat scaling effects ("each 1% Crit Rate grants +0.7% X DMG")
    for k in list(stats):
        if k.startswith("per:"):
            _, src, dst = k.split(":", 2)
            base = stats.get(src, 0) + (weapon.get("crit_rate_pct") or 0 if src == "crit_rate" else 0)
            stats[dst] = stats.get(dst, 0) + base * stats.pop(k)

    fire_rate *= 1 + pct(stats.get("fire_rate"))
    mag = mag * (1 + pct(stats.get("magazine"))) + stats.get("magazine_flat", 0)
    reload_s /= max(0.2, 1 + pct(stats.get("reload_speed")))
    fire_time = mag / fire_rate
    sustain = fire_time / (fire_time + reload_s)
    hits_ps = fire_rate * pellets * acc * sustain  # 90% accuracy (75% of shotgun pellets)
    shots_ps = fire_rate * 0.9 * sustain

    crit_rate = min(1.0, pct(weapon.get("crit_rate_pct")) + pct(stats.get("crit_rate")))
    crit_dmg = pct(weapon.get("crit_dmg_pct")) + pct(stats.get("crit_dmg"))
    ws_dmg = pct(weapon.get("weakspot_dmg_pct")) + pct(stats.get("weakspot_dmg"))
    ws_rate = scn["weakspot_rate"] * (SHOTGUN_WS_FACTOR if pellets > 1 else 1.0)
    if (weapon.get("type") or "") in SNIPER_TYPES:
        # snipers aim each shot at the head; your setting wins, otherwise double the spray rate (max 90%)
        ws_rate = sniper_weakspot_rate(scn["weakspot_rate"], wstate.get("_sniper_ws"))
    # "DMG Boost" (General mod substat) is treated as additive with Weapon/Status DMG,
    # not as its own multiplier, to avoid over-rating General mods.
    stats["weapon_dmg"] = stats.get("weapon_dmg", 0) + stats.get("dmg_boost", 0)
    stats["status_dmg"] = stats.get("status_dmg", 0) + stats.get("dmg_boost", 0)
    common = (1 + pct(stats.get("vs_enemies"))) * (1 + pct(stats.get("vulnerability")))
    attack = weapon_damage(weapon, wstate.get("stars", 1)) * (1 + pct(stats.get("attack")))
    hit_mult = 1 + crit_rate * crit_dmg + ws_rate * ws_dmg
    weapon_taken = 1 + pct(stats.get("weapon_taken"))
    # Bull's Eye mark uptime (own keyword, or a support weapon / teammate keeping it on the target)
    mark_up = 0.9 if stats.get("_marked") else 0.0
    marked_mult = 1 + pct(stats.get("marked_dmg")) * (mark_up if kw != "The Bull's Eye" else 0.9)
    common *= marked_mult
    bullet_hit = attack * (1 + pct(stats.get("weapon_dmg"))) * hit_mult * common * weapon_taken
    breakdown = {"Bullets": bullet_hit * hits_ps}

    # keyword
    kw_chance = pct(stats.get(f"kw_base:{kw}")) * (1 + pct(stats.get(f"kw_chance:{kw}")))
    if kw_chance and stats.get("_chance_on_weakspot"):
        kw_chance *= ws_rate
    if kw_chance and stats.get("_chance_on_crit"):
        kw_chance *= crit_rate
    kw_procs = hits_ps * min(1.0, kw_chance) if kw_chance else 0.0
    reverb = reverb_model(weapon, mag, ws_rate, acc, stats) if kw == "Shrapnel" else None
    if reverb:
        kw_procs = hits_ps * reverb["p_trigger"]
    if stats.get("_crit_counts_double"):
        kw_procs *= 1 + crit_rate
    if stats.get("_extra_crit_chance"):
        kw_procs += hits_ps * crit_rate * pct(stats["_extra_crit_chance"])
    if stats.get("_after_crit_extra"):
        in_window = 1 - math.exp(-hits_ps * crit_rate * stats.get("_after_crit_window", 1))
        kw_procs *= 1 + stats["_after_crit_extra"] * in_window
    if kw_chance and stats.get("_reload_kw_guarantee") and kw_chance < 1:
        # Vanguard / Boost calibration: first shot after a reload is a guaranteed (or likelier) trigger.
        kw_procs += min(1.0, stats["_reload_kw_guarantee"]) * (1 - kw_chance) / (fire_time + reload_s)
    kw_procs *= 1 + stats.get(f"_kw_trigger_extra:{kw}", 0)
    if stats.get("_kw_cooldown"):
        cdv = stats["_kw_cooldown"]
        red = re.search(r"cooldown reduction (\d+(?:\.\d+)?) ?s", (weapon.get("effect_text") or ""), re.I)
        if red:  # per-hit cooldown reduction (e.g. KAM - Abyss Glance)
            cdv = max(0.5, cdv / (1 + hits_ps * float(red.group(1))))
        kw_procs = min(kw_procs, 1.0 / cdv)
    el = fe.KEYWORD_ELEMENT.get(kw or "")
    status_mult = ((1 + pct(stats.get("status_dmg"))) *
                   (1 + pct(stats.get("elemental_dmg")) + pct(stats.get(f"el:{el}")) if el else 1) * common
                   * (1 + pct(stats.get(f"el_taken:{el}")) if el else 1))
    # keyword crits: status keywords can't crit unless the weapon unlocks it (e.g. DE.50 - Jaws)
    kcr = pct(stats.get(f"kw_crit_rate:{kw}"))
    kw_crit_mult = 1.0
    if kcr:
        kw_crit_mult = 1 + min(1.0, crit_rate + kcr) * (crit_dmg + pct(stats.get(f"kw_crit_dmg:{kw}")))
    kw_mult = (1 + pct(stats.get(f"kw_dmg:{kw}"))) * (1 + pct(stats.get(f"kw_final:{kw}")))
    if kw == "Power Surge":
        breakdown["Power Surge"] = kw_procs * 0.5 * psi * kw_mult * status_mult * kw_crit_mult
    elif kw == "Burn":
        max_st = 5 + stats.get("kw_stacks:Burn", 0)
        stacks = min(max_st, kw_procs * 6.0)
        breakdown["Burn"] = stacks * 0.12 * psi * 2 * kw_mult * status_mult * kw_crit_mult
    elif kw == "Frost Vortex":
        uptime = min(1.0, kw_procs * 4.0)
        breakdown["Frost Vortex"] = uptime * 0.5 * psi * 2 * kw_mult * status_mult * kw_crit_mult
    elif kw == "Unstable Bomber":
        breakdown["Unstable Bomber"] = kw_procs * 1.2 * psi * kw_mult * status_mult * kw_crit_mult
    elif kw == "Shrapnel":
        # Shrapnel is Weapon DMG: it crits (plus Shrapnel-only Crit DMG) and can land on weakspots.
        s_cr = min(1.0, crit_rate + pct(stats.get("kw_crit_rate:Shrapnel")))
        s_hit = (1 + s_cr * (crit_dmg + pct(stats.get("kw_crit_dmg:Shrapnel")))
                 + ws_rate * (ws_dmg + pct(stats.get("kw_ws_dmg:Shrapnel"))))
        parts = 1 if stats.get("_shrapnel_single") else min(scn.get("shrapnel_parts", 2), 1 + stats.get("_shrapnel_parts", 0))
        if reverb:
            parts = reverb["parts_per_trigger"]
            breakdown["Bullets"] *= 1 + reverb["last_bullet_bonus"]
        breakdown["Shrapnel"] = (kw_procs * 0.6 * parts * attack * (1 + pct(stats.get("weapon_dmg"))) * s_hit
                                 * kw_mult * common * weapon_taken)
    elif kw == "Bounce":
        # Bounce (Dec 2024 rework, https://www.oncehuman.game/news/devBlog/20241123/40781_1195665.html):
        # 40% of Attack per bounce, bounces twice; with no second enemy it bounces off the environment,
        # so a lone boss takes about one bounce per trigger (estimate).
        hops = 2 if scn["enemies_hit"] > 1 else 1
        b_hit = (1 + min(1.0, crit_rate + pct(stats.get("kw_crit_rate:Bounce"))) * (crit_dmg + pct(stats.get("kw_crit_dmg:Bounce")))
                 + ws_rate * (ws_dmg + pct(stats.get("kw_ws_dmg:Bounce"))))
        breakdown["Bounce"] = kw_procs * 0.4 * hops * attack * (1 + pct(stats.get("weapon_dmg"))) * b_hit * kw_mult * common * weapon_taken
    elif kw == "Fast Gunner":
        breakdown["Bullets"] *= 1.10  # 5 stacks of +1% fire rate and +1% attack, applied to bullets
    elif kw == "The Bull's Eye":
        bonus = 0.08 * min(1.0, kw_procs * 12)
        for k in breakdown:
            breakdown[k] *= 1 + bonus
    elif kw == "Fortress Warfare":
        breakdown["Bullets"] *= 1.12  # standing in the fortress zone (approximate)

    # weapon signature procs
    ctx2 = dict(ctx, hits_per_s=hits_ps, kw_procs_per_s=kw_procs, reload_cycle_s=fire_time + reload_s)
    zone_uptime = None
    sig_total = 0.0
    for p in procs:
        rate, how = proc_rate(p["sentence"], ctx2, scn)
        full = (weapon.get("effect_text") or "").lower()
        if "orb" in p["sentence"] and re.search(r"when triggering [a-z' ]+ on a unit within the zone", full):
            zone = re.search(r"radius \d+m for (\d+(?:\.\d+)?)s", full)
            zone_up = min(1.0, float(zone.group(1)) / ctx2["reload_cycle_s"]) if zone else 0.6
            zone_uptime = zone_up
            rate, how = kw_procs * zone_up, "per keyword proc inside the zone"
        p["how"] = how
        base = psi if p["basis"] == "psi" else attack
        pel = fe.KEYWORD_ELEMENT
        mult = status_mult if p["basis"] == "psi" else (1 + pct(stats.get("weapon_dmg"))) * hit_mult * common * weapon_taken
        if p["element"] and p["basis"] == "psi" and el != p["element"]:
            mult = (1 + pct(stats.get("status_dmg"))) * (1 + pct(stats.get("elemental_dmg")) + pct(stats.get(f"el:{p['element']}"))) * common
        if p["uses_keyword_bonus"]:
            mult *= kw_mult
        bounce = re.search(r"bounces? up to (\d+) times", (weapon.get("effect_text") or "").lower())
        if bounce and "orb" in p["text"].lower():
            rate *= 1.5 if scn["enemies_hit"] <= 1 else min(int(bounce.group(1)), 3 * scn["enemies_hit"])
        sig_total += rate * p["coef"] * base * mult
    if sig_total:
        breakdown[f"{weapon.get('effect_name') or 'Weapon'} effect"] = sig_total

    total = sum(breakdown.values())
    return {
        "dps": total,
        "breakdown": {k: round(v) for k, v in breakdown.items() if v},
        "stats": {k: round(v, 1) for k, v in sorted(stats.items()) if not k.startswith("_") and abs(v) > 0.05},
        "derived": {"crit_rate": round(crit_rate * 100, 1), "crit_dmg": round(crit_dmg * 100, 1),
                    "weakspot_dmg": round(ws_dmg * 100, 1), "attack": round(attack),
                    "fire_rate_rpm": round(fire_rate * 60), "magazine": round(mag), "uptime": round(sustain, 2),
                    "reload_s": round(reload_s, 2), "cycle_s": round(fire_time + reload_s, 2),
                    "zone_uptime": None if zone_uptime is None else round(zone_uptime, 2),
                    "magazine_acc": mag_id if acc_st else None,
                    "keyword_procs_per_s": round(kw_procs, 2), "psi": round(psi)},
        "sources": sources,
        "unmodeled": sorted(set(unmodeled))[:30],
    }


# ============================================================ optimizer
def estimate_psi(profile: dict, set_counts: dict | None = None) -> tuple[float, str]:
    if profile.get("psi_intensity"):
        return float(profile["psi_intensity"]), "from your character sheet"
    gd = gamedata()
    total, n = 0.0, 0
    for slot, piece in (profile.get("armor") or {}).items():
        a = gd["armor"].get(piece.get("name", ""))
        if a and a.get("stats_per_star"):
            st = a["stats_per_star"].get(str(piece.get("stars") or 1)) or a["stats_per_star"].get(piece.get("stars") or 1) or {}
            total += st.get("Psi Intensity") or a.get("psi_intensity") or 0
            n += 1
    if n >= 6:
        return total, "sum of your 6 armor pieces"
    if n:
        est = total / n * 6
        return max(est, 600.0 * (6 - n) / 6 + total), f"estimated: {n} of 6 armor pieces recorded"
    return 600.0, "assumed (no armor or Psi Intensity recorded yet)"


def set_counts_from_profile(profile: dict) -> dict[str, int]:
    gd = gamedata()
    counts: dict[str, int] = {}
    for slot, piece in (profile.get("armor") or {}).items():
        a = gd["armor"].get(piece.get("name", ""))
        if a and piece.get("name") not in fx.KEY_ARMOR:
            k = set_key(a)
            if k in gd["sets"]:
                counts[k] = counts.get(k, 0) + 1
    return counts


def best_mods_for(weapon, wstate, pool, set_counts, psi, scenario, fixed=None, passes=3, extras=None):
    """Coordinate ascent over the 7 mod slots."""
    by_slot: dict[str, list[dict]] = {s: [] for s in MOD_SLOTS}
    for m in pool:
        if m["slot"] in by_slot:
            by_slot[m["slot"]].append(m)
    chosen: dict[str, dict | None] = {s: None for s in MOD_SLOTS}
    if fixed:
        chosen.update(fixed)

    def score(ch):
        return evaluate(weapon, wstate, [m for m in ch.values() if m], set_counts, psi, scenario, extras=extras)["dps"]

    # Seed each slot independently (greedy), then refine.
    for _ in range(passes):
        changed = False
        for s in MOD_SLOTS:
            if fixed and s in fixed:
                continue
            cands = by_slot[s]
            if not cands:
                continue
            best_m, best_v = chosen[s], score(chosen)
            for m in prefilter(cands, weapon):
                trial = dict(chosen); trial[s] = m
                v = score(trial)
                if v > best_v * 1.0005:
                    best_m, best_v = m, v
            if best_m is not chosen[s]:
                chosen[s] = best_m; changed = True
        if not changed:
            break
    return chosen


def prefilter(cands: list[dict], weapon: dict, keep: int = 40) -> list[dict]:
    """Cheap relevance ordering so large pools stay fast."""
    kw = (weapon.get("keyword") or "").lower()

    def rel(m):
        text = (mod_core_text(m) + " " + m["variant"]).lower()
        r = m["level"] / MAX_MOD_LEVEL
        if kw and kw in text:
            r += 2
        if any(x in text for x in ["weapon dmg", "crit", "weakspot"]) and kw in {"shrapnel", "bounce", "fast gunner", "the bull's eye", "fortress warfare"}:
            r += 1
        if any(x in text for x in ["status dmg", "elemental", "psi"]) and kw in {"power surge", "burn", "frost vortex", "unstable bomber"}:
            r += 1
        return r
    return sorted(cands, key=rel, reverse=True)[:keep]


def pick_magazine(weapon, wstate, mods, set_counts, psi, scenario, extras, owned) -> dict:
    """Best owned magazine for this gun and build (keeps the equipped one when you haven't listed any)."""
    opts = [k for k in owned if forge_accessories.fits(k, weapon)]
    if not opts:
        return wstate
    cand = [None] + opts
    if wstate.get("magazine_acc") and wstate["magazine_acc"] not in cand:
        cand.append(wstate["magazine_acc"])
    best = max(cand, key=lambda k: evaluate(weapon, dict(wstate, magazine_acc=k), mods, set_counts, psi, scenario,
                                            extras=extras)["dps"])
    return dict(wstate, magazine_acc=best)


def magazine_choice(weapon, wstate, mods, set_counts, psi, scenario, extras, owned=(), overrides=None) -> dict:
    """Every magazine that fits this gun, scored on this exact build (calibration, mods, sets, food).

    Shows the reload-cycle math so the reason is visible: fire time, reload time, share of time spent
    reloading and, for guns with an "after reloading" zone, how much of the time the zone is up."""
    owned = set(owned or [])
    equipped = wstate.get("magazine_acc")
    rows = []
    for k in [None] + forge_accessories.compatible(weapon):
        st = dict(wstate, magazine_acc=k)
        r = evaluate(weapon, st, mods, set_counts, psi, scenario, extras=extras)
        d = r["derived"]
        m = forge_accessories.MAGAZINES.get(k) if k else None
        rows.append({"id": k, "name": m["name"] if m else "No magazine", "rarity": m["rarity"] if m else None,
                     "text": m["text"] if m else "Base magazine", "confirmed": True if not m else (m["confirmed"] or bool((overrides or {}).get(k))),
                     "source": m["source"] if m else None, "owned": k is None or k in owned, "equipped": k == equipped,
                     "dps": round(r["dps"]), "magazine": d["magazine"], "reload_s": d["reload_s"],
                     "fire_s": round(d["cycle_s"] - d["reload_s"], 2), "cycle_s": d["cycle_s"],
                     "uptime": d["uptime"], "zone_uptime": d.get("zone_uptime")})
    base = next(r for r in rows if r["id"] == equipped) if any(r["id"] == equipped for r in rows) else rows[0]
    for r in rows:
        r["vs_equipped_pct"] = round(100 * (r["dps"] / base["dps"] - 1), 1) if base["dps"] else 0
    rows.sort(key=lambda r: -r["dps"])
    top = rows[0]
    top_owned = next((r for r in rows if r["owned"]), None)
    # marginal value of one more round vs 1% more Reload Efficiency, from the reload-cycle formula
    ref = evaluate(weapon, wstate, mods, set_counts, psi, scenario, extras=extras)
    d = ref["derived"]
    fire_s, rel = d["cycle_s"] - d["reload_s"], d["reload_s"]
    why = []
    why.append(f"You shoot for {fire_s:.1f}s ({d['magazine']} rounds at {d['fire_rate_rpm']} RPM) then reload for {rel:.2f}s, "
               f"so {100 * rel / d['cycle_s']:.0f}% of the fight is spent reloading.")
    why.append("Extra rounds cut how often you reload; Reload Efficiency cuts each reload. On their own, with "
               f"{rel:.2f}s of reload against {fire_s:.1f}s of shooting, +10 rounds would be worth about "
               f"{100 * ((fire_s * (1 + 10 / max(1, d['magazine'])) / (fire_s * (1 + 10 / max(1, d['magazine'])) + rel)) / (fire_s / d['cycle_s']) - 1):.1f}% "
               f"and +10% Reload Efficiency about {100 * ((fire_s / (fire_s + rel / 1.10)) / (fire_s / d['cycle_s']) - 1):.1f}% of bullet uptime here.")
    for r in rows:
        mm = forge_accessories.MAGAZINES.get(r["id"] or "")
        st = forge_accessories.stats_for(r["id"], overrides) if mm else {}
        if st.get("reload_speed", 0) < 0 and (st.get("magazine_flat") or st.get("magazine")):
            delta = next((x["dps"] for x in rows if x["id"] is None), r["dps"])
            why.append(f"{mm['name']} adds rounds but also has Reload Efficiency {st['reload_speed']:g}%, so every reload gets slower; "
                       f"net it is {100 * (r['dps'] / delta - 1):+.1f}% against no magazine on this build.")
    if d.get("zone_uptime") is not None:
        zt = re.search(r"radius \d+m for (\d+(?:\.\d+)?)s", (weapon.get("effect_text") or "").lower())
        z = float(zt.group(1)) if zt else None
        if z:
            worst = max(rows, key=lambda r: r["cycle_s"])
            why.append(f"{weapon.get('effect_name') or 'The weapon'}'s zone appears on the first hit after each reload and lasts {z:g}s. "
                       + (f"Every magazine here keeps a reload cycle under {z:g}s (longest {worst['cycle_s']:.1f}s), so the zone never drops "
                          "and a bigger mag costs you nothing there."
                          if worst["cycle_s"] <= z else
                          f"With {worst['name']} the cycle is {worst['cycle_s']:.1f}s, longer than {z:g}s, so the zone is down "
                          f"{100 * (1 - (worst['zone_uptime'] or 0)):.0f}% of the time; that is counted in its DPS."))
    gap = (top["dps"] / rows[-1]["dps"] - 1) * 100 if rows[-1]["dps"] else 0
    if gap < 1.5:
        why.append(f"All options land within {gap:.1f}% of each other, so pick for feel (accuracy, mobility).")
    return {"weapon": weapon["name"], "equipped": equipped, "best": top["id"], "best_name": top["name"],
            "best_owned": top_owned and top_owned["id"], "best_owned_name": top_owned and top_owned["name"],
            "rows": rows, "why": why, "not_counted": [forge_accessories.NOT_COUNTED,
                                                    "Energy Style's auto-reload after taking damage is not counted.",
                                                    f"Base reload time is an estimate ({RELOAD_SECONDS.get(weapon.get('type') or '', 2.4)}s for this gun type); "
                                                    "type your timed reload on the Weapons page to sharpen it."],
            "estimate": True}


def build_summary(weapon, wstate, chosen, set_counts, psi, scenario, label=None, extras=None, config=None):
    mods = [m for m in chosen.values() if m]
    res = evaluate(weapon, wstate, mods, set_counts, psi, scenario, extras=extras)
    return {
        "label": label,
        "weapon": {"name": weapon["name"], "keyword": weapon.get("keyword"), "stars": wstate.get("stars"),
                   "tier": wstate.get("tier", 5), "type": weapon.get("type"), "effect_name": weapon.get("effect_name"),
                   "effect_text": weapon.get("effect_text"), "source_url": weapon.get("source_url")},
        "mods": {s: (None if not m else {"name": m["name"], "variant": m["variant"], "level": m["level"],
                                          "tiers": m["tiers"], "owned": m.get("owned", False),
                                          "core": mod_core_text(m), "shiny": bool(m.get("shiny"))}) for s, m in chosen.items()},
        "sets": set_counts,
        "config": config or {},
        "dps": round(res["dps"]),
        "magazine_acc": wstate.get("magazine_acc"),
        "result": res,
    }


def profile_cfg(profile: dict) -> dict:
    cfg = dict(profile.get("extras") or {})
    cfg.setdefault("deviation_level", 5)
    keys = [fx.KEY_ARMOR_ALIASES.get(p.get("name"), p.get("name")) for p in (profile.get("armor") or {}).values()]
    keys = [k for k in keys if k in fx.KEY_ARMOR]
    cfg["key_armor"] = keys[0] if keys else None
    cfg["calibration"] = None  # per-weapon calibration lives on the weapon
    if "vuln_amp" not in cfg:
        try:
            cfg["vuln_amp"] = any(m.get("name") == "Vulnerability Amplifier" for m in owned_mods(profile))
        except Exception:
            cfg["vuln_amp"] = False
    return cfg


def effort_cfg(cfg: dict, scenario: str, profile: dict | None = None) -> dict:
    """Apply the play-effort level: Koala never swaps to mark and ignores fiddly hide conditions.
    Try-hard marks the boss only if you own a Bull's Eye gun (or already said a teammate does it)."""
    e = fe.EFFORTS[fe.split_key(scenario)[1]]
    cfg = dict(cfg)
    if e.get("marked") is False:
        cfg["marked"] = False
    elif e.get("marked") is True:
        owns = any(w.get("name") in fx.MARKER_NAMES for w in ((profile or {}).get("weapons") or []))
        cfg["marked"] = bool(cfg.get("marked")) or owns
    if e.get("hide_cond") is not None:
        cfg["hide_cond"] = list(e["hide_cond"])
    if e.get("hide_cond_add"):
        cfg["hide_cond"] = sorted(set(cfg.get("hide_cond") or []) | set(e["hide_cond_add"]))
    return cfg


_FOOD_CACHE: dict = {}


def auto_cfg(profile: dict, weapon: dict, scenario: str) -> dict:
    """profile_cfg, with the best food and drink for this weapon and your class filled in.

    Food is cheap to cook, so by default the optimizer picks it for you. Set extras.auto_food = false to
    count only what you marked as eaten.
    """
    cfg = effort_cfg(profile_cfg(profile), scenario, profile)
    cfg["weapon"] = weapon.get("name")
    cfg = cradle_cfg(cfg, weapon, scenario)
    if cfg.get("auto_food") is False:
        return cfg
    kw, cls = weapon.get("keyword"), cfg.get("class") or "freelancer"
    key = (weapon["name"], cls, scenario, cfg.get("deviation"), cfg.get("deviation_level"), bool(cfg.get("marked")),
           cfg.get("key_armor"), cfg.get("mask_hide"), cfg.get("vuln_amp"), tuple(sorted(cfg.get("hide_cond") or [])),
           cfg.get("map"), json.dumps(cfg.get("cradle"), sort_keys=True))
    if key not in _FOOD_CACHE:
        st = {"name": weapon["name"], "stars": 6, "tier": 5}
        def score(names):
            return evaluate(weapon, st, [], {}, 600, scenario, extras=fx.build_extras(dict(cfg, consumables=names), kw, scenario))["dps"]
        _FOOD_CACHE[key] = fx.best_consumables(score, cls)[1]
    return dict(cfg, consumables=list(_FOOD_CACHE[key]), food_auto=True)


_CRADLE_CACHE: dict = {}


def cradle_cfg(cfg: dict, weapon: dict, scenario: str) -> dict:
    """Fill in suggested Cradle overrides when your map has a Cradle and you haven't picked yours.
    The pick compares real DPS per row for this weapon (labeled as a suggestion in the notes)."""
    import forge_cradle as fc
    m = fc.map_info(cfg.get("map"))
    if not m or not m["cradle"] or fc.picks_of(cfg) or fe.split_key(scenario)[0] == "abyss":
        return cfg
    kw = weapon.get("keyword")
    key = (weapon.get("name"), cfg.get("map"), scenario, cfg.get("deviation"), bool(cfg.get("marked")))
    if key not in _CRADLE_CACHE:
        st = {"name": weapon["name"], "stars": 6, "tier": 5}
        base = dict(cfg, cradle=[])
        def score(names):
            return evaluate(weapon, st, [], {}, 600, scenario,
                            extras=fx.build_extras(dict(base, cradle=names), kw, scenario))["dps"]
        _CRADLE_CACHE[key] = fc.auto_pick(cfg.get("map"), weapon.get("type"), kw, cfg, scenario, score=score)
    return dict(cfg, cradle=list(_CRADLE_CACHE[key]), cradle_auto=True)


def owned_extras(profile: dict, weapon: dict, scenario: str) -> list:
    return fx.build_extras(auto_cfg(profile, weapon, scenario), weapon.get("keyword"), scenario)


def wearing_now(profile, weapons, pool, set_counts, psi, scenario, best):
    """Your gear exactly as it is right now (the mods you said are on each piece), so the app can say
    what to swap. extras.equipped = {"helmet": {name, variant, level}, ..., "weapon": {...}};
    extras.equipped_weapon = the gun in your hands (defaults to your only gun)."""
    ex = profile.get("extras") or {}
    eq = {k.lower(): v for k, v in (ex.get("equipped") or {}).items() if isinstance(v, dict) and v.get("name")}
    names = [w["name"] for w in weapons]
    gun = ex.get("equipped_weapon") if ex.get("equipped_weapon") in names else (names[0] if len(names) == 1 else None)
    if not eq and not gun:
        return None
    out = {"weapon": gun, "slots": {s: eq.get(s) for s in MOD_SLOTS}, "empty": [s for s in MOD_SLOTS if s not in eq]}
    if not gun:
        out["note"] = "Pick the gun you are using to see the damage of your gear right now."
        return out
    gd = gamedata()
    w = gd["weapons"][gun]
    ws = next(x for x in weapons if x["name"] == gun)
    by = {(m["name"].lower(), m["variant"].lower()): m for m in pool}
    chosen = {}
    for s, e in eq.items():
        m = by.get((e["name"].lower(), (e.get("variant") or "General").lower()))
        if m and m["slot"] == s:
            lvl = max(1, min(MAX_MOD_LEVEL, int(e.get("level") or m["level"])))
            chosen[s] = m if lvl == m["level"] else dict(m, level=lvl, tiers=tiers_from_level(lvl), tiers_observed=False)
    ext = owned_extras(profile, w, scenario)
    b = build_summary(w, ws, {s: chosen.get(s) for s in MOD_SLOTS}, set_counts, psi, scenario, "Wearing now", extras=ext,
                      config=_public_cfg(auto_cfg(profile, w, scenario)))
    out.update(dps=b["dps"], build=b)
    if best:
        out["best_dps"] = best["dps"]
        out["gain_pct"] = round((best["dps"] / b["dps"] - 1) * 100, 1) if b["dps"] else None
        swaps = []
        if best["weapon"]["name"] != gun:
            swaps.append({"slot": "gun", "now": gun, "to": best["weapon"]["name"]})
        for s in MOD_SLOTS:
            bm, cm = (best.get("mods") or {}).get(s), chosen.get(s)
            if bm and (not cm or (bm["name"], bm["variant"]) != (cm["name"], cm["variant"])):
                swaps.append({"slot": s, "now": f"{cm['name']} ({cm['variant']}, Lv {cm['level']})" if cm else None,
                              "to": f"{bm['name']} ({bm['variant']}, Lv {bm['level']})"})
        out["swaps"] = swaps
    return out


SAVIOR_SHIELD_UPTIME = 0.9  # estimate: shield refreshed on hit while firing; drops while reloading or out of combat
ARMOR_SLOT_NAMES = ["Helmet", "Mask", "Top", "Gloves", "Bottoms", "Shoes"]


def best_owned_armor(profile, weapons, pool, scenario, current, keep_best, top_sets=8):
    """The best armor you could wear from pieces you own (not just what you have on), with its best mods.

    Search: every owned key armor (or none) x set combos (one set, two sets 4+2 / 3+3 / 2+2, three sets 2+2+2)
    among your 8 most useful sets, filled with your highest-star pieces; each scored with the current best mods,
    then the top layouts get a single-slot polish and a full mod re-pick on your top 3 guns."""
    gd = gamedata()
    oa = owned_armor(profile)
    if not oa or not current:
        return None
    by_slot = {s: [] for s in ARMOR_SLOT_NAMES}
    for n, o in oa.items():
        if o.get("slot") in by_slot:
            by_slot[o["slot"]].append({"name": n, "stars": o["stars"], "set": o.get("set"), "key": n in fx.KEY_ARMOR})
    for v in by_slot.values():
        v.sort(key=lambda x: (-x["stars"], x["name"]))
    worn = {s: (p or {}).get("name") for s, p in (profile.get("armor") or {}).items()}
    set_slots: dict[str, list] = {}
    for s, v in by_slot.items():
        for x in v:
            if x["set"] and x["set"] in gd["sets"]:
                set_slots.setdefault(x["set"], []).append(s)
    if not set_slots:
        return None
    w0 = gd["weapons"][keep_best["weapon"]["name"]]
    ws0 = next(x for x in weapons if x["name"] == w0["name"])
    mods0 = _mods_from_summary(keep_best, pool)

    def prof_for(layout):
        arm = {s: {"name": x["name"], "stars": x["stars"], "tier": 5} for s, x in layout.items() if x}
        return dict(profile, armor=arm, psi_intensity=profile.get("psi_intensity"))

    def quick(layout):
        p2 = prof_for(layout)
        sc = set_counts_from_profile(p2)
        psi, _ = estimate_psi(p2, sc)
        return evaluate(w0, ws0, mods0, sc, psi, scenario, extras=owned_extras(p2, w0, scenario))["dps"]

    def piece(slot, setname):
        return next((x for x in by_slot[slot] if x["set"] == setname), None)

    def filler(slot, taken_sets):
        v = by_slot[slot]
        return v[0] if v else None

    def layout_for(combo, key):
        lay, used = {}, set()
        if key:
            lay[key[0]] = key[1]; used.add(key[0])
        for setname, n in sorted(combo.items(), key=lambda kv: -kv[1]):
            others = {o for o in combo if o != setname}
            cands = [s for s in ARMOR_SLOT_NAMES if s not in used and piece(s, setname)]
            cands.sort(key=lambda s: (-piece(s, setname)["stars"], sum(1 for o in others if piece(s, o))))
            if len(cands) < n:
                return None
            for s in cands[:n]:
                lay[s] = piece(s, setname); used.add(s)
        for s in ARMOR_SLOT_NAMES:
            if s not in lay:
                lay[s] = filler(s, combo)
        return lay

    # rank sets by what 4 (or all owned) pieces alone would do
    single = []
    for setname, sl in set_slots.items():
        lay = layout_for({setname: min(4, len(sl))}, None)
        if lay:
            single.append((quick(lay), setname))
    single.sort(reverse=True)
    worn_sets = set(set_counts_from_profile(profile))
    pick = [n for _, n in single[:top_sets]] + [n for n in worn_sets if n not in [x for _, x in single[:top_sets]]]
    combos = [{}]
    for a in pick:
        combos.append({a: min(4, len(set_slots[a]))})
        for b in pick:
            if b == a:
                continue
            for na, nb in ((4, 2), (3, 3), (2, 2), (4, 1), (3, 2)):
                if na < nb or (na == nb and a > b):
                    continue
                combos.append({a: na, b: nb})
    for i, a in enumerate(pick):
        for j, b in enumerate(pick[i + 1:], i + 1):
            for c in pick[j + 1:]:
                combos.append({a: 2, b: 2, c: 2})
    keys = [None] + [(s, x) for s in ARMOR_SLOT_NAMES for x in by_slot[s] if x["key"]]
    seen, scored = set(), []
    worn_layout = {s: next((x for x in by_slot[s] if x["name"] == worn.get(s)), None) for s in ARMOR_SLOT_NAMES}
    for key in keys:
        for combo in combos:
            lay = layout_for(combo, key)
            if not lay:
                continue
            sig = tuple((lay[s] or {}).get("name") for s in ARMOR_SLOT_NAMES)
            if sig in seen:
                continue
            seen.add(sig)
            scored.append((quick(lay), sig, lay))
    sig0 = tuple((worn_layout[s] or {}).get("name") for s in ARMOR_SLOT_NAMES)
    if sig0 not in seen:
        scored.append((quick(worn_layout), sig0, worn_layout))
    scored.sort(key=lambda t: -t[0])

    def polish(lay, d):  # try every owned piece in every slot, keep improvements
        for _ in range(2):
            better = False
            for s in ARMOR_SLOT_NAMES:
                for x in by_slot[s]:
                    if lay.get(s) and x["name"] == lay[s]["name"]:
                        continue
                    trial = dict(lay, **{s: x})
                    t = quick(trial)
                    if t > d + 1e-6:
                        lay, d, better = trial, t, True
            if not better:
                break
        return lay, d

    finals = []
    for d, sig, lay in scored[:6]:
        finals.append(polish(dict(lay), d)[0])
    guns = [gd["weapons"][b["weapon"]["name"]] for b in current[:3]]
    best = None
    for lay in finals:
        p2 = prof_for(lay)
        sc = set_counts_from_profile(p2)
        psi, _ = estimate_psi(p2, sc)
        for w in guns:
            ws = next(x for x in weapons if x["name"] == w["name"])
            ex = owned_extras(p2, w, scenario)
            chosen = best_mods_for(w, ws, pool, sc, psi, scenario, extras=ex)
            b = build_summary(w, ws, chosen, sc, psi, scenario, "Best armor you own", extras=ex,
                              config=_public_cfg(auto_cfg(p2, w, scenario)))
            if not best or b["dps"] > best[0]["dps"]:
                best = (b, lay)
    if not best:
        return None
    b, lay = best
    base = keep_best["dps"] or 1
    changes = [{"slot": s, "now": worn.get(s), "to": (lay.get(s) or {}).get("name"), "stars": (lay.get(s) or {}).get("stars")}
               for s in ARMOR_SLOT_NAMES if (lay.get(s) or {}).get("name") != worn.get(s)]
    gain = round((b["dps"] / base - 1) * 100, 1)
    return {"dps": b["dps"], "gain_pct": gain, "same": not changes or gain < 0.5,
            "armor": {s: ({"name": x["name"], "stars": x["stars"], "set": x["set"], "key": x["key"]} if x else None) for s, x in lay.items()},
            "changes": changes, "build": b, "layouts_checked": len(scored),
            "note": "Searched every armor piece you own. Stars are what you entered; untested sets and 1-piece bonuses are counted only where the app models them."}


_OPT_CACHE: dict = {}
_OPT_LOCK = __import__("threading").Lock()


def _inputs_stamp() -> tuple:
    """Everything optimize() reads besides the profile: the database, typed-in/live data and the game data."""
    out = [id(gamedata())]
    for p in (DB, Path(str(DB) + "-wal"), SNAPSHOT, SUPPLEMENT):
        try:
            st = p.stat(); out.append((st.st_mtime_ns, st.st_size))
        except OSError:
            out.append(None)
    try:
        out.append(tuple(sorted((f.name, f.stat().st_mtime_ns) for f in fl.LIVE.glob("*.json"))))
    except OSError:
        out.append(None)
    return tuple(out)


def optimize(profile: dict | None = None) -> dict:
    """Best build + upgrades. Remembers the last answers, so reopening the page is instant until
    the profile, inventory or game data changes."""
    import copy
    profile = profile or load_profile()
    key = (json.dumps(profile, sort_keys=True, default=str), _inputs_stamp())
    with _OPT_LOCK:
        if key not in _OPT_CACHE:
            if len(_OPT_CACHE) >= 6:
                _OPT_CACHE.pop(next(iter(_OPT_CACHE)))
            _OPT_CACHE[key] = _optimize(copy.deepcopy(profile))
        return copy.deepcopy(_OPT_CACHE[key])


def _optimize(profile: dict) -> dict:
    gd = gamedata()
    scenario = fe.split_key(profile.get("scenario"))[0]
    effort = (profile.get("extras") or {}).get("effort") or "normal"
    if effort in fe.EFFORTS and effort != "normal":
        scenario = f"{scenario}@{effort}"
    pool = owned_mods(profile)
    weapons = owned_weapons(profile)
    set_counts = set_counts_from_profile(profile)
    psi, psi_basis = estimate_psi(profile, set_counts)
    notes = []
    if not profile.get("armor"):
        notes.append("No armor recorded: set bonuses are not counted and Psi Intensity is assumed. "
                     "Add your armor or Psi Intensity on the Armor page for a real number.")
    if not weapons:
        notes.append("No weapons recorded yet. Add the guns you own on the Weapons page.")

    current, inner = [], {}
    owned_acc = list(profile.get("accessories_owned") or [])
    for ws in weapons:
        w = gd["weapons"][ws["name"]]
        ex = owned_extras(profile, w, scenario)
        chosen = best_mods_for(w, ws, pool, set_counts, psi, scenario, extras=ex)
        ws_best = pick_magazine(w, ws, [m for m in chosen.values() if m], set_counts, psi, scenario, ex, owned_acc)
        b = build_summary(w, ws_best, chosen, set_counts, psi, scenario, "Best with what you own", extras=ex,
                          config=_public_cfg(auto_cfg(profile, w, scenario)))
        current.append(b)
        inner[w["name"]] = (w, ws, chosen, ex)
    current.sort(key=lambda b: b["dps"], reverse=True)
    best = current[0] if current else None
    for b in current[:4]:
        w, ws, chosen, ex = inner[b["weapon"]["name"]]
        try:
            b["magazine"] = magazine_choice(w, ws, [m for m in chosen.values() if m], set_counts, psi, scenario, ex,
                                            owned_acc, profile.get("accessory_values"))
        except Exception as e:  # never break the main answer
            b["magazine"] = {"error": str(e)}
    wearing = wearing_now(profile, weapons, pool, set_counts, psi, scenario, best)
    try:
        best_armor = best_owned_armor(profile, weapons, pool, scenario, current, best) if best else None
    except Exception as e:  # never break the main answer
        best_armor = {"error": str(e)}

    upgrades = next_upgrades(profile, best, pool, set_counts, psi, scenario, weapons) if best else []
    ladder = top_ladder(scenario, bool((profile.get("extras") or {}).get("marked")), best, upgrades)
    secondary = secondary_advice(profile, best, weapons, scenario) if best else None
    if secondary and not secondary["marked_on"] and not secondary["primary_marks"]:
        g = secondary["dps_amp"] if secondary["has_amp"] else secondary["dps_mark"]
        name = secondary["pick"] or "AWS.338 - Bullseye or DE.50 - Wildfire"
        cost = 0 if secondary["pick"] else weapon_cost(1)
        up = _upg("secondary", f"Carry {name} as secondary and mark the boss", g, best["dps"], cost,
                  "One shot with the secondary puts The Bull's Eye on the boss (+8% damage taken"
                  + (", +16% with your Vulnerability Amplifier on the secondary" if secondary["has_amp"] else "")
                  + "), then swap back. Turn on 'Bull's Eye kept on target' once you do this.", None)
        gun = secondary["pick"] or next((n for n in fx.MARKER_NAMES if n in gd["weapons"]), None)
        up["action"] = {"extras": {"marked": True}, **({"weapon": gun, "secondary": True} if gun and not secondary["pick"] else {})}
        budget = profile.get("starchrom")
        up["affordable"] = None if budget is None else cost <= budget
        upgrades = sorted(upgrades + [up], key=lambda r: -r["dps"])
    weapon_dps = {b["weapon"]["name"]: {"dps": b["dps"], "owned": True} for b in current}
    set_dps = {}
    for u in upgrades:
        if u["kind"] == "weapon" and u.get("build"):
            weapon_dps.setdefault(u["build"]["weapon"]["name"], {"dps": u["dps"], "owned": False, "cost": u["cost_starchrom"]})
        elif u["kind"] == "armor" and u["title"].startswith("Craft 4-piece "):
            set_dps[u["title"][len("Craft 4-piece "):]] = {"dps": u["dps"], "gain_pct": u["gain_pct"], "cost": u["cost_starchrom"]}
    starter = None
    if not weapons:
        try:
            import forge_starter
            starter = forge_starter.plan(profile, scenario, bool((profile.get("extras") or {}).get("marked")))
        except Exception as e:  # never break the main answer
            starter = {"error": str(e)}
    return {
        "starter": starter,
        "fresh": bool(profile.get("fresh")),
        "weapon_dps": weapon_dps,
        "set_dps": set_dps,
        "secondary": secondary,
        "ladder": ladder,
        "scenario": {"key": scenario, "effort": fe.split_key(scenario)[1],
                     "effort_label": fe.EFFORTS[fe.split_key(scenario)[1]]["label"],
                     **{k: v for k, v in fe.scn(scenario).items() if k != "vision"}},
        "psi": {"value": round(psi), "basis": psi_basis},
        "owned_counts": {"mods": len(pool), "weapons": len(weapons), "armor": len(profile.get("armor") or {}),
                         "armor_owned": len(owned_armor(profile))},
        "best": best,
        "wearing": wearing,
        "best_armor": best_armor,
        "alternatives": current[1:4],
        "upgrades": upgrades,
        "starchrom": profile.get("starchrom"),
        "notes": notes,
        "data": {"source": gd["source"], "retrieved_at": gd["retrieved_at"]},
    }


def top_ladder(scenario: str, marked: bool, best: dict | None, upgrades: list) -> dict | None:
    """Top 10 builds in the game (theory, max everything) and where your build lands among them."""
    try:
        import forge_theory
        th = forge_theory.theory(scenario, marked)
    except Exception as e:  # never break the main answer over the ladder
        return {"error": str(e)}
    ranking = th.get("ranking") or [{"weapon": b["weapon"]["name"], "dps": b["dps"]} for b in th["builds"]]
    rows = [{"weapon": b["weapon"]["name"], "keyword": b["weapon"].get("keyword"), "dps": b["dps"],
             "sets": b.get("sets"), "foods": [f["name"] for f in (b.get("config") or {}).get("consumables") or []],
             "deviation": ((b.get("config") or {}).get("deviation") or {}).get("name"),
             "key_armor": ((b.get("config") or {}).get("key_armor") or {}).get("name"),
             "mods": [{"slot": sl, "name": m["name"], "variant": m.get("variant")}
                      for sl in ["weapon"] + ARMOR_SLOTS for m in [(b.get("mods") or {}).get(sl)] if m]}
            for b in th["builds"][:10]]
    top = ranking[0]["dps"] if ranking else 0

    def place(dps):
        if dps is None:
            return None
        above = sum(1 for r in ranking if r["dps"] > dps)
        return {"dps": dps, "rank": above + 1, "of": len(ranking), "in_top10": above < 10,
                "pct_of_top": round(dps / top * 100, 1) if top else None,
                "beyond": above >= len(ranking)}
    you = place(best and best["dps"])
    if you and best:
        you["weapon"] = best["weapon"]["name"]
    nxt = None
    affordable = [u for u in upgrades if u.get("affordable") is not False]
    if affordable:
        u = max(affordable, key=lambda u: u["dps"])
        nxt = place(u["dps"]); nxt["title"] = u["title"]
    return {"top": rows, "you": you, "next": nxt, "basis": "Best possible builds: every weapon at 6 stars, every mod at "
            "level 17, max-roll calibration, best food for a Chef. Ranks are estimates.", "scenario": scenario}


def _public_cfg(cfg):
    out = {}
    for field, table in (("key_armor", fx.KEY_ARMOR), ("deviation", fx.DEVIATIONS)):
        n = cfg.get(field)
        out[field] = n and table.get(n) and {"name": n, "text": table[n]["text"], "source": table[n]["source"],
                                             "approx": table[n].get("approx")}
    out.update(public_consumables(cfg))
    out["food_auto"] = bool(cfg.get("food_auto"))
    out["marked"] = bool(cfg.get("marked"))
    cal = cfg.get("calibration")
    out["calibration"] = cal and {"label": cal.get("label"), "source": cal.get("source")}
    out.update(public_cradle(cfg))
    return out


def public_cradle(cfg: dict) -> dict:
    import forge_cradle as fc
    m = fc.map_info(cfg.get("map"))
    return {"map": cfg.get("map"), "map_label": m and m["label"], "has_cradle": bool(m and m["cradle"]),
            "cradle": [p["name"] for p in fc.picks_of(cfg)], "cradle_auto": bool(cfg.get("cradle_auto")),
            "cradle_skipped": fc.skipped(cfg)}


def public_consumables(cfg: dict) -> dict:
    kept, _ = fx.fit_consumables(fx.consumables_of(cfg), cfg.get("class"))
    cls = cfg.get("class") or "freelancer"
    return {"class": {"key": cls, **{k: v for k, v in fx.CLASSES.get(cls, fx.CLASSES["freelancer"]).items()}},
            "consumables": [{"name": n, "slot": fx.slot_label(fx.CONSUMABLES[n]), "text": fx.CONSUMABLES[n]["text"],
                             "source": fx.CONSUMABLES[n]["source"], "approx": fx.CONSUMABLES[n].get("approx")} for n in kept]}


# ---------------------------------------------------------------- upgrades
def armor_cost(pieces: int, stars: int = 1) -> int:
    star_cost = sum(v for k, v in STARCHROM["armor_legendary_stars"].items() if k <= stars)
    return pieces * (STARCHROM["armor_legendary_unlock"] + star_cost)


def weapon_cost(stars: int = 1) -> int:
    return STARCHROM["weapon_legendary_unlock"] + sum(v for k, v in STARCHROM["weapon_legendary_stars"].items() if k <= stars)


def owned_armor(profile: dict) -> dict[str, dict]:
    """Every armor piece you own: your list plus whatever you are wearing. name -> {stars, slot, set, worn}."""
    gd = gamedata()
    out = {}
    for name, v in (profile.get("armor_owned") or {}).items():
        a = gd["armor"].get(name)
        if a or name in fx.KEY_ARMOR:
            out[name] = {"stars": int((v or {}).get("stars") or 1), "slot": (a or {}).get("slot"),
                         "set": set_key(a) if a and name not in fx.KEY_ARMOR else None, "worn": False}
    for slot, piece in (profile.get("armor") or {}).items():
        n = (piece or {}).get("name")
        if not n:
            continue
        a = gd["armor"].get(n)
        o = out.setdefault(n, {"stars": int(piece.get("stars") or 1), "slot": slot,
                               "set": set_key(a) if a and n not in fx.KEY_ARMOR else None})
        o["worn"] = True
        o["stars"] = max(o["stars"], int(piece.get("stars") or 1))
    return out


def owned_set_slots(profile: dict) -> dict[str, set]:
    """set name -> the slots where you own a piece of it."""
    res: dict[str, set] = {}
    for n, o in owned_armor(profile).items():
        if o.get("set"):
            res.setdefault(o["set"], set()).add(o["slot"])
    return res


def pieces_to_get(profile: dict, combo: dict) -> tuple[int, dict]:
    """How many pieces you still need for an armor combo like {"Lonewolf": 4, "Agent": 2}, using what you own.
    Each set gets its own slots (bigger set first); returns (missing, {set: owned_used})."""
    have = owned_set_slots(profile)
    used: set = set()
    missing, owned_used = 0, {}
    for name, n in sorted(combo.items(), key=lambda kv: -kv[1]):
        slots = [s for s in sorted(have.get(name, set())) if s not in used][:n]
        used |= set(slots)
        owned_used[name] = len(slots)
        missing += max(0, n - len(slots))
    return missing, owned_used


def _armor_title(set_name: str, combo: dict, missing: int, owned_used: dict) -> str:
    own = owned_used.get(set_name, 0)
    if missing == 0:
        return f"Wear 4-piece {set_name} (you own the pieces)"
    if own:
        return f"Craft {missing} more {set_name} piece{'s' if missing != 1 else ''} for 4-piece (you own {own})"
    return f"Craft 4-piece {set_name}"


def set_options(current_counts: dict) -> list[tuple[str, dict[str, int], int]]:
    """Armor set combos to test: 4pc of a set (+ keep up to 2 current pieces)."""
    gd = gamedata()
    out = []
    for name, s in gd["sets"].items():
        if len(s["pieces"]) < 4:
            continue
        have = current_counts.get(name, 0)
        need4 = max(0, 4 - have)
        if need4:
            combo = {name: 4}
            for other, c in current_counts.items():
                if other != name and c >= 2:
                    combo[other] = 2
            out.append((name, combo, need4))
        need6 = max(0, len(s["pieces"]) - have)
        if len(s["effects"]) >= 4 and need6 and need6 != need4:
            pass
    return out


def next_upgrades(profile, best, pool, set_counts, psi, scenario, owned_ws) -> list[dict]:
    gd = gamedata()
    base_dps = best["dps"] or 1
    owned_names = {w["name"] for w in owned_ws}
    cur_w = gd["weapons"][best["weapon"]["name"]]
    cur_state = next(w for w in owned_ws if w["name"] == cur_w["name"])
    results = []
    ex_cur = owned_extras(profile, cur_w, scenario)

    # 1) Stars on the current weapon
    if (cur_state.get("stars") or 1) < 6:
        st = dict(cur_state, stars=6)
        mods = [m for m in _mods_from_summary(best, pool)]
        dps = evaluate(cur_w, st, mods, set_counts, psi, scenario, extras=ex_cur)["dps"]
        cost = sum(v for k, v in STARCHROM["weapon_legendary_stars"].items() if k > (cur_state.get("stars") or 1))
        results.append(_upg("stars", f"Star up {cur_w['name']} to 6★", dps, base_dps, cost,
                            "Needs blueprint fragments from duplicate drops plus Starchrom.", None))
        results[-1]["action"] = {"stars": cur_w["name"]}

    # 2) Every other legendary weapon at 1★ with your owned mods
    for name, w in gd["weapons"].items():
        if name in owned_names or not w.get("legendary"):
            continue
        st = {"name": name, "stars": 1, "tier": 5, "calibration": None}
        exw = owned_extras(profile, w, scenario)
        chosen = best_mods_for(w, st, pool, set_counts, psi, scenario, passes=1, extras=exw)
        b = build_summary(w, st, chosen, set_counts, psi, scenario, extras=exw)
        results.append(_upg("weapon", f"Get {name}", b["dps"], base_dps, weapon_cost(1),
                            f"{w.get('keyword') or ''} weapon, rebuilt with mods you already own.", b))
        results[-1]["action"] = {"weapon": name}

    # 3) Armor sets (4pc) on the current weapon
    for set_name, combo, pieces in set_options(set_counts):
        chosen = best_mods_for(cur_w, cur_state, pool, combo, psi, scenario, passes=1, extras=ex_cur)
        b = build_summary(cur_w, cur_state, chosen, combo, psi, scenario, extras=ex_cur)
        pieces, own_used = pieces_to_get(profile, combo)
        results.append(_upg("armor", _armor_title(set_name, combo, pieces, own_used), b["dps"], base_dps, armor_cost(pieces) if pieces else 0,
                            "; ".join(f"{k}pc: {v}" for k, v in list(gd['sets'][set_name]['effects'].items())[:4]), b))
        results[-1]["action"] = {"set": set_name, "combo": combo}

    # 4) Mods you don't own yet, at a typical level 10 roll
    have = {(m["name"].lower(), m["variant"].lower()) for m in pool}
    mods_now = _mods_from_summary(best, pool)
    for gm in gd["mods"].values():
        slot = gm.get("slot_key")
        if not slot:
            continue
        for variant in (gm.get("variant_substats") or {"General": []}):
            if (gm["name"].lower(), variant.lower()) in have:
                continue
            cand = {"name": gm["name"], "variant": variant, "slot": slot, "level": 10, "tiers": tiers_from_level(10), "owned": False}
            trial = [m for m in mods_now if m["slot"] != slot] + [cand]
            dps = evaluate(cur_w, cur_state, trial, set_counts, psi, scenario, extras=ex_cur)["dps"]
            if dps > base_dps * 1.01:
                results.append(_upg("mod", f"Find {gm['name']} ({variant})", dps, base_dps, 0,
                                    f"{slot.title()} mod. {mod_core_text(cand)[:140]}", None, slot=slot))
                results[-1]["action"] = {"mod": {"name": gm["name"], "variant": variant, "level": 10}}
    # keep the best mod per slot only
    best_mod_per_slot: dict[str, dict] = {}
    for r in [r for r in results if r["kind"] == "mod"]:
        if r["slot"] not in best_mod_per_slot or r["gain_pct"] > best_mod_per_slot[r["slot"]]["gain_pct"]:
            best_mod_per_slot[r["slot"]] = r
    results = [r for r in results if r["kind"] != "mod"] + list(best_mod_per_slot.values())

    # 4b) Food, drink, deviation, key armor, calibration, Bull's Eye support
    results += extra_upgrades(profile, cur_w, cur_state, mods_now, set_counts, psi, scenario, base_dps)

    # 5) Combined jump: best new weapon x best set
    weapons_ranked = sorted([r for r in results if r["kind"] == "weapon"], key=lambda r: -r["dps"])[:5]
    sets_ranked = set_options(set_counts)
    combos = []
    for wr in weapons_ranked:
        w = gd["weapons"][wr["title"][4:]]
        st = {"name": w["name"], "stars": 1, "tier": 5}
        for set_name, combo, pieces in sets_ranked:
            exw = owned_extras(profile, w, scenario)
            chosen = best_mods_for(w, st, pool, combo, psi, scenario, passes=1, extras=exw)
            b = build_summary(w, st, chosen, combo, psi, scenario, extras=exw)
            pieces, own_used = pieces_to_get(profile, combo)
            combos.append(_upg("combo", f"Get {w['name']} + 4-piece {set_name}"
                               + (" (you own the armor)" if not pieces else f" ({own_used.get(set_name, 0)} pieces owned)" if own_used.get(set_name) else ""),
                               b["dps"], base_dps, weapon_cost(1) + (armor_cost(pieces) if pieces else 0), "Full new build around a new weapon and set.", b))
            combos[-1]["action"] = {"weapon": w["name"], "set": set_name, "combo": combo}
    combos.sort(key=lambda r: -r["dps"])
    results += combos[:5]

    budget = profile.get("starchrom")
    for r in results:
        r["affordable"] = None if budget is None else r["cost_starchrom"] <= budget
        r["gain_per_10k"] = round(r["gain_pct"] / max(r["cost_starchrom"], 1) * 10000, 2) if r["cost_starchrom"] else None
    results.sort(key=lambda r: -r["dps"])
    return results


def effort_compare(profile: dict | None = None) -> dict:
    """Best build for Koala / Normal / Try-hard play, and how each one does when played at every effort."""
    profile = profile or load_profile()
    gd = gamedata()
    base = fe.split_key(profile.get("scenario"))[0]
    pool = owned_mods(profile)
    weapons = owned_weapons(profile)
    sc = set_counts_from_profile(profile)
    psi, _ = estimate_psi(profile, sc)
    keys = {"easy": f"{base}@easy", "normal": base, "max": f"{base}@max"}
    if not weapons:
        return {"builds": {}, "efforts": fe.EFFORTS, "notes": ["Add a weapon you own first."]}

    def play(w, ws, chosen, eff):
        k = keys[eff]
        return evaluate(w, ws, [m for m in chosen.values() if m], sc, psi, k, extras=owned_extras(profile, w, k))

    picked = {}
    for eff, k in keys.items():
        best = None
        for ws in weapons:
            w = gd["weapons"][ws["name"]]
            chosen = best_mods_for(w, ws, pool, sc, psi, k, extras=owned_extras(profile, w, k))
            d = play(w, ws, chosen, eff)["dps"]
            if not best or d > best[0]:
                best = (d, w, ws, chosen)
        picked[eff] = best
    top = picked["max"][0] or 1
    out = {}
    for eff, (d, w, ws, chosen) in picked.items():
        at = {e: round(play(w, ws, chosen, e)["dps"]) for e in keys}
        res = play(w, ws, chosen, eff)
        out[eff] = {
            "weapon": w["name"], "keyword": w.get("keyword"), "stars": ws.get("stars"),
            "mods": {s2: (None if not m else {"name": m["name"], "variant": m["variant"], "level": m["level"]}) for s2, m in chosen.items()},
            "dps": round(d), "pct_of_max": round(d / top * 100, 1), "played_at": at,
            "conditions": sorted({c for c in (res.get("conditions") or []) if c})[:8] if isinstance(res.get("conditions"), list) else [],
        }
    # which mods change between the easy and the try-hard build
    diff = []
    e_m, m_m = out["easy"]["mods"], out["max"]["mods"]
    for slot in sorted(set(e_m) | set(m_m)):
        a, b = e_m.get(slot), m_m.get(slot)
        if (a or {}).get("name") != (b or {}).get("name") or (a or {}).get("variant") != (b or {}).get("variant"):
            diff.append({"slot": slot, "easy": a, "max": b})
    easy_pct = out["easy"]["pct_of_max"]
    lazy_max = round(out["max"]["played_at"]["easy"] / top * 100, 1)
    koala_hard = round(out["easy"]["played_at"]["max"] / top * 100, 1)
    lazy_loss = round((1 - out["max"]["played_at"]["easy"] / max(out["easy"]["dps"], 1)) * 100, 1)
    play_gain = round((out["easy"]["played_at"]["max"] / max(out["easy"]["dps"], 1) - 1) * 100, 1)
    same = out["easy"]["weapon"] == out["max"]["weapon"] and not diff
    if same:
        verdict = (f"Same gear either way. All of the difference (+{play_gain}%) comes from how you play, "
                   "not from what you wear.")
    elif koala_hard >= 97:
        verdict = (f"Wear the Koala build. Played easy it beats the try-hard gear by {lazy_loss}%, and even if you "
                   f"play hard it still reaches {koala_hard}% of the max. The extra damage comes from playing harder "
                   f"(+{play_gain}%), not from swapping gear.")
    else:
        verdict = (f"The try-hard gear is worth {round(100 - koala_hard, 1)}% more, but only if you really play it that way. "
                   f"Played easy it does {lazy_loss}% less than the Koala build.")
    return {
        "builds": out, "diff": diff, "verdict": verdict, "lazy_max_pct": lazy_max, "koala_hard_pct": koala_hard,
        "play_gain_pct": play_gain, "lazy_loss_pct": lazy_loss,
        "efforts": {k: {kk: vv for kk, vv in v.items() if kk in ("label", "short", "desc")} for k, v in fe.EFFORTS.items()},
        "assumptions": {k: {kk: v["scn"].get(kk) for kk in ("weakspot_rate", "airborne", "low_hp", "moving")} | {"marks": v.get("marked")}
                        for k, v in fe.EFFORTS.items()},
        "notes": ["Estimates. Weakspot rate, time in the air and low-HP time are assumptions per effort level, not measured from your play.",
                  "Try-hard counts the Bull's Eye mark only if you own a marking gun or switched it on in settings."],
    }


def secondary_advice(profile: dict, best: dict, weapons: list, scenario: str) -> dict:
    """Which secondary weapon to carry: a Bull's Eye marker, measured on your best build."""
    gd = gamedata()
    w = gd["weapons"][best["weapon"]["name"]]
    ws = next((x for x in weapons if x["name"] == w["name"]), {"name": w["name"], "stars": 1, "tier": 5})
    mods = [m for m in (best.get("mods") or {}).values() if m] if isinstance(best.get("mods"), dict) else []
    pool = owned_mods(profile)
    if not mods:
        mods = list(best_mods_for(w, ws, pool, set_counts_from_profile(profile), estimate_psi(profile, set_counts_from_profile(profile))[0],
                                  scenario, extras=owned_extras(profile, w, scenario)).values())
        mods = [m for m in mods if m]
    sc = set_counts_from_profile(profile)
    psi = estimate_psi(profile, sc)[0]
    cfg = auto_cfg(profile, w, scenario)
    kw = w.get("keyword")

    def d(**k):
        return evaluate(w, ws, mods, sc, psi, scenario, extras=fx.build_extras(dict(cfg, **k), kw, scenario))["dps"]
    base, mark, amp = d(marked=False, vuln_amp=False), d(marked=True, vuln_amp=False), d(marked=True, vuln_amp=True)
    owned_names = {x["name"] for x in weapons}
    owned_markers = [n for n in fx.MARKER_NAMES if n in owned_names and n != w["name"]]
    pick = owned_markers[0] if owned_markers else None
    info = {m[0]: {"why": m[1], "src": m[2]} for m in fx.MARKERS}
    return {
        "primary": w["name"], "primary_marks": kw == "The Bull's Eye",
        "gain_pct": round((mark / base - 1) * 100, 1), "gain_amp_pct": round((amp / base - 1) * 100, 1),
        "dps_no_mark": round(base), "dps_mark": round(mark), "dps_amp": round(amp),
        "has_amp": bool(cfg.get("vuln_amp")), "marked_on": bool(cfg.get("marked")),
        "pick": pick, "owned_markers": owned_markers,
        "markers": [{"name": n, **info[n], "owned": n in owned_names, "icon": gd["weapons"].get(n, {}).get("icon")}
                    for n in fx.MARKER_NAMES if n in gd["weapons"]],
        "source": fx.SECONDARY_SRC,
    }


def extra_upgrades(profile, w, wstate, mods, set_counts, psi, scenario, base_dps) -> list[dict]:
    """Free or cheap power outside mods/sets: consumables, deviation, key armor, calibration."""
    cfg = auto_cfg(profile, w, scenario)
    kw = w.get("keyword")
    out = []

    def dps_with(c, sets=set_counts, st=wstate):
        return evaluate(w, st, mods, sets, psi, scenario, extras=fx.build_extras(c, kw, scenario))["dps"]

    # food & drink: best set that fits your class's slots, and what Chef's 2+2 would give
    cur_names, _ = fx.fit_consumables(fx.consumables_of(cfg), cfg.get("class"))

    def cons_score(cls):
        return lambda names: dps_with(dict(cfg, consumables=names, **{"class": cls}))

    def cons_text(names):
        return " + ".join(f"{n} ({fx.slot_label(fx.CONSUMABLES[n]).lower()})" for n in names)

    cls_now = cfg.get("class") or "freelancer"
    v, names = fx.best_consumables(cons_score(cls_now), cls_now)
    if names and sorted(names) != sorted(cur_names) and v > base_dps * 1.005:
        out.append(_upg("food", f"Eat and drink: {cons_text(names)}", v, base_dps, 0,
                        "Best food and drink for your class's slots (a food + drink dish uses one of each). "
                        + " ".join(f"{n}: {fx.CONSUMABLES[n]['text']}." for n in names), None))
        out[-1]["action"] = {"extras": {"consumables": list(names)}}
    if cls_now != "chef":
        v2, names2 = fx.best_consumables(cons_score("chef"), "chef")
        if names2 and v2 > max(v, base_dps) * 1.005:
            out.append(_upg("food", f"Play as Chef: {cons_text(names2)}", v2, base_dps, 0,
                            "Chef's Glutton trait keeps 2 food + 2 drink effects. Needs a class-change item, not Starchrom. "
                            f"Source: {fx.CLASS_NEWS}", None))
            out[-1]["action"] = {"extras": {"class": "chef", "consumables": list(names2)}}
    for field, table, kind, verb in (("deviation", fx.DEVIATIONS, "deviation", "Use deviation"),):
        best = None
        for name, item in table.items():
            if name == cfg.get(field) or item.get("unmodeled"):
                continue
            d = dps_with(dict(cfg, **{field: name}, deviation_level=5 if field == "deviation" else cfg.get("deviation_level", 5)))
            if d > base_dps * 1.005 and (not best or d > best[0]):
                best = (d, name, item)
        if best:
            d, name, item = best
            extra = " (skill level 5)" if field == "deviation" else ""
            out.append(_upg(kind, f"{verb} {name}{extra}", d, base_dps, 0,
                            f"{item['text']}. Source: {item['source']}", None))
            out[-1]["action"] = {"extras": {"deviation": name, "deviation_level": 5}}
    # key armor: replaces the piece in its slot (that piece stops counting toward its set)
    gd = gamedata()
    best = None
    for name, ka in fx.KEY_ARMOR.items():
        if name == cfg.get("key_armor") or ka.get("unmodeled") or not ka["stats"]:
            continue
        if not fx.key_armor_fits(name, kw, cfg.get("weapon")):
            continue
        slot = (gd["armor"].get(name) or {}).get("slot") or ka["slot"]
        prof2 = json.loads(json.dumps(profile))
        prof2.setdefault("armor", {})[slot] = {"name": name, "stars": 1, "tier": 5}
        d = dps_with(dict(cfg, key_armor=name), sets=set_counts_from_profile(prof2))
        if d > base_dps * 1.005 and (not best or d > best[0]):
            best = (d, name, ka, slot)
    if best:
        d, name, ka, slot = best
        have_it = name in owned_armor(profile)
        out.append(_upg("keyarmor", f"Wear {name} ({slot})" + (" (you own it)" if have_it else ""), d, base_dps, 0 if have_it else armor_cost(1),
                        f"Key armor: {ka['text']}. Replaces your {slot}; it does not count toward a set."
                        + (f" Estimate: {ka['approx']}." if ka.get("approx") else "") + f" Source: {ka['source']}", None, slot=slot))
        out[-1]["action"] = {"armor": {slot: name}}
    # mask hide: best hide for this build under the fight conditions you switched on
    best = None
    for name, h in fx.MASK_HIDES.items():
        if name == cfg.get("mask_hide") or h["unmodeled"]:
            continue
        d = dps_with(dict(cfg, mask_hide=name))
        if d > base_dps * 1.005 and (not best or d > best[0]):
            best = (d, name, h)
    if best:
        d, name, h = best
        out.append(_upg("hide", f"Craft your mask with {name}", d, base_dps, 0,
                        f"Mask hide: {h['text']}. Re-craft the mask with this hide (your blueprint stars stay). "
                        f"Hide rarity's Psi bonus is already in your typed Psi. Source: {fx.HIDE_SRC}", None, slot="Mask"))
        out[-1]["action"] = {"extras": {"mask_hide": name}}
    # calibration: best legendary roll for this weapon type
    best = None
    for opt in fx.calibration_options(w.get("type")):
        cal = {"style": opt["style"], "attack": fx.CAL_ATTACK_MAX, "sub": opt["sub"], "sub_value": fx.CAL_SUB_MAX[opt["sub"]]}
        d = dps_with(cfg, st=dict(wstate, calibration=cal))
        if not best or d > best[0]:
            best = (d, opt)
    if best and best[0] > base_dps * 1.01:
        out.append(_upg("calibration", f"Calibrate {w['name']}: {best[1]['label']}", best[0], base_dps, 0,
                        "Best legendary calibration roll for this weapon type (top of the range; real rolls are lower). "
                        f"Source: {fx.CAL_BLOG}", None))
        o = best[1]
        out[-1]["action"] = {"calibration": [w["name"], {"style": o["style"], "attack": fx.CAL_ATTACK_MAX, "sub": o["sub"],
                                                         "sub_value": fx.CAL_SUB_MAX[o["sub"]]}]}
    if not cfg.get("marked") and kw != "The Bull's Eye":
        d = dps_with(dict(cfg, marked=True))
        if d > base_dps * 1.01:
            out.append(_upg("deviation", "Keep The Bull's Eye on the target (secondary weapon or teammate)", d, base_dps, 0,
                            "Bull's Eye adds 8% vulnerability and turns on 'vs marked target' bonuses.", None))
            out[-1]["action"] = {"extras": {"marked": True}, "needs_team": True}
    return out


def _mods_from_summary(summary, pool):
    out = []
    for s, m in summary["mods"].items():
        if not m:
            continue
        match = next((p for p in pool if p["name"] == m["name"] and p["variant"] == m["variant"]), None)
        if match:
            out.append(match)
    return out


def _upg(kind, title, dps, base, cost, detail, build, slot=None):
    return {"kind": kind, "title": title, "dps": round(dps), "gain_pct": round((dps / base - 1) * 100, 1),
            "multiplier": round(dps / base, 2), "cost_starchrom": cost, "detail": detail, "slot": slot,
            "build": build}


if __name__ == "__main__":
    import sys
    r = optimize()
    print(json.dumps({k: r[k] for k in ["psi", "owned_counts", "notes"]}, indent=1))
    if r["best"]:
        b = r["best"]
        print("BEST", b["weapon"]["name"], b["dps"], b["result"]["breakdown"])
        for s, m in b["mods"].items():
            print("  ", s, m and f"{m['name']} ({m['variant']}) L{m['level']}")
    for u in r["upgrades"][:15]:
        print(f"{u['kind']:7} x{u['multiplier']:<5} {u['cost_starchrom']:>6}  {u['title']}")
    sys.exit(0)


def inventory(profile: dict) -> dict:
    """What the gear screen lists: owned weapons and mods after quick edits."""
    mods = sorted(({"name": m["name"], "variant": m["variant"], "slot": m["slot"], "level": m["level"],
                    "shiny": bool(m.get("shiny")), "shiny_main": m.get("shiny_main"), "shiny_extra": m.get("shiny_extra")}
                   for m in owned_mods(profile)), key=lambda m: (MOD_SLOTS.index(m["slot"]) if m["slot"] in MOD_SLOTS else 9, m["name"]))
    seen, weapons = set(), []
    for w in owned_weapons(profile):
        if w["name"] in seen:
            continue
        seen.add(w["name"])
        weapons.append({"name": w["name"], "stars": w["stars"], "source": w["source"], "calibration": w.get("calibration")
                        if (w.get("calibration") or {}).get("style") else None,
                        "magazine_acc": w.get("magazine_acc"), "reload_s": w.get("reload_s")})
    return {"mods": mods, "weapons": weapons}


@lru_cache(maxsize=1)
def icon_index() -> dict:
    p = ROOT / "gamedata" / "icons.json"
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return {}


@lru_cache(maxsize=1)
def icon_map() -> dict:
    """Item name -> local picture URL (only files that were downloaded)."""
    ix = icon_index()
    out: dict[str, str] = {}
    for kind in ("gear", "mods", "deviations", "consumables", "materials", "fallback"):
        for n, url in (ix.get(kind) or {}).items():
            if (ROOT / "static" / url.lstrip("/")).exists():
                out.setdefault(n, url)
                out.setdefault(n.lower(), url)
    for n, u in fl.live_icons().items():
        out.setdefault(n, u)
        out.setdefault(n.lower(), u)
    for n, f in fx.FOODS.items():
        if f.get("aka") and f["aka"] in out:
            out.setdefault(n, out[f["aka"]]); out.setdefault(n.lower(), out[f["aka"]])
    return out


def ui_catalog() -> dict:
    """Name lists for the 'My gear' form."""
    gd = gamedata()
    armor: dict[str, list[str]] = {}
    for name, a in gd["armor"].items():
        armor.setdefault(a.get("slot") or "other", []).append(name)
    mods = []
    for m in gd["mods"].values():
        mods.append({"name": m["name"], "slot": m.get("slot_key"), "variants": sorted((m.get("variant_substats") or {}).keys()),
                     "summary": m.get("summary") or ""})
    return {
        "weapons": sorted(gd["weapons"]),
        "armor": {k: sorted(v) for k, v in armor.items()},
        "mods": sorted(mods, key=lambda m: m["name"]),
        "scenarios": {k: v.get("label", k) for k, v in fe.SCENARIOS.items()},
        "efforts": {k: {"label": v["label"], "short": v["short"], "desc": v["desc"]} for k, v in fe.EFFORTS.items()},
        "weapon_family": {n: fx.weapon_family(w.get("type")) for n, w in gd["weapons"].items()},
        "weapon_info": {n: {"type": w.get("type"), "keyword": w.get("keyword"), "legendary": bool(w.get("legendary"))} for n, w in gd["weapons"].items()},
        "armor_info": {n: {"slot": a.get("slot"), "set": set_key(a) if n not in fx.KEY_ARMOR else None} for n, a in gd["armor"].items()},
        "icons": icon_map(),
        "sets": {k: {"effects": v.get("effects") or {}, "pieces": v.get("pieces") or {}} for k, v in gd["sets"].items()},
        "all_deviations": sorted(icon_index().get("deviations", {})),
        "extras": fx.catalog(),
        "cradle": __import__("forge_cradle").catalog(),
        "magazines": {"items": forge_accessories.public(), "not_counted": forge_accessories.NOT_COUNTED,
                      "reload_s": RELOAD_SECONDS},
        "crates": __import__("forge_crates").catalog(),
        **_new_classes(),
        "data_info": data_info(gd),
        "custom_scenarios": {k: {f: v.get(f) for f in ("label", "base", "buff_text", "buffs", "unparsed", "weakspot_rate",
                                                       "enemies_hit", "note", "source")}
                             for k, v in fe.SCENARIOS.items() if v.get("custom")},
        "typed": fl.overrides(),
        "dev_guide": __import__("forge_devguide").catalog(),
        "mod_art": __import__("forge_modart").catalog(mods),
    }


def _new_classes() -> dict:
    c = fl.classify()
    return {"new_marks": c["new"], "data_marks": c["data"], "scenario_marks": c["scenario"]}


def data_info(gd: dict | None = None) -> dict:
    gd = gd or gamedata()
    act = fl.active_snapshot()
    last = fl.read_json(fl.LIVE / "last_report.json", None) or {}
    news = fl.read_json(fl.NEWS, {})
    return {"retrieved_at": gd.get("retrieved_at"), "refreshed": act == fl.LIVE_SNAP, "app_version": fl.APP_VERSION,
            "last_check": last.get("finished"), "latest_post": news.get("latest"),
            "can_undo": bool(fl.HIST.exists() and any(fl.HIST.glob("*-before.*")))}


def reload_data() -> None:
    """Forget cached game data after the Update button (or Undo) swapped the data file."""
    for f in (gamedata, _core_text, catalog_mod_names, _mod_substats, icon_index, icon_map):
        f.cache_clear()
    fl.apply()
    try:
        import forge_theory
        forge_theory._CACHE.clear()
    except Exception:  # noqa: BLE001
        pass


def startup() -> None:
    """Called once by the server: count typed-in items and record first-seen dates (NEW! badges)."""
    fl.apply()
    try:
        fl.mark_seen(gamedata(), "app")
    except OSError:
        pass


fl.apply()
