# Retention register PyUVM validation

This suite validates [retention_register.sv](../../../rtl/common/retention_register.sv)
against the [MOSAIC retention register specification](../../../../../specs/common/mosaic-retention-register/README.md).
It uses real PyUVM sequences, a sequencer, driver, passive monitor, independent
visible/saved-state model, scoreboard, sampled protocol assertions, and mandatory
coverage. It publishes portable functional save/restore evidence. There are no
supply ports, UPF state transitions, or technology retention cells in this test.

## Running the tests

From `mosaic-cgra`, with Python 3.10 or newer:

```sh
make setup
make retention-register-regression                 # VCS on the licensed server
make retention-register-regression SIM=icarus      # Local four-state alternative
```

Defaults are seed `20261011` and 2000 random clocked cycles per profile; at least
1000 are required. Each profile adds its full matrix index to the seed, including
when selecting a subset.

```sh
make retention-register-regression SIM=icarus \
  RETENTION_REGISTER_SEED=1234 RETENTION_REGISTER_RANDOM_CYCLES=3000 \
  RETENTION_REGISTER_REGRESSION_BUILD="$(pwd)/build/retention-custom"

.venv/bin/python src/val/common/retention_register/run_retention_register_regression.py \
  --sim icarus --build-dir build/retention-focused --case width8_async_enable_mixed
```

Repeat `--case` for several profiles. `--rtl /absolute/path/design.sv` selects
another implementation with the same interface and portable `retained_image`.
Focused campaigns still run all nine invalid-parameter checks and all 14 protocol
assertion probes. Reports identify subsets separately from the full matrix.
`VCS_BIN_DIR`/`ICARUS_BIN_DIR` select binaries; `COMPILE_ARGS`/`SIM_ARGS` extend
native flags.

Normal discovery runs the default one-bit, synchronous-reset, enabled instance:

```sh
make pyuvm SIM=icarus COCOTB_TOPLEVEL=retention_register
```

Direct overrides must supply matching expected parameters:

```sh
RETENTION_REGISTER_WIDTH=8 RETENTION_REGISTER_RESET_VALUE=0xa5 \
  RETENTION_REGISTER_ASYNC_RESET=1 RETENTION_REGISTER_HAS_ENABLE=0 \
  make pyuvm SIM=icarus COCOTB_TOPLEVEL=retention_register \
  COMPILE_ARGS="-Pretention_register.WIDTH=8 -Pretention_register.RESET_VALUE=165 \
                -Pretention_register.ASYNC_RESET=1 -Pretention_register.HAS_ENABLE=0" \
  SIM_BUILD="$(pwd)/build/retention-direct8"
```

Direct tests accept `RETENTION_REGISTER_SEED`, `RETENTION_REGISTER_RANDOM_CYCLES`,
and `RETENTION_REGISTER_COVERAGE_FILE` through the environment. The runner supplies
all expected parameters/settings automatically. Sized reset literals preserve all
bits through WIDTH=128; their apostrophes are quoted for Make's shell. Data that
does not fit the port is rejected instead of truncated.

## Parameter matrix

| WIDTH | Reset classes | Reset styles | Enable settings | Profiles |
|---:|---|---|---|---:|
| 1 | Zero, one | Sync, async | Present, absent | 8 |
| 8 | Zero, one, mixed | Sync, async | Present, absent | 12 |
| 16 | Zero, one, mixed | Sync, async | Present, absent | 12 |
| 32 | Zero, one, mixed | Sync, async | Present, absent | 12 |
| 64 | Zero, one, mixed | Sync, async | Present, absent | 12 |
| 128 | Zero, one, mixed | Sync, async | Present, absent | 12 |

Names follow `width<width>_<sync|async>_<enable|noenable>_<zero|one|mixed>`.
The one reset sets every bit. Mixed resets repeat/truncate `10100101` to the
width. One-bit words have no mixed class. The aggregate gate requires the complete
width × reset-value-class × reset-style × enable-configuration cross.

## Timing and portable storage visibility

`TEST_CLOCK_PERIOD_NS` defaults to 4. Use a whole number of picoseconds divisible
by four, at least 32 ps, with simulation precision of 1 ps or finer. Each cycle
has setup, rising edge, high-phase control/data activity, and falling edge phases.
Inputs settle before the rising edge and change again while the clock stays high
to prove that off-edge activity cannot capture, save, or restore state.

Every action is checked 1 ps after driving and again 1 ps before the next action.
The driver preserves the requested phase interval. `TEST_SETTLE_NS` must be zero:
this suite checks zero-delay RTL and does not qualify gate/SDF timing.

The default monitor reads portable `retained_image`, requires WIDTH bits, and
checks both storage values at every sample and output-change time. Missing
internal visibility fails explicitly. Direct runs against another zero-delay
implementation may set `RETENTION_REGISTER_CHECK_IMAGE=0`; visible-state and
protocol checks remain active, while `portable_image_assertions=NOT_RUN` is
reported. The full regression forces image checking on.

