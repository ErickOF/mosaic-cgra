"""Interface stimulus and immutable real-port/waveform observations."""

from dataclasses import dataclass
from pyuvm import uvm_sequence_item

INPUTS = ('i_rstb', 'i_flush', 'i_valid', 'i_data', 'i_keep', 'i_last', 'i_user', 'i_ready')
OUTPUTS = ('o_ready', 'o_valid', 'o_data', 'o_keep', 'o_last', 'o_user', 'o_busy')
PAYLOAD = ('i_data', 'i_keep', 'i_last', 'i_user')
CONTROLS = ('i_rstb', 'i_flush', 'i_valid', 'i_ready')
STORAGE = ('buffered_data', 'buffered_keep', 'buffered_last', 'buffered_user')


class WidthConverterItem(uvm_sequence_item):
    def __init__(self, label, ports, *, edge=True, random=False, pulse=''):
        super().__init__(label)
        self.ports = dict(ports)
        self.edge, self.random, self.pulse = edge, random, pulse
        self.pre = self.observation = None


@dataclass(frozen=True)
class Observation:
    ports: dict[str, str]
    internals: dict[str, str]
    item: WidthConverterItem
    stage: str


@dataclass(frozen=True)
class Activity:
    name: str
    previous: str
    current: str
    forbidden_bits: tuple[int, ...]
