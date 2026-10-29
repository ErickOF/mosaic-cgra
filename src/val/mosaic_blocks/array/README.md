# Array RTL and PyUVM validation

The implementation follows the single-cluster and two-cluster MVP profiles in the
[array specification](../../../../../specs/mosaic-blocks/mosaic-array/README.md).
It reuses the real cluster generator and production BCT, MST, static mesh, banked
scratchpad, configuration network, NoC routers and TNIs. Control/event storage uses
released protected-state blocks, event queues, round-robin arbitration and counters.
Scheduling policy and host/SoC protocols remain outside this boundary.

```sh
make array-generate
make pyuvm SIM=icarus COCOTB_TOPLEVEL=array
make array-regression SIM=icarus
# Run the same Python/PyUVM campaign on the licensed VCS server:
make array-regression SIM=vcs
# Select individual integration cases:
make array-regression SIM=icarus ARRAY_REGRESSION_ARGS='--case single --case mvp'
```

`array-regression` runs Python reference/descriptor tests, PyUVM simulation against
actual generated arrays, a focused PyUVM controller test, and Python-driven invalid
parameter elaboration checks. Only Python tests are run: no HDL assertion suite,
lint, formal, synthesis, timing, power or physical signoff. Design Compiler synthesis
is deferred. VCS commands are provided for the server and are not local VCS evidence.
The summary records simulator, profile, seed, coverage, source and verification
hashes; source changes during a campaign invalidate its result.

## Profiles and verification structure

The structured suite separates config, sequence/transaction generation, driver,
monitor, agent, environment, passive scoreboard, independent models and coverage.
It reuses the existing cluster transaction helpers and shared PyUVM components.
The scoreboard observes public ready/valid boundaries, correlates terminal runtime
responses, checks stalled payloads, verifies whole-mask owner isolation and checks
monotonic, exactly-once global completion events. Named hierarchy references are
used only for fault injection.

The integration cases cover one-cluster SRAM/load/compute/store, two-cluster
SRAM/load/compute/NoC/compute/store, permuted logical IDs, disabled clock gating,
simultaneous independent kernels, and an actual partial native configuration commit.
Arithmetic and committed-byte expectations are computed independently in Python.
The two-cluster stream carries different local package IDs and deliberately delays
the store consumer to exercise real NoC backpressure. Configuration writes, CRC
validation, endpoint PREPARE, commit acknowledgements and native tile execution are
real RTL transactions. The concurrent-kernel case uses independent SRAM regions,
owner-scoped counters and disjoint completion masks.

The focused controller test supplies explicit tagged Python cluster responders for
rollback, total rejection, timeout and wrong-tag checks. It qualifies that controller
interface only; it is not counted as actual multi-cluster integration. It also
injects a protected-state fault and requires reset-only sticky containment.

## Runtime contract

Command encodings are the enums in `array_pkg.sv`: QUERY0, ALLOCATE1, CONFIGURE2,
VALIDATE3, COMMIT4, START5, SUSPEND6, RESUME7, DRAIN8, RESIZE9, MIGRATE10, ABORT11,
RELEASE12, COUNTER_SNAPSHOT13, CLEAR_ERROR14, POWER_REQUEST15. Optional commands and
nonzero mapping/QoS/power profiles or flags are rejected without changing ownership.
The interface is repository-local; it does not claim an external mosaic-contracts ABI.

One request reserves the controller until one held terminal response is consumed.
The immutable `i_runtime_manifest_hash` must match `o_manifest_hash`.
Owner, kernel, array package, complete cluster mask, allocation generation and epoch
must match. A kernel's mask cannot be changed through a subset command. Disjoint
kernels can run concurrently, while the management command channel is serialized.
The runtime supplies policy; hardware does not choose which kernel to schedule.

ALLOCATE supplies the last successful **array allocation serial** (zero after reset).
A successful whole-mask reservation advances that serial and publishes it in each
selected record. Failed reservations roll back successful native reservations. Native
cluster allocation generations are separate and must be used in local package/MST
records; a rolled-back native reservation can still have advanced its native serial.
A generation never wraps into a stale allocation. Records are authoritative when
allocated; fatal masks also reserve unhealthy resources until reset.