## Independent model and active checks

The reference applies the architectural table to pre-edge visible and saved
values: reset overrides restore, restore overrides save, save overrides capture,
and disabled functional state holds. Save uses pre-edge visible state, never
`i_d`; restore uses the saved image, never current data. Functional updates leave
the image unchanged. With enable absent, ordinary capture ignores `i_enable`.

| Requirement | Stimulus and checks |
|---|---|
| Normal capture/hold | Seeded binary/four-state data, disabled-hold stress, and enable-present/absent configurations. |
| Both resets | Reset of both images, off-edge assertion/release in both phases, and synchronous/asynchronous event behavior. |
| Save of required data classes | Zero, all-one, alternating, random, walking bits, all-X/all-Z, and mixed/partial unknown data where representable. |
| Pre-edge save | Save-edge data differs from visible state; save must preserve visible state and snapshot its old value. |
| Data changes after save | Multiple functional writes and high/low-phase input changes must leave the image unchanged. |
| Most recent save | Save A, write B, save B, overwrite visible state, then restore B. |
| Short/long saved intervals | Required saved-data classes cross intervals shorter than eight periods and long intervals with stopped clocks. |
| Stopped clock | Hold both clock levels for eight periods; data changes cannot alter visible/saved state without an event. |
| Repeated epochs | At least 16 legal save/restore epochs per profile, followed by functional writes. |
| Restored bits | Every visible bit is saved and restored as zero, one, X, and Z. |
| Priority | All 16 binary reset/restore/save/enable combinations, with data distinct from the saved value during restore. |
| Waveform legality | Continuously watch both images, reject activity outside legal clock/reset events, and verify predicted values at each event. |

All per-profile goals are mandatory. Directed bit patterns and randomized samples
cover wide data; this is not exhaustive enumeration of every wide word/history.
JSON reports show the actual saved/restored bits, interval crosses, priority
combinations, reset phases, commands, and protocol diagnostics.

The clock-stopped intervals and writes of X/Z data are logical stress. They do
not remove a supply, force simulator state, or prove main-off retention. No
simulation checkpointing is used as physical evidence.

## Protocol assertions and negative tests

The testbench checks sampled controls on every rising edge, plus reset validity
when the asynchronous reset process is triggered. Unknown reset, enable, save,
and restore inputs are illegal when sampled. Unknown enable is diagnosed even
when HAS_ENABLE=0; its value is functionally ignored in that configuration.
Off-edge save/restore/enable changes do not constitute sampled operations.

Active assertions reject:

- Simultaneous save and restore.
- Enable high during save/restore when HAS_ENABLE=1.
- Restore without a fresh save, including restore immediately after reset.
- Consecutive save or restore operations under this controller protocol.
- X or Z on each sampled control.

A verification-only fresh-save token is cleared by reset, unknown reset/PM
control, or restore, and set by save. It adds no RTL state or acknowledgement.
Two saves separated by a functional write explicitly test the portable
latest-image behavior. Repeated save/restore samples are negative controller
tests; they do not authorize repeated technology-cell pulses. A real shutdown
cycle and its supply-validity window require power-aware integration evidence.

Deliberate negative stimulus explicitly acknowledges expected assertion
violations and continues checking the defined portable priority/state behavior.
For example, restore wins over simultaneous known save, and reset still overrides
conflicting controls. Every expected diagnostic is counted; unacknowledged
violations fail the simulation.

Fourteen separate probes prove the checks are live: X/Z on each of four controls,
save/restore conflict, enable during each retention operation, restore without
save, and repeated save/restore. A probe passes only when the exact PyUVM test
runs, JUnit reports failure, and the log contains the expected protocol assertion.
Compiler errors, skipped tests, and unrelated failures cannot pass. The internal
`RETENTION_REGISTER_PROTOCOL_PROBE` variable selects only those negative tests.
HDL-bound SVA and formal proofs remain separate `NOT_RUN` checks.

## RTL fixes and four-state behavior

The original model treated unknown controls as ordinary hold/update decisions;
the suite reproduced a silent X-save hold before the fix. The portable model now:

- Gives known asserted reset highest priority, resetting both images even when
  other controls are unknown (the testbench still diagnoses sampled violations).
- Exposes unknown reset or save/restore control as X in both storage images.
- Keeps a known save/restore operation above functional enable. In ordinary
  enabled mode, an X/Z enable makes visible state X and leaves the image intact.
- Uses static reset/enable generate branches and no generated clock.

The unknown reset behavior obeys Verilog event rules: asynchronous 1-to-X/Z is a
negedge and exposes uncertainty immediately; 0-to-X/Z waits for a rising clock
event. Synchronous reset is sampled only on a rising clock edge. These digital
choices do not model supply corruption or analog retention limits.

