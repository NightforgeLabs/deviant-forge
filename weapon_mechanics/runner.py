"""Small event runner for source-labeled weapon bindings.

It emits keyword events and state changes, not a fabricated full DPS result.
Unknown status lifetime, proc RNG, and stack policy are explicit caller inputs.
"""
from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from .operators import (D, I, Ammo, Cooldown, HitCounter, SameTargetRamp,
                        TimedStacks, ammo_blast_coefficient, chance, proc_with_roll)

MAX_DERIVED_EVENTS = 10000


def load_bindings() -> dict:
    return json.loads((Path(__file__).parent / "bindings.json").read_text())


@dataclass
class WeaponTimeline:
    weapon_id: str
    evidence_mode: str
    model_mode: str
    magazine: int | None = None
    stream_id: str | None = None
    binding: dict = field(init=False)
    counters: dict = field(default_factory=dict)
    cooldowns: dict = field(default_factory=dict)
    stacks: dict = field(default_factory=dict)
    ramps: dict = field(default_factory=dict)
    buffs_until: dict = field(default_factory=dict)
    ammo: Ammo | None = field(init=False)
    last_stack_count: dict = field(default_factory=dict)
    last_at: Decimal = field(default=Decimal("-1"), init=False)
    sequence: int = field(default=0, init=False)
    event_cache: dict = field(default_factory=dict, init=False)

    def __post_init__(self):
        if self.stream_id is None:
            self.stream_id = uuid4().hex
        if not isinstance(self.stream_id, str) or not self.stream_id:
            raise ValueError("stream_id must be a nonempty string")
        self.binding = load_bindings()["weapons"][self.weapon_id]
        if self.evidence_mode not in {"dated_release", "preview_simulation", "historical_release"}:
            raise ValueError("select dated_release, preview_simulation or historical_release")
        if self.weapon_id == "weapon:mg4-conflicting-memories":
            if self.evidence_mode != "historical_release":
                raise ValueError("Current Conflicting Memories proc rule is unresolved after the 2026 rework; select historical_release only for the older 12-hit/32-round what-if")
        elif self.evidence_mode == "historical_release":
            raise ValueError("historical_release is reserved for the older Conflicting Memories rule")
        if self.model_mode not in {"explicit_assumptions", "verified_only"}:
            raise ValueError("select explicit_assumptions or verified_only")
        sources = load_bindings()["sources"]
        for rule in self.binding["rules"]:
            status = sources[rule["source"]]["status"]
            if "preview" in status and self.evidence_mode != "preview_simulation":
                raise ValueError(f"{self.weapon_id} requires preview_simulation")
            if "assum" in rule.get("model_status", "") and self.model_mode != "explicit_assumptions":
                raise ValueError(f"{self.weapon_id} requires explicit_assumptions")
        self.ammo = Ammo(self.magazine, self.magazine) if self.magazine is not None else None

    def _begin(self, kind: str, input_id: str | None, at: Decimal, payload: dict):
        if at < 0:
            raise ValueError("negative event time")
        if input_id is not None and (not isinstance(input_id, str) or not input_id):
            raise ValueError("input_id must be a nonempty string")
        fingerprint = json.dumps(payload, sort_keys=True, default=str)
        key = (kind, input_id)
        if input_id is not None and key in self.event_cache:
            previous, events = self.event_cache[key]
            if previous != fingerprint:
                raise ValueError("input_id reused with different payload")
            return deepcopy(events)
        if at < self.last_at:
            raise ValueError("events must be processed in time order")
        return None

    def _end(self, kind: str, input_id: str | None, at: Decimal,
             payload: dict, events: list[dict]) -> list[dict]:
        if len(events) > MAX_DERIVED_EVENTS:
            raise ValueError("derived event limit exceeded")
        self.sequence += 1
        source_id = f"input-{input_id}" if input_id is not None else f"sequence-{self.sequence}"
        damage_names = {item["name"] for item in self.binding.get("damage_events", [])}
        for index, event in enumerate(events):
            event["event_id"] = f"{self.stream_id}/{self.weapon_id}/{kind}/{source_id}/{index}"
            event["source_event_id"] = source_id
            event["weapon_id"] = self.weapon_id
            if event["event"] in damage_names:
                event["effect_type"] = "damage_trigger"
            elif "coefficient" in event:
                event["effect_type"] = "damage_packet"
            elif "keyword" in event:
                event["effect_type"] = "keyword_trigger"
            else:
                event["effect_type"] = "state_change"
        if input_id is not None:
            self.event_cache[(kind, input_id)] = (
                json.dumps(payload, sort_keys=True, default=str), deepcopy(events))
        self.last_at = at
        return events

    def hit(self, at, target: str, *, weakspot=False, distance=None,
            rolls: dict | None = None, conditions: dict | None = None,
            input_id: str | None = None) -> list[dict]:
        at = D(at)
        rolls, conditions = rolls or {}, conditions or {}
        payload = {"at": at, "target": target, "weakspot": weakspot,
                   "distance": distance, "rolls": rolls, "conditions": conditions}
        cached = self._begin("hit", input_id, at, payload)
        if cached is not None:
            return cached
        if not isinstance(target, str) or not target:
            raise ValueError("target id required")
        if not isinstance(weakspot, bool):
            raise ValueError("weakspot must be boolean")
        # Validate all required inputs before any rule can mutate state.
        for rule in self.binding["rules"]:
            if rule["kind"] == "proc":
                if rule.get("nearby") and distance is None:
                    raise ValueError(f"distance required for {rule['name']}")
                if distance is not None and D(distance) < 0:
                    raise ValueError("negative target distance")
                if rule["name"] not in rolls:
                    raise ValueError(f"roll required for {rule['name']}")
                proc_with_roll(rule["probability"], rolls[rule["name"]])
            elif rule["kind"] == "counter" and rule.get("requires_condition"):
                if rule["requires_condition"] not in conditions:
                    raise ValueError(f"condition {rule['requires_condition']} required")
                if not isinstance(conditions[rule["requires_condition"]], bool):
                    raise ValueError("condition must be boolean")
            elif rule["kind"] == "conditional_stack":
                if rule["condition"] not in conditions:
                    raise ValueError(f"condition {rule['condition']} required")
                if not isinstance(conditions[rule["condition"]], bool):
                    raise ValueError("condition must be boolean")
        out = []
        for rule in self.binding["rules"]:
            kind = rule["kind"]
            name = rule["name"]
            if kind == "proc":
                p = D(rule["probability"])
                near = rule.get("nearby")
                if near and distance is None:
                    raise ValueError(f"distance required for {name}")
                if near and distance is not None and D(distance) <= D(near["meters_lte"]):
                    p = D(near["probability"])
                if name in self.buffs_until and at < self.buffs_until[name]:
                    p = chance(p, rule["reload_relative_bonus"])
                if name not in rolls:
                    raise ValueError(f"roll required for {name}")
                if proc_with_roll(p, rolls[name]):
                    out.append({"at": at, "event": name, "keyword": rule["keyword"], "probability": p})
            elif kind == "counter":
                required = rule.get("requires_condition")
                if required and required not in conditions:
                    raise ValueError(f"condition {required} required")
                if required and conditions.get(required) is not True:
                    continue
                key = (name, target if rule.get("per_target") else "all")
                counter = self.counters.setdefault(key, HitCounter(rule["hits"], rule["overflow_model"]))
                weight = rule.get("weakspot_weight", 1) if weakspot else 1
                if (counter.overflow == "subtract" and
                    (counter.count + weight) // counter.threshold > MAX_DERIVED_EVENTS):
                    raise ValueError("counter event limit exceeded")
                for _ in range(counter.add(weight)):
                    out.append({"at": at, "event": name, "keyword": rule["keyword"],
                                "counter_remainder": counter.count})
            elif kind == "cooldown":
                key = (name, target if rule.get("per_target") else "all")
                cd = self.cooldowns.setdefault(key, Cooldown(D(rule["seconds"])))
                if cd.try_trigger(at):
                    out.append({"at": at, "event": name, "keyword": rule["keyword"]})
            elif kind == "same_target_ramp":
                ramp = self.ramps.setdefault(name, SameTargetRamp(D(rule["per_hit"]),
                    D(rule["cap"]), rule["target_change_model"]))
                value = ramp.hit(target)
                out.append({"at": at, "event": name, "stat": rule["stat"],
                            "additive_fraction": value})
            elif kind == "conditional_stack":
                if rule["condition"] not in conditions:
                    raise ValueError(f"condition {rule['condition']} required")
                if conditions.get(rule["condition"]) is True:
                    stacks = self.stacks.setdefault(name, TimedStacks(rule["cap"],
                        D(rule["duration_seconds"]), rule["refresh_model"]))
                    count = stacks.add(at)
                    out.append({"at": at, "event": name, "stat": rule["stat"],
                                "stacks": count, "additive_fraction": count * D(rule["per_stack"])})
        return self._end("hit", input_id, at, payload, out)

    def reload(self, at, *, loaded_rounds: int | None = None, refund_roll=None,
               refund_rounding=None, input_id: str | None = None) -> list[dict]:
        at = D(at)
        payload = {"at": at, "loaded_rounds": loaded_rounds,
                   "refund_roll": refund_roll, "refund_rounding": refund_rounding}
        cached = self._begin("reload", input_id, at, payload)
        if cached is not None:
            return cached
        is_blast = any(rule["kind"] == "reload_blast" for rule in self.binding["rules"])
        if is_blast:
            if loaded_rounds is not None:
                raise ValueError("blast reload cannot assume a refill")
            if refund_roll is not None and refund_rounding is None:
                raise ValueError("refund rounding model required")
            if refund_roll is None and refund_rounding is not None:
                raise ValueError("refund roll required with refund rounding")
        elif self.ammo is not None and loaded_rounds is None:
            raise ValueError("caller-supplied loaded_rounds required")
        if not is_blast and (refund_roll is not None or refund_rounding is not None):
            raise ValueError("refund inputs require blast reload")
        if loaded_rounds is not None and I(loaded_rounds, name="loaded_rounds") < 0:
            raise ValueError("negative loaded rounds")
        out = []
        did_blast = False
        for rule in self.binding["rules"]:
            kind = rule["kind"]
            if kind == "reload_relative_proc":
                self.buffs_until[rule["proc_name"]] = at + D(rule["duration_seconds"])
                out.append({"at": at, "event": rule["name"], "until": self.buffs_until[rule["proc_name"]]})
            elif kind == "reload_blast":
                did_blast = True
                if self.ammo is None:
                    raise ValueError("magazine required for reload blast")
                remaining = self.ammo.rounds
                coefficient = ammo_blast_coefficient(remaining, base=rule["base"],
                    per_round=rule["per_round"], cap=rule["cap"])
                out.append({"at": at, "event": rule["name"], "basis": rule["basis"],
                            "damage_class": rule["damage_class"],
                            "coefficient": coefficient, "consumed_ammo": remaining})
                if refund_roll is not None:
                    from .operators import refund_rounds
                    if refund_rounding is None:
                        raise ValueError("refund rounding model required")
                    fraction = rule["refund_fraction_high"] if proc_with_roll(
                        rule["refund_probability_high"], refund_roll) else rule["refund_fraction_low"]
                    refunded = refund_rounds(remaining, fraction, rounding=refund_rounding)
                    out.append({"at": at, "event": "ammo_refund", "rounds": refunded,
                                "rounding_model": refund_rounding})
                self.ammo.rounds = 0
        if self.ammo and not did_blast:
            loaded = self.ammo.reload(loaded_rounds)
            out.append({"at": at, "event": "ammo_loaded", "rounds": loaded})
        return self._end("reload", input_id, at, payload, out)

    def observe_keyword_stacks(self, at, keyword: str, count: int,
                               *, input_id: str | None = None) -> list[dict]:
        """Caller supplies actual keyword stack count; stacking rule is unknown."""
        at = D(at)
        payload = {"at": at, "keyword": keyword, "count": count}
        cached = self._begin("observe_stacks", input_id, at, payload)
        if cached is not None:
            return cached
        if I(count, name="stack count") < 0:
            raise ValueError("negative stack count")
        if not any(rule["kind"] == "stack_multiple" and rule["keyword"] == keyword
                   for rule in self.binding["rules"]):
            raise ValueError("unknown keyword stack observer")
        out = []
        old = self.last_stack_count.get(keyword, 0)
        for rule in self.binding["rules"]:
            if rule["kind"] == "stack_multiple" and rule["keyword"] == keyword:
                multiple = rule["multiple"]
                crossed = count // multiple - old // multiple
                if crossed > MAX_DERIVED_EVENTS:
                    raise ValueError("stack milestone event limit exceeded")
                for _ in range(max(0, crossed)):
                    if self.ammo is None:
                        raise ValueError("magazine required for unlimited ammo")
                    self.ammo.start_unlimited(at, rule["duration_seconds"])
                    out.append({"at": D(at), "event": rule["name"],
                                "until": self.ammo.unlimited_until})
        self.last_stack_count[keyword] = count
        return self._end("observe_stacks", input_id, at, payload, out)
