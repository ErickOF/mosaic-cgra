"""Directed lane/slice access and conflict-free randomized vector traffic."""

from itertools import combinations, product
import random
from pyuvm import uvm_sequence
from mosaic_uvm.logic import bits
from vector_register_file.transaction import VectorRegisterFileItem, fields, pack


class VectorRegisterFileSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__('vector_register_file_sequence')
        self.config = config
        self.rng = random.Random(config.seed)
        self.ports = {name: '0'*width for name, width in config.widths.items() if name.startswith('i_')}

    async def send(self, label, *, edge=True, random=False, four_state_data=False, quiet=False, **changes):
        for name, value in changes.items():
            self.ports[name] = bits(value, self.config.widths[name])
        item = VectorRegisterFileItem(label, self.ports, edge=edge, random=random, four_state_data=four_state_data, quiet=quiet)
        await self.start_item(item)
        await self.finish_item(item)

    def reads(self, address):
        c = self.config
        return dict(i_read_enable=(1 << c.read_ports)-1,
            i_read_lane_enable=(1 << (c.read_ports*c.lanes))-1,
            i_read_address=pack([address]*c.read_ports, c.address_width))

    def write(self, port, address, vector, mask=None, broadcast=0):
        c = self.config
        addresses, data, masks = [0]*c.write_ports, [0]*c.write_ports, [0]*c.write_ports
        addresses[port], data[port] = address, vector
        masks[port] = (1 << c.mask_width)-1 if mask is None else mask
        return dict(i_write_enable=1 << port, i_write_mask=pack(masks, c.mask_width),
            i_write_broadcast=broadcast << port, i_write_address=pack(addresses, c.address_width),
            i_write_data=pack(data, c.width))

    async def initialize(self):
        c = self.config
        for address in range(c.depth):
            await self.send('uninitialized_read', edge=False, i_write_enable=0, **self.reads(address))
        await self.send('partial_initialization', **(self.reads(0) | self.write(0, 0, 0, 1)))
        for address in range(c.depth):
            await self.send('initialize_vector', **(self.reads(address) | self.write(0, address, self.rng.getrandbits(c.width))))

    async def addresses_and_timing(self):
        c = self.config
        for w, address in product(range(c.write_ports), range(c.depth)):
            await self.send('every_port_entry', **(self.reads(address) | self.write(w, address, self.rng.getrandbits(c.width))))
            await self.send('read_after_write', i_write_enable=0)
        for r, w, other in product(range(c.read_ports), range(c.write_ports), range(min(2, c.depth))):
            await self.send('collision_baseline', **(self.reads(0) | self.write(w, 0, 0)))
            addresses = [0]*c.read_ports; addresses[r] = other
            await self.send('masked_setup_without_edge', edge=False, i_read_address=pack(addresses, c.address_width),
                **self.write(w, 0, (1 << c.width)-1, sum(1 << s for s in range(0, c.mask_width, 2))))
            await self.send('masked_read_during_write')
            await self.send('read_after_masked_write', i_write_enable=0)

    async def lanes_and_masks(self):
        c = self.config
        full_lanes, full_mask = (1 << c.lanes)-1, (1 << c.mask_width)-1
        for r, enabled, population in product(range(c.read_ports), (0, 1), range(c.lanes+1)):
            masks = [0]*c.read_ports; masks[r] = (1 << population)-1
            await self.send('read_lane_population', edge=False, i_write_enable=0,
                i_read_enable=enabled << r, i_read_lane_enable=pack(masks, c.lanes), i_read_address=0)
        for r, lane, complement in product(range(c.read_ports), range(c.lanes), (False, True)):
            masks = [0]*c.read_ports; masks[r] = full_lanes ^ (1 << lane) if complement else 1 << lane
            await self.send('individual_read_lane', edge=False, i_read_enable=1 << r, i_read_lane_enable=pack(masks, c.lanes))
        for w, broadcast in product(range(c.write_ports), (0, 1) if c.broadcast else (0,)):
            masks = {(1 << population)-1 for population in range(c.mask_width+1)}
            masks.update(1 << s for s in range(c.mask_width))
            masks.update(((1 << c.slices_per_lane)-1) << (lane*c.slices_per_lane) for lane in range(c.lanes))
            masks.update(sum(1 << s for s in range(start, c.mask_width, 2)) for start in (0, 1))
            for mask in sorted(masks):
                await self.send('write_mask_population', **(self.reads(0) |
                    self.write(w, 0, self.rng.getrandbits(c.width), mask, broadcast)))

        for re, we in product(range(1 << c.read_ports), range(1 << c.write_ports)):
            if we.bit_count() > c.depth*c.mask_width:
                continue
            addresses, masks, cursor = [0]*c.write_ports, [0]*c.write_ports, 0
            for w in range(c.write_ports):
                if we & (1 << w):
                    addresses[w], masks[w] = cursor//c.mask_width, 1 << (cursor % c.mask_width)
                    cursor += 1
            await self.send('port_enable_cross', i_read_enable=re, i_read_lane_enable=(1 << (c.read_ports*c.lanes))-1,
                i_read_address=pack([r % c.depth for r in range(c.read_ports)], c.address_width),
                i_write_enable=we, i_write_mask=pack(masks, c.mask_width), i_write_broadcast=0,
                i_write_address=pack(addresses, c.address_width), i_write_data=self.rng.getrandbits(c.write_ports*c.width))
        for a, b in combinations(range(c.read_ports), 2):
            for other in range(min(2, c.depth)):
                addresses = [0]*c.read_ports; addresses[b] = other
                await self.send('read_port_pair', edge=False, i_write_enable=0, i_read_enable=(1 << a) | (1 << b),
                    i_read_lane_enable=(1 << (c.read_ports*c.lanes))-1, i_read_address=pack(addresses, c.address_width))
        for a, b in combinations(range(c.write_ports), 2):
            for same in (False, True):
                if same and c.mask_width == 1 or not same and c.depth == 1:
                    continue
                addresses, masks = [0]*c.write_ports, [0]*c.write_ports
                addresses[b] = 0 if same else 1
                masks[a] = sum(1 << s for s in range(0, c.mask_width, 2)) if same else full_mask
                masks[b] = full_mask ^ masks[a] if same else full_mask
                await self.send('simultaneous_merged_writes', i_write_enable=(1 << a) | (1 << b),
                    i_write_mask=pack(masks, c.mask_width), i_write_broadcast=(1 << b) if c.broadcast else 0,
                    i_write_address=pack(addresses, c.address_width),
                    i_write_data=pack([self.rng.getrandbits(c.width) for _ in range(c.write_ports)], c.width), **self.reads(addresses[b]))

    async def patterns_and_ignored(self):
        c = self.config
        maximum = (1 << c.slice_width)-1
        words = {0, maximum, 1, maximum ^ 1, sum(1 << bit for bit in range(0, c.slice_width, 2))}
        masks = {1, (1 << c.mask_width)-1, (1 << c.slices_per_lane)-1, sum(1 << s for s in range(0, c.mask_width, 2))}
        for w, mask, word in product(range(c.write_ports), sorted(masks), sorted(words)):
            vector = pack([word]*c.mask_width, c.slice_width)
            await self.send('pattern_mask_cross', **(self.reads(0) | self.write(w, 0, vector, mask)))
        for w, state in product(range(c.write_ports), 'xz'):
            await self.send('intentional_four_state_write', four_state_data=True,
                **(self.reads(0) | self.write(w, 0, state*c.width)))
            await self.send('intentional_four_state_read', edge=False, i_write_enable=0)
            await self.send('restore_known_vector', **self.write(w, 0, 0))
            if c.mask_width > 1:
                slices = [state*c.slice_width]*c.mask_width; slices[0] = 0
                await self.send('unmasked_unknown_slices', **self.write(w, 0, pack(slices, c.slice_width), 1))
            if c.broadcast:
                vector = pack([0]+[state*c.lane_width]*(c.lanes-1), c.lane_width)
                await self.send('broadcast_ignores_other_lanes', **self.write(w, 0, vector, broadcast=1))
            else:
                await self.send('disabled_broadcast_unknown', **(self.write(w, 0, self.rng.getrandbits(c.width)) |
                    dict(i_write_broadcast=state*c.write_ports)))
        for state in 'xz':
            await self.send('disabled_unknown_inputs', i_read_enable=0, i_read_lane_enable=state*(c.read_ports*c.lanes),
                i_read_address=state*(c.read_ports*c.address_width), i_write_enable=0,
                i_write_mask=state*(c.write_ports*c.mask_width), i_write_broadcast=state*c.write_ports,
                i_write_address=state*(c.write_ports*c.address_width), i_write_data=state*(c.write_ports*c.width))
            await self.send('zero_lane_and_write_masks', i_read_enable=(1 << c.read_ports)-1, i_read_lane_enable=0,
                i_write_enable=(1 << c.write_ports)-1, i_write_mask=0)

    async def probe(self):
        c = self.config
        await self.initialize()
        name, state, bit = c.probe.split(':')
        changes = self.reads(0) | self.write(0, 0, 0)
        if name == 'write_conflict':
            address, selected = map(int, bit.split(','))
            changes |= dict(i_write_enable=3, i_write_mask=pack([1 << selected]*c.write_ports, c.mask_width),
                i_write_address=pack([address]*c.write_ports, c.address_width))
        elif name == 'broadcast_data':
            w, source_bit = divmod(int(bit), c.lane_width)
            vector = list('0'*c.width); vector[-source_bit-1] = state
            changes |= self.write(w, 0, ''.join(vector),
                ((1 << c.slices_per_lane)-1) << ((c.lanes-1)*c.slices_per_lane), 1)
        elif state == 'range':
            port, address = map(int, bit.split(','))
            addresses = [0]*(c.read_ports if name == 'i_read_address' else c.write_ports)
            addresses[port] = address
            changes[name] = pack(addresses, c.address_width)
            changes['i_read_enable' if name == 'i_read_address' else 'i_write_enable'] = 1 << port
            if name == 'i_write_address':
                changes['i_write_mask'] = pack([(1 << c.mask_width)-1]*c.write_ports, c.mask_width)
        else:
            word = list(bits(changes.get(name, 0), c.widths[name])); word[-int(bit)-1] = state
            changes[name] = ''.join(word)
            if name.startswith('i_write_') and name != 'i_write_enable':
                divisor = dict(i_write_address=c.address_width, i_write_data=c.width,
                    i_write_mask=c.mask_width, i_write_broadcast=1)[name]
                changes['i_write_enable'] = 1 << (int(bit)//divisor)
                if name != 'i_write_mask':
                    changes['i_write_mask'] = (1 << c.widths['i_write_mask'])-1
        await self.send('illegal_access', **changes)
        raise AssertionError('Illegal stimulus did not trigger its live assertion')

    async def body(self):
        if self.config.probe:
            await self.probe()
            return
        await self.initialize()
        await self.addresses_and_timing()
        await self.lanes_and_masks()
        await self.patterns_and_ignored()
        c = self.config
        for index in range(c.random_cycles):
            addresses = [self.rng.randrange(c.depth) for _ in range(c.write_ports)]
            masks, occupied = [], set()
            for w in range(c.write_ports):
                mask = self.rng.getrandbits(c.mask_width)
                mask &= ~sum(1 << s for address, s in occupied if address == addresses[w])
                occupied.update((addresses[w], s) for s in range(c.mask_width) if mask & (1 << s))
                masks.append(mask)
            await self.send(f'random_{index}', random=True, i_read_enable=self.rng.getrandbits(c.read_ports),
                i_read_lane_enable=self.rng.getrandbits(c.read_ports*c.lanes),
                i_read_address=pack([self.rng.randrange(c.depth) for _ in range(c.read_ports)], c.address_width),
                i_write_enable=self.rng.getrandbits(c.write_ports), i_write_mask=pack(masks, c.mask_width),
                i_write_broadcast=self.rng.getrandbits(c.write_ports), i_write_address=pack(addresses, c.address_width),
                i_write_data=self.rng.getrandbits(c.write_ports*c.width))
        for address in range(c.depth):
            await self.send('final_storage_audit', edge=False, i_write_enable=0, **self.reads(address))
        await self.send('final_idle', i_read_enable=0, i_write_enable=0)
