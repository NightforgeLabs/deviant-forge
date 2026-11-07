# Active numeric source cleanup — 2026-11-02

## Tier I raw-page intake

`source_intake.py` reads the archived five-weapon source packet without changing it.
Its deterministic `evidence_packets/five-weapon-tier1-intake-v1.json` report keeps
exact blueprint and gear IDs, original labels and values, page URLs, capture
date, archive SHA-256, and the calculation binding for every accepted field. It
accepts 8 verified timing fields: three explicitly labeled Fire Rate (RPM)
values and five Magazine Capacity values. Two further Fire Rate values (AUG
and bow) are conditional and require an explicit Fire Rate-as-RPM hypothesis
before the scheduler uses them. It withholds 65 fields,
including displayed DMG and star damage (per-projectile/current-Attack unit
unknown), Reload Speed (score, no seconds conversion), and fields without a
typed binding. The raw archive retains every withheld field.
The bounded local game-data identity sample corroborates the five blueprint-to-
gear ID pairs and is recorded with Steam build, archive entry, payload hash and
byte offset. It establishes identity only; it does not promote public DMG or
other source fields to current-game numeric facts.

For Tier I page scenarios, `published_item_tier.explicit_page_scenario()` takes
RPM and magazine size from this intake and exposes their field provenance to
normal Build. Displayed DMG enters damage math only through a separately
entered and labeled per-projectile hypothesis. The importer rejects identity,
URL, title and value conflicts before replacing its report. Repeat imports are
byte-identical; a failed import retains the prior report. Other tiers keep
their separately sourced page packet until corresponding raw-page intake exists.
Three secondary pages explicitly print “Fire Rate (RPM)”; the AUG and bow
secondary pages print only “Fire Rate.” Normal Build and Compare default to
blocking Tier I page damage timing for those two until their separate RPM
hypothesis is selected; the raw label remains visible in the archive.

`native_field_intake.py` defines the next local game-data record contract:
Steam build ID, archive entry, payload SHA-256, native field identifier, raw
value and byte offset. It defaults to zero active numeric bindings. A decoded
number stays withheld until its exact item identity, source-native unit and
implemented calculation handler can be tied together. Future approved bindings
must also match an allowlisted blueprint/gear pair and a declared configuration
scope; a field from one gun or tier cannot silently migrate to another. The first bounded local
sample contains identity pairs only; it has not supplied numeric semantics.

The newer bounded game-data suffix sample is retained as
`evidence_packets/native-gun-suffix-sample-v1.json`, alongside its capture
manifest and two copied literal-byte payloads in `evidence_packets/native_raw/`.
`native_gun_suffix.py` checks source hashes, blueprint-to-gear-to-gun links,
ordered native names and types, byte offsets and decoded values. The resulting
`native-gun-suffix-intake-v1.json` contains 23 located fields from five guns:
11 for AUG and three focused numeric fields for each of the other four. All 23
remain evidence-only. AUG contains distinct `weapon_rpm` ≈409.794 and
`weapon_rpm_affix_value` 720; the latter matches the public Fire Rate but its
consumer and crafted-configuration scope remain unknown. The local API
`/api/native-gun-suffix/{catalog_id}` exposes these raw facts with
`calculation_included:false`; no native number enters damage or scheduling.

The app keeps every identity and artwork mapping so catalog browsing remains intact. Numerical values without an exact item/configuration binding were removed from active calculation inputs. This is a reversible source cleanup, not a personal inventory or saved-build migration.

## Reversible snapshot

`~/Documents/Codex/2026-11-01/task-2/cleanup-backup-2026-11-02/project` is a full pre-cleanup project copy. `manifest.json` records SHA-256 and size for 2,539 files, including 2,093 images. `python3 restore.py --restore-to /tmp/empty-directory` restored and reverified the entire copy. To inspect a future rollback, first run `python3 restore.py --verify`; restoring into production requires a separate explicit deployment command, since the script refuses nonempty targets.

## Active numeric records removed

- 131 unanchored calculator weapon baselines from `weapon-baselines-published.json`.
- 131 historical weapon stat rows and 112 tier-unlabeled page stat rows from the v3/v4/v5 reference packets. Their source history remains in the snapshot, not the running numeric registry.
- One unlabeled SN700 legacy profile from `weapon_profiles.json`; the old saved-build estimate now withholds a winner.
- 468 generic armor slot/rarity/star/tier rows, including 280 nonzero HP/Psi rows, from `armor-table-published.json`. A shared rarity row is not an item-specific crafted stat.
- 5,182 mod main-effect magnitude candidates across 706 identities from `catalog_effect_magnitudes.json`. They had no Field Guide level binding and were display-only source candidates, not connected formula inputs. The raw detail source and reproducible audit tool remain available; the active catalog no longer exposes these numbers as item-level candidates.

All image files and the personal SQLite database retain their pre-cleanup hashes. Isolated arithmetic regression fixtures live only under `tests/fixtures`; the product loaders cannot access them.

## First source-native import

The active `weapon-item-tier-pages-v1.json` retains five exact blueprint-linked weapon families, 25 tier pages and 130 explicitly listed star/damage cells. These are page-display facts, not per-projectile, Attack, current crafted damage, or final DPS. `published_item_tier.validate_packet` rejects title, URL, item ID, blueprint Crafts-link and star-cell conflicts. The newly captured `aug-raw-page-sample-v1.json` additionally checks original source labels and 12 AUG star cells against the active registry. For AUG, source DMG is 34 at Tier 1/1★ and 132 at Tier 4/1★; source Reload Speed 47 is retained as a score and never converted to seconds. `published_item_tier.explicit_page_scenario` requires a caller's per-projectile hypothesis and projectile count before the displayed DMG enters arithmetic. Reload seconds remain explicit input.

`five-weapon-tier1-raw-v1.json` independently checks the five exact Tier 1 item IDs, page titles, source labels and 30 star cells. The QBJ97 blueprint says “Fiery” while its linked gear page says “Firey”; the identity check preserves that specific source spelling difference instead of normalizing unrelated weapons. The batch does not establish a game build, damage unit or reload seconds.

`published_reference_model.build` cannot fall back to imported calculator damage or generic armor stats. Normal Build and Compare still accept explicit caller packet and exact item-page scenarios. Mod and effect rows with conflicts stay gated by their existing evidence policy. Catalog images remain available for entries that have no complete numeric path.

## Remaining acquisition

The remaining 133 weapons have no active item-ID-anchored damage registry; the five imported families still lack selected crafted damage unit, calibration attributes and reload seconds. Generic armor HP/Psi must be reimported from exact item/configuration pages or held exact tooltips, not inferred from rarity. Current ordinary mod fixed-line data and exact observed mod cards were not purged because those feed typed formulas with existing conflict gates; their remaining semantic/source conflicts are item-specific. No actual current AUG build damage can be stated without matching weapon input and encounter details.
