# AUG Power Surge: Dot-configured hit path and exact executor gap

This follows the installed copied build `26267212` from the AUG graph's `attack_value` port to every readable downstream method. [trace_aug_dot_hit_downstream.py](trace_aug_dot_hit_downstream.py) pins source hashes, byte offsets, typed node fields, enum values, class inheritance and a controlled two-stage vector; [aug_dot_hit_downstream_trace.json](aug_dot_hit_downstream_trace.json) retains the checks. Neither extracted code nor the game was run or modified.

## Configured category and graph input

The exact AUG fixed-skill join is blueprint `13451401` → `WS15704` → passive buff `354509000` and keyword buff `110300000`, with keyword status `302` (prior packet `native_aug_fixed_skill_source.json`). In `buff_110300000_1`, native nodes `129` and `215` receive their `attack_value` ports from arithmetic nodes `140` and `172` respectively. Both paths construct:

```text
configured_attack_value = skill_power × skill_dam_base_dam_surge
                          × (1 + dam_up) × pvp_ratio
```

The typed node records set `formula_attack_type=4`, `element_type=3`, `is_buff_damage=1`, `is_keyword_damage=0`, `keyword=302`, `use_final_dam_add_rate=1`, and `use_final_ignore_dam_rate=1` on both nodes. Copied `formula_const.FormulaAttackType` explicitly assigns **`Dot=4`**. The element code `3` is retained as a code here; this packet does not assert its localized label. The native default `skill_dam_base_dam_surge=0.5` and `D41/skill_power` default `0` are property-table values, not a current player's values. `dam_up` and `pvp_ratio` are conditional blackboard inputs, as traced in `AUG_PROPERTY_SOURCES_AND_SCOPE.md`.

## Readable downstream route

The server component's static class creation includes `IBeHitCalcDamageServer` as a base at `CompBeHitServer.pyc` offset `1292`. That class inherits `IBeHitCalcDamageCommonBase` from `CompBeHitCommon.pyc` offset `684`. This resolves the earlier apparent absence of `_calc_damage_hp_with_hit_info`: it is in the imported common mixin at `[19388,20276)`, not in `CompBeHitServer`'s own class body.

For a durative event with a target that passes its checks, `CompBeHitServer._deal_entity_durative_hit_event_imp` `[21488,24202)` calls the inherited `_calc_damage_hp_with_hit_info` and stores the result, or enters the reuse path. `_process_entity_durative_hit` `[27938,30298)` calls it again for due hits, then passes the result to `entity_be_hit` for the local target or `Cmd.TAKE_DAMAGE_WITH_RESULT` for a remote target. This method has an exact `keyword == 302` branch with `keyword_proc_time_surge`; it is a source-bound status identity check, not a proof of how often the AUG node emits events.

`IBeHitCalcDamageCommonBase._calc_damage_hp_with_hit_info` has a default `if_crit=False` in its class definition. For an accepted ordinary single hit, its `_calc_damage` `[21606,25082)` selects `CompDamageFormula.calc_damage`, not the separate forced-crit comparison function. `calc_damage` `[5211,5867)` uses the same native formula-version-13 **damage graph**, whose inputs and guards vary by attack type. `get_formula_damage_result` `[10894,11520)` returns zero for nonpositive final attack, otherwise `max(round(final_attack),1.0)`. The common wrapper then applies `IBeHitCommonBase._calc_damage_attenuation`: `max(0, damage × (1−attenuation_factor)^obstruct_nums)`. `entity_be_hit` and its target-specific health/shield branches are the later settlement steps; outgoing formula damage is not automatically HP loss.

The category matters. `_calc_damage` checks `formula_attack_type != FormulaAttackType.Dot` at `[22394,22422)` before setting a weak-body-part flag. For `Dot=4`, it **skips that automatic flag**, even when the target part is typed weak. In the formula graph, Dot maps to `attack_is_buff=1`; its `use_weak` is then `clamp(BB.attack_buff_use_weak,0,1)`. Thus a physical weak-part hit is not enough to grant the Dot weakspot branch; an explicit buff weak permission would be needed. Crit is also conditional: the graph's `use_crit` includes `attack_is_buff`, `keyword_type`, `attack_type_crit_enable`, `BB.keyword_proc_crit_enable`, and other guards. The copied node executor does not show which of those leaves this AUG event supplies, so **neither crit allowed nor crit forbidden is established for AUG**. The raw `element_type=3` and enabled final-damage/ignore flags likewise do not give numeric elemental or target multipliers without the corresponding active leaves.

## Controlled vector and its explicit bridge assumption

Supply `skill_power=100`, surge base coefficient `.5`, `dam_up=0`, `pvp_ratio=1`. The **configured input** is `100 × .5 × 1 × 1 = 50`. Separately supply a synthetic `hit_info` whose attacker `attack=50`, `formula_attack_type=Dot`, single damage amount, all other graph and target factors neutral, no outer final-attack-rate dictionary, no obstruction, an accepted unshielded normal player target at HP `100`, and the guard inputs from [CONTROLLED_PLAYER_HIT_REPLAY.md](CONTROLLED_PLAYER_HIT_REPLAY.md). The formula result is `max(round(50),1)=50`; attenuation leaves `50`; under those supplied target conditions the pure replay gives HP `100→50`.

The **bridge between those two stages is not recovered**. The copied `NodeDurativeAttack.NodeServer` defines only `need_reset`; inherited `NormalNodeServerBase._do` raises `NotImplementedError`. No readable method proves that this node writes its connected `attack_value=50` into `hit_info.attacker_infos.attack`, nor that its configured flags become the exact event fields. The vector is a conditional integration test for a proposed bridge, **not** a certified Power Surge proc result or live DPS. Actual trigger/scheduling, crit eligibility, target mitigation, active `D41`, player/monster guards and damage packet count remain unresolved.

## Sources

- `CompBeHitServer.pyc` SHA-256 `face8eca67ea51e5fb5aa53e60efe4b2e589b00db97b93095f98ac70d0a70799`.
- `CompBeHitCommon.pyc` SHA-256 `accfc688e30e341b8bc43f3113c7e1c929bcb9f2c1e9edc697d6f883e6ba48b2`.
- `CompDamageFormula.pyc` SHA-256 `6aa212978067cf11a1de412915f1904dc6d7da5365746d79c0d305b3773dc4df`.
- `formula_const.pyc` SHA-256 `db441046402c48186681a6cc2ef49a34e1009e6d91bcfd1e2728315b60e098a1`.
- `damage_formula.pyc` SHA-256 `244bf28269e6b46ae9fafc164c14f33e95822616775abaf64484224c119117ee`; graph tuple bytes `[15637,28373)`.
- `NodeDurativeAttack.pyc` SHA-256 `0e04fa1d31d86caf025082b0d3ca059f5238f03715547ad159e838a8382218a8`; `LogicTreeNodeNormal.pyc` SHA-256 `041d6b5077750e80976b58f7f60682de682d1ecb2d00d8efacdd518799ff841d`.
- AUG graph/config source hashes and node field offsets are pinned in the machine packet, with the source workers' `native_aug_graph_port_ledger.json` and this task's `aug_typed_node_configs.json`.
