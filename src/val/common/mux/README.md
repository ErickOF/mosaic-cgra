# Mux PyUVM validation

This suite validates `src/rtl/common/mux.sv` against the
[MOSAIC mux specification](../../../../../specs/common/mosaic-mux/README.md).
It uses real PyUVM sequences, a sequencer, driver, passive monitor, independent
reference model, scoreboard, and mandatory functional coverage. The reference
model splits the actual packed input port into words and matches the selector
against an exact dictionary of legal binary keys. It reads no internal RTL
signals and does not copy the RTL's relational selection condition.

## Running the tests

From `mosaic-cgra`, using Python 3.10 or newer:

```sh
make setup
make mux-regression                  # VCS on the licensed server
make mux-regression SIM=icarus       # Local four-state alternative
```

Defaults are seed `20261011` and 2000 random transactions per profile. At least
1000 random transactions are required. Each profile adds its full matrix index
to the seed, including when selecting a subset.

```sh
make mux-regression SIM=icarus MUX_SEED=1234 MUX_RANDOM_CYCLES=3000 \
  MUX_REGRESSION_BUILD="$(pwd)/build/mux-custom"

.venv/bin/python src/val/common/mux/run_mux_regression.py \
  --sim icarus --build-dir build/mux-focused --case inputs3_width16_mixed
```

Repeat `--case` to select several profiles. `--rtl /absolute/path/mux.sv`
selects an alternative implementation without changing the original source.
Focused campaigns still run all seven invalid-parameter elaboration checks.
Reports distinguish a selected subset from the full matrix. `VCS_BIN_DIR` and
`ICARUS_BIN_DIR` select simulator binaries; `COMPILE_ARGS` and `SIM_ARGS` extend
the native compiler/runtime options.

Normal Makefile discovery also runs the default two-input, 32-bit instance:

```sh
make pyuvm SIM=icarus COCOTB_TOPLEVEL=mux
```

For direct parameterized runs, set matching expected parameters through the
environment and use a separate build directory:

```sh
MUX_NUM_INPUTS=3 MUX_DATA_WIDTH=16 MUX_DEFAULT_VALUE=0xa55a \
  make pyuvm SIM=icarus COCOTB_TOPLEVEL=mux \
  COMPILE_ARGS="-Pmux.NUM_INPUTS=3 -Pmux.DATA_WIDTH=16 -Pmux.DEFAULT_VALUE=42330" \
  SIM_BUILD="$(pwd)/build/mux-direct3"
```

Direct tests accept `MUX_SEED`, `MUX_RANDOM_CYCLES`, and `MUX_COVERAGE_FILE`
through the environment; the runner sets these automatically. `SEL_WIDTH`
is left derived for every positive profile and checked against the actual
selection port. Sized SystemVerilog literals preserve defaults through 128 bits;
the runner quotes their apostrophes for the Make shell command.

`TEST_SETTLE_NS` defaults to zero, with at least 1 ps before settled sampling.
Every transaction is checked again after holding both inputs unchanged.
Short holds last 1 ps; directed long holds last 1 ns. No clock or reset is used.
The existing gate/SDF targets supply settling time through `GATE_SETTLE_NS`;
choose enough time for the actual netlist's propagation. The functional suite
does not characterize physical delay or power.

## Parameter matrix

| NUM_INPUTS | DATA_WIDTH | Default classes | Profiles |
|---:|---:|---|---:|
| 1 | 1 | Zero, one | 2 |
| 2 | 8 | Zero, one, mixed | 3 |
| 3 | 16 | Zero, one, mixed | 3 |
| 4 | 32 | Zero, one, mixed | 3 |
| 5 | 64 | Zero, one, mixed | 3 |
| 8 | 128 | Zero, one, mixed | 3 |

Profile names follow `inputs<count>_width<width>_<zero|one|mixed>`.
The one default sets every bit. Mixed defaults repeat/truncate `10100101` to
the data width; a one-bit word has no mixed class. An aggregate gate checks the
complete input-count × width × default-class matrix. These are the six recommended
configuration pairs, not every possible count/width combination.

## Requirement mapping and active checks

| Specification requirement | Stimulus and checks |
|---|---|
| Every legal selection | Exact selected-word equality and `o_select_valid=1` for each input. |
| Every unused binary encoding | Every representable index outside the input count produces the configured default and valid zero. |
| Unknown selection | Every selector word containing X/Z, including full/partial/mixed unknowns, fails closed with the known default and valid zero. |
| Single-input instance | Zero selects its only source; one, X, and Z are invalid. Selection width is one. |
| Bit and word ordering | Input zero is the least-significant packed word; unique source words, walking bits, and exact four-state word comparisons detect reordered words/bits. |
| Selected-input activity | Each source changes while it remains selected; every source bit passes zero, one, X, and Z. |
| Unselected-input activity | Every ordered selected/unselected source pair changes the unselected word through uniform zero, one, X, and Z while the selected word stays fixed. Both outputs must remain unchanged. |
| Invalid-selection data activity | Hold every invalid/unknown selector fixed while changing/corrupting all source words; both outputs remain at their defaults. |
| Legal transition pairs | Every ordered legal selection pair, including repeated selections. |
| Invalid-entry and recovery | Every legal-to-invalid binary pair and every invalid-to-legal pair; unknown-selection recovery also exercised. |
| Required data classes | Select every source containing zero, all ones, walking one/zero, alternating, all-X/all-Z, partial unknowns, and mixed X/Z where representable. |
| Distinct source words | Select every input from a bus of distinct words in all recommended configurations. |
| Simultaneous changes | Change the packed data and selector together, including the single-input instance's invalid encoding. |
| No retained state | Current-port reference checks, recovery from invalid indices, revisited patterns, and a second check after each held-input interval. |
| Randomized data/selection | Seeded binary and four-state data, partial X/Z words, legal/unused indices, and unknown selectors. |

