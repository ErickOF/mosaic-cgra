# Runtime controller RTL and PyUVM validation

The implementation follows
[`mosaic-runtime-controller`](../../../../../specs/mosaic-blocks/mosaic-runtime-controller/README.md)
for **Runtime-Static** and **Runtime-Partitioned**. It selects validated precompiled
packages, reserves complete clusters and declared service resources, sequences
external authorities, and tracks each accepted descriptor to its terminal outcome.
The controller does not generate mappings or contain array/system datapaths.

```sh
make runtime-controller-generate
make pyuvm SIM=icarus COCOTB_TOPLEVEL=runtime_controller
make runtime-controller-regression SIM=icarus
# Use the same Python campaign on the licensed server:
make runtime-controller-regression SIM=vcs
```

The regression writes `build/<sim>/runtime_controller/regression/summary.json`,
per-profile `profile.json`, `coverage.json`, simulator logs and JUnit results.
`RUNTIME_CONTROLLER_SEED`, `RUNTIME_CONTROLLER_RANDOM_CYCLES` (minimum 1000),
`RUNTIME_CONTROLLER_REGRESSION_BUILD`, and `RUNTIME_CONTROLLER_REGRESSION_ARGS`
control the campaign. For example, pass
`RUNTIME_CONTROLLER_REGRESSION_ARGS='--case balanced --case secded'` to select cases.
Direct `make pyuvm` uses the default balanced geometry. Parameter changes require
matching simulator overrides and `RUNTIME_CONTROLLER_<PARAMETER>` environment
values; use the regression driver to supply both consistently.

All verification is Python: PyUVM runs cocotb against the production RTL, Python
unit tests check the ABI and reference ledgers, and Python-driven elaboration
checks require the named invalid-parameter guard. There are no validation RTL
wrappers, HDL assertions, lint, formal or synthesis steps in this campaign.
Synthesis and timing/resource assessment remain deferred to **Design Compiler**.

## Composition and supported limits

The RTL reuses `round_robin_arbiter`, `priority_encoder`, `counter`,
`performance_counters`, `event_barrier_queue`/`fifo`, and protected
`tile_shell_state`/`dff` storage with `parity`/`ecc`. No existing RTL was changed.
The production source closure is
[`runtime_controller_sources.py`](../../../gen/runtime_controller/runtime_controller_sources.py)
and the Makefile contains the same ordered source list.

Supported geometry is 1–16 clusters, 1–16 retained descriptors, 1–4 active kernels,
1–16 configured owners and 1–4 package variants. Active kernels cannot exceed
clusters or records. Static requires one active kernel and one variant, including
an optional single package spanning the full array. DMA and memory masks have
up to 16 resources; scratchpad and event masks have up to 32; counter namespaces
are fixed at 16. QoS and power profile IDs have up to 16 values.

Queue depths are independently configurable: submission/action/response 2–32,
event ingress/diagnostic output 2–64, coherent snapshots 2–16. There is **one
outstanding managed action** across all peers. Action issue is serialized even
when multiple kernels execute concurrently; the action queue's occupancy is at
most one in this implementation. Each retained kernel record reserves capacity
for its eventual terminal notice.

`CONTROL_PROTECTION=0/1/2` selects plain, parity or striped SECDED descriptor,
lifecycle and action-ledger storage. Queues use parity when protection is enabled.
A corrected state word is scrubbed; detected uncorrectable state/queue corruption
halts functional handshakes and requests recovery. The root clock request does
not generate a clock. All adapters share one synchronous clock/reset domain;
clock-ready, power-good and test/scan qualification stop functional transfers.
Physical retention, isolation and power switching require external wrappers.

## Normalized v1 records

[`runtime_controller_pkg.sv`](../../../rtl/mosaic_blocks/runtime_controller_pkg.sv)
defines fixed wire enums and packed records. Parameter-dependent record storage
stays local to the controller. The matching Python
[`runtime_controller_contract.py`](../../../gen/runtime_controller/runtime_controller_contract.py)
provides checked `pack()`/`unpack()` helpers. Fields are packed least-significant
first; generated `profile.json` publishes every offset, width and encoding.
These are repository-local v1 encodings, with no `mosaic-contracts` dependency.
V1 identity/timestamp/budget width parameters are guarded at their published
values rather than silently changing the peer ABI.

