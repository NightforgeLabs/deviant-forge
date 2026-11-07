# Precision Charge `<Aero>`: native identity and Weapon DMG ambiguity

[`trace_precision_charge_aero_identity.py`](trace_precision_charge_aero_identity.py) rechecks pinned source packets, the installed English TID, one exact item/mod/frame path, and the two colliding Weapon DMG affixes. Its output is [`precision_charge_aero_identity_trace.json`](precision_charge_aero_identity_trace.json). This is configuration evidence for installed build 26267212, not an owned item profile or game observation. No game code was executed and no game or Forge file changed.

## Exact item and family identity

| Link | Native evidence |
| --- | --- |
| Item → mod | `new_mod_item_data` exact indexed item `19500811` → mod code `2400811`, mod-code token at literal byte 6445 (`abc49201`). |
| Mod property | `new_mod_property_data` key `2400811`, body `[120919,120959)`: `item_no=19500811`, `main_entry_no=9318`, `frame=26`, `is_shiny_mod=0`, `shiny_replace_mod_code=2410208`, `mode_component_id=19000027`. |
| Installed name | Typed `mod_name` source `精准充能<御空>_$S@TIDS$_39o6|0` maps by exact installed English TID key to `Precision Charge <Aero>`; English map pair byte offset 20475443. |
| Main-entry family | `new_mod_sort__mod_codes_under_entry` group key `9318` contains mod `2400811` at member byte 4394. This is an exact family-member join. |
| Suffix/frame | `new_mod_frame_lib_data` frame `26` names `<Aero>` and lists `sub_entry_item_no=[2601,2602,7405,5101]`, with source token offsets 2159, 2161, 2163, 2165. Its `activation_mapping` pointer resolves to literal bytes `07 00` at 1535; these bytes are retained without an invented effect interpretation. |

The **Aero frame/badge `26` is an appearance/layout identity**, not a stored roll rank or Field Guide level. The ordinary-to-Shiny link points to a separate mod code; it does not make the ordinary item Shiny. The source packet's 17 global mod levels do not map this exact item to a specific level or roll.

## What “Weapon DMG” can and cannot mean here

The published pants/Aero bonus-line layout candidate lists `aero_weapon_dmg` first (THGL source `mod_9311`). That page is a layout source, not a native affix-ID foreign key to item `19500811`; its page number must not be equated to native `main_entry_no=9318`.

The [installed English crosswalk](NATIVE_COMBAT_ENGLISH_LABEL_CROSSWALK.md) proves two exact but distinct native affixes both format as `Weapon DMG +{:.1%}`:

- `D0102 → D01 attack`: current-weapon attack property, native affix type 2/range 2.
- `E4200 → E42 attack_type_dam_add_rate_remote`: Remote attack-type bonus, native affix type 1/range 1.

Neither `new_mod_item_data`, the exact mod-property row, group 9318, nor frame 26 names `D0102` or `E4200` as the selected subattribute. The four `sub_entry_item_no` integers are **not proven affix IDs**. Thus the English line and this exact item identity still do **not** decide which Weapon DMG property is active. A numeric damage vector for this mod would be fabricated.

## Main-effect candidate and activation limit

`mod_entry_data` contains two *name-matched* `精准充能` entries, `19289` and `58166`, each referencing buff `589318000`. Their exact name/ID records do not include a captured foreign key from `main_entry_no=9318`. A bounded static copy of `buff_589318000_1.pyc` (archive index 48316, SHA-256 `870a3baacbf70b21caeb98536be79970890b5f5361ae50c8e1eb2411ac2637d8`) has the string members `weakspot_count`, `NodeReloadSucEvent`, and `NodeCastBuffToTarget`, but string membership alone does not prove node connections, buff coefficient, or effect execution. The community core-text candidate says previous-magazine weakspot rate yields Elemental DMG after reload; its two numeric candidates and level binding remain unverified by this native join. Do not apply the candidate as an active native buff.

**Exact next missing records:** a native foreign key `main_entry_no=9318` → entry `19289`/`58166`; typed `sub_entry_item_no` 2601/2602/7405/5101 → concrete affix IDs and values (or an owned-item selected affix list); and the readable activation path from the selected entry/buff to a holder property change. Until those links are present, the exact item name and Aero badge cannot resolve the Weapon DMG collision or certify a core-effect numeric result.
