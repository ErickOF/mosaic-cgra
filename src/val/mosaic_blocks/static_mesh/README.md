# Static mesh RTL and PyUVM validation

The production top is `src/rtl/mosaic_blocks/static_mesh.sv`, implementing
[the mesh specification](../../../../../specs/mosaic-blocks/mosaic-static-mesh/README.md).
All mesh interfaces use `i_clk`; asynchronous endpoints need an external async FIFO.
No synthesis, HDL assertions, HDL lint, CDC, formal, or physical signoff runs in this suite.
Design Compiler synthesis and extracted timing/power characterization remain separate work.

Run from `mosaic-cgra`:

```sh
make static-mesh-regression SIM=icarus
make static-mesh-regression SIM=vcs
# One baseline simulation, using the Makefile's production dependency closure:
make pyuvm SIM=icarus COCOTB_TOPLEVEL=static_mesh
# Selected campaign cases:
.venv/bin/python src/val/mosaic_blocks/static_mesh/run_static_mesh_regression.py \
  --sim icarus --build-dir build/icarus/static_mesh/selected --case small --case parity
```

`STATIC_MESH_SEED` and `STATIC_MESH_RANDOM_CYCLES` configure the Make target.
`STATIC_MESH_JOBS` controls concurrent simulator processes (default four for Icarus,
one for VCS). Each random transport phase sends at least the requested count of
beats through the selected long path, with reproducible source gaps and destination
stalls. The scheduled profiles exercise continuous, unstalled periodic traffic instead.
No VCS installation or license is assumed by the Icarus campaign.

The campaign writes `summary.json`, per-profile `results.xml`, `coverage.json`,
`parameters.json`, `simulation.log`, and `contract.json` beneath
`build/<sim>/static_mesh/regression`. Source hashes cover the RTL, production dependencies,
Python suite, shared UVM helpers, and Makefile. The campaign fails if those sources change
while it runs, a requested test is skipped, results are stale, or a mandatory goal is missing.
Generated artifacts are build products, not source dependency manifests.

## Composition and flow control

Each present node uses the existing `local_switch` with its `register_slice` input
storage and pending multicast masks. Only output rows with physical connectivity
are instantiated; the wrapper translates those compact rows into the published
local/cardinal port space. Absent nodes, edges, and output rows are tied off.
Existing common RTL is unchanged.

Each internal directed link reuses `skid_buffer`. Its forward bypass adds no
unstalled latency, and its registered ready cuts the combinational ready path to
one node. Under a late stall it owns one extra beat. Each exposed boundary direction
uses `event_barrier_queue`, which reuses common FIFOs and supports synchronous flush.
Boundary depth zero is allowed only for schedule-checked flow. Depths one through
eight have no fall-through and add one cycle of unstalled latency, regardless of depth.

An unstalled route with H neighbor hops has H + 1 node stages. Queued ingress and
egress boundaries add one stage each. A packet is first visible after the accepting
edge of its final node stage; consumers accept it at the next eligible edge.
Skid slots and multicast pending branches are included in drain and flush ownership.
A blocked branch cannot consume or duplicate a copy already delivered to another branch.

Control, context-directory, active-image, pending-branch, and skid-valid witnesses
reuse `banked_scratchpad_state` and the existing striped parity/SECDED codec. Boundary
FIFO metadata uses the queue's parity detection when either control-protection mode
is enabled. Link data protection is even parity over data and metadata, with no retry
or correction. Runtime integrity failures contain transport until reset; ordinary
metadata, schedule, parity, and directed-link faults block admission while safe egress
may drain. Flush preserves routes, contexts, counters, and fault masks; it discards all
transport ownership and increments the epoch once per asserted flush episode.

`o_node_clock_enable` is an activity hint with scan/test overrides. The RTL uses
the original clock and data enables; approved clock gates and power-domain cells
belong to physical integration. Boundary isolation acknowledges only after the mesh
is empty and clamps boundary transport. `i_enable=0` stops admission but permits drain.
In a running schedule, disable is a legal pause only when the image allows it and
all transport storage is empty; drain explicitly suppresses required-new-beat checks.

## Local encodings and image generation

This workspace has no external `mosaic-contracts` package. `static_mesh_pkg.sv` and
`topology.py` define a repository-local v1 contract. The generated connectivity matrix
and topology fingerprint are authoritative, including custom masks. These encodings
must be translated when integrating a separately versioned system contract.

Nodes are row-major. Node inputs are local TX lanes, north, south, east, west;
outputs are local RX lanes followed by the same directions. Channel increases
inside each direction. Boundary lanes are north west-to-east, south west-to-east,
west north-to-south, east north-to-south, with channel inside coordinate.

