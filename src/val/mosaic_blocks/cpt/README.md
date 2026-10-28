# CPT Python functional validation

This suite exercises `src/rtl/mosaic_blocks/cpt.sv` through the actual released
`tile_shell`. It implements the repository-local fixed-width CPT-Local and
CPT-Cluster baseline from `specs/mosaic-blocks/mosaic-cpt/README.md`. The source
profile and interface catalog are in `src/gen/cpt`; no external `mosaic-contracts`
package or dependency JSON manifest is required.

```sh
make cpt-generate
make pyuvm SIM=icarus COCOTB_TOPLEVEL=cpt
make cpt-regression SIM=icarus
# Use the same Python campaign on the licensed simulator server:
make cpt-regression SIM=vcs
```

`CPT_REGRESSION_BUILD`, `CPT_SEED`, `CPT_RANDOM_CYCLES` (minimum 1000),
`CPT_JOBS`, `COMPILE_ARGS` and `SIM_ARGS` select campaign settings. Individual
cases can be selected with the runner's `--case` argument. The runner uses the
repository Python interpreter and the common `mosaic_uvm` simulator/evidence
helpers. Every profile must execute exactly one decorated `CptTest`.

## Composition and execution

The wrapper has exactly the public tile-shell ports, reports tile class 4, and
reuses the shell's configuration, CRC32C, ownership, lifecycle, queues, protection,
power controller, counters and single architectural context sequencer. No host,
configuration or participant-control side channel is added.

The body composes the released `predicate_unit`, `scalar_alu` restricted to exact
comparisons, `register_file` for typed control values, `loop_controller`,
`event_barrier` with its mutation arbiter, `round_robin_arbiter`, `packer` for signed
index and unsigned ordinal extension, protected shell queues, `counter` and
`performance_counters`. Network blocks remain external integration peers.

One command owns the command engine at a time. It reserves its result, predicate
branches and optional event before mutating state. Predicate branches hold their
own pending bits, so a stalled destination cannot duplicate another branch.
Commands retire in acceptance order. Autonomous event ingress, wait completion,
barrier release, loop framing and action transactions can progress concurrently.

The body uses enabled cycles rather than a generated clock. Native validation,
response pipelines, egress and live timeout counters keep the body clock eligible.
Input stalls and output stalls use the shell's documented stall-bit meanings.

## Context image

A complete image has a 512-bit header followed by `MAX_LOOP_DEPTH` loop-level
records. `CONFIG_WORD_COUNT` is the ceiling of this size divided by 64. Every word
is written using `CFG_WRITE`, checked by CRC32C and `CFG_VALIDATE`, then exposed
atomically by `CFG_ACTIVATE`. Active image writes are rejected by the shell.
Unused bits are zero. The header fields are:

| Bits | Field |
|---|---|
| 15:0 | Local schema magic `0xc701` |
| 19:16 | Configured command class; 8 selects the metadata class dispatcher |
| 47:32 | Permitted predicate lane mask |
| 63:48 | Predicate output branch mask |
| 79:64 | Enabled event-ID mask |
| 95:80 | Nonzero transport epoch |
| 127:96 | Action progress timeout in enabled cycles; zero disables it |
| 143:128 | Remote participant target mask |
| 159:144 | Validated remote package version |
| 175:160 | Remote route version |
| 183:176 | Active loop depth |
| 191:184 | Loop initiation interval, at least one |
| 199:192 | Exported loop-level mask |
| 207:200 | Loop completion event ID |
| 239:208 | Optional command retirement limit; zero means unbounded |
| 240 | Enable finite local context progression |
| 241 | Terminal context rather than progression |
| 255:248 | Next resident context ID |
| 263:256 | Permitted command-class bitmap |
| 271:264 | Reserved control-type policy selector (0 through 6) |

The remaining header bits are zero. Each level record contains signed initial,
bound and step (`INDEX_WIDTH` each), unsigned trip count (`TRIP_COUNT_WIDTH`),
2-bit mode and 3-bit comparison in that order, least significant field first.
Level zero is innermost. Inactive levels contain zero. Native loop validation
checks mode, step, bounds, induction overflow and total-count overflow before `CFG_VALIDATE` succeeds and repeats its checks when installing the active
package.

Context transitions wait for command, loop, event, barrier and action obligations
to retire. The shell owns resident context identity and version. The body does not
create a second architectural sequencer. Working predicates, control registers,
event state and sequence history belong to the active context version and are
invalidated at a context switch; resident images belong to the shell allocation.

## Command inputs and outputs

Data input zero carries command tokens. Metadata bit 60 optionally joins a token
from data input one, using that token's low 32 bits as operand B. The released
`stream_join` consumes both inputs atomically. Metadata bit 61 selects predicate
input zero or one; unselected inputs are not consumed by the body. Data payload bits 31:0 and 63:32 contain
control operands A and B. Payloads are exact integers, without implicit formats.
Data metadata bits `[CI-1:0]` and `[CI+:16]` carry shell context and version.
The command overlay is:

