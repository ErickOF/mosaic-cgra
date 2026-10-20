# SRAM-wrapper verification

The specification is
[`specs/basic/mosaic-sram-wrapper/README.md`](../../../../../specs/basic/mosaic-sram-wrapper/README.md).
The implementation separates [`sram_wrapper.sv`](../../../rtl/basic/sram_wrapper.sv)
from [`sram_wrapper_backend.sv`](../../../rtl/basic/sram_wrapper_backend.sv).
The decorated PyUVM test is `test_sram_wrapper.SramTest`.

```sh
make setup
make sram-wrapper-regression              # native VCS
make sram-wrapper-regression SIM=icarus   # four-state RTL simulation
make pyuvm SIM=icarus COCOTB_TOPLEVEL=sram_wrapper
```

To filter profiles while retaining all parameter and protocol probes:

```sh
.venv/bin/python src/val/basic/sram_wrapper/run_sram_wrapper_regression.py \
  --sim icarus --build-dir build/sram-focused \
  --case w16_d3_g4_t3_l2_c3_a1 --seed 42 --random-cycles 1000
```

Names encode width, depth, mask granularity, tag width, read latency, read credits
and asynchronous reset. `reference_` names select the verification backend.
`--case` is repeatable. Seeds use the base seed plus each profile's position in
the full matrix, preserving reproducibility when filtering. Paths resolve relative
to the runner, so another working directory is supported. At least 1000 random
cycles are required. The runner also accepts compiler/runtime flags, a simulator
binary directory and `--rtl` for shell-checker qualification.

Make settings are `SRAM_WRAPPER_REGRESSION_BUILD`, `SRAM_WRAPPER_RANDOM_CYCLES` and
`SRAM_WRAPPER_SEED`. Reports default to
`build/<simulator>/sram_wrapper/regression`; dry runs preserve existing evidence.
Direct `make pyuvm` expects the `SRAM_WRAPPER_` environment variables corresponding
to `DATA_WIDTH`, `DEPTH`, `MASK_GRANULARITY`, `TAG_WIDTH`, `READ_LATENCY`,
`MAX_OUTSTANDING_READS` and `ASYNC_RESET`, with specification defaults. HDL compiler
overrides must match; the regression runner supplies both configurations.

`SRAM_WRAPPER_CHECK_INTERNALS=0` selects port-only checking and records geometry,
raw-storage and backend-pin assertions as `NOT_RUN`. It supports adapters whose
private hierarchy differs from the provided implementations.
`SRAM_WRAPPER_COVERAGE_FILE` selects another coverage path. Use
`TEST_SETTLE_NS=0` and 1 ps or finer precision. Timing-annotated gate simulation
needs a separate timing-aware sampling policy.

## RTL reuse and backend replacement

The shell reuses common `decoder` for fail-closed address qualification, `dff` for
latency/tag and response-pointer state, `counter` for outstanding and queued read
counts, and `operand_isolation` for idle backend inputs and invalid responses.
Its response ring provides synchronous flush and a maturity bypass, whereas the
existing FIFO has no flush input and a registered empty-output boundary.
Dependency and backend source hashes provide release evidence without a dependency
lockfile. Tags are opaque bits; no private memory-protocol encoding is introduced.

The default backend contains unreset storage and native per-granule clocked writes.
Zero-mask writes are accepted no-ops and issue no backend operation. Idle address,
write mask and write data are clamped; masked-off write-data lanes are also clamped.
One accepted request issues at most one physical operation. Reads snapshot the
word at acceptance, preserving read-before-later-write ordering.

For direct `pyuvm`, SAIF and synthesis targets, set
`SRAM_BACKEND_SOURCE=/absolute/path/to/adapter.sv` to replace the default file.
The adapter must define `sram_wrapper_backend` with the same geometry parameters
and pins: `i_clk`, `i_enable`, `i_write`, `i_addr`, `i_wdata`, `i_wmask`, `o_rdata`.
Select exactly one backend definition. Additional vendor model sources can be
provided through an explicit ordered `VERILOG_SOURCES` list. The built-in regression
deliberately selects its two provided backends explicitly.

