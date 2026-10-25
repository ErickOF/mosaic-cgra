# BCT RTL and Python validation

This suite checks [`bct.sv`](../../../rtl/mosaic_blocks/bct.sv) against the
[BCT specification](../../../../../specs/mosaic-blocks/mosaic-bct/README.md).
The top composes the actual released tile shell and scalar body. No body stub or
Python replacement for a functional unit is used.

```sh
make setup
make bct-regression                     # VCS installation and license required
make bct-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=bct
```

`BCT_SEED` defaults to `20261025`; `BCT_RANDOM_CYCLES` defaults to `2000`, with a
minimum of 1000. `BCT_REGRESSION_BUILD` selects the evidence directory and
`BCT_JOBS` selects parallel simulations, defaulting to four for Icarus and one
for VCS. A selected profile can be run with:

```sh
.venv/bin/python src/val/mosaic_blocks/bct/run_bct_regression.py \
  --sim icarus --build-dir build/icarus/bct/selected --case default
```

Custom direct runs must set both compiler overrides and matching `BCT_<PARAMETER>`
environment values. The campaign constructs these pairs, exactly sized masks and
separate build directories automatically. It rejects duplicate profile names.

## Reused implementation

| Dependency | Purpose |
| --- | --- |
| `tile_shell`, `context_memory`, `context_sequencer` | Configuration, CRC, ownership, validated contexts, runtime and safe context selection. |
| `scalar_alu` | Mandatory ALU operations, min/max, saturation, arithmetic status and mixed-MAC final addition. |
| `multiplier`, `mac`, `dot_product` | Complete narrow products and exact multiply-add. BCT-A omits these datapaths; BCT-M omits MAC and accumulator storage. |
| `register_file` | Two selected logical RF reads and one selected write, with configured additional physical ports disabled. RF codewords have no reset. |
| `predicate_unit`, `accumulator` | Predicate updates/readback and persistent accumulator loads/clear. Protected witnesses check their data and validity. |
| `bypass_network` | Generated sparse source graph for the three operand positions. |
| `rdu` | Shared, statically partitioned delay storage with payload and metadata kept together. |
| `stream_join`, `tile_shell_queue`, `event_barrier_queue` | Ordered elastic operand joins, result reservation, protected storage and atomic boundary admission. |
| `performance_counters` | Body event counts and the shell's existing monitoring. |
| `dff`, `decoder`, `write_gate`, `lane_mask`, `operand_isolation`, `parity`, `ecc`, `reset_synchronizer` | Storage, isolation, write qualification, error protection and shell reset release. |

The shell gains an optional `BODY_CONTEXT_ADVANCE` parameter, defaulting to zero.
When enabled, an internal body request selects a validated next context only while
body transport and shell boundaries are empty. It preserves the ACTIVE runtime
state and ownership. Default standalone shell behavior and public BCT interface
groups remain unchanged. The BCT keeps the shell's physical power/test controls;
functional body ports are internal connections.

## Repository-local context ABI

The external `mosaic-contracts` package is absent. This implementation follows the
repository's existing local-encoding convention: `bct_pkg.sv` owns FU, source-profile,
synchronization, predicate and error enums, and reuses `scalar_alu_pkg` opcodes.
`layout.py` publishes the context field widths and order. A generated packed RTL
struct remains inside the body because its widths depend on tile parameters.

Fields are packed from low bits upward in this order. A configuration word contains
its corresponding little-endian slice of the image. Every word must be written
and the image validated through the shell before activation. `schema` is one;
unused high image bits and reserved opcode/mode encodings are zero.

