# Reset synchronizer PyUVM validation

This suite validates [reset_synchronizer.sv](../../../rtl/common/reset_synchronizer.sv)
against the [MOSAIC reset synchronizer specification](../../../../../specs/common/mosaic-reset-synchronizer/README.md).
It uses real PyUVM sequences, a sequencer, driver, passive monitor, independent
event-count reference model, scoreboard, active assertions, and mandatory
functional coverage. The model counts qualifying rising edges after reset or
unknown-state initialization; it does not duplicate the RTL shift-register code.

## Running the tests

From `mosaic-cgra`, with Python 3.10 or newer:

```sh
make setup
make reset-synchronizer-regression                 # VCS on the licensed server
make reset-synchronizer-regression SIM=icarus      # Local four-state alternative
```

The matrix contains `stages2`, `stages3`, and `stages4`. Defaults are seed
`20261011` and 2000 random clock/reset actions per profile; at least 1000 are
required. Each profile adds its full matrix index to the seed, even in a subset.

```sh
make reset-synchronizer-regression SIM=icarus \
  RESET_SYNCHRONIZER_SEED=1234 RESET_SYNCHRONIZER_RANDOM_CYCLES=3000 \
  RESET_SYNCHRONIZER_REGRESSION_BUILD="$(pwd)/build/reset-custom"

.venv/bin/python src/val/common/reset_synchronizer/run_reset_synchronizer_regression.py \
  --sim icarus --build-dir build/reset-focused --case stages3
```

Repeat `--case` for several profiles. `--rtl /absolute/path/design.sv` selects
another implementation of the same interface and portable stage vector. Focused
campaigns still run both parameter guards and X/Z assertion probes. Reports
identify selected subsets separately from the full matrix. `VCS_BIN_DIR` and
`ICARUS_BIN_DIR` select binaries; `COMPILE_ARGS` and `SIM_ARGS` extend native flags.

Normal discovery runs the default two-stage instance:

```sh
make pyuvm SIM=icarus COCOTB_TOPLEVEL=reset_synchronizer
```

For direct overrides, provide the expected depth as well:

```sh
RESET_SYNCHRONIZER_STAGES=5 \
  make pyuvm SIM=icarus COCOTB_TOPLEVEL=reset_synchronizer \
  COMPILE_ARGS="-Preset_synchronizer.STAGES=5" \
  SIM_BUILD="$(pwd)/build/reset-direct5"
```

Direct tests accept `RESET_SYNCHRONIZER_SEED`, `RESET_SYNCHRONIZER_RANDOM_CYCLES`,
and `RESET_SYNCHRONIZER_COVERAGE_FILE` through the environment. The runner supplies
matching expected depth and settings automatically and requires portable stage
assertions for every matrix profile.

## Timing controls

| Environment variable | Default | Meaning |
|---|---:|---|
| `TEST_CLOCK_PERIOD_NS` | 4 | Nominal directed destination-clock period. |
| `RESET_SYNCHRONIZER_NEAR_NS` | 0.01 | Reset transition offset before/after a clock edge. |
| `RESET_SYNCHRONIZER_PULSE_NS` | 0.01 | Directed short reset pulse width in the digital model. |
| `TEST_SETTLE_NS` | 0 | Must be zero; this suite verifies zero-delay RTL. |
| `RESET_SYNCHRONIZER_CHECK_STAGES` | 1 | Enable assertions on portable `sync_stages`. |

Times must be whole picoseconds with simulator precision of 1 ps or finer.
Near-edge offsets and pulse widths must be at least 3 ps; the clock period must
be even in ps, and a half-period must exceed twice both timing values. The driver
checks settled state 1 ps after each action and held state 1 ps before the next
action. Its actual drive-to-drive interval matches the requested duration,
including short pulses. Clock/reset inputs are unchanged between actions.

```sh
TEST_CLOCK_PERIOD_NS=8 RESET_SYNCHRONIZER_NEAR_NS=0.02 \
  RESET_SYNCHRONIZER_PULSE_NS=0.02 \
  make reset-synchronizer-regression SIM=icarus
```

The default 10 ps short pulse is a deliberately small digital stimulus. The
specification supplies no technology minimum pulse width; this result does not
establish a silicon minimum. PrimeTime/library pulse-width, recovery/removal,
SDF timing, and analog metastability checks remain separate `NOT_RUN` work.

