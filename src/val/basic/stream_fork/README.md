# Stream-fork verification

The specification is
[`specs/basic/mosaic-stream-fork/README.md`](../../../../../specs/basic/mosaic-stream-fork/README.md).
The implementation is [`stream_fork.sv`](../../../rtl/basic/stream_fork.sv).
The decorated PyUVM test is `test_stream_fork.StreamForkTest`.

```sh
make setup
make stream-fork-regression              # native VCS
make stream-fork-regression SIM=icarus   # four-state RTL simulation
make pyuvm SIM=icarus COCOTB_TOPLEVEL=stream_fork
```

Run selected profiles while retaining every parameter guard and protocol probe:

```sh
.venv/bin/python src/val/basic/stream_fork/run_stream_fork_regression.py \
  --sim icarus --build-dir build/stream-focused \
  --case n3_w8_m1_a0 --seed 42 --random-cycles 1000
```

`--case` is repeatable. Names encode output count, data width, runtime-mask mode
and asynchronous-reset selection. Seeds use the base plus the profile's position
in the complete matrix, preserving reproducibility when filtering. The runner
resolves sources from its own location and accepts `--rtl`, compiler/runtime flags
and a simulator binary directory. At least 1000 random clock opportunities are
required; the default is 2000 per profile.

Make settings are `STREAM_FORK_SEED`, `STREAM_FORK_RANDOM_CYCLES` and
`STREAM_FORK_REGRESSION_BUILD`. Reports default to
`build/<simulator>/stream_fork/regression`. `make -n` preserves existing evidence.
Direct `make pyuvm` expects `STREAM_FORK_NUM_OUTPUTS`, `STREAM_FORK_DATA_WIDTH`,
`STREAM_FORK_HAS_DESTINATION_MASK` and `STREAM_FORK_ASYNC_RESET`, defaulting to
`2`, `32`, `0` and `0`. HDL parameter overrides must match those expectations;
the runner sets both configurations.

`STREAM_FORK_CHECK_INTERNALS=0` enables port-only checks and records elaborated
parameter and raw-storage assertions as `NOT_RUN`. `STREAM_FORK_COVERAGE_FILE`
changes the report path. Use `TEST_SETTLE_NS=0` with 1 ps or finer precision.
These checks target zero-delay RTL; a timing-annotated netlist needs a separate
sampling and protocol-checking policy.

## RTL reuse and interface obligations

Common `dff` implements the `NUM_OUTPUTS` resettable pending bits, with reset style
selected statically. Common `operand_isolation` clamps every invalid output lane.
The `DATA_WIDTH` payload bits have no reset or initialization and write only on
accepted input. There are no generated clocks, memories or per-output payload
registers. The Makefile supplies ordered source dependencies for simulation,
SAIF collection and synthesis. Regression evidence records their exact source
hashes without introducing a dependency lockfile.

Output `k` occupies `o_data[k*DATA_WIDTH +: DATA_WIDTH]`. Each pending destination
independently consumes one copy on a rising edge with valid and ready asserted.
Once consumed, that lane stays invalid and zero until a following accepted input
selects it. Input ready ignores completed/unselected outputs and asserts when
empty or when every remaining destination can consume on the next edge. New
input and old output handshakes may coincide; there is no forward combinational
bypass from input data, valid or destination to output data/valid.

With mask support enabled, valid input must select a known, nonzero destination
mask. Disabled mask support ignores the destination port, including X/Z values,
and selects every output. A blocked producer must hold valid, data and the
enabled mask until acceptance or reset. Ready must be known on pending outputs;
X/Z ready on completed/unselected outputs is harmless and explicitly exercised.
Normal accepted data must be known. Directed intentional X/Z payloads opt into
four-state transport checks and must retain their exact bits through storage,
stalls, packing and consumption.

Reset wins over every handshake and discards each still-pending copy. Previously
delivered copies remain delivered; there is no replay or transaction recovery.
Synchronous reset acts at a rising edge, so an entirely clockless reset pulse
preserves pending state. Asynchronous assertion clears pending immediately. Both
styles preserve raw payload. After reset takes effect all output data/valid is
zero and input ready is one; integrators must disregard apparent handshakes
during reset. Asynchronous reset release must be synchronized externally.

A slow selected consumer blocks the next multicast transaction. Progress requires
every selected consumer eventually to become ready and the surrounding system to
avoid cyclic dependencies. Consumer indexing, mask legality for disabled sinks,
CDC/RDC, reset ordering and power-transition recovery belong to integration.

## PyUVM structure and assertions

Separate files contain configuration, transaction, sequence, driver, monitor,
agent, independent model, scoreboard, coverage, environment and test. They reuse
`mosaic_uvm` component wiring, four-state conversion, pattern classification and
regression execution/evidence validation.

