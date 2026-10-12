"""Mux model components for specification-based PyUVM validation."""

from __future__ import annotations

from mux.config import MuxConfig


def input_words(packed: str, width: int) -> tuple[str, ...]:
    """The rightmost packed word is input zero; preserve each word's bit order."""
    assert len(packed) % width == 0
    return tuple(reversed(tuple(packed[offset:offset + width] for offset in range(0, len(packed), width))))


def expected_outputs(config: MuxConfig, packed: str, select: str) -> tuple[str, str]:
    """Match exact legal keys; unknown and unused encodings cannot select data."""
    choices = {f"{index:0{config.select_width}b}": word
               for index, word in enumerate(input_words(packed, config.data_width))}
    return (choices[select], "1") if select in choices else (config.default_bits, "0")


def interval_kind(config: MuxConfig, old_data: str, old_select: str, new_data: str, new_select: str) -> str:
    """Classify intervals whose outputs must remain unchanged during input activity."""
    if old_select != new_select:
        return "changing_selection"
    if old_data == new_data:
        return "stable"
    if set(new_select) & {"x", "z"} or int(new_select, 2) >= config.num_inputs:
        return "invalid"
    index = int(new_select, 2)
    old_word = input_words(old_data, config.data_width)[index]
    new_word = input_words(new_data, config.data_width)[index]
    return "unselected" if old_word == new_word else "selected"
