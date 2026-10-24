# Exponential RTL and PyUVM validation

This suite implements the [exponential specification](../../../../../specs/building-blocks/mosaic-exp-unit/README.md)
with [`exp_unit.sv`](../../../rtl/building_blocks/exp_unit.sv).
It reuses the common `multiplier` for base-e conversion and interpolation,
`scalar_alu` for endpoint subtraction and addition, and `polynomial_unit_round`
for signed conversion and unsigned interpolation rounding. The arithmetic is
combinational inside the existing elastic stages; it adds no pipeline latency.
Unequal operands are extended before multiplication, preserving their complete
signed or unsigned products. Both multipliers isolate their operands when inactive.

Common `fifo`, `dff`, `counter`, `operand_isolation`, `parity`, `ecc`, `mux`, and
`decoder` RTL provide control and storage. Existing `event_barrier_state` and
`event_barrier_queue` helpers protect queue metadata and provide synchronous
parallel queue flush. The generated endpoint ROM keeps the immutable
`TABLE_SEGMENTS + 1` image and two independently protected reads required here;
the programmable LUT unit has a different programming and lookup contract.
Floor partitioning and final signed scaling remain specific to the exp unit.

## Run

```sh
make setup
make exp-unit-images
make exp-unit-regression                    # Requires VCS and its license
make exp-unit-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=exp_unit
```

The runner executes the decorated `test_exp_unit.ExpUnitTest` with separate test,
environment, agent, sequencer, driver, passive monitor, mathematical reference,
scoreboard and coverage collector. Common `mosaic_uvm` components provide wiring,
simulator execution, actual JUnit identity checks and evidence handling.
Local validation uses Python 3.12, cocotb 2.1, PyUVM 5.0 and gmpy2 2.2.1.

`EXP_UNIT_SEED` defaults to 20261021, `EXP_UNIT_RANDOM_CYCLES` to 2000 (minimum
1000), and `EXP_UNIT_REGRESSION_BUILD` to `build/<simulator>/exp_unit/regression`.
The seed advances by profile index. `EXP_UNIT_JOBS` selects independent parallel
simulations (default four for Icarus and one for VCS; range 1 through 32).
Select cases directly when needed:

```sh
.venv/bin/python src/val/building_blocks/exp_unit/run_exp_unit_regression.py \
  --sim icarus --build-dir build/exp-unit-selected \
  --case g2_p0_r0_l5_q2_features111
```

For custom direct Make runs, compiler parameters and matching
`EXP_UNIT_<PARAMETER>` environment variables must agree. Icarus accepts
`-Pexp_unit.PARAMETER=value`; VCS accepts `-pvalue+exp_unit.PARAMETER=value`.
Use a fresh direct build directory when changing parameters. The regression runner
writes parameter-file dependencies and checks every actual port width and parameter.

Validation defaults to Python-only: `EXP_UNIT_HDL_ASSERTIONS=0`. The regression
explicitly disables the optional native HDL checker and reports it as `NOT_RUN`.
Python checks cover conservation, output stability, floor reconstruction,
interpolation bounds, arithmetic capture/hold, reset and fatal containment.
The optional `EXP_UNIT_HDL_ASSERTIONS=1` direct-run checker is retained for other
flows. Synthesis and gate sources exclude it. A port-only RTL run is:

```sh
EXP_UNIT_CHECK_INTERNALS=0 EXP_UNIT_HDL_ASSERTIONS=0 \
  make pyuvm SIM=icarus COCOTB_TOPLEVEL=exp_unit
```

Private storage checking and table/ownership fault injection are omitted in that
mode and reported as `NOT_RUN`. The driver uses nominal 10 ns clock opportunities,
pre-NBA observations, settled post-edge checks and clockless intervals. It requires
zero-delay RTL and does not qualify SDF-annotated gate timing or power simulation.

## Generated constants and images

