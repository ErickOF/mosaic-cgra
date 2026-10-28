"""Ordered production source closure shared by Make and Python validation."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCES = (
    'mosaic_blocks/runtime_controller_pkg', 'common/dff', 'common/counter',
    'common/priority_encoder', 'common/operand_isolation', 'common/decoder',
    'basic/fifo', 'basic/parity', 'basic/ecc', 'basic/round_robin_arbiter',
    'basic/performance_counters', 'building_blocks/event_barrier_state',
    'building_blocks/event_barrier_queue', 'mosaic_blocks/tile_shell_codec',
    'mosaic_blocks/tile_shell_state', 'mosaic_blocks/runtime_controller',
)
PATHS = tuple(ROOT / f'src/rtl/{name}.sv' for name in SOURCES)
