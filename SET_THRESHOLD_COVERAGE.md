# Set-threshold execution and evidence — 2026-11-01

The [74-row audit](evidence_packets/set-threshold-coverage-v1.json) is rebuilt
with `python tools/build_set_threshold_coverage.py`. It joins the 20 runtime
set identities and their 74 threshold descriptions to the source-attributed
[armor/set packet](evidence_packets/set-threshold-source-v4.json). The source
packet has 79 thresholds: four Dark Resonance rows are not in the runtime
catalog, and its current Treacherous Tides one-piece row has no matching
runtime description. The old Treacherous descriptions and Savior three-piece
number cannot override their newer official rules.

| Audit dimension | Count |
| --- | ---: |
| Source status: March 2026 catalog snapshot / official live release / historical official release / preview | 63 / 7 / 3 / 1 |
| Operator shape: static / conditional / timed or stacked / resource or shield / mixed | 37 / 8 / 20 / 5 / 4 |
| Executable current official thresholds | 3 |
| Executable only in opted-in community snapshot / historical official scenario | 39 / 2 |
| Unresolved threshold descriptions | 30 |

The three current numeric rules are Bastille two-piece Reload Efficiency
+15% ([January 2026 release](https://www.oncehuman.game/news/update/20260121/40780_1282991.html)),
Treacherous Tides two-piece Weapon/Status +12% below 70% HP, and Treacherous
Tides three-piece Weapon/Status +8% at 100% HP or +28% at or below 60% HP
([September 2026 release](https://www.oncehuman.game/news/update/20261009/40780_1314019.html)).
The three-piece intermediate curve is unknown. At low HP, combining it with
the two-piece rule needs the explicit `additive_named_pools` scenario
hypothesis; without that input the complete total stays unknown.

An explicit `set_evidence_mode: "community_snapshot"` adds 39 threshold
operators from the cached March 2026 tooltip transcription. Fifteen can
alter outgoing damage or shot timing; 24 are classified utility only. An
explicit `historical_official` mode adds Bastille one-piece +10% Weapon DMG
above 70% HP and its three-piece +40% Weapon DMG while the Bastille state is
explicitly active, from the [2024 official adjustment](https://www.oncehuman.game/news/update/20241218/40780_1200958.html).
Those historical values are not asserted current. Community mode also makes
these two available with their historical provenance. The one-piece
threshold is counted at one piece; thresholds accumulate only when earned.

The 30 unresolved descriptions comprise 24 catalog-snapshot rules needing
event, refresh, rounding or target behavior; Bastille four-piece shield
timing; four current released Savior thresholds without usable numeric
strengths; and the preview-only Treacherous shield value. The current Savior
release specifies shield and HP behavior qualitatively and later refresh
behavior, but no full numeric magnitudes in those texts
([release](https://www.oncehuman.game/news/update/20250924/40780_1261275.html),
[refresh update](https://www.oncehuman.game/news/update/20251029/40780_1267745.html)).
Their old catalog numbers are not quietly used. The [January 2026 Dark
Resonance release](https://www.oncehuman.game/news/update/20260121/40780_1282991.html)
describes four effects without enough numeric values; those four are outside
the 74-row runtime denominator until the set identity is reconciled.

## Calculation contract

Equipped armor IDs supply set counts. `published_set_thresholds.evaluate`
returns named pools, sourced applied rows, covered thresholds and missing
inputs. `published_timed_combat.evaluate` combines them once with selected
mod pools and typed core rules, then recomputes crit share, shot timing,
direct damage and eligible packets. Unknown conditions leave a partial total;
a confirmed false condition contributes zero to its known threshold. The
structured Compare form exposes source mode, HP/stamina/load/temperature,
spotted state, historical Bastille state and the optional Treacherous stacking
hypothesis for each side. Saved planned builds use the same armor identities
and evaluator as unsaved selections. All source scenarios retain
`game_winner_established: false`.

## Persistent ownership and next acceptance

| Owner scope | Next action | Shared integration test |
| --- | --- | --- |
| Set and armor rules | Reconcile Dark Resonance into the runtime catalog when identity and set membership are sourced; close the 30 threshold gaps by source/version and implement supported stack/resource transitions. | Multiple sets count by actual equipped pieces, combine once, and unknown thresholds withhold a full total. |
| Weapon mechanics | Bind the seven missing source-native baselines where identity and published values are established; then close proc class, target, chance and ammo semantics by weapon family. | A selected weapon emits only its eligible packets into the same timed state, with no duplicate hit or ammo event. |
| Mod mechanics | Map exact main-effect rank separately from Field Guide bonus-line level and close the remaining timed, utility-dependent and Most Wanted inputs. | A selected mod contributes each known suffix/core effect once; unbound conditions and values stay partial. |
| Shared calculation integrator | Keep the typed pool/event contract and source status consistent across direct selection, structured Compare and saved plans. | Equal sourced selections agree, distinct gear changes only eligible components, and no incomplete scenario gets a game winner. |

The 2024/2026 source statuses and public snapshot are scenario provenance,
not validation of universal game damage buckets or target mitigation.
