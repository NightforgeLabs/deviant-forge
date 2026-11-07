import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from weapon_mechanics.operators import (Ammo, Cooldown, DamagePacket, HitCounter, SameTargetRamp,
                                 TimedStacks, ammo_blast_coefficient, chance,
                                 independent_expected_procs, proc_with_roll,
                                 independent_expected_procs_with_cooldown,
                                 refund_rounds, reload_seconds, tick_times,
                                 magazine_extra_parts, ammo_fraction_above, delay_bonus)
from weapon_mechanics.runner import WeaponTimeline, load_bindings


class OperatorTests(unittest.TestCase):
    def test_chance_is_relative(self):
        self.assertEqual(chance("0.30", "0.40"), Decimal("0.4200"))
        self.assertTrue(proc_with_roll("0.42", "0.41"))
        self.assertFalse(proc_with_roll("0.42", "0.42"))
        self.assertEqual(independent_expected_procs(10, "0.3"), Decimal("3.0"))

    def test_independent_expected_cooldown_model(self):
        self.assertEqual(independent_expected_procs_with_cooldown(
            [0, 1, 2], [".5", ".5", ".5"], 2), Decimal("1.125"))
        self.assertEqual(independent_expected_procs_with_cooldown(
            [0, 1, 2], [".5", ".5", ".5"], 0), Decimal("1.50"))

    def test_counter_weight_and_overflow(self):
        c = HitCounter(14, "subtract")
        self.assertEqual(sum(c.add(2) for _ in range(7)), 1)
        self.assertEqual(c.count, 0)
        self.assertEqual(c.add(29), 2)
        self.assertEqual(c.count, 1)

    def test_timed_stack_policies_are_explicit(self):
        s = TimedStacks(3, Decimal(5), "independent")
        self.assertEqual(s.add(0), 1)
        self.assertEqual(s.add(2, 3), 3)
        self.assertEqual(s.count(5), 2)
        self.assertEqual(s.count(7), 0)
        a = TimedStacks(2, Decimal(5), "all")
        a.add(0)
        a.add(3)
        self.assertEqual(a.count(6), 2)

    def test_ticks_and_cooldown(self):
        self.assertEqual(tick_times(0, 3, 1, first_delay=1, include_endpoint=True),
                         [Decimal(1), Decimal(2), Decimal(3)])
        self.assertEqual(tick_times(0, 3, 1, first_delay=1, include_endpoint=False),
                         [Decimal(1), Decimal(2)])
        c = Cooldown(Decimal(2))
        self.assertTrue(c.try_trigger(0))
        self.assertFalse(c.try_trigger(1))
        self.assertTrue(c.try_trigger(2))

    def test_ammo_and_reload(self):
        a = Ammo(10, 10)
        self.assertEqual(a.fire(0), 1)
        a.start_unlimited(1, "0.5")
        self.assertEqual(a.fire("1.4"), 0)
        self.assertEqual(a.fire("1.5"), 1)
        self.assertEqual(reload_seconds(3, 50), Decimal(2))
        self.assertEqual(refund_rounds(7, ".75", rounding="floor"), 5)
        self.assertEqual(refund_rounds(7, ".75", rounding="exact"), Decimal("5.25"))

    def test_damage_basis_independent_of_class(self):
        p = DamagePacket("attack", "status", Decimal("1.2"), "frost", True, True)
        self.assertEqual(p.amount(attack=100, psi=300, crit=True, crit_multiplier=2), 240)
        q = DamagePacket("psi", "weapon", Decimal("1.5"), "shock", None, None)
        self.assertEqual(q.amount(attack=100, psi=300), 450)
        with self.assertRaises(ValueError):
            q.amount(attack=100, psi=300, crit=True)

    def test_magazine_threshold_and_delay_rounding(self):
        self.assertEqual(magazine_extra_parts(125, 25, 6), 5)
        self.assertEqual(magazine_extra_parts(200, 25, 6), 6)
        self.assertTrue(ammo_fraction_above(41, 100, ".4"))
        self.assertFalse(ammo_fraction_above(40, 100, ".4"))
        self.assertEqual(delay_bonus("0.25", ".15", rounding="full_tenths"), Decimal("0.30"))
        self.assertEqual(delay_bonus("0.25", ".15", rounding="continuous"), Decimal("0.375"))

    def test_ramp_does_not_accumulate_hidden_excess(self):
        ramp = SameTargetRamp(Decimal(".04"), Decimal(".8"), "halve_floor")
        for _ in range(100):
            ramp.hit("a")
        self.assertEqual(ramp.hits, 20)
        self.assertEqual(ramp.hit("b"), Decimal(".44"))


