"""Gun accessories for the Deviant Forge damage model.

Only magazines change sustained DPS in this model: they change how many shots you fire before a reload
and how long the reload takes. That also changes how often "after reloading" effects fire (AUG - Electron
Cloud's zone, Vanguard, Shelterer-style resets). Muzzles, scopes and grips change recoil, spread and range,
which the model does not count (it assumes 90% of bullets hit).

Reload numbers use the Jan 2026 "Reload Efficiency" system: reload time = base / (1 + total efficiency).
Official dev blog: https://www.oncehuman.game/banner/20260113/41906_1281545.html

Each entry says whether its numbers are confirmed. Unconfirmed ones can be overridden with the numbers
from your own tooltip (profile["accessory_values"][id] = {"reload_speed": x, "magazine_flat": y, "magazine": z}).
"""
from __future__ import annotations

DEV_BLOG = "https://www.oncehuman.game/banner/20260113/41906_1281545.html"

# stats use engine keys: reload_speed (% Reload Efficiency), magazine (% capacity), magazine_flat (+rounds)
MAGAZINES: dict[str, dict] = {
    "extended_rifle": {
        "name": "Extended Rifle Mag", "rarity": "Legendary", "fits": ["Assault Rifle"],
        "stats": {"magazine_flat": 10, "reload_speed": -9}, "text": "Magazine Capacity +10, Reload Efficiency -9%",
        "confirmed": True, "source": DEV_BLOG},
    "amended_rifle": {
        "name": "Amended Rifle Mag", "rarity": "Rare", "fits": ["Assault Rifle"],
        "stats": {"reload_speed": 10}, "text": "Reload Speed +10%, Accuracy +8",
        "confirmed": True, "source": "your in-game screenshot (accessory tooltip)"},
    "light_rifle": {
        "name": "Light Rifle Mag", "rarity": "Epic", "fits": ["Assault Rifle"],
        "stats": {"reload_speed": 13}, "text": "Reload Efficiency about +13% (old Reload Speed +13, Stability +7)",
        "confirmed": False,
        "source": "https://upcomer.com/where-to-get-the-best-assault-rifle-weapon-accessories-in-once-human/"},
    # Quick Magazine / Expanded Magazine (old all-gun mags) were removed: the in-game shop only offers
    # Extended, Light and Amended Rifle Mag for assault rifles (user report, 2026-11-05).
    "tactical_pistol": {
        "name": "Tactical Pistol Mag", "rarity": "Legendary", "fits": ["Pistol"],
        "stats": {"reload_speed": 16}, "text": "Reload Efficiency +16%, Accuracy +8%, Mobility +10%",
        "confirmed": True, "source": DEV_BLOG},
    "tactical_sr": {
        "name": "Tactical SR Mag", "rarity": "Legendary",
        "fits": ["Sniper Rifle", "Bolt-Action Sniper Rifle", "Semi-Auto Sniper Rifle"],
        "stats": {"reload_speed": 15}, "text": "Reload Efficiency +15%, Accuracy +8%, Mobility +10%",
        "confirmed": True, "source": DEV_BLOG},
    "large_lmg_drum": {
        "name": "Large LMG Drum Mag", "rarity": "Legendary", "fits": ["Light Machine Gun"],
        "stats": {"magazine_flat": 20, "reload_speed": -14}, "text": "Magazine Capacity +20, Reload Efficiency -14%",
        "confirmed": True, "source": DEV_BLOG},
}

NOT_COUNTED = ("Muzzles, scopes, grips and lasers change recoil, spread, range and aim speed. "
               "The model assumes 90% of bullets hit, so they don't change the number.")


def fits(mag_id: str, weapon: dict) -> bool:
    m = MAGAZINES.get(mag_id)
    if not m:
        return False
    return "*" in m["fits"] or (weapon.get("type") or "") in m["fits"]


def compatible(weapon: dict) -> list[str]:
    return [k for k in MAGAZINES if fits(k, weapon)]


def stats_for(mag_id: str | None, overrides: dict | None = None) -> dict:
    if not mag_id or mag_id not in MAGAZINES:
        return {}
    st = dict(MAGAZINES[mag_id]["stats"])
    for k, v in ((overrides or {}).get(mag_id) or {}).items():
        if k in ("reload_speed", "magazine", "magazine_flat") and v is not None:
            st[k] = float(v)
    return st


def public(weapon: dict | None = None, overrides: dict | None = None) -> list[dict]:
    out = []
    for k, m in MAGAZINES.items():
        if weapon is not None and not fits(k, weapon):
            continue
        st = stats_for(k, overrides)
        out.append({"id": k, "name": m["name"], "rarity": m["rarity"], "fits": m["fits"], "text": m["text"],
                    "stats": st, "confirmed": m["confirmed"] or bool((overrides or {}).get(k)),
                    "custom": bool((overrides or {}).get(k)), "source": m["source"]})
    return out
