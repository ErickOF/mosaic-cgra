"""ResetSynchronizer scoreboard components for specification-based PyUVM validation."""

from __future__ import annotations

from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from reset_synchronizer.model import reset_negedge
from reset_synchronizer.transaction import Activity


class ResetSynchronizerScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.coverage = ConfigDB().get(self, "", "coverage")
        self.analysis_export = uvm_analysis_export("analysis_export", self)
        self.analysis_export.write = self.write
        self.previous = None
        self.base, self.edges = "0", 0


        self.last_clock = self.last_reset = None
        self.last_assertion = None


    def expected_stages(self) -> str:
        # Count elapsed qualifying edges rather than duplicating the RTL shift.
        return self.base * (self.config.stages - self.edges) + "1" * self.edges

    def next_state(self, clk, rstb):
        old_clk, old_reset = (self.previous.clk, self.previous.rstb) if self.previous else ("0", "0")
        if rstb == "0":
            return "0", 0
        if old_clk == "0" and clk == "1" or reset_negedge(old_reset, rstb):
            return (self.base, min(self.config.stages, self.edges + 1)) if rstb == "1" else ("x", 0)
        return self.base, self.edges

    def write(self, observation):
        if isinstance(observation, Activity):
            assert observation.allowed, f"Out-of-event activity changed {observation.signal} to {observation.value}"
            base, edges = self.next_state(observation.clk, observation.rstb)
            predicted = base * (self.config.stages - edges) + "1" * edges
            expected = predicted[0] if observation.signal == "o_rstb" else predicted
            assert observation.value == expected, f"Event waveform violated stage latency/clear: {observation.signal}={observation.value}, expected={expected}"
            if observation.rstb == "0":
                assert set(observation.value) <= {"0"}, "Reset assertion did not clear output/stages"
            if observation.signal == "o_rstb" and observation.value == "1":
                assert observation.rstb == "1" and observation.clk == "1" and observation.rising_clock, "Reset released asynchronously or without a rising clock"
            self.coverage.transitions[observation.signal] += 1
            return
        config, item = self.config, observation.item
        assert observation.clk == str(item.clk) and observation.rstb == item.rstb, "Clock/reset stimulus was coerced"
        illegal = observation.rstb if observation.rstb in "xz" else None
        try:
            assert illegal is None, f"Unknown-reset assertion failed: i_async_rstb={illegal}"
        except AssertionError:
            if item.expected_unknown != illegal:
                raise
            if observation.stage == "settled":
                if illegal not in self.coverage.unknowns:
                    self.logger.info("Expected unknown-reset assertion: i_async_rstb=%s", illegal)
                self.coverage.unknowns.add(illegal)
                self.coverage.unknown_violations += 1
        else:
            assert item.expected_unknown is None, "Expected unknown reset became known"
        if observation.stage == "held":
            self.coverage.held_checks += 1
            self.check_outputs(observation)
            return
        assert observation.stage == "settled"
        previous = self.previous
        old_clk, old_reset = (previous.clk, previous.rstb) if previous else ("0", "0")
        rising = old_clk == "0" and observation.clk == "1"
        falling = old_clk == "1" and observation.clk == "0"
        reset_change = old_reset != observation.rstb
        before_edges = self.edges
        self.base, self.edges = self.next_state(observation.clk, observation.rstb)
        self.check_outputs(observation)
        self.coverage.checks += 1
        self.coverage.random_checks += observation.label.startswith("random_")
        if observation.rstb == "1":
            self.coverage.progress.add(self.edges)
        if previous and previous.output != "1" and observation.output == "1":
            self.coverage.releases += 1
            self.coverage.release_counts.add(self.edges)
            assert rising and self.edges == config.stages, "Release skipped synchronization stages"
        kind = "assert" if observation.rstb == "0" else "deassert" if observation.rstb == "1" else None
        if reset_change and kind:
            phase = "high" if observation.clk == "1" else "low"
            self.coverage.phases.add((kind, phase))
            self.coverage.contexts.add((kind, item.context))
            if rising or falling:
                self.coverage.phases.add((kind, "on_rise" if rising else "on_fall"))
            elif self.last_clock and 0 < observation.time_ps - self.last_clock[0] <= config.near_ps:
                self.coverage.phases.add((kind, "after_" + self.last_clock[1]))
            self.last_reset = observation.time_ps, kind
            if kind == "assert":
                self.last_assertion = observation.time_ps, observation.clk
                if old_reset == "1":
                    self.coverage.reassertions.add((before_edges, observation.clk))
                if not rising and not falling:
                    self.coverage.asynchronous_assertions += 1
            elif self.last_assertion:
                duration = observation.time_ps - self.last_assertion[0]
                if duration == config.pulse_ps:
                    self.coverage.pulses.add(self.last_assertion[1])
        if rising or falling:
            edge = "rise" if rising else "fall"
            if self.last_reset and 0 < observation.time_ps - self.last_reset[0] <= config.near_ps:
                self.coverage.phases.add((self.last_reset[1], "before_" + edge))
            self.last_clock = observation.time_ps, edge
        if item.context == "stopped":
            assert old_clk == observation.clk and item.duration_ps >= 2 * config.period_ps, "Stopped-clock scenario did not stop/hold the clock"
            if observation.rstb == "1" and self.edges < config.stages:
                self.coverage.stops.add((self.edges, observation.clk))
        if illegal and reset_change:
            self.coverage.unknown_sources.add((old_reset, illegal))
        self.previous = observation

    def check_outputs(self, observation):
        expected = self.expected_stages()
        assert observation.output == expected[0], (
            f"{observation.label}/{observation.stage}: reset={observation.rstb}, edges={self.edges}, "
            f"output={observation.output}, expected={expected[0]}"
        )
        if observation.stages is not None:
            assert observation.stages == expected, f"Stage progression/clear failed: stages={observation.stages}, expected={expected}"
            assert observation.output == observation.stages[0], "Output does not track the final stage"
