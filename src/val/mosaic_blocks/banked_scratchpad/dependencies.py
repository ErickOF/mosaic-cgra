"""Ordered production RTL closure; no behavioral replacement of reused blocks."""
DEPENDENCIES = (
    'mosaic_blocks/banked_scratchpad_pkg',
    'building_blocks/scratchpad_bank_pkg',
    'building_blocks/scratchpad_controller_pkg',
    'common/dff', 'common/counter', 'common/decoder', 'common/priority_encoder',
    'common/operand_isolation', 'common/write_gate', 'basic/round_robin_arbiter',
    'basic/parity', 'basic/ecc', 'basic/sram_wrapper_backend', 'basic/sram_wrapper',
    'building_blocks/scratchpad_bank_counters',
    'building_blocks/scratchpad_controller_counters',
    'building_blocks/scratchpad_bank', 'building_blocks/scratchpad_controller',
    'mosaic_blocks/tile_shell_codec', 'mosaic_blocks/banked_scratchpad_state',
    'mosaic_blocks/banked_scratchpad_power', 'mosaic_blocks/banked_scratchpad_counters',
)
