# Counter functional verification with PyUVM

The verification contract is the
[MOSAIC counter specification](../../../specs/common/mosaic-counter/README.md),
especially its Functional Verification, Required Assertions, and Coverage
Requirements sections. `test_counter_spec.CounterSpecTest` verifies the
unmodified `src/rtl/common/counter.sv` against that contract.

## Run the regression

From `mosaic-cgra`:

```sh
make setup
make counter-regression                         # VCS on the licensed server
make counter-regression SIM=icarus              # Icarus Verilog locally
make counter-regression SIM=vcs VCS_BIN_DIR=/server/vcs/bin
make counter-regression SIM=icarus COUNTER_SEED=12345 COUNTER_RANDOM_CYCLES=5000
```

The existing requirements pin cocotb 2.1.0 and PyUVM 5.0.0. Use a four-state
simulator: the campaign deliberately injects X and Z. The regression accepts
VCS and Icarus; two-state simulation cannot satisfy its known-control checks.
`COMPILE_ARGS`, `SIM_ARGS`, `PYTHON_BIN`, `TEST_CLOCK_PERIOD_NS`, and simulator
binary directory settings also apply. The target selects the counter source,
top, and test itself, regardless of overrides used for other designs.

The minimum random sequence is 1000 cycles per profile; the default is 2000.
The base seed is `20261010`, incremented by the profile's index. A local
`random.Random` instance makes stimulus reproducible. Each profile has its own
build directory and parameter dependency so it cannot reuse a compilation
from another configuration.

For a focused diagnostic run, use the same runner directly:

```sh
.venv/bin/python verif/pyuvm/run_counter_regression.py \
  --sim icarus --build-dir build/icarus/counter/focused --case async_reset
```

A focused run is recorded as `selected_profiles`, rather than a complete
recommended matrix. `--rtl` can select a temporary faulty RTL copy to check
whether the verification environment detects a defect.

## Recommended configurations

These are the eight profiles listed in the specification. The nonzero-reset
profile uses the concrete value `0x35A7`.

| Profile | WIDTH | SATURATE | ASYNC_RESET | RESET_VALUE |
| --- | ---: | ---: | ---: | ---: |
| `minimum_saturating` | 1 | 1 | 0 | 0 |
| `minimum_wrapping` | 1 | 0 | 0 | 0 |
| `fifo_pointer` | 4 | 0 | 0 | 0 |
| `small_event` | 8 | 1 | 0 | 0 |
| `performance` | 32 | 1 | 0 | 0 |
| `extended` | 64 | 1 | 0 | 0 |
| `async_reset` | 32 | 1 | 1 | 0 |
| `nonzero_reset` | 16 | 1 | 0 | `0x35A7` |

## Environment and checks

`CounterSpecSequence` submits `CounterItem` transactions to a PyUVM sequencer.
`CounterDriver` drives controls on falling clock edges. `CounterMonitor`
reads actual DUT inputs and outputs between edges and after rising edges,
then publishes observations through a UVM analysis port.
`CounterScoreboard` checks those observations against bounded integer
arithmetic in `next_state`, rather than deriving expected values from the
DUT's outputs. The scoreboard owns the functional coverage collector.

Between-edge sampling checks that registered outputs remain stable when no
asynchronous reset occurs. A short reset pulse asserted and released entirely
between rising edges distinguishes asynchronous from synchronous reset.
After-edge sampling checks the count, both event flags, and terminal output.
Checks execute during simulation; a mismatch raises an assertion and fails
the cocotb/PyUVM test.

| Specification requirement | Stimulus and check |
| --- | --- |
| Reset and reset priority | All control combinations, reset from loaded states, outstanding-event resets, short reset pulse, and reset release |
| Clear and load priority | All 32 combinations of reset, clear, load, enable, and direction; distinct starting and loaded values |
| Hold and one-cycle event clearing | Disabled sequences; count and both event flags checked on every valid cycle |
| Increment and decrement | Directed arithmetic, both directions during long active periods, and seeded random commands |
| Saturation and wrapping | Both boundary attempts and subsequent opposite-direction commands in each configured arithmetic mode |
| Direction-aware terminal count | Zero and maximum with both directions and enable low; terminal checked before and after each edge |
| Unknown controls | X and Z injected individually into reset, clear, load, enable, and direction; unexpected unknowns fail |
| Unknown direction | Terminal must be zero for both X and Z, with enable high and low |
| Minimum and larger widths | Eight independently elaborated profiles, including 1, 4, 8, 16, 32, and 64 bits |
| Nonzero reset value | Reset and clear checked against `0x35A7`, including competing load and enable commands |
| Small-state exploration | Every count crossed with all 32 control combinations for WIDTH <= 4 |
| Reset from reachable states | Every count for WIDTH <= 8; representative and random states at larger widths |

