"""Mathematical integer conversion and a separate accepted-beat ledger."""

from collections import deque
from mosaic_uvm.logic import bits
from packer.transaction import FIELDS


def split_elements(word, width):
    return [word[len(word) - width * (lane + 1):len(word) - width * lane] for lane in range(len(word) // width)]


def known(word):
    return not set(word) & {'x', 'z'}


def protocol_violation(config, ports):
    for name in ('i_rstb', 'i_flush'):
        if not known(ports[name]):
            return name
    if ports['i_rstb'] == '0' or ports['i_flush'] == '1':
        return None
    for name in ('i_valid', 'i_ready'):
        if not known(ports[name]):
            return name
    if ports['i_valid'] == '1':
        for name in ('i_signed', 'i_saturate', 'i_reverse', 'i_lane_valid', 'i_last', 'i_user'):
            if not known(ports[name]):
                return name
        if any(valid == '1' and not known(word) for valid, word in
               zip(reversed(ports['i_lane_valid']), split_elements(ports['i_data'], config.source_width))):
            return 'i_data'
    return None


def isolated_input(config, ports):
    return ''.join(reversed([word if ports['i_valid'] == '1' and valid == '1' else
        '0' * config.source_width if ports['i_valid'] == '0' or valid == '0' else 'x' * config.source_width
        for word, valid in zip(split_elements(ports['i_data'], config.source_width), reversed(ports['i_lane_valid']))]))


def illegal_causes(config, mode):
    signed, saturate, reverse = mode
    return tuple(name for name, active in (
        ('signed', signed and not config.signed), ('saturation', saturate and not config.saturation),
        ('reverse', reverse and not config.reverse), ('not_narrowing', saturate and not config.narrowing)) if active)


def configuration_error(config, ports):
    if ports['i_rstb'] == '0' or ports['i_flush'] == '1' or ports['i_valid'] == '0':
        return False
    return bool(illegal_causes(config, tuple(int(ports[name]) for name in ('i_signed', 'i_saturate', 'i_reverse'))))


def limits(width, signed):
    return (-(1 << (width - 1)), (1 << (width - 1)) - 1) if signed else (0, (1 << width) - 1)


def boundary_values(config, signed):
    source_min, source_max = limits(config.source_width, signed)
    low, high = limits(config.destination_width, signed)
    candidates = {source_min, source_min + 1, source_max - 1, source_max, -1, 0, 1,
                  low - 1, low, low + 1, high - 1, high, high + 1}
    return tuple(sorted({value % (1 << config.source_width) for value in candidates if source_min <= value <= source_max}))


def convert(config, ports):
    """Interpret signed values arithmetically and clamp using unbounded integers."""
    signed, saturate, reverse = (int(ports[name]) for name in ('i_signed', 'i_saturate', 'i_reverse'))
    low, high = limits(config.destination_width, signed)
    data, valid, overflow, saturated, routes = [0] * config.elements, [0] * config.elements, [0] * config.elements, [0] * config.elements, []
    for lane, (word, mask) in enumerate(zip(split_elements(ports['i_data'], config.source_width), reversed(ports['i_lane_valid']))):
        if mask == '0':
            continue
        raw = int(word, 2)
        value = raw - (1 << config.source_width) if signed and raw >= 1 << (config.source_width - 1) else raw
        destination = config.elements - 1 - lane if reverse else lane
        exceeds = value < low or value > high
        adjusted = min(high, max(low, value)) if saturate else value
        data[destination] = adjusted % (1 << config.destination_width)
        valid[destination], overflow[destination], saturated[destination] = 1, int(exceeds), int(exceeds and saturate)
        routes.append(dict(source=lane, destination=destination, raw=raw, value=value,
                           value_class='below' if value < low else 'above' if value > high else 'in_range',
                           overflow=int(exceeds), saturated=int(exceeds and saturate)))
    result = dict(o_data=''.join(bits(value, config.destination_width) for value in reversed(data)),
                  o_lane_valid=''.join(map(str, reversed(valid))), o_overflow=''.join(map(str, reversed(overflow))),
                  o_saturated=''.join(map(str, reversed(saturated))), o_last=ports['i_last'], o_user=ports['i_user'])
    return result, routes


def pack_result(result):
    return ''.join(result[name] for name in FIELDS)


class PackerModel:
    def __init__(self, config):
        self.config = config
        self.queue = deque()
        self.storage = 'x' * config.result_width
        self.initialized = not config.registered
        self.accepted = self.consumed = self.cancelled = 0

    def cancel(self, *, reset=False):
        self.cancelled += len(self.queue)
        self.queue.clear()
        if reset:
            self.storage = '0' * self.config.result_width
            self.initialized = True

    def outputs(self, ports):
        config = self.config
        running = ports['i_rstb'] == '1' and ports['i_flush'] == '0'
        error = configuration_error(config, ports)
        valid = bool(self.queue) if config.registered else ports['i_valid'] == '1' and not error
        room = (not self.queue or ports['i_ready'] == '1') if config.registered else ports['i_ready'] == '1'
        result = {name: '0' * config.widths[name] for name in FIELDS}
        if running and valid:
            result = dict(self.queue[0]) if config.registered else convert(config, ports)[0]
        result.update(o_ready=str(int(running and not error and room)), o_valid=str(int(running and valid)),
                      o_busy=str(int(bool(self.queue))) if self.initialized else 'x', o_config_error=str(int(error)),
                      o_any_overflow=str(int('1' in result['o_overflow'])), o_any_saturated=str(int('1' in result['o_saturated'])))
        return result

    def step(self, ports):
        before, occupancy = self.outputs(ports), bool(self.queue)
        event = dict(occupancy=int(occupancy), accepted=False, consumed=False, frame=None,
                     reset=ports['i_rstb'] == '0', flush=ports['i_flush'] == '1')
        if event['reset'] or event['flush']:
            self.cancel(reset=event['reset'])
        else:
            event['consumed'] = before['o_valid'] == '1' and ports['i_ready'] == '1'
            event['accepted'] = before['o_ready'] == '1' and ports['i_valid'] == '1'
            if event['consumed']:
                self.consumed += 1
                if self.config.registered:
                    self.queue.popleft()
            if event['accepted']:
                self.accepted += 1
                event['frame'] = convert(self.config, ports)
                if self.config.registered:
                    self.queue.append(event['frame'][0])
                    self.storage = pack_result(event['frame'][0])
        assert len(self.queue) <= int(self.config.registered), 'Registered occupancy assertion failed'
        assert self.accepted == self.consumed + self.cancelled + len(self.queue), 'Beat conservation assertion failed'
        return event
