# Programmable LUT RTL and PyUVM validation

[`lut_unit.sv`](../../../rtl/building_blocks/lut_unit.sv) implements the
[LUT-unit specification](../../../../../specs/building-blocks/mosaic-lut-unit/README.md).
Software programs invalid banks, verifies entries, and atomically commits an image.
Lookups capture image identity and return ordered, bit-exact results through an
elastic pipeline and result queue.

## Run

```sh
make setup
make lut-unit-regression                       # Requires VCS and a license
make lut-unit-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=lut_unit
```

The decorated test is `test_lut_unit.LutUnitTest`. Separate test, environment,
agent, sequencer, driver, passive monitor, reference, scoreboard, coverage and image
recipe modules reuse `mosaic_uvm`. Actual ports are checked before the edge, at the
edge, after settling and during a held interval. Every public output is checked,
including invalid payloads, status, metadata, errors, events and queue occupancy.

The **51-profile** matrix contains the exact defaults; address widths 4/6/8/10;
outputs 8/16/32 bits; fractions 4/8/12 bits; banks 1/2/4/8; all protection and reset
choices; and every interpolation/coverage/protection/reset combination using three
banks, a three-stage pipeline and queues of depth three/five. Two extra profiles
exercise a 257-bit entry, one-stage processing and one-entry queues. Every profile
runs 2000 random cycles plus directed traffic. There are **68 strict elaboration
guards** for invalid dimensions, feature switches, protection, version and packed
size. No invalid parameter is silently truncated into a valid configuration.

Configure `LUT_UNIT_SEED`, `LUT_UNIT_RANDOM_CYCLES` (minimum 1000) and
`LUT_UNIT_REGRESSION_BUILD`. Seeds advance by profile index. Select a case directly:

```sh
.venv/bin/python src/val/building_blocks/lut_unit/run_lut_unit_regression.py \
  --sim icarus --build-dir build/lut-selected --case default
```

The runner checks fresh JUnit identity, coverage, parameters and seed, and records
RTL/dependency/verification SHA-256 hashes. Logs, coverage and aggregate evidence
are under the selected build directory. Missing tools/licenses remain `NOT_RUN`.
Direct custom runs require matching compiler overrides and `LUT_UNIT_<PARAMETER>`
environment variables; the runner sets both and tracks parameter dependencies.

Private checks and fault injection default on. The regression enables native HDL
assertions; enable them for a direct RTL run, or select public-port mode:

```sh
LUT_UNIT_HDL_ASSERTIONS=1 make pyuvm SIM=icarus COCOTB_TOPLEVEL=lut_unit
LUT_UNIT_CHECK_INTERNALS=0 LUT_UNIT_HDL_ASSERTIONS=0 \
  make pyuvm SIM=icarus COCOTB_TOPLEVEL=lut_unit
```

Public-port mode omits hierarchical read-activity checks and fault injection. HDL
assertions are reported `NOT_RUN` when disabled. This is zero-delay RTL verification
with nominal 10 ns clock opportunities and 1 ps observation ticks; it does not
qualify SDF-annotated timing.

## Composition and encodings

No existing RTL primitive is modified. The implementation reuses:

- `event_barrier_state` and common DFFs for bank metadata and diagnostic state.
- `event_barrier_queue`, common FIFOs and operand isolation for elastic stages and
  both response queues, with unreset payload storage and independent flush control.
- Common parity/ECC codecs and the ECC decoder's common binary decoder for entries.

[`lut_unit_bank.sv`](../../../rtl/building_blocks/lut_unit_bank.sv) provides inferred,
unreset codeword storage with two isolated asynchronous read ports and one clocked
write port. Two adjacent reads support throughput-one interpolation without
requiring the single-read SRAM wrapper to perform two accesses in one cycle.
A macro implementation must preserve those ports and the published latency.

[`lut_unit_pkg.sv`](../../../rtl/building_blocks/lut_unit_pkg.sv) defines local enums
using the specified command, rounding and protection values. No external contracts
package or dependency manifest is required. Parameterized packet/metadata structs
remain local to the RTL. Integration with other encodings must map explicitly.

| Field | Encoding |
|---|---|
| Programming | WRITE=0, READ=1, COMMIT=2, INVALIDATE=3 |
| Rounding | Toward zero=0, nearest-even=1 |
| Protection | None=0, parity=1, SECDED=2 |
| Error | NONE=0, UNKNOWN=1, BANK=2, INVALID_BANK=3, INTERPOLATION=4 |
| Error | WRITE_COMMITTED=5, COVERAGE=6, BUSY=7, LIFECYCLE=8 |
| Error | CORRECTED=9, UNCORRECTABLE=10, INTERNAL=11 |

`defaults.DEFAULTS`, `transaction.PORTS` and `config.aliases` describe parameters,
port directions and derived widths in machine-readable Python form. Bank zero is
the least-significant packed metadata slice. Every address is representable because
table depth is a power of two; an unknown address fails closed.

## Numerical behavior and timing

Coordinate width is one plus address width plus fraction width. Signed negatives
clip to entry zero; coordinates strictly above `(TABLE_DEPTH−1) << fraction_width`
clip high. Exact endpoints do not report clipping. Direct lookup returns stored
bits regardless of signedness. Only a fractional, unclipped interpolation below
the final entry reads a neighbor and activates the multiplier.

