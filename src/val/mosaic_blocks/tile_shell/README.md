# Tile shell RTL and PyUVM validation

This suite implements the [tile-shell specification](../../../../../specs/mosaic-blocks/mosaic-tile-shell/README.md)
with [`tile_shell.sv`](../../../rtl/mosaic_blocks/tile_shell.sv). It exercises the
actual RTL through Python 3.12, cocotb and structured PyUVM components. Synthesis is
deferred to Design Compiler.

```sh
make setup
make tile-shell-regression                 # VCS and a license are required
make tile-shell-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=tile_shell
```

`TILE_SHELL_SEED` defaults to 20261025 and `TILE_SHELL_RANDOM_CYCLES` to 2000
(minimum 1000). `TILE_SHELL_REGRESSION_BUILD` selects the evidence directory.
`TILE_SHELL_JOBS` selects independent simulations, defaulting to four for Icarus
and one for VCS. A selected profile can be run directly:

```sh
.venv/bin/python src/val/mosaic_blocks/tile_shell/run_tile_shell_regression.py \
  --sim icarus --build-dir build/icarus/tile_shell/selected \
  --case context2_control2_cfg1
```

Custom direct simulations must supply matching compiler parameter overrides and
`TILE_SHELL_<PARAMETER>` environment values. Mask overrides must have exactly the
port count's width, for example `-Ptile_shell.INPUT_ELASTIC_MASK=2'b10` in Icarus
or the corresponding `-pvalue+tile_shell.` override in VCS. The regression constructs
these literals, parameter dependencies, separate build directories and exact test
filters automatically.

## Reused RTL

| Block | Shell use |
| --- | --- |
| `context_memory` | Raw context words, masked protected-word writes, committed validity and readback. |
| `context_sequencer` | Atomic safe-point selection of committed contexts. The opaque context schema does not enable automatic progression; software uses `CFG_ACTIVATE`. |
| `fifo`, `event_barrier_queue` | Independent boundary queues, response ownership and synchronous parallel flush. |
| `async_fifo` | Paired configuration request and response bridges. |
| `reset_synchronizer` | Independent asynchronous reset release in functional and configuration domains. |
| `tile_power_controller` | Always-on idle, stall, drain, retention, isolation, power-off and wakeup sequencing. |
| `performance_counters`, `counter` | Monitoring and trace ordering. |
| `dff`, `decoder`, `operand_isolation`, `parity`, `ecc` | Storage, selection, payload isolation and protection inside reused blocks. |

The small shell helpers provide a common striped codec, reset-valid protected
records and boundary queues. Their geometry is checked by the shell's strict
elaboration guard. No technology cells, generated clocks, external contracts
package or dependency manifest are introduced.

## Repository-local boundary

[`tile_shell_pkg.sv`](../../../rtl/mosaic_blocks/tile_shell_pkg.sv) is the shared
repository-local v1 encoding source. Tile classes, configuration/runtime commands,
execution states and architectural power states use the specification's values.
Configuration/runtime commands are three bits, execution states four bits, power
states three bits, debug addresses eight bits, and shell errors at least eight
bits. The package defines error and event classes for bodies and software.

Physical power-controller states are translated to the shell's architectural
states. The shell publishes architectural version 1 and a reproducible capability
fingerprint over its configured interface and feature parameters. Full parameters
and hashes accompany each regression profile; the fingerprint is not a security
attestation.

Port zero occupies the least-significant packed slice. Payload bits are opaque.
This baseline defines these metadata fields, from least-significant bit upward:

| Record | Shell-owned fields | Remaining bits |
| --- | --- | --- |
| Data | Full context ID, full context version. | Body-owned datatype, predicate, framing and routing information. |
| Predicate | Context ID. | Body-owned operation/predicate association. |
| Event | Three-bit type, context ID, kernel ID. | Body-owned source/payload/reliability information. |

This preserves the specification's default widths. Predicate-version and numerical
schema checks belong to the specialized body's integration profile; they are not
silently inferred from opaque upper bits. Integrations must fence producers and
routes before recycling kernel/operation identities. Error and completion events
use external event output zero; completion type is zero, wakeup one, error five,
fatal six, and ordinary body events seven.

The raw context image is opaque. Generic validation checks ownership, bounds,
complete word coverage, version and integrity, plus CRC-32C when enabled. The body
validator checks operation, datatype, framing and every body-specific field.

## Configuration and ownership

Unallocated provisioning is permitted. Once allocated, configuration requests must
match the owner and runtime requests both owner and kernel. Requests crossing the
configuration bridge are checked again when serviced by the functional domain.
Responses preserve command, context, version, CRC and tag.

A write initializes unwritten bytes to zero, merges enabled bytes, marks the word
written, advances the version and clears validation. Active contexts cannot be
written or invalidated. A zero-strobe write is a successful zero-byte update and
still advances the version and marks the word written.

CRC-32C covers increasing word index and least-significant byte first, with
reflected polynomial `0x82f63b78`, initial/final XOR `0xffffffff`. Query returns the
written-word bitmap followed by the validated bit, truncated to the configuration
word width; version and full CRC have separate response fields.

One body validation may be outstanding. Its ID, version, image and word bitmap
remain immutable while stalled. Other configuration operations may proceed, so a
later write can make a response stale. A matching current-version legal result
commits validity atomically. Rejection or mismatch returns an error without commit.
Validation responses can therefore complete after later independent configuration
commands; clients correlate them by tag.

Activation requires allocation, committed validity, empty boundaries and a body
safe point while unstarted, suspended, drained or completed. It does not start the
body. Release clears ownership, active selection, validity and nonpersistent
counters. It advances context versions to prevent prior data records aliasing the
next allocation. Version exhaustion requires reset; versions never wrap silently.

## Runtime and transfers

Start and resume wait for required power wakeup, then produce one body pulse and
one command response. The body must accept a start when reporting idle and safe.
Suspend stops new admission and waits for safe-point acknowledgement. Drain stops
new ordinary inputs while previously accepted records retire. Its response follows
the body and boundary drain; a completed kernel additionally commits its completion
event before reporting completed. Termination flushes owned work and does not
produce successful completion.

Each buffered port is an ordered record queue with simultaneous consume/replace.
Zero-depth data and predicate ports are explicit combinational paths. Their mapping
must prove the absence of a surrounding ready-valid loop. Event buffers have at
least one slot even when data depth is zero, allowing always-on wakeup capture.
Body transfers require the functional body clock to be enabled and reset released.

For scheduled inputs, asserted body ready is the reserved transfer opportunity;
a missing producer or blocked transfer reports a schedule violation. Scheduled
outputs treat body valid as the reservation. Elastic ready means capacity and does
not imply that the body requires an absent operand. The body reports elastic input,
memory and synchronization requirements through its stall bitmap. Stall priority
is output, memory, synchronization, then input; the full bitmap remains visible.

All accepted functional records must retire once or be explicitly discarded by
termination, containment or reset. Completion cannot pass queued data, predicates,
body events or an earlier error notification. A second completion indication before
retirement or after completion is fatal. The body must deassert its completion
level between distinct indications.

## Power, reset and containment

The shell emits logical clock, save/restore, isolation and supply controls. The
existing power controller remains on the root clock. The shell additionally holds
supply enabled until isolation acknowledgement. Save, restore and power-good
acknowledgements must be driven according to the body/technology contract.
Power-off of suspended preserved work requires retention. Unsupported requests
return errors without starting a transition.

Wakeup/error events remain admissible while ordinary execution is stopped or gated.
They are buffered in always-on shell storage and delivered after wakeup and reset
release. A body reset used during power recovery does not flush these event queues.
Test and scan enable override the logical body clock without removing isolation.
Physical gating, isolation, retention and supply cells remain integration work.

With asynchronous configuration, either reset begins a coordinated whole-shell
command epoch. Both bridges are cleared and each domain independently synchronizes
release. This conservative reset policy discards pending runtime/configuration and
functional ownership, so no pre-reset response can return in the new epoch. In
synchronous configuration, the integration ties configuration clock/reset to the
functional clock/reset. Unknown reset controls pause interfaces and retain owned
state while reporting a diagnostic; they do not impersonate a known asserted reset.

Parity detects changed protected data. SECDED corrects one bit in a 256-bit stripe
and rejects uncorrectable words or multiple corrected stripes. Context words,
versions, validation snapshots, owner/state and command records use the selected
protection. State-valid markers also use the selected codec; losing a committed active
context is contained before any further transfer. Boundary payloads use the selected codec; queue pointer/occupancy
metadata also has parity detection. The reused Gray FIFO supplies the asynchronous
bridge protocol; physical CDC/RDC and metastability qualification remain separate.

The first sticky error retains code, source, owner, kernel, context, state and tag.
A later fatal condition sets fatal status without replacing first evidence. Fatal
containment blocks execution and activation, flushes functional queues, and keeps
configuration readback, debug and reliable error notification serviceable. Pending
validation is cancelled with a matching error response. Reset is required to recover
fatal state. A body implementation must cancel its own pending validation/results
when body flush is asserted.

## Debug, counters and trace

Debug reads are available during containment. Writes require matching ownership or
trusted privilege and a safe boundary. They cannot program or activate contexts.

| Address | Access |
| --- | --- |
| `0x00` | Execution state. |
| `0x01`, `0x02`, `0x03` | Owner, kernel, active context. |
| `0x04` through `0x09` | First error: code, owner, kernel, context, state, tag. |
| `0x0a`, `0x0b`, `0x0c` | Input occupancy, output occupancy, first-error source. |
| `0x20`, write | Bit 0 clears recoverable error; bit 1 clears counters. |
| `0x21`, write | Bit 0 enables/disables monitoring. |
| `0x40` through `0x4f` | Sixteen saturating monitoring counters. |

The first six counters use per-port weighted increments, including simultaneous
transfers and shell-generated output events. Counter slots describe data, predicate
and event transfers per direction (0-5),
stall cycles (6), writes (7), successful validation (8), activation (9), accepted
legal runtime commands (10), completion (11), diagnostic cycles (12), wake activity
cycles (13), power-transition cycles (14), and dropped trace records (15).

Trace uses a one-entry sampled queue. Backpressure preserves the presented record;
additional samples are dropped and counted without stalling functional execution.
The packed record contains event class, context, kernel, owner and tile identity,
followed by an ordering sequence in the remaining high bits. The sequence advances
on sample attempts, including drops. Trace remains in the always-on domain and is
flushed on release; it cannot prevent a safe body power transition.

## Python validation and evidence

The test/environment/agent/driver/passive-monitor/model/scoreboard/coverage structure
reuses `mosaic_uvm`. The Python body stub provides validation acknowledgements,
completion, safe points and technology acknowledgements. It is a protocol fixture,
not an arithmetic tile implementation.

The 27-profile campaign covers every tile class, data widths 8/16/32/64/128, 1/2/4/8
data ports, asymmetric predicate/event ports, mixed transfer masks, boundary depths
0/1/2/4, context depths 1/3/4/8/16, word counts 1/3/8/32, asynchronous configuration
with non-power-of-two logical bridge capacity, both functional reset profiles,
checksum/trace selection, every context/control protection combination, and all
retention/off feature combinations. Every context and word is written and read.
There are 148 strict invalid-parameter probes and three independent Python model
tests, including standard CRC vectors and bytearray write-mask references.

Each profile adds 2000 seeded random cycles with stable producers under independent
backpressure. Directed checks cover all commands, wrong destination/owner, complete
and incomplete images, CRC mismatch, body rejection, stale results, atomic context
selection, every port, suspension, drain, ordered completion, duplicate completion,
termination, response stalls, debug, trace stalls, gated wakeups, retention/off,
unknown controls, single/double payload and state-validity faults, active commit-bit loss, validation
cancellation, clockless
periods and reset with pending commands/work. The independent per-port ledgers
check conservation and ordering; configuration responses are checked by owned tags.

The runner verifies the exact decorated PyUVM test and archives parameters, seeds,
actual JUnit/coverage/logs and hashes of RTL, dependencies and Python helpers. Source
changes during a campaign invalidate its result. The campaign runs no HDL checker,
lint, formal, synthesis, physical implementation or power analysis. Full release
qualification and integrated BCT/MST body validation are separate from this Python
functional campaign.
