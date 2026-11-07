"""Composable, deterministic weapon event operators.

No game PRNG, stack refresh rule, or missing keyword coefficient is inferred here.
Callers supply those choices explicitly. Seconds and damage are decimal values.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation, ROUND_FLOOR
from typing import Literal


def D(value: object) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid decimal: {value!r}") from exc
    if not result.is_finite():
        raise ValueError("nonfinite number")
    return result


def I(value: object, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    return value


def chance(base: object, relative_bonus: object = 0) -> Decimal:
    """A +40% relative factor maps a 30% base chance to 42%."""
    p = D(base) * (1 + D(relative_bonus))
    if not 0 <= D(base) <= 1 or D(relative_bonus) < -1:
        raise ValueError("invalid base chance or relative bonus")
    return min(D(1), p)


def proc_with_roll(probability: object, roll: object) -> bool:
    """Deterministic branch; the caller supplies a uniform [0, 1) roll."""
    p, r = D(probability), D(roll)
    if not 0 <= p <= 1 or not 0 <= r < 1:
        raise ValueError("probability must be [0,1], roll [0,1)")
    return r < p


def independent_expected_procs(hits: int, probability: object) -> Decimal:
    """Expectation ONLY if hit rolls are independent and no cooldown applies."""
    if I(hits, name="hits") < 0 or not 0 <= D(probability) <= 1:
        raise ValueError("invalid hits or probability")
    return D(hits) * D(probability)


def independent_expected_procs_with_cooldown(hit_times: list, probabilities: list,
                                             cooldown_seconds: object,
                                             *, max_hits: int = 1000) -> Decimal:
    """Exact expected count for independent rolls and deterministic cooldown.

    This is a named alternate model, not a claim about Once Human's pseudo RNG.
    A probability may vary by hit (for example during a reload buff).
    """
    if (len(hit_times) != len(probabilities) or D(cooldown_seconds) < 0
        or I(max_hits, name="max_hits") < 1):
        raise ValueError("invalid cooldown model inputs")
    if len(hit_times) > max_hits:
        raise ValueError("expected-model hit limit exceeded")
    times = [D(t) for t in hit_times]
    ps = [D(p) for p in probabilities]
    if times != sorted(times) or any(t < 0 for t in times) or any(not 0 <= p <= 1 for p in ps):
        raise ValueError("times must be sorted, probabilities in [0,1]")
    states = {D(0): D(1)}  # ready_at -> probability mass
    expected = D(0)
    for at, p in zip(times, ps):
        next_states: dict[Decimal, Decimal] = {}
        for ready_at, mass in states.items():
            if at < ready_at:
                next_states[ready_at] = next_states.get(ready_at, D(0)) + mass
                continue
            expected += mass * p
            next_states[ready_at] = next_states.get(ready_at, D(0)) + mass * (1 - p)
            new_ready = at + D(cooldown_seconds)
            next_states[new_ready] = next_states.get(new_ready, D(0)) + mass * p
        states = next_states
    return expected


@dataclass
class HitCounter:
    threshold: int
    overflow: Literal["subtract", "reset"]
    count: int = 0

    def __post_init__(self):
        if (I(self.threshold, name="threshold") <= 0 or I(self.count, name="count") < 0
            or self.overflow not in {"subtract", "reset"}):
            raise ValueError("invalid counter")

    def add(self, weight: int = 1) -> int:
        if self.threshold <= 0 or I(weight, name="weight") < 0:
            raise ValueError("invalid threshold or weight")
        self.count += weight
        n = self.count // self.threshold
        if n:
            if self.overflow == "reset":
                self.count = 0
                return 1
            self.count %= self.threshold
        return n


@dataclass
class Cooldown:
    seconds: Decimal
    ready_at: Decimal = D(0)

    def __post_init__(self):
        self.seconds, self.ready_at = D(self.seconds), D(self.ready_at)
        if self.seconds < 0 or self.ready_at < 0:
            raise ValueError("invalid cooldown")

    def try_trigger(self, at: object) -> bool:
        at = D(at)
        if at < 0 or self.seconds < 0:
            raise ValueError("negative time or cooldown")
        if at < self.ready_at:
            return False
        self.ready_at = at + self.seconds
        return True

    def reduce(self, at: object, seconds: object) -> None:
        """Explicit cooldown reduction; never assumes the game permits it."""
        if D(seconds) < 0 or D(at) < 0:
            raise ValueError("negative reduction")
        self.ready_at = max(D(at), self.ready_at - D(seconds))


@dataclass
class TimedStacks:
    cap: int
    duration: Decimal
    refresh: Literal["independent", "all", "replace_oldest"]
    expiries: list[Decimal] = field(default_factory=list)

    def __post_init__(self):
        self.duration = D(self.duration)
        if I(self.cap, name="cap") < 1 or self.duration <= 0 or self.refresh not in {
            "independent", "all", "replace_oldest"
        }:
            raise ValueError("invalid stack settings")

    def count(self, at: object) -> int:
        at = D(at)
        if at < 0:
            raise ValueError("negative time")
        self.expiries = [expiry for expiry in self.expiries if expiry > at]
        return len(self.expiries)

    def add(self, at: object, amount: int = 1) -> int:
        at = D(at)
        if self.cap < 1 or self.duration <= 0 or I(amount, name="amount") < 0:
            raise ValueError("invalid stack settings")
        self.count(at)
        if self.refresh == "all" and self.expiries:
            self.expiries = [at + self.duration] * len(self.expiries)
        for _ in range(min(amount, self.cap)):
            if len(self.expiries) >= self.cap:
                if self.refresh == "replace_oldest":
                    self.expiries.remove(min(self.expiries))
                else:
                    continue
            self.expiries.append(at + self.duration)
        return len(self.expiries)


def tick_times(start: object, duration: object, interval: object, *, first_delay: object,
               include_endpoint: bool, max_ticks: int = 100000) -> list[Decimal]:
    """Exact scheduled tick instants; first tick/endpoint policy must be chosen."""
    start, duration, interval, first_delay = map(D, (start, duration, interval, first_delay))
    if (not isinstance(include_endpoint, bool) or start < 0 or duration < 0
        or interval <= 0 or first_delay < 0
        or I(max_ticks, name="max_ticks") < 1):
        raise ValueError("invalid tick schedule")
    end = start + duration
    t = start + first_delay
    result = []
    while t <= end if include_endpoint else t < end:
        if len(result) >= max_ticks:
            raise ValueError("tick limit exceeded")
        result.append(t)
        t += interval
    return result


@dataclass
class Ammo:
    capacity: int
    rounds: int
    unlimited_until: Decimal = D(0)

    def __post_init__(self):
        self.unlimited_until = D(self.unlimited_until)
        if (I(self.capacity, name="capacity") < 0 or I(self.rounds, name="rounds") < 0
            or self.rounds > self.capacity or self.unlimited_until < 0):
            raise ValueError("invalid ammo")

    def fire(self, at: object, rounds: int = 1) -> int:
        if (I(rounds, name="rounds") < 0 or D(at) < 0
            or self.rounds < 0 or self.rounds > self.capacity):
            raise ValueError("invalid ammo")
        consumed = 0 if D(at) < self.unlimited_until else rounds
        if consumed > self.rounds:
            raise ValueError("empty magazine")
        self.rounds -= consumed
        return consumed

    def reload(self, loaded: int) -> int:
        """Load up to ``loaded`` caller-supplied rounds; return rounds used.

        The caller owns reserve ammo and subtracts the returned amount from it.
        """
        if I(loaded, name="loaded") < 0:
            raise ValueError("negative reload count")
        before = self.rounds
        self.rounds = min(self.capacity, before + loaded)
        return self.rounds - before

    def start_unlimited(self, at: object, duration: object) -> None:
        if D(at) < 0 or D(duration) < 0:
            raise ValueError("invalid unlimited ammo window")
        self.unlimited_until = max(self.unlimited_until, D(at) + D(duration))


def reload_seconds(base_seconds: object, efficiency_percent: object) -> Decimal:
    """May 2025 official formula: base/(1 + efficiency percentage/100)."""
    efficiency = D(efficiency_percent)
    if D(base_seconds) < 0 or efficiency <= -100:
        raise ValueError("invalid reload input")
    return D(base_seconds) / (1 + efficiency / 100)


def ammo_blast_coefficient(remaining_ammo: int, *, base: object, per_round: object,
                           cap: object) -> Decimal:
    if I(remaining_ammo, name="remaining_ammo") < 0 or min(D(base), D(per_round), D(cap)) < 0:
        raise ValueError("negative ammo")
    return min(D(cap), D(base) + D(per_round) * remaining_ammo)


def refund_rounds(expended: int, fraction: object, *, rounding: Literal["floor", "exact"]):
    """The game rounding rule is unknown; caller must select an explicit model."""
    if I(expended, name="expended") < 0 or not 0 <= D(fraction) <= 1:
        raise ValueError("invalid refund")
    value = D(expended) * D(fraction)
    if rounding == "exact":
        return value
    if rounding == "floor":
        return int(value.to_integral_value(rounding=ROUND_FLOOR))
    raise ValueError("unknown rounding model")


def magazine_extra_parts(capacity: int, rounds_per_part: int, cap: int) -> int:
    """For effects granting one extra part per full magazine-size threshold."""
    if (I(capacity, name="capacity") < 0 or I(rounds_per_part, name="rounds_per_part") <= 0
        or I(cap, name="cap") < 0):
        raise ValueError("invalid magazine part settings")
    return min(cap, capacity // rounds_per_part)


def ammo_fraction_above(rounds: int, capacity: int, threshold: object) -> bool:
    if (I(capacity, name="capacity") <= 0 or I(rounds, name="rounds") < 0
        or rounds > capacity or not 0 <= D(threshold) <= 1):
        raise ValueError("invalid ammo fraction inputs")
    return D(rounds) > D(capacity) * D(threshold)


def delay_bonus(delay_seconds: object, fraction_per_tenth: object,
                *, rounding: Literal["full_tenths", "continuous"]) -> Decimal:
    """A source may say 'per 0.1s' without specifying fractional tenths."""
    tenths = D(delay_seconds) * 10
    if tenths < 0:
        raise ValueError("negative delay")
    if rounding == "full_tenths":
        tenths = tenths.to_integral_value(rounding=ROUND_FLOOR)
    elif rounding != "continuous":
        raise ValueError("unknown delay rounding")
    return tenths * D(fraction_per_tenth)


@dataclass(frozen=True)
class DamagePacket:
    basis: Literal["attack", "psi"]
    damage_class: Literal["weapon", "status"]
    coefficient: Decimal
    element: str | None = None
    crit_eligible: bool | None = None
    weakspot_eligible: bool | None = None

    def __post_init__(self):
        if self.basis not in {"attack", "psi"} or self.damage_class not in {"weapon", "status"}:
            raise ValueError("invalid damage basis or class")
        if D(self.coefficient) < 0:
            raise ValueError("negative damage coefficient")

    def amount(self, *, attack: object, psi: object, additive_bonus: object = 0,
               multiplicative_bonus: object = 1, crit_multiplier: object = 1,
               weakspot_multiplier: object = 1, crit: bool = False,
               weakspot: bool = False) -> Decimal:
        if crit and self.crit_eligible is not True:
            raise ValueError("crit eligibility unverified or false")
        if weakspot and self.weakspot_eligible is not True:
            raise ValueError("weakspot eligibility unverified or false")
        base = D(attack) if self.basis == "attack" else D(psi)
        if (base < 0 or D(additive_bonus) < -1 or D(multiplicative_bonus) < 0
            or D(crit_multiplier) < 0 or D(weakspot_multiplier) < 0):
            raise ValueError("negative damage component")
        return (base * self.coefficient * (1 + D(additive_bonus))
                * D(multiplicative_bonus)
                * (D(crit_multiplier) if crit else 1)
                * (D(weakspot_multiplier) if weakspot else 1))


@dataclass
class SameTargetRamp:
    per_hit: Decimal
    cap: Decimal
    target_change: Literal["halve_floor", "reset"]
    target: str | None = None
    hits: int = 0

    def __post_init__(self):
        self.per_hit, self.cap = D(self.per_hit), D(self.cap)
        if (self.per_hit <= 0 or self.cap < 0 or I(self.hits, name="hits") < 0
            or self.target_change not in {"halve_floor", "reset"}):
            raise ValueError("invalid ramp")

    def hit(self, target: str) -> Decimal:
        if self.per_hit <= 0 or self.cap < 0:
            raise ValueError("invalid ramp")
        if self.target is not None and self.target != target:
            self.hits = self.hits // 2 if self.target_change == "halve_floor" else 0
        self.target = target
        # Stacks stop accumulating at the cap. Otherwise switching targets
        # after a long burst would incorrectly preserve hidden excess stacks.
        max_hits = int((self.cap / self.per_hit).to_integral_value(rounding=ROUND_FLOOR))
        self.hits = min(max_hits, self.hits + 1)
        return min(self.cap, self.per_hit * self.hits)
