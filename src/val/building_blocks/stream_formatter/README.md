# Canonical stream formatter RTL and PyUVM validation

[`stream_formatter.sv`](../../../rtl/building_blocks/stream_formatter.sv) implements
the [stream-formatter specification](../../../../../specs/building-blocks/mosaic-stream-formatter/README.md).
It generates canonical frame and row markers, applies lane eligibility, clamps
invalid bytes, and either generates or validates incoming metadata. Data width,
lane positions and numerical representation remain unchanged.

## Run

```sh
make setup
make pyuvm SIM=icarus COCOTB_TOPLEVEL=stream_formatter
make stream-formatter-regression SIM=icarus
make stream-formatter-regression                # Requires VCS and its license
```

The decorated test is `test_stream_formatter.StreamFormatterTest`. Separate test,
environment, agent, driver, monitor, transaction, sequence, model, scoreboard and
coverage files follow the repository's PyUVM structure. The existing `mosaic_uvm`
library supplies component wiring, simulator execution, JUnit validation and
evidence handling. No existing shared RTL or Python helper is changed.

The full campaign contains **40 profiles**, **43 invalid-parameter checks** and
**16 expected-failure selected-byte probes**:

- Required 32-bit/one-lane, 64-bit/two- and four-lane, and 128-bit/four- and
  eight-lane geometries with both output profiles and both reset styles.
- Eight-bit/one-lane, 24-bit/three-lane, 48-bit/three-lane and 16-bit/two-lane
  geometries, narrow identifiers and count widths one through four.
- Exact default data, lane, count and identity widths, with both output and reset
  profiles. These runs transfer all 65535 beats of a maximum-length frame.
- Invalid widths, lane division/alignment, option values, unknown parameters and
  derived-width overflow, rejected at elaboration rather than startup.
- X/Z in selected byte zero and byte 15, in both output profiles and reset styles.

Every profile includes directed traffic and 2000 seeded random clock
opportunities. `STREAM_FORMATTER_SEED` defaults to 20261022 and advances by global
profile index. `STREAM_FORMATTER_RANDOM_CYCLES` must be at least 1000.
`STREAM_FORMATTER_REGRESSION_BUILD` selects the evidence directory.
`STREAM_FORMATTER_JOBS` selects 1–32 simulator processes; defaults are four for
Icarus and one for VCS. Select individual profiles with:

```sh
.venv/bin/python src/val/building_blocks/stream_formatter/run_stream_formatter_regression.py \
  --sim icarus --build-dir build/stream-formatter-selected \
  --case d128_l4_c8_p1_r0_m0
```

Custom direct runs require matching compiler parameters and
`STREAM_FORMATTER_<PARAMETER>` environment values. Icarus accepts
`-Pstream_formatter.PARAMETER=value`; VCS accepts
`-pvalue+stream_formatter.PARAMETER=value`. Use a fresh build directory when
changing geometry. The full runner handles flags, environment and rebuild
dependencies automatically.

Private storage/isolation checks default to enabled. A public-interface-only run
is available with `STREAM_FORMATTER_CHECK_INTERNALS=0`; its omitted checks are
reported as `NOT_RUN`. Tests use nominal 10 ns clock opportunities with 1 ps
observations and require zero-delay RTL (`TEST_SETTLE_NS=0`). They do not qualify
SDF-annotated netlists.

## Reuse and timing

The registered profile instantiates the existing `register_slice` for the entire
formatted data/metadata bundle. It has one entry, one-cycle minimum forward
latency, one beat per cycle throughput, and a combinational reverse ready path.
Consumption and replacement may occur together. The combinational profile stores
no beat and accepts input exactly when output is accepted. Both profiles require
integration that avoids a combinational ready/valid loop.

The existing `lane_mask` combines input lane validity with the frame eligibility
mask. Per-byte `operand_isolation` blocks clamp disabled bytes to zero. Separate
isolation blocks clamp invalid output payloads and both operands of metadata
comparisons, so generate mode ignores arbitrary incoming claims. Common DFFs
capture configuration, frame state, sticky flags and events. A common `write_gate`
enables configuration capture only for legal accepted configurations.

Common counters track accepted beats, emitted beats and row position. Row position
increments only on acceptance and clears at row end or the final partial row;
runtime row length never drives a divider or modulo operator. Beat counts hold
their terminal values after completion and clear on the next legal configuration,
flush or reset. They never exceed the configured count, including all-ones counts.

The configuration structure and output-beat structure remain local because their
field widths depend on public parameters. Configuration payload and register-slice
payload do not need reset: active/valid state qualifies every use. The checker
verifies actual capture enables and all unqualified storage holds.

## Framing and lane policy

A legal configuration has positive frame and row lengths, row length no larger
than the frame, nonzero lane eligibility and known controls and identities. It
owns the formatter through final output acceptance or flush. A partial final row
asserts both last and row-last. Row length one makes every beat row-first and
row-last; a one-beat frame asserts all four first/last markers. EOS is generated
only on the final beat when configured.

Both modes emit configured datatype, channel and context. Generate mode ignores
incoming marker and identity claims. Validate mode compares every claim against
the canonical values and still emits canonical metadata on errors. Input error
always propagates. Format and upstream errors accumulate independently when input
is accepted; final completion includes errors on the final beat. Error clear
affects only idle configuration errors, never active-frame error accumulation.

