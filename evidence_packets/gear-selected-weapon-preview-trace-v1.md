# Selected-weapon Gear preview: affix substitution and calculation

Read-only static trace for installed build `26267212`. Original archive entry offsets and copied pyc hashes are in [gear_ui_capture/manifest.json](gear_ui_capture/manifest.json); all cited byte spans below are within the copied pyc. The `ItemDataTools.pyc` copy is in `item_data_tools_capture/`. No extracted game code was loaded or executed and no installed game or Forge file was changed.

## Entry and branch

`UIEquipmentData.get_player_weapon_armor_info` (`ui/data_model/UIEquipmentData.pyc` `[200591,201451)`) obtains Gear's weapon summary through `get_player_info_by_prop` (`[139903,140795)`). The latter initially reads the requested keys from `Env.PLAYER_HOLDER`. It compares the selected `main_hold_item_id` or explicit `select_item_id` to `holder.hold_item_id`:

1. Same item: retains current holder `attack` and magazine size; it changes `weapon_rpm` to `holder.weapon_rpm × (1 + holder.weapon_rpm_add_rate)` at `[140243,140343)`.
2. Different item: obtains `all_calc_affix_add` for the current held item and selected item from `_get_weapon_item_data_by_item_id` (`[16684,16782)`, delegates to `ClientAvatar.get_weapon_item_data_by_item_id`), passes the two maps to `ItemDataTools.get_player_replace_affix_list`, and writes its returned properties into the weapon summary. If the live holder already supplies a nonzero property, that value takes precedence in one subbranch `[140639,140729)`; absent or zero values can take the replacement map. The actual item IDs and this subbranch's condition are unavailable from the screenshot.

## What the replacement function does

`ItemDataTools.get_player_replace_affix_list` (`ui/data_tools/ItemDataTools.pyc` `[31190,31890)`) performs a **client property preview**, not a direct addition of two visible Attack numbers:

* It builds a removal map from the held item's affixes by source type, negating their values. When the caller did not supply a held map but `holder.hold_item_no` exists, it asks `EquipHelper.get_affix_info` for the held item.
* It sums the selected item's affix IDs across its source-type maps. It then calls `PROPERTY_FORMULA_CLIENT.get_preview_ability_changes_client(holder, removal_map)`, followed by `get_preview_ability_infos_by_affix_infos(holder, selected_affix_sum, True, SOURCE_TYPE_GUN_CORE, changed_values)`.
* The selected affixes are submitted to that final call as `SOURCE_TYPE_GUN_CORE` even though the input `all_calc_affix_add` can contain both `SOURCE_TYPE_GUN_CORE` and `SOURCE_TYPE_EQUIP` entries. Thus source-type placement is observable in the code and should not be assumed to preserve every original channel after substitution.

`CompPropertyFormulaClient.get_preview_ability_changes_client` (`dcs_extend/component/CompPropertyFormula.pyc` `[28958,30356)`) groups removed affixes by init versus other source type, turns them into absolute/rate/independent/set changes, makes copies of the holder's four corresponding change dictionaries, and adds the removal deltas into the copies. It does not start from a bare weapon. `attr_const.INIT_SOURCE_TYPE_LIST` includes `SOURCE_TYPE_EQUIP` but not `SOURCE_TYPE_GUN_CORE` (copied `dcs_extend/const/attr_const.pyc` at `[11400,11418)`).

`CompPropertyFormulaClient.get_preview_ability_infos_by_affix_infos` (`[25190,26888)`) converts selected affixes into the same four channels, reads the modified holder change dictionaries, recomputes affected attributes with `_calc_attr_by_base_formula`, then calls `_adjust_attr_val`. `_calc_attr_by_base_formula` (`[7096,7200)`) uses a set override if present, otherwise an independent-rate path if present, otherwise `(init + absolute) × (1 + rate)`. `_calc_attr_init_val` (`[6794,6868)`) similarly applies init rates; `_calc_by_rate_addition_type` selects add/multiply behavior from the native attribute config. `AffixUtils.adjust_attr_val` (`dcs_extend/common/affix/AffixUtils.pyc` `[30004,30500)`) clamps to native min/max, rounds to six decimal places, and for absolute-valued attributes returns `int(round(value))`. The native `attack`/`D01` row has `init_val=0`, `min_val=0`, `max_val=130000`, `val_type=1` (absolute) in `native_attack_affix_typed_inputs.json`. Finally `UIEquipmentData.get_player_weapon_armor_info` calls `int(round(...))` before display.

## Selected item's affix map: known construction, incomplete caller binding

The copied `ItemDataTools` `VM_GUN_FORMULAS` data flow has an `all_calc_affix_add` key (root `[10310,10342)`) built by `get_gun_calc_affix_add(gun_no, base_affix_add, accessory_calc_affix_add, rand_affix_add, affix_option_add, correct_affix_add)`. `get_gun_calc_accessory_affix_add` (`[103879,104457)`) collects equipped accessory attributes and sight scope ratio. `get_gun_calc_affix_add` (`[96953,98575)`) routes:

| Input | Native source bucket in constructed map |
| --- | --- |
| Base gun affixes, except `Q0800`/`Q1100` | `SOURCE_TYPE_GUN_CORE` |
| Base `Q0800`/`Q1100` | `SOURCE_TYPE_EQUIP` |
| Accessory `D0101`/`D0102` attack ratios | `SOURCE_TYPE_GUN_CORE` |
| Other accessory affixes | `SOURCE_TYPE_EQUIP` |
| Random roll, affix option, correction/calibration | `SOURCE_TYPE_GUN_CORE` |

The function starts `attack_radio=1.0`, adds random `D0101`/`D0102` values into it, and adjusts the mapped `D0100` base attack using that ratio. The copied tooltip investigation in `NATIVE_TOOLTIP_VALUE_PATH.md` traces the underlying base, star, accessory, random, option and correction inputs. The `all_calc_affix_add` constructor itself has **no attached-mod argument**. This does not prove that wearer-wide or attached-mod effects are absent from the *holder's existing* change dictionaries, which the preview copies.

The exact `ClientAvatar.get_weapon_item_data_by_item_id` implementation is **not** a method body in the copied `entities/ClientAvatar.pyc` or its `AvatarEntityBase` module, despite the direct call in `UIEquipmentData`. Therefore this packet verifies the `all_calc_affix_add` constructor and the preview consumer, but cannot prove that a particular live selected item returned precisely that LazyDict field or which item detail was cached at screenshot time. The eventual server assignment of current `holder.attack` also remains outside the readable client path.

## Consequence for the visible `422` and `20`

Expanded Basic Attack is configured as `D01 → attack` and reads current `holder.attack` through `PlayerAttributeTools`; it is a **current holder property**, not certified base attack or a free-standing +20 bonus. Gear Primary Weapon Attack can be a replacement preview of a selected primary weapon. The copied preview begins with holder changes, removes old weapon contributions, adds selected contributions, applies absolute/rate/set logic, clamps and rounds. It is therefore invalid to compute `422 + 20` or infer a selected weapon's native `D0100` as `402` merely from those two displayed numbers. A numerical vector for this character would require the actual selected/held IDs and affix maps plus the holder's change dictionaries. Those are not in the supplied observations; no screenshot-fitted vector is asserted.
