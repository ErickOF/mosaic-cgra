# Stream-join verification

The specification is
[`specs/basic/mosaic-stream-join/README.md`](../../../../../specs/basic/mosaic-stream-join/README.md).
The implementation is [`stream_join.sv`](../../../rtl/basic/stream_join.sv).
The decorated PyUVM test is `test_stream_join.StreamJoinTest`.

```sh
make setup
make stream-join-regression              # native VCS
make stream-join-regression SIM=icarus   # four-state RTL simulation
make pyuvm SIM=icarus COCOTB_TOPLEVEL=stream_join
```

Run selected profiles while retaining every parameter and protocol check:

```sh
.venv/bin/python src/val/basic/stream_join/run_stream_join_regression.py \
  --sim icarus --build-dir build/join-focused \
  --case n3_w8_m1 --seed 42 --random-cycles 1000
```

`--case` is repeatable. Names encode input count, per-input width and runtime-mask
selection. The seed is the base seed plus the profile's position in the complete
matrix, so filtering preserves reproducibility. The runner resolves sources from
its location, works from another directory, and accepts `--rtl`, compile/runtime
flags and a simulator binary directory. At least 1000 random edge opportunities
are required; the default is 2000 per profile.

Make settings are `STREAM_JOIN_SEED`, `STREAM_JOIN_RANDOM_CYCLES` and
`STREAM_JOIN_REGRESSION_BUILD`. Reports default to
`build/<simulator>/stream_join/regression`. `make -n` preserves existing evidence.
Direct `make pyuvm` expects `STREAM_JOIN_NUM_INPUTS`, `STREAM_JOIN_DATA_WIDTH` and
`STREAM_JOIN_HAS_REQUIRED_MASK`, defaulting to `2`, `32` and `0`. HDL parameter
overrides must match those expectations; the runner configures both sides.

`STREAM_JOIN_CHECK_PARAMETERS=0` selects port-only verification and records
elaborated-parameter assertions as `NOT_RUN`. Port widths and all functional
checks remain active. `STREAM_JOIN_COVERAGE_FILE` changes the coverage path.
Use `TEST_SETTLE_NS=0` and 1 ps or finer precision. These checks target zero-delay
RTL; timing-annotated simulation requires an appropriate sampling policy.

## RTL reuse and interface obligations

Common `operand_isolation` clamps each invalid/optional data lane and the invalid
output mask. It preserves intentional four-state payloads on active lanes.
Ready uses exclusive prefix/suffix reductions: input `k` depends on every other
required valid, its own required bit and downstream ready, independently of its
own valid. This permits the final missing producer to observe ready before
arrival. The module has no clock/reset ports, registers, memories or buffering.
The Makefile supplies ordered sources to simulation, SAIF and synthesis flows.
Reports record dependency hashes without adding a dependency lockfile.

Lane `k` occupies `[k*DATA_WIDTH +: DATA_WIDTH]`, with lane zero at the least
significant end. A nonempty complete required set makes output valid assert
combinationally. Every required input handshake coincides with output acceptance;
partial input consumption and optional input consumption are prohibited.
Invalid output data and mask are zero. Optional output lanes are always zero.
An all-zero enabled mask leaves every output/ready zero rather than producing
continuous empty operations. Disabled masking ignores `i_required`, including
X/Z values, and requires all inputs.

Every required producer asserts valid independently of ready. An early valid
operand holds valid and data until its handshake. The mask locks as soon as any
selected valid appears, even before output becomes valid or a sampling edge
occurs. It stays fixed through input waits and downstream stalls until output
acceptance. The suite completes active operations before changing masks; there
is no cancellation or reset protocol inside this DUT.

The environment checks required producers' obligations. Optional producer
traffic is owned by external routing/selection logic; the suite intentionally
perturbs it to verify suppression and does not credit optional handshakes.
Required-mask and required-valid controls must be known. Downstream ready must
be known whenever it can affect an input-ready output. With at least two missing
required inputs, or an empty mask, every ready output is already zero, so X/Z
downstream ready is harmless and tested. Optional valid/data unknowns are also
ignored. A required X/Z valid with all other required inputs valid must make
output valid unknown; the negative probes check this before reporting the
illegal control. Normal accepted operands must be known; explicit intentional
four-state tests preserve X/Z through holds, packing and handshakes.

Integration owns handshake clock domains, reset ordering of connected endpoints,
mask configuration, optional-input routing, timing boundaries and power states.
Progress requires all required producers eventually to present valid operands
and the consumer eventually to assert ready. Sources that cannot hold early
operands require buffers before the join. Large joins may require balanced
reductions or external pipeline boundaries for the target timing budget.

## PyUVM structure and assertions

Configuration, transactions, sequences, driver, monitor, model, scoreboard,
coverage, agent, environment and test live in separate files. They reuse
`mosaic_uvm` wiring, four-state conversion, pattern classification and campaign
execution/evidence validation.

