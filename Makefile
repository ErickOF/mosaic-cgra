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
AGU_TEST_DIR := $(firstword $(wildcard $(PROJECT_ROOT)/src/val/*/agu))
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
_AGU_SOURCES := $(PROJECT_ROOT)/src/rtl/building_blocks/agu_pkg.sv $(PROJECT_ROOT)/src/rtl/common/counter.sv $(PROJECT_ROOT)/src/rtl/common/dff.sv $(PROJECT_ROOT)/src/rtl/common/operand_isolation.sv $(PROJECT_ROOT)/src/rtl/building_blocks/agu.sv
_RTL_SOURCES_agu := $(_AGU_SOURCES)
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
AGU_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/agu/regression
AGU_RANDOM_CYCLES ?= 2000
AGU_SEED ?= 20261020
export AGU_HDL_ASSERTIONS ?= 1
_AGU_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
_AGU_MAKE := $(MAKE)
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
# Assertions use only architectural ports and a precision-tick observation delay.
# Keep this verification fixture out of synthesis and mapped-netlist compilation.
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

.PHONY: agu-regression
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
		'Accumulator: ACCUMULATOR_REGRESSION_BUILD, ACCUMULATOR_RANDOM_CYCLES,' \
		'             ACCUMULATOR_SEED, ACCUMULATOR_HDL_ASSERTIONS' \
		'Width converter: WIDTH_CONVERTER_REGRESSION_BUILD, WIDTH_CONVERTER_RANDOM_CYCLES,' \
		'                 WIDTH_CONVERTER_SEED' \
		'Stream fork: STREAM_FORK_REGRESSION_BUILD, STREAM_FORK_RANDOM_CYCLES, STREAM_FORK_SEED' \
		'SRAM wrapper: SRAM_WRAPPER_REGRESSION_BUILD, SRAM_WRAPPER_RANDOM_CYCLES,' \
		'              SRAM_WRAPPER_SEED; SRAM_BACKEND_SOURCE selects the backend file'
endif
