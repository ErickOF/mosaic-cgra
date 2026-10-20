# SECDED ECC RTL and PyUVM validation

[ecc.sv](../../../rtl/basic/ecc.sv) implements the
[MOSAIC ECC specification](../../../../../specs/basic/mosaic-ecc/README.md): a
combinational shortened extended Hamming codec with independent encode and decode
ports. It corrects every single-bit codeword error and detects every double-bit
error. It has no clock, reset, valid, ready, memory, or scrub scheduler.

## Geometry and implementation

The default protects 32 data bits with six Hamming parity bits and one overall
parity bit, giving a 39-bit codeword. The supported implementation range is
`1 <= DATA_WIDTH <= 256`. Invalid, unknown, negative, oversized, and above-cap
widths fail elaboration. The cap bounds supported tool elaboration; it is not a
claim that physical signoff or full formal release qualification has completed.

An elaboration-time constant function derives the smallest positive `P` for
which `2**P >= DATA_WIDTH + P + 1`. Powers use 64-bit intermediates. Hamming,
codeword, and position widths are local derived values and cannot be independently
configured. Safe fallback dimensions allow invalid parameters to reach the
elaboration guard without allocating enormous or negative port vectors.

Conceptual one-based Hamming position `u` occupies codeword bit `u-1`. Powers of
two contain even Hamming parity. Data bits occupy the remaining positions in
ascending order; the overall even-parity bit is the most-significant codeword
bit. Static parity coverage masks and reduction XORs permit balanced trees.
No external generator or layout table is required.

The common `decoder` generates the bounded one-hot correction mask. ECC status
classification does not depend on that helper's fail-closed select-valid flag.
The common `operand_isolation` clamps an uncorrectable codeword to zero before
data extraction, protecting both data use and external scrub writeback.

The implementation follows the explicit bit layout and status meanings in the
specification. It uses no external contracts package or dependency lockfile.
Reports hash the current RTL, both common dependencies, suite components, shared
helpers, and Makefile to identify the tested source snapshot.

## Decode and scrub behavior

| Syndrome | Overall mismatch | Result |
| --- | ---: | --- |
| Zero | 0 | No error; preserve codeword |
| Zero | 1 | Correct the overall parity bit |
| Within the Hamming field, nonzero | 1 | Correct bit `syndrome-1` |
| Nonzero | 0 | Uncorrectable; fail closed |
| Beyond the Hamming field | 1 | Unsafe shortened-code pattern; fail closed |

Exactly one status is high for a known received word. Corrected results assert
scrub and position-valid, report the zero-based corrected bit index, and supply
the repaired complete codeword. No-error and uncorrectable results report zero
position with position-valid low. Uncorrectable results also clear decoded data,
corrected codeword, and scrub.

Unknown received bits propagate through parity and syndrome checks. Four-state
classification expressions cannot turn an unknown word into a known no-error or
corrected status. A provably unsafe unknown pattern may still fail closed.
Encode-side unknowns do not contaminate the independent decode cone, and received
unknowns do not contaminate the independent encoder.

SECDED guarantees apply to at most two flipped bits. Larger faults can alias a
different valid word, be miscorrected, or be classified uncorrectable. The suite
explicitly demonstrates both miscorrection and undetected corruption; a corrected
flag is not evidence of the physical number of faults.

Scrub arbitration, address/ownership tracking, atomic writeback, partial-write
read-modify-write, recovery, and valid qualification remain external controller
responsibilities. The codec supplies combinational results and never writes
memory or buffers an error event.

## Running

From `mosaic-cgra`:

```sh
make setup
make ecc-regression                         # VCS on the licensed server
make ecc-regression SIM=icarus              # Native four-state simulation
make pyuvm SIM=icarus COCOTB_TOPLEVEL=ecc
```

The Makefile supplies ordered decoder/isolation/codec sources for simulation and
synthesis. Explicit `VERILOG_SOURCES` overrides take precedence.

```sh
make ecc-regression SIM=icarus ECC_SEED=1234 ECC_RANDOM_CYCLES=3000 \
  ECC_REGRESSION_BUILD="$(pwd)/build/ecc-custom"

.venv/bin/python src/val/basic/ecc/run_ecc_regression.py \
  --sim icarus --build-dir build/ecc-focused --case width8 --case width32
```

Focused cases retain all parameter guards. Seeds add the full-matrix index, so a
focused case retains its original campaign seed. The runner works from another
directory and accepts compatible alternate implementations through `--rtl`.
Missing tools or recognized license failures report `NOT_RUN` and exit nonzero.

## Verification and coverage

The suite separates configuration, transactions, sequences, driver, monitor,
mathematical model, scoreboard, coverage, agent, environment, and test entry
point. It reuses shared PyUVM wiring, four-state utilities, simulator execution,
exact JUnit validation, and coverage-report infrastructure.

The mathematical reference derives conceptual data positions independently. It
calculates a syndrome by XORing the positions of received one-bits, rather than
copying RTL masks or generated tables. The encoder places data and uses this
column sum to calculate parity. The decoder follows the specification's table.
Immutable geometry and bounded reference-result caches avoid redundant work;
every real output is still compared during both settled and held sampling.

