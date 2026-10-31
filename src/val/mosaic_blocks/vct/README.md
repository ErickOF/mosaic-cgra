# VCT RTL and Python validation

The suite checks [`vct.sv`](../../../rtl/mosaic_blocks/vct.sv) against the
[VCT specification](../../../../../specs/mosaic-blocks/mosaic-vct/README.md).
The DUT contains the real tile shell and vector dependencies, without a body stub.

```sh
make setup
make vct-regression                     # VCS installation and license required
make vct-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=vct
```

`VCT_RANDOM_CYCLES` defaults to 2000 and must be at least 1000.
`VCT_SEED` defaults to 20261026. `VCT_REGRESSION_BUILD` selects the evidence directory.
`VCT_JOBS` selects concurrent simulations, defaulting to four for Icarus and one for
VCS. Select individual profiles using the Python entry point:

```sh
.venv/bin/python src/val/mosaic_blocks/vct/run_vct_regression.py \
  --sim icarus --build-dir build/icarus/vct/selected --case default
```

Custom direct tests must supply matching compiler parameter overrides and
`VCT_<PARAMETER>` environment values. The campaign creates these pairs, separate
build directories and exactly sized interface masks. `DATA_WIDTH` and
`PREDICATE_WIDTH` are derived from lane geometry and cannot be overridden.

## Composition

| Dependency | VCT use |
| --- | --- |
| `tile_shell` | Public protocols, protected contexts, CRC, ownership, runtime, events, power, debug, and safe context advance. |
| `vector_lane`, `scalar_alu`, `multiplier`, `mac` | One generated integer lane per physical lane, complete products and widened MAC. |
| `vector_reduction`, `vector_reduction_tree` | Exact masked SUM, MIN, MAX, AND and OR; absent in VCT-Lane. |
| `dot_product` | Exact masked dot and scalar accumulation; present only in VCT-Dot. |
| `vector_register_file`, `register_file` | Independently enabled slice banks; extra configured ports remain disabled. |
| `predicate_unit`, `lane_mask` | Masked predicate updates and effective lane masks. |
| `accumulator` | Persistent independently valid vector lanes and scalar entries. |
| `bypass_network` | Generated sparse operand selection and local feedback. |
| `rdu`, `stream_join`, `tile_shell_queue` | Whole-token delays, ordered joins, protected input holding slots and result elasticity. |
| `packer` | Explicit element/product packing from full lane results. |
| `tile_shell_state`, `tile_shell_codec`, `parity`, `ecc` | Control, validity, typed-state witnesses, per-slice codes and result protection. |
| `performance_counters`, common cells | Body monitoring, storage, operand isolation, reset and write control. |

The shell RTL is reused without modification. `vct_vrf.sv` adapts each logical VRF
slice to an encoded physical bank. `vct_accumulator.sv` composes independently
invalidatable accumulator lanes and protected witnesses. The shell's physical
power and test signals remain external; functional body ports remain internal.

## Repository-local context and metadata ABI

The absent external `mosaic-contracts` package is not required. Local v1 encodings
are published in `vct_pkg.sv`, `layout.py`, and `model.py`, following the existing
tile convention. Lane ALU opcodes reuse `vector_lane_pkg`; reduction opcodes reuse
`vector_reduction_pkg`. Parameter-dependent packed records stay in `vct_body.sv`.

`layout.py` is the explicit context schema, ordered from least-significant field
upward. `model.layout(parameters)` gives every offset and width; `pack` and `unpack`
are executable codecs. Every context word must be written, CRC checked and validated
through the shell. `schema` is one. Unused high image bits are zero. The generated
element width is fixed; contexts cannot select another precision.

