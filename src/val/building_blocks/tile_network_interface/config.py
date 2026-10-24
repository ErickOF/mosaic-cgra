"""Specification-derived widths and Python-only test controls."""

from dataclasses import dataclass
from functools import cached_property
from math import prod
import os
from pathlib import Path
from tile_network_interface.transaction import PORTS

DEFAULTS = {
    'NUM_TX_CHANNELS': 4,
    'NUM_RX_CHANNELS': 4,
    'TILE_DATA_WIDTH': 128,
    'NOC_FLIT_DATA_WIDTH': 32,
    'TX_QUEUE_DEPTH': 2,
    'RX_VC_DEPTH': 2,
    'RX_QUEUE_DEPTH': 2,
    'NUM_VCS': 1,
    'NUM_TRAFFIC_CLASSES': 8,
    'NOC_FLOW_CONTROL': 0,
    'TX_INITIAL_CREDITS_PER_VC': 2,
    'NODE_ID_WIDTH': 8,
    'ENDPOINT_ID_WIDTH': 4,
    'CONTEXT_ID_WIDTH': 8,
    'MESSAGE_TYPE_WIDTH': 4,
    'PACKET_ID_WIDTH': 8,
    'USER_METADATA_WIDTH': 16,
    'ERROR_WIDTH': 4,
    'LINK_EPOCH_WIDTH': 2,
    'LOCAL_NODE_ID': 0,
    'ENABLE_LINK_PARITY': 0,
    'ASYNC_RESET': 0,
    'TRAFFIC_CLASS_TO_VC': 0,
}


@dataclass(frozen=True)
class InterfaceConfig:
    parameters: dict
    seed: int
    random_cycles: int
    coverage_file: Path

    def __getattr__(self, name):
        return self.parameters[name]

    @classmethod
    def from_environment(cls):
        def setting(n, d):
            return int(os.getenv('TILE_NETWORK_INTERFACE_' + n, str(d)), 0)

        results = Path(os.getenv('COCOTB_RESULTS_FILE', 'build/tile_network_interface/results.xml'))
        c = cls(
            {k: setting(k, v) for k, v in DEFAULTS.items()},
            setting('SEED', 20261023),
            setting('RANDOM_CYCLES', 2000),
            Path(
                os.getenv(
                    'TILE_NETWORK_INTERFACE_COVERAGE_FILE', str(results.with_name('coverage.json'))
                )
            ),
        )
        assert c.random_cycles >= 1000
        return c

    @cached_property
    def fragments(self):
        return (self.TILE_DATA_WIDTH + self.NOC_FLIT_DATA_WIDTH - 1) // self.NOC_FLIT_DATA_WIDTH

    @cached_property
    def aliases(self):
        p = self.parameters
        a = {
            k: p[v]
            for k, v in {
                'TX': 'NUM_TX_CHANNELS',
                'RX': 'NUM_RX_CHANNELS',
                'TD': 'TILE_DATA_WIDTH',
                'FD': 'NOC_FLIT_DATA_WIDTH',
                'V': 'NUM_VCS',
                'N': 'NODE_ID_WIDTH',
                'EP': 'ENDPOINT_ID_WIDTH',
                'CX': 'CONTEXT_ID_WIDTH',
                'MT': 'MESSAGE_TYPE_WIDTH',
                'PI': 'PACKET_ID_WIDTH',
                'U': 'USER_METADATA_WIDTH',
                'ER': 'ERROR_WIDTH',
                'E': 'LINK_EPOCH_WIDTH',
            }.items()
        }
        return a | dict(
            TB=a['TD'] // 8,
            FB=a['FD'] // 8,
            VW=max(1, (a['V'] - 1).bit_length()),
            TC=max(1, (self.NUM_TRAFFIC_CLASSES - 1).bit_length()),
            F=max(1, (self.fragments - 1).bit_length()),
            TO=self.TX_QUEUE_DEPTH.bit_length(),
            VO=self.RX_VC_DEPTH.bit_length(),
            RO=self.RX_QUEUE_DEPTH.bit_length(),
            CW=max(1, self.TX_INITIAL_CREDITS_PER_VC.bit_length()),
            **{'tile_network_interface_pkg::NI_ERROR_WIDTH': 5},
        )

    @cached_property
    def widths(self):
        def width(expr):
            return expr if isinstance(expr, int) else prod(self.aliases[n] for n in expr.split('*'))

        return {n: width(w) for n, (_, w) in PORTS.items()}

    def vc(self, traffic_class):
        return self.TRAFFIC_CLASS_TO_VC >> (traffic_class * self.aliases['VW']) & (
            (1 << self.aliases['VW']) - 1
        )
