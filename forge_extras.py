"""Build-wide damage sources that sit outside weapons/mods/armor sets.

Key armor, calibration blueprints, combat deviations, food and drinks.
Every entry carries the source it came from. Entries marked "approx" use a
documented simplification of a conditional effect; the UI shows that flag.

Stat keys match forge.evaluate():
  weapon_dmg, status_dmg, elemental_dmg, el:<Element>, crit_rate, crit_dmg,
  weakspot_dmg, attack, fire_rate, magazine, reload_speed, vs_enemies,
  vulnerability, kw_dmg:<KW>, kw_final:<KW>, kw_crit_rate:<KW>,
  weapon_taken (target takes more Weapon DMG), el_taken:<Element>,
  marked_dmg (DMG vs targets under The Bull's Eye),
  _kw_trigger_extra:<KW> (each trigger fires N extra times),
  _shrapnel_parts (extra parts hit), _shrapnel_single (Gas-tight: max 1 part)
"""
from __future__ import annotations

import re

FANDOM_ARMOR = "https://once-human.fandom.com/wiki/Armor"
MB = "https://meta-builds.net/once-human/armor/"
GAME8_GASTIGHT = "https://game8.co/games/Once-Human/archives/463208"
DEVBLOG_S4 = "https://www.oncehuman.game/news/devBlog/20260702/40781_1306465.html"
DEVBLOG_CODEV = "https://www.oncehuman.game/news/devBlog/20241123/40781_1195665.html"
FROST_GUIDE = "https://mmochronicles.com/en/guides/once-human/the-ultimate-frost-vortex-build-guide-in-once-human"
FOOD_WIKI = "https://once-human.fandom.com/wiki/Food_and_Water/Cooked_Food_List"
FOOD_LIST = "https://allthings.how/once-human-food-recipe-locations-for-50-free-damage-buffs/"
CAL_BLOG = "https://www.oncehuman.game/news/devBlog/20260113/40781_1281545.html"
CAL_WIKI = "https://once-human.fandom.com/wiki/Calibration_Blueprints"

