"""Complete four-state interface transactions and passive observations."""
from dataclasses import dataclass
from pyuvm import uvm_sequence_item

PORTS = {
    'i_clk': ('input', 1), 'i_rstb': ('input', 1), 'i_flush': ('input', 1),
    'i_error_clear': ('input', 1), 'i_config_valid': ('input', 1),
    'o_config_ready': ('output', 1), 'i_mode': ('input', 1),
    'i_frame_beats': ('input', 'C'), 'i_row_beats': ('input', 'C'),
    'i_lane_enable': ('input', 'L'), 'i_datatype': ('input', 'F'),
    'i_channel_id': ('input', 'H'), 'i_context_id': ('input', 'T'),
    'i_emit_end_of_stream': ('input', 1), 'i_valid': ('input', 1),
    'o_ready': ('output', 1), 'i_data': ('input', 'D'), 'i_keep': ('input', 'B'),
    'i_lane_mask': ('input', 'L'), 'i_first': ('input', 1), 'i_last': ('input', 1),
    'i_row_first': ('input', 1), 'i_row_last': ('input', 1),
    'i_end_of_stream': ('input', 1), 'i_stream_datatype': ('input', 'F'),
    'i_stream_channel_id': ('input', 'H'), 'i_stream_context_id': ('input', 'T'),
    'i_error': ('input', 1), 'o_valid': ('output', 1), 'i_ready': ('input', 1),
    'o_data': ('output', 'D'), 'o_keep': ('output', 'B'), 'o_lane_mask': ('output', 'L'),
    'o_first': ('output', 1), 'o_last': ('output', 1), 'o_row_first': ('output', 1),
    'o_row_last': ('output', 1), 'o_end_of_stream': ('output', 1),
    'o_datatype': ('output', 'F'), 'o_channel_id': ('output', 'H'),
    'o_context_id': ('output', 'T'), 'o_stream_error': ('output', 1),
    'o_format_error_code': ('output', 4), 'o_idle': ('output', 1), 'o_busy': ('output', 1),
    'o_frame_started': ('output', 1), 'o_input_accepted': ('output', 1),
    'o_output_accepted': ('output', 1), 'o_frame_completed': ('output', 1),
    'o_completed_with_error': ('output', 1), 'o_frame_aborted': ('output', 1),
    'o_beats_accepted': ('output', 'C'), 'o_beats_emitted': ('output', 'C'),
    'o_format_error_seen': ('output', 1), 'o_input_error_seen': ('output', 1),
    'o_error': ('output', 1), 'o_config_error_code': ('output', 3),
}
INPUTS = tuple(n for n, (d, _) in PORTS.items() if d == 'input' and n != 'i_clk')
OUTPUTS = tuple(n for n, (d, _) in PORTS.items() if d == 'output')
CONFIG = ('i_mode', 'i_frame_beats', 'i_row_beats', 'i_lane_enable', 'i_datatype',
          'i_channel_id', 'i_context_id', 'i_emit_end_of_stream')
CLAIMS = ('first', 'last', 'row_first', 'row_last', 'end_of_stream',
          'stream_datatype', 'stream_channel_id', 'stream_context_id')
PAYLOAD = ('data', 'keep', 'lane_mask', *CLAIMS, 'error')
RESULT = ('o_data', 'o_keep', 'o_lane_mask', 'o_first', 'o_last', 'o_row_first', 'o_row_last',
          'o_end_of_stream', 'o_datatype', 'o_channel_id', 'o_context_id',
          'o_stream_error', 'o_format_error_code')
EVENTS = ('o_frame_started', 'o_input_accepted', 'o_output_accepted', 'o_frame_completed',
          'o_completed_with_error', 'o_frame_aborted')


class StreamFormatterItem(uvm_sequence_item):
    def __init__(self, label, ports, *, edge=True, random=False):
        super().__init__(label)
        self.ports = ports
        self.edge = edge
        self.random = random
        self.pre = None
        self.observation = None


@dataclass(frozen=True)
class Observation:
    ports: dict
    storage: dict
    item: StreamFormatterItem
    stage: str
