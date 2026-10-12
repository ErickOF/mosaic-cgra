# Priority encoder PyUVM validation

This suite validates [priority_encoder.sv](../../../rtl/common/priority_encoder.sv)
against the [MOSAIC priority encoder specification](../../../../../specs/common/mosaic-priority-encoder/README.md).
It uses real PyUVM sequences, a sequencer, driver, passive monitor, independent
four-state reference model, scoreboard, and mandatory coverage. Only interface
ports are observed. No clock, reset, state, handshake, or fairness policy is added.

## Running the tests

From `mosaic-cgra`, with Python 3.10 or newer:

```sh
make setup
make priority-encoder-regression                 # VCS on the licensed server
make priority-encoder-regression SIM=icarus      # Local four-state alternative
```

Defaults are seed `20261011` and 2000 seeded campaign transactions per profile.
At least 1000 are required. Each profile adds its full matrix index to the seed,
including when running a subset.

```sh
make priority-encoder-regression SIM=icarus \
  PRIORITY_ENCODER_SEED=1234 PRIORITY_ENCODER_RANDOM_CYCLES=3000 \
  PRIORITY_ENCODER_REGRESSION_BUILD="$(pwd)/build/priority-encoder-custom"

.venv/bin/python src/val/common/priority_encoder/run_priority_encoder_regression.py \
  --sim icarus --build-dir build/priority-encoder-focused --case width5_msb
```

Repeat `--case` to select several profiles; `--rtl /absolute/path/design.sv`
selects another implementation of the same module interface. Focused campaigns
still run all four parameter checks and both assertion probes. Reports identify
a subset separately from the full matrix. `VCS_BIN_DIR` and `ICARUS_BIN_DIR`
select simulator binaries; `COMPILE_ARGS` and `SIM_ARGS` extend native flags.

Normal discovery runs the default four-request, LSB-first instance:

```sh
make pyuvm SIM=icarus COCOTB_TOPLEVEL=priority_encoder
```

For direct overrides, provide matching expected parameters:

```sh
PRIORITY_ENCODER_WIDTH=5 PRIORITY_ENCODER_LSB_HIGH_PRIORITY=0 \
  make pyuvm SIM=icarus COCOTB_TOPLEVEL=priority_encoder \
  COMPILE_ARGS="-Ppriority_encoder.WIDTH=5 -Ppriority_encoder.LSB_HIGH_PRIORITY=0" \
  SIM_BUILD="$(pwd)/build/priority-encoder-direct5"
```

Direct tests accept `PRIORITY_ENCODER_SEED`, `PRIORITY_ENCODER_RANDOM_CYCLES`, and
`PRIORITY_ENCODER_COVERAGE_FILE` through the environment. The runner supplies
matching expected parameters and settings. `INDEX_WIDTH` remains derived in all
positive profiles and is checked against the actual output port width. Requests
that do not fit the port are rejected instead of truncated.

`TEST_SETTLE_NS` defaults to zero with at least 1 ps before settled sampling.
All four outputs are checked again after every unchanged-input hold. Short holds
last 1 ps and directed long holds last 1 ns. Existing gate/SDF targets use
`GATE_SETTLE_NS`; select enough time for the actual netlist to settle.

## Parameter matrix

| WIDTH | INDEX_WIDTH | Priority directions |
|---:|---:|---|
| 1 | 1 | LSB, MSB |
| 2 | 1 | LSB, MSB |
| 3 | 2 | LSB, MSB |
| 4 | 2 | LSB, MSB |
| 5 | 3 | LSB, MSB |
| 8 | 3 | LSB, MSB |
| 16 | 4 | LSB, MSB |
| 32 | 5 | LSB, MSB |

Names follow `width<width>_<lsb|msb>`. LSB means `LSB_HIGH_PRIORITY=1`; MSB means
zero. All 16 profiles must pass the width × direction matrix and the selected
index × direction cross at every width. This finite matrix includes the minimum,
power-of-two, and specified non-power-of-two widths.

## Independent model and four-state behavior

The model collects sets of known asserted and unknown request positions. It
selects `min` or `max` for known requests and calculates the set of possible
winners if each X/Z bit could be zero or one. An optional no-request outcome
is included when no known request exists. It does not copy the RTL's scan loop
and never enumerates all binary completions of a wide unknown vector.

