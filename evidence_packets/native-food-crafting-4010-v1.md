# Food crafting and enhancement configuration, build 26267212

The full deterministic ledger is [food_combat_crafting_recipes.json](food_combat_crafting_recipes.json), reproduced by `python decode_food_crafting_recipes.py`. It has **77 typed forge configuration rows for all 33 combat relevant food IDs**: 15 foods have three rows, 14 have two, and four have one. These are installed configuration rows, not evidence that a recipe is currently unlocked, available in a season, or usable by this player.

## Sparkling Pumpkin Soup (`30110374`)

| Forge record byte | Configured materials for one Soup | Configured seconds | Station method IDs and installed English labels |
| --- | --- | ---: | --- |
| `480109` | `30102922` Deviated Mint ×1; `30102007` Pumpkin ×2; `30102011` Seaweed ×2; `933` ×3 (**name unbound**) | 5 | `52,514` Electric Stove; `609` Campfire Stove; `53,515` Kitchen Set |
| `1243417` | Same four material IDs and amounts | 5 | Same five methods, plus `71` Campsite |
| `1243554` | `30102007` Pumpkin ×1; `30102922` Deviated Mint ×1; `30100012` Purified Water ×1 | 20 | `53,515` Kitchen Set; `609` Campfire Stove |

The three records are preserved separately because the source has three distinct typed rows. `seconds` is the raw forge field; speed buffs and actual queuing are separate. ID `933` has no indexed `item_data` row in the copied build, so assigning it an ingredient name would be a guess.

`forge_data.pyc` SHA-256 `674a1e190668b7f5e445863ecfc1e1a33a587308772e727f5e9120c398b04d7e` supplies the 36-field schema with 26 optional fields, typed `cost_item_list`, `cost_num_list`, `forge_method`, `item_no`, `item_num`, and `seconds`. The decoder checked 2,549 valid records and quarantined 13,995 `0x96 0x67` byte occurrences that failed the schema/typed constraints. All 33 requested item IDs have a valid row. The source method `ForgeDataHelper.get_proc_method_by_formula_no` reads `forge_data[formula_no].forge_method`; `get_build_no_by_formula_nos` resolves those method IDs through `machine_way_data.build_no_lst`. `get_formula_cost_item_list` reads the typed cost list. `machine_way_data.pyc` SHA-256 `a3e970cce48ea68de08cfe85eb01d89d2e08b8cb87cf08e3b60a21b36a56311a` has a validated 57-key index; station labels are exact joins to the installed English translation map. The copied `ForgeDataHelper.pyc` SHA-256 is `c02abceb91016ed0a35a5550ad926d66cd32b8416a10c2787658de171cab584d`.

## Effect type `4010` sources

The separate [food_4010_ingredient_sources.json](food_4010_ingredient_sources.json), reproduced by `python decode_food_4010_sources.py`, identifies five distinct ingredient choice items in `diy_forge_choice_material_data` whose typed `effect_type_list` contains `4010` and whose parallel `effect_params_list` provides the following string value:

| Item ID | Installed English name | Configured `4010` value |
| ---: | --- | ---: |
| `30104008` | Butter | `0.3` |
| `30104009` | Cheese | `0.3` |
| `30104010` | Pickles | `-0.5` |
| `30104014` | Nut Jam | `0.4` |
| `30104906` | Stardust Cheese | `0.5` |

Each identity appears in six validated typed choice rows, with source offsets and encoded arrays in the JSON. The source pyc SHA-256 is `01f840abe8d2b9bda18b25086b5082a14dbf2b77c711bfc5d68529f567a2dd02`. `MemeMasteryHelper.get_all_meme_mastery_types` reads the choice table's parallel effect type/parameter lists for **selected** mastery entries. `cuisine_buff_utility.calc_item_meme_effect` can then add the first `4010` value to `effect_rate`, as documented in [SPARKLING_PUMPKIN_EFFECT_RATE.md](SPARKLING_PUMPKIN_EFFECT_RATE.md).

None of these five ingredient IDs is in the three decoded Soup cost lists. Their configured `4010` values do **not** establish a Soup enhancement or a selected player recipe. The separate `pal_effect_dct` route and recipe/quality selection remain unobserved. The item-use handoff to the buff constructor is still absent from readable copied code. Current unlock, acquisition location, inventory, and in-game availability are unknown.

All decoding used copied static bytes and existing trusted parsers. No extracted game code ran and no installed game or Forge file was changed.
