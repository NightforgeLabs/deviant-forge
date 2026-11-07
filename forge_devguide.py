"""Deviation guide: what every deviation does in plain words, whether to keep it, and which rating matters.

Ratings: every deviation has Skill Rating (1-5, how well it does its job: damage, buff size, yield) and
Activity Rating (1-5, how long it works before resting and how fast it recovers). Players write them as
"Skill/Activity", e.g. a 4/4 Digby or a 5/1 Lonewolf.

Roles and jobs: Fandom deviation list (https://once-human.fandom.com/wiki/Deviation/list) and the ability
text on oncehuman.th.gl. Verdicts and "which rating matters" are the app's calls (hand-written; check them).
"""
from __future__ import annotations

SRC_LIST = "https://once-human.fandom.com/wiki/Deviation/list"
SRC_RATING = "https://once-human.fandom.com/wiki/Deviation"
SRC_THGL = "https://oncehuman.th.gl/db/deviations"

# tier: must | strong | situational | low | pvp
# rating: skill | activity | both | none   (which number decides keep/toss)
# tag: combat | resources | base | crafting | comfort | defense
G = {}


def _d(name, role, tag, job, tier, rating, why=""):
    G[name] = {"role": role, "tag": tag, "job": job, "tier": tier, "rating": rating, "why": why}


# ---- combat (synced in the cradle; skills scale with Psi Intensity)
_d("Lonewolf's Whisper", "Combat", "combat", "Marks a target, pulls aggro and makes it take more Weapon DMG; leaves a clone when the target dies.",
   "must", "skill", "Best all-round damage deviation for gun builds.")
_d("Butterfly's Emissary", "Combat", "combat", "Auto-attacks and makes weakspot hits hit harder.", "must", "skill",
   "Top pick for weakspot builds (snipers, Fast Gunner, Bounce on heads).")
_d("Zapamander", "Combat", "combat", "Auto-attacks and makes the target take more Power Surge DMG.", "must", "skill",
   "The pick for Power Surge / Shock builds.")
_d("Pyro Dino", "Combat", "combat", "Breathes fire; makes targets take more Blaze DMG.", "strong", "skill", "Burn builds.")
_d("Chaosaurus", "Combat", "combat", "Chaos Pyro Dino: more Blaze DMG taken, and burning targets explode.", "strong", "skill", "Burn builds.")
_d("Polar Jelly", "Combat", "combat", "Area Frost DMG, slows and pulls enemies, boosts Frost DMG.", "strong", "skill", "Frost Vortex builds and crowds.")
_d("Snowsprite", "Combat", "combat", "Drops Ice Crystals that burst for Frost DMG and make the target take more Frost DMG.", "strong", "skill", "Frost builds.")
_d("Chaos Snowsprite", "Combat", "combat", "Chaos Snowsprite: same Ice Crystal Frost boost.", "strong", "skill", "Frost builds.")
_d("Shattered Maiden", "Combat", "combat", "Marks a target and auto-attacks.", "strong", "skill", "Solid general damage.")
_d("Mini Feaster", "Combat", "combat", "Tentacles on the target; up to +70% Weapon DMG with Bounce builds.", "strong", "skill", "Bounce builds.")
_d("ZapCam", "Combat", "combat", "Teleports to the target, photographs it for Status DMG and makes it take more Weapon DMG.", "strong", "skill")
_d("Soul Summoner", "Combat", "combat", "Auto-attacks for Status DMG and makes the target take more Weapon DMG.", "strong", "skill")
_d("Whalepup", "Combat", "combat", "Auto-attacks; more Weapon DMG taken, extra Vulnerability on drowning targets.", "situational", "skill", "Water fights.")
_d("Invincible Sun", "Combat", "combat", "Area Blaze DMG around you.", "situational", "skill", "Crowds, burn builds.")
_d("Grumpy Bulb", "Combat", "combat", "Area status damage; confuses enemies so they fight each other.", "situational", "skill", "Mob-heavy content.")
_d("Voodoo Doll", "Combat", "combat", "Reflects damage from a target; a double absorbs hits.", "situational", "skill", "Survival / status builds.")
_d("Festering Gel", "Combat", "combat", "Builds a fortification that heals and restores Sanity.", "situational", "skill", "Keep one for hard content and healing.")
_d("By-the-Wind", "Combat", "combat", "Floating zone: fly at a fixed height, +move speed, no fall damage or stagger.", "situational", "activity", "Aero / airborne builds and travel.")
_d("Behemoth", "Combat", "combat", "Floating zone like By-the-Wind (+move and jump speed, no fall damage).", "situational", "activity", "Airborne builds.")
_d("Brave George", "Combat", "combat", "Floating zone like By-the-Wind.", "situational", "activity", "Airborne builds.")
_d("Radiant One", "Combat", "combat", "Floating zone like By-the-Wind.", "situational", "activity", "Airborne builds.")
_d("Enchanting Void", "Combat", "combat", "Black Cat form: faster with melee weapons, heals on melee hits.", "situational", "skill", "Melee builds only.")
_d("Mini Wonder", "Combat", "combat", "Absorbs bullets and refills your magazine from reserves.", "low", "skill")
_d("Chaos - Mini Wonder", "Combat", "combat", "Absorbs bullets and refills your magazine; buffs an ally.", "low", "skill")
_d("Zeno-Purifier", "Combat", "combat", "Teleports you to its target with a melee attack.", "low", "skill")
_d("Snapshot", "Combat", "combat", "Locks onto enemies while you aim and auto-attacks.", "low", "skill")
_d("Mr. Wish", "Combat", "combat", "Shoots targets and marks them with The Bull's Eye.", "pvp", "skill", "PvP servers.")
_d("Chaos Mr. Wish", "Combat", "combat", "Auto-attacks and marks targets with The Bull's Eye.", "situational", "skill",
   "Free Bull's Eye mark without a secondary gun.")
