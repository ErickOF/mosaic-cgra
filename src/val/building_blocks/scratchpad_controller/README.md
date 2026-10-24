# Scratchpad controller: RTL and PyUVM validation

The implementation follows
[`mosaic-scratchpad-controller`](../../../../../specs/building-blocks/mosaic-scratchpad-controller/README.md).
The public `scratchpad_controller` top exposes the specified packed client and bank
interfaces. Storage remains in external `scratchpad_bank` instances. The Python
regression also composes the controller with real banks, their SRAM wrappers, parity
and ECC in `scratchpad_controller_system_tb.sv`.

## Running validation

From `mosaic-cgra`:

```sh
make scratchpad-controller-regression SIM=icarus
make scratchpad-controller-regression SIM=vcs
make pyuvm SIM=icarus COCOTB_TOPLEVEL=scratchpad_controller
```

`SIM` defaults to VCS. The full regression runs 45 standalone controller profiles,
12 released-bank integration profiles, 56 strict invalid-parameter checks and eight
expected-failure X/Z data probes. Each profile includes 2,000 seeded random cycles
by default. `SCRATCHPAD_CONTROLLER_RANDOM_CYCLES` and `SCRATCHPAD_CONTROLLER_SEED`
configure the full Makefile target; the minimum random campaign is 1,000 cycles.
`SCRATCHPAD_CONTROLLER_JOBS` sets simulation concurrency (Icarus default four,
VCS default one).

To select one profile or use a separate evidence directory:

```sh
.venv/bin/python src/val/building_blocks/scratchpad_controller/run_scratchpad_controller_regression.py \
  --sim icarus --build-dir build/icarus/scratchpad_controller/selected \
  --case b3_c3_d32_n3_m0_s1_w6_r1_e1_a0_t8
```

Parameter overrides in a direct `make pyuvm` invocation must match the corresponding
`SCRATCHPAD_CONTROLLER_<PARAMETER>` environment variables, just as in the regression.
The test checks every public port width and elaborated parameter. Prefer the
regression runner, which supplies both sets of values and isolates each build.

Only Python/PyUVM tests are executed. Simulator compilation elaborates the RTL for
those tests; it is not synthesis or a lint run. Design Compiler synthesis is deferred.
Formal, CDC, RDC, DFT, low-power, physical, timing and power signoff are not claimed.

## Reuse and structure

- `round_robin_arbiter`: one pending-grant request arbiter per bank, and one
  dynamically selected response collector per client. Locking is disabled.
- `dff`: completion validity, pointers, occupancy, enabled metadata/result storage,
  permissions, flush acknowledgements, events and first-error state.
- `counter`: saturating optional traffic, wait, error and byte counters.
- `scratchpad_bank`, `sram_wrapper`, `sram_wrapper_backend`, `parity`, `ecc` and
  their common dependencies: real-bank subsystem validation.
- `mosaic_uvm`: shared agent/environment wiring, coverage reporting, simulator
  execution, strict parameter-guard checks and evidence helpers.
- The released bank's independent Python storage/protection model, including the
  independently qualified Python ECC model: subsystem checking of delayed RMW,
  scrub, flush cancellation and persistent storage.

The completion table cannot be replaced by an ordinary FIFO: younger completions
must write their reserved slots while only the oldest slot may retire. Metadata
and result DFFs have no reset; reset/flush invalidates their authority to appear on
an interface. They capture only on allocation or collection. Unselected crossbar
lanes, read-only write fields and disabled write bytes drive zero.

The suite separates `transaction`, `config`, `sequences`, `driver`, `monitor`,
`agent`, `model`, `scoreboard`, `coverage`, `env` and the decorated PyUVM test.
`peer.py` supplies programmable bank endpoints, independently from the passive
storage oracle. The SystemVerilog fixtures only wire real RTL and optional
counters; safety and fairness checks run in Python.

## Geometry and mapping

The public parameters and defaults match the specification:

| Parameter | Default |
| --- | ---: |
| `DATA_WIDTH` | 128 |
| `NUM_BANKS` | 8 |
| `BANK_DEPTH_WORDS` | 1024 |
| `NUM_CLIENTS` | 4 |
| `CLIENT_TAG_WIDTH` | 8 |
| `MAX_OUTSTANDING_PER_CLIENT` | 8 |
| `INTERLEAVE_BYTES` | 16 |
| `MAP_MODE` | 0 |
| `ENFORCE_PERMISSIONS` | 1 |
| `DEFAULT_ALLOW` | 0 |
| `ASYNC_RESET` | 0 |