Endpoints extend before subtraction, so descending unsigned tables use a signed
delta. Rounding operates on delta magnitude, with nearest-even applied to the
retained delta integer, then restores sign and adds the base entry. Negative
fractional deltas truncate toward zero rather than toward negative infinity. The
result clamps between endpoints under the selected interpretation. Unknown rounding
is ignored for direct lookup; unknown active interpolation controls block intake.
A known interpolation request is rejected when interpolation is disabled, including
on an inactive token. Invalid banks also remain errors on inactive tokens.

A request accepted at edge `t` enters the result queue just after edge
`t + LOOKUP_PIPELINE_DEPTH` without stalls. It can retire on the following edge.
All lookup kinds share that latency. Each elastic stage owns one token; a full
response queue can extend latency and propagate backpressure. Arithmetic is
combinational before the first holding stage; additional stages preserve the fixed
architectural delay. Technology timing must characterize that arithmetic path.

Programming creates a registered response on its acceptance edge. The two streams
preserve their own orders, with no cross-stream ordering promise. Both queues allow
consume-and-replace at full occupancy.

## Lifecycle, references and recovery

WRITE is legal only while invalid. Coverage records distinct addresses; duplicate
writes cannot replace a missing address. COMMIT requires an invalid, unreferenced
bank and complete coverage when tracking is enabled. It captures IDs, increments
version modulo its width and sets valid atomically. With tracking disabled,
program-complete is always high and software owns complete-image verification.
INVALIDATE requires a committed, unreferenced bank; it clears IDs/coverage/validity
while preserving version and entry bits.

Reference counts include pipeline and queued-result tokens, including predicated
and in-range illegal requests. A separate census compares those counts with actual
owned tokens. Queue occupancies are independently compared with occupied slots.
An outstanding token owns its bank through its retiring edge; invalidate may succeed
on the next edge. Program-response records do not hold lookup references: they
retain the metadata captured at their own command.

Lifecycle and WRITE commands exclude a same-bank lookup on their acceptance edge.
Lookup has priority over same-bank readback when it actually uses the read port.
Predicated lookup uses no port, allowing readback to proceed. Independent banks can
serve lookup and programming concurrently.

Drain blocks new lookups and holds programming until the lookup path empties.
Flush masks request/response handshakes on its edge, discards lookup-owned tokens,
clears references and preserves tables, coverage, identity and completed program
responses. Program responses reappear afterward in their original order. Reset
invalidates banks and clears both queues and metadata while leaving table data
unreset. Asynchronous reset release synchronization belongs to integration.

Protected profiles parity-check bank validity, version, IDs, coverage, reference
counts, pipeline ownership/data and queue pointers/payloads. Entry SECDED uses
stripes of at most 256 data bits. Multiple corrected stripes are classified as a
whole-entry uncorrectable error, so two-bit faults across stripes also fail the
entry. Single-bit faults correct before use; correction reports a recoverable unit
error/event while the response succeeds. There is no automatic scrub.

An uncorrectable visible entry latches a bank fault. Accepted tokens still drain;
new lookups and commit are blocked. Drain or flush, invalidate the faulted bank,
rewrite, read back and commit to recover. Corrupted metadata/ownership latches a
hard fault and requires reset. Error clear and flush remove recoverable errors;
an outstanding fatal cause remains reported. Diagnostic error/event flops are
outside parity banks and do not own data or image identity.

Unknown active request fields block their handshake and set UNKNOWN rather than
creating an uncorrelated response. Known illegal requests produce ordered error
responses with zero data and preserved known identity. Unknown reset/flush clamp
handshakes and hold progression. Unknown readiness cannot retire an item.

## Verification and image recipes

The numerical oracle uses Python integers, `divmod` and an independent extended
Hamming bit-position implementation. A deadline-based bounded ledger models fixed
latency and elastic occupancy without copying RTL stage or carry code. The
scoreboard proves accepted = retired + explicitly discarded + pending for both
streams on every checked edge. Reset may discard both streams; flush discards
lookups and preserves programming responses.

Directed cases program and read back every address before publishing, sweep every
integer boundary, exercise fraction/clipping corners, both signedness/rounding
choices, increasing/decreasing/constant images, exact ties, mode/predicate errors,
incomplete/duplicate commit, ownership conflicts, concurrent banks, full queues,
drain, flush, X/Z controls and reset between clock edges. Small two-bit-version
profiles exercise wrap. Protected runs inject every codeword bit at a representative
entry, double-bit faults, visible-bank failures and metadata/queue corruption.
Random cycles hold complete producer packets until accepted and vary both response
readiness signals. HDL assertions independently check stalls, occupancy, legal read
activity, fatal containment, multiplier isolation and event correspondence.

Synthetic image recipes are versioned in `images.py`, included in evidence hashes,
and can be regenerated byte for byte:

```sh
.venv/bin/python src/val/building_blocks/lut_unit/images.py \
  --address-width 8 --output-width 16 --fraction-width 8 --banks 4 \
  --output build/lut-images.json
```

These fixtures verify bit-level behavior. They are not released exponential,
activation or trigonometric images and do not claim mathematical/application
accuracy, monotonicity across wrapping boundaries, energy or PPA suitability.
Actual software images need their own domain/format/quality characterization.

Native Verilator lint and Slang/Yosys structural synthesis check geometry,
clocking, latches, combinational loops and optional protection. VCS execution,
formal proof, exhaustive reduced-width equivalence, commercial lint/CDC/RDC/DFT/
low-power checks, technology mapping, physical timing, PrimePower and application
quality signoff require external tools/data and remain `NOT_RUN` locally. The
functional campaign does not close every specification coverage cross or constitute
complete physical release qualification.