| Bits | Field |
|---|---|
| 35:32, 39:36 | Class and opcode |
| 43:40, 47:44, 51:48 | Predicate/control source A, source B and destination |
| 52, 53 | Predicate write enable and signed comparison |
| 54, 55 | Require external predicate token and false-token policy |
| 56, 57 | Select typed control-register operands A/B for comparison |
| 58, 59 | Predicate LOAD uses external lanes; wait consumes matched counts |
| 60, 61 | Join operand B from data input one; select predicate input port |
| 79:64 | Predicate lane mask or wait event mask |
| 87:80, 95:88 | Object ID and secondary event ID |
| 103:96 | Association/action/run/waiter tag |
| 107:104, 115:108 | Barrier generation and participant ID |
| 119:116, 120 | Control-register type and terminal command |

Unused input overlay bits are zero. A required external predicate arrives through
the selected predicate input. Its token is consumed atomically with command issue. A valid
all-false token suppresses every local and remote effect; the optional false-result
policy emits a data result marked suppressed plus valid-false predicate branches
for predicate/compare classes, or a false forwarding event for other classes.

Class encodings are predicate 0, compare 1, loop-config 2, loop-control 3, event 4,
barrier 5, action 6 and status 7. Predicate opcodes are the released predicate-unit
CLEAR, SET, LOAD, PASS, NOT, AND, OR, XOR and INVALIDATE (0 through 8).
Comparisons are EQ, NE, LT, LE, GT, GE, EQ-zero and NE-zero (0 through 7), with
signedness selecting signed or unsigned ordering. Required invalid predicate lanes
and wrong-type/uninitialized control-register reads return an error result and
cannot update architectural state.

Loop-config opcode zero acknowledges the immutable image's configuration.
Loop-control opcodes 0/1/2/3 start/pause/resume/abort the native loop and use the
command tag as run ID. Event opcodes are post 0, acknowledge-one 1, clear-all 2,
arm ANY 3, arm ALL 4, cancel matching waiter 5 and emit a payload-forwarding record 6.
Barrier operations are configure 0 (operand A is the participant mask), arrive 1
and query generation 2. Status operations read/write/invalidate a typed register
(0/1/2), read event count 3, read barrier generation/arrivals 4 and read counter 5.
Register types 1 through 6 represent bound, threshold, mask fragment, status,
event payload and software control values. They are checked before every read.

Every unsuppressed command returns one data result with marker `0xb` in bits
127:124, error at bit 121, suppressed at bit 122, and its original tag/identity.
Predicate and comparison commands additionally produce the configured branch
copies. Predicate metadata carries context/version, per-lane validity at bit 32,
and association tag at bit 48. A valid false lane remains distinct from an
invalid lane.

## Loop token framing

A token frame contains its 64-bit linear iteration header, followed by the selected
levels' signed index and unsigned ordinal beats in ascending level order. Metadata
contains first/last level masks at bits 32/40, run ID at 48, native configuration
epoch at 56, beat index/count at 72/76, first/final at 122/123 and marker `0xc`
at 127:124. The body holds the native loop's iteration-ready low until the final
beat transfers at the public data output. Admission to a shell output queue alone
does not advance the loop. No iteration skips or duplicate launches are permitted.

## Event and action records

The 64-bit example default in the specification cannot represent all mandatory
owner, version, epoch, sequence and action fields. This baseline therefore requires
`EVENT_RECORD_WIDTH = EVENT_WIDTH = 256` and rejects narrower records. Bits 31:0
are the exact released shell event envelope: 3-bit shell event kind, context ID,
then 16-bit kernel ID, with remaining bits zero. The body record layout is:

| Bits | Field |
|---|---|
| 35:32, 39:36 | Record kind and operation |
| 47:40, 55:48 | Event/object ID and source ID |
| 59:56, 63:60 | Namespace (zero) and status flags |
| 79:64, 95:80 | Owner and context version |
| 111:96, 127:112 | Nonzero epoch and per-source sequence |
| 135:128, 151:136 | Transaction/waiter tag and participant mask |
| 167:152, 183:168 | Package and route versions |
| 247:184, 255:248 | Canonical payload and zero reserved bits |

Kinds are counted post 0, payload forwarding 1, wait result 2, barrier release 3,
loop completion 4, action request 5, authoritative response 6, participant safe
point 7, uncertain-state query 8 terminal action result 9 and rejected ingress 10.

Counts never wrap. Posts stall before a full count is changed. Each source starts
at sequence zero, then advances by exactly one within an epoch. Duplicate, gap,
wrong-owner, wrong-version, wrong-epoch and noncanonical records cannot repeat an
effect. Sequence 65535 cannot wrap in the same epoch. The integration must provide
a fresh configuration epoch before delayed pre-reset records can be replayed.
Payload-bearing forwarding records retain their payload rather than being folded
into pending counts. Locally created records receive monotonically increasing
sequence numbers at egress reservation; forwarded records preserve source and
sequence. Sequence exhaustion contains the tile instead of wrapping. Action
responses and safe points use the shell WAKEUP envelope so they can reach a
draining CPT; their body type remains response or safe point.

