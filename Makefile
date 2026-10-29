SHELL := bash
.DEFAULT_GOAL := pyuvm

PROJECT_ROOT := $(patsubst %/,%,$(dir $(abspath $(lastword $(MAKEFILE_LIST)))))
PYTHON ?= python3
VENV ?= $(PROJECT_ROOT)/.venv
PYTHON_BIN ?= $(VENV)/bin/python

SIM ?= vcs
TOPLEVEL_LANG ?= verilog
COCOTB_TOPLEVEL ?= counter
COCOTB_TEST_MODULES ?= test_$(COCOTB_TOPLEVEL)
# Discover validation modules by top name across RTL/validation categories.
# Override the directory when a top has multiple suites or lives elsewhere.
PYUVM_TEST_DIR ?= $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/$(COCOTB_TOPLEVEL)))
ACCUMULATOR_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/accumulator))
PREDICATE_UNIT_TEST_DIR := $(PROJECT_ROOT)/src/val/building_blocks/predicate_unit
VECTOR_REDUCTION_TEST_DIR := $(PROJECT_ROOT)/src/val/building_blocks/vector_reduction
VECTOR_LANE_TEST_DIR := $(PROJECT_ROOT)/src/val/building_blocks/vector_lane
SCALAR_ALU_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/scalar_alu))
NOC_ROUTER_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/noc_router))
MULTIPLIER_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/multiplier))
MAC_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/mac))
LUT_UNIT_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/lut_unit))
RSQRT_UNIT_TEST_DIR := $(PROJECT_ROOT)/src/val/building_blocks/rsqrt_unit
RECIPROCAL_UNIT_TEST_DIR := $(PROJECT_ROOT)/src/val/building_blocks/reciprocal_unit
POLYNOMIAL_UNIT_TEST_DIR := $(PROJECT_ROOT)/src/val/building_blocks/polynomial_unit
LOOP_CONTROLLER_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/loop_controller))
TILE_POWER_CONTROLLER_TEST_DIR := $(PROJECT_ROOT)/src/val/building_blocks/tile_power_controller
TILE_NETWORK_INTERFACE_TEST_DIR := $(PROJECT_ROOT)/src/val/building_blocks/tile_network_interface
LOCAL_SWITCH_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/local_switch))
SCRATCHPAD_CONTROLLER_TEST_DIR := $(PROJECT_ROOT)/src/val/building_blocks/scratchpad_controller
SCRATCHPAD_BANK_TEST_DIR := $(PROJECT_ROOT)/src/val/building_blocks/scratchpad_bank
STREAM_FORMATTER_TEST_DIR := $(PROJECT_ROOT)/src/val/building_blocks/stream_formatter
STORE_ENGINE_TEST_DIR := $(PROJECT_ROOT)/src/val/building_blocks/store_engine
LOAD_ENGINE_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/load_engine))
EXP_UNIT_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/exp_unit))
EVENT_BARRIER_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/event_barrier))
DOT_PRODUCT_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/dot_product))
AGU_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/agu))
DMA_ENGINE_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/dma_engine))
COUNTER_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/counter))
CLOCK_GATE_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/clock_gate))
DECODER_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/decoder))
DFF_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/dff))
ISOLATION_CELL_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/isolation_cell))
LANE_MASK_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/lane_mask))
LEVEL_SHIFTER_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/level_shifter))
MUX_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/mux))
OPERAND_ISOLATION_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/operand_isolation))
PRIORITY_ENCODER_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/priority_encoder))
RESET_SYNCHRONIZER_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/reset_synchronizer))
RETENTION_REGISTER_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/retention_register))
WRITE_GATE_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/write_gate))
ASYNC_FIFO_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/async_fifo))
BYPASS_NETWORK_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/bypass_network))
CONTEXT_MEMORY_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/context_memory))
CONTEXT_SEQUENCER_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/context_sequencer))
DATA_ALIGNER_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/data_aligner))
ECC_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/ecc))
FIFO_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/fifo))
PACKER_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/packer))
RDU_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/rdu))
VECTOR_REGISTER_FILE_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/vector_register_file))
REGISTER_FILE_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/register_file))
REGISTER_SLICE_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/register_slice))
ROUND_ROBIN_ARBITER_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/round_robin_arbiter))
SKID_BUFFER_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/skid_buffer))
STREAM_JOIN_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/stream_join))
WIDTH_CONVERTER_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/width_converter))
STREAM_FORK_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/stream_fork))
SRAM_WRAPPER_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/sram_wrapper))
PERFORMANCE_COUNTERS_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/performance_counters))
PARITY_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/parity))
# Locate the selected RTL top using the same category layout as validation.
# Include each basic module's common dependencies. Caller lists take precedence.
_ACCUMULATOR_SOURCES := $(PROJECT_ROOT)/src/rtl/building_blocks/accumulator_pkg.sv $(PROJECT_ROOT)/src/rtl/common/dff.sv $(PROJECT_ROOT)/src/rtl/common/lane_mask.sv $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv $(PROJECT_ROOT)/src/rtl/building_blocks/accumulator.sv
_RTL_SOURCES_accumulator := $(_ACCUMULATOR_SOURCES)
_LUT_UNIT_SOURCES := $(PROJECT_ROOT)/src/rtl/building_blocks/lut_unit_pkg.sv $(PROJECT_ROOT)/src/rtl/common/dff.sv $(PROJECT_ROOT)/src/rtl/common/decoder.sv $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv $(PROJECT_ROOT)/src/rtl/basic/fifo.sv $(PROJECT_ROOT)/src/rtl/basic/parity.sv $(PROJECT_ROOT)/src/rtl/basic/ecc.sv $(PROJECT_ROOT)/src/rtl/building_blocks/event_barrier_state.sv $(PROJECT_ROOT)/src/rtl/building_blocks/event_barrier_queue.sv $(PROJECT_ROOT)/src/rtl/building_blocks/lut_unit_bank.sv $(PROJECT_ROOT)/src/rtl/building_blocks/lut_unit.sv
_RTL_SOURCES_lut_unit := $(_LUT_UNIT_SOURCES)
_RSQRT_UNIT_SOURCES := $(PROJECT_ROOT)/src/rtl/building_blocks/rsqrt_unit_pkg.sv $(PROJECT_ROOT)/src/rtl/building_blocks/scalar_alu_pkg.sv $(PROJECT_ROOT)/src/rtl/common/dff.sv $(PROJECT_ROOT)/src/rtl/common/reset_synchronizer.sv $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv $(PROJECT_ROOT)/src/rtl/common/decoder.sv $(PROJECT_ROOT)/src/rtl/common/priority_encoder.sv $(PROJECT_ROOT)/src/rtl/common/mux.sv $(PROJECT_ROOT)/src/rtl/basic/fifo.sv $(PROJECT_ROOT)/src/rtl/basic/parity.sv $(PROJECT_ROOT)/src/rtl/basic/ecc.sv $(PROJECT_ROOT)/src/rtl/building_blocks/event_barrier_state.sv $(PROJECT_ROOT)/src/rtl/building_blocks/event_barrier_queue.sv $(PROJECT_ROOT)/src/rtl/building_blocks/multiplier.sv $(PROJECT_ROOT)/src/rtl/building_blocks/scalar_alu.sv $(PROJECT_ROOT)/src/rtl/building_blocks/polynomial_unit_round.sv $(PROJECT_ROOT)/src/rtl/building_blocks/protected_seed_rom.sv $(PROJECT_ROOT)/src/rtl/building_blocks/reciprocal_unit_scale.sv $(PROJECT_ROOT)/src/rtl/building_blocks/rsqrt_unit_normalize.sv $(PROJECT_ROOT)/src/rtl/building_blocks/rsqrt_unit_seed.sv $(PROJECT_ROOT)/src/rtl/building_blocks/rsqrt_unit_newton.sv $(PROJECT_ROOT)/src/rtl/building_blocks/rsqrt_unit.sv
_RTL_SOURCES_rsqrt_unit := $(_RSQRT_UNIT_SOURCES)
_RECIPROCAL_UNIT_SOURCES := $(PROJECT_ROOT)/src/rtl/building_blocks/reciprocal_unit_pkg.sv $(PROJECT_ROOT)/src/rtl/building_blocks/scalar_alu_pkg.sv $(PROJECT_ROOT)/src/rtl/common/dff.sv $(PROJECT_ROOT)/src/rtl/common/reset_synchronizer.sv $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv $(PROJECT_ROOT)/src/rtl/common/decoder.sv $(PROJECT_ROOT)/src/rtl/common/priority_encoder.sv $(PROJECT_ROOT)/src/rtl/common/mux.sv $(PROJECT_ROOT)/src/rtl/basic/fifo.sv $(PROJECT_ROOT)/src/rtl/basic/parity.sv $(PROJECT_ROOT)/src/rtl/basic/ecc.sv $(PROJECT_ROOT)/src/rtl/building_blocks/event_barrier_state.sv $(PROJECT_ROOT)/src/rtl/building_blocks/event_barrier_queue.sv $(PROJECT_ROOT)/src/rtl/building_blocks/multiplier.sv $(PROJECT_ROOT)/src/rtl/building_blocks/scalar_alu.sv $(PROJECT_ROOT)/src/rtl/building_blocks/polynomial_unit_round.sv $(PROJECT_ROOT)/src/rtl/building_blocks/reciprocal_unit_normalize.sv $(PROJECT_ROOT)/src/rtl/building_blocks/protected_seed_rom.sv $(PROJECT_ROOT)/src/rtl/building_blocks/reciprocal_unit_seed.sv $(PROJECT_ROOT)/src/rtl/building_blocks/reciprocal_unit_newton.sv $(PROJECT_ROOT)/src/rtl/building_blocks/reciprocal_unit_scale.sv $(PROJECT_ROOT)/src/rtl/building_blocks/reciprocal_unit.sv
_RTL_SOURCES_reciprocal_unit := $(_RECIPROCAL_UNIT_SOURCES)
_POLYNOMIAL_UNIT_SOURCES := $(PROJECT_ROOT)/src/rtl/building_blocks/polynomial_unit_pkg.sv $(PROJECT_ROOT)/src/rtl/common/dff.sv $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv $(PROJECT_ROOT)/src/rtl/common/decoder.sv $(PROJECT_ROOT)/src/rtl/common/mux.sv $(PROJECT_ROOT)/src/rtl/basic/fifo.sv $(PROJECT_ROOT)/src/rtl/basic/parity.sv $(PROJECT_ROOT)/src/rtl/basic/ecc.sv $(PROJECT_ROOT)/src/rtl/building_blocks/event_barrier_state.sv $(PROJECT_ROOT)/src/rtl/building_blocks/event_barrier_queue.sv $(PROJECT_ROOT)/src/rtl/building_blocks/lut_unit_bank.sv $(PROJECT_ROOT)/src/rtl/building_blocks/multiplier.sv $(PROJECT_ROOT)/src/rtl/building_blocks/polynomial_unit_round.sv $(PROJECT_ROOT)/src/rtl/building_blocks/polynomial_unit_horner.sv $(PROJECT_ROOT)/src/rtl/building_blocks/polynomial_unit_scale.sv $(PROJECT_ROOT)/src/rtl/building_blocks/polynomial_unit.sv
_RTL_SOURCES_polynomial_unit := $(_POLYNOMIAL_UNIT_SOURCES)
_LOOP_CONTROLLER_SOURCES := $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv $(PROJECT_ROOT)/src/rtl/building_blocks/loop_controller_pkg.sv $(PROJECT_ROOT)/src/rtl/common/dff.sv $(PROJECT_ROOT)/src/rtl/common/decoder.sv $(PROJECT_ROOT)/src/rtl/common/priority_encoder.sv $(PROJECT_ROOT)/src/rtl/common/write_gate.sv $(PROJECT_ROOT)/src/rtl/basic/parity.sv $(PROJECT_ROOT)/src/rtl/building_blocks/event_barrier_state.sv $(PROJECT_ROOT)/src/rtl/building_blocks/loop_controller.sv
_RTL_SOURCES_loop_controller := $(_LOOP_CONTROLLER_SOURCES)
_TILE_POWER_CONTROLLER_SOURCES := $(PROJECT_ROOT)/src/rtl/building_blocks/tile_power_controller_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/common/dff.sv $(PROJECT_ROOT)/src/rtl/common/counter.sv \
    $(PROJECT_ROOT)/src/rtl/common/reset_synchronizer.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/tile_power_controller.sv
_RTL_SOURCES_tile_power_controller := $(_TILE_POWER_CONTROLLER_SOURCES)
_TILE_SHELL_SOURCES := $(PROJECT_ROOT)/src/rtl/mosaic_blocks/tile_shell_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/basic/context_sequencer_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/tile_power_controller_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/common/dff.sv \
    $(PROJECT_ROOT)/src/rtl/common/counter.sv \
    $(PROJECT_ROOT)/src/rtl/common/decoder.sv \
    $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv \
    $(PROJECT_ROOT)/src/rtl/common/reset_synchronizer.sv \
    $(PROJECT_ROOT)/src/rtl/basic/fifo.sv \
    $(PROJECT_ROOT)/src/rtl/basic/parity.sv \
    $(PROJECT_ROOT)/src/rtl/basic/ecc.sv \
    $(PROJECT_ROOT)/src/rtl/basic/context_memory.sv \
    $(PROJECT_ROOT)/src/rtl/basic/context_sequencer.sv \
    $(PROJECT_ROOT)/src/rtl/basic/async_fifo.sv \
    $(PROJECT_ROOT)/src/rtl/basic/performance_counters.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/event_barrier_state.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/event_barrier_queue.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/tile_power_controller.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/tile_shell_codec.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/tile_shell_state.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/tile_shell_queue.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/tile_shell.sv
_RTL_SOURCES_tile_shell := $(_TILE_SHELL_SOURCES)
_RTL_SOURCES_configuration_network := $(PROJECT_ROOT)/src/rtl/common/dff.sv \
    $(PROJECT_ROOT)/src/rtl/common/counter.sv \
    $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv \
    $(PROJECT_ROOT)/src/rtl/common/write_gate.sv \
    $(PROJECT_ROOT)/src/rtl/common/decoder.sv \
    $(PROJECT_ROOT)/src/rtl/common/mux.sv \
    $(PROJECT_ROOT)/src/rtl/common/priority_encoder.sv \
    $(PROJECT_ROOT)/src/rtl/basic/fifo.sv \
    $(PROJECT_ROOT)/src/rtl/basic/skid_buffer.sv \
    $(PROJECT_ROOT)/src/rtl/basic/register_slice.sv \
    $(PROJECT_ROOT)/src/rtl/basic/stream_fork.sv \
    $(PROJECT_ROOT)/src/rtl/basic/round_robin_arbiter.sv \
    $(PROJECT_ROOT)/src/rtl/basic/parity.sv \
    $(PROJECT_ROOT)/src/rtl/basic/ecc.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/tile_shell_codec.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/banked_scratchpad_state.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/banked_scratchpad_counters.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/event_barrier_state.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/event_barrier_queue.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/static_mesh_queue.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/static_mesh_link.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/configuration_network_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/configuration_network_crc.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/configuration_network_serializer.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/configuration_network_receiver.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/configuration_network_link.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/configuration_network_fork.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/configuration_network_tree.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/configuration_network_tile_adapter.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/configuration_network.sv
_RTL_SOURCES_configuration_network_tile_adapter := $(filter-out %/configuration_network.sv,$(_RTL_SOURCES_configuration_network))

_RTL_SOURCES_predicate_network := $(PROJECT_ROOT)/src/rtl/building_blocks/local_switch_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/static_mesh_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/common/dff.sv \
    $(PROJECT_ROOT)/src/rtl/common/mux.sv \
    $(PROJECT_ROOT)/src/rtl/common/decoder.sv \
    $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv \
    $(PROJECT_ROOT)/src/rtl/common/write_gate.sv \
    $(PROJECT_ROOT)/src/rtl/common/counter.sv \
    $(PROJECT_ROOT)/src/rtl/common/priority_encoder.sv \
    $(PROJECT_ROOT)/src/rtl/common/lane_mask.sv \
    $(PROJECT_ROOT)/src/rtl/basic/register_slice.sv \
    $(PROJECT_ROOT)/src/rtl/basic/skid_buffer.sv \
    $(PROJECT_ROOT)/src/rtl/basic/fifo.sv \
    $(PROJECT_ROOT)/src/rtl/basic/ecc.sv \
    $(PROJECT_ROOT)/src/rtl/basic/parity.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/banked_scratchpad_counters.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/local_switch.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/event_barrier_state.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/event_barrier_queue.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/tile_shell_codec.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/banked_scratchpad_state.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/static_mesh_node.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/static_mesh_link.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/static_mesh_queue.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/predicate_network_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/predicate_network_schedule.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/predicate_network_control.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/predicate_network.sv

_RTL_SOURCES_static_mesh := $(PROJECT_ROOT)/src/rtl/building_blocks/local_switch_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/static_mesh_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/common/dff.sv \
    $(PROJECT_ROOT)/src/rtl/common/mux.sv \
    $(PROJECT_ROOT)/src/rtl/common/decoder.sv \
    $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv \
    $(PROJECT_ROOT)/src/rtl/common/write_gate.sv \
    $(PROJECT_ROOT)/src/rtl/common/counter.sv \
    $(PROJECT_ROOT)/src/rtl/common/priority_encoder.sv \
    $(PROJECT_ROOT)/src/rtl/common/lane_mask.sv \
    $(PROJECT_ROOT)/src/rtl/basic/register_slice.sv \
    $(PROJECT_ROOT)/src/rtl/basic/skid_buffer.sv \
    $(PROJECT_ROOT)/src/rtl/basic/context_memory.sv \
    $(PROJECT_ROOT)/src/rtl/basic/fifo.sv \
    $(PROJECT_ROOT)/src/rtl/basic/ecc.sv \
    $(PROJECT_ROOT)/src/rtl/basic/parity.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/banked_scratchpad_counters.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/local_switch.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/event_barrier_state.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/event_barrier_queue.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/tile_shell_codec.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/banked_scratchpad_state.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/static_mesh_node.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/static_mesh_link.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/static_mesh_queue.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/static_mesh_control.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/static_mesh.sv

_RTL_SOURCES_mst := $(PROJECT_ROOT)/src/rtl/basic/context_sequencer_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/agu_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/dma_engine_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/load_engine_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/store_engine_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/stream_formatter_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/tile_power_controller_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/mst_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/tile_shell_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/basic/async_fifo.sv \
    $(PROJECT_ROOT)/src/rtl/basic/context_memory.sv \
    $(PROJECT_ROOT)/src/rtl/basic/context_sequencer.sv \
    $(PROJECT_ROOT)/src/rtl/basic/data_aligner.sv \
    $(PROJECT_ROOT)/src/rtl/basic/ecc.sv \
    $(PROJECT_ROOT)/src/rtl/basic/fifo.sv \
    $(PROJECT_ROOT)/src/rtl/basic/packer.sv \
    $(PROJECT_ROOT)/src/rtl/basic/parity.sv \
    $(PROJECT_ROOT)/src/rtl/basic/performance_counters.sv \
    $(PROJECT_ROOT)/src/rtl/basic/register_slice.sv \
    $(PROJECT_ROOT)/src/rtl/basic/round_robin_arbiter.sv \
    $(PROJECT_ROOT)/src/rtl/basic/width_converter.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/agu.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/dma_engine_bounds.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/dma_engine_command_queue.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/event_barrier_queue.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/event_barrier_state.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/load_engine.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/store_engine.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/stream_formatter.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/tile_power_controller.sv \
    $(PROJECT_ROOT)/src/rtl/common/counter.sv \
    $(PROJECT_ROOT)/src/rtl/common/decoder.sv \
    $(PROJECT_ROOT)/src/rtl/common/dff.sv \
    $(PROJECT_ROOT)/src/rtl/common/lane_mask.sv \
    $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv \
    $(PROJECT_ROOT)/src/rtl/common/priority_encoder.sv \
    $(PROJECT_ROOT)/src/rtl/common/reset_synchronizer.sv \
    $(PROJECT_ROOT)/src/rtl/common/write_gate.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/banked_scratchpad_counters.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/banked_scratchpad_state.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/mst.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/mst_body.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/mst_channel.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/mst_command_queue.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/mst_element_converter.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/mst_fragment_adapter.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/mst_validate.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/tile_shell.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/tile_shell_codec.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/tile_shell_queue.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/tile_shell_state.sv
_BCT_SOURCES := $(_TILE_SHELL_SOURCES) $(PROJECT_ROOT)/src/rtl/mosaic_blocks/bct_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/scalar_alu_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/predicate_unit_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/accumulator_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/common/write_gate.sv \
    $(PROJECT_ROOT)/src/rtl/common/lane_mask.sv \
    $(PROJECT_ROOT)/src/rtl/common/mux.sv \
    $(PROJECT_ROOT)/src/rtl/basic/register_file.sv \
    $(PROJECT_ROOT)/src/rtl/basic/bypass_network.sv \
    $(PROJECT_ROOT)/src/rtl/basic/rdu.sv \
    $(PROJECT_ROOT)/src/rtl/basic/stream_join.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/scalar_alu.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/multiplier.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/dot_product.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/mac.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/accumulator.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/predicate_unit.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/bct_body.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/bct.sv
_RTL_SOURCES_bct := $(_BCT_SOURCES)
_VCT_SOURCES := $(PROJECT_ROOT)/src/rtl/mosaic_blocks/tile_shell_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/basic/context_sequencer_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/tile_power_controller_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/common/dff.sv \
    $(PROJECT_ROOT)/src/rtl/common/counter.sv \
    $(PROJECT_ROOT)/src/rtl/common/decoder.sv \
    $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv \
    $(PROJECT_ROOT)/src/rtl/common/reset_synchronizer.sv \
    $(PROJECT_ROOT)/src/rtl/basic/fifo.sv \
    $(PROJECT_ROOT)/src/rtl/basic/parity.sv \
    $(PROJECT_ROOT)/src/rtl/basic/ecc.sv \
    $(PROJECT_ROOT)/src/rtl/basic/context_memory.sv \
    $(PROJECT_ROOT)/src/rtl/basic/context_sequencer.sv \
    $(PROJECT_ROOT)/src/rtl/basic/async_fifo.sv \
    $(PROJECT_ROOT)/src/rtl/basic/performance_counters.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/event_barrier_state.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/event_barrier_queue.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/tile_power_controller.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/tile_shell_codec.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/tile_shell_state.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/tile_shell_queue.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/tile_shell.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/scalar_alu_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/predicate_unit_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/accumulator_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/common/write_gate.sv \
    $(PROJECT_ROOT)/src/rtl/common/lane_mask.sv \
    $(PROJECT_ROOT)/src/rtl/common/mux.sv \
    $(PROJECT_ROOT)/src/rtl/basic/register_file.sv \
    $(PROJECT_ROOT)/src/rtl/basic/bypass_network.sv \
    $(PROJECT_ROOT)/src/rtl/basic/rdu.sv \
    $(PROJECT_ROOT)/src/rtl/basic/stream_join.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/scalar_alu.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/multiplier.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/dot_product.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/mac.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/accumulator.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/predicate_unit.sv \
    $(PROJECT_ROOT)/src/rtl/basic/vector_register_file.sv \
    $(PROJECT_ROOT)/src/rtl/basic/packer.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/vector_lane_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/vector_reduction_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/vector_lane_pipeline.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/vector_lane.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/vector_reduction_tree.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/vector_reduction.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/vct_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/vct_vrf.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/vct_accumulator.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/vct_body.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/vct.sv