| Field groups | Meaning |
| --- | --- |
| `fu`, `opcode`, `signed_mode`, `saturate` | Lane=0, reduction=1, dot=2, broadcast=3, extraction=4, pass=5; dependency operation encodings. |
| `format_a/b/c`, `result_format` | Element vector=0, full-product vector=1, accumulator vector=2, scalar element=3, scalar accumulator=4. |
| `source_a/b/c`, `rf_read_a/b`, `read_slice_a/b` | Explicit operand sources, VRF entries and contiguous slice groups. |
| `lane_mask`, `metadata_mask`, `tail_mask`, `runtime_tail`, `local_mask` | Static mask and enabled metadata, runtime-tail and stored execution-mask factors. |
| `predicate_mode`, `predicate_read`, `predicate_invert`, `false_token` | Always=0, external=1, local=2, never=3; inversion precedes intersection. |
| `select_mask`, `extract_lane` | Independent lane SELECT conditions and selected scalar extraction lane. |
| `output_mask`, `write_rf`, `rf_write`, `write_slice`, `slice_mask` | Atomic external copies and masked VRF slice writes. Zero `slice_mask` selects the complete declared group. |
| `write_predicate`, `predicate_write`, `predicate_output`, `write_mask` | Masked local predicates, external predicates and execution-mask updates. |
| `write_vacc`, `vacc_write`, `write_sacc`, `sacc_write`, `accumulate` | Typed vector/scalar state, feedback and masked write destinations; the selected entry is also the feedback source. |
| `write_bypass`, `invalidate_bypass` | Persistent masked bypass capture and explicit bypass/previous-result lifetime. |
| `required_*`, `invalidate_*`, `clear_vacc`, `clear_sacc` | Protected lane/slice validity requirements, invalidation and valid zero reconstruction on activation. |
| `iterations`, `advance_mode`, `next_context`, `terminal` | Zero iterations runs until runtime control; modes hold=0, count=1, predicate=2, event=3. |
| `delays`, `immediate`, `monitor`, `trap_overflow` | Static per-input delay allocation, one full-width immediate, counters and overflow rejection. |

For `NI` external inputs, source indexes are external `0 .. NI-1`, VRF read A=`NI`,
VRF read B=`NI+1`, immediate=`NI+2`, zero=`NI+3`, vector accumulator=`NI+4`, scalar
accumulator=`NI+5`, bypass=`NI+6`, previous compatible result=`NI+7`.
The minimal graph omits VRF reads and scalar-to-lane paths. Balanced adds VRF reads;
flexible also permits scalar sources and external accumulator operands. Operand C
otherwise selects zero or the appropriate vector/scalar accumulator. Validation
rejects absent edges, formats, resources, reserved fields and contradictory masks.

Data metadata starts with the shell's context ID (`CI` bits) and version (`V` bits).
At `B = CI + V`, it contains:

| Field | Bits |
| --- | --- |
| Format | `B +: 3` |
| Lane mask | `B + 3 +: NUM_LANES` |
| Signedness | `B + 3 + NUM_LANES` |
| Input runtime-tail factor | `B + 4 + NUM_LANES +: NUM_LANES` |

Output metadata publishes result format, effective mask and signedness; other bits
are zero. Used external operands must agree on mask and tail and carry each
operand's declared format and signedness. Predicate metadata carries context ID.
Lane zero occupies the low bits. Compact formats have zero physical padding;
VRF elements/products occupy the configured contiguous slice group inside each
accumulation-width lane. No lane compaction or hidden narrowing occurs.

## Timing, storage and lifetime

This implementation uses a conservative single outstanding operation. Reused
arithmetic is combinational inside the body; protected enabled-cycle stages
implement `LANE_LATENCY`, `REDUCTION_LATENCY`, or `DOT_LATENCY`. MUL and MAC latency
parameters select legal lane-alignment configurations and cannot exceed lane
latency. Broadcast, extraction and pass have zero arithmetic latency.
Selecting the registered bypass adds one enabled cycle. Result packing is
combinational; result admission and atomic commit add one cycle after arithmetic.
With continuously enabled clocks and available destinations, issue-to-body-commit
latency is `L + 1` edges and minimum issue interval is `L + 2`. Shell buffering adds
its own external transfer latency. This implementation does not promise one vector
issue per cycle.

