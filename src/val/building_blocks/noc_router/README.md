# NoC router validation

This suite implements the [router specification](../../../../../specs/building-blocks/mosaic-noc-router/README.md)
using [`noc_router.sv`](../../../rtl/building_blocks/noc_router.sv) and an independent
PyUVM packet ledger. Encodings are defined locally in `noc_router_pkg.sv`, consistent
with this repository's existing blocks; no external contract package is required.

## Run

From `mosaic-cgra`:

```sh
make setup
make pyuvm SIM=icarus COCOTB_TOPLEVEL=noc_router
make noc-router-regression SIM=icarus
make noc-router-mesh-regression SIM=icarus
make noc-router-topology
make noc-router-regression SIM=vcs VCS_BIN_DIR=/path/to/vcs/bin
```

`NOC_ROUTER_SEED` and `NOC_ROUTER_RANDOM_CYCLES` configure the campaigns. The default
is 2,000 randomized cycles per profile; regression runners require at least 1,000.
Directed traffic runs in addition to that count. Build paths are configurable with
`NOC_ROUTER_REGRESSION_BUILD`, `NOC_ROUTER_MESH_BUILD`, and `NOC_ROUTER_TOPOLOGY_BUILD`.
Each simulator campaign writes `summary.json`, per-profile logs, JUnit results,
parameters and coverage, including source and verification hashes. A missing
simulator or license is reported as `NOT_RUN` and returns a failing process status.

Select individual profiles directly:

```sh
.venv/bin/python src/val/building_blocks/noc_router/run_noc_router_regression.py \
    --sim icarus --build-dir build/icarus/noc_router/selected \
    --case core_f1_r0_p1_b2 --random-cycles 1000
```

For direct custom runs, specify matching `NOC_ROUTER_<PARAMETER>` environment values
and compiler overrides: `-Pnoc_router.PARAMETER=value` for Icarus or
`-pvalue+noc_router.PARAMETER=value` for VCS. The runner generates both automatically,
including the packed class maps. It also performs explicit invalid-parameter probes.
The native HDL checker is enabled by default through `NOC_ROUTER_HDL_ASSERTIONS=1`.
Disabling it reports `NOT_RUN` for that check. Synthesis source lists exclude it.

## RTL composition

The implementation reuses the following released blocks without modifying them:

- `fifo`, `decoder`, and `mux`: a ring of one-entry FIFO lanes per input VC.
- `round_robin_arbiter`: input VC selection and separate normal/high output selection.
- `counter`: each output VC's downstream credits.
- `parity` and `ecc`: complete input records, with SECDED striped at 256 data bits.
- `event_barrier_state` and `event_barrier_queue`: protected control state and output holds.
- `dff`: state and event registers; FIFO and mux dependencies also use `operand_isolation`.
- `skid_buffer`: registered reverse-flow boundaries in the valid-ready mesh fixture.

`noc_router_buffer.sv` supplies synchronous flush and protects ring ownership.
`noc_router_codec.sv` distinguishes correctable faults, double payload faults and
unsafe ownership faults. A separately checked ownership copy covers routing,
framing, VC, epoch, metadata and discard state. SECDED double faults in data/keep
can forward with all error bits set; ownership disagreement is fatal. Parity mode
conservatively treats every stored mismatch as fatal. Payload RAM is unreset;
empty lanes are isolated from routing and output logic.

Parameterized packed records remain inside the router. Port, routing, flow,
protection and error enums are in the package. There are no generated clocks or
flush-derived resets. Local `UNUSEDSIGNAL` lint directives cover partial record
views and holding-stage inputs absent in pipeline-zero profiles. Their owner is
the MOSAIC NoC maintainers; their scope is the adjacent declaration; review them
whenever those fields or pipeline profiles change. Functional width, latch and
loop warnings are not suppressed.

## Link and configuration contract

| Setting | Encoding / behavior |
| --- | --- |
| Ports | LOCAL=0, NORTH=1, EAST=2, SOUTH=3, WEST=4 |
| Coordinates | Row-major node `y * MESH_X + x`; north decreases Y |
| Routing | 0=XY, 1=YX; every router in a dependency domain uses the same order |
| Flow control | 0=valid-ready, 1=credit |
| Protection | 0=none, 1=parity, 2=SECDED plus checked ownership copy |
| Pipeline | 0=direct FIFO-to-link, 1=one output holding stage |
| Reset | Active low; `ASYNC_RESET` selects synchronous/asynchronous assertion |
| Class maps | Least-significant slice is class zero; VC width is `max(1, clog2(NUM_VCS))` |
| Default maps | Class modulo VC count; even classes normal, odd classes high |
| Epoch | Per physical port; incremented on flush; at least two bits in credit mode |
| Credits | `OUTPUT_INITIAL_CREDITS` equals the connected receiver's input-VC depth |

All physical-link fields use least-significant slices for port zero. Occupancies
and credits use index `port * NUM_VCS + vc`. A packet retains its VC at every hop.
The physical input and output remain reserved through the external tail transfer,
including when the tail has already moved into the output hold. A single-flit
packet releases both reservations on its external transfer edge.

