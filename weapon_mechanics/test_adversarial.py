import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from weapon_mechanics.operators import (
    D, Ammo, Cooldown, DamagePacket, HitCounter, SameTargetRamp, TimedStacks,
    chance, independent_expected_procs_with_cooldown, tick_times,
)
from weapon_mechanics.runner import MAX_DERIVED_EVENTS, WeaponTimeline


def timeline(weapon_id, *, magazine=None, preview=False):
    return WeaponTimeline(weapon_id,
                          evidence_mode="preview_simulation" if preview else "dated_release",
                          model_mode="explicit_assumptions", magazine=magazine)


class AdversarialOperators(unittest.TestCase):
    def test_simultaneous_reload_hit_order_is_call_order(self):
        first_reload = timeline("weapon:mps7-outer-space")
        first_reload.reload(2, input_id="reload")
        events = first_reload.hit(2, "boss", rolls={"power_surge": ".35"},
                                  conditions={"target_affected_by_power_surge": False},
                                  input_id="hit")
        self.assertEqual(events[0]["probability"], Decimal(".420"))

        first_hit = timeline("weapon:mps7-outer-space")
        self.assertEqual(first_hit.hit(2, "boss", rolls={"power_surge": ".35"},
                                       conditions={"target_affected_by_power_surge": False},
                                       input_id="hit"), [])
        first_hit.reload(2, input_id="reload")
        self.assertEqual(first_hit.hit(2, "boss", rolls={"power_surge": ".35"},
                                       conditions={"target_affected_by_power_surge": False},
                                       input_id="next")[0]["probability"], Decimal(".420"))

    def test_delayed_ticks_and_exact_endpoint(self):
        self.assertEqual(tick_times(10, 3, 1, first_delay=1, include_endpoint=True),
                         [Decimal(11), Decimal(12), Decimal(13)])
        self.assertEqual(tick_times(10, 3, 1, first_delay=1, include_endpoint=False),
                         [Decimal(11), Decimal(12)])
        self.assertEqual(tick_times(0, 0, 1, first_delay=0, include_endpoint=True), [Decimal(0)])
        self.assertEqual(tick_times(0, 0, 1, first_delay=0, include_endpoint=False), [])
        self.assertEqual(tick_times(0, 1, 1, first_delay=2, include_endpoint=True), [])

    def test_cooldown_expiry_boundary_and_reduce(self):
        cd = Cooldown(Decimal(10))
        self.assertTrue(cd.try_trigger(0))
        self.assertFalse(cd.try_trigger("9.999999"))
        self.assertTrue(cd.try_trigger(10))
        cd.reduce(12, 3)
        self.assertEqual(cd.ready_at, 17)
        self.assertFalse(cd.try_trigger(16))
        self.assertTrue(cd.try_trigger(17))

    def test_counter_subtract_and_reset_are_different(self):
        subtract = HitCounter(12, "subtract")
        reset = HitCounter(12, "reset")
        self.assertEqual(subtract.add(25), 2)
        self.assertEqual(subtract.count, 1)
        self.assertEqual(reset.add(25), 1)
        self.assertEqual(reset.count, 0)
        self.assertEqual(HitCounter(12, "subtract").add(0), 0)

    def test_stack_expiry_refresh_and_replace_oldest(self):
        independent = TimedStacks(2, Decimal(3), "independent")
        independent.add(0)
        independent.add(2)
        self.assertEqual(independent.count(3), 1)
        self.assertEqual(independent.count(5), 0)
        all_refresh = TimedStacks(2, Decimal(3), "all")
        all_refresh.add(0)
        all_refresh.add(2)
        self.assertEqual(all_refresh.count(3), 2)
        self.assertEqual(all_refresh.count(5), 0)
        oldest = TimedStacks(2, Decimal(3), "replace_oldest")
        oldest.add(0)
        oldest.add(1)
        oldest.add(2)
        self.assertEqual(oldest.count(3), 2)
        self.assertEqual(oldest.count(4), 1)

    def test_no_implicit_reserve_ammo_or_blast_refill(self):
        ammo = Ammo(10, 10)
        ammo.fire(0, 4)
        with self.assertRaises(TypeError):
            ammo.reload()  # no implicit full-magazine refill
        self.assertEqual(ammo.rounds, 6)
        self.assertEqual(ammo.reload(2), 2)
        self.assertEqual(ammo.rounds, 8)
        self.assertEqual(ammo.reload(20), 2)
        self.assertEqual(ammo.rounds, 10)

        ordinary = timeline("weapon:mg4-predator", magazine=10)
        ordinary.ammo.fire(0, 4)
        with self.assertRaisesRegex(ValueError, "loaded_rounds"):
            ordinary.reload(1)
        self.assertEqual(ordinary.ammo.rounds, 6)
        self.assertEqual(ordinary.reload(1, loaded_rounds=2, input_id="r")[0]["rounds"], 2)
        self.assertEqual(ordinary.ammo.rounds, 8)

        blast = timeline("weapon:g17-hazardous-object", magazine=10)
        blast.ammo.fire(0, 3)
        events = blast.reload(1, refund_roll=".1", refund_rounding="floor", input_id="r")
        self.assertEqual(blast.ammo.rounds, 0)
        self.assertEqual(events[0]["consumed_ammo"], 7)
        self.assertEqual(events[1]["rounds"], 5)
        self.assertEqual(blast.ammo.reload(events[1]["rounds"]), 5)
        self.assertEqual(blast.ammo.rounds, 5)

    def test_negative_and_nonfinite_values_are_rejected(self):
        for value in (float("nan"), float("inf"), float("-inf"), "NaN", "Infinity"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                D(value)
        with self.assertRaises(ValueError):
            chance("NaN", 0)
        with self.assertRaises(ValueError):
            tick_times(-1, 1, 1, first_delay=0, include_endpoint=False)
        with self.assertRaises(ValueError):
            Ammo(10, 10).start_unlimited(0, -1)
        with self.assertRaises(ValueError):
            Ammo(10, 10).reload(-1)
        with self.assertRaises(ValueError):
            TimedStacks(2, Decimal(1), "unknown")
        with self.assertRaises(ValueError):
            HitCounter(2, "unknown")
        with self.assertRaises(ValueError):
            DamagePacket("attack", "status", Decimal("1")).amount(
                attack=100, psi=0, multiplicative_bonus=-1)
        with self.assertRaises(ValueError):
            SameTargetRamp(Decimal(".1"), Decimal("1"), "unknown")
        for factory in (lambda: Ammo(10, float("inf")),
                        lambda: Ammo(10, 10).reload(float("inf")),
                        lambda: HitCounter(2, "subtract").add(float("inf")),
                        lambda: TimedStacks(2, Decimal(1), "all").add(0, float("inf"))):
            with self.assertRaises(ValueError):
                factory()

    def test_runaway_schedules_and_expected_states_are_bounded(self):
        with self.assertRaisesRegex(ValueError, "tick limit"):
            tick_times(0, 100, ".001", first_delay=0, include_endpoint=True, max_ticks=10)
        with self.assertRaisesRegex(ValueError, "hit limit"):
            independent_expected_procs_with_cooldown(list(range(11)), [".5"] * 11,
                                                     1, max_hits=10)


class AdversarialRunner(unittest.TestCase):
    def test_stream_scopes_ids_and_reload_retry_does_not_refill_again(self):
        left = WeaponTimeline("weapon:mg4-predator", "dated_release",
                              "explicit_assumptions", magazine=10, stream_id="build-left")
        right = WeaponTimeline("weapon:mg4-predator", "dated_release",
                               "explicit_assumptions", magazine=10, stream_id="build-right")
        for w in (left, right):
            w.ammo.fire(0, 4)
        first = left.reload(1, loaded_rounds=2, input_id="reload-1")
        self.assertEqual(left.reload(1, loaded_rounds=2, input_id="reload-1"), first)
        self.assertEqual(left.ammo.rounds, 8)
        second = right.reload(1, loaded_rounds=2, input_id="reload-1")
        self.assertNotEqual(first[0]["event_id"], second[0]["event_id"])

    def test_same_input_id_is_idempotent_without_counter_double_count(self):
        w = timeline("weapon:kam-abyss-glance")
        for i in range(6):
            w.hit(i, "boss", weakspot=True, input_id=f"hit-{i}")
        first = w.hit(6, "boss", weakspot=True, input_id="seventh")
        self.assertEqual(len(first), 1)
        self.assertEqual(first[0]["effect_type"], "keyword_trigger")
        second = w.hit(6, "boss", weakspot=True, input_id="seventh")
        self.assertEqual(second, first)
        self.assertEqual(w.counters[("frost_vortex", "all")].count, 0)
        with self.assertRaisesRegex(ValueError, "different payload"):
            w.hit(6, "other", weakspot=True, input_id="seventh")

    def test_damage_trigger_and_keyword_trigger_are_distinct(self):
        w = timeline("weapon:mps7-outer-space")
        for i in range(11):
            w.hit(i, "boss", rolls={"power_surge": ".99"},
                  conditions={"target_affected_by_power_surge": True}, input_id=f"h{i}")
        events = w.hit(11, "boss", rolls={"power_surge": ".1"},
                       conditions={"target_affected_by_power_surge": True}, input_id="both")
        self.assertEqual([e["effect_type"] for e in events],
                         ["keyword_trigger", "damage_trigger"])
        self.assertEqual(len({e["event_id"] for e in events}), 2)
        self.assertEqual(w.hit(11, "boss", rolls={"power_surge": ".1"},
                               conditions={"target_affected_by_power_surge": True},
                               input_id="both"), events)

    def test_failed_prevalidation_does_not_mutate_state(self):
        w = timeline("weapon:mps7-outer-space")
        with self.assertRaisesRegex(ValueError, "condition"):
            w.hit(5, "a", rolls={"power_surge": ".1"}, input_id="bad")
        self.assertEqual(w.last_at, -1)
        self.assertEqual(w.counters, {})
        self.assertEqual(w.hit(0, "a", rolls={"power_surge": ".1"},
                               conditions={"target_affected_by_power_surge": False},
                               input_id="good")[0]["event"], "power_surge")

    def test_time_order_and_expiry_boundary(self):
        w = timeline("weapon:tec9-additional-rules", preview=True)
        self.assertEqual(len(w.hit(0, "a")), 1)
        self.assertEqual(w.hit("9.999", "a"), [])
        self.assertEqual(len(w.hit(10, "a")), 1)
        with self.assertRaisesRegex(ValueError, "time order"):
            w.hit(9, "a")

    def test_required_condition_and_branch_inputs_are_typed(self):
        w = timeline("weapon:mps7-outer-space")
        with self.assertRaisesRegex(ValueError, "boolean"):
            w.hit(0, "a", weakspot=1, rolls={"power_surge": ".1"},
                  conditions={"target_affected_by_power_surge": False})
        with self.assertRaisesRegex(ValueError, "boolean"):
            w.hit(0, "a", rolls={"power_surge": ".1"},
                  conditions={"target_affected_by_power_surge": "false"})
        with self.assertRaisesRegex(ValueError, "refund inputs"):
            w.reload(0, refund_roll=".1")
        with self.assertRaisesRegex(ValueError, "unknown keyword"):
            w.observe_keyword_stacks(0, "fast_gunner", 5)
        with self.assertRaisesRegex(ValueError, "tick schedule"):
            tick_times(0, 2, 1, first_delay=0, include_endpoint=1)

    def test_stack_milestone_duplicate_not_extended(self):
        w = timeline("weapon:mg4-predator", magazine=30)
        first = w.observe_keyword_stacks(1, "fast_gunner", 5, input_id="stack-five")
        self.assertEqual(first[0]["until"], Decimal("1.5"))
        self.assertEqual(w.observe_keyword_stacks(1, "fast_gunner", 5,
                                                   input_id="stack-five"), first)
        self.assertEqual(w.ammo.unlimited_until, Decimal("1.5"))
        self.assertEqual(w.observe_keyword_stacks(2, "fast_gunner", 5,
                                                   input_id="same-count"), [])
        second = w.observe_keyword_stacks(2, "fast_gunner", 10,
                                          input_id="stack-ten")
        self.assertEqual(len(second), 1)
        self.assertNotEqual(first[0]["event_id"], second[0]["event_id"])

    def test_no_recursive_trigger_and_large_stack_guard(self):
        w = timeline("weapon:mps7-outer-space")
        for i in range(11):
            w.hit(i, "a", rolls={"power_surge": ".99"},
                  conditions={"target_affected_by_power_surge": True})
        # Both events occur on one hit; derived lightning is never fed back as a hit.
        events = w.hit(11, "a", rolls={"power_surge": ".1"},
                       conditions={"target_affected_by_power_surge": True})
        self.assertEqual(len(events), 2)
        self.assertEqual(w.counters[("celestial_lightning", "a")].count, 0)
        fast = timeline("weapon:mg4-predator", magazine=30)
        with self.assertRaisesRegex(ValueError, "event limit"):
            fast.observe_keyword_stacks(1, "fast_gunner", (MAX_DERIVED_EVENTS + 1) * 5)
        self.assertEqual(fast.ammo.unlimited_until, 0)
        self.assertEqual(fast.last_stack_count, {})


if __name__ == "__main__":
    unittest.main()
