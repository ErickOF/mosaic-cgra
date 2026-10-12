# Lane mask PyUVM validation

This suite validates `src/rtl/common/lane_mask.sv` against the
[MOSAIC lane mask specification](../../../../../specs/common/mosaic-lane-mask/README.md).
It uses real PyUVM sequences, a sequencer, driver, passive monitor, scoreboard,
and mandatory coverage. The independent reference model reads only interface
ports and evaluates each lane with a four-state truth table. It uses no RTL
internal signals and does not copy the RTL's vector expression.

## Running the tests

From `mosaic-cgra`, using Python 3.10 or newer:

```sh
make setup
make lane-mask-regression                  # VCS on the licensed server
make lane-mask-regression SIM=icarus       # Local four-state alternative
```

The matrix covers `LANES=1, 2, 3, 4, 8, 16`. The specification requires all of
these except three, which checks a non-power-of-two size. Defaults are seed
`20261011` and 2000 random transactions per profile. Each profile adds its matrix
index to the seed, including when selecting a subset. At least 1000 random
transactions are required.

```sh
make lane-mask-regression SIM=icarus LANE_MASK_SEED=1234 \
  LANE_MASK_RANDOM_CYCLES=3000 \
  LANE_MASK_REGRESSION_BUILD="$(pwd)/build/lane-mask-custom"

.venv/bin/python src/val/common/lane_mask/run_lane_mask_regression.py \
  --sim icarus --build-dir build/lane-mask-focused --case lanes8
```

Repeat `--case` to select multiple profiles. `--rtl /absolute/path/lane_mask.sv`
selects another implementation without changing the source. The runner records
whether it executed the whole matrix or a selected subset. `VCS_BIN_DIR` and
`ICARUS_BIN_DIR` select simulator binaries; `COMPILE_ARGS` and `SIM_ARGS` extend
the native compile/runtime options.

The standard Makefile discovery runs the default four-lane instance:

```sh
make pyuvm SIM=icarus COCOTB_TOPLEVEL=lane_mask
```

For direct parameterized simulation, set the matching `LANE_MASK_LANES`
environment variable, for example:

```sh
LANE_MASK_LANES=8 make pyuvm SIM=icarus COCOTB_TOPLEVEL=lane_mask \
  COMPILE_ARGS=-Plane_mask.LANES=8 SIM_BUILD="$(pwd)/build/lane-mask-direct8"
```

Direct tests accept `LANE_MASK_SEED`, `LANE_MASK_RANDOM_CYCLES`, and
`LANE_MASK_COVERAGE_FILE` through the environment; the regression supplies them
automatically. `TEST_SETTLE_NS` defaults to zero, with at least 1 ps before
settled sampling. There is no clock, reset, or stall input. For gate/SDF
simulation, select sufficient settling time using `GATE_SETTLE_NS`, supported
by the existing gate targets. Functional masks may transiently change while
controls settle; this suite does not impose glitch-free physical clock gating.

## Requirement mapping and coverage

| Specification requirement | Stimulus and active checks |
|---|---|
| Canonical activity | Compare every output bit with an independent per-lane truth table for operation-valid, lane-valid, mask, and predicate. |
| Derived controls | Exact four-state complement for isolation; exact equality for the base write mask. Derived outputs cannot contain Z. |
| Invalid operation | Known zero global valid suppresses every lane, including all-X/all-Z lane controls. |
| Every lane independently active | One-hot masks for each of the three vector controls; all other controls asserted. |
| Every input source disables a lane | Isolate each lane-valid, mask, and predicate bit; global-valid suppression with all local controls asserted. |
| Lane independence | Toggle each vector bit in both directions and check that every other output bit remains unchanged. |
| All-active/all-inactive and population counts | Cover every count from zero through `LANES`, and every ordered population-count transition pair. |
| Tail and boundary masks | Every low contiguous tail length, additional high contiguous masks, walking one/zero, and alternating patterns. |
| Noncontiguous predicates | The full directed pattern set is applied as predicates, including alternating/noncontiguous patterns where representable. |
| Mask cross coverage | Lane-valid × mask and mask × predicate cover every ordered pair in the finite directed mask set. |
| Simultaneous and back-to-back changes | Change all four input ports together; drive and check every transaction without a clock boundary. |
| No retained state | Repeated unchanged inputs, short/long held masks, revisited masks, and exact checks after changing all controls. |
| Unknown controls | Active known-control diagnostics for operation-valid X/Z always, and for lane-control X/Z when operation-valid is one. |
| Four-state output behavior | A zero dominates; four known ones activate a lane; all remaining combinations produce X, including Z operands. |
| Lane count coverage | Every required size plus `LANES=3`; exact widths checked on all vector ports. |

Each lane runs all 16 binary and all 256 four-state combinations of its four
controls. Other lanes remain asserted during per-lane tests to expose coupling.
`LANES=1, 2, 3, 4` also cover every complete binary input vector. `LANES=1, 2`
cover every complete four-state input vector: 256 and 16,384 combinations.

