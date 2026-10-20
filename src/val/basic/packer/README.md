# Element packer and unpacker validation

This PyUVM suite checks `src/rtl/basic/packer.sv` against
`specs/basic/mosaic-packer/README.md`. Every accepted beat contains the same
`NUM_ELEMENTS` logical elements at input and output; there is no accumulation,
serialization, rescaling, rounding, or mixed-signedness conversion.

Lane zero occupies the least-significant element. A valid lane is zero extended,
sign extended, forwarded, truncated to low bits, or saturated according to the
width relation and the explicit Boolean controls. Complete lane reversal moves
data, validity, overflow and saturation together. Invalid lanes are zero and do
not contaminate any valid lane or aggregate flag, including with X/Z source data.

## Parameters, state and reuse

| Parameter | Default | Restriction |
| --- | --- | --- |
| `NUM_ELEMENTS` | 4 | Positive integer |
| `SRC_ELEMENT_WIDTH` | 8 | Positive integer |
| `DST_ELEMENT_WIDTH` | 16 | Positive integer |
| `USER_WIDTH` | 1 | Positive integer |
| `SUPPORT_SIGNED` | 1 | Exactly 0 or 1 |
| `SUPPORT_SATURATION` | 1 | Exactly 0 or 1 |
| `SUPPORT_REVERSE` | 1 | Exactly 0 or 1 |
| `REGISTER_OUTPUTS` | 0 | Exactly 0 or 1 |
| `ASYNC_RESET` | 0 | Exactly 0 or 1 |

The baseline accepts arbitrary positive element widths, including one-bit and
non-power-of-two widths. Input/output bus widths are derived local parameters,
`NUM_ELEMENTS * SRC_ELEMENT_WIDTH` and `NUM_ELEMENTS * DST_ELEMENT_WIDTH`.
They cannot be configured independently. Invalid parameters are rejected during
elaboration by `packer_parameters_must_be_valid`. Safe declaration sizes keep
unknown or negative dimensions from allocating a malformed datapath first.

Common `operand_isolation` instances clamp each invalid/idle source element
before conversion and clamp the complete output payload whenever output valid
is low. Common `dff` instances implement the optional one-entry elastic output.
The registered payload captures only an accepted conversion, and reset clears
both payload and validity. Flush clears validity on the active edge and leaves
the payload unchanged; output clamping hides that disposable stale payload.

Boolean feature parameters select generate branches. Disabled signed, saturation,
reverse and registered conversion logic is absent from the corresponding profile.
All registers use `i_clk`; there is no internal clock or power gate.

The combinational profile has zero registered latency and connects ready/valid
through the legal conversion. The registered profile adds one cycle, holds every
output field during backpressure, and permits consume-and-replace without a
bubble. Changing input mode does not reinterpret a buffered result.

Runtime controls are qualified by `i_valid`, which declares that conversion
controls are valid. An active unsupported signed/reverse/saturation request, or
saturation requested without narrowing, raises a nonsticky configuration error.
It blocks new input while an older registered output may remain stalled or drain.
Idle controls are ignored. Reset and flush clamp ready, valid, error and payload
outputs; `o_busy` reflects underlying stored validity until the selected reset or
flush event clears it.

This implementation uses the specification's Boolean ports and lane layout, with
opaque user metadata. It defines no additional conversion encodings or contract
package. Canonical external `mosaic-contracts` qualification remains `NOT_RUN`,
consistent with the repository's existing convention. Ordered RTL dependencies
are discovered by Make and recorded by source hash in validation evidence; no
dependency lockfile is introduced.

## Running

```sh
make packer-regression                       # VCS on the licensed server
make packer-regression SIM=icarus            # local four-state simulation
make pyuvm SIM=icarus COCOTB_TOPLEVEL=packer  # default-parameter profile

.venv/bin/python src/val/basic/packer/run_packer_regression.py \
  --sim icarus --build-dir build/packer-focused \
  --case n3_s8_d4_sync --case features_s5_d1_000_async
```

