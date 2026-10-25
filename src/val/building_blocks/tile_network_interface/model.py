"""Independent packet expansion, endpoint completion ledgers, and VC parsers.

Completed receives are ordered by endpoint deques, independently from the RTL's
predecessor masks. All queue state is derived from public accepted transactions.
"""

from collections import deque
from copy import deepcopy
from mosaic_uvm.logic import bits
from tile_network_interface.transaction import FLIT_FIELDS, RX_FIELDS, TX_FIELDS


def num(value):
    if isinstance(value, int):
        return value
    return int(value, 2) if isinstance(value, str) and set(value) <= {'0', '1'} else None


def lane(value, index, width, *, data=False):
    value = (
        bits(
            value,
            max(width * (index + 1), len(value) if isinstance(value, str) else value.bit_length()),
        )
        if isinstance(value, int)
        else value
    )
    end = len(value) - index * width
    part = value[end - width : end]
    return part if data else num(part)


def pack(values, width):
    return ''.join(bits(value, width) for value in reversed(values))


def flit(c, ports, prefix):
    return {n: (ports[prefix + n] if n == 'data' else num(ports[prefix + n])) for n in FLIT_FIELDS}


def tile(c, ports, prefix, channel, names):
    count = c.NUM_TX_CHANNELS if 'tx' in prefix else c.NUM_RX_CHANNELS
    return {
        n: lane(ports[prefix + n], channel, c.widths[prefix + n] // count, data=n == 'data')
        for n in names
    }


def normalize(data, keep, byte_count):
    text = bits(data, byte_count * 8)
    return ''.join(
        text[n : n + 8] if keep >> (byte_count - n // 8 - 1) & 1 else '00000000'
        for n in range(0, len(text), 8)
    )


def parity(c, record):
    ones = 0
    for name, expression in FLIT_FIELDS.items():
        if name == 'parity':
            continue
        width = expression if isinstance(expression, int) else c.aliases[expression]
        value = record[name]
        if value is None:
            return 'x'
        word = bits(value, width)
        if num(word) is None:
            return 'x'
        ones += word.count('1')
    return ones % 2


def expand(c, beat, source, epoch):
    data = normalize(beat['data'], beat['keep'], c.aliases['TB'])
    meta = {
        k: beat[k]
        for k in (
            'destination_node',
            'destination_endpoint',
            'context_id',
            'message_type',
            'traffic_class',
            'packet_id',
            'user_metadata',
            'error',
        )
    }
    meta |= dict(
        vc=c.vc(beat['traffic_class']),
        source_node=c.LOCAL_NODE_ID,
        source_endpoint=source,
        stream_last=beat['last'],
        epoch=epoch,
    )
    result = []
    for fragment in range(c.fragments):
        lower = fragment * c.NOC_FLIT_DATA_WIDTH
        end = len(data) - lower
        selected = data[max(0, end - c.NOC_FLIT_DATA_WIDTH) : max(0, end)]
        record = meta | dict(
            data=selected.rjust(c.NOC_FLIT_DATA_WIDTH, '0'),
            keep=beat['keep'] >> (fragment * c.aliases['FB']) & ((1 << c.aliases['FB']) - 1),
            head=int(fragment == 0),
            tail=int(fragment == c.fragments - 1),
            fragment_index=fragment,
        )
        record['parity'] = parity(c, record) if c.ENABLE_LINK_PARITY else 0
        result.append(record)
    return result


def winner(candidates, start, count):
    return next((n for n in [(start + k) % count for k in range(count)] if n in candidates), None)


class InterfaceModel:
    def __init__(self, c):
        self.c = c
        self.accepted_tx = self.sent_tx = self.discarded_tx = 0
        self.accepted_rx = self.delivered_rx = self.discarded_rx = 0
        self.packet_drops = self.serial = 0
        self.tx_flits = self.canceled_tx_flits = 0
        self.rx_flits = self.popped_rx_flits = self.canceled_rx_flits = 0
        self.reset()

    def reset(self, *, flush=False):
        c = self.c
        if hasattr(self, 'tx'):
            self.canceled_tx_flits += sum(len(q) * c.fragments for q in self.tx) - self.fragment
            self.canceled_rx_flits += sum(map(len, self.vc_queues))
            self.discarded_tx += sum(map(len, self.tx))
            self.discarded_rx += sum(map(len, self.rx)) + sum(len(q) for q in self.completed)
        self.tx = [deque() for _ in range(c.NUM_TX_CHANNELS)]
        self.vc_queues = [deque() for _ in range(c.NUM_VCS)]
        self.rx = [deque() for _ in range(c.NUM_RX_CHANNELS)]
        self.partial = [None] * c.NUM_VCS
        self.completed = [deque() for _ in range(c.NUM_RX_CHANNELS)]
        self.tx_pointer = self.process_pointer = self.emit_pointer = 0
        self.tx_pending = None
        self.owner = None
        self.fragment = 0
        self.credits = [c.TX_INITIAL_CREDITS_PER_VC if c.NOC_FLOW_CONTROL else 0] * c.NUM_VCS
        self.fatal = False
        if not flush:
            self.configured = self.context_check = False
            self.tx_enable = self.rx_enable = self.context = self.epoch = self.error = 0
        self.events = dict(
            o_config_accepted=0,
            o_config_rejected=0,
            o_flushed=0,
            o_event_tile_tx_accept=0,
            o_event_tile_rx_transfer=0,
            o_event_noc_tx_transfer=0,
            o_event_noc_rx_accept=0,
            o_event_tx_stall=0,
            o_event_rx_stall=0,
            o_event_tx_drop=0,
            o_event_rx_drop=0,
            o_event_parity_error=0,
            o_noc_rx_credit_valid=0,
            o_noc_rx_credit_vc=0,
            o_noc_rx_credit_epoch=0,
        )

    def tx_error(self, beat, channel):
        if any(beat[n] is None for n in TX_FIELDS if n != 'data'):
            return 14
        if not self.tx_enable >> channel & 1:
            return 16
        if not beat['keep']:
            return 1
        if beat['traffic_class'] >= self.c.NUM_TRAFFIC_CLASSES:
            return 2
        if self.context_check and beat['context_id'] != self.context:
            return 6
        return 0

    def parse(self, v, f):
        """Return next packet state, completed beat, error and drop/parity events."""
        c = self.c
        old = self.partial[v]
        current = deepcopy(old)
        start = bool(f['head'])
        abandoned = bool(start and old)
        invariant = {
            n: f[n]
            for n in FLIT_FIELDS
            if n not in ('data', 'keep', 'head', 'tail', 'fragment_index', 'parity')
        }
        if start:
            current = dict(
                next=0, bad=False, fields=invariant, bytes=['00000000'] * c.aliases['TB'], keep=0
            )
        parity_bad = bool(c.ENABLE_LINK_PARITY and f['parity'] != parity(c, f))
        error = 13 if parity_bad else 0
        if not error and current is None:
            error = 10
        if not error and (
            f['fragment_index'] != (0 if start else old['next'])
            or f['tail'] != int(f['fragment_index'] == c.fragments - 1)
        ):
            error = 10
        if not error:
            if f['epoch'] != self.epoch:
                error = 7
            elif f['traffic_class'] >= c.NUM_TRAFFIC_CLASSES:
                error = 2
            elif f['vc'] != c.vc(f['traffic_class']):
                error = 4
            elif (
                f['destination_node'] != c.LOCAL_NODE_ID
                or f['destination_endpoint'] >= c.NUM_RX_CHANNELS
            ):
                error = 5
            elif not self.rx_enable >> f['destination_endpoint'] & 1:
                error = 16
            elif self.context_check and f['context_id'] != self.context:
                error = 6
            elif not start and invariant != current['fields']:
                error = 11
        for b in range(c.aliases['FB']):
            position = f['fragment_index'] * c.aliases['FB'] + b
            value = lane(f['data'], b, 8, data=True)
            if position >= c.aliases['TB']:
                if (f['keep'] >> b & 1 or value != '00000000') and not error:
                    error = 12
            elif current is not None and not current['bad']:
                current['bytes'][position] = value if f['keep'] >> b & 1 else '00000000'
                if f['keep'] >> b & 1:
                    current['keep'] |= 1 << position
                else:
                    current['keep'] &= ~(1 << position)
        finish = (
            f['tail']
            or f['fragment_index'] >= c.fragments - 1
            or (not start and old and old['next'] >= c.fragments - 1)
        )
        if finish and (current is None or not current['keep']) and not error:
            error = 1
        if current is None:
            return None, None, 10 if abandoned else error, True, parity_bad
        current['bad'] |= bool(error)
        current['next'] = 1 if start else old['next'] + 1
        result = None
        drop = abandoned
        if finish:
            if current['bad']:
                drop = True
            else:
                meta = current['fields']
                result = dict(
                    data=''.join(reversed(current['bytes'])),
                    keep=current['keep'],
                    last=meta['stream_last'],
                    **{n: meta[n] for n in RX_FIELDS if n not in ('data', 'keep', 'last')},
                )
            current = None
        return current, result, 10 if abandoned else error, drop, parity_bad

    def evaluate(self, ports):
        c = self.c
        p = {n: num(value) for n, value in ports.items()}
        run = p['i_rstb'] == 1
        flushing = run and p['i_flush'] == 1
        known_global = all(
            p[n] is not None for n in ('i_drain', 'i_flush', 'i_config_valid', 'i_error_clear')
        )
        active = run and p['i_flush'] == 0 and known_global
        empty = (
            not any(self.tx)
            and not any(self.rx)
            and not any(self.vc_queues)
            and not any(self.partial)
            and not any(self.completed)
            and self.owner is None
        )
        tx_beats = [tile(c, ports, 'i_tile_tx_', n, TX_FIELDS) for n in range(c.NUM_TX_CHANNELS)]
        config_ready = (
            active
            and p['i_drain'] == 0
            and empty
            and (p['i_config_valid'] == 1 or p['i_tile_tx_valid'] == 0 and p['i_noc_rx_valid'] == 0)
        )
        config_accept = config_ready and p['i_config_valid'] == 1
        config_good = config_accept and all(
            p[n] is not None
            for n in (
                'i_config_tx_enable',
                'i_config_rx_enable',
                'i_config_context_check',
                'i_config_context_id',
            )
        )
        operate = active and self.configured and not config_accept
        rx_outputs = [q[0] if operate and q else None for q in self.rx]
        rx_consume = [
            n
            for n, beat in enumerate(rx_outputs)
            if beat and lane(ports['i_tile_rx_ready'], n, 1) == 1
        ]
        completion_owner = {q[0]['vc'] for q in self.completed if q}
        emit_candidates = {
            v
            for v in completion_owner
            if any(
                q and q[0]['vc'] == v and len(self.rx[n]) < c.RX_QUEUE_DEPTH + int(n in rx_consume)
                for n, q in enumerate(self.completed)
            )
        }
        emit_vc = winner(emit_candidates, self.emit_pointer, c.NUM_VCS) if operate else None
        completed_vcs = {entry['vc'] for q in self.completed for entry in q}
        process_vc = (
            winner(
                {v for v in range(c.NUM_VCS) if self.vc_queues[v] and v not in completed_vcs},
                self.process_pointer,
                c.NUM_VCS,
            )
            if operate
            else None
        )
        process = (
            self.parse(process_vc, self.vc_queues[process_vc][0])
            if process_vc is not None
            else None
        )
        requests = {
            n
            for n, q in enumerate(self.tx)
            if q
            and self.tx_enable >> n & 1
            and (
                self.owner == n
                if self.owner is not None
                else not c.NOC_FLOW_CONTROL or self.credits[q[0]['flits'][0]['vc']] > 0
            )
        }
        selected = (
            self.tx_pending
            if self.tx_pending is not None
            else winner(requests, self.tx_pointer, c.NUM_TX_CHANNELS)
        )
        tx_output = None
        if operate and selected is not None and selected in requests:
            candidate = self.tx[selected][0]['flits'][self.fragment]
            if not c.NOC_FLOW_CONTROL or self.credits[candidate['vc']] > 0:
                tx_output = candidate
        tx_transfer = tx_output is not None and (c.NOC_FLOW_CONTROL or p['i_noc_tx_ready'] == 1)
        tail = tx_transfer and tx_output['tail']
        tx_ready = [0] * c.NUM_TX_CHANNELS
        tx_accept, tx_drop = [], []
        errors = [self.tx_error(beat, n) for n, beat in enumerate(tx_beats)]
        if operate and not self.fatal and p['i_drain'] == 0:
            for n, q in enumerate(self.tx):
                tx_ready[n] = int(
                    errors[n] != 0 or len(q) < c.TX_QUEUE_DEPTH + int(tail and selected == n)
                )
                if lane(ports['i_tile_tx_valid'], n, 1) == 1 and tx_ready[n]:
                    tx_accept.append(n)
                    if errors[n]:
                        tx_drop.append(n)
        incoming = flit(c, ports, 'i_noc_rx_')
        known = all(incoming[n] is not None for n in FLIT_FIELDS if n not in ('data', 'parity'))
        valid_vc = incoming['vc'] is not None and incoming['vc'] < c.NUM_VCS
        stale = known and incoming['epoch'] != self.epoch
        capacity = valid_vc and len(self.vc_queues[incoming['vc']]) < c.RX_VC_DEPTH + int(
            process_vc == incoming['vc']
        )
        receive_ready = bool(
            operate
            and not self.fatal
            and not c.NOC_FLOW_CONTROL
            and known
            and valid_vc
            and (stale or capacity)
        )
        rx_accept = rx_direct_drop = overflow = False
        rx_push = None
        admission_error = 0
        if operate and not self.fatal:
            if p['i_noc_rx_valid'] == 1:
                if not known:
                    admission_error = 14
                elif not valid_vc:
                    admission_error = 3
                elif stale:
                    rx_accept = rx_direct_drop = True
                    admission_error = 7
                elif c.NOC_FLOW_CONTROL or receive_ready:
                    if capacity:
                        rx_accept = True
                        rx_push = incoming['vc']
                    else:
                        overflow = rx_direct_drop = True
                        admission_error = 9
                if c.NOC_FLOW_CONTROL and (not known or not valid_vc):
                    rx_direct_drop = True
            elif p['i_noc_rx_valid'] is None:
                admission_error = 14
        credit_error = 0
        returned_credit = None
        if active and self.configured and c.NOC_FLOW_CONTROL:
            if p['i_noc_tx_credit_valid'] == 1:
                cv, ce = p['i_noc_tx_credit_vc'], p['i_noc_tx_credit_epoch']
                if cv is None or ce is None:
                    credit_error = 14
                elif cv >= c.NUM_VCS:
                    credit_error = 3
                elif ce != self.epoch:
                    credit_error = 7
                elif self.credits[cv] == c.TX_INITIAL_CREDITS_PER_VC and not (
                    tx_transfer and tx_output['vc'] == cv
                ):
                    credit_error = 8
                else:
                    returned_credit = cv
            elif p['i_noc_tx_credit_valid'] is None:
                credit_error = 14
        error = 0
        if run:
            error = (
                14
                if not known_global
                else 15
                if config_accept and not config_good
                else credit_error or admission_error or (process[2] if process else 0)
            )
            if not error:
                error = next((errors[n] for n in tx_drop), 0)
            if (
                not error
                and operate
                and any(
                    lane(ports['i_tile_tx_valid'], n, 1) is None for n in range(c.NUM_TX_CHANNELS)
                )
            ):
                error = 14
            if (
                not error
                and operate
                and (
                    (
                        not c.NOC_FLOW_CONTROL
                        and tx_output is not None
                        and p['i_noc_tx_ready'] is None
                    )
                    or num(ports['i_tile_rx_ready']) is None
                    and any(rx_outputs)
                )
            ):
                error = 14
        output = dict(
            o_config_ready=int(config_ready),
            o_active_tx_enable=self.tx_enable,
            o_active_rx_enable=self.rx_enable,
            o_active_context_id=self.context,
            o_link_epoch=self.epoch,
            o_tx_queue_occupancy=pack(list(map(len, self.tx)), c.aliases['TO']),
            o_rx_vc_occupancy=pack(list(map(len, self.vc_queues)), c.aliases['VO']),
            o_rx_queue_occupancy=pack(list(map(len, self.rx)), c.aliases['RO']),
            o_tx_credit_count=pack(self.credits, c.aliases['CW']),
            o_idle=int(empty),
            o_quiescent=int(
                active
                and p['i_drain'] == 0
                and empty
                and not (tx_accept or rx_accept or tx_transfer)
            ),
            o_drain_done=int(run and p['i_drain'] == 1 and empty),
            o_error=int(self.error != 0),
            o_error_code=self.error,
            o_tile_tx_ready=pack(tx_ready, 1),
            o_noc_rx_ready=int(receive_ready),
            o_noc_tx_valid=int(tx_output is not None),
            o_tile_rx_valid=pack([int(e is not None) for e in rx_outputs], 1),
        )
        for n in FLIT_FIELDS:
            output['o_noc_tx_' + n] = tx_output[n] if tx_output else 0
        for n in RX_FIELDS:
            key = 'o_tile_rx_' + n
            output[key] = pack(
                [e[n] if e else 0 for e in rx_outputs], c.widths[key] // c.NUM_RX_CHANNELS
            )
        output.update({k: v if run else 0 for k, v in self.events.items()})
        q = dict(
            p=p,
            run=run,
            flush=flushing,
            active=active,
            operate=operate,
            empty=empty,
            config_accept=config_accept,
            config_good=config_good,
            selected=selected,
            requests=requests,
            tx_output=tx_output,
            tx_transfer=tx_transfer,
            tail=tail,
            tx_beats=tx_beats,
            tx_accept=tx_accept,
            tx_drop=tx_drop,
            tx_errors=errors,
            rx_outputs=rx_outputs,
            rx_consume=rx_consume,
            emit_vc=emit_vc,
            process_vc=process_vc,
            process=process,
            processed_destination=(
                self.vc_queues[process_vc][0]['destination_endpoint']
                if process_vc is not None
                else None
            ),
            incoming=incoming,
            rx_accept=rx_accept,
            rx_push=rx_push,
            rx_direct_drop=rx_direct_drop,
            overflow=overflow,
            credit_return=returned_credit,
            error=error,
        )
        return {k: bits(v, c.widths[k]) for k, v in output.items()}, q

    def step(self, ports, edge):
        _, q = self.evaluate(ports)
        c, p = self.c, q['p']
        if p['i_rstb'] == 0 and (edge or c.ASYNC_RESET):
            self.reset()
            return q
        if not edge:
            return q
        if not q['run']:
            self.tx_pending = None
            self.tx_pointer = self.process_pointer = self.emit_pointer = 0
            return q
        if q['flush']:
            self.reset(flush=True)
            self.events['o_flushed'] = int(not q['empty'])
            self.epoch = (self.epoch + 1) % (1 << c.LINK_EPOCH_WIDTH)
            return q
        self.events = dict.fromkeys(self.events, 0)
        self.events.update(
            o_config_accepted=int(q['config_good']),
            o_config_rejected=int(q['config_accept'] and not q['config_good']),
            o_event_tile_tx_accept=sum(1 << n for n in q['tx_accept']),
            o_event_tile_rx_transfer=sum(1 << n for n in q['rx_consume']),
            o_event_noc_tx_transfer=int(q['tx_transfer']),
            o_event_noc_rx_accept=int(q['rx_accept']),
            o_event_tx_drop=sum(1 << n for n in q['tx_drop']),
            o_event_tx_stall=sum(
                1 << n
                for n in range(c.NUM_TX_CHANNELS)
                if q['operate']
                and not self.fatal
                and p['i_drain'] == 0
                and lane(ports['i_tile_tx_valid'], n, 1) == 1
                and n not in q['tx_accept']
            ),
            o_event_rx_stall=sum(
                1 << n
                for n, e in enumerate(q['rx_outputs'])
                if e and lane(ports['i_tile_rx_ready'], n, 1) == 0
            ),
            o_event_rx_drop=int(q['rx_direct_drop'] or bool(q['process'] and q['process'][3])),
            o_event_parity_error=int(
                bool(q['process'] and q['process'][4])
                or q['rx_direct_drop']
                and c.ENABLE_LINK_PARITY
                and q['incoming']['parity'] != parity(c, q['incoming'])
            ),
        )
        if q['process_vc'] is not None and c.NOC_FLOW_CONTROL:
            self.events.update(
                o_noc_rx_credit_valid=1,
                o_noc_rx_credit_vc=q['process_vc'],
                o_noc_rx_credit_epoch=self.vc_queues[q['process_vc']][0]['epoch'],
            )
        if not self.error:
            self.error = q['error']
        elif (
            q['active']
            and p['i_drain'] == 0
            and q['empty']
            and not q['config_accept']
            and p['i_error_clear'] == 1
            and not q['error']
        ):
            self.error = 0
        if q['overflow']:
            self.fatal = True
        if q['credit_return'] is not None:
            self.credits[q['credit_return']] += 1
        if q['tx_transfer']:
            self.tx_flits += 1
            n = q['selected']
            if c.NOC_FLOW_CONTROL:
                self.credits[q['tx_output']['vc']] -= 1
            if q['tail']:
                self.tx[n].popleft()
                self.sent_tx += 1
                self.fragment = 0
                self.owner = None
                self.tx_pointer = (n + 1) % c.NUM_TX_CHANNELS
                self.tx_pending = None
            else:
                self.fragment += 1
                self.owner = n
        if not q['tail'] and q['selected'] is not None:
            self.tx_pending = q['selected']
        for n in q['rx_consume']:
            self.rx[n].popleft()
            self.delivered_rx += 1
        if q['emit_vc'] is not None:
            for endpoint, queue in enumerate(self.completed):
                if queue and queue[0]['vc'] == q['emit_vc']:
                    self.rx[endpoint].append(queue.popleft()['beat'])
                    break
            self.emit_pointer = (q['emit_vc'] + 1) % c.NUM_VCS
        if q['process_vc'] is not None:
            v = q['process_vc']
            self.vc_queues[v].popleft()
            self.popped_rx_flits += 1
            partial, beat, error, drop, _ = q['process']
            self.partial[v] = partial
            self.packet_drops += int(drop)
            if beat is not None:
                self.completed[q['processed_destination']].append(dict(vc=v, beat=beat))
                self.accepted_rx += 1
            self.process_pointer = (v + 1) % c.NUM_VCS
        if q['rx_push'] is not None:
            self.vc_queues[q['rx_push']].append(q['incoming'])
            self.rx_flits += 1
        for n in q['tx_accept']:
            if n not in q['tx_drop']:
                self.tx[n].append(dict(flits=expand(c, q['tx_beats'][n], n, self.epoch)))
                self.accepted_tx += 1
        if q['config_good']:
            self.configured = True
            self.tx_enable = p['i_config_tx_enable']
            self.rx_enable = p['i_config_rx_enable']
            self.context_check = bool(p['i_config_context_check'])
            self.context = p['i_config_context_id']
        return q
