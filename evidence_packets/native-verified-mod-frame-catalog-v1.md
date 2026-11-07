# Verified V2 mod frame catalog coverage

Installed build `26267212`. Reproduce with `python build_verified_mod_frame_catalog.py`; output: `verified_mod_frame_catalog.json`. The builder reads copied static tables and source bodies. It never imports or executes extracted game code, and neither the installed game nor Forge was modified.

## What the join proves

`new_mod_property_data` supplies each exact `mod_code`, item number, Shiny flag and frame. The frame row supplies four ordered `sub_entry_item_no_array` values. The inspected `ModDataHelper.get_mod_v2_levels` body uses `new_mod_level_data` to turn an explicitly selected Field Guide total level 1–17 into four entry levels; `get_mod_fixed_sub_entries_data_lst_v2` looks up the corresponding composite `(entry_no, entry_level)` rows. The total level is a read only catalog input. The helper has no Shiny branch, so the ordinary and Shiny identities linked to one frame share these configured bonus lines. Shiny core effects and owned core ranks remain separate.

For a direct row, the entry gives an exact affix ID and configured fraction. `affix_prototype_data` gives the native attribute ID/property and installed English label. For a buff text row, the entry gives an exact buff ID, and `buff_level_data` gives the configured display tokens, English template and, when present, runtime parameters. All output rows retain original offsets and source hashes. The installed translation for entry `7405` says “all DMG Boost” where the native text and typed monster classes say damage to all monsters; the preview uses “Damage to all monsters” and retains the original translation for audit.

## Coverage

| Measure | Count |
| --- | ---: |
| Captured frames | 37 |
| Frames linked to current mod identities | 32 |
| Unlinked frames, all marked Abandoned | 5 |
| Exact mod identities | 1,662: 831 ordinary and 831 Shiny |
| Frame × total level previews | 544 = 32 × 17 |
| Ordered preview line positions | 2,176 |
| Configured lines | 1,984: 685 direct and 1,299 buff text |
| Locked positions | 192 |
| Missing or quarantined required line positions | 0 |
| Required distinct composite entry rows | 395: 150 direct and 245 buff text |
| Direct affix IDs / buff entry IDs | 30 / 49 |
| Buff level rows with / without configured runtime parameters | 215 / 30 |
| Buff IDs with / without separately verified graph attribute joins | 5 / 44 |

The five unlinked Abandoned frames are explicitly quarantined; no current identity is assigned to them by a name match. The 44 buff IDs without independently verified graph target attributes **still have complete configured catalog text and level values**. The missing graph join limits combat classification and activation claims, not display of their sourced lines. For the five known graph joins, the graph attributes remain a source link; the preview does not certify server activation. All other missing row and translation quarantine lists are empty.

## Three independently checked frames

All three have entry-level vector `[1,0,0,0]` at total level 1, `[2,2,2,2]` at 8, and `[5,5,5,2]` at 17. Zero means locked. Exact source identities and offsets are in the JSON.

| Frame | Level 8 configured lines in order |
| --- | --- |
| Aero `26` | Weapon DMG +2.4%, additional +1.2% for aerial hits; Crit DMG +6%, additional +3% for aerial hits; damage to all monsters +3%; Max HP +2.4%. |
| Survival `19` | Max HP +2.4%; receive 3.2% damage reduction for 3 seconds after taking damage, cooldown value 6; damage from monsters −3.2%; damage to all monsters +3%. |
| Shrapnel `1201` | Shrapnel DMG +2.4%; Shrapnel Crit DMG +10%; Shrapnel Weakspot DMG +6%; damage to all monsters +3%. |

Frame `0` General is another useful control: level 8 gives `DMG +2.4%`, `Magazine Capacity +4.8%`, `Reload Efficiency +3.6%`, and `Damage to all monsters +3%`. This is a **frame bonus preview**, not the Flame Resonance Weapon General core effect or the user's actual roll.

## Integration contract and limits

Use the exact identity's `frame` to select `frame_level_previews[frame_code,total_level]`. Render `ordered_lines` by `position`. `state=locked` means no configured entry at that level. `state=configured` supplies `text`, native IDs, configured value and source offsets; direct rows carry `native_attr_id`, while buff rows may have `attribute_status=graph_attribute_unverified`. Source rows remain available in `entry_rows`, `affix_prototypes` and `buff_level_rows`.

Do not infer a player's owned roll, owned total level, core effect rank, Shiny core effect, active server buff, combat multiplier, trigger probability or damage result from these rows. The client level helper is a configured catalog preview, not a proof of the game's owned item state. Source bytecode body hashes, literal hashes, record offsets, translation offsets and the explicit quarantine are recorded in the JSON.
