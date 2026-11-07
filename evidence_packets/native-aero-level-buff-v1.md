# Aero Weapon DMG: exact level text and graph configuration

This is a read-only static trace for installed build `26267212`. The [level and buff ledger](aero_level_buff_config.json) is reproduced by [`trace_aero_level_buff_config.py`](trace_aero_level_buff_config.py); the [node and state ledger](aero_buff_graph_config.json) is reproduced by [`trace_aero_buff_graph.py`](trace_aero_buff_graph.py). Their SHA-256 hashes are `ccf1089f823d57f1c6d23765cabe3718f54c1ccba98bf687a7cc5d58eb3f8a05` and `4b8eb268893961a44eb333ec7eb382b6909e1b2b547961d2d6e4228b2cb799f0`. No extracted game code was loaded or executed; no installed game or Forge files changed.

## Total level → Aero entry level

`ModDataHelper.get_mod_v2_levels` (first source line 1794, original body `[72021,72687)`, SHA-256 `7e51156e1c5613e11572c99020c4a78ec11fc826a450272df2c72e764e4cfcb2`) reads the mod's `frame`, the frame row's `sub_entry_item_no` count, and the `new_mod_level_data` row for a clamped `total_levels`. Its list comprehension reads `int(row.get('frame_lv_' + str(i+1), 0))` for four positions. `get_mod_fixed_sub_entries_data_lst_v2` (body `[77854,78096)`, SHA-256 `4e57a8055ef7af2eed4f517ddc4b04cad3a0e9bd8c6ef61b12e4b4236612985e`) calls that level helper for the selected mod and total level, then pairs each result with the frame's ordered entry number in `get_entry_data(entry_no, level)`.

For item `19500811` / ordinary Precision Charge `<Aero>` mod `2400811`, frame `26` supplies ordered entry numbers `[2601,2602,7405,5101]`. The typed `new_mod_level_data` rows are:

| Total level | Ordered Aero entry levels | First line |
| ---: | --- | --- |
| 1 | `[1,0,0,0]` | `(2601,1)` |
| 8 | `[2,2,2,2]` | `(2601,2)` |
| 17 | `[5,5,5,2]` | `(2601,5)` |

These are **suffix entry levels**, distinct from core family keys `(9318,4/5)` and any owned-roll rank. `BUFF_LEVEL_MAP` has exact key `582601000 → maximum level 5`. The `buff_level_data` map has precisely five composite keys `(582601000,1..5)`; entry-level 6 exists in `mod_entry_data`, but the decoded current total-level table never yields 6 for this first line. Do not relabel these entry levels as the core rank.

## Exact configured tooltip and parameter rows

Each `(2601,level)` entry has `buff_id=582601000`. The native buff description for all five levels is `枪械伤害#7#+{1}%#7#，空中命中额外#7#+{2}%#7#`; the installed English TID maps it to **“Weapon DMG +{1}%, additional +{2}% for aerial hits”** (formatting markers `#7#` omitted here). The `buff_level_data.desc_value` array holds the displayed pair; its separate `params` map holds the matching decimal values:

| Entry/buff level | Weapon DMG text | Additional aerial text | `params[1]` | `params[2]` |
| ---: | ---: | ---: | ---: | ---: |
| 1 | +1.2% | +0.6% | 0.012 | 0.006 |
| 2 | +2.4% | +1.2% | 0.024 | 0.012 |
| 3 | +3.6% | +1.8% | 0.036 | 0.018 |
| 4 | +4.8% | +2.4% | 0.048 | 0.024 |
| 5 | +6% | +3% | 0.06 | 0.03 |

Thus the **catalog configuration for total level 8** selects `(2601,2)` and sources **Weapon DMG +2.4%, additional +1.2% for aerial hits**. This is a tooltip/configuration vector, not a claim that Maurice owns that roll or that a particular hit receives 2.4% or 3.6%. The source `desc_value` values and decimal `params` are separate native fields; the matching 100× relation is verified for all five rows. Source: `buff_level_data.pyc` archive index `84932`, copied pyc SHA-256 `fb0d46a975c0c25ef9abeda96d5b625b5de741d92cf8a3e4b49e74740a08f525`, literal SHA-256 `5667f98f77fd46bb9b9a68679ea5284d573aedfcf332fd09bde0374c54b02633`, 3,897 composite indexed keys. The map and each selected row's byte offsets are in the ledger.

## Configured property and conditions

The exact buff's graph `buff_582601000_1` has two `NodeChangeAttrInputValue` records, node `31` and node `20`. Both typed `attribute` fields resolve to `attack_type_dam_add_rate_remote` (`E42`), with `need_disable=0`, `value_type=1`, and a separately stored default `in_data_args.value=0.0`. The `NodeBuffNone` entry node `32` has serialized control links to node `31` and checker `23`; checker `23` has a `trigger` link to node `20`. Two `NodeConstFloat` nodes, `24` and `21`, have default `value=0.0`; the graph's dynamic-parameter map names node `24` → `effect_params.params.value[0]` and node `21` → `effect_params.params.value[1]`. These are exact serialized paths and edges; runtime wiring of `params[1/2]` to a particular change node is still unproven.

Checker `23` contains six `state_checker` configurations with `in_state=1`, `role=0` and event names `on_state_change::<code>`. Installed `StateType` constants bind those codes to `FALLING (40)`, `JUMPING (2)`, `GLIDE (83)`, `BEHAVE_MOVING (110)`, `FLOAT (111)`, and `UPDRAFT (95)`. The graph's `trigger_op=0`, `reset_op=1`, `auto_reset_trigger=1`, and `cd=0.0` are serialized values; the checker combination, event dispatch, and whether a state causes the extra aerial value were not reconstructed from an authoritative executor. The five selected buff-level rows do not set either optional `life_time` field, so no duration is assigned here.

## Integration limit

The client provides a complete source-backed **catalog line and total-level preview** for this first Aero bonus. The static graph establishes `E42` as the affected property and lists the candidate state conditions. Applying either decimal parameter to live combat requires the missing graph executor/value-binding semantics and the actual active instance context. This packet does not infer permanent uptime, aerial predicate logic, or an observed hit result.

The stale pointer-as-entry claims in `MOD_2400001_NATIVE_JOIN.md`, `MOD_2400001_FIVE_TABLE_PACKET.md`, `PRECISION_CHARGE_AERO_NATIVE_ACTIVATION_BOUNDARY.md`, and `precision_charge_aero_identity_trace.json` have been corrected or marked. The acquisition packet `native_mod_entry_source_records.json` remains read-only and quarantined: its `entry_id` field is a key pointer, not a scalar entry identity.
