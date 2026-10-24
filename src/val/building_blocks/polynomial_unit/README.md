# Polynomial evaluation RTL and PyUVM validation

[`polynomial_unit.sv`](../../../rtl/building_blocks/polynomial_unit.sv) implements
the [polynomial-unit specification](../../../../../specs/building-blocks/mosaic-polynomial-unit/README.md).
It evaluates immutable signed fixed-point coefficient images with Horner order,
stage rounding and saturation, domain policy, and signed final scaling.

## Running

```sh
make setup
make polynomial-unit-regression SIM=icarus
make polynomial-unit-regression                  # VCS installation/license required
make pyuvm SIM=icarus COCOTB_TOPLEVEL=polynomial_unit
PYTHONPATH=src/val/building_blocks .venv/bin/python -m unittest polynomial_unit.test_model
```

All commands above run from `mosaic-cgra`. The decorated simulation test is
`test_polynomial_unit.PolynomialUnitTest`. The test, environment, agent, sequencer,
driver, passive monitor, reference model, scoreboard and coverage collector follow
the existing `mosaic_uvm` structure. There is no native HDL checker in this flow.
Synthesis is deferred to Design Compiler; lint, formal and synthesis are outside
this Python-only campaign.

Configure `POLYNOMIAL_UNIT_SEED`, `POLYNOMIAL_UNIT_RANDOM_CYCLES` (minimum 1000),
`POLYNOMIAL_UNIT_REGRESSION_BUILD`, and `POLYNOMIAL_UNIT_JOBS` (1 through 32).
Parallelism defaults to four Icarus workers or one VCS worker. Each profile has its
own build directory and a deterministic seed based on its original profile index.

Select profiles directly:

```sh
.venv/bin/python src/val/building_blocks/polynomial_unit/run_polynomial_unit_regression.py \
  --sim icarus --build-dir build/icarus/polynomial_unit/selected \
  --case degree1_a0_p0 --case degree1_a1_p0
```

The 55 profiles include the exact defaults; all architecture/protection/coverage/
reset combinations at degree three; and degrees 1, 2, 3, 4 and 8 across input/output
widths 8/16/32, accumulators 24/32/64, fractions 4/8/12/16, and 1/2/3/4/8 banks.
Both response queues include depths one, two and three. Each profile adds 2000
random cycles to directed scenarios, for 110000 random cycles in the full campaign.
The runner also checks 85 strict invalid-parameter elaboration probes.

`summary.json` records exact test identity, parameters, seeds, coverage, per-profile
logs, model tests, and architecture-equivalence groups. SHA-256 hashes cover RTL,
dependencies, Python components, shared helpers, the Makefile and the identity
image. Hashes must still match at campaign completion. Stale results are removed
before each run. Missing simulators or licenses report `NOT_RUN`.

## Hardware reuse and numerical behavior

The arithmetic helpers are separate files:

- `polynomial_unit_horner.sv` reuses the existing combinational `multiplier`.
  Operands are sign extended to its common operand width; no significant product
  bits are discarded before fractional rescaling.
- `polynomial_unit_round.sv` rounds unsigned magnitude and restores sign. It
  implements truncation toward zero and nearest-even, including negative ties.
- `polynomial_unit_scale.sv` retains sufficient width for the largest legal left
  shift before output saturation. It shares the magnitude-rounding helper for
  right shifts.

Coefficient storage reuses `lut_unit_bank`, including its existing parity and
striped SECDED implementations. Bank selection reuses `decoder` and `mux`.
Configuration, version, coverage, references and iterative ownership reuse
`event_barrier_state`; elastic stages and both response queues reuse
`event_barrier_queue`, which composes common FIFOs. These helpers also reuse DFFs,
operand isolation, parity and ECC. No existing common module is modified.

Iterative mode uses one coefficient-memory copy per bank and one multiplier. It
reads the highest coefficient at acceptance, then only the coefficient for the
current committed Horner step. An ordinary degree-`d` evaluation becomes
result-valid after `d + 1` edges and can accept its replacement on the result
creation edge. Predicated and known illegal requests bypass arithmetic and return
after one edge when unstalled.

Unrolled mode has `MAX_DEGREE + 1` elastic positions, including initialization.
It uses one multiplier per Horner position and replicates coefficient storage per
read position. Every copy receives the same legal programming write. Each position
reads only its selected coefficient when a numeric stage commits; unused positions
bypass. Fixed unstalled latency is `MAX_DEGREE + 1`, including predicated and error
tokens, and initiation interval is one. A separate result queue absorbs stalls.

Both architectures clamp every intermediate sum, propagate inexact/saturation
flags, and share final scaling. Latency assertions exercise every supported degree.
The full campaign also compares observed arithmetic response traces between
matching iterative and unrolled profiles, excluding timing and generated tags.

## Programming, ownership and recovery

Every accepted known program operation creates one ordered response. Program fields
must be known, including unused fields. Unknown active fields are rejected by
withholding readiness and setting a recoverable diagnostic. Known illegal commands
are consumed and return an error response. Request fields follow the same rule;
an invalid bank still returns an error when predicate is false.