The required selected-data, legal-valid, and invalid-default assertions are
active Python scoreboard checks. Output checking remains active for unknown
selectors and data. Selected X/Z data must propagate exactly while valid remains
one; unselected X/Z data must not corrupt a known selected word. Unknown selection
is an expected fail-closed test, rather than an assertion failure that is ignored.
HDL-bound SVA and formal proofs are separate `NOT_RUN` checks.

Data widths through eight also run every binary word on each selected input;
widths through two run every four-state word. Every profile covers the entire
four-state selection space. Wide data words and combinations of all source
words are covered by directed and random samples, not exhaustive enumeration.

Legal-selection and unused-binary-encoding targets are 100 percent for each
profile. Power-of-two counts above one have no unused binary indices; their
invalid-encoding percentage is `null`, and the report shows an empty bin set.
All such profiles still run X/Z selection tests. For a custom configuration with
more inputs than distinct representable word values, a simultaneous bus of
unique words is impossible; the report records this and omits that single goal.
Selection, ordering, source activity, and bit propagation checks remain active.

## Activity monitor semantics

Both outputs are watched during unselected-input changes, fixed invalid-selection
data changes, and held-input intervals. Activity is checked after combinational
delta cycles at each observed output-change time. The RTL's blocking default
assignments may expose intermediate callback values within one `always_comb`
evaluation; these do not constitute a settled functional output change.

A finite pulse that persists into a read-only phase fails even if it disappears
before the transaction's settled/held sample. Selection changes and selected-data
changes may alter the output before the configured settling point. The test
does not require physically glitch-free selection transitions or authorize using
this data mux as a clock mux.

## Reports and parameter guards

Reports default to `build/<simulator>/mux/regression`:

| File | Contents |
|---|---|
| `<profile>/results.xml` | Exactly one successful, unskipped `test_mux.MuxTest`. |
| `<profile>/coverage.json` | Parameters/default class, seed, transaction/held/random counts, selection/data/activity bins, and coverage goals. |
| `<profile>/simulation.log` | Native compilation and PyUVM simulation output. |
| `<profile>/parameters.json` | Compile dependency forcing changed parameters to rebuild the simulator. |
| `invalid_parameters/<case>/elaboration.log` | Native compiler rejection and intended guard diagnostic. |
| `summary.json` | Matrix gate, source hashes, parameter results, and separate external checks. |

Seven negative cases reject zero input count, zero data width, undersized and
oversized selectors, a zero-width selector on the minimum instance, and X/Z
bits in the default. Each requires a failing compiler exit and the intended
unresolved guard-module diagnostic. A random syntax error cannot pass a guard
check. The actual rejection stage is elaboration. These finite cases do not
prove rejection of every possible caller literal or implicit parameter conversion.

Old JUnit/coverage reports are removed before each profile. Missing, duplicated,
skipped, wrongly selected, or failing tests cannot pass. Missing bins and parameter,
seed, or random-count mismatches also fail. Missing simulator binaries and
recognizable license checkout failures produce `NOT_RUN` and a nonzero exit.
`make -n mux-regression` prints commands without executing the wrapper or
changing existing reports.

## Integration and release boundary

This suite publishes standalone functional evidence. CDC compatibility,
configuration validation, operand isolation, power-domain/voltage crossings,
DFT controllability/observability, and downstream timing depend on the actual
integration. Commercial lint, CDC, DFT, VC LP, synthesis/equivalence, PrimeTime,
and annotated PrimePower results remain `NOT_RUN` in this campaign.

Local Verilator lint and portable PyUVM results do not substitute for those
release checks. Output inactivity with unselected data does not by itself prove
energy savings in an implemented datapath.

## Local validation evidence

Native local results use Python 3.12, cocotb 2.1.0, PyUVM 5.0.0, and Icarus 12.0.

- All 17 profiles passed: 126,551 checked transactions, including 34,000 random
  transactions, plus 126,551 held-input checks. Every functional goal and the
  aggregate input-count/width/default cross passed. Legal selections and every
  representable unused binary encoding reached 100 percent coverage.
- Seven invalid-parameter cases failed elaboration with their intended guards.
  X/Z defaults are instantiated in SV wrappers because Icarus's command-line
  defparam parser does not accept unknown digits.
- Nineteen isolated, compilable RTL mutants were detected: reordered words/bits,
  ignored selection, inversion, hardcoded-zero default, out-of-range remapping,
  unknown fail-open behavior, stuck valid outputs, Z-to-X data coercion,
  unselected-input coupling, retained invalid data, a truncated power-of-two
  limit, four removed parameter guards, and 1 ps unselected-input glitches on
  `o_data` and `o_select_valid`. The monitors detected both finite pulses before
  a 10 ps transaction sampling point.
- Verilator `--lint-only --timing -Wall` passed all 17 configurations without
  waivers. The existing 31 synthesis/power orchestration checks passed with
  licensed commands stubbed.
- Direct Makefile discovery from another directory passed. A relative simulator
  binary directory and custom seed/random count passed a focused campaign.
  The additional three-input, one-bit case passed with the impossible distinct
  simultaneous-word goal omitted. Dry runs and invalid random settings preserved
  reports. Missing VCS and a stubbed license failure both produced `NOT_RUN`.

Native reports are in ignored `build/icarus/mux/regression`; supporting evidence
is in `build/validation/mux`. Source hashes identify the tested RTL and scripts.
VCS and physical/integration release checks remain `NOT_RUN` locally.
