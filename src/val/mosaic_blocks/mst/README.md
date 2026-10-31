# Memory and Stream Tile (MST)

This suite implements the [MST specification](../../../../../specs/mosaic-blocks/mosaic-mst/README.md)
with the production `mst` wrapper, its real tile shell, and structured PyUVM
agent, driver, passive monitor, scoreboard, sequences, and coverage collector.
The memory and DMA peers are Python testbench endpoints. They do not replace
any RTL in the tile.

```sh
make pyuvm SIM=icarus COCOTB_TOPLEVEL=mst
make mst-regression SIM=icarus
# On the licensed server:
make mst-regression SIM=vcs
```

`MST_RANDOM_CYCLES` selects the number of randomized complete transfers per
profile; the default is 30, in addition to directed scenarios. `MST_SEED`
selects the reproducible seed. `MST_JOBS` controls parallel profile execution.
The runner also accepts `--case`, `--random-cycles`, and `--build-dir`.
Simulation logs, parameters, result XML, coverage, source hashes, and the
campaign summary live under `build/<sim>/mst/regression/`.

Only Python tests and Python-driven simulator elaboration checks are run.
HDL assertions, formal verification, lint, physical implementation, and
synthesis are outside this campaign. Design Compiler synthesis is deferred.
A missing simulator or license is reported as `NOT_RUN`.

## Implemented profile and reuse

The balanced repository-local v1 profile implements all eight transfer modes:
scratchpad to tile stream, tile stream to scratchpad, nonoverlapping local copy,
DMA to tile stream, tile stream to DMA, DMA to scratchpad, scratchpad to DMA,
and tile stream forwarding. It supports linear, signed 1D and signed 2D affine
patterns, byte-level unaligned accesses, integer conversion, event-controlled
start, chaining, buffer roles, cancellation, and concurrent independent
load/store channels. Datatype values 0 and 1 identify opaque and integer payloads;
conversion uses the explicit signedness and element-width controls.

| Existing RTL | MST use |
| --- | --- |
| `tile_shell` | Context memory, CRC/validation, owner, version, lifecycle, streams, power and debug |
| `load_engine`, `store_engine` | Tagged logical requests and ordered per-channel retirement |
| `agu`, `dma_engine_bounds` | Actual signed affine addresses and complete rectangle bounds |
| `dma_engine_command_queue` | Per-channel FIFO, directory, ordered cancellation tombstones |
| `data_aligner` | Adjacent-word read alignment and write-window placement |
| `width_converter`, `packer` | Positional shell/memory width adaptation and explicit integer conversion |
| `stream_formatter` | Canonical input validation and output framing |
| `round_robin_arbiter` | Command, completion, response, and physical endpoint arbitration |
| `tile_shell_queue`, `tile_shell_codec` | Protected elastic payloads and striped parity/SECDED |
| `banked_scratchpad_state`, `banked_scratchpad_counters` | Protected control records and saturating instrumentation |

`mst_fragment_adapter` translates aligned synthetic engine positions into
physical scratchpad fragments. Reads fetch aligned complete memory words and
retain only the declared element bytes. Region base and exclusive limit must
therefore align to a memory word. Writes use naturally aligned power-of-two
subword fragments with right-justified data and address-positioned strobes,
matching the banked-scratchpad interface. Responses must echo the full opaque
tag and immutable identity. The write response supplies the exact number of
committed bytes, including when it reports an error.

Memory and shell widths are powers of two from 8 through 256 bits. A position
contains `2**lane_log2` integer lanes of `8 * 2**element_log2` bits. Each source
and destination position must fit `MAX_ELEMENT_BYTES` and the wider transport.
A position may span several shell beats; partial positions never coalesce across
position boundaries. Inner/outer counts count positions. Unsupported datatype
or descriptor modes are rejected before effects. Copy overlap is checked using
the full affine interval hull; disjoint sparse patterns with overlapping hulls
are conservatively rejected.

There are at most eight combined load/store channels, with up to eight physical
or stream endpoints of each kind. This release selects one predicate input,
one predicate output, one event input, and one event output. Asynchronous
configuration uses the existing shell CDC adapter; scratchpad and DMA endpoints
share the core clock. The following enabled profiles fail a named elaboration
guard because their released adapters are not present: 3D, circular, indexed
scatter/gather, atomics, multicast, direct memory proxy, and asynchronous
scratchpad/DMA clocks. These features are not silently advertised.

No throughput or physical power claim is made. Physical requests use registered
offers, arbitration, and per-command engine initialization. Independent commands
can overlap; the implementation deliberately reserves terminal credits before
consuming their sources.

## Public v1 ABI

The repository has no external contract package. Encodings are versioned in
`mst_pkg.sv`; parameter-dependent packed records remain local to their modules.
[`layout.py`](layout.py), [`model.py`](model.py), and [`defaults.py`](defaults.py)
define executable field order, packing helpers, and exact public port dimensions.
Fields in each catalog are listed from least-significant bit upward. Unused
high context, stream, and event bits are zero.

Descriptors use one ready/valid request and seven packed groups:

| Group | Contents |
| --- | --- |
| `identity` | Command ID, generation, owner, kernel, package, context, version, allocation, epoch |
| `mode` | Transfer kind, addressing kind, load channel, store channel |
| `source`, `destination` | Space, endpoint, region/generation, optional buffer/generation, base and signed strides |
| `format` | Source/destination element logs, lane log, datatype, signed, saturate, reverse, EOS |
| `events` | Immediate/single/OR/AND start, mask, dependency ID/generation, completion event, chain successor |
| `control` | Inner/outer counts, priority hint, timeout override, cancelable |

