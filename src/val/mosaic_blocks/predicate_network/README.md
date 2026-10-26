# Predicate network RTL and PyUVM validation

The production top is `src/rtl/mosaic_blocks/predicate_network.sv`, implementing
[the predicate-network specification](../../../../../specs/mosaic-blocks/mosaic-predicate-network/README.md).
All interfaces use `i_clk`. Cross-clock attachments need an external asynchronous adapter.

Run from `mosaic-cgra`:

```sh
make predicate-network-regression SIM=icarus
make predicate-network-regression SIM=vcs
# One baseline simulation with the production RTL closure:
make pyuvm SIM=icarus COCOTB_TOPLEVEL=predicate_network
# Selected cases:
.venv/bin/python src/val/mosaic_blocks/predicate_network/run_predicate_network_regression.py \
  --sim icarus --build-dir build/icarus/predicate_network/selected \
  --case small --case boundary --case control_ecc
```

`PREDICATE_NETWORK_SEED` and `PREDICATE_NETWORK_RANDOM_CYCLES` configure the Make target.
The latter sets the number of randomized beats on a long route, with source gaps and
independent destination stalls. `PREDICATE_NETWORK_JOBS` controls parallel simulator
processes: four by default for Icarus, one for VCS. The Python campaign invokes only the
specified PyUVM test, rejects skipped/stale results, and checks all required functional goals.
VCS needs an installed executable and license; Icarus does not require either.

Reports under `build/<sim>/predicate_network/regression` include `summary.json`, per-case
`parameters.json`, `coverage.json`, `results.xml`, `simulation.log`, and `contract.json`.
Source hashes cover production RTL dependencies, this Python suite, reused static-mesh
Python helpers, shared UVM helpers, and the Makefile. Changes during a campaign make its
summary fail. Packed route, slot, enable and proof fields in contracts use hexadecimal
strings so the 8x8 schedule image is portable across Python integer serialization limits.
These files are generated evidence, not checked-in dependency manifests.

## RTL composition

Each present node instantiates `static_mesh_node`, which wraps the existing registered
`local_switch` and its independent pending-branch witness. Only physically connected
output rows are instantiated. Unicast and multicast keep each accepted predicate until
every selected branch consumes its copy. Consumed branches cannot repeat a delivery.

Internal links reuse `static_mesh_link` and `skid_buffer`. Forward bypass adds no unstalled
cycle; registered ready limits a reverse combinational path to one node. Exposed perimeter
inputs and outputs each use a one-entry `static_mesh_queue`, composed from
`event_barrier_queue` and common `fifo`. Each queued perimeter direction adds one cycle.
Unstalled local acceptance to destination-valid latency is H+1 node stages for H internal
hops, with an extra stage for each traversed perimeter queue. Consumption occurs on the
following eligible edge. The contract records startup depths for every used input.

The link helper has an additional observation output for the actual quarantined packet.
It supplies first-error producer/tag attribution without releasing or acknowledging that
packet. Existing static-mesh instantiations can leave this output unconnected.

Control state, candidate, shadow, active routes, dependency work records and validity
witnesses reuse `banked_scratchpad_state`, the striped `tile_shell_codec`, parity and ECC.
Counter storage reuses `banked_scratchpad_counters` and common counters. Protection 1 detects
odd control bit errors; protection 2 corrects single errors and contains detected doubles.
Internal link parity covers predicate value, lane validity and the entire metadata word.
Uncorrectable control integrity errors require reset. Link parity faults require flush
before the affected held beat can be discarded.

`predicate_network_control` owns prepare/commit, fault masks, epoch, schedule phase, output
quarantine and first-error state. `predicate_network_schedule` derives input capture slots
from directed-link bitmaps and checks consistency through nodes and perimeter queues.
Width-dependent structs stay in their parameterized modules; phase, class and error enums
are in `predicate_network_pkg`.

## Repository-local v1 contract

This workspace has no `mosaic-contracts` package. Following the repository convention,
`predicate_network_pkg.sv`, `defaults.py` and `topology.py` define local encodings.
Integration with a separately versioned system contract requires an explicit translation.

Nodes are row-major. Inputs are local TX lanes, north, south, east and west; outputs are
local RX lanes followed by the same directions. Channels increase within each direction.
Internal directed links enumerate horizontal edges, east then west per channel, followed
by vertical edges, south then north. Boundary lanes enumerate north, south, west and east
perimeters, with coordinate then channel within each side; their directed input/output
pairs follow the internal links. A legal single-node unexposed network uses one disabled
sentinel link bit. Explicit masks must have the exact derived packed width.

Supported dimensions are 1..8 rows/columns, 1..2 channels, 1..4 local ports, 1..16 predicate
lanes, and 8..512 metadata bits in whole bytes. Metadata must contain every required field.
Identity widths are 1..32 bits; producer/tag widths are 1..16 bits, class width 2..8, error
width 1..8, proof width 32..64, and schedule period 1..256. The producer field must name
all exposed producers. Other spec fanout, tree-size, Boolean and physical-mask restrictions
are enforced at elaboration. Internal helper widths are supplied by the production top.

