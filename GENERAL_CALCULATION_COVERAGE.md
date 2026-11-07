# General calculation coverage audit — 2026-11-01

## Current correction: weapon damage progression quarantined

`evidence_packets/integration-ledger-v1.json` is the current per-item requirements
ledger. Read-only API routes `/api/integration-coverage` and
`/api/integration-ledger/{id}` expose its counts and records. It covers 984
selectable mods, 138 weapons, 162 armor pieces, and 74 set thresholds. Strict
item-local categories are: mods 0 complete / 941 partial / 43 display-only;
weapons 0 / 138 / 0; armor 0 / 160 / 2; set thresholds 2 / 42 / 30.
Partial means a component path exists, not complete damage calculation.

The 133 calculator weapon rows are name or exact-alias matches, **not validated
Tier 1 damage baselines**. The previously paired KAM pages were different
named weapons: Crank Tier 1 versus Burning Rage Tier 4. Matching AUG Electron
Cloud pages show Tier 1 damage 34 and Tier 4 damage 132, refuting the
calculator's generic tier multiplier.
The adapter therefore retains raw source damage but withholds scaled damage
and dependent direct-hit, firing, reload-cycle and timed totals. Earlier
published-reference examples and tests claiming complete totals from that
basis are superseded. Five previously unmatched weapons now have explicit
item-ID Tier 1–5 display rows and 130 sourced tier/star cells, but some higher
star cells, selected blueprint attributes and the damage unit remain unknown.
Their page damage can enter a direct/firing calculation only
under an explicit per-projectile hypothesis with a caller projectile count.
Classic calibration levels were removed in January 2026; AUG was released
afterward and its item-page scenario keeps that level at zero. Chosen calibration
blueprint attributes remain separate. The official reload relation is applied
only when base reload seconds are entered; reload scores are not seconds.

This is an implementation inventory, not a claim that an arbitrary current-game
build has verified DPS. Counts below come from `catalog.ENTRIES`,
`public_catalog_detail.calculation_rows`, `published_calculator_adapter`,
`weapon_timeline_api`, `weapon_packet_timeline_api`, the published evidence
packets and the existing catalog contract tests. The catalog itself has not
been certified as every item in the live game.

| Catalog area | Identities | What the installed calculator can compute | Remaining limit |
| --- | ---: | --- | --- |
| Mod base names / name–slot groups / tree labels | 138 / 144 / 152 | These are three groupings of the same 984 selectable identities. | `tree` includes keyword categories and exceptional variant labels; it is not a count of base mods. The older “137 name-and-slot groups” figure is not reproducible from the current runtime catalog. |
| Selectable mod identities | 984 of 985 catalog entries | At Lv10, 795 identities have four numeric bonus rows (781 published candidates, 14 other complete); 189 are partial. Selected rows enter supported direct pools and typed timed scenarios. | A complete four-line profile does not imply its main effect, conditional activity, or all damage packets are known. |
| Ordinary fixed-layout identity × level pairs | 14,977 of 16,728 published formula candidates (881 identities × 17 levels) | Public level formulas supply ordered lines with provenance; exact observations take precedence. | 1,751 pairs across 103 identities remain blocked: 42 legacy random-roll, 59 mixed-generation, two current Resistance identities. At Lv10, 41 Lunar identities have sourced maxima but no HP curve. Another 45 Resonance identities have sourced timed-stack parameters connected to explicit qualifying packet outcomes in both guided published-reference timed Compare and advanced selected-build scenarios, under named expiry and bucket assumptions. These 86 candidate profiles lack four scalar numeric rows, explaining 881 − 86 = 795. Three further exact photographed Lunar profiles have numeric maxima yet still lack the HP curve. |
| Weapon identities | 138 | 133 have name-matched imported calculator rows, including two exact-identity short-name aliases; 66 have all reference fields populated. Five previously unmatched weapons have blueprint-linked exact Tier 1–5 pages and 130 sourced tier/star damage cells. Guided Compare exposes those cells under an explicit per-projectile hypothesis. Event templates remain separate. | Zero imported damage values have a proven tier/star basis; their scaled damage and dependent totals are withheld. Four Tier 5 higher-star tables, selected blueprint attributes, projectile unit and reload seconds remain unsourced. |
| Armor identities | 162 | 154 have published HP and Psi at the default 1-star/tier-1 reference row, including five exact Rustic blueprint matches and Frost Tactical Vest. Armor selection and saved plans both enter the reference build. | Five Snowland Rustic items still lack verified source rarity/progression; three unique pieces lack item-specific reference mapping. Catalog rarity conflicts on the six added rows remain visible separately. Higher upgrade rows can contain placeholders; the generic stat table does not model each unique armor effect. |
| Set identities | 20, with 74 catalog threshold descriptions | Three current sourced thresholds have executable numeric components at their supported conditions or endpoints; 41 further thresholds have explicit historical or community source scenarios. | See `SET_THRESHOLD_COVERAGE.md`: 30 thresholds still lack an executable current or conditional operator, and only three current-source thresholds have numeric execution. |

