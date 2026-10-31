# Generated Cluster-MVP RTL and PyUVM validation

The implementation follows the [cluster specification](../../../../../specs/mosaic-blocks/mosaic-cluster/README.md)
for the selected **2×2 MVP with three BCTs and one MST**. It instantiates the actual
released `bct`, `mst`, `tile_shell`, `static_mesh`, `banked_scratchpad` and
`configuration_network` RTL. Their normal arithmetic, SRAM backends, context
storage, queues, permission checks and configuration validation remain in the
simulation. Python supplies configuration and external peers; it does not replace
the integrated blocks.

The shared implementation reuses `configuration_network_tile_adapter`,
`tile_shell_state`/`tile_shell_codec`, parity/ECC, `dff`, `counter`,
`performance_counters`, `fifo` and the approved `clock_gate` wrapper. The cluster
event collector now directly reuses `round_robin_arbiter`, a saturating `counter`,
`event_barrier_queue` and `tile_shell_state`, replacing its private rotating cursor,
wrapping sequence register and unprotected export FIFO. Native BCT/MST
bodies also reuse their existing ALU, register-file, stream, event/barrier,
load/store and memory-service components. The cluster accesses published ports;
functional control never depends on a tile-body hierarchy path. The fault tests
use explicitly named status/protected-storage probes solely for fault injection.

## Generate and run

```sh
make setup
make cluster-generate
make pyuvm SIM=icarus COCOTB_TOPLEVEL=cluster
make cluster-regression SIM=icarus
make cluster-regression                       # Requires VCS and a license
```

`src/gen/cluster/mvp.toml` is the architecture source. Edit its explicit IDs,
classes and coordinates, then regenerate. Do not edit the generated
`src/rtl/mosaic_blocks/cluster.sv` directly. The generator emits its architecture
manifest, exact public-port catalog and source file list under
`src/gen/cluster/generated/`. The manifest records descriptor, geometry, endpoint
and client mappings, optional-feature exclusions, dependency/generator hashes and
unperformed signoff work. Its fingerprint is also a top-level status output and
is checked by the package interface.

A custom descriptor can be generated with:

```sh
make cluster-generate CLUSTER_DESCRIPTOR=/path/to/cluster.toml
.venv/bin/python src/gen/cluster/generate.py --descriptor /path/to/cluster.toml \
  --output build/custom/cluster.sv --artifacts build/custom/architecture
```

The current generator accepts complete 2×2 and 4×4 BCT/MST grids with exactly one
MST, four context slots, two native data inputs/outputs per tile, 32-bit data,
64-bit SRAM words and four scratchpad clients. The full execution campaign
qualifies 2×2. The 4×4 case qualifies reset, allocation, command fanout and release;
it does not claim a 4×4 kernel/route campaign. Duplicate IDs/coordinates, missing
positions, unsupported geometries and unavailable tile dependencies fail generation.

Released SFT, CPT, VCT, global-NoC and cluster-power-manager RTL are available
in the repository. Their class-specific context, metadata, predicate, lifecycle
and clock-domain adapters are not part of the previously selected MVP descriptor.
They cannot be substituted for BCT/MST or tied into an unused power interface
without a new generated integration contract. Express links, a dedicated
predicate network, inter-cluster NoC, partitioning, asynchronous clocks, power
gating, retention and DVFS are absent from this MVP. Requests for those descriptor fields or package requirements fail;
there are no placeholder tile bodies. Native predicate outputs remain
backpressured, and packages must leave predicate transport disabled. The MST
retains its actual external DMA *stream* ports; the cluster does not invent an AXI
or external-memory transaction adapter.

## Public interfaces and package loading

The generated `ports.json` records every width. Clock/reset are synchronous
`i_clk` and active-low `i_rstb`; configuration and memory use that same domain.
The lifecycle, event and counter logic remain on the ungated clock. The root
clock gate closes only while free and all control/event obligations have retired.
An incoming runtime request or test/scan request wakes it. This is functional
clock-gate verification, not physical clock-tree or power signoff.

Runtime commands use `cluster_pkg.sv`:

