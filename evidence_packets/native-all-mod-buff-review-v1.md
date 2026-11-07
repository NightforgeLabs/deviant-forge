# Complete configured mod-buff graph target review

Installed build `26267212`. This is a static review of **all 49 buff IDs** referenced by the 32 current identity-linked V2 mod frames' ordered bonus entries. It does not evaluate an owned mod or execute extracted game code. Reproduce the four remaining eight-ID capture batches with `python capture_remaining_mod_buff_graphs.py`, parse each with `trace_priority_mod_buff_graphs.py`, then run `python build_all_mod_buff_graph_review.py`. The complete [`all_mod_buff_graph_review.json`](all_mod_buff_graph_review.json) records all 49 IDs, source hashes, byte offsets, node and target IDs, level parameters, dynamic paths, control/data links, exact secondary cast references and schema boundaries. No installed game or Forge file was modified.

## Coverage result

| Graph result for 49 frame buff IDs | Count |
| --- | ---: |
| Previously reviewed with typed direct or indirect target | 17 |
| Newly reviewed with direct typed attribute target | 24 |
| Newly reviewed with exact secondary cast to typed attribute target | 5 |
| Newly reviewed effect nodes without an attribute target | 3 |
| **Primary graphs reviewed** | **49** |

Thus **46 IDs** have a source-keyed direct or secondary attribute target; the remaining **three** are effect-node cases, not missing IDs. This is target/operation coverage, **not** 46 verified combat effects. Every catalog text and level preview was already sourced in `verified_mod_frame_catalog.json`.

The five indirect paths are exact graph edges: Resonance `581701000 → 581701100 → E02 Crit DMG`; `581702000 → 581702100 → E03 Weakspot DMG`; `581703000 → 581703100 → E32/E33/E34/E38 elemental damage`; `581704000 → 581704100 → E32/E33/E34/E38`; Battle `589723000 → 589721100 → G52/G53` remote and Dot damage ignore. The four Resonance secondary graphs have `NodeChangeAttr.change_attr[].extra_value` paths bound to five level rows in native `buff_level_data`. The parent graph has no dynamic parameter row and configures `mapping_buff=1`; that flag and an exact cast ID do not prove which secondary level or stack the server applies.

The three effect-node cases are:

- Battle `581902000` casts secondary `581902100`. Its 14-node typed map names `NodeHeal` and `NodeGetFloatAttr`, but parameter records mix marker `0xd6` with `0x96`; the validated small-record parser does not decode its healing value or HP formula. The exact secondary node IDs, markers and offsets are preserved in the JSON.
- Mirror `582303000` contains `NodeHitAngleDamageReduce` with configured front threshold `80` and `value=12` at its captured graph default. Its level parameter and duration/angle behavior are not certified as applied damage reduction.
- Wild `582403000` contains `NodeDistanceDamageReduce` with configured distance `15` and `value=12` at its graph default. The node's damage settlement behavior is not decoded.

## Other newly resolved families

The direct graph ledger now includes Downstar's `highland_*` attributes separately from base `E02/E42/E43` and elemental `E32/E33/E34/E38`; Crescent's shield-dependent graph names `sum_field`, `max_hp`, floor and change nodes; Mirror's behind-target effects target E42/E02/E43 or four elemental attributes; Wild's distance effects target E42/E02/E43 or the elemental group; Phantasmal's switch effects target E42/E02/E43 or the elemental group, while its low-HP reduction targets `G11`; and Fast Gunner's three state effects target E42/E03/E02. These are typed target identities and graph configuration. The source files retain the exact condition fields, thresholds, numeric defaults and dynamic paths; no distance, shield, angle, timing or stacking equation is inferred from the node names.

The prior batch's level-bound constants that lack a decoded link to their attribute nodes remain unresolved. Some newly captured graphs likewise contain a configured constant and a change node without a typed data link. The review preserves those as distinct fields. Client/server node executor semantics, selected owned level and Shiny state, event truth, buff lifetime, activation, additive bucket placement and actual damage remain separate requirements. The source-visible graph target alone must never trigger an automatic combat contribution.

## Source and validation details

All 32 remaining primary archive paths were matched by exact `buff_<id>_1.pyc` name and copied in four batches of eight. Five secondary IDs came from exact `NodeCastBuffToTarget.buff_id` fields; four use the validated graph schema, and the fifth has the recorded mixed-marker boundary. The scripts assert expected 32/49 counts, unique IDs, all five level-row and dynamic index joins where present, native attribute IDs from the 838-row map, and the three effect-only exclusions. The JSON contains the complete per-ID coverage ledger and hashes for every capture packet. Static graph parsing is reproducible without importing game code.
