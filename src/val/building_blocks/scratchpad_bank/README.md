# Scratchpad bank RTL and PyUVM validation

[`scratchpad_bank.sv`](../../../rtl/building_blocks/scratchpad_bank.sv) implements
the [scratchpad-bank specification](../../../../../specs/building-blocks/mosaic-scratchpad-bank/README.md).
It translates byte-addressed requests into one replaceable word-addressed SRAM
backend and returns one ordered response for each accepted read, write, no-op or
illegal request. None, granular even parity and word SECDED are supported.

## Run

```sh
make setup
make pyuvm SIM=icarus COCOTB_TOPLEVEL=scratchpad_bank
make scratchpad-bank-regression SIM=icarus
make scratchpad-bank-regression                 # Requires VCS and its license
```

The decorated test is `test_scratchpad_bank.ScratchpadBankTest`. Test, environment,
agent, transaction, sequence, driver, monitor, model, scoreboard and coverage are
separate files. Existing `mosaic_uvm` helpers supply wiring, simulator execution,
JUnit validation and evidence handling. The independent ECC reference model and
its geometry are reused from the basic ECC suite. Shared RTL and shared Python
helpers are unchanged.

The full campaign has **184 profiles**, **47 strict invalid-parameter checks** and
**28 expected-failure data probes**:

- The full cross of 32/64/128-bit words, depths 256/1024, completion capacities
  1/3/4/8, all three protection modes and both reset styles: 144 profiles.
- Sixteen larger-granule parity profiles using 16-bit, 32-bit and full-word
  granules, odd depth five, latency two and both resets.
- Six SECDED profiles with scrub disabled, odd depth three and latency two.
- Eighteen edge profiles with 8/16/256-bit words, depths 1/3/5, latencies 1/2/3,
  corresponding capacities 1/2/3, all protection modes and both resets.
- Invalid geometry/options, insufficient read credits, elaboration overflow and
  the inherited 256-bit maximum SECDED data width are rejected at elaboration.
- Twenty-four selected-write probes inject X/Z at data bit zero and bit 127,
  across protection modes and resets. Four probes check X/Z in initialized
  unprotected read data, across resets. A specific checker diagnostic and failed
  decorated JUnit test are required; compiler errors do not count as rejection.

Every profile runs initialization, directed cases and 2000 seeded random clock
opportunities. `SCRATCHPAD_BANK_SEED` defaults to 20261023 and advances by global
profile index. `SCRATCHPAD_BANK_RANDOM_CYCLES` must be at least 1000.
`SCRATCHPAD_BANK_REGRESSION_BUILD` selects the evidence directory.
`SCRATCHPAD_BANK_JOBS` selects 1–32 simulator processes, defaulting to four for
Icarus and one for VCS. Select profiles with:

```sh
.venv/bin/python src/val/building_blocks/scratchpad_bank/run_scratchpad_bank_regression.py \
  --sim icarus --build-dir build/scratchpad-selected \
  --case d32_w5_n3_p1_l2_g16_s1_r1
```

Direct custom runs require matching compiler parameters and
`SCRATCHPAD_BANK_<PARAMETER>` environment values. Icarus accepts
`-Pscratchpad_bank.PARAMETER=value`; VCS accepts
`-pvalue+scratchpad_bank.PARAMETER=value`. Use a fresh build directory after
changing geometry. The runner supplies matching flags, environment and rebuild
dependencies automatically.

Private storage checks and optional-counter instrumentation default to enabled.
For a backend with different private hierarchy, set
`SCRATCHPAD_BANK_CHECK_INTERNALS=0`; this omits raw-storage fault campaigns and
private assertions. `SCRATCHPAD_BANK_INSTRUMENTATION=0` omits the simulation-only
counter fixture. Omitted checks are recorded separately and are not full
qualification. The full runner enables both. Tests require zero-delay RTL
(`TEST_SETTLE_NS=0`) and 1 ps or finer simulator precision.

## Reuse and backend layout

The existing `sram_wrapper` owns the fixed-latency read pipeline, read credits and
tagged returns. Its existing `sram_wrapper_backend` supplies unreset 1RW storage.
The bank reuses `parity`, `ecc`, common DFFs, counters, decoders, write gates and
operand isolation. The optional lifetime-counter helper also uses common counters
and a DFF for maximum occupancy.

The bank's completion ring is separate from the wrapper's read-return buffer:
writes and illegal requests also need ordered responses. Internal slot indices
are backend tags; public tags are opaque captured metadata and may repeat. Slot
ownership lasts until public response consumption. Pointers wrap explicitly for
non-power-of-two capacities. A cycle that begins full blocks allocation even if
the head response is consumed on that edge.

Allocation, completion-presence and awaiting-read flags reset. Metadata, response
payloads and work payloads are unreset, independently enabled banks. Only a valid
allocated completion may expose them. Private assertions check each actual DFF
capture and unqualified hold, as well as allocation, presence and outstanding-read
ownership against the independent model.

