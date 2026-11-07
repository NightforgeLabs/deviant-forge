# Native DOT modifier buckets, build 26267212

Static copied-source inspection only. [`trace_dot_modifier_buckets.py`](trace_dot_modifier_buckets.py) rechecks pinned hashes, typed native rows and graph nodes; it writes [`dot_modifier_bucket_trace.json`](dot_modifier_bucket_trace.json). It passes locally. No extracted game code was imported or executed, and no installed game or Forge file was changed.

## One configured AUG event and its graph

The AUG's two typed durative attack nodes 129 and 215 configure `formula_attack_type=4`, `element_type=3`, `keyword=302`, `is_buff_damage=1`, `is_keyword_damage=0`, and both final damage/ignore switches at 1. The copied `FormulaAttackType` enum gives `Dot=4`. The `CompBeHitCommon._calc_damage` path calls the same `CompDamageFormula.calc_damage` graph for a durative event, and skips automatic weak-part marking when type is Dot. The node executor that constructs the actual event/hit leaves is absent from the readable copy, so this is a **configured graph path**, not a certified actual proc or tick schedule. See `AUG_DOT_HIT_DOWNSTREAM_AND_EXECUTOR_BOUNDARY.md` for the exact call/offset ledger.

Graph version 13 selects `attack_is_buff=1` for type 4 (nodes 2, 168, 170, 182). Node 301 multiplies these factors, among others:

| Graph factor | Native expression | Separate typed property candidate |
| --- | --- | --- |
| DOT attack type | `final_skill_rate = 1 + BB.bound_attack_type_dam_add_rate` (139–142) | `E43` = `attack_type_dam_add_rate_dot`, parent `attack_type_dam_add_rate` |
| Keyword | `1 + is_keyword_type × BB.keyword_proc_dam_add_rate + final_tag_melee_dam_add_rate` (247–250) | `E121` = `keyword_proc_dam_add_rate_surge`, parent `keyword_proc_dam_add_rate` |
| Element | `max(1 + BB.bound_element_type_dam_add_rate, 0)` (24, 53, 86, 113) | `E34` = `element_type_dam_add_rate_lightning`, parent `element_type_dam_add_rate` |
| Generic final damage | `1 + final_dam_add_rate` (286–287) | `E98` = `final_dam_add_rate` |
| Target reduction | Multiplicative factors in node 308, including `1 − BB.element_type_ignore_dam_rate` (131, 144), `1 − BB.element_type_ignore_dam` (123–124), and `1 − BB.attack_type_ignore_dam_rate` (128, 146–147) | Native property map has `G44` = `element_type_ignore_dam_rate_lightning`, `G104` = `element_type_ignore_dam_lightning`, and `G53` = `attack_type_ignore_dam_rate_dot`; actual attacker/target scope still needs binding. |

`CompFormulaAdapter.get_bound_attack_type_dam_add_rate` (body `[73950,74368)`) explicitly reads `attack_type_dam_add_rate` and `formula_attack_type`, and calls `FormulaManagerHelper.get_attack_type_attr_name_by_tag`. The element counterpart (`[72968,73400)`) reads `element_type` and calls `get_element_attr_name_by_tag`; the keyword counterpart (`[71731,71911)`) reads `keyword_type` and calls `get_keyword_attr_name_by_tag`. `FormulaManagerHelper.pre_load_cache_data_dict` builds those name maps from `char_property_data.extra_info`, `element_type_data`, and `keyword_tag_data`. The exact tag-3→lightning and keyword-302→Surge table rows are not yet decoded here. The AUG skill graph separately contains the literal `element_type_dam_add_rate_lightning`, but literal membership alone does not close the name-map join.

## Affix and accumulation evidence

The native `attr_id_index_attr_name` map explicitly assigns the IDs above. Independently decoded `affix_prototype_data` rows `E4300` `[51106,51142)`, `E3400` `[50926,50962)`, and `E12100` `[50602,50638)` target `E43`, `E34`, and `E121` respectively. Each has effect range 1 / type 1, which is `AP_EFFECT_ALL` / `AP_CALC_TYPE_ABS` in `attr_const`. The corresponding `char_property_data` rows are `[72198,72241)`, `[83462,83505)`, `[105721,105765)`; each has `calc_type=0`, `init_val=0`, `val_type=2`, and a typed parent key matching the table above. The native prototype `affix_name` fields are localization pointers; this packet does not equate them with a verified English display string. The property names provide the safe semantic labels DOT damage, lightning element damage, and Surge keyword proc damage.

`AffixUtils.add_effect_all_ability_change` sums active type-1 values into one absolute change for the property. The ordinary property formula adds that sum to the initial value before its rate factor. Thus two **supplied active** `E43` modifiers of `+0.10` and `+0.20` produce one DOT property value `0.30`, not a product `1.10 × 1.20`. If the graph adapter binds that property as the Dot factor and all other factors are 1, supplied attack 100 gives `100 × (1 + 0.10 + 0.20) = 130` before rounding. The `132` from multiplying those same-bucket bonuses is contrary to the native accumulator structure. This is a synthetic conditional vector, not an owned AUG build or observed proc damage. Distinct **confirmed** buckets multiply at node 301 after their own accumulation.

## Boundaries for DV

- `keyword=302` in the effect config is not by itself proof that graph leaf `keyword_type` is nonzero. The same node config has `is_keyword_damage=0`; do not grant `E121` to an AUG DOT event until the executor's leaf assignment or a readable caller establishes it.
- The `element_type=3` typed value and the graph's lightning string do not yet prove the exact element tag table lookup. Keep `E34` conditional until `element_type_data` binds code 3.
- The copied files do not prove that an item's selected calibration print, mod or affix is active on a specific player. Native affix IDs and property grouping are source facts; activation is instance state.
- The graph's target mitigation is several separate factors. `G44`, `G104`, and `G53` native names alone do not establish the actual enemy's resistance values or all target/attacker ownership. No flat generic enemy resistance can be inserted.
- The missing NodeDurativeAttack executor prevents a proc frequency, event timing, complete status damage or full DPS claim. This packet does not retry that absent branch.
