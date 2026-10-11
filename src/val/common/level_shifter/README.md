# Level shifter PyUVM validation

This suite validates `src/rtl/common/level_shifter.sv` against the
[MOSAIC level shifter specification](../../../../../specs/common/mosaic-level-shifter/README.md).
It uses real PyUVM sequences, a sequencer, driver, passive monitor, independent
bitwise reference model, scoreboard, and mandatory coverage. The model reads
only interface ports and implements the specification's four-entry identity
truth table; it reads no RTL internal nodes.

## Running the tests

From `mosaic-cgra`, using Python 3.10 or newer:

```sh
make setup
make level-shifter-regression                  # VCS on the licensed server
make level-shifter-regression SIM=icarus       # Local four-state alternative
```

The 14-profile matrix crosses widths `1, 2, 4, 8, 16, 32, 64` with direction
zero (low-to-high, `l2h`) and one (high-to-low, `h2l`). Direction is an elaboration
parameter and does not select a runtime datapath. The portable model has no
voltage or supply ports; its functional checks assume valid powered operation.

Defaults are seed `20261011` and 2000 randomized transactions per configuration.
At least 1000 random transactions are required. Each width adds its index in
the width list to the seed. Both directions use the same seed and full input
history at that width. An aggregate gate compares their stimulus hashes, while
both implementations independently must preserve every sampled bit.

```sh
make level-shifter-regression SIM=icarus LEVEL_SHIFTER_SEED=1234 \
  LEVEL_SHIFTER_RANDOM_CYCLES=3000 \
  LEVEL_SHIFTER_REGRESSION_BUILD="$(pwd)/build/level-shifter-custom"

.venv/bin/python src/val/common/level_shifter/run_level_shifter_regression.py \
  --sim icarus --build-dir build/level-shifter-focused --case width8_h2l
```

Repeat `--case` to choose multiple configurations. Use
`--rtl /absolute/path/level_shifter.sv` to validate another implementation.
Focused campaigns still run all six invalid-parameter checks and record their
selected scope. `VCS_BIN_DIR` and `ICARUS_BIN_DIR` select simulator binaries;
`COMPILE_ARGS` and `SIM_ARGS` extend native compiler/runtime options.

The normal Makefile discovery runs the default single-bit, low-to-high instance:

```sh
make pyuvm SIM=icarus COCOTB_TOPLEVEL=level_shifter
```

For a direct parameterized run, supply matching expected parameters through the
environment and choose a separate build directory:

```sh
LEVEL_SHIFTER_WIDTH=8 LEVEL_SHIFTER_DIRECTION=1 \
  make pyuvm SIM=icarus COCOTB_TOPLEVEL=level_shifter \
  COMPILE_ARGS="-Plevel_shifter.WIDTH=8 -Plevel_shifter.DIRECTION=1" \
  SIM_BUILD="$(pwd)/build/level-shifter-direct8"
```

Direct tests also accept `LEVEL_SHIFTER_SEED`, `LEVEL_SHIFTER_RANDOM_CYCLES`,
and `LEVEL_SHIFTER_COVERAGE_FILE` through the environment. The runner sets
these automatically. Both port widths must match the requested width.
`TEST_SETTLE_NS` defaults to zero, with a minimum 1 ps before settled sampling.
Each transaction is checked again after an unchanged-input interval; directed
long holds last 4 ns and rapid transitions use 1 ps holds. No clock or reset
is required. For an implemented netlist/SDF, the existing gate targets supply
`GATE_SETTLE_NS`; choose enough time for the actual characterized propagation.
This test does not measure physical delay or bus skew.

## Requirement mapping and coverage

| Specification requirement | Stimulus and active checks |
|---|---|
| Non-inverting pass-through | Exact four-state equality with the actual source port, evaluated through the independent bitwise truth table. |
| Preserved bus ordering | Walking-one/zero patterns and exact per-bit comparison at every transaction. |
| Both translation directions | All representative widths in both directions; paired input histories and direction × pattern coverage. |
| Uniform and mixed data | All zero/one, alternating, walking one/zero, mixed binary, all-X/all-Z, partial unknowns, and mixed X/Z vectors. |
| Four-state propagation | Every bit passes zero, one, X, and Z without coercion, clamping, inversion, or Z-to-X conversion. |
| Independent activity | Every ordered four-state transition on each individual bit, with all other bits held zero and then one. |
| Every bit toggles both ways | Mandatory per-bit zero-to-one and one-to-zero bins within the complete independent-transition cross. |
| Stable source data | Short/long holds, repeated values, a second settled check after each hold, and continuous output inactivity while the source stays stable. |
| Rapid/random changes | Back-to-back transactions, revisited patterns, random binary words, partial unknowns, and independent four-state random bits. |
| No retained state | Output follows current input at both samples; revisited words must behave identically regardless of preceding data. |
| Width × direction | Full seven-width × two-direction cross; all coverage goals must pass in every configuration. |
| Invalid parameters | Intended rejection diagnostics for zero width in both directions, and numeric directions `2` and `-1` at widths one and four. |

Widths through eight run every binary word. Widths one, two, and four also run
every four-state word: 4, 16, and 256 combinations. At every width, independent
bit stimulus covers all 16 ordered four-state transition pairs on both known
backgrounds, including same-state transitions. These are complete bit-transition
checks, not exhaustive wide-bus vector or transition-pair enumeration.