An adapter must preserve depth, width, 1RW behavior, mask polarity/granularity,
bit order, latency and back-to-back hazards. Native enables or an approved
combinational mapping are required; sequential read-modify-write emulation is
outside this contract. Macro test, sleep, repair and power pins stay in the
adapter. Vendor functional models, consistent physical views and technology
libraries are required to qualify a physical SRAM implementation.

`sram_wrapper_model_backend.sv` is a verification-only alternative using granule
planes and a timestamped return calendar. It has no memory initialization and
drives the same pins with the same timing. Its calendar initialization is testbench
state. Passing this model establishes local backend contract checking, not vendor
macro equivalence.

## Edge timing, credits and cancellation

A read accepted at edge `t` matures **after edge `t + READ_LATENCY`**. If no earlier
response is queued, response valid/data/tag become visible at that edge. The first
possible consumption is the following edge. This is the explicit timing selected
for this implementation. Legal minimum credits equal `READ_LATENCY`; sustaining
one accepted read every cycle needs at least `READ_LATENCY + 1` credits. Minimum
credit profiles have admission bubbles, recorded as an explicit coverage exclusion
for the continuous-read-stream goal. Writes sustain one accepted request per cycle.

Credits count every accepted, unconsumed read, including backend pipeline slots and
completed responses. The final backend stage bypasses an empty response ring. A
stalled return is stored on the next edge, and queued older responses always win.
Simultaneous consumption and maturity are supported, and consuming a response frees
a read credit on that same edge. Writes need no read credit.

Reset and flush clamp request ready, response fields, busy and visible count
immediately. Synchronous reset/flush clear protocol state on the edge; an entirely
clockless pulse leaves its read obligations intact after release. Asynchronous
reset assertion cancels obligations immediately. Backend returns from canceled
reads continue physically but cannot create a response or consume a new credit.
Response payload slots hold while invalid; protocol validity, pointers and tags
clear, and public invalid data/tag are zero. Memory contents never reset, and
previously committed writes survive cancellation.

An active invalid or unknown address raises request error and blocks acceptance
and backend issue. Known unused encodings are exercised as rejected requests that
can be corrected or withdrawn. Unknown addresses also trigger a live assertion.
Only a legal stalled offer acquires a requester hold obligation; reset/flush cancel
that offer. All its fields, including currently ignored fields, must otherwise
remain stable until acceptance.

Write masks must be known on active writes. Enabled write data and accepted read
tags must normally be known; directed fault items explicitly permit X/Z transport.
Masked-off data is ignored, as are data/mask on reads and tags on writes.
Unwritten words remain unknown until software/configuration writes them. Read
responses preserve unknown storage data without substituting a deterministic value.

Ownership, context interpretation, canonical contract packaging, reset release,
CDC/RDC, BIST, power-state entry and cancellation side effects belong to integration.
Liveness requires eventual response readiness; this wrapper cannot force progress
against permanent consumer backpressure.

## PyUVM structure and checking

The suite separates config, transactions, sequences, driver, monitor, agent,
independent model, scoreboard, coverage and environment, reusing `mosaic_uvm`
component wiring, four-state conversion, pattern classification and runner tools.

The model keeps committed words and a deque of timestamped read snapshots and
tags. It distinguishes accepted reads/writes, effective writes, zero-mask no-ops,
physical backend returns, live read maturity, consumed responses and canceled
obligations. It enforces `accepted_reads = consumed + canceled + pending` after
every observation. Expected data comes from accepted masked writes rather than
DUT storage. Unreset response-slot samples provide only a quiet-state baseline.

Checks run before the edge, at the real rising edge before NBA updates, after
settling and during a held interval. Optional internal checks compare every memory
word, backend pins, pipeline-valid bits, tags, counts, pointers and response slots.
Canceled physical returns are checked independently of live public responses.
Continuous monitors reject finite requester changes, unknown controls, held-output
pulses and unauthorized writes between samples. Clockless reset/flush tests check
the difference between immediate output clamps and actual state cancellation.

## Matrix and required coverage

