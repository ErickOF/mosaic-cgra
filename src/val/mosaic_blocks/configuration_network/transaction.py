"""One observed root/endpoint clock step, using the shared fault-capable item."""

from static_mesh.transaction import MeshItem as NetworkItem, Observation
from configuration_network.defaults import PORTS

INPUTS = tuple(n for n, (d, _) in PORTS.items() if d == "Input" and n != "i_clk")
OUTPUTS = tuple(n for n, (d, _) in PORTS.items() if d == "Output")


def field(ports, name, index, width):
    return ports[name] >> (index * width) & ((1 << width) - 1)