Unknown source data is legal in the portable model. Assertions remain active
for X and Z and require exact preservation. The specification's powered-state
equality assertion is implemented as an active Python scoreboard check at
each settled and held sample. There is no invented power-state signal gating
these checks. HDL-bound SVA is recorded separately as `NOT_RUN`.

The continuous listener re-arms immediately without waiting for `ReadOnly`.
Once a transaction has settled, every observable output change during its
unchanged-input interval fails, including glitches that vanish before the held
sample. Changes before the configured settling point are allowed. Observing
portable functional behavior does not prove atomic multi-bit transfer, safe
CDC, technology-cell behavior, or physical voltage conversion.

## Reports and parameter validation

Reports default to `build/<simulator>/level_shifter/regression`:

| File | Contents |
|---|---|
| `<profile>/results.xml` | Exactly one successful, unskipped `test_level_shifter.LevelShifterTest`. |
| `<profile>/coverage.json` | Parameters, seed, stimulus hash, transaction/held/random counts, four-state bit/transition/pattern bins, and goals. |
| `<profile>/simulation.log` | Native compilation and PyUVM simulation output. |
| `<profile>/parameters.json` | Compile dependency forcing parameter changes to rebuild the simulator. |
| `invalid_parameters/<case>/guard.log` | Native compiler/startup diagnostics for invalid configurations. |
| `summary.json` | Matrix and paired-stimulus gates, source hashes, parameter rejection stages, specification gaps, and external checks. |

Old JUnit/coverage files are removed before each profile. A missing, duplicate,
skipped, wrongly selected, or failed test cannot pass. Missing bins, incorrect
parameters/seeds/random counts, and matrix mismatches also fail. Missing tools
and recognizable license checkout failures produce `NOT_RUN` with a nonzero
exit. Dry runs print commands without running the wrapper or changing reports.

Six negative cases require the intended width/direction diagnostic and a failing
compiler or runtime exit. An unrelated syntax error or the wrapper's fallback
failure cannot satisfy a guard check. The unchanged RTL uses `initial $fatal`;
Icarus rejects these configurations at **simulation startup**. The stricter
elaboration-time requirement is recorded as `BLOCKED`. These finite checks
cover the listed numeric overrides, rather than every possible caller literal
or implicit conversion of the unsigned integer parameters.

## Power-aware and physical release boundary

The portable simulation supplies ordinary digital data and has no explicit
supplies, target UPF loaded into the simulator, voltage views, or bound
technology cells. All-X source data tests four-state propagation; it does not
simulate removal of source power. Both directions must have identical logical
behavior, but this does not demonstrate translation between any voltage pair.

Actual power-aware verification must use the implementation's UPF and approved
cell models. Reports record the following as `NOT_RUN` in this campaign:

- Legal and illegal source/destination power-state pairs, power-up/down
  transitions, supported voltage pairs, and DVFS transitions.
- Separate/combined isolation structures, isolation assertion before source
  shutdown, release after valid restoration, and prevention of consuming
  unavailable or unstable destination data.
- Formal/equivalence, CDC/RDC, DFT, and required VC LP signoff of complete bus
  insertion, direction, approved cells, supplies, and lack of duplicate shifts.
- Synthesis/physical implementation, placement and rail connectivity, DRC/LVS,
  cross-voltage timing arcs and skew, and multi-supply PrimePower analysis.

Power, leakage, isolation/buffering overhead, and the complete multi-voltage
energy tradeoff need representative implemented-design activity and libraries.
This standalone functional regression publishes portable-model evidence and
does not meet the specification's multi-voltage implementation release criteria.

## Local validation evidence

Native local results use Python 3.12, cocotb 2.1.0, PyUVM 5.0.0, and Icarus 12.0.

- All 14 profiles passed: 51,214 checked transactions, including 28,000 random
  transactions, plus 51,214 held-input checks. Every functional goal and the
  aggregate width/direction, direction/pattern, and paired-stimulus gates passed.
- Six intended invalid-parameter guards rejected their configurations at startup.
- Fourteen isolated, compilable RTL mutants were detected: inversion, constant
  zero/one outputs, reversed bits, broadcast bit zero, a missing most-significant
  bit, Z-to-X coercion, unknown fail-open/fail-closed behavior, direction-dependent
  inversion, retained state, removed width/direction guards, and a 1 ps glitch
  during stable source data. The continuous monitor detected the glitch before
  the held sample.
- Verilator `--lint-only --timing -Wall` passed all 14 configurations without
  waivers. The existing 31 synthesis/power orchestration checks passed with
  licensed commands stubbed.
- Direct Makefile discovery from another directory passed. A focused campaign
  with a relative simulator binary directory and custom seed/random count passed.
  Dry runs and invalid random settings preserved reports. Missing VCS and a
  stubbed license checkout failure both produced `NOT_RUN`.

Native reports are in ignored `build/icarus/level_shifter/regression`; supporting
evidence is in `build/validation/level_shifter`. Source hashes identify the RTL
and verification scripts. VCS and all power-aware/technology release checks
remain `NOT_RUN` locally.