Stored layouts are:

| Mode | Stored bits and native mask |
| --- | --- |
| None | `DATA_WIDTH` data bits; one mask bit per byte |
| Parity | Data low, one even parity bit per granule high; bit masks |
| SECDED | Existing ECC extended-Hamming codeword; bit masks, full-codeword writes |

For direct simulation and the existing synthesis flow,
`SRAM_BACKEND_SOURCE=/absolute/path/to/adapter.sv` replaces the inferred backend.
The adapter must define the same `sram_wrapper_backend` parameters and pins and
preserve stored width, bit ordering, masks, depth, latency and acceptance-edge read
snapshot semantics. Select exactly one backend definition. The regression selects
the inferred backend explicitly; it does not qualify vendor models or macros.
Production builds must supply approved SRAM/mask views and must fail on missing
required views. The inferred simulation array is not evidence of ASIC SRAM mapping.

## Subwords, writes and protection

The address is local to one bank. Word selection divides by the compile-time
power-of-two byte count; the low bits select the byte offset. Requests must be
naturally aligned and contained in a word. Read results are right-justified and
zero above the requested size. Write data and strobes are shifted by the same
offset. Disabled source bytes are clamped before encoding or storage access.

All-zero write strobes are legal no-ops: they return one successful write
response and perform no backend access. Ordinary writes commit on acceptance and
become response-present after that edge. Masked writes preserve every untouched
byte. Backend reads snapshot before later writes, preserving read-before-write
and write-before-read ordering without depending on macro collision behavior.

Parity writes that completely replace every touched granule regenerate only those
granules. A partially overwritten granule requires atomic RMW. The old parity of
each partially overwritten granule is checked; untouched and fully replaced
granules need not be trusted. The merged write commits complete touched granules
and their parity together. A parity failure aborts RMW without a storage write.
Reads check every granule intersecting their transfer. A failed or unknown check
returns zero data, parity error and uncorrectable status. Unrelated bad granules
do not poison a read of independently valid granules. Even-bit errors in a parity
granule are not guaranteed to be detected.

SECDED full-word/full-strobe writes encode directly. Every other nonzero write
performs read, decode/correct, merge and full-codeword commit while excluding all
other public requests. An uncorrectable or unknown old codeword aborts without
modification. Successful recovery from a single-bit old error reports corrected
on the write response. The reused ECC helper supports data widths through 256
bits; that limit applies only to SECDED profiles.

SECDED reads reserve the backend from acceptance through decode and any inline
scrub. This conservative policy prevents a younger write from being overwritten
by a stale scrub. Correctable reads return repaired data and corrected status;
with scrub enabled, response presence waits for corrected-codeword commit. Scrub
disabled leaves storage unchanged. Uncorrectable or unknown decode status returns
zero data and error, with no scrub. The fault guarantee is the ECC helper's
single-bit correction and double-bit detection, not universal multi-bit recovery.

## Timing and ordering

An accepted wrapper read at edge `t` matures after `t + BACKEND_READ_LATENCY`.
The bank captures that return on the following edge. Thus an ordinary read becomes
response-present after `t + BACKEND_READ_LATENCY + 1`; earliest public consumption
is the next edge. A protected RMW or correcting read with scrub commits one further
edge later and becomes response-present on commit. Client backpressure may extend
response latency without releasing its slot or changing its payload.

Unprotected traffic and direct writes can issue one request per cycle when credits,
completion space and response readiness permit. SECDED reads and protected RMW
serialize backend ownership as described above. Minimum completion credits equal
to backend latency are legal but introduce admission bubbles. No throughput or
physical timing claim is inferred from these functional simulations.

Illegal requests reserve one slot, issue no backend operation and return one
ordered error response. They do not require backend readiness, but still wait
behind an active protected reservation. Per-request errors are nonfatal. Sticky
internal errors stop new requests while expected responses and accepted work drain
where possible. Clear is accepted only when otherwise quiescent. A damaged backend
that can no longer return an owned read requires coordinated reset rather than an
invented completion.

## Reset, flush and initialization

Neither reset nor flush initializes data or protection bits. Before protected
reads, software or initialization logic must establish matching data and code.
Unprotected unwritten bytes may return X/Z according to their uninitialized bit
state; verification tracks initialized bits and rejects unknown initialized read
data. Protected unknown data/check status fails closed. Enabled unknown write
bytes fail verification; disabled bytes may be unknown.

Flush clamps public handshakes, invalidates completion and wrapper protocol state,
resets pointers, and cancels uncommitted RMW/scrub work on its edge. Committed
writes remain. Completion pulses once per asserted flush interval, after the
protocol state is canceled; held flush does not repeat it. New requests resume
after completion and release of flush. Sticky internal error survives flush.

Reset clears all protocol state and sticky errors using the selected reset style.
Asynchronous assertion is supported; deassertion must be synchronized externally.
Both endpoints must discard old tags and coordinate recovery. Unreset physical
read data from canceled requests cannot create new public responses.

