# Aero / Precision Charge family 9318: counter, reload, cap and element labels

Installed data build `26267212`. This packet is a static read of copied game source, with exact typed records in [`aero_9318_lifecycle_cap_labels.json`](aero_9318_lifecycle_cap_labels.json) (SHA-256 `b705c6a1360317ab6fa7efd1f194896120c9ef43e58bafb6d9d64b0a8b8b242b`). Reproduce with `python trace_aero_core_lifecycle.py`. The earlier [`aero_9318_core_math_graph.json`](aero_9318_core_math_graph.json) (SHA-256 `502ee43dd9fec111524e06c9b8e4497f87e62b867ce2c3c718799f896ddc133a`) binds these conditions to the typed graph. No extracted game code was executed; no installed game or Forge file was modified.

## Configured event and arithmetic chain

| Event or condition | Graph and readable-code evidence | Configured outcome |
|---|---|---|
| Core graph begins | Root node 19 controls nodes 9, 33, 16, 15 and 2 | Save `weakspot_count = 0`; save `mag_size = floor(weapon_magazine_size)`; register attack, reload and holding-change checkers. |
| Holding state changes | Checker node 2 tests state 45 (`HOLDING_CHANGE`), `enter_state = 1`; children 4 and 3 | Refresh `mag_size` from current `weapon_magazine_size` and reset `weakspot_count = 0`. This describes the configured event; actual ordinary weapon-equip timing is not inferred. |
| Attack damage event | Checker node 16 has `formula_attack_type = [2]` (`Remote`), `attack_type = [1]` (`AttackDamageType.WEAK`), `check_all_bullet = 0`; child 31 uses integer ADD operation with input 1 | Increment `weakspot_count` for a matching **weak remote damage event**. Native `PassiveChecker.attack_checker` delegates to `buff_utility.common_attack_checker`, which checks the event's `damage_type` against `attack_type`. Keywords 311/312 are configured with `keyword_negate = 1`; the installed tag rows end in `proj` / `shrap`, but exact eligibility of every multi-hit case is not proved. Count events, not necessarily distinct trigger pulls. |
| Successful reload event | Node 15 is `reload_once_suc_checker`; node 35 compares callback `cur_clip_left >= weapon_magazine_size` (`OpType.GE = 0`); true branch has nodes 57, 78, 23, 61 and 76 | On that configured true branch, compute `floor(weakspot_count / mag_size × 10)`, request secondary buff `589318100` with that many stacks, and reset `weakspot_count = 0`. The typed graph includes other sibling actions; serialized child order is not assumed to be runtime execution order. A callback with clip left below configured magazine size fails this condition. |

The reload computation uses **configured magazine size as denominator**, rather than shots fired. The graph does not include a divide-by-zero guard in the recovered expression; normal magazine size and event dispatch remain caller responsibilities.

## Six-stack cap and lifetime

The exact composite `buff_data` row `(589318100, level 1)` has `buff_max_stack = 6`, `life_time = 10.0`, `refresh_buff_stack = 0` and `refresh_rule = 0`. It is the only `buff_data` configuration row for that buff ID. It is at byte offsets 545456–545492 in the pinned copied literal (SHA-256 `48eb8011cf45cbb24d91e0fecb695ac669b3823ffcb98e197d28005aa6a5b73f`). Native `RefreshLifeTimeRule.MAX_TIME = 0`.

The readable `CompBuffServer` inherits `CompBuffBase`. Its `init_buff` uses `min(buff_max_stack, incoming buff_stack)` when the cap is positive and `multi_buff_enable` is false (the absent field defaults false in that code). Its `refresh_buff` computes `old_stack + incoming_stack + refresh_buff_stack` and applies the same positive maximum. Thus **the standard server buff component enforces six stacks if the graph's cast reaches it**. The node cast executor and reload callback dispatch were not readable; the packet does not certify that an owned mod fired the cast or establish expiration after a later refresh.

| Synthetic supplied events | Graph stack request | Standard new-buff cap | Conditional bonus at secondary level 4 / 5 |
|---|---:|---:|---:|
| Magazine size 10; five remote hit events, three WEAK and two NORMAL; callback reports clip left 10 | `floor(3 / 10 × 10) = 3` | 3 | `3 × 3% = 9%` / `3 × 4% = 12%` to each of the four configured element attributes |
| Magazine size 10; nine qualifying WEAK remote hit events; full reload callback | `floor(9 / 10 × 10) = 9` | `min(6, 9) = 6` | `6 × 3% = 18%` / `6 × 4% = 24%` to each attribute |

The per-stack 3% and 4% parameters come from `buff_level_data` for secondary levels 4 and 5. These are **conditional calculation vectors**, not Maurice's owned rank, observed proc, actual hit count or active combat result. Core rank, secondary buff level and the mod frame's four-line total level remain separate until their runtime selection is independently joined.

## Exact elemental property and English label join

The secondary buff's four `NodeChangeAttrInputValue` targets join to these native attribute definitions and installed English affix labels. They are four named element buckets, not a generic element damage property.

| Graph property | Native property | Affix key | Installed English label |
|---|---|---|---|
| `E32` | `element_type_dam_add_rate_fire` | `E3200` | Blaze DMG Bonus |
| `E33` | `element_type_dam_add_rate_ice` | `E3300` | Frost DMG Bonus |
| `E34` | `element_type_dam_add_rate_lightning` | `E3400` | Shock DMG Bonus |
| `E38` | `element_type_dam_add_rate_explode` | `E3800` | Blast DMG Bonus |

The crosswalk is from `native_attr_id_index_attr_name.json`, pinned `affix_prototype_data.pyc` (SHA-256 `a5732321ba5f84fa62fbfca910be49a93a26723d361a43afa28ea1a906d45d17`), and pinned English `translate_data_en.pinned.pyc` (SHA-256 `0bd9092f37c3fc4b3d771be76018cef66796e45ce7ca824dfb599a94a1117f95`). Exact row bounds and English pair offsets are in the JSON packet.

## Integration boundary

The source supports displaying the configured reload condition, weak remote event counter, stack arithmetic, six-stack standard buff cap, ten-second configured lifetime and four native element targets. A live damage/DPS contribution still requires proof of ordinary owned-item activation, the specific secondary level selected by `mapping_buff`, actual cast/event dispatch, and target damage graph application. Do not substitute this conditional vector for an observed player's result or conflate family core rank with frame bonus level.
