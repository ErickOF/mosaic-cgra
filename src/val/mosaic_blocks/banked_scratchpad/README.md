# Banked scratchpad RTL and PyUVM validation

[`banked_scratchpad.sv`](../../../rtl/mosaic_blocks/banked_scratchpad.sv) implements
[the banked-scratchpad specification](../../../../../specs/mosaic-blocks/mosaic-banked-scratchpad/README.md).
It instantiates the production `scratchpad_controller`, one `scratchpad_bank` per
bank, and their actual `sram_wrapper` backends. Arbitration, SRAM timing, masked
writes, parity/SECDED, protected read-modify-write, scrub and coordinated flush
reuse those modules. Critical wrapper records reuse `tile_shell_codec`, `ecc`,
`parity` and `dff`; lifetime statistics reuse the common saturating `counter`.
No dependency manifest or external contracts package is required.

```sh
make setup
make banked-scratchpad-regression                  # VCS installation and license required
make banked-scratchpad-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=banked_scratchpad
```

The regression uses only Python/PyUVM tests, including Python-driven compilation
and strict invalid-parameter elaboration checks. There are no standalone HDL
assertion tests, lint, formal checks or synthesis runs. Design Compiler synthesis
and physical power/UPF/DFT signoff remain later integration work. Local results use
Icarus; a VCS command is provided but does not imply local VCS execution.

`BANKED_SCRATCHPAD_RANDOM_CYCLES` defaults to 2000 (minimum 1000), and
`BANKED_SCRATCHPAD_SEED` defaults to 20261026. `BANKED_SCRATCHPAD_REGRESSION_BUILD`
selects the evidence directory. `BANKED_SCRATCHPAD_JOBS` selects concurrent profiles.
For individual profiles:

```sh
.venv/bin/python src/val/mosaic_blocks/banked_scratchpad/run_banked_scratchpad_regression.py \
  --sim icarus --build-dir build/icarus/banked_scratchpad/selected --case default
```

Direct custom simulation must pair compiler parameter overrides with matching
`BANKED_SCRATCHPAD_<PARAMETER>` environment values. The runner supplies both and
checks elaborated values and every public port width. Default total capacity is
64 KiB. The released dependencies additionally require a power-of-two byte count
per data word. Linear mapping permits non-power-of-two bank counts and depths;
XOR mapping requires a power-of-two bank count. All invalid configurations reach
a named elaboration guard before unsafe arrays or arithmetic are instantiated.

## Public ABI

`banked_scratchpad_pkg.sv` publishes repository-local enum encodings. Request,
region, buffer-role, power-state and command values match the specification.
Memory errors 0–10 preserve the controller/bank namespace; 11–16 add unsupported
opcode, region mismatch, stale generation, owner/kernel mismatch, invalid contents,
and sleeping-bank errors. Management and internal-error enums have separate
namespaces. This implementation does not claim compatibility with an unavailable
external `mosaic-contracts` artifact.

Packed clients/banks use low slices first, `index * WIDTH +: WIDTH`. Public sizes
are **bytes**, with width `clog2(DATA_BYTES + 1)`. Write data is right-justified;
strobes exactly cover the transfer's address-positioned byte lanes. For example,
a two-byte write at address 2 in a 64-bit word uses strobe `0x0c`. The wrapper
converts size and strobe to the reused controller's log2/right-justified interface.
There are no sparse writes within a declared transfer: select smaller transfer
sizes to update fewer bytes. Reads return only the requested, right-justified bytes.

Baseline logical client classes are fixed: client 0 is host, client 1 is DMA, and
clients 2 and higher are CGRA/MST. TRANSFER uses descriptor masks to designate
producers. SHARED_READ_ONLY uses the read mask without owner/kernel matching and
never permits writes. Other readable/writable states require matching identity,
class and masks. Precise region enforcement can be disabled; in that profile all
coarse permissions are initialized and installed as allow, independently of region
metadata. With enforcement enabled, reset and default-deny block all unprovisioned
addresses; coarse permissions are derived from valid descriptors.

The parameter-dependent descriptor is packed **MSB to LSB** in this field order:

| Field | Width |
| --- | --- |
| valid | 1 |
| base, limit | GLOBAL_ADDR_WIDTH, GLOBAL_ADDR_WIDTH + 1 |
| owner, kernel | OWNER_ID_WIDTH, KERNEL_ID_WIDTH |
| state, contents | 3, 1 |
| read_mask, write_mask | NUM_CLIENTS each |
| generation | REGION_GENERATION_WIDTH |
| group_id, role | BUFFER_GROUP_WIDTH, 2 |
| corrected, uncorrectable | 1 each |

`config.descriptor_fields` and `model.encode_descriptor` provide executable codecs.
The local descriptor width `DW` is the sum of these fields. Region occupancy width
is `clog2(NUM_CLIENTS * MAX_OUTSTANDING_PER_CLIENT + 1)`; client occupancy width is
`clog2(MAX_OUTSTANDING_PER_CLIENT + 1)`. Bank capacity is
`max(MAX_OUTSTANDING_PER_CLIENT, BACKEND_READ_LATENCY)` and its occupancy width is
`clog2(bank capacity + 1)`.

## Ordering and management

Every accepted request reserves a public slot, including local errors and fences.
The controller tag contains client, public slot and a 32-bit slot epoch. A slot
cannot be reused until retirement; its epoch survives flush and increments on
reuse. Epoch exhaustion is a sticky internal error requiring reset. Controller
bank tags retain the released controller's own client/slot encoding; coordinated
bank flush contains stale work before those tags can be reused.

