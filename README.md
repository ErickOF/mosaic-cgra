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
SystemVerilog signals and memories. It enables `-ucli2Proc`, required by
`config endofsim noexit`, to keep UCLI active after cocotb finishes so the
report is written before exiting. No changes to the RTL or Python tests are
required.

The target also passes `-lca` to `simv` to enable SystemVerilog SAIF monitoring
in VCS releases that gate the SV-SAIF flow as a Limited Customer Availability
feature. This prevents `LCA_FEATURES_NEED_OPTION` at `power -gate_level`.

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

## Synthesis and gate-level simulation

Synthesize the selected RTL with Synopsys Design Compiler on the licensed server:

```sh
make synth \
  TECH_SETUP_TCL=/server/tech/lib_setup.tcl \
  TOOL_SETUP_TCL=/server/scripts/dc_setup.tcl
```

`TECH_SETUP_TCL` is required and must configure `target_library` with the
technology `.db` libraries and their search paths. `TOOL_SETUP_TCL` is an optional
second setup script, sourced after the technology script. Use absolute paths in
these scripts; DC runs from `SYNTH_BUILD`. The PDK and cell models remain on the
server. Override `DC_SHELL` with an absolute executable path when `dc_shell` is
not on `PATH`, and use `DC_ARGS` for shell options. Python is not needed for
`make synth`.

The driver `synth/run.tcl` follows the sections and commands in the
reference screenshots: base paths (`PROY_HOME`, `PROY_HOME_SYN`), design, RTL,
technology setup, directories, debug output, read/elaborate, checks, constraints,
compile, reports, and outputs. It analyzes `VERILOG_SOURCES` in order,
elaborates `COCOTB_TOPLEVEL`, and sources the shared `constraints/timing.sdc`
budget. Script comments and diagnostics are in English. Output paths remain
under `SYNTH_BUILD`:

| Output under `build/synth/<top>/` | Purpose |
| --- | --- |
| `netlist/<top>_syn.v` | Mapped Verilog netlist |
| `netlist/<top>.sdf` | Synthesis delay estimates |
| `netlist/<top>.sdc` | Constraints for downstream tools |
| `db/<top>.ddc`, `db/<top>.svf` | Design database and formal verification guidance |
| `reports/<top>_*.rpt` | Design checks, design summary, QoR, area, timing, constraint violations, power, references, resources |
| `dc.log` | Design Compiler log |

`SYNTH_BUILD` changes the output directory. Each `make synth` reruns synthesis,
removes previous handoff files, and fails on analysis, linking, compilation, or
design-check errors and on missing/empty handoff files. Inspect the timing and
constraint reports to assess whether the chosen budget is met. The power report
uses DC's default activity estimates; simulation activity is generated separately
with the SAIF targets.

The shared SDC retains the reference uncertainty, transition, source/network
latency, I/O delay, and output-load budgets. `SYNTH_CLOCK_PERIOD=4.0` sets
250 MHz for libraries whose time unit is ns; load values use the library
capacitance unit. `SYNTH_CLOCK_PORT=i_clk` selects the counter's actual port;
set it to `clk` for the port in the screenshots. The synthesis driver maps
these Make options to the SDC's `CLOCK_PERIOD` and `CLOCK_PORT` variables.
As in the reference, sequential constraints are skipped when that port is
absent. `SYNTH_CONSTRAINTS` defaults to `constraints/timing.sdc`; set it to
`/server/path/design.sdc` to replace this budget, including for combinational
designs.

Other flows can source the same SDC after loading/linking their design and
technology libraries. It uses ordinary Tcl variables and has no dependency
on the synthesis environment or DC compilation commands:

```tcl
set CLOCK_PORT clk
set CLOCK_PERIOD 4.0
set CLOCK_NAME CLK
set OUTPUT_LOAD 0.04
source /absolute/path/mosaic-cgra/constraints/timing.sdc
```

Defaults are `CLOCK_PORT=i_clk`, `CLOCK_PERIOD=4.0`, `CLOCK_NAME=CLK`, and
`OUTPUT_LOAD=0.04`. Configure these variables before sourcing the file in a
tool with the corresponding SDC commands. The DC-specific
`set_fix_multiple_port_nets` command stays in the synthesis driver.

Additional synthesis options are configurable:

```sh
make synth TECH_SETUP_TCL=/server/tech/lib_setup.tcl \
  SYNTH_CLOCK_PERIOD=4 SYNTH_CLOCK_PORT=clk \
  SYNTH_PARAMETERS="WIDTH=16" SYNTH_COMPILE_ARGS="-no_autoungroup"
```

