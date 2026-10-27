# Specialized Function Tile RTL and PyUVM validation

The implementation follows the [SFT specification](../../../../../specs/mosaic-blocks/mosaic-sft/README.md)
with four fixed-point FU profiles. `sft.sv` exposes the released `tile_shell`
boundary, reports tile class 2, and composes real production arithmetic and storage.
There are no Python substitutes for functional units in the simulation.

```sh
make setup
make sft-generate
make pyuvm SIM=icarus COCOTB_TOPLEVEL=sft
make sft-regression SIM=icarus
make sft-regression                       # VCS on the licensed server
```

The Python regression writes results, coverage, profile contracts, numerical
samples and a source-stability summary under `build/<sim>/sft/regression`.
`SFT_SEED`, `SFT_RANDOM_CYCLES` (minimum 1000), `SFT_REGRESSION_BUILD` and
`SFT_JOBS` control the run. The regression runner also accepts repeated `--case`
arguments for focused work. A plain `make pyuvm` runs exactly one `SftTest`.

## Reused RTL and supported profiles

Every profile reuses `tile_shell`, protected shell queues/state/codecs, input
FIFOs, `stream_join`, `bypass_network`, `register_file`, `scalar_alu`,
`vector_reduction`, dedicated `multiplier` instances for SUMSQ, `accumulator`,
`polynomial_unit_round`, `packer` and `performance_counters`.

| FU profile | Additional native units |
|---|---|
| 0 Minimal | `lut_unit`; exact scalar/reduction/format/state paths |
| 1 Balanced | `polynomial_unit` and the general scalar `multiplier` |
| 2 Norm | `reciprocal_unit` and `rsqrt_unit` |
| 3 Transformer | `exp_unit`, with both natural and base-two exponential |

Disabled FUs are absent from elaborated generate branches and the generated
capability inventory. Selecting an absent operation fails package validation.
SUMSQ remains available in Minimal without exposing a scalar multiply opcode.

The current profile generator supports synchronous body reset, two data inputs,
one to four buffered data outputs, shell widths 48 through 128, scalar input
widths 4 through 16, and the guarded table, coefficient, queue, state and reduction
geometries in `sft.sv`. Default shell width is 64; default reduction is four 16-bit
lanes into 48 bits. The exact unsigned SUMSQ growth guard uses
`2 * REDUCTION_ELEMENT_WIDTH + ceil(log2(MAX_REDUCTION_ELEMENTS + 1))`.

Elastic synchronization is the default. Profile 0 synchronization uses the same
atomic operand join without extra body input storage; the mapper supplies aligned
operands. Static RDU synchronization, FP16/BF16, asynchronous body reset and zero
shell output buffers are rejected. Approximation profiles currently retain the
released maximum of two refinement iterations, with quality selections 0/1/2.
Asynchronous shell configuration is supported and tested independently of body
reset mode. This is a declared implementation subset, not qualification of every
parameter combination listed in the specification.

## Issue, execution and retirement

The tile accepts at most one operation per enabled cycle. Each acceptance reserves
an entry in a protected ordered request queue and a `MAX_INFLIGHT` credit. The
selected external operands and optional predicate are joined atomically; repeated
sources consume their token once. Unused PASS operands are not consumed. Metadata
must match across required data operands, including opaque operation tags.

One shared FU engine executes reserved operations serially. Independent FUs do
not execute out of order in this implementation. This conservative schedule makes
RF, accumulator and persistent-reduction dependencies explicit: an older operation
retires before a younger operation reads its architectural state. It also bounds
native response ownership to one tagged FU request. Context/tag mismatches,
uncorrectable state, invalid local sources, noncanonical narrow inputs and invalid
persistent updates stop issue and enter shell-managed fatal containment.

Exact paths take three engine edges from an empty-queue acceptance to commit.
Approximation paths add the actual native request/result handshake latency;
quality, iterations, polynomial architecture and pipeline parameters remain
visible. Queue wait and output backpressure add latency. Coverage archives observed
issue-to-commit cycle sets per operation. No throughput claim assumes concurrent
iterative units.

A result first reserves all selected shell output buffers together. On that same
edge it updates any requested RF, accumulator, reduction or previous-result state.
The shell then delivers multicast copies independently. External output valid,
payload and metadata remain stable under backpressure. Local writes never occur
before reservation or for a false predicate or an errored numerical result.

