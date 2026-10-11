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

Run the counter's specification-based functional regression:

```sh
make counter-regression
# Local alternative when VCS is unavailable:
make counter-regression SIM=icarus
```

This runs `CounterSpecTest` in a PyUVM environment with a sequencer, driver,
passive monitor, independent reference model, scoreboard, and functional
coverage checks. It exercises the eight recommended configurations from the
[counter specification](../specs/common/mosaic-counter/README.md), including
wrapping arithmetic, asynchronous reset, nonzero reset values, and widths
from 1 to 64 bits. Each configuration runs directed tests, at least 1000
randomized cycles, and X/Z control tests. `CounterTest` remains the quick
smoke test used by the default simulation and power targets.

`COUNTER_SEED` defaults to `20261010`; `COUNTER_RANDOM_CYCLES` defaults to
`2000` per configuration. Each profile adds its matrix index to the seed.
Set `COUNTER_REGRESSION_BUILD` to relocate the reports; the default is
`build/<simulator>/counter/regression`. A missing coverage bin, scoreboard
mismatch, absent result, or simulator failure makes the target fail. The
aggregate `summary.json` records missing simulator tools as `NOT_RUN`.
See the [verification details and local results](verif/pyuvm/README.md)
for requirement mapping, artifacts, and limits of the simulation campaign.

Choose a different HDL top and Python test module:

```sh
make pyuvm COCOTB_TOPLEVEL=my_top COCOTB_TEST_MODULES=test_my_top \
  VERILOG_SOURCES="$(pwd)/src/rtl/my_top.sv $(pwd)/src/rtl/common/counter.sv"
```

Place tests in `verif/pyuvm`, or set `PYUVM_TEST_DIR` to another test directory.
Additional import directories can be supplied through `PYTHONPATH`. Set
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

`make -n counter-regression` prints its command without changing reports.

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
  DC_SETUP_TCL=/server/scripts/dc_setup.tcl
```

`TECH_SETUP_TCL` is required and must configure `target_library` with the
technology `.db` libraries and their search paths. `DC_SETUP_TCL` is an optional
second setup script, sourced after the technology script. Use absolute paths in
these scripts; DC runs from `SYNTH_BUILD`. The PDK and cell models remain on the
server. Override `DC_SHELL` with an absolute executable path when `dc_shell` is
not on `PATH`, and use `DC_ARGS` for shell options. Python is not needed for
`make synth`.

The driver `synth/run.tcl` follows the sections and commands in the
reference screenshots: base paths (`PROJECT_HOME`, `PROJECT_HOME_SYN`), design, RTL,
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

## Test-driven power and energy

Run a selected PyUVM test on the gate netlist, capture its activity with VCS,
and analyze average power with PrimeTime PX/PrimePower in one command:

```sh
make power \
  COCOTB_TOPLEVEL=counter COCOTB_TEST_MODULES=test_counter \
  COCOTB_TEST_FILTER=CounterTest \
  POWER_TECH_SETUP_TCL=/server/tech/pt_lib_setup.tcl \
  CELL_MODELS=/server/tech/cells.v \
  NETLIST_FILE=/server/route/counter.v \
  POWER_SDC_FILE=/server/route/counter.sdc \
  SDF_FILE=/server/route/counter.sdf \
  SPEF_FILE=/server/route/counter.spef \
  TEST_CLOCK_PERIOD_NS=4 GATE_SETTLE_NS=1
```

Use matching netlist, SDF, SPEF, and constraints exported by the physical
implementation flow. SDF supplies the simulation delays; SPEF supplies the
extracted capacitances for power analysis. The technology libraries need
internal and leakage power models, and should match the selected process,
voltage, temperature, and parasitic corner. This target consumes physical
implementation outputs; it does not run placement and routing.
Synopsys describes this combination in its [post-route power analysis
overview](https://qacf-www.synopsys.com/blogs/chip-design/software-enabled-full-chip-power-signoff-soc-verification.html).

`POWER_SHELL` defaults to `pt_shell` and requires a PrimeTime PX/PrimePower
license in addition to the VCS simulation license. Set it to an absolute
executable path when needed; `POWER_ARGS` adds shell options.
`POWER_TECH_SETUP_TCL` defaults to `TECH_SETUP_TCL`. It must be compatible with
PrimeTime and configure `link_library` with power-characterized `.db`
libraries and their search paths. If only `target_library` is supplied, the
driver builds `link_library` from it. An optional `POWER_TOOL_SETUP_TCL` is
sourced after the technology script and configures PrimeTime PX/PrimePower
independently of the synthesis setup. The DC-only `DC_SETUP_TCL` is not used
by this analysis. Python 3.12+ is needed to generate the energy summary, using
`PYTHON` (for example, `PYTHON=python3.12`); this script has no third-party
dependencies.

For a synthesis-stage estimate, first run `make synth` and then use its
default netlist and SDC:

```sh
make power TECH_SETUP_TCL=/server/tech/pt_compatible_lib_setup.tcl \
  CELL_MODELS=/server/tech/cells.v \
  SDF_FILE="$(pwd)/build/synth/counter/netlist/counter.sdf" \
  COCOTB_TEST_FILTER=CounterTest
