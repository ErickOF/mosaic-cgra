"""Backward-compatible defaults for independently selectable native tile FUs.

FU_PROFILE selects defaults only. Explicit ENABLE_* values always take precedence.
Address generators, formatters and storage used inside an MST channel are structural
parts of the selected load/store engine, rather than independently executable FUs.
"""

# None means enabled in every legacy profile; integers are the first legacy profile.
UNIT_DEFAULTS = {
    "BCT": {"ENABLE_ALU": None, "ENABLE_MULTIPLIER": 1, "ENABLE_MAC": 2},
    "MST": {"ENABLE_LOAD": None, "ENABLE_STORE": None},
    "VCT": {"ENABLE_LANE_ALU": None, "ENABLE_REDUCTION": 1, "ENABLE_DOT_PRODUCT": 2},
    "SFT": {"ENABLE_ALU": None, "ENABLE_MULTIPLIER": 1, "ENABLE_LUT": None,
            "ENABLE_POLYNOMIAL": 1, "ENABLE_RECIPROCAL": 2, "ENABLE_RSQRT": 2,
            "ENABLE_EXPONENTIAL": 3, "ENABLE_REDUCTION": None,
            "ENABLE_FORMATTER": None, "ENABLE_ACCUMULATOR": None},
    "CPT": {"ENABLE_PREDICATE": None, "ENABLE_LOOP_CONTROLLER": None,
            "ENABLE_EVENT_BARRIER": None, "ENABLE_ACTIONS": 1},
}


def unit_defaults(kind, profile=1):
    return {name: int(minimum is None or profile >= minimum)
            for name, minimum in UNIT_DEFAULTS[kind].items()}


def resolve_units(kind, parameters, overrides):
    """Resolve after the profile, so old TOML and explicit selections both work."""
    return parameters | unit_defaults(kind, parameters.get("FU_PROFILE", 1)) | {
        name: overrides[name] for name in UNIT_DEFAULTS[kind] if name in overrides}
