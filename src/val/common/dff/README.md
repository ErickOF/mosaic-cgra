# DFF PyUVM validation

This suite checks `src/rtl/common/dff.sv` against the
[MOSAIC DFF specification](../../../../../specs/common/mosaic-dff/README.md).
It uses a PyUVM sequencer, driver, passive monitor, independent sequential
model, scoreboard, and mandatory functional coverage. The model reads only
interface ports; it does not inspect RTL generate branches or internal state.

## Running the tests

From `mosaic-cgra`, with the existing Python environment installed:

```sh
make setup
make dff-regression                 # VCS on the licensed server
make dff-regression SIM=icarus      # Four-state local alternative
```

Configure seed, randomized cycles per profile, and report location:

```sh
make dff-regression SIM=icarus DFF_SEED=1234 DFF_RANDOM_CYCLES=3000 \
  DFF_REGRESSION_BUILD="$(pwd)/build/dff-custom"
```

Defaults are `DFF_SEED=20261010` and `DFF_RANDOM_CYCLES=2000`; at least 1000
randomized cycles are required. Each profile adds its matrix index to the
seed. `VCS_BIN_DIR` and `ICARUS_BIN_DIR` select the simulator executables.
`COMPILE_ARGS` and `SIM_ARGS` extend the normal compilation and simulation.
`TEST_CLOCK_PERIOD_NS` defaults to 4 ns and must be divisible by 4 ps and at
least 32 ps. The driver separates control changes from rising edges.

Run a focused profile, including the invalid-width guard check:

```sh
.venv/bin/python src/val/common/dff/run_dff_regression.py \
  --sim icarus --build-dir build/dff-focused --case nonzero_reset
```

Repeat `--case` to select multiple profiles; `--rtl /absolute/path/dff.sv`
supports testing an alternate implementation without editing the design.
The aggregate report distinguishes a selected subset from the full matrix.

The normal discovery flow also runs the default single-bit synchronous DFF:

```sh
make pyuvm SIM=icarus COCOTB_TOPLEVEL=dff
```

For direct runs with parameter overrides, set the matching `DFF_WIDTH`,
`DFF_RESET_VALUE`, `DFF_ASYNC_RESET`, and `DFF_HAS_ENABLE` environment variables.
The regression runner does this automatically, uses sized SystemVerilog reset
and boolean literals, and checks data/output widths and report parameters.

## Parameter matrix

The first seven rows match the specification's recommended configurations.
Additional rows exercise all four static reset/enable branches and wider
always-enabled storage.

| Profile | WIDTH | ASYNC_RESET | HAS_ENABLE | RESET_VALUE |
|---|---:|---:|---:|---|
| `single_bit_sync` | 1 | 0 | 1 | 0 |
| `single_bit_async` | 1 | 1 | 1 | 0 |
| `byte_register` | 8 | 0 | 1 | 0 |
| `scalar_register` | 32 | 0 | 1 | 0 |
| `vector_register` | 128 | 0 | 1 | 0 |
| `always_enabled` | 32 | 0 | 0 | 0 |
| `nonzero_reset` | 32 | 1 | 1 | `0x5A5AA5A5` |
| `async_always_enabled` | 32 | 1 | 0 | `0xA55A5AA5` |
| `sync_nonzero_reset` | 8 | 0 | 1 | `0xA5` |
| `minimum_nonzero_reset` | 1 | 1 | 0 | 1 |
| `extended_always_enabled` | 128 | 0 | 0 | 0 |

## Specification and assertion mapping

| Requirement | Stimulus and active checks |
|---|---|
| Enabled capture, one-cycle latency | Independent model samples `i_d` only at rising edges; every settled phase checks `o_q` against that state. |
| Disabled hold and input activity | Long holds, alternating enable, and data changes at both clock levels; output waveform must remain unchanged between legal events. |
| Reset priority over data/enable | Both enable values, opposite reset/data patterns, input changes while reset is asserted, and X/Z enables masked by reset. |
| Synchronous reset | Reset pulses entirely between rising edges must leave state unchanged; reset at a rising edge must load `RESET_VALUE`. |
| Asynchronous reset | Pulses while either clock level is held must immediately load `RESET_VALUE`; reset release must not capture data. |
| Reset release | Release is observed before the next rising edge and during a held high clock phase; the reference model checks both. |
| `HAS_ENABLE=0` | Capture on every rising edge while enable takes all four states; high-phase enable changes cannot update state. |
| Consecutive updates/holds | At least 16 consecutive captures, at least 16 holds when enable is supported, and both capture/hold transition directions. |
| Minimum/extended widths and nonzero reset | Eleven elaborations, walking ones/zeros across every bit, and asymmetric reset patterns in both reset modes. |
| Random data/reset/enable | At least 1000 reproducible binary-control cycles per profile, with independent randomized data. |
| Known reset assertion | X and Z are each injected at a rising edge with enable low and high; the monitor must detect each illegal control. |
| Known enable assertion | X and Z are illegal with reset released when `HAS_ENABLE=1`; reset masks the assertion and `HAS_ENABLE=0` ignores enable. |
| No output change without a legal event | Every observable output transition is recorded and compared with the model's complete expected transition list, including timestamps. |

