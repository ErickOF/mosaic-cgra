"""Common data-pattern classification; each suite chooses its required bins."""


def pattern_classes(word: str) -> set[str]:
    classes = {name for state, name in (("0", "zero"), ("1", "one"), ("x", "all_x"), ("z", "all_z"))
               if word == state * len(word)}
    if set(word) <= {"0", "1"}:
        if word.count("1") == 1:
            classes.add("walking_one")
        if word.count("0") == 1:
            classes.add("walking_zero")
        if word in (("01" * len(word))[:len(word)], ("10" * len(word))[:len(word)]):
            classes.add("alternating")
    if set(word) & {"0", "1"} and set(word) & {"x", "z"}:
        classes.add("partial_unknown")
    if {"x", "z"} <= set(word):
        classes.add("mixed_x_z")
    return classes
