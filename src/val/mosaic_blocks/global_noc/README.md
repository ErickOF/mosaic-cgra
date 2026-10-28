# Global NoC: RTL and PyUVM validation

Implements the synchronous rectangular-mesh baseline of
[`mosaic-global-noc`](../../../../../specs/mosaic-blocks/mosaic-global-noc/README.md).
`src/rtl/mosaic_blocks/global_noc.sv` instantiates one released `noc_router` and
one released `tile_network_interface` per node. There is no behavioral router or
endpoint packetizer in the production source closure.

```sh
make global-noc-generate
make pyuvm SIM=icarus COCOTB_TOPLEVEL=global_noc
make global-noc-regression SIM=icarus
make global-noc-regression SIM=vcs
```

Use `GLOBAL_NOC_REGRESSION_ARGS='--case balanced --case protected'` to select
profiles, and `GLOBAL_NOC_SEED` / `GLOBAL_NOC_RANDOM_CYCLES` for reproducible random
traffic. The campaign defaults to at least 2,000 randomized clock opportunities
per profile. XML, checked coverage, generated manifests, source hashes and a final
`summary.json` are written under `build/<sim>/global_noc/regression`.

## Transport and reuse

Node IDs are row-major: `y * NOC_X + x`. Ports are local=0, north=1, east=2,
south=3 and west=4. A full rectangle has exactly one endpoint per router. An
endpoint ID in a packet denotes its source or destination TNI channel, rather
than another node. Every directed cardinal link preserves the complete flit and
parity record; credit returns have their own direction, VC and epoch pipeline.
Boundary ports are disabled.

The wrapper reuses router FIFOs, round-robin/QoS arbiters, counters, parity/ECC,
TNI queues and reassembly, common `dff`, and the released `skid_buffer`. In Lite
ready/valid mode, each directed link breaks the reverse combinational path with
a skid buffer; additional stages are elastic queues. Credit stages never stall
and do not create additional downstream capacity. Router outputs are registered. Parity-enabled cardinal links add one mandatory
fixed register boundary, in addition to `LINK_PIPELINE_STAGES`. It captures data,
metadata and parity together and breaks combinational propagation of native
router fatal containment through a bidirectional mesh. Generated links publish
requested, protection-boundary and total stage counts separately.

The default balanced profile uses four VCs, four entries per router/TNI input VC,
32-bit flits and 128-bit endpoint beats. Class order is data, reduction, request,
response, event, runtime, migration, debug. VC mapping is `[0,0,1,2,3,3,0,0]`;
event/runtime receive critical bounded service. Routing is XY or YX.

A beat produces `ceil(ENDPOINT_DATA_WIDTH / FLIT_DATA_WIDTH)` flits in increasing
byte order, with zero padding. Native TNI fragment indices are widened with zeros
and checked before narrowing on ejection. Stream `last` is preserved independently
of packet tail. Packet metadata is unchanged by intermediate routers.

Balanced/protected credit mode reserves downstream credits for a whole fixed
packet **before** acquiring a router input/output or TNI serializer reservation.
This is an optional `PACKET_CREDIT_RESERVATION` parameter on the reused router/TNI;
its default of zero preserves their existing standalone wormhole behavior.
Global NoC input VC depth must therefore hold a full endpoint packet. Router and
TNI RX VC depths must match because the router exposes one initial-credit value
for all its ports. Critical flows use the last TX and RX channel, exclusively;
ordinary flows cannot use those channels. A stalled data packet cannot partially
acquire transport ownership ahead of a packet with available critical credits.

## Configuration ABI (repository-local v1)

The dedicated configuration interface carries no runtime data. Commands are
write=0, read=1, validate=2, prepare=3, commit=4, abort=5, status=6. It accepts one
request at a time and holds tagged responses until acknowledged. Status values
are OK=0, bad command=1, index=2, image=3, CRC=4, version=5, busy=6, ownership=7.

An inactive image has `2 + NUM_ROUTERS + 4 * MAX_ACTIVE_FLOWS` 64-bit words:

| Words | Meaning |
| --- | --- |
| 0 | Compiled layout signature from `global_noc_contract.signature()` |
| 1 | Repository-local protocol/layout ID `0x4e4f430000000001` |
| `2 + node` | Five router fault bits; reserved/boundary bits must be zero |
| `2 + NUM_ROUTERS + 4 * flow` | Four-word binding, defined below |

Each valid binding is one source node/channel and destination node/channel.
Multiple explicit bindings/copies implement source-driven multicast. Flow IDs are
unique in an image. The four binding words contain:

| Word | Bits (inclusive) |
| --- | --- |
| 0 | valid `[0]`, flow ID `[16:1]`, allocation generation `[32:17]`, execution epoch `[40:33]`, package slot `[48:41]`, context `[56:49]`; upper bits zero |
| 1 | owner `[15:0]`, kernel `[31:16]`, full package ID `[63:32]` |
| 2 | source node `[7:0]`, source channel `[15:8]`, destination node `[23:16]`, destination channel `[31:24]`, allowed classes `[39:32]`, allowed message types `[55:40]`, outstanding budget `[63:56]` |
| 3 | reverse response flow ID `[15:0]`, initial sequence `[31:16]`; upper bits zero |

`flow_words()`, `image()` and `crc32c()` provide executable examples. CRC32C covers
all words, byte zero first, reflected polynomial `0x82f63b78`, initial/final XOR
`0xffffffff`. Byte strobes support read/modify/write of the inactive image.