```

`POWER_SDC_FILE` defaults to `build/synth/<top>/netlist/<top>.sdc`. When no
`SPEF_FILE` is supplied, the log and JSON identify the result as a
`mapped_netlist_estimate`. Supply post-route inputs for an analysis including
the physical interconnect. `SDF_FILE` is optional for functional simulation,
but timing simulation captures additional transitions caused by gate delays.

`make power` always runs a fresh gate simulation, rebuilding the simulator
to pick up the selected netlist, models, SDF, and options. It uses the usual
`COCOTB_TEST_MODULES`, `COCOTB_TEST_FILTER`, and plusarg selection. Without a
filter, power and energy cover the whole selected test campaign. The SAIF
capture starts at time zero and includes reset, initialization, and idle time
through the end of the test. To characterize a workload, select a test whose
simulation interval represents that workload.

The analyzer reads the same netlist used by the simulator and annotates the
gate SAIF with `read_saif -strip_path`. `POWER_SAIF_STRIP_PATH` defaults to
`SAIF_SCOPE`, with dots replaced by slashes. Override it to match the hierarchy
inside the SAIF, for example `tb/dut`, corresponding to the analysis top.
The summary requires at least one net annotated from the file. Inspect
`activity.rpt` and `activity_unannotated.rpt` to assess coverage; remaining
activity can be propagated or estimated by the tool. The flow uses the
[vendor's averaged SAIF analysis](https://pdfcoffee.com/primetimepxptpxuserguidepdf-pdf-free.html)
and keeps clock scaling disabled to retain the test's measured activity.

Results go under `build/power/<top>/timing/` when `SDF_FILE` is set, or
`build/power/<top>/functional/` otherwise. Set `POWER_BUILD` to keep separate
results for different tests or corners.

| Output under `POWER_BUILD` | Contents |
| --- | --- |
| `summary.json` | Capture duration in seconds, average power in watts, energy in joules, activity coverage, and input/test selection |
| `reports/power.rpt` | Average power and its units |
| `reports/power_hierarchy.rpt` | Power by hierarchy |
| `reports/activity.rpt`, `reports/activity_unannotated.rpt` | SAIF annotation coverage and unannotated objects |
| `reports/check_timing.rpt` | Timing checks |
| `reports/parasitics.rpt` | Parasitic annotation report when SPEF is supplied |
| `power.log` | Power tool log |

The console prints total, dynamic, and leakage power in mW and energy in pJ.
The JSON also includes separate internal and net-switching components.
Energy is computed over the complete captured interval:

```text
duration_s = SAIF DURATION * SAIF TIMESCALE in seconds
dynamic_power_w = internal_power_w + switching_power_w
total_power_w = dynamic_power_w + leakage_power_w
energy_j = average_power_w * duration_s
```

Power units come from the verbose report, including separate dynamic and
leakage units; the summary does not assume that bare numbers are watts.
SAIF provides average activity, so these results describe average power and
interval energy. Peak power and a power waveform require an event-based
analysis with VCD/FSDB.

To analyze an existing gate SAIF without rerunning its test:

```sh
make power-report \
  POWER_TECH_SETUP_TCL=/server/tech/pt_lib_setup.tcl \
  NETLIST_FILE=/server/route/counter.v \
  POWER_SDC_FILE=/server/route/counter.sdc \
  SPEF_FILE=/server/route/counter.spef \
  POWER_SAIF_FILE=/server/activity/CounterTest.saif
```

`POWER_SAIF_FILE` defaults to `GATE_SAIF_FILE`; `make power` also writes its
fresh capture to this path. For `power-report`, input/test selection recorded
in JSON comes from the supplied Make options; use values matching the
original simulation. A failed test, tool error, invalid duration, ambiguous
power units, or zero SAIF annotation makes the target fail. Previous power
reports and summaries are removed before each attempt. `make clean-power`
removes the selected `POWER_BUILD`; the simulation and SAIF are cleaned with
`make clean-gate`. If `POWER_SAIF_FILE` uses a custom path, also pass that
path as `GATE_SAIF_FILE` when cleaning.

Run the flow checks without DC/VCS licenses with
`python3 -m unittest discover -s tests -v` (requires `make` and `tclsh`). They
exercise the real synthesis Tcl with stubbed DC commands and check error
propagation, stale-output removal, and gate simulation prerequisites. The VCS
command check uses the Python dependencies from `make setup` or `PYTHON_BIN`.
Power checks also exercise the real Make/Tcl flow with stubbed licensed
commands, unit conversions, SAIF duration, coverage, and simulation failures.
Local checks do not validate the technology models or native licensed power
analysis; run the command above on the server to obtain design power values.
