# Operand isolation PyUVM validation

This suite validates [operand_isolation.sv](../../../rtl/common/operand_isolation.sv)
against the [MOSAIC operand isolation specification](../../../../../specs/common/mosaic-operand-isolation/README.md).
It uses real PyUVM sequences, a sequencer, driver, passive monitor, independent
port-based reference model, scoreboard, and mandatory functional coverage.
The scoreboard compares exact four-state bit strings without reading internal
RTL signals. No clock, reset, supply model, or sequential state is introduced.

## Running the tests

From `mosaic-cgra`, with Python 3.10 or newer:

```sh
make setup
make operand-isolation-regression                 # VCS on the licensed server
make operand-isolation-regression SIM=icarus      # Local four-state alternative
```

Defaults are seed `20261011` and 2000 random transactions per profile. The
minimum is 1000 random transactions. Each profile adds its full matrix index to
the seed; selecting a subset preserves the same seed as the full campaign.

```sh
make operand-isolation-regression SIM=icarus \
  OPERAND_ISOLATION_SEED=1234 OPERAND_ISOLATION_RANDOM_CYCLES=3000 \
  OPERAND_ISOLATION_REGRESSION_BUILD="$(pwd)/build/operand-isolation-custom"

.venv/bin/python src/val/common/operand_isolation/run_operand_isolation_regression.py \
  --sim icarus --build-dir build/operand-isolation-focused --case width8_mixed
```

Repeat `--case` to select multiple profiles. `--rtl /absolute/path/design.sv`
selects another implementation of the same interface. Focused campaigns still
run all parameter checks and both unknown-control assertion probes; the report
identifies them as a selected subset. `VCS_BIN_DIR` and `ICARUS_BIN_DIR` select
simulator binaries. `COMPILE_ARGS` and `SIM_ARGS` extend compiler/runtime flags.

Normal discovery runs the default 32-bit, zero-clamp instance:

```sh
make pyuvm SIM=icarus COCOTB_TOPLEVEL=operand_isolation
```

For direct parameter overrides, provide matching expected parameters:

```sh
OPERAND_ISOLATION_WIDTH=8 OPERAND_ISOLATION_CLAMP_VALUE=0xa5 \
  make pyuvm SIM=icarus COCOTB_TOPLEVEL=operand_isolation \
  COMPILE_ARGS="-Poperand_isolation.WIDTH=8 -Poperand_isolation.CLAMP_VALUE=165" \
  SIM_BUILD="$(pwd)/build/operand-isolation-direct8"
```

Direct tests accept `OPERAND_ISOLATION_SEED`, `OPERAND_ISOLATION_RANDOM_CYCLES`,
and `OPERAND_ISOLATION_COVERAGE_FILE` through the environment. The runner supplies
all expected parameters and campaign settings automatically. It uses sized
SystemVerilog literals, preserving the full clamp through 256 bits, and quotes
their apostrophes for Make's shell. Stimulus that does not fit a port is rejected.

`TEST_SETTLE_NS` defaults to zero with at least 1 ps before settled sampling.
Each transaction is checked again with both inputs held unchanged. Short holds
last 1 ps; long holds last 1 ns. The existing gate/SDF flows use
`GATE_SETTLE_NS`; choose a settling budget suitable for the actual netlist.

## Parameter matrix

| WIDTH | Clamp classes | Profiles |
|---:|---|---:|
| 1 | Zero, one | 2 |
| 8 | Zero, one, mixed | 3 |
| 16 | Zero, one, mixed | 3 |
| 32 | Zero, one, mixed | 3 |
| 64 | Zero, one, mixed | 3 |
| 128 | Zero, one, mixed | 3 |
| 256 | Zero, one, mixed | 3 |

Profile names follow `width<width>_<zero|one|mixed>`. The one clamp sets every bit;
mixed clamps repeat/truncate `10100101` to the width. A one-bit word has no mixed
class. All 20 profiles must pass the aggregate width × clamp-class coverage gate.
This is a finite specification matrix, not every possible width or clamp.

## Requirement mapping

| Specification requirement | Active stimulus and checks |
|---|---|
| Transparent operand | With control zero, exact output/input equality preserves every bit, including X and Z. |
| Constant isolated operand | With control one, every output bit equals the configured clamp, including during binary/X/Z source activity. |
| Required data classes | Zero, all-one, alternating, walking one/zero, all-X/all-Z, partial unknowns, mixed X/Z where representable, and seeded random data in both known modes. |
| Input activity in both modes | Every bit takes all four states in each mode. Every transparent bit traverses all ordered changes between four-state values, with zero and one background words. Every bit toggles zero-to-one and one-to-zero while isolated. |
| Assertion and release | Every ordered control pair is crossed with stable and changing data, including simultaneous changes and recovery from illegal controls. |
| Unknown/high-impedance control | X and Z each trigger the known-control assertion and poison the complete output to X, even where source and clamp bits agree. |
| No stale value or state | Compare against current ports, return to previous patterns, recover known controls, test consecutive assertion/release, and repeat every check after a stable hold. |
| Long operation sequences | 2000 seeded random transactions by default, plus 64 long-held changing-input transactions in each known mode. |
| Required crosses | Isolation state × stable/changing data, control transition × data activity, and aggregate width × clamp class. |

Widths through eight run all binary input words in both known modes. Widths
through two also run every four-state input/control truth-table entry. Wide
operands use directed bit tests and randomized samples rather than exhaustive
enumeration. All per-profile coverage goals must be met; bins appear in JSON.
The datapath-use-case × isolation-state cross belongs to integration tests and
remains `NOT_RUN` here.

## Assertions and output activity