Internal link IDs enumerate horizontal edges in row-major order, east then west
per channel, followed by vertical edges, south then north per channel. Boundary
IDs follow, input then output per boundary lane. Thus
`IL = 2*channels*(rows*(cols-1)+(rows-1)*cols)` and
`L = IL + 2*EXPOSE_BOUNDARY_PORTS*B`. For the legal single-node, unexposed case,
link buses have one disabled sentinel bit instead of a zero-width vector.
Masks must have their exact derived width; use sized SystemVerilog literals in overrides.
Sparse masks never invent a reverse edge or skip a missing tile.

The default minimal profile permits local-to-local, local-to-cardinal,
cardinal-to-local, and straight cardinal forwarding. Balanced adds right-angle
turns; flexible adds immediate U-turns. Custom connectivity can explicitly permit
other physical relations. An explicit mask cannot connect absent nodes or links.

`image(parameters, routes, ...)` accepts `{(node, output): input}` and emits a padded
integer image, proof ID, and certificate. Words and fields are little-endian.
The low-to-high layout is:

1. Schema (8), topology fingerprint (32), context version (V), kernel (K),
   proof ID (P), period (`ceil(log2(PERIOD_MAX+1))`), pause permission (1).
2. All output-enable bits, node-major then output-major.
3. All input selections in the same output order, `ceil(log2(I))` bits each.
4. All input-resource ranks, node-major/input-major, `ceil(log2(N*I))` bits each.
5. All input arrival offsets in the same order, with width
   `ceil(log2((N*I+1)*(PERIOD_MAX+1)+4))`.
6. Zero padding to a whole configuration word. Every padded byte must be written.

The topology fingerprint starts at `0x534d0101`. In `DEFAULTS` insertion order,
fold every scalar parameter, then each node mask bit, link mask bit, and connectivity
bit (least-significant first), using `(hash XOR value) * 16777619` modulo 2^32.
The proof ID is CRC-32C of the padded image with its proof field zero, XOR the
topology fingerprint. Zero is reserved. Wider proof fields zero-extend this value.
The complete-image checksum is CRC-32C with the final proof ID included. CRC uses
polynomial `0x82f63b78`, reflected bytes, initial/final XOR `0xffffffff`.

The offline generator topologically sorts input-resource dependencies and refuses
cyclic, dangling, orphaned, or physically absent paths. Hardware verifies strictly
increasing ranks on each internal edge, complete upstream/downstream ownership,
physical selections, fanout, fault exclusions, and matching image identities/hashes.
The certificate is an integrity/consistency contract, not authentication: the trusted
configuration master must authorize images. Dependencies through endpoints, memory,
barriers, or other networks still require a system-level proof.

Schedule-checked flow gives each used input one slot per period. Its first absolute
arrival offset and period define all later slots. Neighbor arrival is exactly source
arrival + 1; queued boundary input offsets must be at least one. Used arrival offsets
are bounded by `(N*I+1)*(PERIOD_MAX+1)`. The checker reports missing, off-slot, and
backpressured node transfers without discarding or relabeling an accepted beat.
This release does not implement shared-output time-division arbitration.

Metadata low-to-high fields are context ID, version, kernel ID, epoch, byte keep,
`first`, `last`, `row_first`, `row_last`, `eos`, `error`, and a two-bit datatype.
Datatype 0 and 1 are legal. Unkept data bytes must be zero; zero keep requires EOS.
All upper metadata bits are opaque and preserved. Context checking is configurable;
known metadata, datatype, keep, and padding checks remain active when it is disabled.
The epoch wraps modulo its configured width only at coordinated activation/flush
boundaries: endpoints must discard old transactions before restart.

## Configuration and status

The configuration request and response are independently backpressured. Commands
are WRITE=0, READ=1, VALIDATE=2, ACTIVATE=3, INVALIDATE=4, QUERY=5. Request fields
are held through `i_cfg_valid && o_cfg_ready`; response fields through
`o_cfg_rsp_valid && i_cfg_rsp_ready`.

A nonzero-strobe WRITE opens an inactive generation with a version strictly greater
than that entry's previous version. Later writes to that generation use the same
version and kernel; byte strobes merge without marking unwritten bytes complete.
READ returns a word with unwritten bytes zero. VALIDATE requires every byte,
matching version/kernel/proof/checksum, and all local certificate checks. Failure
invalidates that candidate and leaves installed routes unchanged. QUERY returns
low-to-high valid, loading, version, kernel, proof (truncated to the response width).
INVALIDATE clears an inactive image while preserving its version history.

ACTIVATE requires a valid candidate and an empty mesh. Ingress is blocked while
all nodes install the same image and acknowledge matching selections/identity.
Success increments epoch and emits one response. Busy or rejected activation
preserves the old context. Active images cannot be written or invalidated.
With depth one, replacing the sole active image therefore requires reset.
Payload RAM is unreset; protected byte-written and valid directories establish
which bytes can be read or activated.