# ------------------------------------------------------------------ key armor
# One key armor piece may be worn. `kw` = only works with that keyword.
KEY_ARMOR: dict[str, dict] = {
    "Gas-tight Helmet": {"slot": "Helmet", "kw": "Shrapnel", "text": "Max Shrapnel target parts 1. Shrapnel DMG +120%",
                         "stats": {"kw_dmg:Shrapnel": 120, "_shrapnel_single": 1}, "source": GAME8_GASTIGHT,
                         "disputed": "Fandom lists +150%; Game8 and Meta-Builds quote the tooltip as +120%"},
    "Beret": {"slot": "Helmet", "kw": "Shrapnel", "text": "Shrapnel Hit Part +1", "stats": {"_shrapnel_parts": 1}},
    "Cage Helmet": {"slot": "Helmet", "kw": "Shrapnel", "text": "Shrapnel Trigger Count +1", "stats": {"_kw_trigger_extra:Shrapnel": 1}},
    "Gas Mask Hood": {"slot": "Helmet", "kw": "Power Surge", "text": "After triggering Power Surge, Crit Rate +35% for 3 seconds",
                      "stats": {"crit_rate": 35}, "uptime": "kw3s"},
    "Mayfly Goggles": {"slot": "Helmet", "kw": "Power Surge", "text": "Power Surge trigger count +1. Power Surge DMG -30%",
                       "stats": {"_kw_trigger_extra:Power Surge": 1, "kw_final:Power Surge": -30}},
    "Yellow Painted Mask": {"slot": "Helmet", "kw": "Power Surge", "text": "Defeating enemies generates an EMP that applies Power Surge once",
                          "stats": {}, "unmodeled": True},
    "Shaman Vulture Top": {"slot": "Top", "kw": "Unstable Bomber", "text": "After triggering Unstable Bomber, Crit Rate +35% for 3 seconds",
                           "stats": {"crit_rate": 35}, "uptime": "kw3s"},
    "Explosive Front Top": {"slot": "Top", "kw": "Unstable Bomber", "text": "Unstable Bomber delay +0.3s and Unstable Bomber DMG +30%",
                            "stats": {"kw_dmg:Unstable Bomber": 30}},
    "Sleek Leather Jacket": {"slot": "Top", "kw": "Unstable Bomber", "text": "Unstable Bomber Final DMG +2% per 1m away from you",
                             "stats": {"kw_final:Unstable Bomber": 20}, "approx": "assumes about 10 m distance"},
    "Viper Mask": {"slot": "Mask", "kw": "Unstable Bomber", "text": "Unstable Bomber range +50%; +1% Unstable Bomber DMG per 2% range",
                   "stats": {"kw_dmg:Unstable Bomber": 25}},
    "Charmed Mag Top": {"slot": "Top", "kw": "Fast Gunner", "text": "Fast Gunner: lower ammo raises the chance of an extra bullet (40% at 1% ammo)",
                        "stats": {"fire_rate": 20}, "approx": "about 20% extra bullets over a magazine"},
    "Oasis Mask": {"slot": "Mask", "kw": "Fast Gunner", "text": "Fast Gunner max stacks +10 and Attack +1% per stack",
                   "stats": {"attack": 10, "fire_rate": 10}, "approx": "assumes full stacks"},
    "Desert Dust Mask": {"slot": "Mask", "kw": "Fast Gunner", "text": "Fast Gunner: 70% chance to reload 1 bullet, reloaded bullets +20% Attack",
                  "stats": {"magazine": 25, "attack": 5}, "approx": "rough sustained value"},
    "Precise Shot Mask": {"slot": "Mask", "kw": "Fast Gunner", "text": "Fast Gunner: Reload Speed +25% per stack, up to 10",
                          "stats": {"reload_speed": 60}, "approx": "average stacks at reload"},
    "Cowboy Boots": {"slot": "Shoes", "kw": "Fortress Warfare", "text": "Fortress Warfare only affects self; Attack +25% in Fortress Warfare",
                     "stats": {"attack": 25}},
    "Tactical Combat Boots": {"slot": "Shoes", "kw": "Fortress Warfare", "text": "In Fortress Warfare: refill 1 bullet and Fire Rate +15%",
                            "stats": {"fire_rate": 15, "magazine": 10}, "approx": "refill value estimated"},
    "Earthly Boots": {"slot": "Shoes", "kw": None, "needs_mark": True, "text": "When hitting marked enemies, DMG +30%",
                      "stats": {"marked_dmg": 30}},
    "Old Huntsman Boots": {"slot": "Shoes", "kw": None, "needs_mark": True,
                           "text": "Weakspot DMG +30% to enemies affected by The Bull's Eye", "stats": {"weakspot_dmg": 30}},
    "Tactical Combat Shoes": {"slot": "Shoes", "kw": None, "needs_mark": True,
                              "text": "Hitting marked enemies: 40% chance to reload 1 ammo", "stats": {"magazine": 30},
                              "approx": "ammo refund as magazine"},
    "Fire Rune Boots": {"slot": "Shoes", "kw": "Burn", "text": "Burning targets nearby: 50% chance for a particle, Blaze DMG +30% for 15s",
                        "stats": {"el:Blaze": 25}, "approx": "about 80% uptime"},
    "BBQ Gloves": {"slot": "Gloves", "kw": "Burn", "text": "Burn damage frequency rises with stacks, up to +100%",
                   "stats": {"kw_final:Burn": 80}, "approx": "near-full stacks on a boss"},
    "Hardy Gloves": {"slot": "Gloves", "kw": "Burn", "text": "At full stacks Burn explodes for 300% Psi Intensity and clears stacks",
                     "stats": {}, "unmodeled": True},
    "Drifter Gauntlets": {"slot": "Gloves", "kw": None, "text": "When you are affected by Burn, Weapon DMG +15% and Crit Rate +15%",
                          "stats": {}, "unmodeled": True},
    "Snow Camo Gloves": {"slot": "Gloves", "kw": "Frost Vortex", "text": "Ice Crystal shatter launches 4 missiles (50% Psi Intensity each)",
                         "stats": {}, "unmodeled": True},
    "Snowline Elite Vest": {"slot": "Top", "kw": "Frost Vortex", "source": FROST_GUIDE,
                            "text": "Frost Vortex side effects trigger 1 extra time; Frost Vortex DMG +5% per trigger, up to 25%",
                            "stats": {"kw_dmg:Frost Vortex": 25}},
    "Frost Tactical Vest": {"slot": "Top", "kw": "Frost Vortex", "text": "Frost Vortex generates Ice Spikes dealing 100% Psi Intensity Frost DMG",
                       "stats": {"kw_final:Frost Vortex": 25}, "approx": "spike value estimated"},
    "Doyen's Cloak": {"slot": "Top", "kw": None, "text": "When Frozen ends, deal 50% of the damage dealt during Frozen",
                      "stats": {}, "unmodeled": True},
    "Hot Dog Shorts": {"slot": "Bottoms", "kw": "Bounce", "text": "Bounces +2", "stats": {"kw_final:Bounce": 60}, "approx": "single target gets part of the extra bounces"},
    "Sharp Blade Pants": {"slot": "Bottoms", "kw": "Bounce", "text": "Bounce Trigger Count +1", "stats": {"_kw_trigger_extra:Bounce": 1}},
    "Overloaded Pants": {"slot": "Bottoms", "kw": "Power Surge", "text": "Every 20 Power Surges: next 6 shots use reserve ammo, Shock DMG +20%",
                         "stats": {"el:Shock": 8, "magazine": 5}, "approx": "partial uptime"},
    # ---- added 2026.11.06 (full key-armor coverage; texts from Meta-Builds / dev blog, IDs matched to the game data)
    "Snowdrift Top": {"slot": "Top", "kw": "Frost Vortex", "weapons": ["SKS - Pathfinder"], "source": MB + "snowdrift-top-206/",
                      "text": "When picking up Deviant Particles, gains an additional charge stack, and Weapon and Status DMG +25% for 25s",
                      "stats": {"weapon_dmg": 25, "status_dmg": 25},
                      "approx": "near-full uptime (60% particle chance per hit, 25s buff); the extra charge stack (more ice spikes) is not counted"},
    "Wind Intepreter Cap": {"slot": "Helmet", "kw": "Unstable Bomber", "source": DEVBLOG_S4,
                            "text": "When Unstable Bomber explodes, automatically load 1 bullet; Unstable Bomber DMG Rate +25%",
                            "stats": {"kw_dmg:Unstable Bomber": 25}, "approx": "the bullet refund is not counted"},
    "Ankh Mask": {"slot": "Mask", "kw": None, "source": MB + "ankh-mask-232/",
                  "text": "When the magazine is emptied, 40% chance to consume reserve ammo and refill 20% of the magazine",
                  "stats": {"magazine": 8}, "approx": "40% x 20% = about 8% more bullets per reload"},
    "Bloodstained Tracker Boots": {"slot": "Shoes", "kw": None, "needs_mark": True, "source": MB + "bloodstained-tracker-boots-216/",
                                   "text": "Applying The Bull's Eye to an already-marked target: Attack +20% for 5s, and the mark spreads to one nearby target",
                                   "stats": {"attack": 10}, "approx": "about half uptime; depends on how often you re-mark"},
    "Gilded Gloves": {"slot": "Gloves", "kw": "Burn", "source": MB + "gilded-gloves-218/",
                      "text": "Unlocks the ability for Burn to crit (uses your character Crit Rate)",
                      "stats": {"kw_crit_rate:Burn": 0.001}, "approx": "Burn crits with your normal Crit Rate and Crit DMG"},
    "Gilded Palm Shield": {"slot": "Gloves", "kw": "Burn", "source": MB + "gilded-gloves-218/", "aka": "Gilded Gloves",
                           "text": "Unlocks the ability for Burn to crit (uses your character Crit Rate)",
                           "stats": {"kw_crit_rate:Burn": 0.001}, "approx": "Burn crits with your normal Crit Rate and Crit DMG"},
    "Covert Walker Shirt": {"slot": "Top", "kw": "Frost Vortex", "source": DEVBLOG_CODEV, "utility": True,
                            "text": "Frost Vortex collapses in the center and keeps pulling enemies within 1.5x the vortex range (crowd control)",
                            "stats": {}, "unmodeled": True},
    "Magnetic Moment Top": {"slot": "Top", "kw": "Power Surge", "source": MB + "magnetic-moment-top-221/", "utility": True,
                            "text": "Targets affected by Power Surge keep pulling in other enemies within 7 m (crowd control)",
                            "stats": {}, "unmodeled": True},
    "Tattoo Pants": {"slot": "Bottoms", "kw": "Bounce", "source": MB + "tattoo-pants-152/",
                     "text": "Bounce can hit allies (no damage to them); sources disagree on the exact refund/extra-bounce effect",
                     "stats": {}, "unmodeled": True},
    "Glide Pants": {"slot": "Bottoms", "kw": None, "source": MB + "glide-pants-222/", "utility": True,
                    "text": "Roll becomes Slide; after sliding, Reload Efficiency +100% and Movement Speed +30% for 2s (bows: load 1 arrow)",
                    "stats": {}, "unmodeled": True},
    "Leather Boots": {"slot": "Shoes", "kw": "Fortress Warfare", "source": MB + "leather-boots-73/", "utility": True,
                      "text": "Recover 2.5% HP per second in Fortress Warfare; doubled below 50% HP",
                      "stats": {}, "unmodeled": True},
    "Pivot Step Leather Boots": {"slot": "Shoes", "kw": None, "source": MB + "pivot-step-leather-boots-217/", "utility": True,
                                 "text": "Resets Battle Skill cooldown after using a Deviation Ultimate",
                                 "stats": {}, "unmodeled": True},
}
# old names used by earlier versions of the app -> game names (old profiles keep working)
KEY_ARMOR_ALIASES = {"Yellow Paint Mask": "Yellow Painted Mask", "Dust Mask": "Desert Dust Mask",
                     "Hard Tactical Boots": "Tactical Combat Boots", "Frost Tactical": "Frost Tactical Vest",
                     "Gilded Gauntlets": "Gilded Gloves", "Wind Interpreter Cap": "Wind Intepreter Cap",
                     "Stealth Walker Wrap": "Covert Walker Shirt"}


