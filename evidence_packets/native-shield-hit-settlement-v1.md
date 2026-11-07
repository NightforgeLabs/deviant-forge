# Native held-shield hit settlement: bounded source rule

This is an offline static trace of copied build `26267212` modules. The captured module hashes and archive offsets are in [shield_settlement_capture/manifest.json](shield_settlement_capture/manifest.json). [synthetic_shield_settlement_reference.py](synthetic_shield_settlement_reference.py) implements only the recovered branch with explicitly supplied inputs; [synthetic_shield_settlement_vectors.json](synthetic_shield_settlement_vectors.json) records its passing vectors. No extracted game code was run, no live game process was accessed, and no installed game or Forge file was changed.

## Exact callback chain and gate

`CompBeHitServer.get_damage_hp_without_apply` in the prior copied `be_hit_server_capture/CompBeHitServer.pyc` `[49397,50275)` computes `damage_hp` with `_pre_calc_damage`, then `_calc_damage_attenuation`, then obtains the hit `part_name`. A missile-object early return is separate. Its `_process_shield(holder, part_name, damage_hp)` call is at `[49855,49899)`. For a true result, it jumps to `[50271,50275)` and **returns the same `damage_hp`**; it does not execute the subsequent level adapter, DPS correction, field subtraction or invincibility check in this method.

The specific `IBeHitServerWithPowerShield._process_shield` implementation `[151521,151661)` calls `_is_shield_obj`; if true it calls `holder[POWER_SHIELD_SERVER].reduce_shield_hp(holder, part_name, damage_hp)` and returns true. `_is_shield_obj` `[150968,151054)` delegates to `has_shield`. In `dcs_extend/common/shield_utility.pyc`, `util_get_real_shield_name` `[171,269)` resolves a part-name alias via `shield_part_name_dict`; `util_has_shield` `[484,680)` requires a matching `shield_dict` entry with state `ShieldState.shield_hold`. Thus this packet applies to a recognized, held shield object. It does not apply to ordinary health/armor hits or every direct shot.

## Pure shield HP rule

`CompPowerShieldServer.reduce_shield_hp` in `dcs_extend/component_server/CompPowerShieldServer.pyc` `[27745,28347)` normalizes the shield name, reads `shield_hp` and `shield_hp_type`, and, unless the type is `ShieldMaxHpType.Invincible`, calls `_change_shield_hp(holder, shield_name, -damage_hp)` at `[27937,27983)`. It bubbles `on_shield_be_hit`. If the resulting shield HP is `<=0` and the shield still exists, it changes state to `shield_crush` and bubbles `on_shield_destroy`. For Invincible type, it skips the HP change but still emits the hit event; an already-zero stored HP could still satisfy the subsequent break test.

`CompPowerShieldServer._change_shield_hp` `[29747,30109)` calculates a maximum, then applies:

```text
shield_hp_after = min(max(shield_hp_before + delta, 0), shield_maximum)
delta = -post_attenuation_damage in reduce_shield_hp
```

It stores the new value, bubbles `on_shield_hp_change`, and returns it. There is no rounding in these two shield methods. `_get_max_shield_value` `[30465,31205)` supports Fixed Value and Input Value (`shield_max_hp × skill_durability`), relative attribute, relative master attribute, skill strength, and an Invincible sentinel. `skill_durability` is `1` unless a summon owner exists and `summon_use_skill_config` is true; then it is `1 + owner.skill_durability`. The synthetic vectors supply an already resolved numeric maximum and do not model those context-dependent maximum branches.

| Synthetic input: post-attenuation damage, shield HP, max | Shield HP after | Shield events | `get_damage_hp_without_apply` return |
| --- | ---: | --- | ---: |
| `30, 80, 100` | `50` | hit | `30` |
| `35, 20, 100` | `0` | hit, crush, destroy | `35` |
| Invincible type: `40, 80, 100` | `80` | hit | `40` |

These vectors are computed from supplied synthetic inputs, not gameplay measurements. The second vector's 15 points beyond remaining shield HP are **not proven to spill into health**. The unchanged return `35` is a value from a method named `get_damage_hp_without_apply`, not a verified health decrement.

## Boundary for a complete final-hit result

The incoming `damage_hp` to this branch has already passed `_calc_damage_attenuation`; its body is not in the copied `CompBeHitServer` class, so this packet treats that value as a typed input. The class also lacks the `entity_on_hit_target` implementation that would connect its returned number to actual HP mutation. The shield callback itself supplies a real shield-HP update rule, while final health loss, overflow behavior, and the authoritative player/server settlement path remain unproven. Do not substitute this shield rule for the outgoing direct-hit graph or report its return as applied DPS.