For each bank:

1. Invalidate while no accepted request or queued result references it.
2. Write coefficients in ascending-power order; readback is available independently
   of evaluation.
3. Commit degree, inclusive signed domain, policy, rounding, shift and image IDs.
4. Evaluate the immutable image. Commit increments version modulo its width.

With coverage tracking enabled, commit requires slots zero through degree. The
complete bitmap requires every physical coefficient slot. With tracking disabled,
software owns completeness and the bitmap is high for every bank after reset
release. Coefficient payload does not reset. Reset invalidates metadata and
coverage; invalidation preserves payload and version while clearing metadata,
coverage and recoverable bank-integrity ownership.

Lifecycle exclusion is per bank: accepted requests retain references until their
result transfers, including predicated and range-error responses. Invalidation of
a referenced bank returns `BUSY`, even if its last result transfers on that edge.
Commit/invalidate commands block same-bank acceptance on their edge. Other banks
may evaluate concurrently with programming.

Coefficient parity detects errors. SECDED corrects a single-bit error on each read;
there is no automatic scrub. Uncorrectable reads return zero-data errors and a
visible-bank fault blocks new evaluations and commits. Accepted work and program
responses can still drain. Flush preserves bank faults. Explicit invalidation
clears the affected fault, after which software can write, verify and recommit.
Control, ownership, metadata, stage and queue faults require reset. Protected
profiles use parity for those control records, independently of coefficient
SECDED; an independent reference census also checks bank ownership in every mode.
This protection detects the exercised faults; it does not claim arbitrary
multiple-bit fault tolerance for control state.

Drain blocks requests and allows accepted results to retire; program commands wait
until evaluation is empty. Flush discards evaluation tokens/results, clears their
references and recoverable error, and preserves coefficient images and program
responses. Program responses pause at flush and resume afterward. `o_flushed`
pulses when evaluation work was discarded. Fatal state survives flush. Unknown
handshake controls freeze transfers and report a diagnostic; reset assertion
clamps interfaces, with state reset on an edge or asynchronously as configured.

## Encodings

[`polynomial_unit_pkg.sv`](../../../rtl/building_blocks/polynomial_unit_pkg.sv)
defines repository-local enums. No external `mosaic-contracts` package or dependency
manifest is used. Module-width-dependent packed records remain in the RTL.

| Field | Encoding |
| --- | --- |
| Architecture | 0 iterative, 1 unrolled |
| Programming | 0 write, 1 read, 2 commit, 3 invalidate |
| Range policy | 0 clip, 1 error |
| Rounding | 0 toward zero, 1 nearest-even |
| Coefficient protection | 0 none, 1 parity, 2 SECDED |
| Errors, 5 bits | 0 none, 1 unknown, 2 bank, 3 uncommitted, 4 committed, 5 index, 6 degree, 7 domain, 8 shift, 9 incomplete, 10 busy, 11 range, 12 coefficient, 13 corrected, 14 internal |

The shift field must encode both signs of `ACCUMULATOR_WIDTH - 1`. Parameter
arithmetic rejects impossible widths and storage sizes before allocating hardware.
Consumers must coordinate version wrap, reset and flush; version tags are not a
system-wide stale-reference policy.

## Verification scope

The scoreboard uses Python integers, complete Horner evaluation and independent
coefficient-protection decoding. Rounding is additionally checked against Python
`Fraction`, `int` and nearest-even `round`. Directed tests check every degree, bank,
coefficient readback, positive and negative ties, domain endpoints, shift extremes,
reachable internal saturation, both output saturation signs, predication, illegal
requests, lifecycle failures, version wrap, concurrent interfaces, exact latency,
continuous throughput, both response stalls, drain, flush, reset and X/Z inputs.

Protection tests flip every bit of a degree-zero coefficient codeword, exercise
faults at every coefficient index and unrolled read position, inject SECDED double
faults, and corrupt iterative/pipeline ownership. They verify correction, error
results, fatal containment and recovery. This is not the exhaustive cross of every
storage copy, coefficient index and possible multiple-bit error. Pure Python codec
tests also enumerate single and double codeword faults for representative widths.

The passive monitor samples actual pre-NBA edges plus settled and held intervals.
It checks coefficient accesses, stage commits, response order, events, bank metadata,
reference ownership, invalid-payload clamps, and conservation across completion,
reset and flush. Coverage distinguishes structurally unavailable encodings and
unreachable internal saturation for wide accumulators.

`identity_image.json` is a versioned exact identity recipe generated by
`images.py`. The Python tests regenerate and compare it byte for byte. It records
formats, coefficient order, domain, IDs and analytically zero error without fitting
tools. These synthetic tests establish bit-level correctness. Activation-function
coefficient fitting, workload accuracy and application quality remain separate work.

VCS execution, lint, formal proof, CDC/RDC/DFT/low-power checks, Design Compiler
synthesis, physical implementation, PrimeTime and PrimePower remain `NOT_RUN`.
No area, timing, energy or complete physical-release qualification is claimed.