The clockless DUT is tested directly. The driver schedules logical harness
sampling edges through a cocotb event; no RTL clock port or wrapper is added.
The passive monitor reads actual DUT ports before the edge, at the event, after
it and during a held interval. Non-edge transactions verify immediate changes
without crediting a handshake. These are sampled Python assertions, separate
from native HDL SVA and clocked system integration verification.

The independent functional model uses sets of required/present/missing inputs,
including set subtraction for each ready. It does not reproduce the RTL's
prefix/suffix network. On an actual observed input handshake, the scoreboard
records that lane's data and sampling edge in its reference queue. A joined
output must consume exactly its required set, with every queue entry from the
same edge and with unchanged data. No queue may retain an unmatched operand.
Per-input acceptance counts and joined-operation counts must balance.

Live signal watchers enforce early-producer and mask stability, complete output
holds under backpressure, optional/idle suppression and held output inactivity.
They detect finite protocol pulses between sample points. Mask stability starts
at the first selected arrival and is released only by a sampled output handshake.

## Matrix and coverage

The 34 profiles combine both mask modes with:

- Input counts `1, 2, 3, 4, 5, 8, 16`, each at widths `1` and `32`.
- Additional `(input count, width)` pairs `(3, 8)`, `(5, 64)` and `(16, 128)`.

Every profile requires 24 coverage goals:

- All binary valid vectors and downstream ready values for up to five inputs,
  crossed with every enabled required mask, including zero. Each control sample
  obeys the surrounding producer/mask protocol and active operations are drained.
- Every small nonzero mask, each required population, individual final arrival,
  and population/final-arrival cross. Larger configurations rotate selected sets
  around each possible final input.
- Simultaneous, forward, reverse and mixed/grouped arrival classes for each
  small mask where reachable, plus every serial permutation for up to three
  inputs. Each input also appears as the final missing producer with ready high.
- One-cycle and 32-cycle producer waits for each feasible population and
  consumer stalls for every required population; 64 consecutive joins.
- Optional valid and data as 0, 1, X and Z at each input, idle mask transitions,
  disabled-mask unknowns, irrelevant downstream-ready unknowns, and non-edge
  complete/incomplete changes.
- Zero, one, alternating, walking-one and walking-zero patterns crossed with
  every small nonzero mask; walking lane bits; every operand bit as 0, 1, X and Z
  at both acceptance and output consumption.
- Acceptance/required-vector crosses, exact atomic operand accounting,
  randomized edge count and all observation stages.

Twelve malformed parameter configurations must fail the named
`stream_join_parameters_must_be_valid` elaboration guard. `OUTPUT_WIDTH` is a
non-overridable derived local parameter.

Sixty-seven negative probes cover X/Z relevant valid/ready/mask controls,
unintentional unknown accepted operands at every bit of a three-input,
three-bit instance, blocked producer data/valid changes and finite pulses, and
active-mask removal, expansion and finite pulses. They exercise both mask modes
where applicable. Each must fail exactly the decorated test with its expected
assertion; compilation errors, missing tests and unrelated failures never count.

## Evidence and qualification scope

The runner validates native JUnit identity, geometry, every coverage goal,
seed and randomized count. Summaries include source/dependency/verification
hashes, UTC timestamps and logs. Filtered runs are marked `selected_profiles`.
Generated artifacts and supplemental local checking helpers remain under ignored
`build/validation/`.

The local Icarus campaign passed all 34 profiles, 68,000 randomized sampling
cycles, 12 parameter guards and 67 protocol probes. Across 495,504 observations,
28,941 joined operations consumed 127,300 operands, with none unmatched.
Port-only validation, five Make integration checks and all 31 existing
synthesis/power flow tests passed; the latter use their licensed-tool stubs.
The checker detected all 22 injected defects, including early partial
consumption, loss of final-missing ready, optional activity leaks, swapped lanes,
Z-to-X payload conversion and silent coercion of unknown required-valid controls.

Verilator lint passes all 34 profiles with no warnings or waivers. Yosys
structural checks confirm purely combinational, acyclic logic with no state or
memory, preserved lane connectivity, no data-to-handshake path, and no own-valid
path to that input's ready. All-required mode removes the runtime mask cone.

Supplemental binary proofs pass all 34 profiles against an independent model
that counts missing required operands. They exhaustively check valid, ready,
mask, data-lane equivalence and atomic consumption. A generated observer view's
source hash is recorded separately; simulation and lint use original RTL. These
are combinational proofs, separate from X/Z tests, temporal interface stability,
liveness, clocked integration or technology equivalence.

VCS, native HDL SVA, licensed lint/CDC/RDC/DFT/VC LP, technology synthesis and
equivalence, physical implementation, PrimeTime and PrimePower require their
tools, libraries and integration artifacts. Missing checks are `NOT_RUN`.
Standalone functional verification does not establish eventual progress or
technology release qualification.
