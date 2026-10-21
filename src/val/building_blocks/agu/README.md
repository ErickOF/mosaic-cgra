# AGU PyUVM validation

This suite checks [the regular address-generation specification](../../../../../specs/building-blocks/mosaic-agu/README.md)
against `src/rtl/building_blocks/agu.sv`. It uses the normal PyUVM test,
environment, agent, sequencer, driver, monitor, scoreboard and coverage hierarchy.
Shared `mosaic_uvm` components provide wiring, four-state conversion, simulator
execution, exact JUnit validation and evidence hashes. Python 3.10 or newer is
required; the local campaign uses Python 3.12, cocotb 2.1 and PyUVM 5.0.

## Running

```sh
make agu-regression                  # VCS, with a working installation/license
make agu-regression SIM=icarus       # native four-state RTL simulation
make pyuvm SIM=icarus COCOTB_TOPLEVEL=agu
```

The regression has 32 profiles spanning address widths `1, 3, 4, 8, 32, 64`,
count widths `1, 2, 3, 4, 8, 16`, maximum element sizes `1, 2, 4, 8, 16`,
different metadata widths and both reset styles. The default hardware geometry
is also covered. Set `AGU_SEED`, `AGU_RANDOM_CYCLES` (at least 1000) and
`AGU_REGRESSION_BUILD` to configure a campaign. The default is 2000 random
clock opportunities per profile, in addition to directed and exhaustive traffic.

Select a profile using the runner directly:

```sh
.venv/bin/python src/val/building_blocks/agu/run_agu_regression.py \
  --sim icarus --build-dir build/icarus/agu/selected \
  --case w32_c16_e16_s2_h4_t8_a0
```

`summary.json`, profile `coverage.json`, simulator logs, `parameters.json` and
JUnit `results.xml` are written under the selected build directory. The runner
requires the expected test exactly once, matching parameters and seed, every
mandatory goal, storage assertions and the HDL checker. It records source,
dependency, shared-helper and Makefile hashes. Missing tools/licenses produce
`NOT_RUN`; a partial or failing campaign cannot produce `PASS`.

## Hardware and reuse

The implementation reuses common `counter` instances for inner index, outer
index and accepted-address count, `dff` for captured descriptors, addresses and
control, and `operand_isolation` for adder operands and inactive outputs.
One extended address adder is shared by inner and row-base updates. It accepts
one address each cycle at full downstream readiness. No generated clock,
descriptor queue, request issuance, memory response handling, cancellation or
power retention is added.

`agu_pkg.sv` defines local mode and error enums. As requested for earlier MOSAIC
modules, this implementation uses repository definitions rather than introducing
an external `mosaic-contracts` dependency or a dependency JSON manifest. Mode
values match the specification. The error encoding below is repository-local;
an integration using an external contract must map and qualify it explicitly.

| Code | Enum suffix | Meaning |
| --- | --- | --- |
| 0 | `NONE` | No error |
| 1 | `MODE` | Reserved or unknown mode |
| 2 | `INNER_COUNT` | Zero inner count |
| 3 | `OUTER_COUNT` | Zero outer count |
| 4 | `1D_OUTER_COUNT` | A 1D descriptor has more than one row |
| 5 | `ELEMENT_SIZE` | Unsupported element-size encoding |
| 6 | `BASE_ALIGNMENT` | Misaligned base |
| 7 | `INNER_ALIGNMENT` | Misaligned programmable inner stride |
| 8 | `OUTER_ALIGNMENT` | Misaligned 2D row stride |
| 9 | `UNKNOWN_FIELD` | Unknown required field other than mode |
| 10 | `UNDERFLOW` | Required successor is below zero |
| 11 | `OVERFLOW` | Required successor exceeds the address width |

The prefix is `AGU_ERR_`. Mode errors have first priority, then unknown required
fields, then the remaining descriptor classes in table order. The specification
does not otherwise order simultaneous descriptor errors. Ignored strides do
not enter knownness or alignment checks. Linear steps remain positive even if
the element-byte count is too large for the signed stride port.

Descriptor legality is resolved before capture. Illegal attempts are consumed
and clear the accepted count, but never assert started or address valid. Legal
acceptance captures all metadata and makes the first address valid after that
edge. Final acceptance completes without calculating an unused successor.
A required out-of-range successor stops generation with the current transfer
counted, no wrapped output, and no completion pulse.

Control, counters, error and pulses reset. Captured descriptor and address
storage has no architectural reset; inactive output isolation makes it
unobservable. All address and metadata outputs are zero while inactive.
Synchronous reset changes registered outputs at the sampling edge;
asynchronous assertion changes them immediately. Descriptor ready is suppressed
combinationally during reset and inactive error clear. Error clear during active
generation is ignored. Unknown output ready holds the sequence, count and
transfer/completion pulses. No timeout is imposed.

## Verification mapping