Make accepts `PACKER_REGRESSION_BUILD`, `PACKER_SEED` (default 20261013), and
`PACKER_RANDOM_CYCLES` (default 2000, minimum 1000). The standalone runner also
accepts `--seed`, `--random-cycles`, `--rtl`, `--sim-bin-dir`, `--make`,
`--compile-args`, `--sim-args`, and repeated `--case`. Case seeds retain their
index in the full matrix, including when a focused run is launched from another
working directory. Each run invalidates old JUnit and coverage files; changed
parameters force recompilation.

For direct parameterized simulation, set matching `PACKER_<PARAMETER>` environment
variables as expected geometry and pass actual RTL parameter overrides to the
simulator. For example:

```sh
PACKER_NUM_ELEMENTS=3 PACKER_SRC_ELEMENT_WIDTH=5 PACKER_DST_ELEMENT_WIDTH=1 \
PACKER_USER_WIDTH=3 PACKER_REGISTER_OUTPUTS=1 PACKER_ASYNC_RESET=1 \
  make pyuvm SIM=icarus COCOTB_TOPLEVEL=packer SIM_BUILD=build/packer-custom \
  COMPILE_ARGS='-Ppacker.NUM_ELEMENTS=3 -Ppacker.SRC_ELEMENT_WIDTH=5 -Ppacker.DST_ELEMENT_WIDTH=1 -Ppacker.USER_WIDTH=3 -Ppacker.REGISTER_OUTPUTS=1 -Ppacker.ASYNC_RESET=1'
```

Use a fresh direct-run build directory when changing parameters or options.
`PACKER_CHECK_INTERNALS=0` permits port-only checking of equivalent implementations,
with structural assertions explicitly `NOT_RUN`; the standard regression requires
internal checks. Use `TEST_SETTLE_NS=0` and precision of 1 ps or finer. This suite
checks zero-delay RTL and is not a delayed gate-level timing checker.

## Independent model and assertions

The reference interprets each signed source using mathematical two's-complement
value, computes unbounded Python integer limits, detects values outside that
range, and clamps or takes the destination-width modulus. It does not duplicate
the RTL discarded-bit comparisons or use host-width casts. Every valid source
maps to one destination; data, masks, both per-lane flags, aggregate flags, last,
user metadata, readiness, validity, configuration error and busy are compared.

An independent accepted-beat queue checks complete output ordering and conservation.
Consumed beats are checked before a same-edge replacement is appended. Reset and
flush explicitly cancel accepted obligations, and the final queue is drained.
No forward progress is assumed against a permanently stalled consumer.

Real DUT signals are sampled before the edge, after sequential updates, and after
a held interval. Continuous monitors catch finite pulses during quiet intervals,
including stored payload changes without acceptance and changes to a stalled
output. The actual isolated input bus and registered payload/validity are checked.
Between-edge reset pulses distinguish synchronous state preservation from
asynchronous clearing; between-edge flush pulses clamp the interface but cannot
cancel registered state until a clock edge occurs.

Normal traffic obeys producer hold and uses known active fields. Inactive lanes
deliberately carry X/Z while active lanes remain known; the isolated conversion
input and public outputs must remain uncontaminated. Unknown active controls,
valid-lane data, mask, last and metadata cause explicit protocol assertions.
Separate fresh-process negative probes inject X and Z into each field and change
every held beat field, including withdrawing valid. Detection requires the exact
decorated test to fail with the expected protocol diagnostic; skipped tests and
unrelated compiler failures cannot pass a negative probe.

## Matrix and mandatory coverage

The 330 profiles include:

- All 25 source/destination pairs drawn from 1, 4, 8, 16 and 32 bits, with 1, 3
  and 4 elements in combinational, synchronous registered and asynchronous
  registered profiles: 225 cases.
- All eight signed/saturation/reversal feature combinations for 1-to-3 widening,
  3-to-3 forwarding and 5-to-1 narrowing, each with three elements and all four
  register/reset flag combinations: 96 cases.
- Stress geometries with 9 x 64-to-17, 16 x 127-to-256 and 17 x 256-to-65 elements,
  varied user widths and all three timing profiles: 9 cases.

