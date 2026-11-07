# Native HP ceiling and player max-HP formula (controlled path)

All evidence is from copied build `26267212` code objects and typed literal rows. [synthetic_hp_ceiling_reference.py](synthetic_hp_ceiling_reference.py) performs static assertions and runs only handwritten pure arithmetic. Its [vectors](/home/dv/Documents/Codex/2026-11-01/task-5/synthetic_hp_ceiling_vectors.json) are synthetic; no extracted game code was imported or executed, and no installed game or Forge file was changed.

## HP ceiling: `real_max_hp` when present

The native `char_property_data` rows in [native_hp_property_bounds.json](native_hp_property_bounds.json) are `hp/A00` with min `0`, `max_hp/A02` with min `1`, and `real_max_hp/A01` with min `0`. All three store max `999,999,999`, `val_type=1` (`ATTR_VAL_ABS`), and init `300`. These table initials are **not** current player or boss HP. The native `max_val` is float64 in these rows; row bounds and exact byte offsets are in the JSON.

Copied `attr_const.pyc` SHA-256 `a3ca0592024ba9a69db5ed0fd00131ed1bc392108d7da5e6ecec800b93c9c8e3` builds `ATTR_MAPPING` at bytes `[9172,9194)` with the first key/value **`hp → real_max_hp`**. It then builds `CHANGE_ATTR_WITH_MAX_ATTR` from the native `change_with_max_dict` keys and merges `ATTR_MAPPING` at `[9318,9352)`. The 19 native `change_with_max_dict` keys exclude `hp`, so that mapping is not displaced. `CompPropertyServer._adjust_attr_val` `[16645,16943)` and its avatar/player variant `[21632,22082)` check this mapping: **if the holder has `real_max_hp`**, they pass its current value as `with_max_attr_value` to `AffixUtils.adjust_attr_val`. The avatar variant's extra `BOUND_OVERRIDE_ATTRS` list is only `san`, `max_san`, and `san_hp_ratio`; it does not replace the HP bounds.

`AffixUtils.adjust_attr_val` `[30004,30498)` first applies `max(min(candidate, current_real_max_hp), 0)` when that current maximum is supplied; then applies the typed `[0, 999999999]` HP bounds, rounds to six decimals, and for ABS type converts using `int(round(...))`. If `real_max_hp` is absent from the holder, that dynamic maximum is not passed; only the typed bounds and any other explicit caller overrides apply. **HP is therefore capped by current `real_max_hp` on holders that expose it, not directly by `max_hp` and not only by the global 999,999,999 table maximum.** This is a conditional source rule, not proof that every NPC has that attribute.

## Player `max_hp` channels and order

`CompPropertyFormulaServerPlayer._calc_attr_named_max_hp` in `attack_consumer_captures/CompPropertyFormula.pyc` `[20000,20638)` reads:

```text
initial = calc_attr_init_val(holder, 'max_hp')
other_abs = abs_change_values[OTHER]['max_hp']
other_rate = rate_change_values[OTHER]['max_hp']
other_independent = independent_change_values[OTHER]['max_hp']
set_value = set_change_values.get('max_hp')
```

`calc_attr_init_val` `[6275,6495)` gets a combat-unit/table initial plus INIT absolute change, then INIT rate or independent channel. In its ordinary branch `[6794,6868)`, `initial = (base_initial + init_abs) × (1 + init_rate)`. The server player method optionally transforms **other rate** using a source range in `formula_pvp_adjust_max_hp_data` when `use_max_hp_rate_adjust` is true: `other_rate = adjust_multiplier × other_rate + adjust_addend` `[20168,20460)`. No numerical PvP range is asserted here; the vectors supply this flag as false.

The shared `_calc_attr_by_base_formula` `[7096,7200)` then chooses, in order:

```text
if set_value is not None: raw_max_hp = set_value
elif other_independent is nonempty:
    raw_max_hp = _calc_by_rate_addition_type(initial + other_abs, other_independent)
else:
    raw_max_hp = (initial + other_abs) × (1 + other_rate)
```

The INIT independent branch similarly calls `_calc_by_rate_addition_type(base_initial + init_abs, init_independent)` instead of using INIT rate. For `max_hp`, the typed `calc_type` is **0**, while `RATE_CALC_TYPE_ADD=1` and `RATE_CALC_TYPE_MINUS=2`. The helper `[13860,14506)` has no calculation branch for type 0 and returns its incoming amount. Thus, under the copied code, a nonempty independent list for `max_hp` selects a branch that returns the absolute amount and does not apply that list or the ordinary rate channel. This is a code finding, not a statement that an actual mod supplies such a list. After the formula, `_base_calc_attr_imp` `[3017,3259)` applies the native `max_hp` bound `[1,999999999]`, six-decimal round, and ABS integer conversion.

`CompPropertyFormulaServerPlayer._calc_attr_named_real_max_hp` `[18800,19306)` computes `(1 − effective_san_hp_ratio) × max_hp`. It obtains the effective ratio from `survival_utility.get_real_san_hp_radio_max(max_san, san, san_hp_ratio, san_hp_ratio_max)`; the maximum ratio itself is adjusted by contamination resistance and survival config values. The **helper output** is supplied as a typed input to the controlled vector. The `real_max_hp` result is then bounded and ABS-rounded through `_base_calc_attr_imp`.

## Recalculation and HP revalidation

`attr_const.CHANGE_RELATE_ATTRS` has ordered entries `max_hp → [max_toughness, real_max_hp]` and `real_max_hp → [hp]` at `[7584,7604)`. The player map clones this and updates other keys without replacing `max_hp`. `CompPropertyServer._on_attr_changed` `[10297,10771)` recalculates related properties and calls `set_attr`. For `hp`, `CompPropertyFormulaBase.calc_attr` `[2325,2577)` returns `None` because HP is a survival attribute; the property callback then reassigns the holder's **current** HP through `set_attr`, which runs the dynamic clamp above. The separate native `max_change_relate_attrs` map has 19 maximum-resource keys but excludes `max_hp`, so this route does not use its percentage-preservation helper for HP. The source supports revalidation/clamping of the current absolute HP after a changed `real_max_hp`, not an automatic proportional HP rescale.

## Synthetic vectors

Each vector explicitly supplies base initial 100, INIT absolute 0, INIT rate 0.1, OTHER absolute 20, OTHER rate 0.25, PvP adjustment disabled, a holder with `real_max_hp`, survival helper output 0.25, and current HP 150. These are controlled numbers, not observed game values.

| Extra input | Raw `max_hp` | Stored `max_hp` | Stored `real_max_hp` | HP after revalidation |
| --- | ---: | ---: | ---: | ---: |
| No independent/set | `(100×1.1 + 20)×1.25 = 162.5` | **162** (`int(round(162.5))`) | **122** (`int(round(0.75×162))`) | **122** (150 clamped to 122) |
| Nonempty OTHER independent list `(0.1,0.2)` | `110 + 20 = 130` | 130 | 98 | 98 |
| SET override `180.5` | 180.5 | **180** | 135 | 135 |

The independent case exercises `calc_type=0`; the set case bypasses all additive/rate arithmetic at the final branch. The static assertions verify the native map and relation tokens, and the pure runner asserts all three outputs. Remaining context for a real build includes which active affixes feed each source bucket, the PvP adjustment table when enabled, the survival helper's actual output, and the holder's current attributes.
