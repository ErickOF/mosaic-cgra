"""Editable native hardware settings, grouped by the FU they configure."""

from dataclasses import asdict

from tile_parameters import Parameter, PARAMETERS as LEGACY
from flavor.native import defaults
from tile_units import UNIT_DEFAULTS, resolve_units
from flavor.guidance import parameter_info, unit_info


PARAMETERS = {kind: dict(values) for kind, values in LEGACY.items()}
PARAMETERS.update(VCT={}, SFT={}, CPT={})


def add(kind, group, names):
    native = defaults(kind)
    for name, choices in names.items():
        title = name.replace("_", " ").lower().capitalize()
        PARAMETERS[kind][name] = Parameter(title, native[name], tuple(choices), group,
            f"{name}: elaboration-time setting for this tile's {group.lower()}.")


add("BCT", "ALU", {"DATA_WIDTH": (2, 4, 6, 8, 16, 32, 64, 128), "ALU_LATENCY": range(2), "SUPPORT_SATURATION": range(2),
                  "SUPPORT_MINMAX": range(2)})
add("BCT", "Multiplier", {"MULTIPLY_OPERAND_WIDTH": (1, 2, 3, 4, 8, 16, 32),
                         "MULTIPLY_LATENCY": range(5)})
add("BCT", "MAC", {"MAC_LATENCY": range(5), "ACCUMULATOR_COUNT": (1, 2, 4, 8)})
add("MST", "Load engine", {"READ_DATA_FIFO_DEPTH": (2, 4, 8, 16)})
add("MST", "Store engine", {"WRITE_DATA_FIFO_DEPTH": (2, 4, 8, 16)})
add("MST", "Address generation", {"SUPPORT_2D": range(2), "SUPPORT_CIRCULAR": range(2)})
add("MST", "Formatter", {"SUPPORT_UNALIGNED": range(2), "SUPPORT_WIDTH_CONVERSION": range(2),
                         "SUPPORT_ELEMENT_CONVERSION": range(2)})

add("VCT", "Functional units", {"FU_PROFILE": range(3)})
add("VCT", "Vector lanes", {"NUM_LANES": (2, 4, 8), "ELEMENT_WIDTH": (4, 8, 16),
    "ACC_WIDTH": (16, 32, 64, 128), "WRITE_SLICE_WIDTH": (1, 2, 4, 8, 16),
    "LANE_LATENCY": range(5), "SUPPORT_SATURATION": range(2), "SUPPORT_MINMAX": range(2)})
add("VCT", "Multiplier", {"SUPPORT_MUL": range(2), "MUL_LATENCY": range(5)})
add("VCT", "MAC", {"SUPPORT_MAC": range(2), "MAC_LATENCY": range(5)})
add("VCT", "Reduction", {"REDUCTION_LATENCY": range(9), "SCALAR_ACC_DEPTH": (1, 2, 4, 8)})
add("VCT", "Dot product", {"DOT_LATENCY": range(9)})
add("VCT", "Storage", {"VRF_DEPTH": (2, 4, 8, 16, 32, 64),
    "PREDICATE_DEPTH": (2, 4, 8, 16), "VECTOR_ACC_DEPTH": (1, 2, 4, 8),
    "INPUT_FIFO_DEPTH": (1, 2, 4, 8), "RESULT_QUEUE_DEPTH": (1, 2, 4, 8)})
add("VCT", "Protection", {"VRF_PROTECTION": range(3), "CONTROL_PROTECTION": range(3),
                          "CONTEXT_PROTECTION": range(3)})

add("SFT", "Functional units", {"FU_PROFILE": range(4)})
add("SFT", "Number formats", {"INPUT_WIDTH": (8, 12, 16), "INPUT_FRAC_BITS": range(1, 16),
    "OUTPUT_WIDTH": (8, 16, 24, 32), "OUTPUT_FRAC_BITS": range(1, 32),
    "INTERNAL_WIDTH": (24, 32, 40, 48, 64), "INTERNAL_FRAC_BITS": range(1, 48)})
add("SFT", "LUT", {"LUT_ADDRESS_WIDTH": range(1, 9), "LUT_INDEX_FRACTION_WIDTH": range(1, 9),
    "LUT_BANKS": (1, 2, 4), "LUT_PIPELINE_DEPTH": range(1, 5), "SUPPORT_INTERPOLATION": range(2)})