_d("Dr. Teddy", "Combat", "combat", "Instant 50% heal, heal over time and revives.", "pvp", "skill", "PvP servers.")

# ---- territory: resources
_d("The Digby Boy", "Territory", "resources", "Mines ore (up to silver); runs the Mining Operation Platform for higher ores.",
   "must", "both", "Activity keeps it mining longer; Skill makes each trip better.")
_d("Cattiva", "Territory", "resources", "Collab miner: mines ore like the Digby Boy.", "must", "both", "Same job as the Digby Boy.")
_d("Logging Beaver", "Territory", "resources", "Cuts logs; rare chance to find furniture.", "must", "both")
_d("Fetch-A-Lot Bunny", "Territory", "resources", "Harvests shrubs (fibers, fruit).", "strong", "activity")
_d("Lethal Rabbit", "Territory", "resources", "Collects animal resources (meat, hides).", "strong", "activity", "Good with a ranch.")
_d("Hydronaut Fish", "Territory", "resources", "Gathers sea water and fish; speeds up water filters and brewing barrels.", "strong", "activity")
_d("Tar Pudding", "Territory", "resources", "Gathers fuel; speeds up refining.", "strong", "activity")
_d("H37", "Territory", "resources", "Scavenges materials.", "situational", "activity")
_d("Growshroom", "Territory", "resources", "Plants seeds, collects crops and speeds up growth.", "must", "activity",
   "A 2/5 out-farms a 5/2: it stays awake longer.")
_d("Buzzy Bee", "Territory", "resources", "Higher chance for crops to mutate (better crops).", "strong", "activity")
_d("Rain Man", "Territory", "resources", "Sets every plant's water to perfect, even if overwatered.", "strong", "activity")
_d("Director Fox", "Territory", "resources", "Ranch animals may have an extra baby when breeding (uses Fine Meat).", "strong", "activity",
   "Great if you breed animals for hides.")
# ---- territory: base boosts
_d("Electric Eel", "Territory", "base", "More power from your generators.", "must", "both")
_d("Flame Essence", "Territory", "base", "Faster furnaces (ingots).", "must", "both", "Skill 5 roughly halves smelting time.")
_d("Chefosaurus Rex", "Territory", "base", "Cooks faster and makes dishes stronger.", "must", "skill", "As a Chef, keep the best one you can find.")
_d("Berserkosaurus Rex", "Territory", "base", "Raises your cooking proficiency.", "strong", "skill", "Chef helper.")
_d("Doctor Raven", "Territory", "base", "Faster Supplies Workbench; Healing Syringes sometimes get a bonus effect.", "strong", "skill")
_d("Rebecca", "Territory", "base", "Mitsuko plays piano: other deviations recover energy faster.", "strong", "skill")
_d("Chaos - Rebecca", "Territory", "base", "Chaos Rebecca: deviations recover energy faster.", "strong", "skill")
_d("Paper Doll", "Territory", "base", "Repairs walls, floors and the filter; extra drops from Purification.", "situational", "activity")
_d("Duet", "Territory", "base", "Changes the weather inside your territory.", "low", "none", "Cosmetic / farming convenience; no combat effect.")
_d("Strange Door", "Territory", "base", "Makes portal pieces so you can teleport between two points.", "strong", "none", "Keep one; ratings barely matter.")
_d("Wish Box", "Territory", "base", "Turns items you feed it into other items.", "situational", "none")
# ---- territory: defense
_d("Nutcracker", "Territory", "defense", "Mobile turret that defends your base.", "situational", "skill")
_d("Gazocchio", "Territory", "defense", "Patrols and attacks intruders; makes items that clear shadow effects.", "situational", "skill")
# ---- comfort (sleep / sanity)
_d("Extradimensional Cat", "Territory", "comfort", "Sleeps with you in your bed: extra healing (Cat Snooze).", "situational", "none",
   "Helps you sleep better. Keep one, toss duplicates.")