def key_armor_fits(name: str, kw: str | None, weapon: str | None = None) -> bool:
    """Does this key armor piece do anything for this gun? (keyword, and gun-specific pieces like Snowdrift Top)"""
    ka = KEY_ARMOR.get(name) or {}
    if ka.get("kw") and ka["kw"] != kw:
        return False
    if ka.get("weapons") and weapon not in ka["weapons"]:
        return False
    return True
for _v in KEY_ARMOR.values():
    _v.setdefault("source", FANDOM_ARMOR)

# ------------------------------------------------------------------ deviations
# Combat deviation auto-attack debuffs at skill level 5 (scale linearly by level).
DEVIATIONS: dict[str, dict] = {
    "Lonewolf's Whisper": {"stats": {"weapon_taken": 43.75}, "lv1": {"weapon_taken": 18.75},
                           "text": "Target takes +43.75% Weapon DMG (Lv 5)", "source": "https://wikily.gg/once-human/deviations/99000011/"},
    "Butterfly's Emissary": {"stats": {"weakspot_dmg": 35}, "lv1": {"weakspot_dmg": 15},
                             "text": "Marked weakspot takes +35% extra Weakspot DMG for 5s (Lv 5)",
                             "source": "https://wikily.gg/once-human/deviations/99900001/"},
    "Pyro Dino": {"stats": {"el_taken:Blaze": 34.3}, "lv1": {"el_taken:Blaze": 15},
                  "text": "Target takes +34.3% Blaze DMG (Lv 5)", "source": "https://wikily.gg/once-human/deviations/99000030/"},
    "Polar Jelly": {"stats": {"el_taken:Frost": 34.3}, "lv1": {"el_taken:Frost": 15},
                    "text": "Nearby targets take +34.3% Frost DMG (Lv 5)", "source": "https://wikily.gg/once-human/deviations/99000003/"},
    "Shattered Maiden": {"stats": {"el_taken:Blast": 70}, "lv1": {"el_taken:Blast": 30}, "mobs_only": True,
                         "text": "Non-boss enemies take +70% Explosion DMG (Lv 5)", "source": "https://wikily.gg/once-human/deviations/99000049/"},
    "Zapamander": {"stats": {"kw_final:Power Surge": 37.8}, "lv1": {"kw_final:Power Surge": 16.2}, "kw": "Power Surge",
                   "text": "Target takes +37.8% Power Surge DMG (Lv 5). Its Ultimate's status vulnerability is not counted",
                   "source": "https://wikily.gg/once-human/deviations/99000059/"},
    "ZapCam": {"stats": {}, "unmodeled": True, "text": "Stacks a Weapon DMG taken debuff (exact values not published)",
               "source": "https://mmochronicles.com/en/guides/once-human/once-human-shrapnel-build-guide-best-socr-the-last-valor-setup-and-mods"},
}

# ------------------------------------------------------------------ food & drink
DAOPA = "https://gamingwithdaopa.ellatha.com/once-human/recipes/"
CLASS_NEWS = "https://www.oncehuman.game/news/official/20260513/40779_1300125.html"
BEAST_NEWS = "https://allthings.how/once-human-beast-riding-how-the-beastmaster-rework-works/"
BOTH_RULE = ("fills a food slot and a drink slot (it restores Energy and Hydration); "
             "rule from your report, not confirmed in patch notes")

# Classes: how many food / drink effects can be active. Only Chef changes it.
CLASSES: dict[str, dict] = {
    "freelancer": {"label": "Freelancer", "food": 1, "drink": 1, "text": "No class abilities. 1 food + 1 drink effect.",
                   "source": "https://game8.co/games/Once-Human/archives/533171"},
    "chef": {"label": "Chef", "food": 2, "drink": 2,
             "text": "Glutton: up to 2 food + 2 drink effects at the same time.", "source": CLASS_NEWS},
    "beastmaster": {"label": "Beastmaster", "food": 1, "drink": 1,
                    "text": "1 food + 1 drink. Your Beast Partner does its own damage; that is not counted.",
                    "not_counted": "Beast Partner damage and mount buffs (no published numbers)", "source": BEAST_NEWS},
    "gardener": {"label": "Gardener", "food": 1, "drink": 1, "text": "No damage abilities. 1 food + 1 drink.",
                 "source": "https://game8.co/games/Once-Human/archives/533024"},
}


def _c(slots, stats, text, src=DAOPA, **kw):
    return {"slots": slots, "stats": stats, "text": text, "source": src, **kw}


F, D, FD = ("food",), ("drink",), ("food", "drink")
CONSUMABLES: dict[str, dict] = {
    "Shattered Bread": _c(F, {"weapon_dmg": 25}, "Weapon DMG +25%", aka="Crumbly Bread",
                          approx="listed in-game as Crumbly Bread (name match not confirmed)"),
    "Bone-In Deviated Sausage": _c(F, {"vs_enemies": 15}, "DMG vs bosses +15%", boss_only=True),
    "Stardust Pumpkin Salad": _c(F, {"crit_dmg": 15}, "Crit DMG +15%"),
    "Stargazy Pie": _c(F, {"crit_dmg": 25}, "Crit DMG +25% while Energy is full"),
    "Mixed Fried Hot Dog": _c(F, {"marked_dmg": 20}, "+20% DMG vs Bull's Eye targets", needs_mark=True),
    "Ginger Poppers": _c(F, {"kw_dmg:Shrapnel": 10}, "Shrapnel DMG +10%", kw="Shrapnel"),
    "Canned Steak": _c(F, {"kw_dmg:Shrapnel": 20}, "Shrapnel DMG +20%", kw="Shrapnel"),
    "Shellfish Meat": _c(F, {"vulnerability": 5}, "Enemies hit take 5% more DMG"),
    "Canned Minty Meat": _c(F, {"el:Frost": 15}, "Frost DMG +15%"),
    "Canned Spicy Rabbit Dices": _c(F, {"el:Blaze": 15}, "Blaze DMG +15% above 30\u00b0C",
                                    approx="only in hot areas (above 30\u00b0C)"),
    "Flaming Eggtart": _c(F, {"kw_dmg:Burn": 10}, "Burn DMG +10%", kw="Burn"),
    "Popcorn": _c(F, {"kw_dmg:Unstable Bomber": 10}, "Unstable Bomber DMG +10%", kw="Unstable Bomber"),
    "Surprise Spring Roll": _c(F, {"elemental_dmg": 10}, "Elemental DMG +5\u201315% (10% used)",
                               approx="listed as 5\u201315%; 10% used, low-HP doubling not counted"),
    "Assorted Canned Fruit": _c(FD, {"weakspot_dmg": 25}, "Weakspot DMG +25% while Sanity > 80%", approx=BOTH_RULE),
    "Hearty Meat Stew": _c(FD, {"el:Blaze": 15}, "Blaze DMG +15%", approx=BOTH_RULE),
    "Honey Glazed Meat": _c(FD, {"crit_rate": 15}, "Crit Rate +15% vs targets in a Frost Vortex", kw="Frost Vortex",
                            approx=BOTH_RULE),
    "Whimsical Drink": _c(D, {"status_dmg": 25}, "Status DMG +25% at full Sanity",
                          src="https://once-human.fandom.com/wiki/Food_and_Water/Cooked_Food_List"),
    "Sparkling Pumpkin Soup": _c(D, {"kw_dmg:Power Surge": 10}, "Power Surge DMG +10% (a drink)", kw="Power Surge"),
}
FOODS = {k: v for k, v in CONSUMABLES.items() if "food" in v["slots"]}
DRINKS = {k: v for k, v in CONSUMABLES.items() if "drink" in v["slots"]}


