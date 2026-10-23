"""Checked geometry, packed-field widths and local class maps."""

from dataclasses import dataclass
import os
from pathlib import Path
from noc_router.transaction import FIELDS, INPUTS, OUTPUTS, SCALARS

DEFAULTS = dict(
    MESH_X=4,
    MESH_Y=4,
    ROUTER_X=0,
    ROUTER_Y=0,
    FLIT_DATA_WIDTH=32,
    NUM_VCS=2,
    INPUT_VC_DEPTH=2,
    FLOW_CONTROL=1,
    OUTPUT_INITIAL_CREDITS=2,
    ROUTING_ALGORITHM=0,
    NUM_TRAFFIC_CLASSES=8,
    ENABLE_QOS=1,
    HIGH_SERVICE_BURST_LIMIT=8,
    NODE_ID_WIDTH=8,
    ENDPOINT_ID_WIDTH=4,
    CONTEXT_ID_WIDTH=8,
    MESSAGE_TYPE_WIDTH=4,
    TRAFFIC_CLASS_WIDTH=3,
    PACKET_ID_WIDTH=8,
    FRAGMENT_INDEX_WIDTH=4,
    USER_METADATA_WIDTH=16,
    ERROR_WIDTH=4,
    LINK_EPOCH_WIDTH=2,
    ENABLE_LINK_PARITY=0,
    BUFFER_PROTECTION=0,
    OUTPUT_PIPELINE=1,
    ASYNC_RESET=0,
)


@dataclass(frozen=True)
class RouterConfig:
    parameters: dict[str, int]
    seed: int
    random_cycles: int
    coverage_file: Path

    @classmethod
    def from_environment(cls):
        def read(name, default):
            return int(os.getenv('NOC_ROUTER_' + name, str(default)), 0)

        p = {name: read(name, value) for name, value in DEFAULTS.items()}
        vw = max(1, (p['NUM_VCS'] - 1).bit_length())
        p['TRAFFIC_CLASS_TO_VC'] = read(
            'TRAFFIC_CLASS_TO_VC',
            sum((c % p['NUM_VCS']) << (c * vw) for c in range(p['NUM_TRAFFIC_CLASSES'])),
        )
        p['TRAFFIC_CLASS_TO_SERVICE'] = read(
            'TRAFFIC_CLASS_TO_SERVICE', sum((c % 2) << c for c in range(p['NUM_TRAFFIC_CLASSES']))
        )
        result = Path(os.getenv('COCOTB_RESULTS_FILE', 'build/noc_router/results.xml'))
        return cls(
            p,
            read('SEED', 20261022),
            read('RANDOM_CYCLES', 2000),
            Path(os.getenv('NOC_ROUTER_COVERAGE_FILE', str(result.with_name('coverage.json')))),
        )

    def __getattr__(self, name):
        return self.parameters[name]

    @property
    def aliases(self):
        p = self.parameters
        names = dict(
            D='FLIT_DATA_WIDTH',
            N='NODE_ID_WIDTH',
            EP='ENDPOINT_ID_WIDTH',
            CX='CONTEXT_ID_WIDTH',
            MT='MESSAGE_TYPE_WIDTH',
            TC='TRAFFIC_CLASS_WIDTH',
            PI='PACKET_ID_WIDTH',
            F='FRAGMENT_INDEX_WIDTH',
            U='USER_METADATA_WIDTH',
            ER='ERROR_WIDTH',
            E='LINK_EPOCH_WIDTH',
        )
        return {key: p[name] for key, name in names.items()} | dict(
            K=p['FLIT_DATA_WIDTH'] // 8, VW=max(1, (p['NUM_VCS'] - 1).bit_length())
        )

    @property
    def field_widths(self):
        return {
            name: self.aliases[value] if isinstance(value, str) else value
            for name, value in FIELDS.items()
        }

    @property
    def widths(self):
        result = dict.fromkeys((*INPUTS, *OUTPUTS), 5)
        result.update(
            dict.fromkeys(
                (
                    *SCALARS,
                    'o_config_ready',
                    'o_config_accepted',
                    'o_config_rejected',
                    'o_idle',
                    'o_quiescent',
                    'o_drain_done',
                    'o_flushed',
                    'o_error',
                    'o_fatal_error',
                ),
                1,
            )
        )
        result['o_error_code'] = 5
        for name, width in self.field_widths.items():
            result['i_in_' + name] = result['o_out_' + name] = 5 * width
        for direction in ('i_out', 'o_in'):
            result[direction + '_credit_vc'] = 5 * self.aliases['VW']
            result[direction + '_credit_epoch'] = 5 * self.LINK_EPOCH_WIDTH
        result['o_link_epoch'] = 5 * self.LINK_EPOCH_WIDTH
        result['o_input_vc_occupancy'] = 5 * self.NUM_VCS * self.INPUT_VC_DEPTH.bit_length()
        result['o_output_credit_count'] = (
            5 * self.NUM_VCS * self.OUTPUT_INITIAL_CREDITS.bit_length()
        )
        return result

    def usable_ports(self, x=None, y=None):
        x = self.ROUTER_X if x is None else x
        y = self.ROUTER_Y if y is None else y
        return [
            0,
            *([1] if y else []),
            *([2] if x + 1 < self.MESH_X else []),
            *([3] if y + 1 < self.MESH_Y else []),
            *([4] if x else []),
        ]
