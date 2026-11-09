"""Qualified per-instance parameters shared by cluster generation and its editor.

These settings preserve the Cluster-MVP port ABI and 512/1024-bit context slots.
Interface widths, identities and clock domains belong to the cluster adapter.
"""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Parameter:
    title: str
    default: int
    choices: tuple[int, ...]
    group: str
    description: str


PARAMETERS = {
    "BCT": {
        "FU_PROFILE": Parameter("Functional units", 1, (0, 1, 2), "Compute",
            "0: ALU; 1: ALU and multiplier; 2: ALU, multiplier and MAC."),
        "RF_DEPTH": Parameter("Register file entries", 8, (4, 8, 16, 32), "Storage",
            "Private register entries in this tile. Context packing follows this depth."),
        "MULTIPLY_OPERAND_WIDTH": Parameter("Multiply operand bits", 16, (4, 8, 16),
            "Compute", "Operand precision within the shared 32-bit stream interface."),
        "ALU_LATENCY": Parameter("ALU latency", 1, (0, 1), "Pipeline", "Enabled clock edges."),
        "MULTIPLY_LATENCY": Parameter("Multiply latency", 1, tuple(range(5)), "Pipeline",
            "Enabled clock edges, when the multiplier is present."),
        "MAC_LATENCY": Parameter("MAC latency", 1, tuple(range(5)), "Pipeline",
            "Enabled clock edges, when the MAC is present."),
        "BYPASS_PROFILE": Parameter("Bypass profile", 1, (0, 1, 2), "Pipeline",
            "Released bypass connectivity profile."),
        "REGISTER_BYPASS": Parameter("Register bypass", 0, (0, 1), "Pipeline",
            "Insert the released bypass register stage."),
        "INPUT_FIFO_DEPTH": Parameter("Input FIFO entries", 2, (1, 2, 4, 8), "Storage",
            "Private input buffering; the cluster-facing ports stay unchanged."),
        "RESULT_QUEUE_DEPTH": Parameter("Result queue entries", 2, (1, 2, 4, 8), "Storage",
            "Private result buffering."),
        "RF_PROTECTION": Parameter("Register protection", 0, (0, 1, 2), "Protection",
            "0: plain; 1: parity; 2: SECDED."),
        "CONTROL_PROTECTION": Parameter("Control protection", 1, (0, 1, 2), "Protection",
            "0: plain; 1: parity; 2: SECDED."),
        "CONTEXT_PROTECTION": Parameter("Context protection", 0, (0, 1, 2), "Protection",
            "0: plain; 1: parity; 2: SECDED."),
    },
    "MST": {
        "READ_DATA_FIFO_DEPTH": Parameter("Read FIFO entries", 8, (2, 4, 8, 16), "Storage",
            "Buffering inside the memory-service load path."),
        "WRITE_DATA_FIFO_DEPTH": Parameter("Write FIFO entries", 8, (2, 4, 8, 16), "Storage",
            "Buffering inside the memory-service store path."),
        "COMMAND_PROTECTION": Parameter("Command protection", 0, (0, 1, 2), "Protection",
            "0: plain; 1: parity; 2: SECDED."),
        "FIFO_PROTECTION": Parameter("FIFO protection", 0, (0, 1, 2), "Protection",
            "0: plain; 1: parity; 2: SECDED."),
        "CONTROL_PROTECTION": Parameter("Control protection", 1, (0, 1, 2), "Protection",
            "0: plain; 1: parity; 2: SECDED."),
        "CONTEXT_PROTECTION": Parameter("Context protection", 0, (0, 1, 2), "Protection",
            "0: plain; 1: parity; 2: SECDED."),
    },
}


def tile_parameters(tile):
    """Resolve only qualified settings; reject typos and adapter-owned parameters."""
    kind = tile["class"]
    if kind not in PARAMETERS:
        raise ValueError(f"Tile {tile['id']}: {kind} has no qualified cluster adapter")
    overrides = tile.get("parameters", {})
    if not isinstance(overrides, dict):
        raise ValueError(f"Tile {tile['id']}.parameters must be a table")
    result = {name: spec.default for name, spec in PARAMETERS[kind].items()}
    for name, value in overrides.items():
        spec = PARAMETERS[kind].get(name)
        if spec is None:
            raise ValueError(f"Tile {tile['id']}.parameters.{name} is not editable in Cluster-MVP")
        if type(value) is not int or value not in spec.choices:
            raise ValueError(f"Tile {tile['id']}.parameters.{name} must be one of {spec.choices}")
        result[name] = value
    return result


def catalog():
    return {kind: {name: asdict(spec) for name, spec in parameters.items()}
            for kind, parameters in PARAMETERS.items()}