For completely known requests, valid equals nonzero population, multiple equals
population greater than one, and index/one-hot identify the highest-priority bit.
All no-request outputs are zero. Independent interface assertions also verify
one-hot consistency, grant membership, binary-index agreement, and priority.

For X/Z requests:

- If a known request outranks every unknown bit, its index and one-hot stay
  known. Lower-priority unknown bits cannot change the winner.
- If an unknown bit could outrank the best known request, or there is no known
  request, index and one-hot become entirely X. A lower known request must not
  be silently granted.
- Valid is one when any known request is asserted, X when only unknown requests
  may be asserted, and zero for an all-zero vector.
- Multiple is one when at least two known requests exist, zero when even the
  maximum possible population is at most one, and X otherwise.

These conservative unknown-output choices refine the specification's recommended
four-state behavior. For example, LSB-first `100x` gives valid one, index `xx`,
one-hot `xxxx`, and multiple X. `00x1` preserves index zero and one-hot `0001`
while multiple is X. A one-bit X/Z request gives valid/index/one-hot X and
multiple zero.

The previous RTL skipped unknown bits and could grant a lower-priority request.
The suite reproduced that defect before the fix. The RTL now traverses possible
requests in priority order and propagates ambiguity; its binary selection
contract is unchanged. Parameter guards now use elaboration-time unresolved
guard modules, consistent with the other common primitives.

## Requirement mapping and coverage

| Specification requirement | Active stimulus/checks |
|---|---|
| No request | All four outputs zero, revisited after winners and unknown requests. |
| Every single request | Every position selected, index/one-hot agreement, valid one, multiple zero. |
| Every simultaneous pair | Every unordered pair, correct priority winner and multiple one. |
| All asserted | Both directions select their highest-priority endpoint. |
| Contiguous/noncontiguous patterns | Every contiguous interval, sparse pairs, alternating vectors, and randomized patterns. |
| Population counts | Every count from zero through WIDTH and every reachable selected-index/population combination. |
| Priority direction | Both static directions at every matrix width, with explicit no-higher-request assertions. |
| Unknown requests | Each bit X/Z alone, above/below every known winner, all-X/all-Z/mixed vectors, and recovery. |
| Lower-priority activity | Each lower bit changes through zero/one/X/Z while a known winner remains fixed. Multiple is checked independently. |
| Request transitions | Every bit's 16 ordered four-state transitions in zero/one background vectors; every ordered winner pair. |
| No retained state | Current-port reference, repeated patterns, no-request recovery, and a second check after each held interval. |
| Randomized sequences | Seeded binary and four-state vectors, with biased no/single/all-request slots to retain corner coverage. |

Widths through eight exhaust every binary vector. Widths through five exhaust
every four-state vector. Larger widths use directed bit/pair/population tests
and randomized samples rather than exhaustive vector enumeration.

All functional goals are mandatory. Selected-index/population bins are limited
to reachable combinations: an LSB-first winner at index `i` supports populations
1 through `WIDTH-i`; an MSB-first winner supports 1 through `i+1`. The lowest-
priority index cannot win under contention. Its exclusion is recorded as
`contention_ineligible_indices`, rather than credited as covered. For WIDTH=1,
pair/multiple bins are empty and both directions still run all other checks.

The lowest/highest asserted-index cross covers every ordered bound pair with
lowest ≤ highest. Pattern-class × multiple coverage includes every required
reachable class. Held intervals cover no-request, single, and multiple states
where representable. JSON reports include actual bins and counts.

## Assertions and output activity

Ambiguous requests raise the active Python testbench assertion. Directed
negative stimulus explicitly acknowledges that expected violation, logs the
first diagnostic, counts every violation, and continues checking the outputs.
An untagged ambiguous request fails the test. Known winners with only lower-
priority unknown requests do not violate the selection-ambiguity assertion.

Separate X/Z probes prove the assertion is live. Each must run the exact PyUVM
test, produce a failing JUnit record, and log the matching ambiguous-request
diagnostic. A compilation failure, skipped test, or unrelated failure cannot
pass. The internal `PRIORITY_ENCODER_AMBIGUITY_PROBE` variable enables only these
negative tests. HDL-bound SVA and formal proofs remain separate `NOT_RUN` checks.

