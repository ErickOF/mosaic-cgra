"""Independent allocation expectations and native context image construction."""
from cluster.model import images, routes, cycle_order, mesh_parameters, dimensions, mesh_image
from static_mesh.topology import physical


def stream_images(descriptor, *, role='local', **identity):
    """Source: SRAM→three BCTs→NoC; sink: NoC→three BCTs→SRAM.

    NoC packets are not predicted by copying DUT results. The ordinary arithmetic
    reference model composes both local chains, and SRAM readback checks the result.
    """
    raw, info = images(descriptor, **identity)
    if role == 'local': return raw, info
    p = mesh_parameters(descriptor)
    graph = physical(p)
    selected, ingress, egress = routes(descriptor, boundary=True)
    order = cycle_order(descriptor)
    if role == 'source':
        edge = next(e for e in graph['edges'] if e.get('source_node') == order[0] and
                    e.get('destination_node') == order[1])
        selected.pop((order[1], 0))
        selected[order[0], edge['source_port']] = 0
        selected[order[1], 0] = edge['destination_port']
    elif role == 'sink':
        edge = next(e for e in graph['edges'] if e.get('source_node') == order[-1] and
                    e.get('destination_node') == order[0])
        boundary_edge = next(e for e in graph['edges'] if e.get('boundary_output') == egress)
        selected.pop((order[-1], boundary_edge['source_port']))
        selected[order[-1], edge['source_port']] = 0
        selected[order[0], 0] = edge['destination_port']
    else: raise ValueError(f'Unknown stream role: {role}')
    raw[-2], proof, certificate = mesh_image(p, selected,
        version=dimensions(p)['WORDS'], kernel=identity['kernel'])
    return raw, dict(proof=proof, certificate=certificate, ingress=ingress, egress=egress)


class AllocationModel:
    """Whole-mask software oracle independent of the RTL state representation."""
    def __init__(self, count):
        self.count = count
        self.serial = 0
        self.records = {}

    def allocate(self, mask, owner, kernel, package):
        if not 0 < mask < 1 << self.count or any(mask & m for m in self.records):
            raise ValueError('overlap/resource')
        if any(v[:2] == (owner, kernel) for v in self.records.values()):
            raise ValueError('duplicate kernel')
        self.serial += 1
        self.records[mask] = owner, kernel, package, self.serial
        return self.serial

    def authorize(self, mask, owner, kernel, package, generation):
        return self.records.get(mask) == (owner, kernel, package, generation)

    def release(self, mask, *identity):
        if not self.authorize(mask, *identity): raise ValueError('identity')
        del self.records[mask]
