"""Initialization, scalar accesses, port independence and seeded legal traffic."""

from itertools import product
import random
from pyuvm import uvm_sequence
from mosaic_uvm.logic import bits
from register_file.transaction import RegisterFileItem, pack


class RegisterFileSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__('register_file_sequence')
        self.config = config
        self.rng = random.Random(config.seed)
        self.ports = {name: '0'*width for name, width in config.widths.items() if name != 'o_read_data'}

    async def send(self, label, *, edge=True, random=False, four_state_data=False, **changes):
        for name, value in changes.items():
            self.ports[name] = bits(value, self.config.widths[name])
        item = RegisterFileItem(label, self.ports, edge=edge, random=random, four_state_data=four_state_data)
        await self.start_item(item)
        await self.finish_item(item)

    def reads(self, address):
        c = self.config
        return dict(i_read_enable=(1 << c.read_ports)-1, i_read_address=pack([address]*c.read_ports, c.address_width))

    def write(self, port, address, word):
        c = self.config
        addresses, data = [0]*c.write_ports, [0]*c.write_ports
        addresses[port], data[port] = address, word
        return dict(i_write_enable=1 << port, i_write_address=pack(addresses, c.address_width), i_write_data=pack(data, c.width))

    async def initialize(self):
        c = self.config
        for address in range(c.depth):
            # Unwritten reads are legal but have no deterministic data oracle.
            await self.send('uninitialized_read', edge=False, i_write_enable=0, **self.reads(address))
        for address in range(c.depth):
            await self.send('first_write', **(self.reads(address) | self.write(0, address, self.rng.getrandbits(c.width))))

    async def addresses_and_timing(self):
        c = self.config
        maximum = (1 << c.width)-1
        for w, address, value in product(range(c.write_ports), range(c.depth), (0, maximum)):
            await self.send('every_write_port_address', **(self.reads(address) | self.write(w, address, value)))
            await self.send('read_after_write', i_write_enable=0)
        for address in range(c.depth):
            await self.send('combinational_read', edge=False, i_write_enable=0, **self.reads(address))
        for r, w, relation in product(range(c.read_ports), range(c.write_ports), range(min(2, c.depth))):
            # Change write pins without a clock to reject implicit forwarding.
            await self.send('collision_baseline', **(self.reads(0) | self.write(w, 0, 0)))
            addresses = [0]*c.read_ports
            addresses[r] = relation
            changes = dict(i_read_enable=1 << r, i_read_address=pack(addresses, c.address_width)) | self.write(w, 0, maximum)
            await self.send('write_setup_without_edge', edge=False, **changes)
            await self.send('read_during_write')
            await self.send('read_after_write', i_write_enable=0)
        for distance in range(1, c.depth) if c.write_ports > 1 else ():
            await self.send('simultaneous_write_distance', i_write_enable=3,
                i_write_address=pack([0, distance] + [0]*(c.write_ports-2), c.address_width),
                i_write_data=pack([0, maximum] + [0]*(c.write_ports-2), c.width), **self.reads(distance))

    async def concurrency(self):
        c = self.config
        for re, we in product(range(1 << c.read_ports), range(1 << c.write_ports)):
            if we.bit_count() > c.depth:
                continue
            addresses, cursor = [], 0
            for w in range(c.write_ports):
                addresses.append(cursor if we & (1 << w) else 0)
                cursor += bool(we & (1 << w))
            for same in (True, False):
                await self.send('enable_cross', i_read_enable=re,
                    i_read_address=pack([0 if same else r % c.depth for r in range(c.read_ports)], c.address_width),
                    i_write_enable=we, i_write_address=pack(addresses, c.address_width),
                    i_write_data=pack([self.rng.getrandbits(c.width) for _ in range(c.write_ports)], c.width))
        # Every pair can read the same address and, where possible, different
        # addresses, even when there are more read ports than physical words.
        for a in range(c.read_ports):
            for b in range(a+1, c.read_ports):
                for other in range(min(2, c.depth)):
                    addresses = [0]*c.read_ports
                    addresses[b] = other
                    await self.send('read_port_pair', edge=False, i_write_enable=0,
                        i_read_enable=(1 << a) | (1 << b), i_read_address=pack(addresses, c.address_width))

    async def patterns_and_ignored_inputs(self):
        c = self.config
        maximum = (1 << c.width)-1
        patterns = {0, maximum, sum(1 << bit for bit in range(0, c.width, 2)), sum(1 << bit for bit in range(1, c.width, 2))}
        patterns.update(1 << bit for bit in range(c.width))
        patterns.update(maximum ^ (1 << bit) for bit in range(c.width))
        for w, value in product(range(c.write_ports), sorted(patterns)):
            await self.send('data_pattern_write', **(self.reads(0) | self.write(w, 0, value)))
            await self.send('data_pattern_read', edge=False, i_write_enable=0)
        for w, state in product(range(c.write_ports), 'xz'):
            # Explicitly intentional four-state transport, outside normal known
            # data operation. The default checker still rejects accidental X/Z.
            await self.send('intentional_four_state_write', four_state_data=True,
                **(self.reads(0) | self.write(w, 0, state*c.width)))
            await self.send('intentional_four_state_read', edge=False, i_write_enable=0)
            await self.send('restore_known_data', **self.write(w, 0, 0))
        for state in 'xz':
            await self.send('all_disabled_unknown_inputs', i_read_enable=0, i_read_address=state*(c.read_ports*c.address_width),
                i_write_enable=0, i_write_address=state*(c.write_ports*c.address_width), i_write_data=state*(c.write_ports*c.width))
            # Ignore each disabled port while the remaining ports stay active.
            for r in range(c.read_ports):
                addresses = [0]*c.read_ports
                addresses[r] = state*c.address_width
                await self.send('disabled_read_independence', edge=False, i_write_enable=0,
                    i_read_enable=((1 << c.read_ports)-1) ^ (1 << r), i_read_address=pack(addresses, c.address_width))
            for w in range(c.write_ports):
                addresses, data = [0]*c.write_ports, [0]*c.write_ports
                addresses[w], data[w] = state*c.address_width, state*c.width
                other = (w+1) % c.write_ports
                await self.send('disabled_write_independence', i_write_enable=1 << other if other != w else 0,
                    i_write_address=pack(addresses, c.address_width), i_write_data=pack(data, c.width), **self.reads(0))

    async def probe(self):
        c = self.config
        await self.initialize()
        name, state, bit = c.probe.split(':')
        changes = self.reads(0) | self.write(0, 0, 1)
        if name == 'write_conflict':
            changes |= dict(i_write_enable=int(bit), i_write_address=pack([int(state)]*c.write_ports, c.address_width))
        elif state == 'range':
            port, address = map(int, bit.split(','))
            addresses = [0]*(c.read_ports if name == 'i_read_address' else c.write_ports)
            addresses[port] = address
            changes[name] = pack(addresses, c.address_width)
            changes['i_read_enable' if name == 'i_read_address' else 'i_write_enable'] = 1 << port
        else:
            word = list(bits(changes.get(name, 0), c.widths[name]))
            word[-int(bit)-1] = state
            changes[name] = ''.join(word)
            if name == 'i_write_address':
                changes['i_write_enable'] = 1 << (int(bit)//c.address_width)
            elif name == 'i_write_data':
                changes['i_write_enable'] = 1 << (int(bit)//c.width)
        await self.send('illegal_access', **changes)
        raise AssertionError('Illegal stimulus did not trigger its live assertion')

    async def body(self):
        if self.config.probe:
            await self.probe()
            return
        await self.initialize()
        await self.addresses_and_timing()
        await self.concurrency()
        await self.patterns_and_ignored_inputs()
        c = self.config
        for index in range(c.random_cycles):
            enabled = self.rng.sample(range(c.write_ports), self.rng.randrange(min(c.depth, c.write_ports)+1))
            targets = self.rng.sample(range(c.depth), len(enabled))
            addresses = [self.rng.randrange(c.depth) for _ in range(c.write_ports)]
            for w, address in zip(enabled, targets):
                addresses[w] = address
            await self.send(f'random_{index}', random=True, i_read_enable=self.rng.getrandbits(c.read_ports),
                i_read_address=pack([self.rng.randrange(c.depth) for _ in range(c.read_ports)], c.address_width),
                i_write_enable=sum(1 << w for w in enabled), i_write_address=pack(addresses, c.address_width),
                i_write_data=pack([self.rng.getrandbits(c.width) for _ in range(c.write_ports)], c.width))
        for address in range(c.depth):
            await self.send('final_storage_audit', edge=False, i_write_enable=0, **self.reads(address))
        await self.send('final_idle', i_read_enable=0, i_write_enable=0)