The descriptor ingress has explicit metadata ports and packed variant/resource/
QoS/power/lifecycle records. All fields are snapshotted on `valid && ready`.
`contract_version=1` and `integrity_valid=1` attest to prior **system** validation;
they do not authenticate a host by themselves. Owner IDs must match the generated,
nonzero, unique `OWNER_ID_TABLE` (defaults 1–4). A live owner/kernel pair cannot
have a second descriptor. Each variant contains an exact precompiled cluster
mask, package/mapping IDs, capabilities, architecture/proof IDs and profile IDs.
Mask population, compatibility, present/healthy clusters, capabilities and
connectivity are checked before choosing a variant. Closest cluster count to the
preferred count wins, followed by the stable variant index.

Resource records contain DMA, memory, scratchpad, event and counter masks, shared
memory/NoC bandwidth, power reservation units and required service bits. Complete
clusters, DMA channels, memory ports, scratchpad regions and namespaces are
**exclusive** in this baseline. Bandwidth and power sums cannot exceed platform
capacities or programmed owner bounds. Best effort cannot borrow reserved
capacity. Guaranteed requests additionally require QoS enable, a matching proof,
and the configured enforced-service mask. Physical enforcement and units remain
part of the external adapter/platform contract; no hard latency claim is made.

Configuration and event services are mandatory. Memory/NoC service bindings are
required for nonzero corresponding budgets. Power is mandatory when power policy
is enabled. Nonzero energy budgets and hard latency flags are rejected as
unsupported; measured energy analysis remains a separate physical-power flow.

Lifecycle flags are:

| Bit | Meaning |
|---|---|
| 0 | Package supports a declared safe suspension point |
| 1 | Initial input readiness is already established |
| 2 | Initial output space is already established |
| 3 | External visibility/completion event is required |
| 4 | A coherent snapshot at/after compute completion is required |
| 5–6 | Resize/migration requests; rejected in this baseline |
| 7 | Package permits destructive abort |

Nonzero per-descriptor action/kernel timeouts override parameter defaults. Kernel
timeout counts running cycles. The safe-point ID is forwarded in action flags
15:8; the resume cookie must match an authorized resume request.

## Authoritative peers and terminal handshakes

The array uses `o_array_runtime_*` and `i_array_runtime_response_*`. Six service
lanes use `o_service_*` and `i_service_response_*` in this order:

| Lane | Authority |
|---|---|
| 0 | Configuration |
| 1 | DMA |
| 2 | Memory and scratchpad |
| 3 | NoC |
| 4 | Event/counter namespaces |
| 5 | Power/clock policy requests |

Each action includes the full owner/kernel/descriptor/generation/package/mapping/
allocation-generation/epoch identity, command, complete cluster mask, resource
mask, profile, flags and runtime tag. It also forwards immutable resource, QoS,
power and lifecycle records, so a service can enforce the actual reservation.
The opaque `slot` field in notices is internal bookkeeping, not an owner ID.

A command transfers on `valid && ready`. Its payload stays stable while stalled.
The matching terminal can transfer on that same edge or later. It must match the
endpoint, full identity, command and runtime tag. Successful terminals must
acknowledge the complete command mask with no error. `NO_EFFECT` promises that
the failed command made no changes. Partial/uncertain effects are contained.
Wrong/old/duplicate replies are consumed and counted without changing ownership.

Launch reserves a complete shadow record, obtains array allocation and every
required service reservation, then publishes **one admission**. Configuration
load/validate/prepare, array commit, activation of service bindings and input/
output readiness precede array start. A fresh nonwrapping epoch is installed in
service ACTIVATE/RESUME commands before array START/RESUME accepts it. Only a
matching array terminal makes a kernel RUNNING.

Every accepted descriptor produces exactly one admission. Rejected/canceled
pre-admission requests produce no kernel result. Every admitted request produces
exactly one terminal result. Admission and result records remain stable under
backpressure. Cancellation does not withdraw an already offered action. Cleanup
can release resources while admission/result sinks are stalled; a result is
published only after the admitted notice has transferred.

Failures before start release acquired service bindings in reverse order, then
release the array. Started kernels must first abort/drain. Normal completion
requires an authoritative full-mask compute event and, when requested, a separate
external-visibility event. Array/service drain acknowledges all external memory,
DMA and output obligations before release. An abort cannot undo memory writes;
service/system adapters must invalidate or retire those obligations explicitly.
Power WAKE requires a ready acknowledgement; IDLE is an external policy request
after all bindings/array ownership have been released.

Safe suspend requires the package flag, an authorized policy request, an array
safe-point/state-preserved terminal, and state-preserving service drain terminals.
Resources remain reserved while suspended. Resume checks the current identity,
health and cookie, restores bindings in a fresh epoch and waits for the array
terminal. No arbitrary-cycle preemption is implemented.

