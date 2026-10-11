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
# Add the selected test directory to the Python import path used by cocotb.
PYUVM_TEST_DIR ?= $(PROJECT_ROOT)/verif/pyuvm
COUNTER_TEST_DIR := $(PROJECT_ROOT)/verif/pyuvm
VERILOG_SOURCES ?= $(PROJECT_ROOT)/src/rtl/common/$(COCOTB_TOPLEVEL).sv
SIM_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/$(COCOTB_TOPLEVEL)
COCOTB_RESULTS_FILE ?= $(SIM_BUILD)/results.xml
SAIF_FILE ?= $(SIM_BUILD)/$(COCOTB_TOPLEVEL).saif
SAIF_SCOPE ?= $(COCOTB_TOPLEVEL)
SAIF_TIME_UNIT ?= 1e-9
SAIF_SCRIPT := $(PROJECT_ROOT)/verif/vcs/saif.tcl

DC_SHELL ?= dc_shell
DC_ARGS ?=
TECH_SETUP_TCL ?=
DC_SETUP_TCL ?=
SYNTH_SCRIPT := $(PROJECT_ROOT)/synth/run.tcl
SYNTH_CONSTRAINTS ?= $(PROJECT_ROOT)/constraints/timing.sdc
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
POWER_SCRIPT := $(PROJECT_ROOT)/power/run.tcl
POWER_SUMMARY_SCRIPT := $(PROJECT_ROOT)/power/summarize.py
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
COUNTER_REGRESSION_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/counter/regression
COUNTER_RANDOM_CYCLES ?= 2000
COUNTER_SEED ?= 20261010
_COUNTER_SIM_BIN_DIR = $(if $(filter vcs,$(SIM)),$(VCS_BIN_DIR),$(ICARUS_BIN_DIR))
# GNU make treats a direct MAKE reference as recursive, even inside a Python
# command. Indirection keeps -n from running the wrapper and deleting reports.
_COUNTER_MAKE := $(MAKE)

export PYTHONPATH := $(PYUVM_TEST_DIR)$(if $(PYTHONPATH),:$(PYTHONPATH))
CUSTOM_COMPILE_DEPS += $(PROJECT_ROOT)/Makefile

# Load cocotb only in the simulation subprocess so setup/help/clean work
# before the Python environment or licensed simulator has been installed.
ifeq ($(_COCOTB_RUN),1)
# Treat caller options as a starting value so cocotb can append mandatory
# backend flags even when COMPILE_ARGS was supplied on the command line.
_USER_COMPILE_ARGS := $(COMPILE_ARGS)
override undefine COMPILE_ARGS
COMPILE_ARGS := $(_USER_COMPILE_ARGS)
ifeq ($(_GATE_RUN),1)
ifneq ($(strip $(SDF_FILE)),)
# VCS unified SDF annotation is a compilation option, not a simv option.
COMPILE_ARGS += -sdf $(SDF_CORNER):$(SDF_SCOPE):$(abspath $(SDF_FILE))
CUSTOM_COMPILE_DEPS += $(abspath $(SDF_FILE))
endif
endif
include $(shell "$(PYTHON_BIN)" -m cocotb_tools.config --makefiles)/Makefile.sim
else
.PHONY: all sim pyuvm counter-regression saif synth gate-sim gate-saif gate-check power power-report power-check power-invalidate setup clean clean-gate clean-synth clean-power help

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
		echo 'Counter regression missing under verif/pyuvm.' >&2; exit 2; }
	@"$(PYTHON_BIN)" "$(COUNTER_TEST_DIR)/run_counter_regression.py" \
		--sim "$(SIM)" --build-dir "$(COUNTER_REGRESSION_BUILD)" \
		--seed "$(COUNTER_SEED)" --random-cycles "$(COUNTER_RANDOM_CYCLES)" \
		--compile-args="$(COMPILE_ARGS)" --sim-args="$(SIM_ARGS)" --make "$(_COUNTER_MAKE)" \
		$(if $(strip $(_COUNTER_SIM_BIN_DIR)),--sim-bin-dir "$(_COUNTER_SIM_BIN_DIR)")

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
		'Counter:   COUNTER_REGRESSION_BUILD, COUNTER_RANDOM_CYCLES, COUNTER_SEED'
endif
