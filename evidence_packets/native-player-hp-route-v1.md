# Native hit settlement to HP write (offline static trace)

This packet supersedes the unresolved `entity_on_hit_target` and attenuation statements at the end of `RECOVERED_SHIELD_HIT_SETTLEMENT.md`. It traces copied build `26267212` data only. No extracted game code was loaded or run; no installed game, live process, or Forge file was changed.

## Exact modules and checks

| Archive index | Copied module | SHA-256 of pyc |
| ---: | --- | --- |
| 24730 | `dcs_extend/component/CompBeHitCommon.pyc` | `accfc688e30e341b8bc43f3113c7e1c929bcb9f2c1e9edc697d6f883e6ba48b2` |
| 4306 | `dcs_extend/component_server/CompHealthServer.pyc` | `68cd0d09c2b8ef3d1ffd83420e587bd58771d3b9174706a288cdc3acaf4704b1` |
| 59609 | `dcs_extend/component_server/CompPropertyServer.pyc` | `963c9b27084862d413157367bbc09d4baa35acdb9015bf68ad78bc3f50c518d4` |
| 76687 | `dcs_extend/common/affix/AffixUtils.pyc` | `325659f19ca8c55bd82c925162e880db1a49ee12caed4fa6ec8aadbe6a6715f5` |

`be_hit_server_capture/CompBeHitServer.pyc` and `shield_settlement_capture/28630_dcs_extend\\component_server\\CompPowerShieldServer.pyc` are the previously captured server modules. All offsets below are offsets in the copied pyc files, as reported by the static reader. The class-creation sequence at `CompBeHitServer.pyc` `[1378,1386)` places `IBeHitServerWithPowerShield` before `CompBeHitServer` among `CompBeHitPlayerServer` bases; its `_process_shield` override is therefore on the player path.

## Calculation, application, and write order

1. `IBeHitCommonBase._calc_damage_attenuation` `[6430,6570)` reads `hit_info.obstruct_nums` (default 0) and `attenuation_factor` (default 0), returning `max(0, damage_hp × (1 − attenuation_factor)^obstruct_nums)`. This arithmetic is fully readable. `IBeHitCalcDamageCommonBase._calc_damage_hp_with_hit_info` invokes it after `_calc_damage` at `[19832,19898)` or `[19964,20008)` for its packet branches. It is a pre-application amount.
2. `IBeHitCalcDamageServer.entity_on_hit_target` `[34973,35395)` checks hit eligibility, calculates damage via `_calc_damage_hp_with_hit_info`, and returns a dictionary with `damage_hp`, `damage_amount_info`, and `hit_check_ret`. There is no health mutation in this method.
3. `CompBeHitServer.entity_be_hit` calls `_entity_be_hit_imp` at `[71858,71904)` after its checks and merge gate. `_entity_be_hit_imp` invokes `_apply_damage` for the normal packet at `[74135,74217)` (and in the multiple-packet branch `[73489,73701)`), after `_on_be_hit`. It reads `real_damage_hp` and `res` from the returned dictionary; these are **not equivalent to measured HP loss**.
4. `CompBeHitPlayerServer._apply_damage` `[161479,161561)` delegates to its superclass after its optional illusion share-damage reduction. The underlying `CompBeHitServer._apply_damage` checks `_process_shield(holder, hit_part, damage_hp)` at `[85000,85044)` **before** the ordinary health and field branches. When this returns true, it jumps to `[86106,86220)`, sets `res = HIT_SHIELD`, and skips `HEALTH_SERVER.take_damage` entirely. `IBeHitServerWithPowerShield._process_shield` `[151521,151661)` calls `POWER_SHIELD_SERVER.reduce_shield_hp` on a recognized shield, then returns true. Its actual shield decrement and clamp were recovered in the earlier packet.
5. When the shield predicate is false and the ordinary branch is reached, `_apply_damage` calls `holder[HEALTH_SERVER].take_damage(holder, damage_hp, damage_info, check_invincible=...)` at `[85870,85998)`, after level/DPS correction, optional field handling, and independent-part/overflow conditions. The structure and stun branches have separate calls. Thus a generic outgoing graph number alone cannot be treated as HP loss.
6. For the player health component, `CompHealthServerPlayer.take_damage` `[77182,78348)` can return early on guards (nonpositive value, invincibility, dead state, etc.). It may transform `value` through `_damage_sync_process`; normal state calls `normal_state_take_damge` `[78260,78306)`. That calls `_normal_health_damage_imp` `[89737,89785)`. In `_normal_health_damage_imp` `[92854,93600)`, positive structure field can intercept; otherwise `_cost_field_value` may reduce the value and `_change_hp_value(holder, -value, damage_info)` is called at `[93100,93144)`. `IHealthServerCommon._cost_field_value` `[9688,10002)` consumes temporary and named field values before returning remaining value.
7. `CompHealthServerBase._change_hp_value` `[49458,50132)` applies lock-HP and `must_die`/`must_alive` adjustments to the delta, then calls `holder[PROPERTY].change_attr(holder, 'hp', delta)` at `[49902,49986)`. `CompPropertyServerPlayer.change_attr` `[29890,30250)` can reject direction-forbidden changes, otherwise computes old property plus delta and calls `_adjust_attr_val`. The inherited `_adjust_attr_val` `[16645,16943)` calls `AffixUtils.adjust_attr_val`, then `_set_attr`; `_set_attr` `[8770,8986)` resolves the actual holder property and executes `setattr(holder, real_attr_name, real_value)` at `[8834,8866)`. The helper `adjust_attr_val` `[30004,30498)` uses typed min/max bounds, an optional max-attribute value, and round/int conversion before that assignment. This is the exact readable HP write route, conditional on all preceding gates.

