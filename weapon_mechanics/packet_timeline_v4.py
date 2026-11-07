"""Additive timelines for six v3 damage packets absent from mechanics v2.

All target lists, charge inventory, orb lifetime and RNG outcomes come from the
caller. This module does not modify the frozen v2 runner or guess game behavior.
"""
from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from .operators import D, I, Cooldown, HitCounter, tick_times

MAX_RESOLVED_UNITS = 10000


def load_timeline_bindings() -> dict:
    return json.loads((Path(__file__).parent / "packet_timeline_bindings_v4.json").read_text())


def _ids(values, name: str, *, allow_repeat: bool = False) -> list[str]:
    if not isinstance(values, list) or len(values) > MAX_RESOLVED_UNITS:
        raise ValueError(f"{name} must be a bounded list")
    if any(not isinstance(value, str) or not value for value in values):
        raise ValueError(f"{name} needs nonempty target IDs")
    if not allow_repeat and len(values) != len(set(values)):
        raise ValueError(f"{name} contains duplicate targets")
    return values


@dataclass
class PacketTimelineV4:
    weapon_id: str
    evidence_mode: str
    stream_id: str
    observed_charges: int = 0
    observed_charged_rounds: int = 0
    counter_overflow: str | None = None
    binding: dict = field(init=False)
    last_at: Decimal = field(default=Decimal("-1"), init=False)
    cache: dict = field(default_factory=dict, init=False)
    orb_schedules: dict = field(default_factory=dict, init=False)
    resolved_orb_tick_keys: set = field(default_factory=set, init=False)
    cooldown: Cooldown | None = field(default=None, init=False)
    counter: HitCounter | None = field(default=None, init=False)

    def __post_init__(self):
        self.binding = load_timeline_bindings()["weapons"][self.weapon_id]
        if self.evidence_mode not in {"dated_release", "preview_simulation"}:
            raise ValueError("select dated_release or preview_simulation")
        if ("preview" in self.binding["evidence_status"]
            and self.evidence_mode != "preview_simulation"):
            raise ValueError("preview trigger requires preview_simulation")
        if not isinstance(self.stream_id, str) or not self.stream_id:
            raise ValueError("stable stream_id required")
        if I(self.observed_charges, name="observed_charges") < 0:
            raise ValueError("negative observed charges")
        if I(self.observed_charged_rounds, name="observed_charged_rounds") < 0:
            raise ValueError("negative observed charged rounds")
        if self.weapon_id == "weapon:kvd-boom-boom":
            self.cooldown = Cooldown(D(self.binding["cooldown_seconds"]))
        if self.weapon_id == "weapon:pdw90-holographic-resonance":
            if self.counter_overflow not in {"reset", "subtract"}:
                raise ValueError("explicit counter_overflow model required")
            self.counter = HitCounter(self.binding["hit_threshold"], self.counter_overflow)

    def _event(self, at: Decimal, target: str, **extra) -> dict:
        return {"at": at, "event": self.binding["packet_id"].rsplit("/", 1)[1],
                "weapon_id": self.weapon_id, "packet_id": self.binding["packet_id"],
                "target": target, "resolved_hit": True,
                "effect_type": "damage_trigger", **extra}

    def _once(self, method: str, at, input_id: str, payload: dict, build) -> list[dict]:
        at = D(at)
        if at < 0 or not isinstance(input_id, str) or not input_id:
            raise ValueError("nonnegative time and stable input_id required")
        key = (method, input_id)
        fingerprint = json.dumps(payload, sort_keys=True, default=str)
        if key in self.cache:
            previous, events = self.cache[key]
            if fingerprint != previous:
                raise ValueError("input_id reused with different payload")
            return deepcopy(events)
        if at < self.last_at:
            raise ValueError("events must arrive in nondecreasing time order")
        events = build(at)
        if len(events) > MAX_RESOLVED_UNITS:
            raise ValueError("resolved event limit exceeded")
        for index, event in enumerate(events):
            event["event_id"] = f"{self.stream_id}/{self.weapon_id}/{method}/{input_id}/{index}"
            event["source_event_id"] = input_id
        self.last_at = at
        self.cache[key] = (fingerprint, deepcopy(events))
        return events

    def observe_resource_balance(self, at, input_id: str, *, charges: int | None = None,
                                 charged_rounds: int | None = None) -> list[dict]:
        """Synchronize observed resources after external pickup/reload resolution.

        This assigns observed balances; it never computes acquisition or conversion.
        """
        if charges is None and charged_rounds is None:
            raise ValueError("at least one observed resource balance required")
        if charges is not None and I(charges, name="charges") < 0:
            raise ValueError("negative observed charges")
        if charged_rounds is not None and I(charged_rounds, name="charged_rounds") < 0:
            raise ValueError("negative observed charged rounds")
        payload = {"at": at, "charges": charges, "charged_rounds": charged_rounds}

        def build(now):
            if charges is not None:
                self.observed_charges = charges
            if charged_rounds is not None:
                self.observed_charged_rounds = charged_rounds
            return [{"at": now, "event": "resource_balance_observed",
                     "weapon_id": self.weapon_id, "effect_type": "state_change",
                     "charges": self.observed_charges,
                     "charged_rounds": self.observed_charged_rounds}]

        return self._once("resource_observation", at, input_id, payload, build)

    def critical_pulse_start_orb(self, at, input_id: str, *, hit_target: str,
                                 orb_duration_seconds, first_tick_delay_seconds,
                                 include_endpoint: bool) -> list[dict]:
        if self.weapon_id != "weapon:critical-pulse":
            raise ValueError("wrong weapon for orb")
        if not isinstance(hit_target, str) or not hit_target:
            raise ValueError("hit target required")
        duration = D(orb_duration_seconds)
        if duration <= 0:
            raise ValueError("positive caller-supplied orb duration required")
        payload = {"at": at, "hit_target": hit_target, "duration": duration,
                   "first_delay": first_tick_delay_seconds,
                   "include_endpoint": include_endpoint}

        def build(now):
            if self.observed_charges < 1:
                raise ValueError("observed charge required")
            times = tick_times(now, duration, self.binding["tick_interval_seconds"],
                               first_delay=first_tick_delay_seconds,
                               include_endpoint=include_endpoint)
            self.observed_charges -= 1
            self.orb_schedules[input_id] = set(times)
            return [{"at": now, "event": "orb_started", "weapon_id": self.weapon_id,
                     "orb_id": input_id, "effect_type": "state_change",
                     "scheduled_tick_count": len(times)}]

        return self._once("orb_start", at, input_id, payload, build)

    def critical_pulse_orb_tick(self, at, input_id: str, *, orb_id: str,
                                target: str, distance_meters) -> list[dict]:
        if self.weapon_id != "weapon:critical-pulse":
            raise ValueError("wrong weapon for orb")
        if not isinstance(target, str) or not target:
            raise ValueError("target required")
        distance = D(distance_meters)
        if distance < 0:
            raise ValueError("negative target distance")
        payload = {"at": at, "orb_id": orb_id, "target": target, "distance": distance}

        def build(now):
            if orb_id not in self.orb_schedules or now not in self.orb_schedules[orb_id]:
                raise ValueError("tick outside caller-specified orb schedule")
            if distance > D(self.binding["radius_meters"]):
                return []
            # Transport input IDs are not a sufficient identity for this
            # periodic effect. One orb may damage one target once per tick.
            logical_key = (orb_id, now, target)
            if logical_key in self.resolved_orb_tick_keys:
                return []
            self.resolved_orb_tick_keys.add(logical_key)
            return [self._event(now, target, orb_id=orb_id)]

        return self._once("orb_tick", at, input_id, payload, build)

    def hammerhead_chain_hit(self, at, input_id: str, *, primary_target: str,
                             primary_power_surge_status: bool,
                             nearby_affected_targets: list[str]) -> list[dict]:
        if self.weapon_id != "weapon:r500-hammerhead-shark":
            raise ValueError("wrong weapon for shock chain")
        if not isinstance(primary_target, str) or not primary_target:
            raise ValueError("primary target required")
        if not isinstance(primary_power_surge_status, bool):
            raise ValueError("Power Surge status must be boolean")
        targets = _ids(nearby_affected_targets, "nearby affected targets")
        if primary_target in targets:
            raise ValueError("primary target must not be in nearby list")
        payload = {"at": at, "primary": primary_target,
                   "affected": primary_power_surge_status, "nearby": targets}

        def build(now):
            if not primary_power_surge_status:
                return []
            events = [self._event(now, target, primary_target=primary_target)
                      for target in targets]
            # The source says 150% to the main target but does not specify
            # whether that is 150% of the chain packet or 150% Psi outright.
            events.append({"at": now, "event": "main_chain_damage_unresolved",
                           "weapon_id": self.weapon_id, "target": primary_target,
                           "effect_type": "unresolved", "reason": "main_target_150_percent_interpretation"})
            return events

        return self._once("chain_hit", at, input_id, payload, build)

    def boom_boom_hit(self, at, input_id: str, *, explosion_targets: list[str]) -> list[dict]:
        if self.weapon_id != "weapon:kvd-boom-boom":
            raise ValueError("wrong weapon for explosion")
        targets = _ids(explosion_targets, "explosion targets")
        payload = {"at": at, "targets": targets}

        def build(now):
            if not self.cooldown.try_trigger(now):
                return []
            return [self._event(now, target) for target in targets]

        return self._once("explosion_hit", at, input_id, payload, build)

    def pyroclasm_charged_shot(self, at, input_id: str, *,
                               resolved_damage_units: list[str]) -> list[dict]:
        if self.weapon_id != "weapon:acs12-pyroclasm-starter":
            raise ValueError("wrong weapon for charged round")
        # Multiple damage units may legitimately strike the same target.
        units = _ids(resolved_damage_units, "resolved damage units", allow_repeat=True)
        payload = {"at": at, "units": units}

        def build(now):
            if self.observed_charged_rounds < 1:
                raise ValueError("observed charged round required")
            self.observed_charged_rounds -= 1
            return [self._event(now, target, damage_unit_index=index)
                    for index, target in enumerate(units)]

        return self._once("charged_round", at, input_id, payload, build)

    def pathfinder_charged_shot(self, at, input_id: str, *,
                                charge_cost: int,
                                pierced_targets: list[str]) -> list[dict]:
        if self.weapon_id != "weapon:sks-pathfinder":
            raise ValueError("wrong weapon for charged spike")
        targets = _ids(pierced_targets, "pierced targets")
        if I(charge_cost, name="charge_cost") < 1:
            raise ValueError("positive caller-supplied charge_cost required")
        payload = {"at": at, "charge_cost": charge_cost, "targets": targets}

        def build(now):
            if self.observed_charges < charge_cost:
                raise ValueError("observed charge balance below supplied cost")
            self.observed_charges -= charge_cost
            return [self._event(now, target) for target in targets]

        return self._once("charged_spike", at, input_id, payload, build)

    def holographic_hit(self, at, input_id: str, *,
                         pulse_targets: list[str] | None = None) -> list[dict]:
        if self.weapon_id != "weapon:pdw90-holographic-resonance":
            raise ValueError("wrong weapon for area pulse")
        targets = None if pulse_targets is None else _ids(pulse_targets, "pulse targets")
        payload = {"at": at, "targets": targets}

        def build(now):
            triggering = self.counter.count + 1 >= self.counter.threshold
            if triggering and targets is None:
                raise ValueError("pulse targets required on trigger hit")
            n = self.counter.add(1)
            if not n:
                return []
            return [self._event(now, target) for target in targets]

        return self._once("area_hit", at, input_id, payload, build)
