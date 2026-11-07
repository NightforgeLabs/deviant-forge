# Published calculator reference comparison

`POST /api/published-reference-compare` accepts hypothetical left and right catalog builds. It does not read or change inventory, saved builds, or Field Guide records.

```json
{
  "left": {
    "weapon": {"catalog_id": "weapon:kam", "stars": 1, "tier": 1, "calibration": 0},
    "mods": [{"catalog_id": "mod:weapon_mod:flame-resonance-general", "level": 8}],
    "armor": [{"catalog_id": "armor:bastille-boots", "stars": 1, "tier": 5}]
  },
  "right": {
    "weapon": {"catalog_id": "weapon:mps5-blue-tiger", "stars": 2, "tier": 3, "calibration": 4},
    "mods": [{"catalog_id": "mod:weapon_mod:flame-resonance-violent", "level": 17}],
    "armor": [{"catalog_id": "armor:agent-shoes", "stars": 1, "tier": 5}]
  }
}
```

The source-native weapon baseline comes only from the Apache-2.0 [OnceHuman_Tools calculator](https://github.com/lReDragol/OnceHuman_Tools), never from an unlabeled database page damage number. Its published star/tier/calibration multiplier applies to per-projectile damage. The reference direct-only hit applies supported selected mod pools; firing and reload-cycle rates use source RPM, magazine and reload seconds. Reload Speed rating is excluded because its conversion to seconds is unknown. Magazine rounding follows the calculator's Python model. These are named model outputs, **not established current-game DPS or a game winner**.

Current installed packet coverage: 131 of 138 catalog weapons match a source-native baseline, 128 have numeric per-projectile damage and projectile count, and 103 have all direct-only reload-cycle inputs. The armor packet contains 468 exact slot/rarity/star/tier rows: 280 complete, 4 partial and 184 zero placeholders. Missing source rows and zero placeholders return unknown, never zero. The six armor slots can provide aggregate HP and Psi only when every supplied row resolves; `complete_six_slot_build` requires all six slots. Armor set bonuses are outside this reference layer.

The published ordinary mod packet plus the identity-scoped Elemental Havoc Violence bridge supplies 14,977 of 16,728 theoretical identity-level profiles; the reference builder consumes selected level rows. The remaining 1,751 are 714 retained old random-roll profiles needing their actual rolls, 1,003 mixed-generation identity mappings, and 34 current Resistance profiles needing their layout. These identities are not declared obsolete. The bridge adds 17 candidates for only one Violence identity; no global Violence-to-Violent rename is made. The reference model applies only source-described Weapon DMG, All DMG Boost, Magazine Capacity, Fire Rate and Reload Efficiency under a named additive-pool assumption. Other lines, blocked layouts and conditional activations remain in `selected_mod_rows` and `unresolved`; they do not become zero or passive bonuses. The four-line data is also consumed by the existing component and planned-build comparison paths.

Source snapshots and attribution: `evidence_packets/weapon-baselines-published.json`, `evidence_packets/armor-table-published.json`, `evidence_packets/published-gap-resolution-v2.json`, and `evidence_packets/LICENSE-ONCEHUMAN-TOOLS.txt`. Source game version is not certified. Current-client calibration and the remaining source rows need evidence rather than invented values.

The structured Compare screen now offers a guided published-reference section. A selected catalog item or saved plan supplies its mod/armor rows; a mod-only or armor-only selection needs an explicit reference weapon. Existing crit/status/proc/set sensitivity and typed outputs are displayed in the same result, but they are **not compounded into the direct-only rate**. If a missing published line could alter that rate, the complete ratio is withheld.

## Timed composition

The guided timed subsection now composes supported pieces of one explicitly named encounter: source RPM/magazine/reload shot times, a published direct-body baseline, crit and weakspot branches through the shared `combat_projection.components` operator, static numeric main-mod outputs when evidence and context gates pass, released set rules where activation is stated, and one selected source-bound extra packet with an entered occurrence count and Attack/Psi/reference basis. A complete six-slot armor table can supply Psi; otherwise Psi is an explicit scenario input. Source crit rate is the default hit share; blank weakspot share is the stated body-only scenario. Equal duration and a confirmed common target are required for a conditional modeled rate comparison.

The installed source packet library has 14 packet descriptions: 13 constant-coefficient event shapes can enter this guided path when their class, basis and count resolve. The Hazardous Object affine ammo blast needs a linked reload/ammo event and stays unresolved here. Preview coefficients require the preview scenario mode. Packet uncertainties such as tick lifetime, crit eligibility, target mitigation and stacking are displayed separately. A counted source packet is a caller-selected outcome, never an inferred random trigger rate.

The released Bastille 2-piece Reload Efficiency rule and Treacherous Tides 2-piece conditional Weapon/Status rule are applied under the stated PvE non-RaidZone and HP conditions. Other reached thresholds, including historical Bastille 1-piece and Treacherous Tides 3-piece interpolation, remain unresolved; the known subtotal remains visible and the complete timed total is withheld. Healing, shields, ammo utility, target defense, resistance, range falloff, unknown main effects and undocumented procs are not silently treated as zero. No result establishes a current-game winner.
