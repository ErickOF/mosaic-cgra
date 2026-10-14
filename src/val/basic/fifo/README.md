# Synchronous FIFO validation

This PyUVM suite checks `src/rtl/basic/fifo.sv` against
`specs/basic/mosaic-fifo/README.md`. It uses the shared agent, environment,
coverage and regression helpers under `src/val/lib/mosaic_uvm`.

The module has a single rising-edge clock, independent ready/valid producer and
consumer interfaces, exact `DEPTH` capacity, and no empty-queue bypass. Input
accepted at an edge first becomes visible after that edge. At full capacity,
`i_ready` can assert `o_ready` so the old head is consumed and replaced without a
bubble, including at depth one. `o_valid` depends only on stored occupancy.

## RTL parameters and reuse

| Parameter | Default | Restriction |
| --- | --- | --- |
| `DATA_WIDTH` | 32 | Positive integer |
| `DEPTH` | 4 | Positive integer, including non-powers of two |
| `ASYNC_RESET` | 0 | Exactly 0 or 1 |
| `ALMOST_FULL_LEVEL` | `DEPTH > 1 ? DEPTH - 1 : 1` | 1 through `DEPTH` |
| `ALMOST_EMPTY_LEVEL` | `DEPTH > 1 ? 1 : 0` | 0 through `DEPTH - 1` |

`PTR_WIDTH = max(1, ceil(log2(DEPTH)))` and
`OCC_WIDTH = ceil(log2(DEPTH + 1))` are derived local parameters. Widths cannot be
overridden independently. Thresholds are independent: almost-full and almost-empty
may overlap when the selected levels overlap. Invalid configurations instantiate
an explicit unresolved elaboration guard; safe declaration sizes prevent invalid
negative or unknown dimensions from allocating an array first.

Common `dff` instances hold read/write pointers and occupancy. Pointer enables are
exactly pop/push; occupancy is enabled only when push differs from pop. Explicit
terminal wrapping handles depth one and odd depths. Common `operand_isolation`
clamps the output to zero while empty, hiding uninitialized/stale memory.

The inferred unpacked array contains exactly `DEPTH * DATA_WIDTH` bits. Only a
push with reset inactive writes one entry. Storage has no reset and all state
uses `i_clk` directly. For full replacement, the consumer samples the old head
before the nonblocking write updates the same address. A technology memory must
preserve this behavior; this portable array does not qualify a particular macro.

Ordered dependencies are discovered for simulation and synthesis. Reports hash
the actual RTL, both common dependencies, all suite/shared Python helpers and
the Makefile. No dependency lockfile is needed.

## Running

```sh
make fifo-regression                         # VCS on the licensed server
make fifo-regression SIM=icarus              # local four-state simulation
make pyuvm SIM=icarus COCOTB_TOPLEVEL=fifo    # default-parameter profile

.venv/bin/python src/val/basic/fifo/run_fifo_regression.py \
  --sim icarus --build-dir build/fifo-focused \
  --case w8_d3_sync --case w1_d1_async
```

`FIFO_REGRESSION_BUILD`, `FIFO_SEED` (default 20261013), and
`FIFO_RANDOM_CYCLES` (default 2000; minimum 1000) configure the Make target.
The standalone runner also accepts `--seed`, `--random-cycles`, `--rtl`,
`--sim-bin-dir`, `--make`, `--compile-args`, and `--sim-args`. Selected cases keep
their index in the complete matrix when deriving their seed. Paths are resolved
from the runner, so it can be invoked from another working directory.

For direct parameterized simulation, match the RTL options with `FIFO_DATA_WIDTH`,
`FIFO_DEPTH`, `FIFO_ASYNC_RESET`, `FIFO_ALMOST_FULL_LEVEL`, and
`FIFO_ALMOST_EMPTY_LEVEL` environment variables. These describe the expected
elaborated interface; setting an environment variable does not change the RTL.
For example:

```sh
FIFO_DATA_WIDTH=8 FIFO_DEPTH=3 FIFO_ASYNC_RESET=1 \
  FIFO_ALMOST_FULL_LEVEL=2 FIFO_ALMOST_EMPTY_LEVEL=1 \
  make pyuvm SIM=icarus COCOTB_TOPLEVEL=fifo \
  SIM_BUILD=build/fifo-custom \
  COMPILE_ARGS='-Pfifo.DATA_WIDTH=8 -Pfifo.DEPTH=3 -Pfifo.ASYNC_RESET=1'
```

Use fresh build directories when changing direct-run parameters or compiler
options. The runner invalidates JUnit/coverage and makes parameter changes force
recompilation automatically. Use `TEST_SETTLE_NS=0` and 1 ps precision or finer.
This is a zero-delay RTL suite, not a delayed gate-level timing checker.

`FIFO_CHECK_INTERNALS=0` permits port-only checking for equivalent implementations;
the report records structural assertions as `NOT_RUN`. The standard regression
requires the internal checks, so it never treats missing hierarchy as a pass.

## Reference model and assertions

The model uses a Python `deque` of accepted four-state words. It computes capacity
and handshakes from its own queue and the driven inputs, without using DUT
occupancy, pointers or storage. Each consumed output is compared with the oldest
accepted word before removing that word. Accepted items must equal consumed items
plus items explicitly discarded by reset; the test drains the final queue.