`DATA_BYTES = DATA_WIDTH / 8`; each bank has
`BANK_DEPTH_WORDS * DATA_BYTES` bytes. Global capacity is the sum of all banks.
Address, size, client/bank index, slot, occupancy and tag widths are derived local
parameters and cannot be independently overridden. Every flat field uses the
least-significant slice for logical index zero. Permission bit
`client * NUM_BANKS + bank` identifies one client/bank pair.

For global byte address `a`, stripe size `I` and bank count `B`:

```text
stripe, offset = divmod(a, I)
row, raw_bank = divmod(stripe, B)
local_address = row * I + offset
linear bank = raw_bank
XOR bank = raw_bank XOR (row modulo B)
```

XOR requires a power-of-two bank count. Linear mapping also supports non-power-of-two
counts. `I = DATA_BYTES` interleaves words; `I = BANK_CAPACITY_BYTES` allocates one
contiguous region per bank. A stripe must divide bank capacity exactly.

Legal transfers are naturally aligned powers of two fitting one storage word;
write strobes are relative to the right-justified transfer data, not the full
storage word. A zero-strobe write still routes to its bank and receives a completion.

## Ordering, permissions and recovery

Every accepted request reserves its client's issue slot. Bank tags concatenate
`client` in the upper bits and `slot` in the lower bits; the original opaque public
tag stays in the completion table. Repeated public tags are supported. A bank must
use `TAG_WIDTH = BANK_TAG_WIDTH`, identical data/size widths and the controller's
bank capacity. Client slot count and bank outstanding capacity are independent.

The client head becomes response-valid after its result is stored; younger bank
returns never bypass it. A table starting a cycle full inserts an allocation bubble
even if a head retires on that edge. Request and response arbitration pointers move
only on acceptance, with explicit modulo wrap for arbitrary counts. Requests hold
identity and payload through bank backpressure. One collector writes at most one
slot per client per edge; untargetable malformed responses may drain independently.

Permission updates are atomic and accepted only when tables are empty, every bank
is idle, no request grant is pending, flush is inactive and no internal error is
sticky. An accepted permission update takes priority over new requests that cycle.
Enforcement-disabled profiles ignore permission writes and hold permission-ready
and update events low. Unknown permission bits are stored as denial. Reset loads
`DEFAULT_ALLOW`; the baseline therefore requires configuration before legal access.

A known-high `i_flush` starts one all-bank transaction per assertion interval.
Client interfaces stop immediately; the next edge invalidates completion state and
cancels arbiter ownership. Each bank's flush bit stays asserted until that bank's
acknowledgement is sampled. Same-edge launch acknowledgements are supported.
Acknowledged banks deassert independently. Completion pulses once after the last
acknowledgement, with a recovery cycle before new traffic. Holding `i_flush` high
does not restart it. Permissions and lifetime counters survive flush; writes already
committed in banks survive both flush and reset. Reset with traffic must be
coordinated across every bank and client.

A malformed response stops new client requests after its acceptance edge. Existing
completions may drain. A recognizable incomplete slot receives zero data, error 9,
corrected zero and uncorrectable one; an unrecognizable response is discarded.
The first controller diagnosis stays sticky. `i_error_clear` clears it only after
all banks are idle, tables empty, flush inactive and no new malformed response is
being accepted. Flush cancels obligations but retains the diagnosis until clear.

Request, response, denial and conflict events describe the preceding active edge;
consecutive qualified edges can produce consecutive high event cycles. Readiness,
validity and events are clamped during reset. Unknown ready inputs never authorize
an acceptance. Unknown selected write data and successful bank read data are rejected
by verification; unknown disabled bytes and ignored read write-fields are permitted.

## Repository-local error contract

No external `mosaic-contracts` package or dependency manifest is required.
`scratchpad_controller_pkg.sv` owns mapping, memory-error, controller-error and
counter enums. Bank errors translate identically to the memory namespace:

| Code | Memory error |
| ---: | --- |
| 0 | None |
| 1 | Unknown request control |
| 2 | Address out of range |
| 3 | Unsupported transfer size |
| 4 | Misalignment |
| 5 | Storage-word crossing |
| 6 | Strobe beyond transfer size |
| 7 | Parity failure |
| 8 | Uncorrectable SECDED |
| 9 | Internal protocol failure |
| 10 | Permission denial |

Structural classification priority is unknown control, range, size, crossing,
alignment, then strobe; permission follows structural legality. Local errors preserve
known operation/tag, sanitize an unknown operation to read and an unknown tag to
zero, and create no bank traffic.