_RTL_SOURCES_vct := $(_VCT_SOURCES)
_TILE_NETWORK_INTERFACE_SOURCES := $(PROJECT_ROOT)/src/rtl/building_blocks/tile_network_interface_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/common/dff.sv $(PROJECT_ROOT)/src/rtl/common/counter.sv \
    $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv $(PROJECT_ROOT)/src/rtl/common/decoder.sv \
    $(PROJECT_ROOT)/src/rtl/common/priority_encoder.sv $(PROJECT_ROOT)/src/rtl/basic/fifo.sv \
    $(PROJECT_ROOT)/src/rtl/basic/parity.sv $(PROJECT_ROOT)/src/rtl/basic/round_robin_arbiter.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/event_barrier_state.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/event_barrier_queue.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/tile_network_interface.sv
_RTL_SOURCES_tile_network_interface := $(_TILE_NETWORK_INTERFACE_SOURCES)
_LOCAL_SWITCH_SOURCES := $(PROJECT_ROOT)/src/rtl/building_blocks/local_switch_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/common/dff.sv $(PROJECT_ROOT)/src/rtl/common/decoder.sv \
    $(PROJECT_ROOT)/src/rtl/common/mux.sv $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv \
    $(PROJECT_ROOT)/src/rtl/basic/register_slice.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/local_switch.sv
_RTL_SOURCES_local_switch := $(_LOCAL_SWITCH_SOURCES)
_RTL_SOURCES_scratchpad_controller = $(PROJECT_ROOT)/src/rtl/building_blocks/scratchpad_bank_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/scratchpad_controller_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/common/dff.sv $(PROJECT_ROOT)/src/rtl/common/priority_encoder.sv \
    $(PROJECT_ROOT)/src/rtl/common/counter.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/scratchpad_controller_counters.sv \
    $(PROJECT_ROOT)/src/rtl/common/decoder.sv $(PROJECT_ROOT)/src/rtl/basic/round_robin_arbiter.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/scratchpad_controller.sv
_RTL_SOURCES_scratchpad_bank = $(PROJECT_ROOT)/src/rtl/building_blocks/scratchpad_bank_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/common/dff.sv \
    $(PROJECT_ROOT)/src/rtl/common/counter.sv \
    $(PROJECT_ROOT)/src/rtl/common/decoder.sv \
    $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv \
    $(PROJECT_ROOT)/src/rtl/common/write_gate.sv \
    $(PROJECT_ROOT)/src/rtl/basic/parity.sv \
    $(PROJECT_ROOT)/src/rtl/basic/ecc.sv \
    $(SRAM_BACKEND_SOURCE) \
    $(PROJECT_ROOT)/src/rtl/basic/sram_wrapper.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/scratchpad_bank_counters.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/scratchpad_bank.sv
_RTL_SOURCES_banked_scratchpad = $(PROJECT_ROOT)/src/rtl/mosaic_blocks/banked_scratchpad_pkg.sv \
    $(_RTL_SOURCES_scratchpad_controller) \
    $(filter-out $(_RTL_SOURCES_scratchpad_controller),$(_RTL_SOURCES_scratchpad_bank)) \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/tile_shell_codec.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/banked_scratchpad_state.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/banked_scratchpad_power.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/banked_scratchpad_counters.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/banked_scratchpad.sv
_RTL_SOURCES_stream_formatter := $(PROJECT_ROOT)/src/rtl/building_blocks/stream_formatter_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/common/dff.sv \
    $(PROJECT_ROOT)/src/rtl/common/counter.sv \
    $(PROJECT_ROOT)/src/rtl/common/lane_mask.sv \
    $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv \
    $(PROJECT_ROOT)/src/rtl/common/write_gate.sv \
    $(PROJECT_ROOT)/src/rtl/basic/register_slice.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/stream_formatter.sv
_RTL_SOURCES_store_engine := $(PROJECT_ROOT)/src/rtl/building_blocks/agu_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/dma_engine_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/store_engine_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/common/dff.sv \
    $(PROJECT_ROOT)/src/rtl/common/counter.sv \
    $(PROJECT_ROOT)/src/rtl/common/decoder.sv \
    $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv \
    $(PROJECT_ROOT)/src/rtl/common/write_gate.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/dma_engine_bounds.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/agu.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/store_engine_counters.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/store_engine.sv
_LOAD_ENGINE_SOURCES := $(PROJECT_ROOT)/src/rtl/building_blocks/agu_pkg.sv $(PROJECT_ROOT)/src/rtl/building_blocks/dma_engine_pkg.sv $(PROJECT_ROOT)/src/rtl/building_blocks/load_engine_pkg.sv $(PROJECT_ROOT)/src/rtl/common/dff.sv $(PROJECT_ROOT)/src/rtl/common/counter.sv $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv $(PROJECT_ROOT)/src/rtl/common/decoder.sv $(PROJECT_ROOT)/src/rtl/building_blocks/dma_engine_bounds.sv $(PROJECT_ROOT)/src/rtl/common/write_gate.sv $(PROJECT_ROOT)/src/rtl/building_blocks/agu.sv $(PROJECT_ROOT)/src/rtl/building_blocks/load_engine_counters.sv $(PROJECT_ROOT)/src/rtl/building_blocks/load_engine.sv
_RTL_SOURCES_load_engine := $(_LOAD_ENGINE_SOURCES)
_EXP_UNIT_SOURCES := $(PROJECT_ROOT)/src/rtl/building_blocks/generated/exp_unit_tables_pkg.sv $(PROJECT_ROOT)/src/rtl/building_blocks/exp_unit_pkg.sv $(PROJECT_ROOT)/src/rtl/building_blocks/scalar_alu_pkg.sv $(PROJECT_ROOT)/src/rtl/common/dff.sv $(PROJECT_ROOT)/src/rtl/common/counter.sv $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv $(PROJECT_ROOT)/src/rtl/common/decoder.sv $(PROJECT_ROOT)/src/rtl/basic/fifo.sv $(PROJECT_ROOT)/src/rtl/basic/parity.sv $(PROJECT_ROOT)/src/rtl/basic/ecc.sv $(PROJECT_ROOT)/src/rtl/building_blocks/event_barrier_state.sv $(PROJECT_ROOT)/src/rtl/building_blocks/event_barrier_queue.sv $(PROJECT_ROOT)/src/rtl/common/mux.sv $(PROJECT_ROOT)/src/rtl/building_blocks/multiplier.sv $(PROJECT_ROOT)/src/rtl/building_blocks/scalar_alu.sv $(PROJECT_ROOT)/src/rtl/building_blocks/polynomial_unit_round.sv $(PROJECT_ROOT)/src/rtl/building_blocks/exp_unit_interpolate.sv $(PROJECT_ROOT)/src/rtl/building_blocks/exp_unit_rom.sv $(PROJECT_ROOT)/src/rtl/building_blocks/exp_unit_stage.sv $(PROJECT_ROOT)/src/rtl/building_blocks/exp_unit.sv
_RTL_SOURCES_exp_unit := $(_EXP_UNIT_SOURCES)
_EVENT_BARRIER_SOURCES := $(PROJECT_ROOT)/src/rtl/building_blocks/event_barrier_pkg.sv $(PROJECT_ROOT)/src/rtl/common/dff.sv $(PROJECT_ROOT)/src/rtl/common/counter.sv $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv $(PROJECT_ROOT)/src/rtl/common/decoder.sv $(PROJECT_ROOT)/src/rtl/common/priority_encoder.sv $(PROJECT_ROOT)/src/rtl/basic/fifo.sv $(PROJECT_ROOT)/src/rtl/basic/parity.sv $(PROJECT_ROOT)/src/rtl/basic/round_robin_arbiter.sv $(PROJECT_ROOT)/src/rtl/building_blocks/event_barrier_state.sv $(PROJECT_ROOT)/src/rtl/building_blocks/event_barrier_queue.sv $(PROJECT_ROOT)/src/rtl/building_blocks/event_barrier.sv
_RTL_SOURCES_event_barrier := $(_EVENT_BARRIER_SOURCES)
_DOT_PRODUCT_SOURCES := $(PROJECT_ROOT)/src/rtl/common/dff.sv $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv $(PROJECT_ROOT)/src/rtl/building_blocks/dot_product.sv
_RTL_SOURCES_dot_product := $(_DOT_PRODUCT_SOURCES)
_RTL_SOURCES_scalar_alu := $(PROJECT_ROOT)/src/rtl/building_blocks/scalar_alu_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv \
    $(PROJECT_ROOT)/src/rtl/common/mux.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/scalar_alu.sv
_RTL_SOURCES_predicate_unit := $(PROJECT_ROOT)/src/rtl/building_blocks/predicate_unit_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/common/dff.sv \
    $(PROJECT_ROOT)/src/rtl/common/decoder.sv \
    $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv \
    $(PROJECT_ROOT)/src/rtl/common/write_gate.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/predicate_unit.sv
_RTL_SOURCES_vector_reduction := $(PROJECT_ROOT)/src/rtl/building_blocks/scalar_alu_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/vector_lane_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/vector_reduction_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/common/dff.sv \
    $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv \
    $(PROJECT_ROOT)/src/rtl/common/write_gate.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/vector_lane_pipeline.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/vector_reduction_tree.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/vector_reduction.sv
_RTL_SOURCES_vector_lane := $(PROJECT_ROOT)/src/rtl/building_blocks/scalar_alu_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/vector_lane_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/common/dff.sv \
    $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv \
    $(PROJECT_ROOT)/src/rtl/common/mux.sv \
    $(PROJECT_ROOT)/src/rtl/common/write_gate.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/scalar_alu.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/multiplier.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/dot_product.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/mac.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/vector_lane_pipeline.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/vector_lane.sv
_NOC_ROUTER_SOURCES := $(PROJECT_ROOT)/src/rtl/building_blocks/noc_router_pkg.sv $(PROJECT_ROOT)/src/rtl/common/dff.sv $(PROJECT_ROOT)/src/rtl/common/counter.sv $(PROJECT_ROOT)/src/rtl/common/decoder.sv $(PROJECT_ROOT)/src/rtl/common/mux.sv $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv $(PROJECT_ROOT)/src/rtl/common/priority_encoder.sv $(PROJECT_ROOT)/src/rtl/basic/fifo.sv $(PROJECT_ROOT)/src/rtl/basic/parity.sv $(PROJECT_ROOT)/src/rtl/basic/ecc.sv $(PROJECT_ROOT)/src/rtl/basic/round_robin_arbiter.sv $(PROJECT_ROOT)/src/rtl/building_blocks/event_barrier_state.sv $(PROJECT_ROOT)/src/rtl/building_blocks/event_barrier_queue.sv $(PROJECT_ROOT)/src/rtl/building_blocks/noc_router_codec.sv $(PROJECT_ROOT)/src/rtl/building_blocks/noc_router_buffer.sv $(PROJECT_ROOT)/src/rtl/building_blocks/noc_router.sv
_RTL_SOURCES_noc_router := $(_NOC_ROUTER_SOURCES)
_RTL_SOURCES_multiplier := $(PROJECT_ROOT)/src/rtl/common/dff.sv $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv $(PROJECT_ROOT)/src/rtl/building_blocks/multiplier.sv
_RTL_SOURCES_mac := $(_DOT_PRODUCT_SOURCES) $(PROJECT_ROOT)/src/rtl/building_blocks/mac.sv
_AGU_SOURCES := $(PROJECT_ROOT)/src/rtl/building_blocks/agu_pkg.sv $(PROJECT_ROOT)/src/rtl/common/counter.sv $(PROJECT_ROOT)/src/rtl/common/dff.sv $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv $(PROJECT_ROOT)/src/rtl/common/write_gate.sv $(PROJECT_ROOT)/src/rtl/building_blocks/agu.sv
_RTL_SOURCES_agu := $(_AGU_SOURCES)
_DMA_ENGINE_SOURCES := $(PROJECT_ROOT)/src/rtl/building_blocks/dma_engine_pkg.sv $(PROJECT_ROOT)/src/rtl/common/dff.sv $(PROJECT_ROOT)/src/rtl/common/decoder.sv $(PROJECT_ROOT)/src/rtl/common/write_gate.sv $(PROJECT_ROOT)/src/rtl/common/counter.sv $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv $(PROJECT_ROOT)/src/rtl/common/priority_encoder.sv $(PROJECT_ROOT)/src/rtl/basic/fifo.sv $(PROJECT_ROOT)/src/rtl/basic/parity.sv $(PROJECT_ROOT)/src/rtl/basic/round_robin_arbiter.sv $(PROJECT_ROOT)/src/rtl/building_blocks/dma_engine_bounds.sv $(PROJECT_ROOT)/src/rtl/building_blocks/dma_engine_command_queue.sv $(PROJECT_ROOT)/src/rtl/building_blocks/dma_engine.sv
_RTL_SOURCES_dma_engine := $(_DMA_ENGINE_SOURCES)
_ASYNC_FIFO_SOURCES := $(PROJECT_ROOT)/src/rtl/common/counter.sv $(PROJECT_ROOT)/src/rtl/common/dff.sv $(PROJECT_ROOT)/src/rtl/basic/async_fifo.sv
_BYPASS_NETWORK_SOURCES := $(PROJECT_ROOT)/src/rtl/common/dff.sv $(PROJECT_ROOT)/src/rtl/basic/bypass_network.sv
_CONTEXT_MEMORY_SOURCES := $(PROJECT_ROOT)/src/rtl/common/decoder.sv $(PROJECT_ROOT)/src/rtl/common/dff.sv $(PROJECT_ROOT)/src/rtl/basic/context_memory.sv
_CONTEXT_SEQUENCER_SOURCES := $(PROJECT_ROOT)/src/rtl/basic/context_sequencer_pkg.sv $(PROJECT_ROOT)/src/rtl/common/dff.sv $(PROJECT_ROOT)/src/rtl/common/counter.sv $(PROJECT_ROOT)/src/rtl/basic/context_sequencer.sv
_RTL_SOURCES_async_fifo := $(_ASYNC_FIFO_SOURCES)
_RTL_SOURCES_bypass_network := $(_BYPASS_NETWORK_SOURCES)
_RTL_SOURCES_context_memory := $(_CONTEXT_MEMORY_SOURCES)
_RTL_SOURCES_context_sequencer := $(_CONTEXT_SEQUENCER_SOURCES)
_DATA_ALIGNER_SOURCES := $(PROJECT_ROOT)/src/rtl/common/dff.sv $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv $(PROJECT_ROOT)/src/rtl/basic/data_aligner.sv
_RTL_SOURCES_data_aligner := $(_DATA_ALIGNER_SOURCES)
_ECC_SOURCES := $(PROJECT_ROOT)/src/rtl/common/decoder.sv $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv $(PROJECT_ROOT)/src/rtl/basic/ecc.sv
_RTL_SOURCES_ecc := $(_ECC_SOURCES)
_FIFO_SOURCES := $(PROJECT_ROOT)/src/rtl/common/dff.sv $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv $(PROJECT_ROOT)/src/rtl/basic/fifo.sv
_RTL_SOURCES_fifo := $(_FIFO_SOURCES)
_PACKER_SOURCES := $(PROJECT_ROOT)/src/rtl/common/dff.sv $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv $(PROJECT_ROOT)/src/rtl/basic/packer.sv
_RTL_SOURCES_packer := $(_PACKER_SOURCES)
_PARITY_SOURCES := $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv $(PROJECT_ROOT)/src/rtl/basic/parity.sv
_RTL_SOURCES_parity := $(_PARITY_SOURCES)
_PERFORMANCE_COUNTERS_SOURCES := $(PROJECT_ROOT)/src/rtl/common/dff.sv $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv $(PROJECT_ROOT)/src/rtl/basic/performance_counters.sv
_RTL_SOURCES_performance_counters := $(_PERFORMANCE_COUNTERS_SOURCES)
_RDU_SOURCES := $(PROJECT_ROOT)/src/rtl/common/dff.sv $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv $(PROJECT_ROOT)/src/rtl/basic/rdu.sv
_RTL_SOURCES_rdu := $(_RDU_SOURCES)
_REGISTER_FILE_SOURCES := $(PROJECT_ROOT)/src/rtl/common/decoder.sv $(PROJECT_ROOT)/src/rtl/basic/register_file.sv
_RTL_SOURCES_register_file := $(_REGISTER_FILE_SOURCES)
_VECTOR_REGISTER_FILE_SOURCES := $(PROJECT_ROOT)/src/rtl/common/decoder.sv $(PROJECT_ROOT)/src/rtl/basic/register_file.sv $(PROJECT_ROOT)/src/rtl/basic/vector_register_file.sv
_RTL_SOURCES_vector_register_file := $(_VECTOR_REGISTER_FILE_SOURCES)
_REGISTER_SLICE_SOURCES := $(PROJECT_ROOT)/src/rtl/common/dff.sv $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv $(PROJECT_ROOT)/src/rtl/basic/register_slice.sv
_RTL_SOURCES_register_slice := $(_REGISTER_SLICE_SOURCES)
_ROUND_ROBIN_ARBITER_SOURCES := $(PROJECT_ROOT)/src/rtl/common/dff.sv $(PROJECT_ROOT)/src/rtl/common/priority_encoder.sv $(PROJECT_ROOT)/src/rtl/basic/round_robin_arbiter.sv
_RTL_SOURCES_round_robin_arbiter := $(_ROUND_ROBIN_ARBITER_SOURCES)
_SKID_BUFFER_SOURCES := $(PROJECT_ROOT)/src/rtl/common/dff.sv $(PROJECT_ROOT)/src/rtl/common/mux.sv $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv $(PROJECT_ROOT)/src/rtl/basic/skid_buffer.sv
_RTL_SOURCES_skid_buffer := $(_SKID_BUFFER_SOURCES)
_WIDTH_CONVERTER_SOURCES := $(PROJECT_ROOT)/src/rtl/common/dff.sv $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv $(PROJECT_ROOT)/src/rtl/basic/width_converter.sv
_RTL_SOURCES_width_converter := $(_WIDTH_CONVERTER_SOURCES)
_STREAM_FORK_SOURCES := $(PROJECT_ROOT)/src/rtl/common/dff.sv $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv $(PROJECT_ROOT)/src/rtl/basic/stream_fork.sv
_RTL_SOURCES_stream_fork := $(_STREAM_FORK_SOURCES)
_STREAM_JOIN_SOURCES := $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv $(PROJECT_ROOT)/src/rtl/basic/stream_join.sv
_RTL_SOURCES_stream_join := $(_STREAM_JOIN_SOURCES)
SRAM_BACKEND_SOURCE ?= $(PROJECT_ROOT)/src/rtl/basic/sram_wrapper_backend.sv
_SRAM_WRAPPER_SOURCES = $(PROJECT_ROOT)/src/rtl/common/dff.sv $(PROJECT_ROOT)/src/rtl/common/counter.sv $(PROJECT_ROOT)/src/rtl/common/decoder.sv $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv $(SRAM_BACKEND_SOURCE) $(PROJECT_ROOT)/src/rtl/basic/sram_wrapper.sv
_RTL_SOURCES_sram_wrapper = $(_SRAM_WRAPPER_SOURCES)
_SFT_SOURCES := $(PROJECT_ROOT)/src/rtl/mosaic_blocks/tile_shell_pkg.sv $(PROJECT_ROOT)/src/rtl/basic/context_sequencer_pkg.sv $(PROJECT_ROOT)/src/rtl/building_blocks/tile_power_controller_pkg.sv $(PROJECT_ROOT)/src/rtl/building_blocks/lut_unit_pkg.sv $(PROJECT_ROOT)/src/rtl/building_blocks/polynomial_unit_pkg.sv $(PROJECT_ROOT)/src/rtl/building_blocks/reciprocal_unit_pkg.sv $(PROJECT_ROOT)/src/rtl/building_blocks/scalar_alu_pkg.sv $(PROJECT_ROOT)/src/rtl/building_blocks/vector_lane_pkg.sv $(PROJECT_ROOT)/src/rtl/building_blocks/rsqrt_unit_pkg.sv $(PROJECT_ROOT)/src/rtl/building_blocks/generated/exp_unit_tables_pkg.sv $(PROJECT_ROOT)/src/rtl/building_blocks/exp_unit_pkg.sv $(PROJECT_ROOT)/src/rtl/building_blocks/vector_reduction_pkg.sv $(PROJECT_ROOT)/src/rtl/building_blocks/accumulator_pkg.sv $(PROJECT_ROOT)/src/rtl/mosaic_blocks/sft_pkg.sv $(PROJECT_ROOT)/src/rtl/common/dff.sv $(PROJECT_ROOT)/src/rtl/common/counter.sv $(PROJECT_ROOT)/src/rtl/common/decoder.sv $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv $(PROJECT_ROOT)/src/rtl/common/reset_synchronizer.sv $(PROJECT_ROOT)/src/rtl/basic/fifo.sv $(PROJECT_ROOT)/src/rtl/basic/parity.sv $(PROJECT_ROOT)/src/rtl/basic/ecc.sv $(PROJECT_ROOT)/src/rtl/basic/context_memory.sv $(PROJECT_ROOT)/src/rtl/basic/context_sequencer.sv $(PROJECT_ROOT)/src/rtl/basic/async_fifo.sv $(PROJECT_ROOT)/src/rtl/basic/performance_counters.sv $(PROJECT_ROOT)/src/rtl/building_blocks/event_barrier_state.sv $(PROJECT_ROOT)/src/rtl/building_blocks/event_barrier_queue.sv $(PROJECT_ROOT)/src/rtl/building_blocks/tile_power_controller.sv $(PROJECT_ROOT)/src/rtl/mosaic_blocks/tile_shell_codec.sv $(PROJECT_ROOT)/src/rtl/mosaic_blocks/tile_shell_state.sv $(PROJECT_ROOT)/src/rtl/mosaic_blocks/tile_shell_queue.sv $(PROJECT_ROOT)/src/rtl/mosaic_blocks/tile_shell.sv $(PROJECT_ROOT)/src/rtl/building_blocks/lut_unit_bank.sv $(PROJECT_ROOT)/src/rtl/building_blocks/lut_unit.sv $(PROJECT_ROOT)/src/rtl/common/mux.sv $(PROJECT_ROOT)/src/rtl/building_blocks/multiplier.sv $(PROJECT_ROOT)/src/rtl/building_blocks/polynomial_unit_round.sv $(PROJECT_ROOT)/src/rtl/building_blocks/polynomial_unit_horner.sv $(PROJECT_ROOT)/src/rtl/building_blocks/polynomial_unit_scale.sv $(PROJECT_ROOT)/src/rtl/building_blocks/polynomial_unit.sv $(PROJECT_ROOT)/src/rtl/common/priority_encoder.sv $(PROJECT_ROOT)/src/rtl/building_blocks/scalar_alu.sv $(PROJECT_ROOT)/src/rtl/building_blocks/reciprocal_unit_normalize.sv $(PROJECT_ROOT)/src/rtl/building_blocks/protected_seed_rom.sv $(PROJECT_ROOT)/src/rtl/building_blocks/reciprocal_unit_seed.sv $(PROJECT_ROOT)/src/rtl/building_blocks/reciprocal_unit_newton.sv $(PROJECT_ROOT)/src/rtl/building_blocks/reciprocal_unit_scale.sv $(PROJECT_ROOT)/src/rtl/building_blocks/reciprocal_unit.sv $(PROJECT_ROOT)/src/rtl/building_blocks/rsqrt_unit_normalize.sv $(PROJECT_ROOT)/src/rtl/building_blocks/rsqrt_unit_seed.sv $(PROJECT_ROOT)/src/rtl/building_blocks/rsqrt_unit_newton.sv $(PROJECT_ROOT)/src/rtl/building_blocks/rsqrt_unit.sv $(PROJECT_ROOT)/src/rtl/building_blocks/exp_unit_interpolate.sv $(PROJECT_ROOT)/src/rtl/building_blocks/exp_unit_rom.sv $(PROJECT_ROOT)/src/rtl/building_blocks/exp_unit_stage.sv $(PROJECT_ROOT)/src/rtl/building_blocks/exp_unit.sv $(PROJECT_ROOT)/src/rtl/common/lane_mask.sv $(PROJECT_ROOT)/src/rtl/basic/register_file.sv $(PROJECT_ROOT)/src/rtl/basic/bypass_network.sv $(PROJECT_ROOT)/src/rtl/basic/stream_join.sv $(PROJECT_ROOT)/src/rtl/basic/packer.sv $(PROJECT_ROOT)/src/rtl/building_blocks/accumulator.sv $(PROJECT_ROOT)/src/rtl/building_blocks/vector_reduction_tree.sv $(PROJECT_ROOT)/src/rtl/building_blocks/vector_reduction.sv $(PROJECT_ROOT)/src/rtl/common/write_gate.sv $(PROJECT_ROOT)/src/rtl/building_blocks/vector_lane_pipeline.sv $(PROJECT_ROOT)/src/rtl/mosaic_blocks/sft_datapath.sv $(PROJECT_ROOT)/src/rtl/mosaic_blocks/sft_body.sv $(PROJECT_ROOT)/src/rtl/mosaic_blocks/sft.sv
_RTL_SOURCES_sft := $(_SFT_SOURCES)
_CPT_SOURCES := $(PROJECT_ROOT)/src/rtl/mosaic_blocks/tile_shell_pkg.sv $(PROJECT_ROOT)/src/rtl/basic/context_sequencer_pkg.sv $(PROJECT_ROOT)/src/rtl/building_blocks/tile_power_controller_pkg.sv $(PROJECT_ROOT)/src/rtl/building_blocks/predicate_unit_pkg.sv $(PROJECT_ROOT)/src/rtl/building_blocks/scalar_alu_pkg.sv $(PROJECT_ROOT)/src/rtl/building_blocks/event_barrier_pkg.sv $(PROJECT_ROOT)/src/rtl/building_blocks/loop_controller_pkg.sv $(PROJECT_ROOT)/src/rtl/mosaic_blocks/cpt_pkg.sv $(PROJECT_ROOT)/src/rtl/common/dff.sv $(PROJECT_ROOT)/src/rtl/common/counter.sv $(PROJECT_ROOT)/src/rtl/common/decoder.sv $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv $(PROJECT_ROOT)/src/rtl/common/reset_synchronizer.sv $(PROJECT_ROOT)/src/rtl/common/priority_encoder.sv $(PROJECT_ROOT)/src/rtl/common/write_gate.sv $(PROJECT_ROOT)/src/rtl/common/lane_mask.sv $(PROJECT_ROOT)/src/rtl/common/mux.sv $(PROJECT_ROOT)/src/rtl/basic/fifo.sv $(PROJECT_ROOT)/src/rtl/basic/parity.sv $(PROJECT_ROOT)/src/rtl/basic/ecc.sv $(PROJECT_ROOT)/src/rtl/basic/context_memory.sv $(PROJECT_ROOT)/src/rtl/basic/context_sequencer.sv $(PROJECT_ROOT)/src/rtl/basic/async_fifo.sv $(PROJECT_ROOT)/src/rtl/basic/performance_counters.sv $(PROJECT_ROOT)/src/rtl/basic/register_file.sv $(PROJECT_ROOT)/src/rtl/basic/packer.sv $(PROJECT_ROOT)/src/rtl/basic/stream_join.sv $(PROJECT_ROOT)/src/rtl/basic/round_robin_arbiter.sv $(PROJECT_ROOT)/src/rtl/building_blocks/event_barrier_state.sv $(PROJECT_ROOT)/src/rtl/building_blocks/event_barrier_queue.sv $(PROJECT_ROOT)/src/rtl/building_blocks/event_barrier.sv $(PROJECT_ROOT)/src/rtl/building_blocks/loop_controller.sv $(PROJECT_ROOT)/src/rtl/building_blocks/tile_power_controller.sv $(PROJECT_ROOT)/src/rtl/mosaic_blocks/tile_shell_codec.sv $(PROJECT_ROOT)/src/rtl/mosaic_blocks/tile_shell_state.sv $(PROJECT_ROOT)/src/rtl/mosaic_blocks/tile_shell_queue.sv $(PROJECT_ROOT)/src/rtl/mosaic_blocks/tile_shell.sv $(PROJECT_ROOT)/src/rtl/building_blocks/predicate_unit.sv $(PROJECT_ROOT)/src/rtl/building_blocks/scalar_alu.sv $(PROJECT_ROOT)/src/rtl/mosaic_blocks/cpt_actions.sv $(PROJECT_ROOT)/src/rtl/mosaic_blocks/cpt_egress.sv $(PROJECT_ROOT)/src/rtl/mosaic_blocks/cpt_body.sv $(PROJECT_ROOT)/src/rtl/mosaic_blocks/cpt.sv
_RTL_SOURCES_cpt := $(_CPT_SOURCES)
_RTL_SOURCES_cluster = $(addprefix $(PROJECT_ROOT)/,$(file <$(PROJECT_ROOT)/src/gen/cluster/generated/sources.f))
_GLOBAL_NOC_SOURCES := $(PROJECT_ROOT)/src/rtl/building_blocks/noc_router_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/tile_network_interface_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/global_noc_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/common/dff.sv \
    $(PROJECT_ROOT)/src/rtl/common/counter.sv \
    $(PROJECT_ROOT)/src/rtl/common/decoder.sv \
    $(PROJECT_ROOT)/src/rtl/common/mux.sv \
    $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv \
    $(PROJECT_ROOT)/src/rtl/common/priority_encoder.sv \
    $(PROJECT_ROOT)/src/rtl/basic/fifo.sv \
    $(PROJECT_ROOT)/src/rtl/basic/parity.sv \
    $(PROJECT_ROOT)/src/rtl/basic/ecc.sv \
    $(PROJECT_ROOT)/src/rtl/basic/round_robin_arbiter.sv \
    $(PROJECT_ROOT)/src/rtl/basic/skid_buffer.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/event_barrier_state.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/event_barrier_queue.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/noc_router_codec.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/noc_router_buffer.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/noc_router.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/tile_network_interface.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/global_noc_link.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/global_noc.sv
