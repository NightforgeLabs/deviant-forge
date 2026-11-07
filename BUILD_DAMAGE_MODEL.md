# Saved-build primary-fire comparison

This model reads **two saved catalog builds** through `/api/planned-compare`. It audits every selected mod on both sides, including unchanged mods, and reached armor thresholds. It never changes confirmed inventory. A conditional scoped winner is distinct from a full-build DPS winner.

## Sources and exact numeric coverage

- The [official Field Guide overhaul](https://www.oncehuman.game/news/devBlog/20251212/40781_1276354.html) fixes current subattributes, maps levels 1–17 to four ordered tiers, and says a Shiny Lv. 17 mod retains the ordinary Lv. 17 subattributes while its main effect increases.
- The [official Gravity Abyss preview](https://www.oncehuman.game/news/devBlog/20260522/40781_1301328.html) contains [two pictured Shiny Lv. 17 cards](research/official-gravity-en-6.png): Elemental Resonance `<Aero>` and Ferocious Charge `<Downstar>`. The reviewed transcription, image hash, variants, ordered attributes, conditional additions, and Flash effects are in [official_mod_cards.json](research/official_mod_cards.json). `tools/import_official_mod_cards.py` checks the image hash and catalog identity before adding numeric evidence; it is idempotent and rejects conflicts. The Shiny Flash bonuses remain separate from ordinary main effects. These two cards increase complete numeric profiles **30 → 32** and fully resolved identities **16 → 18**. Validated shared tiers increase **12 → 15**. No other level is interpolated.
- The native [Distant Strike `<Survival>` Lv. 10 card](data/media/b0aad7d457fd4e699605ae1f78d4ec51/frames/1b99d4a1dce94a8294f2459acf6303a7/0064.png) establishes its +20% weak-spot main effect beyond 20 meters, plus an additional +1% per meter up to +20%. The importer pins that image's SHA-256 in [native_main_effects.json](research/native_main_effects.json) and attaches same-level evidence only; it does not infer strengths at other levels.
- `tools/audit_detail_magnitudes.py` reconciles the 1,473 downloaded [Once Human Database mod detail pages](https://www.oncehumandb.com/mods) to exact catalog identities. Its index records **5,182 numeric effect-description candidates for 706 identities**, with percentage, duration, and stack literals. These are **not** exact level profiles. The detail pages do not establish which description strength maps to a Field Guide level, so those candidates cannot silently become calculated bonuses.
- The [SN700 client-derived reference record](https://www.oncehumandb.com/weapons/sn700-62c4313c0646) lists 980 damage, 40 RPM, five rounds, 3.6-second reload, 2% critical rate, 24% critical damage, 90% weak-spot damage, and 57m full-damage range. Its **in-game tier, stars, and calibration are unlabeled** on that source. The app calls this a reference profile, never the player's crafted weapon. The pinned [community weapon catalog](https://github.com/lReDragol/OnceHuman_Tools/tree/d6b1d5b99f84cb6ddc6b8f85144ee067af2a4e45) says SN700 has no unique effect; the current database page lists no unique effect. This supports a conditional direct-only encounter, but is not proof that no later hidden mechanic exists.

## Mechanic classification and calculation gate

`weapon_capabilities.json` supplies exact-identity evidence for direct hits, triggered damage, status damage, debuffs, conditional buffs, and firing/reload changes. Unlisted weapons stay **unknown**. KAM - Crank has a historically documented Burn status source without a separate triggered-damage claim; Boom! Boom! has officially described Burn and explosion components. The engine no longer sets both flags from a family-name match.

`damage_rules.json` supplies exact mod-and-level main effects with activation, component, stacking group, limits, trigger, timing, and provenance. The generic evaluator applies supported numeric subattributes from `catalog.resolve()`, keeps base and conditional additions separate, and blocks unsupported names/units/directions. If a selected mod's main effect lacks a same-level rule, a status/trigger source is present or unknown, a reached set effect is unverified, or a common item could interact with the swap, the scoped winner is withheld. The trace names the rule and source. The currently supported set threshold is the [official Treacherous Tides 2-piece rule](https://www.oncehuman.game/news/update/20261009/40780_1314019.html) when PvE mode and HP are explicit; its interaction with a 3-piece threshold remains unresolved.

The model tests additive and multiplicative damage-bucket applications, additive and multiplicative critical-plus-weak-spot base branches, floor/ceil magazine rounding, and lower/upper bounds on Distant Strike's extra distance bonus. These are **sensitivity assumptions**, not claims about the game's exact stacking formula. The first shot is at t=0; each magazine consumes `rounds × 60/RPM` seconds before reload. Target defense, falloff beyond the full-damage range, projectile misses, external buffs, and equipment scaling are not modeled.

## A supported saved-plan recommendation

The tested catalog plans select the same SN700 reference primary and Hot Dog Shorts with a bottoms mod:

| Plan | Mod | Same-target encounter at 25m |
| --- | --- | --- |
| Distant | Distant Strike `<Survival>` Lv. 10 | +3% All DMG subattribute; at least +20% weak-spot main effect beyond 20m. The additional per-meter strength is bounded from 0 to +20% because its origin is not established. |
| Aero | Elemental Resonance `<Aero>` Lv. 17 | +6% Weapon DMG, +15% Crit DMG, +7.5% All DMG; aerial additions inactive when grounded. Its next-magazine Elemental effect is inactive with explicitly zero prior-magazine elemental events. The pictured Shiny +2% Flash effect is excluded. |

Illustrative encounter inputs are **40 seconds, 25m, 2% critical share, 80% weak-spot share, grounded, no HP consumption, stamina spending, nearby kills, or elemental events**, and a single PvE target inside SN700's listed full-damage range. These are not ownership or personal combat observations. [The official historical Hot Dog Shorts adjustment](https://www.oncehuman.game/news/devBlog/20241123/40781_1195665.html) concerns Bounce; the SN700 direct-only source profile has no Bounce. Its current standalone effect remains a condition on any full-build claim.

For the additive, floor-magazine, lower-distance-bound row, the four shot branches have shares 19.6% normal, 0.4% critical, 78.4% weak spot, and 1.6% both. SN700's source base yields `980`, `980×1.24`, `980×1.90`, and `980×(1+.24+.90)` before mod bonuses. Independent arithmetic gives:

| Metric | Distant | Aero |
| --- | ---: | ---: |
| Weighted primary hit | 2,039.68576 | 1,924.25744 |
| Five-round burst | 10,198.4288 | 9,621.2872 |
| Shots in 40s | 20 | 20 |
| 40s primary damage proxy | 40,793.7152 | 38,485.1488 |

Five rounds at 40 RPM occupy 7.5 seconds; a 3.6-second reload gives an 11.1-second cycle. **Distant wins across all 16 tested sensitivity rows at 25m.** At **10m**, its distance main effect is inactive: the same additive row becomes **8,705.0656 vs 9,621.2872 burst**, and **34,820.2624 vs 38,485.1488 over 40s**, so **Aero wins across those rows**. An aerial encounter adds Aero's separate +3% Weapon and +7.5% Crit subattribute bonuses. Any prior-magazine elemental events activate an unresolved timed buff and block a winner.

This is a **conditional reference-profile primary-fire recommendation** through the saved-build UI. It does not establish absolute in-game hits or a full-build winner. To advance the full advisor, the largest needs are current exact-level mod layouts, exact weapon tier/calibration mapping, status/proc event models, current armor effects, and measured stacking behavior across common gear.