## Repository-local context and programming ABI

`mosaic-contracts` is absent from this workspace. The versioned production
[contract](../../../gen/sft/contract.py) supplies local v1 fields and defaults;
[profile.json](../../../gen/sft/generated/profile.json) publishes the generated
inventory, field offsets, graph, formats, source hashes and deferred signoff work.
Native ALU and programming command encodings are reused without renumbering.

Each shell context contains:

1. A 512-bit header, schema 1, with operation, datatype, signedness, sources,
   predicate policy, output mask, local destinations, quality/model, range,
   rounding, reduction state/phase, sequence count and next context.
2. One complete selected LUT image, with `2**LUT_ADDRESS_WIDTH` output-width entries.
3. In Balanced and later profiles, `POLY_MAX_DEGREE + 1` selected-bank coefficients.
4. Zero padding to whole 64-bit configuration words.

The default image occupies 74 words. There is no extra programming interface.
Software writes every inactive context word, optionally reads it back, submits the
shell CRC-32C, validates, then activates. Header reserved bits and image padding
must be zero. Context ownership, byte strobes, CRC, version exhaustion, active
write rejection and activation safety use the actual shell.

Validation programs the selected native bank in a disjoint physical slice:
`context_id * logical_bank_count + bank`. First programming writes an invalid
bank directly. Replacement invalidates a previously committed inactive image
before writing. Every entry/required coefficient is present before native commit.
The protected loader returns validation success only after the native programming
responses complete. Validation of another inactive context cannot overwrite the
active context's table or coefficients. Activation changes the context and bank
binding together and does not start execution.

Contexts choose sources 0/1 = data input A/B, 2/3 = RF read A/B, 4 = accumulator,
5 = previous result, 6 = immediate, and 7 = zero. Minimal graphs omit RF/previous
sources, Balanced adds RF, and Flexible adds the previous result. Disabling local
chaining removes local-source and explicit local-write permissions. The generated
graph is checked during validation. RF and accumulator state carries owner,
kernel, context version, signedness and format annotations. Previous-result state
carries the same identity. Mismatched state cannot silently become a new operand.

Operation codes are ALU 0, multiply 1, LUT 2, polynomial 3, reciprocal 4, rsqrt 5,
exponential 6, reduction 7, explicit format 8, and accumulator 9. ALU opcodes 0–19
are `scalar_alu_pkg`; opcode 20 is ABS using the native subtract/pass paths.
ALU SELECT uses the separately encoded `select_condition`, independently of work
predication. Accumulator actions are clear 0, write 1, add 2 and read 3.

## Numeric and reduction behavior

Native approximation input/output formats come from the profile parameters; there
is no conversion inferred from the shell width. Narrow scalar operands require
canonical zero/sign extension. LUT input is a signed/unsigned coordinate with
`LUT_INDEX_FRACTION_WIDTH` fraction bits, with native endpoint clipping and optional
linear interpolation. LUT values use the programmed output representation.

Polynomial coefficients and inputs use `INPUT_FRAC_BITS`, matching the released
polynomial unit's common binary point. Its signed Horner state uses `INTERNAL_WIDTH`,
explicit stage rounding/saturation and the programmed result shift. Reciprocal,
rsqrt and exponential retain their native normalization, seed/ROM generation,
rounding, exceptional-input and saturation behavior. Rsqrt epsilon is an explicit
header value; it is never inserted automatically. Exponential input is signed;
the output signedness follows the context. Both exponential bases are tested.

Scalar multiplication preserves the complete `2 * INPUT_WIDTH` product. SUMSQ
uses full products before the exact reduction tree. ALU scaling shifts retain the
full shift amount, including oversized shifts. FORMAT explicitly rounds toward
zero or ties to even, then invokes the released packer for wrapping/saturating
narrowing to `OUTPUT_WIDTH`. Output extension is signedness-aware.

Format identifiers are explicit storage annotations; 0 denotes opaque native bits.
Changing an annotation does not rescale arithmetic. The mapper must schedule
FORMAT/scaling operations where binary points differ, including reduction to
approximation input and full product to the desired output representation.

