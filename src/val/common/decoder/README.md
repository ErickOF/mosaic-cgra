# Decoder functional verification with PyUVM

The verification contract is the [MOSAIC decoder specification](../../../../../specs/common/mosaic-decoder/README.md).
`test_decoder.DecoderTest` verifies the unmodified `src/rtl/common/decoder.sv`
through its ports, without a clock or reset and without reading implementation
internals.

## Run the regression

From `mosaic-cgra`:

```sh
make setup
make decoder-regression                         # VCS on the licensed server
make decoder-regression SIM=icarus               # Local four-state simulation
make decoder-regression SIM=vcs VCS_BIN_DIR=/server/vcs/bin
make decoder-regression SIM=icarus DECODER_SEED=12345 DECODER_RANDOM_CYCLES=5000
```

The existing requirements pin cocotb 2.1.0 and PyUVM 5.0.0. VCS and Icarus
are supported; a two-state simulator cannot verify the required X/Z behavior.
Each configuration runs in its own simulator process and build directory.
Only `NUM_OUTPUTS` is overridden, so the RTL must derive `SELECT_WIDTH`.
The test checks both port widths against the expected parameters.

`DECODER_SEED` defaults to `20261010`, incremented by the profile's matrix
index. `DECODER_RANDOM_CYCLES` defaults to `2000` transactions per profile;
the minimum is `1000`. A local `random.Random` instance makes the stimulus
reproducible. `DECODER_REGRESSION_BUILD` relocates the reports; its default is
`build/<simulator>/decoder/regression`. `COMPILE_ARGS`, `SIM_ARGS`, `PYTHON_BIN`,
and simulator binary directory settings also apply.

`TEST_SETTLE_NS` defaults to zero. The driver advances at least `1 ps`, then
the passive monitor samples in the settled ReadOnly phase. This scheduling
step does not introduce a clock or architectural latency. A larger setting
can supply settling time for another simulation flow; passing this campaign
does not establish physical timing or power results.

Run the default four-output configuration through the normal Make flow:

```sh
make pyuvm SIM=icarus COCOTB_TOPLEVEL=decoder
```

Its JUnit and coverage reports are stored in `build/<simulator>/decoder`.
For a focused configuration or temporary RTL mutation:

```sh
.venv/bin/python src/val/common/decoder/run_decoder_regression.py \
  --sim icarus --case non_power_of_two_extended \
  --build-dir build/icarus/decoder/focused
.venv/bin/python src/val/common/decoder/run_decoder_regression.py \
  --sim icarus --rtl /tmp/faulty_decoder.sv \
  --build-dir build/icarus/decoder/mutation
```

Focused runs are recorded as `selected_profiles`, rather than the complete
recommended matrix. They still execute the four parameter rejection checks.

## Recommended configurations

The minimum selection port is one bit, including for `NUM_OUTPUTS=1`.

| Profile | NUM_OUTPUTS | SELECT_WIDTH | Invalid binary encodings | Legal transition pairs |
| --- | ---: | ---: | --- | ---: |
| `minimum` | 1 | 1 | 1 | 1 |
| `binary` | 2 | 1 | None | 4 |
| `non_power_of_two` | 3 | 2 | 3 | 9 |
| `directional_ports` | 4 | 2 | None | 16 |
| `non_power_of_two_extended` | 5 | 3 | 5, 6, 7 | 25 |
| `register_selection` | 8 | 3 | None | 64 |
| `context_selection` | 16 | 4 | None | 256 |
| `large_decode` | 32 | 5 | None | 1024 |

## Environment and requirement mapping

`DecoderSequence` submits `DecoderItem` transactions to a PyUVM sequencer.
`DecoderDriver` drives enable and selection and notifies a passive
`DecoderMonitor` when the combinational observation window is ready. The
monitor reads actual ports, including X/Z, and publishes them through a UVM
analysis port. Identical successive input transactions are sampled too,
so legal self-transitions and stable input behavior are checked.

`DecoderScoreboard` derives the expected output independently from the current
observed inputs: only a known asserted enable and a known in-range selection
may produce `1 << selection` and valid high. Every other input must produce
known zero on both outputs. Assertions compare the exact encoding and validity,
verify one-hot-or-zero, and confirm that the requested four-state stimulus
actually reached the DUT. No expected value is derived from DUT outputs.

Separate continuous listeners observe both output signals. They reject an
unknown or multi-hot output and reject any output transition while enable was
already low and remains low during selection activity. Enable deassertion may
remove the preceding active output; subsequent disabled selection changes must
have no output activity. The listeners immediately re-arm so observable short
transients cannot hide behind a later correct settled value.