[`tools/generate_exp_unit.py`](../../../../tools/generate_exp_unit.py) emits the
[table package](../../../rtl/building_blocks/generated/exp_unit_tables_pkg.sv) and
[image evidence](../../../rtl/building_blocks/generated/exp_unit_tables.json).
Generation pins gmpy2 2.2.1 and MPFR 4.2.1. MPFR contexts provide explicit precision
and rounding controls; see the [gmpy2 documentation](https://gmpy2.readthedocs.io/en/stable/contexts.html).

The generator computes 257 endpoints and `log2(e)` with 128 fractional bits.
Directed 512-bit lower and upper bounds must round to the same integer. It then
checks every supported target fraction width directly against those bounds.
This certification prevents double rounding when deriving smaller images.
The JSON records exact master bits, SHA-256 checksums, generator/library versions,
precision and certification scope; timestamps and machine paths are excluded.

The family supports table address widths 1 through 8 and internal/constant fraction
widths 1 through 64. Internal storage may have up to 256 bits, matching the common
ECC decoder's limit, with at least two integer bits. Wider families require a
regenerated and recertified catalog. Other positive widths/depths are constrained
by the specification and explicit host-index/packed-storage bounds.
The range-width guard covers every representable input for each supported base.

```sh
.venv/bin/python tools/generate_exp_unit.py         # Regenerate artifacts
.venv/bin/python tools/generate_exp_unit.py --check # Recompute and compare
```

Both Make regression and direct runner invocations verify regeneration. The native
reference independently computes endpoints and `log2(e)` directly with MPFR; it
never reads the RTL master table or generator functions.

## Numerical contract

Input is signed two's complement. Base-e multiplication uses a full signed product
with the generated positive constant; base-2 conversion uses exact scaling or
request-controlled right rounding. Right conversion divides the magnitude and
restores sign, implementing truncation toward zero or nearest-even for negatives.
The reduced coordinate never wraps.

Two's-complement integer/fraction partitioning implements floor decomposition,
including negative nonintegers. Interpolation uses an unsigned full-width product
and rounds only after the complete product. Final scaling uses a signed shift
count with explicit positive and negative overshift cases.

Overflow compares the unrounded **approximated mantissa's rational output
magnitude** to the selected maximum. This comparison precedes output rounding,
including when truncation would otherwise hide a small excess above the maximum.
Unsigned and signed-positive modes clamp to their respective maxima. Underflow
means a positive active evaluation rounds to zero. Neither is a sticky error.
Rounded status accumulates nonzero discarded bits from conversion, interpolation
and output scaling; approximate is set on every active legal result.

For a fixed legal mode, conversion rounding is monotone; generated endpoints are
ordered; each interpolated segment is monotone and stays within its endpoints;
adjacent power-of-two segments meet at the same endpoint. Final rounding and
saturation preserve nondecreasing order. Reduced-width tests exhaust every input,
and the scoreboard checks ordered observations for monotonicity as well as exact
bit agreement.

## Elastic stages and timing

The five logical boundaries contain conversion, floor partition, endpoint lookup,
interpolation and final scaling. Additional partitions forward the same result.
Each boundary reuses a common one-entry FIFO for token/metadata control and a
separately enabled unreset arithmetic bank. Predicated and known illegal tokens
move at normal latency while their arithmetic banks hold. Empty or stalled banks
also hold. Base-e multiplication and interpolation are absent when disabled by
parameter and isolated when inactive per request.

A request accepted at rising edge `t` becomes result-valid **after edge
`t + PIPELINE_DEPTH`** without stalls. The result queue is registered, so earliest
consumption is the following edge. Initiation interval is one, including with a
one-entry output queue using consume-and-replace. Capacity is pipeline depth plus
output queue depth. Backpressure may fill empty stages and then propagates to the
request input. Responses remain ordered; healthy stalled output records are stable.

Drain prevents new acceptance while existing work retires. Flush overrides drain,
request and result transfer; it clears all tokens and queues on one clock edge,
clears recoverable error, preserves fatal error and immutable identities, and
pulses flushed only when evaluation state existed. Flush never gates asynchronous
reset. Both reset styles clear validity, ownership, errors and events; arithmetic
payload and immutable images do not reset. Asynchronous reset release must be
synchronized by integration.

All request fields must be known for acceptance, including predicated requests.
Unknown fields hold request ready low and set recoverable unknown-control status.
Unknown interface controls stop transfers and are reported. Reset is normalized
before reusable DFF banks so an X/Z reset cannot overwrite retained state.
A known unsupported base or interpolation request is accepted as a zero-data error
token. Legality has priority over predication. Legal false predicates return zero
with predicated status and preserve base/range/owner/tag metadata.

## Protection and containment

The immutable ROM has independently checked lower and upper reads. Upper lookup
is disabled without interpolation. Parity detects odd-bit changes; common SECDED
corrects one codeword bit and rejects double-bit errors. A correction permits the
correct result and emits a recoverable correction event/error. An uncorrectable
endpoint suppresses successful delivery and latches fatal table status.

Protected profiles also add parity to every occupied control word, active
arithmetic bank, output record and queue pointer/occupancy state. An independent
accepted-minus-delivered counter is compared with physical pipeline/queue occupancy
and detects token-valid corruption. This ownership protection is parity/detection,
including when table protection is SECDED; it does not promise metadata correction.

Fatal containment freezes evaluation and suppresses ready/valid outputs. Pending
tags remain owned until coordinated flush or reset discards them. Error clear
cannot recover fatal state. Flush can discard quarantined work while preserving
fatal status. Invalid response fields are zero. Normal backpressure stability is
qualified by known interface controls and nonfatal integrity.

Table/constant identity is bound to immutable generated build artifacts; there is
no programming port or startup load. A mutable ROM integration would need an
explicit image-validation/repair sequence before enabling requests.

## Repository-local encodings

[`exp_unit_pkg.sv`](../../../rtl/building_blocks/exp_unit_pkg.sv) defines base and
rounding enums, table protection and error classes. No external `mosaic-contracts`
package or dependency manifest is introduced.

| Field | Encoding |
| --- | --- |
| Base, 1 bit | e = 0; 2 = 1. |
| Rounding, 1 bit | Toward zero = 0; nearest, ties to even = 1. |
| Table protection | None = 0; parity = 1; SECDED = 2. |
| Error, 4 bits | None 0; unsupported base 1; unsupported interpolation 2; unknown control 3; corrected table 4; uncorrectable table 5; range conversion 6; identity 7; ownership 8; arithmetic 9. |

The first recoverable error remains sticky until idle error-clear or flush. Fatal
errors override it and require reset. Corrected lookup errors take priority over
simultaneous unsupported requests; unknown interface controls take priority over
recoverable request errors. Within simultaneous fatal detections, identity, range,
table, ownership and arithmetic are prioritized in that order.

Checksums use CRC-32/ISO-HDLC over little-endian, zero-padded bytes per endpoint
word, or over the generated constant's `LOG2E_FRACTION_WIDTH + 2` bits. Image and
constant IDs XOR those checksums with `0x45585001` and `0x4c324501` respectively.
These are reproducible 32-bit identifiers, not cryptographic attestations.
Quality ID uses CRC over the ten numerical-format parameters in reverse table
order as little-endian 32-bit words, clears its low four bits, then inserts
`{base, interpolation, round_mode, output_signed}`. It is zero for inactive/error
tokens. Full formats and SHA-256 evidence accompany every campaign.

## Validation and accuracy scope

The 57-profile matrix covers input/output widths 8, 16 and 32 plus a five-bit
exhaustive profile; input fractions 4/8/12/16; range fractions 12/20/28 plus reduced
and down-conversion profiles; internal widths 16/24/32/48; table address widths
2/3/4/6/8; every legal base-support combination; interpolation on/off; all three
protection modes; both resets; depths 5/6/8; queue depths 1/2/3; and narrow/default
metadata. Two profiles additionally use a 25-bit interpolation remainder with
16-bit endpoints, checking the case where the remainder is wider than the table
word. Each profile runs 2000 random cycles plus directed traffic (114000 random
cycles in the full campaign). There are 88 strict invalid-parameter elaboration
checks and four pure Python model tests using independent rational references.

Directed tests exhaust every signed input and legal mode at five/eight input bits.
Larger profiles cover endpoints, midpoints, remainder extremes reachable from the
input grid, integer neighbors, signed limits, both rounding/output modes,
predication, unsupported requests, exact reduced-format half ties, saturation,
underflow, overshifts, fixed latency, full capacity, stable persistent requests,
output stalls, drain, flush/reset in every pipeline phase, clockless intervals,
X/Z controls, lower/upper ROM faults and ownership/identity corruption.
Python scoreboards check accepted/retired conservation, occupancy limits, floor
reconstruction, interpolation bounds, reset, stable output and containment.
Private checks verify every arithmetic capture and inactive-bank hold, both full
multiplier products, signed/unsigned operand extension, operand isolation and the
rounded interpolation sum. These catch arithmetic errors even when saturation
would hide them at the public output.

[`accuracy.json`](accuracy.json) characterizes every default-profile input on the
candidate compiler interval `[-8, 0]`, separately for each base, interpolation,
rounding and output mode. It reports absolute/relative errors, percentiles,
difference from ideally quantized output, monotonicity, plateaus, and maximum error
from conversion, fractional approximation, endpoint quantization, interpolation
rounding and output quantization. In this interval, interpolated nearest-even
results differ from ideally quantized results by at most one output LSB for both
bases. Relative error near the smallest outputs is dominated by output quantization;
consult the report before choosing an application tolerance.

```sh
.venv/bin/python tools/characterize_exp_unit.py
```

The scalar report characterizes the independent equations; RTL conformance is
established separately by simulation. Other geometries need their own application
accuracy contract. Compiler/application acceptance and PPA qualification remain
unrun. No composite sigmoid, SiLU, Softmax or task-level accuracy is claimed.

Campaigns archive actual JUnit results, parameters, seeds, coverage, simulator logs,
and exact RTL/dependency/test/generator/image hashes. They rerun the pure Python
model tests, regenerate table/constant certification and scalar accuracy, compare
the versioned artifacts byte for byte, and reject source changes during a campaign.
Synthesis is deferred to Design Compiler. Formal safety/liveness,
commercial lint/CDC/RDC/DFT/LP, technology timing/area, physical implementation,
PrimeTime/PrimePower and application accuracy are separate release requirements.
Unavailable checks report `NOT_RUN`; functional success is not full release signoff.
