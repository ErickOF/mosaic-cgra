"""Stable producers, topology-aware configurations and adversarial consumers."""
import random
from pyuvm import uvm_sequence
from mosaic_uvm.logic import bits
from local_switch.model import lane
from local_switch.transaction import INPUTS, LocalSwitchItem


class LocalSwitchSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__('local_switch_sequence')
        self.c = config
        self.rng = random.Random(config.seed)
        self.p = dict.fromkeys(INPUTS, 0)
        self.p.update(i_rstb=1, i_output_ready=(1 << config.NUM_OUTPUTS) - 1)
        self.offers = [None] * config.NUM_INPUTS
        self.last = None
        self.serial = 0

    def offer(self, i, data=None, metadata=None):
        assert self.offers[i] is None
        self.offers[i] = (self.rng.getrandbits(self.c.DATA_WIDTH) if data is None else data,
                          self.rng.getrandbits(self.c.METADATA_WIDTH) if metadata is None else metadata)

    async def tick(self, label='cycle', *, edge=True, random=False, fault=None, **values):
        c = self.c
        data = [offer or (self.rng.getrandbits(c.DATA_WIDTH), self.rng.getrandbits(c.METADATA_WIDTH))
                for offer in self.offers]
        ports = self.p | dict(i_flush=0, i_error_clear=0, i_config_valid=0,
            i_input_valid=sum(1 << i for i, offer in enumerate(self.offers) if offer is not None),
            i_input_data=''.join(bits(d, c.DATA_WIDTH) for d, _ in reversed(data)),
            i_input_metadata=''.join(bits(m, c.METADATA_WIDTH) for _, m in reversed(data))) | values
        item = LocalSwitchItem(label, ports, edge=edge, random=random, fault=fault)
        await self.start_item(item)
        await self.finish_item(item)
        pre = item.pre.ports
        if ports['i_rstb'] == 0 and (edge or c.ASYNC_RESET):
            self.offers = [None] * c.NUM_INPUTS
        elif edge and ports['i_rstb'] == 1:
            if ports['i_flush'] == 1:
                self.offers = [None] * c.NUM_INPUTS
            else:
                for i in range(c.NUM_INPUTS):
                    if pre['o_input_ready'][-i - 1] == '1' and pre['i_input_valid'][-i - 1] == '1':
                        self.offers[i] = None
        self.last = item.observation.ports
        self.serial += 1
        return self.last

    def routes(self):
        c = self.c
        enabled = int(self.last['o_active_output_enable'], 2)
        return [int(lane(self.last['o_active_output_select'], o, c.aliases['INPUT_SELECT_WIDTH']), 2)
                if enabled >> o & 1 else None for o in range(c.NUM_OUTPUTS)]

    def config(self, routes):
        c = self.c
        self.p.update(i_config_output_enable=sum(1 << o for o, i in enumerate(routes) if i is not None),
            i_config_output_select=sum((i if i is not None else self.rng.randrange(
                1 << c.aliases['INPUT_SELECT_WIDTH'])) << (o * c.aliases['INPUT_SELECT_WIDTH'])
                for o, i in enumerate(routes)), i_config_context_id=self.rng.getrandbits(c.CONTEXT_ID_WIDTH))

    async def configure(self, routes):
        self.config(routes)
        for _ in range(32):
            post = await self.tick('configure routes', i_config_valid=1)
            if post['o_config_accepted'] == '1' or post['o_config_rejected'] == '1':
                return post
        raise AssertionError('Stable configuration was never consumed')

    async def drain(self):
        for _ in range(128):
            post = await self.tick('fair drain')
            if post['o_idle'] == '1' and not any(self.offers):
                return
        raise AssertionError('Fair consumers could not drain copies and producers')

    async def reset(self):
        await self.tick('clockless coordinated reset', edge=False, i_rstb=0)
        await self.tick('reset edge', i_rstb=0)
        await self.tick('reset release')

    async def clear(self):
        post = await self.tick('quiescent error clear', i_error_clear=1)
        assert post['o_error'] == '0'

    def matching(self):
        assigned = {}
        def find(i, visited):
            for o in range(self.c.NUM_OUTPUTS):
                if (i, o) in self.c.edges and o not in visited:
                    visited.add(o)
                    if o not in assigned or find(assigned[o], visited):
                        assigned[o] = i
                        return True
            return False
        for i in range(self.c.NUM_INPUTS):
            find(i, set())
        return [assigned.get(o) for o in range(self.c.NUM_OUTPUTS)]

    async def edges_and_rate(self):
        c = self.c
        for i, o in sorted(c.edges):
            routes = [None] * c.NUM_OUTPUTS
            routes[o] = i
            await self.configure(routes)
            for data, meta in ((0, 0), ((1 << c.DATA_WIDTH) - 1, (1 << c.METADATA_WIDTH) - 1)):
                self.offer(i, data, meta)
                await self.tick('physical edge capture')
                await self.drain()
        # Drive every independently routed source at one item per cycle.
        routes = self.matching()
        await self.configure(routes)
        sources = sorted(set(routes) - {None})
        for cycle in range(24):
            for i in sources:
                self.offer(i)
            post = await self.tick('maximum unicast rate')
            assert int(post['o_event_input_accept'], 2) == sum(1 << i for i in sources)
            if cycle:
                assert int(post['o_event_output_transfer'], 2) == sum(
                    1 << o for o, i in enumerate(routes) if i is not None)
        await self.drain()
        # Fill each occupancy class and exercise independent blocked owners.
        for count in range(1, len(sources) + 1):
            for i in sources[:count]:
                self.offer(i)
            await self.tick('occupancy fill', i_output_ready=0)
            await self.tick('occupied hold', i_output_ready=0)
            await self.tick('clockless occupied hold', edge=False, i_output_ready=0)
            await self.tick('flush each occupancy', i_flush=1)
            for i in sources[:count]:
                self.offer(i)
            await self.tick('fill before occupancy reset', i_output_ready=0)
            await self.reset()
            await self.configure(routes)
        # One output may stall without preventing an unrelated source progressing.
        if len(sources) > 1:
            blocked = next(o for o, i in enumerate(routes) if i == sources[0])
            for i in sources:
                self.offer(i)
            await self.tick('independent sources fill', i_output_ready=0)
            for _ in range(8):
                for i in sources[1:]:
                    if self.offers[i] is None:
                        self.offer(i)
                await self.tick('independent stalled output', i_output_ready=((1 << c.NUM_OUTPUTS) - 1) ^ (1 << blocked))
            await self.drain()
        # The item layout remains opaque, including known-valid four-state payloads.
        self.offer(sources[0], 'x' * c.DATA_WIDTH, 'z' * c.METADATA_WIDTH)
        await self.tick('opaque four-state capture', i_output_ready=0)
        await self.tick('opaque held payload', i_output_ready=0)
        await self.drain()

    async def fanout_and_flush(self):
        c = self.c
        for i in range(c.NUM_INPUTS):
            outputs = [o for source, o in sorted(c.edges) if source == i]
            if not outputs:
                continue
            sizes = range(1, len(outputs) + 1) if c.SUPPORT_MULTICAST else (1,)
            for size in sizes:
                routes = [i if o in outputs[:size] else None for o in range(c.NUM_OUTPUTS)]
                await self.configure(routes)
                self.offer(i)
                await self.tick('fanout capture', i_output_ready=0)
                await self.drain()
            if c.SUPPORT_MULTICAST:
                await self.configure([i if o in outputs else None for o in range(c.NUM_OUTPUTS)])
                if len(outputs) > 1:
                    full = sum(1 << o for o in outputs)
                    for o in outputs:
                        self.offer(i)
                        await self.tick('capture before first consumer', i_output_ready=0)
                        await self.tick('unique first multicast consumer', i_output_ready=1 << o)
                        await self.drain()
                        self.offer(i)
                        await self.tick('capture before last consumer', i_output_ready=0)
                        await self.tick('all but last multicast consumer', i_output_ready=full ^ (1 << o))
                        await self.tick('unique last multicast consumer', i_output_ready=1 << o)
                # Exhaust every subset of delivered destinations, then flush the rest.
                for subset in range(1 << len(outputs)):
                    self.offer(i)
                    await self.tick('multicast capture', i_output_ready=0)
                    ready = sum(1 << o for k, o in enumerate(outputs) if subset >> k & 1)
                    await self.tick('partial multicast progress', i_output_ready=ready)
                    await self.tick('flush partial state', i_flush=1)
                # All destinations consume one old item while a new one replaces it.
                for _ in range(12):
                    self.offer(i)
                    await self.tick('maximum multicast rate')
                await self.drain()
            else:
                for o in outputs:
                    routes = [i if k == o else None for k in range(c.NUM_OUTPUTS)]
                    await self.configure(routes)
                    self.offer(i)
                    await self.tick('unicast before flush', i_output_ready=0)
                    await self.tick('unicast flush', i_flush=1)
        await self.tick('empty flush', i_flush=1)

    async def configuration_errors(self):
        c = self.c
        cases = []
        if c.NUM_INPUTS < 1 << c.aliases['INPUT_SELECT_WIDTH']:
            routes = [None] * c.NUM_OUTPUTS
            routes[0] = c.NUM_INPUTS
            cases.append(routes)
        missing = next(((i, o) for i in range(c.NUM_INPUTS) for o in range(c.NUM_OUTPUTS)
                        if (i, o) not in c.edges), None)
        if missing:
            i, o = missing
            routes = [None] * c.NUM_OUTPUTS
            routes[o] = i
            cases.append(routes)
        if not c.SUPPORT_MULTICAST:
            for i in range(c.NUM_INPUTS):
                outputs = [o for source, o in sorted(c.edges) if source == i]
                if len(outputs) > 1:
                    cases.append([i if o in outputs[:2] else None for o in range(c.NUM_OUTPUTS)])
                    break
        for routes in cases:
            post = await self.configure(routes)
            assert post['o_config_rejected'] == '1'
            await self.clear()
        await self.configure([None] * c.NUM_OUTPUTS)
        for name in ('i_config_output_enable', 'i_config_output_select', 'i_config_context_id'):
            for bit in ('x', 'z'):
                await self.tick('unknown configuration', i_config_valid=1, **{name: bit * c.widths[name]})
                assert self.last['o_config_rejected'] == '1' and self.last['o_error_code'] == '100'
                await self.clear()
        for name in ('i_flush', 'i_error_clear', 'i_config_valid', 'i_input_valid', 'i_output_ready', 'i_rstb'):
            for bit in ('x', 'z'):
                await self.tick('unknown handshake control', **{name: bit * c.widths[name]})
                await self.clear()

    async def held_config_and_error(self):
        c = self.c
        routes = self.matching()
        await self.configure(routes)
        source = next(i for i in routes if i is not None)
        self.offer(source)
        await self.tick('pending before sticky error', i_output_ready=0)
        await self.tick('unknown ready while pending', i_output_ready='x' * c.NUM_OUTPUTS)
        post = await self.tick('prohibited busy clear', i_output_ready=0, i_error_clear=1)
        assert post['o_error'] == '1'
        # Hold a new complete descriptor through a stalled old-context item.
        self.config(routes)
        for _ in range(5):
            await self.tick('held configuration', i_config_valid=1, i_output_ready=0)
            assert self.last['o_config_ready'] == '0'
        for _ in range(4):
            await self.tick('drain then install held config', i_config_valid=1)
            if self.last['o_config_accepted'] == '1':
                break
        else:
            raise AssertionError('Held context was not installed after drain')
        assert self.last['o_error'] == '1', 'Legal configuration implicitly cleared sticky error'
        await self.clear()
        # Configuration has priority over a concurrent input offer while empty.
        self.offer(source)
        await self.tick('atomic configuration priority', i_config_valid=1)
        assert int(self.last['o_event_input_accept'], 2) == 0
        await self.drain()

    async def state_faults(self):
        if not self.c.check_internals:
            return
        await self.configure([None] * self.c.NUM_OUTPUTS)
        for fault, code in (({'valid': {0: 1}}, 5),
                            ({'valid': {0: 1}, 'pending': {0: 1}}, 6),
                            ({'pending': {0: 1}}, 7),
                            ({'pending': {0: 'x' * self.c.NUM_OUTPUTS}}, 7)):
            await self.tick('ownership fault', fault=fault)
            assert int(self.last['o_error_code'], 2) == code
            await self.tick('fault cannot clear while occupied', i_error_clear=1)
            await self.tick('flush corrupt ownership', i_flush=1)
            await self.clear()

    async def random_campaign(self):
        c = self.c
        remaining = c.random_cycles
        epoch = 0
        while remaining:
            routes = []
            used = set()
            for o in range(c.NUM_OUTPUTS):
                sources = [i for i in range(c.NUM_INPUTS) if (i, o) in c.edges and
                           (c.SUPPORT_MULTICAST or i not in used)]
                source = self.rng.choice(sources) if sources and self.rng.random() > .25 else None
                routes.append(source)
                if source is not None:
                    used.add(source)
            if not any(i is not None for i in routes):
                i, o = self.rng.choice(sorted(c.edges))
                routes[o] = i
            await self.configure(routes)
            count = min(remaining, self.rng.randint(48, 120))
            sources = set(routes) - {None}
            for cycle in range(count):
                for i in sources:
                    if self.offers[i] is None and self.rng.random() > .25:
                        self.offer(i)
                ready = sum(1 << o for o in range(c.NUM_OUTPUTS) if self.rng.random() > .35)
                await self.tick('random independent traffic', random=True, i_output_ready=ready)
            remaining -= count
            if epoch % 3 == 0:
                await self.tick('random context flush', i_flush=1)
            else:
                await self.drain()
            epoch += 1

    async def body(self):
        await self.reset()
        for i in range(self.c.NUM_INPUTS):
            self.offer(i)
        for _ in range(4):
            await self.tick('traffic blocked before first configuration')
            assert int(self.last['o_input_ready'], 2) == 0
        await self.tick('cancel unconfigured producers', i_flush=1)
        await self.edges_and_rate()
        await self.fanout_and_flush()
        await self.configuration_errors()
        await self.held_config_and_error()
        await self.state_faults()
        # Coordinated resets with a whole or partially delivered owned item.
        i = next(iter(sorted(self.c.edges)))[0]
        outputs = [o for source, o in sorted(self.c.edges) if source == i]
        selected = outputs if self.c.SUPPORT_MULTICAST else outputs[:1]
        for partial in (False, True):
            await self.configure([i if o in selected else None for o in range(self.c.NUM_OUTPUTS)])
            self.offer(i)
            await self.tick('capture before active reset', i_output_ready=0)
            if partial:
                await self.tick('partial copies before reset', i_output_ready=1 << selected[0])
            await self.reset()
        await self.random_campaign()
        for _ in range(3):
            await self.tick('final idle')