Minimal connectivity permits local injection/ejection and straight cardinal paths; it
requires scalar width one and multicast disabled. Balanced permits turns. Broadcast uses
the same physical turn matrix and supports trees within the configured fanout and total
terminal limits. It does not silently add branches or resources. Custom matrices can
select other physically present relations. Physical masks, not profile names, determine
which routes exist.

Metadata fields are packed least-significant first:

| Field | Default width | Default low bit |
|---|---:|---:|
| Context ID | 8 | 0 |
| Context version | 16 | 8 |
| Kernel ID | 16 | 24 |
| Epoch | 2 | 40 |
| Producer ID | 8 | 42 |
| Association tag | 8 | 50 |
| Predicate class | 4 | 58 |
| Poison/error status | 2 | 62 |

Upper metadata bits are opaque and preserved. Local producer IDs are `node*TX+lane`;
boundary producer IDs are `N*TX+boundary_lane`. With `CHECK_CONTEXT=1`, context, version,
kernel, epoch and producer must match the active contract. Tag and poison bits are
preserved exactly. Tags may wrap or repeat; matching operation association is checked by
an external ordered consumer, not inferred by the network.

Classes are scalar=0, vector=1, scalar-with-empty-mask-permitted=2, and
vector-with-empty-mask-permitted=3. Scalar masks can name only lane zero. Empty masks
require class 2 or 3. Class 2/3 also permit nonempty masks. A known false active lane
remains a delivered predicate. Inactive values must be zero; unknown inactive values
canonicalize to zero. Unknown active values, masks or metadata prevent acceptance.
These semantic checks remain enabled when context matching is disabled.

## Prepare, commit, schedules and recovery

`image(parameters, routes, ...)` accepts `{(node, output): source_input}` and emits the
whole-image input fields and an independent DFS certificate. The route vector contains
all node-major/output-major enable bits first, followed by all source selectors of
`ceil(log2(I))` bits in the same order. Schedule slots use link-major groups of
`SCHEDULE_PERIOD_MAX` bits; bit t names phase t of the configured period.

The proof body packs route, schedule-enable bitmap, slot image, period, context ID,
version, kernel and epoch, least-significant first. Prepend the 32-bit topology ID at
the low end, pad the high end to a whole byte and compute reflected CRC-32C
(polynomial `0x82f63b78`, initial/final XOR `0xffffffff`). Zero proof is reserved;
wide proof IDs zero-extend the CRC. The topology ID starts at `0x504e0101` and folds
all scalar defaults in declaration order, then node, directed-link and connectivity
mask bits least-significant first, using `(hash XOR value)*16777619` modulo 2^32.

Hardware checks known fields, hash, physical selections, fault exclusions, fanout,
version, schedule slots, complete upstream/downstream ownership, acyclic dependencies
and total terminal count. A leaf-elimination pass counts destinations; a forward pass
computes depths. Rejection preserves the active image and any previously prepared
shadow. This checksum is a consistency contract, not authentication; the configuration
master must authorize images. Dependencies involving endpoints, data, memory, barriers
or other networks require the system-level proof described in the specification.

Versions are nonzero and must increase for the same active or prepared context ID.
Prepare may run while active traffic continues. Commit requires matching shadow
context/version and all switch, skid and boundary ownership empty. Ingress and egress
are blocked while every node installs and acknowledges the same image. An asserted commit request blocks new ingress, including on its acceptance edge.
Commit consumes the shadow. Abort cancels uncommitted validation/shadow state and cannot undo a consumed
commit. The cluster controller must coordinate readiness and acknowledgement with data
routes and endpoint tables before allowing execution.

A schedule is optional per image. Local-only routes have no directed-link slot and
remain elastic unless checked by the tile controller. If any link is checked, this implementation requires
all links used by that route image to be checked. Enabled maps must be nonempty and
contain no bits beyond the period. The generator offsets each link slot by its certified
latency; hardware rejects incompatible adjacent slot maps. Phase resets on commit and
starts on the first enabled execution cycle. Missing required presentation, off-slot use
and backpressure report errors without dropping, reordering or retagging owned tokens.
`i_drain` suppresses required-new-token checks. `i_schedule_pause` freezes phase only at
an empty period boundary; associated data and tile schedules must use the same safe point.

Drain blocks new ingress and retires accepted copies. Flush overrides transport and
configuration, removes node/skid/boundary/quarantine ownership, and advances epoch once
per held flush episode. Routes, faults and lifetime counters survive. Endpoint data
queues must be canceled in the same recovery transaction; stale data cannot remain live.
Epoch wrap requires that coordinated cancellation, not merely comparison of epoch bits.

Fault additions may be accepted while occupied; clearing needs quiescence. A fault
intersecting the active route stops all new ingress conservatively, contains the affected
links and sets sticky error; unaffected owned branches can drain. Software must flush
and install an authorized alternative or terminate. No autonomous rerouting occurs.
Error clear requires quiescence and removal of the root cause. A first fault without a
qualifying token records its node/link and active identity; producer/tag may be zero.

