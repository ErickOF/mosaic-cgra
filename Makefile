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
.PHONY: all sim pyuvm setup clean help

all sim: pyuvm

pyuvm:
	@test -x "$(PYTHON_BIN)" || { \
		echo 'Python environment missing. Run make setup first.' >&2; exit 2; }
	@"$(PYTHON_BIN)" -c 'import cocotb, pyuvm' || { \
		echo 'PyUVM/cocotb missing. Run make setup first.' >&2; exit 2; }
	+$(MAKE) --no-print-directory -C "$(PROJECT_ROOT)" -f Makefile \
		_COCOTB_RUN=1 PYTHON_BIN="$(PYTHON_BIN)" sim

setup:
	"$(PYTHON)" -m venv "$(VENV)"
	"$(VENV)/bin/python" -m pip install -r "$(PROJECT_ROOT)/requirements.txt"

clean:
	$(RM) -r -- "$(SIM_BUILD)"
	$(RM) -- "$(COCOTB_RESULTS_FILE)"

help:
	@printf '%s\n' \
		'make setup           Install pinned PyUVM and cocotb into .venv' \
		'make [pyuvm|sim]     Run PyUVM with VCS (default: counter)' \
		'make clean           Remove the selected simulator/top build and results' \
		'' \
		'Overrides: SIM, VCS_BIN_DIR, COCOTB_TOPLEVEL, COCOTB_TEST_MODULES,' \
		'           VERILOG_SOURCES, COMPILE_ARGS, SIM_ARGS, COCOTB_PLUSARGS,' \
		'           COCOTB_TEST_FILTER, VENV, PYTHON_BIN, SIM_BUILD'
endif
