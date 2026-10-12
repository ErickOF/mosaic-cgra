"""Counter model components for specification-based PyUVM validation."""

from __future__ import annotations

from counter.config import CounterConfig
from counter.transaction import Inputs, State


def next_state(config: CounterConfig, state: State | None, inputs: Inputs) -> State:
    """Apply the specified command priority and bounded integer arithmetic."""
    command = inputs.command
    if command in ("reset", "clear"):
        return State(config.reset_value)
    if command == "load":
        return State(inputs.load_value)
    assert state is not None, "Recover from illegal controls with reset or load"
    if command == "hold":
        return State(state.count)
    candidate = state.count + (-1 if command == "decrement" else 1)
    count = (
        min(max(candidate, 0), config.maximum)
        if config.saturate else candidate & config.maximum
    )
    return State(count, int(candidate > config.maximum), int(candidate < 0))