CONFIGURE captures the per-cluster local package IDs and common context ID. Load
local package manifests through the packed `i_cluster_package_*` channels using the
native architecture hash, local package ID and native allocation generation.
The serialized array configuration root uses `i_cfg_cluster_slot` (descriptor order)
and `i_cfg_array_package_id`, preserving the native command/destination/tag/version/
CRC/epoch fields. It reserves that gateway until its last response is consumed.
Unauthorized/unknown selectors fail closed without a request handshake. Root and
runtime management admission are mutually exclusive. Native configuration errors
are returned by the local root.

Write every inactive image, validate CRCs and PREPARE all six native endpoints.
ARRAY_VALIDATE requires all endpoint acknowledgements plus the local manifest and
captures the per-cluster packed versions. ARRAY_COMMIT issues captured native commit
identities, collects all acknowledgements, then issues native VALIDATE while execution
remains held. START is admitted only after the whole selected set is committed.
Native starts are accepted together. A partial commit, response-identity failure or
transition timeout quarantines the affected allocation; it never reports rollback
of already activated state. Reset and complete reload are required.

The public epoch is eight bits, but this profile explicitly restricts it to native
nonwrapping epochs 0..15. COMMIT advances it; request epochs name the current record.
There is no silent truncation or wrap. Reconfiguration/relaunch requires release and
a fresh allocation; fast in-place switching and active-kernel NoC flush are deferred.
Timeouts bound each controller phase, assuming the common clock continues.

## NoC, completion and memory

The NoC configuration port is a privileged maintenance boundary, usable only while
all clusters are free and management/events are idle. Load/validate/PREPARE/COMMIT its
native image before allocating a communicating kernel. The NoC's fabric package ID
is shared by its flow table and is distinct from kernel array/local package IDs.
Its transport epoch is separate from the full execution identity in the envelope.
Flows use ID1 for endpoint0→1 and ID2 for endpoint1→0, source/destination channel0,
context matching the kernel, native source allocation generation, package-slot0,
class DATA and initial sequence0. Sequences stop before wrap; reconfigure while free.
NoC tables cannot be changed or flushed behind running kernels.

Only clusters in the same owner/kernel/array-package allocation can communicate
through the gateways. Source and received envelopes are authenticated before local
package/epoch rebinding. Declared command-identity namespace fields inside the common
MST stream are translated to the destination package/context/generation/MST epoch;
other common payload bits are preserved. The receiving native MST additionally
requires its admitted store binding. Packages must use compatible native mesh/context
versions. The generator declares reserved mesh ingress/egress lanes; those lanes
are masked at the external boundary. Other lanes remain protocol-neutral system
attachments. This MVP implements scalar/native stream transport on data VC0; it does
not claim all eight array-level traffic protocols or global barriers.

Cluster terminal events contribute once per authenticated kernel epoch. The array
waits for every selected cluster and NoC idle before exporting exactly one kernel
event (type2). Native cluster terminal records are forwarded as type6. Event payloads
are 256 bits and sequence numbers 32 bits to preserve the released native contract.
A protected, backpressured queue and held round-robin grants preserve accepted events.
Duplicate/stale completion, sequence mismatch and queue-integrity faults fail closed.
Critical events use the dedicated ungated control network and do not wait on data VC0.
RELEASE requires native quiescence, empty NoC and consumed events.

Each cluster exposes its three permission-checked external SRAM clients and native
MST descriptor/region/buffer/stream/completion channels, packed in descriptor order.
These are protocol-neutral boundaries, not synthesized cell models or host AXI ports.
An array fatal mask blocks new functional boundary admission and isolates exported
streams; already accepted memory responses may retire. Native root clock gating
remains operational on the common clock, with ungated lifecycle/event control.

See the generated manifest for identities, capacities, topology, domains, source
closure, supported limits and deferred signoff. Four-cluster balanced composition,
heterogeneous/sparse arrays, standalone services, global barriers, migration/resize,
CDC, retention, power gating and DVFS are not implemented by this MVP.