All four outputs are monitored throughout stable-request intervals. Changes are
checked after combinational delta cycles at each observed output-change time.
A finite pulse persisting into the read-only phase fails even between transaction
samples. Request transitions may change outputs before settling; this does not
promise physical glitch-free asynchronous request switching or coherent CDC.

## Reports and parameter guards

Reports default to `build/<simulator>/priority_encoder/regression`:

| File | Contents |
|---|---|
| `<profile>/results.xml` | Exactly one successful, unskipped `test_priority_encoder.PriorityEncoderTest`. |
| `<profile>/coverage.json` | Parameters/seed, checked/held/random counts, coverage bins, and expected ambiguity violations. |
| `<profile>/simulation.log` | Native compilation, expected ambiguity diagnostic, and PyUVM results. |
| `<profile>/parameters.json` | Compile dependency forcing parameter changes to rebuild. |
| `invalid_parameters/<case>/elaboration.log` | Native rejection with the intended guard diagnostic. |
| `ambiguous_request_checks/<x|z>/results.xml` | Expected failing assertion probe. |
| `ambiguous_request_checks/<x|z>/simulation.log` | Matching assertion diagnostic. |
| `summary.json` | Matrix/cross gates, source hashes, negative results, and separate external checks. |

Four parameter cases reject zero width, undersized/oversized index width, and
zero index width on the minimum instance. Each requires nonzero native compiler
exit and the intended guard module diagnostic; an unrelated syntax error cannot
pass. All actual rejection stages are elaboration. The static priority parameter
is a typed SystemVerilog bit; this campaign does not claim to reject every caller
literal that SystemVerilog implicitly converts to that type.

Stale JUnit/coverage files are removed before runs. Missing, duplicate, skipped,
wrong, or failed positive tests cannot pass. Missing goals, wrong parameters,
seed mismatches, and incorrect campaign counts fail. Missing binaries and
recognized license checkout failures produce `NOT_RUN` and a nonzero exit.
`make -n priority-encoder-regression` leaves existing reports unchanged.

## Integration and release boundary

This suite publishes standalone functional evidence. Request coherence,
acknowledgement/retention, pulse capture, starvation policy, and arbitration
handshakes depend on the consuming controller. CDC/RDC, DFT, VC LP, commercial
lint, formal, synthesis/equivalence, PrimeTime, and annotated PrimePower checks
remain `NOT_RUN` here. Output transition counts are not power or energy estimates.
Local PyUVM and Verilator results do not substitute for these release reports.

## Local validation evidence

Native local results use Python 3.12, cocotb 2.1.0, PyUVM 5.0.0, and Icarus 12.0.

- All 16 profiles passed: 76,340 checked transactions, including 32,000 seeded
  campaign transactions, plus 76,340 held-input checks. Every functional goal
  and both aggregate width/direction and selected-index/direction crosses passed.
  Every selected-index bin reached 100 percent coverage.
- Exhaustive cases covered 636 binary vectors across widths through eight and
  2728 four-state vectors across widths through five, counting both directions.
- Four invalid-parameter cases failed native elaboration with their intended
  guard diagnostics. Both untagged X/Z ambiguity probes failed the live PyUVM
  assertion as required. The pre-fix RTL failed the `100x` false-grant test.
- Twenty-three temporary, compilable RTL defects were detected: the original
  unknown-bit skipping behavior, reversed/stuck priority, index/one-hot faults,
  incorrect valid/multiple flags, retained no-request outputs, unknown fallthrough,
  incorrect poisoning of known winners or contention, two missing parameter
  guards, and 1 ps stable-request pulses on each of the four outputs.
- Verilator `--lint-only --timing -Wall` passed all 16 profiles without waivers.
  The existing 31 synthesis/power orchestration checks passed with licensed
  tool commands stubbed.
- Direct Makefile discovery from another directory passed. A custom seven-bit,
  MSB-first instance passed, as did a relative simulator binary directory and
  custom seed/campaign count. Dry runs and invalid random settings preserved
  reports. Missing VCS and a stubbed license failure produced `NOT_RUN`.

Native reports are in ignored `build/icarus/priority_encoder/regression`;
supporting evidence is in `build/validation/priority_encoder`. Source hashes
identify the tested RTL and scripts. Native VCS and physical/integration release
checks remain `NOT_RUN` locally.