| Code | Command | MVP behavior |
|---:|---|---|
| 0 | QUERY | Read lifecycle state |
| 1 | RESERVE | Allocate the complete tile mask to one owner/kernel |
| 2 | CONFIGURE | Open inactive-image staging and clear the pending manifest |
| 3 | VALIDATE | Require a completed, held commit for the requested package/context |
| 4 | START | Release configuration hold, fan out START, collect every acknowledgement |
| 5 | SUSPEND | Preserve the native queues/state at declared tile safe points |
| 6 | RESUME | Check owner/package/context and resume preserved state |
| 7 | DRAIN | Stop admission and retain accepted work until native drain acknowledgements |
| 8 | ABORT | Explicitly cancel compute at an empty memory/transport/event boundary |
| 9 | RELEASE | Reject busy release; invalidate SRAM permissions and retire control/events |
| 10 | CLEAR_ERROR | Clear only a recoverable error at a quiet boundary |
| 11 | COUNTER_SNAPSHOT | Capture the cluster counter bank for this allocation |
| 12 | POWER_REQUEST | Reject: no power-gating/DVFS implementation is declared |

All terminal responses carry the original command/tag, status, error and resulting
state and remain stable under backpressure. Mutations require the allocated
owner/kernel. MVP resource selection is the entire generated mask; flags are zero.
A timed-out or partially failed lifecycle transition preserves allocation and
enters ERROR_ISOLATED. Fatal recovery requires coordinated reset. A response does
not claim rollback of memory writes or partially applied configuration.

The normal sequence is:

1. RESERVE the full generated tile mask; record allocation generation.
2. CONFIGURE. Program the MST's published protection-region interface, using the
   same owner/kernel, allocation generation and scratchpad region generation.
3. Submit `i_package_*`: architecture fingerprint, native topology ID, local
   contract version 1, owner/kernel/package/context/allocation, full resource and
   endpoint masks, per-endpoint versions/CRCs, next mesh epoch and suspend-safe flag.
   Requirements are zero in this MVP. Bad identity, hash, topology, version or
   feature requirements return a held error response before activation. The
   manifest is immutable after commit acceptance.
4. WRITE each inactive image through `i_cfg_request_*`, then VALIDATE and PREPARE.
   These are the released configuration-network command encodings, **not** the
   native tile-shell configuration encodings. Native image CRC is reflected
   CRC-32C over every padded image byte, low byte first. Native versions increment
   on every successful WRITE. The shared mesh endpoint stages the entire image,
   then programs and validates the actual mesh with that resulting version.
5. Submit the dedicated `i_cfg_commit_*` tuple: the exact full endpoint set, one
   common context, per-endpoint native versions and next mesh epoch. Owner,
   kernel, package, versions, prepared CRCs and accepted manifest must match.
   The wrapper captures the tuple at acceptance, so changing the source pins
   afterward cannot change the in-flight commit.
6. Wait for native acknowledgements from every endpoint. PREPARE never activates.
   During commit, the checked safe point is retained and external offers are
   blocked. Native ACTIVATE itself makes a tile's public quiescent pin false;
   retaining the earlier safe point avoids a ready/valid combinational loop.
7. VALIDATE, initialize the declared readable SRAM contents, then START. A fresh
   commit is required for each launch. Native commands and memory completions
   continue to own their responses until accepted.
8. End the MST manual session with `i_mst_session_end` after admitting all commands.
   Consume command completions and exported events. Kernel completion requires
   every tile's native completion plus empty transport/memory/service obligations.
   RELEASE requires those records to retire too.

Read `o_status_topology_id` for the actual native mesh topology identity. The
configuration epoch (`o_cfg_configuration_epoch`) belongs to transport flush and
is distinct from the mesh execution epoch. The MST has its own published epoch;
construct its native descriptors from `o_mst_execution_epoch`. The explicit stream
bridge relates native MST identities to the current canonical cluster epoch.
There is one resident manifest and one active kernel. Packages rotate inactive
contexts; writing an active context remains illegal. Native finite generation
namespaces retain their own exhaustion/reset rules.

## Shared configuration and memory

Endpoint slot order is coordinate order, independent of logical ID. Default
endpoint IDs are tiles 0–3, mesh 240 and scratchpad policy 241. Word counts are
8/BCT, 16/MST, 9/2×2 mesh and 2/policy. Reordering tiles or IDs changes the emitted
tables. Multicast groups contain compatible BCT endpoints; heterogeneous image
multicast is rejected. Responses retire in architectural endpoint-ID order.

The scratchpad policy image is two low-first 64-bit words. For address width A and
four clients, word zero holds schema 1 (8 bits), base (A bits), exclusive limit
(A+1 bits), read mask (4 bits) and write mask (4 bits); remaining bits are zero.
Word one holds owner (16), kernel (16), next region generation (16), then zero
padding (16). Region zero is the MVP region. Commit invalidates an existing
permission descriptor before reprovisioning it, while execution remains held.
Release invalidates that descriptor before the owner becomes free.

