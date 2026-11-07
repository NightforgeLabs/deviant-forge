# Precision Charge / Aero reload cast and shared buff stack behavior

Installed build `26267212`. All analysis is static on copied data and code bytes. Reproduce the bounded assertions with `python trace_aero_cast_refresh.py`; its typed output is [`aero_cast_refresh_boundary.json`](aero_cast_refresh_boundary.json), SHA-256 `d9ab0dac386822afe09e01c7208f2608c0c773d8b06c797d05dc244ec3818e1d`. No extracted game code was executed and no installed game or Forge file was changed.

## Exact configured reload branch

The prior [core graph packet](aero_9318_core_math_graph.json) has `NodeReloadSucEvent` 15 feeding `NodeBuffIfTask` 18. The true branch after the `cur_clip_left >= weapon_magazine_size` comparison contains these **sibling** effects:

| Node | Configured effect |
|---|---|
| 57 | Dispel ID list `[58931810400]` on the holder. |
| 78 | Dispel ID list `[58931810500]` on the holder. |
| 23 | Save `mag_size` from floored current weapon magazine size. |
| 61 | `NodeCastBuffToTarget`: `buff_id=589318100`, `buff_lv=1`, `mapping_buff=1`, `reset=0`; its `buff_stack` input is wired to node 60, `floor(weakspot_count / mag_size × 10)`, and its target is the holder UID. No dynamic `buff_level` input is wired. |
| 76 | Save `weakspot_count=0`. |

The two dispel IDs are exact decoded integer arrays, not name matches. Generic `BuffDataHelper.get_buff_id` contains a `%s%02d%02d` template/level/star formatter, and `buff_level_map` gives `589318100` a maximum level of 5. Those facts make the IDs consistent with level 4 and 5, star 0 variants, **but do not prove that this cast calls that helper, chooses either level, or dispels before casting**. The graph's child serialization is not proof of server execution order.

`NodeReloadSucEvent` configures `reset_last_effect=1`; that is a node setting, not a proven server removal sequence. The graph has no separate reload-cancel event node. It does reset the counter on the reload-success true branch and on a holding-change checker. A canceled reload's counter behavior is not established from the readable event implementation.

## Exact executable-source boundary

The copied `NodeCastBuffToTarget.pyc` contains a `NodeServer` class with `need_reset`, but **no readable `NodeServer._do` method**. Its `NormalNodeServerBase._do` is a `NotImplementedError` stub. Likewise, the copied `NodeReloadSucEvent.pyc` has no readable `NodeServer._do` or callback-dispatch body. The exact missing join is the cast node's server executor that takes its linked `buff_stack` and level/template settings and calls the buff manager/component, plus the reload-success event dispatcher. No further level, cast or event-order assertion is made from class names.

## Shared server buff component: proved conditional rules

`CompBuffServer` inherits the readable `CompBuffBase` (source SHA-256 `1067d9cdf3d208109088762a606249108cd123ec95fb39778d2b69e2cafc2ce1`). The secondary buff's only `buff_data` configuration row sets `buff_max_stack=6`, `life_time=10.0`, `refresh_buff_stack=0`, `refresh_rule=0` (`MAX_TIME`); it omits `multi_buff_enable`, for which `init_buff` uses false as its default.

| Shared method | Source-proved operation if the manager calls it |
|---|---|
| `CompBuffBase.init_buff` | If `multi_buff_enable` is true, set initial stack to 1. Otherwise, if `buff_max_stack > 0`, set `stack = min(max_stack, incoming_stack)`; without a positive maximum, use incoming stack. |
| `CompBuffBase.refresh_buff` | `stack = old_stack + incoming_stack + refresh_buff_stack`; if maximum is positive, apply `min(max_stack, stack)`. It writes that computed stack and the caller-supplied `life_time` into buff runtime data. For `refresh_rule=IGNORE`, it sets `create_time` to now; otherwise it retains the prior `create_time`. |
| `CompBuffBase.refresh_buff_time` | Separately writes the caller-supplied `life_time` and sets `create_time` to the current time. |

Synthetic vectors with this secondary buff's cap: a **new** buff requested with 9 stacks starts at `min(6,9)=6`; an existing 4-stack buff refreshed with 3 incoming stacks becomes `min(6,4+3+0)=6`; an existing 2-stack buff refreshed with 1 incoming stack becomes 3. Thus **a repeated same-ID refresh accumulates then caps**. A replacement on each reload would require a verified prior dispel or a different manager branch. The readable graph does not prove either happens, so Forge must not model unconditional stack replacement or exact ten-second renewal from this packet.

These shared rules can be reused for other mods **only after their exact buff configuration and invocation path are joined**. The unresolved server cast executor, mapped level, sibling effect order, and reload callback are the remaining boundary for this mod's live behavior.