Twenty profiles cover widths `1, 2, 4, 5, 8, 11, 12, 16, 26, 27, 32, 57, 58, 64,
120, 121, 128, 247, 248, 256`. They include every parity-count boundary through
the implementation cap and common 8/16/32/64/128/256-bit words. These are local
validation profiles, not a technology-qualified release matrix.

Each profile covers:

- Zero, ones, alternating, walking-one, walking-zero, and seeded random data.
- Every single-bit codeword fault on zero and all-one payloads, including every
  data bit, every Hamming parity bit, and the overall parity bit.
- Every unordered two-bit codeword pair on a reproducible nonzero payload. No
  width substitutes a proof waiver for exhaustive pair simulation.
- Every syndrome value crossed with both overall-parity outcomes, including
  all unused shortened-code positions.
- Representative three-bit faults and explicit larger-fault alias examples.
- Every encode and decode input bit individually X and Z, all-X/all-Z and mixed
  patterns, simultaneous independent activity, and stable repeated evaluations.
- At least 1000 random trials per profile (2000 by default), with independently
  changing encode data and zero-, one-, two-, three-, or four-bit decode faults.

Widths through eight data bits also exhaustively encode all data values; profiles
with at most 13 codeword bits exhaustively decode every binary received word.
All 11 output ports are checked, including repaired codeword, position, syndrome,
overall parity, all status flags, and scrub. Known fault metadata additionally
checks restoration and double-error rejection directly against the original word.

Seventeen coverage goals require every corrected position and role, every fault
pair and role pair, syndrome/parity cross, data pattern, unknown input bit/state,
larger-fault classification, scrub role, and independent cone-transition cross.
The minimal four-bit code has no uncorrectable pattern of weight greater than
two; full Hamming fields have no unused syndrome positions. These exclusions are
recorded per profile. Missing reachable bins fail the test.

Continuous monitors reject finite held-output pulses and activity in one cone
while only the other cone's input changes. Optional internal checking also
compares the correction mask. Unknown inputs are intentional stimuli, not
protocol errors: this codec has no valid port. A consuming integration must add
known-codeword assertions under its own valid qualification.

## Reports and external scope

Each profile writes fresh `results.xml`, `coverage.json`, `parameters.json`, and
`simulation.log`; the campaign writes `summary.json`. These record actual checked
profiles, geometry, seeds, all pair bins, unknown cases, source hashes, and tool
scope. Seven parameter guards check zero, negative, unknown, above-cap, and
host-integer/oversized inputs. Failed or skipped tests cannot count as passing.

Direct settings use `ECC_DATA_WIDTH`, `ECC_SEED`, `ECC_RANDOM_CYCLES`,
`ECC_COVERAGE_FILE`, and `ECC_CHECK_INTERNALS`. Match expected width with compiler
overrides. Setting `ECC_CHECK_INTERNALS=0` enables port-only checks and reports
private structural observation as `NOT_RUN`. `TEST_SETTLE_NS` must be zero; this
suite models zero-delay combinational RTL and does not claim SDF timing support.

Native VCS, HDL SVA, full formal qualification, commercial lint, CDC/RDC, DFT,
UPF, technology synthesis, PrimeTime, PrimePower, canonical contract integration,
and scrub/partial-write controllers need their respective tool or integration
flows. Missing runs remain `NOT_RUN`; functional simulation is not physical or
reliability signoff.

## Local verification

Icarus Verilog 12.0, cocotb 2.1.0, and PyUVM 5.0.0 passed all 20 width profiles
and seven strict elaboration guards. Every profile met all 17 mandatory goals.
Coverage includes all 1,579 single-bit positions and 136,058 unordered double-bit
pairs across the matrix. The suite checked 208,123 settled and held samples each
(416,246 observations), including 40,000 randomized trials. The 256-bit profile
alone checks all 35,245 pairs in its 266-bit codeword.

Verilator `--lint-only --timing -Wall` passed all 20 widths without warnings or
waivers. Twenty-three injected defects were detected, including layout/parity
errors, wrong correction positions, incorrect shortened-code handling, missing
fail-closed outputs or scrub flags, unknown sanitization, cross-cone coupling,
and 1 ps pulses. Portable Yosys structure checks passed all 60 width/usage
combinations with no latches, registers, memory, or unresolved references. Both
unused encoder and unused decoder cones were removed in their respective modes.

Yosys SAT proved arbitrary binary data with zero, one, or two distinct in-range
fault bits for data widths 1, 2, 4, 5, 8, and 11. Proofs include restoration,
classification, syndrome, scrub, position, and fail-closed fields. The other 14
widths reached the local ten-second proof limit and remain `NOT_RUN` for that
proof; exhaustive pair simulation passed at every width. These partial binary
proofs do not establish complete formal release qualification or analog fault
assumptions. Logs retain the source hash used for each proof attempt.

All 31 existing synthesis/power tests passed with their tool stubs. Port-only
validation and a focused run from `/tmp` with seed 46 also passed. Native VCS
was unavailable and explicitly reports `NOT_RUN`. Evidence is under
`build/validation/ecc-final` and the neighboring `ecc-*` directories; build
artifacts remain ignored by Git.
