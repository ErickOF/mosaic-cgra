"""Independent per-destination copy queues, captured routes and ownership ledgers.

The model stores accepted transactions and their remaining destination queues. It
does not model the register-slice implementation or use DUT state for predictions.
"""
from collections import deque
from dataclasses import dataclass
from mosaic_uvm.logic import bits
from local_switch.transaction import CONFIG, EVENTS, OUTPUTS


def known(word):
    return set(word) <= {'0', '1'}


def number(word):
    return int(word, 2) if known(word) else None


def lane(word, index, width):
    end = len(word) - index * width
    return word[end - width:end]


@dataclass(frozen=True)
class Copy:
    source: int
    serial: int
    destinations: int
    data: str
    metadata: str
    accepted_edge: int


class LocalSwitchModel:
    def __init__(self, config):
        self.c = config
        self.edge = self.serial = 0
        self.accepted = [0] * config.NUM_INPUTS
        self.completed = [0] * config.NUM_INPUTS
        self.discarded = [0] * config.NUM_INPUTS
        self.copy_accepted = [0] * config.NUM_OUTPUTS
        self.copy_delivered = [0] * config.NUM_OUTPUTS
        self.copy_discarded = [0] * config.NUM_OUTPUTS
        self.queues = [deque() for _ in range(config.NUM_OUTPUTS)]
        self.fault = {}
        self.reset()

    def pending(self, source):
        return sum(1 << o for o, q in enumerate(self.queues) if q and q[0].source == source)

    def discard(self):
        for i in range(self.c.NUM_INPUTS):
            self.discarded[i] += int(bool(self.pending(i)))
        for o, q in enumerate(self.queues):
            self.copy_discarded[o] += len(q)
            q.clear()
        self.fault = {}

    def reset(self):
        self.discard()
        self.enabled = 0
        self.select = [0] * self.c.NUM_OUTPUTS
        self.context = 0
        self.error = 0
        self.events = {n: bits(0, self.c.widths[n]) for n in EVENTS}

    def destinations(self, source):
        return sum(1 << o for o in range(self.c.NUM_OUTPUTS)
                   if self.enabled >> o & 1 and self.select[o] == source)

    def raw_state(self):
        c = self.c
        valid = [bits(int(bool(self.pending(i))), 1) for i in range(c.NUM_INPUTS)]
        masks = [bits(self.pending(i), c.NUM_OUTPUTS) for i in range(c.NUM_INPUTS)]
        for name, entries in self.fault.items():
            target, width = (valid, 1) if name == 'valid' else (masks, c.NUM_OUTPUTS)
            for i, value in entries.items():
                target[i] = bits(value, width)
        return valid, masks

    def state_error(self, valid, masks):
        for i, (v, p) in enumerate(zip(valid, masks, strict=True)):
            if not known(v + p):
                return 7
            pending = int(p, 2)
            if v == '1' and not pending:
                return 5
            if v == '0' and pending:
                return 7
            if pending & ~self.destinations(i):
                return 6
        return 0

    def config_error(self, p):
        if not all(known(p[n]) for n in CONFIG):
            return 4
        enabled = int(p['i_config_output_enable'], 2)
        seen = set()
        for o in range(self.c.NUM_OUTPUTS):
            if not (enabled >> o & 1):
                continue
            source = int(lane(p['i_config_output_select'], o, self.c.aliases['INPUT_SELECT_WIDTH']), 2)
            if source >= self.c.NUM_INPUTS:
                return 1
            if (source, o) not in self.c.edges:
                return 2
            if not self.c.SUPPORT_MULTICAST and source in seen:
                return 3
            seen.add(source)
        return 0

    def evaluate(self, p):
        c = self.c
        run = p['i_rstb'] == '1'
        flush = run and p['i_flush'] == '1'
        global_known = all(known(p[n]) for n in ('i_flush', 'i_config_valid', 'i_error_clear'))
        unknown = not global_known or not known(p['i_input_valid'] + p['i_output_ready'])
        valid, masks = self.raw_state()
        state_error = self.state_error(valid, masks)
        idle = all(v == '0' and set(mask) == {'0'} for v, mask in zip(valid, masks, strict=True))
        allowed = run and p['i_flush'] == '0' and global_known and not state_error
        config_window = allowed and idle and p['i_config_valid'] == '1'
        traffic = allowed and not config_window
        out = {n: bits(0, c.widths[n]) for n in OUTPUTS}
        out.update(o_idle=bits(int(idle), 1), o_error=bits(int(bool(self.error)), 1),
                   o_error_code=bits(self.error, 3), o_active_output_enable=bits(self.enabled, c.NUM_OUTPUTS),
                   o_active_output_select=''.join(bits(v, c.aliases['INPUT_SELECT_WIDTH']) for v in reversed(self.select)),
                   o_active_context_id=bits(self.context, c.CONTEXT_ID_WIDTH),
                   o_input_buffered=''.join('1' if v == '1' else '0' for v in reversed(valid)),
                   o_pending_delivery=''.join(''.join(b if b == '1' else '0' for b in p) for p in reversed(masks)))
        if run:
            out.update(self.events)
        output_valid = [traffic and bool(q) for q in self.queues]
        transfer = [v and p['i_output_ready'][-o - 1] == '1' for o, v in enumerate(output_valid)]
        ready = []
        for i in range(c.NUM_INPUTS):
            ready.append(bool(traffic and self.destinations(i) and all(
                not q or q[0].source != i or transfer[o] for o, q in enumerate(self.queues))))
        accept = [r and p['i_input_valid'][-i - 1] == '1' for i, r in enumerate(ready)]
        quiescent = allowed and idle and not any(accept) and not any(transfer)
        config = quiescent and p['i_config_valid'] == '1'
        cfg_error = self.config_error(p) if config else 0
        detected = state_error or (4 if unknown else cfg_error)
        complete = [traffic and bool(self.pending(i)) and all(
            not q or q[0].source != i or transfer[o] for o, q in enumerate(self.queues))
            for i in range(c.NUM_INPUTS)]
        out.update(o_quiescent=bits(int(quiescent), 1), o_config_ready=bits(int(quiescent), 1),
                   o_input_ready=''.join(str(int(r)) for r in reversed(ready)),
                   o_output_valid=''.join(str(int(v)) for v in reversed(output_valid)),
                   o_output_data=''.join(q[0].data if v else '0' * c.DATA_WIDTH
                       for q, v in reversed(list(zip(self.queues, output_valid, strict=True)))),
                   o_output_metadata=''.join(q[0].metadata if v else '0' * c.METADATA_WIDTH
                       for q, v in reversed(list(zip(self.queues, output_valid, strict=True)))))
        return out, dict(run=run, flush=flush, traffic=traffic, idle=idle, accept=accept,
            transfer=transfer, complete=complete, config=config, config_error=cfg_error,
            detected=detected, quiescent=quiescent, state_error=state_error,
            delivery_tokens={o: q[0] for o, q in enumerate(self.queues) if q})

    def step(self, p, edge):
        out, plan = self.evaluate(p)
        if not edge:
            return {}, plan
        self.edge += 1
        if p['i_rstb'] == '0':
            self.reset()
            return {'reset': 1}, plan
        if not plan['run']:
            return {}, plan
        c = self.c
        events = dict.fromkeys(EVENTS, 0)
        events.update(o_config_accepted=int(plan['config'] and not plan['config_error']),
                      o_config_rejected=int(plan['config'] and bool(plan['config_error'])),
                      o_flushed=int(plan['flush'] and not plan['idle']))
        for i in range(c.NUM_INPUTS):
            events['o_event_input_accept'] |= int(plan['accept'][i]) << i
            events['o_event_item_complete'] |= int(plan['complete'][i]) << i
            events['o_event_multicast_accept'] |= int(plan['accept'][i] and
                self.destinations(i).bit_count() > 1) << i
            events['o_event_input_stall'] |= int(plan['traffic'] and p['i_input_valid'][-i - 1] == '1'
                and out['o_input_ready'][-i - 1] == '0') << i
        for o in range(c.NUM_OUTPUTS):
            events['o_event_output_transfer'] |= int(plan['transfer'][o]) << o
            events['o_event_output_stall'] |= int(out['o_output_valid'][-o - 1] == '1' and
                p['i_output_ready'][-o - 1] == '0') << o
        if not self.error and plan['detected']:
            self.error = plan['detected']
        elif plan['quiescent'] and not plan['config'] and p['i_error_clear'] == '1' and not plan['detected']:
            self.error = 0
        if plan['flush']:
            self.discard()
        else:
            for o, pop in enumerate(plan['transfer']):
                if pop:
                    token = self.queues[o].popleft()
                    assert token.accepted_edge < self.edge, 'Combinational payload bypass'
                    self.copy_delivered[o] += 1
            for i, complete in enumerate(plan['complete']):
                self.completed[i] += int(complete)
            for i, push in enumerate(plan['accept']):
                if push:
                    self.serial += 1
                    token = Copy(i, self.serial, self.destinations(i),
                        lane(p['i_input_data'], i, c.DATA_WIDTH),
                        lane(p['i_input_metadata'], i, c.METADATA_WIDTH), self.edge)
                    self.accepted[i] += 1
                    for o in range(c.NUM_OUTPUTS):
                        if token.destinations >> o & 1:
                            assert not self.queues[o], 'Copy overwritten before retirement'
                            self.queues[o].append(token)
                            self.copy_accepted[o] += 1
            if events['o_config_accepted']:
                assert not any(self.queues), 'Context updated while copies owned'
                self.enabled = int(p['i_config_output_enable'], 2)
                self.select = [int(lane(p['i_config_output_select'], o,
                    c.aliases['INPUT_SELECT_WIDTH']), 2) for o in range(c.NUM_OUTPUTS)]
                self.context = int(p['i_config_context_id'], 2)
        self.events = {n: bits(v, c.widths[n]) for n, v in events.items()}
        self.conservation()
        return events, plan

    def conservation(self):
        for i in range(self.c.NUM_INPUTS):
            assert self.accepted[i] == self.completed[i] + self.discarded[i] + bool(self.pending(i))
        for o, q in enumerate(self.queues):
            assert len(q) <= 1
            assert self.copy_accepted[o] == self.copy_delivered[o] + self.copy_discarded[o] + len(q)

    def accounting(self):
        return dict(items=[dict(accepted=self.accepted[i], completed=self.completed[i],
            discarded=self.discarded[i], pending=int(bool(self.pending(i)))) for i in range(self.c.NUM_INPUTS)],
            copies=[dict(accepted=self.copy_accepted[o], delivered=self.copy_delivered[o],
            discarded=self.copy_discarded[o], pending=len(q)) for o, q in enumerate(self.queues)])
