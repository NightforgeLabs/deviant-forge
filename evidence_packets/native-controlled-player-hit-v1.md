# Controlled player hit replay from a supplied post-graph amount

[synthetic_player_hit_reference.py](synthetic_player_hit_reference.py) is a handwritten pure reference for one proven, ordinary player-hit branch. [synthetic_player_hit_vectors.json](synthetic_player_hit_vectors.json) contains every supplied input and the four results. Running this reference imports no game code. The source-to-HP chain and copied-module hashes are in [RECOVERED_FINAL_HP_MUTATION_ROUTE.md](RECOVERED_FINAL_HP_MUTATION_ROUTE.md) and [hp_path_capture_manifest.json](shield_settlement_capture/hp_path_capture_manifest.json).

## Branch contract

The starting value is an explicitly supplied **post-graph damage amount**. It is not a weapon tooltip number, an observed live hit, or a claim that the outgoing graph was accepted. The fixture supplies hit accepted and unmerged, `DEFAULT` hit type, normal living player state, disabled level adaptation, no missile/stun/illusion branch, zero structure and field, no independent part or part overflow, no damage share group, `dps_ratio=1`, sync rate 1, no lock HP, no `must_die`/`must_alive`, no property direction forbid, and effective synthetic HP property bounds `[0,100]` with ABS integer conversion and a direct scalar `hp` mapping. The script rejects alternate guards it does not model.

These are **synthetic inputs**, not game defaults. Source: `IBeHitCommonBase._calc_damage_attenuation` `[6430,6570)` applies `max(0, d × (1 − factor)^count)`. `IBeHitAvatarCommon._check_level_adapter_damage_hp` `[13215,13731)` returns false when its disabled gate is true. `IBeHitCommonBase._get_dps_corrected_damage_hp` `[11856,12102)` leaves a ratio of 1 unchanged. `CompHealthServerBase._damage_sync_process` `[28644,29826)` skips group sharing when no group is present and for nonzero damage uses `max(round(damage × rate), 1)`; with rate 1 and integer damage it is unchanged. `IHealthServerCommon._cost_field_value` `[9688,10002)` has no amount to consume under the supplied zero-field inputs. `CompHealthServerBase._change_hp_value` `[49458,50132)` calls `PROPERTY.change_attr('hp', -damage)` after the supplied lock/death guard conditions. `AffixUtils.adjust_attr_val` `[30004,30498)` applies the supplied effective typed bounds and ABS conversion before `CompPropertyServer._set_attr` writes the holder property at `[8834,8866)`.

The invincibility fixture supplies `_need_check_invincible=True` and `holder.avoid_be_hit != InvincibleLevel.NO`. `CompHealthServerBase._check_is_invincible` `[22880,23106)` therefore returns true, and `CompHealthServerPlayer.take_damage` `[77730,77810)` returns `SUCCESS` before the HP write. The be-hit wrapper zeros `real_damage_hp` and displayed amount at `[85998,86018)`. Part-only invincibility is rejected by this reference because its reporting path differs.

## Results

| Controlled case | Post graph → post attenuation | Shield HP before → after | Player HP before → after | Reported `real_damage_hp` | Actual HP change | Result |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Held shield, 50 HP, 100 damage, one 20% obstruction | `100 → 80` | `50 → 0` | `100 → 100` | 80 | 0 | `HIT_SHIELD`; no overflow HP call |
| Unshielded ordinary hit | `80 → 80` | absent | `100 → 20` | 80 | 80 | `SUCCESS` |
| Unshielded lethal hit with `[0,100]` ABS HP bounds | `80 → 80` | absent | `40 → 0` | 80 | 40 | `KNOCK_DOWN`, **conditional on** supplied successful `DYING` state action |
| Unshielded, invincibility block | `80 → 80` | absent | `100 → 100` | 0 | 0 | `SUCCESS` with no HP write |

On the shield branch, `IBeHitServerWithPowerShield._process_shield` `[151521,151661)` calls the shield HP reducer, and `CompBeHitServer._apply_damage` jumps past `HEALTH_SERVER.take_damage` at `[85000,85044)`; a shield with only 50 HP still consumes the whole 80-point hit for this branch. `real_damage_hp` was initialized to 80 before that gate and is not zeroed. The wrapper separately computes `hp_change_value` from original minus current HP and `actual_total_damage` from HP plus field change; both are zero in this isolated shield fixture. An attacked event may still be emitted.

For the lethal vector, `CompHealthServerPlayer._normal_health_damage_imp` `[93100,93144)` passes negative remaining damage to the HP writer. The explicit property minimum 0 clamps `40 − 80` to 0. `normal_state_take_damge` `[89737,90457)` checks HP after the write, calls `DYING` unless `_check_direct_enter_die` is true, and returns `KNOCK_DOWN` if that state action succeeds. `_check_direct_enter_die` `[88091,88325)` returns true for swimming, nuclear-bomb death cause, or the avatar direct-die setting; all three are explicitly false in the fixture. The supplied state-action success is a controlled callback result, not an assertion about live game state.

## Scope and corrected earlier packets

- [RECOVERED_SETTLEMENT_AND_AUG_STATUS_BOUNDARY.md](RECOVERED_SETTLEMENT_AND_AUG_STATUS_BOUNDARY.md), points 5–6, said attenuation, level, DPS and field helpers were unavailable and that `entity_on_hit_target` had no readable body. Those helpers are in the imported `CompBeHitCommon.pyc`; `IBeHitCalcDamageServer.entity_on_hit_target` `[34973,35395)` is readable. The older warning that an outgoing graph number is not automatically final HP loss remains correct.
- [RECOVERED_SHIELD_HIT_SETTLEMENT.md](RECOVERED_SHIELD_HIT_SETTLEMENT.md), final boundary section, said the attenuation body and player HP route were unknown and shield overflow was unproven. The player `_apply_damage` path now proves the shield branch skips health application, and the attenuation equation is recovered. Its earlier shield-HP clamp and event observations remain valid.
- [RECOVERED_FINAL_HP_MUTATION_ROUTE.md](RECOVERED_FINAL_HP_MUTATION_ROUTE.md) already incorporates the corrected call chain. This replay narrows it to four controlled fixtures and adds the explicit sync, property-bound, invincibility and death-action conditions.

The remaining limit is live applicability: actual equipped attack, eligibility, field, property bounds, target state and state-action result must be supplied or independently established before presenting a full hit or DPS number for a real player. This reference intentionally raises for unsupported branches rather than treating their outputs as zero.