class FamilyBindingTests(unittest.TestCase):
    def test_evidence_and_assumption_gates(self):
        with self.assertRaisesRegex(ValueError, "preview_simulation"):
            WeaponTimeline("weapon:kam-crank", evidence_mode="dated_release",
                           model_mode="explicit_assumptions")
        with self.assertRaisesRegex(ValueError, "explicit_assumptions"):
            WeaponTimeline("weapon:mps7-outer-space", evidence_mode="dated_release",
                           model_mode="verified_only")
        with self.assertRaisesRegex(ValueError, "preview_simulation"):
            WeaponTimeline("weapon:tec9-additional-rules", evidence_mode="dated_release",
                           model_mode="verified_only")

    def test_missing_status_and_distance_are_not_silently_false(self):
        surge = WeaponTimeline("weapon:mps7-outer-space", evidence_mode="dated_release",
                               model_mode="explicit_assumptions")
        with self.assertRaisesRegex(ValueError, "condition"):
            surge.hit(0, "a", rolls={"power_surge": ".9"})
        eye = WeaponTimeline("weapon:dbsg-doombringer", evidence_mode="dated_release",
                             model_mode="explicit_assumptions")
        with self.assertRaisesRegex(ValueError, "distance"):
            eye.hit(0, "a", rolls={"bullseye": ".9"},
                    conditions={"all_pellets_hit_non_meta_human": False})

    def test_nine_families_present_with_source_and_missing(self):
        bindings = load_bindings()
        families = {w["family"] for w in bindings["weapons"].values()}
        self.assertEqual(families, {"Power Surge", "Shrapnel", "Burn", "Frost Vortex",
                                    "Unstable Bomber", "Bounce", "Fast Gunner",
                                    "Fortress Warfare", "Bull's Eye"})
        for weapon in bindings["weapons"].values():
            self.assertTrue(weapon["missing"])
            for rule in weapon["rules"]:
                self.assertIn(rule["source"], bindings["sources"])

    def test_outer_space_reload_factor_and_affected_target_counter(self):
        w = WeaponTimeline("weapon:mps7-outer-space", evidence_mode="dated_release", model_mode="explicit_assumptions")
        self.assertEqual(w.reload(0)[0]["until"], 6)
        self.assertEqual(w.hit(1, "boss", rolls={"power_surge": ".40"},
                               conditions={"target_affected_by_power_surge": False})[0]["probability"],
                         Decimal("0.420"))
        for i in range(11):
            events = w.hit(1 + i / 10, "boss", rolls={"power_surge": ".99"},
                           conditions={"target_affected_by_power_surge": True})
            self.assertFalse(any(e["event"] == "celestial_lightning" for e in events))
        events = w.hit(3, "boss", rolls={"power_surge": ".99"},
                       conditions={"target_affected_by_power_surge": True})
        self.assertEqual([e["event"] for e in events], ["celestial_lightning"])
        self.assertEqual(w.hit(6, "other", rolls={"power_surge": ".35"},
                               conditions={"target_affected_by_power_surge": False}), [])

    def test_shrapnel_counter_preview(self):
        w = WeaponTimeline("weapon:mg4-conflicting-memories", evidence_mode="historical_release", model_mode="explicit_assumptions")
        events = [e for _ in range(12) for e in w.hit(0, "a")]
        self.assertEqual([e["keyword"] for e in events], ["shrapnel"])

    def test_burn_counter_preview_and_tick_schedule(self):
        w = WeaponTimeline("weapon:kam-crank", evidence_mode="preview_simulation", model_mode="explicit_assumptions")
        events = [e for _ in range(7) for e in w.hit(0, "a")]
        self.assertEqual([e["keyword"] for e in events], ["burn"])
        self.assertEqual(tick_times(0, 4, 1, first_delay=1, include_endpoint=False),
                         [Decimal(1), Decimal(2), Decimal(3)])

    def test_frost_weakspots_weight_two(self):
        w = WeaponTimeline("weapon:kam-abyss-glance", evidence_mode="dated_release", model_mode="explicit_assumptions")
        events = [e for _ in range(7) for e in w.hit(0, "a", weakspot=True)]
        self.assertEqual([e["keyword"] for e in events], ["frost_vortex"])

    def test_hazardous_ammo_blast_and_refund_branch(self):
        w = WeaponTimeline("weapon:g17-hazardous-object", evidence_mode="dated_release", model_mode="explicit_assumptions", magazine=20)
        for _ in range(10):
            w.ammo.fire(0)
        events = w.reload(1, refund_roll=".2", refund_rounding="floor")
        self.assertEqual(events[0]["coefficient"], Decimal("2.30"))
        self.assertEqual(events[0]["basis"], "psi")
        self.assertIsNone(events[0]["damage_class"])
        self.assertEqual(events[1]["rounds"], 7)
        self.assertEqual(w.ammo.rounds, 0)  # source does not specify refill placement
        self.assertEqual(ammo_blast_coefficient(30, base=.5, per_round=.18, cap=4.8), Decimal("4.8"))

    def test_bounce_proc(self):
        w = WeaponTimeline("weapon:mps5-blue-tiger", evidence_mode="dated_release", model_mode="explicit_assumptions")
        self.assertEqual(w.hit(0, "a", rolls={"bounce": ".2"})[0]["keyword"], "bounce")
        self.assertEqual(w.hit(1, "a", rolls={"bounce": ".3"}), [])

    def test_fast_gunner_ramp_and_stack_milestone(self):
        w = WeaponTimeline("weapon:mg4-predator", evidence_mode="dated_release", model_mode="explicit_assumptions", magazine=100)
        for i in range(3):
            events = w.hit(i, "a", rolls={"fast_gunner": ".9"})
        self.assertEqual(events[0]["additive_fraction"], Decimal("0.12"))
        events = w.hit(3, "b", rolls={"fast_gunner": ".9"})
        self.assertEqual(events[0]["additive_fraction"], Decimal("0.08"))
        self.assertEqual(w.observe_keyword_stacks(4, "fast_gunner", 5)[0]["until"], Decimal("4.5"))
        self.assertEqual(w.ammo.fire("4.4"), 0)
        self.assertEqual(w.ammo.fire("4.5"), 1)

    def test_fortress_cooldown(self):
        w = WeaponTimeline("weapon:tec9-additional-rules", evidence_mode="preview_simulation", model_mode="explicit_assumptions")
        self.assertEqual(len(w.hit(0, "a")), 1)
        self.assertEqual(w.hit(9, "a"), [])
        self.assertEqual(len(w.hit(10, "a")), 1)

    def test_bullseye_near_and_timed_pellet_stacks(self):
        w = WeaponTimeline("weapon:dbsg-doombringer", evidence_mode="dated_release", model_mode="explicit_assumptions")
        events = w.hit(0, "a", distance=8, rolls={"bullseye": ".7"},
                       conditions={"all_pellets_hit_non_meta_human": True})
        self.assertEqual(events[0]["probability"], Decimal("0.8"))
        self.assertEqual(events[1]["additive_fraction"], Decimal("0.12"))
        self.assertEqual(w.hit(1, "a", distance=9, rolls={"bullseye": ".7"},
                               conditions={"all_pellets_hit_non_meta_human": False}), [])
        self.assertEqual(w.stacks["pellet_attack_ramp"].count(15), 0)

    def test_supersessions_are_dated_and_not_applied_to_old_files(self):
        data = load_bindings()
        by_id = {x["weapon_id"]: x for x in data["supersessions"]}
        self.assertEqual(by_id["weapon:kv-sbr-little-jaws"]["newer"], .15)
        self.assertEqual(by_id["weapon:r500-memento"]["newer"], 1.0)
        self.assertEqual(by_id["weapon:r500-memento"]["newer_source"], "feb25_release")


if __name__ == "__main__":
    unittest.main()
