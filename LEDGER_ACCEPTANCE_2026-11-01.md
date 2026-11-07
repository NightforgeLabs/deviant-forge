# Per-item calculation acceptance, 2026-11-01

`integration_ledger.build()` is the current per-item requirements register. Its
strict categories are item implementation coverage for the specified scenario,
not a claim that a conditional model has been validated against the game.

| Kind | Selectable | Fully integrated | Partial | Display only |
| --- | ---: | ---: | ---: | ---: |
| Mod suffix identities | 984 | 0 | 941 | 43 |
| Weapons | 138 | 0 | 138 | 0 |
| Armor identities | 162 | 0 | 160 | 2 |
| Set thresholds | 74 | 2 | 42 | 30 |

The ordinary four-line published layouts, exact level observations, and a
representative weapon event timeline are component coverage. They do not by
themselves make an entire item complete. The ledger records the required
effect, wired calculation path, missing fields, source status, owner lane and
next action separately for each identity/threshold.

## Closures in this acceptance pass

- Against All Odds <Deviant Energy> shoes, exact held-video Lv12: its +10%
  Weapon and Status base enters guided published comparison exactly once when
  the unknown variant/build evidence is explicitly accepted and the scenario
  states that no HP-cost event occurs. The extra HP-cost stacks remain partial;
  Lv12 does not imply values at other levels.
- A body-only scenario does not request crit or weakspot baseline bonuses for
  branches that cannot occur. Those bonuses remain required when such hits
  are included.
- A weapon with unbound unique effect is no longer reported as a complete
  weapon total merely because its direct-hit packet is known. An explicit
  `exclude_unbound_weapon_effect` option permits a clearly scoped direct-body
  subtotal; it does not certify the full weapon.
- The ledger now names the exact Static Shock <Survival> Lv11 and Elemental
  Overload <Resonance> Lv9 operator state, rather than treating all 54 exact
  core observations as having the same integration status.

## Next bounded work, separated by blocker

| Item or group | Missing field or behavior | Why it blocks | Next action and owner |
| --- | --- | --- | --- |
| Static Shock <Survival> Lv11 | Exact +20% Power Surge damage applies to eligible tagged packets; -50% affects target Power Surge **status lifetime**, not a damage tick schedule. A caller may enter a named lifetime/refresh model; status expiry is checked against later hit conditions. | The photographed mod gives no universal base lifetime or refresh policy. Ordinary Power Surge is an instant damage event with a separate status; Critical Pulse has its own orb pulse schedule. | **Weapon evidence:** confirm current target status lifetime and refresh/order from an exact source or one controlled proc-and-expiry contrast, then bind it. Keep unverified lifetime scenarios conditional; never infer recurring Power Surge ticks. |

The earlier 2-second/0.5-second four-to-two tick illustration was a synthetic
scenario that wrongly equated status duration with recurring damage. It has
been removed from acceptance tests and calculation logic. The exact held mod
tooltip establishes the two modifiers, while the [official Shock Diffusion
change](https://www.oncehuman.game/news/update/20241218/40780_1200958.html)
distinguishes applying Power Surge status from dealing damage. The [AUG Electron
Cloud item page](https://wikily.gg/once-human/items/10451401) describes a
single Power Surge damage instance and a separate status as a community source;
it is a candidate for base lifetime, not a current game-verified default.
| Against All Odds <Deviant Energy> Lv12 | Extra stack recipient, event ordering/expiry and applicability outside the held unknown-build observation | The +10% base is known; additional damage cannot be assumed passive | **Mod mechanics/evidence:** one controlled HP-cost contrast with event time and recipient, then source other levels separately. Keep no-event scenario available. |
| AUG Electron Cloud | Source-native tier-one page gives 34 displayed damage, 720 RPM and 40 rounds; damage unit/projectiles, reload seconds and unique effect event output remain unresolved | Displayed damage cannot be promoted to final bullets or timed full-weapon DPS | **Weapon evidence:** inspect the exact item/official effect wording, then one controlled direct-hit plus reload contrast if those fields remain unpublished. Current direct-body calculation is explicitly scoped. |
| Steady Hand <Resistance>; Slow and Steady <Resistance> | No sourced ordered four-line layout for these two current identities | Stat pools and level progression cannot be generated safely | **Catalog evidence:** obtain the exact identity page or one tooltip for each; do not transfer a different suffix layout. |
| Lunar low-HP bonus group | Known maxima but no HP-to-magnitude curve | A current HP point cannot be mapped to a specific bonus | **Mechanics evidence:** retain endpoint bounds or explicit magnitude; use two controlled HP points to distinguish candidate curves. |
| 133 imported weapon references | Imported damage basis lacks an item-ID anchored tier/star interpretation | Generic progression gives wrong tier values for known examples | **Weapon source mapping:** follow exact blueprint craft links to native tier/star pages; retain quarantine until each basis is anchored. |

These owner names identify the responsible engineering lane and concrete next
action; they do not imply a worker is currently executing every row. The full
ledger has nonempty owner and next-action fields for its missing requirements,
but many source-only rows still need item-specific acquisition details. Overall
all-gear calculation acceptance remains blocked.
