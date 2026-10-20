"""Independent initialized-word model; no DUT contents predict legal read data."""

from collections import Counter
from register_file.transaction import fields, known, pack


def legal_writes(config, ports):
    addresses = fields(ports['i_write_address'], config.address_width)
    data = fields(ports['i_write_data'], config.width)
    return tuple((w, int(address, 2), data[w]) for w, address in enumerate(addresses)
        if ports['i_write_enable'][-w-1] == '1' and known(address) and int(address, 2) < config.depth)


def read_violation(config, ports):
    if not known(ports['i_read_enable']):
        return 'read_enable'
    for r, address in enumerate(fields(ports['i_read_address'], config.address_width)):
        if ports['i_read_enable'][-r-1] == '1' and (not known(address) or int(address, 2) >= config.depth):
            return f'read_address:{r}'
    return None


def write_violation(config, ports, four_state_data):
    if not known(ports['i_write_enable']):
        return 'write_enable'
    data = fields(ports['i_write_data'], config.width)
    for w, address in enumerate(fields(ports['i_write_address'], config.address_width)):
        if ports['i_write_enable'][-w-1] == '1':
            if not known(address) or int(address, 2) >= config.depth:
                return f'write_address:{w}'
            if not four_state_data and not known(data[w]):
                return f'write_data:{w}'
    writes = legal_writes(config, ports)
    if len({address for _, address, _ in writes}) != len(writes):
        return 'write_conflict'
    return None


class RegisterFileModel:
    def __init__(self, config):
        self.config = config
        # None means unspecified power-up content, not an expected zero or X.
        self.words = [None] * config.depth
        self.raw = None
        self.write_counts = [0] * config.depth

    def step(self, ports):
        writes = legal_writes(self.config, ports)
        counts = Counter(address for _, address, _ in writes)
        for _, address, data in writes:
            # Collision results are unspecified. The live interface assertion
            # rejects them after checking that unrelated entries held state.
            self.words[address] = data if counts[address] == 1 else None
            if self.raw is not None:
                self.raw[address] = data if counts[address] == 1 else None
            self.write_counts[address] += 1
        return writes

    def reads(self, ports):
        config = self.config
        expected = []
        for r, address in enumerate(fields(ports['i_read_address'], config.address_width)):
            enable = ports['i_read_enable'][-r-1]
            if enable == '0':
                expected.append('0' * config.width)
            elif enable != '1' or not known(address):
                expected.append('x' * config.width)
            elif int(address, 2) >= config.depth:
                expected.append('0' * config.width)
            else:
                expected.append(self.words[int(address, 2)])
        return expected
