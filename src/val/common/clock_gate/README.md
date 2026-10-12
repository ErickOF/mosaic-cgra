# Clock gate functional verification with PyUVM

The contract is the [MOSAIC clock gate specification](../../../../../specs/common/mosaic-clock-gate/README.md).
This suite verifies the unmodified portable `src/rtl/common/clock_gate.sv`
through its four ports. It does not read the implementation's internal latch.

## Run the regression

From `mosaic-cgra`:

```sh
make setup
make clock-gate-regression                         # VCS on the licensed server
make clock-gate-regression SIM=icarus               # Local four-state simulation
make clock-gate-regression SIM=vcs VCS_BIN_DIR=/server/vcs/bin
make clock-gate-regression SIM=icarus CLOCK_GATE_SEED=12345 CLOCK_GATE_RANDOM_CYCLES=5000
```

The regression runs `test_clock_gate.ClockGateTest` in two fresh simulator
processes, with functional enable low and high at startup respectively.
Both start with a defined source-clock low phase and test enable low; no reset
is introduced. This checks defined startup controls without assuming an
implementation-specific power-up value for the latch.

`CLOCK_GATE_SEED` defaults to `20261010`; the enabled-startup case adds one.
`CLOCK_GATE_RANDOM_CYCLES` defaults to `2000` per case and must be at least
`1000`. A local `random.Random` instance makes the activity reproducible.
`TEST_CLOCK_PERIOD_NS` defaults to `4` through the Makefile. Use an even
period in picoseconds of at least `16 ps`, with simulator precision of `1 ps`
or finer. The driver changes controls `1 ps` before and after clock edges,
never simultaneously with an edge.

`COMPILE_ARGS`, `SIM_ARGS`, `PYTHON_BIN`, and the simulator binary directory
also apply. `CLOCK_GATE_REGRESSION_BUILD` changes the artifact directory;
the default is `build/<simulator>/clock_gate/regression`.
Only VCS and Icarus are accepted because X/Z controls require four-state
simulation. The runner selects its own top, source, import directory, and test.

To run a single startup case through the regular Make flow:

```sh
make pyuvm SIM=icarus COCOTB_TOPLEVEL=clock_gate
CLOCK_GATE_STARTUP_ENABLED=1 make pyuvm SIM=icarus COCOTB_TOPLEVEL=clock_gate
```

The single test defaults to disabled startup. Its JUnit and coverage reports
are stored in `build/<simulator>/clock_gate`. The full regression requires
both startup cases to pass. A focused RTL mutation check can use the runner:

```sh
.venv/bin/python src/val/common/clock_gate/run_clock_gate_regression.py \
  --sim icarus --rtl /tmp/faulty_clock_gate.sv \
  --build-dir build/icarus/clock_gate/mutation
```

## Environment and requirement mapping

`ClockGateSequence` submits timed transactions to a PyUVM sequencer.
`ClockGateDriver` drives complete source-clock cycles and within-cycle
control changes. `ClockGateMonitor` publishes settled input/output snapshots
and independently records every observable change of `o_gclk`. Its output
listener immediately re-arms without waiting for the end of the time step,
so a transient returning to the original value is still checked.

`ClockGateScoreboard` implements low-phase capture of the effective enable
from observed ports. It compares every settled output against that model
and compares the entire output transition history against the expected
history. Binary rising and falling edges must coincide with the matching
source-clock edge. Each complete high pulse must equal the source high phase;
each low pulse must be at least the source low phase. The zero-delay RTL
contract allows no pulse-width shortening. Simulator precision limits the
smallest observable glitch; this is not an analog pulse-width measurement.

