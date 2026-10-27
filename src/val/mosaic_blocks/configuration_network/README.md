# Configuration network RTL and PyUVM validation

The production implementation is
[`configuration_network.sv`](../../../rtl/mosaic_blocks/configuration_network.sv).
It implements the synchronous configuration transport, endpoint handshake,
ordered completion and coordinated activation contract from the
[specification](../../../../../specs/mosaic-blocks/mosaic-configuration-network/README.md).

Run from `mosaic-cgra`:

```sh
make configuration-network-regression SIM=icarus PYTHON_BIN=.venv/bin/python
```

On the Synopsys server, use `SIM=vcs` and the server's Python environment. VCS
is supported by the runner but was not available for local verification. This
campaign runs Python model checks and cocotb/PyUVM simulations. It does not run
HDL assertions, lint, formal verification, synthesis, timing or power analysis.
Design Compiler synthesis remains a later step.

For one parameter profile (the tile-adapter tests and invalid-parameter checks
still run):

```sh
.venv/bin/python src/val/mosaic_blocks/configuration_network/run_configuration_network_regression.py \
    --sim icarus --build-dir build/icarus/configuration_network/small --case small
```

For the focused canonical-FLUSH/retirement race across every profile:

```sh
CONFIGURATION_NETWORK_FOCUSED_FLUSH=1 .venv/bin/python \
    src/val/mosaic_blocks/configuration_network/run_configuration_network_regression.py \
    --sim icarus --build-dir build/icarus/configuration_network/flush_overlap
```

The coverage report labels this mode `flush-overlap`; it exercises buffered
multicast results and simultaneous retirement/cancellation rather than the full
random command phase. The same scenario also runs in the full campaign.

`CONFIGURATION_NETWORK_JOBS` controls concurrent simulations; the default is four
for Icarus and one for VCS. `--seed` defaults to `20261026`; `--random-cycles`
defaults to 1000 and is a cycle budget for the random command phase in each
network profile. Directed tests run in addition to that budget. The 68-endpoint
profile takes substantially longer than reduced profiles.

## Implementation and reuse

The forward path serializes complete command packets into flits. Independent
branch buffers and multicast forks deliver exactly one copy to each selected
present endpoint. Leaves reassemble and check the complete packet before a
native command can be accepted. Each endpoint has an ordered complete-packet
queue and one outstanding native operation. Separate reverse links arbitrate
with packet locks through the last response flit.

The root reserves a transaction slot on ingress, collects terminal endpoint
results and retires transactions in acceptance order. Within a transaction,
records retire in ascending architectural endpoint ID. IDs can differ from
physical leaf indices. The last record carries success, failure, timeout and
absent masks; `transaction_success` requires all destinations to succeed.
A slot is released when its last record enters the root response FIFO. That FIFO
then owns the record until the master accepts it. Master backpressure can never
reallocate a live record.

The design reuses `stream_fork`, packet-locking `round_robin_arbiter`, `fifo`,
`skid_buffer`, `register_slice`, parity/SECDED protection, `dff`, and the existing
static-mesh queue/link and protected-state helpers. Statistics reuse
`banked_scratchpad_counters`. The dependency list is maintained in
[`dependencies.py`](dependencies.py) and the Makefile; no RTL dependency manifest
is required.

## Supported profiles and descriptors

`TOPOLOGY_PROFILE=0` creates a daisy chain, `1` a generated balanced tree, and
`2` the grouped tree used for a row/column physical layout. All destination sets
are explicit masks; software derives row, column and endpoint-class groups from
the generated endpoint mapping. A profile name does not imply characterized
floorplan timing. Absent-only branches are removed at elaboration.

The implementation supports 1–128 endpoint positions, 1–4 masters, branch factors
2–4 and byte-aligned data/flit widths of 8–256 bits. The campaign exercises 1, 4,
6, 20 and 68 endpoints, multiple masters, permuted IDs, sparse presence, 8/32/64/256
bit links, shallow/deep queues, CRC/readback/multicast feature switches, all three
control-protection settings and both reset modes. The implementation's parameter
bounds are resource guards, not a claim that every Cartesian combination has
been verified.

Each packed table uses the physical endpoint position as its index; entry zero
occupies the least significant bits:

