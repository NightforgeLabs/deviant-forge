# Lightning DOT factor order with supplied hit inputs

This is the shared native damage graph's arithmetic **after a hit has been accepted and its formula leaves supplied**. [`trace_lightning_dot_factors.py`](trace_lightning_dot_factors.py) statically checks source hashes, native property IDs, graph edges and two vectors; output is [`lightning_dot_factor_trace.json`](lightning_dot_factor_trace.json). The copied graph's version is 13, and the installed game build is 26267212. No game code was executed or game/Forge file changed.

The [tag lookup packet](AUG_ELEMENT_KEYWORD_TAG_LOOKUP.md) proves that AUG `element_type=3` names `lightning`; its configured formula attack type `4` names `Dot`. Native property IDs are `E34→element_type_dam_add_rate_lightning`, `E43→attack_type_dam_add_rate_dot`, and `E42→attack_type_dam_add_rate_remote`. Thus the native **remote/weapon attack type** property and the **DOT/status attack type** property are distinct. The copied UI localization does not yet prove that every player-facing “Weapon DMG,” “Status DMG,” or “Elemental DMG” string maps one-to-one to those IDs; use typed property IDs in DV until that display join is checked.

With both final-damage and final-ignore switches set to 1, graph node 301 multiplies the DOT factor `1 + BB.bound_attack_type_dam_add_rate` (139–142) by the element factor `max(1 + BB.bound_element_type_dam_add_rate, 0)` (24, 53, 86, 113), alongside keyword, crit/weak, generic final damage, and other factors. `CompFormulaAdapter.get_bound_element_type_dam_add_rate` reads the integer `element_type` and uses the element suffix lookup to select the elemental property. For type 3 that is the `lightning` suffix, whose typed property is `E34`. `E43` belongs to the Dot attack-type parent; `E42` belongs to Remote. An active modifier to one native property adds within that property's ABS bucket before the graph multiplies distinct buckets.

Target reductions form a **separate product** at graph node 308. Its native order includes:

1. `1 − BB.element_type_ignore_dam_rate` (nodes 131, 144), whose lightning subtype property is `G44→element_type_ignore_dam_rate_lightning`.
2. `1 − BB.attack_type_ignore_dam_rate` (nodes 128, 146–147), whose Dot subtype property is `G53→attack_type_ignore_dam_rate_dot`.
3. `1 − BB.element_type_ignore_dam` (nodes 123–124), whose lightning subtype property is `G104→element_type_ignore_dam_lightning`.

These factors are distinct from outgoing `E34`, `E43`, and `final_dam_add_rate` (`E98`). The copied formula adapter has exact getters for all three target properties; `formula_const` lists them in the target leaf group. The graph itself has no `max` around each reduction factor. Other node-308 factors, such as species, part, critical, weak and field terms, are held at 1 in the fixtures below. The terminal graph clamps the full product at zero (node 313), and the positive result wrapper rounds and applies a minimum of 1.

| Synthetic supplied graph inputs | Ordered selected calculation | Pre-round | Positive wrapper |
| --- | --- | ---: | ---: |
| Attack 100; Dot +0.20; lightning +0.10; target lightning rate 0.25; target Dot rate 0; target lightning other 0 | `100 × 1.20 × 1.10 × 0.75 × 1 × 1` | 99 | 99 |
| Attack 100; Dot +0.30; lightning −0.50; target lightning rate 0.20; target Dot rate 0.05; target lightning other 0.10 | `100 × 1.30 × 0.50 × 0.80 × 0.95 × 0.90` | 44.46 | 44 |

The two vectors supply **already bound graph leaf values** and set all other factors to 1, both final switches to 1, and keyword damage bonus to 0. They are arithmetic controls, not a player's AUG result. They establish how a DOT/status-type bonus and a lightning elemental bonus multiply once accepted. They do **not** establish an owned item's active affixes, how the absent durative executor fills hit leaves, whether `is_keyword_damage=0` suppresses the Surge keyword factor, proc frequency, target resistances, or complete DPS. A user-facing Weapon DMG bonus must be mapped to its exact native property before deciding whether it affects this DOT event; the Remote property `E42` is distinct from Dot `E43`.
