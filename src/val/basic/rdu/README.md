# Reconfigurable delay-unit verification

The specification is
[`specs/basic/mosaic-rdu/README.md`](../../../../../specs/basic/mosaic-rdu/README.md).
The implementation is [`rdu.sv`](../../../rtl/basic/rdu.sv).
The decorated PyUVM test is `test_rdu.RduTest`.

```sh
make setup
make rdu-regression              # native VCS
make rdu-regression SIM=icarus   # local four-state RTL regression
make pyuvm SIM=icarus COCOTB_TOPLEVEL=rdu
```

Run selected allocations with all parameter and protocol guards:

```sh
.venv/bin/python src/val/basic/rdu/run_rdu_regression.py \
  --sim icarus --build-dir build/rdu-focused \
  --case w8_c6-2_a1 --seed 42 --random-cycles 1000
```

`--case` is repeatable. Case names encode data width, channel capacities in
channel order, and asynchronous-reset selection. The effective seed is the base
seed plus the case's index in the complete matrix, preserving reproducibility
when filtering. The runner resolves sources relative to its own location and
works from another directory. It accepts `--rtl`, compiler/runtime flags and a
simulator binary directory. At least 1000 random cycles are required per case.

Make settings are `RDU_REGRESSION_BUILD`, `RDU_RANDOM_CYCLES` and `RDU_SEED`.
Reports default to `build/<simulator>/rdu/regression`; `make -n` preserves them.
For direct `make pyuvm`, expected geometry uses `RDU_DATA_WIDTH`,
`RDU_NUM_CHANNELS`, `RDU_TOTAL_DELAY_ENTRIES`, `RDU_CHANNEL_CAPACITY` and
`RDU_ASYNC_RESET`, with specification defaults. `RDU_CHANNEL_CAPACITY` is the
packed integer in decimal or `0x` notation. These environment values describe
expected parameters; compiler overrides must match them. The runner supplies
both automatically, including shell quoting for sized Verilog literals.

`RDU_CHECK_INTERNALS=0` selects port-only checking. Elaboration and internal
storage assertions then report `NOT_RUN`. `RDU_COVERAGE_FILE` overrides the
coverage report path. `TEST_SETTLE_NS` must be zero, with 1 ps or finer precision.
This suite checks zero-delay RTL, rather than timing-annotated gate models.

## Allocation and RTL behavior

`CAPACITY_WIDTH = max(1, ceil(log2(TOTAL_DELAY_ENTRIES + 1)))`; the runtime delay
field has the same width. Channel zero occupies the least-significant data,
delay and capacity fields. The packed allocation must have exactly
`NUM_CHANNELS * CAPACITY_WIDTH` bits and contain known, nonnegative fields whose
sum equals the total entry budget.

| Geometry | Legal `CHANNEL_CAPACITY` example | Meaning |
|---|---|---|
| Two channels, eight entries | `8'h44` | Four stages per channel; the default |
| Two channels, eight entries | `8'h26` | Six stages for channel zero, two for channel one |
| Three channels, seven entries | `9'h142` | Capacities `(2, 0, 5)` |
| Three channels, zero entries | `3'b000` | Pure bypass on all channels |

An unsized decimal such as `68` has the wrong declared width for the default
allocation and is rejected even though its numeric value equals `8'h44`.
Nondefault channel/budget geometries require an explicit allocation; they do not
silently reuse the default expression. Derived widths are local parameters.
Invalid dimensions, reset flags, unknown allocations, incorrect packed widths,
field bounds or allocation sums fail elaboration through the named
`rdu_parameters_must_be_valid` guard.

Channel `c` begins after the prefix sum of earlier capacities. The implementation
contains exactly `TOTAL_DELAY_ENTRIES * DATA_WIDTH` payload bits and
`TOTAL_DELAY_ENTRIES` validity bits. Flat storage buses use a constant wire
fallback when total capacity is zero; that fallback infers no sequential storage.

Common `dff` instances implement validity with the selected reset style. Payload
registers have no reset. They update only on an accepted advance and only when
their incoming token is valid. Bubbles shift validity while retaining payload.
Stages above the selected delay, disabled partitions and stalled channels hold
all state. Common `operand_isolation` instances clamp invalid or disabled outputs.
The Makefile supplies these ordered dependencies for simulation and synthesis.

A delay of zero bypasses storage. A delay of `D` exposes stage `D`, whose history
advances only on enabled, legal, unflushed schedule advances. The pre-edge output
is the token transferred at that edge; the post-edge output is the next tap value.
`o_output_transfer = i_advance AND o_output_valid` remains a combinational event
qualifier, rather than a clock or an independent ready-valid handshake.

Reset has priority over flush and advance. Reset and flush immediately clamp
outputs, even before a clock edge. Synchronous validity reset and all flushes
change stored validity only at a rising edge; asynchronous reset clears validity
immediately. Payload holds during both operations. Empty status reflects every
allocated validity bit, including inactive stages, and is always high for a
zero-capacity channel. A pending bypass operand is not included in empty status.

A known delay above capacity reports configuration error and cannot read another
partition or advance storage. An enabled unknown delay propagates X through its
unclamped outputs and error indication, then fails a live verification assertion.
Disabled channels ignore delay pins and clamp outputs without hiding live storage.

## Protocol and context boundaries

Delay changes require an empty partition, reset, or a flush that actually reaches
a clock edge. Disabling a live channel alone does not permit reassignment. The
checker retains the last clocked delay, so asserting flush without an edge cannot
license a later delay change after flush is withdrawn. Immediate output clamping
also prevents stale data exposure when new delay pins accompany a real flush.