ANY waits choose the lowest matching event. ALL waits match every selected event.
Consume and completion reservation are atomic in the native event bank. Wait
cancellation uses the matching slot and waiter tag. Barrier releases use unique
participants and current generation, reserve the result, then advance generation.

Action opcodes 0 through 8 request start, stop, suspend, resume, drain, activation,
wake, checkpoint and recovery. Checkpoint is rejected in this baseline. Each live
tag reserves a slot and terminal result capacity. Requests identify the target set,
owner, kernel, context/version, epoch and package/route versions. Safe-point records
collect the required target mask; an authoritative matching response is required
for successful completion. Rejection returns one terminal error. The CPT never
changes a participant's lifecycle or context through raw control wires.

Timeouts monitor sent actions in enabled CPT cycles and pause during suspension.
After timeout, the CPT emits one query and retains the slot until an authoritative
response resolves the uncertain state. It does not replay the original request.
Zero disables the monitor. Source-class egress priority is action/terminal,
barrier, wait/loop completion, forwarded/rejected ingress, then configured post.
A bounded priority burst forces round-robin service among waiting lower classes.

## Lifecycle, protection and scope

Suspend preserves the current context, predicates, registers, counts and live
transactions. Drain finishes accepted effects and reaches a quiet boundary.
Drained pending event counts remain architectural state; unresolved waits, partial
barriers and uncertain actions must be resolved before a quiet transition.
Terminate, release, flush and reset cancel private obligations explicitly. Shell
configuration ownership protects the body and its counters; body debug counters
are read-only at `0x80..0x8f` and require matching owner or privilege. Counter indices
0..10 count idle monitor cycles, issue, retire, decode errors, wait completions,
barrier releases, delivered iterations, processed ingress, rejected ingress,
action timeouts and enabled command-engine cycles. Indices 11..15 are reserved.
Command counter reads and debug reads arbitrate access to the same native bank.

The profile generator permits synchronous body reset, one namespace, fixed 32-bit
control values, a 64-bit data shell and 128-bit data metadata. It supports 1..16
predicate lanes, 2..16 predicate entries, 1..4 loop levels, 1..16 event IDs,
1..4 waits/barriers, 1..16 participant IDs, and 1..8 outstanding actions. `TILE_ID` fits the generated local event-source space.
Shell channels are elastic; checksum support is enabled. Exact
ranges and dependent capacity restrictions live in the production contract and
RTL elaboration guard.

CPT-Adaptive, CPT-local checkpoint/restore, multiple namespaces, predicate-file and
body-control protection, retention, power-off and asynchronous body reset are
explicitly rejected. The native event bank supports its parity profile and shell
context storage supports parity/SECDED. No protected-predicate or checkpoint
capability is advertised without a native implementation. There is no full-cluster
checkpoint or hidden event/configuration/predicate network inside this tile.

Current tests instantiate the real shell and all listed native blocks. A modeled
authoritative controller drives action responses through public event ports.
Physical predicate-network, MST and cluster-controller integration is a later
vertical integration gate; this campaign does not claim that gate has passed.

## Evidence

Structured PyUVM agent, sequencer, driver, monitor, scoreboard, reference model and
coverage components reuse `mosaic_uvm` and existing shell programming helpers.
Independent models check predicate validity, exact comparisons, typed register
state and public transfer accounting. Directed architectural checks cover event
counts, sequencing and ownership, waits, barriers, delivered loop frames, action
safe points, rejection and timeout queries. Held outputs are checked on every
cycle and reset discards are counted explicitly.

The final Icarus campaign passed eight profiles (`default`, `local`, `small`,
`single_lane`, `wide_predicate`, `event_parity`, `context_ecc_async` and
`features_off`), 50 strict elaboration guards and 14 standalone Python model
checks. It checked 183,609 simulation cycles with 1000 seeded random transactions
per profile. Source and verification hashes remained unchanged. The documented
default `make pyuvm` entry point also passed exactly one `CptTest`.

The campaign writes `summary.json`, per-profile `results.xml`, `coverage.json`,
`profile.json`, simulator logs, Python model results and strict elaboration-guard
results under the selected build directory. It hashes production sources and
verification components before and after the run. Failed, skipped, missing,
misconfigured or stale tests cannot produce a passing summary.

The final regression also checks active-loop suspension, terminal completion,
context progression, unknown reset/readiness, event-parity fault containment and
exact command/data/predicate cancellation ledgers.

Only Python-driven functional validation is run. HDL assertion/formal campaigns,
lint, CDC/RDC/DFT/low-power signoff, synthesis, timing and physical/power signoff are
not run here. Synthesis remains deferred to Design Compiler.