Transfer encodings are 0 through 7 in the order listed above. Address kinds
0/1/2 are linear/1D/2D. Spaces 0/2/3 select scratchpad/tile stream/DMA stream.
Start kinds 0/1/2/3 select immediate/single event/OR/AND. The dependency identity
must match owner, kernel, package, allocation, context/version, execution epoch,
and the descriptor's dependency command/generation. Sequence numbers are
strictly increasing per event ID in an execution epoch. Start events are
one-shot. Chained completion events target the declared successor identity;
a failed predecessor propagates an error dependency.

A context image, low bits first, contains schema (8 bits, value 1), package,
allocation generation, automatic-command flag, terminal-session flag, load mask,
store mask, region mask, and the packed descriptor. Its identity is populated
from the shell at launch. With automatic-command clear, the descriptor template
is ignored and the host submits manual commands. Set `i_session_end` or `i_drain`
to close a manual session after admission. A terminal automatic context closes
once its command is admitted and all effects/reports retire.

Region/buffer programming has its own request and held response. Programming is
accepted only at global quiescence. Regions bind owner, kernel, allocation,
space, half-open byte interval, access permissions, channel mask, and buffer
mask. Reprogramming a valid entry requires a strictly newer generation. Buffers
also bind package/context and a role state. Initial states are FREE (0) or FULL
(2); a fill claims FREE -> FILLING (1) -> FULL, and a consumer claims FULL ->
CONSUMING (3) -> FREE. Claim and terminal transition each increment generation.
A partial failed effect leaves ERROR (5). Commands reserve sufficient generation
space before effects. Runtime configuration is a privileged integration path;
its caller must be authorized to program the currently allocated tile.

Stream metadata contains context, version, full identity, byte keep, canonical
byte-lane mask, datatype, endpoint channel, first/last, row-first/row-last, EOS,
error, element log, and lane log. Event metadata retains the shell's
kind/context/kernel prefix, then event ID, 16-bit sequence, full identity,
error, and 32-bit terminal payload. Kind 7 is a body event. The completion event
payload packs low 20 bits of committed destination bytes, overflow, partial,
8-bit error code, and 2-bit status. Full-width accounting is always available in
the separate completion record.

`o_completion_*` reports success (0), failure (1), cancellation (2), or
containment (3), with identity, channel, first error, useful read bytes, committed
destination bytes, complete destination positions, partial/unknown effects,
and conversion overflow/saturation. Status and data remain stable under
backpressure. The duplicate key is owner/command/generation, retained until
both completion and optional terminal event have been externally accepted.

Cancellation stops new logical effects while draining already advertised and
accepted physical requests. Buffered, externally unaccepted shell data can be
discarded by coordinated flush. Completion accounting includes only accepted
stream bytes and acknowledged memory bytes. Timeout first requests cancellation;
a missing response past the cancellation deadline produces containment with
unknown effects and prevents tag reuse. A stale or malformed response is also
contained. Expected command failures do not stop unrelated channels.

A reset must be coordinated with the endpoint peers so old transactions cannot
return into a fresh reset epoch. Flush drains old obligations before advancing
the epoch; it does not cancel accepted writes in the memory system. Buffer
ownership becomes ERROR when partial effects make its contents uncertain.
Retention/save/isolation handshakes remain physical integration hooks through
the shell. The RTL does not model supply loss or implement a physical retention
cell. `BODY_DRAIN_EVENTS=1` lets this tile finish terminal reporting in READY
after runtime termination; other shell users retain the default behavior.

## Instrumentation and checks

Owned read-only debug addresses `0x80 + index` snapshot 32-bit saturating
lifetime counters. Indices 0..15 count accepted descriptors, rejections, starts,
terminal records, completion accepts, found/not-found cancels, timeouts, partial
terminals, rejected events, event FIFO departures, fatal cycles, scheduler wait
cycles, flush cycles, suspend-request cycles, and resume pulses. Indices 16/17 count useful source and committed destination bytes; index 18
counts request cycles with an asserted scratchpad conflict hint. Indices 19..31
are reserved. Per-channel indices `32 + 8*channel` count starts, accepted physical
requests/responses, external input/output accepts, conversion overflow/saturation,
and physical request stall cycles. Peak occupancies start at index 112: each
channel's command queue, completion queue, terminal event queue, and total
physical outstanding count. Reset is the only counter clear.

The campaign checks equal, narrower and wider transports, byte and 256-bit
profiles, depth-one and odd resources, multiple channels, parity/SECDED,
feature removal, asynchronous configuration, retention handshakes, and short
timeout containment. Directed and randomized transfers check addresses, bytes,
framing, metadata, complete counts and ordering against the independent Python
oracle. Negative cases cover malformed metadata, unknown descriptors, permission,
mode and count failures, overlap, duplicate identity, stale generations/tags,
queue capacity, cancellation, flush, suspension, and termination. Backpressure
checks run on held completions, events, streams and physical request offers.
Protected control probes exercise correction and fail-stop containment. Model
unit tests use hand-calculated affine, packing and conversion examples.

The campaign hashes the RTL dependency closure, local verification, shared
PyUVM helpers, reused shell Python helpers, and Makefile. A result cannot pass
if those sources change during execution. Synthesis and physical signoff remain
separate Design Compiler and downstream implementation work.
