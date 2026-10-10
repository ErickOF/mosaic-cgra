# Mosaic CGRA

Run PyUVM tests through cocotb with Synopsys VCS:

```sh
make setup
make pyuvm
```

Use Python 3.9 or newer with the `venv` module. VCS must be installed with a
working license and its `vcs` executable on `PATH`; alternatively, pass
`VCS_BIN_DIR=/path/to/vcs/bin`. `make setup` installs cocotb 2.1.0 and PyUVM
5.0.0 into `.venv`. No virtual-environment activation is needed.

`make`, `make sim`, and `make pyuvm` all run the included `CounterTest` against
`src/rtl/common/counter.sv` with its default parameters. The test checks reset,
increment/decrement, disabled hold, clear/load priority, saturating boundaries,
and event pulses. A failing test makes the command fail.

Choose a different HDL top and Python test module:

```sh
make pyuvm COCOTB_TOPLEVEL=my_top COCOTB_TEST_MODULES=test_my_top \
  VERILOG_SOURCES="$(pwd)/src/rtl/my_top.sv $(pwd)/src/rtl/common/counter.sv"
```

Place tests in `verif/pyuvm`, or add their directory to `PYTHONPATH`. Set
`COCOTB_TEST_MODULES` to importable module names without `.py`; multiple modules
are comma-separated. It defaults to `test_<COCOTB_TOPLEVEL>`. When
`VERILOG_SOURCES` is omitted, it defaults to
`src/rtl/common/<COCOTB_TOPLEVEL>.sv`. Package sources must precede sources
that import them.

Pass additional compiler options with `COMPILE_ARGS`, runtime options with
`SIM_ARGS`, and HDL plusargs with `COCOTB_PLUSARGS`. The cocotb VCS backend
supplies SystemVerilog, 64-bit compilation for 64-bit Python, and VPI loading
and signal access. Select a single test with
`COCOTB_TEST_FILTER=CounterTest`. To use an existing Python environment, pass
`PYTHON_BIN=/absolute/path/to/python` with the requirements already installed.

Build products and the JUnit report are stored in
`build/<simulator>/<top>/`, with results in `results.xml`. `make clean` removes
the selected build and report. Clean before changing compiler options or the
source list to force recompilation. `make help` lists the main options.

Generate a SAIF activity file from the PyUVM simulation with VCS:

```sh
make saif
```

The target records activity from time zero through the end of the selected
tests and writes `build/vcs/<top>/<top>.saif`. It uses the VCS UCLI `power`
commands in `verif/vcs/saif.tcl` to collect activity directly, including
SystemVerilog signals and memories. It keeps UCLI active after cocotb finishes
so the report is written before exiting. No changes to the RTL or Python
tests are required.

Configure the output path, captured hierarchy, and report time unit (in
seconds) as needed:

```sh
make saif SAIF_FILE="$(pwd)/build/activity.saif" \
  SAIF_SCOPE=counter SAIF_TIME_UNIT=1e-9
```

`SAIF_SCOPE` defaults to `COCOTB_TOPLEVEL`; it can also select a child instance,
such as `my_top.dut`. `SAIF_TIME_UNIT` defaults to `1e-9` (1 ns) and controls
the report units, not the simulation clock. The usual source, test, compiler,
and runtime overrides also apply. This target requires `SIM=vcs`, removes any
previous output before running, and fails if the simulation fails or no
nonempty SAIF file is produced. `make clean` also removes `SAIF_FILE`, including
when its path is outside the selected build directory.

The simulator can be overridden, for example:

```sh
make pyuvm SIM=icarus
```

This uses the same PyUVM test with Icarus Verilog, which must be installed
separately. VCS remains the default.
