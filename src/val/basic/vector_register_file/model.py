"""Independent slice-aware storage with unspecified power-up content and no bypass."""

from collections import Counter
from dataclasses import dataclass
from vector_register_file.transaction import fields, known


@dataclass(frozen=True)
class Write:
    port: int
    address: int
    slices: dict[int, str]
    broadcast: str


def effective_slices(config, vector, broadcast):
    normal = fields(vector, config.slice_width)
    if not config.broadcast or broadcast == '0':
        return normal
    scalar = fields(vector, config.lane_width)[0]
    replicated = fields(scalar, config.slice_width)*config.lanes
    if broadcast == '1':
        return replicated
    return tuple(''.join(a if a == b else 'x' for a, b in zip(normal[s], replicated[s], strict=True))
        for s in range(config.mask_width))


def legal_writes(config, ports):
    addresses = fields(ports['i_write_address'], config.address_width)
    masks = fields(ports['i_write_mask'], config.mask_width)
    vectors = fields(ports['i_write_data'], config.width)
    writes = []
    for w, address in enumerate(addresses):
        if ports['i_write_enable'][-w-1] == '1' and known(address) and int(address, 2) < config.depth:
            values = effective_slices(config, vectors[w], ports['i_write_broadcast'][-w-1])
            selected = {s: values[s] for s, bit in enumerate(reversed(masks[w])) if bit == '1'}
            if selected:
                writes.append(Write(w, int(address, 2), selected, ports['i_write_broadcast'][-w-1] if config.broadcast else '0'))
    return tuple(writes)


def read_violation(config, ports):
    if not known(ports['i_read_enable']):
        return 'read_enable'
    lanes = fields(ports['i_read_lane_enable'], config.lanes)
    for r, address in enumerate(fields(ports['i_read_address'], config.address_width)):
        if ports['i_read_enable'][-r-1] == '1':
            if not known(lanes[r]):
                return f'read_lane_enable:{r}'
            if '1' in lanes[r] and (not known(address) or int(address, 2) >= config.depth):
                return f'read_address:{r}'
    return None


def write_violation(config, ports, intentional):
    if not known(ports['i_write_enable']):
        return 'write_enable'
    addresses = fields(ports['i_write_address'], config.address_width)
    masks = fields(ports['i_write_mask'], config.mask_width)
    vectors = fields(ports['i_write_data'], config.width)
    for w, mask in enumerate(masks):
        if ports['i_write_enable'][-w-1] != '1':
            continue
        if not known(mask):
            return f'write_mask:{w}'
        if '1' not in mask:
            continue
        if not known(addresses[w]) or int(addresses[w], 2) >= config.depth:
            return f'write_address:{w}'
        broadcast = ports['i_write_broadcast'][-w-1]
        if config.broadcast and broadcast not in '01':
            return f'write_broadcast:{w}'
        values = effective_slices(config, vectors[w], broadcast)
        if not intentional and any(not known(values[s]) for s, bit in enumerate(reversed(mask)) if bit == '1'):
            return f'write_data:{w}'
    owners = Counter((write.address, s) for write in legal_writes(config, ports) for s in write.slices)
    return 'write_conflict' if any(count > 1 for count in owners.values()) else None


class VectorRegisterFileModel:
    def __init__(self, config):
        self.config = config
        # A functional slice becomes specified only through a modeled write.
        self.slices = [[None]*config.mask_width for _ in range(config.depth)]
        self.raw = None

    def step(self, ports):
        writes = legal_writes(self.config, ports)
        owners = Counter((write.address, s) for write in writes for s in write.slices)
        for write in writes:
            for s, data in write.slices.items():
                value = data if owners[write.address, s] == 1 else None
                self.slices[write.address][s] = value
                if self.raw is not None:
                    self.raw[write.address*self.config.mask_width+s] = value
        return writes

    def reads(self, ports):
        c = self.config
        expected = []
        lanes = fields(ports['i_read_lane_enable'], c.lanes)
        for r, address in enumerate(fields(ports['i_read_address'], c.address_width)):
            for s in range(c.mask_width):
                enable, lane_enable = ports['i_read_enable'][-r-1], lanes[r][-(s//c.slices_per_lane)-1]
                if '0' in (enable, lane_enable):
                    value = '0'*c.slice_width
                elif enable != '1' or lane_enable != '1' or not known(address):
                    value = 'x'*c.slice_width
                elif int(address, 2) >= c.depth:
                    value = '0'*c.slice_width
                else:
                    value = self.slices[int(address, 2)][s]
                expected.append(value)
        return expected
