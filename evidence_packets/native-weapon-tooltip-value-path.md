# Native weapon tooltip value path: inventory versus blueprint preview

This is a static, offline trace of installed build `26267212`. The source is the copied `script.npk` (SHA-256 `8007b2e16b71d10ac1e0b215f12a4bd68387c22b304e031c60f9a00b0c3c876a`). Captures and original-byte hashes are in `weapon_tooltip_caller_captures/manifest.json`, `item_data_tools_capture/manifest.json`, `common_tips_ui_capture/manifest.json`, and the earlier `attack_consumer_captures/manifest.json`. No game code was executed; no installed files, process, server, or game window were touched.

## Ordinary inventory tooltip

`ui/PanelWeaponTipsPC.pyc` `PanelWeaponTipsBase.init_data` (line 45, pyc `[1888,2018)`) calls `ItemDataTools.get_gun_info(item_id,item_no,item_detail)`. The ordinary parts tooltip has the same call. `ItemDataTools.get_gun_info` (line 4196, `[224749,224805)`) creates a `LazyDict` with `VM_GUN_FORMULAS`, so each requested UI field follows that map. `PanelWeaponTipsBase.init_part_data_list` (`[2225,5017)`) assigns `item_base_attr_data` to the `base_attr` part. `CommonTipsUI.TipsEquipBaseAbilityBase.update_info` (line 2285, `[142820,143090)`) reads that `base_attr` list into the visible stat rows.

The `VM_GUN_FORMULAS` byte range `[8874,11702)` binds:

```text
item_attack_base      = get_gun_attack_base(item_no, item_star, item_detail)
base_affix_add        = get_gun_base_affix_add(item_attack_base, blueprint_affix_add,
                                              item_no, item_detail)
rand_affix_add        = get_gun_rand_attr_affix_add(item_detail)
correct_affix_add     = get_gun_correct_affix_add(item_detail)
all_affix_add         = get_gun_affix_add(item_no, base_affix_add,
                                         accessory_affix_add, rand_affix_add,
                                         affix_option_add, ..., correct_affix_add)
no_rand_affix_add     = get_gun_no_rand_affix_add(item_no, base_affix_add,
                                                 accessory_affix_add,
                                                 affix_option_add, correct_affix_add)
item_base_attr_list_all = get_gun_base_attr_list(item_no, all_affix_add)
item_base_attr_data   = calc_gun_attr_data(item_base_attr_list_all, bullet_num)
```

`GunCoreHelper.get_gun_base_attr_list` (line 995, `[38754,39118)`) starts its list with `D0100` (Attack), then native RPM and magazine affix IDs. `ItemDataTools.get_gun_base_attr_list` (line 1984, `[107734,107900)`) applies the selected affix map to that list through `_calc_gun_attr_list` (`[106657,106853)`). `calc_gun_attr_data` (line 2084, `[111560,112538)`) formats the resulting rows, including a special `D0100` multi-bullet display. Thus the visible **base stat list** in the ordinary tooltip draws its Attack and RPM from `all_affix_add`, not the separate `item_attack`/`item_rpm` LazyDict keys.

The separate keys are easy to confuse: `item_attack = get_gun_attack(no_rand_affix_add)` and `item_rpm = get_gun_rpm_val(item_no,no_rand_affix_add)` at root bytes `[8926,8958)`. `get_gun_no_rand_affix_add` (line 1775, `[96276,96320)`) delegates to `get_gun_affix_add` with an empty random-affix map but retains base, accessory, affix-option and correction maps. The ordinary visible `base_attr` route above instead uses `all_affix_add`, which includes the random map. This is an important input distinction for Forge.

`get_gun_attack_base` (line 1587, `[88237,88717)`) normally reads `gun_preset_attack` from the item's native origin data, then multiplies by the blueprint/star record's `preset_attack_radio`. A private custom weapon-detail override can supply an Attack affix directly. `get_gun_base_affix_add` (line 1693, `[93419,93941)`) puts that base Attack into `D0100` after blueprint `D0101`/`D0102` ratios, and also inserts native RPM/magazine affixes. `get_gun_affix_add` (line 1721, `[94561,95371)`) combines base, accessory, random, affix-option and correction maps; its `D0100` path applies `D0101`/`D0102` ratio deltas, and its `Q0800` RPM path uses the native shooting interval calculation with `Q0900` when no explicit RPM value is supplied. These are item tooltip contributions. The trace does not show global build-set/mod/food buffs being folded into those rows.

**Forge implication:** if a user copies the visible Attack or RPM base-stat line from an owned inventory weapon, label it an *equipped item tooltip value*. It already includes the item/blueprint star and the item-detail affix maps on this native UI path. Forge should not apply those same quality/star, calibration, accessory or item random contributions a second time. This is a dataflow conclusion from the copied client UI, not proof of the unseen authoritative server snapshot or of all possible game UI modes.

## Blueprint preview

