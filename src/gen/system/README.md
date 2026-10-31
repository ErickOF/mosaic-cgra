# Canonical System-RTL generator

The generator implements the synchronous, software-driven `System-RTL` subset of
[the system specification](../../../../specs/mosaic-blocks/mosaic-system/README.md).
It generates one actual released array, its native clusters and configuration
roots, a system adapter, the register package, C register header, descriptor schema,
public port catalog and ordered source closure.

```sh
make system-generate
make system-generate SYSTEM_DESCRIPTOR=/absolute/path/to/system.toml
```

`rtl.toml` is the versioned profile source. The checked-in profile contains two
MVP clusters (three BCTs and one MST each), four registered buffers, a two-entry
program queue, an eight-entry event queue and one 128-bit canonical memory port.
One-cluster arrays, 64-bit memory, 1–8 command entries, 1–32 event entries and 1–8
buffer records are supported. Full kernel examples need three buffers: program,
input and output. One kernel owns the entire selected array; concurrent kernels,
hardware scheduling and balanced four-cluster arrays are rejected.

One common `i_clk`/`i_rstb` domain supplies control, configuration, memory, array
and lifecycle logic. Native cluster clock gates are reused. System-control gating,
CDC, AXI/APB/TileLink/platform wrappers, coherence, IOMMU, trace, direct results,
retention, power gating and DVFS are unavailable and fail generation when selected.
There is no clock generation, physical-memory controller or processor in this RTL.

The canonical MMIO window is 64 KiB at base zero, with 32-bit naturally aligned
little-endian accesses. External memory uses 64-bit physical byte addresses,
16-bit nonwrapping transaction IDs, one outstanding request, 256-byte descriptor
read bursts and one-beat data reads/writes. Transfers are linear, memory-beat
aligned, 1–4096 bytes in whole beats; each native SRAM transaction transfers eight
bytes. Native descriptors retain their own published formats and validations.

Generated files are release artifacts of this schema. Edit the generator or TOML
and regenerate; manual wrapper, enum, header and offset edits are not durable.
The manifest fingerprints the system schema, core, generator and actual array
closure. Companion hashes detect changed register, descriptor, header and port
artifacts. `sources.f` contains portable paths in compilation order and requires
no dependency JSON loader.

The system does not import an absent `mosaic-contracts` package. Encodings are
explicit repository-local v1 contracts. See the
[validation and software contract](../../val/mosaic_blocks/system/README.md) for
program framing, buffer ownership, interrupts, errors and verified limits.
Synthesis and physical characterization remain deferred to Design Compiler and
the later implementation flows; this generator supplies no physical signoff claim.