Native scratchpad client classes are respected: client 2 belongs to the MST;
external memory slots map to native clients 0, 1 and 3. The MVP uses the native
TRANSFER state with explicit permission masks and owner/kernel checks. New host
requests are admitted only while reserved/configuring/ready, and are frozen during
commit. Accepted responses remain live. The memory payload persists across
allocation release; permission descriptors are invalidated. This is an explicit
preserve/rebind policy, not SRAM erasure. Software must initialize every byte its
new package can read.

Public `i_memory_req_size` is a **byte count**, matching `banked_scratchpad`.
The MST emits log2 sizes; `cluster_memory_bridge` explicitly converts them.
Addresses outside the scratchpad window and unsupported region indices produce
errors rather than truncating. Data is right justified and strobes are positioned
within the 64-bit word. A one-request directory per MST client retains the full
opaque identity/tag and checks the native response opcode/region/generation/tag.
Committed store bytes are the acknowledged strobe population; a failed atomic
scratchpad write reports zero. No accepted store is cancelled by a transport flush.

MST descriptors use the released `mst` ABI, with memory space 0 and tile-stream
space 2. One ordered store binding is retained per MST input stream. An admitted
store descriptor supplies its explicit identity/format; load-result metadata is
validated before rebinding to that destination command. Another store cannot
replace a live binding. The directory clears only on that command's consumed
completion. Independent loads and native command completions remain real MST work.

## Stream and event metadata

The canonical stream envelope is 512 bits because native shell formats differ.
It is not silently narrowed to the specification's 64-bit seed value:

| Bits | Meaning |
|---|---|
| 0–7 | Canonical context |
| 8–23 | Native mesh context version |
| 24–39 | Kernel |
| 40–43 | Canonical execution epoch |
| 44–47 | Mesh byte keep |
| 48–53 | Mesh first/last/row/eos/error flags |
| 54–55 | Opaque-byte mesh transport class |
| 56–63 | Zero reserved |
| 64–319 | Complete common 256-bit native payload metadata |
| 320–335 | Owner |
| 336–367 | Package |
| 368–375 | Logical producer tile ID |
| 376–511 | Zero reserved |

BCT context/version occupies the low 18 common bits; bit 18 is its false-token bit.
The bridge inserts/removes that bit around MST metadata, whose own reserved upper
bits must be zero. Destination shell context/version is explicitly translated;
inner memory command identity remains available and is checked before binding a
store. BCT-to-BCT metadata retains all other bits, including arbitrary upper-bit
markers. Unknown or mismatched owner/kernel/package/context/epoch and noncanonical
MST padding fail closed. Ready values other than known one do not accept data.

Events retain the full native payload: 32 bits for BCT, explicitly extended with
zero reserved bits, and 256 for MST. The export header captures owner, kernel,
context, package, epoch, logical source, severity and monotonic sequence at queue
admission. Native completion is counted once per tile/epoch. The terminal kernel
event follows native completions; stalled events prevent release. A sticky first
fault records its source, isolates execution and generates one fault event when
the export transport remains healthy.
Protected lifecycle-state failure uses an independent sticky integrity latch so
re-encoding cannot accidentally clear fail-stop state.

## Event admission, protection and recovery

Events use the existing 377-bit export format and the same stable logical source
IDs. Fault, terminal-kernel and scratchpad events take precedence over native tile
events. The released round-robin arbiter holds a selected tile through queue or
critical-source backpressure and advances only when that tile's beat is admitted.
Tile fairness is bounded in accepted tile grants; eventual tile progress assumes
higher-priority sources eventually deassert and the export sink eventually accepts.

The collector captures all owner, kernel, context, package, epoch, source, severity
and native payload fields at admission. Changing later allocation inputs cannot
change an already queued or stalled record. The protected queue checks occupancy,
read/write pointers and occupied payloads. Completion and duplicate state use
released protected storage as well. Unknown valid/control fields, unknown selected
payloads and withdrawal of a held tile request fail closed.

The common 32-bit counter saturates. Sequence `0xffffffff` can be accepted and
exported once; subsequent ingress is disabled. It never silently wraps into an
old namespace. Completion clear and a coincident new completion are atomic;
clearing completion bits does not clear the sticky duplicate diagnostic or reset
the event sequence.

An ingress protocol fault or exhausted namespace stops admission while intact
accepted records can still retire. A corrupt export queue invalidates that
transport until coordinated reset; it cannot export untrusted data or acknowledge
more ingress. Its sticky failure keeps `o_empty` low even if occupancy becomes
zero, so it cannot authorize release or idle clock shutdown. The cluster reports
integrity error 17 from event source 245, retains the allocation, asserts boundary
isolation and keeps the interrupt pending. If the event transport itself failed,
software must use the independent sticky status/interrupt and coordinated reset;
no additional record can be promised through the failed transport.

