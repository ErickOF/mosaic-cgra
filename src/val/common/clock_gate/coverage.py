"""ClockGate coverage components for specification-based PyUVM validation."""

from bisect import bisect_left, bisect_right
from itertools import product, zip_longest
import cocotb
from clock_gate.constants import CONTROLS
from mosaic_uvm.components import CoverageCollector


class ClockGateCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.expected_changes = []
        self.output_changes = []
        self.source_edges = []
        self.requests = []
        self.decisions = []
        self.combinations = set()
        self.unknown_controls = set()
        self.half_cycle_transitions = set()
        self.snapshots = 0

    def report(self):
        actual = [(edge.time_ps, edge.previous, edge.current) for edge in self.output_changes]
        # This comparison rejects extra edges even when the settled value and
        # the total number of propagated cycles happen to be correct.
        mismatch = next((pair for pair in zip_longest(actual, self.expected_changes) if pair[0] != pair[1]), None)
        assert mismatch is None, (
            f"Output transition history differs from the independent model: "
            f"actual={mismatch[0]}, expected={mismatch[1]}"
        )
        high_widths, low_widths = [], []
        rise, fall = None, None
        for edge in self.output_changes:
            if (edge.previous, edge.current) == ("0", "1"):
                assert edge.source_level == "1", "Output rose while source clock was low"
                assert (edge.time_ps, "rise") in self.source_edges, "Output rose without a source rising edge"
                if fall is not None:
                    low_widths.append(edge.time_ps - fall)
                    assert low_widths[-1] >= self.config.half_ps, "Output low pulse is too short"
                rise = edge.time_ps
            elif (edge.previous, edge.current) == ("1", "0"):
                assert edge.source_level == "0", "Output fell while source clock was high"
                assert (edge.time_ps, "fall") in self.source_edges, "Output fell without a source falling edge"
                assert rise is not None, "Output high pulse has no rising edge"
                high_widths.append(edge.time_ps - rise)
                assert high_widths[-1] == self.config.half_ps, "Output high pulse was truncated or extended"
                fall, rise = edge.time_ps, None
            else:
                # Illegal controls may produce X; their exact four-state
                # transitions are checked above, not counted as legal pulses.
                rise, fall = None, None
        assert rise is None, "Simulation ended with an incomplete output pulse"

        near_edges = set()
        source_times = [time for time, _ in self.source_edges]
        rise_times = [decision["time_ps"] for decision in self.decisions]
        for request in self.requests:
            time = request["time_ps"]
            for edge_time, edge_kind in self.source_edges[bisect_left(source_times, time - 1):bisect_right(source_times, time + 1)]:
                if abs(edge_time - time) == 1:
                    near_edges.add((request["control"], request["requested_value"], edge_kind,
                                    "before" if time < edge_time else "after"))
            following_index = bisect_right(rise_times, time)
            following = self.decisions[following_index] if following_index < len(self.decisions) else None
            request["next_source_rise_ps"] = following["time_ps"] if following else None
            request["next_pulse_propagated"] = following["actual_output"] if following else None

        runs = []
        for decision in self.decisions:
            value = decision["captured_enable"]
            if runs and runs[-1][0] == value:
                runs[-1][1] += 1
            else:
                runs.append([value, 1])
        enabled_runs = [length for value, length in runs if value == "1"]
        disabled_runs = [length for value, length in runs if value == "0"]
        consecutive_changes = 0
        longest_changes = 0
        for previous, current in zip(self.decisions, self.decisions[1:]):
            changed = {previous["captured_enable"], current["captured_enable"]} == {"0", "1"}
            consecutive_changes = consecutive_changes + 1 if changed else 0
            longest_changes = max(longest_changes, consecutive_changes)
        random_cycles = sum(decision["label"].startswith("random_") for decision in self.decisions)
        scan_values = {
            decision["enable"] for decision in self.decisions
            if decision["label"].startswith("scan_") and decision["test_enable"] == "1"
            and decision["actual_output"] == "1"
        }
        goals = {
            "startup": self.decisions[0]["actual_output"] == str(int(self.config.startup_enabled)),
            "control_half_cycle_transitions": set(product(CONTROLS, ("0", "1"), ("low", "high"))) <= self.half_cycle_transitions,
            "control_combinations": set(product(("0", "1"), repeat=2)) <= self.combinations,
            "near_both_edges": set(product(CONTROLS, ("0", "1"), ("rise", "fall"), ("before", "after"))) <= near_edges,
            "zero_propagated_pulses": bool(disabled_runs),
            "one_propagated_pulse": 1 in enabled_runs,
            "multiple_propagated_pulses": max(enabled_runs, default=0) >= 3,
            "short_disabled_interval": any(length <= 2 for length in disabled_runs),
            "long_disabled_interval": max(disabled_runs, default=0) >= 64,
            "long_enabled_interval": max(enabled_runs, default=0) >= 64,
            "back_to_back_gating": longest_changes >= 4,
            "scan_override": scan_values == {"0", "1"},
            "random_activity": random_cycles >= self.config.random_cycles,
            "unknown_controls": set(product(CONTROLS, ("x", "z"), ("0", "1"), ("low", "high"))) <= self.unknown_controls,
            "complete_output_pulses": bool(high_widths) and len(high_widths) == sum(
                (edge.previous, edge.current) == ("0", "1") for edge in self.output_changes
            ),
        }
        return {
            "status": "PASS" if all(goals.values()) else "FAIL",
            "startup_enabled": self.config.startup_enabled,
            "seed": self.config.seed, "simulator": cocotb.SIM_NAME,
            "source_cycles": len(self.decisions), "random_cycles": random_cycles,
            "snapshots_checked": self.snapshots,
            "output_transitions_checked": len(actual), "complete_high_pulses": len(high_widths),
            "high_width_ps": {"minimum": min(high_widths, default=0), "maximum": max(high_widths, default=0)},
            "minimum_low_width_ps": min(low_widths, default=0),
            "expected_control_diagnostics": len(self.unknown_controls),
            "longest_enabled_interval": max(enabled_runs, default=0),
            "longest_disabled_interval": max(disabled_runs, default=0),
            "goals": goals,
            "bins": {
                "control_transitions": sorted(self.half_cycle_transitions),
                "control_combinations": sorted(self.combinations),
                "near_edges": sorted(near_edges), "unknown_controls": sorted(self.unknown_controls),
            },
            "requested_transitions": self.requests,
            "source_pulse_decisions": self.decisions,
        }
