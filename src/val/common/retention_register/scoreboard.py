"""Retention scoreboard components for specification-based PyUVM validation."""

from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from mosaic_uvm.logic import bits
from retention_register.model import next_state, pattern_classes, violations
from retention_register.transaction import Activity, Inputs, State


class RetentionScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.coverage = ConfigDB().get(self, "", "coverage")
        self.analysis_export = uvm_analysis_export("analysis_export", self)
        self.analysis_export.write = self.write
        initial = self.config.reset_bits if self.config.async_reset else "x" * self.config.width
        self.state = State(initial, initial)
        self.previous = None
        self.valid_save = False
        self.previous_command = None
        self.last_save = None


        self.writes_since_save = self.saves_before_restore = 0

    def event(self, inputs):
        old = self.previous.inputs if self.previous else Inputs(0, "0", "0", "0", "0", "0" * self.config.width)
        rising = old.clk == 0 and inputs.clk == 1
        negative = str(old.rstb) == "1" and str(inputs.rstb) in "0xz" or str(old.rstb) in "xz" and str(inputs.rstb) == "0"
        return rising, self.config.async_reset and negative

    def predicted(self, inputs):
        rising, asynchronous = self.event(inputs)
        return next_state(self.config, self.state, inputs) if rising or asynchronous else (self.state, None)

    def write(self, observation):
        if isinstance(observation, Activity):
            assert observation.allowed, f"Out-of-event activity changed {observation.signal} to {observation.value}"
            state, _ = self.predicted(observation.inputs)
            expected = state.visible if observation.signal == "o_q" else state.retained
            assert observation.value == expected, f"Event waveform mismatch: {observation.signal}={observation.value}, expected={expected}"
            self.coverage.activity_counts[observation.signal] += 1
            return
        config, inputs, item = self.config, observation.inputs, observation.item
        requested = item.inputs
        assert inputs == Inputs(requested.clk, str(requested.rstb).lower(), str(requested.enable).lower(),
                                str(requested.save).lower(), str(requested.restore).lower(), bits(requested.data, config.width)), "Stimulus was coerced"
        if observation.stage == "held":
            self.coverage.held_checks += 1
            self.check_outputs(observation)
            return
        rising, asynchronous = self.event(inputs)
        if rising or asynchronous:
            errors = violations(config, inputs, self.valid_save, self.previous_command, rising=rising, async_event=asynchronous)
            try:
                assert not errors, "Protocol assertion failed: " + ",".join(sorted(errors))
            except AssertionError:
                if not errors <= item.expected:
                    raise
                for name in errors:
                    if not self.coverage.diagnostics[name]:
                        self.logger.info("Expected protocol assertion: %s", name)
                    self.coverage.diagnostics[name] += 1
            if rising:
                assert errors == item.expected, f"Expected protocol diagnostics {sorted(item.expected)}, got {sorted(errors)}"
            prior = self.state
            self.state, command = next_state(config, prior, inputs)
            self.coverage.command_counts[command] += 1
            if rising:
                self.coverage.clocked_checks += 1
                self.coverage.random_checks += observation.item.get_name().startswith("random_cycle_")
                if all(str(value) in ("0", "1") for value in (inputs.rstb, inputs.restore, inputs.save, inputs.enable)):
                    self.coverage.priority.add((str(inputs.rstb), str(inputs.restore), str(inputs.save), str(inputs.enable)))
                if not config.has_enable:
                    self.coverage.ignored_enable.add(str(inputs.enable))
            if command == "reset" or command == "unknown" and (str(inputs.rstb) != "1" or str(inputs.save) in "xz" or str(inputs.restore) in "xz"):
                self.valid_save, self.last_save = False, None
                self.saves_before_restore = self.writes_since_save = 0
            elif command == "save":
                self.valid_save = True
                self.saves_before_restore += 1
                self.writes_since_save = 0
                classes = pattern_classes(prior.visible)
                if item.get_name().startswith("random_saved_") or item.get_name().startswith("random_cycle_"):
                    classes.add("random")
                self.coverage.saved_classes.update(classes)
                self.last_save = observation.time_ps, classes
                if not errors:
                    self.coverage.saved_bits.update(enumerate(reversed(prior.visible)))
            elif command == "capture" and self.valid_save:
                self.writes_since_save += 1
            elif command == "restore":
                if self.valid_save and not errors:
                    self.coverage.legal_restores += 1
                    self.coverage.restored_bits.update(enumerate(reversed(self.state.visible)))
                    self.coverage.multiple_write_restores += self.writes_since_save >= 2
                    self.coverage.latest_save_restores += self.saves_before_restore >= 2
                    if self.last_save:
                        interval = "long" if observation.time_ps - self.last_save[0] >= 8 * config.period_ps else "short"
                        self.coverage.interval_cross.update((name, interval) for name in self.last_save[1])
                self.valid_save = False
                self.saves_before_restore = self.writes_since_save = 0
            self.previous_command = command
            for name in errors:
                if name.startswith("unknown_"):
                    field = {"reset": "rstb", "enable": "enable", "save": "save", "restore": "restore"}[name[8:]]
                    self.coverage.unknown_controls.add((name, str(getattr(inputs, field))))
        old = self.previous.inputs if self.previous else None
        if old and str(old.rstb) == "1" and str(inputs.rstb) == "0":
            self.coverage.reset_phases.add(inputs.clk)
        if old and str(old.rstb) == "0" and str(inputs.rstb) == "1":
            self.coverage.release_phases.add(inputs.clk)
        if item.context == "stopped":
            assert old is not None and old.clk == inputs.clk and item.duration_ps >= 2 * config.period_ps
            self.coverage.stopped.add(inputs.clk)
        self.check_outputs(observation)
        self.coverage.checks += 1
        self.previous = observation

    def check_outputs(self, observation):
        assert observation.visible == self.state.visible, f"Visible state mismatch: {observation.visible}, expected={self.state.visible}"
        if observation.retained is not None:
            assert observation.retained == self.state.retained, f"Retained image mismatch: {observation.retained}, expected={self.state.retained}"