A timeout starts **after command acceptance**. It retains the original tag,
action and ownership, reports recovery, and waits for the original terminal.
Late success triggers rollback/abort rather than continuing launch. No blind
retry/query/replay is issued. A permanently absent terminal stalls the serialized
control path until global system recovery. A terminal reporting uncertain/partial
effects requires an authorized destructive FORCE_ABORT and explicit backend drain/
release. Tag, epoch and allocation counters never wrap; exhaustion fails closed.

## Events, policy, reset and observability

Runtime events carry the full identity, source, complete/subset cluster mask,
sequence and timestamp. Sources 0–N-1 are clusters; source N is the authoritative
array/system adapter. Compute/external completion must come from that adapter;
compute completion must cover the full allocated mask. Sequence starts at zero
per identity/source. Duplicates/foreign events cannot advance lifecycle; a gap
contains that kernel until authorized recovery. Sequence wrap is unsupported.
Critical ingress has a separate FIFO from diagnostic output. Diagnostic overflow
is sticky, deadline warnings remain visible per record, and a stopped diagnostic
sink cannot block resource release or terminal results.

Policy commands are authorized QUERY, ENABLE, DISABLE, UPDATE_BOUNDS, SUSPEND,
RESUME, CANCEL and FORCE_ABORT. Kernel commands match the complete current
identity. ENABLE/DISABLE require system owner ID zero; submission owners remain
nonzero. Bounds updates cannot revoke existing reservations or guaranteed
priorities. Running/uncertain cancellation requires the package abort capability
and an explicit destructive flag. Every accepted policy command has one queued,
backpressured terminal reply.

Coherent snapshots match the complete identity, generation, timestamp and all four
metric-valid bits. Old/incomplete/foreign records are ignored. Sampling is limited
by `POLICY_SAMPLE_INTERVAL`, with a critical override. The four 64-bit metrics are
monitoring inputs; Partitioned does not resize or migrate based on them. A requested
completion snapshot must be no older than the applied compute-completion event.

After **local reset**, new admission is blocked. Reconciliation requires the v1
ABI marker `0x4d52540100000001`, zero remote busy masks and a system clean proof
that old actions, epochs, resources and output obligations were globally retired
or invalidated. Fresh tag/allocation/epoch bases must prevent old identity reuse;
bases cannot rewind within an already reconciled controller lifetime. A local
reset itself never sends a release or proves an external resource free. Lost
local obligations belong to the explicit global system recovery procedure.

Public status includes protected record identities/states, reservations, backend
ownership, ages, scheduler ranks/eligibility, action/timer identity, fault masks,
coherent metrics, running/allocated cycles, sticky diagnostics, idle and quiescent.
A running or resource-blocked controller can be idle without being quiescent.
Quiescent additionally requires no live records, queued notices/events, managed
actions, held resources or recovery obligations. Sixteen reused 64-bit saturating
performance counters count event cycles; simultaneous occurrences coalesce.
Counter snapshot/read ports support a coherent software observation.

## Evidence and integration limits

The agent/driver/monitor/scoreboard/coverage/sequence files follow the shared UVM
structure. Python peers independently delay/stall/fail external commands. The
passive scoreboard checks full action metadata, exact shadow resource sums,
nonoverlapping ownership, reverse release, immutable outputs, monotonic tags and
exactly-once admissions/results. The campaign covers Static single/full-array,
Partitioned concurrency, priority/RR/burst/aging, malformed descriptors, every
launch failure boundary, same-edge/late/premature terminals, cancellation,
timeout containment, safe suspend/resume, event gaps, coherent snapshots, queue
saturation, budget conflicts, fault-aware variants, test qualification, local reset,
identity exhaustion, protected-state injection and seeded random latency/traffic.

Generated manifests publish all layouts/encodings, cluster connectivity/capability
tables, owner IDs, resource policy, action/state/reset contracts and source hashes.
The regression rejects skipped tests, missing functional goals, mismatched ports/
parameters and sources changed during the campaign.

Runtime-Adaptive, resize/migration, CDC, trace, hard real-time guarantees, physical
power gating and nonzero energy budgets are explicitly unsupported. Actual array/
system/service RTL adapters are external integration work; the Python peers do
not constitute vertical hardware integration, physical signoff or a measured
performance/fairness bound. Wall-clock progress assumes finite kernels, readiness,
eventually responding peers and consumers. Design Compiler synthesis is deferred.