_RTL_SOURCES_global_noc := $(_GLOBAL_NOC_SOURCES)
_RUNTIME_CONTROLLER_SOURCES :=     $(PROJECT_ROOT)/src/rtl/mosaic_blocks/runtime_controller_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/common/dff.sv \
    $(PROJECT_ROOT)/src/rtl/common/counter.sv \
    $(PROJECT_ROOT)/src/rtl/common/priority_encoder.sv \
    $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv \
    $(PROJECT_ROOT)/src/rtl/common/decoder.sv \
    $(PROJECT_ROOT)/src/rtl/basic/fifo.sv \
    $(PROJECT_ROOT)/src/rtl/basic/parity.sv \
    $(PROJECT_ROOT)/src/rtl/basic/ecc.sv \
    $(PROJECT_ROOT)/src/rtl/basic/round_robin_arbiter.sv \
    $(PROJECT_ROOT)/src/rtl/basic/performance_counters.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/event_barrier_state.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/event_barrier_queue.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/tile_shell_codec.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/tile_shell_state.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/runtime_controller.sv
_RTL_SOURCES_runtime_controller := $(_RUNTIME_CONTROLLER_SOURCES)

_CLUSTER_POWER_MANAGER_SOURCES := \
    $(PROJECT_ROOT)/src/rtl/building_blocks/tile_power_controller_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/cluster_power_manager_pkg.sv \
    $(PROJECT_ROOT)/src/rtl/common/dff.sv \
    $(PROJECT_ROOT)/src/rtl/common/counter.sv \
    $(PROJECT_ROOT)/src/rtl/common/clock_gate.sv \
    $(PROJECT_ROOT)/src/rtl/common/reset_synchronizer.sv \
    $(PROJECT_ROOT)/src/rtl/common/isolation_cell.sv \
    $(PROJECT_ROOT)/src/rtl/common/decoder.sv \
    $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv \
    $(PROJECT_ROOT)/src/rtl/basic/fifo.sv \
    $(PROJECT_ROOT)/src/rtl/basic/parity.sv \
    $(PROJECT_ROOT)/src/rtl/basic/ecc.sv \
    $(PROJECT_ROOT)/src/rtl/basic/performance_counters.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/event_barrier_state.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/event_barrier_queue.sv \
    $(PROJECT_ROOT)/src/rtl/building_blocks/tile_power_controller.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/tile_shell_codec.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/tile_shell_state.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/cluster_power_manager_sync.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/cluster_power_manager_tiles.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/cluster_power_manager_events.sv \
    $(PROJECT_ROOT)/src/rtl/mosaic_blocks/cluster_power_manager.sv
_RTL_SOURCES_cluster_power_manager := $(_CLUSTER_POWER_MANAGER_SOURCES)

