"""Counter coverage components for specification-based PyUVM validation."""

from collections import Counter
from itertools import product
from counter.constants import COMMANDS, CONTROLS
from mosaic_uvm.components import CoverageCollector


class CounterCoverage(CoverageCollector):
    """Require positive hits for the specification's functional bins/crosses."""

    def build_phase(self):
        super().build_phase()
        self.commands = set()
        self.command_direction = set()
        self.control_combinations = set()
        self.values = set()
        self.loaded_values = set()
        self.reset_from = set()
        self.state_controls = set()
        self.unknown_controls = set()
        self.disabled_terminal = set()
        self.events = Counter()
        self.checks = 0
        self.random_cycles = 0
        self.run_command = None
        self.run_length = 0
        self.longest_hold = 0
        self.longest_active = 0

    def sample(self, observation, previous, current):
        inputs = observation.edge_inputs
        command = inputs.command
        self.checks += 1
        self.commands.add(command)
        self.command_direction.add((command, inputs.direction))
        controls = tuple(getattr(inputs, name) for name in CONTROLS)
        self.control_combinations.add(controls)
        self.values.add(current.count)
        self.random_cycles += observation.label.startswith("random_")
        if command == "load":
            self.loaded_values.add(inputs.load_value)
        if previous is not None:
            self.state_controls.add((previous.count, *controls))
            if command == "reset":
                self.reset_from.add(previous.count)
            if command == "increment" and previous.count == self.config.maximum - 1:
                self.events["increment_to_maximum"] += 1
            if command == "decrement" and previous.count == 1:
                self.events["decrement_to_zero"] += 1
            if previous.overflow and command == "decrement":
                self.events["overflow_then_decrement"] += 1
            if previous.underflow and command == "increment":
                self.events["underflow_then_increment"] += 1
        self.events["overflow"] += current.overflow
        self.events["underflow"] += current.underflow
        self.events["short_reset_pulse"] += observation.pulse_reset
        if command == "hold" and current.count in (0, self.config.maximum):
            boundary = "zero" if current.count == 0 else "maximum"
            self.disabled_terminal.add((boundary, inputs.direction))
        self.events["direction_change"] += (
            getattr(self, "last_direction", inputs.direction) != inputs.direction
        )
        self.last_direction = inputs.direction
        run_command = "active" if command in ("increment", "decrement") else command
        self.run_length = self.run_length + 1 if run_command == self.run_command else 1
        self.run_command = run_command
        if run_command == "hold":
            self.longest_hold = max(self.longest_hold, self.run_length)
        if run_command == "active":
            self.longest_active = max(self.longest_active, self.run_length)

    def report(self):
        config = self.config
        # Exhaustive reset-state sampling is finite for small widths. Wider
        # counters use boundary, reset, pattern, and randomized values.
        required_reset = (
            set(range(config.maximum + 1)) if config.width <= 8
            else config.representative_values
        )
        goals = {
            "commands": set(COMMANDS) <= self.commands,
            # Arithmetic command names already encode direction; the opposite
            # direction bins for increment/decrement are structurally illegal.
            "command_direction_cross": (
                set(product(("reset", "clear", "load", "hold"), (0, 1)))
                | {("increment", 0), ("decrement", 1)}
            ) <= self.command_direction,
            "control_priority_cross": set(product((0, 1), repeat=5)) <= self.control_combinations,
            "zero_maximum_reset_values": {0, config.maximum, config.reset_value} <= self.values,
            "representative_loads": config.representative_values <= self.loaded_values,
            "reset_states": required_reset <= self.reset_from,
            "disabled_terminal_direction_cross": set(product(("zero", "maximum"), (0, 1))) <= self.disabled_terminal,
            "unknown_controls": set(product(CONTROLS, ("x", "z"))) <= self.unknown_controls,
            "long_hold": self.longest_hold >= 32,
            "long_active": self.longest_active >= 64,
            "long_random_sequence": self.random_cycles >= config.random_cycles,
        }
        for event in (
            "increment_to_maximum", "decrement_to_zero", "overflow", "underflow",
            "overflow_then_decrement", "underflow_then_increment",
            "direction_change", "short_reset_pulse",
        ):
            goals[event] = self.events[event] > 0
        if config.width <= 4:
            goals["exhaustive_state_control_cross"] = all(
                (value, *controls) in self.state_controls
                for value in range(config.maximum + 1)
                for controls in product((0, 1), repeat=5)
            )
        return {
            "status": "PASS" if all(goals.values()) else "FAIL",
            "parameters": {
                "WIDTH": config.width, "RESET_VALUE": config.reset_value,
                "SATURATE": int(config.saturate), "ASYNC_RESET": int(config.async_reset),
            },
            "seed": config.seed,
            "checked_cycles": self.checks,
            "random_cycles": self.random_cycles,
            "expected_control_assertions": len(self.unknown_controls),
            "reset_states_checked": len(self.reset_from),
            "reset_states_exhaustive": config.width <= 8,
            "longest_hold": self.longest_hold,
            "longest_active": self.longest_active,
            "events": dict(self.events),
            "bins": {
                "commands": sorted(self.commands),
                "command_direction": sorted(self.command_direction),
                "control_combinations": sorted(self.control_combinations),
                "loaded_values": sorted(self.loaded_values),
                "reset_from_values": sorted(self.reset_from),
                "disabled_terminal": sorted(self.disabled_terminal),
                "unknown_controls": sorted(self.unknown_controls),
                "state_control_combinations": len(self.state_controls),
            },
            "goals": goals,
        }
