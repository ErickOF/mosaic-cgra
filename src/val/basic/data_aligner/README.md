# Data aligner RTL and PyUVM validation

[data_aligner.sv](../../../rtl/basic/data_aligner.sv) implements the
[byte-window specification](../../../../../specs/basic/mosaic-data-aligner/README.md).
Each accepted input describes two adjacent words. Every strobed byte moves by
one common byte offset into the low word, high word, or explicit edge spill.
One input window produces one output window, including empty metadata windows.

## Interface and RTL reuse

Defaults are `DATA_WIDTH=128`, `USER_WIDTH=1`, both shift directions enabled,
`REGISTER_OUTPUTS=0`, and `ASYNC_RESET=0`. Word widths must be positive multiples
of eight. User width must be positive, Boolean flags must be exactly zero or one,
and at least one direction must be enabled. Illegal parameters fail elaboration;
word bytes, window bytes, and offset width are local derived parameters.

The common `operand_isolation` clamps each unstrobed input byte before shifting
and clamps the complete output result while output valid is low. The registered
profile reuses common `dff` banks for the complete result and its valid bit.
Both banks reset to zero using the selected reset style. Payload storage updates
only on input acceptance; flush clears validity while preserving hidden payload.
Static generate branches remove disabled shift directions and registered logic.

The interface follows the conventions stated in the specification:

- Byte zero is bits `[7:0]` at the lowest address. The high word follows the low
  word in ascending addresses. No element endianness conversion is performed.
- `i_shift_high=0` translates source index `p` to `p-offset`. Negative positions
  map to preceding-word spill lane `WORD_BYTES+p-offset`.
- `i_shift_high=1` translates source index `p` to `p+offset`. Positions above the
  window map to spill lane `p+offset-2*WORD_BYTES`.
- Offset zero preserves all strobed bytes and both strobes; unstrobed data bytes
  remain zero. Spill direction still reflects the accepted direction.
- `o_unaligned` requires a nonempty input and nonzero offset. `o_split` requires
  nonempty low and high outputs; spill does not contribute to split.

There is no external contracts package or dependency lockfile. Reports hash the
current RTL, common dependencies, verification components, shared helpers, and
Makefile to identify each tested snapshot. Compatibility with an external
canonical contract remains a separate integration check.

## Ready-valid, configuration, and cancellation

The combinational profile has zero registered latency. Legal valid and ready
pass through in their respective directions. The registered profile is a single
elastic entry: an empty entry accepts regardless of downstream readiness, and
an occupied entry can consume and accept its replacement on the same edge.

`o_config_error` describes a valid input request outside reset and flush. It is
high for an unused offset encoding or unsupported direction. Such a request
cannot be accepted. It must stay stable while stalled until the producer's
request is canceled by reset or flush. Inactive controls are ignored. A legal
buffered output keeps its original data, metadata, and validity when current
input controls become illegal; it can still drain normally.

Reset and flush immediately clamp output valid, input ready, and result fields.
The registered valid bank clears on the selected reset event or on the rising
flush edge. Synchronous reset and flush pulses without a clock edge do not erase
stored state. Asynchronous reset clears both banks without an edge. `o_busy`
reflects stored validity, including before a synchronous cancellation edge.
Reset release synchronization is the integrator's responsibility.

Every output byte with strobe zero is zero. All result fields are zero while
output valid is zero. Unknown unstrobed data cannot contaminate qualified bytes;
unknown active controls, strobes, metadata, or qualified data fail the protocol
checker. Idle payload and alignment controls may be X/Z.

## Running

From `mosaic-cgra`:

```sh
make setup
make data-aligner-regression                    # VCS on the licensed server
make data-aligner-regression SIM=icarus         # Native four-state simulation
make pyuvm SIM=icarus COCOTB_TOPLEVEL=data_aligner
```

The Makefile discovers the suite and ordered DFF/isolation/aligner sources for
simulation and synthesis. Explicit `VERILOG_SOURCES` overrides take precedence.

```sh
make data-aligner-regression SIM=icarus DATA_ALIGNER_SEED=1234 \
  DATA_ALIGNER_RANDOM_CYCLES=3000 \
  DATA_ALIGNER_REGRESSION_BUILD="$(pwd)/build/data-aligner-custom"

.venv/bin/python src/val/basic/data_aligner/run_data_aligner_regression.py \
  --sim icarus --build-dir build/data-aligner-focused \
  --case three_byte_both_async --case nominal_high_sync
```

Focused cases retain all parameter guards and assertion probes. The runner works
from another directory and keeps each case's full-matrix seed index. `--rtl`
accepts a compatible alternate implementation for checker-sensitivity studies.
Missing tools and recognized license failures report `NOT_RUN` and exit nonzero.

## Verification structure

The suite separates configuration, transaction, sequence, driver, monitor,
scoreboard, coverage, agent, environment, and test entry point. It reuses the
shared active-agent/environment wiring, four-state utilities, regression CLI,
simulator execution, exact JUnit checking, and coverage-report infrastructure.

The independent model iterates source-byte arrays and places each strobed byte
at a signed integer destination index. It does not reproduce the RTL packed
shifts. It checks unique destinations and strobe-population conservation, and
the scoreboard compares all 15 output ports, including all payload fields,
spill, status, metadata, configuration error, ready, valid, and busy.

