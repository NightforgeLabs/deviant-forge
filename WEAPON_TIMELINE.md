# Weapon event timeline scenarios

The local API accepts source actions for nine representative keyword weapons. It returns trigger, packet, state and ammo events with stable IDs. An optional `damage_model` projects explicit hit and packet inputs into a known subtotal, modeled scenario total, burst rate and sustained rate. It does **not** infer landed hits, add generated triggers back as bullets, compute a current weapon's absolute damage, or claim verified game DPS.

`GET /api/weapon-timeline-coverage` lists the nine families. `POST /api/weapon-timeline-simulate` runs one scenario. Structured Compare lets the user choose gear or saved plans by name and enter paired weapon scenarios through guided fields under Encounter inputs. Advanced JSON remains optional for event details outside the guided form. The advanced Compare context also accepts `weapon_timeline: {"left": <scenario>, "right": <scenario>}`; the two event timelines are shown separately and are never added to component ratios. The selected weapon ID is a binding for a dated release or preview rule, not proof of the user's owned weapon or crafted stats.

The guided form requires a weapon, dated-release or preview evidence mode, landed hit count, exposure, target, direct basis/class/element/coefficient, per-side final damage pools, and a chosen random-proc outcome. It can generate firing and reload actions from entered RPM, magazine, and reload seconds. Hazardous Object supports a single-magazine reload blast with an explicit target count; refill or multi-magazine behavior needs advanced inputs. A complete pair with the same duration gets a **modeled scenario** rate difference when landed hit counts match, or when different counts equal the maximum supported by each entered RPM, magazine and reload cycle. Unexplained count differences, different durations and unresolved packets get no modeled winner. `game_winner_established` remains false. Selected equipment does not silently alter the entered weapon pools; the user enters each side’s final pool values.

Example body for a Power Surge branch:

```json
{
  "weapon_id": "weapon:mps7-outer-space",
  "evidence_mode": "dated_release",
  "model_mode": "explicit_assumptions",
  "stream_id": "example-left",
  "actions": [
    {"kind": "hit", "at": 0, "target": "dummy", "rolls": {"power_surge": "0.1"}, "conditions": {"target_affected_by_power_surge": false}, "input_id": "hit-1"}
  ]
}
```

Other source actions are `fire` (requires a magazine and explicit rounds), `reload` (requires caller-supplied loaded rounds for an ordinary reload), and `observe_stacks` (requires an externally observed keyword stack count). Supply events in time order. Give every source action a stable `input_id` and every scenario stream a unique `stream_id`; duplicate input IDs with identical payloads return the same derived IDs and are suppressed from the output. A reused ID with changed payload fails. Equal timestamps follow the supplied action order.

Use `preview_simulation` only for preview-backed weapons; `dated_release` cannot run them. Use `explicit_assumptions` when a counter overflow, refresh, or rounding policy is not sourced. Every response includes dated source status, unresolved binding fields and final ammo. Without a `damage_model`, totals and rates remain null. A generated `keyword_trigger` is a notification, not another landed bullet. To turn one into modeled damage, supply a resolved hit count or a tick schedule, basis, coefficient, class and element applicability. Unknown events keep the full total null while `known_damage_subtotal` shows the calculated parts.

For example, add this to the Power Surge request above to calculate its entered direct hit while keeping the unmodeled Power Surge proc unresolved:

```json
"damage_model": {
  "basis_values": {"attack": 100, "psi": 80},
  "bonus_pools_percent": {"weapon": 20, "status": 10, "elemental": 30},
  "direct": {"basis": "attack", "damage_class": "weapon", "element": "none", "coefficient_percent": 100},
  "duration_seconds": 2,
  "burst_window": {"start_seconds": 0, "end_seconds": 1}
}
```

Advanced and guided Compare can opt into `context.weapon_timeline_pool_mode: "selected_reviewed_rows"`. Enter all six `context.base_pools` (Weapon, Status, Elemental, All, Crit, Weakspot) as the common baseline **excluding** the selected alternatives. Leave `damage_model.bonus_pools_percent` absent on both sides. Compare adds each side’s resolved selected rows once, reports the applied values and source/gap audit, and rejects unknown activation or manual pool double entry. It does not apply keyword-specific, fire-rate, magazine, reload or typed core state outputs to the event timeline. The six packet-only weapon timelines reject this pool mode until their damage class and bonus routing are established. The guided form exposes this as “Apply selected reviewed gear rows.”

`packet_models` can supply missing classifications and explicitly resolved target or tick counts. The sourced Outer Space lightning uses the dated 500% Psi coefficient without re-entering it. Hazardous Object's reload blast uses the sourced ammo-dependent coefficient but requires `target_count`, including zero if the blast hit nothing. `reload_timing` requires a base reload duration and optional efficiency percent; the official denominator rule is applied. Missing reload timing blocks a sustained rate without erasing a known damage total. `reference_values` names Shrapnel, Bomber or Burn bases only when the caller has a defined basis. The 14 source packet definitions live in `weapon_mechanics/damage_bindings_v3.json`; preview values remain gated.

Damage class, elemental applicability and crit/weakspot eligibility are independent. If the class is unknown but entered Weapon and Status pools are equal, the damage is invariant under those two class hypotheses and the result retains `damage_class: null`. Otherwise choose an explicit named class scenario or leave the packet unresolved. User-provided class and packet values are labeled assumptions, not current tooltip verification. A periodic schedule needs duration, interval, initial delay and refresh policy. Replayed event IDs and landed hits are counted once; derived triggers never feed themselves back as source actions.

The package's nine representatives are Outer Space (Power Surge), Conflicting Memories (Shrapnel), Crank (Burn), Abyss Glance (Frost Vortex), Hazardous Object (Unstable Bomber), Blue Tiger (Bounce), Predator (Fast Gunner), Additional Rules (Fortress Warfare), and Doombringer (Bull's Eye). Their source bindings cover these representatives only; they do not make all 138 catalog weapons executable or verify November 2026 tooltip values.

## Additional sourced packet timelines

Six further weapon identities now accept explicit source-action timelines through the same `/api/weapon-timeline-simulate` endpoint: Critical Pulse, Hammerhead, Boom! Boom!, Pyroclasm Starter, Pathfinder and Holographic Resonance. Their actions include observed resource balances, charged shots, orb ticks, chains, explosions and resolved area targets. These paths use `weapon_mechanics/packet_timeline_v4.py` and the source-qualified v3 packet arithmetic. They return a **base packet subtotal** and, with an entered duration, a packet-only rate. Direct bullet damage, target mitigation, unresolved classes and selected bonus pools remain outside that subtotal; `total_damage` and full `damage_per_second` stay null. Preview-only coefficients require `preview_simulation`. The Critical Pulse runner deduplicates one orb/tick/target even when the same observation uses two input IDs.

## Stateful main-mod candidates

`POST /api/mod-stateful-simulate` executes explicit event scenarios for the 39 candidate identities in Covered Advance, Momentum Up and Ruthless Reaper families. `GET /api/mod-stateful-coverage` reports operator and evidence coverage. Supply the exact catalog identity and selected level for linkage, `allow_candidate: true`, initial state, ordered events and any required named semantic assumptions. Candidate values remain unbound to the selected level and current game version. Structured Compare accepts paired scenarios under `context.mod_stateful` and displays outputs separately from damage ratios. Duplicate event IDs are ignored. Covered Advance uses the v7.1 time-advance fix; exact activation boundaries require a named ordering assumption.