The driver sets up inputs with the clock low. The monitor samples real DUT ports
before the edge, after sequential updates, and after a quiet hold interval. Reset
pulses without a clock distinguish synchronous preservation from asynchronous
clearing. Reset wins over attempted push/pop and does not write memory.

Checks include occupancy bounds, all status/threshold equations, readiness at full,
valid independent of ready, zero data while empty, no input fall-through, ordering,
state updates, and pointer bounds/wrapping. The monitor also watches actual signal
changes so finite pulses during quiet intervals cannot disappear between samples.
Every memory entry is checked after every sample: only an accepted write may
change its addressed entry. Pointers and occupancy must remain quiet without
their enables; output valid/data remain stable under consumer backpressure.

The producer must hold valid and data until acceptance, unless reset cancels the
request. Directed and random normal traffic obey this assumption. X/Z reset,
valid and ready are illegal and cause explicit protocol assertions. Separate
expected-failure probes verify each diagnostic for both reset styles, plus data
changes and valid withdrawal by a stalled producer. An unrelated failure or
skipped test does not count as detection.

Normal accepted data is known. A labeled four-state transport campaign deliberately
injects X and Z into each data bit, checking exact storage and returned values
without integer conversion or sanitization. No known-control behavior is promised
after an illegal control injection; every negative probe runs in a fresh process.

## Matrix and coverage

The 114 profiles comprise:

- All 6 widths (1, 8, 32, 64, 128, 256) by all 8 depths (1, 2, 3, 4, 5, 8, 16, 31)
  by both reset styles, with default thresholds: 96 profiles.
- Opposite extreme thresholds (almost-full 1, almost-empty `DEPTH - 1`) at every
  non-unit depth and both reset styles: 14 profiles.
- Middle thresholds at depths 8 and 31 with both reset styles: 4 profiles.

Each profile includes every occupancy, all reachable occupancy x push x pop bins,
all occupancy x input-valid x output-ready bins, all read-wrap x write-wrap bins,
reset from every occupancy, both directions of each threshold crossing, prolonged
producer/consumer stalls, repeated wrap, full replacement and full-rate streams.
It checks data patterns, every intentional X/Z payload bit, between-edge reset
pulses, and seeded random traffic with producer hold and reset cancellation.

Coverage has 17 mandatory goals. The runner requires exactly one unskipped
`test_fifo.FifoTest`, matching parameters/seed/random-cycle count, every coverage
goal, internal assertions, all 22 invalid-parameter guards, and all 16 protocol
probes. Results are written to `build/<sim>/fifo/regression/summary.json` with
per-profile JUnit, coverage, compilation inputs and simulator logs. Expected-failure
probe JUnit files contain failures by design; the summary verifies their cause.

## Local evidence

The local 2026-10-13 run used Icarus, cocotb 2.1.0 and PyUVM 5.0.0. The full
matrix passed 228,000 randomized cycles and 1,129,650 pre/post/held observations.
All 227,014 accepted items were either consumed (156,618) or explicitly discarded
by reset (70,396). These counts include directed and intentional X/Z traffic.

| Check | Result | Evidence under `build/validation/` |
| --- | --- | --- |
| 114 profiles, 17 goals each, 22 guards, 16 protocol probes | PASS | `fifo-final/summary.json` |
| Focused external-directory run, seed 42, 1000 random cycles | PASS | `fifo-custom/summary.json` |
| Direct Make invocation with port-only assertions | PASS; internals NOT_RUN | `fifo-port-only/coverage.json` |
| All-profile Verilator lint, no warnings or waivers | PASS | `fifo-lint/summary.json` |
| All-profile Yosys storage, reset, clock and latch checks | PASS | `fifo-structure/summary.json` |
| 20 intentionally broken implementations detected | PASS | `fifo-mutations/summary.json` |
| Existing synthesis/power flow tests using tool stubs | PASS, 31 tests | `python3 -m unittest discover -s tests -v` |
| Native VCS | NOT_RUN, executable unavailable | `fifo-vcs/summary.json` |

The mutation checks include full-boundary bubbles, ready-dependent valid,
fall-through, empty-data leakage, unauthorized writes, pointer enables/wrapping,
occupancy updates, payload corruption, reset-style errors, thresholds, lost
depth-one replacement, and four finite 1 ps pulses during quiet intervals.
Portable structural checks confirm exactly one inferred array with the specified
capacity, one clocked write port and one asynchronous read port, uninitialized
storage, resettable control registers, no generated clocks and no latches.
The local static/mutation probe scripts and reports stay in the ignored build
directory; the maintained PyUVM regression is the runner documented above.

## Tool and integration scope

The summary records missing licensed/static/physical checks as `NOT_RUN`.
PyUVM provides live equivalents of the required assertions; HDL SVA compilation,
formal safety/liveness, commercial lint, CDC/RDC, DFT, VC LP, technology synthesis,
physical timing and physical power are separate qualification steps. Local lint or
portable structural synthesis does not substitute for those checks.

The hierarchy has no CDC synchronizer or internally gated clock. For asynchronous
reset, release must be synchronized externally. Integration must provide coherent
single-domain data, producer/consumer reset ordering, a queue drain/discard or
retention policy, and a timing budget for the full-boundary `i_ready` to `o_ready`
path. Insert a suitable interface buffer if that combinational path is prohibited.
Formal liveness requires consumer fairness; a permanently stalled consumer cannot
be required to drain. Physical and power characterization require the server's
technology, cell/memory models, timing constraints and representative activity.
