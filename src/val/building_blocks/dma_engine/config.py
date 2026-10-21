"""Expected DMA geometry and reproducible native-simulation settings."""
from dataclasses import dataclass
from functools import cached_property
from decimal import Decimal
import os
from pathlib import Path
from dma_engine.constants import PORTS

DEFAULTS=dict(NUM_CHANNELS=2,COMMAND_QUEUE_DEPTH=4,DATA_FIFO_DEPTH=8,COMPLETION_QUEUE_DEPTH=4,
    EVENT_QUEUE_DEPTH=4,DATA_WIDTH=128,ADDR_WIDTH=40,COUNT_WIDTH=16,MODE_WIDTH=2,SPACE_ID_WIDTH=4,
    STREAM_ID_WIDTH=8,CONTEXT_ID_WIDTH=8,COMMAND_ID_WIDTH=12,PRIORITY_WIDTH=3,NUM_EVENTS=16,
    NUM_PROTECTION_REGIONS=8,MAX_BURST_BEATS=16,TRANSFER_TIMEOUT_CYCLES=65535,CANCEL_TIMEOUT_CYCLES=1024,
    DESCRIPTOR_EPOCH_WIDTH=2,SUPPORT_EVENT_START=1,SUPPORT_CANCELLATION=1,PROTECT_COMMAND_FIFO=0,ASYNC_RESET=0)


@dataclass(frozen=True)
class DmaConfig:
    parameters: dict[str,int]
    seed: int
    random_cycles: int
    coverage_file: Path
    check_internals: bool

    @classmethod
    def from_environment(cls):
        def get(name,default): return int(os.getenv('DMA_ENGINE_'+name,str(default)),0)
        parameters={name:get(name,value) for name,value in DEFAULTS.items()}
        report=Path(os.getenv('COCOTB_RESULTS_FILE','build/dma_engine/results.xml')).with_name('coverage.json')
        c=cls(parameters,get('SEED',20261020),get('RANDOM_CYCLES',2000),
            Path(os.getenv('DMA_ENGINE_COVERAGE_FILE',str(report))),bool(get('CHECK_INTERNALS',1)))
        assert c.random_cycles>=1000
        assert Decimal(os.getenv('TEST_SETTLE_NS','0'))==0
        return c

    def __getattr__(self,name):
        if name in self.parameters: return self.parameters[name]
        raise AttributeError(name)

    @cached_property
    def derived(self):
        p=self.parameters.copy()
        clog=lambda value:max(1,(value-1).bit_length())
        p['DATA_BYTES']=p['DATA_WIDTH']//8
        p['MAX_ELEMENT_BYTES_LOG2']=p['DATA_BYTES'].bit_length()-1
        p['SIZE_WIDTH']=clog(p['MAX_ELEMENT_BYTES_LOG2']+1)
        for derived,param in (('CHANNEL_WIDTH','NUM_CHANNELS'),('EVENT_ID_WIDTH','NUM_EVENTS'),
                ('REGION_ID_WIDTH','NUM_PROTECTION_REGIONS')): p[derived]=clog(p[param])
        for derived,param in (('BURST_WIDTH','MAX_BURST_BEATS'),('COMMAND_OCCUPANCY_WIDTH','COMMAND_QUEUE_DEPTH'),
                ('DATA_OCCUPANCY_WIDTH','DATA_FIFO_DEPTH'),('TIMEOUT_WIDTH','TRANSFER_TIMEOUT_CYCLES'),
                ('CANCEL_TIMEOUT_WIDTH','CANCEL_TIMEOUT_CYCLES')): p[derived]=clog(p[param]+1)
        p['BYTE_COUNT_WIDTH']=2*p['COUNT_WIDTH']+p['MAX_ELEMENT_BYTES_LOG2']+1
        return p

    @cached_property
    def widths(self):
        # Expressions are a checked-in arithmetic schema, never user input.
        return {name:eval(expression,{'__builtins__':{}},self.derived) for name,(_,expression) in PORTS.items()}