| Specification requirement | Stimulus and check |
| --- | --- |
| Enabled and disabled startup, no functional reset | Separate simulations with known controls established during the initial low phase |
| Functional and test control changes in either half-cycle | Both polarities of each control, with the other control low |
| Changes near both edges | Each control/polarity crossed with before/after each source rising/falling edge, at a 1 ps offset |
| Transparent low-phase capture | Control transients ending before the next rise; the final low-phase value controls the pulse |
| High-phase changes cannot create or truncate a pulse | Assert/deassert transients during high phases while the captured gate is open and closed |
| Test override and scan clocks | All four control combinations and functional toggling while test enable remains asserted |
| Repeated opening/closing | Alternating decisions on successive source cycles |
| Long activity and inactivity | At least 64 consecutive enabled cycles and 64 consecutive disabled cycles |
| Zero, one, and multiple output pulses; short idle intervals | Directed bursts and checked output history |
| Randomized enable activity | Independently seeded low/high-phase control changes on every random cycle |
| Illegal functional and test controls | X/Z injected into each control, in both phases, with the other control low and high |
| Every edge and complete pulse width | Continuous output transition recording, model history matching, source alignment, and high/low width assertions |

Coverage must hit all required bins in each startup case. Reports distinguish
the time and phase of each requested transition from the captured enable and
the next observed source-pulse decision. A short request overwritten before
capture need not propagate a pulse.

Unknown controls produce expected Python checker diagnostics during explicitly
marked negative tests. Unexpected unknown controls fail immediately. Unmasked
X/Z must remain unknown when captured; a known asserted OR input may mask the
unknown in the output, but the illegal-control diagnostic is still required.
The model checks these four-state transitions separately from legal pulse-width
statistics. HDL-bound SVA is not added to the portable RTL and remains `NOT_RUN`.

## Artifacts and failure handling

| Artifact | Contents |
| --- | --- |
| `summary.json` | Aggregate status, both startup results, seeds, timestamps, RTL/verification SHA-256 hashes, and unexecuted external checks |
| `<startup>/coverage.json` | Required goals/bins, source cycles, all output transition counts, pulse widths, requested transitions, and actual source-pulse decisions |
| `<startup>/results.xml` | cocotb JUnit result identifying the actual PyUVM test |
| `<startup>/simulation.log` | Compilation, simulation, diagnostics, assertion failures, and coverage output |

The runner removes previous coverage and JUnit results for each attempted case.
It requires exactly one successful `ClockGateTest`, matching startup/seed/random
settings, and passing functional coverage. A simulator failure, missing result,
unexpected edge, runt pulse, or missing bin fails the command. Missing simulator
executables produce `NOT_RUN` and a nonzero exit. Read aggregate status before
using artifacts from previous runs. `make -n clock-gate-regression` preserves
existing reports.

## Local verification evidence

Both startup cases passed with Python 3.12, cocotb 2.1.0, PyUVM 5.0.0, and
Icarus Verilog 12.0. The default seeds produced 4,622 source cycles, including
4,000 random cycles. The checker verified 6,716 output transitions and 3,334
complete known high pulses, each exactly `2,000 ps` at the default `4 ns`
clock period. All functional coverage goals passed in each case.

Five deliberately faulty temporary RTL copies were detected: combinational
gating, falling-edge-only enable storage, missing test override, conversion
of unknown controls to zero, and an extra `1 ps` output glitch. The last defect
returned to the correct value before settled sampling; the continuous output
history checker detected it. The original RTL was not modified.

The normal top-selecting Make invocation also passed from outside the project.
Dry runs preserved reports, missing VCS was recorded as `NOT_RUN`, and invalid
random settings were rejected. Verilator `--lint-only --timing -Wall` passed
for the portable module without a broad latch waiver. All 31 existing local
synthesis/power checks passed using stubbed licensed commands.

The verified RTL SHA-256 is
`41f9e1ff400938b76e5ca1514de781f9c040abad09ad66842c3bf224d9a7d1f9`.
Build artifacts are ignored by Git. Rerun the regression after changing RTL
or verification sources; the aggregate report records the current source hashes.

## Verification scope

This campaign checks the portable, zero-delay RTL model. Timing-annotated
technology cells require their own delay and pulse-width contract; this
checker does not establish post-route timing or technology equivalence.
Formal proof, bound HDL SVA, commercial CDC/RDC/DFT/low-power checks,
approved ICG mapping, equivalence, generated-clock STA, and physical power
analysis remain `NOT_RUN` here. Passing this functional regression alone
does not meet the specification's complete release criteria or demonstrate
energy savings.