A separate transaction ledger records accepted windows and consumes the oldest
obligation first. It checks one-entry occupancy, minimum latency, replacement
ordering, cancellation, and accepted/consumed/canceled counts. The driver holds
producer frames stable during backpressure; the checker independently asserts
this requirement. Every run drains outstanding obligations under ready-high
fairness. No unbounded-progress or physical timing claim is made.

Each drive has samples before the clock transition, after it, and after a quiet
hold. Continuous monitors reject finite changes during quiet intervals, including
registered payload changes between edges and changes on falling edges. Optional
internal checks verify pre-shifter isolation, reset of every stored payload bit,
validity, and capture/hold activity. The reference obtains neither mapping nor
validity from the DUT.

## Profiles and mandatory coverage

The 57-profile matrix covers:

- Word widths 8, 24, 32, 64, 128, and 512 bits, with user widths 1, 3, 7, 17, and 32.
- Low-only, high-only, and both-direction configurations.
- Combinational, synchronous registered, and asynchronous registered timing.
- Three nominal combinational profiles with the asynchronous flag set, completing
  the legal feature/reset cross without introducing state.

These are repository validation profiles. The specification does not define a
maximum qualified product width; 512 bits is the local stress profile.

Directed traffic covers every legal offset, every source lane as a one-byte
transfer, full/empty/partial/sparse masks, both spill boundaries, empty metadata
windows, unknown inactive data and controls, full-rate traffic, 64-cycle stalls,
consume-and-replace, illegal requests while a buffered result drains, and
reset/flush during idle and occupied states. Random traffic adds at least 1000
cycles per profile (2000 by default), with stable held inputs, bubbles, changing
offsets, backpressure, reset, flush, and unknown unstrobed bytes.

Coverage gates require direction/offset, direction/spill, direction/output class,
offset/source lane, source word/destination class, strobe class/offset,
destination and spill lanes, one-byte transfers, unaligned/nonempty, last/stall,
occupancy transitions, reset/flush occupancy, all unused offset encodings, and
unsupported directions. They also require conserved transaction counts, at least
eight consecutive peak-throughput cycles, at least 32 stalled cycles, and equal
pre-edge/post-edge/held check counts.

Unreachable bins are profile-specific: a one-byte word has no nonzero legal
offset or spill; low-direction spill lane zero and high-direction final spill
lane are unreachable for offsets below one word; disabled directions and
combinational occupancy are excluded. Two-byte windows cannot express every
partial/sparse mask class. The coverage JSON records these exclusions and missing
bins; missing reachable coverage fails the run.

All 33 strict parameter guards reject invalid widths, unknown dimensions,
non-Boolean flags, and profiles with no direction. Seventy-four live negative
probes verify that unknown controls, strobes, qualified data, and producer
instability fail the exact expected PyUVM protocol assertion. Unrelated compiler
errors, skipped tests, and unrelated assertion failures cannot satisfy a probe.

## Reports and direct settings

Each profile writes `simulation.log`, fresh `results.xml`, `parameters.json`, and
`coverage.json`. The campaign writes `summary.json` with settings, source hashes,
simulator identity, checked cases, assertion probes, and external scope. Defaults are
under `build/<simulator>/data_aligner/regression`. Build artifacts are ignored.

Direct settings use the `DATA_ALIGNER_` prefix: primary parameter names, `SEED`,
`RANDOM_CYCLES`, `COVERAGE_FILE`, `CHECK_INTERNALS`, and `ASSERTION_PROBE`. Match
compiler parameter overrides with expected environment values. Setting
`CHECK_INTERNALS=0` enables port-only validation and reports private structure
checks as `NOT_RUN`. `TEST_SETTLE_NS` must be zero for these zero-delay checks;
post-route SDF timing is outside this suite's timing model.

Native VCS, HDL SVA, formal proof, commercial lint, CDC/RDC, DFT, UPF, technology
synthesis, PrimeTime, PrimePower, canonical external contracts, and integrated
reset release require their respective tools and integration environment.
Functional PyUVM results do not imply physical or product-release signoff.

## Local verification

Icarus Verilog 12.0, cocotb 2.1.0, and PyUVM 5.0.0 passed all 57 profiles,
33 elaboration guards, and 74 exact protocol probes. Each profile met its 23 or
25 mandatory goals. Checks covered 277,390 pre-edge, post-edge, and held samples
each (832,170 observations), including 114,000 randomized cycles. The ledger
recorded 44,591 accepted windows, 42,485 consumed windows, and 2,106 explicitly
canceled windows, with every remaining obligation drained.

Verilator `--lint-only --timing -Wall` passed all 57 profiles without warnings or
waivers. Twenty-three injected faults were detected, including wrong byte/bit
offsets, spill loss, missing isolation, incorrect metadata/status, stalled-entry
overwrites, flush replay, incorrect reset/clock timing, and 1 ps output pulses.
Portable Yosys structure checks passed 36 profiles with no latches or unresolved
references; combinational profiles have no storage and disabled directions have
no corresponding shift cells. This is independent of technology synthesis.

All 31 existing synthesis/power tests passed with their tool stubs. Port-only
checking, ordered source discovery, explicit source overrides, and report
preservation during Make dry runs passed. A focused three-byte asynchronous run
from `/tmp` with seed 53 passed with all guards/probes retained. Native VCS was
unavailable and is explicitly `NOT_RUN`.

Reports are under `build/validation/data-aligner-final` and the neighboring
`data-aligner-*` directories. Recorded source/helper/dependency hashes match
the tested snapshots; these artifacts remain ignored by Git.
