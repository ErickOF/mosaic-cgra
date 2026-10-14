"""Whole-window transactions and driver-coordinated passive observations."""

from dataclasses import dataclass
from pyuvm import uvm_sequence_item


INPUTS = ('i_clk', 'i_rstb', 'i_flush', 'i_valid', 'i_data_lo', 'i_strb_lo', 'i_data_hi', 'i_strb_hi',
          'i_offset', 'i_shift_high', 'i_last', 'i_user', 'i_ready')
FIELDS = ('o_data_hi', 'o_data_lo', 'o_strb_hi', 'o_strb_lo', 'o_spill_data', 'o_spill_strb',
          'o_spill_high', 'o_unaligned', 'o_split', 'o_last', 'o_user')
OUTPUTS = ('o_ready', 'o_valid', *FIELDS, 'o_config_error', 'o_busy')
FRAME_INPUTS = tuple(name for name in INPUTS if name not in ('i_clk', 'i_rstb', 'i_flush', 'i_ready'))


class AlignerItem(uvm_sequence_item):
    def __init__(self, label, ports, *, random=False, hold_ps=10):
        super().__init__(label)
        self.ports = dict(ports)
        self.random = random
        self.hold_ps = hold_ps
        self.pre = None
        self.observation = None


@dataclass(frozen=True)
class Observation:
    ports: dict[str, str]
    internals: dict[str, str]
    item: AlignerItem
    stage: str


@dataclass(frozen=True)
class Activity:
    name: str
    quiet: bool
