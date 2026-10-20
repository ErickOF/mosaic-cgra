# Skid-buffer verification

The specification is
[`specs/basic/mosaic-skid-buffer/README.md`](../../../../../specs/basic/mosaic-skid-buffer/README.md).
The implementation is [`skid_buffer.sv`](../../../rtl/basic/skid_buffer.sv).
The decorated PyUVM test is `test_skid_buffer.SkidBufferTest`.

```sh
make setup
make skid-buffer-regression              # native VCS
make skid-buffer-regression SIM=icarus   # four-state RTL simulation
make pyuvm SIM=icarus COCOTB_TOPLEVEL=skid_buffer
```

Run selected profiles while retaining all parameter and protocol probes:

```sh
.venv/bin/python src/val/basic/skid_buffer/run_skid_buffer_regression.py \
  --sim icarus --build-dir build/skid-focused \
  --case w65_a1 --seed 42 --random-cycles 1000
```

`--case` is repeatable. Names encode data width and asynchronous-reset selection.
The seed is the base seed plus the profile's position in the full matrix, so
filtering preserves reproducibility. The runner resolves sources relative to
itself and works from another directory. At least 1000 random cycles are required.
It also accepts `--rtl`, compiler/runtime flags and a simulator binary directory.

Make settings are `SKID_BUFFER_REGRESSION_BUILD`, `SKID_BUFFER_RANDOM_CYCLES` and
`SKID_BUFFER_SEED`. Reports default to `build/<simulator>/skid_buffer/regression`;
`make -n` preserves existing evidence. Direct `make pyuvm` expects
`SKID_BUFFER_DATA_WIDTH` and `SKID_BUFFER_ASYNC_RESET`, defaulting to 32 and zero.
HDL compiler overrides must match; the runner supplies both configurations.

`SKID_BUFFER_CHECK_INTERNALS=0` selects port-only checks and records geometry and
raw-storage assertions as `NOT_RUN`. `SKID_BUFFER_COVERAGE_FILE` selects a different
coverage path. Use `TEST_SETTLE_NS=0` and 1 ps or finer precision. These checks
target zero-delay RTL rather than timing-annotated gate models.

## RTL reuse and interface obligations

Common `dff` implements the single resettable validity bit. Common `mux` selects
buffered or bypassed data; `operand_isolation` clamps invalid output to zero.
The `DATA_WIDTH` payload bits are unreset and write only on stall capture. Idle,
bypass, hold, release and reset preserve them. The Makefile supplies ordered
dependencies for simulation and synthesis, and evidence records their source
hashes without introducing a dependency lockfile.

Upstream ready is `!buffer_valid`. Empty valid traffic bypasses immediately. When
the consumer stalls, the empty entry accepts and captures the offered item. While
full, the stored item wins over current input. Releasing it consumes the old item
without accepting a replacement because pre-edge upstream ready is still low.
After release, bypass resumes immediately; a waiting input can transfer on the
following edge, allowing consecutive output transfers.

The producer must retain valid and the complete item whenever blocked. The test
keeps that obligation through the full release edge and until the next actual
input acceptance. Invalid input data may change freely. Normal accepted data must
be known; directed transactions explicitly opt into intentional X/Z transport.
All sidebands must be packed into the same item to preserve coherence.

Reset has priority over capture and release, and no reset edge credits a transfer.
Synchronous reset clears occupancy on its rising edge; an entirely clockless pulse
does not discard storage. Asynchronous assertion clears occupancy immediately.
Payload holds for both styles. Reset does not mask the forward bypass: after reset
takes effect, upstream ready is high and output valid equals input valid. The
integration must suppress or disregard reset traffic. Unknown reset, valid and
ready controls trigger live assertions even between sampled transactions.

Reset release synchronization, CDC/RDC, item format, power-transition policy and
consumer progress belong to integration. Eventual downstream ready is required
for liveness. Chaining breaks each reverse ready path, while data and valid still
pass combinationally through empty entries. The skid buffer is neither a CDC
primitive nor a fully registered forward boundary.

## PyUVM structure and checking

The suite separates configuration, transactions, sequences, driver, monitor, agent,
model, scoreboard, coverage and environment. It reuses shared `mosaic_uvm`
component wiring, four-state helpers, data-pattern classification and regression
execution/validation.