The standalone consumer treats a valid zero-delay operand during a stall as
pending. Its data, valid, enable and bypass selection must remain stable until an
advance transfers it, or reset/flush explicitly cancels it. Continuous input
monitors enforce this obligation, including finite changes between sample points.
Changing data for a delayed channel during a stall is permitted because no input
is consumed then. Unknown invalid-input payload and unconsumed disabled inputs
are ignored; unknown consumed controls, validity or payload fail assertions.

Sequences exercise context-style drain, flush, reconfiguration and reuse. The RDU
does not know context IDs, operand identities, mapper encodings or activation safe
points. Those integration checks require the actual context controller and
architecture artifacts. Empty status alone does not cancel a pending bypass
operand in the producer/consumer interface.

## PyUVM structure and coverage

The suite separates `config`, `transaction`, `agent`, `driver`, `monitor`, `model`,
`scoreboard`, `coverage`, `env` and `sequences`. Agent/environment wiring, four-state
conversion, data-pattern classification and regression execution reuse
`mosaic_uvm`.

The independent functional model maintains per-channel token/bubble histories,
accepted counts, transferred counts and explicitly discarded counts. Expected
outputs come from those histories and current inputs, never DUT storage. It
checks per-channel token conservation after each edge and drains surviving tokens
before the test ends. Data patterns may repeat at one-bit widths, but validity,
bubble positions, scheduled opportunities and complete history are still checked.

Every item is observed before the edge, after the edge and during a held interval.
Optional internal checking compares every validity bit and payload stage. Only the
initial contents of unreset payload are sampled as a hold-check baseline; future
expected writes come from independently modeled tokens. That baseline never
determines functional output expectations. Bit masks identify which storage bits
may change at each edge. Continuous monitors reject changes to stalled, disabled,
inactive or bubble-fed stages, and detect finite output pulses during held periods.

The 88 profiles use both reset styles for 44 geometries:

- Width one: one-channel totals zero through three; every two-channel allocation
  of totals zero through three; every three-channel allocation totaling three;
  and a three-channel zero budget.
- Widths 8 and 65: `(4,4)`, `(6,2)`, `(0,8)`, `(8,0)`, `(2,0,5)`, `(1,3,0)` and `(16)`.
- Width 32: the default `(4,4)` allocation.
- Width 3: four-channel allocations `(1,2,0,3)`, `(1,1,1,1)` and `(0,0,0,0)`.
- Width 129: `(1,2)`.

Every profile requires 19 coverage goals: every channel/delay/input-valid cross,
every allocated stage's validity, every occupancy through the selected delay,
drain and flush from those occupancies, every representable illegal delay,
enable/transfer populations, stall lengths zero through eight, a 32-cycle stall,
all reset/flush/advance priority cases, reset occupancy, between-edge reset,
legal reconfiguration classes, all pattern classes and walking bits at every
delay, ignored unknowns, token conservation, exact random count and all sampling
stages. Zero-budget delay-change classes are explicitly unreachable and recorded
in `coverage_limits`.

Parameter guards cover 25 malformed dimensions, flags and allocation encodings.
The 61 negative protocol probes require the exact decorated test to fail with the
expected live assertion: individual unknown control/delay/valid/data bits, both
reset styles, pending-bypass instability, live delay changes while advancing,
stalled or disabled, and a flush that never reaches an edge. Unknown-delay
propagation is checked before the expected protocol assertion rejects it.
Known illegal delays are positive error-response tests: output clamping, error
reporting and state preservation must match the model.

## Evidence and qualification scope

The simulation runner checks exact JUnit identity, expected geometry, coverage,
seed and random count. Summaries include RTL, dependency and verification hashes,
per-case logs and UTC timestamps. Filtered campaigns are marked `selected_profiles`.
Generated reports and local qualification helpers stay under ignored `build/`.
No new dependency manifest or private channel-encoding package is introduced.

The local qualification campaign completed with these results:

| Check | Result |
|---|---|
| Icarus/PyUVM regression | 88 profiles; all 19 coverage goals per profile |
| Random stimulus | 176,000 cycles with 859,446 pre-edge, post-edge and held observations |
| Token accounting | 153,973 accepted, 127,682 transferred, 26,291 explicitly discarded |
| Parameter rejection | All 25 invalid configurations rejected at elaboration |
| Live protocol assertions | All 61 negative probes produced the expected assertion |
| Checker mutation campaign | All 23 injected defects detected |
| Verilator lint | All 88 profiles passed with the explicit waivers below |
| Yosys structural synthesis | All 88 profiles; exact storage budget, reset styles and clock connectivity |
| Local sequential equivalence | Unbounded induction passed for all 88 profiles |

Lint permits only an unused clock for a zero-entry combinational configuration,
and a constant capacity-bound comparison when the packed field's type already
limits it to the total budget. The allocation-sum check remains active. These
waivers are restricted to their exact diagnostics; other warnings fail the local
qualification check.

The local proof compares every output and storage bit against an independently
generated channel-history model. Both sides start with equal arbitrary binary
state; initial payload and validity are not forced to zero. Arbitrary binary
inputs include every representable delay, reset, flush, stall and enable case.
Yosys `async2sync` normalizes asynchronous reset for an edge-domain proof. This
proof does not cover X/Z behavior, reset timing between edges, or equivalence to a
technology-mapped netlist. Four-state and between-edge behavior are checked by
simulation. Separate passing runs checked port-only operation and a filtered
campaign launched from another working directory with a different seed.

Native VCS, licensed lint/CDC/RDC, DFT, VC LP, technology mapping, physical timing,
physical power, mapper contracts and context activation checks require the actual
tools and integration artifacts. The simulation runner marks these external
checks `NOT_RUN`; unavailable tools and incomplete proofs must never be reported
as passing. Separate local synthesis and formal results describe their own scope
and do not constitute physical release qualification.