## Active checks and requirement mapping

| Requirement | Stimulus and assertions |
|---|---|
| Asynchronous assertion | Assert while clock is low/high and stopped; output and every stage clear without waiting for a clock edge. |
| Exact nominal release latency | Count destination rising edges; output stays low before STAGES and releases at exactly STAGES in digital simulation. |
| Clock phase relationships | Assert/deassert during low/high phases, before/after rising/falling edges, and simultaneously with either edge. Phase bins are derived from observed ports and event times. |
| Stopped clock | Hold the clock in both phases for two periods; assertion clears state, deassertion stays pending, and already-released state remains released. |
| Clock restart | Stop at every pending edge count, restart, and complete only the remaining synchronization edges. |
| Interrupted release | Reassert at counts zero through STAGES-1 in both phases; clear all prior progress and require a fresh sequence. |
| Short pulses | Assert for the configured digital pulse width in both phases, release with stopped clock, then synchronize after restart. |
| Repeated/reset-priority behavior | Revisit reset/release sequences and change clock/reset simultaneously; asserted reset wins. |
| Random phase relationships | Seeded clock levels, known/X/Z reset values, and randomized action intervals. |
| Portable stage invariants | Exact count-derived stage values, all-stage clearing, one-stage advancement, and output equality to the final stage. |
| Waveform legality | Watch output and stages continuously; reject changes without a qualifying event and detect early/asynchronous output release, including pulses between samples. |
| Depth/phase crosses | Every reset-transition phase at depths 2, 3, 4, running/stopped transition crosses, and every reassertion/pending-stop stage/phase bin. |

The reference's expected stage word is an initial zero/X prefix followed by the
number of known ones introduced by qualifying rising edges. This independently
checks ordering and propagation using an elapsed-edge count. Output assertion,
release latency, and waveform checking remain active without internal observation.

All coverage goals are mandatory; JSON includes actual phase, stage, latency,
pulse, and unknown-input bins. Continuous monitors check delta-settled changes
at each observed event time. A finite pulse persisting into a read-only phase
fails even if it disappears before transaction sampling. The checker also
predicts the expected state at a clock event, so a premature release pulse on
an otherwise legal rising edge cannot escape the latency assertion.

## Unknown reset and RTL fixes

X and Z reset values are illegal and trigger the active Python testbench
assertion. Deliberate negative stimulus acknowledges the expected violation,
logs its first diagnostic, counts violations, and continues checking state.
An untagged unknown reset fails the simulation.

The RTL conservatively exposes unknown reset state whenever its sequential
process is triggered with an X/Z input. A 1-to-X/Z reset transition is a Verilog
negedge and poisons the chain asynchronously. A 0-to-X/Z transition is not a
negedge; an asserted chain remains low until a rising clock edge exposes the
unknown state. Known deassertion flushes that unknown state through exactly
STAGES rising edges, or a known assertion clears it immediately.

The previous `if (!i_async_rstb)` branch treated X/Z as released and could leave
`o_rstb=1` with an unknown reset. The new suite reproduced this stopped-clock
failure before the fix. Explicit four-state reset handling fixes it. Invalid
depths now instantiate an unresolved elaboration guard, and the datapath is
excluded for invalid depths to avoid unrelated part-select failures.

Separate X/Z probes prove the assertion is live. Each passes only when the
exact PyUVM test runs, JUnit reports failure, and the log contains the matching
unknown-reset assertion diagnostic. Compilation errors and unrelated failures
cannot pass. The internal `RESET_SYNCHRONIZER_UNKNOWN_PROBE` variable enables
these negative tests. HDL-bound SVA and formal proof remain `NOT_RUN` checks.

## Portable implementation and alternate interfaces

The default test reads `sync_stages` from the portable RTL and requires its
width to match STAGES. Simulator signal access must expose that vector. Missing
internal visibility fails explicitly; it is not credited as a passing stage check.

For an alternative zero-delay implementation without that portable vector,
direct `make pyuvm` runs can set `RESET_SYNCHRONIZER_CHECK_STAGES=0`. Port-based
latency, assertion, and waveform checks remain active, while coverage reports
`portable_stage_assertions=NOT_RUN`. The full regression intentionally forces
stage checking on. Technology equivalence and internal cell structure require
their own verification.