The finite directed mask set includes zero, all ones, every walking one and
zero, every low/high contiguous tail, and both alternating patterns. The two
vector crosses cover its complete Cartesian square. For `LANES=8, 16`, this
does not exhaust every possible vector pair. Random activity supplements the
directed tests. Coverage gates require all designated bins; counts and actual
bin values are included in `coverage.json`.

The required functional and known-control assertions are active Python checks
in the scoreboard. Negative sequences mark expected illegal controls separately
from the monitor's actual-port detection. Unexpected unknowns fail; expected
unknowns are logged and counted. Output checking stays active in negative
tests, including unknown suppression by any controlling zero. Lane-control
X/Z with a known invalid operation is legal at this module boundary and must
produce known disabled outputs. HDL-bound SVA remains a separate `NOT_RUN` check.

## Reports and parameter rejection

Reports default to `build/<simulator>/lane_mask/regression`:

| File | Contents |
|---|---|
| `<profile>/results.xml` | Exactly one successful, unskipped `test_lane_mask.LaneMaskTest`. |
| `<profile>/coverage.json` | Parameters, seed, transaction counts, truth-table/control/mask/transition bins, and coverage goals. |
| `<profile>/simulation.log` | Native compilation and PyUVM output. |
| `<profile>/parameters.json` | Compile dependency forcing parameter changes to rebuild the simulator. |
| `invalid_parameters/zero_lanes/guard.log` | Native diagnostic and exit status for `LANES=0`. |
| `summary.json` | Profile results, matrix gate, source hashes, parameter rejection stage, gaps, and external checks. |

The runner rejects missing, duplicate, skipped, wrongly selected, or failing
tests; missing coverage, parameter/seed mismatches, and incorrect random counts
also fail. Old JUnit and coverage reports are removed before each profile.
Missing simulator binaries and recognizable license checkout failures produce
`NOT_RUN` and a nonzero exit. `make -n lane-mask-regression` prints the command
without running the wrapper or changing reports.

The zero-lane test accepts the intended `LANES` guard diagnostic with a failing
compiler/runtime exit. For Icarus, it also recognizes its specific elaboration
error for a zero-count concatenation. An unrelated compile error cannot pass.
The report distinguishes `explicit_guard` from `structural_replication`, and
records the actual rejection stage.

In the existing RTL, `LANES=0` is rejected during Icarus elaboration by the
zero-count replication before the `initial $fatal` can execute. Rejection
passes, but coverage of that explicit guard is `BLOCKED`; removing the guard
would still produce the structural rejection. Other simulators may execute
the guard at startup, which is recorded separately with the strict
elaboration-time requirement `BLOCKED`. No native VCS parameter result is
inferred from the Icarus result. The RTL remains unchanged.

## Integration and release boundary

This standalone module has no data, state, consumer clock, stall, operation
class, datatype, or precision interface. Consequently lane-data alignment,
write-request/kill/acceptance gating, prevention of inactive architectural
writes, reductions and identity values, stall-mask stability, in-flight context
changes, and mask × datatype/operation/stall crosses require a lane-aware
integration harness. They are recorded as `NOT_RUN` rather than simulated
with invented interfaces.

Clock gating needs an approved boundary and pipeline retirement policy.
CDC/RDC, DFT, VC LP, formal proofs, logical equivalence, synthesis of independent
combinational logic, timing to actual consumers, and PrimePower analysis of
net lane-energy savings require the corresponding tools, libraries, and
downstream design. Functional output activity alone does not demonstrate
energy savings or authorize direct combinational clock gating.

## Local validation evidence

Native local results use Python 3.12, cocotb 2.1.0, PyUVM 5.0.0, and Icarus 12.0.

- All six profiles passed: 59,562 checked transactions, including 12,000
  randomized transactions and 952 repeated-input checks. Every functional
  coverage goal passed, including exhaustive small-vector truth tables.
- Twelve isolated, compilable RTL mutants were detected by actual PyUVM
  failures: each of the four omitted control sources, wrong isolation polarity,
  broadcast write/activity masks, reversed lane-valid ordering, unknown
  fail-open/fail-closed behavior, overly pessimistic unknowns, and retained state.
- Verilator `--lint-only --timing -Wall` passed every configuration without
  waivers. The existing 31 synthesis/power orchestration checks passed with
  licensed tool commands stubbed.
- Direct Makefile discovery from another directory passed the default
  four-lane instance. Dry runs and invalid random settings preserved reports.
  Missing VCS and a stubbed license checkout failure both produced `NOT_RUN`.

Native reports are in ignored `build/icarus/lane_mask/regression`; supporting
evidence is in `build/validation/lane_mask`. Source hashes identify the tested
RTL and scripts. VCS and downstream release checks remain `NOT_RUN` locally.
This finite functional campaign does not prove all wide-vector inputs or
fulfill the specification's integration and physical release criteria.
