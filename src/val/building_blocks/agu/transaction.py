"""Descriptor clock opportunities and observations from the real DUT interface."""

from dataclasses import dataclass
from pyuvm import uvm_sequence_item

DESCRIPTOR = ('i_mode', 'i_base_address', 'i_inner_count', 'i_outer_count',
    'i_inner_stride', 'i_outer_stride', 'i_element_size_log2', 'i_is_write',
    'i_address_space', 'i_channel_id', 'i_context_id', 'i_emit_end_of_stream')
INPUTS = ('i_rstb', 'i_error_clear', 'i_config_valid', 'i_ready', *DESCRIPTOR)
ADDRESS = ('o_address', 'o_inner_index', 'o_outer_index', 'o_first', 'o_last',
    'o_row_first', 'o_row_last', 'o_end_of_stream', 'o_element_size_log2',
    'o_is_write', 'o_address_space', 'o_channel_id', 'o_context_id')
OUTPUTS = ('o_config_ready', 'o_valid', *ADDRESS, 'o_idle', 'o_active',
    'o_descriptor_started', 'o_address_accepted', 'o_completed',
    'o_addresses_accepted', 'o_error', 'o_error_code')
STORAGE = ('address', 'row_base', 'inner_index', 'outer_index', 'inner_delta',
    'outer_delta', 'inner_last', 'outer_last', 'mode', 'metadata')


class AguItem(uvm_sequence_item):
    def __init__(self, label, ports, *, edge=True, random=False):
        super().__init__(label)
        self.ports = ports
        self.edge, self.random = edge, random
        self.pre = self.observation = None


@dataclass(frozen=True)
class Observation:
    ports: dict[str, str]
    internals: dict[str, str]
    item: AguItem
    stage: str


@dataclass(frozen=True)
class Activity:
    name: str
    value: str
