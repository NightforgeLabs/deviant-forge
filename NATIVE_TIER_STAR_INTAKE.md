# Native tier and star evidence, 2026-11-02

## Field-level partial-star intake

### Independently checked v2 links and one blueprint preview

The prior installed checkpoint was **75/138** distinct Forge weapon identities.
`native_crosswalk_v2_intake.py` pins the v2 proposal, local build 26267212
field packet, independently read exact source pages, and native literal bytes.
Nine new alias links have both exact blueprint and Tier I gear pages plus
validated native blueprint-to-gear IDs. MPS7 - Chaos Domain has an exact
blueprint title, Tier I Crafts identity, and five native typed equip IDs; its
origin attack rows are unresolved, so it is **identity-only**. AA12 is withheld
because the exact blueprint page could not be read independently. The installed
total is **85/138** linked identities, with **52** source-backed star maxima
in the current selector. No new identity link establishes a final damage input.
AKM/KAM duplicate native ID, Flare Gun conflicting gear ID, shorthands, and
KAM Burning Rage/Crank remain separate and unmerged.

`aug_blueprint_preview.py` pins and hash-checks the existing October 22 frame
for the AUG Electron Cloud **Tier V, 4★ Weapon Blueprints preview**. Build shows
its exact visible labels: DMG 231, Fire Rate 720, MAG 40, with a source-frame
link. This is neither an equipped tooltip nor a selected 5★/6★ value, and
the preview is excluded from Attack and damage formulas. The corresponding
native Tier V attack 201 and 4★ ratio 1.15 agree with 231 under some rounding
rules; one cell does not verify a universal formula or game build equivalence.

### Frozen exact-identity crosswalk

`native_crosswalk_intake.py` checks the frozen 138-row proposal against exact
public blueprint titles, two independently named Tier I gear pages, the
validated native blueprint-to-gear IDs, stored tier/star fields and 40 public
blueprint **Max Stars** statements. Of 43 proposed links, two (R500 and
Goshawk) were already installed, 40 new links pass, and Nail Gun is withheld
because its cited blueprint URL returned HTTP 404 on independent recheck.
Normal Build now has exact-ID native evidence for **75 of 138 catalog
weapons**, with 17 of the 92 byte-validated native blueprint records still
unbound to a Forge weapon. Identity coverage is separate from full weapon
calculation coverage; the new links add no numeric fields or damage formula.