add("SFT", "Polynomial", {"POLY_COEFFICIENT_WIDTH": (12, 16, 18, 24, 32),
    "POLY_MAX_DEGREE": range(1, 5), "POLY_BANKS": (1, 2, 4), "POLY_EVALUATION_ARCH": range(2)})
add("SFT", "Reciprocal", {"RECIP_INTERNAL_WIDTH": (16, 24, 32, 48, 64),
    "RECIP_INTERNAL_FRAC_BITS": range(8, 31), "RECIP_SEED_ADDRESS_WIDTH": range(1, 7)})
add("SFT", "RSQRT", {"RSQRT_INTERNAL_WIDTH": (16, 24, 28, 32, 48, 64),
    "RSQRT_INTERNAL_FRAC_BITS": range(8, 31), "RSQRT_SEED_ADDRESS_WIDTH": range(1, 7)})
add("SFT", "Exponential", {"EXP_RANGE_WIDTH": (40, 48, 64),
    "EXP_TABLE_ADDRESS_WIDTH": range(1, 7), "EXP_PIPELINE_DEPTH": range(5, 9)})
add("SFT", "Reduction", {"REDUCTION_LANES": (1, 2, 4, 8),
    "REDUCTION_ELEMENT_WIDTH": (4, 8, 16), "REDUCTION_ACC_WIDTH": (32, 40, 48, 64),
    "MAX_REDUCTION_ELEMENTS": (16, 64, 256, 1024), "REDUCTION_STATE_DEPTH": (1, 2, 4, 8)})
add("SFT", "Storage", {"LOCAL_RF_DEPTH": (2, 4, 8, 16, 32),
    "INPUT_FIFO_DEPTH": (1, 2, 4, 8, 16), "RESULT_QUEUE_DEPTH": (1, 2, 4, 8, 16, 32),
    "MAX_INFLIGHT": (1, 2, 4, 8, 16, 32)})
add("SFT", "Protection", {"TABLE_PROTECTION": range(3), "COEFFICIENT_PROTECTION": range(3),
                          "CONTROL_PROTECTION": range(3), "CONTEXT_PROTECTION": range(3)})

add("CPT", "Functional units", {"FU_PROFILE": range(2)})
add("CPT", "Predicate unit", {"PREDICATE_LANES": (1, 2, 4, 8, 16),
    "PREDICATE_DEPTH": (2, 4, 8, 16)})
add("CPT", "Loop controller", {"MAX_LOOP_DEPTH": range(1, 5),
    "INDEX_WIDTH": (4, 8, 16, 32), "TRIP_COUNT_WIDTH": (2, 4, 8, 16, 32),
    "LOOP_EXPORT_LEVELS": range(1, 5)})
add("CPT", "Event barrier", {"NUM_EVENTS": (1, 2, 4, 8, 16),
    "EVENT_COUNT_WIDTH": (1, 2, 4, 8), "NUM_WAIT_SLOTS": range(1, 5),
    "NUM_BARRIERS": range(1, 5), "MAX_PARTICIPANTS": (1, 2, 4, 8, 16)})
add("CPT", "Actions", {"MAX_OUTSTANDING_ACTIONS": (1, 2, 4, 8),
    "ACTION_QUEUE_DEPTH": (1, 2, 4, 8, 16), "ACTION_RESPONSE_DEPTH": (1, 2, 4, 8, 16),
    "SUPPORT_CONTEXT_COORDINATION": range(2), "SUPPORT_CLUSTER_LIFECYCLE": range(2),
    "SUPPORT_TIMEOUT": range(2)})
add("CPT", "Storage", {"CONTROL_REGISTER_DEPTH": (4, 8, 16),
    "EVENT_INPUT_FIFO_DEPTH": (1, 2, 4, 8, 16), "EVENT_OUTPUT_FIFO_DEPTH": (1, 2, 4, 8, 16)})
add("CPT", "Protection", {"EVENT_PROTECTION": range(2), "CONTEXT_PROTECTION": range(3)})

# Enables live in the checklist; FU_PROFILE remains an import-compatible preset.
for kind, flags in UNIT_DEFAULTS.items():
    add(kind, "Functional units", {name: range(2) for name in flags})