The runner defines 46 inferred profiles and eight verification-backend profiles.
The exact tuples are in `run_sram_wrapper_regression.py`. Widths range from 1 to
257 bits, depths from 1 to 1024 with odd and power-of-two organizations, granules
from one bit to a full word, tags from one to seven bits, latencies 1–4, credits
from the legal minimum through nine, and both reset modes.

Every profile requires 28 goals, including:

- Every read/write address, every same-address operation pair, every mask bit and
  mask-pattern/change-preserve cross. Directed writes preserve masked-off zeros
  and ones independently.
- Every outstanding count, completed-queue level and latency-stage/count cross.
- Read/write by empty/partial/full credit state, every feasible acceptance/response
  consumption combination, writes at full credits and same-edge read-credit reuse.
- Response stalls of zero through eight plus 32 cycles, and stalls at every
  outstanding count; tag-pattern/ordering-distance crosses.
- Reset/flush from every latency stage and response-queue occupancy, and pulses
  between edges while empty, in flight and buffered.
- Every unused address encoding, uninitialized reads, canceled physical returns,
  zero-mask no-ops, masked-off X/Z bits, and every response-data/tag bit as 0, 1, X and Z.
- Continuous writes, continuous reads when credits permit, exact random cycle
  count, obligation conservation and all sampling stages.

Unreachable bins identify their profile: one-bit walking-zero masks cannot change
storage, one-credit profiles have no partial credit state, exact power-of-two
address spaces have no unused encoding, and minimum-credit profiles have the
timing-related read-stream exclusion described above.

Thirty-one malformed parameter profiles must fail the named elaboration guard.
There are 102 negative probes for unknown global/operation/address/mask controls,
each enabled write-data/read-tag bit in a small profile, every stalled request
field and a finite requester pulse, across both reset styles. Each must fail the
exact decorated test with its expected live assertion; compile failures, missing
tests, unrelated exceptions and fallback failures do not count as rejection.

## Evidence and qualification scope

The runner checks native JUnit identity, exact parameters/backend, every mandatory
goal, seed and random count. Reports include shell, dependency, backend and
verification source hashes, UTC timestamps and per-case logs. Filtered runs are
marked `selected_profiles`. Generated evidence and local qualification helpers
remain under ignored `build/validation/`.

The local Icarus campaign passed all 54 profiles, 108,000 random cycles and
1,000,578 observations. It accounted for 59,079 accepted reads, 52,928 consumed
responses and 6,151 cancellations, with no read pending. All 59,079 physical
returns were tracked, including canceled returns. The 55,596 accepted writes
included 4,790 zero-mask no-ops. All 31 parameter guards and 102 protocol probes
passed. The checker detected all 30 injected shell/backend defects, including
incorrect credits, mask polarity/order, address aliasing, wrong latency, response
reordering, cancellation failures and idle accesses. All 31 synthesis/power flow
tests also passed with their tool stubs.

Verilator lint passed all 46 inferred profiles without warnings or waivers, using
`--unroll-count 1024` for the widest granular-write loop. Yosys structural checks
passed those profiles, confirming logical bank width/depth, synchronous read and
write ports, unknown initialization, no bank reset, no latch/generated clock and
no unresolved reference. These generic checks do not establish SRAM macro mapping
or physical area, timing or power.

Supplemental unbounded binary proofs cover eight depth-one/depth-three profiles,
full-word/granular masks, latencies one/two, minimum/expanded credits and both reset
styles. They compare committed memory and timestamped read queues from equal
arbitrary initial memory and empty protocol state. Observer-only backend ports
expose memory and latency state for proof invariants; functional logic is unchanged.
The asynchronous reset model uses `async2sync` at clock edges. These proofs do not
establish X/Z behavior, reset-release timing, liveness or technology equivalence.

Native VCS, native HDL SVA, licensed lint/CDC/RDC, DFT, VC LP, vendor macro/view
qualification, canonical contract matching, technology mapping and physical
timing/power require their tools and integration artifacts. Reports record those
checks as `NOT_RUN`, separately from local RTL simulation and generic analysis.