The [Hammerhead Shark blueprint](https://oncehuman.th.gl/db/blueprints/13123301)
and its [R500 - Hammerhead Shark Tier I gear page](https://oncehuman.th.gl/db/gear/10123301)
have different titles but the same source-linked native ID. The same narrow
gear-title bridge is used for [R500 - Hunter](https://oncehuman.th.gl/db/gear/10121201)
under its [Hunter 500 blueprint](https://oncehuman.th.gl/db/blueprints/13121201).
The source titles are shown separately; short names, punctuation changes,
KAM Burning Rage/Crank, and conflicting names are not merged. For KAM Pioneer,
the [blueprint page](https://oncehuman.th.gl/db/blueprints/13421201) says max
4★ while the bounded native capture has only three star rows. Its 4★ selection
is valid by the published maximum but has an unknown native ratio; its tier
attack row remains visible independently. Source-backed star maxima reach Build
through the validated backend crosswalk, including read-only warnings for
older saved plans outside those maxima. No personal record is rewritten.

`native_partial_intake.py` validates a hash-pinned 92-blueprint native snapshot
against six read-only literal captures from build 26267212. All 92 have five
located tier attack rows (460 total). Stored blueprint star rows vary: 25
blueprints have three, 14 have four, 20 have five, and 33 have six (429 total).
The earlier 33 six-star records remain byte/value checked and unchanged. The
new 59 contribute 295 tier attack and 231 star ratio fields. These are **526
new evidence fields, zero new formula-ready damage inputs**. “Stored star
count” means rows located in this native capture, not gameplay completeness.

The [R500 blueprint](https://oncehuman.th.gl/db/blueprints/13121101) and
[DE.50 Goshawk blueprint](https://oncehuman.th.gl/db/blueprints/13111201)
independently name and bound two of the 59 partial-star identities to the
catalog, with published max stars three and four respectively. Normal Build
shows the selected native tier value even if its requested star row is absent;
the star remains null with a reason, and no total is calculated. The other 57
remain blueprint-ID evidence until their exact public identity is checked.
The source-backed maxima are delivered from the validated backend report to
Build's star selector. New 4★ R500 and 5★ Goshawk plans are rejected. Older
saved values remain verbatim and show an invalid-configuration warning; the
read-only analysis path accepts them solely to explain the problem and
suppresses its Attack-rate proxy. An absent native row *within* a sourced
maximum remains unknown, not invalid. Other weapons still use the catalog
rarity choice range with an explicit item-specific uncertainty label;
Burning Rage's maximum is not transferred to KAM Crank, and a six-star AUG
selection remains available.
The [KAM Burning Rage blueprint](https://oncehuman.th.gl/db/blueprints/13421301)
has five stored star rows, but its public Crafts list mixes Burning Rage and
KAM Crank gear. It is deliberately **not** bound to catalog KAM Crank.

The source parser identifies 27 other five-tier equipment families whose
origin attack shape it cannot yet decode and 14 more blueprint rows without
five typed equip rows. This limits parser coverage; it does not prove absent
game data. Native consumer arithmetic, damage unit, rounding, crafted
configuration, and current Attack remain unresolved for every new record.

The installed build 26267212 captures five exact blueprint families. The
staged importer checks each of 25 `equip_data` gear rows against its blueprint,
crafted tier, gear ID, `item_to_gun_mapping_data` gun number and
`equip_origin_data` `gun_preset_attack` bytes. It checks 30
`gun_blueprint_attr_data` `preset_attack_radio` records by blueprint and star.
Each literal capture is hash pinned. The corresponding named public item pages
corroborate all 25 displayed one-star numbers, but matching numbers do not prove
the runtime consumer equation.

An expanded, separately captured source check gives a direct counterexample:
the [R500 Memento Tier I page](https://oncehuman.th.gl/db/gear/10122301)
displays 4★ DMG 195. Its native tier attack is 170 and blueprint 4★ ratio is
1.15; decimal half-up multiplication gives 196. The source and literal hashes
are retained in `evidence_packets/native-star-rounding-counterexample-v1.json`.
This mismatch rules out promoting the 130 previously matching public cells as
proof of a universal half-up formula.

Example: AUG Electron Cloud blueprint `13451401`, Tier V gear `10451405`,
native `gun_preset_attack=201`; the same blueprint's 5★
`preset_attack_radio=1.2`. Build displays these **separately** as local-file
evidence and does not multiply them or substitute either for current crafted
Attack, per-hit damage, or per-projectile damage. Zero of 55 native numeric
fields are admitted into calculation. Public source-native item-page scenarios
remain explicit hypotheses and are not changed by this import.

The next source task is to establish the actual `get_gun_omg_value` consumer
formula, rounding, calibration and equipped-configuration scope from a
bounded static trace, then validate that formula against an independently
recorded matching configuration before promoting a typed binding. No game code
was run, and no original game file or personal record was changed.

## Second bounded batch

Ten additional exact catalog identities are matched to named public blueprint
and Tier I gear pages. `native_tier_expanded.py` verifies the original literal
hashes, gear-to-blueprint bytes, item-to-gun index, 50 tier origin rows, 60
blueprint star rows and the published Tier I labels. Build shows the selected
native tier and star fields and a Tier I public reference. The public Fire Rate
label is not treated as RPM without a unit source. All 110 additional native
numeric fields remain evidence only; no inferred final damage is calculated.

Nine of these public gear pages show a six-cell star table. The inspected
DBSG Format Tier I page does not, so Build says that the native ratio has no
public star-table comparison. The R500 discrepancy above remains visible for
its Tier I 4★ selection. Further source rows in the acquisition queue are
not imported by this bounded batch until their exact identities are checked.

## Frozen 33-record snapshot

The next frozen native snapshot contains the prior 15 plus 18 newly named
blueprints. All 18 new IDs pass raw blueprint→Tier I gear, item→gun, five
equipment/origin tier rows, six blueprint star rows and unique catalog-name
checks. Eight have directly named public Tier I gear pages; ten have a public
blueprint title and local native gear chain without an independently inspected
gear page. No numeric public gear fields are imported for this group.

The published blueprint says **FP9 - Additional Rules**, while the existing
catalog says **TEC9 - Additional Rules**. [The named weapon source](https://www.oncehumandb.com/weapons/tec9-additional-rules)
explicitly says it was previously listed as TEC9; the bridge applies to this
one identity only, not to the separate base TEC9. The [official release notes](https://www.oncehuman.game/m/news/update/20260121/40780_1282991.html)
also use the TEC9 name. The original public title and both source names remain
visible in the evidence packet.

**Acceptance scope:** 33 of 33 complete records in this *bounded native
snapshot* are linked to exact catalog identities; zero are rejected within that
set. This is not 33 complete gameplay weapons. Across those records, 165 native
tier fields and 198 native star fields are retained as evidence; zero are
admitted as final-damage inputs. The snapshot's `selection_exclusions` lists
other raw blueprint rows for which this parser could not establish five tier
rows or six star rows. Those rows were not part of the 33-record denominator and
were not imported. Missing public gear pages, version alignment, consumer
arithmetic, rounding, unit, calibration and equipped-state behavior remain
separate requirements.
