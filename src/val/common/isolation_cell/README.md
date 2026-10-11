# Isolation cell PyUVM validation

This suite validates `src/rtl/common/isolation_cell.sv` against the
[MOSAIC isolation cell specification](../../../../../specs/common/mosaic-isolation-cell/README.md).
It uses real PyUVM sequences, a sequencer, driver, passive monitor, independent
four-state model, scoreboard, and mandatory functional coverage. The reference
model reads interface ports and configured parameters, without reading RTL
internal nodes or copying the implementation's conditional expression.

## Running the tests

From `mosaic-cgra`, using Python 3.10 or newer:

```sh
make setup
make isolation-cell-regression                  # VCS on the licensed server
make isolation-cell-regression SIM=icarus       # Four-state local alternative
```

Configure the randomized campaign and report location:

```sh
make isolation-cell-regression SIM=icarus ISOLATION_CELL_SEED=1234 \
  ISOLATION_CELL_RANDOM_CYCLES=3000 \
  ISOLATION_CELL_REGRESSION_BUILD="$(pwd)/build/isolation-custom"
```

Defaults are seed `20261011` and 2000 random transactions per configuration.
At least 1000 random transactions are required. Each profile adds its matrix
index to the seed. `VCS_BIN_DIR` and `ICARUS_BIN_DIR` select simulator binaries;
`COMPILE_ARGS` and `SIM_ARGS` extend the native compiler and runtime options.
`TEST_SETTLE_NS` defaults to zero, with a minimum 1 ps interval before settled
sampling. No clock or reset is used.

Run a focused profile, including all five invalid-parameter guard checks:

```sh
.venv/bin/python src/val/common/isolation_cell/run_isolation_cell_regression.py \
  --sim icarus --build-dir build/isolation-focused --case width8_low_mixed
```

Repeat `--case` to select several profiles. Use `--rtl /absolute/path/design.sv`
to test an alternative implementation without changing the original source.
Reports distinguish selected profiles from the full specification matrix.

The normal Makefile discovery also runs the default single-bit, active-high,
clamp-zero instance:

```sh
make pyuvm SIM=icarus COCOTB_TOPLEVEL=isolation_cell
```

For direct parameterized runs, set the matching `ISOLATION_CELL_WIDTH`,
`ISOLATION_CELL_CLAMP_VALUE`, and `ISOLATION_CELL_ACTIVE_HIGH` environment
variables. The regression runner supplies them automatically and uses sized
SystemVerilog clamp and polarity literals, preserving their apostrophes through
the Make shell command. Data/output widths, report parameters, and seeds must
match the requested configuration.

## Parameter matrix

| WIDTH | Polarities | Clamp classes | Profiles |
|---:|---|---|---:|
| 1 | High, low | Zero, one | 4 |
| 2 | High, low | Zero, one, mixed | 6 |
| 4 | High, low | Zero, one, mixed | 6 |
| 8 | High, low | Zero, one, mixed | 6 |
| 16 | High, low | Zero, one, mixed | 6 |
| 32 | High, low | Zero, one, mixed | 6 |
| 64 | High, low | Zero, one, mixed | 6 |

Profile names follow `width<width>_<high|low>_<zero|one|mixed>`.
The one clamp sets every bit; mixed clamps repeat and truncate `10010110` to
the selected width. A one-bit bus has no mixed clamp class. The aggregate
coverage gate checks the complete width × polarity × clamp-class cross.

## Requirements and active checks

| Specification requirement | Stimulus and checks |
|---|---|
| Inactive pass-through | Exact string comparison against actual four-state `i_data`; every bit passes zero, one, X, and Z. |
| Active known clamp | Exact comparison against the configured clamp, including all-X/all-Z source corruption; every bit is checked. |
| Both control polarities | Every supported width/clamp combination runs in both active-high and active-low configurations. |
| Unknown isolation control | X/Z each produce an expected known-control assertion diagnostic; the independent bitwise model also checks conservative merging. |
| Correct conditional merge | For each bit and each X/Z control, equal pass/clamp bits stay known; unequal, X, or Z source bits become X. |
| Data pattern classes | All zero/one, walking one/zero, alternating, all-X/all-Z, partial unknowns, and mixed X/Z vectors; seeded random activity. |
| Assertion and release | Every directed pattern is observed with unchanged data across both control transitions, including unknown data. |
| Data activity before/during/after isolation | Pass-through activity, continuously isolated source changes, and renewed activity after release; repeated transitions and long intervals. |
| Isolation prevents downstream activity | Every observable output change is rejected during continuously isolated intervals, including transients before settled sampling. |
| Small-width complete truth tables | Every four-state data vector × every control value (`0`, `1`, `X`, `Z`) for widths 1, 2, and 4. |
| Width/clamp and polarity/state crosses | Full 40-profile parameter matrix; each profile covers active, inactive, and unknown control states and all required pattern classes. |