def slot_label(item: dict) -> str:
    return {F: "Food", D: "Drink", FD: "Food + Drink"}[tuple(item["slots"])]


def class_caps(cls: str | None) -> dict:
    c = CLASSES.get(cls or "freelancer") or CLASSES["freelancer"]
    return {"food": c["food"], "drink": c["drink"]}


def consumables_of(cfg: dict) -> list[str]:
    """Selected consumables; older profiles stored one 'food' and one 'drink'."""
    if cfg.get("consumables") is not None:
        names = list(cfg["consumables"])
    else:
        names = [cfg.get("food"), cfg.get("drink")]
    out = []
    for n in names:
        if n and n in CONSUMABLES and n not in out:
            out.append(n)
    return out


def fit_consumables(names: list[str], cls: str | None) -> tuple[list[str], list[str]]:
    """Keep what fits in the class's food/drink slots, in order. A food+drink dish uses one of each."""
    left = class_caps(cls)
    kept, dropped = [], []
    for n in names:
        slots = CONSUMABLES[n]["slots"]
        if all(left[s] > 0 for s in slots):
            for s in slots:
                left[s] -= 1
            kept.append(n)
        else:
            dropped.append(n)
    return kept, dropped


def consumable_combos(cls: str | None, candidates: list[str]):
    """Every set of candidates that fits the class's slots (including the empty set)."""
    from itertools import combinations
    caps = class_caps(cls)
    mx = caps["food"] + caps["drink"]
    for r in range(0, min(mx, len(candidates)) + 1):
        for combo in combinations(candidates, r):
            kept, dropped = fit_consumables(list(combo), cls)
            if not dropped:
                yield list(combo)


def best_consumables(score, cls: str | None, names=None) -> tuple[float, list[str]]:
    """Pick the best-scoring set. Prescreen each item alone, then try every fitting set of the useful ones."""
    names = list(names or CONSUMABLES)
    base = score([])
    useful = sorted((n for n in names if score([n]) > base * 1.001), key=lambda n: -score([n]))[:8]
    best = (base, [])
    for combo in consumable_combos(cls, useful):
        v = score(combo)
        if v > best[0]:
            best = (v, combo)
    return best


# ------------------------------------------------------------------ calibration
# 2026 system: one Attack roll (legendary 33-50%) + one bonus roll whose cap is the
# sum of the old two caps (Elemental confirmed 15-20%; others derived the same way).
CAL_ATTACK_MAX = 50.0
CAL_SUB_MAX = {"crit_rate": 16.0, "crit_dmg": 40.0, "weakspot_dmg": 24.0, "elemental_dmg": 20.0}
CAL_WIKI_LIST = "https://once-human.fandom.com/wiki/Calibration_Blueprints"
CAL_SEASON_BLOG = "https://www.oncehuman.game/news/devBlog/20241123/40781_1195665.html"
CAL_SEASON_PATCH = "https://www.oncehuman.game/news/update/20240814/40780_1174319.html"


def _st(stats, text, seasonal=False, var=None, note=""):
    return {"stats": stats, "text": text, "seasonal": seasonal, "var": var, "note": note}


# Seasonal styles (from Super Anomalies). Effects that don't change sustained boss DPS
# are listed but count as 0. "var" = a number that differs by blueprint rarity; the user
# can type the value from their tooltip.
_VANGUARD = _st({"_reload_kw_guarantee": 1.0},
                "After reloading from empty, the next shot is guaranteed to trigger its keyword effect.", True,
                {"key": "vs_enemies", "label": "DMG penalty % (0 if none)", "default": 0, "sign": -1, "max": 20},
                "Official Nov 2024 change removed the Final DMG -10% penalty; older community lists show DMG -12/-16%. "
                "Type the penalty if your tooltip shows one.")
_ENERGY = _st({}, "After taking damage, automatically reload 1 bullet (0.3s cooldown). Attack +15%.", True,
              {"key": "attack", "label": "Style Attack %", "default": 15, "sign": 1, "max": 20},
              "Official value Attack +15%; purple blueprints have been reported at +8%. The auto-reload is not counted.")
_BOOST = _st({}, "After reloading, the next shot's keyword gains extra Trigger Chance. Fire Rate down.", True,
             {"key": "_reload_kw_guarantee_pct", "label": "Trigger Chance % after reload", "default": 32, "sign": 1, "max": 100},
             "Purple roll reported as Trigger Chance +32%, Fire Rate -12%.")
_BOOST["stats"] = {"fire_rate": -12}
_OVERFLOW = _st({"magazine": 50, "attack": 2.7},
                "When reloading, load extra ammo equal to 50% of shots fired in the last 20s (max 100% of magazine). "
                "Extra ammo gains Attack +8%.", True, None,
                "Counted as about +50% magazine with +8% Attack on a third of shots (estimate for sustained fire).")
_FRUGAL = _st({}, "After missing a shot, automatically reload 1 ammo. The next shot that hits gains Attack +12–15%.", True, None,
              "Only triggers after a miss, so it is not counted for sustained boss damage.")
_PORTABLE = _st({}, "Mobility and movement speed while holding the gun.", note="No damage effect.")
_STABLE = _st({}, "Stability up, less aim shake.", note="No damage effect.")