The Python model computes each address independently as
`base + row * outer_step + column * inner_step` using unbounded integers.
It tracks descriptor ownership, indices, accepted transfers, completion and
sticky errors. It never seeds functional expectations from DUT storage or uses
the DUT's previous address as the arithmetic reference.

The monitor observes actual pre-NBA rising-edge ports, settled pre/post-edge
ports and a held interval. Checks cover every address, index, marker, identifier,
direction, element size, EOS, count, ready/valid and pulse. Storage observations
verify descriptor capture, accepted-only writes, disabled 1D row updates,
backpressure holds and unreset payload behavior. Both extended adder operands
must be zero while idle, stalled, final, reset-qualified or in sticky error.
Continuous waveform observations catch between-edge output/storage changes;
raw observations serve hold assertions only.

Directed traffic includes:

- Every mode and element size; positive, zero and negative inner/row strides;
  minimum and maximum signed strides at zero, midpoint and maximum bases.
- One/multiple element and row classes, power-of-two and non-power-of-two row
  lengths, and maximum count encodings. Large maximum counts run bounded
  prefixes followed by reset; count widths up to four also complete the full
  maximum-count product. No claim is made to complete `65535 * 65535` transfers.
- Contiguous streaming, matrix row/column, convolution-window and repeated
  address shapes; full-rate readiness, bursty stalls, 32-cycle stalls at each
  marker shape, unknown ready, waiting descriptors and active error clear.
- Base and positive/negative stride misalignment for every multi-byte element
  size; every reachable descriptor error; inner and row range failures at the
  first six reachable positions, final elements with invalid unused successors,
  sticky-error hold, clear and restart.
- All X/Z required descriptor fields and ignored strides, changing invalid
  inputs, both directions, zero/maximum identifiers, EOS enable, and reset in
  idle, active, stalled and error lifetimes, including clockless reset pulses.
- Seeded random descriptors, metadata and bursty ready, with descriptors held
  stable while awaiting acceptance and explicit reset/error recovery.

For `ADDR_WIDTH=3`, `COUNT_WIDTH=2`, `MAX_ELEMENT_BYTES=2`, every legal binary
base/count/stride/size descriptor is simulated with full-rate and alternating
ready. Ignored strides use one representative value; unknown ignored values
are checked separately. This is 10,920 descriptors per reset style, excluding
the additional directed/random cases. Metadata equivalence classes are crossed
separately rather than exhaustively enumerating all identifiers.

Coverage records mode/count and mode/stride-sign crosses, every size/alignment
error cross, read/write/identifier extremes, markers, unknown fields, maximum
counts, stall duration, classified recovery, range-failure positions and real
edge observations. Profile waivers identify impossible bins: one-bit counts
cannot request a successor or illegal multi-row 1D descriptor; one-byte-only
profiles cannot misalign; some size encodings have no unused values; one-bit
signed strides cannot represent positive programmable steps. Linear overflow
remains tested in that last geometry.

`agu_assertions.sv` is a port-only HDL checker with handshake-qualified history
and an independent closed-form address equation. It checks captured metadata,
indices, markers, alignment, counts, active lifetime, completion exclusivity,
reset and sticky first errors. The Makefile includes it only for native RTL
simulation, via `MOSAIC_AGU_ASSERTIONS`; synthesis and mapped-netlist source
lists contain hardware only. Its one-precision-tick delay requires zero-delay
RTL (`TEST_SETTLE_NS=0`, precision at least 1 ps).

For an explicit port-only RTL run:

```sh
AGU_CHECK_INTERNALS=0 AGU_HDL_ASSERTIONS=0 \
  make pyuvm SIM=icarus COCOTB_TOPLEVEL=agu
```

Disabled internal/HDL checks report `NOT_RUN`. This switch alone does not qualify
the suite for SDF timing; delayed gate sampling requires a separate timing-aware
driver and an independent physical verification campaign.

## Evidence and limits

Local qualification artifacts live under ignored `build/validation/agu-*`:
native PyUVM results, native-package Verilator lint, generic Yosys structure,
small-profile formal safety proofs and injected RTL fault checks. Yosys's
portable proof/synthesis view inlines the exact enum package because its
Verilog frontend lacks package imports; native lint and simulation compile
the original package and RTL directly.

The 16 formal profiles cross address widths 3/4, count widths 1/2, maximum
element bytes 1/2 and both resets. They prove unbounded binary safety after
reset against a closed-form reference with arbitrary descriptors and stalls.
Asynchronous proofs use `async2sync` clock-edge abstraction. Four-state behavior
and between-edge reset pulses are checked in native simulation; formal results
do not establish reset recovery/removal or physical timing.

Technology synthesis, VCS execution, VC Lint/CDC/RDC/LP, DFT, mapped sequential
equivalence, load/store integration, timing corners, clock-gating insertion,
physical power/energy and external contract compatibility require their own
tools and evidence. Missing results remain `NOT_RUN`; generic RTL qualification
does not establish the specification's complete physical release criteria.
