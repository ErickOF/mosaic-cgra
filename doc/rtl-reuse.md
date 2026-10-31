# RTL duplication review

The initial scan covered all 192 SystemVerilog files under `src/rtl`, including
packages and generated wrappers. Repeated function bodies and token sequences were checked
alongside their parameter, reset, unknown-value and integrity behavior.

## Shared implementations

| Repeated code | Shared implementation | Consumers |
| --- | --- | --- |
| Shortened-Hamming parity count | `common/ecc_pkg.sv::hamming_bits` | ECC, NoC codecs, LUT/seed/exp ROMs, scratchpad, tile shell, BCT, VCT and SFT |
| Striped protected-record width | `common/ecc_pkg.sv::code_width` | Shell codec/state/queue, banked scratchpad state, LUT/seed ROMs, mesh control and MST queue |
| Hamming data-position mapping | `common/ecc_pkg.sv::data_index` | ECC encoder/decoder and NoC raw-data recovery |
| Reflected CRC-32C recurrence | `common/crc_pkg.sv` | Tile shell, static mesh control, predicate proof hashes, configuration network, global NoC and system records |

The ECC helpers use wide intermediate arithmetic and retain the existing
256-data-bit SECDED stripes. Each consumer still owns its protection policy,
ownership checks, correction accounting and response to uncorrectable errors.

CRC callers retain their byte ordering, padding, initial state, final complement
and excluded fields. The byte helper preserves four-state conditional merging.
The global NoC explicitly retains its procedural branch behavior for unknown
feedback; the system record still zeroes the checksum field before hashing.
The exponential unit's IEEE CRC-32 uses a different polynomial and remains separate.

Makefile and Python source closures compile the new packages before their users.
Generated manifests, source lists, wrapper identities and the system C header are
regenerated from those closures. Interface layouts and architectural encodings do
not change; source-qualified manifest identities change with the implementation.

The RTL totals decrease from **73,573 to 73,476 lines**, a net reduction of
**97 lines**, including both new shared packages. Tests and documentation are
counted separately. Twenty-one existing module/package files use the helpers.

## Similar code retained locally

| Area | Reason |
| --- | --- |
| Data/predicate mesh topology functions | Icarus rejects package functions called from local constant functions during topology elaboration. Keep these functions local for simulator compatibility. |
| MST descriptor/identity structures | Field widths depend on module parameters. Keep the records local, as required by the repository's parameterization style. |
| Counter instrumentation wrappers | They differ in event weights, clear qualification, reset handling and peak tracking. A shared bank would require an explicit policy interface. |
| Protected/cancelable queues | Cancellation tombstones, validity witnesses, ownership and corruption handling differ. They already share the FIFO, parity and ECC primitives. |
| Generated cluster/array/system wiring | Each wrapper specializes a descriptor and qualified architecture identity. Preserve generation instead of editing copied wiring. |
| Reciprocal/rsqrt arithmetic | The iterations and normalization differ; the implementations already share multiplication, rounding, scaling and protected seed storage where appropriate. |

## Validation

Run the focused Python checks with Icarus on `PATH`:

```sh
.venv/bin/python -m unittest discover -s src/val/common/rtl_helpers -v
```

These checks cover parity and striped-code widths 1–4096, the maximum positive
32-bit width, Hamming position mapping, independently computed polynomial
division, the CRC-32C `123456789` check value, 1000 deterministic random CRC inputs
and 80 X/Z comparisons against the previous byte recurrence.

The existing Python/PyUVM campaigns check the consuming modules, including
protected and multi-stripe configurations. The system campaign exercises actual
configuration, input DMA, array computation, output DMA and fence completion:

```sh
make system-regression SIM=icarus
```

The refactor passed 48 selected PyUVM parameter profiles across 18 campaigns,
the focused system-core checks, 1537 strict parameter guards, all three helper
unit tests and elaboration of 25 Makefile source lists. Formatting equivalence is
verified against the recorded source fingerprints and SystemVerilog token streams;
regenerated manifests fingerprint the current files. Local evidence is under
`build/icarus/rtl_dedup/`.

Validation uses Python tests and Icarus simulations. Synthesis remains deferred
to Design Compiler.