`ui/PanelWeaponBluePrintTipsPC.pyc` `PanelWeaponBluePrintTipsBase.init_data` (line 35, `[1593,2147)`) calls `ItemDataTools.get_blueprint_info`. That method (line 4204, `[225162,225324)`) uses a separate `VM_BLUEPRINT_FORMULAS` map. The blueprint `init_part_data_list` (`[2630,4518)`) assigns its own `item_base_attr_data` to `base_attr` for the visible rows.

The blueprint map's `gun_item_data` key calls `get_gun_item_data(gun_item_no,item_star)` at root bytes `[15592,15608)`. `get_gun_item_data` (line 3032, `[150883,150923)`) calls `get_gun_info('',gun_item_no,{'star':item_star})`: a synthetic gun tooltip data object with a star input, not the player's `item_detail`. The blueprint map then takes `item_base_attr_data` from that nested `weapon_item_data` (`[15062,15078)`). Its `item_attack_base` separately uses `get_gun_attack_base(gun_item_no,item_star)` (`[15558,15576)`). This ties a blueprint preview's Attack/other base rows to the chosen star and native synthetic item data; no owned item's random rolls or correction detail were passed through this call.

**Forge implication:** mark a copied blueprint preview as a *blueprint preview*, not as an owned equipped Attack value. The preview still includes the native blueprint/star ratio and default weapon item parameters, so star scaling must not be applied again. A blueprint preview is not a reliable substitute for an owned weapon's actual calibration/random/accessory values.

## Bounded limits

This is one complete client display path from panel caller through formula map and formatted base-stat list. It does not prove the authoritative server's ordinary-player Attack assignment, all conditional combat buffs, or the exact player's tooltip numbers. The copied ordinary tooltip requires `item_detail`; the blueprint preview constructs a synthetic detail dictionary. A build calculator should keep those two input origins explicit. The source packet `native_weapon_tooltip_method_candidates.json` was used to select targets; the caller/dataflow conclusions here are based on the captured methods, not the packet's earlier inferred role labels.

## Per-attribute inclusion check

The visible ordinary inventory rows use `item_base_attr_data`, whose `D0100` and native RPM affix IDs are supplied by `GunCoreHelper.get_gun_base_attr_list` and updated from `all_affix_add`. The following applies to those **two displayed rows**; it is not a claim about every tooltip field:

| Contributor | Displayed Attack (`D0100`) | Displayed RPM (`Q0800` path) | Source boundary |
| --- | --- | --- | --- |
| Native weapon origin and blueprint star | Included: `gun_preset_attack × preset_attack_radio`, then blueprint `D0101`/`D0102` contribution | Native gun's shoot interval is the base for RPM | `get_gun_attack_base` `[88237,88717)`; `get_gun_base_affix_add` `[93419,93941)`; recovered `get_gun_shoot_interval` in `RECOVERED_NATIVE_BASE_INTERVAL.md` |
| Equipped accessories | Included when they supply `D0100` or Attack-ratio affixes | Included when they supply `Q0900` to the interval-derived RPM | `get_gun_accessory_list` `[132625,132997)` merges default slots with `item_detail.equipped_accessors`; `get_gun_accessory_affix_add` `[102535,103133)` gets their attributes |
| Weapon's random affix list | Included when it supplies Attack/ratio affixes | Included when it supplies `Q0900` | `get_gun_rand_attr_affix_add` `[122324,122530)` reads `item_detail.gun_affix_list` |
| Weapon correction/calibration affixes | Included when they supply Attack/ratio affixes | Included when they supply `Q0900` | `get_gun_correct_affix_add` `[122802,123358)` reads `item_detail.gun_correct_affix_list`; `get_gun_affix_option_add` `[124771,125179)` resolves `item_detail.affix_options` through `gun_calibration_affix_option_data` |
| Attached mod | No data link from `mod_id` or `mod_item_detail` into this `D0100` map | No data link into this `Q0800` map | The `VM_GUN_FORMULAS` mod fields at root `[11014,11136)` feed separate mod display; `all_affix_add` at `[10108,10144)` receives base/accessory/random/option/correction maps only |
| Wearer-wide armor, food, set and temporary buffs | No data link in this item tooltip producer | No data link in this item tooltip producer | The complete `D0100`/RPM dependency chain above takes item number/detail and native tables; it does not read a player holder's combat property snapshot |

`get_gun_affix_add` (`[94561,95371)`) merges the item maps and then **recomputes `Q0800`** with `shoot_utility.get_gun_shoot_attr_weapon_rpm(gun_no, merged_Q0900)` on this normal `cal_affix=None` path (`[95259,95367)`). The method reads `Q0900` from the merged map. Direct `Q0800` values in an earlier item map are overwritten by this final computation, so “accessory/random/calibration included in RPM” specifically means their `Q0900` contributions where present. This does not show that every accessory or roll affects RPM.

The attached mod appears in the ordinary tooltip as its own descriptive part; the lack of a mod-to-`D0100`/`Q0800` edge here does not imply mods have no combat effect. Likewise wearer-wide effects may change the player's effective combat properties elsewhere. Forge should retain them as separate modeled contributions if its input is copied from this visible **item tooltip** row. The blueprint-preview row uses a synthetic star-only `item_detail`, so none of an actual owned item's equipped accessories, random list or correction list is supplied through that call.
