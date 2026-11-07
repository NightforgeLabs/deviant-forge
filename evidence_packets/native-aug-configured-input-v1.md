# AUG Electron Cloud: connected graph inputs

All reads were offline from copied bytes of installed build `26267212`. The source archive hash is `8007b2e16b71d10ac1e0b215f12a4bd68387c22b304e031c60f9a00b0c3c876a`. No extracted game code was imported or executed and no installed file, process, server, or window was touched.

## Identity and execution edge

The native blueprint `13451401` has fixed skill `WS15704`. Its passive record names buff `354509000` and keyword buff `110300000` (`native_aug_fixed_skill_source.json`). The port ledger (`native_aug_graph_port_ledger.json`, independently controlled in `AUG_GRAPH_PORT_FORMAT.md`) resolves 47 control/data nodes in the first graph and 75 in the second. The exact graph literal SHA-256 values are `ce57cbbcebda71a5d35036b42300d822e6c2ca3c54e3dfd6c89a2b62f17f3ecb` and `41802f01bb9d66d2698ccc44a7b861227f4ef523dafeb2d9a77aad2e059973dc`.

## Attack event → probability inputs (`buff_354509000_1`)

The entry node 0 arms attack event node 1. Its `trigger` control edge reaches node 53 (`NodeBuffIfTask`), whose `Condition` comes from node 52 (`NodeCheckInPinballArea`). The `False` branch reaches probability node 17, whose success output casts buff to the victim through node 15. The `True` branch reaches probability node 13, whose success output reaches snapshot node 93, pinball node 57, and victim buff cast node 8. This is a serialized route; its condition implementation and success likelihood remain unverified.

Both probability nodes receive an `input_rate` from an `ADD` node: node 13 ← node 10; node 17 ← node 18. The ADD nodes' unlinked `data1` is a typed in-data constant `1.0` at literal `[6830,6837)`, and each `data2` is linked to a `NodeGetFloatAttr` output (`10 ← 12`, `18 ← 14`). Both readers name holder attribute `keyword_proc_chance_add_rate_surge` at 100% (attribute-reader source records `[7032,7044)` and `[7160,7172)`). Thus the connected input is:

```text
input_rate_13 = 1.0 + holder.keyword_proc_chance_add_rate_surge
input_rate_17 = 1.0 + holder.keyword_proc_chance_add_rate_surge
```

This establishes the value presented to each chance node, **not** a final 30% or other success probability. The descriptor and optional-field bitmap now prove both records configure separate `probability=30.0`, `input_factor=30.0`, `speed_factor=0.8`, `use_input=true`, and `use_expect_rate=true` fields; exact byte offsets are in `AUG_TYPED_CONFIG_AUDIT.md`. The connected `input_rate` is a port, not another configured scalar. The copied `NodeServer` lacks the chance evaluator, so the interaction of these fields cannot be reduced to a certified final chance. The separate successful-reload event node 74 directly reaches cast node 83, not either chance node.

## Durative damage inputs (`buff_110300000_1`)

The following source-bound names are typed reader or BB-key values, rather than inferred from neighboring strings. Target reader nodes 139 and 188 read `skill_power` at 100%; nodes 144 and 174 read `skill_dam_base_dam_surge` at 100%; nodes 202 and 206 read `keyword_proc_time_surge` at 100%. Local blackboard load nodes 135 and 169 use `dam_up`, while 141 and 182 use `pvp_ratio`. The reader `NodeGetTargetFloatAttr` implementation is readable for `NodeMainClient`; the copied `NodeServer` uses an unimplemented base method, so the authoritative server calculation remains a boundary.

The exact `NodeBBFloatCalculation` operation codes resolve through `logic_state_const.CalculateOpType`: `0=ADD`, `1=MUL`, `2=SUB`, `3=DIV`; `logic_tree_utility.numeral_calculation` implements these at pyc bytes `[45038,45280)`. The node handler `NodeBBFloatCalculation.NodeMainClient._do` calls that function with its two input values and configured operation at pyc bytes `[1111,1347)`. On the first damage branch:

```text
node142 = dam_up + 1.0                       # 135 + typed constant [5683,5693)
node143 = skill_power * skill_dam_base_dam_surge  # 139 * 144
node137 = node143 * node142
node140 = node137 * pvp_ratio                # 141
node129.attack_value = node140
node129.damage_times = floor(keyword_proc_time_surge)  # 204 ← 202
node129.damage_gap = 0.0                     # typed in-data constant, value [5370,5374)
```

The exact controlling route is entry 25 → checker 160 → checker 210 `False` → durative attack 129. Other control checks branch at 160; passing them is not assumed. `damage_gap=0.0` is the configured input, **not** proof of a zero-second runtime tick interval.

For the second branch, node 212 is a `NodeGetTargetBBFloatData` reader connected to the caster and holder. Its source record `[6179,6203)` contains native buff ID `354701200` and string key `"354701200"`; its handler sums matching target-buff blackboard float values, so call its output `G` rather than assuming a duration unit. `logic_tree_utility.numeral_calculation` returns zero on division when the divisor's magnitude is below `MIN_STEP`.

```text
node175 = skill_power * skill_dam_base_dam_surge  # 188 * 174
node179 = dam_up + 1.0                       # 169 + typed constant 1.0
node178 = node175 * node179
node172 = node178 * pvp_ratio                # 182
node190 = safe_divide(3.0, G)                # typed constant [3736,3746), op 3
node208 = keyword_proc_time_surge * node190 # 206 * 190
node192 = floor(node208)
node211.damage_times = node192
node211.damage_gap = G                       # 212
node215.attack_value = node172
node215.damage_times/gap = node211.reuse_invalid.damage_times/gap
```

The control route here is checker 210 `True` → `NodeDurativeAttackCheckTask` 211 → its `reuse_invalid` output → durative attack 215. This is a reuse check path. The node editor describes refresh/reuse behavior, but its server executor is not readable here. Treat the formulas as **configured attack-value/count/gap inputs**, not proof that `floor(keyword_proc_time_surge × 3/G)` damage packets happen, nor proof of their timing or target mitigation.

The two connected attack-value branches share the configured arithmetic `skill_power × skill_dam_base_dam_surge × (1 + dam_up) × pvp_ratio`, but the actual values and conditions at a player's hit are not in these graph literals. The `NodeDurativeAttack` copied server class contains no readable evaluator, and no exact node evaluator binding emerged from the named installed extension inventory or bounded executable metadata/string check. The game's authoritative hit settlement and status packet count are therefore unresolved.

## Original-byte and method controls

- `NodeBBFloatCalculation.pyc`: SHA-256 `93bd7593698a2815195b443e7c3c2508de3f76a057fa5940c9d38e1125787da1`.
- `logic_tree_utility.pyc`: copied archive index 42943; `numeral_calculation` line 864, pyc `[45038,45280)`.
- `logic_state_const.pyc`: copied archive index 78239; `CalculateOpType` line 303, pyc `[9504,9534)`.
- `NodeMathFloor.pyc`: SHA-256 `ad399f26f992720b9cc0af1377ef163795e84ccb4fe4c9b1f87742559ba8615a`; `NodeMainClient._do` `[845,1033)` uses `int(math.floor(data))`.
- `NodeBBLoadFloatData.pyc`: SHA-256 `35702a2ac2fb42a82abb76770ba2226b4635e2b12adbb130ed1f1f0e84e2f270`; `_do` `[1071,1625)` gets the named float from the tree blackboard, defaulting to zero when the key has no value.
- `NodeGetTargetBBFloatData.pyc`: SHA-256 `10c01d20fb857ec15be2e26b51c57371c8a19ee89123d0ab60589711cb65f1dd`; `_do` `[1585,2465)` sums the named target-buff blackboard float.
- `capture_aug_arithmetic_nodes.py` and its manifest preserve archive indices, offsets, compressed and copied hashes. `inspect_aug_arithmetic_static.py` reads the copied pyc as data only.

The copied reader/module names do not themselves certify server execution. The parent Forge writer should treat this packet as a source-backed configured-input model with an explicit authoritative-executor boundary.