CAL_STYLES: dict[str, dict[str, dict]] = {
    "rifle": {"Precision": _st({"attack": 25, "fire_rate": -10}, "Attack +25%, Range +40%, Fire Rate -10%"),
              "Heavy": _st({"magazine": 75, "reload_speed": -30}, "Magazine Capacity +75%, Reload Speed -30%"),
              "Rapid Shot": _st({"fire_rate": 20, "reload_speed": 10, "attack": -10},
                                "Fire Rate +20%, Reload Speed +10%, Attack -10% (gold AR blueprint tooltip; Reload Efficiency system)"),
              "Vanguard": _VANGUARD, "Energy": _ENERGY},
    "smg": {"Assault": _st({"attack": 20, "magazine": -25}, "Attack +20%, Magazine Capacity -25%, Accuracy -50"),
            "Heavy": _st({"magazine": 60, "reload_speed": -30}, "Magazine Capacity +60%, Reload Speed -30%"),
            "Lightweight": _st({"reload_speed": 150, "magazine": -30}, "Reload Speed +150%, Magazine Capacity -30%"),
            "Vanguard": _VANGUARD, "Energy": _ENERGY},
    "shotgun": {"Rapid Shot": _st({"fire_rate": 25, "magazine": 45, "attack": -10}, "Fire Rate +25%, Magazine Capacity +45%, Attack -10% (12-Gauge)"),
                "Lightweight": _st({"reload_speed": 150, "magazine": -30}, "Reload Speed +150%, Magazine Capacity -30% (16-Gauge)"),
                "Heavy": _st({"magazine": 60, "reload_speed": -30}, "Magazine Capacity +60%, Reload Speed -30% (20-Gauge)"),
                "Boost": _BOOST},
    "lmg": {"Assault": _st({"attack": 25, "magazine": -30}, "Attack +25%, Magazine Capacity -30%, Stability -50"),
            "Rapid Shot": _st({"fire_rate": 20}, "Fire Rate +10%, +10% more after 2s of continuous fire, Accuracy -50"),
            "Stabilized": _STABLE, "Vanguard": _VANGUARD, "Overflow": _OVERFLOW},
    "pistol": {"Rapid Shot": _st({"fire_rate": 25, "magazine": 40, "attack": -15}, "Fire Rate +25%, Magazine Capacity +40%, Attack -15% (P22)"),
               "Precision": _st({"attack": 25, "fire_rate": -10}, "Attack +25%, Range +40%, Fire Rate -10%"),
               "Portable": _PORTABLE, "Boost": _BOOST, "Overflow": _OVERFLOW, "Frugal": _FRUGAL},
    "sniper": {"Rapid Shot": _st({"fire_rate": 30, "reload_speed": 50, "attack": -10}, "Bolt-pulling Speed +50%, Reload Speed +50%, Attack -10%"),
               "Portable": _PORTABLE, "Stabilized": _STABLE, "Frugal": _FRUGAL},
    "bow": {"Precision": _st({"attack": 12.5, "reload_speed": -25}, "Attack +12.5%, Range +20%, Reload Speed -25%"),
            "Portable": _st({}, "Mobility +30, Weapon Switching Speed +35%", note="No damage effect.")},
}
CAL_ALIASES = {"rapid": "Rapid Shot", "rapid fire": "Rapid Shot", "light": "Lightweight", "steady": "Stabilized",
               "handy": "Portable", "mobility": "Portable"}


def cal_style_name(style: str | None, fam: str) -> str | None:
    """Normalise 'Energy Style', 'vanguard', 'Rapid' -> a key in CAL_STYLES[fam]."""
    if not style:
        return None
    s = re.sub(r"\s*style\s*$", "", str(style).strip(), flags=re.I)
    s = CAL_ALIASES.get(s.lower(), s)
    for k in CAL_STYLES.get(fam, {}):
        if k.lower() == s.lower():
            return k
    for f in CAL_STYLES.values():
        for k in f:
            if k.lower() == s.lower():
                return k
    return None


def cal_style(fam: str, style: str | None) -> dict | None:
    k = cal_style_name(style, fam)
    if not k:
        return None
    return CAL_STYLES.get(fam, {}).get(k) or next((f[k] for f in CAL_STYLES.values() if k in f), None)


def weapon_family(wtype: str) -> str:
    t = (wtype or "").lower()
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
    if "bow" in t:
        return "bow"
    return "rifle"


def calibration_options(wtype: str) -> list[dict]:
    """Best possible (legendary, max roll) calibrations for a weapon type."""
    out = []
    for style, ent in CAL_STYLES.get(weapon_family(wtype), CAL_STYLES["rifle"]).items():
        for sub, v in CAL_SUB_MAX.items():
            d = _style_stats(ent, None)
            d["attack"] = d.get("attack", 0) + CAL_ATTACK_MAX
            d[sub] = d.get(sub, 0) + v
            out.append({"label": f"{style} style · Attack +{CAL_ATTACK_MAX:g}% · {sub.replace('_', ' ').title()} +{v:g}%",
                        "style": style, "sub": sub, "stats": d, "source": CAL_BLOG})
    return out


# ------------------------------------------------------------------ armor hides
# Only the MASK hide slot adds damage (other slots: resistances, stamina, yields). Hide rarity's
# +15/30/40% base HP and Psi is already inside the Psi Intensity number the game shows, so we never
# add it again. cond = a fight condition the user switches on in settings; None = always on.
HIDE_SRC = "https://meta-builds.net/once-human/armor/scout-mask-30/"
HIDE_SRC2 = "https://game8.co/games/Once-Human/archives/481673"
HIDE_CONDS = {
    "moving": "Moving while shooting",
    "stamina90": "Stamina above 90",
    "stamina120": "Stamina 120 or more (needs Max Stamina bonuses)",
    "low_hp": "HP below 30% (Lunar hides)",
    "water": "Fighting in water",
    "dream": "In the Dream Zone",
    "airborne": "Airborne (jumping / Aero builds)",
    "dampened": "Dampened (wet)",
    "energy100": "Energy at 100",
    "energy_low": "Energy below 60",
}


def _h(text, stats=None, cond=None, cond_stats=None, unmodeled=False):
    return {"text": text, "stats": stats or {}, "cond": cond, "cond_stats": cond_stats or {}, "unmodeled": unmodeled}


