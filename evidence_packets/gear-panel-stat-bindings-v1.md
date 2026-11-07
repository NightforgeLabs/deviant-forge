# Gear screen stat bindings — static source trace

Scope: installed build `26267212`, copied `script.npk` Python objects only. The copies and archive offsets/hashes are in [gear_ui_capture/manifest.json](gear_ui_capture/manifest.json). No game code was loaded or executed and no installed file was changed. The observed `422`, `20`, `720`, `58`, `793`, `14402`, `0.0%`, and `5.4%` come from the parent's screenshot description; this trace does not read the live character.

## Actual Gear widgets

`ui/PanelEquipmentBag.pyc` `PanelEquipmentBagBase.init_main_panel` at copied pyc bytes `[40875,41137)` creates `MainWeaponPanel`. Its `_deferred_set_player_info` `[41448,41544)` calls that part's `set_player_info`. `ui/equip_part/EquipmentPartItem.pyc` `MainWeaponPanelBase.init_player_detail_info` `[46213,46295)` creates `CommonPlayerDetailInfo`; `MainWeaponPanelBase.init_player_score_info` `[52879,52987)` creates `PlayerScorePanel`. `PlayerScorePanelBase.fresh_data` `[19474,20972)` calls `self.data_model.get_player_weapon_armor_info()` and displays each returned `attr_value` in the six summary stat nodes. `CommonPlayerDetailInfoBase.refresh_detail_info` in `ui/common_ui/CommonPlayerBaseInfo.pyc` `[21612,22608)` calls `PlayerAttributeTools.get_player_info_attr()` for the expanded list.

### Summary row, including Primary Weapon Attack

`ui/data_model/UIEquipmentData.pyc` `get_player_weapon_armor_config` `[199444,199914)` reads `client_data/equipment_panel_attr_show_data` selected by season. The copied native config at index 3150 (`sha256:c042ef0dd27aa49e45d0bc471320ebae91eca42bcccc00702eec134deb3a8949`) contains weapon keys `attack`, `weapon_rpm`, `weapon_magazine_size`, then `skill_power` and `max_hp` among the other summary keys. `get_player_weapon_armor_info` `[200591,201451)` sends the weapon keys to `get_player_info_by_prop`, rounds to integer, and displays them. It reads armor/character summary keys including `skill_power` and `max_hp` directly from `Env.PLAYER_HOLDER` and rounds them.

`get_player_info_by_prop` `[139903,140795)` starts with the current holder values. It selects `main_hold_item_id` (or an explicit selected item) and compares it with `holder.hold_item_id`:

* If selected item equals held item, it retains `holder.attack`, `holder.weapon_magazine_size`, etc. For `weapon_rpm`, it specifically computes `holder.weapon_rpm * (1 + holder.weapon_rpm_add_rate)` at `[140243,140343)`. The method can force a zero current-held ID when holder attack is zero.
* If the selected weapon differs, it gets the held and selected weapon's `all_calc_affix_add`, passes both to `ItemDataTools.get_player_replace_affix_list`, and uses the returned preview properties for weapon summary rows. `get_player_replace_affix_list` in `ui/data_tools/ItemDataTools.pyc` `[31190,31890)` removes the held item's affixes and adds the selected item's affixes via the client property-formula preview component. That component's internal arithmetic is not present in this trace. The UI can also show dashes when no held item or a melee item makes RPM/magazine inapplicable.

`UIEquipmentData.get_hold_item_id_no` `[137545,138085)` chooses the actually held normal gun when present, otherwise the first equipped gun; `init_hold_item` `[138576,138686)` seeds `main_hold_item_id` from it. Thus “Primary Weapon Attack 422” is a weapon-context/current-or-preview **summary**. The summary may represent an equipped primary weapon while the avatar holder represents an unarmed, tool, melee, or other currently held context. It is not proven to be an item-only base attack, an affix bonus, or a damage total.

### Expanded Basic and Battle rows

The native `client_data/player_person_info_data.pyc` literal (index 38009, `sha256:8f1353dc9f4e52cfcac7ee38c62e12150b5eafd2a3d64642434c8aa32a4cb2b8`) has these checked type-11 attribute-array bindings (literal offsets are record starts):

| Row ID | Config | Attribute ID | Property name from `char_property_data` | Literal offset |
| --- | --- | --- | --- | ---: |
| 1 | `attack` | `D01` | `attack` | 11847 |
| 101 | `crit_rate` | `E01` | `crit_rate` | 12505 |
| 102 | `crit_dam_rate` | `E02` | `crit_dam_rate` | 12598 |
| 103 | `weak_dam_rate` | `E03` | `weak_dam_rate` | 12629 |

The ID-to-property names are independently indexed by `native_attr_id_index_attr_name.json` in the source acquisition workspace. `PlayerAttributeTools.get_player_info_attr` `[2649,3487)` walks the configured basic/battle categories and calls `get_player_attr_show_data` `[4401,5229)`. That helper resolves each ID through `AffixUtils.get_attr_name_by_attr_id`, then `calculate_attr_value` `[8116,8614)`. For these rows, the `equation` field is empty, so it reads the property through `get_attr` `[7501,7811)`, which takes `Env.PLAYER_HOLDER` and `AffixUtils.get_holder_property_attr`. The copied `OriAffixUtils.get_holder_property_attr` `[734,1438)` ultimately reads `getattr(holder, attr_name, default)` for an ordinary scalar unless a snapshot override or parent mapping applies. The `attack` name is not listed as a parent mapping in the copied `attr_const` construction; the source has `attack` as a scalar attribute. `get_player_attr_show_data` formats absolute attack with integer rounding; `format_value` `[1066,1416)` formats rate rows as `round(value*100, 1)` percent. Therefore expanded `Crit DMG 5.4%` represents a displayed `crit_dam_rate` of about `0.054` (rounded), not an inherent critical-hit multiplier or guaranteed actual crit outcome.

## Interpretation of the simultaneous screenshot values

The source verifies that the summary `422` and expanded `20` are rendered through **different paths**, but it does not expose the screenshot's live `main_hold_item_id`, `hold_item_id`, snapshot overrides, or update timing. The most concrete supported explanation is a different selected/equipped weapon versus currently held avatar context: the summary may be the client property-formula *replacement preview*, while the expanded row reads current `holder.attack`. This is a conditional explanation, not a proof of what caused these exact two numbers.

If selected item actually equals the held item, holder attack is nonzero, neither row is stale, and there is no snapshot override, these two identified code paths would both read the same `holder.attack`; `422` versus `20` would then need another panel/version/context explanation. Do not infer `422 = weapon base + 20`, or add `20` to `422` in Deviant Forge. Treat `422` as the displayed primary weapon-context Attack input and `20` as the displayed current-player Basic Attack observation until the context and inclusion are resolved. Likewise `720` is a weapon-context RPM (with an explicit additive-rate adjustment on the same-item branch), `58` is weapon-context magazine size, while summary `793` Psi/skill power and `14402` HP are current holder reads. Battle `0.0%` Crit Rate, `5.4%` Crit DMG, and `0.0%` Weakspot DMG are current-holder rate rows, subject to display rounding and conditional combat bonuses not shown in those rows.

The ordinary **item tooltip** path in `NATIVE_TOOLTIP_VALUE_PATH.md` is a third path and should not be equated with either Gear row. The client property-formula preview's internal aggregation and the authoritative server producer for `holder.attack` are still unverified. A live `hold_item_id`/selected-item comparison or a controlled Gear observation would settle which branch generated `422`, but this task does not access the game.
