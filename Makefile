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
VERILOG_SOURCES ?= $(PROJECT_ROOT)/src/rtl/common/$(COCOTB_TOPLEVEL).sv
SIM_BUILD ?= $(PROJECT_ROOT)/build/$(SIM)/$(COCOTB_TOPLEVEL)
COCOTB_RESULTS_FILE ?= $(SIM_BUILD)/results.xml
SAIF_FILE ?= $(SIM_BUILD)/$(COCOTB_TOPLEVEL).saif
SAIF_SCOPE ?= $(COCOTB_TOPLEVEL)
SAIF_TIME_UNIT ?= 1e-9
SAIF_SCRIPT := $(PROJECT_ROOT)/verif/vcs/saif.tcl

export PYTHONPATH := $(PROJECT_ROOT)/verif/pyuvm$(if $(PYTHONPATH),:$(PYTHONPATH))
CUSTOM_COMPILE_DEPS += $(PROJECT_ROOT)/Makefile

# Load cocotb only in the simulation subprocess so setup/help/clean work
# before the Python environment or licensed simulator has been installed.
ifeq ($(_COCOTB_RUN),1)
# Treat caller options as a starting value so cocotb can append mandatory
# backend flags even when COMPILE_ARGS was supplied on the command line.
_USER_COMPILE_ARGS := $(COMPILE_ARGS)
override undefine COMPILE_ARGS
COMPILE_ARGS := $(_USER_COMPILE_ARGS)
include $(shell "$(PYTHON_BIN)" -m cocotb_tools.config --makefiles)/Makefile.sim
else
.PHONY: all sim pyuvm saif setup clean help

all sim: pyuvm

pyuvm:
	@test -x "$(PYTHON_BIN)" || { \
		echo 'Python environment missing. Run make setup first.' >&2; exit 2; }
	@"$(PYTHON_BIN)" -c 'import cocotb, pyuvm' || { \
		echo 'PyUVM/cocotb missing. Run make setup first.' >&2; exit 2; }
	+$(MAKE) --no-print-directory -C "$(PROJECT_ROOT)" -f Makefile \
		_COCOTB_RUN=1 PYTHON_BIN="$(PYTHON_BIN)" sim

# Pass values through the environment so Tcl treats paths and hierarchy names
# as data. Keep existing runtime options when enabling the UCLI capture script.
# The script's config endofsim noexit command requires -ucli2Proc at runtime.
saif: export MOSAIC_SAIF_FILE = $(abspath $(SAIF_FILE))
saif: export MOSAIC_SAIF_SCOPE = $(SAIF_SCOPE)
saif: export MOSAIC_SAIF_TIME_UNIT = $(SAIF_TIME_UNIT)
saif:
	@test "$(SIM)" = vcs || { \
		echo 'SAIF generation requires SIM=vcs.' >&2; exit 2; }
	@mkdir -p "$(dir $(abspath $(SAIF_FILE)))"
	$(RM) -- "$(abspath $(SAIF_FILE))"
	+$(MAKE) --no-print-directory -C "$(PROJECT_ROOT)" -f Makefile \
		pyuvm SIM_ARGS="$(SIM_ARGS) -ucli -ucli2Proc -i $(SAIF_SCRIPT)"
	@test -s "$(abspath $(SAIF_FILE))" || { \
		echo 'VCS did not generate a nonempty SAIF file.' >&2; exit 2; }
	@printf 'SAIF generated: %s\n' "$(abspath $(SAIF_FILE))"

setup:
	"$(PYTHON)" -m venv "$(VENV)"
	"$(VENV)/bin/python" -m pip install -r "$(PROJECT_ROOT)/requirements.txt"

clean:
	$(RM) -r -- "$(SIM_BUILD)"
	$(RM) -- "$(COCOTB_RESULTS_FILE)" "$(SAIF_FILE)"

help:
	@printf '%s\n' \
		'make setup           Install pinned PyUVM and cocotb into .venv' \
		'make [pyuvm|sim]     Run PyUVM with VCS (default: counter)' \
		'make saif            Run PyUVM with VCS and write switching activity' \
		'make clean           Remove the selected build, results, and SAIF file' \
		'' \
		'Overrides: SIM, VCS_BIN_DIR, COCOTB_TOPLEVEL, COCOTB_TEST_MODULES,' \
		'           VERILOG_SOURCES, COMPILE_ARGS, SIM_ARGS, COCOTB_PLUSARGS,' \
		'           COCOTB_TEST_FILTER, VENV, PYTHON_BIN, SIM_BUILD,' \
		'           SAIF_FILE, SAIF_SCOPE, SAIF_TIME_UNIT'
endif
