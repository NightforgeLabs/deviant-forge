# Battle heal secondary: configured input chain

Installed build `26267212`. Exact primary frame entry `1902` uses buff `581902000`, which casts secondary `581902100`. The secondary's 14-node, 38-field parameter schema is now typed in [`heal_secondary_mixed_schema.json`](heal_secondary_mixed_schema.json), reproduced by `python trace_heal_secondary_mixed_schema.py`. The source pyc SHA-256 is `f354778f4e4ca6eac762e8e7b307c2f71da1a00b1d2895cc2636ef1c19c4afd3`; the typed packet SHA-256 is `88ce92c3614f97eed4e99d88b8f9d292b6a9eaede15a46c292b8b71c8200e345`. No extracted game code was executed; neither game nor Forge files were changed.

## Format correction

The secondary parameter schema is at literal byte `1903` with 38 fields and 37 optional fields. Marker `0x96` stores the optional bitmap inline. Marker `0xd6` stores a backward reference to a bitmap, which the earlier small-record reader mistook for inline values. The new parser validates each marker, schema descriptor, optional mask, typed fields, backward pointers and record end against the next wrapper. It decodes all 14 node parameter records. This is a parser-format correction, not a reconstructed game executable.

## Exact configured path

| Source | Bound value or edge |
| --- | --- |
| Primary `581902000` buff level table | Entry levels 1–5 configure `params[1] = .024, .048, .072, .096, .12`, displayed as 2.4–12% HP recovery. |
| Primary node 4 → node 1 | `NodeConstFloat.value ← params[1]` has a typed data edge into `NodeBBSaveFloatData.data`. Node 1 names blackboard key `suck_it`. |
| Primary node 2 | Configured cast target is exact secondary buff `581902100`, level 1, `mapping_buff=0`. Save and cast are sibling control edges; their execution order is not established here. |
| Secondary node 10 → 7 → 9 | Two configured `change_buff_checker` rows watch the parent buff `581902000` on add and remove. Node 7 reads parent key `suck_it` with `get_data_type=1`; its data edge feeds node 9, which saves key `suck_it_all`. Runtime event delivery and active instance enumeration are not proved. |
| Secondary node 17 → 22 | `NodeGetFloatAttr(attr_name=max_hp, percent=100)` supplies node 22 `data1`. The readable attribute reader computes `holder.max_hp × 100/100` when available. |
| Secondary node 19 → 22 | `NodeBBLoadFloatData(bb_key=suck_it_all, scope=0)` supplies `data2`. Its readable helper returns the stored float or zero when missing. |
| Secondary node 22 → 25 | Node 22's operation code `1` is `MUL` in the copied `CalculateOpType`/`numeral_calculation` path. Its result feeds `NodeHeal.heal_value`. Node 26's `holder_uid` output feeds `NodeHeal.target_uid`. Node 25 configures `cure_add_rate=100`. |

Therefore, **conditional on an explicit stored fraction F and max HP H being available**, the graph configures the `NodeHeal` input as `H × F`. Synthetic examples: `H=1000, F=.024 → heal_value input 24`; `H=1000, F=.12 → heal_value input 120`. These are node input vectors, **not actual HP restored**. The `NodeHeal` module's readable `NodeServer` class has no `_do` override, and the copied `NormalNodeServerBase._do` raises `NotImplementedError` (source pyc SHA-256 `041d6b5077750e80976b58f7f60682de682d1ecb2d00d8efacdd518799ff841d`). The authoritative heal application, cap, modifiers and HP delta are not verified from this copy.

The secondary root has a `NodeKillEvent` control edge to `NodeHeal`. Its typed `check_args` record is at byte `2396`; `target_type` is an integer array `[0]`, `check_all_hit_same_one=1`, `multi_bullet_one_attack=1`, with the other raw filter fields in the JSON. The installed tooltip says “Defeating Metas,” but `[0]` has no proven target-class label in this trace. We cannot certify that predicate or its timing. A separate checker tests parent-buff absence and leads to dispel, while add/remove checkers lead to the `suck_it_all` refresh; the native task executor remains outside the proven path.

## Remaining boundaries across the 49 reviewed IDs

The full [`all_mod_buff_graph_review.json`](all_mod_buff_graph_review.json) still categorizes 46 IDs with direct or exact secondary attribute targets and three effect-only graphs. Target and catalog value coverage are complete, but the following links are still necessary for live calculator contributions:

1. **Activation and instance state:** the readable V2 client path gives frame and total-level previews, but the authoritative equipped-mod handler, actual active level/variant, and buff application path are not proved. No historical screenshot is a current owned state.
2. **Value propagation:** General `589720000`, Lunar Deviant Energy `582003000`, Aero Deviant Energy `582603000/582604000`, and the previously noted Lunar `582006000` have level parameters or literal defaults without a complete decoded data path into every change node. Their displayed values remain valid catalog values; automatic combat application is withheld.
3. **Conditional executors:** Resonance casts and stacks, Downstar elevation, Crescent shield, Mirror attack angle, Wild distance, Phantasmal switch/loop, and Fortress/Fast Gunner buff tags have typed graph configuration but not a complete validated server event/condition/value lifetime for an actual encounter. Their attribute IDs alone do not prove uptime or a numeric damage change.
4. **Effect settlement:** Mirror `582303000` and Wild `582403000` use damage-reduction nodes with no attribute target. Battle `581902000` now has a configured heal-value input, but `NodeHeal` HP mutation and the kill target filter remain unresolved. The final direct-hit/target-health path must not treat these as ordinary additive damage stats.

**Follow-up:** [`GENERAL_VALUE_AND_KILL_TARGET.md`](GENERAL_VALUE_AND_KILL_TARGET.md) checks both of those leads. General's change nodes have empty serialized input pins despite a separate level-bound float; the kill filter's `[0]` has no proved `TargetType` label or event producer. The copied `NodeHeal` base has now been checked and only raises `NotImplementedError`; repeating it or the missing V2 server equip-handler search without a new source lead would not establish activation. None of these gaps should be filled by matching an English tooltip name to a generic percentage.