`i_link_fault_valid && o_link_fault_ready` installs a directed bitmap atomically.
Adding faults is allowed during transport; clearing faults requires an empty mesh.
A fault intersecting the installed route blocks new ingress and raises sticky error.
Affected links stop; other safe pending branches can retire. Recovery requires
coordinated flush, a validated alternate context, or termination. No automatic reroute
is provided. Quiescent error clear requires removal of the root cause.

Error codes are enumerated in `static_mesh_pkg.sv`: unknown=1, context=2,
version=3, active write=4, word=5, incomplete=6, checksum=7, route=8,
physical=9, fanout=10, kernel=11, proof=12, busy=13, faulted link=14,
metadata=15, schedule=16, parity=17, integrity=18, epoch=19, counter=20,
command=21. Configuration errors are response-only. Runtime errors retain the
first code and node/link identity; an immediate integrity indication takes priority
for containment. Transfer/stall/parity/schedule event outputs describe the preceding edge.
The multicast event has one additional register stage inherited from the node switch.

## Counter observation map

Counters are 32-bit saturating lifetime values, reset only by reset. Read requests
return `o_counter_valid/o_counter_value` after the next edge. Each active context's
identity is separately observable; software must sample/difference counts at context
switches for attribution. Node occupancy observations count local input buffers;
link occupancy observations count skid slots. Boundary counts are independent.

| Indices | Measurements |
|---|---|
| 0..3 | Tile-offered cycles, tile-accepted beats, tile-delivered beats, directed transfers |
| 4..7 | Activation events, drain cycles, flush cycles, active-fault cycles |
| 8..11 | Node schedule violations, parity events, multicast source events, malformed ingress cycles |
| 12..15 | Idle cycles, injection stall port-cycles, ejection stall port-cycles, configuration busy cycles |
| `TX_BASE=16`, two per tile TX | Offered beats/cycles, accepted beats |
| `RX_BASE=TX_BASE+2*N*TX`, two per tile RX | Valid cycles, delivered beats |
| `LINK_BASE=RX_BASE+2*N*RX`, three per link | Transfers, occupied skid cycles, parity events |
| `BOUNDARY_BASE=LINK_BASE+3*max(1,L)`, four per boundary | Ingress beats, egress beats, ingress stall cycles, egress stall cycles |
| `NODE_BASE=BOUNDARY_BASE+4*B`, four per node | Occupancy integral, idle cycles, inactive clock-enable cycles, schedule violations |
| `COUNTERS=NODE_BASE+4*N`, N+1 entries | Per-node peak input occupancy, then mesh peak input occupancy |

Offered counters count valid each cycle, including a held stalled beat. They are
not unique transaction counters. Boundary directed-transfer counters measure the
external ingress/egress handshake. Route lengths, fanout, and destination sets are
available from route-image artifacts and checked transport ledgers; hardware does
not store a per-kernel history or arbitrary route histogram.

## Python verification structure and limits

The suite follows UVM separation: transaction, sequence, driver, monitor, agent,
scoreboard, coverage, environment, and test. Agent/environment wiring reuses
`mosaic_uvm`. The passive monitor samples pre-edge handshakes and settled events.
The cycle oracle models dictionaries of node inputs, pending destination sets,
link skid slots, and boundary FIFO records. A separate recursive graph traversal
feeds an endpoint ledger for every accepted source beat. It checks exact-once
multicast delivery and path ordering without trusting DUT event counts.

Directed cases exercise local lanes, cardinal directions/channels, perimeter
attachments, long paths, context loading/readback/atomic activation, byte writes,
incomplete/hash/certificate rejection, active-write protection, response stalls,
context versions, busy activation, invalidation, epoch checking, flush/drain,
counters/isolation, directed faults, scheduled slots, and physical fault injection.
Randomized ready/valid traffic checks payload and complete metadata preservation,
finite buffering, backpressure, and registered path latency. Pure Python unit tests
have hand-derived topology, CRC, rank, multicast, orphan, cycle, and latency vectors.

The parameter campaign covers baseline and larger meshes, widths 16/32/64/128,
one/two channels, local ports 1/2/4, contexts 1/4/8, all connectivity profiles,
boundary depths 0/1/2/4/8, sparse/asymmetric edges, parity/SECDED, feature removal,
and both reset modes. Named invalid-parameter guards are exercised from Python.
This is functional simulation evidence. Full specification coverage closure,
formal safety/progress proofs, physical timing, CDC/RDC/DFT/LP, and measured energy
remain release gates outside this requested Python-only task. Generated contracts
explicitly label physical timing and energy `NOT_CHARACTERIZED`.
