"""Independent packet ledger, coordinate routes, framing, credits and ownership."""

from collections import deque


def integer(value):
    assert set(value) <= {'0', '1'}, f'Unexpected X/Z architectural value: {value}'
    return int(value, 2)


def part(value, index, width):
    return (integer(value) >> (index * width)) & ((1 << width) - 1)


def flit(config, ports, prefix, index):
    return {
        name: part(ports[f'{prefix}_{name}'], index, width)
        for name, width in config.field_widths.items()
    }


def route(config, node):
    if not 0 <= node < config.MESH_X * config.MESH_Y:
        return None
    x, y = node % config.MESH_X, node // config.MESH_X
    dx, dy = x - config.ROUTER_X, y - config.ROUTER_Y
    horizontal = 2 if dx > 0 else 4 if dx < 0 else 0
    vertical = 3 if dy > 0 else 1 if dy < 0 else 0
    return (horizontal or vertical) if not config.ROUTING_ALGORITHM else (vertical or horizontal)


class RouterModel:
    def __init__(self, config):
        self.c = config
        self.accepted = self.forwarded = self.discarded = self.sunk = self.canceled = 0
        self.serial = 0
        self.reset()

    def reset(self):
        c = self.c
        if hasattr(self, 'queues'):
            self.canceled += self.pending
        self.queues = [deque() for _ in range(5 * c.NUM_VCS)]
        self.flight = [deque() for _ in range(5)]
        self.frames = [None] * (5 * c.NUM_VCS)
        self.locks = [None] * 5
        self.output_owner = [None] * 5
        self.epochs = [0] * 5
        self.enable = self.fault = 0
        self.credits = [c.OUTPUT_INITIAL_CREDITS if c.FLOW_CONTROL else 0] * (5 * c.NUM_VCS)
        self.fatal = False

    @property
    def pending(self):
        return sum(map(len, self.queues)) + sum(map(len, self.flight))

    @property
    def idle(self):
        return not self.pending and not any(self.frames) and not any(self.locks)

    def flush(self):
        enable, fault, epochs, fatal = (
            self.enable,
            self.fault,
            self.epochs,
            self.fatal,
        )
        self.reset()
        self.enable, self.fault, self.fatal = enable, fault, fatal
        self.epochs = [(epoch + 1) % (1 << self.c.LINK_EPOCH_WIDTH) for epoch in epochs]

    def legal_config(self, enable, fault):
        return (
            bool(enable & 1)
            and not fault & 1
            and all(
                not (enable & ~fault & (1 << p)) or p in self.c.usable_ports() for p in range(5)
            )
        )

    def enqueue(self, p, f):
        c = self.c
        v = f['vc']
        if v >= c.NUM_VCS or f['epoch'] != self.epochs[p]:
            self.sunk += 1
            return
        index = p * c.NUM_VCS + v
        frame = self.frames[index]
        invariant = {
            name: value
            for name, value in f.items()
            if name not in ('data', 'keep', 'error', 'head', 'tail', 'fragment_index')
        }
        class_valid = f['traffic_class'] < c.NUM_TRAFFIC_CLASSES
        mapped_vc = (
            (c.TRAFFIC_CLASS_TO_VC >> (f['traffic_class'] * c.aliases['VW']))
            & ((1 << c.aliases['VW']) - 1)
            if class_valid
            else None
        )
        if frame is None:
            self.serial += 1
            destination = route(c, f['destination_node'])
            bad = (
                not f['head']
                or f['fragment_index'] != 0
                or not class_valid
                or mapped_vc != v
                or f['source_node'] >= c.MESH_X * c.MESH_Y
            )
            drop = (
                bad or destination is None or not (self.enable & ~self.fault & (1 << destination))
            )
            frame = dict(
                uid=self.serial,
                invariant=invariant,
                fragment=0,
                bad=bad,
                drop=drop,
                route=destination,
            )
        else:
            frame['bad'] |= bool(
                f['head']
                or f['fragment_index'] != frame['fragment']
                or invariant != frame['invariant']
                or not class_valid
                or mapped_vc != v
            )
        expected = dict(f)
        if frame['bad']:
            expected['error'] = (1 << c.ERROR_WIDTH) - 1
        record = dict(
            fields=expected,
            uid=frame['uid'],
            route=frame['route'],
            drop=frame['drop'],
            port=p,
            vc=v,
        )
        self.queues[index].append(record)
        frame['fragment'] = f['fragment_index'] + 1
        self.frames[index] = None if f['tail'] else frame

    def expected_output(self, p, actual):
        c = self.c
        records = (
            list(self.flight[p])[:1]
            if c.OUTPUT_PIPELINE
            else [q[0] for q in self.queues if q and not q[0]['drop'] and q[0]['route'] == p]
        )
        candidates = []
        for record in records:
            expected = record['fields'] | dict(epoch=self.epochs[p])
            if expected == actual:
                candidates.append(record)
        assert len(candidates) == 1, f'Output {p} has no unique accepted FIFO head: {actual}'
        return candidates[0]

    def check_outputs(self, ports):
        for p in range(5):
            valid = part(ports['o_out_valid'], p, 1)
            if not valid:
                assert all(
                    part(ports['o_out_' + name], p, width) == 0
                    for name, width in self.c.field_widths.items()
                ), f'Invalid output clamp {p}'
                assert part(ports['o_out_parity'], p, 1) == 0
                continue
            actual = flit(self.c, ports, 'o_out', p)
            self.expected_output(p, actual)
            parity = 0
            for value in actual.values():
                parity ^= value.bit_count() & 1
            assert part(ports['o_out_parity'], p, 1) == (parity if self.c.ENABLE_LINK_PARITY else 0)
            assert self.enable & ~self.fault & (1 << p)
            if self.c.FLOW_CONTROL:
                assert self.credits[p * self.c.NUM_VCS + actual['vc']] > 0

    def step(self, pre, post):
        c, p, after = self.c, pre.ports, post.ports
        if p['i_rstb'] == '0':
            self.reset()
            return dict(kind='reset')
        if p['i_flush'] == '1':
            owned = not self.idle
            self.flush()
            assert integer(after['o_flushed']) == owned
            return dict(kind='flush')
        if p['i_config_valid'] == p['o_config_ready'] == '1':
            known = set(p['i_config_port_enable'] + p['i_config_fault_port_mask']) <= {'0', '1'}
            enable = integer(p['i_config_port_enable']) if known else 0
            fault = integer(p['i_config_fault_port_mask']) if known else 0
            legal = known and self.legal_config(enable, fault)
            if legal:
                self.enable, self.fault = enable, fault
            assert integer(after['o_config_accepted']) == legal
            assert integer(after['o_config_rejected']) == (not legal)
            return dict(kind='config', legal=legal)
        self.check_outputs(p)
        popped = integer(pre.internal['queue_pop'])
        input_credit = 0
        input_credit_vc = 0
        input_credit_epoch = 0
        transfers = 0
        deliveries = []
        for port in range(5):
            pop_mask = (popped >> (port * c.NUM_VCS)) & ((1 << c.NUM_VCS) - 1)
            assert pop_mask.bit_count() <= 1, 'Physical input used more than once'
            for vc in range(c.NUM_VCS):
                if not pop_mask & (1 << vc):
                    continue
                q = self.queues[port * c.NUM_VCS + vc]
                assert q, 'Input FIFO underflow'
                record = q.popleft()
                if record['drop']:
                    self.discarded += 1
                else:
                    output = record['route']
                    lock = (vc, record['uid'], output)
                    assert self.locks[port] in (None, lock), 'Input packet interleaving'
                    assert self.output_owner[output] in (None, port), 'Output reservation collision'
                    self.locks[port] = lock
                    self.output_owner[output] = port
                    self.flight[output].append(record)
                input_credit |= 1 << port
                input_credit_vc |= vc << (port * c.aliases['VW'])
                input_credit_epoch |= self.epochs[port] << (port * c.LINK_EPOCH_WIDTH)
        for output in range(5):
            if part(p['o_out_valid'], output, 1) and (
                c.FLOW_CONTROL or part(p['i_out_ready'], output, 1)
            ):
                actual = flit(c, p, 'o_out', output)
                assert self.flight[output], 'Output flit without a switch traversal'
                record = self.flight[output].popleft()
                assert record['fields'] | dict(epoch=self.epochs[output]) == actual
                self.forwarded += 1
                deliveries.append(
                    (
                        record['port'],
                        output,
                        record['vc'],
                        actual['traffic_class'],
                        actual['head'],
                        actual['tail'],
                    )
                )
                transfers |= 1 << output
                if c.FLOW_CONTROL:
                    self.credits[output * c.NUM_VCS + actual['vc']] -= 1
                if actual['tail']:
                    self.locks[record['port']] = None
                    self.output_owner[output] = None
        if c.FLOW_CONTROL:
            for output in range(5):
                if part(p['i_out_credit_valid'], output, 1):
                    vc = part(p['i_out_credit_vc'], output, c.aliases['VW'])
                    epoch = part(p['i_out_credit_epoch'], output, c.LINK_EPOCH_WIDTH)
                    if (
                        self.enable & ~self.fault & (1 << output)
                        and vc < c.NUM_VCS
                        and epoch == self.epochs[output]
                        and self.credits[output * c.NUM_VCS + vc] < c.OUTPUT_INITIAL_CREDITS
                    ):
                        self.credits[output * c.NUM_VCS + vc] += 1
        accepted = integer(after['o_event_input_accept'])
        for port in range(5):
            if accepted & (1 << port):
                assert part(p['i_in_valid'], port, 1)
                if not c.FLOW_CONTROL:
                    assert part(p['o_in_ready'], port, 1)
                self.accepted += 1
                self.enqueue(port, flit(c, p, 'i_in', port))
        assert integer(after['o_event_output_transfer']) == transfers
        assert integer(after['o_in_credit_valid']) == (input_credit if c.FLOW_CONTROL else 0)
        if c.FLOW_CONTROL:
            assert integer(after['o_in_credit_vc']) == input_credit_vc
            assert integer(after['o_in_credit_epoch']) == input_credit_epoch
        self.fatal |= after['o_fatal_error'] == '1'
        return dict(
            kind='traffic',
            accepted=accepted,
            transfers=transfers,
            pops=popped,
            deliveries=deliveries,
        )

    def check_state(self, ports):
        c = self.c
        assert integer(ports['o_active_port_enable']) == self.enable
        assert integer(ports['o_active_fault_port_mask']) == self.fault
        for p in range(5):
            assert part(ports['o_link_epoch'], p, c.LINK_EPOCH_WIDTH) == self.epochs[p]
            assert part(ports['o_input_packet_locked'], p, 1) == bool(self.locks[p])
            assert part(ports['o_output_packet_locked'], p, 1) == (self.output_owner[p] is not None)
        for k, q in enumerate(self.queues):
            assert part(ports['o_input_vc_occupancy'], k, c.INPUT_VC_DEPTH.bit_length()) == len(q)
            assert len(q) <= c.INPUT_VC_DEPTH
            assert (
                part(ports['o_output_credit_count'], k, c.OUTPUT_INITIAL_CREDITS.bit_length())
                == self.credits[k]
            )
        assert (
            self.accepted
            == self.forwarded + self.discarded + self.sunk + self.canceled + self.pending
        )
