"""One clock step and a native-to-generic mesh observation adapter."""

from static_mesh.transaction import MeshItem as PredicateItem, Observation
from predicate_network.defaults import PORTS

INPUTS = tuple(n for n, (d, _) in PORTS.items() if d == "Input" and n != "i_clk")
OUTPUTS = tuple(n for n, (d, _) in PORTS.items() if d == "Output")
ALIASES = dict(
    i_tile_tx_valid="i_pred_tx_valid",
    o_tile_tx_ready="o_pred_tx_ready",
    i_tile_tx_metadata="i_pred_tx_metadata",
    o_tile_rx_valid="o_pred_rx_valid",
    i_tile_rx_ready="i_pred_rx_ready",
    o_tile_rx_metadata="o_pred_rx_metadata",
    i_boundary_rx_valid="i_boundary_pred_valid",
    o_boundary_rx_ready="o_boundary_pred_ready",
    i_boundary_rx_metadata="i_boundary_pred_metadata",
    i_boundary_rx_parity="i_boundary_pred_parity",
    o_boundary_tx_valid="o_boundary_pred_valid",
    i_boundary_tx_ready="i_boundary_pred_ready",
    o_boundary_tx_metadata="o_boundary_pred_metadata",
    o_boundary_tx_parity="o_boundary_pred_parity",
    o_directed_link_active="o_link_transfer",
)
DATA = dict(
    i_tile_tx_data=("i_pred_tx", "N*TX"),
    o_tile_rx_data=("o_pred_rx", "N*RX"),
    i_boundary_rx_data=("i_boundary_pred", "B"),
    o_boundary_tx_data=("o_boundary_pred", "B"),
)


def native(ports, a):
    result = {n: ports.get(n, 0) for n in INPUTS}
    for old, new in ALIASES.items():
        if old in ports and new in INPUTS:
            result[new] = ports[old]
    for old, (prefix, count) in DATA.items():
        if old not in ports or prefix + "_value" not in INPUTS:
            continue
        value = mask = 0
        for j in range(eval(count, {}, a)):
            value |= (ports[old] >> (j * a["D"]) & ((1 << a["PV"]) - 1)) << (j * a["PV"])
            mask |= (ports[old] >> (j * a["D"] + a["PV"]) & ((1 << a["PV"]) - 1)) << (j * a["PV"])
        result[prefix + "_value"] = value
        result[prefix + "_lane_valid"] = mask
    return result


def virtual(ports, a):
    result = ports | {old: ports[new] for old, new in ALIASES.items()}
    for old, (prefix, count) in DATA.items():
        # Diagnostics retain None in the native view. The shared traffic oracle
        # is disabled for these probes, so its compatibility view may use zero.
        value = ports[prefix + "_value"]
        mask = ports[prefix + "_lane_valid"]
        if prefix.startswith("i_"):
            value = 0 if value is None else value
            mask = 0 if mask is None else mask
        result[old] = sum(
            (
                (value >> (j * a["PV"]) & ((1 << a["PV"]) - 1))
                | ((mask >> (j * a["PV"]) & ((1 << a["PV"]) - 1)) << a["PV"])
            )
            << (j * a["D"])
            for j in range(eval(count, {}, a))
        )
    result.update(
        i_cfg_valid=0,
        i_link_fault_valid=ports["i_link_fault_valid"],
        o_context_valid=int(bool(ports["o_active_context_valid"])),
        o_cfg_ready=ports["o_cfg_prepare_ready"],
    )
    return result
