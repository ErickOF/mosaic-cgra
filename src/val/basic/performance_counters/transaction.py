"""A clock opportunity, port observation, or continuous waveform transition."""

from dataclasses import dataclass
from pyuvm import uvm_sequence_item

INPUTS = ('i_rstb', 'i_global_enable', 'i_freeze', 'i_counter_enable', 'i_clear',
    'i_event_select', 'i_event_valid', 'i_event_increment', 'i_threshold_enable',
    'i_threshold_value', 'i_snapshot', 'i_read_enable', 'i_read_snapshot', 'i_read_index')
OUTPUTS = ('o_read_data', 'o_read_overflow', 'o_read_valid', 'o_counter_overflow',
    'o_threshold_event', 'o_config_error', 'o_snapshot_valid')


class PerformanceCountersItem(uvm_sequence_item):
    def __init__(self, label, ports, *, edge=True, random=False):
        super().__init__(label)
        self.ports = dict(ports)
        self.edge = edge
        self.random = random
        self.observation = None


@dataclass(frozen=True)
class Observation:
    ports: dict[str, str]
    internals: dict[str, str]
    item: PerformanceCountersItem
    stage: str


@dataclass(frozen=True)
class Activity:
    name: str
    quiet: bool