MASK_HIDES: dict[str, dict] = {
    "Golden Wool": _h("Weapon DMG and Status DMG +12% in total, split changing every second", {"weapon_dmg": 6, "status_dmg": 6}),
    "Wool": _h("Status DMG +4%", {"status_dmg": 4}),
    "Rock Wall Wool": _h("Status DMG +6% while moving", cond="moving", cond_stats={"status_dmg": 6}),
    "Mountain Wool": _h("Status DMG +6% when Stamina exceeds 90", cond="stamina90", cond_stats={"status_dmg": 6}),
    "Lunar Wool": _h("Status DMG +1.5% per 10% HP missing, up to +10.5%", {"status_dmg": 3}, "low_hp", {"status_dmg": 10.5}),
    "Dreamfused Wool": _h("Status DMG +4%, doubles in the Dream Zone", {"status_dmg": 4}, "dream", {"status_dmg": 8}),
    "Velvet": _h("Status DMG +10% while Dampened", cond="dampened", cond_stats={"status_dmg": 10}),
    "Squid Skin": _h("Status DMG +8% when fighting in water", cond="water", cond_stats={"status_dmg": 8}),
    "Starfall Down": _h("Status DMG +15% while airborne", cond="airborne", cond_stats={"status_dmg": 15}),
    "Rabbit Fur": _h("Elemental DMG +4%", {"elemental_dmg": 4}),
    "Dreamy Rabbit Fur": _h("Elemental DMG +6%", {"elemental_dmg": 6}),
    "Lucky Rabbit Fur": _h("After a Crit, Elemental DMG +10% for 3s (counted at ~90% uptime when crit rate is decent)", {"elemental_dmg": 9}),
    "Lunar Rabbit Fur": _h("Elemental DMG +5%, doubles if HP is below 30%", {"elemental_dmg": 5}, "low_hp", {"elemental_dmg": 10}),
    "Dreamfused Rabbit Fur": _h("Elemental DMG +4%, doubles in the Dream Zone", {"elemental_dmg": 4}, "dream", {"elemental_dmg": 8}),
    "Tuna Skin": _h("Elemental DMG +8% when fighting in water", cond="water", cond_stats={"elemental_dmg": 8}),
    "Bear Skin": _h("Frost Elemental DMG +5%", {"el:Frost": 5}),
    "Floating Ice Bear Skin": _h("Frost Elemental DMG +8% when Energy is at 100", cond="energy100", cond_stats={"el:Frost": 8}),
    "Snowfield Bear Skin": _h("Shock Elemental DMG +8% when Energy is below 60", cond="energy_low", cond_stats={"el:Shock": 8}),
    "Cave Bear Skin": _h("Elemental DMG +7% while crouched", unmodeled=True),
    "Wolf Skin": _h("Weakspot DMG +3%", {"weakspot_dmg": 3}),
    "Wasteland Wolf Skin": _h("Weakspot DMG +6% when Stamina exceeds 90", cond="stamina90", cond_stats={"weakspot_dmg": 6}),
    "Grassland Wolf Skin": _h("Weakspot DMG +4.5%", {"weakspot_dmg": 4.5}),
    "Lunar Wolf Skin": _h("Weakspot DMG +4%, +8% if HP is below 30%", {"weakspot_dmg": 4}, "low_hp", {"weakspot_dmg": 8}),
    "Dreamfused Wolf Skin": _h("Weakspot DMG +3%, doubles in the Dream Zone", {"weakspot_dmg": 3}, "dream", {"weakspot_dmg": 6}),
    "Jungle Wolf Skin": _h("Weapon DMG +6% when Stamina is below 60", unmodeled=True),
    "Cowhide": _h("Weapon DMG +5% when Stamina is at least 100", {"weapon_dmg": 5}),
    "Mountain Cowhide": _h("Weapon DMG +8% when Stamina is at least 120", cond="stamina120", cond_stats={"weapon_dmg": 8}),
    "Dreamfused Cowhide": _h("Weapon DMG +5% at 100+ Stamina, doubles in the Dream Zone", {"weapon_dmg": 5}, "dream", {"weapon_dmg": 10}),
    "Starfall Cowhide": _h("Weapon DMG +8% at 120+ Stamina, doubles while airborne", cond="stamina120", cond_stats={"weapon_dmg": 8}),
    "Sealskin": _h("Weapon DMG +8% while Dampened", cond="dampened", cond_stats={"weapon_dmg": 8}),
    "Shark Skin": _h("Weapon DMG +8% when fighting in water", cond="water", cond_stats={"weapon_dmg": 8}),
    "Deviated Shark Hide": _h("Weapon DMG +4.5%, doubled while fighting in water", {"weapon_dmg": 4.5}, "water", {"weapon_dmg": 9}),
    "Bubble Fish Skin": _h("Crit Rate +5% when fighting in water", cond="water", cond_stats={"crit_rate": 5}),
    "Bay Crocodile Skin": _h("Crit DMG +10% when fighting in water", cond="water", cond_stats={"crit_dmg": 10}),
    "Anglerfish Skin": _h("In water, Crit DMG +2% per 20% Sanity (counted at full Sanity)", cond="water", cond_stats={"crit_dmg": 10}),
    "Starfall Fox Skin": _h("Crit Rate +10% when not in combat", unmodeled=True),
    "Fox Skin": _h("Crit DMG +6% when not in combat", unmodeled=True),
    "Polar Fox Skin": _h("Crit Rate +5% when not in combat", unmodeled=True),
    "Desert Fox Skin": _h("Crit DMG +10% when not in combat", unmodeled=True),
    "Coastal Bay Crocodile Skin": _h("Crit DMG +10% while invisible", unmodeled=True),
    "Deer Hide": _h("Impact DMG +12% (melee/impact only)", unmodeled=True),
    "Hide": _h("Melee DMG +8%", unmodeled=True),
    "Crocodile Hide": _h("Melee DMG +10%", unmodeled=True),
}
# Where each mask hide comes from: (animal, breeding trait or None, note). Trait names from
# https://once-human.fandom.com/wiki/Ranching/Animal_Traits (Rank I/II/III = small/moderate/large extra yield).
HIDE_TRAITS_SRC = "https://once-human.fandom.com/wiki/Ranching/Animal_Traits"
_SEED = "Breed for the trait; higher rank gives more of this hide per harvest."
HIDE_ORIGIN: dict[str, tuple] = {
    "Golden Wool": ("Goat (ram or ewe)", "Golden Sheep Bloodline", "Also drops as a byproduct harvest, so the goat doesn't have to die. The best breeding target for most gun builds."),
    "Rock Wall Wool": ("Goat", "Rock Wall Seed", "Slaughter or byproduct harvest."),
    "Mountain Wool": ("Goat", "Mountain Seed", "Slaughter or byproduct harvest."),
    "Wool": ("Any goat", None, "Common; no trait needed."),
    "Lunar Wool": ("Lunar goat", None, "Lunar-variant animal; the wiki trait list doesn't name the trait."),
    "Rabbit Fur": ("Any rabbit", None, "Common; no trait needed."),
    "Dreamy Rabbit Fur": ("Rabbit", "Dreamy Seed", _SEED),
    "Lucky Rabbit Fur": ("Rabbit", "Lucky Seed", _SEED),
    "Lunar Rabbit Fur": ("Lunar rabbit", None, "Lunar-variant animal; the wiki trait list doesn't name the trait."),
    "Bear Skin": ("Any bear or polar bear", None, "Common; no trait needed."),
    "Floating Ice Bear Skin": ("Bear / polar bear", "Floating Ice Seed", _SEED),
    "Snowfield Bear Skin": ("Bear / polar bear", "Snowfield Seed", _SEED),
    "Cave Bear Skin": ("Bear / polar bear", "Cave Seed", _SEED),
    "Wolf Skin": ("Any wolf", None, "Common; no trait needed."),
    "Wasteland Wolf Skin": ("Wolf", "Wasteland Seed", _SEED),
    "Grassland Wolf Skin": ("Wolf", "Grassland Seed", _SEED),
    "Jungle Wolf Skin": ("Wolf", "Jungle Seed", _SEED),
    "Lunar Wolf Skin": ("Lunar wolf", None, "Lunar-variant animal; the wiki trait list doesn't name the trait."),
    "Cowhide": ("Any wild buffalo", None, "Also a byproduct of tamed buffalo."),
    "Mountain Cowhide": ("Wild buffalo", "Mountain Range Seed", _SEED),
    "Fox Skin": ("Any fox", None, "Common; no trait needed."),
    "Desert Fox Skin": ("Fox", "Desert Seed", _SEED),
    "Polar Fox Skin": ("Polar fox", "Polar Seed", _SEED),
    "Coastal Bay Crocodile Skin": ("Crocodile", "Coastal Bay Seed", _SEED),
    "Deer Hide": ("Any buck, doe or fawn", None, "Common; no trait needed."),
    "Hide": ("Boar, capybara or leopard", None, "Hunt only."),
    "Sealskin": ("Seal", None, "Hunt only."),
    "Crocodile Hide": ("Any crocodile", None, "Common; no trait needed."),
    "Bay Crocodile Skin": ("Crocodile", None, "Gold quality, so same Psi/HP boost as Golden Wool, but its mask effect only works in water."),
    "Velvet": ("Flamingo feathers", None, "Crafted from 5 Feathers at the Supplies Workbench (Leatherworking memetic)."),
}
for _n in list(MASK_HIDES):
    if _n.startswith("Dreamfused "):
        HIDE_ORIGIN.setdefault(_n, (_n.split(" ", 1)[1].split()[0] + " from the Dream Zone", "Dream Zone Genes",
                                    "Capture in the Dream Zone and breed the gene."))
    elif _n.startswith("Starfall "):
        HIDE_ORIGIN.setdefault(_n, ("Starfall creature", None, "Starfall scenario animal."))
    elif any(w in _n for w in ("Shark", "Squid", "Tuna", "Fish", "Anglerfish")):
        HIDE_ORIGIN.setdefault(_n, ("Sea creature", None, "Fished or hunted in water; not bred."))