## Event amount versus actual loss

In `_apply_damage`, `real_damage_hp` is initialized to incoming `damage_hp` at `[83330,83334)`. In the true shield branch it is **not zeroed** before the return. However that branch never calls `HEALTH_SERVER.take_damage`. Later, `_apply_damage` sets `hit_info['actual_total_damage'] = max(original_hp − holder.hp, 0) + actual_field_damage` at `[87198,87340)`, and calls `_event_trigger` with `min(original_hp − holder.hp, PYTHON_TO_INT_SENTINEL)` at `[87342,87452)`. It also returns `hp_change_value = clamp(original_hp − holder.hp, 0, holder.max_hp)` at `[87676,87802)`. `_event_trigger` builds and may bubble attacked events; event emission is not evidence of a health write. On an otherwise isolated shield-only hit with no field or other concurrent HP change, these HP-loss values are zero even though `real_damage_hp` still carries the pre-shield amount and the shield hit event fires.

### Synthetic branch checks (conditional, not gameplay observations)

| Supplied conditions | Pre-application amount | Shield after | Holder HP after | Result |
| --- | ---: | ---: | ---: | --- |
| Damage 100, obstruction count 1, attenuation factor 0.2; held finite shield 50/100; holder HP 100; no concurrent changes | 80 | 0 | 100 | `HIT_SHIELD`, `real_damage_hp=80`, `hp_change_value=0`; no HP overflow call |
| Same inputs, shield 90/100 | 80 | 10 | 100 | `HIT_SHIELD`, `real_damage_hp=80`, `hp_change_value=0` |

For an ordinary **unshielded** hit, the source proves the *route* to the HP setter, not a universal `HP_after = HP_before − graph_damage` equation: invincibility, state, sync, structure/field, lock HP, part-overflow, direction forbids, and property bounds can all change or prevent the write. The readable source does prove that exceeding shield HP does not itself cause an overflow call to `HEALTH_SERVER.take_damage` on the shield branch.

## Remaining boundary

This is a source-backed player server settlement path. It does not prove that a given outgoing formula packet is accepted by eligibility checks, nor does it prove the authoritative equipped attack input or the exact live HP loss for Maurice's screenshot. The observed runtime state and any additional native/server overrides are not in this static packet. Do not replace the returned `real_damage_hp` or an attacked event with measured HP loss in Deviant Forge.