Unknown ready or valid values cannot cause transfers. Unknown request controls
produce ordered error responses; an unknown public tag is replaced by zero and an
unknown operation is represented as read in that error response. Read write-data
and strobe fields are ignored. Unknown reset/flush suppress public handshakes and
bank work; the wrapper can queue already-admitted physical returns until control
becomes known, avoiding dropped read obligations.

## Local error and counter inventory

[`scratchpad_bank_pkg.sv`](../../../rtl/building_blocks/scratchpad_bank_pkg.sv)
defines local enums. Protection modes are none 0, parity 1 and SECDED 2; mode 3 is
reserved. No external contracts package or dependency manifest is introduced.

| Error | Code |
| --- | ---: |
| None | 0 |
| Unknown relevant request control | 1 |
| Address outside capacity | 2 |
| Unsupported size | 3 |
| Natural alignment | 4 |
| Word crossing | 5 |
| Strobe outside transfer | 6 |
| Parity | 7 |
| Uncorrectable SECDED | 8 |
| Internal protocol | 9 |

Request classification priority is unknown, range, size, crossing, alignment, then
strobe. Crossing takes priority over alignment so it is explicitly observable.
Known illegal encodings that cannot exist for a geometry are excluded with their
parameter conditions: for example, exact power-of-two capacities have no spare
address, one-byte words have no crossing/alignment/strobe overflow, and two-byte
words have no misalignment that is not also crossing.

[`scratchpad_bank_counters.sv`](../../../rtl/building_blocks/scratchpad_bank_counters.sv)
is optional bindable instrumentation. Connect `g_bank.performance_events`,
`g_bank.read_bytes`, `g_bank.write_bytes` and current occupancy. Default width is
48; choose a width that represents the maximum byte increment and occupancy.
All counts saturate, enable suppresses both clear and event updates, and reset
still clears them. Count `n` occupies `o_counts[n*WIDTH+:WIDTH]`:

| Index | Count |
| --- | --- |
| 0–1 | Accepted legal reads and writes, including zero-strobe writes |
| 2–3 | Read bytes and enabled write bytes |
| 4–5 | Consumed read and write responses, including error responses |
| 6–7 | Request stalls and response backpressure |
| 8 | Full completion cycles |
| 9 | Nonzero partial writes |
| 10–11 | Protected RMW operations and offered-request reservation stalls |
| 12–13 | Corrected decodes and scrub commits |
| 14–15 | Parity and uncorrectable SECDED decodes |
| 16–21 | Illegal requests in code order 1 through 6 |
| 22 | Completed flush intervals |

Maximum occupancy is a separate register. Instrumentation does not change bank
ports or baseline state. The simulation-only fixture instantiates eight-bit
enabled and disabled copies; the Python model checks all counters, weighted
saturation, maximum occupancy and disabled clear/event holds.

## Verification evidence and scope

The reference keeps raw words and initialized-bit masks, independently encodes
parity/ECC, snapshots reads at acceptance, and uses a timestamped return calendar.
A deque owns public obligations independently of DUT slots. Storage changes only
on predicted ordinary, RMW or scrub commits. The scoreboard checks every public
field at pre-NBA, settled and held observations, plus the conservation equation
`accepted = emitted + canceled + outstanding`.

Directed coverage includes all addresses, sizes and aligned offsets; sparse and
zero strobes; same-address hazards; full rings, wrap and simultaneous allocation/
retirement; each stored data/protection bit flipped individually; representative
SECDED double errors; parity even-error limitations; old-word correction and RMW
abort; unrelated parity granules; scrub races; flush during read wait and before
RMW commit; reset persistence; unknown controls and internal malformed/duplicate
returns. Random traffic mixes byte masks, reads, writes, protection faults,
backpressure, wrap and flush. Fair progress is an environment assumption.

Private assertions compare actual backend enable, operation, address, data and
mask with independently predicted operations; check raw storage after commits;
verify slot DFF captures/holds, pointers and awaiting flags; and compare the entire
memory at quiescent test completion. Functional coverage records the specified
operation/size/offset, hazard/latency, occupancy/transfer, error/operation,
protection/status, RMW old-error and flush/work crosses. Parameter-unreachable
goals are identified in the coverage collector.

The runner checks the exact decorated JUnit identity, geometry, seed, random count,
all mandatory goals and final accounting. Evidence contains per-profile coverage,
logs and hashes of RTL, dependencies, verification files, reused ECC reference,
shared helpers and Makefile.

Only Python/PyUVM simulation is run for this change. Lint, formal, CDC/RDC/DFT/MBIST,
low-power analysis, technology synthesis, vendor-macro qualification and physical
timing/power are `NOT_RUN`. Synthesis is deferred to **Design Compiler** when the
required SRAM adapters, views and technology setup are available. These functional
results do not claim physical or complete release qualification.
