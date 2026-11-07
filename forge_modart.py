"""Game-style mod screen data: variant glyph art, family emblems, and the in-game order.

Art comes from the classic app's static/artwork (artwork_manifest.json); order comes from the
game's Mods screen as recorded in static/mod-reference.js. Read-only; nothing here touches the game.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ART = ROOT / "static" / "artwork"
SLOT_ART = {"helmet": "helmet_mod", "top": "chest_mod", "bottoms": "pants_mod", "shoes": "boots_mod",
            "gloves": "gloves_mod", "mask": "mask_mod", "weapon": "weapon_mod"}
# the game's tab order on the Mods screen
GAME_SLOTS = ["weapon", "helmet", "top", "bottoms", "shoes", "gloves", "mask"]
WEAPON_FAMILIES = {
 "burn": [
  "Flame Resonance",
  "Embers",
  "Blaze Blessing",
  "Burning Wrath"
 ],
 "electric": [
  "Shock Rampage",
  "Shock Diffusion",
  "Static Shock",
  "Surge Amplifier"
 ],
 "frost": [
  "Shattering Ice",
  "Cryo Blast",
  "Cryo Catalyst",
  "Frosty Blessing"
 ],
 "bullseye": [
  "Recover Mark",
  "Hunter's Perk",
  "Spreading Marks",
  "Vulnerability Amplifier"
 ],
 "fortress_warfare": [
  "United We Stand",
  "Durable Territory",
  "Portable Territory",
  "Final Territory"
 ],
 "unstable_bomber": [
  "Super Charged",
  "Reckless Bomber",
  "Bombardier Souvenir",
  "Heavy Explosives"
 ],
 "fast_gunner": [
  "Shoot Out",
  "Precision Rush",
  "Shooting Blitz",
  "Cowboy"
 ],
 "bounce": [
  "Super Bullet",
  "Multi-Bounce",
  "Boomerang Bullet",
  "Bounce Rampage"
 ],
 "shrapnel": [
  "Shatter Them All",
  "Shrapnel Souvenir",
  "Shrapnel Smash",
  "Shield Breaker"
 ]
}
FAMILY_LABEL = {"burn": "Burn", "electric": "Power Surge", "frost": "Frost Vortex", "bullseye": "The Bull's Eye",
                "fortress_warfare": "Fortress Warfare", "unstable_bomber": "Unstable Bomber", "fast_gunner": "Fast Gunner",
                "bounce": "Bounce", "shrapnel": "Shrapnel"}
FAMILY_ICON = {"burn": "burn", "electric": "electric", "frost": "frost", "bullseye": "bullseye",
               "fortress_warfare": "fortress-warfare", "unstable_bomber": "unstable-bomber", "fast_gunner": "fast-gunner",
               "bounce": "bounce", "shrapnel": "shrapnel"}
ARMOR_ORDER = {
 "helmet_mod": [
  "Precise Strike",
  "Deviation Expert",
  "First-Move Advantage",
  "Mag Expansion",
  "Work of Proficiency",
  "Fortune's Favor",
  "Momentum Up",
  "Elemental Havoc",
  "Weapon Symphony",
  "Quick Toss"
 ],
 "chest_mod": [
  "Healing Fortification",
  "Quick Comeback",
  "Rejuvenating",
  "Critical Rescue",
  "Head-on Conflict",
  "Head Guard",
  "Resist Advantage",
  "Enduring Shield",
  "Status Immune",
  "Ardent Shield"
 ],
 "pants_mod": [
  "Critical Surge",
  "Precision Load",
  "Reload Rampage",
  "Three Strikes",
  "Bullet Siphon",
  "Deadshot",
  "Abnormal Increase",
  "Melee Momentum",
  "Distant Strike",
  "Precision Charge",
  "Elemental Resonance"
 ],
 "boots_mod": [
  "Slow and Steady",
  "Against All Odds",
  "Covered Advance",
  "Ruthless Reaper",
  "Rush Hour",
  "Ferocious Charge",
  "Secluded Strike",
  "Power of Striving"
 ],
 "gloves_mod": [
  "Weapon Amplifier",
  "Melee Amplifier",
  "Crit Boost",
  "Crit Amplifier",
  "Weakspot DMG Boost",
  "Lifeforce Boost",
  "Flame Resonance",
  "Elemental Overload",
  "Turret Enhancement"
 ],
 "mask_mod": [
  "Blaze Amplifier",
  "Frost Construct",
  "Explosive Shrapnel",
  "Precision Bounce",
  "Explosive Barrage",
  "Pinpoint Strike",
  "Targeted Strike",
  "Thunderclap",
  "Light Cannon",
  "Unbreakable",
  "Retrusion Explosion",
  "Shrapnel Carnage",
  "First Electrocution",
  "Frostwave Wither",
  "Most Wanted",
  "Break Bounce",
  "Blitzkrieg",
  "Delayed Blast"
 ]
}
# locked tiles in the game sit after the owned ones; base variants first, then the rarer suffix sets
VARIANT_ORDER = ["Violent", "Precision", "Deviant Energy", "Survival", "General", "Battle", "Lunar", "Crescent",
                 "Mirror", "Wild", "Phantasmal", "Downstar", "Resonant"]
ALIAS = {"resonant": "resonance", "violence": "violent"}


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


def _vslug(v: str) -> str:
    s = slug(v)
    for a, b in ALIAS.items():
        s = re.sub(rf"(^|-){a}(-|$)", rf"\g<1>{b}\g<2>", s)
    return s


def variant_rank(v: str) -> tuple:
    base = v.replace(" Deviant Energy", "") if v != "Deviant Energy" else v
    i = VARIANT_ORDER.index(base) if base in VARIANT_ORDER else 6
    return (v.endswith("Deviant Energy") and v != "Deviant Energy", i, v)


@lru_cache(maxsize=1)
def _files() -> dict:
    out = {}
    try:
        rec = json.loads((ROOT / "artwork_manifest.json").read_text()).get("records", {})
    except (OSError, ValueError):
        rec = {}
    for k, v in rec.items():
        p = v.get("local_path")
        if k.startswith("mod:") and p and (ROOT / "static" / p.lstrip("/")).exists():
            out[k] = p
    if ART.exists():
        for f in ART.iterdir():   # files on disk that the manifest doesn't list
            m = re.match(r"mod__([a-z_]+)__(.+)\.png$", f.name)
            if m:
                out.setdefault(f"file:{m.group(1)}:{m.group(2)}", f"/artwork/{f.name}")
    return out


@lru_cache(maxsize=1)
def _glyph_by_variant() -> dict:
    """Same variant = same glyph across mods; used where one mod has no picture of its own."""
    out = {}
    for k, p in sorted(_files().items()):
        tail = k.split(":", 2)[2]
        for v in sorted(VARIANT_ORDER + [x + " Deviant Energy" for x in VARIANT_ORDER], key=len, reverse=True):
            vs = _vslug(v)
            if tail.endswith("-" + vs):
                out.setdefault(vs, p)
                break
    return out


def base_name(name: str) -> str:
    return re.sub(r"\s*\(all weapons\)$", "", name or "", flags=re.I)


def tile_art(slot: str, name: str, variant: str) -> str | None:
    sa, n, v = SLOT_ART.get(slot, ""), slug(base_name(name)), _vslug(variant)
    f = _files()
    return (f.get(f"mod:{sa}:{n}-{v}") or f.get(f"file:{sa}:{n}-{v}") or f.get(f"mod:{sa}:{n}-{slug(variant)}")
            or _glyph_by_variant().get(v))


def family_art(slot: str, name: str) -> str | None:
    p = ART / f"family__{SLOT_ART.get(slot, '')}__{slug(base_name(name))}.png"
    return f"/artwork/{p.name}" if p.exists() else None


_IDS: dict | None = None


def game_ids() -> dict[str, int]:
    """mod name (lower) -> numeric game mod ID from the gamedata snapshot (armor mods only)."""
    global _IDS
    if _IDS is None:
        _IDS = {}
        try:
            d = json.loads((Path(__file__).parent / "gamedata" / "thgl_snapshot.json").read_text())
            mods = d.get("mods") or []
            for m in (mods.values() if isinstance(mods, dict) else mods):
                mid = str(m.get("id") or "")
                if m.get("slot") != "All Weapons" and mid.startswith("mod_") and mid[4:].isdigit():
                    _IDS[m["name"].lower()] = int(mid[4:])
        except (OSError, ValueError):
            pass
    return _IDS


def catalog(mods: list[dict]) -> dict:
    """mods = ui_catalog()["mods"] rows (name, slot, variants)."""
    tiles, emblems, order, group = {}, {}, {}, {}
    for fam, names in WEAPON_FAMILIES.items():
        for i, n in enumerate(names):
            group[n.lower()] = fam
            order[f"weapon|{n.lower()}"] = list(WEAPON_FAMILIES).index(fam) * 10 + i
    ids = game_ids()
    for sa, names in ARMOR_ORDER.items():
        slot = next((k for k, v in SLOT_ART.items() if v == sa), None)
        # The game lists armor mods by their internal mod ID (e.g. Bottoms: Reload Rampage 9311 ... Precision Load 9321).
        # Mods without a known ID keep the reference order, after the ones we can place.
        ranked = sorted(names, key=lambda n: (ids.get(n.lower()) is None, ids.get(n.lower()) or 0, names.index(n)))
        for i, n in enumerate(ranked):
            order[f"{slot}|{n.lower()}"] = i
    for m in mods:
        s, n = m.get("slot") or "", m["name"]
        for v in (m.get("variants") or ["General"]):
            a = tile_art(s, n, v)
            if a:
                tiles[f"{s}|{n}|{v}".lower()] = a
        e = family_art(s, n)
        if e:
            emblems[f"{s}|{n}".lower()] = e
        b = base_name(n).lower()
        if b != n.lower():
            for k in (f"{s}|{b}",):
                if k in order:
                    order[f"{s}|{n.lower()}"] = order[k]
            if b in group:
                group[n.lower()] = group[b]
    return {"tiles": tiles, "emblems": emblems, "order": order, "weapon_group": group, "slots": GAME_SLOTS,
            "groups": {k: {"label": FAMILY_LABEL[k], "icon": f"/artwork/mod-category-{FAMILY_ICON[k]}.png"}
                       for k in WEAPON_FAMILIES},
            "variant_order": VARIANT_ORDER}
