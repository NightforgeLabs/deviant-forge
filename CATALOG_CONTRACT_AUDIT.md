# Catalog contract and bonus-line audit — 2026-11-01

The contract sweep uses isolated, unsaved selections. It checks identity,
variant, level, provenance and read-only comparison behavior. It does not prove
that a source's game numbers are current or that modeled DPS equals game DPS.

## Coverage, with distinct denominators

| Capability | Current result | Meaning / next owner action |
| --- | ---: | --- |
| Catalog identities | 985 mods, 138 weapons, 162 armor, 20 sets | 984 mods selectable; one family-only identity. Catalog maintainer should reconcile 93 mods lacking a parsed current variant against newer sources. |
| Four numeric bonus lines at an exact mod identity and level | 68 complete, 7 partial observed profiles / 16,728 selectable-mod × level grid cells | 65 identities have at least one complete profile. Data owner should map published calculator tier/level formulas to each line, preserving source version and conflicts. This is the main user-requested data gap. |
| Derived suffix candidate grid | 938 complete, 1,567 partial / 2,505 candidates | Explicit opt-in; transfer across identities is a hypothesis. Formula owner should verify tier and suffix scaling, then promote scoped rules without claiming ownership or obtainable levels. |
| Main mod-effect templates | 652 typed, 198 partial, 38 unknown, 5 conflicting, 92 without effect text / 985 packet identities | Template support is not a level-bound numeric profile. Core-effect owner should close operator semantics and source/version conflicts. |
| Exact typed core observations | 54 identity-level cards | 51 current Field Guide frames, one unknown-build video, two official preview cards. Timed preview remains opt-in. |
| Timed candidate state | 39 executable candidate identities | No current level numeric binding; opt-in only. |
| Weapon scenarios | 138 caller-direct, 15 sourced event timelines | None has a fully current crafted-weapon damage profile. Weapon/data owner should bind sourced coefficients, class, targets and timing by version. |
| Set rules | 2 of 20 families with released sourced rules in current comparator | Set owner should bind remaining thresholds with source/version and explicit trigger semantics. |

## Contract checks completed

- All 984 selectable mods resolve through levels 1–17; complete profiles have four non-null numeric lines. Synthetic Shiny Lv17 and legacy Lv10 paths retain their variant/source gates.
- All catalog weapons, armor and selectable mods enter read-only structured comparison. Set names and the family-only mod are rejected as single equipment choices.
- All 984 mods at ordinary levels 1, 10 and 17 plus synthetic Shiny 17 (3,936 plan cases) preserve source row fields, identity, level, Shiny flag and typed-effect status between direct and hypothetical saved-plan paths. The suite asserts no game winner and does not save any plan.
- A sweep of all selectable mod identities at level 10 with candidate opt-in found no uncaught operator error. Explicit candidate outputs retain source warning, level-unbound label and false whole-DPS certification. Context-dependent and unsupported operators remain individually classified.
- Exact timed offensive output now feeds the integrated scheduler after its trigger, with sourced identity, level, variant and evidence gates. The official-preview Elemental Resonance Aero Shiny Lv17 fixture gives a +10% elemental pool only from reload completion through the half-open 15-second window. Retriggers before expiry are rejected because the refresh rule is unresolved.

## Remaining work by cause

| Gap | Cause | Required closure / acceptance |
| --- | --- | --- |
| All four bonus lines for each mod and level | Data/formula mapping, not identity routing | Import credible published calculator and open-source level/tier tables with URLs, versions and conflict handling. Verify sampled known cards and audit every produced line; never fill unavailable cells with zero. |
| Legacy/current/variant ambiguity | Source-version reconciliation | Match current identity, suffix, Shiny, obtainable level and game patch; retain alternative source rows where disagreement persists. |
| Core effect templates that need event state | Operator/context implementation | Bind explicit triggers and duration/stack policies to scheduler; deterministic fixtures prove activation, expiry, ammo and no duplicate application. |
| Timed exact core plus weapon proc in one run | Code integration | Compose one event state for both paths; test shot/proc ordering and no double count. Until then the API rejects this combination explicitly. |
| Preview-only and community effect strengths | Source status | Keep labeled conditional scenarios; obtain released cards or controlled tests before asserting current values. |
| Universal final damage buckets and target rules | Mechanics evidence | One or two controlled tests targeted to distinguish rival bucket/class/crit models, with explicit buff/HP/reload timing, then update only supported equations. |

## Published formula integration added later on 2026-11-01

The public detail endpoint now loads 89 THGL representative slot/suffix
layouts and 79 stat formulas, expanded by the official 1–17 level chart.
The generated grid covers all 16,728 theoretical ordinary identity-level
cells: 10,693 current-generation formula candidates, 4,267
generation-unverified formula candidates and 1,768 blocked cells. Of the
14,960 candidate cells, 11,074 have all four scalar percentages at levels
where all four are unlocked. The remainder includes locked lines at lower
levels or structured event-conversion terms that cannot be reduced to one
percentage; 54,560 present rows have published numeric components. The
source packet reports 75/75 held profile and 126/126
corroborated tier comparisons matching, with no numerical conflict. These
are public source formulas, not exact current-client observations.

The default public API presents those candidate values with visible source
and generation labels. Exact observations retain priority, and legacy
random-roll instances stay blocked. Next work: reconcile the 1,768 blocked
cells and connect remaining component types to the damage engine. No full-game
DPS certification follows from the numeric coverage alone.

The read-only comparator and hypothetical planned-build path now consume the
same default published rows. Exact observed rows retain priority; an
explicitly requested older suffix-candidate scenario remains available.
Only mapped damage pools enter conditional ratios. For Flame Resonance
<General> Lv8 to Lv17, the illustrative All DMG Boost pool changes from
2.4% to 6.0%; Reload Speed and damage against enemies remain separate
unmodeled components. The result never establishes a game winner.

Among 984 selectable identities, 629 cataloged current-generation and 251
generation-unverified identities have published layout candidates. The 104
blocked identities comprise 42 legacy random-roll identities, 59 mixed or
unverified identities and three cataloged current-generation identities.
The three current-generation layout gaps are Elemental Havoc <Violence>,
Steady Hand <Resistance>, and Slow and Steady <Resistance>. The 24
Resonance/Resonant Deviant Energy identities carry a sourced naming bridge
from one Deadshot anchor; transfer to each other identity stays labeled as a
published-layout candidate.

Shiny Lv17 suffixes use a separate conditional artifact: 629 of 632
cataloged current-generation identities have published four-line candidates;
three lack a layout. This never establishes that a particular Shiny item is
available or owned, or supplies its Shiny core effect. Other generations are
not silently promoted to Shiny candidates. Sourced maxima such as Lunar's
low-HP Crit DMG +30% are displayed as maxima and are not fed to the damage
model as always-active percentages.