The independent queue appends each accepted input before consuming an output on
the same edge, allowing empty bypass. A buffered release cannot append a new item.
Every consumed output must match the oldest accepted token, including its bypass
or buffered timing. The ledger checks
`accepted = consumed + reset_discards + pending` after every observation. The test
drains stored tokens and waiting producer offers before finishing.

The monitor observes real DUT ports before the edge, on the actual rising edge
before NBA updates, after settling and during a held interval. Clockless items
check forward bypass and the registered ready boundary. Optional raw-storage
predictions verify that only capture writes data. The initial payload is sampled
only as a hold baseline, never as an architectural power-up value.

Continuous monitors enforce producer stability, reject finite held-output pulses
and unauthorized storage writes, and check asynchronous reset responses. Checks
cover both sampled values and signal activity between samples.

## Matrix and coverage

Eighteen widths run with both reset styles, for 36 profiles:
`1, 2, 3, 7, 8, 16, 31, 32, 33, 63, 64, 65, 127, 128, 129, 255, 256, 257`.

Every profile requires 19 goals:

- All eight occupancy/input-valid/downstream-ready combinations and every feasible
  previous-operation/next-operation pair across idle, bypass, capture, hold and release.
- Buffered hold lengths zero through eight plus 32 cycles, with and without a
  waiting producer, crossed with captured data-pattern classes.
- Producer stalls of zero or each buffered hold length plus the release edge.
- At least 64 consecutive bypass transfers, consecutive release/bypass transfers,
  and a 32-cycle producer idle interval.
- Reset occupancy/handshake crosses, first acceptance after reset, and clockless
  reset pulses while empty and buffered.
- Every clockless occupancy/valid/ready combination, checking immediate bypass
  and absence of a combinational reverse ready path.
- Zero, one, alternating, walking-one and walking-zero data in bypass, capture
  and release; every data bit transported in all three phases as 0, 1, X and Z.
- Every invalid payload bit carrying X and Z, exact token conservation, exact
  randomized cycle count and all sampling stages.

Eight malformed width/reset configurations must fail the named
`skid_buffer_parameters_must_be_valid` elaboration guard. Fifty-four negative
probes cover X/Z controls while empty and buffered, every accepted data bit in a
three-bit bypass and capture instance, dropping/changing a blocked offer and a
finite blocked-producer pulse, with both reset styles. Each must fail the exact
decorated test with the expected live assertion. Compile errors, missing tests,
unrelated exceptions and the probe's fallback failure do not count as rejection.

## Evidence and qualification scope

The runner validates native JUnit identity, geometry, every mandatory coverage
goal, seed and random count. Summaries record RTL, dependency and verification
source hashes, UTC timestamps and per-case evidence. Filtered runs are marked
`selected_profiles`. Generated evidence and local qualification helpers remain
under ignored `build/validation/`.

The local Icarus campaign passed all 36 profiles, 72,000 randomized cycles and
749,528 observations. Its ledger accounted for 60,226 accepted items, 59,255
consumed items and 971 reset discards, with nothing pending. All eight elaboration
guards and 54 protocol probes passed. The checker detected all 25 injected RTL
defects, including broken bypass, a combinational reverse ready path, buffered
replacement, payload writes outside capture, wrong reset styles, sanitized X/Z
storage, wrong clock edges and finite output pulses. All 31 existing synthesis and
power flow tests also passed using their tool stubs.

Verilator lint passes all 36 profiles without warnings or waivers. Yosys structural
checks confirm exactly `DATA_WIDTH` unreset data bits and one validity bit with
the selected reset style, no latch/memory/generated clock, combinational forward
data/valid paths, and no combinational path from input data, input valid or
downstream ready to upstream ready.

All 36 supplemental unbounded binary proofs pass against an independent
accepted-item state/output model from equal arbitrary initial state. They cover
bypass, capture, stored-item priority, holds, release and reset. Asynchronous reset
uses `async2sync` for an edge-domain model; these proofs do not establish X/Z,
between-edge reset timing, liveness or technology equivalence. Yosys 0.33 cannot
parse the common mux's multidimensional packed port, so its generated frontend
view flattens that port and the indexed word select without changing bit order.
The view's hash is recorded separately. Lint and simulation use the original RTL.

Native VCS and licensed lint/CDC/RDC, DFT, VC LP, technology synthesis, physical
timing/power, forward-chain timing and power-transition checks require their tools,
libraries and integration artifacts. Reports record those external checks as
`NOT_RUN`, separately from local qualification.
