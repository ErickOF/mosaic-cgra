"""Dff scoreboard components for specification-based PyUVM validation."""

from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from dff.model import illegal_control
from dff.transaction import OutputChange, Snapshot


class DffScoreboard(uvm_scoreboard):
    """Model only specified clock/reset events; audit the entire output waveform."""

    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.coverage = ConfigDB().get(self, "", "coverage")
        self.analysis_export = uvm_analysis_export("analysis_export", self)
        self.analysis_export.write = self.write
        self.previous = None


        self.pending_reset = None
        self.run_command = None

        self.run_length = 0


    def write(self, observation):
        if isinstance(observation, OutputChange):
            self.coverage.output_changes.append(observation)
            return
        assert isinstance(observation, Snapshot)
        config, previous = self.config, self.previous
        self.coverage.checks += 1
        assert observation.clk in ("0", "1"), "The functional clock must be known"
        if observation.requested:
            requested = observation.requested
            assert (observation.clk, observation.rstb, observation.enable, observation.data) == (
                str(requested.clk), str(requested.rstb).lower(), str(requested.enable).lower(),
                requested.data_bits(config.width),
            ), "Stimulus did not reach the DUT without four-state coercion"
        rising = previous is not None and previous.clk == "0" and observation.clk == "1"
        reset_assert = previous is not None and previous.rstb != "0" and observation.rstb == "0"
        reset_release = previous is not None and previous.rstb == "0" and observation.rstb == "1"
        before, command = self.coverage.state, None
        if config.async_reset and observation.rstb not in ("0", "1"):
            # An illegal asynchronous reset has no specified numeric behavior.
            self.coverage.state = None
        if rising:
            violation = illegal_control(observation.rstb, observation.enable, config.has_enable)
            assert violation == observation.expected_unknown, (
                f"{observation.label}: known-control assertion {violation}, "
                f"expected {observation.expected_unknown}"
            )
            if violation:
                name, value = violation
                self.coverage.unknown_controls.add((name, value, observation.enable if name == "rstb" else "1"))
                self.logger.info("Expected known-control assertion: %s=%s", name, value)
                self.coverage.state = None
            elif observation.rstb == "0":
                self.coverage.state, command = config.reset_bits, "reset"
                self.coverage.reset_enable.add(observation.enable)
                if observation.enable in ("x", "z"):
                    self.coverage.masked_unknown_enable.add(observation.enable)
            elif not config.has_enable or observation.enable == "1":
                self.coverage.state, command = observation.data, "capture"
                if not config.has_enable:
                    self.coverage.ignored_enable.add(observation.enable)
            else:
                command = "hold"
            self.coverage.commands[command or "illegal"] += 1
            self.coverage.random_checks += observation.label.startswith("random_")
            if self.run_command and command:
                self.coverage.command_pairs.add((self.run_command, command))
            if command == self.run_command:
                self.run_length += 1
            else:
                self.run_command, self.run_length = command, 1
            if command:
                self.coverage.longest_runs[command] = max(self.coverage.longest_runs[command], self.run_length)
            if self.pending_reset:
                self.pending_reset["clocked"] = True
        if reset_assert:
            phase = "low" if observation.clk == "0" else "high"
            self.pending_reset = {"phase": phase, "clocked": rising, "before": before}
            if config.async_reset:
                self.coverage.state = config.reset_bits
                self.coverage.commands["async_assert"] += 1
        if reset_release:
            self.coverage.reset_release.add(observation.clk)
            if self.pending_reset and not self.pending_reset["clocked"]:
                # A discriminating reset pulse starts with non-reset state.
                if self.pending_reset["before"] not in (None, config.reset_bits):
                    self.coverage.short_reset_phases.add(self.pending_reset["phase"])
            self.pending_reset = None
        if previous:
            phase = "low" if observation.clk == "0" else "high"
            if previous.data != observation.data and observation.rstb == "1" and not rising:
                self.coverage.data_activity.add((phase, observation.enable))
            if previous.enable != observation.enable and observation.enable in ("0", "1"):
                self.coverage.enable_transitions.add((phase, observation.enable))
        if before is None and self.coverage.state is not None:
            self.coverage.ignored_intervals.append((self.coverage.ignore_start, observation.time_ps))
            self.coverage.ignore_start = None
        elif before is not None and self.coverage.state is None:
            self.coverage.ignore_start = observation.time_ps
        elif before is not None and self.coverage.state != before:
            self.coverage.expected_changes.append((observation.time_ps, before, self.coverage.state))
        if self.coverage.state is not None:
            assert observation.q == self.coverage.state, (
                f"{observation.label} at {observation.time_ps} ps: o_q={observation.q}, "
                f"expected {self.coverage.state}; clk={observation.clk}, rstb={observation.rstb}, "
                f"enable={observation.enable}, data={observation.data}"
            )
            for bit, value in enumerate(reversed(self.coverage.state)):
                if value in ("0", "1"):
                    self.coverage.bit_values.add((bit, value))
        self.previous = observation
