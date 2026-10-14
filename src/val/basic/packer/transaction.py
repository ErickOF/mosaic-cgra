"""Complete input beats and driver-coordinated observations of real signals."""

from dataclasses import dataclass
from pyuvm import uvm_sequence_item

INPUTS = ('i_rstb', 'i_flush', 'i_valid', 'i_data', 'i_lane_valid', 'i_signed',
          'i_saturate', 'i_reverse', 'i_last', 'i_user', 'i_ready')
FRAME_INPUTS = tuple(name for name in INPUTS if name not in ('i_rstb', 'i_flush', 'i_ready'))
FIELDS = ('o_data', 'o_lane_valid', 'o_overflow', 'o_saturated', 'o_last', 'o_user')
OUTPUTS = ('o_ready', 'o_valid', *FIELDS, 'o_any_overflow', 'o_any_saturated', 'o_config_error', 'o_busy')


class PackerItem(uvm_sequence_item):
    def __init__(self, label, ports, *, edge=True, random=False):
        super().__init__(label)
        self.ports = dict(ports)
        self.edge = edge
        self.random = random
        self.pre = None
        self.observation = None


@dataclass(frozen=True)
class Observation:
    ports: dict[str, str]
    internals: dict[str, str]
    item: PackerItem
    stage: str


@dataclass(frozen=True)
class Activity:
    name: str
    quiet: bool
