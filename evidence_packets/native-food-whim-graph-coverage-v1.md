# Source-linked cuisine and Whim buff-graph coverage

Installed build `26267212`. The complete machine-readable ledger is [`food_whim_bonus_coverage.json`](food_whim_bonus_coverage.json); a compact 33-item combat subset is [`food_whim_combat_priority.json`](food_whim_combat_priority.json). Reproduce both with `python capture_food_whim_graphs.py`, `python trace_food_whim_graphs.py`, `python capture_food_whim_secondary.py`, `python trace_food_whim_secondary.py`, `python capture_food_whim_tertiary.py`, then `python build_food_whim_bonus_coverage.py`. Every capture is an exact archive-name match followed by bounded Zstd decompression and static marshal/bindict reading. No copied game code was imported or executed; installed game and Forge files were unchanged.

## Coverage and exact joins

| Source scope | Result |
| --- | ---: |
| Indexed cuisine items; adjacent Whim items | 509; 12 |
| Items with a typed buff token; item-to-buff references | 225; 265 |
| Distinct directly linked buff IDs | 143 |
| Direct buff graphs typed; archive graph absent | 142; 1 (`403152800`) |
| Exact cast targets typed one hop; two hops | 27; 1 |
| Total buff IDs reviewed including missing graph | 171 |
| Graphs with typed native attribute targets | 93 |
| Item records with a combat or Psi-related native target | 33 |

The item ledger records every item ID, installed English title where available, exact source buff token and offset, typed nominal `life_time` in seconds, and configured cast path. It retains all 296 items without an exact buff token and eight without a validated English title. The graph ledger records source hashes/offsets, every node type, control/data edges, typed attribute and value fields, linked numeric input expressions, checker records, cast IDs, and unresolved input pins. All 48 `NodeChecker` configurations in the 142 primary graphs have typed child checker records. A cast edge shows configured reachability, **not** runtime activation.

## Selected combat inputs

These are source graph configurations. `R` below is an explicitly supplied `buff.effect_rate`; no current player value is inferred. The copied arithmetic consumer and enum establish `ADD=0`, `MUL=1` for the linked numeric pins. The final server attribute change and any condition truth remain unproved.

| Item and exact buff | Nominal source lifetime | Typed native target | Configured value or input | Graph condition |
| --- | ---: | --- | --- | --- |
| French Fries `30110206 → 403132700` | 1,800 s | `E42 attack_type_dam_add_rate_remote` | `(R + 1) × 0.2` | Checker for presence of buff `110600100` precedes target. |
| Stargazy Pie `30110303 → 403133600` | 1,800 s | `E02 crit_dam_rate` | `(R + 1) × 0.25` | An `attr_value_checker` precedes target; its runtime result is unknown. |
| Bone-in Deviated Sausage `30110324 → 403132600` | 1,800 s | `E100 unit_prototype_dam_add_rate_boss` | `(R + 1) × 0.15` | No local checker node in the linked graph. |
| Whimsical Drink `30110344 → 403134100` | 1,800 s | `E43 attack_type_dam_add_rate_dot` | `(R + 1) × 0.25` | No local checker node in the linked graph. |
| Sparkling Pumpkin Soup `30110374 → 403136600` | 1,980 s | `E121 keyword_proc_dam_add_rate_surge` | `(R + 1) × 0.1` | No local checker node in the linked graph. |
| Heavy Strike Azure Cake `30119705 → 499008005` | 1,200 s | `E101/E100/E99/E102` creeps/boss/elite/leader damage rates | Four typed float64 values `0.1` | Entry node directly targets one fixed attribute node; no local checker. |
| Predator Whim `30139011 → 530001700 → 530001800` | 7,200 s for first buff | `E03 weak_dam_rate` in cast target `530001800` | Typed float64 value `0.5` on the secondary graph | Parent and secondary contain multiple state, fight, attack, delay and buff checks; no uptime is inferred. |

The full ledger includes the other 26 items with combat-named targets, elemental and Shrapnel properties, all noncombat targets, and each node's exact raw fields. Across 125 `NodeChangeAttrInputValue` targets, 96 have a typed numeric expression trace, 23 have a connected input that cannot yet be reduced with the proven arithmetic subset, and six have an unlinked stored default. Another 37 `NodeChangeAttr` target records have fixed typed values. These counts describe serialized graph inputs, not automatically applied stats. No directly typed `skill_power` target was found among the captured item-linked graphs; this does not rule out indirect or uncaptured effects.

Whimsical Drink also directly references `404000600` with a typed `life_time=0`; that graph casts `404000610`. Its zero source lifetime does not establish permanence, and neither graph is reduced to an automatic damage contribution.

## Control items and unresolved behavior

- **Gingerdrop** `30110378 → 403137000` has nominal `1,800 s`. Its sole typed attribute target is `L21 tag_buff_time_extend_add_rate_armed`, with connected input `(R + 1) × 5`. The installed description speaks of defense, but this graph does not provide a bound defense attribute or amount. The expression is not a verified defense bonus or applied duration.
- **Utter Delight** `30139002 → 530001300` has an aligned `get_image` item-use token and same-ID typed buff row with nominal `7,200 s`. Its two-node graph fixes `R37 mutation_time_extend` to raw `0.35`, `value_type=1`. The item-use application and property consumer remain unproved; do not apply a blanket 35% Whim duration increase.
- **Missing source:** item-linked `403152800` has no exact `buff_<id>_1.pyc` in the installed archive and an ambiguous/missing typed buff row in the upstream packet. Its effect and duration remain unavailable.

This packet is ready for catalog descriptions and source inspection. Live build calculations still require the authoritative equip/use application, graph executor, selected buff rate, conditions, recipient, stacking, and duration rules. No food or Whim bonus is marked automatically active by this review.