Reduction operations are SUM 0, SUMSQ 1, MIN 2 and MAX 3. Phases are beat 0,
clear 1, begin 2, update 3, end 4 and read 5. A context may select the phase from
input metadata bits 32–34 using `dynamic_phase`, allowing a persistent stream
without rewriting its active context. State retains operation, count, owner,
kernel, context/version, signedness and format. UPDATE/END/READ require matching
valid state; the widened count check rejects the first over-limit beat before
commit. CLEAR invalidates state. BEGIN/UPDATE/CLEAR do not emit a result; END and
READ do. Empty policy 0 emits zero/empty, 1 emits a flagged error, and 2 suppresses
output. False predicates consume their declared input set but perform no table,
coefficient, iterative or architectural state work; false-token mode emits zero.

Result metadata preserves shell context/version and opaque application fields,
with these defined overlays:

| Field | Bits |
|---|---|
| False-token status | `CI + CONTEXT_VERSION_WIDTH` |
| Optional input reduction phase | 32–34 |
| Operation | 64–71 |
| Quality | 72–73 |
| Local numerical-model identifier | 80–111 |
| Numerical flags | 112–127 |
| Reduction count | 128–143 |
| Empty | 144 |
| Result format annotation | 152–159 |

Flag bits are error 0, overflow 1, underflow 2, saturation 3, rounding/inexact 4,
approximate/interpolated 5, low clip/zero exception 6, high clip 7, empty 8 and
false predicate 9. Native negative-rsqrt and zero-input errors emit flagged
results, with no local writes. Model IDs are qualified by the complete generated
profile and immutable context/package image.

## Lifetime, observability and evidence

Finite temporal chains advance only to a higher resident context ID after the
configured number of ordered retirements and a quiet transport boundary. Local
state survives a compatible transition unless `invalidate` is requested. Suspend
stops ingress, retires accepted work and preserves declared state; resume retains
owner/configuration. Drain retires accepted obligations. Terminate, release,
nonretained power-off and reset invalidate private state and transport. Physical
retention, UPF and power-domain qualification are outside this campaign.

Unknown active controls fail closed. An unknown reset pauses admission and public
transfers without impersonating an asserted reset. The shell records a recoverable
protocol error; accepted work can finish after controls become known, then software
clears the error at a safe boundary. Fatal body faults require coordinated reset.

Read-only owner/privileged debug addresses `0x80..0x9f` expose 32 counters. Slots
0/1 count issue/retire; 2–11 count FU dispatch cycles; 12/13 count output/credit
stall cycles; 14 false predicates; 15–17 RF, accumulator and reduction writes;
18 programming transfers; 19 context advances; 20 corrected control/loader state;
21 fatal detection; 22 idle; 23 enabled clocks; and 24 numerical error commits.
Slots 25–31 are reserved. Responses remain stable under backpressure.

The structured PyUVM agent, driver, passive monitor, scoreboard, coverage collector
and sequences reuse `mosaic_uvm` infrastructure. Independent Python integer models
reuse the existing native FU mathematical oracles; they do not predict from RTL
arithmetic signals. Checks cover actual accepted operands, ordered reservations,
bit-exact results/flags, metadata, local effects, every output copy, cancellation
ledgers, completion events, bank isolation, ownership, runtime transitions,
unknown controls and protection faults. A mapper-owned replay workload consumes
real SUMSQ results, explicitly formats them, and in Norm/Transformer profiles
replays an inverse magnitude through multiplication and output formatting. It does
not hide a private full-row buffer or claim fused RMSNorm/Softmax behavior.

The 12-profile campaign includes all FU profiles, actual defaults, small/odd
geometries, wide payloads, one-credit queues, both polynomial architectures,
synchronization 0/2, disabled features, parity, SECDED and asynchronous configuration.
Each profile adds at least 1000 seeded random scalar transactions. Standalone
Python tests check packing, interfaces, arithmetic, growth, connectivity, generator
reproducibility and guards. Strict parameter guards are driven from Python.

Each approximate profile also publishes deterministic 80-digit Decimal sample
characterization with tested interval, absolute/relative error, mean, p99, worst
witness and a content hash. These compare the Python bit models with Decimal; the integration simulations
check those models separately against RTL. The reports are not RTL sweeps or
universal function/composite error guarantees. Arbitrary programmed LUT/polynomial
functions require their own function-specific characterization.

Only Python-driven model tests and functional simulations are run. HDL assertion
suites, lint, formal, CDC/RDC, DFT, low-power checks, synthesis, timing, physical
implementation and power/energy signoff are not run. Design Compiler synthesis is
explicitly deferred. Cluster integration and complete SFT release qualification
remain separate work.
