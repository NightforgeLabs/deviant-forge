# Forge variant provenance for 33 combat foods

The source-of-truth packet is [food_combat_forge_variant_ledger.json](food_combat_forge_variant_ledger.json), reproduced by `python decode_combat_food_forge_variants.py` from copied installed build `26267212` data. It joins every prior typed recipe row to the native `forge_data` root key and cross-checks that item's `item_to_forge_dict` key list. No key is inferred from a nearby number or item name.

## Coverage and five aliases

| Scope | Verified count |
| --- | ---: |
| Combat food item IDs | 33 |
| Distinct typed crafting rows | 77 |
| Forge keys pointing to those rows | 82 |
| Rows with two alias keys | 5 |
| Item-to-forge lists exactly matching observed keys | 33/33 |

The earlier 77-row recipe ledger remains correct: **five additional keys are aliases to existing rows**, not additional recipes. The aliases are:

| Item ID | Row byte offset | Keys for the same row |
| ---: | ---: | --- |
| `30110206` | `564377` | `1200125`, `(1200125,1)` |
| `30110303` | `514034` | `1200307`, `(1200307,1)` |
| `30110322` | `482713` | `1200311`, `(1200311,1)` |
| `30110345` | `565313` | `1200340`, `(1200340,1)` |
| `30110346` | `493382` | `1200341`, `(1200341,1)` |

Among the 82 keys, the tuple selector counts are `1`: 22, `11`: 1, `222`: 26, and `223`: 1; the remaining 32 are scalar keys. Sparkling Pumpkin Soup retains its three distinct rows for `1200379`, `(1200379,1)`, and `(1200379,222)` as detailed in [SOUP_FORGE_VARIANT_SELECTION.md](SOUP_FORGE_VARIANT_SELECTION.md).

## Configured gate fields

All 77 rows point `valid_time` to the same typed empty object `07 00`; none serializes `season_no`, `can_invent`, or `invent_tech_ids`. `forge_display` is explicitly zero in 74 rows and absent in three; the readable `get_forge_can_hide` consumer defaults absent values to zero. Six rows set `is_diy=1`: two Supreme Meat Platter, two Supreme Wild Vegetable Platter, one Source of Deviation, and one Ultraman row. The generic `get_forge_no_by_server_num` resolver returns a DIY key directly before seasonal substitution. Nine rows have configured `build_lv=1`; this is a field value, not proof the player meets a station requirement.

Seven rows have a typed, localized `unlock_tip`: Old Captain's Spirit says **“Unlock Memetics”**; the six DIY rows above say **“Memetic not yet unlocked.”** The packet includes exact native text pointers and installed English translation offsets. The UI also calls live `ClientAvatar.is_memes_unlocked` for candidate recipes, but the copied rows do not encode the specific Memetic ID and the player's unlock state is unknown. The UI checks the server's active forge-season and disabled-formula settings; no current server state is claimed.

## What selector IDs mean here

The copied `season_template_data` has a typed `forge_season_no` field. Among 317 indexed server-template rows, selector `1` occurs in 47 templates (all area code `ne_frac`), `11` in six (also `ne_frac`), `222` in 267 across several area codes, and `223` in 14 (area code `w_ev`). Every matching template ID, area code, typed leaf offset, and selector list is in the packet. These associations establish **numeric selector provenance**, but `area_no` is a code, not a verified English scenario name. No exact localized scenario-name join was found in the inspected template record, so none is assigned to `1`, `11`, `222`, or `223`.

The native forge table includes recipe configuration and historical/seasonal variants. Current availability, active season, disabled list, client candidate list, station state, inventory, and player unlocks require live context; this static ledger does not assert them. No game code ran, and no game or Forge files were changed.