Each client dispatches requests in order and retires responses in acceptance order.
Independent banks can accept different clients concurrently. A fence waits for all
preceding results and committed writes without waiting for unrelated clients; later
admission on that client remains blocked until the fence response is consumed.
Response backpressure preserves all public payload fields.

Only one management command executes at a time. Mutations block **all** new client
admission and wait for public responses, controller work and bank maintenance to
drain. This stronger global barrier permits atomic replacement of the reused
controller's complete permission matrix. READ does not wait for data quiescence.
Admission resumes after the command response is consumed. Transitions preserve
range, buffer group/role and sticky fault summaries while changing the access tuple.
A swap exchanges access tuples and roles atomically; ranges, groups, physical bytes
and per-range fault summaries stay in place.

Generation wrap rejects a transition or swap without changing descriptors.
INVALIDATE then PROVISION explicitly restarts an exhausted generation namespace at
one. Runtime software must discard old schedules before using that restart.
A command response is accompanied by one architectural event for mutations or
errors. There is **one lossless event holding slot**; an unconsumed event blocks
new management commands. Events carry the selected regions and generation values
at command evaluation. Responses and events remain stable under backpressure.

Flush cancels requests, completion slots and uncommitted management commands,
without resetting SRAM, committed descriptors or events. An already committed
permission update completes installation after flush. Integrators must discard
pre-flush public tags. Reset invalidates descriptors and protocol state; SRAM data
and protection bits remain unreset. Software must initialize every readable word
before publishing a region's contents. A partial write never publishes region-wide
validity. SECDED partial writes use bank RMW; parity writes use RMW when a parity
granule is partially replaced. Fully replaced parity granules need no old data.

## Power and control protection

With power support disabled, banks report ACTIVE, power and clock enables remain
high, isolation stays low, and commands are not accepted. Enabled power commands
use a conservative global quiescent point. Clock-gating preserves contents;
retention additionally waits for save/restore acknowledgements. Off is refused
while any valid descriptor can touch the bank, using exact mapping even across an
XOR row boundary. Wakeup waits for physical acknowledgement and restoration before
removing isolation and enabling requests. Destructive off clears bank content
validity; ordinary writes followed by explicit management publication restore it.

Power signals are logical hooks, with one acknowledgement per sequencing phase.
A technology adapter supplies actual switches, retained SRAM, isolation, clock
cells and DFT behavior. RTL does not create clocks or emulate analog power loss.
Reset returns logical bank control to ACTIVE; physical integration must establish
a safe powered state before releasing reset.

`CONTROL_PROTECTION` protects descriptors, queued metadata/results, occupancy,
pointers, fence/slot generations, management/events, sticky error and power state.
Detected bad records are held and admission stops; corrected records are rewritten
through the shared codec. Error clear requires quiescence and removal of the cause.
Protocol flush can cancel outstanding slots before clearing a recoverable fault.

## Observability

`g_scratchpad.statistics` contains synthesizable, saturating 32-bit lifetime counters;
`outstanding_peaks` contains client, bank, then region high-water marks. These are
integration/debug buses, not a new software CSR protocol. Reset is the sole clear;
flush preserves counts. A runtime adapter supplies privileged transport or atomic
snapshots if required.

Counter groups appear in ascending client order (18 each), bank order (16 each),
region order (6 each), then ten global counters:

- Client: accepted reads/writes, requested read/write bytes, committed write bytes,
  permission/region/owner denials, generation denials, arbitration wait, full-table
  stalls, response stalls, three read latency bins, three write latency bins,
  fences, fence cycles. Latency bins are fewer than 8, fewer than 32, and 32 or
  more clocks from acceptance to public consumption; the age saturates at 65535.
- Bank: reads/writes, requested bytes, committed write bytes, conflicts, corrected
  and uncorrectable events, active/idle/clock-gated/retention/off cycles, wakeups,
  waking cycles, request stalls, response stalls.
- Region: reads/writes, requested bytes, committed write bytes, corrected and
  uncorrectable completions. Accepted region-matched errors count as attempts.
- Global: drain cycles, flush cycles, flush completions, transition/swap cycles,
  accepted commands, consumed events, total released clocks, useful-access cycles,
  admission-stall cycles.

## Verification and evidence

The PyUVM agent has separate sequence, driver, passive monitor, scoreboard and
coverage components using `mosaic_uvm`. Its independent model maintains byte memory,
region descriptors, ownership, permissions, generations, physical mapping,
protection faults and power state. Actual bank arbitration defines cross-client
memory order. Local-error requests must produce no bank access, while every normal
bank access must match a live accepted public obligation. Scoreboards check every
response, event, descriptor result, selected lifetime counter and outstanding peak.

Directed and seeded random traffic cover legal sizes and positions, region and bank
edges, conflicts/parallel grants, ownership denials, stale generations, command
comparison, swap/refusal, fences, full occupancy, response/event stalls, ECC/parity
faults and partial writes, control faults, four-state legality, drain, flush/reset
storage survival and power transitions. Profiles cover the default, all required
bank/width points, 16–512 KiB capacity points, both mappings, outstanding counts
1/4/8/16, protected and unprotected controls/storage, optional features, asynchronous
reset and odd geometries. Invalid arguments must fail through the named guard.

Each profile produces `simulation.log`, `results.xml`, `parameters.json` and
`coverage.json`. `summary.json` records model-test results, exact decorated PyUVM
execution, mandatory coverage, parameters, seeds and source/dependency/test hashes.
The campaign fails if a test is skipped, coverage is missing, a profile fails or
sources change during execution. Synthesis and HDL assertions remain NOT_RUN.
