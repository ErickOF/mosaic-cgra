# System RTL and PyUVM validation

The synchronous `System-RTL` implementation follows the
[system specification](../../../../../specs/mosaic-blocks/mosaic-system/README.md)
using one real generated array. It reuses released clusters, BCT/MST execution,
SRAM banks, configuration roots, NoC routers/TNIs, native memory bridges,
round-robin arbitration, protected state and queues, counters, parity and ECC.
System policy remains in software. The core has canonical interfaces and contains
no AXI, APB, TileLink or board-specific bus signals.

```sh
make system-generate
make pyuvm SIM=icarus COCOTB_TOPLEVEL=system
make system-regression SIM=icarus
# Same Python/PyUVM campaign on the licensed server:
make system-regression SIM=vcs
# Select real-array profiles:
make system-regression SIM=icarus SYSTEM_REGRESSION_ARGS='--case single --case mvp'
```

Only Python tests run: independent Python model tests, PyUVM simulations against
actual RTL and Python-driven invalid-parameter elaboration tests. HDL assertions,
lint, formal, synthesis, protocol compliance and physical/power signoff are not run.
Synthesis is deferred to Design Compiler. VCS commands are provided for the server;
local Icarus results are not VCS evidence.

## Qualified composition

| Profile | Clusters | Memory data | Buffers | Command/event depths |
|---|---:|---:|---:|---:|
| `minimal` (control/fetch only) | 1 MVP | 64 bits | 1 | 1 / 1 |
| `single` | 1 MVP | 128 bits | 3 | 1 / 1 |
| `mvp` | 2 MVP | 128 bits | 4 | 2 / 8 |
| `mem64` | 1 MVP | 64 bits | 3 | 1 / 1 |
| `maxqueues` | 2 MVP | 128 bits | 8 | 8 / 32 |

One active kernel owns the whole generated array. Memory arbitration is serialized:
program/configuration fetch and data transfer never alias a live memory ID. There
is one external memory port and one outstanding request. A program fetch is one
256-byte read burst; data movement uses single memory beats split into native
64-bit SRAM operations. No wider parallel-memory or reordering claim is made.

Balanced four-cluster systems, concurrent kernels, hardware runtime, system-control
clock gating, external protocol adapters, CDC/asynchronous reset, coherence, IOMMU,
trace, direct-result registers, strided/unaligned/chained DMA, retention, power
gating and DVFS are unavailable. The generator rejects those profiles. Native
array clock gating remains operational. `i_test_mode` and scan changes require an
idle, drained system; they do not provide live protocol cancellation.

## Boot and platform obligations

All boundaries share `i_clk` and active-low synchronous `i_rstb`. The platform must
hold `i_memory_reset_done` low until old memory/fence responses have drained or
been discarded by coordinated reset, then assert it. Reset does not roll back
committed external writes or erase DRAM. A matching generated array manifest is
also required before doorbells are admitted. Discovery reads remain available.
Loss of the reset acknowledgement or manifest after boot is fatal.

The platform supplies trusted requester/privilege attributes, an ordered physical
memory service and a visibility fence service. The baseline is noncoherent:
software cleans input/program caches before handing ownership to DMA and invalidates
output caches after ownership returns. Hardware cannot prove software performed
cache maintenance. Fence responses mean platform visibility has completed, not
just that a request was received. Wrong IDs/tags, unknown controls or bad framing
never retire an outstanding transaction.

A stalled request, write beat, response or event stays stable. Accepted read bursts
are drained through their final beat. Writes complete only on the matching terminal
write response. Offered memory bundles are preserved on timeout for safe retirement;
no write is retried. The fatal interrupt is immediate, while complete recovery
requires reset and the platform memory-reset acknowledgement.

## Register and requester contract

`src/gen/system/generated/registers.json`, `system_registers_pkg.sv` and `system.h`
are generated from the same address map. Offsets are relative to base zero. Reads
and writes are aligned 32-bit operations. Full strobes are required except for
`INTERRUPT_MASK`, which permits byte updates. Reserved fields reject nonzero writes;
RO writes return permission errors, unmapped addresses return decode errors and
WO reads return zero. Side effects occur once at request acceptance. Every accepted
request has exactly one held terminal response with its original eight-bit tag.

Requester ID is the owner ID; IDs zero and 65535 are reserved. Buffer registration
requires privilege >= 4. Global IRQ/counter/error/drain control requires requester
1 and privilege >= 4. Other owners cannot mutate a held shadow bank, inspect or
acknowledge another owner's queue head, or submit another owner's program buffer.
A platform with multiple untrusted processes must enforce these attributes upstream.

