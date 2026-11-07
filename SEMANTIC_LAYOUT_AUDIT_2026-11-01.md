# Held tooltip versus published layout audit, 2026-11-01

The 75 held profile and 126 tier comparisons in the original published formula
packet checked **numeric values only**. Equal numbers do not establish matching
stats. The runtime now compares stat identity, unit, condition, direction and
slot at exact held levels before calling a published row corroborated.

## Result

| Measure | Count |
| --- | ---: |
| Ordinary identities with at least one semantic noncorroboration | 72 |
| Distinct conflicting line positions on those identities | 149 |
| Exact held level/position discrepancies | 152 |
| Candidate numeric rows withheld where held value is unavailable | 1,836 |
| Identity/level profiles with at least one withheld candidate | 1,013 |

Across the 16,728 theoretical ordinary identity/level profiles, calculation
coverage after reconciliation is **12,437 complete published candidates**, **2,465
partial published candidates**, **68 complete from held values**, and **1,758
partial**. Before this repair, 13,393 were counted as complete published
candidates and 1,509 as partial published candidates. Thus 956 profiles moved
from candidate-complete to candidate-partial. These are mod-level profiles, not
individual mods or fully integrated build effects. The strict all-effect item
counts in `integration_ledger.py` do not change.

## Overflow <General> example

The held Lv8 frame at
`data/media/b0aad7d457fd4e699605ae1f78d4ec51/frames/1b99d4a1dce94a8294f2459acf6303a7/0033.png`
shows **DMG +2.4%, Magazine Capacity +4.8%, Reload Efficiency +3.6%, All
DMG Boost +3.0%**. The published helmet/General candidate uses **All DMG
Boost, Magazine Capacity, Reload Speed, Damage against enemies**. Positions
1, 3 and 4 are not corroborated merely because their percentages match.
The held Lv8 values and labels remain intact and separate from the rejected
candidate. At levels where a conflicting position has no held numeric value,
the published value is withheld. In particular, Lv7 no longer displays a
candidate Damage against enemies +1.5% for position 4, and Lv9 does not
invent a position-1 All DMG Boost value.

The public detail marks the disagreement; `calculation_rows()` passes exact
held values to supported pools without importing the conflicting published
meaning. Normal catalog selection and saved planned-build selection use the
same reconciled rows. The per-item ledger names each conflicting position and
its source comparison. A semantic difference may reflect wording or version
drift; resolving it requires the exact current identity tooltip or a source
that proves an equivalence. No broad Reload Speed/Efficiency or All DMG/enemy
damage aliases are assumed.

The photographed Elemental Overload <Resonance> Lv9 lines use "on weakspot
hit" and "on elemental hit" wording. Those two descriptions match the
published trigger, destination, per-stack amount, cap, and duration exactly.
They are the only event-wording aliases admitted by this repair. Their
observed source stays attached to the timed rule; its separate All DMG Boost
versus Damage against enemies discrepancy remains gated. The effective Lv10
catalog has 740 identities with four numeric lines and 244 partial identities;
the raw published-formula count predates semantic reconciliation.

## Bounded source-lineage follow-up

The official S4 image `research/official-gravity-en-6.png` (SHA-256
`36879f030b802302fd4bfeffd5e879b9c6d5c3a06dcf4b96add72dfef797db6b`)
anchors **Elemental Resonance <Aero>** pants and **Ferocious Charge <Downstar>**
boots at Lv17. Both show All DMG Boost +7.5% at position 3. The ordinary Lv17
subattribute values follow the official Field Guide rule for Shiny cards; this
does not transfer the Shiny main effect. The exact named values are used in the
All DMG pool for these two identities, while the candidate Damage against
enemies pool remains zero. At unobserved levels, disputed positions retain
their held layout names and source references, with no numeric value.

Across 64 identities in 27 slot/suffix layouts, held All DMG Boost conflicts
with the imported candidate Damage against enemies. This class accounts for
742 of the 1,836 withheld numeric rows. The official level chart supplies row
tiers, but no equivalence between the two damage scopes. The compressed source
packet supplies English labels and coefficients, not the raw source tooltip,
native stat ID, or localization key. Its distinct `dmg_boost` (1.2 per tier)
and `dmg_against_enemies` (1.5 per tier) keys cannot be merged based on matching
values at sampled tiers. All 64 selected identities were checked through the
reconciled calculation rows; none applies these disputed positions to the
target-specific enemy-damage pool. Ordinary selection and saved plans use the
same exact card values.

Next bounded acquisition: obtain the raw source tooltip and stat ID or
localization key for the representative helmet/General, pants/Aero, and
boots/Downstar layouts, with their game-build dates. Compare that ID and its
target scope against the held exact cards before restoring any unobserved
numeric progression. If this source artifact is unavailable, keep the
candidate rows withheld. No additional user recording is currently required.

A separate, narrow wording correction admits “aerial hit” versus “aerial hit
for extra component” only when the exact identity's named base and extra
percentages both equal the published structured components. Held Elemental
Resonance <Aero> Lv17, Precision Charge <Aero> Lv8/Lv17, and Bullet Siphon
<Aero Deviant Energy> Lv12 meet that test. Their candidate Weapon/Crit or
Status/Elemental rows may therefore use the existing conditional operator at
unobserved levels. The All DMG Boost versus Damage against enemies rows on
these identities remain withheld. A name match or conditional wording alone
does not pass the test.