The model uses one queue per output. On an observed output handshake it checks
and removes that output's oldest copy. Only after consuming the old transaction
does it enqueue a newly accepted input into every selected queue. Each copy
records its transaction identity and acceptance edge. Assertions check at most
one active transaction, one-cycle minimum latency and the per-output ledger:

```text
accepted copies = consumed copies + reset discards + pending copies
```

All queues and producer obligations must drain before the test finishes. The
expected output values come from accepted transactions, independently of DUT
pending or payload storage. Optional raw-storage checks separately verify pending
state and capture-only payload writes. The initial payload is observed only as a
hold baseline; it is never treated as an architectural initialized value.

The monitor samples actual ports before the clock, on the rising edge before NBA
updates, after settling and during a held interval. It checks pre-edge consumption
of the old item even when replacement changes all lanes afterward. Continuous
signal watchers enforce producer stability, each stalled lane's stability,
clockless forward boundaries and authorized raw-storage/output activity. Native
HDL SVA is recorded separately from these executable Python assertions.

## Matrix and coverage

The 68 profiles combine both mask modes and both reset styles with:

- Output counts `1, 2, 3, 4, 5, 8, 16`, each at data widths `1` and `32`.
- Additional `(output count, width)` pairs `(3, 8)`, `(5, 64)` and `(16, 128)`.

Every profile requires 24 coverage goals, including:

- Every nonzero destination mask for enabled-mask configurations with up to five
  outputs, and each mask's feasible simultaneous/staggered completion classes.
- Every selected population, individual destination, first and final consumer,
  and population/final-consumer cross. Larger masks use rotated population-sized
  selections plus singleton and all-output traffic.
- Every pending population crossed with none, some or all pending consumers
  ready, excluding the impossible partial-ready class for population one.
- Simultaneous/staggered completion with and without replacement, all four
  acceptance/completion combinations, and at least 64 consecutive replacements.
- One-cycle and 32-cycle stalls for every output, each output independently held
  for a 32-cycle tail after other copies complete, blocked input offers and a
  32-cycle empty idle interval.
- Reset at every pending population, with real clock edges and clockless pulses;
  clockless empty/occupied and valid/invalid input combinations.
- Zero, one, alternating, walking-one and walking-zero patterns crossed with all
  small masks (or the all-output mask for larger configurations); walking every
  data bit; each accepted and delivered bit on each output as 0, 1, X and Z.
- Ignored invalid data and completed-output X/Z ready, exact copy conservation,
  randomized cycle count and all four observation stages.

Sixteen malformed configurations must fail the named
`stream_fork_parameters_must_be_valid` elaboration guard: zero/negative/unknown
counts and widths, and invalid mask/reset selections. `OUTPUT_WIDTH` is a
non-overridable derived local parameter.

Fifty-four negative protocol probes cover X/Z reset/valid and every ready/mask
bit, unintentional X/Z accepted data, zero valid masks, dropping/changing a
blocked producer's data/valid/mask, and finite blocked-data pulses, with both
reset styles. Each probe must fail exactly the decorated test with its expected
assertion. Compile errors, missing tests, unrelated exceptions or the probe's
fallback failure never count as successful rejection.

## Evidence and qualification scope

The runner checks native JUnit identity, parameters, every coverage goal, seed and
random count. Summary JSON records RTL, dependency and verification source hashes,
UTC timestamps and per-case logs. Filtered runs are marked `selected_profiles`.
Generated artifacts and local qualification helpers stay under ignored
`build/validation/`.

The local Icarus campaign passed all 68 profiles, 136,000 randomized cycles,
16 parameter guards and 54 protocol probes. Across 868,404 observations, the
per-output ledgers account for 283,325 accepted copies, 274,234 consumed copies
and 9,091 reset discards, with none pending. Port-only validation and five Make
integration checks passed. The checker detected all 20 injected RTL defects;
the existing 31 synthesis/power flow tests also passed with their tool stubs.

Verilator lint and Yosys structural checks pass all 68 profiles. The latter
confirm exactly `DATA_WIDTH` unreset payload bits and `NUM_OUTPUTS` pending bits
with the selected reset style, no latches/memories/generated clocks, no
combinational input-data/valid/destination path to output data/valid, and no
destination-mask cone in all-output mode.

Supplemental unbounded binary safety proofs pass all 68 profiles against
independent per-output outstanding-copy state and shared accepted payload.
They start from equal arbitrary initial state and use `async2sync` for an
edge-domain reset model. They do not prove X/Z behavior, between-edge reset
timing, liveness, technology equivalence or release signoff. The proof uses a
generated observer view whose source hash is recorded separately; simulation
and lint use the original RTL.

Native VCS, licensed lint/CDC/RDC/DFT/VC LP, technology synthesis/equivalence,
physical implementation, PrimeTime and PrimePower require their tools, libraries
and integration artifacts. Missing checks are recorded as `NOT_RUN`. Standalone
RTL verification does not establish release qualification or eventual progress
against a permanently stalled consumer.