| Parameter | Bits per position | Meaning |
|---|---:|---|
| `ENDPOINT_PRESENT_MASK` | 1 | Physical presence |
| `ENDPOINT_ID_TABLE` | `ENDPOINT_ID_WIDTH` | Unique architectural ID |
| `ENDPOINT_TYPE_TABLE` | `ENDPOINT_TYPE_WIDTH` | Endpoint class; default tile 0, infrastructure 1 |
| `ENDPOINT_CAPABILITY_TABLE` | `2 ** COMMAND_WIDTH` | Bit indexed by canonical command |
| `ENDPOINT_PERMISSION_TABLE` | `OWNER_ID_WIDTH + 4` | Owner, then read/write/admin/privileged-root rights |
| `ENDPOINT_WORD_COUNT_TABLE` | 32 | Native word capacity; default 4 |
| `ENDPOINT_CONTEXT_DEPTH_TABLE` | 32 | Native context capacity; default 4 |
| `ENDPOINT_SCHEMA_TABLE` | 32 | Equal schema required for multicast; default 4 |
| `MULTICAST_GROUP_TABLE` | `NUM_ENDPOINTS` | Allowed peers for a selected endpoint |
| `ENDPOINT_CLOCK_DOMAIN_TABLE` | 1 | Root clock domain, currently zero |
| `COMMIT_DOMAIN_TABLE` | 1 | Synchronous commit domain, currently zero |

Set capacities and schemas to the actual attached backend. The default generic
endpoint geometry is not the tile shell's context-image geometry. Protocol is 1;
flag bit 0 requests privileged access and flag bits 7:1 are reserved. Capability,
permission, geometry, schema, group and presence checks happen before distribution.
A selected absent endpoint produces an explicit `NOT_PRESENT` failure record.

This implementation rejects `SUPPORT_ASYNC_ENDPOINTS=1`, reserved-NoC profile 3,
and packet retry at elaboration. Those options need CDC or reserved-network
proof and integration beyond this synchronous implementation. A tile shell may
bridge its own functional clock domain internally while its configuration port
remains in the configuration-network clock domain.

## Local packet ABI

The repository has no canonical `mosaic-contracts` package. The local v1 enums
live in `configuration_network_pkg.sv`, and the independent Python layout is in
[`layout.py`](layout.py). Canonical commands are NOP 0, WRITE 1, READ 2, VALIDATE 3,
INVALIDATE 4, QUERY 5, PREPARE 6, ABORT_PREPARE 7, COMMIT 8, DRAIN 9 and FLUSH 10.
COMMIT is rejected on ordinary packet ingress and uses the dedicated commit port.
Status encodings are SUCCESS 0, REJECTED 1, TIMEOUT 2, CANCELED 3, NOT_PRESENT 4.
Error codes distinguish packet CRC/frame/correlation failures from native image
CRC/package validation errors; a semantic validation rejection is not a transport
failure.

Fields are packed from least significant to most significant in these orders:

- Command: command, transaction ID, tag, owner, kernel, package, configuration
  epoch, context ID, expected version, word index, write data, byte strobes,
  expected image CRC, destination mask, master index, sequence ID (32), protocol
  (8), flags (8).
- Leaf response: command, transaction ID, tag, endpoint ID, context ID, version,
  read data, image CRC, configuration epoch, status (4), error (8), sequence ID
  (32), protocol (8), prepared (1), committed (1).
- Flit: payload, start (1), end (1), flit index, envelope, packet type (1;
  command 0, response 1). The envelope contains
  destination mask, transaction ID, configuration epoch, sequence ID and master
  index, in that low-to-high order.

Packets are padded with zero bits to an integer number of flits. The highest
32 bits hold CRC-32C over every lower byte, including padding. The polynomial is
reflected `0x82f63b78`, initial/final XOR `0xffffffff`, low byte first. Flits travel
least significant first. CRC checking can be disabled explicitly, while framing,
identity and epoch checks remain active. The receiver checks the expected length
independently of an untrusted end marker.

The root's public completion CRC covers the response body followed by endpoint
type, first, last, transaction success, failure mask, success mask, timeout mask
and absent mask, then zero byte padding. Aggregate masks are zero before the last
record. It protects the final completion representation, not just the leaf packet.
A separate internal flush generation prevents the public epoch from reviving an
old buffered record on wraparound; internal generation exhaustion requires reset.
Sequence IDs are private non-reused correlation tokens until reset; transaction
IDs are their low bits. Admission stops at sequence exhaustion.

## Native endpoint and recovery contract

All flattened endpoint buses use `e * FIELD_WIDTH +: FIELD_WIDTH`. A request is
accepted only on valid and ready. Native responses must echo transaction ID,
sequence ID and configuration epoch and remain stable until consumed. The
endpoint owns configuration storage, byte merging, image CRC, semantic validation,
active-context immutability and context-version semantics. A successful response
must represent completed work. QUERY is read-only. PREPARE must validate and
retain the complete context/version/package/owner/kernel/image-CRC identity.

After reset, the root asserts cancellation and blocks new requests until every
present backend acknowledges that all earlier native work and responses have
drained. The same rule applies during flush and transport recovery. A cancel
acknowledgement is a guarantee that no earlier native response can arrive later;
simply clearing an adapter's local valid bit is insufficient. The handshake is
bounded by the configured transaction timeout.