`make pyuvm SIM=icarus COCOTB_TOPLEVEL=cluster_events` runs a focused PyUVM suite
against the production collector ports. It reuses the cluster driver, passive
monitor, transaction type and common agent/environment construction. A separate
Python ledger predicts arbitration, complete immutable records, exact admission
and retirement, FIFO capacity, simultaneous pop/push and completion accounting.
The normal source agents retain every offered payload until its handshake. Named
parity/counter probes are used only for corruption and namespace-exhaustion tests.
Intentional producer protocol faults and coordinated reset are explicit cases.

## Counters and validation evidence

The coherent 48-bit saturating bank counts allocation cycles, running cycles,
accepted runtime requests, boundary input-offer cycles, boundary output-offer
cycles, accepted MST completions, successful commits and fault cycles, in indices
0–7. Snapshot requests and reads require the current owner. A new allocation
cannot read the previous owner's snapshot.

`cluster-regression` generates each profile separately and runs a conventional
PyUVM agent/driver/monitor/environment/scoreboard/sequence/coverage structure.
Common UVM construction and the synchronous driver are reused. Independent Python
code creates context images and route certificates, predicts integer arithmetic
and checks memory readback, rather than echoing DUT results.

The campaign covers:

- Full 2×2 MVP, changed placement/IDs, clock gating disabled and smaller SRAM
- Real load → three arithmetic tiles → store → completion → release
- Held configuration/runtime/package/memory/completion/event/boundary interfaces
- Configuration multicast, image CRC, package binding and manifest compatibility
- Native safe-point suspend/resume, owner rejection and orderly drain
- Exact native command IDs, committed-byte counts and one terminal kernel event
- Full metadata conservation and explicit epoch/version adaptation
- Native fault containment, protected controller failure and partial commit failure
- Four-by-four allocation/fanout/release smoke and Python-driven elaboration guards
- Native event-collector integrity faults propagated into cluster containment
- Seven focused event profiles: one, four, sixteen and 64 sources, permuted IDs,
  one-entry/full queues and optional parity
- Event priority, held arbitration, every payload/identity bit, full-queue pop/push,
  unknown inputs, withdrawn producers, sequence exhaustion and real parity injection

```sh
.venv/bin/python src/val/mosaic_blocks/cluster/run_cluster_regression.py \
  --sim icarus --build-dir build/icarus/cluster/selected --case mvp
```

`CLUSTER_REGRESSION_ARGS` forwards runner options, such as `--case mvp`, through
the Makefile. The focused event subcampaign runs for every selected cluster run.
`ICARUS_BIN_DIR`/`VCS_BIN_DIR` select the simulator installation.

`CLUSTER_JOBS` selects concurrent independent profiles; default is 2 for Icarus
and 1 for VCS. `CLUSTER_RANDOM_CYCLES` defaults to 1000 and the minimum is 1000.
Evidence includes the actual descriptor/manifest, generated RTL, simulator log,
JUnit XML, checked functional goals, seed and hashes of production/generator/UVM
sources. A suite passes only when the expected decorated test ran once, every
mandatory goal passed and sources remained stable.

Only Python tests/PyUVM and Python-driven simulator compilation are run. HDL
assertion suites, lint, CDC/RDC, formal, synthesis, timing, UPF, DFT, physical design
and power/energy characterization are not run or claimed. Synthesis is deferred
to Design Compiler. Unsupported profiles and application/physical qualification
remain outside this MVP evidence.

## Recorded Python-only evidence

The updated Icarus campaign passes six cluster cases (four complete 2×2 workloads,
4×4 control smoke and partial-commit containment), seven focused event profiles,
26 strict elaboration guards and 21 Python model tests. The cluster cases check
39,312 cycles; the event profiles check 8,662 cycles with 1,000 seeded traffic
iterations each. Their ledger conserves all 4,230 accepted records: 4,110 retire
and 120 are explicitly invalidated by the directed coordinated-reset/fault cases.
No accepted record is silently lost during normal backpressure or arbitration.
The 64-source case instantiates the collector alone and does not qualify an 8×8
cluster.

The campaign uses seed 20261026 with deterministic per-case offsets. Production
and verification hashes remain unchanged throughout the passing run. Generated
production RTL and dependency hashes match the checked-in architecture manifest.
Both direct Makefile entry points (`cluster` and `cluster_events`) also pass.
Reproducible results, JUnit, coverage, profile manifests and logs are under
`build/icarus/cluster/regression/`, with the aggregate result in `summary.json`.
VCS and physical signoff require the licensed server and were not run locally.