Lane zero occupies the least significant lane slice; byte zero is bits 7:0.
An input lane is consistent when its mask bit equals the reduction-OR of its keep
slice. Sparse keep inside a valid lane is legal. An empty input mask is an error.
Configured eligibility intentionally removes lanes without creating an error,
even if every effective output byte becomes invalid. Invalid bytes are zero and
the formatter never compacts or moves lanes.

Unknown input keep or lane-mask bits create format error and conservatively
disable those individual bits; known bits remain usable. An unknown input error
also creates format error and an asserted output error; only a known asserted
input error sets the separate input-error-seen flag. Unknown incoming claims are
ignored in generate mode and classified in validate mode. Unknown data in bytes
with effective keep low is allowed; unknown selected data fails verification.

Unknown valid cannot create acceptance. Unknown output ready cannot consume a
beat; an empty registered entry may still accept input independently of output
ready. Unknown flush or reset suppresses handshakes and preserves frame and held
payload state. Known reset clears state according to the selected reset style.
Asynchronous reset release must be synchronized externally.

## Flush and recovery

Flush suppresses input, output and configuration handshakes immediately. Its edge
clears active state, counters and frame error flags, drops the registered entry,
and pulses aborted if a frame existed. It preserves sticky configuration error.
Flush clears register-slice validity through its synchronous ready/valid path;
it never becomes an asynchronous payload reset. Repeated flush does not repeat
abort events once the frame is gone.

Illegal configuration is consumed without a frame start and leaves a sticky error
until idle error clear. A simultaneous invalid configuration takes priority over
error clear. Reset discards frame and buffered state without completion. The
producer and consumer must coordinate reset/flush and reframe before reuse.
Eventual input and consumer readiness are environment assumptions, separate from
the design safety assertions.

## Repository-local encodings

[`stream_formatter_pkg.sv`](../../../rtl/building_blocks/stream_formatter_pkg.sv)
defines modes and errors. Existing repository RTL contains no datatype catalog;
this baseline supports **every known datatype identifier as an opaque label**.
No external `mosaic-contracts` package or dependency manifest is introduced.
Integrations needing a restricted datatype catalog must validate it upstream or
define a future profile.

| Mode | Value |
| --- | ---: |
| `FORMAT_GENERATE` | 0 |
| `FORMAT_VALIDATE` | 1 |

| Configuration error | Code |
| --- | ---: |
| None | 0 |
| Unknown configuration field | 1 |
| Zero frame length | 2 |
| Zero row length | 3 |
| Row longer than frame | 4 |
| Empty lane eligibility | 5 |

| Format error, in priority order | Code |
| --- | ---: |
| None | 0 |
| Unknown checked control | 1 |
| Empty input beat | 2 |
| Lane/keep inconsistency | 3 |
| First / last mismatch | 4 / 5 |
| Row-first / row-last mismatch | 6 / 7 |
| EOS mismatch | 8 |
| Datatype / channel / context mismatch | 9 / 10 / 11 |

The lowest nonzero format code wins. Every detected class is also represented in
`g_formatter.detected[code-1]`. The bindable
`g_formatter.format_error_events[code-1]` qualifies each bit with input acceptance,
preserving all simultaneous mismatches exactly once per consumed beat. An optional
existing `performance_counters` bank can select these 11 events with unit
increments, independently enabled collection and saturation. Public start,
completion, abort and acceptance events supply the remaining frame/traffic event
inventory. The Python checker compares the complete fault bitmap and its qualified
events, rather than inferring them from the priority code.

## Verification evidence and scope

The reference model derives canonical framing mathematically from the accepted
index and maintains an independent one-entry output ledger. The source persists
beats until actual input acceptance; consumer backpressure is independently
scheduled. The scoreboard checks every public output at settled, pre-NBA and held
observations, including stalled payload stability, exact events, beat counts,
completion error and `accepted = emitted + discarded + buffered` conservation.

Directed cases cover both modes, every eligibility pattern and input mask,
full/partial/sparse byte keeps, all metadata faults, simultaneous faults, X/Z in
checked and ignored controls, one/two/typical/maximum frame lengths, partial rows,
first/middle/final input errors, sustained stalls, consume/replace, flush with a
final beat buffered, reset and error-clear recovery. Random traffic combines
sparse masks and keeps, metadata errors, upstream errors, starvation, output
backpressure and consecutive frames. Mandatory goals include random-only stalls,
starvation, errors and reachable replacement. Coverage records the specification's
geometry, marker, lane, keep, mode/error, identity, stall and recovery crosses.

Private assertions check configuration and elastic storage capture/hold, the
configuration write gate, row counter, isolated comparator operands and complete
fault events. Selected-byte probes must fail the actual PyUVM scoreboard with its
specific unknown-data diagnostic; a build failure or unrelated exception cannot
satisfy a probe.

The runner requires the exact decorated JUnit test identity, no skipped test,
matching geometry and seed, every mandatory goal and final accounting. Evidence
includes per-profile coverage, simulator logs and hashes of RTL, dependencies,
verification files, shared helpers and the Makefile.

Only Python/PyUVM simulation is run for this change. Lint, formal, CDC/RDC/DFT,
low-power checks, technology synthesis and physical timing/power are `NOT_RUN`.
Synthesis is deferred to **Design Compiler** with the repository flow when library
and technology setup are supplied. Simulation results do not claim those release
checks or physical qualification.