The required combinational clamp/pass assertions and known-control assertion
are active Python checks in the scoreboard. Expected illegal-control tests
record diagnostics and coverage; an unexpected unknown fails. Illegal control
does not disable output checking: the portable model's conservative four-state
output remains mandatory. HDL-bound SVA is a separate `NOT_RUN` check.

The passive output listener re-arms immediately without a `ReadOnly` wait.
A glitch that disappears before the settled transaction sample still fails
while isolation remains asserted. Clamp assertion and release may change the
output, as allowed by the specification. This RTL simulation does not impose
physical delay, bus-atomicity, or receiving-protocol timing requirements.

## Power-aware integration boundary

The sequence illustrates logical corruption and restoration: establish valid
source data, assert isolation, drive source X/Z values, restore valid data while
isolated, then release isolation. These are logical input patterns in a portable
model with no supply ports, UPF, or technology-cell instances.

Power-state-table coverage, supply removal/restoration, power-good/state-valid
sequencing, always-on control supplies, protocol-safe clamps, transaction drain,
retention policies, and separate/combined level-shifter implementations require
the actual integration harness, UPF, and approved library models. Their results
are explicitly `NOT_RUN`; no simulated supply state or physical isolation-cell
signoff is inferred from this campaign.

## Reports and parameter guards

Reports default to `build/<simulator>/isolation_cell/regression`:

| File | Contents |
|---|---|
| `<profile>/results.xml` | Exactly one successful, unskipped `test_isolation_cell.IsolationCellTest`. |
| `<profile>/coverage.json` | Parameters, seed, transaction counts, bit/merge/control/pattern bins, and coverage goals. |
| `<profile>/simulation.log` | Native compilation and PyUVM simulation output. |
| `<profile>/parameters.json` | Compile dependency that forces rebuilding when parameters change. |
| `invalid_parameters/<case>/guard.log` | Native compiler/startup diagnostic for an invalid parameter case. |
| `summary.json` | Matrix results, source hashes, guard stages, specification gaps, and external checks. |

Five guard checks require rejection of `WIDTH=0` and X/Z clamp bits with both
control polarities. An unrelated compiler error cannot satisfy a guard check:
the intended diagnostic and a failing compiler or simulator exit are required.
The current RTL uses `initial $fatal`, so Icarus rejects these cases at
**simulation startup**. The specification's strict elaboration-validation
requirement is recorded as `BLOCKED`. Typed clamp and polarity parameters also
resize/coerce caller literals; these checks do not prove rejection of every
incorrectly sized clamp literal or non-boolean polarity override. The RTL is
unchanged.

Old JUnit/coverage reports are removed before each profile. Missing, skipped,
duplicated, wrongly selected, or failed tests cannot pass. Missing bins,
parameter/seed mismatches, and incorrect random counts also fail the target.
Missing simulator binaries and recognizable license checkout failures produce
`NOT_RUN` and a nonzero exit. `make -n isolation-cell-regression` prints its
command without running the wrapper or modifying existing reports.

## Local validation evidence

With Python 3.12, cocotb 2.1.0, PyUVM 5.0.0, and Icarus 12.0:

- All 40 profiles passed: 142,272 checked transactions, including 80,000
  randomized transactions, with every functional goal and four-state bit bin
  covered. All 16 width-1/2/4 profiles passed exhaustive four-state truth tables.
- Five invalid-parameter cases were rejected by their intended startup guards.
- Thirteen isolated RTL mutants were detected: reversed data/clamp ordering,
  wrong polarity/clamp, ignored isolation, X/Z data coercion, fail-open,
  fail-closed, and overly pessimistic unknown-control behavior, retained data,
  removed width/clamp guards, and a 1 ps isolated-output glitch.
- Verilator `--lint-only --timing -Wall` passed all 40 configurations without
  waivers. All 31 existing synthesis/power orchestration checks passed with
  licensed tool commands stubbed.
- Direct Make execution from another directory passed. Dry runs and invalid
  random settings preserved existing reports. Missing VCS and a stubbed license
  checkout failure both produced `NOT_RUN`.

Evidence is stored in ignored `build/validation/isolation_cell`; native reports
are in `build/icarus/isolation_cell/regression`. Source hashes identify the
validated RTL and verification scripts. VCS, HDL SVA, formal, technology
equivalence, UPF power-aware simulation, commercial static/integration checks,
physical implementation, timing, and power are `NOT_RUN` locally. This finite
functional campaign does not prove all wide-bus vectors or satisfy power-gating
implementation release criteria.
