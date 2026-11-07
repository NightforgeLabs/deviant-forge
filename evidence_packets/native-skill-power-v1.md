# Native D41 / `skill_power` property calculation

This packet follows the copied build `26267212` **player property** path. [trace_skill_power_default.py](trace_skill_power_default.py) pins all cited source-file hashes and byte offsets, then calls the already checked handwritten pure functions from `synthetic_preview_reference.py`. The machine packet [skill_power_default_trace.json](skill_power_default_trace.json) contains six controlled vectors. No extracted game code was imported/executed and no game or Forge file was changed.

## Identity, typed row and dispatch

The independently decoded 838-entry native attribute map binds `D41 → skill_power` at literal offsets `[95583,95587)`. The copied `char_property_data` row `[107695,107735)` sets `init_val=0`, `min_val=0`, `max_val=9999`, `calc_type=0`, `ent_type=1`, and `val_type=2`. In copied `attr_const.pyc` SHA-256 `a3ca0592024ba9a69db5ed0fd00131ed1bc392108d7da5e6ecec800b93c9c8e3`, type `2` is `ATTR_VAL_RATE`, while `1` is `ATTR_VAL_ABS`. This is a **native storage/calculation type**, not proof that displayed Psi is a percent. `AffixUtils.adjust_attr_val` `[30004,30500)` clamps D41 to `[0,9999]`, rounds to six decimals, then to three decimals for this val type; it does not convert D41 to an integer. A Gear summary may separately format its holder value to an integer.

`skill_power` is absent from the 14 special keys of `attr_const.CALC_ATTR_FUNCS`; the player map only adds a `max_hp` special method. `CompPropertyFormulaBase._base_calc_attr_imp` `[3017,3259)` therefore selects `_calc_attr_default` for D41. It calls `AffixUtils.adjust_attr_val` after the formula. The copied server player `get_attr_init_abs_val` `[21899,22243)` reads the character property table using holder `char_property_lib_no`, then a combat-unit/vehicle table override, then adds the INIT absolute bucket. Thus `init_val=0` is the generic table fallback, **not** a guarantee that a live holder's pre-affix value is zero.

## Channel equation and ordering

`_calc_attr_default` `[3653,3999)` reads INIT, OTHER absolute, OTHER rate, OTHER independent, and SET channels. `calc_attr_init_val` `[6275,6495)` and `_calc_attr_init_val` `[6794,6868)` calculate the initial portion. `_calc_attr_by_base_formula` `[7096,7200)` selects SET first, then independent, then the ordinary rate branch. For D41's `calc_type=0`, `_calc_by_rate_addition_type` `[13860,14506)` has no add/minus branch and returns its incoming amount. With explicitly supplied channel inputs:

```text
init_abs_total = table_or_combat_initial + INIT.absolute
if INIT.independent is nonempty:
    initial = init_abs_total                  # D41 calc_type 0; INIT.rate bypassed
else:
    initial = init_abs_total * (1 + INIT.rate)

if SET is not None:
    raw_skill_power = SET                    # includes a numeric zero
elif OTHER.independent is nonempty:
    raw_skill_power = initial + OTHER.absolute # OTHER.rate bypassed
else:
    raw_skill_power = (initial + OTHER.absolute) * (1 + OTHER.rate)

stored_skill_power = round(round(clamp(raw_skill_power, 0, 9999), 6), 3)
```

The copied source-type constants and `INIT_SOURCE_TYPE_LIST` place `SOURCE_TYPE_EQUIP=3` in INIT. `SOURCE_TYPE_BUFF=4`, `SOURCE_TYPE_PASSIVE=5`, and `SOURCE_TYPE_MOD=26` are outside that list and therefore in OTHER when those sources submit property changes. This is **source-bucket routing**, not proof that a specific buff, mod or armor item is active. The SET channel is an override in the holder's separate `set_change_values` dictionary, not a claim that every equipment set uses this channel.

Native affix prototypes `D4100`, `D4101`, `D4102` all target `D41`; the typed rows are respectively `(effect_range=1, type=1 absolute)`, `(1,2 rate)`, and `(2,2 rate)`. The installed source's Shelterer Hat, gear `21001005`, Tier V six-star **stock client base preview** has `D4100 = 92 × 1.25 = 115`. This source-qualified item display value is not an owned-item or active-holder total. If that exact 115-valued D4100 reaches an active EQUIP source, it contributes to INIT absolute; the owned instance, selected model, other affixes, set, buff and server assignment are unresolved.

## Controlled arithmetic

The first vector is conditional on a hypothetical active `D4100=115` and all other supplied channels zero. Other numbers below are expressly synthetic; none reconstruct the user's observed `793` Psi.

| Input variation from generic base `0`, conditional INIT absolute `115` | Initial | Raw | Stored D41 |
| --- | ---: | ---: | ---: |
| No other changes | 115 | 115 | 115 |
| INIT rate `.10`, OTHER absolute `20`, OTHER rate `.25` | 126.5 | 183.125 | 183.125 |
| INIT independent `[.5]` also present; its plain `.10` rate bypassed | 115 | 168.75 | 168.75 |
| OTHER independent `[.5]` also present; its plain `.25` rate bypassed | 115 | 135 | 135 |
| SET override `250.56789` | 126.5 | 250.56789 | 250.568 |
| Supplied INIT absolute `10000` | 10000 | 10000 | 9999 |

The final missing join for a user-specific AUG Power Surge input is the active holder's complete D41 source map and any server/combat-unit initialization. The graph reads this resolved property, while the source-qualified stock armor preview only identifies one possible input contribution. No character-specific Psi or status damage follows from this packet alone.
