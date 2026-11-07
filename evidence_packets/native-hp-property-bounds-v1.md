# Named boss combat join: bounded negative result and native HP property rows

Static copied-source analysis only; no extracted game code was loaded or executed, and no installed game or Forge file was modified.

## Named encounter still stops before a combat unit

The existing [named rule packet](/home/dv/Documents/Codex/2026-11-02/task/native_named_boss_rule_links.json) binds encounter `40001101`, source name `天空之触_$S@TIDS$_cq9|0`, to creation rule `4001`. [Creation-member fields](/home/dv/Documents/Codex/2026-11-02/task/native_named_creation_member_fields.json) bind three tokens `400101`, `400102`, `400103` to typed rows. These include `monster_team_lst` paths such as `base|ai|51500101` and `base|ai|51500102`, plus facility references `0`, `830118`, `320141`, `320142`. The five named encounters reuse only six typed creation-member bodies; these references are group/spawn inputs, not proven combat-unit IDs. The [display packet](/home/dv/Documents/Codex/2026-11-02/task/native_named_boss_info_display_only.json) shows `boss_monster_info` as icon/localized-text pairs.

The prior [10,670-key review](/home/dv/Documents/Codex/2026-11-02/task/native_named_enemy_hp_join_review.json) found zero direct matches from the 12 unique creation-member tokens into `combat_property_inner_boss`. I resumed the interrupted exact archive filename check against build `26267212`'s 92,748-entry NXPK index. `51500101`, `51500102`, and `830118` occur in **zero filenames**. `320141` occurs only in `game_common/data/logic_tree/buff_532014100_1.pyc`; `400101` has three unrelated filename matches, including `battle_field/dun_data_400101.pyc`. These name matches do not establish a unit join. The 13 `source_battle`/`SourceBattle` filenames include the boss/creation data, UI, build templates, and only two `impSourceBattle` client modules; no same-named server spawn initializer appears in this archive. This is a bounded filename finding, not a proof that no differently named resolver exists.

The [client consumer review](/home/dv/Documents/Codex/2026-11-02/task/named_enemy_creation_consumer_boundary.json) found war-phase and whitelist calls but no selected creation-member→combat-unit/template resolver. `combat_property_data` exposes a `unit_no` field and separate inner boss/mob property tables, but the above named records do not provide that key or a validated map to it. Without that join, a named boss's `CompBeHitMonsterServer`/`CompHealthNpcServer` binding, base `max_hp`, active shield, level, and scenario/co-op scaling remain unknown. The same missing identity link prevents presenting a named ordinary enemy as a fully bound fallback from these records.

## Separate proven HP property input

The copied native `char_property_data.pyc` has a distinct 42-byte `hp` row (literal offsets `[78264,78306)`) and `max_hp` row (`[83585,83627)`). [decode_hp_native_bounds.py](decode_hp_native_bounds.py) verifies the copied pyc SHA-256 `74e5e434d0a34140822f5644c9116d93ff7b560c69f61a98b34b9fcd038ae967`, bounded index, source row headers, native attr IDs, field byte offsets and values. Its output is [native_hp_property_bounds.json](native_hp_property_bounds.json).

| Native property | Attribute ID | Stored `init_val` | Stored `min_val` | Stored `max_val` | `val_type` |
| --- | --- | ---: | ---: | ---: | ---: |
| `hp` | `A00` | 300 | 0 | 999,999,999 | 1 (`ATTR_VAL_ABS`) |
| `max_hp` | `A02` | 300 | 1 | 999,999,999 | 1 (`ATTR_VAL_ABS`) |

The HP rows use a float64 `max_val` field; the previously decoded `attack` row used float32 there. The shared property helper `AffixUtils.adjust_attr_val` reads these bounds, optionally substitutes a caller-supplied maximum attribute or entity-specific bounds, clamps, and rounds absolute values before `CompPropertyServer._set_attr` assigns the holder value. Thus the source backs a generic nonnegative HP floor and at-least-1 `max_hp` property floor. The stored `init_val=300` is a table value, **not** a named boss's HP or an observed live initialization. Whether `hp` is capped at a particular holder's `max_hp`, and which entity-specific property bounds apply, require the relevant mapping and instance state.

The next necessary boss evidence is an exact spawn initializer/registry that maps the creation-member team/facility token to a combat `unit_no` and component set, followed by the selected level/scenario/party profile. No base HP or boss DPS number should be attached to the five named display rows before that chain is proven.
