"""Retention model components for specification-based PyUVM validation."""

from __future__ import annotations

import cocotb
from mosaic_uvm.logic import bits, logic
from retention_register.config import RetentionConfig
from retention_register.transaction import Inputs, State


def violations(config, inputs, valid_save, previous_command, *, rising=True, async_event=False) -> set[str]:
    """Protocol is checked at sampled events, not at off-edge control activity."""
    reset, enable, save, restore = (str(value).lower() for value in (inputs.rstb, inputs.enable, inputs.save, inputs.restore))
    result = set()
    if (rising or async_event) and reset not in ("0", "1"):
        result.add("unknown_reset")
    if rising:
        for name, value in (("enable", enable), ("save", save), ("restore", restore)):
            if value not in ("0", "1"):
                result.add("unknown_" + name)
        if save == restore == "1":
            result.add("save_restore_conflict")
        if config.has_enable and enable == "1" and (save == "1" or restore == "1"):
            result.add("enable_during_retention")
        if reset == "1":
            if restore == "1" and not valid_save:
                result.add("restore_without_save")
            command = "restore" if restore == "1" else "save" if save == "1" else None
            if command == previous_command and command in ("save", "restore"):
                result.add("repeat_" + command)
    return result


def next_state(config: RetentionConfig, state: State, inputs: Inputs) -> tuple[State, str]:
    """Reference the architectural priority table and pre-edge storage values."""
    reset, restore, save, enable = (str(value).lower() for value in (inputs.rstb, inputs.restore, inputs.save, inputs.enable))
    unknown = "x" * config.width
    if reset == "0":
        return State(config.reset_bits, config.reset_bits), "reset"
    if reset != "1" or restore not in ("0", "1") or save not in ("0", "1"):
        return State(unknown, unknown), "unknown"
    requests = {"restore": restore == "1", "save": save == "1",
                "capture": not config.has_enable or enable == "1", "hold": True}
    command = next(name for name in ("restore", "save", "capture", "hold") if requests[name])
    if restore == save == "0" and config.has_enable and enable not in ("0", "1"):
        return State(unknown, state.retained), "unknown"
    outcomes = {
        "restore": State(state.retained, state.retained),
        "save": State(state.visible, state.visible),
        "capture": State(bits(inputs.data, config.width), state.retained), "hold": state,
    }
    return outcomes[command], command


def pattern_classes(word: str) -> set[str]:
    classes = set()
    for state, name in (("0", "zero"), ("1", "one"), ("x", "all_x"), ("z", "all_z")):
        if word == state * len(word):
            classes.add(name)
    if word in (("01" * len(word))[:len(word)], ("10" * len(word))[:len(word)]):
        classes.add("alternating")
    if set(word) & {"x", "z"} and set(word) & {"0", "1"}:
        classes.add("partial_unknown")
    if {"x", "z"} <= set(word):
        classes.add("mixed_x_z")
    return classes


def ports() -> Inputs:
    dut = cocotb.top
    return Inputs(int(logic(dut.i_clk)), logic(dut.i_rstb), logic(dut.i_enable), logic(dut.i_save), logic(dut.i_restore), logic(dut.i_d))