| Fields, in order | Widths or interpretation |
| --- | --- |
| `schema`, `fu`, `opcode` | 8, 2, 5 bits; FU ALU=0, multiply=1, MAC=2. |
| `signed_a`, `signed_b`, `saturate` | One bit each. ALU uses `signed_a`; multiply/MAC interpret operands independently. |
| `source_a`, `source_b`, `source_c` | Generated source-index width each. Unused accumulator source is zero-constant. |
| `rf_read_a`, `rf_read_b` | RF address width each. |
| `output_mask`, `write_rf`, `rf_write` | Output-port mask, write enable, RF address. |
| `write_predicate`, `predicate_write`, `predicate_output` | Local write enable/address and external predicate-output enable. |
| `write_accumulator`, `accumulator_write`, `write_bypass` | Local destination enables and accumulator address. |
| `predicate_mode`, `predicate_read`, `predicate_invert`, `false_token` | Always=0, external predicate=1, local predicate=2, never=3; inversion follows validity checking. |
| `flag_select`, `select_condition`, `trap_overflow` | Three-bit result-flag selection; independent ALU SELECT condition; modular-overflow trap enable. |
| `iterations`, `advance_mode`, `next_context`, `terminal` | 16-bit issue count, two-bit transition mode, context address, terminal-completion enable. |
| `required_rf`, `invalidate_rf` | One bit per RF entry. |
| `required_predicate`, `invalidate_predicate` | One bit per predicate entry. |
| `required_accumulator`, `clear_accumulator`, `invalidate_accumulator` | One bit per generated accumulator slot. Clear reconstructs valid zero; invalidate removes validity. |
| `invalidate_bypass`, `delays`, `immediates`, `monitor` | Bypass lifetime flag, one delay per input, immediate array, counter enable. |

`pack`, `unpack` and `layout` in `model.py` provide executable context construction
and field offsets. `iterations=0` holds a spatial mapping until runtime control
stops it. For bounded mappings, the producer supplies exactly that many complete
operand sets. `terminal=1` requests completion after the bounded work commits and
transport empties. Terminal and automatic-advance modes cannot be combined.

Transition modes are hold=0, bounded operation count=1, selected result predicate=2,
and body event=3. Event mode may use a bounded count to stop issuing before waiting
for its transition event. Old-context operations and external output copies drain
before the shell accepts the next-context request. MAC feedback also checks stored
accumulator signedness and saturation compatibility; clear explicitly reconstructs
state under the new interpretation. An invalid next context is
contained by the shell. There is no overlapping temporal pipeline.

### Source graph

Source indexes are external inputs first, then RF read port A and B, immediate
entries, zero, one, accumulator entries, captured bypass, previous result, and
local predicate expanded to scalar. RF indexes select read ports; the context
supplies their addresses. A repeated external source consumes its token once.
Unused SELECT operands and unused FU operands consume no token.

Minimal graphs omit ordinary bypass/previous-result sources except required MAC
feedback, and omit local-predicate expansion. Balanced graphs add bypass/previous
results and RF output forwarding; flexible graphs also admit predicate expansion.
Minimal profiles reject direct RF pass-through to external outputs. Absent edges
and unavailable resources fail validation rather than aliasing to another source.
Connectivity is reproducible from parameters and the `graph`/`edge_legal` functions.

### Datatypes and metadata

Values are full-width scalars. Narrow multiply operands are checked for unsigned
zero extension or signed canonical sign extension before FU admission, unless
`REQUIRE_CANONICAL_NARROW=0` explicitly permits low-bit selection. Full products
are retained and extended to `DATA_WIDTH`. Same-signedness MAC uses the released
MAC; mixed-signedness MAC composes the exact multiplier and signed final-add ALU.

Data metadata retains the shell's low context-ID and full-version fields. The first
required input supplies body-owned metadata; operations with no external operand
construct their context/version identity directly. Bit `CONTEXT_ID_WIDTH +
CONTEXT_VERSION_WIDTH` marks a false output token. False suppression and false
zero tokens suppress RF, predicate, accumulator and bypass writes. Predicate
outputs select compare, zero, negative, carry, borrow, overflow or saturation flags
with `flag_select=0..6`. ALU SELECT uses `select_condition` independently of operation
predication, so both alternatives remain executable.

## Timing, commit and lifetime

The body computes with combinational released FUs and owns protected enabled-cycle
pipeline records. Configured FU latency adds exactly that many enabled stages;
a selected registered-bypass source adds one more. The protected result queue adds
one edge before commit. Uncongested issue-to-body-commit latency is therefore:

```text
FU latency + selected registered-bypass stage + 1
```

Shell input/output buffers add their own externally visible transfer latency.
Independent operations can issue once per enabled cycle when capacity permits.
Dependent RF, predicate, accumulator and bypass reads interlock until older results
commit; no implicit RF write forwarding is assumed. A full result queue freezes
pipeline records. Results retain context/version, owner/kernel, destinations,
predicate, flags and sequence until commit.

