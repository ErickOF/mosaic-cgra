"""Independent cycle model of registered nodes and reverse-ready skid cuts.

The oracle uses dictionaries and sets, not RTL packed masks or pending helpers.
Every branch owns its copy until consumed; a skid entry belongs to the link.
"""

from collections import deque
from static_mesh.topology import dimensions, physical


def lanes(value, count, width):
    return [(value >> (i * width)) & ((1 << width) - 1) for i in range(count)]


class MeshModel:
    def __init__(self, parameters, routes):
        self.p = parameters
        self.a = dimensions(parameters)
        self.g = physical(parameters)
        self.routes = routes
        self.nodes = {}
        self.skids = {}
        self.incoming = {b: deque() for b in range(self.a["B"])}
        self.outgoing = {b: deque() for b in range(self.a["B"])}
        self.accepted = self.delivered = self.flushed = 0
        self.link_transfers = 0
        self.copies = 0

    def destinations(self, resource):
        return {o for (n, o), source in self.routes.items() if (n, source) == resource}

    def endpoints(self, resource):
        """Graph-level multicast oracle, separate from cycle transition logic."""
        results = []
        node, _ = resource
        for out in sorted(self.destinations(resource)):
            if out < self.a["RX"]:
                results.append(("tile", node * self.a["RX"] + out))
            else:
                edge = self.g["edges"][self.g["outputs"][node, out]]
                if "boundary_output" in edge:
                    results.append(("boundary", edge["boundary_output"]))
                else:
                    results.extend(
                        self.endpoints((edge["destination_node"], edge["destination_port"]))
                    )
        return results

    def occupancy(self):
        return (
            len(self.nodes)
            + len(self.skids)
            + sum(map(len, self.incoming.values()))
            + sum(map(len, self.outgoing.values()))
        )

    def step(self, ports, *, ingress=True, transport=True):
        a, p, g = self.a, self.p, self.g
        if not ports["i_reset_n"] or ports["i_flush"]:
            self.flushed += self.occupancy()
            self.nodes.clear()
            self.skids.clear()
            for q in (*self.incoming.values(), *self.outgoing.values()):
                q.clear()
            return dict(tile={}, boundary={}, ready_tile=set(), ready_boundary=set(), links=0)
        depth = p["BOUNDARY_BUFFER_DEPTH"]
        faults = ports["o_faulted_link_mask"]
        good = lambda l: transport and not (faults >> l & 1)
        tile_ready = set(i for i in range(a["N"] * a["RX"]) if ports["i_tile_rx_ready"] >> i & 1)
        boundary_ready = set(i for i in range(a["B"]) if ports["i_boundary_tx_ready"] >> i & 1)
        outputs = {}
        for (node, _), (packet, pending) in self.nodes.items():
            for out in pending:
                outputs[node, out] = packet
        ready_out = {}
        for node, out in self.routes:
            if out < a["RX"]:
                ready_out[node, out] = transport and node * a["RX"] + out in tile_ready
            else:
                link = g["outputs"][node, out]
                edge = g["edges"][link]
                if "boundary_output" in edge:
                    b = edge["boundary_output"]
                    ready_out[node, out] = good(link) and (
                        b in boundary_ready
                        if depth == 0
                        else len(self.outgoing[b]) < depth or b in boundary_ready
                    )
                else:
                    ready_out[node, out] = good(link) and link not in self.skids
        ready_in = {}
        for resource in {(n, i) for (n, _), i in self.routes.items()}:
            pending = self.nodes.get(resource, (None, set()))[1]
            ready_in[resource] = transport and all(ready_out[resource[0], out] for out in pending)
        tile = {
            n * a["RX"] + o: packet
            for (n, o), packet in outputs.items()
            if o < a["RX"] and transport
        }
        boundary = {}
        incoming_packets = {}
        for link, packet in self.skids.items():
            edge = g["edges"][link]
            if good(link):
                incoming_packets[edge["destination_node"], edge["destination_port"]] = packet
        transfers = 0
        for edge in g["edges"][: a["IL"]]:
            link = edge["index"]
            if not (g["mask"] >> link & 1):
                continue
            src = edge["source_node"], edge["source_port"]
            dst = edge["destination_node"], edge["destination_port"]
            if good(link) and link not in self.skids and src in outputs:
                incoming_packets[dst] = outputs[src]
                transfers |= 1 << link
        ready_boundary = set()
        for b in range(a["B"]):
            link = a["IL"] + 2 * b
            if not p["EXPOSE_BOUNDARY_PORTS"] or not (g["mask"] >> link & 1):
                continue
            edge = g["edges"][link]
            dst = edge["destination_node"], edge["destination_port"]
            packet = (
                (ports["i_boundary_rx_data"] >> (b * a["D"])) & ((1 << a["D"]) - 1),
                (ports["i_boundary_rx_metadata"] >> (b * a["M"])) & ((1 << a["M"]) - 1),
            )
            valid = ingress and good(link) and ports["i_boundary_rx_valid"] >> b & 1
            consume = good(link) and ready_in.get(dst, False)
            if depth == 0:
                if valid:
                    incoming_packets[dst] = packet
                if consume and ingress and good(link):
                    ready_boundary.add(b)
            else:
                if self.incoming[b] and good(link):
                    incoming_packets[dst] = self.incoming[b][0]
                capacity = len(self.incoming[b]) < depth or consume
                if ingress and good(link) and capacity:
                    ready_boundary.add(b)
                if self.incoming[b] and consume:
                    self.incoming[b].popleft()
                if valid and capacity:
                    self.incoming[b].append(packet)
            if valid and b in ready_boundary:
                transfers |= 1 << link
        for b in range(a["B"]):
            link = a["IL"] + 2 * b + 1
            if not p["EXPOSE_BOUNDARY_PORTS"] or not (g["mask"] >> link & 1):
                continue
            edge = g["edges"][link]
            src = edge["source_node"], edge["source_port"]
            if depth == 0:
                if good(link) and src in outputs:
                    boundary[b] = outputs[src]
            else:
                if self.outgoing[b] and good(link):
                    boundary[b] = self.outgoing[b][0]
                if b in boundary and b in boundary_ready:
                    self.outgoing[b].popleft()
                if src in outputs and ready_out.get(src, False):
                    self.outgoing[b].append(outputs[src])
            if b in boundary and b in boundary_ready:
                transfers |= 1 << link
        ready_tile = set()
        for node in range(a["N"]):
            for i in range(a["TX"]):
                j = node * a["TX"] + i
                if ingress and ready_in.get((node, i), False):
                    ready_tile.add(j)
                if ingress and ports["i_tile_tx_valid"] >> j & 1:
                    incoming_packets[node, i] = (
                        ports["i_tile_tx_data"] >> (j * a["D"]) & ((1 << a["D"]) - 1),
                        ports["i_tile_tx_metadata"] >> (j * a["M"]) & ((1 << a["M"]) - 1),
                    )
        for edge in g["edges"][: a["IL"]]:
            link = edge["index"]
            if not (g["mask"] >> link & 1):
                continue
            src = edge["source_node"], edge["source_port"]
            dst = edge["destination_node"], edge["destination_port"]
            if good(link):
                if link in self.skids:
                    if ready_in.get(dst, False):
                        del self.skids[link]
                elif src in outputs and not ready_in.get(dst, False):
                    self.skids[link] = outputs[src]
        updated = {}
        for resource, (packet, pending) in self.nodes.items():
            left = {out for out in pending if not ready_out[resource[0], out]}
            if left:
                updated[resource] = packet, left
        for resource, packet in incoming_packets.items():
            if ready_in.get(resource, False):
                updated[resource] = packet, self.destinations(resource)
        self.nodes = updated
        self.accepted += (ports["i_tile_tx_valid"] & sum(1 << j for j in ready_tile)).bit_count()
        self.delivered += sum(j in tile_ready for j in tile)
        self.link_transfers += transfers.bit_count()
        return dict(
            tile=tile,
            boundary=boundary,
            ready_tile=ready_tile,
            ready_boundary=ready_boundary,
            links=transfers,
        )
