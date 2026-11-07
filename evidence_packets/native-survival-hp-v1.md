# Native player survival ratio and PvP HP-rate adjustment

This is a static source packet for copied build `26267212`. No extracted game code was loaded or executed. The controlled reference [synthetic_survival_pvp_hp_reference.py](synthetic_survival_pvp_hp_reference.py) checks the copied-file hashes and runs handwritten arithmetic only. Its inputs are synthetic, not Maurice's current player or any named encounter.

## Exact survival ratio expression

`dcs_extend\common\survival_utility.pyc` SHA-256 `f999c9fd13c835c2fba707ea49ffa249ca59fc593edfc482a8cb65f9d3b0cf2d`, `get_real_san_hp_radio_max` byte offsets `[3706,3758)`:

```text
ratio = min((max_san - san) * san_hp_ratio / 100, san_hp_ratio_max)
```

The helper has no lower clamp, no absolute value and no rounding. Offsets `[3720,3746)` contain subtraction, multiplication, division by literal `100`, then `min` with the fourth argument. Negative output remains possible for synthetic `san > max_san`; the ordinary property boundaries for these inputs require separate validation.

`CompPropertyFormulaServerPlayer._calc_attr_named_real_max_hp` in copied `CompPropertyFormula.pyc` SHA-256 `1e9e352e0b948b5eb0e4020dc26cf26b78724297329d6fbbbab2352bf5dd54f0`, offsets `[18800,19306)`, binds `max_san`, `san`, `san_hp_ratio`, `max_hp` from the **holder** (`getattr(..., None)`). It takes `survival_lib_no` from the holder with default `0`, and `contamination_resistance` with default `0`. The three config reads are:

```text
base_cap         = get_survival_config_val('san_hp_ratio_max',     default_val=0.9, survival_lib_no=no)
resistance_rate  = get_survival_config_val('resistance_hp_ratio',   default_val=0.0, survival_lib_no=no)
resistance_limit = get_survival_config_val('resistance_hp_limit',   default_val=0.3, survival_lib_no=no)
cap = base_cap - min(resistance_rate * contamination_resistance, resistance_limit)
raw_real_max_hp = (1 - min((max_san - san) * san_hp_ratio / 100, cap)) * max_hp
```

The numerical defaults apply only if a config entry is absent; they are **not** proof of the installed live config values. `survival_utility.get_survival_config_val` `[1061,1291)` checks a nonzero `survival_lib_no` override in `SURVIVAL_LIB_CONFIGS` first, returns it if non-`None`, then falls back to `player_survival_config[config_key][val_key]`, ultimately the caller's default. The `val_key` default is `'value'`. The `real_max_hp` typed ABS bound and integer rounding subsequently apply: clamp to `[0,999999999]`, round to six decimals, then `int(round(...))`; this is detailed with the HP revalidation cascade in [RECOVERED_HP_CEILING_AND_MAX_HP_FORMULA.md](RECOVERED_HP_CEILING_AND_MAX_HP_FORMULA.md).

### Controlled vectors

All use supplied `max_hp=200`, `max_san=100`. They test only this recovered expression and final typed rounding.

| Supplied `san`, `san_hp_ratio`, cap/resistance inputs | Ratio | Stored `real_max_hp` |
| --- | ---: | ---: |
| `san=80`, ratio factor `1`, base cap `.9`, no resistance | `.2` | `160` |
| `san=0`, factor `2`, base cap `.9`, resistance rate `.01`, limit `.3`, resistance `20` | `.7` | `60` |
| Same, resistance `100` (reduction limited to `.3`) | `.6` | `80` |

## PvP adjustment to the `max_hp` OTHER rate

`CompPropertyFormulaServerPlayer._calc_attr_named_max_hp` `[20000,20638)` gets OTHER `max_hp` rate and enters the table branch only when holder `use_max_hp_rate_adjust` is truthy `[20168,20190)`. It constructs `value_%d` from holder `formula_pvp_lib_no`, selects that key when present in `formula_pvp_adjust_max_hp_data['max_hp_rate']`, otherwise selects `value` `[20192,20336)`. It iterates table range/adjustment pairs, picks the first matching range and applies the exact pure transform:

```text
other_rate = adjustment_multiplier * other_rate + adjustment_addend
```

The operation is at `[20428,20456)` and occurs **before** the ordinary `max_hp` base formula (absolute addition and rate multiplication). No matching range leaves the original rate. The `[20386,20426)` chain compares a lower and upper range with the current rate, but the exact custom compare-op identities have not been independently proven for this code object; inclusive endpoints are plausible from the Python chained-comparison shape and remain unasserted here.

The compact native table copy `game_common\data\formula_pvp_adjust_max_hp_data.pyc`, archive index `27349`, SHA-256 `156e21565337a3b2d64ac36709b4be72c0974ac0d3a1ff88734a619866d22604`, contains a 194-byte bindict literal with the six string-pool names `value`, `value_2`, `value_3`, `value_1`, `value_4`, `max_hp_rate`. Its numeric region contains recognizable encoded doubles/floats, but the nested map/range/tuple rows have **not** been reconstructed and independently checked. Nearby numbers cannot be assigned to a PvP key or bracket without that typed decode. Thus the branch gate, lookup order and transform are source-backed; specific numeric PvP coefficients, ranges and endpoint policy remain unresolved. The reference script's bracket `(0.2,0.4,0.5,0.1)` is deliberately synthetic: rate `.25` becomes `.225`, while disabled/outside-bracket cases remain unchanged. It is **not** a game PvP row.

This packet closes the survival helper's arithmetic but does not supply live holder/config values or a fully decoded PvP table. It must not be used to claim the user's HP or boss damage from screenshot numbers alone.