RDU payloads include metadata. One holding slot per channel prevents producer skew
from dropping a delayed token. A channel advances only when its slot can accept
work. Elastic mode adds a configured FIFO per input and an atomic ordered join.
Static delay allocation cannot change with live tokens. Backpressure holds the
complete protected record and all destinations commit on one edge. External output
copies can subsequently retire independently.

VRF payload codewords do not reset. Protected validity controls each slice, and only
valid selected slices are read. Partial writes preserve all other slices and lanes.
Accumulator payloads remain unreset; lane validity and typed witnesses control
reads. Predicates and execution masks carry lane validity. Bypass writes merge
compatible active lanes and preserve inactive lanes. Architectural sources serialize
behind earlier commits, providing explicit read-after-write interlocks.

Known static/metadata/tail-inactive lanes are isolated before entering protected
shell buffers. The body isolates masked FU operands and checks only selected active
operand bits; SELECT checks each lane's chosen operand. Active unknowns, unknown
controls, bad formats, wrong ownership and uncorrectable state fail closed.

Activation applies declared validity masks. Accumulator feedback checks stored
signedness and saturation type. Suspend and drain preserve committed state. Safe
points exclude issue and commit edges, partial transport and queued output effects.
Temporal advance waits for the shell's safe context boundary and preserves ownership.
Compatible state may survive between resident contexts. Termination, release, reset
and nonretained power-off invalidate owner-private state. Retention preserves
quiescent state under the shell's physical save/restore/isolation acknowledgements.

## Debug and evidence

Owner or privileged reads at `0x80 .. 0x9f` expose 32 saturating 32-bit body counters.
Writes and unauthorized reads are rejected; responses hold under backpressure and
unknown ready. Counter indexes 0 through 31 count issue, commit, active lanes,
masked lanes, lane FU, multiply, MAC, reduction, dot, VRF slice reads, slice writes,
missing local sources, predication, predicate writes, empty masks, vector state
writes, scalar state writes, bypass writes, broadcast, extraction, RDU advances,
input stalls, output stalls, activation, advance, overflow, saturation, format
errors, corrections, errors, idle and completion. Shell counters remain available.

The structured PyUVM agent, driver, monitor, sequencer, scoreboard, coverage and
sequences reuse the common `mosaic_uvm` infrastructure and shell protocol helpers.
An independent integer model predicts arithmetic, masks, local state and external
outputs from accepted inputs. The scoreboard checks actual issue/commit edges,
minimum/exact latency, partial writes, atomic destinations, stalled output stability,
ordered completion and explicit reset/termination discards.

The campaign includes lane/precision/FU profiles, all protection combinations,
latencies, optional-feature removal, RDU/elastic skew, every effective lane mask,
all formats, predicates, VRF slice reuse, vector/scalar feedback, broadcast,
extraction, context sequencing, reset, runtime, debug and retained power transitions.
Python unit tests independently exercise the codec, exhaustive INT4 products,
reduced reductions/masks and signed dot accumulation. Python-driven parameter probes
require the named elaboration guard. A successful campaign requires exactly one
requested PyUVM test per profile, all mandatory coverage, reproducible seeds, and
unchanged hashes for RTL, dependencies, Python helpers and Makefile. Logs, JUnit,
coverage and `summary.json` are archived beneath the selected build directory.

Only Python-driven simulation and model tests are run here. Synthesis is deferred
to Design Compiler. Native VCS execution requires the server toolchain. Lint,
formal, CDC/RDC, DFT, low-power signoff, physical implementation, timing and
power/energy qualification remain separate release activities.

The local Icarus campaign passed 47 parameter profiles, 161 strict elaboration
guards, four Python model tests and 94000 seeded random cycles. The direct Makefile
entry also passed. The campaign's archived source hashes match the final RTL,
ordered dependencies, reused Python helpers, verification components and Makefile.
The finest-slice profile checks an exact 256-slice read increment through debug
counter readback. Native VCS and Design Compiler runs are deferred to the server.
