"""Integer reference codecs; no implementation state or generated RTL is consulted."""
from copy import deepcopy
from bct.defaults import DEFAULTS as BCT_DEFAULTS
from bct.model import pack as bct_pack, sources
from mst.defaults import DEFAULTS as MST_DEFAULTS
from mst.model import pack as mst_pack
from static_mesh.defaults import DEFAULTS as MESH_DEFAULTS
from static_mesh.topology import image as mesh_image, dimensions, physical, metadata

BCT_PARAMETERS = BCT_DEFAULTS | dict(DATA_INPUT_PORTS=2, DATA_OUTPUT_PORTS=2,
    DATA_METADATA_WIDTH=256, TILE_ID_WIDTH=8, RUNTIME_TAG_WIDTH=16)
MST_PARAMETERS = MST_DEFAULTS | dict(SHELL_DATA_WIDTH=32, EXECUTION_EPOCH_WIDTH=4,
    MAX_ELEMENT_BYTES=8, TILE_ID_WIDTH=8, RUNTIME_TAG_WIDTH=16)


def mesh_parameters(descriptor):
    return MESH_DEFAULTS | dict(MESH_ROWS=descriptor['rows'], MESH_COLS=descriptor['cols'],
        LINK_METADATA_WIDTH=512, LINK_EPOCH_WIDTH=4, SCHEDULE_PERIOD_MAX=16, CONTROL_PROTECTION=1)


def crc32c(value, size):
    crc = 0xffffffff
    for byte in value.to_bytes(size, 'little'):
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0x82f63b78 if crc & 1 else 0)
    return crc ^ 0xffffffff


def ordered_tiles(descriptor):
    return sorted(descriptor['tiles'], key=lambda t: (t['row'], t['col']))


def cycle_order(descriptor):
    """A perimeter Hamilton cycle for the released 2x2 integration campaign."""
    if descriptor['rows'] != 2:
        raise ValueError('The end-to-end cycle campaign requires the 2x2 profile')
    ring = [0, 1, 3, 2]
    mst = next(i for i, t in enumerate(ordered_tiles(descriptor)) if t['class'] == 'MST')
    start = ring.index(mst)
    return ring[start:] + ring[:start]


def routes(descriptor, *, boundary=False):
    p = mesh_parameters(descriptor)
    a, graph = dimensions(p), physical(p)
    order = cycle_order(descriptor)
    # Each hop is a separate tile-produced stream. Tile ejection/injection queues
    # break execution dependencies; the mesh certificate still checks its channels.
    result = {}
    hops = list(zip(order, order[1:] + order[:1]))
    if boundary:
        hops = hops[1:-1]  # First BCT -> second BCT -> third BCT.
    for source, dest in hops:
        edge = next(e for e in graph['edges'] if e.get('source_node') == source and
                    e.get('destination_node') == dest)
        result[source, edge['source_port']] = 0
        result[dest, 0] = edge['destination_port']
    if boundary:
        first, last = order[1], order[-1]
        ingress = next(e for e in graph['edges'] if e.get('destination_node') == first and
                       'boundary_input' in e)
        egress = next(e for e in graph['edges'] if e.get('source_node') == last and
                      'boundary_output' in e)
        result[first, 0] = ingress['destination_port']
        result[last, egress['source_port']] = 0
        return result, ingress['boundary_input'], egress['boundary_output']
    return result, None, None


def images(descriptor, *, owner, kernel, package, allocation, context, count,
           region_generation=1, boundary=False):
    tiles = ordered_tiles(descriptor)
    order = cycle_order(descriptor)
    increment = {slot: i for i, slot in enumerate(order[1:], 1)}
    result = []
    for slot, tile in enumerate(tiles):
        if tile['class'] == 'BCT':
            s = sources(BCT_PARAMETERS)
            context_image = dict(schema=1, source_a=0, source_b=s['immediate'],
                source_c=s['zero'], opcode=0, output_mask=1, iterations=count,
                terminal=1, monitor=1, immediates=increment[slot])
            result.append(bct_pack(BCT_PARAMETERS, context_image))
        else:
            result.append(mst_pack(MST_PARAMETERS, 'context', dict(schema=1,
                package_id=package, allocation=allocation, automatic_command=0,
                terminal=0, loads=1, stores=1, regions=1)))
    selected, ingress, egress = routes(descriptor, boundary=boundary)
    p = mesh_parameters(descriptor)
    words = dimensions(p)['WORDS']
    raw, proof, certificate = mesh_image(p, selected, version=words, kernel=kernel)
    result.append(raw)
    a = (descriptor['scratchpad_banks'] * descriptor['scratchpad_bank_words'] * 8 - 1).bit_length()
    capacity = 1 << a
    policy = 1 | capacity << (8 + a) | 15 << (9 + 2*a) | 15 << (13 + 2*a)
    policy |= (owner | kernel << 16 | region_generation << 32) << 64
    result.append(policy)
    return result, dict(proof=proof, certificate=certificate, ingress=ingress, egress=egress)


def descriptor(identity, *, store=False, count=8, base=0, destination=256):
    return dict(identity=deepcopy(identity),
        mode=dict(transfer=int(store), address_mode=0, load_channel=0, store_channel=0),
        source=dict(space=2 if store else 0, base=base, channel=0,
                    region_id=0, region_generation=1),
        destination=dict(space=0 if store else 2, base=destination, channel=0,
                         region_id=0, region_generation=1),
        format=dict(source_log2=2, destination_log2=2, lane_log2=0, datatype=0, eos=1),
        events=dict(start=0, completion_enable=1, completion_id=int(store)),
        control=dict(inner_count=count, outer_count=1, priority_hint=0, timeout=4095, cancelable=1))


def envelope(d, *, owner, kernel, package, context, version, epoch, common=0, source=255):
    p = mesh_parameters(d)
    return (metadata(p, context, version, kernel, epoch) | common << 64 |
            owner << 320 | package << 336 | source << 368)


def expected_results(values, stages=3):
    return [(value + sum(range(1, stages+1))) & 0xffffffff for value in values]