Sticky controller codes are unknown tag (1), invalid client (2), invalid slot (3),
unallocated slot (4), duplicate response (5), wrong bank (6), wrong operation (7),
invalid or unknown reliability status (8), and request/collector arbiter protocol
failure (9). For simultaneous faults, the lowest accepting bank index wins.

Response validation also requires a defined bank error code, agreement between error
and nonzero code, and error assertion for uncorrectable status. Corrected and
uncorrectable cannot both be asserted. Unknown tags never index completion storage.

## Optional counters

`scratchpad_controller_counters` is independently instantiable/bindable. It accepts
qualified width-wide increments and occupancy snapshots. Counters saturate; peaks
retain the maximum sampled pre-edge occupancy. Disable freezes increments, clear and
peaks. Clear takes priority when enabled. No generated clock is used.

`o_counts` flattens groups in this order; each counter occupies `WIDTH` bits:

| Group | Entries and meaning |
| --- | --- |
| Each client (15) | accepted requests, retired responses, routed read bytes, routed write-strobe bytes, eligible arbitration wait cycles, offered full-table stall cycles, response backpressure, collector contention cycles, denials, local errors 1 through 6 |
| Each bank (10) | accepted reads, accepted writes, read bytes, write-strobe bytes, contention cycles, any eligible unserved client, request not ready, response collector stall, accepted corrected returns, accepted uncorrectable returns |
| Each client/bank pair | accepted permission denials, in client-major order |
| Global (2) | flush starts, cycles with coordinated flush active |

Ordinary traffic counters hold during flush; the two explicit flush counters continue
to describe the operation and duration. These are interface traffic counters;
write bytes count accepted strobes, and do not claim physical commits or energy.
Bank-level instrumentation supplies RMW, scrub and committed-storage observability.

Python tests enable a verification-only 8-bit counter adapter to exercise saturation,
clear, disabled copies and all increments. Set
`SCRATCHPAD_CONTROLLER_INSTRUMENTATION=0` to run the production controller without
that adapter. The macro is omitted from synthesis and gate-simulation sources.

## Verification scope and evidence

The 32 primary standalone profiles cross 2/4/8/16 banks with 1/2/4/8 clients and
linear/XOR mapping. Widths 32/64/128, capacities 1/3/4/8, both resets and word,
intermediate and blocked stripes rotate across those profiles. This is a selected
matrix, not a full Cartesian product of all parameters. Additional profiles include
1/3/5 linear banks, 3 clients, capacities 1/2/3, odd depths, 8/16-bit data, a one-byte
address space, disabled enforcement, default allow, one-bit public tags and the
unmodified default geometry. The 12 integration profiles cross none/parity/SECDED
protection with both reset styles and linear/XOR mapping.

The passive checker compares all public outputs before and after NBA and during
holds. It verifies request and collector round-robin selection, pending grant
ownership, pointer movement, slot allocation/presence/occupancy, payload capture and
hold, all permissions, public tag restoration and exact per-client retirement order.
Synthetic peers provide independent variable latency and stable responses; a
separate byte-memory oracle checks read data and masked write effects. Real-bank
runs instead compare every bank against its released storage/protection reference,
which accounts for delayed commits, RMW, scrub and canceled work. Protected
integration profiles also flip real SRAM data/protection bits to check parity,
SECDED correction and uncorrectable status through every bank/client route.

Directed tests include exhaustive byte mapping for small spaces, every transfer
size/aligned offset, strobe classes, every client/bank operation, every contender
population at every bank, stalled grants, full completion tables, public repeated
tags, reverse and simultaneous cross-bank completions, collector contention,
permissions, structural errors, all bank error-code translations, malformed tags,
slots, banks, operations and reliability status, coordinated flush, reset with
traffic, X/Z controls and legal masked data. Expected-failure probes establish
that selected X/Z write data and successful X/Z read data are detected. Each profile
also mixes all clients and banks, random readiness, latency, conflicts, repeated
tags, reads/writes, permission updates and periodic flush.

Evidence is written beneath `build/<sim>/scratchpad_controller/regression/`:

- Per-profile `results.xml`, `coverage.json`, `parameters.json`, and simulation log.
- `summary.json` with exact parameter profiles, goals, acceptance/retirement/cancel
  accounting, strict guard and expected-failure results, seeds, source/dependency
  hashes and verification/shared-model hashes.
- Explicit `NOT_RUN` status for checks outside this Python-only scope.

A profile passes only when the intended PyUVM test ran exactly once, its mandatory
coverage goals passed, all accepted obligations retired or were canceled by a
modeled flush/reset, and no obligation remains. These artifacts qualify simulation
behavior, not the specification's later physical-release requirements.