The 985 mod entries include one family-only entry. Of the 984 selectable
identities, 632 are cataloged as current Field Guide, 310 have mixed or
unverified generation, and 42 are legacy random-roll. The two current fixed
layout gaps are Steady Hand `<Resistance>` and Slow and Steady `<Resistance>`.
Legacy random-roll items cannot be assigned universal fixed four-line values.
The separate Shiny artifact has 629 suffix-only candidates across 632 current
identities; it establishes neither item availability nor Shiny main effects.

Main-effect counts use different evidence denominators. There are 54 exact
identity/level typed observations (51 Field Guide, one unknown-build video,
two official previews), with the last three gated by default. A separate
57-identity normal public-source crosswalk has 26 arithmetic operators and
23 of 24 timed/resource operators executable under an explicit community
source scenario. Most Wanted remains gated on Attack basis and mark-event
semantics. Six remaining source identities provide utility/melee effects and
one lacks effect text. The exact and public arithmetic sets overlap in two
identities, so 54 + 26 + 23 − 2 = 101 distinct identities with at least some
typed main-effect path; this is **not** 101 complete build models. Community
main-effect rank is separate from Field Guide Lv1–17.

## End-to-end classification

- **Complete explicit modeled scenario:** requires independently anchored weapon
  damage or an explicit caller damage basis, all selected damage components
  have supported buckets and activation, and target, event, ammo and timing
  inputs close the chosen scenario. Compare labels this a conditional model;
  it never establishes a game winner. The quarantined imported reference path
  cannot currently meet this condition. There is no catalog-wide count of
  complete arbitrary builds, since combinations and scenario inputs vary.
- **Component or partial scenario:** the common case. Known direct hits,
  numeric suffix rows, typed core events, supported procs and set thresholds
  are reported separately. Missing packets, set thresholds, conversions or
  conditions remain unresolved instead of contributing zero.
- **Display or evidence blocked:** 103 mod fixed-layout identities, five
  weapon baselines, eight default armor reference rows, most set thresholds, and
  unbound or preview main-effect strengths require the stated source or
  scenario input. These categories overlap at build level and must not be
  summed as one count of unsupported items.

## Contract and integration result

`tests/test_catalog_contracts.py` exercises every selectable mod's 1–17
identity resolution, direct/unsaved-plan selection at representative levels,
ordinary/Shiny evidence gates, every equipment selection kind, and unchanged
isolated data. Representative source-backed timed cases cover direct shots,
status/proc packets, finite ammo, reload and conditional set output. The
current audit additionally checked all 984 ordinary Lv10 and synthetic
Shiny Lv17 single-mod reference selections: four row records each, no
uncaught error, and blocked rows remain partial. The direct reference now
tracks completeness separately for hit, firing rate and reload-cycle metrics:
an unknown Reload Speed conversion withholds the reload-cycle ratio but
leaves supported hit and firing ratios available; an unmapped Firearm Damage
line withholds the hit ratio. This avoids calling a partial comparison
complete merely because another line's condition was inactive.

## Next implementable batch

The installed Wind Intepreter Cap current-release rule adds +25% damage to source-linked Unstable Bomber explosion packets in a named additive keyword-pool scenario; its one-bullet load now changes later shots under three named created, reserve-transfer or not-retained scenarios. The official source does not settle bullet origin or retention during reload, so no scenario is selected by default and the complete total is withheld until a choice is made. See `WIND_AMMO_SCENARIOS.md`. Separately, close the five
missing source-native weapon baseline mappings only where a baseline is
actually published. The two Resistance layouts, legacy rolls, Most Wanted,
and universal bucket/target mitigation questions need specific evidence;
they cannot be filled from the current level table.
