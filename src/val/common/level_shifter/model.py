"""LevelShifter model components for specification-based PyUVM validation."""

from __future__ import annotations


def expected_data(source: str) -> str:
    """Apply the specification's identity truth table independently to each bit."""
    table = {"0": "0", "1": "1", "x": "x", "z": "z"}
    return "".join(table[bit] for bit in source)


def pattern_classes(word: str) -> set[str]:
    classes = set()
    for state, name in (("0", "zero"), ("1", "one"), ("x", "all_x"), ("z", "all_z")):
        if word == state * len(word):
            classes.add(name)
    if set(word) <= {"0", "1"}:
        if word.count("1") == 1:
            classes.add("walking_one")
        if word.count("0") == 1:
            classes.add("walking_zero")
        if word in (("01" * len(word))[:len(word)], ("10" * len(word))[:len(word)]):
            classes.add("alternating")
        if set(word) == {"0", "1"}:
            classes.add("mixed_known")
    if set(word) & {"x", "z"} and set(word) & {"0", "1"}:
        classes.add("mixed_unknown_known")
    if {"x", "z"} <= set(word):
        classes.add("mixed_x_z")
    return classes