`SYNTH_PARAMETERS` uses DC's `elaborate -parameters` syntax.
`SYNTH_COMPILE_ARGS` is a Tcl list of additional `compile_ultra` options; the
default is empty. Both passes use `-gate_clock -retime`, and the second adds
`-incremental`. The script enables leakage optimization and configures latch
clock gating with `-control_point before`, as in the screenshots. Use a test
matching the chosen parameters and transformations.

`SYNTH_CPUS` defaults to 4. If the server provides `set_multi_cpu_usage`, the
script uses the command from the photo; otherwise, it uses DC's documented
[`set_host_options -max_cores`](https://studylib.net/doc/27956669/design-compiler%C2%AE-user-guide-version-v-2023.12--december-2023).
It calls `optimize_leakage` between passes when the server provides it. When
that command is absent, the log states that leakage optimization is handled
during the enabled `compile_ultra` passes. Synopsys documents leakage
optimization during compilation in the [Power Compiler user
guide](https://iccircle.com/static/upload/img20240918122431.pdf).
The script retains error propagation, Verilog name normalization, and SDF
output for the gate simulation flow.

Run the same PyUVM test on the mapped netlist, supplying the Verilog models for
all cells and macros instantiated by that netlist:

```sh
make gate-sim CELL_MODELS="/server/tech/cells.v /server/macros/models.v"
make gate-saif CELL_MODELS="/server/tech/cells.v /server/macros/models.v"
```

These targets use `NETLIST_FILE`, defaulting to the synthesized netlist, and
compile it with `CELL_MODELS` instead of the RTL. They use existing netlists
without rerunning synthesis. Functional gate simulation results are stored in
`build/vcs/<top>/gate/functional/`; `gate-saif` also writes `<top>.saif` there.
Override `GATE_SIM_BUILD`, `GATE_RESULTS_FILE`, and `GATE_SAIF_FILE` to change
these paths. The existing test selection, include paths, compiler, runtime,
and SAIF scope/time-unit options apply.

For timing simulation, add an SDF file. VCS receives
`-sdf <corner>:<scope>:<absolute-file>` at compilation, with `SDF_CORNER=max`
and `SDF_SCOPE=COCOTB_TOPLEVEL` by default; `min` and `typ` are also accepted:

```sh
make gate-saif CELL_MODELS=/server/tech/cells.v \
  SDF_FILE="$(pwd)/build/synth/counter/netlist/counter.sdf"

# Use matching post-route outputs from your physical implementation tool.
make gate-saif CELL_MODELS=/server/tech/cells.v \
  NETLIST_FILE=/server/route/counter.v SDF_FILE=/server/route/counter.sdf \
  SDF_CORNER=max GATE_SETTLE_NS=2 TEST_CLOCK_PERIOD_NS=10
```

Timing simulation outputs go in `build/vcs/<top>/gate/timing/`. DC synthesis
produces a mapped netlist and estimated delays. Simulation of the placed and
routed design uses its exported netlist and matching SDF; this Makefile does
not perform place and route. Check VCS's SDF annotation messages to confirm the
cell models and instance names match. See the vendor's [SDF annotation
documentation](https://device.report/m/21147a58a2161729f264107c63437223e00ed7e3bf0dc09504e86cb06b5da352)
for the compilation option.

The starter `CounterTest` drives inputs at the falling edge and samples after
the rising edge. `gate-sim` and `gate-saif` set its settling delay with
`GATE_SETTLE_NS` (default 1 ns); RTL uses `TEST_SETTLE_NS=0`. Set the delay long
enough for the selected netlist/SDF, and keep it below half
`TEST_CLOCK_PERIOD_NS`. The test clock defaults to `SYNTH_CLOCK_PERIOD` interpreted
in ns; override it explicitly if the technology has different time units. The
test has a 1 us timeout. Other PyUVM tests must implement their own timing-aware
sampling.

Use `make clean-gate` before changing the netlist/model list or SDF path, scope,
corner, or compiler flags to force a fresh compilation. Pass the same
`SDF_FILE`/`GATE_SIM_BUILD` overrides when cleaning the timing build.
`make clean-synth` removes the selected synthesis output directory.

Run the flow checks without DC/VCS licenses with
`python3 -m unittest discover -s tests -v` (requires `make` and `tclsh`). They
exercise the real synthesis Tcl with stubbed DC commands and check error
propagation, stale-output removal, and gate simulation prerequisites. The VCS
command check uses the Python dependencies from `make setup` or `PYTHON_BIN`.
