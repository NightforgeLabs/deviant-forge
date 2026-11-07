"""Source-qualified packet arithmetic layered beside the frozen v2 event runner.

Only base packets and explicitly selected factors are computed. Game defense,
resistance, modifier grouping, and unresolved target mechanics are not invented.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from .operators import D, I, ammo_blast_coefficient


def load_damage_bindings() -> dict:
    return json.loads((Path(__file__).parent / "damage_bindings_v3.json").read_text())


@dataclass(frozen=True)
class PacketResult:
    packet_id: str
    event_id: str
    evidence_status: str
    basis: str
    damage_class: str | None
    element: str | None
    coefficient: Decimal
    instances: int
    raw_damage: Decimal
    source_only_total: Decimal
    total_with_external: Decimal
    applied_factors: tuple[str, ...]
    unresolved: tuple[str, ...]


def project_event(packet_id: str, event: dict, *, attack=None, psi=None,
                  references: dict | None = None, evidence_mode: str,
                  pvp: bool = False, include_intrinsic_bonus: bool = False,
                  crit_multiplier=None, weakspot_multiplier=None,
                  external_multiplier=1, external_multiplier_label: str | None = None) -> PacketResult:
    """Compute one resolved damage event under explicitly named source/scenario choices.

    ``external_multiplier`` is caller-aggregated; this module has no game bonus
    grouping rule. A non-unit factor needs a label naming that assumption/model.
    """
    catalog = load_damage_bindings()
    spec = catalog["packets"][packet_id]
    if evidence_mode not in {"dated_release", "preview_simulation", "historical_release"}:
        raise ValueError("select dated_release, preview_simulation or historical_release")
    source_status = catalog["sources"][spec["coefficient_source"]]["status"]
    if "preview" in source_status and evidence_mode != "preview_simulation":
        raise ValueError("preview coefficient requires preview_simulation")
    if not isinstance(event, dict) or event.get("event") != spec["event"]:
        raise ValueError("event does not match packet binding")
    if spec["weapon_id"] is not None and event.get("weapon_id") != spec["weapon_id"]:
        raise ValueError("weapon does not match packet binding")
    if spec["requires_resolved_hit"] and event.get("resolved_hit") is not True:
        raise ValueError("resolved_hit required; a proc is not a damage hit")
    if event.get("effect_type") == "keyword_trigger":
        raise ValueError("keyword trigger cannot be counted as damage")
    event_id = event.get("event_id")
    if not isinstance(event_id, str) or not event_id:
        raise ValueError("stable event_id required")
    if spec.get("requires_target_count"):
        if "target_count" not in event:
            raise ValueError("explicit target_count required for AoE blast")
        target_count = I(event["target_count"], name="target_count")
        if "instances" in event and event["instances"] != target_count:
            raise ValueError("instances and target_count disagree")
        instances = target_count
    else:
        instances = I(event.get("instances", 1), name="instances")
    if not 0 <= instances <= 10000:
        raise ValueError("invalid instance count")
    if not isinstance(pvp, bool) or not isinstance(include_intrinsic_bonus, bool):
        raise ValueError("scenario switches must be boolean")

    coefficient_spec = spec["coefficient"]
    if coefficient_spec["kind"] == "constant":
        coefficient = D(coefficient_spec["value"])
    elif coefficient_spec["kind"] == "affine_capped_ammo":
        field_name = coefficient_spec["ammo_field"]
        if field_name not in event:
            raise ValueError(f"{field_name} required")
        coefficient = ammo_blast_coefficient(
            event[field_name], base=coefficient_spec["base"],
            per_round=coefficient_spec["per_round"], cap=coefficient_spec["cap"])
    else:
        raise ValueError("unsupported coefficient expression")
    if coefficient < 0:
        raise ValueError("negative coefficient")
    if "coefficient" in event and D(event["coefficient"]) != coefficient:
        raise ValueError("timeline coefficient disagrees with packet source")

    basis = spec["basis"]
    if basis == "attack":
        basis_value = attack
    elif basis == "psi":
        basis_value = psi
    elif basis == "reference_damage":
        basis_value = (references or {}).get(spec["reference_key"])
    else:
        raise ValueError("unsupported damage basis")
    if basis_value is None:
        raise ValueError(f"caller-supplied {basis} value required")
    basis_value = D(basis_value)
    if basis_value < 0:
        raise ValueError("negative damage basis")
    raw = basis_value * coefficient * instances
    total = raw
    factors = []
    if include_intrinsic_bonus:
        bonus = spec["intrinsic_bonus_fraction"]
        if bonus is None:
            raise ValueError("packet has no evidenced intrinsic bonus")
        bonus_source_status = catalog["sources"][spec["bonus_source"]]["status"]
        if "preview" in bonus_source_status and evidence_mode != "preview_simulation":
            raise ValueError("preview bonus requires preview_simulation")
        total *= 1 + D(bonus)
        factors.append("isolated_intrinsic_bonus_no_other_same_group_mods")
    if pvp:
        if spec["pvp_multiplier"] is None:
            raise ValueError("PvP multiplier is unresolved")
        total *= D(spec["pvp_multiplier"])
        factors.append("source_pvp_multiplier")
    source_only = total
    for name, multiplier, eligibility in (
        ("crit", crit_multiplier, spec["crit_eligible"]),
        ("weakspot", weakspot_multiplier, spec["weakspot_eligible"]),
    ):
        if multiplier is not None:
            if eligibility is not True:
                raise ValueError(f"{name} eligibility unresolved or false")
            if D(multiplier) < 0:
                raise ValueError(f"negative {name} multiplier")
            total *= D(multiplier)
            factors.append(f"caller_{name}_multiplier")
    external = D(external_multiplier)
    if external < 0:
        raise ValueError("negative external multiplier")
    if external != 1:
        if not isinstance(external_multiplier_label, str) or not external_multiplier_label.strip():
            raise ValueError("non-unit external multiplier needs a model label")
        total *= external
        factors.append(f"external:{external_multiplier_label}")
    unresolved = list(spec["unresolved"])
    if spec["intrinsic_bonus_fraction"] is not None and not include_intrinsic_bonus:
        unresolved.append("available_intrinsic_bonus_not_applied")
    return PacketResult(packet_id, event_id, source_status, basis,
                        spec["damage_class"], spec["element"], coefficient,
                        instances, raw, source_only, total,
                        tuple(factors), tuple(unresolved))


def project_events(items: list[tuple[str, dict]], **kwargs) -> tuple[Decimal, list[PacketResult]]:
    """Sum resolved effects; reject generic/specific bindings for the same hit."""
    seen = set()
    results = []
    catalog = load_damage_bindings()["packets"]
    for packet_id, event in items:
        effect_slot = catalog[packet_id]["event"]
        identity = (event.get("event_id") if isinstance(event, dict) else None,
                    effect_slot)
        if identity in seen:
            raise ValueError("duplicate effect slot for event")
        seen.add(identity)
        results.append(project_event(packet_id, event, **kwargs))
    return sum((result.total_with_external for result in results), D(0)), results


def packet_dps(total_damage, *, duration_seconds) -> Decimal:
    """Explicit-denominator scenario DPS; no firing window is inferred."""
    total, duration = D(total_damage), D(duration_seconds)
    if total < 0 or duration <= 0:
        raise ValueError("DPS needs nonnegative damage and positive duration")
    return total / duration