# Starfall Cowhide airborne doubling
MASK_HIDES["Starfall Cowhide"]["cond2"] = ("airborne", {"weapon_dmg": 8})


def hide_stats(name: str | None, conds) -> tuple[dict, str | None]:
    """Stats for the mask hide given active fight conditions; second value = a 'not counted' note."""
    h = MASK_HIDES.get(name or "")
    if not h:
        return {}, None
    if h["unmodeled"]:
        return {}, f"{name} mask hide: {h['text']} (not counted for sustained boss damage)"
    conds = set(conds or [])
    d = dict(h["stats"])
    if h["cond"] and h["cond"] in conds:
        for k, v in h["cond_stats"].items():
            d[k] = max(d.get(k, 0), v) if k in h["stats"] else d.get(k, 0) + v
    c2 = h.get("cond2")
    if c2 and c2[0] in conds and h["cond"] in conds:
        for k, v in c2[1].items():
            d[k] = d.get(k, 0) + v
    note = None
    if h["cond"] and h["cond"] not in conds and not h["stats"]:
        note = f"{name} mask hide: needs “{HIDE_CONDS[h['cond']]}” (switch it on in Class & settings)"
    return d, note

# ------------------------------------------------------------------ secondary weapon
# The secondary is a support gun: shoot the boss once to put The Bull's Eye on it, swap back.
# Order = how easy the mark is to land (guaranteed > high chance > needs weakspot).
MARKERS = [
    ("AWS.338 - Bullseye", "First shot after swapping to it is a guaranteed mark, even on a body shot (15s cooldown). Best-in-slot.",
     "https://mmochronicles.com/en/guides/once-human/once-human-shrapnel-build-guide-best-socr-the-last-valor-setup-and-mods"),
    ("DE.50 - Wildfire", "About 60% chance to mark on hit and spreads the mark nearby. Easy budget pick.",
     "https://mmochronicles.com/en/guides/once-human/once-human-burn-build-guide-2026-best-kvd-boom-boom-loadout-shelterer-set-and-mods"),
    ("Recurve Crossbow", "Weakspot hit marks the target and gives extra Crit Rate. Needs one aimed bolt.",
     "https://www.oncehumandb.com/guides/best-weapons"),
    ("PDW90 - Holographic Resonance", "Marks in under a second of fire. Fine if you already own it.",
     "https://www.reddit.com/r/OnceHumanOfficial/comments/1wb60f6/best_secondary_build_or_weapon_to_run_to/"),
    ("DBSG - Doombringer", "Bull's Eye shotgun; works at close range.", "https://www.oncehumandb.com/guides/best-weapons"),
    ("DBSG - Old Huntsman", "Older Bull's Eye shotgun; works at close range.", "https://www.oncehumandb.com/guides/best-weapons"),
    ("Old Huntsman", "Older Bull's Eye shotgun; works at close range.", "https://www.oncehumandb.com/guides/best-weapons"),
]
MARKER_NAMES = [m[0] for m in MARKERS]
SECONDARY_SRC = "https://mmoculture.com/tips-guides/once-human-best-builds/"


# ------------------------------------------------------------------ helpers
def _kind(scenario: str | None) -> str:
    """boss / abyss / mobs, also for custom fights (they keep the kind they were built on)."""
    import forge_effects as _fe
    b = (scenario or "boss").split("@")[0]
    return (_fe.SCENARIOS.get(b) or {}).get("base", b)


def _scale_level(dev: dict, level: int | None) -> dict:
    lv = max(1, min(5, int(level or 5)))
    hi, lo = dev["stats"], dev.get("lv1") or dev["stats"]
    return {k: lo.get(k, v) + (v - lo.get(k, v)) * (lv - 1) / 4 for k, v in hi.items()}


