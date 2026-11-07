"""Turn Once Human effect text into numeric stat contributions.

Every parsed effect returns a list of Contribution objects. Conditional
effects (timed buffs, stacking buffs, low-HP clauses...) get an *uptime*
multiplier from the active scenario so that a "+30% for 2s after reload"
does not count the same as a permanent "+30%".

Anything the parser cannot understand is reported back as `unmodeled` so the
UI can show the player exactly which effects were NOT counted.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

KEYWORDS = ["Power Surge", "Burn", "Frost Vortex", "Unstable Bomber", "Shrapnel", "Bounce",
            "Fast Gunner", "Fortress Warfare", "The Bull's Eye"]
KEYWORD_ELEMENT = {"Power Surge": "Shock", "Burn": "Blaze", "Frost Vortex": "Frost", "Unstable Bomber": "Blast"}
ELEMENTS = ["Shock", "Blaze", "Frost", "Blast"]

# Stat keys used by the damage model.  Values are percentages (12 == +12%).
STAT_ALIASES = [
    (r"weapon dmg", "weapon_dmg"),
    (r"crit dmg", "crit_dmg"),
    (r"crit rate", "crit_rate"),
    (r"weakspot dmg", "weakspot_dmg"),
    (r"status dmg", "status_dmg"),
    (r"elemental dmg", "elemental_dmg"),
    (r"(?:all )?dmg boost", "dmg_boost"),
    (r"dmg against (?:enemies|normal enemies|great ones|bosses)", "vs_enemies"),
    (r"(?:dmg|damage) (?:to|against) (?:elite|boss)", "vs_enemies"),
    (r"attack", "attack"),
    (r"fire rate", "fire_rate"),
    (r"magazine capacity", "magazine"),
    (r"reload speed", "reload_speed"),
    (r"psi intensity", "psi"),
    (r"vulnerability", "vulnerability"),
    (r"melee dmg", "melee_dmg"),
]
for _kw in KEYWORDS:
    _k = _kw.lower().replace("the ", "").replace("'", "").replace(" ", "_")
    STAT_ALIASES.insert(0, (re.escape(_kw.lower()) + r" final dmg", f"kw_final:{_kw}"))
    STAT_ALIASES.insert(0, (re.escape(_kw.lower()) + r"(?: trigger| activation)? chance", f"kw_chance:{_kw}"))
    STAT_ALIASES.insert(0, (r"(?:weapon )?trigger chance for " + re.escape(_kw.lower()), f"kw_chance:{_kw}"))
    STAT_ALIASES.insert(0, (re.escape(_kw.lower()) + r" (?:crit dmg)", f"kw_crit_dmg:{_kw}"))
    # mod suffix lines "<Shrapnel> Shrapnel Crit / Shrapnel Weakspot" are Crit DMG / Weakspot DMG
    # (https://www.reddit.com/r/OnceHumanOfficial/comments/1qk8j4c/)
    STAT_ALIASES.insert(0, (re.escape(_kw.lower()) + r" crit", f"kw_crit_dmg:{_kw}"))
    STAT_ALIASES.insert(0, (re.escape(_kw.lower()) + r" weakspot(?: dmg)?", f"kw_ws_dmg:{_kw}"))
    STAT_ALIASES.insert(0, (re.escape(_kw.lower()) + r" crit rate", f"kw_crit_rate:{_kw}"))
    STAT_ALIASES.insert(0, (re.escape(_kw.lower()) + r" dmg", f"kw_dmg:{_kw}"))
for _el in ELEMENTS:
    STAT_ALIASES.insert(0, (re.escape(_el.lower()) + r"(?: elemental)?(?: dmg)?", f"el:{_el}"))
# "Explosive"/"Blast" DMG are Unstable Bomber bonuses in game text
STAT_ALIASES.insert(0, (r"explosive dmg", "kw_dmg:Unstable Bomber"))
STAT_ALIASES.insert(0, (r"explosive final dmg", "kw_final:Unstable Bomber"))


from functools import lru_cache


@lru_cache(maxsize=None)
def stat_key(name: str) -> str | None:
    n = name.lower().strip().strip(":")
    n = re.sub(r"\s+", " ", n)
    for pattern, key in STAT_ALIASES:
        if re.fullmatch(pattern, n) or re.fullmatch(pattern + r"(?: bonus)?", n):
            return key
    for pattern, key in STAT_ALIASES:
        if re.search(r"\b" + pattern + r"\b", n):
            return key
    return None


@dataclass
class Contribution:
    stat: str
    value: float          # percent, already multiplied by uptime
    raw: float            # percent at full effect
    uptime: float
    note: str = ""


@dataclass
class ParsedEffect:
    text: str
    contributions: list[Contribution] = field(default_factory=list)
    unmodeled: list[str] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)


# --------------------------------------------------------------------- uptime
SCENARIOS = {
    "boss": {
        "label": "Single boss / elite, sustained fire",
        "kill_uptime": 0.15, "reload_uptime_per_s": 0.18, "low_hp": 0.25, "high_hp": 0.8,
        "weakspot_rate": 0.35, "enemies_hit": 1, "airborne": 0.0, "shield": 0.3,
        "stack_fill": 0.9, "first_hit": 0.1, "moving": 0.3, "shrapnel_parts": 2,
    },
    "abyss": {
        "label": "Abyss / Nightmare dungeon boss (no cradle)",
        "kill_uptime": 0.15, "reload_uptime_per_s": 0.18, "low_hp": 0.25, "high_hp": 0.8,
        "weakspot_rate": 0.35, "enemies_hit": 1, "airborne": 0.0, "shield": 0.3,
        "stack_fill": 0.9, "first_hit": 0.1, "moving": 0.3, "shrapnel_parts": 2,
    },
    "mobs": {
        "label": "Groups of normal enemies (silos, events)",
        "kill_uptime": 0.75, "reload_uptime_per_s": 0.18, "low_hp": 0.25, "high_hp": 0.8,
        "weakspot_rate": 0.25, "enemies_hit": 3, "airborne": 0.0, "shield": 0.3,
        "stack_fill": 0.85, "first_hit": 0.2, "moving": 0.5, "shrapnel_parts": 2,
    },
}


# --------------------------------------------------------------------- play effort
# Same fight, different amount of work from the player. "normal" = the plain fight type.
VISION_UPTIME = {"Lunar": 0.3, "Crescent": 0.4, "Downstar": 0.15, "Aero": 0.0, "Resonance": 0.7}
EFFORTS = {
    "easy": {
        "label": "Koala", "short": "Easy mode",
        "desc": "Hold the trigger on the body. No jumping, no weapon swapping, no playing at low HP, no positioning tricks.",
        "scn": {"weakspot_rate": 0.15, "airborne": 0.0, "moving": 0.1, "low_hp": 0.0, "first_hit": 0.05, "stack_fill": 0.85},
        "vision": {"Lunar": 0.0, "Crescent": 0.3, "Downstar": 0.05, "Aero": 0.0, "Resonance": 0.7},
        "marked": False, "hide_cond": [],
    },
    "normal": {
        "label": "Normal", "short": "Normal play",
        "desc": "Aim for weak spots some of the time, mark the boss if you set it up, stay grounded.",
        "scn": {}, "vision": dict(VISION_UPTIME), "marked": None, "hide_cond": None,
    },
    "max": {
        "label": "Try-hard", "short": "Max effort",
        "desc": "Hit weak spots most of the time, jump or fight from high ground constantly, swap to mark the boss, "
                "play at low HP when it pays off.",
        "scn": {"weakspot_rate": 0.6, "airborne": 0.6, "moving": 0.6, "low_hp": 0.45, "first_hit": 0.15, "stack_fill": 1.0},
        "vision": {"Lunar": 0.6, "Crescent": 0.6, "Downstar": 0.4, "Aero": 0.6, "Resonance": 0.8},
        "marked": True, "hide_cond_add": ["airborne", "moving", "stamina90", "low_hp"],
    },
}


def split_key(key: str | None) -> tuple[str, str]:
    """'boss@easy' -> ('boss', 'easy'). Plain keys are normal effort."""
    base, _, eff = (key or "boss").partition("@")
    return (base if base in SCENARIOS else "boss"), (eff if eff in EFFORTS else "normal")


_SCN_CACHE: dict = {}


def scn(key: str | None) -> dict:
    if key not in _SCN_CACHE:
        base, eff = split_key(key)
        d = dict(SCENARIOS[base])
        d.update(EFFORTS[eff]["scn"])
        d["vision"] = EFFORTS[eff]["vision"]
        _SCN_CACHE[key] = d
    return _SCN_CACHE[key]


@lru_cache(maxsize=4096)
def mentioned_keywords(text: str) -> frozenset[str]:
    """Keywords a text names. Cached: the same mod/set texts are checked ~850k times per optimize."""
    t = text.lower()
    found = set()
    for kw in KEYWORDS:
        k = kw.lower().replace("the ", "")
        if k == "burn":
            if re.search(r"\bburn(?:ing)?\b", t):
                found.add(kw)
        elif k in t:
            found.add(kw)
    if "marked" in t or "bull's eye" in t or "the mark" in t:
        found.add("The Bull's Eye")
    return frozenset(found)


def timed_uptime(duration: float, trigger_every: float) -> float:
    """Fraction of time a buff of `duration` seconds is up if retriggered every `trigger_every` s."""
    if trigger_every <= 0:
        return 1.0
    return max(0.0, min(1.0, duration / trigger_every))


def estimate_uptime(text: str, scn: dict, ctx: dict) -> tuple[float, list[str]]:
    t = text.lower()
    up, why = 1.0, []
    hits_per_s = ctx.get("hits_per_s", 8.0)
    cycle = ctx.get("reload_cycle_s", 6.0)
    dur_m = re.search(r"for (\d+(?:\.\d+)?)\s*s(?:ec(?:onds?)?)?\b", t)
    dur = float(dur_m.group(1)) if dur_m else None

    if re.search(r"after (?:killing|defeating)|upon (?:killing|defeating)|when (?:you )?(?:kill|defeat)", t):
        up *= scn["kill_uptime"]; why.append("needs kills")
    if re.search(r"after reload|upon reload|after reloading|when reloading|next reload|first .* after reload", t):
        if dur:
            up *= timed_uptime(dur, cycle); why.append(f"{dur:g}s after each reload")
        elif "until next reload" not in t:
            up *= 0.5; why.append("reload-linked")
    if re.search(r"hp (?:is )?(?:below|lower than|less than)|lower your hp|the lower your hp", t):
        up *= scn["low_hp"]; why.append("low HP only")
    if re.search(r"hp (?:is )?(?:above|higher than|more than)|full hp|hp is full", t):
        up *= scn["high_hp"]; why.append("high HP only")
    if re.search(r"aerial|airborne|in the air|while (?:jumping|falling)", t):
        up *= max(scn["airborne"], 0.0); why.append("airborne only")
    if re.search(r"shield", t) and re.search(r"(?:when|while|if) .*shield|based on shield", t):
        su = ctx.get("shield_uptime") or scn["shield"]
        up *= su; why.append("needs shield" + (" (Savior 3pc keeps it up)" if ctx.get("shield_uptime") else ""))
    if re.search(r"magazine is empty|last bullet|when the magazine", t):
        up *= 0.35 if dur else 0.1; why.append("empty-magazine trigger")
    if re.search(r"when (?:taking|you take) damage|after taking damage|when hit", t):
        up *= 0.5; why.append("when taking damage")
    if re.search(r"crouch|sliding|while aiming down|hip ?fire", t):
        up *= 0.6; why.append("stance-dependent")
    if re.search(r"multiple enemies|each enemy|enemies hit|more targets", t):
        if scn["enemies_hit"] <= 1:
            up *= 0.3; why.append("multi-target")
    if re.search(r"after switching weapons|after switching to", t):
        up *= 0.15; why.append("only right after weapon swap")
    if re.search(r"more than \d+ ?(?:meters|m)\b away|target more than", t):
        up *= scn.get("long_range", 0.4); why.append("long range only")
    if re.search(r"max hp consumed|hp consumed|hp lost", t):
        up *= scn["low_hp"] if scn["low_hp"] > 0.4 else 0.45; why.append("scales with HP lost")
    kwt = re.search(r"(?:after )?triggering (" + "|".join(re.escape(k.lower()) for k in KEYWORDS) + r")", t)
    if dur and not why and kwt:
        trig = max(ctx.get("kw_procs_per_s", 0.0), 0.05)
        if re.search(r"(?:stack|stacks)\s*(?:up to|to)?\s*\d+|up to \d+ stacks|stacking up to", t):
            why.append("stacks per keyword trigger")  # stack count handled in parse_effect
        else:
            up *= timed_uptime(dur, 1.0 / trig); why.append(f"{dur:g}s after each {kwt.group(1)}")
    elif dur and not why:
        # Generic "on hit / on crit / on weakspot gain X for Ns": frequent triggers.
        trig = hits_per_s
        if "weakspot" in t:
            trig *= scn["weakspot_rate"]
        if "crit" in t and "crit dmg +" not in t[:12]:
            trig *= max(ctx.get("crit_rate", 0.2), 0.05)
        m = re.search(r"cooldown[: ]+(\d+(?:\.\d+)?)", t)
        every = max(1.0 / max(trig, 0.01), float(m.group(1)) if m else 0)
        up *= timed_uptime(dur, every); why.append(f"{dur:g}s timed buff")
    return max(0.0, min(1.0, up)), why


def stack_count(text: str, scn: dict) -> tuple[float, str | None]:
    t = text.lower()
    m = re.search(r"(?:stack|stacks)\s*(?:up to|to)?\s*(\d+)\s*times?(?:\(s\))?|up to (\d+) stacks|max(?:imum)? stacks?:?\s*(\d+)|stacking up to (\d+)", t)
    if not m:
        return 1.0, None
    n = int(next(g for g in m.groups() if g))
    return n * scn["stack_fill"], f"{n} stacks (~{int(scn['stack_fill']*100)}% filled)"


VAL = r"([+-]?\d+(?:\.\d+)?)\s*%"


def parse_effect(text: str, scn: dict, ctx: dict) -> ParsedEffect:
    out = ParsedEffect(text=text)
    if not text:
        return out
    clean = re.sub(r"\s+", " ", text.replace("\u00a0", " "))
    # "Element DMG (Blaze, Frost, Shock, Blast) +8%" -> one entry per listed element
    clean = re.sub(r"Elements? DMG \(([^)]*)\)\s*\+\s*" + VAL,
                   lambda m: ", ".join(f"{e.strip()} DMG +{m.group(2)}%" for e in m.group(1).split(",") if e.strip()), clean)
    # "Weapon DMG and Status DMG dealt increases by +10%" -> "Weapon DMG and Status DMG +10%"
    clean = re.sub(r"(DMG|Rate|Chance)(?: dealt)? increases? by \+?\s*(?=\d)", r"\1 +", clean)
    uptime, why = estimate_uptime(clean, scn, ctx)
    stacks, stack_note = stack_count(clean, scn)
    if "stacks per keyword trigger" in why and stack_note:
        dm = re.search(r"for (\d+(?:\.\d+)?)\s*s", clean.lower())
        nmax = stacks / scn["stack_fill"]
        stacks = min(nmax, max(ctx.get("kw_procs_per_s", 0.0), 0.05) * float(dm.group(1))) if dm else stacks
        stack_note = f"about {stacks:.0f} of {nmax:.0f} stacks at this trigger rate"
    out.conditions = why + ([stack_note] if stack_note else [])
    found = False
    # Pattern A: "<Stat> +X%"  /  "<Stat> and <Stat> +X%"
    for m in re.finditer(r"((?:[A-Z][A-Za-z'.]*\s?){1,5}(?:DMG|Rate|Attack|Intensity|Capacity|Speed|Chance|Vulnerability|Boost)(?:\s+and\s+(?:[A-Z][A-Za-z'.]*\s?){1,4}(?:DMG|Rate|Chance))?)\s*(?:by\s*)?\+\s*" + VAL, clean):
        names, val = m.group(1), float(m.group(2))
        for part in re.split(r"\s+and\s+", names):
            key = stat_key(part)
            if not key:
                out.unmodeled.append(part.strip()); continue
            # Stack multiplier only if the stacking clause follows this value
            seg = clean[m.end():m.end() + 90].lower()
            mult = stacks if (stack_note and ("stack" in seg or "stack" in clean[:m.start()].lower()[-60:])) else 1.0
            out.contributions.append(Contribution(key, val * mult * uptime, val * mult, uptime))
            found = True
    # Pattern B: "Increases <stat> by X%"
    for m in re.finditer(r"[Ii]ncreases? ((?:[A-Za-z'.]+\s){1,5}?)by\s*" + VAL, clean):
        key = stat_key(m.group(1))
        if key and not any(c.stat == key for c in out.contributions):
            out.contributions.append(Contribution(key, float(m.group(2)) * uptime, float(m.group(2)), uptime))
            found = True
    # Pattern C: "Each 1% Crit Rate grants +0.7% Unstable Bomber DMG" -> handled by ctx later
    m = re.search(r"each 1% ([a-z ]+?) grants \+?" + VAL + r" ([A-Za-z' ]+DMG)", clean, re.I)
    if m:
        out.contributions.append(Contribution(f"per:{stat_key(m.group(1)) or m.group(1)}:{stat_key(m.group(3)) or m.group(3)}",
                                              float(m.group(2)), float(m.group(2)), 1.0, "scales with another stat"))
        found = True
    # Extra damage instances based on Psi Intensity or Attack -> proc damage
    for m in re.finditer(r"(?:deal|dealing|deals)[^.]*?(\d+(?:\.\d+)?)%\s*(?:of\s*)?(Psi Intensity|Attack)", clean, re.I):
        out.contributions.append(Contribution("proc_note", 0, float(m.group(1)), uptime,
                                              f"extra hit {m.group(1)}% {m.group(2)}"))
    if not found and not out.contributions:
        out.unmodeled.append(clean[:140])
    return out


def merge(contribs: list[Contribution]) -> dict[str, float]:
    tot: dict[str, float] = {}
    for c in contribs:
        if c.stat == "proc_note":
            continue
        tot[c.stat] = tot.get(c.stat, 0.0) + c.value
    return tot
