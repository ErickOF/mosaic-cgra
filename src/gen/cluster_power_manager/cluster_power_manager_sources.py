"""Ordered production source closure for Clocked and Protected profiles."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCES = (
    'building_blocks/tile_power_controller_pkg', 'mosaic_blocks/cluster_power_manager_pkg',
    'common/dff', 'common/counter', 'common/clock_gate', 'common/reset_synchronizer',
    'common/isolation_cell', 'common/decoder', 'common/operand_isolation',
    'basic/fifo', 'basic/parity', 'basic/ecc', 'basic/performance_counters',
    'building_blocks/event_barrier_state', 'building_blocks/event_barrier_queue',
    'building_blocks/tile_power_controller', 'mosaic_blocks/tile_shell_codec',
    'mosaic_blocks/tile_shell_state', 'mosaic_blocks/cluster_power_manager_sync',
    'mosaic_blocks/cluster_power_manager_tiles', 'mosaic_blocks/cluster_power_manager_events',
    'mosaic_blocks/cluster_power_manager',
)
PATHS = tuple(ROOT / f'src/rtl/{name}.sv' for name in SOURCES)