def extra_sources(cfg: dict, weapon_kw: str | None, scenario: str) -> tuple[list[tuple[str, dict]], list[str]]:
    """Turn a build config into labelled stat dicts for forge.evaluate().

    cfg keys: key_armor, deviation, deviation_level, food, drink, calibration (dict with stats), marked (bool)
    """
    out: list[tuple[str, dict]] = []
    notes: list[str] = []
    marked = bool(cfg.get("marked")) or weapon_kw == "The Bull's Eye"

    ka = KEY_ARMOR.get(cfg.get("key_armor") or "")
    if ka:
        name = cfg["key_armor"]
        if ka.get("kw") and ka["kw"] != weapon_kw:
            notes.append(f"{name}: only works with {ka['kw']}")
        elif ka.get("weapons") and cfg.get("weapon") not in ka["weapons"]:
            notes.append(f"{name}: only works with {', '.join(ka['weapons'])}")
        elif ka.get("needs_mark") and not marked:
            notes.append(f"{name}: needs a Bull's Eye mark (turn on 'Bull's Eye support')")
        elif ka.get("unmodeled"):
            notes.append(f"{name}: {ka['text']} (not counted)")
        else:
            s = dict(ka["stats"])
            if ka.get("uptime") == "kw3s":
                s = {k: v * 0.85 for k, v in s.items()}  # re-triggered often in sustained fire
            out.append((f"{name} (key armor)", s))
            if ka.get("approx"):
                notes.append(f"{name}: estimate ({ka['approx']})")

    dv = DEVIATIONS.get(cfg.get("deviation") or "")
    if dv:
        name = cfg["deviation"]
        if dv.get("unmodeled"):
            notes.append(f"{name}: {dv['text']} (not counted)")
        elif dv.get("mobs_only") and _kind(scenario) != "mobs":
            notes.append(f"{name}: does not affect bosses")
        elif dv.get("kw") and dv["kw"] != weapon_kw:
            notes.append(f"{name}: only boosts {dv['kw']}")
        else:
            out.append((f"{name} (deviation)", _scale_level(dv, cfg.get("deviation_level"))))

    kept, dropped = fit_consumables(consumables_of(cfg), cfg.get("class"))
    for name in dropped:
        notes.append(f"{name}: no free {slot_label(CONSUMABLES[name]).lower()} slot for your class (not counted)")
    for name in kept:
        f = CONSUMABLES[name]
        kind = slot_label(f).lower()
        if f.get("kw") and f["kw"] != weapon_kw:
            notes.append(f"{name}: only helps {f['kw']}")
        elif f.get("needs_mark") and not marked:
            notes.append(f"{name}: needs a Bull's Eye mark")
        elif f.get("boss_only") and _kind(scenario) == "mobs":
            notes.append(f"{name}: bosses only")
        else:
            out.append((f"{name} ({kind})", dict(f["stats"])))
    cls = CLASSES.get(cfg.get("class") or "")
    if cls and cls.get("not_counted"):
        notes.append(f"{cls['label']}: {cls['not_counted']} (not counted)")

    hs, hnote = hide_stats(cfg.get("mask_hide"), cfg.get("hide_cond"))
    if hs:
        out.append((f"{cfg['mask_hide']} (mask hide)", hs))
    if hnote:
        notes.append(hnote)

    cal = cfg.get("calibration")
    if cal and cal.get("stats"):
        out.append((f"Calibration: {cal.get('label', '')}", dict(cal["stats"])))

    if cfg.get("map") or cfg.get("cradle"):
        import forge_cradle as _fc
        wtype = cfg.get("weapon_type")
        if not wtype and cfg.get("weapon"):
            try:
                import forge as _f
                wtype = (_f.gamedata()["weapons"].get(cfg["weapon"]) or {}).get("type")
            except Exception:
                wtype = None
        cs, cn = _fc.sources(cfg, wtype, weapon_kw, scenario)
        out += cs
        notes += cn
    return out, notes


def catalog() -> dict:
    return {
        "key_armor": {k: {"slot": v["slot"], "kw": v.get("kw"), "text": v["text"], "source": v["source"],
                          "approx": v.get("approx"), "unmodeled": v.get("unmodeled", False)} for k, v in KEY_ARMOR.items()},
        "deviations": {k: {"text": v["text"], "source": v["source"], "unmodeled": v.get("unmodeled", False), "typed": v.get("typed", False)} for k, v in DEVIATIONS.items()},
        "foods": {k: {"text": v["text"], "source": v["source"]} for k, v in FOODS.items()},
        "drinks": {k: {"text": v["text"], "source": v["source"], "approx": v.get("approx")} for k, v in DRINKS.items()},
        "consumables": {k: {"text": v["text"], "source": v["source"], "approx": v.get("approx"), "slots": list(v["slots"]),
                            "slot_label": slot_label(v), "kw": v.get("kw"), "typed": v.get("typed", False)} for k, v in CONSUMABLES.items()},
        "classes": CLASSES,
        "mask_hides": {k: {"text": v["text"], "cond": v["cond"], "unmodeled": v["unmodeled"],
                           "origin": dict(zip(("animal", "trait", "note"), HIDE_ORIGIN[k])) if k in HIDE_ORIGIN else None}
                       for k, v in MASK_HIDES.items()},
        "hide_traits_source": HIDE_TRAITS_SRC,
        "hide_conds": HIDE_CONDS, "hide_source": HIDE_SRC,
        "calibration": {"attack_max": CAL_ATTACK_MAX, "sub_max": CAL_SUB_MAX, "styles": CAL_STYLES, "source": CAL_BLOG, "list_source": CAL_WIKI_LIST, "season_source": CAL_SEASON_BLOG},
    }


def build_extras(cfg: dict, weapon_kw: str | None, scenario: str) -> list:
    """extra_sources() plus the Bull's Eye support toggle, in evaluate(extras=...) format."""
    srcs, notes = extra_sources(cfg, weapon_kw, scenario)
    import forge_effects as _fe
    sc = _fe.SCENARIOS.get((scenario or "boss").split("@")[0]) or {}
    if sc.get("buffs"):
        srcs.append((f"Fight buff: {sc.get('label')}", dict(sc["buffs"])))
    if sc.get("unparsed"):
        notes.append(f"{sc.get('label')}: " + "; ".join(sc["unparsed"])[:200] + " (not counted)")
    if cfg.get("marked") and weapon_kw != "The Bull's Eye":
        srcs.append(("Bull's Eye support (mark on target)", {"_marked": 1, "vulnerability": 16 if cfg.get("vuln_amp") else 8}))
    return srcs + [("_notes", notes)]


def _style_stats(ent: dict, value) -> dict:
    """Stats for a style entry; value = the rarity-dependent number typed by the user (or default)."""
    d = dict(ent["stats"])
    var = ent.get("var")
    if var:
        v = var["default"] if value in (None, "") else max(0.0, min(float(var.get("max", 100)), float(value)))
        if var["key"] == "_reload_kw_guarantee_pct":
            d["_reload_kw_guarantee"] = d.get("_reload_kw_guarantee", 0) + v / 100.0
        else:
            d[var["key"]] = d.get(var["key"], 0) + var["sign"] * v
    return d


def calibration_from_profile(cal: dict | None, wtype: str) -> dict:
    """Profile calibration {style, attack, sub, sub_value} -> stat dict."""
    if not cal or not cal.get("style"):
        return {}
    ent = cal_style(weapon_family(wtype), cal["style"])
    if not ent:
        return {}
    st = _style_stats(ent, cal.get("style_value"))
    st["attack"] = st.get("attack", 0) + float(cal.get("attack") or 0)
    if cal.get("sub") in CAL_SUB_MAX:
        st[cal["sub"]] = st.get(cal["sub"], 0) + float(cal.get("sub_value") or 0)
    return st