| Specification requirement | Stimulus and check |
| --- | --- |
| Every legal selection and output bit | Exhaustive enabled sweep, exact bit-index model, and activation bins |
| Every invalid encoding | Exhaustive enabled sweep of the entire selection space; known zero and valid low |
| Disabled behavior for every selection | Exhaustive disabled sweeps and continuous output activity checking |
| Every pair of legal selections | Exhaustive ordered pair sweep, including self-pairs |
| Legal/invalid transitions | Every legal-to-invalid and invalid-to-legal pair when invalid encodings exist |
| Enable assertion/deassertion | Both transitions for every binary selection encoding |
| Simultaneous enable/selection changes | Directed assertion/deassertion with changed selection, plus randomized commands |
| Unknown enable | X and Z for every binary encoding, including invalid selections |
| Unknown selection | X/Z in every bit with zero/one backgrounds and enable low/high; all-X, all-Z, and mixed X/Z vectors |
| No retained decoded value | Active selections followed by disabled, invalid, or unknown inputs must clear outputs |
| Minimum and power/non-power-of-two sizes | Eight separately elaborated reference configurations |
| Random activity | Seeded binary and X/Z stimulus, with independent enable and selection choices |
| Invalid parameters | Four compile-only rejection tests requiring the intended elaboration guard diagnostic |

All functional goals must pass in every profile. Binary input coverage is
exhaustive for these small widths; the legal pair cross covers all 1,399
ordered pairs across the matrix. Unknown patterns are directed and randomized,
rather than exhaustive enumeration of every possible four-state vector.
For power-of-two configurations there are no invalid binary encodings; their
invalid encoding percentage is `null` with applicability set false.

Unlike the clock gate's illegal-control tests, unknown decoder inputs have
specified fail-closed behavior. These are passing functional checks, not
expected assertion failures. Python assertions are active during simulation;
HDL-bound SVA and formal proof remain `NOT_RUN`.

## Parameter rejection and artifacts

The runner requires elaboration failure for `NUM_OUTPUTS=0`, `NUM_OUTPUTS=3`
with `SELECT_WIDTH=1`, `NUM_OUTPUTS=4` with `SELECT_WIDTH=3`, and `NUM_OUTPUTS=1`
with `SELECT_WIDTH=0`. It checks the diagnostic for the corresponding RTL
guard. An unrelated syntax error, missing license, or accepted invalid
configuration cannot count as a passing rejection check. These four tests
cover the zero-output boundary and under/oversized selection width cases.

| Artifact | Contents |
| --- | --- |
| `summary.json` | Aggregate status, profiles, parameter rejection results, seeds, timestamps, RTL/verification SHA-256 hashes, and unexecuted external checks |
| `<profile>/coverage.json` | Actual parameters, transaction counts, output activity counts, functional bins, pair crosses, and coverage goals |
| `<profile>/results.xml` | cocotb JUnit result identifying the actual PyUVM test |
| `<profile>/simulation.log` | Compilation, simulation, assertions, and coverage output |
| `<profile>/parameters.json` | Parameter metadata and a rewritten compilation dependency preventing stale elaborations |
| `invalid_parameters/<case>/elaboration.log` | Compiler diagnostic for the rejected parameter case |

The runner removes previous coverage and JUnit results for each attempted
profile and requires exactly one successful `DecoderTest`, matching parameters,
seed, and random count. Missing results, skipped tests, failed assertions,
absent coverage bins, or failed parameter checks fail the command. Missing
simulator executables are `NOT_RUN` with a nonzero exit. Read aggregate status
before using profile artifacts from an earlier run.
`make -n decoder-regression` preserves existing reports.

## Local verification evidence

All eight profiles passed with Python 3.12, cocotb 2.1.0, PyUVM 5.0.0, and
Icarus Verilog 12.0. The default seeds produced 20,119 checked transactions,
including 16,000 randomized transactions. Every legal selection, applicable
invalid encoding, disabled encoding, output bit, and all 1,399 legal pair
bins were covered. Every functional coverage goal and all four parameter
rejection checks passed.

Eight deliberately faulty temporary RTL copies were detected: reversed
encoding, ignored enable, wrapped invalid selections, retained outputs,
unknown selections converted to zero, multi-hot output, missing parameter
guards, and an extra disabled-output glitch. The `1 ps` glitch ended before
the mutation test's `10 ps` settled observation; the continuous activity
checker detected it. The original RTL was not modified.

Verilator `--lint-only --timing -Wall` passed for all eight configurations.
The normal Make invocation passed from outside the repository, dry runs
preserved all regression artifacts, and invalid settings were rejected
without overwriting earlier evidence. All 31 existing local synthesis/power
checks passed using stubbed licensed commands. VCS was unavailable locally
and was recorded as `NOT_RUN`.

The verified RTL SHA-256 is
`ed39d268ad87f931ada335a517e850a0c300f6275d3ffce969150e5422c836cf`.
Build artifacts are ignored by Git. Rerun the regression after changing
RTL or verification sources; the aggregate report records their hashes.

## Verification scope

This campaign checks portable RTL functionality and the four listed invalid
parameter cases. It does not prove every four-state combination or absence of
state for all possible parameter values. Formal proof, bound HDL SVA, commercial
lint/CDC/DFT/low-power checks, synthesis, physical timing, and annotated power
analysis remain `NOT_RUN`. Passing the functional regression alone does not
satisfy all release criteria or demonstrate energy savings.