Important register groups:

- `0x0000`: identity, versions, geometry, queue limits, boot/state and system/array hashes.
- `0x1000`: program buffer, offset, count/generation shadows, doorbell, status,
  shadow discard and active-program cancellation.
- `0x2000`: native MST epochs, native allocation generations and SRAM generations.
  Array and native epochs are separate namespaces; software reads these fields
  after commit/start before building native MST descriptors.
- `0x3000`: six-word buffer shadow, atomic registration, shadow discard, status
  and fenced host/DMA ownership transitions.
- `0x4000`: interrupt mask/status, event count, explicit sequence ACK and 16-word head.
- `0x5000`: explicit coherent snapshot and eight words of four 64-bit counters.
- `0x7000`: sticky first error, fatal flag, address/identity, recoverable-error clear,
  drain and the last native response snapshot.

Buffer shadows are index, base-low, base-high, size, owner/kernel (16 bits each),
and generation/permissions (generation bits 15:0, read bit16, write bit17).
All six words must be written before `BUFFER_COMMIT=1`. Bases align to 256 bytes,
start at or above `0x100000`, cannot overlap another registered region and cannot
wrap. A fresh region uses generation one; replacement advances generation without
wrap and requires host ownership, no reservation and no array allocation.
Replacing another owner's existing record additionally requires the administrator.

`BUFFER_FENCE` writes the buffer index in bits 7:0 and target DMA ownership in bit8
(one for host→DMA, zero for DMA→host). The request returns submission status; a
fence event reports retirement. The region remains reserved through that event.
Output ownership cannot return before a full successful output transfer. Partial,
failed or canceled transfer buffers become invalid and require reset/reinitialization.

## Immutable memory-resident programs

MMIO carries descriptor references, not full configuration images. Register a
readable program buffer, clean caches, fence it into DMA ownership, and write
`PROGRAM_BUFFER`, 256-byte-aligned `PROGRAM_OFFSET`, and
`PROGRAM_COUNT_GENERATION` (count bits15:0, generation bits31:16). Write
`PROGRAM_DOORBELL=1`. Admission snapshots these fields and reserves the buffer and
protected command-queue capacity. Later shadow writes cannot change queued work.
Program generations advance per buffer, beginning at one and stopping before wrap.

Each record is exactly 256 little-endian bytes:

| Bytes | Field |
|---|---|
| 0–3 | Magic `MSYS` (`0x5359534d`) |
| 4–5 | Schema one |
| 6 | Record kind |
| 7 | Flags: required output-buffer mask for START; zero otherwise |
| 8–9 / 10–11 | Owner / kernel |
| 12–15 | Array package ID |
| 16–17 | Submitted program generation |
| 18 / 19 | Array execution epoch / native cluster slot |
| 20–21 / 22–23 | Exact payload bit count / reserved zero |
| 24–25 / 26–27 | Native correlation tag / reserved zero |
| 28–31 | CRC32C over all 256 bytes with this field zero |
| 32–63 | Generated system manifest hash |
| 64–255 | Payload with all unused high bits zero |

Kinds are RUNTIME0, CONFIG1, PACKAGE2, MST_REGION3, MST_BUFFER4, MST_DESCRIPTOR5,
NOC_CONFIG6 (two-cluster profile only), LOAD7, STORE8, WAIT_ARRAY9, FENCE10 and
SESSION_END12. SRAM11 is an internal bridge command and is rejected in host records.
`descriptors.json` publishes exact native field offsets/widths and response layouts;
`model.py` demonstrates packing. Canonical array owner/kernel/package/tag fields
are injected from the checked header. Native package IDs, versions and formats
retain their native contract and are independently checked by the real array.

LOAD/STORE payloads contain buffer index at bit0 (8 bits), external offset at bit32
(32), native byte address at bit64 (32), length at bit96 (32), SRAM generation at
bit128 (16), and region ID at bit144 (3); all reserved bits are zero. Transfers are
whole memory beats, aligned in both spaces, at most 4096 bytes and within both
registered external bounds and native SRAM capacity. LOAD needs read permission;
STORE needs write permission. Both require matching owner/kernel and DMA ownership.
The program buffer cannot also be the transfer buffer. A STORE for a live kernel
waits for verified array completion before issuing SRAM reads; an input LOAD cannot
modify that kernel's inputs while it is executing. Transfer identity must match the
live kernel, and native dispatch also checks the current array execution epoch.

