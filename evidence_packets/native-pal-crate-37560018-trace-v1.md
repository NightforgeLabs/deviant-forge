# Random Pal Deviation crate: configured source trace

Installed build: `26267212`. This is an offline, read-only trace of item `37560018`, not a runtime opening test.

## Exact configured chain

1. `item_data` indexed row `[9643567, 9643690)` binds item `37560018` to the installed English name **Random Pal Deviation** and native icon token `icon_summer_2_lv4_new.png`. Its installed English description says a Cattiva, Chillet, or Chillet Ignis with Skill and Activity Rating 3–5 may be obtained, a max-level one is guaranteed within up to 15 attempts, and guaranteed pulls do not repeat. The wording is item text, not proof of the draw implementation.
2. The item's typed `item_use_para_data.related_func` token at byte `122759`, indexed row `[122747,122763)`, is `junxuxiang_open`. The item-use `CmdClient._do` references `CompType.USE_ITEM.process_cmd_use_item`; client `CompUseItem.use_item_start_effect` and `.use_item_finish_effect` call `ClientAvatar.run_sel_item_type_func` with item identifiers. The exact branch for this crate is not established because the called method body is absent from the readable copied `ClientAvatar` module.
3. The typed crate config binds three nonempty normal pool IDs `37560018001`, `37560018002`, `37560018003` and rare pool `37560018004`. Six other normal slots point to a shared empty object. The typed `must_rare_reward_loot_times` value is `15`; `rare_back=0` and `rare_loop=1` are recorded without inferring their runtime meanings.
4. The four bounded drop-pool records bind **21 distinct reward item IDs**. Every ID resolves to an indexed item row, exact installed English translation, source-text Skill/Activity rating, quantity token `1`, and `item_data.icon` token. Full IDs, byte offsets, raw weight thresholds, translation pair offsets and icon names are in [`pal_crate_37560018_crosswalk.json`](pal_crate_37560018_crosswalk.json).

| Pool role | Pool ID | Configured item variants | Installed English reward | Skill/Activity ratings | Native icon token |
|---|---:|---:|---|---|---|
| Normal | 37560018001 | 6 | Cattiva | 3/3, 3/4, 4/3, 4/4, 4/5, 5/4 | `icon_containments_cbt2_sco_pal02.png` |
| Normal | 37560018002 | 6 | Chillet Ignis | 3/3, 3/4, 4/3, 4/4, 4/5, 5/4 | `icon_containments_cbt2_sco_pal03_1.png` |
| Normal | 37560018003 | 6 | Chillet | 3/3, 3/4, 4/3, 4/4, 4/5, 5/4 | `icon_containments_cbt2_sco_pal03.png` |
| Rare | 37560018004 | 3 | Cattiva, Chillet, Chillet Ignis | 5/5 each | corresponding three icon tokens above |

The ratings come from item description text. The icons above are native asset *identifiers*, not verified rendered files. Pool thresholds and pool total-weight fields are raw configuration values, **not calculated probabilities**. The 16 keyed rare-weight adjustment records for this crate have step tokens `0…15` with raw `add_weight=0` and `normal_add_weight=0`; these do not establish zero odds.

## Open and pity implementation boundary

Static archive inspection of the exact client/server command and use-item components is recorded in [`crate_open_module_inventory.json`](crate_open_module_inventory.json). `CompUseItemServer.process_cmd_use_item` has a six-byte code body with no referenced names. The three `CmdServer` class bodies examined have no draw or pity names. The actual `ClientAvatar.run_sel_item_type_func` implementation is absent from the copied readable module. Thus the pool-selection call, weight interpretation, counter ownership/reset, rare-pool trigger, repeated-guarantee exclusion and reward grant are not proved. The item text and typed threshold agree on 15, but this does not justify a 15th-open algorithm or final odds. Installed archive presence also does not establish current event availability.

The native `choose_reward_data.choose_reward_list` packet is separate: **five indexed choose-reward lists** with 15 list entries, only eight first numeric tokens matching indexed item IDs. It supplies neither the four crate pool IDs above nor a proved use-item consumer. The “579 lists” label in the assignment does not match the held decoded packet; `579` appears elsewhere as a different row count. This crate is configured through `military_supply_crate_data` and `military_supply_crate_drop_data`, not the five choose-reward lists.

## Reproduction and source hashes

Run `python build_pal_crate_crosswalk.py` and `python inspect_crate_open_modules.py` in this folder. Both only parse exact copied or indexed bytes; neither imports or executes game modules. The crosswalk pins the item-data literal SHA-256 `bcb0eed8c4d9ca658179558ee4e6002b3f13b686c7839e09a9a7aa695eea8035` and installed English translation pyc SHA-256 `0bd9092f37c3fc4b3d771be76018cef66796e45ce7ca824dfb599a94a1117f95`. It also hashes the source named-crate packet and module inventory. No installed file or Forge code was changed.