Transparent equality, constant clamp, and known-control properties are active
Python scoreboard assertions. Deliberate X/Z transactions explicitly acknowledge
an expected known-control assertion failure while continuing to check the output.
The first diagnostic for each illegal state is logged, and every expected
violation is counted in `coverage.json`. An untagged illegal control raises
`AssertionError` and fails the simulation.

The runner proves that behavior with separate X and Z probes using the same
live PyUVM scoreboard. A probe passes only when the exact expected test runs,
its JUnit record contains a failure, and the simulation log contains the
matching known-control assertion diagnostic. A compiler error, skipped test,
or unrelated test failure cannot pass. The internal
`OPERAND_ISOLATION_CONTROL_PROBE` variable is used only for these negative checks.
HDL-bound SVA and formal proofs are separate `NOT_RUN` checks.

The activity monitor watches `o_data` while isolation remains asserted, while
an unknown control remains fixed, and while all inputs remain stable. It checks
changes after combinational delta cycles at each observed output-change time.
A finite pulse persisting into the read-only phase fails even if it disappears
before settled sampling. This is not a guarantee about zero-duration delta
events or physical hazards during control transitions. A control transition or
transparent data change may alter the output before the settling point.

## Reports and parameter guards

Reports default to `build/<simulator>/operand_isolation/regression`:

| File | Contents |
|---|---|
| `<profile>/results.xml` | Exactly one successful, unskipped `test_operand_isolation.OperandIsolationTest`. |
| `<profile>/coverage.json` | Width/clamp/seed, transaction and held counts, four-state bins, expected control violations, and mandatory goals. |
| `<profile>/simulation.log` | Native compilation, expected unknown-control diagnostics, and PyUVM results. |
| `<profile>/parameters.json` | Compile dependency forcing changed parameters to rebuild. |
| `invalid_parameters/<case>/elaboration.log` | Native rejection with the intended parameter guard. |
| `unknown_control_checks/<x|z>/results.xml` | Expected failing test proving the known-control assertion is active. |
| `unknown_control_checks/<x|z>/simulation.log` | Matching assertion diagnostic. |
| `summary.json` | Aggregate status, source hashes, matrix gate, negative checks, and external checks. |

Three negative parameter cases cover zero width and an X or Z bit in the clamp.
Each requires a nonzero native compiler exit with the intended unresolved guard
module diagnostic. X/Z literals are instantiated in SV wrappers because Icarus's
command-line defparam parser cannot pass them faithfully. The actual rejection
stage is elaboration. All positive clamp literals are exactly `WIDTH` bits.
These cases do not prove rejection of every implicit conversion or caller
literal width; the RTL's typed parameter applies normal SystemVerilog resizing.

Stale JUnit and coverage reports are removed before each profile/probe. Missing,
duplicate, skipped, wrong, or failed positive tests cannot pass. Coverage gaps,
parameter mismatches, and incorrect seed/random counts fail the campaign.
Missing binaries or recognized license checkout failures produce `NOT_RUN` and
a nonzero exit. `make -n operand-isolation-regression` prints commands without
running the wrapper or changing existing reports.

## Integration and power boundary

This primitive implements architectural data gating. It must not be credited
as a UPF power-domain isolation cell or a synchronizer. Standalone simulation
cannot prove accepted-operation correctness across valid/ready/stall/kill,
predicate or pipeline state, CDC/RDC compatibility, DFT controllability, or power
intent sequencing. Those integration checks remain `NOT_RUN`.

Output inactivity is functional evidence, not a power or energy estimate. Net
savings require equivalent downstream datapaths with/without isolation and
representative activity, including always-transparent, active, isolated, and
control-transition intervals. Annotated PrimePower results must include the
complete downstream cone, isolation/control overhead, leakage, and activity
coverage. Commercial lint, formal, synthesis/equivalence, PrimeTime, PrimePower,
CDC/RDC, DFT, VC LP, and downstream savings remain `NOT_RUN` in this campaign.

## Local validation evidence

Native local results use Python 3.12, cocotb 2.1.0, PyUVM 5.0.0, and Icarus 12.0.

- All 20 profiles passed: 253,284 checked transactions, including 40,000 random
  transactions, plus 253,284 held-input checks. All functional goals and the
  aggregate width/clamp-class cross passed.
- All three invalid-parameter cases failed native elaboration with the intended
  guard diagnostics. Both untagged X/Z control probes failed the live PyUVM
  known-control assertion as required.
- Sixteen temporary, compilable RTL defects were detected: inverted control,
  reversed bits, a dropped bit, Z-to-X coercion, zero/one/shifted clamps,
  retained transparent/isolated data, unknown-control pass-through/clamping,
  conditional merge behavior, two missing parameter guards, and 1 ps isolated
  and stable-input output glitches. The isolated pulse was detected before a
  10 ps transaction sample; the stable pulse was detected during a held interval.
- Verilator `--lint-only --timing -Wall` passed all 20 profiles without waivers.
  The existing 31 synthesis/power orchestration checks passed with licensed
  tool commands stubbed.
- Direct Makefile discovery from another directory passed. A custom two-bit,
  mixed-clamp instance passed the exhaustive four-state truth table. A relative
  simulator binary directory and custom seed/random count passed. Dry runs and
  invalid random settings preserved reports. Missing VCS and a stubbed license
  failure produced `NOT_RUN` rather than a functional pass.

Native reports are in ignored `build/icarus/operand_isolation/regression`;
supporting evidence is in `build/validation/operand_isolation`. Source hashes
identify the tested RTL and scripts. Native VCS and physical/integration release
checks remain `NOT_RUN` locally. No downstream power savings are claimed.