VERILOG_SOURCES ?= $(or $(_RTL_SOURCES_$(COCOTB_TOPLEVEL)),$(firstword $(wildcard $(PROJECT_ROOT)/src/rtl/*/$(COCOTB_TOPLEVEL).sv)),$(PROJECT_ROOT)/src/rtl/common/$(COCOTB_TOPLEVEL).sv)
SIM_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/$(COCOTB_TOPLEVEL)
COCOTB_RESULTS_FILE ?= $(SIM_BUILD)/results.xml
SAIF_FILE ?= $(SIM_BUILD)/$(COCOTB_TOPLEVEL).saif
SAIF_SCOPE ?= $(COCOTB_TOPLEVEL)
SAIF_TIME_UNIT ?= 1e-9
SAIF_SCRIPT := $(PROJECT_ROOT)/flows/vcs/saif.tcl

DC_SHELL ?= dc_shell
DC_ARGS ?=
TECH_SETUP_TCL ?=
DC_SETUP_TCL ?=
SYNTH_SCRIPT := $(PROJECT_ROOT)/flows/synth/run.tcl
SYNTH_CONSTRAINTS ?= $(PROJECT_ROOT)/src/constraints/timing.sdc
SYNTH_BUILD ?= $(PROJECT_ROOT)/build/synth/$(COCOTB_TOPLEVEL)
SYNTH_CLOCK_PORT ?= i_clk
SYNTH_CLOCK_PERIOD ?= 4.0
SYNTH_CPUS ?= 4
SYNTH_PARAMETERS ?=
SYNTH_COMPILE_ARGS ?=
SYNTH_NETLIST := $(SYNTH_BUILD)/netlist/$(COCOTB_TOPLEVEL)_syn.v
SYNTH_SDF := $(SYNTH_BUILD)/netlist/$(COCOTB_TOPLEVEL).sdf

NETLIST_FILE ?= $(SYNTH_NETLIST)
CELL_MODELS ?=
SDF_FILE ?=
SDF_SCOPE ?= $(COCOTB_TOPLEVEL)
SDF_CORNER ?= max
GATE_SIM_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/$(COCOTB_TOPLEVEL)/gate/$(if $(strip $(SDF_FILE)),timing,functional)
GATE_RESULTS_FILE ?= $(GATE_SIM_BUILD)/results.xml
GATE_SAIF_FILE ?= $(GATE_SIM_BUILD)/$(COCOTB_TOPLEVEL).saif
GATE_SETTLE_NS ?= 1
POWER_SHELL ?= pt_shell
POWER_ARGS ?=
POWER_TECH_SETUP_TCL ?= $(TECH_SETUP_TCL)
POWER_TOOL_SETUP_TCL ?=
POWER_SCRIPT := $(PROJECT_ROOT)/flows/power/run.tcl
POWER_SUMMARY_SCRIPT := $(PROJECT_ROOT)/flows/power/summarize.py
POWER_BUILD ?= $(PROJECT_ROOT)/build/power/$(COCOTB_TOPLEVEL)/$(if $(strip $(SDF_FILE)),timing,functional)
POWER_SDC_FILE ?= $(SYNTH_BUILD)/netlist/$(COCOTB_TOPLEVEL).sdc
SPEF_FILE ?=
POWER_SAIF_FILE ?= $(GATE_SAIF_FILE)
POWER_SAIF_STRIP_PATH ?= $(subst .,/,$(SAIF_SCOPE))
POWER_REPORT := $(abspath $(POWER_BUILD))/reports/power.rpt
POWER_ACTIVITY_REPORT := $(abspath $(POWER_BUILD))/reports/activity.rpt
POWER_SUMMARY := $(abspath $(POWER_BUILD))/summary.json
export TEST_CLOCK_PERIOD_NS ?= $(SYNTH_CLOCK_PERIOD)
export TEST_SETTLE_NS ?= 0
ACCUMULATOR_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/accumulator/regression
ACCUMULATOR_RANDOM_CYCLES ?= 2000
ACCUMULATOR_SEED ?= 20261020
export ACCUMULATOR_HDL_ASSERTIONS ?= 1
_ACCUMULATOR_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_ACCUMULATOR_MAKE := $(MAKE)
PREDICATE_UNIT_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/predicate_unit/regression
PREDICATE_UNIT_STATIC_BUILD ?= $(PROJECT_ROOT)/build/static/predicate_unit
PREDICATE_UNIT_FORMAL_BUILD ?= $(PROJECT_ROOT)/build/formal/predicate_unit
PREDICATE_UNIT_YOSYS ?= yosys
PREDICATE_UNIT_VERILATOR ?= verilator
PREDICATE_UNIT_RANDOM_CYCLES ?= 2000
PREDICATE_UNIT_SEED ?= 20261022
export PREDICATE_UNIT_HDL_ASSERTIONS ?= 1
_PREDICATE_UNIT_MAKE := $(MAKE)
_PREDICATE_UNIT_SIM_BIN_DIR := $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
VECTOR_REDUCTION_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/vector_reduction/regression
VECTOR_REDUCTION_STATIC_BUILD ?= $(PROJECT_ROOT)/build/static/vector_reduction
VECTOR_REDUCTION_FORMAL_BUILD ?= $(PROJECT_ROOT)/build/formal/vector_reduction
VECTOR_REDUCTION_YOSYS ?= yosys
VECTOR_REDUCTION_VERILATOR ?= verilator
VECTOR_REDUCTION_RANDOM_CYCLES ?= 2000
VECTOR_REDUCTION_SEED ?= 20261022
export VECTOR_REDUCTION_HDL_ASSERTIONS ?= 1
_VECTOR_REDUCTION_MAKE := $(MAKE)
_VECTOR_REDUCTION_SIM_BIN_DIR := $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
VECTOR_LANE_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/vector_lane/regression
VECTOR_LANE_STATIC_BUILD ?= $(PROJECT_ROOT)/build/static/vector_lane
VECTOR_LANE_FORMAL_BUILD ?= $(PROJECT_ROOT)/build/formal/vector_lane
VECTOR_LANE_YOSYS ?= yosys
VECTOR_LANE_VERILATOR ?= verilator
VECTOR_LANE_RANDOM_CYCLES ?= 2000
VECTOR_LANE_SEED ?= 20261022
export VECTOR_LANE_HDL_ASSERTIONS ?= 1
_VECTOR_LANE_MAKE := $(MAKE)
_VECTOR_LANE_SIM_BIN_DIR := $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
SCALAR_ALU_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/scalar_alu/regression
SCALAR_ALU_STATIC_BUILD ?= $(PROJECT_ROOT)/build/static/scalar_alu
SCALAR_ALU_VERILATOR ?= verilator
SCALAR_ALU_FORMAL_BUILD ?= $(PROJECT_ROOT)/build/formal/scalar_alu
SCALAR_ALU_YOSYS ?= yosys
SCALAR_ALU_SEED ?= 20261022
SCALAR_ALU_RANDOM_CYCLES ?= 2000
export SCALAR_ALU_HDL_ASSERTIONS ?= 1
_SCALAR_ALU_MAKE := $(MAKE)
_SCALAR_ALU_SIM_BIN_DIR := $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
NOC_ROUTER_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/noc_router/regression
NOC_ROUTER_MESH_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/noc_router/mesh
NOC_ROUTER_TOPOLOGY_BUILD ?= $(PROJECT_ROOT)/build/noc_router/topology
NOC_ROUTER_SEED ?= 20261022
NOC_ROUTER_RANDOM_CYCLES ?= 2000
export NOC_ROUTER_HDL_ASSERTIONS ?= 1
_NOC_ROUTER_MAKE := $(MAKE)
_NOC_ROUTER_SIM_BIN_DIR := $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
MULTIPLIER_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/multiplier/regression
MULTIPLIER_SEED ?= 20261022
MULTIPLIER_RANDOM_CYCLES ?= 2000
export MULTIPLIER_HDL_ASSERTIONS ?= 1
_MULTIPLIER_MAKE := $(MAKE)
_MULTIPLIER_SIM_BIN_DIR := $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))

MAC_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/mac/regression
MAC_SEED ?= 20261022
MAC_RANDOM_CYCLES ?= 2000
export MAC_HDL_ASSERTIONS ?= 1
_MAC_MAKE := $(MAKE)
_MAC_SIM_BIN_DIR := $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))

LUT_UNIT_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/lut_unit/regression
LUT_UNIT_SEED ?= 20261022
LUT_UNIT_RANDOM_CYCLES ?= 2000
_LUT_UNIT_MAKE := $(MAKE)
_LUT_UNIT_SIM_BIN_DIR := $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
RSQRT_UNIT_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/rsqrt_unit/regression
RSQRT_UNIT_SEED ?= 20261025
RSQRT_UNIT_RANDOM_CYCLES ?= 2000
_RSQRT_UNIT_MAKE := $(MAKE)
_RSQRT_UNIT_SIM_BIN_DIR := $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
RECIPROCAL_UNIT_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/reciprocal_unit/regression
RECIPROCAL_UNIT_SEED ?= 20261024
RECIPROCAL_UNIT_RANDOM_CYCLES ?= 2000
_RECIPROCAL_UNIT_MAKE := $(MAKE)
_RECIPROCAL_UNIT_SIM_BIN_DIR := $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
POLYNOMIAL_UNIT_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/polynomial_unit/regression
POLYNOMIAL_UNIT_SEED ?= 20261023
POLYNOMIAL_UNIT_RANDOM_CYCLES ?= 2000
_POLYNOMIAL_UNIT_MAKE := $(MAKE)
_POLYNOMIAL_UNIT_SIM_BIN_DIR := $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
LOOP_CONTROLLER_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/loop_controller/regression
LOOP_CONTROLLER_SEED ?= 20261022
LOOP_CONTROLLER_RANDOM_CYCLES ?= 2000
export LOOP_CONTROLLER_HDL_ASSERTIONS ?= 0
_LOOP_CONTROLLER_MAKE := $(MAKE)
_LOOP_CONTROLLER_SIM_BIN_DIR := $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
TILE_POWER_CONTROLLER_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/tile_power_controller/regression
TILE_POWER_CONTROLLER_RANDOM_CYCLES ?= 2000
TILE_POWER_CONTROLLER_SEED ?= 20261023
_TILE_POWER_CONTROLLER_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_TILE_POWER_CONTROLLER_MAKE := $(MAKE)
TILE_NETWORK_INTERFACE_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/tile_network_interface/regression
TILE_NETWORK_INTERFACE_RANDOM_CYCLES ?= 2000
TILE_NETWORK_INTERFACE_SEED ?= 20261023
_TILE_NETWORK_INTERFACE_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_TILE_NETWORK_INTERFACE_MAKE := $(MAKE)
LOCAL_SWITCH_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/local_switch/regression
LOCAL_SWITCH_RANDOM_CYCLES ?= 2000
LOCAL_SWITCH_SEED ?= 20261021
export LOCAL_SWITCH_HDL_ASSERTIONS ?= 0
_LOCAL_SWITCH_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_LOCAL_SWITCH_MAKE := $(MAKE)
SCRATCHPAD_CONTROLLER_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/scratchpad_controller/regression
SCRATCHPAD_CONTROLLER_SEED ?= 20261023
SCRATCHPAD_CONTROLLER_RANDOM_CYCLES ?= 2000
_SCRATCHPAD_CONTROLLER_MAKE := $(if $(filter default,$(origin MAKE)),make,$(MAKE))
_SCRATCHPAD_CONTROLLER_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
export SCRATCHPAD_CONTROLLER_RANDOM_CYCLES SCRATCHPAD_CONTROLLER_SEED
SCRATCHPAD_BANK_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/scratchpad_bank/regression
SCRATCHPAD_BANK_RANDOM_CYCLES ?= 2000
SCRATCHPAD_BANK_SEED ?= 20261023
export SCRATCHPAD_BANK_INSTRUMENTATION ?= 1
_SCRATCHPAD_BANK_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_SCRATCHPAD_BANK_MAKE := $(MAKE)
STREAM_FORMATTER_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/stream_formatter/regression
STREAM_FORMATTER_RANDOM_CYCLES ?= 2000
STREAM_FORMATTER_SEED ?= 20261022
_STREAM_FORMATTER_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_STREAM_FORMATTER_MAKE := $(MAKE)
STORE_ENGINE_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/store_engine/regression
STORE_ENGINE_RANDOM_CYCLES ?= 2000
STORE_ENGINE_SEED ?= 20261022
export STORE_ENGINE_HDL_ASSERTIONS ?= 1
_STORE_ENGINE_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_STORE_ENGINE_MAKE := $(MAKE)
LOAD_ENGINE_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/load_engine/regression
LOAD_ENGINE_RANDOM_CYCLES ?= 2000
LOAD_ENGINE_SEED ?= 20261021
export LOAD_ENGINE_HDL_ASSERTIONS ?= 1
_LOAD_ENGINE_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_LOAD_ENGINE_MAKE := $(MAKE)
EXP_UNIT_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/exp_unit/regression
EXP_UNIT_RANDOM_CYCLES ?= 2000
EXP_UNIT_SEED ?= 20261021
export EXP_UNIT_HDL_ASSERTIONS ?= 0
_EXP_UNIT_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_EXP_UNIT_MAKE := $(MAKE)
EVENT_BARRIER_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/event_barrier/regression
EVENT_BARRIER_RANDOM_CYCLES ?= 2000
EVENT_BARRIER_SEED ?= 20261021
export EVENT_BARRIER_HDL_ASSERTIONS ?= 1
_EVENT_BARRIER_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_EVENT_BARRIER_MAKE := $(MAKE)
DOT_PRODUCT_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/dot_product/regression
DOT_PRODUCT_RANDOM_CYCLES ?= 2000
DOT_PRODUCT_SEED ?= 20261020
export DOT_PRODUCT_HDL_ASSERTIONS ?= 1
_DOT_PRODUCT_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_DOT_PRODUCT_MAKE := $(MAKE)
AGU_LINT_BUILD ?= $(PROJECT_ROOT)/build/lint/agu
AGU_VERILATOR ?= verilator
AGU_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/agu/regression
AGU_RANDOM_CYCLES ?= 2000
AGU_SEED ?= 20261020
export AGU_HDL_ASSERTIONS ?= 1
_AGU_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_AGU_MAKE := $(MAKE)
DMA_ENGINE_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/dma_engine/regression
DMA_ENGINE_RANDOM_CYCLES ?= 2000
DMA_ENGINE_SEED ?= 20261020
export DMA_ENGINE_HDL_ASSERTIONS ?= 0
_DMA_ENGINE_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_DMA_ENGINE_MAKE := $(MAKE)
COUNTER_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/counter/regression
COUNTER_RANDOM_CYCLES ?= 2000
COUNTER_SEED ?= 20261010
_COUNTER_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
# GNU make treats a direct MAKE reference as recursive, even inside a Python
# command. Indirection keeps -n from running the wrapper and deleting reports.
_COUNTER_MAKE := $(MAKE)
CLOCK_GATE_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/clock_gate/regression
CLOCK_GATE_RANDOM_CYCLES ?= 2000
CLOCK_GATE_SEED ?= 20261010
_CLOCK_GATE_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_CLOCK_GATE_MAKE := $(MAKE)
DECODER_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/decoder/regression
DECODER_RANDOM_CYCLES ?= 2000
DECODER_SEED ?= 20261010
_DECODER_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_DECODER_MAKE := $(MAKE)
DFF_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/dff/regression
DFF_RANDOM_CYCLES ?= 2000
DFF_SEED ?= 20261010
_DFF_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_DFF_MAKE := $(MAKE)
ISOLATION_CELL_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/isolation_cell/regression
ISOLATION_CELL_RANDOM_CYCLES ?= 2000
ISOLATION_CELL_SEED ?= 20261011
_ISOLATION_CELL_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_ISOLATION_CELL_MAKE := $(MAKE)
LANE_MASK_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/lane_mask/regression
LANE_MASK_RANDOM_CYCLES ?= 2000
LANE_MASK_SEED ?= 20261011
_LANE_MASK_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_LANE_MASK_MAKE := $(MAKE)
LEVEL_SHIFTER_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/level_shifter/regression
LEVEL_SHIFTER_RANDOM_CYCLES ?= 2000
LEVEL_SHIFTER_SEED ?= 20261011
_LEVEL_SHIFTER_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_LEVEL_SHIFTER_MAKE := $(MAKE)
MUX_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/mux/regression
MUX_RANDOM_CYCLES ?= 2000
MUX_SEED ?= 20261011
_MUX_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_MUX_MAKE := $(MAKE)
OPERAND_ISOLATION_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/operand_isolation/regression
OPERAND_ISOLATION_RANDOM_CYCLES ?= 2000
OPERAND_ISOLATION_SEED ?= 20261011
_OPERAND_ISOLATION_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_OPERAND_ISOLATION_MAKE := $(MAKE)
PRIORITY_ENCODER_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/priority_encoder/regression
PRIORITY_ENCODER_RANDOM_CYCLES ?= 2000
PRIORITY_ENCODER_SEED ?= 20261011
_PRIORITY_ENCODER_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_PRIORITY_ENCODER_MAKE := $(MAKE)
RESET_SYNCHRONIZER_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/reset_synchronizer/regression
RESET_SYNCHRONIZER_RANDOM_CYCLES ?= 2000
RESET_SYNCHRONIZER_SEED ?= 20261011
_RESET_SYNCHRONIZER_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_RESET_SYNCHRONIZER_MAKE := $(MAKE)
RETENTION_REGISTER_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/retention_register/regression
RETENTION_REGISTER_RANDOM_CYCLES ?= 2000
RETENTION_REGISTER_SEED ?= 20261011
_RETENTION_REGISTER_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_RETENTION_REGISTER_MAKE := $(MAKE)
WRITE_GATE_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/write_gate/regression
WRITE_GATE_RANDOM_CYCLES ?= 2000
WRITE_GATE_SEED ?= 20261011
_WRITE_GATE_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_WRITE_GATE_MAKE := $(MAKE)
ASYNC_FIFO_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/async_fifo/regression
ASYNC_FIFO_RANDOM_CYCLES ?= 2000
ASYNC_FIFO_SEED ?= 20261012
_ASYNC_FIFO_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_ASYNC_FIFO_MAKE := $(MAKE)
BYPASS_NETWORK_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/bypass_network/regression
BYPASS_NETWORK_RANDOM_CYCLES ?= 2000
BYPASS_NETWORK_SEED ?= 20261012
_BYPASS_NETWORK_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_BYPASS_NETWORK_MAKE := $(MAKE)
CONTEXT_MEMORY_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/context_memory/regression
CONTEXT_MEMORY_RANDOM_CYCLES ?= 2000
CONTEXT_MEMORY_SEED ?= 20261012
_CONTEXT_MEMORY_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_CONTEXT_MEMORY_MAKE := $(MAKE)
CONTEXT_SEQUENCER_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/context_sequencer/regression
CONTEXT_SEQUENCER_RANDOM_CYCLES ?= 2000
CONTEXT_SEQUENCER_SEED ?= 20261012
_CONTEXT_SEQUENCER_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_CONTEXT_SEQUENCER_MAKE := $(MAKE)
DATA_ALIGNER_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/data_aligner/regression
DATA_ALIGNER_RANDOM_CYCLES ?= 2000
DATA_ALIGNER_SEED ?= 20261013
_DATA_ALIGNER_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_DATA_ALIGNER_MAKE := $(MAKE)
ECC_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/ecc/regression
ECC_RANDOM_CYCLES ?= 2000
ECC_SEED ?= 20261013
_ECC_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_ECC_MAKE := $(MAKE)
FIFO_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/fifo/regression
FIFO_RANDOM_CYCLES ?= 2000
FIFO_SEED ?= 20261013
_FIFO_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_FIFO_MAKE := $(MAKE)
PACKER_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/packer/regression
PACKER_RANDOM_CYCLES ?= 2000
PACKER_SEED ?= 20261013
_PACKER_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_PACKER_MAKE := $(MAKE)
PARITY_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/parity/regression
PARITY_RANDOM_CYCLES ?= 2000
PARITY_SEED ?= 20261013
_PARITY_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_PARITY_MAKE := $(MAKE)
PERFORMANCE_COUNTERS_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/performance_counters/regression
PERFORMANCE_COUNTERS_RANDOM_CYCLES ?= 2000
PERFORMANCE_COUNTERS_SEED ?= 20261013
_PERFORMANCE_COUNTERS_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_PERFORMANCE_COUNTERS_MAKE := $(MAKE)
RDU_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/rdu/regression
RDU_RANDOM_CYCLES ?= 2000
RDU_SEED ?= 20261019
_RDU_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_RDU_MAKE := $(MAKE)
VECTOR_REGISTER_FILE_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/vector_register_file/regression
VECTOR_REGISTER_FILE_RANDOM_CYCLES ?= 2000
VECTOR_REGISTER_FILE_SEED ?= 20261020
_VECTOR_REGISTER_FILE_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_VECTOR_REGISTER_FILE_MAKE := $(MAKE)
REGISTER_FILE_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/register_file/regression
REGISTER_FILE_RANDOM_CYCLES ?= 2000
REGISTER_FILE_SEED ?= 20261019
_REGISTER_FILE_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_REGISTER_FILE_MAKE := $(MAKE)
REGISTER_SLICE_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/register_slice/regression
REGISTER_SLICE_RANDOM_CYCLES ?= 2000
REGISTER_SLICE_SEED ?= 20261019
_REGISTER_SLICE_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_REGISTER_SLICE_MAKE := $(MAKE)
ROUND_ROBIN_ARBITER_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/round_robin_arbiter/regression
ROUND_ROBIN_ARBITER_RANDOM_CYCLES ?= 2000
ROUND_ROBIN_ARBITER_SEED ?= 20261019
_ROUND_ROBIN_ARBITER_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_ROUND_ROBIN_ARBITER_MAKE := $(MAKE)
SKID_BUFFER_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/skid_buffer/regression
SKID_BUFFER_RANDOM_CYCLES ?= 2000
SKID_BUFFER_SEED ?= 20261019
_SKID_BUFFER_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_SKID_BUFFER_MAKE := $(MAKE)
STREAM_JOIN_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/stream_join/regression
STREAM_JOIN_RANDOM_CYCLES ?= 2000
STREAM_JOIN_SEED ?= 20261020
_STREAM_JOIN_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_STREAM_JOIN_MAKE := $(MAKE)
WIDTH_CONVERTER_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/width_converter/regression
WIDTH_CONVERTER_RANDOM_CYCLES ?= 2000
WIDTH_CONVERTER_SEED ?= 20261020
_WIDTH_CONVERTER_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_WIDTH_CONVERTER_MAKE := $(MAKE)
STREAM_FORK_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/stream_fork/regression
STREAM_FORK_RANDOM_CYCLES ?= 2000
STREAM_FORK_SEED ?= 20261020
_STREAM_FORK_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_STREAM_FORK_MAKE := $(MAKE)
SRAM_WRAPPER_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/sram_wrapper/regression
SRAM_WRAPPER_RANDOM_CYCLES ?= 2000
SRAM_WRAPPER_SEED ?= 20261019
_SRAM_WRAPPER_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_SRAM_WRAPPER_MAKE := $(MAKE)

# Component imports use suite packages; shared infrastructure lives under lib.
export PYTHONPATH := $(PYUVM_TEST_DIR):$(patsubst %/,%,$(dir $(PYUVM_TEST_DIR))):$(PROJECT_ROOT)/src/val/lib$(if $(PYTHONPATH),:$(PYTHONPATH))
CUSTOM_COMPILE_DEPS += $(PROJECT_ROOT)/Makefile

# Load cocotb only in the simulation subprocess so setup/help/clean work
# before the Python environment or licensed simulator has been installed.
ifeq ($(_COCOTB_RUN),1)
# Treat caller options as a starting value so cocotb can append mandatory
# backend flags even when COMPILE_ARGS was supplied on the command line.
_USER_COMPILE_ARGS := $(COMPILE_ARGS)
override undefine COMPILE_ARGS
COMPILE_ARGS := $(_USER_COMPILE_ARGS)
# Native RTL checkers sample after a precision-tick observation delay; some
# suites also check private state. Exclude them from synthesis and gate sources.
ifeq ($(COCOTB_TOPLEVEL),predicate_unit)
ifneq ($(_GATE_RUN),1)
ifeq ($(PREDICATE_UNIT_HDL_ASSERTIONS),1)
override VERILOG_SOURCES += $(PREDICATE_UNIT_TEST_DIR)/predicate_unit_reference.sv \
    $(PREDICATE_UNIT_TEST_DIR)/predicate_unit_assertions.sv
COMPILE_ARGS += $(if $(filter vcs,$(SIM)),+define+MOSAIC_PREDICATE_UNIT_ASSERTIONS,-DMOSAIC_PREDICATE_UNIT_ASSERTIONS)
endif
endif
endif
ifeq ($(COCOTB_TOPLEVEL),vector_reduction)
ifneq ($(_GATE_RUN),1)
ifeq ($(VECTOR_REDUCTION_HDL_ASSERTIONS),1)
override VERILOG_SOURCES += $(VECTOR_REDUCTION_TEST_DIR)/vector_reduction_reference.sv \
    $(VECTOR_REDUCTION_TEST_DIR)/vector_reduction_assertions.sv
COMPILE_ARGS += $(if $(filter vcs,$(SIM)),+define+MOSAIC_VECTOR_REDUCTION_ASSERTIONS,-DMOSAIC_VECTOR_REDUCTION_ASSERTIONS)
endif
endif
endif
ifeq ($(COCOTB_TOPLEVEL),vector_lane)
ifneq ($(_GATE_RUN),1)
ifeq ($(VECTOR_LANE_HDL_ASSERTIONS),1)
override VERILOG_SOURCES += $(VECTOR_LANE_TEST_DIR)/vector_lane_reference.sv \
    $(VECTOR_LANE_TEST_DIR)/vector_lane_assertions.sv
COMPILE_ARGS += $(if $(filter vcs,$(SIM)),+define+MOSAIC_VECTOR_LANE_ASSERTIONS,-DMOSAIC_VECTOR_LANE_ASSERTIONS)
endif
endif
endif
ifeq ($(COCOTB_TOPLEVEL),scalar_alu)
ifneq ($(_GATE_RUN),1)
ifeq ($(SCALAR_ALU_HDL_ASSERTIONS),1)
override VERILOG_SOURCES += $(SCALAR_ALU_TEST_DIR)/scalar_alu_assertions.sv
COMPILE_ARGS += $(if $(filter vcs,$(SIM)),+define+MOSAIC_SCALAR_ALU_ASSERTIONS,-DMOSAIC_SCALAR_ALU_ASSERTIONS)
endif
endif
endif
ifeq ($(COCOTB_TOPLEVEL),noc_router)
ifneq ($(_GATE_RUN),1)
ifeq ($(NOC_ROUTER_HDL_ASSERTIONS),1)
override VERILOG_SOURCES += $(NOC_ROUTER_TEST_DIR)/noc_router_assertions.sv
COMPILE_ARGS += $(if $(filter vcs,$(SIM)),+define+MOSAIC_NOC_ROUTER_ASSERTIONS,-DMOSAIC_NOC_ROUTER_ASSERTIONS)
endif
endif
endif
ifeq ($(COCOTB_TOPLEVEL),multiplier)
ifneq ($(_GATE_RUN),1)
ifeq ($(MULTIPLIER_HDL_ASSERTIONS),1)
override VERILOG_SOURCES += $(MULTIPLIER_TEST_DIR)/multiplier_assertions.sv
COMPILE_ARGS += $(if $(filter vcs,$(SIM)),+define+MOSAIC_MULTIPLIER_ASSERTIONS,-DMOSAIC_MULTIPLIER_ASSERTIONS)
endif
endif
endif
ifeq ($(COCOTB_TOPLEVEL),mac)
ifneq ($(_GATE_RUN),1)
ifeq ($(MAC_HDL_ASSERTIONS),1)
override VERILOG_SOURCES += $(DOT_PRODUCT_TEST_DIR)/dot_product_assertions.sv
COMPILE_ARGS += $(if $(filter vcs,$(SIM)),+define+MOSAIC_MAC_ASSERTIONS,-DMOSAIC_MAC_ASSERTIONS)
endif
endif
endif
ifeq ($(COCOTB_TOPLEVEL),lut_unit)
ifneq ($(_GATE_RUN),1)
ifeq ($(LUT_UNIT_HDL_ASSERTIONS),1)
override VERILOG_SOURCES += $(LUT_UNIT_TEST_DIR)/lut_unit_assertions.sv
COMPILE_ARGS += $(if $(filter vcs,$(SIM)),+define+MOSAIC_LUT_UNIT_ASSERTIONS,-DMOSAIC_LUT_UNIT_ASSERTIONS)
endif
endif
endif
ifeq ($(COCOTB_TOPLEVEL),loop_controller)
ifneq ($(_GATE_RUN),1)
ifeq ($(LOOP_CONTROLLER_HDL_ASSERTIONS),1)
override VERILOG_SOURCES += $(LOOP_CONTROLLER_TEST_DIR)/loop_controller_assertions.sv
COMPILE_ARGS += $(if $(filter vcs,$(SIM)),+define+MOSAIC_LOOP_CONTROLLER_ASSERTIONS,-DMOSAIC_LOOP_CONTROLLER_ASSERTIONS)
endif
endif
endif
ifeq ($(COCOTB_TOPLEVEL),local_switch)
ifneq ($(_GATE_RUN),1)
ifeq ($(LOCAL_SWITCH_HDL_ASSERTIONS),1)
override VERILOG_SOURCES += $(LOCAL_SWITCH_TEST_DIR)/local_switch_assertions.sv
COMPILE_ARGS += $(if $(filter vcs,$(SIM)),+define+MOSAIC_LOCAL_SWITCH_ASSERTIONS,-DMOSAIC_LOCAL_SWITCH_ASSERTIONS)
endif
endif
endif
SCRATCHPAD_CONTROLLER_INSTRUMENTATION ?= 1
export SCRATCHPAD_CONTROLLER_INSTRUMENTATION
ifneq ($(filter scratchpad_controller scratchpad_controller_system_tb,$(COCOTB_TOPLEVEL)),)
ifneq ($(_GATE_RUN),1)
ifeq ($(SCRATCHPAD_CONTROLLER_INSTRUMENTATION),1)
override VERILOG_SOURCES += $(SCRATCHPAD_CONTROLLER_TEST_DIR)/scratchpad_controller_instrumentation.sv
COMPILE_ARGS += $(if $(filter vcs,$(SIM)),+define+MOSAIC_SCRATCHPAD_CONTROLLER_INSTRUMENTATION,-DMOSAIC_SCRATCHPAD_CONTROLLER_INSTRUMENTATION)
endif
endif
endif
ifeq ($(COCOTB_TOPLEVEL),scratchpad_bank)
ifneq ($(_GATE_RUN),1)
ifeq ($(SCRATCHPAD_BANK_INSTRUMENTATION),1)
override VERILOG_SOURCES += $(SCRATCHPAD_BANK_TEST_DIR)/scratchpad_bank_instrumentation.sv
COMPILE_ARGS += $(if $(filter vcs,$(SIM)),+define+MOSAIC_SCRATCHPAD_BANK_INSTRUMENTATION,-DMOSAIC_SCRATCHPAD_BANK_INSTRUMENTATION)
endif
endif
endif
ifeq ($(COCOTB_TOPLEVEL),store_engine)
ifneq ($(_GATE_RUN),1)
ifeq ($(STORE_ENGINE_HDL_ASSERTIONS),1)
override VERILOG_SOURCES += $(STORE_ENGINE_TEST_DIR)/store_engine_assertions.sv
COMPILE_ARGS += $(if $(filter vcs,$(SIM)),+define+MOSAIC_STORE_ENGINE_ASSERTIONS,-DMOSAIC_STORE_ENGINE_ASSERTIONS)
endif
endif
endif
ifeq ($(COCOTB_TOPLEVEL),load_engine)
ifneq ($(_GATE_RUN),1)
ifeq ($(LOAD_ENGINE_HDL_ASSERTIONS),1)
override VERILOG_SOURCES += $(LOAD_ENGINE_TEST_DIR)/load_engine_assertions.sv
COMPILE_ARGS += $(if $(filter vcs,$(SIM)),+define+MOSAIC_LOAD_ENGINE_ASSERTIONS,-DMOSAIC_LOAD_ENGINE_ASSERTIONS)
endif
endif
endif
ifeq ($(COCOTB_TOPLEVEL),exp_unit)
ifneq ($(_GATE_RUN),1)
ifeq ($(EXP_UNIT_HDL_ASSERTIONS),1)
override VERILOG_SOURCES += $(EXP_UNIT_TEST_DIR)/exp_unit_assertions.sv
COMPILE_ARGS += $(if $(filter vcs,$(SIM)),+define+MOSAIC_EXP_UNIT_ASSERTIONS,-DMOSAIC_EXP_UNIT_ASSERTIONS)
endif
endif
endif
ifeq ($(COCOTB_TOPLEVEL),event_barrier)
ifneq ($(_GATE_RUN),1)
ifeq ($(EVENT_BARRIER_HDL_ASSERTIONS),1)
override VERILOG_SOURCES += $(EVENT_BARRIER_TEST_DIR)/event_barrier_assertions.sv
COMPILE_ARGS += $(if $(filter vcs,$(SIM)),+define+MOSAIC_EVENT_BARRIER_ASSERTIONS,-DMOSAIC_EVENT_BARRIER_ASSERTIONS)
endif
endif
endif
ifeq ($(COCOTB_TOPLEVEL),dot_product)
ifneq ($(_GATE_RUN),1)
ifeq ($(DOT_PRODUCT_HDL_ASSERTIONS),1)
override VERILOG_SOURCES += $(DOT_PRODUCT_TEST_DIR)/dot_product_assertions.sv
COMPILE_ARGS += $(if $(filter vcs,$(SIM)),+define+MOSAIC_DOT_PRODUCT_ASSERTIONS,-DMOSAIC_DOT_PRODUCT_ASSERTIONS)
endif
endif
endif
ifeq ($(COCOTB_TOPLEVEL),dma_engine)
ifneq ($(_GATE_RUN),1)
ifeq ($(DMA_ENGINE_HDL_ASSERTIONS),1)
override VERILOG_SOURCES += $(DMA_ENGINE_TEST_DIR)/dma_engine_assertions.sv
COMPILE_ARGS += $(if $(filter vcs,$(SIM)),+define+MOSAIC_DMA_ENGINE_ASSERTIONS,-DMOSAIC_DMA_ENGINE_ASSERTIONS)
endif
endif
endif
ifeq ($(COCOTB_TOPLEVEL),agu)
ifneq ($(_GATE_RUN),1)
ifeq ($(AGU_HDL_ASSERTIONS),1)
override VERILOG_SOURCES += $(AGU_TEST_DIR)/agu_assertions.sv
COMPILE_ARGS += $(if $(filter vcs,$(SIM)),+define+MOSAIC_AGU_ASSERTIONS,-DMOSAIC_AGU_ASSERTIONS)
endif
endif
endif
ifeq ($(COCOTB_TOPLEVEL),accumulator)
ifneq ($(_GATE_RUN),1)
ifeq ($(ACCUMULATOR_HDL_ASSERTIONS),1)
override VERILOG_SOURCES += $(ACCUMULATOR_TEST_DIR)/accumulator_assertions.sv
COMPILE_ARGS += $(if $(filter vcs,$(SIM)),+define+MOSAIC_ACCUMULATOR_ASSERTIONS,-DMOSAIC_ACCUMULATOR_ASSERTIONS)
endif
endif
endif
ifeq ($(_GATE_RUN),1)
ifneq ($(strip $(SDF_FILE)),)
# VCS unified SDF annotation is a compilation option, not a simv option.
COMPILE_ARGS += -sdf $(SDF_CORNER):$(SDF_SCOPE):$(abspath $(SDF_FILE))
CUSTOM_COMPILE_DEPS += $(abspath $(SDF_FILE))
endif
endif
# Short simulation timeout overrides keep negative PyUVM tests bounded. RTL
# defaults retain the specification values; the campaign supplies its own flags.
ifeq ($(COCOTB_TOPLEVEL),cluster_power_manager)
ifneq ($(_GATE_RUN),1)
export CLUSTER_POWER_MANAGER_DRAIN_TIMEOUT_CYCLES ?= 256
export CLUSTER_POWER_MANAGER_TILE_ACK_TIMEOUT_CYCLES ?= 128
export CLUSTER_POWER_MANAGER_POWER_TIMEOUT_CYCLES ?= 128
export CLUSTER_POWER_MANAGER_CLOCK_TIMEOUT_CYCLES ?= 128
export CLUSTER_POWER_MANAGER_RELOAD_TIMEOUT_CYCLES ?= 128
_CPM_TEST_TIMERS := DRAIN_TIMEOUT_CYCLES TILE_ACK_TIMEOUT_CYCLES POWER_TIMEOUT_CYCLES CLOCK_TIMEOUT_CYCLES RELOAD_TIMEOUT_CYCLES
COMPILE_ARGS += $(foreach name,$(_CPM_TEST_TIMERS),$(if $(filter vcs,$(SIM)),-pvalue+,-P)cluster_power_manager.$(name)=$(CLUSTER_POWER_MANAGER_$(name)))
endif
endif
include $(shell "$(PYTHON_BIN)" -m cocotb_tools.config --makefiles)/Makefile.sim
else
.PHONY: all sim pyuvm counter-regression clock-gate-regression decoder-regression dff-regression isolation-cell-regression lane-mask-regression level-shifter-regression mux-regression operand-isolation-regression priority-encoder-regression reset-synchronizer-regression retention-register-regression write-gate-regression async-fifo-regression bypass-network-regression context-memory-regression context-sequencer-regression saif synth gate-sim gate-saif gate-check power power-report power-check power-invalidate setup clean clean-gate clean-synth clean-power help

all sim: pyuvm

pyuvm:
	@test -x "$(PYTHON_BIN)" || { \
		echo 'Python environment missing. Run make setup first.' >&2; exit 2; }
	@"$(PYTHON_BIN)" -c 'import cocotb, pyuvm' || { \
		echo 'PyUVM/cocotb missing. Run make setup first.' >&2; exit 2; }
	+$(MAKE) --no-print-directory -C "$(PROJECT_ROOT)" -f Makefile \
		_COCOTB_RUN=1 PYTHON_BIN="$(PYTHON_BIN)" sim

# Run the specification matrix with real PyUVM components and coverage gates.
# Each profile uses its own build directory and elaboration-time parameters.
counter-regression:
	@test -x "$(PYTHON_BIN)" || { \
		echo 'Python environment missing. Run make setup first.' >&2; exit 2; }
	@test -r "$(COUNTER_TEST_DIR)/run_counter_regression.py" || { \
		echo 'Counter regression missing under src/val/<category>/counter.' >&2; exit 2; }
	@"$(PYTHON_BIN)" "$(COUNTER_TEST_DIR)/run_counter_regression.py" \
		--sim "$(SIM)" --build-dir "$(COUNTER_REGRESSION_BUILD)" \
		--seed "$(COUNTER_SEED)" --random-cycles "$(COUNTER_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_COUNTER_MAKE)" \
		$(if $(strip $(_COUNTER_SIM_BIN_DIR)),--sim-bin-dir "$(_COUNTER_SIM_BIN_DIR)")

# Use fresh simulator processes to check both reset-free startup states.
clock-gate-regression:
	@test -x "$(PYTHON_BIN)" || { \
		echo 'Python environment missing. Run make setup first.' >&2; exit 2; }
	@test -r "$(CLOCK_GATE_TEST_DIR)/run_clock_gate_regression.py" || { \
		echo 'Clock gate regression missing under src/val/<category>/clock_gate.' >&2; exit 2; }
	@"$(PYTHON_BIN)" "$(CLOCK_GATE_TEST_DIR)/run_clock_gate_regression.py" \
		--sim "$(SIM)" --build-dir "$(CLOCK_GATE_REGRESSION_BUILD)" \
		--seed "$(CLOCK_GATE_SEED)" --random-cycles "$(CLOCK_GATE_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_CLOCK_GATE_MAKE)" \
		$(if $(strip $(_CLOCK_GATE_SIM_BIN_DIR)),--sim-bin-dir "$(_CLOCK_GATE_SIM_BIN_DIR)")

# Exhaust binary encodings and legal transition pairs in the reference matrix.
decoder-regression:
	@test -x "$(PYTHON_BIN)" || { \
		echo 'Python environment missing. Run make setup first.' >&2; exit 2; }
	@test -r "$(DECODER_TEST_DIR)/run_decoder_regression.py" || { \
		echo 'Decoder regression missing under src/val/<category>/decoder.' >&2; exit 2; }
	@"$(PYTHON_BIN)" "$(DECODER_TEST_DIR)/run_decoder_regression.py" \
		--sim "$(SIM)" --build-dir "$(DECODER_REGRESSION_BUILD)" \
		--seed "$(DECODER_SEED)" --random-cycles "$(DECODER_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_DECODER_MAKE)" \
		$(if $(strip $(_DECODER_SIM_BIN_DIR)),--sim-bin-dir "$(_DECODER_SIM_BIN_DIR)")

# Cross static reset/enable branches and audit state changes between clock edges.
dff-regression:
	@test -x "$(PYTHON_BIN)" || { \
		echo 'Python environment missing. Run make setup first.' >&2; exit 2; }
	@test -r "$(DFF_TEST_DIR)/run_dff_regression.py" || { \
		echo 'DFF regression missing under src/val/<category>/dff.' >&2; exit 2; }
	@"$(PYTHON_BIN)" "$(DFF_TEST_DIR)/run_dff_regression.py" \
		--sim "$(SIM)" --build-dir "$(DFF_REGRESSION_BUILD)" \
		--seed "$(DFF_SEED)" --random-cycles "$(DFF_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_DFF_MAKE)" \
		$(if $(strip $(_DFF_SIM_BIN_DIR)),--sim-bin-dir "$(_DFF_SIM_BIN_DIR)")

# Cross widths, clamp classes, and polarities using four-state source data.
isolation-cell-regression:
	@test -x "$(PYTHON_BIN)" || { \
		echo 'Python environment missing. Run make setup first.' >&2; exit 2; }
	@test -r "$(ISOLATION_CELL_TEST_DIR)/run_isolation_cell_regression.py" || { \
		echo 'Isolation cell regression missing under src/val/<category>/isolation_cell.' >&2; exit 2; }
	@"$(PYTHON_BIN)" "$(ISOLATION_CELL_TEST_DIR)/run_isolation_cell_regression.py" \
		--sim "$(SIM)" --build-dir "$(ISOLATION_CELL_REGRESSION_BUILD)" \
		--seed "$(ISOLATION_CELL_SEED)" --random-cycles "$(ISOLATION_CELL_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_ISOLATION_CELL_MAKE)" \
		$(if $(strip $(_ISOLATION_CELL_SIM_BIN_DIR)),--sim-bin-dir "$(_ISOLATION_CELL_SIM_BIN_DIR)")

# Check lane independence and all derived masks across the specification sizes.
lane-mask-regression:
	@test -x "$(PYTHON_BIN)" || { \
		echo 'Python environment missing. Run make setup first.' >&2; exit 2; }
	@test -r "$(LANE_MASK_TEST_DIR)/run_lane_mask_regression.py" || { \
		echo 'Lane mask regression missing under src/val/<category>/lane_mask.' >&2; exit 2; }
	@"$(PYTHON_BIN)" "$(LANE_MASK_TEST_DIR)/run_lane_mask_regression.py" \
		--sim "$(SIM)" --build-dir "$(LANE_MASK_REGRESSION_BUILD)" \
		--seed "$(LANE_MASK_SEED)" --random-cycles "$(LANE_MASK_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_LANE_MASK_MAKE)" \
		$(if $(strip $(_LANE_MASK_SIM_BIN_DIR)),--sim-bin-dir "$(_LANE_MASK_SIM_BIN_DIR)")

# Preserve every four-state bus bit across both static translation directions.
level-shifter-regression:
	@test -x "$(PYTHON_BIN)" || { \
		echo 'Python environment missing. Run make setup first.' >&2; exit 2; }
	@test -r "$(LEVEL_SHIFTER_TEST_DIR)/run_level_shifter_regression.py" || { \
		echo 'Level shifter regression missing under src/val/<category>/level_shifter.' >&2; exit 2; }
	@"$(PYTHON_BIN)" "$(LEVEL_SHIFTER_TEST_DIR)/run_level_shifter_regression.py" \
		--sim "$(SIM)" --build-dir "$(LEVEL_SHIFTER_REGRESSION_BUILD)" \
		--seed "$(LEVEL_SHIFTER_SEED)" --random-cycles "$(LEVEL_SHIFTER_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_LEVEL_SHIFTER_MAKE)" \
		$(if $(strip $(_LEVEL_SHIFTER_SIM_BIN_DIR)),--sim-bin-dir "$(_LEVEL_SHIFTER_SIM_BIN_DIR)")

# Cross the recommended mux sizes with zero, one, and mixed invalid defaults.
mux-regression:
	@test -x "$(PYTHON_BIN)" || { \
		echo 'Python environment missing. Run make setup first.' >&2; exit 2; }
	@test -r "$(MUX_TEST_DIR)/run_mux_regression.py" || { \
		echo 'Mux regression missing under src/val/<category>/mux.' >&2; exit 2; }
	@"$(PYTHON_BIN)" "$(MUX_TEST_DIR)/run_mux_regression.py" \
		--sim "$(SIM)" --build-dir "$(MUX_REGRESSION_BUILD)" \
		--seed "$(MUX_SEED)" --random-cycles "$(MUX_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_MUX_MAKE)" \
		$(if $(strip $(_MUX_SIM_BIN_DIR)),--sim-bin-dir "$(_MUX_SIM_BIN_DIR)")

# Cross all specified operand widths with the representable clamp classes.
operand-isolation-regression:
	@test -x "$(PYTHON_BIN)" || { \
		echo 'Python environment missing. Run make setup first.' >&2; exit 2; }
	@test -r "$(OPERAND_ISOLATION_TEST_DIR)/run_operand_isolation_regression.py" || { \
		echo 'Operand isolation regression missing under src/val/<category>/operand_isolation.' >&2; exit 2; }
	@"$(PYTHON_BIN)" "$(OPERAND_ISOLATION_TEST_DIR)/run_operand_isolation_regression.py" \
		--sim "$(SIM)" --build-dir "$(OPERAND_ISOLATION_REGRESSION_BUILD)" \
		--seed "$(OPERAND_ISOLATION_SEED)" --random-cycles "$(OPERAND_ISOLATION_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_OPERAND_ISOLATION_MAKE)" \
		$(if $(strip $(_OPERAND_ISOLATION_SIM_BIN_DIR)),--sim-bin-dir "$(_OPERAND_ISOLATION_SIM_BIN_DIR)")

# Check every specified request width with both static priority directions.
priority-encoder-regression:
	@test -x "$(PYTHON_BIN)" || { \
		echo 'Python environment missing. Run make setup first.' >&2; exit 2; }
	@test -r "$(PRIORITY_ENCODER_TEST_DIR)/run_priority_encoder_regression.py" || { \
		echo 'Priority encoder regression missing under src/val/<category>/priority_encoder.' >&2; exit 2; }
	@"$(PYTHON_BIN)" "$(PRIORITY_ENCODER_TEST_DIR)/run_priority_encoder_regression.py" \
		--sim "$(SIM)" --build-dir "$(PRIORITY_ENCODER_REGRESSION_BUILD)" \
		--seed "$(PRIORITY_ENCODER_SEED)" --random-cycles "$(PRIORITY_ENCODER_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_PRIORITY_ENCODER_MAKE)" \
		$(if $(strip $(_PRIORITY_ENCODER_SIM_BIN_DIR)),--sim-bin-dir "$(_PRIORITY_ENCODER_SIM_BIN_DIR)")

# Check asynchronous assertion and exact edge-count release at each depth.
reset-synchronizer-regression:
	@test -x "$(PYTHON_BIN)" || { \
		echo 'Python environment missing. Run make setup first.' >&2; exit 2; }
	@test -r "$(RESET_SYNCHRONIZER_TEST_DIR)/run_reset_synchronizer_regression.py" || { \
		echo 'Reset synchronizer regression missing under src/val/<category>/reset_synchronizer.' >&2; exit 2; }
	@"$(PYTHON_BIN)" "$(RESET_SYNCHRONIZER_TEST_DIR)/run_reset_synchronizer_regression.py" \
		--sim "$(SIM)" --build-dir "$(RESET_SYNCHRONIZER_REGRESSION_BUILD)" \
		--seed "$(RESET_SYNCHRONIZER_SEED)" --random-cycles "$(RESET_SYNCHRONIZER_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_RESET_SYNCHRONIZER_MAKE)" \
		$(if $(strip $(_RESET_SYNCHRONIZER_SIM_BIN_DIR)),--sim-bin-dir "$(_RESET_SYNCHRONIZER_SIM_BIN_DIR)")

# Check portable save/restore behavior; power-aware cell/UPF signoff is separate.
retention-register-regression:
	@test -x "$(PYTHON_BIN)" || { \
		echo 'Python environment missing. Run make setup first.' >&2; exit 2; }
	@test -r "$(RETENTION_REGISTER_TEST_DIR)/run_retention_register_regression.py" || { \
		echo 'Retention register regression missing under src/val/<category>/retention_register.' >&2; exit 2; }
	@"$(PYTHON_BIN)" "$(RETENTION_REGISTER_TEST_DIR)/run_retention_register_regression.py" \
		--sim "$(SIM)" --build-dir "$(RETENTION_REGISTER_REGRESSION_BUILD)" \
		--seed "$(RETENTION_REGISTER_SEED)" --random-cycles "$(RETENTION_REGISTER_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_RETENTION_REGISTER_MAKE)" \
		$(if $(strip $(_RETENTION_REGISTER_SIM_BIN_DIR)),--sim-bin-dir "$(_RETENTION_REGISTER_SIM_BIN_DIR)")

# Check combinational masks and equivalence at real register/memory destinations.
write-gate-regression:
	@test -x "$(PYTHON_BIN)" || { \
		echo 'Python environment missing. Run make setup first.' >&2; exit 2; }
	@test -r "$(WRITE_GATE_TEST_DIR)/run_write_gate_regression.py" || { \
		echo 'Write gate regression missing under src/val/<category>/write_gate.' >&2; exit 2; }
	@"$(PYTHON_BIN)" "$(WRITE_GATE_TEST_DIR)/run_write_gate_regression.py" \
		--sim "$(SIM)" --build-dir "$(WRITE_GATE_REGRESSION_BUILD)" \
		--seed "$(WRITE_GATE_SEED)" --random-cycles "$(WRITE_GATE_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_WRITE_GATE_MAKE)" \
		$(if $(strip $(_WRITE_GATE_SIM_BIN_DIR)),--sim-bin-dir "$(_WRITE_GATE_SIM_BIN_DIR)")

# Validate asynchronous clocks, record ordering, reset cancellation, and CDC stages.
async-fifo-regression:
	@test -x "$(PYTHON_BIN)" || { \
		echo 'Python environment missing. Run make setup first.' >&2; exit 2; }
	@test -r "$(ASYNC_FIFO_TEST_DIR)/run_async_fifo_regression.py" || { \
		echo 'Async FIFO regression missing under src/val/<category>/async_fifo.' >&2; exit 2; }
	@"$(PYTHON_BIN)" "$(ASYNC_FIFO_TEST_DIR)/run_async_fifo_regression.py" \
		--sim "$(SIM)" --build-dir "$(ASYNC_FIFO_REGRESSION_BUILD)" \
		--seed "$(ASYNC_FIFO_SEED)" --random-cycles "$(ASYNC_FIFO_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_ASYNC_FIFO_MAKE)" \
		$(if $(strip $(_ASYNC_FIFO_SIM_BIN_DIR)),--sim-bin-dir "$(_ASYNC_FIFO_SIM_BIN_DIR)")

# Check sparse forwarding, independent destinations, capture/hold, and context flush.
bypass-network-regression:
	@test -x "$(PYTHON_BIN)" || { \
		echo 'Python environment missing. Run make setup first.' >&2; exit 2; }
	@test -r "$(BYPASS_NETWORK_TEST_DIR)/run_bypass_network_regression.py" || { \
		echo 'Bypass network regression missing under src/val/<category>/bypass_network.' >&2; exit 2; }
	@"$(PYTHON_BIN)" "$(BYPASS_NETWORK_TEST_DIR)/run_bypass_network_regression.py" \
		--sim "$(SIM)" --build-dir "$(BYPASS_NETWORK_REGRESSION_BUILD)" \
		--seed "$(BYPASS_NETWORK_SEED)" --random-cycles "$(BYPASS_NETWORK_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_BYPASS_NETWORK_MAKE)" \
		$(if $(strip $(_BYPASS_NETWORK_SIM_BIN_DIR)),--sim-bin-dir "$(_BYPASS_NETWORK_SIM_BIN_DIR)")

# Validate resident context loading, masked writes, commit, and read timing.
context-memory-regression:
	@test -x "$(PYTHON_BIN)" || { \
		echo 'Python environment missing. Run make setup first.' >&2; exit 2; }
	@test -r "$(CONTEXT_MEMORY_TEST_DIR)/run_context_memory_regression.py" || { \
		echo 'Context memory regression missing under src/val/<category>/context_memory.' >&2; exit 2; }
	@"$(PYTHON_BIN)" "$(CONTEXT_MEMORY_TEST_DIR)/run_context_memory_regression.py" \
		--sim "$(SIM)" --build-dir "$(CONTEXT_MEMORY_REGRESSION_BUILD)" \
		--seed "$(CONTEXT_MEMORY_SEED)" --random-cycles "$(CONTEXT_MEMORY_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_CONTEXT_MEMORY_MAKE)" \
		$(if $(strip $(_CONTEXT_MEMORY_SIM_BIN_DIR)),--sim-bin-dir "$(_CONTEXT_MEMORY_SIM_BIN_DIR)")

# Check context selection, loop visits, runtime safe points, and sticky errors.
context-sequencer-regression:
	@test -x "$(PYTHON_BIN)" || { \
		echo 'Python environment missing. Run make setup first.' >&2; exit 2; }
	@test -r "$(CONTEXT_SEQUENCER_TEST_DIR)/run_context_sequencer_regression.py" || { \
		echo 'Context sequencer regression missing under src/val/<category>/context_sequencer.' >&2; exit 2; }
	@"$(PYTHON_BIN)" "$(CONTEXT_SEQUENCER_TEST_DIR)/run_context_sequencer_regression.py" \
		--sim "$(SIM)" --build-dir "$(CONTEXT_SEQUENCER_REGRESSION_BUILD)" \
		--seed "$(CONTEXT_SEQUENCER_SEED)" --random-cycles "$(CONTEXT_SEQUENCER_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_CONTEXT_SEQUENCER_MAKE)" \
		$(if $(strip $(_CONTEXT_SEQUENCER_SIM_BIN_DIR)),--sim-bin-dir "$(_CONTEXT_SEQUENCER_SIM_BIN_DIR)")

.PHONY: data-aligner-regression
# Check byte mapping, spill conservation, elastic occupancy and cancellation.
data-aligner-regression:
	@test -x "$(PYTHON_BIN)" || { \
		echo 'Python environment missing. Run make setup first.' >&2; exit 2; }
	@test -r "$(DATA_ALIGNER_TEST_DIR)/run_data_aligner_regression.py" || { \
		echo 'Data aligner regression missing under src/val/<category>/data_aligner.' >&2; exit 2; }
	@"$(PYTHON_BIN)" "$(DATA_ALIGNER_TEST_DIR)/run_data_aligner_regression.py" \
		--sim "$(SIM)" --build-dir "$(DATA_ALIGNER_REGRESSION_BUILD)" \
		--seed "$(DATA_ALIGNER_SEED)" --random-cycles "$(DATA_ALIGNER_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_DATA_ALIGNER_MAKE)" \
		$(if $(strip $(_DATA_ALIGNER_SIM_BIN_DIR)),--sim-bin-dir "$(_DATA_ALIGNER_SIM_BIN_DIR)")

.PHONY: sram-wrapper-regression
# Check masked memory, fixed latency, read credits and backend replacement.
sram-wrapper-regression:
	@test -x "$(PYTHON_BIN)" || { \
		echo 'Python environment missing. Run make setup first.' >&2; exit 2; }
	@test -r "$(SRAM_WRAPPER_TEST_DIR)/run_sram_wrapper_regression.py" || { \
		echo 'SRAM-wrapper regression missing under src/val/<category>/sram_wrapper.' >&2; exit 2; }
	@"$(PYTHON_BIN)" "$(SRAM_WRAPPER_TEST_DIR)/run_sram_wrapper_regression.py" \
		--sim "$(SIM)" --build-dir "$(SRAM_WRAPPER_REGRESSION_BUILD)" \
		--seed "$(SRAM_WRAPPER_SEED)" --random-cycles "$(SRAM_WRAPPER_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_SRAM_WRAPPER_MAKE)" \
		$(if $(strip $(_SRAM_WRAPPER_SIM_BIN_DIR)),--sim-bin-dir "$(_SRAM_WRAPPER_SIM_BIN_DIR)")

.PHONY: stream-join-regression
# Check atomic input consumption, final arrival, idle masks and backpressure.
stream-join-regression:
	@test -x "$(PYTHON_BIN)" || { \
		echo 'Python environment missing. Run make setup first.' >&2; exit 2; }
	@test -r "$(STREAM_JOIN_TEST_DIR)/run_stream_join_regression.py" || { \
		echo 'Stream-join regression missing under src/val/<category>/stream_join.' >&2; exit 2; }
	@"$(PYTHON_BIN)" "$(STREAM_JOIN_TEST_DIR)/run_stream_join_regression.py" \
		--sim "$(SIM)" --build-dir "$(STREAM_JOIN_REGRESSION_BUILD)" \
		--seed "$(STREAM_JOIN_SEED)" --random-cycles "$(STREAM_JOIN_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_STREAM_JOIN_MAKE)" \
		$(if $(strip $(_STREAM_JOIN_SIM_BIN_DIR)),--sim-bin-dir "$(_STREAM_JOIN_SIM_BIN_DIR)")

.PHONY: predicate-unit-regression predicate-unit-static predicate-unit-formal
predicate-unit-regression:
	@"$(PYTHON_BIN)" "$(PREDICATE_UNIT_TEST_DIR)/run_predicate_unit_regression.py" \
		--sim "$(SIM)" --build-dir "$(PREDICATE_UNIT_REGRESSION_BUILD)" \
		--seed "$(PREDICATE_UNIT_SEED)" --random-cycles "$(PREDICATE_UNIT_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_PREDICATE_UNIT_MAKE)" \
		$(if $(strip $(_PREDICATE_UNIT_SIM_BIN_DIR)),--sim-bin-dir "$(_PREDICATE_UNIT_SIM_BIN_DIR)")

predicate-unit-static:
	@"$(PYTHON_BIN)" "$(PREDICATE_UNIT_TEST_DIR)/run_predicate_unit_static.py" \
		--yosys "$(PREDICATE_UNIT_YOSYS)" --verilator "$(PREDICATE_UNIT_VERILATOR)" \
		--build-dir "$(PREDICATE_UNIT_STATIC_BUILD)"

predicate-unit-formal:
	@"$(PYTHON_BIN)" "$(PREDICATE_UNIT_TEST_DIR)/run_predicate_unit_formal.py" \
		--yosys "$(PREDICATE_UNIT_YOSYS)" --build-dir "$(PREDICATE_UNIT_FORMAL_BUILD)"

.PHONY: vector-reduction-regression vector-reduction-static vector-reduction-formal
vector-reduction-regression:
	@"$(PYTHON_BIN)" "$(VECTOR_REDUCTION_TEST_DIR)/run_vector_reduction_regression.py" \
		--sim "$(SIM)" --build-dir "$(VECTOR_REDUCTION_REGRESSION_BUILD)" \
		--seed "$(VECTOR_REDUCTION_SEED)" --random-cycles "$(VECTOR_REDUCTION_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_VECTOR_REDUCTION_MAKE)" \
		$(if $(strip $(_VECTOR_REDUCTION_SIM_BIN_DIR)),--sim-bin-dir "$(_VECTOR_REDUCTION_SIM_BIN_DIR)")

vector-reduction-static:
	@"$(PYTHON_BIN)" "$(VECTOR_REDUCTION_TEST_DIR)/run_vector_reduction_static.py" \
		--yosys "$(VECTOR_REDUCTION_YOSYS)" --verilator "$(VECTOR_REDUCTION_VERILATOR)" \
		--build-dir "$(VECTOR_REDUCTION_STATIC_BUILD)"

vector-reduction-formal:
	@"$(PYTHON_BIN)" "$(VECTOR_REDUCTION_TEST_DIR)/run_vector_reduction_formal.py" \
		--yosys "$(VECTOR_REDUCTION_YOSYS)" --build-dir "$(VECTOR_REDUCTION_FORMAL_BUILD)"

.PHONY: vector-lane-regression vector-lane-static vector-lane-formal
vector-lane-regression:
	@"$(PYTHON_BIN)" "$(VECTOR_LANE_TEST_DIR)/run_vector_lane_regression.py" \
		--sim "$(SIM)" --build-dir "$(VECTOR_LANE_REGRESSION_BUILD)" \
		--seed "$(VECTOR_LANE_SEED)" --random-cycles "$(VECTOR_LANE_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_VECTOR_LANE_MAKE)" \
		$(if $(strip $(_VECTOR_LANE_SIM_BIN_DIR)),--sim-bin-dir "$(_VECTOR_LANE_SIM_BIN_DIR)")

vector-lane-static:
	@"$(PYTHON_BIN)" "$(VECTOR_LANE_TEST_DIR)/run_vector_lane_static.py" \
		--yosys "$(VECTOR_LANE_YOSYS)" --verilator "$(VECTOR_LANE_VERILATOR)" \
		--build-dir "$(VECTOR_LANE_STATIC_BUILD)"

vector-lane-formal:
	@"$(PYTHON_BIN)" "$(VECTOR_LANE_TEST_DIR)/run_vector_lane_formal.py" \
		--yosys "$(VECTOR_LANE_YOSYS)" --build-dir "$(VECTOR_LANE_FORMAL_BUILD)"

.PHONY: scalar-alu-static
scalar-alu-static:
	@"$(PYTHON_BIN)" "$(SCALAR_ALU_TEST_DIR)/run_scalar_alu_static.py" \
		--yosys "$(SCALAR_ALU_YOSYS)" --verilator "$(SCALAR_ALU_VERILATOR)" \
		--build-dir "$(SCALAR_ALU_STATIC_BUILD)"

.PHONY: scalar-alu-formal
scalar-alu-formal:
	@"$(PYTHON_BIN)" "$(SCALAR_ALU_TEST_DIR)/run_scalar_alu_formal.py" \
		--yosys "$(SCALAR_ALU_YOSYS)" --build-dir "$(SCALAR_ALU_FORMAL_BUILD)"

.PHONY: scalar-alu-regression
scalar-alu-regression:
	@"$(PYTHON_BIN)" "$(SCALAR_ALU_TEST_DIR)/run_scalar_alu_regression.py" \
		--sim "$(SIM)" --build-dir "$(SCALAR_ALU_REGRESSION_BUILD)" \
		--seed "$(SCALAR_ALU_SEED)" --random-cycles "$(SCALAR_ALU_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_SCALAR_ALU_MAKE)" \
		$(if $(strip $(_SCALAR_ALU_SIM_BIN_DIR)),--sim-bin-dir "$(_SCALAR_ALU_SIM_BIN_DIR)")

.PHONY: noc-router-regression noc-router-mesh-regression noc-router-topology
noc-router-regression:
	@"$(PYTHON_BIN)" "$(NOC_ROUTER_TEST_DIR)/run_noc_router_regression.py" \
		--sim "$(SIM)" --build-dir "$(NOC_ROUTER_REGRESSION_BUILD)" \
		--seed "$(NOC_ROUTER_SEED)" --random-cycles "$(NOC_ROUTER_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_NOC_ROUTER_MAKE)" \
		$(if $(strip $(_NOC_ROUTER_SIM_BIN_DIR)),--sim-bin-dir "$(_NOC_ROUTER_SIM_BIN_DIR)")

noc-router-mesh-regression:
	@"$(PYTHON_BIN)" "$(NOC_ROUTER_TEST_DIR)/run_noc_router_mesh.py" \
		--sim "$(SIM)" --build-dir "$(NOC_ROUTER_MESH_BUILD)" \
		--seed "$(NOC_ROUTER_SEED)" --random-cycles "$(NOC_ROUTER_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_NOC_ROUTER_MAKE)" \
		$(if $(strip $(_NOC_ROUTER_SIM_BIN_DIR)),--sim-bin-dir "$(_NOC_ROUTER_SIM_BIN_DIR)")

noc-router-topology:
	@"$(PYTHON_BIN)" "$(NOC_ROUTER_TEST_DIR)/analyze_topology.py" \
		--output "$(NOC_ROUTER_TOPOLOGY_BUILD)/summary.json"

.PHONY: multiplier-regression
# Exact full products, independent operand signedness, enabled-edge timing and X/Z.
multiplier-regression:
	@test -x "$(PYTHON_BIN)" || { \
		echo 'Python environment missing. Run make setup first.' >&2; exit 2; }
	@"$(PYTHON_BIN)" "$(MULTIPLIER_TEST_DIR)/run_multiplier_regression.py" \
		--sim "$(SIM)" --build-dir "$(MULTIPLIER_REGRESSION_BUILD)" \
		--seed "$(MULTIPLIER_SEED)" --random-cycles "$(MULTIPLIER_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_MULTIPLIER_MAKE)" \
		$(if $(strip $(_MULTIPLIER_SIM_BIN_DIR)),--sim-bin-dir "$(_MULTIPLIER_SIM_BIN_DIR)")

.PHONY: mac-regression
# Reuse the scalar dot-product arithmetic and its independent native HDL checker.
mac-regression:
	@test -x "$(PYTHON_BIN)" || { \
		echo 'Python environment missing. Run make setup first.' >&2; exit 2; }
	@"$(PYTHON_BIN)" "$(MAC_TEST_DIR)/run_mac_regression.py" \
		--sim "$(SIM)" --build-dir "$(MAC_REGRESSION_BUILD)" \
		--seed "$(MAC_SEED)" --random-cycles "$(MAC_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_MAC_MAKE)" \
		$(if $(strip $(_MAC_SIM_BIN_DIR)),--sim-bin-dir "$(_MAC_SIM_BIN_DIR)")

.PHONY: lut-unit-regression
lut-unit-regression:
	@"$(PYTHON_BIN)" "$(LUT_UNIT_TEST_DIR)/run_lut_unit_regression.py" \
		--sim "$(SIM)" --build-dir "$(LUT_UNIT_REGRESSION_BUILD)" \
		--seed "$(LUT_UNIT_SEED)" --random-cycles "$(LUT_UNIT_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_LUT_UNIT_MAKE)" \
		$(if $(strip $(_LUT_UNIT_SIM_BIN_DIR)),--sim-bin-dir "$(_LUT_UNIT_SIM_BIN_DIR)")

.PHONY: rsqrt-unit-regression
rsqrt-unit-regression:
	@"$(PYTHON_BIN)" "$(RSQRT_UNIT_TEST_DIR)/run_rsqrt_unit_regression.py" \
		--sim "$(SIM)" --build-dir "$(RSQRT_UNIT_REGRESSION_BUILD)" \
		--seed "$(RSQRT_UNIT_SEED)" --random-cycles "$(RSQRT_UNIT_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_RSQRT_UNIT_MAKE)" \
		$(if $(strip $(_RSQRT_UNIT_SIM_BIN_DIR)),--sim-bin-dir "$(_RSQRT_UNIT_SIM_BIN_DIR)")

.PHONY: reciprocal-unit-regression
reciprocal-unit-regression:
	@"$(PYTHON_BIN)" "$(RECIPROCAL_UNIT_TEST_DIR)/run_reciprocal_unit_regression.py" \
		--sim "$(SIM)" --build-dir "$(RECIPROCAL_UNIT_REGRESSION_BUILD)" \
		--seed "$(RECIPROCAL_UNIT_SEED)" --random-cycles "$(RECIPROCAL_UNIT_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_RECIPROCAL_UNIT_MAKE)" \
		$(if $(strip $(_RECIPROCAL_UNIT_SIM_BIN_DIR)),--sim-bin-dir "$(_RECIPROCAL_UNIT_SIM_BIN_DIR)")

.PHONY: polynomial-unit-regression
polynomial-unit-regression:
	@"$(PYTHON_BIN)" "$(POLYNOMIAL_UNIT_TEST_DIR)/run_polynomial_unit_regression.py" \
		--sim "$(SIM)" --build-dir "$(POLYNOMIAL_UNIT_REGRESSION_BUILD)" \
		--seed "$(POLYNOMIAL_UNIT_SEED)" --random-cycles "$(POLYNOMIAL_UNIT_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_POLYNOMIAL_UNIT_MAKE)" \
		$(if $(strip $(_POLYNOMIAL_UNIT_SIM_BIN_DIR)),--sim-bin-dir "$(_POLYNOMIAL_UNIT_SIM_BIN_DIR)")

.PHONY: loop-controller-regression
loop-controller-regression:
	@"$(PYTHON_BIN)" "$(LOOP_CONTROLLER_TEST_DIR)/run_loop_controller_regression.py" \
		--sim "$(SIM)" --build-dir "$(LOOP_CONTROLLER_REGRESSION_BUILD)" \
		--seed "$(LOOP_CONTROLLER_SEED)" --random-cycles "$(LOOP_CONTROLLER_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_LOOP_CONTROLLER_MAKE)" \
		$(if $(strip $(_LOOP_CONTROLLER_SIM_BIN_DIR)),--sim-bin-dir "$(_LOOP_CONTROLLER_SIM_BIN_DIR)")

.PHONY: tile-power-controller-regression
tile-power-controller-regression:
	@"$(PYTHON_BIN)" "$(TILE_POWER_CONTROLLER_TEST_DIR)/run_tile_power_controller_regression.py" \
		--sim "$(SIM)" --build-dir "$(TILE_POWER_CONTROLLER_REGRESSION_BUILD)" \
		--seed "$(TILE_POWER_CONTROLLER_SEED)" \
		--random-cycles "$(TILE_POWER_CONTROLLER_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" \
		--make "$(_TILE_POWER_CONTROLLER_MAKE)" \
		$(if $(strip $(_TILE_POWER_CONTROLLER_SIM_BIN_DIR)),--sim-bin-dir "$(_TILE_POWER_CONTROLLER_SIM_BIN_DIR)")

.PHONY: tile-network-interface-regression
tile-network-interface-regression:
	@"$(PYTHON_BIN)" "$(TILE_NETWORK_INTERFACE_TEST_DIR)/run_tile_network_interface_regression.py" \
		--sim "$(SIM)" --build-dir "$(TILE_NETWORK_INTERFACE_REGRESSION_BUILD)" \
		--seed "$(TILE_NETWORK_INTERFACE_SEED)" \
		--random-cycles "$(TILE_NETWORK_INTERFACE_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" \
		--make "$(_TILE_NETWORK_INTERFACE_MAKE)" \
		$(if $(strip $(_TILE_NETWORK_INTERFACE_SIM_BIN_DIR)),--sim-bin-dir "$(_TILE_NETWORK_INTERFACE_SIM_BIN_DIR)")

.PHONY: local-switch-regression
local-switch-regression:
	@"$(PYTHON_BIN)" "$(LOCAL_SWITCH_TEST_DIR)/run_local_switch_regression.py" \
		--sim "$(SIM)" --build-dir "$(LOCAL_SWITCH_REGRESSION_BUILD)" \
		--seed "$(LOCAL_SWITCH_SEED)" --random-cycles "$(LOCAL_SWITCH_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_LOCAL_SWITCH_MAKE)" \
		$(if $(strip $(_LOCAL_SWITCH_SIM_BIN_DIR)),--sim-bin-dir "$(_LOCAL_SWITCH_SIM_BIN_DIR)")

.PHONY: scratchpad-controller-regression
scratchpad-controller-regression:
	@"$(PYTHON_BIN)" "$(SCRATCHPAD_CONTROLLER_TEST_DIR)/run_scratchpad_controller_regression.py" \
		--sim "$(SIM)" --build-dir "$(SCRATCHPAD_CONTROLLER_REGRESSION_BUILD)" \
		--seed "$(SCRATCHPAD_CONTROLLER_SEED)" --random-cycles "$(SCRATCHPAD_CONTROLLER_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_SCRATCHPAD_CONTROLLER_MAKE)" \
		$(if $(strip $(_SCRATCHPAD_CONTROLLER_SIM_BIN_DIR)),--sim-bin-dir "$(_SCRATCHPAD_CONTROLLER_SIM_BIN_DIR)")

.PHONY: scratchpad-bank-regression
scratchpad-bank-regression:
	@"$(PYTHON_BIN)" "$(SCRATCHPAD_BANK_TEST_DIR)/run_scratchpad_bank_regression.py" \
		--sim "$(SIM)" --build-dir "$(SCRATCHPAD_BANK_REGRESSION_BUILD)" \
		--seed "$(SCRATCHPAD_BANK_SEED)" --random-cycles "$(SCRATCHPAD_BANK_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_SCRATCHPAD_BANK_MAKE)" \
		$(if $(strip $(_SCRATCHPAD_BANK_SIM_BIN_DIR)),--sim-bin-dir "$(_SCRATCHPAD_BANK_SIM_BIN_DIR)")

.PHONY: stream-formatter-regression
stream-formatter-regression:
	@"$(PYTHON_BIN)" "$(STREAM_FORMATTER_TEST_DIR)/run_stream_formatter_regression.py" \
		--sim "$(SIM)" --build-dir "$(STREAM_FORMATTER_REGRESSION_BUILD)" \
		--seed "$(STREAM_FORMATTER_SEED)" --random-cycles "$(STREAM_FORMATTER_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_STREAM_FORMATTER_MAKE)" \
		$(if $(strip $(_STREAM_FORMATTER_SIM_BIN_DIR)),--sim-bin-dir "$(_STREAM_FORMATTER_SIM_BIN_DIR)")

.PHONY: store-engine-regression
store-engine-regression:
	@"$(PYTHON_BIN)" "$(STORE_ENGINE_TEST_DIR)/run_store_engine_regression.py" \
		--sim "$(SIM)" --build-dir "$(STORE_ENGINE_REGRESSION_BUILD)" \
		--seed "$(STORE_ENGINE_SEED)" --random-cycles "$(STORE_ENGINE_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_STORE_ENGINE_MAKE)" \
		$(if $(strip $(_STORE_ENGINE_SIM_BIN_DIR)),--sim-bin-dir "$(_STORE_ENGINE_SIM_BIN_DIR)")

.PHONY: load-engine-regression
load-engine-regression:
	@"$(PYTHON_BIN)" "$(LOAD_ENGINE_TEST_DIR)/run_load_engine_regression.py" \
		--sim "$(SIM)" --build-dir "$(LOAD_ENGINE_REGRESSION_BUILD)" \
		--seed "$(LOAD_ENGINE_SEED)" --random-cycles "$(LOAD_ENGINE_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_LOAD_ENGINE_MAKE)" \
		$(if $(strip $(_LOAD_ENGINE_SIM_BIN_DIR)),--sim-bin-dir "$(_LOAD_ENGINE_SIM_BIN_DIR)")

.PHONY: exp-unit-regression exp-unit-images
exp-unit-images:
	@"$(PYTHON_BIN)" "$(PROJECT_ROOT)/tools/generate_exp_unit.py" --check

exp-unit-regression: exp-unit-images
	@"$(PYTHON_BIN)" "$(EXP_UNIT_TEST_DIR)/run_exp_unit_regression.py" \
		--sim "$(SIM)" --build-dir "$(EXP_UNIT_REGRESSION_BUILD)" \
		--seed "$(EXP_UNIT_SEED)" --random-cycles "$(EXP_UNIT_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_EXP_UNIT_MAKE)" \
		$(if $(strip $(_EXP_UNIT_SIM_BIN_DIR)),--sim-bin-dir "$(_EXP_UNIT_SIM_BIN_DIR)")

.PHONY: event-barrier-regression
# Check atomic event mutations, wait scheduling, barrier generations and flush.
event-barrier-regression:
	@test -x "$(PYTHON_BIN)" || { \
		echo 'Python environment missing. Run make setup first.' >&2; exit 2; }
	@"$(PYTHON_BIN)" "$(EVENT_BARRIER_TEST_DIR)/run_event_barrier_regression.py" \
		--sim "$(SIM)" --build-dir "$(EVENT_BARRIER_REGRESSION_BUILD)" \
		--seed "$(EVENT_BARRIER_SEED)" --random-cycles "$(EVENT_BARRIER_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_EVENT_BARRIER_MAKE)" \
		$(if $(strip $(_EVENT_BARRIER_SIM_BIN_DIR)),--sim-bin-dir "$(_EVENT_BARRIER_SIM_BIN_DIR)")

.PHONY: dot-product-regression
# Check exact masked products, reduction, accumulation and enabled-edge latency.
dot-product-regression:
	@test -x "$(PYTHON_BIN)" || { \
		echo 'Python environment missing. Run make setup first.' >&2; exit 2; }
	@test -r "$(DOT_PRODUCT_TEST_DIR)/run_dot_product_regression.py" || { \
		echo 'Dot-product regression missing under src/val/<category>/dot_product.' >&2; exit 2; }
	@"$(PYTHON_BIN)" "$(DOT_PRODUCT_TEST_DIR)/run_dot_product_regression.py" \
		--sim "$(SIM)" --build-dir "$(DOT_PRODUCT_REGRESSION_BUILD)" \
		--seed "$(DOT_PRODUCT_SEED)" --random-cycles "$(DOT_PRODUCT_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_DOT_PRODUCT_MAKE)" \
		$(if $(strip $(_DOT_PRODUCT_SIM_BIN_DIR)),--sim-bin-dir "$(_DOT_PRODUCT_SIM_BIN_DIR)")

.PHONY: dma-engine-regression
# Check DMA scheduling, exact data movement, ownership, cancellation and flush.
dma-engine-regression:
	@test -x "$(PYTHON_BIN)" || { \
		echo 'Python environment missing. Run make setup first.' >&2; exit 2; }
	@test -r "$(DMA_ENGINE_TEST_DIR)/run_dma_engine_regression.py" || { \
		echo 'DMA regression missing under src/val/<category>/dma_engine.' >&2; exit 2; }
	@"$(PYTHON_BIN)" "$(DMA_ENGINE_TEST_DIR)/run_dma_engine_regression.py" \
		--sim "$(SIM)" --build-dir "$(DMA_ENGINE_REGRESSION_BUILD)" \
		--seed "$(DMA_ENGINE_SEED)" --random-cycles "$(DMA_ENGINE_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_DMA_ENGINE_MAKE)" \
		$(if $(strip $(_DMA_ENGINE_SIM_BIN_DIR)),--sim-bin-dir "$(_DMA_ENGINE_SIM_BIN_DIR)")

.PHONY: agu-regression agu-lint
agu-lint:
	@"$(PYTHON_BIN)" "$(AGU_TEST_DIR)/run_agu_lint.py" \
		--verilator "$(AGU_VERILATOR)" --build-dir "$(AGU_LINT_BUILD)"
# Check descriptor legality, signed 1D/2D addresses, metadata and backpressure.
agu-regression:
	@test -x "$(PYTHON_BIN)" || { \
		echo 'Python environment missing. Run make setup first.' >&2; exit 2; }
	@test -r "$(AGU_TEST_DIR)/run_agu_regression.py" || { \
		echo 'AGU regression missing under src/val/<category>/agu.' >&2; exit 2; }
	@"$(PYTHON_BIN)" "$(AGU_TEST_DIR)/run_agu_regression.py" \
		--sim "$(SIM)" --build-dir "$(AGU_REGRESSION_BUILD)" \
		--seed "$(AGU_SEED)" --random-cycles "$(AGU_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_AGU_MAKE)" \
		$(if $(strip $(_AGU_SIM_BIN_DIR)),--sim-bin-dir "$(_AGU_SIM_BIN_DIR)")

.PHONY: accumulator-regression
# Check typed atomic lane updates, numerical status and enabled-cycle recurrence.
accumulator-regression:
	@test -x "$(PYTHON_BIN)" || { \
		echo 'Python environment missing. Run make setup first.' >&2; exit 2; }
	@test -r "$(ACCUMULATOR_TEST_DIR)/run_accumulator_regression.py" || { \
		echo 'Accumulator regression missing under src/val/<category>/accumulator.' >&2; exit 2; }
	@"$(PYTHON_BIN)" "$(ACCUMULATOR_TEST_DIR)/run_accumulator_regression.py" \
		--sim "$(SIM)" --build-dir "$(ACCUMULATOR_REGRESSION_BUILD)" \
		--seed "$(ACCUMULATOR_SEED)" --random-cycles "$(ACCUMULATOR_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_ACCUMULATOR_MAKE)" \
		$(if $(strip $(_ACCUMULATOR_SIM_BIN_DIR)),--sim-bin-dir "$(_ACCUMULATOR_SIM_BIN_DIR)")

.PHONY: width-converter-regression
# Check positional packing/serialization, keep, packet boundaries and cancellation.
width-converter-regression:
	@test -x "$(PYTHON_BIN)" || { \
		echo 'Python environment missing. Run make setup first.' >&2; exit 2; }
	@test -r "$(WIDTH_CONVERTER_TEST_DIR)/run_width_converter_regression.py" || { \
		echo 'Width-converter regression missing under src/val/<category>/width_converter.' >&2; exit 2; }
	@"$(PYTHON_BIN)" "$(WIDTH_CONVERTER_TEST_DIR)/run_width_converter_regression.py" \
		--sim "$(SIM)" --build-dir "$(WIDTH_CONVERTER_REGRESSION_BUILD)" \
		--seed "$(WIDTH_CONVERTER_SEED)" --random-cycles "$(WIDTH_CONVERTER_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_WIDTH_CONVERTER_MAKE)" \
		$(if $(strip $(_WIDTH_CONVERTER_SIM_BIN_DIR)),--sim-bin-dir "$(_WIDTH_CONVERTER_SIM_BIN_DIR)")

.PHONY: stream-fork-regression
# Check multicast delivery, partial completion, replacement and reset.
stream-fork-regression:
	@test -x "$(PYTHON_BIN)" || { \
		echo 'Python environment missing. Run make setup first.' >&2; exit 2; }
	@test -r "$(STREAM_FORK_TEST_DIR)/run_stream_fork_regression.py" || { \
		echo 'Stream-fork regression missing under src/val/<category>/stream_fork.' >&2; exit 2; }
	@"$(PYTHON_BIN)" "$(STREAM_FORK_TEST_DIR)/run_stream_fork_regression.py" \
		--sim "$(SIM)" --build-dir "$(STREAM_FORK_REGRESSION_BUILD)" \
		--seed "$(STREAM_FORK_SEED)" --random-cycles "$(STREAM_FORK_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_STREAM_FORK_MAKE)" \
		$(if $(strip $(_STREAM_FORK_SIM_BIN_DIR)),--sim-bin-dir "$(_STREAM_FORK_SIM_BIN_DIR)")

.PHONY: skid-buffer-regression
# Check zero-cycle bypass, late-stall capture, release and producer stability.
skid-buffer-regression:
	@test -x "$(PYTHON_BIN)" || { \
		echo 'Python environment missing. Run make setup first.' >&2; exit 2; }
	@test -r "$(SKID_BUFFER_TEST_DIR)/run_skid_buffer_regression.py" || { \
		echo 'Skid-buffer regression missing under src/val/<category>/skid_buffer.' >&2; exit 2; }
	@"$(PYTHON_BIN)" "$(SKID_BUFFER_TEST_DIR)/run_skid_buffer_regression.py" \
		--sim "$(SIM)" --build-dir "$(SKID_BUFFER_REGRESSION_BUILD)" \
		--seed "$(SKID_BUFFER_SEED)" --random-cycles "$(SKID_BUFFER_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_SKID_BUFFER_MAKE)" \
		$(if $(strip $(_SKID_BUFFER_SIM_BIN_DIR)),--sim-bin-dir "$(_SKID_BUFFER_SIM_BIN_DIR)")

.PHONY: round-robin-arbiter-regression
# Check rotating fairness, stable pending grants, locks, errors and payloads.
round-robin-arbiter-regression:
	@test -x "$(PYTHON_BIN)" || { \
		echo 'Python environment missing. Run make setup first.' >&2; exit 2; }
	@test -r "$(ROUND_ROBIN_ARBITER_TEST_DIR)/run_round_robin_arbiter_regression.py" || { \
		echo 'Arbiter regression missing under src/val/<category>/round_robin_arbiter.' >&2; exit 2; }
	@"$(PYTHON_BIN)" "$(ROUND_ROBIN_ARBITER_TEST_DIR)/run_round_robin_arbiter_regression.py" \
		--sim "$(SIM)" --build-dir "$(ROUND_ROBIN_ARBITER_REGRESSION_BUILD)" \
		--seed "$(ROUND_ROBIN_ARBITER_SEED)" --random-cycles "$(ROUND_ROBIN_ARBITER_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_ROUND_ROBIN_ARBITER_MAKE)" \
		$(if $(strip $(_ROUND_ROBIN_ARBITER_SIM_BIN_DIR)),--sim-bin-dir "$(_ROUND_ROBIN_ARBITER_SIM_BIN_DIR)")

.PHONY: register-slice-regression
# Check one-cycle forward latency, consume/replace ordering and backpressure.
register-slice-regression:
	@test -x "$(PYTHON_BIN)" || { \
		echo 'Python environment missing. Run make setup first.' >&2; exit 2; }
	@test -r "$(REGISTER_SLICE_TEST_DIR)/run_register_slice_regression.py" || { \
		echo 'Register-slice regression missing under src/val/<category>/register_slice.' >&2; exit 2; }
	@"$(PYTHON_BIN)" "$(REGISTER_SLICE_TEST_DIR)/run_register_slice_regression.py" \
		--sim "$(SIM)" --build-dir "$(REGISTER_SLICE_REGRESSION_BUILD)" \
		--seed "$(REGISTER_SLICE_SEED)" --random-cycles "$(REGISTER_SLICE_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_REGISTER_SLICE_MAKE)" \
		$(if $(strip $(_REGISTER_SLICE_SIM_BIN_DIR)),--sim-bin-dir "$(_REGISTER_SLICE_SIM_BIN_DIR)")

.PHONY: vector-register-file-regression
# Check lane/slice masks, broadcast, concurrent writes and edge-ordered reads.
vector-register-file-regression:
	@test -x "$(PYTHON_BIN)" || { \
		echo 'Python environment missing. Run make setup first.' >&2; exit 2; }
	@test -r "$(VECTOR_REGISTER_FILE_TEST_DIR)/run_vector_register_file_regression.py" || { \
		echo 'Vector-register-file regression missing under src/val/<category>/vector_register_file.' >&2; exit 2; }
	@"$(PYTHON_BIN)" "$(VECTOR_REGISTER_FILE_TEST_DIR)/run_vector_register_file_regression.py" \
		--sim "$(SIM)" --build-dir "$(VECTOR_REGISTER_FILE_REGRESSION_BUILD)" \
		--seed "$(VECTOR_REGISTER_FILE_SEED)" --random-cycles "$(VECTOR_REGISTER_FILE_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_VECTOR_REGISTER_FILE_MAKE)" \
		$(if $(strip $(_VECTOR_REGISTER_FILE_SIM_BIN_DIR)),--sim-bin-dir "$(_VECTOR_REGISTER_FILE_SIM_BIN_DIR)")

.PHONY: register-file-regression
# Check unreset multi-port storage and pre-edge/post-edge read semantics.
register-file-regression:
	@test -x "$(PYTHON_BIN)" || { \
		echo 'Python environment missing. Run make setup first.' >&2; exit 2; }
	@test -r "$(REGISTER_FILE_TEST_DIR)/run_register_file_regression.py" || { \
		echo 'Register-file regression missing under src/val/<category>/register_file.' >&2; exit 2; }
	@"$(PYTHON_BIN)" "$(REGISTER_FILE_TEST_DIR)/run_register_file_regression.py" \
		--sim "$(SIM)" --build-dir "$(REGISTER_FILE_REGRESSION_BUILD)" \
		--seed "$(REGISTER_FILE_SEED)" --random-cycles "$(REGISTER_FILE_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_REGISTER_FILE_MAKE)" \
		$(if $(strip $(_REGISTER_FILE_SIM_BIN_DIR)),--sim-bin-dir "$(_REGISTER_FILE_SIM_BIN_DIR)")

.PHONY: rdu-regression
# Check accepted-advance latency, bubbles, partitioning, stalls and flushes.
rdu-regression:
	@test -x "$(PYTHON_BIN)" || { \
		echo 'Python environment missing. Run make setup first.' >&2; exit 2; }
	@test -r "$(RDU_TEST_DIR)/run_rdu_regression.py" || { \
		echo 'RDU regression missing under src/val/<category>/rdu.' >&2; exit 2; }
	@"$(PYTHON_BIN)" "$(RDU_TEST_DIR)/run_rdu_regression.py" \
		--sim "$(SIM)" --build-dir "$(RDU_REGRESSION_BUILD)" \
		--seed "$(RDU_SEED)" --random-cycles "$(RDU_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_RDU_MAKE)" \
		$(if $(strip $(_RDU_SIM_BIN_DIR)),--sim-bin-dir "$(_RDU_SIM_BIN_DIR)")

.PHONY: performance-counters-regression
# Check weighted events, overflow, thresholds, coherent snapshots and ownership.
performance-counters-regression:
	@test -x "$(PYTHON_BIN)" || { \
		echo 'Python environment missing. Run make setup first.' >&2; exit 2; }
	@test -r "$(PERFORMANCE_COUNTERS_TEST_DIR)/run_performance_counters_regression.py" || { \
		echo 'Performance counters regression missing under src/val/<category>/performance_counters.' >&2; exit 2; }
	@"$(PYTHON_BIN)" "$(PERFORMANCE_COUNTERS_TEST_DIR)/run_performance_counters_regression.py" \
		--sim "$(SIM)" --build-dir "$(PERFORMANCE_COUNTERS_REGRESSION_BUILD)" \
		--seed "$(PERFORMANCE_COUNTERS_SEED)" --random-cycles "$(PERFORMANCE_COUNTERS_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_PERFORMANCE_COUNTERS_MAKE)" \
		$(if $(strip $(_PERFORMANCE_COUNTERS_SIM_BIN_DIR)),--sim-bin-dir "$(_PERFORMANCE_COUNTERS_SIM_BIN_DIR)")

.PHONY: parity-regression
# Check per-granule even parity, fault limitations, X/Z and cone independence.
parity-regression:
	@test -x "$(PYTHON_BIN)" || { \
		echo 'Python environment missing. Run make setup first.' >&2; exit 2; }
	@test -r "$(PARITY_TEST_DIR)/run_parity_regression.py" || { \
		echo 'Parity regression missing under src/val/<category>/parity.' >&2; exit 2; }
	@"$(PYTHON_BIN)" "$(PARITY_TEST_DIR)/run_parity_regression.py" \
		--sim "$(SIM)" --build-dir "$(PARITY_REGRESSION_BUILD)" \
		--seed "$(PARITY_SEED)" --random-cycles "$(PARITY_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_PARITY_MAKE)" \
		$(if $(strip $(_PARITY_SIM_BIN_DIR)),--sim-bin-dir "$(_PARITY_SIM_BIN_DIR)")

.PHONY: packer-regression
# Check element conversion, lane mapping, saturation and elastic ready-valid.
packer-regression:
	@test -x "$(PYTHON_BIN)" || { \
		echo 'Python environment missing. Run make setup first.' >&2; exit 2; }
	@test -r "$(PACKER_TEST_DIR)/run_packer_regression.py" || { \
		echo 'Packer regression missing under src/val/<category>/packer.' >&2; exit 2; }
	@"$(PYTHON_BIN)" "$(PACKER_TEST_DIR)/run_packer_regression.py" \
		--sim "$(SIM)" --build-dir "$(PACKER_REGRESSION_BUILD)" \
		--seed "$(PACKER_SEED)" --random-cycles "$(PACKER_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_PACKER_MAKE)" \
		$(if $(strip $(_PACKER_SIM_BIN_DIR)),--sim-bin-dir "$(_PACKER_SIM_BIN_DIR)")

.PHONY: fifo-regression
# Check single-clock ordering, full replacement, odd depths and reset timing.
fifo-regression:
	@test -x "$(PYTHON_BIN)" || { \
		echo 'Python environment missing. Run make setup first.' >&2; exit 2; }
	@test -r "$(FIFO_TEST_DIR)/run_fifo_regression.py" || { \
		echo 'FIFO regression missing under src/val/<category>/fifo.' >&2; exit 2; }
	@"$(PYTHON_BIN)" "$(FIFO_TEST_DIR)/run_fifo_regression.py" \
		--sim "$(SIM)" --build-dir "$(FIFO_REGRESSION_BUILD)" \
		--seed "$(FIFO_SEED)" --random-cycles "$(FIFO_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_FIFO_MAKE)" \
		$(if $(strip $(_FIFO_SIM_BIN_DIR)),--sim-bin-dir "$(_FIFO_SIM_BIN_DIR)")

.PHONY: ecc-regression
# Check shortened Hamming layout, all single bits, and every practical fault pair.
ecc-regression:
	@test -x "$(PYTHON_BIN)" || { \
		echo 'Python environment missing. Run make setup first.' >&2; exit 2; }
	@test -r "$(ECC_TEST_DIR)/run_ecc_regression.py" || { \
		echo 'ECC regression missing under src/val/<category>/ecc.' >&2; exit 2; }
	@"$(PYTHON_BIN)" "$(ECC_TEST_DIR)/run_ecc_regression.py" \
		--sim "$(SIM)" --build-dir "$(ECC_REGRESSION_BUILD)" \
		--seed "$(ECC_SEED)" --random-cycles "$(ECC_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_ECC_MAKE)" \
		$(if $(strip $(_ECC_SIM_BIN_DIR)),--sim-bin-dir "$(_ECC_SIM_BIN_DIR)")

# Pass values through the environment so Tcl treats paths and hierarchy names
# as data. Keep existing runtime options when enabling the UCLI capture script.
# The script's config endofsim noexit command requires -ucli2Proc at runtime.
# SV-SAIF monitoring also requires -lca on VCS releases that gate this feature.
saif: export MOSAIC_SAIF_FILE = $(abspath $(SAIF_FILE))
saif: export MOSAIC_SAIF_SCOPE = $(SAIF_SCOPE)
saif: export MOSAIC_SAIF_TIME_UNIT = $(SAIF_TIME_UNIT)
saif:
	@test "$(SIM)" = vcs || { \
		echo 'SAIF generation requires SIM=vcs.' >&2; exit 2; }
	@test -r "$(SAIF_SCRIPT)" || { \
		echo 'SAIF_SCRIPT must point to a readable VCS capture script.' >&2; exit 2; }
	@mkdir -p "$(dir $(abspath $(SAIF_FILE)))"
	$(RM) -- "$(abspath $(SAIF_FILE))"
	+$(MAKE) --no-print-directory -C "$(PROJECT_ROOT)" -f Makefile \
		pyuvm SIM_ARGS="$(SIM_ARGS) -lca -ucli -ucli2Proc -i $(SAIF_SCRIPT)"
	@test -s "$(abspath $(SAIF_FILE))" || { \
		echo 'VCS did not generate a nonempty SAIF file.' >&2; exit 2; }
	@printf 'SAIF generated: %s\n' "$(abspath $(SAIF_FILE))"

# Technology scripts stay on the licensed server. Lists are passed as Tcl data.
synth: export MOSAIC_SYNTH_TOP = $(COCOTB_TOPLEVEL)
synth: export MOSAIC_SYNTH_RTL = $(foreach source,$(VERILOG_SOURCES),{$(abspath $(source))})
synth: export MOSAIC_SYNTH_INCLUDES = $(foreach path,$(VERILOG_INCLUDE_DIRS),{$(abspath $(path))})
synth: export MOSAIC_SYNTH_TECH_SETUP = $(if $(strip $(TECH_SETUP_TCL)),$(abspath $(TECH_SETUP_TCL)))
synth: export MOSAIC_SYNTH_DC_SETUP = $(if $(strip $(DC_SETUP_TCL)),$(abspath $(DC_SETUP_TCL)))
synth: export MOSAIC_SYNTH_CONSTRAINTS = $(if $(strip $(SYNTH_CONSTRAINTS)),$(abspath $(SYNTH_CONSTRAINTS)))
synth: export MOSAIC_SYNTH_BUILD = $(abspath $(SYNTH_BUILD))
synth: export MOSAIC_SYNTH_CLOCK_PORT = $(SYNTH_CLOCK_PORT)
synth: export MOSAIC_SYNTH_CLOCK_PERIOD = $(SYNTH_CLOCK_PERIOD)
synth: export MOSAIC_SYNTH_CPUS = $(SYNTH_CPUS)
synth: export MOSAIC_SYNTH_PARAMETERS = $(SYNTH_PARAMETERS)
synth: export MOSAIC_SYNTH_COMPILE_ARGS = $(SYNTH_COMPILE_ARGS)
synth:
	@test -n "$(TECH_SETUP_TCL)" && test -r "$(TECH_SETUP_TCL)" || { \
		echo 'Set TECH_SETUP_TCL to a readable technology/library setup script.' >&2; exit 2; }
	@command -v "$(DC_SHELL)" >/dev/null || { \
		echo 'Design Compiler missing. Set DC_SHELL or add dc_shell to PATH.' >&2; exit 2; }
	@mkdir -p "$(abspath $(SYNTH_BUILD))"
	$(RM) -- "$(abspath $(SYNTH_NETLIST))" "$(abspath $(SYNTH_SDF))" \
		"$(abspath $(SYNTH_BUILD))/netlist/$(COCOTB_TOPLEVEL).sdc" \
		"$(abspath $(SYNTH_BUILD))/db/$(COCOTB_TOPLEVEL).ddc"
	@set -o pipefail; cd "$(abspath $(SYNTH_BUILD))" && \
		"$(DC_SHELL)" $(DC_ARGS) -f "$(SYNTH_SCRIPT)" | tee dc.log
	@for output in "$(abspath $(SYNTH_NETLIST))" "$(abspath $(SYNTH_SDF))" \
		"$(abspath $(SYNTH_BUILD))/netlist/$(COCOTB_TOPLEVEL).sdc" \
		"$(abspath $(SYNTH_BUILD))/db/$(COCOTB_TOPLEVEL).ddc"; do \
		test -s "$$output" || { echo "Synthesis output missing or empty: $$output" >&2; exit 2; }; \
	 done
	@printf 'Synthesized netlist: %s\n' "$(abspath $(SYNTH_NETLIST))"

# Accept an existing synthesized or post-route netlist without rerunning DC.
gate-check:
	@test -n "$(CELL_MODELS)" || { \
		echo 'Set CELL_MODELS to the Verilog simulation models for the mapped cells.' >&2; exit 2; }
	@for source in "$(NETLIST_FILE)" $(CELL_MODELS); do \
		test -r "$$source" && test -s "$$source" || { \
			echo "Netlist/cell model missing or empty: $$source (run make synth for the default netlist)." >&2; exit 2; }; \
	 done
	@if test -n "$(SDF_FILE)"; then \
		test "$(SIM)" = vcs || { echo 'SDF annotation requires SIM=vcs.' >&2; exit 2; }; \
		test -s "$(SDF_FILE)" || { echo 'SDF_FILE missing or empty.' >&2; exit 2; }; \
		case "$(SDF_CORNER)" in min|typ|max) ;; *) echo 'SDF_CORNER must be min, typ, or max.' >&2; exit 2;; esac; \
	fi

gate-sim gate-saif: gate-check
	+$(MAKE) --no-print-directory -C "$(PROJECT_ROOT)" -f Makefile \
		$(if $(filter gate-saif,$@),saif,pyuvm) _GATE_RUN=1 \
		VERILOG_SOURCES="$(abspath $(NETLIST_FILE)) $(foreach source,$(CELL_MODELS),$(abspath $(source)))" \
		SIM_BUILD="$(GATE_SIM_BUILD)" COCOTB_RESULTS_FILE="$(GATE_RESULTS_FILE)" \
		SAIF_FILE="$(GATE_SAIF_FILE)" TEST_SETTLE_NS="$(GATE_SETTLE_NS)"

# Invalidate results even if prerequisites or the new simulation fail.
power-invalidate:
	$(RM) -- "$(POWER_SUMMARY)" "$(POWER_REPORT)" "$(POWER_ACTIVITY_REPORT)"
	$(RM) -- "$(abspath $(POWER_BUILD))/reports/power_hierarchy.rpt" \
		"$(abspath $(POWER_BUILD))/reports/activity_unannotated.rpt" \
		"$(abspath $(POWER_BUILD))/reports/parasitics.rpt" \
		"$(abspath $(POWER_BUILD))/reports/check_timing.rpt" \
		"$(abspath $(POWER_BUILD))/power.log"

power-check:
	@test -n "$(POWER_TECH_SETUP_TCL)" && test -r "$(POWER_TECH_SETUP_TCL)" || { \
		echo 'Set POWER_TECH_SETUP_TCL (or TECH_SETUP_TCL) to a readable PrimeTime library setup script.' >&2; exit 2; }
	@command -v "$(POWER_SHELL)" >/dev/null || { \
		echo 'PrimeTime PX/PrimePower missing. Set POWER_SHELL or add pt_shell to PATH.' >&2; exit 2; }
	@for source in "$(NETLIST_FILE)" "$(POWER_SDC_FILE)"; do \
		test -r "$$source" && test -s "$$source" || { \
			echo "Power input missing or empty: $$source" >&2; exit 2; }; \
	 done
	@if test -n "$(SPEF_FILE)"; then \
		test -r "$(SPEF_FILE)" && test -s "$(SPEF_FILE)" || { \
			echo 'SPEF_FILE missing or empty.' >&2; exit 2; }; \
	fi
	@if test -n "$(POWER_TOOL_SETUP_TCL)"; then \
		test -r "$(POWER_TOOL_SETUP_TCL)" || { echo 'POWER_TOOL_SETUP_TCL not readable.' >&2; exit 2; }; \
	fi

# Run one selected test/campaign and analyze precisely that gate-level activity.
# Rebuild the simulator so changes in netlist/models/SDF/options cannot reuse it.
power: power-invalidate
	@test "$(SIM)" = vcs || { echo 'make power requires SIM=vcs for SAIF capture.' >&2; exit 2; }
	+$(MAKE) --no-print-directory -C "$(PROJECT_ROOT)" -f Makefile power-check gate-check
	+$(MAKE) --no-print-directory -C "$(PROJECT_ROOT)" -f Makefile clean-gate
	+$(MAKE) --no-print-directory -C "$(PROJECT_ROOT)" -f Makefile gate-saif GATE_SAIF_FILE="$(POWER_SAIF_FILE)"
	+$(MAKE) --no-print-directory -C "$(PROJECT_ROOT)" -f Makefile power-report

# Analyze an existing gate SAIF without repeating the simulation.
power-report: export MOSAIC_POWER_TOP = $(COCOTB_TOPLEVEL)
power-report: export MOSAIC_POWER_NETLIST = $(abspath $(NETLIST_FILE))
power-report: export MOSAIC_POWER_TECH_SETUP = $(abspath $(POWER_TECH_SETUP_TCL))
power-report: export MOSAIC_POWER_TOOL_SETUP = $(if $(strip $(POWER_TOOL_SETUP_TCL)),$(abspath $(POWER_TOOL_SETUP_TCL)))
power-report: export MOSAIC_POWER_SDC = $(abspath $(POWER_SDC_FILE))
power-report: export MOSAIC_POWER_SPEF = $(if $(strip $(SPEF_FILE)),$(abspath $(SPEF_FILE)))
power-report: export MOSAIC_POWER_SAIF = $(abspath $(POWER_SAIF_FILE))
power-report: export MOSAIC_POWER_STRIP_PATH = $(POWER_SAIF_STRIP_PATH)
power-report: export MOSAIC_POWER_BUILD = $(abspath $(POWER_BUILD))
power-report: power-invalidate
	+$(MAKE) --no-print-directory -C "$(PROJECT_ROOT)" -f Makefile power-check
	@test -r "$(POWER_SAIF_FILE)" && test -s "$(POWER_SAIF_FILE)" || { \
		echo 'POWER_SAIF_FILE missing or empty. Run make power or make gate-saif first.' >&2; exit 2; }
	@mkdir -p "$(abspath $(POWER_BUILD))"
	@set -o pipefail; cd "$(abspath $(POWER_BUILD))" && \
		"$(POWER_SHELL)" $(POWER_ARGS) -f "$(POWER_SCRIPT)" | tee power.log
	@"$(PYTHON)" "$(POWER_SUMMARY_SCRIPT)" \
		--report "$(POWER_REPORT)" --activity-report "$(POWER_ACTIVITY_REPORT)" \
		--saif "$(abspath $(POWER_SAIF_FILE))" --output "$(POWER_SUMMARY)" \
		--design "$(COCOTB_TOPLEVEL)" --netlist "$(abspath $(NETLIST_FILE))" \
		--sdc "$(abspath $(POWER_SDC_FILE))" --spef "$(SPEF_FILE)" --sdf "$(SDF_FILE)" \
		--test-modules "$(COCOTB_TEST_MODULES)" --test-filter "$(COCOTB_TEST_FILTER)"

setup:
	"$(PYTHON)" -m venv "$(VENV)"
	"$(VENV)/bin/python" -m pip install -r "$(PROJECT_ROOT)/requirements.txt"

clean:
	$(RM) -r -- "$(SIM_BUILD)"
	$(RM) -- "$(COCOTB_RESULTS_FILE)" "$(SAIF_FILE)"

clean-gate:
	$(RM) -r -- "$(GATE_SIM_BUILD)"
	$(RM) -- "$(GATE_RESULTS_FILE)" "$(GATE_SAIF_FILE)"

clean-synth:
	$(RM) -r -- "$(SYNTH_BUILD)"

clean-power:
	$(RM) -r -- "$(POWER_BUILD)"

help:
	@printf '%s\n' \
		'make setup           Install pinned PyUVM and cocotb into .venv' \
		'make [pyuvm|sim]     Run PyUVM with VCS (default: counter)' \
		'make counter-regression  Run the counter specification matrix with PyUVM' \
		'make clock-gate-regression  Check clock gate edges, pulses, and coverage' \
		'make decoder-regression  Check all decoder encodings and legal pairs' \
		'make dff-regression  Check DFF reset/enable variants and output events' \
		'make isolation-cell-regression  Check isolation, clamp, and X/Z behavior' \
		'make lane-mask-regression  Check lane activity, isolation, and write masks' \
		'make level-shifter-regression  Check four-state buses in both directions' \
		'make mux-regression  Check selected data, invalid defaults, and coverage' \
		'make operand-isolation-regression  Check operand clamps, activity, and X/Z' \
		'make priority-encoder-regression  Check priority, contention, and X/Z requests' \
		'make reset-synchronizer-regression  Check reset assertion and synchronized release' \
		'make retention-register-regression  Check portable save/restore and protocol' \
		'make write-gate-regression  Check write masks and register/memory state' \
		'make async-fifo-regression  Check dual-clock ordering, resets, and coverage' \
		'make bypass-network-regression  Check sparse forwarding, capture, and flush' \
		'make context-memory-regression  Check masked contexts, commit, and raw reads' \
		'make context-sequencer-regression  Check context control, loops, and runtime safety' \
		'make data-aligner-regression  Check byte alignment, spill, and ready-valid timing' \
		'make ecc-regression   Check SECDED layout, correction, and every fault pair' \
		'make fifo-regression  Check synchronous FIFO ordering, resets, and full replacement' \
		'make packer-regression  Check element widths, saturation, lanes, and elastic timing' \
		'make parity-regression  Check granular parity, fault detection limits, and X/Z' \
		'make performance-counters-regression  Check weighted counters, snapshots and thresholds' \
		'make rdu-regression   Check allocated delays, bubbles, stalls and context boundaries' \
		'make vector-register-file-regression  Check lane/slice masks, broadcasts and concurrent writes' \
		'make register-file-regression  Check multi-port storage and read-before-write timing' \
		'make register-slice-regression  Check elastic one-cycle latency and consume/replace' \
		'make round-robin-arbiter-regression  Check cyclic grants, backpressure, locks and fairness' \
		'make skid-buffer-regression  Check bypass, late stalls and registered backpressure' \
		'make stream-join-regression  Check atomic joins, final arrival and optional inputs' \
		'make accumulator-regression  Check typed atomic lanes, arithmetic, status and clock enables' \
		'make agu-regression  Check signed address sequences, descriptors, errors and backpressure' \
		'make agu-lint  Lint AGU parameter profiles without synthesis' \
		'make predicate-unit-regression  Check predicate bank commands and state' \
		'make predicate-unit-static  Lint and synthesize predicate banks' \
		'make predicate-unit-formal  Prove predicate state/response equivalence' \
		'make vector-reduction-regression  Check masked integer reductions and timing' \
		'make vector-reduction-static  Lint and synthesize reduction profiles' \
		'make vector-reduction-formal  Prove small-width reductions and bounded timing' \
		'make vector-lane-regression  Check lane operations, predication and path alignment' \
		'make vector-lane-static  Lint and synthesize vector lane profiles' \
		'make vector-lane-formal  Prove tractable vector lane profiles' \
		'make scalar-alu-static  Lint and synthesize combinational ALU profiles' \
		'make scalar-alu-formal  Prove ALU profiles with Yosys/slang' \
		'make scalar-alu-regression  Check scalar operations, flags and feature modes' \
		'make noc-router-regression  Check routes, wormhole ownership, credits and protection' \
		'make noc-router-mesh-regression  Check end-to-end delivery in 2x2 and 4x4 meshes' \
		'make noc-router-topology  Analyze dimension-order channel dependencies' \
		'make multiplier-regression  Check exact scalar products, mixed modes and pipeline holds' \
		'make mac-regression  Check scalar multiply-add, saturation and enabled-edge timing' \
		'make lut-unit-regression  Check programmable tables, interpolation and bank lifecycle' \
		'make rsqrt-unit-regression  Check inverse square root, epsilon and seed protection' \
		'make reciprocal-unit-regression  Check fixed-point Newton reciprocal and seed protection' \
		'make polynomial-unit-regression  Check Horner arithmetic and coefficient lifecycle' \
		'make loop-controller-regression  Check nested loops, pacing and runtime safe points' \
		'make tile-power-controller-regression  Check idle policy, wake, retention and power sequencing' \
		'make tile-network-interface-regression  Check packetization, reassembly, credits and epochs' \
		'make local-switch-regression  Check static routes, sparse edges and multicast copies' \
		'make scratchpad-controller-regression  Check bank mapping, arbitration and ordered clients' \
		'make scratchpad-bank-regression  Check ordered subword memory, protection and recovery' \
		'make stream-formatter-regression  Check canonical frames, lanes and elastic output' \
		'make store-engine-regression  Check atomic writes, framing and ordered completions' \
		'make load-engine-regression  Check tagged reads, ordered retirement and fatal drain' \
		'make configuration-network-regression Check configuration delivery and commit with PyUVM' \
		'make predicate-network-regression Check predicate routing and alignment with PyUVM' \
		'make static-mesh-regression Check static mesh RTL with PyUVM' \
		'make mst-regression        Check memory/stream tile RTL with PyUVM' \
		'make banked-scratchpad-regression Check region-managed scratchpad with real banks' \
		'make vct-regression     Check vector tile execution and shell integration' \
		'make bct-regression     Check scalar tile execution and shell integration' \
		'make tile-shell-regression Check context, ownership, transfer and power integration' \
		'make exp-unit-regression  Check fixed-point exponentials and elastic responses' \
		'make exp-unit-images      Verify generated endpoint and log2(e) artifacts' \
		'make event-barrier-regression  Check events, one-shot waits and reusable barriers' \
		'make dot-product-regression  Check exact masked products, arithmetic and pipeline latency' \
		'make dma-engine-regression  Check multi-channel DMA, protection, data, cancellation and events' \
		'make width-converter-regression  Check packing, serialization, keep and packet boundaries' \
		'make stream-fork-regression  Check multicast delivery, masks and partial completion' \
		'make sram-wrapper-regression  Check masked 1RW memory, latency, credits and backends' \
		'make saif            Run PyUVM with VCS and write switching activity' \
		'make synth           Synthesize RTL with Design Compiler' \
		'make gate-sim        Run PyUVM on NETLIST_FILE with CELL_MODELS' \
		'make gate-saif       Run the gate simulation and write its SAIF' \
		'make power           Run a gate test, capture SAIF, report power and energy' \
		'make power-report    Analyze POWER_SAIF_FILE without rerunning the test' \
		'make clean           Remove the selected build, results, and SAIF file' \
		'make clean-gate      Remove the selected gate simulation outputs' \
		'make clean-synth     Remove the selected synthesis outputs' \
		'make clean-power     Remove the selected power reports and summary' \
		'' \
		'Overrides: SIM, VCS_BIN_DIR, COCOTB_TOPLEVEL, COCOTB_TEST_MODULES,' \
		'           VERILOG_SOURCES, COMPILE_ARGS, SIM_ARGS, COCOTB_PLUSARGS,' \
		'           COCOTB_TEST_FILTER, VENV, PYTHON_BIN, SIM_BUILD,' \
		'           PYUVM_TEST_DIR,' \
		'           SAIF_FILE, SAIF_SCOPE, SAIF_TIME_UNIT, VERILOG_INCLUDE_DIRS' \
		'Synthesis: DC_SHELL, DC_ARGS, TECH_SETUP_TCL, DC_SETUP_TCL,' \
		'           SYNTH_BUILD, SYNTH_CONSTRAINTS, SYNTH_CLOCK_PORT,' \
		'           SYNTH_CLOCK_PERIOD, SYNTH_CPUS, SYNTH_PARAMETERS,' \
		'           SYNTH_COMPILE_ARGS' \
		'Gate sim:  NETLIST_FILE, CELL_MODELS, SDF_FILE, SDF_SCOPE, SDF_CORNER,' \
		'           GATE_SIM_BUILD, GATE_RESULTS_FILE, GATE_SAIF_FILE,' \
		'           GATE_SETTLE_NS, TEST_CLOCK_PERIOD_NS' \
		'Power:     POWER_SHELL, POWER_ARGS, POWER_TECH_SETUP_TCL,' \
		'           POWER_TOOL_SETUP_TCL, POWER_SDC_FILE, SPEF_FILE,' \
		'           POWER_SAIF_FILE, POWER_SAIF_STRIP_PATH, POWER_BUILD' \
		'Counter:   COUNTER_REGRESSION_BUILD, COUNTER_RANDOM_CYCLES, COUNTER_SEED' \
		'Clock gate: CLOCK_GATE_REGRESSION_BUILD, CLOCK_GATE_RANDOM_CYCLES, CLOCK_GATE_SEED' \
		'Decoder:   DECODER_REGRESSION_BUILD, DECODER_RANDOM_CYCLES, DECODER_SEED' \
		'DFF:       DFF_REGRESSION_BUILD, DFF_RANDOM_CYCLES, DFF_SEED' \
		'Isolation: ISOLATION_CELL_REGRESSION_BUILD, ISOLATION_CELL_RANDOM_CYCLES,' \
		'           ISOLATION_CELL_SEED' \
		'Lane mask: LANE_MASK_REGRESSION_BUILD, LANE_MASK_RANDOM_CYCLES, LANE_MASK_SEED' \
		'Level shifter: LEVEL_SHIFTER_REGRESSION_BUILD, LEVEL_SHIFTER_RANDOM_CYCLES,' \
		'               LEVEL_SHIFTER_SEED' \
		'Mux:       MUX_REGRESSION_BUILD, MUX_RANDOM_CYCLES, MUX_SEED' \
		'Operand isolation: OPERAND_ISOLATION_REGRESSION_BUILD,' \
		'                   OPERAND_ISOLATION_RANDOM_CYCLES, OPERAND_ISOLATION_SEED' \
		'Priority encoder: PRIORITY_ENCODER_REGRESSION_BUILD,' \
		'                  PRIORITY_ENCODER_RANDOM_CYCLES, PRIORITY_ENCODER_SEED' \
		'Reset synchronizer: RESET_SYNCHRONIZER_REGRESSION_BUILD,' \
		'                    RESET_SYNCHRONIZER_RANDOM_CYCLES, RESET_SYNCHRONIZER_SEED' \
		'Retention register: RETENTION_REGISTER_REGRESSION_BUILD,' \
		'                    RETENTION_REGISTER_RANDOM_CYCLES, RETENTION_REGISTER_SEED' \
		'Write gate: WRITE_GATE_REGRESSION_BUILD, WRITE_GATE_RANDOM_CYCLES, WRITE_GATE_SEED' \
		'Async FIFO: ASYNC_FIFO_REGRESSION_BUILD, ASYNC_FIFO_RANDOM_CYCLES, ASYNC_FIFO_SEED' \
		'Bypass network: BYPASS_NETWORK_REGRESSION_BUILD, BYPASS_NETWORK_RANDOM_CYCLES,' \
		'                BYPASS_NETWORK_SEED' \
		'Context memory: CONTEXT_MEMORY_REGRESSION_BUILD, CONTEXT_MEMORY_RANDOM_CYCLES,' \
		'                CONTEXT_MEMORY_SEED' \
		'Context sequencer: CONTEXT_SEQUENCER_REGRESSION_BUILD, CONTEXT_SEQUENCER_RANDOM_CYCLES,' \
		'                   CONTEXT_SEQUENCER_SEED' \
		'Data aligner: DATA_ALIGNER_REGRESSION_BUILD, DATA_ALIGNER_RANDOM_CYCLES,' \
		'              DATA_ALIGNER_SEED' \
		'ECC:       ECC_REGRESSION_BUILD, ECC_RANDOM_CYCLES, ECC_SEED' \
		'FIFO:      FIFO_REGRESSION_BUILD, FIFO_RANDOM_CYCLES, FIFO_SEED' \
		'Packer:    PACKER_REGRESSION_BUILD, PACKER_RANDOM_CYCLES, PACKER_SEED' \
		'Parity:    PARITY_REGRESSION_BUILD, PARITY_RANDOM_CYCLES, PARITY_SEED' \
		'Performance counters: PERFORMANCE_COUNTERS_REGRESSION_BUILD,' \
		'                      PERFORMANCE_COUNTERS_RANDOM_CYCLES, PERFORMANCE_COUNTERS_SEED' \
		'RDU:       RDU_REGRESSION_BUILD, RDU_RANDOM_CYCLES, RDU_SEED' \
		'Vector register file: VECTOR_REGISTER_FILE_REGRESSION_BUILD, VECTOR_REGISTER_FILE_RANDOM_CYCLES,' \
		'                      VECTOR_REGISTER_FILE_SEED' \
		'Register file: REGISTER_FILE_REGRESSION_BUILD, REGISTER_FILE_RANDOM_CYCLES, REGISTER_FILE_SEED' \
		'Register slice: REGISTER_SLICE_REGRESSION_BUILD, REGISTER_SLICE_RANDOM_CYCLES, REGISTER_SLICE_SEED' \
		'Round-robin arbiter: ROUND_ROBIN_ARBITER_REGRESSION_BUILD,' \
		'                    ROUND_ROBIN_ARBITER_RANDOM_CYCLES, ROUND_ROBIN_ARBITER_SEED' \
		'Skid buffer: SKID_BUFFER_REGRESSION_BUILD, SKID_BUFFER_RANDOM_CYCLES, SKID_BUFFER_SEED' \
		'Stream join: STREAM_JOIN_REGRESSION_BUILD, STREAM_JOIN_RANDOM_CYCLES, STREAM_JOIN_SEED' \
		'Multiplier: MULTIPLIER_REGRESSION_BUILD, MULTIPLIER_RANDOM_CYCLES, MULTIPLIER_SEED,' \
		'            MULTIPLIER_HDL_ASSERTIONS' \
		'MAC:       MAC_REGRESSION_BUILD, MAC_RANDOM_CYCLES, MAC_SEED, MAC_HDL_ASSERTIONS' \
		'Accumulator: ACCUMULATOR_REGRESSION_BUILD, ACCUMULATOR_RANDOM_CYCLES,' \
		'             ACCUMULATOR_SEED, ACCUMULATOR_HDL_ASSERTIONS' \
		'Width converter: WIDTH_CONVERTER_REGRESSION_BUILD, WIDTH_CONVERTER_RANDOM_CYCLES,' \
		'                 WIDTH_CONVERTER_SEED' \
		'Stream fork: STREAM_FORK_REGRESSION_BUILD, STREAM_FORK_RANDOM_CYCLES, STREAM_FORK_SEED' \
		'SRAM wrapper: SRAM_WRAPPER_REGRESSION_BUILD, SRAM_WRAPPER_RANDOM_CYCLES,' \
		'              SRAM_WRAPPER_SEED; SRAM_BACKEND_SOURCE selects the backend file'
endif

TILE_SHELL_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/tile_shell/regression
TILE_SHELL_RANDOM_CYCLES ?= 2000
TILE_SHELL_SEED ?= 20261025
_TILE_SHELL_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_TILE_SHELL_MAKE := $(MAKE)
.PHONY: tile-shell-regression
tile-shell-regression:
	@"$(PYTHON_BIN)" "$(PROJECT_ROOT)/src/val/mosaic_blocks/tile_shell/run_tile_shell_regression.py" \
		--sim "$(SIM)" --build-dir "$(TILE_SHELL_REGRESSION_BUILD)" \
		--seed "$(TILE_SHELL_SEED)" --random-cycles "$(TILE_SHELL_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" \
		--make "$(_TILE_SHELL_MAKE)" \
		$(if $(strip $(_TILE_SHELL_SIM_BIN_DIR)),--sim-bin-dir "$(_TILE_SHELL_SIM_BIN_DIR)")

BCT_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/bct/regression
BCT_RANDOM_CYCLES ?= 2000
BCT_SEED ?= 20261025
_BCT_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
.PHONY: bct-regression
bct-regression:
	@"$(PYTHON_BIN)" "$(PROJECT_ROOT)/src/val/mosaic_blocks/bct/run_bct_regression.py" \
		--sim "$(SIM)" --build-dir "$(BCT_REGRESSION_BUILD)" \
		--seed "$(BCT_SEED)" --random-cycles "$(BCT_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(MAKE)" \
		$(if $(strip $(_BCT_SIM_BIN_DIR)),--sim-bin-dir "$(_BCT_SIM_BIN_DIR)")

VCT_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/vct/regression
VCT_RANDOM_CYCLES ?= 2000
VCT_SEED ?= 20261026
_VCT_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
.PHONY: vct-regression
vct-regression:
	@"$(PYTHON_BIN)" "$(PROJECT_ROOT)/src/val/mosaic_blocks/vct/run_vct_regression.py" \
		--sim "$(SIM)" --build-dir "$(VCT_REGRESSION_BUILD)" \
		--seed "$(VCT_SEED)" --random-cycles "$(VCT_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(MAKE)" \
		$(if $(strip $(_VCT_SIM_BIN_DIR)),--sim-bin-dir "$(_VCT_SIM_BIN_DIR)")

BANKED_SCRATCHPAD_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/banked_scratchpad/regression
BANKED_SCRATCHPAD_RANDOM_CYCLES ?= 2000
BANKED_SCRATCHPAD_SEED ?= 20261026
_BANKED_SCRATCHPAD_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
.PHONY: banked-scratchpad-regression
banked-scratchpad-regression:
	@"$(PYTHON_BIN)" "$(PROJECT_ROOT)/src/val/mosaic_blocks/banked_scratchpad/run_banked_scratchpad_regression.py" \
		--sim "$(SIM)" --build-dir "$(BANKED_SCRATCHPAD_REGRESSION_BUILD)" \
		--seed "$(BANKED_SCRATCHPAD_SEED)" --random-cycles "$(BANKED_SCRATCHPAD_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(MAKE)" \
		$(if $(strip $(_BANKED_SCRATCHPAD_SIM_BIN_DIR)),--sim-bin-dir "$(_BANKED_SCRATCHPAD_SIM_BIN_DIR)")

MST_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/mst/regression
MST_RANDOM_CYCLES ?= 30
MST_SEED ?= 20261025
_MST_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
.PHONY: mst-regression
mst-regression:
	@"$(PYTHON_BIN)" "$(PROJECT_ROOT)/src/val/mosaic_blocks/mst/run_mst_regression.py" \
		--sim "$(SIM)" --build-dir "$(MST_REGRESSION_BUILD)" \
		--seed "$(MST_SEED)" --random-cycles "$(MST_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(MAKE)" \
		$(if $(strip $(_MST_SIM_BIN_DIR)),--sim-bin-dir "$(_MST_SIM_BIN_DIR)")

STATIC_MESH_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/static_mesh/regression
STATIC_MESH_SEED ?= 20261025
STATIC_MESH_RANDOM_CYCLES ?= 1000
_STATIC_MESH_SIM_BIN_DIR := $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
.PHONY: static-mesh-regression
static-mesh-regression:
	@"$(PYTHON_BIN)" "$(PROJECT_ROOT)/src/val/mosaic_blocks/static_mesh/run_static_mesh_regression.py" \
		--sim "$(SIM)" --build-dir "$(STATIC_MESH_REGRESSION_BUILD)" \
		--seed "$(STATIC_MESH_SEED)" --random-cycles "$(STATIC_MESH_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(MAKE)" \
		$(if $(strip $(_STATIC_MESH_SIM_BIN_DIR)),--sim-bin-dir "$(_STATIC_MESH_SIM_BIN_DIR)")

PREDICATE_NETWORK_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/predicate_network/regression
PREDICATE_NETWORK_SEED ?= 20261025
PREDICATE_NETWORK_RANDOM_CYCLES ?= 1000
_PREDICATE_NETWORK_SIM_BIN_DIR := $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
.PHONY: predicate-network-regression
predicate-network-regression:
	@"$(PYTHON_BIN)" "$(PROJECT_ROOT)/src/val/mosaic_blocks/predicate_network/run_predicate_network_regression.py" \
		--sim "$(SIM)" --build-dir "$(PREDICATE_NETWORK_REGRESSION_BUILD)" \
		--seed "$(PREDICATE_NETWORK_SEED)" --random-cycles "$(PREDICATE_NETWORK_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(MAKE)" \
		$(if $(strip $(_PREDICATE_NETWORK_SIM_BIN_DIR)),--sim-bin-dir "$(_PREDICATE_NETWORK_SIM_BIN_DIR)")

CONFIGURATION_NETWORK_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/configuration_network/regression
CONFIGURATION_NETWORK_SEED ?= 20261026
CONFIGURATION_NETWORK_RANDOM_CYCLES ?= 1000
_CONFIGURATION_NETWORK_SIM_BIN_DIR := $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
.PHONY: configuration-network-regression
configuration-network-regression:
	@"$(PYTHON_BIN)" "$(PROJECT_ROOT)/src/val/mosaic_blocks/configuration_network/run_configuration_network_regression.py" \
		--sim "$(SIM)" --build-dir "$(CONFIGURATION_NETWORK_REGRESSION_BUILD)" \
		--seed "$(CONFIGURATION_NETWORK_SEED)" --random-cycles "$(CONFIGURATION_NETWORK_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(MAKE)" \
		$(if $(strip $(_CONFIGURATION_NETWORK_SIM_BIN_DIR)),--sim-bin-dir "$(_CONFIGURATION_NETWORK_SIM_BIN_DIR)")

# The generated file list is an architectural release artifact. The generator's
# Python source owns the dependency closure; no JSON dependency loader is used.
CLUSTER_DESCRIPTOR ?= $(PROJECT_ROOT)/src/gen/cluster/mvp.toml
CLUSTER_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/cluster/regression
CLUSTER_SEED ?= 20261026
CLUSTER_RANDOM_CYCLES ?= 1000
.PHONY: cluster-generate cluster-regression
cluster-generate:
	@"$(PYTHON_BIN)" "$(PROJECT_ROOT)/src/gen/cluster/generate.py" --descriptor "$(CLUSTER_DESCRIPTOR)"

cluster-regression:
	@"$(PYTHON_BIN)" "$(PROJECT_ROOT)/src/val/mosaic_blocks/cluster/run_cluster_regression.py" \
		--sim "$(SIM)" --build-dir "$(CLUSTER_REGRESSION_BUILD)" \
		--seed "$(CLUSTER_SEED)" --random-cycles "$(CLUSTER_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(MAKE)"

SFT_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/sft/regression
SFT_SEED ?= 20261027
SFT_RANDOM_CYCLES ?= 1000
.PHONY: sft-regression
sft-regression:
	@"$(PYTHON_BIN)" "$(PROJECT_ROOT)/src/val/mosaic_blocks/sft/run_sft_regression.py" \
		--sim "$(SIM)" --build-dir "$(SFT_REGRESSION_BUILD)" \
		--seed "$(SFT_SEED)" --random-cycles "$(SFT_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(MAKE)"

.PHONY: sft-generate
sft-generate:
	@"$(PYTHON_BIN)" "$(PROJECT_ROOT)/src/gen/sft/generate.py"

CPT_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/cpt/regression
CPT_SEED ?= 20261027
CPT_RANDOM_CYCLES ?= 1000
.PHONY: cpt-regression cpt-generate
cpt-regression:
	@"$(PYTHON_BIN)" "$(PROJECT_ROOT)/src/val/mosaic_blocks/cpt/run_cpt_regression.py" \
		--sim "$(SIM)" --build-dir "$(CPT_REGRESSION_BUILD)" \
		--seed "$(CPT_SEED)" --random-cycles "$(CPT_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(MAKE)"

cpt-generate:
	@"$(PYTHON_BIN)" "$(PROJECT_ROOT)/src/gen/cpt/generate.py"

GLOBAL_NOC_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/global_noc/regression
GLOBAL_NOC_SEED ?= 20261027
GLOBAL_NOC_RANDOM_CYCLES ?= 2000
GLOBAL_NOC_REGRESSION_ARGS ?=
.PHONY: global-noc-generate global-noc-regression
global-noc-generate:
	@"$(PYTHON_BIN)" "$(PROJECT_ROOT)/src/gen/global_noc/generate.py"
global-noc-regression:
	@"$(PYTHON_BIN)" "$(PROJECT_ROOT)/src/val/mosaic_blocks/global_noc/run_global_noc_regression.py" \
		--sim "$(SIM)" --build-dir "$(GLOBAL_NOC_REGRESSION_BUILD)" \
		--seed "$(GLOBAL_NOC_SEED)" --random-cycles "$(GLOBAL_NOC_RANDOM_CYCLES)" \
		$(GLOBAL_NOC_REGRESSION_ARGS)

# Normalized runtime policy uses external Python peers; no synthesis or HDL assertions.
RUNTIME_CONTROLLER_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/runtime_controller/regression
RUNTIME_CONTROLLER_SEED ?= 20261027
RUNTIME_CONTROLLER_RANDOM_CYCLES ?= 2000
RUNTIME_CONTROLLER_REGRESSION_ARGS ?=
.PHONY: runtime-controller-generate runtime-controller-regression
runtime-controller-generate:
	@"$(PYTHON_BIN)" "$(PROJECT_ROOT)/src/gen/runtime_controller/generate.py"
runtime-controller-regression:
	@"$(PYTHON_BIN)" "$(PROJECT_ROOT)/src/val/mosaic_blocks/runtime_controller/run_runtime_controller_regression.py" \
		--sim "$(SIM)" --build-dir "$(RUNTIME_CONTROLLER_REGRESSION_BUILD)" \
		--seed "$(RUNTIME_CONTROLLER_SEED)" --random-cycles "$(RUNTIME_CONTROLLER_RANDOM_CYCLES)" \
		--make "$(MAKE)" $(if $(filter vcs,$(SIM)),$(if $(VCS_BIN_DIR),--sim-bin-dir "$(VCS_BIN_DIR)"),$(if $(ICARUS_BIN_DIR),--sim-bin-dir "$(ICARUS_BIN_DIR)")) \
		$(RUNTIME_CONTROLLER_REGRESSION_ARGS)

# AON sequencing, released tile controllers and physical Python peers only.
CLUSTER_POWER_MANAGER_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/cluster_power_manager/regression
CLUSTER_POWER_MANAGER_SEED ?= 20261028
CLUSTER_POWER_MANAGER_RANDOM_CYCLES ?= 1000
CLUSTER_POWER_MANAGER_REGRESSION_ARGS ?=
.PHONY: cluster-power-manager-generate cluster-power-manager-regression
cluster-power-manager-generate:
	@"$(PYTHON_BIN)" "$(PROJECT_ROOT)/src/gen/cluster_power_manager/generate.py"
cluster-power-manager-regression:
	@"$(PYTHON_BIN)" "$(PROJECT_ROOT)/src/val/mosaic_blocks/cluster_power_manager/run_cluster_power_manager_regression.py" \
		--sim "$(SIM)" --build-dir "$(CLUSTER_POWER_MANAGER_REGRESSION_BUILD)" \
		--seed "$(CLUSTER_POWER_MANAGER_SEED)" --random-cycles "$(CLUSTER_POWER_MANAGER_RANDOM_CYCLES)" \
		--make "$(MAKE)" $(if $(filter vcs,$(SIM)),$(if $(VCS_BIN_DIR),--sim-bin-dir "$(VCS_BIN_DIR)"),$(if $(ICARUS_BIN_DIR),--sim-bin-dir "$(ICARUS_BIN_DIR)")) \
		$(CLUSTER_POWER_MANAGER_REGRESSION_ARGS)