The negative X/Z tests expect a known-control diagnostic from the Python
checker. They verify that the illegal value reaches the DUT and that unknown
direction forces terminal low. Numerical behavior following an illegal
command is unspecified, so reset restores a known model state before valid
arithmetic checking resumes. These diagnostics do not establish that HDL
SVA properties are bound or enabled; HDL SVA remains `NOT_RUN`.

## Coverage and artifacts

The test fails unless every required functional goal has a positive hit.
Per-profile goals cover commands, legal command/direction combinations, all
control-priority combinations, zero/maximum/reset values, representative
loads, reset states, disabled terminal/direction combinations, X/Z controls,
boundary transitions and attempts, direction changes, boundary-event recovery,
at least 32 consecutive hold cycles, at least 64 consecutive active cycles,
and the configured number of random cycles. Small widths additionally require
the exhaustive state/control cross.

The complete matrix also checks boundary x saturation mode, reset mode x
active command, and width x boundary event across elaborations. Clear x load x
enable is included in the per-profile control-priority cross. Arithmetic
command names already encode direction, so increment/down and decrement/up
are structurally excluded from the command/direction bins.

The default report directory is `build/<simulator>/counter/regression`:

| Artifact | Contents |
| --- | --- |
| `summary.json` | Aggregate status, matrix crosses, profile results, seeds, timestamps, RTL and verification SHA-256 hashes, and unexecuted external checks |
| `<profile>/coverage.json` | Checked-cycle counts, functional bins, event counts, reset-state scope, and individual coverage goals |
| `<profile>/results.xml` | cocotb JUnit result naming the actual PyUVM test |
| `<profile>/simulation.log` | Compiler, simulator, PyUVM, assertion, and coverage output |
| `<profile>/parameters.json` | The elaboration parameters for that profile |

The runner removes previous coverage and JUnit results, requires exactly one
successful `CounterSpecTest`, checks its reported parameters, and checks its
coverage status before declaring `PASS`. A missing simulator is `NOT_RUN` and
causes a nonzero exit. Consult the aggregate status before using profile
artifacts from an earlier run.

## Local verification evidence

The full matrix was executed locally on October 10, 2026 with Python 3.12,
cocotb 2.1.0, PyUVM 5.0.0, and Icarus Verilog 12.0. All eight profiles passed,
with 20,283 checked cycles and 16,000 random cycles using the default seeds.
Every functional coverage goal and every matrix cross passed. Reset-state
coverage was exhaustive for the 1-, 4-, and 8-bit profiles. X and Z were
observed on every control in every profile.

The verified RTL SHA-256 was
`d02f311941ef1fc913b80ab2bb5d66cdc35c817dddacb459e7400b9597d8806f`.
The generated artifacts remain under `build/icarus/counter/regression`;
build products are ignored by Git. Rerun the regression after changing the
RTL or verification sources to obtain evidence for the current revision.

Five deliberate defects in temporary RTL copies were detected: incorrect
clear/load priority, a missing overflow event, wrapping when saturation is
enabled, asserting terminal for unknown direction, and a synchronous
implementation substituted for asynchronous reset. The original `CounterTest`
also passed, and all 31 synthesis/power flow checks passed.

## Verification scope

This establishes functional simulation coverage for the recommended matrix.
VCS execution is `NOT_RUN` locally because its executable is unavailable.
Formal proof, bound HDL SVA, commercial static checks, and physical timing or
power analysis are `NOT_RUN` in this campaign. The regression does not claim
full compliance with the specification's release criteria.

Finite simulation does not exhaust every 16-, 32-, or 64-bit state. These
profiles cover reset from boundary, reset, pattern, and random states; proving
reset and all other properties over every reachable state requires formal
verification. Invalid-parameter elaboration checks and reset-domain analysis
also remain outside this functional campaign.