_d("Chaotic Extradimensional Cat", "Territory", "comfort", "Chaos cat: sleeps with you for the rested buff.", "situational", "none", "Keep one.")
_d("Chillet", "Territory", "comfort", "Collab: sleeps with you for the rested buff.", "situational", "none", "Keep one sleep buddy total.")
_d("Peach Weasel", "Territory", "comfort", "Collab: sleeps with you for the rested buff.", "situational", "none", "Keep one sleep buddy total.")
_d("Blackback", "Territory", "comfort", "Follows you and keeps restoring Sanity.", "situational", "activity", "Keep one Sanity pet.")
_d("Doberman", "Territory", "comfort", "Follows you and keeps restoring Sanity.", "situational", "activity", "Keep one Sanity pet.")
_d("Labrador", "Territory", "comfort", "Follows you and keeps restoring Sanity.", "situational", "activity", "Keep one Sanity pet.")
# ---- crafting (make one special item)
for n, job, tier, why in [
    ("Atomic Snail", "Makes Tunneling Fluid for Aero Leap.", "situational", "Keep if you play airborne builds."),
    ("Orb Lightning", "Makes Plasma for Lightning Bottles (throwable).", "situational", ""),
    ("Snow Globe", "Makes Snowdust for Snowballs.", "low", ""),
    ("Pup Buddy", "Makes Small Balloons for Featherweight (slow fall).", "situational", ""),
    ("Frog the Leaper", "Makes Silver Spring for Spring Legs, and Universal Bait for fishing.", "situational", "Keep if you fish."),
    ("Space Turner", "Makes Spatial Keystone for Space Twister.", "low", ""),
    ("Dreamcatcher", "Makes Thread of Dreams for The Weaver.", "low", "Activity matters more than Skill here."),
    ("Harveseed", "Makes Heart Vine for Chloro-armor.", "low", ""),
    ("Disco Ball", "Makes Inspiration Fragments for Utter Delight.", "low", ""),
    ("Gingerbread House", "Makes Cracker Crumbs for Transformation Cookies.", "low", ""),
    ("Hug-in-a-Bowl", "Makes Homestyle Noodles for the Hug-In-A-Bowl dish.", "situational", "Chef food ingredient."),
    ("Atomic Lighter", "Makes Split-Core Cotton for the Fusion Lighter.", "low", ""),
    ("Ice Pot", "Makes Sticky Ice Crystals.", "low", ""),
    ("Upper World Spawn", "Makes Upper World Feathers (PvP protection item).", "pvp", ""),
    ("Masonic Pyramid", "Makes items for invisibility and 'being aimed at' alerts (PvP).", "pvp", ""),
    ("Party Monkey", "Builds a facility that pulls nearby monsters' aggro.", "situational", "A decoy for hard fights."),
    ("Artisan's Touch", "One-use: repairs your least durable crafted gear.", "low", ""),
]:
    _d(n, "Crafting", "crafting", job, tier, "activity", why or "Keep one if you use the item; otherwise toss.")

TIER_LABEL = {"must": "Must have", "strong": "Strong", "situational": "Situational", "low": "Can toss", "pvp": "PvP only"}
TAG_LABEL = {"combat": "Combat", "resources": "Gets resources", "base": "Base boost", "crafting": "Crafts an item",
             "comfort": "Comfort / sleep", "defense": "Base defense"}


def keep_verdict(name: str, skill: int, activity: int) -> dict:
    """Keep / toss call for one deviation at Skill/Activity ratings (1-5)."""
    g = G.get(name) or {"tier": "situational", "rating": "both", "role": "?"}
    s, a = max(1, min(5, int(skill))), max(1, min(5, int(activity)))
    r = g["rating"]
    if g["tier"] == "pvp":
        return {"keep": "toss", "text": "PvP only. Toss it on PvE servers."}
    if r == "none":
        return {"keep": "keep", "text": "Ratings barely matter for this one. Keep one, toss duplicates."}
    key = s if r == "skill" else a if r == "activity" else None
    which = {"skill": "Skill", "activity": "Activity"}.get(r)
    if key is not None:
        other = a if r == "skill" else s
        if key == 5:
            return {"keep": "keep", "text": f"Keep. {which} 5 is the top roll" + (" — a perfect one." if other == 5 else f"; the other number ({other}) matters less.")}
        if key == 4:
            return {"keep": "keep", "text": f"Keep until you find a {which} 5."}
        if key == 3 and g["tier"] in ("low", "situational"):
            return {"keep": "maybe", "text": f"Fine for now; swap when you catch a better {which.lower()} roll."}
        return {"keep": "toss", "text": f"Toss or use as fusion fodder once you have {'an' if which == 'Activity' else 'a'} {which} 4+. {which} is the number that matters here."}
    tot = s + a
    if tot >= 9:
        return {"keep": "keep", "text": "Keep. Both numbers are high."}
    if tot >= 7 and min(s, a) >= 3:
        return {"keep": "keep", "text": "Keep until you find a 5/4 or better."}
    if min(s, a) <= 2:
        low = "Skill" if s < a else "Activity"
        return {"keep": "toss", "text": f"Toss once you have a better one: {low} {min(s, a)} drags it down. Both numbers matter for this one."}
    return {"keep": "maybe", "text": "Usable. Replace it when you catch a higher pair."}


def catalog() -> dict:
    return {"guide": G, "tiers": TIER_LABEL, "tags": TAG_LABEL,
            "sources": {"list": SRC_LIST, "rating": SRC_RATING, "thgl": SRC_THGL}}
