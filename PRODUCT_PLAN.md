# Deviant Forge product acceptance plan

Updated 2026-10-25. This plan tracks evidence and acceptance criteria; an item listed here is not a claim that the game mechanic is implemented.

## Immediate visual and data fidelity

- The Mods browser must show the game's current seven slot tabs, weapon mechanic sequence, family names and order, five variant cards per row with additional variants wrapping inside the same family, and continuous scrolling.
- Every family image must be the **correct, complete, recognizable game emblem** at readable contrast and size, with its name separately visible. A cropped screenshot fragment, an icon shared with another family, or a partial image cannot satisfy this criterion. Images must be checked against their source at the actual rendered size. A matching symbol is a navigation aid for users who cannot rely on reading the name.
- The 2026-10-25 scrolling recording verifies 100 current family names and placement, but labels obscure the centers of its family emblems. Eight current-shape-matched Burn and Power Surge family emblems have complete source PNGs. Another 82 have complete OhDex named-slot candidate PNGs with visible “current art unverified” labels because hidden details cannot be checked; eight remain partial recording crops. Two archived Fortress symbols proved visibly different from the current-game reference and are withheld. Keep source image, frame/time, completeness and version with each asset. Never invent hidden pixels, family identity, ownership, rarity or lock state.
- Variant cards must show verified rarity, level and lock cues separately from ownership. A known catalog entry with no owned record is not automatically locked. One explicit Add records ownership; browsing and hovering do not.

## Truth layer and calculations

- Keep item identity, variant, rarity, blueprint stars, craft tier, calibration blueprint and roll, calibration upgrade level, mod level, accessories, ownership and build assignment distinct. Preserve duplicate owned instances and saved builds.
- Each effect and roll row needs a typed stat, numeric value and unit, applicable component, trigger/condition, stacking group, duration, confidence, source, version and scenario. Unknown inputs stay unknown; ambiguous signs and inactive Tech-level rows cannot enter arithmetic as zero or as a guessed positive bonus.
- Explain the formula and calculate direct bullets, critical/weakspot cases, magazine and reload cycle, then Power Surge or other keyword components only when their event rates and damage inputs are supplied or verified. Show supported partial results and sensitivity; label assumptions and avoid applying bonuses again to observed damage.
- Verify the complete path from saved gear and equipped mods/accessories/sets to 60-second and 300-second scenario outputs on isolated data. A changed typed roll must change only its relevant component. Include finite-fight boundaries, movement downtime, shield/health conditions and uncertainty.
- Add versioned slices for other weapons, melee and status exceptions rather than a universal rule. A specific balance patch may supersede a previous rule. Test current and historical contexts separately.

## Guided use for two audiences

- The expert path exposes exact source-backed mechanics, conditions, component equations and missing inputs in machine-readable form.
- The guided path uses plain language, recognizable matching symbols and names, one next action at a time, visible prerequisites and progress, and reversible corrections. Keep detail available on demand. Do not assume all users with cognitive disabilities need the same presentation; validate with users.
- For a selected scenario, define 100% completion as verified missions, bosses, collectibles and unlock prerequisites with progress and the next available action. Link maps, missions, enemies, resources, Deviants and loot tables by scenario, version, phase and prerequisites. Acquisition records must distinguish guaranteed, chance with unknown rate, and unknown availability; do not infer a drop table from a named activity. Do not call the whole game complete where coverage is unknown. No gameplay automation or game control is part of this product.

## Evidence-backed expansion order

1. Close current art gaps with complete family assets and actual viewport comparison. Audit known versus unknown variants without mutating ownership.
2. Stabilize and test the calculation path for the user’s AUG build, then add other archetypes with version-specific rules and explicit survivability/healing outputs.
3. Add scenario-aware armor sets, Deviation skills, foods and drinks, Chef stacking, injections, accessory and calibration rules, and Tech-level effect activation with evidence and tests.
4. Add sourced boss, weakspot, puzzle, resource and Deviant guidance. An attributed third-party map embed may be used where permitted; no invented coordinates or scraped raw map data.
5. Add progression, durability and build-maintenance what-ifs; distinguish a hypothetical disabled gear piece from verified break mechanics. Add base and boat design advice with sourced constraints and explicit tradeoffs, not fabricated optimal formulas.

Each hourly review should record what is actually rendered, which decisions the tool supports end to end, a source and version audit for new mechanics, the focused regression result, and the highest remaining blocker. The app's saved gear, inventory and builds are not test fixtures.