## Reports and parameter guards

Reports default to `build/<simulator>/reset_synchronizer/regression`:

| File | Contents |
|---|---|
| `<profile>/results.xml` | Exactly one successful, unskipped `test_reset_synchronizer.ResetSynchronizerTest`. |
| `<profile>/coverage.json` | Depth/seed/timing, checked/held/random counts, stage-check status, and mandatory bins/goals. |
| `<profile>/simulation.log` | Native compilation, expected unknown-reset diagnostics, and PyUVM result. |
| `<profile>/parameters.json` | Compile dependency forcing depth changes to rebuild. |
| `invalid_parameters/<case>/elaboration.log` | Rejection with the intended stage guard diagnostic. |
| `unknown_reset_checks/<x|z>/results.xml` | Expected failing live-assertion probe. |
| `unknown_reset_checks/<x|z>/simulation.log` | Matching unknown-reset diagnostic. |
| `summary.json` | Depth/phase matrix gate, source hashes, negative checks, and separate external checks. |

Zero and one stage must fail native elaboration with the intended guard-module
diagnostic. An unrelated compile error cannot pass. This finite check does not
prove rejection of every caller literal or implicit unsigned conversion.

Stale JUnit and coverage are removed before runs. Missing, duplicate, skipped,
wrong, failed, or insufficiently covered positive tests cannot pass. Parameter,
seed, or random-count mismatches fail. Missing simulator binaries or recognized
license checkout failures produce `NOT_RUN` and nonzero exit. Dry runs print
commands without executing the wrapper or changing reports.

## Integration and release boundary

Digital sequencing and stage checks do not prove metastability containment or
MTBF. Mandatory CDC and RDC signoff must recognize the chain, check raw/reset
reconvergence, and confirm one destination domain per instance. Clock-gating
startup policy, scan treatment, power/wakeup sequencing, stage placement,
technology mapping, recovery/removal, real minimum pulse width, equivalence,
and annotated PrimePower reports remain `NOT_RUN` in this campaign. No physical
release or power result is inferred from standalone simulation.

## Local validation evidence

Native local results use Python 3.12, cocotb 2.1.0, PyUVM 5.0.0, and Icarus 12.0.

- All three depths passed: 7,919 checked transactions, including 6,000 random
  actions, plus 7,919 held-input checks. All functional goals, portable stage
  assertions, and aggregate depth/phase crosses passed. There were 251 checked
  release events, all after the required number of rising edges.
- Zero/one-stage configurations failed elaboration with the intended guard.
  Both untagged X/Z probes failed the live assertion as required. The pre-fix
  RTL failed with `o_rstb=1` after a stopped-clock reset input became X.
- Eighteen temporary, compilable RTL defects were detected: the original unknown
  release behavior, synchronous assertion, falling-edge release, raw bypass,
  intermediate/late output stages, skipped/reversed shifts, partial clearing,
  inverted reset, retained release, incorrect unknown handling, a missing depth
  guard, 1 ps output/internal-stage glitches, and a premature 1 ps release pulse
  during a legal rising-clock event.
- Verilator `--lint-only --timing -Wall` passed all three depths without waivers.
  Portable Yosys synthesis preserved exactly 2/3/4 rising-edge, active-low
  asynchronous-reset flip-flops, direct stage connections, the final-stage
  output, and the RTL preservation attributes. This generic structure check
  is separate from the report's pending technology synthesis/signoff checks.
- The existing 31 synthesis/power orchestration checks passed with licensed
  tool commands stubbed. Direct Makefile discovery from another directory and
  a custom five-stage instance with an 8 ns period and 20 ps pulse/near-edge
  offsets passed. Port-only mode passed and correctly reported internal checks
  as `NOT_RUN`. Relative binary paths and custom seed/action count passed;
  dry runs and invalid random settings preserved reports. Missing VCS and a
  stubbed license failure produced `NOT_RUN`.

Native reports are in ignored `build/icarus/reset_synchronizer/regression`;
supporting evidence is in `build/validation/reset_synchronizer`. Source hashes
identify the tested RTL and scripts. Native VCS, mandatory CDC/RDC, technology
timing/pulse-width analysis, and physical/integration signoff remain `NOT_RUN`.