Flush advances the configuration epoch once, discards transport assembly and
native ownership, invalidates prepared records and returns one ordered new-epoch
`CANCELED` result for every unretired destination. Already buffered records remain
owned and become cancellation records too. Canonical FLUSH adds its successful
control completion after cancellation. Flush does not undo an accepted memory
write; an interrupted image must be fully rewritten and revalidated. Drain blocks
new ingress while allowing accepted work and responses to finish. `i_resume`
reopens a drained, idle network.

## Prepare, commit and execution hold

Ordinary configuration traffic never activates a context. The dedicated commit
request must match the complete armed set and its saved package/owner/kernel and
per-endpoint context/version identities. The root asserts execution hold before
it sends one simultaneous commit pulse to every synchronous selected endpoint.
It waits for independent acknowledgements and compares actual active identities,
including image CRC and commit epoch. It keeps execution held after success until
`i_execution_release && i_release_safe` is explicitly accepted.

An incorrect, missing or timed-out activation acknowledgement enters fail-stop.
Flush cannot establish rollback after activation may have occurred, and execution
stays held. Power/retention loss disarms the affected prepared endpoint. Power loss at an
active endpoint latches execution hold; power restoration alone cannot release it. Unknown
control fails closed. Protected control storage uses no protection, parity, or
SECDED; an independent sticky integrity latch preserves fail-stop even if damaged
control storage cannot update. Test/scan modes block ingress and keep endpoint
clock hints enabled. Clock-enable outputs are activity hints; endpoint isolation,
retention and actual clock-gate integration remain the enclosing system's job.

## Tile-shell adapter

[`configuration_network_tile_adapter.sv`](../../../rtl/mosaic_blocks/configuration_network_tile_adapter.sv)
translates one canonical leaf to the released tile-shell configuration port:
WRITE→0, READ→1, VALIDATE→2, activation→3, INVALIDATE→4, QUERY→5. The tile must
already have its runtime owner/kernel allocation. Connect actual power-safe,
quiescence, validated-context bitmap and active-context/version/owner/kernel
status; the adapter must exclusively own the shell's configuration ingress.
Use identical context/data/version geometry on both sides.

The adapter queries the shell's actual version before WRITE, VALIDATE or PREPARE.
It binds the loading package at the first successful write, rejects changes
within that loading generation and records the validated identity after successful
validation. PREPARE never sends
native activation. Commit launches activation on the common fabric commit edge
and acknowledges only after the native response and matching active status.
Cancellation drains outstanding native operations and marks images dirty; only a
full byte rewrite followed by validation clears that condition.

A separate PyUVM conformance test checks the shell opcodes and its per-write
version increments, readback, validation, rejected stale versions, response
backpressure, prepare without activation, activation identity, native cancellation
drain and dirty-image rewrite. This uses a native protocol model; it is not an
integrated simulation of a complete tile, fabric or physical implementation.
Other infrastructure backends attach through the same canonical endpoint contract
and must implement their own image semantics.

## Evidence and counters

The campaign emits `summary.json`, per-profile logs, `coverage.json`, source
hashes, parameter guard diagnostics and `contract.json` with the actual generated
parent/child/route/buffer tables, endpoint descriptors, packet geometry and
commit/recovery assumptions. Tables are serialized as hexadecimal strings to
avoid integer conversion limits. Source hashes must remain unchanged throughout
the campaign for a PASS. Timing and energy fields explicitly say
`NOT_CHARACTERIZED`.

The passive scoreboard keeps separate accepted-request, expected-native and
endpoint-reference ledgers. It checks complete request capture, byte masking,
exactly-once destination accounting, ordering, root record CRC, aggregate masks,
stalled-output stability, prepared identities and execution hold. Directed fault
probes exercise CRC corruption at every command-flit position, framing, unknown
controls, protected-state faults, dropped native responses and partial commit.
Coverage goals describe checked scenarios; they do not claim the specification's
complete formal, physical, CDC or cross-product release coverage.

Counter indices are: 0 accepted transactions; 1 root command flits; 2 root response
flits; 3/4 all forward/reverse link transfers; 5/6 native requests/responses;
7 records enqueued for retirement; 8 records consumed; 9 commits accepted;
10 commits completed; 11 failed-commit cycles; 12 flush completions; 13 flushing
cycles; 14 execution-held cycles; 15 idle cycles; 16 admission rejections;
17 multicast transactions; 18 selected present destinations; 19 timeout events;
20 packet-CRC errors; 21 frame errors; 22 response errors; 23 stalled masters;
24 stalled retirement cycles; 25 accumulated transaction occupancy;
26/27 accumulated command/response queue occupancy; 28 accumulated armed endpoints;
29 drain cycles; 30 native request stall cycles; 31 native response stall cycles.
All are saturating 32-bit observations. Select an index with `i_counter_index`
and assert `i_counter_read`; the response is valid with the associated value.