Flags preserve caller values until strict 0/1 elaboration checks, avoiding silent
bit truncation. Nine negative parameter cases cover zero width, X/Z reset data,
non-Boolean reset/enable flags, and X/Z flags. Each requires a nonzero native
compiler exit with the intended unresolved guard-module diagnostic. Positive
reset literals are exactly WIDTH bits; finite tests do not prove rejection of
every implicit conversion of caller reset literals into the typed data word.

## Reports

Reports default to `build/<simulator>/retention_register/regression`:

| File | Contents |
|---|---|
| `<profile>/results.xml` | Exactly one successful, unskipped `test_retention_register.RetentionRegisterTest`. |
| `<profile>/coverage.json` | Parameters/seed, checked/held/clocked/random counts, image-check status, and mandatory goals/bins. |
| `<profile>/simulation.log` | Native compilation, expected protocol diagnostics, and PyUVM results. |
| `<profile>/parameters.json` | Compile dependency forcing parameter changes to rebuild. |
| `invalid_parameters/<case>/elaboration.log` | Rejection with the intended guard diagnostic. |
| `protocol_checks/<case>/results.xml` | Expected failing live-assertion test. |
| `protocol_checks/<case>/simulation.log` | Matching assertion diagnostic. |
| `summary.json` | Matrix gate, source hashes, parameter/protocol results, and external checks. |

Stale JUnit/coverage reports are removed before runs. Missing, duplicate, skipped,
wrong, failed, or insufficiently covered positive tests cannot pass. Parameter,
seed, and random-count mismatches fail. Missing binaries and recognized license
checkout failures produce `NOT_RUN` and nonzero exit. Dry runs print commands
without executing the wrapper or changing existing reports.

## Power-aware and physical release boundary

Portable functional evidence does not establish retention across actual main-
supply loss. Power-aware regression must use the implementation UPF, power-state
table, approved retention cells, and retention-supply models. It must check save
before shutdown, isolation, main-off corruption, valid retained storage, restore
before isolation release, retention-supply loss and cold recovery, and every legal
power-state cross. Those tests are recorded as `NOT_RUN` here.

VC LP signoff is mandatory for a retention release and remains `NOT_RUN`.
Technology synthesis/binding, equivalence, CDC/RDC, DFT, physical rail/voltage-area
checks, DRC/LVS, retention timing, and power-aware PrimePower also remain `NOT_RUN`.
Ordinary flip-flops inferred from this two-image model are not approved physical
retention cells. No supply-loss, mapped-retention, power, or energy claim is made
from passing this standalone suite.

## Local validation evidence

Native local results use Python 3.12, cocotb 2.1.0, PyUVM 5.0.0, and Icarus 12.0.

- All 68 profiles passed: 796,000 checked actions, including 136,000 random
  clocked cycles, plus 796,000 held-input checks. There were 198,524 rising-edge
  checks and 16,114 legal restore epochs. All functional goals, portable image
  assertions, and the aggregate parameter cross passed.
- All nine invalid-parameter cases failed native elaboration with the intended
  guards. All 14 untagged protocol probes failed their live assertions. The
  pre-fix RTL failed the unknown-save state check with the final checker.
- Twenty-six temporary, compilable RTL defects were detected: the original
  unknown hold behavior, save/restore data and state corruption, enable and
  priority overrides, inverted/reordered/Z-coerced data, incorrect reset style
  or reset contents, falling-edge capture, enable sensitivity in the absent
  branch, four removed parameter guards, and 1 ps visible/image/clock-event
  pulses. In particular, distinct restore input and saved values expose an
  enable override that equal data values would have hidden.
- Verilator `--lint-only --timing -Wall` passed all 68 profiles without waivers.
  Generic Yosys synthesis preserved `2*WIDTH` ordinary storage bits, rising-edge
  clock connections, asynchronous reset pins where selected, synchronous reset
  through reset pins or data/enable logic, and no latches or generated clocks.
  These generic ordinary flip-flops are not physical retention cells.
- The existing 31 synthesis/power orchestration checks passed with licensed
  commands stubbed. Direct Makefile discovery from another directory and a
  custom three-bit, asynchronous, mixed-reset case with an 8 ns period passed.
  Port-only mode passed and correctly reported image assertions as `NOT_RUN`.
  Relative binary paths, custom seed/cycle count, dry runs, and invalid random
  settings behaved correctly. Missing VCS and a stubbed license failure produced
  `NOT_RUN`.

Native reports are in ignored `build/icarus/retention_register/regression`;
supporting evidence is in `build/validation/retention_register`. Source hashes
identify the tested RTL and scripts. Native VCS, implementation UPF/cell-model
power-aware regression, retention-supply-loss recovery, required VC LP, and
technology/physical retention signoff remain `NOT_RUN` locally.
