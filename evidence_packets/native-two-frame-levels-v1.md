# Two native four-line previews and Aero family 9318 core graph

Installed build `26267212`; all reads are static copies. No extracted game code was executed and no installed game or Forge files were modified. Reproduce the preview with `python trace_two_frame_catalog_previews.py` and the Aero graph packet with `python trace_aero_9318_core_math.py`.

## Exact identity and shared level lookup

`new_mod_property_data` binds ordinary Shock Diffusion `<Survival>` item `19500434` / mod `2400434` and its separate Shiny item `19505174` / mod `2410174` to family `10302`, frame `19`. The frame has ordered subentries `[5101,7402,7403,7405]`. Ordinary Shatter Them All `<Shrapnel>` item `19500304` / mod `2400304` and its separate Shiny item `19505109` / mod `2410109` bind to family `10101`, frame `1201`, ordered subentries `[7311,7313,7314,7405]`. Exact source property row offsets and frame array byte offsets are in [`two_frame_catalog_levels.json`](two_frame_catalog_levels.json), SHA-256 `17a86d1f265c64413f4a950959ddc63a8277426d7958634f38359285fe21076d`.

The same `ModDataHelper.get_mod_v2_levels` body used for Aero reads the selected mod's frame, counts its four subentries, and indexes `new_mod_level_data` by total level to retrieve `frame_lv_1` through `_4`. Its bytecode has no `is_shiny_mod` branch. `get_mod_fixed_sub_entries_data_lst_v2` then looks up each composite `(entry_no, frame_level)` key. Thus **ordinary and Shiny variants of the same frame have the same configured four bonus lines**; their separate `shiny_buff_id` and core effects are outside this preview. This is not an owned-item level or a rank-to-level conversion.

| Total level | Ordered entry levels | Shock Diffusion `<Survival>` lines | Shatter Them All `<Shrapnel>` lines |
| ---: | --- | --- | --- |
| 1 | `[1,0,0,0]` | Max HP +1.2%; other three locked | Shrapnel damage +1.2%; other three locked |
| 8 | `[2,2,2,2]` | Max HP +2.4%; damage reduction after being hit 3.2% for 3 seconds, cooldown 6 seconds; damage received from monsters −3.2%; damage to all monsters +3% | Shrapnel damage +2.4%; Shrapnel Crit DMG +10%; Shrapnel Weakspot DMG +6%; damage to all monsters +3% |
| 17 | `[5,5,5,2]` | Max HP +6%; damage reduction after being hit 8% for 3 seconds, cooldown 6 seconds; damage received from monsters −8%; damage to all monsters +3% | Shrapnel damage +6%; Shrapnel Crit DMG +25%; Shrapnel Weakspot DMG +15%; damage to all monsters +3% |

The JSON has **every level 1–17**, locked state, four ordered lines, typed configured values, exact entry/buff row byte offsets and native property IDs. The direct Shrapnel affixes are `J1200→J12 keyword_proc_dam_add_rate_shrap`, `J6100→J61 keyword_proc_crit_dam_add_rate_shrap`, and `J8100→J81 keyword_proc_weak_dam_add_rate_shrap`. Max HP is `A0202→A02 max_hp`. The `7402` on-hit reduction routes through buff `589721000` and its configured cast of secondary buff `589721100`; typed `NodeChangeAttr` rows in the secondary graph select `G52 attack_type_ignore_dam_rate_remote` and `G53 attack_type_ignore_dam_rate_dot`. Typed `NodeChangeAttrInputValue` rows in the `7403` graph select `G64/G62/G63 species_dam_ignore_rate_vulcher/alters/rosetta`. The `7405` graph's typed rows select `E101/E99/E102/E100` for creeps, elite, leader and boss damage. These graph attributes are source identifiers; catalog text does not establish that all of them are active in a given encounter. In particular, the `7403` text says monsters broadly while the decoded graph lists three factions.

## Aero core family 9318

This section is separate from the frame bonus-line level table. Exact composite `mod_entry_data` family keys `(9318,4)` and `(9318,5)` select core buff `589318000`. Its native `buff_level_data` descriptions at level 4 say “for every 10% weakspot hit rate in the previous magazine, Elemental DMG +3%, up to +18%, lasts 10 seconds, recalculated on reload.” At level 5 the values are +4% per 10% and +24% maximum. Those are native tooltip values, not owned-rank evidence.

The typed [`aero_9318_core_math_graph.json`](aero_9318_core_math_graph.json), SHA-256 `502ee43dd9fec111524e06c9b8e4497f87e62b867ce2c3c718799f896ddc133a`, verifies these **configured graph operations** through actual data links:

```text
node 22 = float(BB weakspot_count) / float(BB mag_size)  # operation 3 = DIV
node 25 = node 22 * 10.0                              # operation 1 = MUL
node 60 = floor(node 25)
node 61 casts secondary buff 589318100 with buff_stack = node 60

secondary node 15 = float(buff_stack) * node 13
secondary node 13 has literal default 0.04 and a dynamic binding to
    effect_params.params.value[0]
secondary node 15 feeds four elemental damage attributes:
    fire, ice, lightning, explosion
```

The secondary buff's level rows separately configure per-stack params `0.03` at levels 1–4 and `0.04` at level 5, with text maximum six stacks and duration ten seconds. As **synthetic input vectors**, BB weakspot count 3 and BB magazine size 10 yield 3 configured stacks; a secondary level-4 value would give `3×0.03 = 0.09` (9%) and level 5 `3×0.04 = 0.12` (12%). Counts 6 and 10 yield 6 stacks, then 18% or 24%, matching the corresponding tooltip maximum. The decoded arithmetic does not itself prove the runtime six-stack clamp when the computed count exceeds six.

The graph does not establish how the blackboard counts are updated for an owned weapon, when its cast and reset actually execute, whether `mapping_buff=1` selects the expected secondary level on the server, or whether the server applies all four attributes. Preserve the displayed core text and the graph expression with this scope; do not merge core rank with total bonus level or present a synthetic vector as Maurice's actual combat result.
