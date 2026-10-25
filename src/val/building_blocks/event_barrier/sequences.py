"""Directed boundaries, permutations, contention and persistent random producers."""
from itertools import permutations
import random
from pyuvm import uvm_sequence
from event_barrier.model import number
from event_barrier.transaction import EventBarrierItem, INPUTS


class EventBarrierSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__('event_barrier_sequence')
        self.c = config
        self.rng = random.Random(config.seed)
        self.index = 0
        self.base = dict.fromkeys(INPUTS, 0)
        self.base.update(i_rstb=1, i_wait_result_ready=1, i_barrier_release_ready=1)
        self.last = None

    async def cycle(self, label='idle', *, edge=True, random=False, fault='', **ports):
        self.index += 1
        item = EventBarrierItem(f'{self.index}_{label}', self.base | ports,
                                edge=edge, random=random, fault=fault)
        await self.start_item(item)
        await self.finish_item(item)
        self.last = item.observation.ports
        return item

    async def send(self, channel, **ports):
        valid = 'i_' + channel + '_valid'
        ready = 'o_' + channel + '_ready'
        for _ in range(200):
            item = await self.cycle(channel, **(ports | {valid: 1}))
            if number(item.pre.ports[ready]):
                return item
        raise AssertionError(f'Transfer starved: {channel}')

    async def policy(self, enable=None):
        await self.send('config', i_config_context_id=1,
                        i_config_event_enable=(1 << self.c.NUM_EVENTS) - 1 if enable is None else enable)

    async def flush(self):
        await self.cycle('flush', i_flush=1)
        await self.cycle()

    async def reset(self):
        await self.cycle('reset_clockless', i_rstb=0, edge=False)
        await self.cycle('reset', i_rstb=0)
        await self.cycle()

    async def post(self, event=0):
        return await self.send('post', i_post_event_id=event, i_post_context_id=1)

    async def ack(self, event=0, mode=1):
        return await self.send('ack', i_ack_event_id=event, i_ack_mode=mode, i_ack_context_id=1)

    async def arm(self, slot=0, mask=1, mode=0, consume=0, **ports):
        return await self.send('wait', **(dict(i_wait_slot=slot, i_wait_mode=mode, i_wait_event_mask=mask,
            i_wait_consume=consume, i_wait_context_id=1, i_wait_tag=slot) | ports))

    async def barrier(self, barrier=0, mask=1, event=False, **ports):
        return await self.send('barrier_config', **(dict(i_barrier_config_id=barrier,
            i_barrier_config_enable=1, i_barrier_expected_mask=mask, i_barrier_context_id=1,
            i_barrier_tag=barrier, i_barrier_release_event_enable=int(event),
            i_barrier_release_event_id=0) | ports))

    def generation(self, barrier):
        return (number(self.last['o_barrier_generation']) >> (barrier * self.c.GENERATION_WIDTH)) & ((1 << self.c.GENERATION_WIDTH) - 1)

    async def arrive(self, barrier=0, participant=0, **ports):
        return await self.send('barrier_arrival', **(dict(i_barrier_arrival_id=barrier,
            i_barrier_participant_id=participant, i_barrier_arrival_context_id=1,
            i_barrier_arrival_generation=self.generation(barrier)) | ports))

    async def directed(self):
        c = self.c
        await self.reset()
        await self.policy()
        await self.send('config', i_config_context_id='x' * c.CONTEXT_ID_WIDTH)
        await self.policy()
        maximum = (1 << c.EVENT_COUNT_WIDTH) - 1
        for event in range(c.NUM_EVENTS):
            for _ in range(maximum):
                await self.post(event)
            for _ in range(3):
                item = await self.cycle('saturated', i_post_valid=1, i_post_event_id=event, i_post_context_id=1)
                assert number(item.pre.ports['o_post_ready']) == 0
            await self.ack(event, 0)
            await self.post(event)
            await self.ack(event, 1)
            await self.ack(event, 0)
        await self.send('post', i_post_event_id=0, i_post_context_id=0)
        assert number(self.last['o_error']) == 1
        await self.cycle('quiescent_error_clear', i_error_clear=1)
        assert number(self.last['o_error']) == 0
        await self.flush()
        await self.policy(enable=0)
        await self.post()
        await self.flush()
        await self.policy()
        # Every ANY winner, consume mode, wait slot, and ALL arrival permutation.
        for event in range(c.NUM_EVENTS):
            await self.arm(slot=event % c.NUM_WAIT_SLOTS, mask=1 << event)
            await self.post(event)
            await self.cycle()
            await self.cycle()
            await self.ack(event)
        for slot in range(c.NUM_WAIT_SLOTS):
            await self.post()
            await self.arm(slot=slot, consume=c.SUPPORT_WAIT_CONSUME)
            await self.cycle()
            await self.cycle()
            await self.flush()
        positions = tuple(range(min(c.NUM_EVENTS, 3)))
        for order in permutations(positions):
            for consume in sorted({0, c.SUPPORT_WAIT_CONSUME}):
                await self.arm(mask=sum(1 << e for e in positions), mode=1, consume=consume)
                for event in order:
                    await self.post(event)
                await self.cycle()
                await self.cycle()
                await self.flush()
        # Dense masks exercise all 64 positions without claiming 64! permutations.
        for order in (range(c.NUM_EVENTS), reversed(range(c.NUM_EVENTS))):
            await self.arm(mask=(1 << c.NUM_EVENTS) - 1, mode=1, consume=c.SUPPORT_WAIT_CONSUME)
            for event in order:
                await self.post(event)
            await self.cycle()
            await self.cycle()
            await self.flush()
        # An active wait cannot be overwritten; mismatched cancellation cannot remove it.
        await self.arm()
        item = await self.cycle('active_slot_not_overwritten', i_wait_valid=1,
            i_wait_context_id=1, i_wait_event_mask=1, i_wait_tag=1)
        assert number(item.pre.ports['o_wait_ready']) == 0
        await self.send('wait_cancel', i_wait_cancel_context_id=1, i_wait_cancel_tag=1)
        assert number(self.last['o_wait_slot_active']) & 1
        await self.flush()
        for channel, name, limit in (
            ('post', 'i_post_event_id', c.NUM_EVENTS),
            ('wait', 'i_wait_slot', c.NUM_WAIT_SLOTS),
            ('barrier_config', 'i_barrier_config_id', c.NUM_BARRIERS),
            ('barrier_arrival', 'i_barrier_participant_id', c.MAX_PARTICIPANTS)):
            if limit < (1 << c.widths[name]):
                await self.send(channel, **{name: limit})
        await self.arm(mask=0)
        await self.arm(mode=3)
        await self.send('wait_cancel', i_wait_cancel_context_id=1)
        for satisfied in (False, True):
            await self.arm()
            if satisfied:
                await self.post()
            await self.send('wait_cancel', i_wait_cancel_context_id=1)
            await self.cycle()
            await self.flush()
        # Fill the wait-result queue, hold outputs, and test cancel/completion stall.
        await self.post()
        for _ in range(c.WAIT_RESULT_QUEUE_DEPTH):
            await self.arm(i_wait_result_ready=0)
            await self.cycle(i_wait_result_ready=0)
        await self.arm(i_wait_result_ready=0)
        for _ in range(4):
            await self.cycle('result_backpressure', i_wait_result_ready=0,
                             i_wait_cancel_valid=1, i_wait_cancel_context_id=1)
        await self.cycle(i_wait_cancel_valid=1, i_wait_cancel_context_id=1)
        await self.flush()
        # All slots satisfied together; continuously rearmed low slots cannot starve peers.
        for slot in range(c.NUM_WAIT_SLOTS):
            await self.arm(slot=slot)
        await self.post()
        for _ in range(4 * c.NUM_WAIT_SLOTS + c.WAIT_RESULT_QUEUE_DEPTH):
            await self.cycle()
        assert number(self.last['o_wait_slot_active']) == 0
        await self.flush()
        # Full participant masks, one-hot masks, sparse shapes, all barriers.
        for barrier in range(c.NUM_BARRIERS):
            for participant in range(c.MAX_PARTICIPANTS):
                await self.barrier(barrier, 1 << participant)
                await self.arrive(barrier, participant)
                await self.cycle()
            shapes = {(1 << c.MAX_PARTICIPANTS) - 1,
                      sum(1 << k for k in range(0, c.MAX_PARTICIPANTS, 2))}
            for mask in sorted(shapes):
                await self.barrier(barrier, mask)
                order = [k for k in reversed(range(c.MAX_PARTICIPANTS)) if mask & (1 << k)]
                for k, participant in enumerate(order):
                    await self.arrive(barrier, participant)
                    if k == 0 and len(order) > 1:
                        await self.arrive(barrier, participant)
                await self.cycle()
        # Exhaust every order of up to three expected participants.
        subset = tuple(range(min(c.MAX_PARTICIPANTS, 3)))
        for order in permutations(subset):
            await self.barrier(mask=sum(1 << k for k in subset))
            for participant in order:
                await self.arrive(participant=participant)
            await self.cycle()
        if c.MAX_PARTICIPANTS > 1:
            await self.barrier(mask=1)
            await self.arrive(participant=1)
        # Explicit duplicate even for the smallest supported participant profile.
        if c.MAX_PARTICIPANTS > 1:
            await self.barrier(mask=3)
            await self.arrive(participant=0)
            await self.arrive(participant=0)
            await self.arrive(participant=1, i_barrier_arrival_context_id=0)
            await self.arrive(participant=1, i_barrier_arrival_generation=(self.generation(0) + 1) % (1 << c.GENERATION_WIDTH))
            await self.arrive(participant=1)
            await self.cycle()
        else:
            # No legal nonfinal state exists for one participant; no duplicate bin.
            pass
        await self.barrier(mask=0)
        await self.barrier(mask=1)
        # Generation wrap and release queue saturation.
        for _ in range((1 << c.GENERATION_WIDTH) + 1):
            await self.arrive()
            await self.cycle()
        for _ in range(c.BARRIER_RELEASE_QUEUE_DEPTH):
            await self.arrive(i_barrier_release_ready=0)
        for _ in range(4):
            item = await self.cycle('release_full', i_barrier_arrival_valid=1,
                i_barrier_arrival_context_id=1, i_barrier_arrival_generation=self.generation(0),
                i_barrier_release_ready=0)
            assert number(item.pre.ports['o_barrier_arrival_ready']) == 0
        await self.arrive()
        await self.flush()
        # Final-arrival event overflow and four-client mutation contention.
        if c.SUPPORT_BARRIER_EVENTS:
            await self.barrier(event=True)
            for _ in range(maximum):
                await self.post()
            for _ in range(3):
                item = await self.cycle('release_event_saturated', i_barrier_arrival_valid=1,
                    i_barrier_arrival_context_id=1, i_barrier_arrival_generation=self.generation(0))
                assert number(item.pre.ports['o_barrier_arrival_ready']) == 0
            await self.ack(mode=0)
            await self.arrive()
            await self.ack()
        await self.flush()
        await self.barrier(event=bool(c.SUPPORT_BARRIER_EVENTS))
        # Independently persistent producers; collect all four contenders together.
        await self.post()
        await self.arm(consume=c.SUPPORT_WAIT_CONSUME)
        pending = {
            'post': dict(i_post_event_id=0, i_post_context_id=1),
            'ack': dict(i_ack_event_id=0, i_ack_mode=0, i_ack_context_id=1),
            'barrier_arrival': dict(i_barrier_arrival_id=0, i_barrier_participant_id=0,
                i_barrier_arrival_context_id=1, i_barrier_arrival_generation=self.generation(0)),
        }
        for _ in range(30):
            ports = {}
            for channel, fields in pending.items():
                ports.update(fields, **{'i_' + channel + '_valid': 1})
            item = await self.cycle('contention', **ports)
            pending = {ch: fields for ch, fields in pending.items()
                       if not number(item.pre.ports['o_' + ch + '_ready'])}
            if not pending:
                break
        assert not pending, 'Persistent mutation requester starved'
        await self.flush()

    async def live_reset(self):
        # Assert reset without a clock while event, wait and both queues are live.
        # Synchronous profiles retain registered state until the next rising edge.
        await self.flush()
        await self.post()
        await self.arm(i_wait_result_ready=0)
        await self.cycle(i_wait_result_ready=0)
        await self.barrier(mask=1, i_wait_result_ready=0)
        await self.arrive(i_wait_result_ready=0, i_barrier_release_ready=0)
        await self.arm(mask=1, i_wait_result_ready=0, i_barrier_release_ready=0)
        await self.reset()
        await self.policy()
        # Flush discards the same live state with no synthetic completion records.
        await self.post()
        await self.arm(i_wait_result_ready=0)
        await self.cycle(i_wait_result_ready=0)
        await self.barrier(mask=1, i_wait_result_ready=0)
        await self.arrive(i_wait_result_ready=0, i_barrier_release_ready=0)
        await self.cycle('flush_live_queues', i_flush=1,
                         i_wait_result_ready=0, i_barrier_release_ready=0)
        await self.cycle()

    async def unknowns(self):
        c = self.c
        fixtures = (
            ('config', 'i_config_context_id', {}),
            ('post', 'i_post_event_id', dict(i_post_context_id=1)),
            ('post', 'i_post_context_id', {}),
            ('ack', 'i_ack_mode', dict(i_ack_context_id=1)),
            ('wait', 'i_wait_mode', dict(i_wait_context_id=1, i_wait_event_mask=1)),
            ('wait', 'i_wait_event_mask', dict(i_wait_context_id=1)),
            ('wait', 'i_wait_consume', dict(i_wait_context_id=1, i_wait_event_mask=1)),
            ('wait', 'i_wait_tag', dict(i_wait_context_id=1, i_wait_event_mask=1)),
            ('barrier_config', 'i_barrier_expected_mask', dict(i_barrier_context_id=1)),
            ('barrier_arrival', 'i_barrier_arrival_generation', dict(i_barrier_arrival_context_id=1)),
            ('barrier_arrival', 'i_barrier_participant_id', dict(i_barrier_arrival_context_id=1)),
        )
        for state in 'xz':
            for channel, name, fields in fixtures:
                await self.flush()
                await self.send(channel, **(fields | {name: state * c.widths[name]}))
            for name in ('i_rstb', 'i_post_valid', 'i_wait_valid', 'i_flush', 'i_error_clear',
                         'i_wait_result_ready', 'i_barrier_release_ready'):
                await self.cycle('unknown_control', **{name: state})
                await self.flush()

    async def faults(self):
        if not self.c.PROTECT_STATE or not self.c.check_internals:
            return
        for target in ('policy', 'event', 'wait', 'barrier', 'generation', 'queue'):
            await self.reset()
            await self.policy()
            await self.post()
            await self.arm(i_wait_result_ready=0)
            await self.cycle(i_wait_result_ready=0)
            await self.cycle('parity_fault', fault=target, i_wait_result_ready=0)
            for _ in range(3):
                await self.cycle('fatal_frozen', i_post_valid=1, i_post_context_id=1, i_flush=1)
            assert number(self.last['o_fatal_error']) == 1
        await self.reset()
        await self.policy()

    async def randomized(self):
        c, rng = self.c, self.rng
        pending = {}
        channels = ('post', 'ack', 'wait', 'wait_cancel', 'barrier_config', 'barrier_arrival')
        for cycle in range(c.random_cycles):
            if cycle % 97 == 0:
                pending.clear()
                await self.cycle('random_flush', random=True, i_flush=1)
                continue
            for channel in channels:
                if channel in pending or rng.random() > 0.35:
                    continue
                owner = 1 if rng.random() < 0.9 else 0
                event = rng.randrange(1 << c.widths['i_post_event_id'])
                slot = rng.randrange(1 << c.widths['i_wait_slot'])
                barrier = rng.randrange(1 << c.widths['i_barrier_config_id'])
                fields = {
                    'post': dict(i_post_event_id=event, i_post_context_id=owner),
                    'ack': dict(i_ack_event_id=event, i_ack_context_id=owner, i_ack_mode=rng.randrange(4)),
                    'wait': dict(i_wait_slot=slot, i_wait_context_id=owner, i_wait_mode=rng.randrange(4),
                        i_wait_event_mask=rng.getrandbits(c.NUM_EVENTS), i_wait_consume=rng.randrange(2), i_wait_tag=slot),
                    'wait_cancel': dict(i_wait_cancel_slot=slot, i_wait_cancel_context_id=owner, i_wait_cancel_tag=slot),
                    'barrier_config': dict(i_barrier_config_id=barrier, i_barrier_config_enable=rng.randrange(2),
                        i_barrier_expected_mask=rng.getrandbits(c.MAX_PARTICIPANTS), i_barrier_context_id=owner,
                        i_barrier_tag=barrier, i_barrier_release_event_enable=rng.randrange(2), i_barrier_release_event_id=event),
                    'barrier_arrival': dict(i_barrier_arrival_id=barrier,
                        i_barrier_participant_id=rng.randrange(1 << c.widths['i_barrier_participant_id']),
                        i_barrier_arrival_context_id=owner,
                        i_barrier_arrival_generation=self.generation(barrier) if barrier < c.NUM_BARRIERS else 0),
                }[channel]
                # Tags remain opaque at narrow widths.
                fields = {name: value & ((1 << c.widths[name]) - 1) for name, value in fields.items()}
                pending[channel] = fields
            ports = dict(i_wait_result_ready=int(rng.random() < .65),
                         i_barrier_release_ready=int(rng.random() < .65))
            for channel, fields in pending.items():
                ports.update(fields, **{'i_' + channel + '_valid': 1})
            item = await self.cycle('random', random=True, **ports)
            pending = {channel: fields for channel, fields in pending.items()
                       if not number(item.pre.ports['o_' + channel + '_ready'])}

    async def body(self):
        await self.directed()
        await self.live_reset()
        await self.unknowns()
        await self.faults()
        await self.randomized()
        await self.flush()
        await self.cycle('error_clear', i_error_clear=1)
        await self.reset()
        await self.cycle()