Each profile covers every supported runtime mode, legal direct/reversed routes,
every lane's valid/overflow/saturation states, numerical lower/in-range/upper
classes where reachable, every boundary vector at every lane, empty/full/sparse
masks, last by backpressure, and zero/nonzero metadata. Small source elements up
to four bits are exhaustive. Directed traffic tests unsigned and signed limits,
one-bit signed saturation, prolonged stalls, peak throughput, reset/flush by
occupancy, illegal modes and all configuration-error causes, old-result draining
under an illegal input request, and seeded randomized traffic.

Coverage goals are profile-specific and mandatory. Unreachable bins are identified
by width relation, disabled feature, unsigned range, lane count or combinational
implementation, rather than counted as missing hits. The runner requires all goals,
matching parameters/seed/random count, exactly one unskipped
`test_packer.PackerTest`, internal assertions, all 41 strict parameter guards,
and all 90 protocol probes.

Each campaign writes `summary.json` plus per-case JUnit, coverage and simulator
logs below its build directory. Source hashes include both common dependencies,
the core RTL, every suite/shared Python helper and the Makefile. Negative-probe
JUnit failures are expected and are validated by the summary.

## Local evidence

The local 2026-10-13 Icarus run passed all 330 profiles, each with 19 to 21
mandatory coverage goals. It checked 660,000 randomized cycles and 2,324,664
pre-edge/post-edge/held observations. Of 419,725 accepted beats, 411,636 were
consumed and 8,089 were explicitly canceled by reset or flush.

| Check | Result | Evidence under `build/validation/` |
| --- | --- | --- |
| Full matrix, 41 elaboration guards and 90 protocol probes | PASS | `packer-final/summary.json` |
| Focused run from `/tmp`, seed 42 and 1000 random cycles | PASS | `packer-custom/summary.json` |
| Direct Make invocation with port-only checking | PASS; internals NOT_RUN | `packer-port-only/coverage.json` |
| All-profile Verilator lint without warnings or waivers | PASS | `packer-lint/summary.json` |
| All-profile Yosys state, feature and clock checks | PASS | `packer-structure/summary.json` |
| 26 intentionally broken implementations detected | PASS | `packer-mutations/summary.json` |
| Existing stubbed synthesis/power flow tests | PASS, 31 tests | `packer-flow-tests.log` |
| Native VCS | NOT_RUN, executable unavailable | `packer-vcs/summary.json` |

Mutation checks exercise sign extension, representability, unsigned overflow,
saturation direction and one-bit limits, data/flag reversal, lane and idle
isolation, output clamping, aggregate flags, metadata, configuration legality,
elastic replacement, accepted-only capture, old-result draining under input
error, flush, both reset styles, and four finite 1 ps output pulses.
Portable structural checks confirm no latches, memories or unresolved references;
combinational profiles have no state, registered state uses the requested reset
style and `i_clk` directly, and disabled features leave no conversion cells.
Local static/mutation probe scripts and reports remain in the ignored build
directory. The maintained regression is the PyUVM runner documented above.

Named-port line wrapping changed while the matrix was running. Original reports
retain their exact tested-source hashes; `packer-source-audit.json` verifies that
the final RTL differs only in whitespace from the archived tested source. The
formatted file was checked directly with three focused profiles plus all 41 guards
and 90 probes (`packer-current-format/summary.json`), and all-profile lint and
structural checks were refreshed for its current hash.

## External qualification

The implementation and PyUVM suite provide local functional evidence. Full formal
safety/liveness, bound HDL SVA, commercial VC Lint, CDC/RDC, DFT, VC LP, technology
synthesis, physical timing/power and canonical-contract qualification are separate
checks and remain `NOT_RUN` unless executed with the required tools and inputs.
Portable lint/structural synthesis does not replace licensed technology signoff.

Integration must constrain a coherent single-clock interface, synchronize
asynchronous reset release externally, prevent ready-valid combinational loops,
and drain or flush accepted state before changing ownership/context. Formal
liveness requires eventual downstream ready. Native VCS execution needs its
executable/license; technology synthesis and power flows additionally need the
server's library setup, cell models, constraints and representative activity.