START requires every matching data input buffer (readable, excluding the program
buffer) to have completed a full input LOAD in the current DMA ownership interval.
It snapshots the required output mask and clears prior output completion state.
One kernel is live until release; a second START is rejected. WAIT_ARRAY has no
payload and waits for the matching real array terminal event. FENCE has an eight-bit
buffer index and returns it to host ownership. SESSION_END sets or clears the
selected native MST session-end bit from payload bit0. Successful RELEASE clears
the persistent session-end bindings before another kernel is admitted.

The demonstrated sequence is discovery → registration/cache clean/fences → NoC and
array allocation/configuration/validate/commit → input LOAD → START → read native
identities → MST descriptors/session close → WAIT_ARRAY → output STORE → fences →
one host terminal interrupt → release. Native image CRC and endpoint PREPARE/commit
are real configuration-root transactions. Native image generation reuses released
cluster/array codecs; expected numerical results are independently computed.

## Completion, events and recovery

Array compute completion is captured internally and cannot directly report host
success. Host completion requires the exact kernel/package/epoch, the complete
output transfer, matching committed external write responses, and successful
platform fences returning every required output to host ownership. It is emitted
once. RELEASE is blocked until that terminal outcome is published.

A 512-bit protected queue preserves accepted event order. Records contain type,
severity, source, owner/kernel/package, epoch/context/generation, global 32-bit
nonwrapping sequence, full 256-bit payload, native sequence, tag/detail and timestamp.
Types are kernel-terminal1, program-terminal3, fence-terminal5 and native array
records `0x80 | native_type`. A program event also identifies its source buffer and
last record index. `EVENT_HEAD` remains fixed across multiword reads. Only an ACK
of its exact sequence by its owner or administrator removes it.

IRQ asserts for any unmasked queued class, including behind a masked head. Masking
never discards events. Queue-full backpressures producers; a pending completion
cannot be withdrawn or overwritten. Fatal status raises an unmaskable level IRQ
independent of queue capacity. First-error evidence survives later faults.

Cancellation applies to the current program: it stops new records and drains an
accepted burst/beat. It does not undo committed writes or automatically implement
array-kernel rollback. Canceled/failed output is invalid; a live kernel requiring
abort may need coordinated reset under the native array policy. Queue-full,
malformed descriptors and stale generations are explicit admission/program errors.
Timeout, identity mismatch and protected-state corruption are fail-stop faults.
Clearing the underlying injected fault or writing ERROR_CLEAR cannot clear fatal.
Reset plus memory/fence drain acknowledgement is the recovery boundary.

Drain blocks new doorbells while queued and accepted operations retire. It does
not discard events, responses, snapshots or allocated kernels; software consumes
those obligations and releases resources explicitly. Counter snapshots capture
accepted controls, external read bytes, committed external write bytes and queued
events together. Native status outputs are observability, not host completion.

## Verification structure and evidence

The suite separates configuration, transaction generation, shared driver/monitor,
agent, environment, passive scoreboard, coverage and independent models. It reuses
the shared PyUVM library and released cluster transaction helpers. Functional
control uses public interfaces. Named hierarchy access is limited to integrity
fault injection in the focused core campaign.

The minimal profile checks discovery, registers, fences, descriptor fetch and real
array QUERY with one buffer; it does not claim a compute/DMA workload. The other
full-system profiles execute real SRAM/compute pipelines and, for two clusters,
real NoC transport, comparing exact committed external bytes with independent
Python arithmetic. The checker separately accounts native MST reads/writes,
control responses, buffer bounds/permissions, live IDs, write acknowledgements,
backpressure and fences. The host services interrupts rather than continuously
polling for array progress.

The focused core test uses explicit Python array peers to qualify descriptor
rejections, stale generations, DMA bounds, cancel/drain, command-queue full/wrap,
event backpressure and masked-head IRQs, delayed writes/fences, timeout/late response,
wrong memory/native identity, sticky protected-region faults and reset recovery.
This is core-interface evidence, separate from actual-array integration.

`summary.json` records exact profiles, seeds, coverage, source/verification hashes
and simulator results. Source changes invalidate the campaign. Generated wrappers,
software/register artifacts and the default Makefile entry are checked separately
for reproducibility. The unsupported platform and physical profiles have no passing
release claim.
