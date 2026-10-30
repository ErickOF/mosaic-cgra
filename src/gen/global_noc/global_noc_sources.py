"""Ordered production source closure; no verification RTL in the design."""
SOURCES = (
    'common/ecc_pkg',
    'building_blocks/noc_router_pkg',
    'building_blocks/tile_network_interface_pkg',
    'mosaic_blocks/global_noc_pkg',
    'common/dff', 'common/counter', 'common/decoder', 'common/mux',
    'common/operand_isolation', 'common/priority_encoder',
    'basic/fifo', 'basic/parity', 'basic/ecc', 'basic/round_robin_arbiter',
    'basic/skid_buffer', 'building_blocks/event_barrier_state',
    'building_blocks/event_barrier_queue', 'building_blocks/noc_router_codec',
    'building_blocks/noc_router_buffer', 'building_blocks/noc_router',
    'building_blocks/tile_network_interface', 'mosaic_blocks/global_noc_link',
)
