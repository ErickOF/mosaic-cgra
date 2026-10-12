"""Four-state conversion shared by drivers and independent reference checks."""


def bits(value: int | str, width: int) -> str:
    """Preserve X/Z and reject implicit port truncation."""
    if isinstance(value, int):
        assert 0 <= value < 1 << width, "Stimulus does not fit the port"
        return f"{value:0{width}b}"
    word = value.lower()
    assert len(word) == width and set(word) <= set("01xz"), "Invalid four-state stimulus"
    return word


def logic(handle) -> str:
    """Read every logic state without converting X/Z to a Boolean."""
    return str(handle.value).lower()