The first write claims an inactive image for the command owner/kernel/package.
Other identities cannot read or modify it. Once configured, infrastructure
owner/kernel remain authoritative. Bindings can name multiple application owners
and kernels within the configured package. The dedicated configuration hierarchy
must authenticate that infrastructure authority and its application allocations.

Validation checks layout, reserved bits, class restrictions, endpoints, complete
fixed-route reachability under fault masks, binding uniqueness, execution epoch,
package identity, budget, and a reverse response-class flow for every request
flow. Requests also require `i_response_reserved[channel]` at admission: the
endpoint adapter must actually reserve the promised response/event resources.

Prepare validates the expected CRC. Writes, abort and flush invalidate preparation.
Commit requires the expected version, matching CRC, `i_run=0`, empty network and
no fatal state. It installs the entire image, then coherently configures every
router/TNI before acknowledging success. Version increments once. Commit does
not start traffic: drive `i_run=1` separately. Version exhaustion requires reset.

## Endpoint and lifecycle rules

Packed endpoint vectors use endpoint-major, channel-minor order, least-significant
channel first. The 64-bit user field contains flow ID `[15:0]`, allocation
generation `[31:16]`, execution epoch `[39:32]`, package slot `[47:40]` and per-VC
flow sequence `[63:48]`. Injection and ejection check the full active binding,
including node, channel, context, class, message, generation, epoch, sequence and
outstanding budget. Illegal injection is rejected before native queue ownership.
Sequence wrap is blocked until flush/reset or a safe configuration transition.

Drain blocks the selected flow slots or all slots. Already accepted packets keep
forwarding; native router/TNI drain pins stay low. Completion requires all selected
public endpoint obligations to finish; all-flow drain additionally requires every
router, TNI, flit link and credit pipeline to be idle. Selected drain waits the
credit-return pipeline latency after its last public endpoint obligation ends;
unselected flows may continue using the network. A timeout returns a tagged
fault completion without discarding packets or declaring idle. The timeout counter supports positive values through `0xffffffff`. Drain masks remain
blocked until software deasserts `i_run`; reassert it to restart. Lifecycle status:
drained=0, flushed=1, timeout=2, exhausted epoch=3. Responses remain stable under
backpressure, and lifecycle commands are serialized.

Flush pulses all connected TNIs, routers and links together, resets outstanding
ownership and sequences, increments execution/link epochs, and counts discarded
accepted packets. Active flow/fault configuration is preserved. New traffic stays
blocked until `i_run` is deasserted and reasserted. Old metadata is rejected. Epoch
wrap and fatal transport faults require reset; flush/error-clear do not clear fatal
state. Fault/parity containment never retries application work automatically.

`o_idle` includes endpoint obligations and pending credit stages. Current and
per-flow/class counters, flow outstanding counts, router VC occupancy/credits,
endpoint occupancy, epochs and fault masks are public. Counters may be disabled;
flow/lifecycle correctness remains active. Snapshots are software-coordinated at
idle and identified with the active package/version/execution epoch.

## Verification scope and integration limits

The UVM structure separates sequence items, sequences, driver, passive monitor,
agent, environment, independent beat scoreboard and checked coverage. It reuses
`mosaic_uvm` wiring and regression infrastructure. Tests cover every source/
destination pair in simulated meshes, metadata/classes, multi-kernel bindings,
serialization/padding, simultaneous injections, backpressure, request admission,
critical progress, selected/all drain, timeout, held responses, configuration
ownership/CRC/fault rejection, flush/stale epoch, reset with live traffic, and
randomized concurrent endpoint traffic. Occupancy/credit bounds and public
accepted/delivered/discarded accounting are checked. A second ledger checks each
fragment at every physical router output, including route, framing, byte enables,
metadata, reservation continuity and exactly-once hop traversal. Credit launches
and returns must exactly predict the following cycle's counter values. Protected
link-parity fault injection checks fatal containment, and reset explicitly
accounts for unresolved packets.

The matrix includes 1×1, 2×2, 3×2 and 4×4 RTL meshes; Lite one/two VCs;
balanced/protected four VCs; XY/YX; ready/valid and credit; flits through 128 bits;
endpoint beats through 256 bits; depths 1/2/4/8; odd width ratios; link/credit
pipelines; parity and SECDED; and disabled counters. Selected original router/TNI suites rerun with their
legacy admission defaults and HDL assertions disabled; eight additional guards
check the new native packet-reservation parameter. Python model tests enumerate
routes and router-channel dependency DAGs through 8×8. **8×8 RTL traffic simulation
is not claimed by this campaign.** The DAG certificate covers router channels,
not application transactions or a full temporal deadlock proof.

Unsupported optional settings fail elaboration: asynchronous endpoints/reset,
control-state protection, trace, sparse meshes, unregistered router outputs,
imbalanced local/cardinal credit capacities, balanced ready/valid, and packet
segmentation beyond one fixed beat. Lite rejects request/response/event/runtime
classes. Fixed identity widths follow the v1 layout. Endpoint clock/reset pins
are reserved and unused in this synchronous profile.

Memory transaction tracking, fence record generation/acknowledgement, application
retry, cluster power sequencing/retention and the complete end-to-end protocol
proof remain responsibilities of integrating endpoint/runtime logic. A selected
flow drain provides the transport barrier an adapter can use before its explicit
cross-VC fence and acknowledgement. A protocol ID is an ABI identifier, not an
end-to-end deadlock proof. No clock-domain, low-power, formal, lint, synthesis,
physical or power signoff is claimed. Validation here is Python-only; synthesis
is deferred to Design Compiler as requested.