# Shared geometry stays editable even when the standalone ALU is disabled.
PARAMETERS["BCT"]["DATA_WIDTH"] = Parameter("Data width", 32,
    (2, 4, 6, 8, 16, 32, 64, 128), "Tile geometry",
    "Payload and accumulator width shared by every selected BCT FU.")
PARAMETERS["BCT"]["SUPPORT_SATURATION"] = Parameter("Saturation", 1, (0, 1), "Arithmetic options",
    "Saturation support shared by the ALU and MAC.")

PROFILES = {
    "BCT": ["ALU", "ALU + multiplier", "ALU + multiplier + MAC"],
    "MST": [],
    "VCT": ["Vector lanes", "Vector lanes + reduction", "Vector lanes + reduction + dot product"],
    "SFT": ["LUT + exact operations", "+ polynomial + multiplier", "+ reciprocal + RSQRT",
            "+ exponential"],
    "CPT": ["Local predicate / loop / event control", "+ tagged actions and timeouts"],
}

UNITS = {
    "BCT": [("ALU", "ENABLE_ALU"), ("Multiplier", "ENABLE_MULTIPLIER"), ("MAC", "ENABLE_MAC")],
    "MST": [("Load engine", "ENABLE_LOAD"), ("Store engine", "ENABLE_STORE")],
    "VCT": [("Lane ALU", "ENABLE_LANE_ALU"), ("Multiplier", "SUPPORT_MUL"),
            ("MAC", "SUPPORT_MAC"), ("Reduction", "ENABLE_REDUCTION"),
            ("Dot product", "ENABLE_DOT_PRODUCT")],
    "SFT": [("ALU", "ENABLE_ALU"), ("Multiplier", "ENABLE_MULTIPLIER"),
            ("LUT", "ENABLE_LUT"), ("Polynomial", "ENABLE_POLYNOMIAL"),
            ("Reciprocal", "ENABLE_RECIPROCAL"), ("RSQRT", "ENABLE_RSQRT"),
            ("Exponential", "ENABLE_EXPONENTIAL"), ("Reduction", "ENABLE_REDUCTION"),
            ("Formatter", "ENABLE_FORMATTER"), ("Accumulator", "ENABLE_ACCUMULATOR")],
    "CPT": [("Predicate unit", "ENABLE_PREDICATE"), ("Loop controller", "ENABLE_LOOP_CONTROLLER"),
            ("Event barrier", "ENABLE_EVENT_BARRIER"), ("Actions", "ENABLE_ACTIONS")],
}


def units(kind):
    return [dict(name=name, activation_parameter=activation,
                 minimum_profile=UNIT_DEFAULTS[kind].get(activation),
                 **unit_info(kind, activation))
            for name, activation in UNITS[kind]]


def effective(tile):
    kind = tile["class"]
    values = {name: spec.default for name, spec in PARAMETERS[kind].items()}
    overrides = tile.get("parameters", {})
    if not isinstance(overrides, dict):
        raise ValueError(f"Tile {tile['id']}.parameters must be a table")
    for name, value in overrides.items():
        spec = PARAMETERS[kind].get(name)
        if spec is None or type(value) is not int or value not in spec.choices:
            choices = spec.choices if spec else "a supported native parameter"
            raise ValueError(f"Tile {tile['id']}.parameters.{name} must be one of {choices}")
        values[name] = value
    return resolve_units(kind, values, overrides)


def catalog():
    result = {}
    for kind, parameters in PARAMETERS.items():
        result[kind] = {}
        for name, spec in parameters.items():
            entry = asdict(spec) | parameter_info(kind, name)
            for key in ("choice_help", "choice_labels"):
                if key in entry:
                    entry[key] = {str(value): entry[key][str(value)] for value in spec.choices
                                  if str(value) in entry[key]}
            if name == "FU_PROFILE":
                entry["choice_labels"] = {str(value): label
                                          for value, label in enumerate(PROFILES[kind])}
            if kind == "MST" and name == "SUPPORT_CIRCULAR":
                entry["unavailable_choices"] = {
                    "1": "Circular addressing requires an unreleased MST adapter."}
            result[kind][name] = entry
    return result