The required capture, hold, reset, and known-control assertions are implemented
as active Python checks in the PyUVM scoreboard. Expected illegal-control tests
validate the independently sampled diagnostic and record its coverage. An
unexpected violation fails immediately. The numeric state is unspecified
during illegal control sequences; each injection is followed by a valid reset
before numerical checking resumes. Unreset startup state is also unspecified.
These intervals are explicitly excluded from waveform comparison.

Waveform checking re-arms on each output change without waiting for `ReadOnly`,
so an observable short glitch that disappears before the settled sample still
fails. Missing transitions, extra transitions, wrong values, or incorrect event
times fail the coverage gate. These are zero-delay RTL checks requiring 1 ps
precision or finer and `TEST_SETTLE_NS=0`; they do not validate SDF delays or
physical setup/hold, recovery/removal, or metastability behavior.

HDL-bound SVA and formal proofs are separate checks recorded as `NOT_RUN`.
Asynchronous reset release in these tests is deliberately separated from
functional clock edges. Integration must supply the external synchronization
required by the specification.

## Reports and failure handling

Each profile writes these files under `build/<simulator>/dff/regression`:

| File | Contents |
|---|---|
| `<profile>/results.xml` | JUnit result for exactly one `test_dff.DffTest`. |
| `<profile>/coverage.json` | Parameters, seed, command/bit/control bins, all coverage goals, and output transition totals. |
| `<profile>/simulation.log` | Native compiler and real PyUVM simulation output. |
| `<profile>/parameters.json` | Compile dependency that forces rebuilding when parameters change. |
| `invalid_parameters/zero_width/guard.log` | Compile and startup result for the existing invalid-width guard. |
| `summary.json` | Matrix status, profile results, source hashes, parameter guard status, specification gaps, and external checks. |

Previous JUnit/coverage results are removed before each profile runs. Failed,
skipped, absent, duplicated, or incorrectly selected tests cannot pass. Missing
coverage goals, mismatched parameters/seeds, incorrect random counts, compiler
errors, and simulator failures also fail the target. Missing simulator binaries
produce `NOT_RUN` and a nonzero exit. `make -n dff-regression` prints the command
without running the wrapper or changing reports.

The invalid-width test requires the intended `WIDTH must be greater than zero`
diagnostic and a failing simulator exit. The current RTL uses `initial $fatal`,
so this is a **simulation-startup rejection**, not an elaboration failure. The
specification's strict elaboration-validation requirement is recorded as
`BLOCKED`. Its typed `RESET_VALUE` parameter also permits implicit resizing of
caller literals; the suite supplies correctly sized patterns but cannot claim
that arbitrary incorrectly sized literals are rejected. The RTL is unchanged.

## Local validation evidence

With Python 3.12, cocotb 2.1.0, PyUVM 5.0.0, and Icarus 12.0:

- All eleven profiles passed, including all recommended configurations and
  all four reset/enable generate branches.
- The campaign checked 24,376 rising edges, including 22,000 randomized cycles,
  and audited 14,893 output transitions. Every required functional goal and
  bit-value bin passed; 58 distinct expected control-assertion cases were seen.
- The zero-width startup guard rejected the invalid configuration.
- Ten isolated RTL mutants were detected: inverted data/reset, ignored enable,
  missing/unexpected asynchronous reset, falling-edge capture, an internally
  gated clock, enable dependence in the no-enable branch, a missing width guard,
  and a 1 ps disabled output glitch. The glitch passed settled state checks but
  failed the complete waveform comparison.
- Verilator `--lint-only --timing -Wall` passed seven enable-supported profiles
  without waivers. Four `HAS_ENABLE=0` profiles passed with the documented
  `UNUSEDSIGNAL` waiver for the intentionally ignored `i_enable` port; sized
  parameter overrides avoided artificial literal-width warnings.
- All 31 existing synthesis/power orchestration checks passed with licensed
  tool commands stubbed.

Local evidence is stored in ignored `build/validation/dff`; native simulation
reports are in `build/icarus/dff/regression`. Source hashes identify the RTL and
verification scripts used. VCS, HDL SVA, formal, commercial lint, CDC/RDC,
DFT/low-power integration, synthesis, physical timing, and physical power are
`NOT_RUN` locally. Passing this finite functional campaign does not satisfy
all release criteria or prove every possible state/parameter configuration.