Reset disables all ports. Before injecting traffic, submit a legal configuration
through `i_config_valid` / `o_config_ready`: LOCAL enabled and not fault-masked,
with unusable boundary links disabled or fault-masked. Configuration is atomic
and requires structural idleness. It cannot coincide with a flit or credit transfer.
A bad or unknown mask produces `o_config_rejected` without installing it.

An illegal head is quarantined through its verified tail. A malformed body cannot
change the captured route; it and remaining flits carry an error indication.
Known stale epochs and out-of-range VCs go to a pre-FIFO sink, which returns no
credit. Coordinated recovery must restore the sender/receiver credit contract.
Link parity failure or untrusted ownership is fatal. Fatal state blocks forwarding
and survives flush and error-clear; reset is required to resume.

Error codes are NONE=0, PORT=1, RANGE=2, CLASS=3, PROTOCOL=4, EPOCH=5, CREDIT=6,
CONFIG=7, CORRECTED=8, UNCORRECTABLE=9, UNKNOWN=10, OVERFLOW=11, PARITY=12 and
OWNERSHIP=13. The first error is sticky. Error-clear succeeds only while idle;
flush clears recoverable errors, preserves configuration and advances epochs.

## Timing and network integration

For an empty, configured router with an immediately available route and receiver,
a flit accepted at edge t transfers at t+1 with pipeline zero, or t+2 with pipeline
one. Arbitration, earlier packets, credits and backpressure add delay. An acquired
multi-flit packet sustains one flit per cycle. Pipeline one does not replace a
retiring tail on that same edge, adding a setup bubble between packets. Pipeline
zero can transfer consecutive one-flit packets on consecutive edges.

Valid-ready outputs hold every field stable while stalled. Depth-one queues permit
same-edge pop/replacement, creating a local reverse ready path. Integrators must
insert registered ready boundaries on connected global links; the mesh fixture
uses the released skid buffer on each directed valid-ready link. Credit links use
registered launch/return events. Input credit returns follow actual FIFO pops,
including quarantine pops, rather than arrival or external output transfer.

Network drain first stops endpoint injection while forwarding in-flight packets.
Only after network delivery completes should all routers receive `i_drain` to
confirm local drain completion; asserting it everywhere mid-flight can prevent
a neighbor's new packet head from entering. Flush is a coordinated network action
covering routers, endpoint credit state and link buffers. Epoch wrap requires
that no pre-wrap traffic or credit remains in the domain.

## Verification structure and scope

The suite uses transaction, sequence, driver, monitor, agent, environment,
scoreboard, reference-model and coverage components, reusing `mosaic_uvm` helpers.
The model computes coordinate routes, accepted-flit identities, framing, FIFO order,
credits, cancellation and packet ownership independently. Internal pop observations
identify switch departures; every departure and external output must match a
previously accepted flit. The scoreboard checks conservation after every clock edge.
Native HDL assertions independently check switch/pop matching, input exclusivity,
occupancy/credit bounds, zero-credit launch prevention, output stability, invalid
clamps, flush exclusion and registered credit returns.

The 73 router profiles cover both routing orders, flow modes, pipelines and reset
styles; VCs 1/2/3/4; depths 1/2/3/4/8; data widths 8/32/64/128/256; all boundary
coordinates of 2x2/4x4/8x8 meshes; interior routers; all protection modes; custom
maps and a burst limit of one. Required goals include input/output/VC routes,
classes, FIFO occupancy, reachable-output credit counts, simultaneous output pairs,
QoS burst limits and forced normal service. Directed tests also cover malformed
packets, disabled and masked ports, drain, flush, active reset, X controls, stale
flits/credits, every link-field parity fault, SECDED correction, double faults and
fatal ownership corruption. Geometry exclusions carry owner, scope, rationale and
an expiration criterion in coverage output.

The four network profiles instantiate actual 2x2 and 4x4 meshes, both flow modes,
both dimension orders, and one/two VCs. Every source/destination pair is exercised,
followed by randomized congestion, delayed credits, backpressure and coordinated
flush. Independent endpoint ledgers check exact delivery, packet ordering and
noninterleaving. `generate_mesh.py` reproducibly generates the checked-in fixture.
TNI RTL is absent in this repository, so endpoints implement the flit contract
behaviorally and TNI integration remains `NOT_RUN`.

`analyze_topology.py` enumerates all source/destination paths for every router
profile and topologically sorts directed link/VC dependencies. It rejects invalid
VC maps and proves the finite dimension-order resource graph acyclic. This does
not establish endpoint message-dependency or temporal liveness properties.

Local validation uses Icarus/PyUVM, Verilator lint and Yosys/slang synthesis
elaboration with structural and combinational-loop checks. This is RTL functional
validation. Commercial VCS execution, temporal formal harnesses, technology mapping,
sequential equivalence, CDC/RDC, DFT, UPF/VC LP, place-and-route, extracted timing,
and PrimePower/physical energy remain separate `NOT_RUN` release checks.
