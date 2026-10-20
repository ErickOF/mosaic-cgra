"""Byte-array oracle and a transaction ledger independent of the RTL shifters."""

from collections import deque
from mosaic_uvm.logic import bits
from data_aligner.transaction import FIELDS


def known(word):
    return not set(word) & {'x', 'z'}


def lanes(word):
    return [word[len(word) - 8 * (lane + 1):len(word) - 8 * lane] for lane in range(len(word) // 8)]


def isolated_window(config, ports):
    data = lanes(ports['i_data_lo']) + lanes(ports['i_data_hi'])
    strobe = ports['i_strb_lo'][::-1] + ports['i_strb_hi'][::-1]
    result = [byte if ports['i_valid'] == '1' and mask == '1' else
              '0' * 8 if ports['i_valid'] == '0' or mask == '0' else 'x' * 8
              for byte, mask in zip(data, strobe)]
    return ''.join(reversed(result))


def configuration_error(config, ports):
    if ports['i_rstb'] == '0' or ports['i_flush'] == '1' or ports['i_valid'] == '0':
        return False
    return int(ports['i_offset'], 2) >= config.word_bytes or int(ports['i_shift_high']) not in config.directions


def protocol_violation(ports):
    for name in ('i_rstb', 'i_flush'):
        if not known(ports[name]):
            return name
    if ports['i_rstb'] == '0' or ports['i_flush'] == '1':
        return None
    for name in ('i_valid', 'i_ready'):
        if not known(ports[name]):
            return name
    if ports['i_valid'] == '1':
        for name in ('i_strb_lo', 'i_strb_hi', 'i_offset', 'i_shift_high', 'i_last', 'i_user'):
            if not known(ports[name]):
                return name
        for side in ('lo', 'hi'):
            if any(mask == '1' and not known(byte) for mask, byte in zip(ports['i_strb_' + side][::-1], lanes(ports['i_data_' + side]))):
                return 'i_data_' + side
    return None


def align(config, ports):
    """Place each qualified byte once using signed integer destination indices."""
    size = config.word_bytes
    words = [["0" * 8 for _ in range(size)] for _ in range(3)]
    masks = [[0 for _ in range(size)] for _ in range(3)]
    data = lanes(ports['i_data_lo']) + lanes(ports['i_data_hi'])
    strobe = ports['i_strb_lo'][::-1] + ports['i_strb_hi'][::-1]
    offset, high = int(ports['i_offset'], 2), int(ports['i_shift_high'])
    routes = []
    for source, (byte, valid) in enumerate(zip(data, strobe)):
        if valid != '1':
            continue
        position = source + (offset if high else -offset)
        if position < 0:
            word, lane = 2, size + position
        elif position >= 2 * size:
            word, lane = 2, position - 2 * size
        else:
            word, lane = divmod(position, size)
        assert not masks[word][lane], 'Reference collision: more than one byte maps to a destination'
        words[word][lane], masks[word][lane] = byte, 1
        routes.append((source, word, lane))
    result = {}
    for index, side in enumerate(('lo', 'hi', 'spill')):
        data_name = 'o_spill_data' if side == 'spill' else 'o_data_' + side
        mask_name = 'o_spill_strb' if side == 'spill' else 'o_strb_' + side
        result[data_name] = ''.join(reversed(words[index]))
        result[mask_name] = ''.join(map(str, reversed(masks[index])))
    result.update(o_spill_high=str(high), o_unaligned=str(int('1' in strobe and offset != 0)),
                  o_split=str(int(any(masks[0]) and any(masks[1]))), o_last=ports['i_last'], o_user=ports['i_user'])
    assert len(routes) == strobe.count('1') == sum(sum(mask) for mask in masks)
    return result, routes


def pack_result(result):
    return ''.join(result[name] for name in FIELDS)


class AlignerModel:
    def __init__(self, config):
        self.config = config
        self.queue = deque()
        self.clock = '0'
        self.initialized = not config.registered
        self.storage = 'x' * config.result_width
        self.accepted = self.consumed = self.cancelled = 0

    def outputs(self, ports):
        config = self.config
        running = ports['i_rstb'] == '1' and ports['i_flush'] == '0'
        error = configuration_error(config, ports)
        valid = bool(self.queue) if config.registered else ports['i_valid'] == '1' and not error
        ready = (not self.queue or ports['i_ready'] == '1') if config.registered else ports['i_ready'] == '1'
        result = {name: '0' * config.widths[name] for name in FIELDS}
        if running and valid:
            result = dict(self.queue[0]) if config.registered else align(config, ports)[0]
        result.update(o_ready=str(int(running and not error and ready)), o_valid=str(int(running and valid)),
                      o_config_error=str(int(error)), o_busy=str(int(bool(self.queue))) if self.initialized else 'x')
        return result

    def step(self, ports):
        """Consume obligations before appending a replacement on the same edge."""
        rising = self.clock == '0' and ports['i_clk'] == '1'
        self.clock = ports['i_clk']
        before = self.outputs(ports)
        occupancy = bool(self.queue)
        reset = ports['i_rstb'] == '0' and (rising or self.config.asynchronous)
        flush = rising and ports['i_flush'] == '1'
        accepted = consumed = False
        frame = None
        if reset or flush:
            self.cancelled += len(self.queue)
            self.queue.clear()
            if reset:
                self.storage = '0' * self.config.result_width
                self.initialized = True
        elif rising:
            consumed = before['o_valid'] == '1' and ports['i_ready'] == '1'
            accepted = before['o_ready'] == '1' and ports['i_valid'] == '1'
            if consumed:
                self.consumed += 1
                if self.config.registered:
                    self.queue.popleft()
            if accepted:
                self.accepted += 1
                frame = align(self.config, ports)
                if self.config.registered:
                    self.queue.append(frame[0])
                    self.storage = pack_result(frame[0])
        assert len(self.queue) <= int(self.config.registered), 'Registered occupancy exceeded one'
        assert self.accepted == self.consumed + self.cancelled + len(self.queue), 'Transaction ledger lost or duplicated a window'
        return dict(rising=rising, reset=reset, flush=flush, occupancy=occupancy,
                    accepted=accepted, consumed=consumed, frame=frame)
