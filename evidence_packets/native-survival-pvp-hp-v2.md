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

The operation is at `[20428,20456)` and occurs **before** the ordinary `max_hp` base formula (absolute addition and rate multiplication). No matching range leaves the original rate. The original bytes at `[20396,20422)` are `LOAD_FAST lower`, `LOAD_FAST rate`, `SWAP 2`, `COPY 2`, `COMPARE_OP 0`, then `LOAD_FAST upper`, `COMPARE_OP 1`. The previously control-validated CPython 3.11 comparison arguments are `0 = <` and `1 = <=`: the bracket test is **`lower < rate <= upper`**.

The compact native table copy `game_common\data\formula_pvp_adjust_max_hp_data.pyc`, archive index `27349`, SHA-256 `156e21565337a3b2d64ac36709b4be72c0974ac0d3a1ff88734a619866d22604`, has literal SHA-256 `74fcb94dfc6b8602ed84ff7377853fdac9b73ef6c4e22962078f2ba266f2a8da`. [decode_pvp_max_hp_table_static.py](decode_pvp_max_hp_table_static.py) parses its typed structure with pinned offsets and hash; [native_pvp_max_hp_table_static.json](native_pvp_max_hp_table_static.json) retains every typed number and byte offset.

The string pool is `[0,76)`. The body-size word at `[76,80)` is `103`, giving body `[80,183)`. Three typed range arrays occupy `[80,99)`, `[110,126)` and `[126,145)`; their shared typed adjustment tuple `(1.0,0.0)` occupies `[99,110)`. A type-11 pointer-key/pointer-value map at `[145,155)` contains three pairs `(4,23)`, `(34,23)`, `(50,23)`, relative to body base `76`. Thus every range points to the same adjustment tuple. The five-field descriptor at `[160,172)` names `value`, `value_1`, `value_2`, `value_3`, `value_4` as pointer fields. Its row at `[172,179)` contains five `69` pointers to the same range map at `76+69=145`. The outer typed map header is `[179,183)` and its sole indexed tail entry at `[191,193)` binds string-pool key `5 = max_hp_rate` to pointer `96`, resolving the five-variant row at `76+96=172`. The `[183,187)` four-byte trailer word is pinned raw (`2fc77ea0`) but its checksum/hash meaning is not needed or claimed; `[187,191)` gives tail offset `115`, resolving `[191,194)` including terminal zero. All 194 literal bytes are bounded by this deterministic parse, with no unassigned numeric value used as a coefficient.

| Native range key | Adjustment `(multiplier, addend)` | Match predicate |
| --- | --- | --- |
| `(0.2, 0.4)` | `(1.0, 0.0)` | `0.2 < rate <= 0.4` |
| `(0.6, 10.0)` | `(1.0, 0.0)` | `0.6 < rate <= 10.0` |
| `(0.4, 0.6)` | `(1.0, 0.0)` | `0.4 < rate <= 0.6` |

The map's native iteration order is shown above. Every variant has the same map. For this copied table, **the enabled PvP adjustment leaves the OTHER `max_hp` rate numerically unchanged**: a matching bracket applies `1.0 × rate + 0.0`, and an unmatched rate is left alone. The source-bound boundary checks in the JSON cover `0.2` (unmatched), `0.4` (first), `0.6` (third), `10.0` (second), and `10.1` (unmatched) for all five variant keys. This finding is specific to the copied build and this one table; it does not imply PvP has no HP effects elsewhere. The separate reference script's nonidentity bracket remains explicitly synthetic and does not represent this table.

This packet closes the survival helper's arithmetic and this PvP adjustment table, but does not supply live holder/config values or establish other PvP HP effects. It must not be used to claim the user's HP or boss damage from screenshot numbers alone.