Commit reserves every selected shell data/predicate destination together and applies
local writes on the same edge. The shell may deliver external multicast copies
independently afterwards. Metadata is presented before admission to let the shell
check destination readiness without a ready/valid feedback loop. Scheduled producers
must honor reserved capacity; they cannot present elastic traffic during a blocked
scheduled cycle.

RDU capacity is partitioned evenly across input channels; the first remainder
channels receive one additional entry. Zero-delay inputs join atomically; nonzero
delays advance in the shared enabled schedule. Mapper schedules must align delayed
operand arrivals. Elastic mode instead stores each required input in an ordered FIFO
and joins the heads without associative matching. Input transport is context-owned.

Reset, release, termination, fatal containment and nonretained power-off invalidate
private state. Unknown reset pauses admission and body updates without treating it
as an asserted reset or discarding already accepted operations. Payload RF and arithmetic registers are not reset. Context masks
invalidate selected architectural state; accumulator clear initializes valid zero.
Bypass/previous results may survive a compatible context switch unless explicitly
invalidated. The mapper must declare compatible scalar state lifetimes. Invalid
local sources stall elastic mappings and report a contained source error in static
mappings. Suspend/drain stop new external admission and retire already accepted
operand sets before reaching a safe point.

Retention preserves quiescent local state in the functional model and waits for the
shell's physical save/restore/power acknowledgements. Technology retention cells,
power intent and physical qualification belong to the later implementation flow.

## Debug and monitoring

Shell debug addresses retain their existing meaning. Read-only BCT addresses
`0x80..0x9f` expose 32 saturating 32-bit event counters to the owner or privileged
reader. Writes and unauthorized reads return an error. Responses are latched and
remain stable under backpressure, including unknown ready. Invalid/reset responses
clamp data and error outputs.

Counter slots are issue, commit, ALU/multiply/MAC issue (0-4); RF reads/write/invalid
live-in (5-7); predicate reads/write/false suppression/false token (8-11);
bypass use/capture (12-13); RDU advance/wait and elastic join wait (14-16);
input/output stall (17-18); activation/advance (19-20); overflow/saturation/
noncanonical/error cycles (21-24); idle/clock-enabled/clock-disabled cycles (25-27);
input transfers/output copies/predicate outputs (28-30); and completed residency (31).
Weighted slots count simultaneous transfers. Context `monitor` and shell monitoring
must both be enabled. The capability fingerprint combines the shell fingerprint
with all BCT-specific parameters, including FU removal, widths and protection.

## Python campaign and evidence

The campaign contains 41 distinct profiles and 121 strict elaboration guards. It
covers required BCT-A widths 8/16/32, BCT-M 8x8/16x16, BCT-MAC 8x8/16x16 into 32,
FU latencies 0..4, RF depths 3/4/8/16/32, predicate depths 1/2, context depths
1/3/4/8/16, all bypass/synchronization/protection choices, both reset modes,
asynchronous configuration, a 512-bit striped RF codeword, extra RF ports,
two immediates/accumulators, scheduled
boundaries, zero-depth boundaries, disabled features, retention and power-off.
Every profile runs 2000 seeded random cycles in addition to directed mappings.

The structured PyUVM environment uses a passive edge monitor, independent scalar
integer oracle, per-input accepted-token queues, local-state model, ordered operation
ledger and per-output copy queues. It checks source values, arithmetic, minimum and
uncongested exact latency, atomic destinations, context image/ownership, output
stability, predication, conservation, explicit reset/flush cancellation, counters,
context transitions and fault containment. Three standalone Python model tests
check context packing, exhaustive small mixed products and saturation boundaries.

The runner requires exactly the decorated `BctTest`, matching parameters/seeds,
all mandatory coverage goals, and unchanged RTL/dependency/Python source hashes.
It archives JUnit, coverage, simulation logs and `summary.json`. The standalone
shell regression is rerun for the optional safe context-advance integration.

Only Python-driven functional simulation and model tests are part of this work.
HDL assertion suites, lint, formal, synthesis, CDC/RDC, DFT, power-intent checks,
physical implementation and timing/power/energy signoff are not run. Design
Compiler synthesis is deferred. Functional simulation is not full BCT release or
cluster-level qualification.