An endpoint reports tag mismatch with `i_endpoint_alignment_error` plus expected and
observed tags. A qualified mismatch clamps that output's valid and ready before
consumption, records the tag pair, and quarantines it until flush. Endpoint reports must remain stable independently of the clamped network outputs,
for example through a registered endpoint fault indication. Consumers keep ready low
until association succeeds. The network neither searches nor joins streams. Successful joins still consume known-false predicates.
`i_boundary_isolate` stops new ingress and acknowledges isolation after all ownership
is empty. `o_node_clock_enable` is an activity hint; there are no generated clocks.
Test/scan inputs force present-node hints high. Power control must retain all nodes
owning tokens or configuration/recovery obligations.

Error enums: unknown=1, route=2, fanout=3, tree=4, dependency=5, version=6, proof=7,
schedule=8, active fault=9, lane semantics=10, context=11, epoch=12, producer=13,
alignment=14, link parity=15, integrity=16 and counter overflow=17.
Transfer, stall, parity, schedule and alignment events describe the preceding edge.
The inherited multicast event has one additional node register stage.

## Observation map

Counters are 32-bit saturating lifetime counts, cleared by reset. Read index on
`i_counter_read` returns `o_counter_valid/o_counter_value` after the next edge.
Offered/valid measurements count cycles, including held stalled presentations.

| Indices | Measurements |
|---|---|
| 0..3 | Tile presentations, tile accepts, tile deliveries, directed transfers |
| 4..7 | Multicast source events, alignment errors, parity errors, schedule errors |
| 8..11 | Commits, aborts, legal prepares, rejected prepares |
| 12..15 | Drain, flush, active-fault and idle cycles |
| 16..20 | Injection, ejection, boundary stall port-cycles; malformed ingress; configuration busy |
| 21..31 | Reserved, zero |
| `TX_BASE=32`, four per tile TX | Presentations, accepts, accepted active lanes, accepted true lanes |
| `RX_BASE=TX_BASE+4*N*TX`, four per tile RX | Valid cycles, deliveries, delivered active lanes, delivered true lanes |
| `LINK_BASE=RX_BASE+4*N*RX`, four per link | Transfers, occupied skid cycles, parity errors, schedule errors |
| `NODE_BASE=LINK_BASE+4*max(1,L)`, four per node | Input occupancy integral, idle cycles, inactive hint cycles, multicast source events |
| `ALIGN_BASE=NODE_BASE+4*N`, one per tile RX | Alignment errors |
| `COUNTERS=ALIGN_BASE+N*RX`, N+1 entries | Per-node peak input occupancy, then network peak input occupancy |

Boundary directed counters measure external ingress/egress handshakes. Node occupancy
counts switch inputs; link occupancy counts skid slots. Perimeter queues participate
in empty/drain checks but are not included in node peaks. Software must sample and
difference counters at context changes for attribution. Route destinations, fanout,
startup latency and endpoint skew are available from route certificates and Python
ledgers; this sampled profile does not store per-kernel histories or arbitrary latency,
producer, class or skew histograms in hardware. Physical utilization and energy need
characterized clocks, capacitances, libraries and activity analysis.

## Verification structure and limits

The suite separates transaction, sequence, driver, monitor, agent, scoreboard, coverage,
environment and test. UVM wiring reuses `mosaic_uvm`. Predicate adapters reuse static-mesh
geometry, routing, randomized traffic and its independent cycle model. The model tracks
node inputs, pending destinations, skid slots and boundary FIFOs. A separate endpoint
ledger checks each accepted copy for exact-once, ordered, bit-identical delivery. Native
checks cover known outputs, inactive payload clamps, false/invalid lane semantics and
boundary parity. Error probes use explicit assertions outside the normal traffic oracle.

Directed scenarios exercise all local ports, directions and channels, legal straight/turn
relations, simultaneous disjoint routes, full-diameter paths, stalls, bounded broadcast,
prepare/reject/abort/commit, active-shadow isolation, cyclic/dangling/orphan routes, lane
classes, producer/context/epoch checks, tag mismatch quarantine, schedule periods one and
three, safe pause, missing/off-slot/backpressured schedule use, link faults, parity faults
in every token field and at the perimeter, protected control faults, counters, reset,
pending-token flush, isolation and clock hints. The positive endpoint model varies data
arrival relative to predicates and checks ordered context/tag matches before authorizing
any lane. It models the external alignment contract, not a new endpoint RTL adapter.

The campaign covers 2x2, 4x4 and 8x8, widths 1/2/4/8/16, channels 1/2, local ports 1/2/4,
all connectivity profiles, sparse/directed masks, exposed/absent boundaries, bounded trees,
feature removal, wide opaque metadata, control parity/SECDED and both reset modes.
Pure Python checks use hand-derived metadata, route, depth, slot, CRC and graph examples.
Invalid parameter combinations are checked by Python-launched elaboration tests.

This suite provides Python/PyUVM functional evidence. It does not run HDL lint, assertions,
formal, synthesis, CDC/RDC/DFT/low-power signoff, or physical timing/power characterization.
Full specification coverage closure and system-level dependency/association proofs remain
release work. Generated contracts label physical timing and energy `NOT_CHARACTERIZED`.
Design Compiler synthesis is deferred as requested.
