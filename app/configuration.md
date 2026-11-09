# CGRA configuration implications

This reference uses the same help catalog as the local Flavor Studio editor. Defaults are editor defaults; legacy FU profiles supply defaults for unspecified enables.

Hardware cost and timing effects are qualitative. Technology libraries, synthesis and implementation measurements are needed to determine area, frequency, power and energy.

## How settings interact

- Hardware settings are resolved before elaboration. Regenerate RTL and matching context images/software bindings after changing capabilities or record geometry. Runtime contexts cannot enable a FU omitted from the generated hardware.
- More tiles or lanes expose resources; useful throughput also needs independent work, appropriate schedules, routing and sufficient memory/transport bandwidth.
- The data fabric uses the widest native tile payload. A destination that cannot represent the upper payload/metadata bits stalls and reports a width error; transport does not automatically quantize, pack, narrow or reinterpret numerical formats.
- BCT/VCT response-delay settings do not automatically retime arithmetic. SFT operations share an ordered issue engine, even when multiple FUs are present or a native polynomial pipeline is unrolled.
- Clock gating controls clock activity. It does not provide power gating, retention, voltage scaling or a physical implementation.

## CGRA and identity settings

| Setting | Editor default | Meaning and implications |
| --- | --- | --- |
| `name` | my_cgra | Names the saved flavor and its output directory. This label changes the bundle identity and location; the exported Verilog top is cluster. |
| `rows` | 2 | Number of tile rows, with exactly one tile at every grid position. More positions add native tiles, local switches, configuration/state ports and wiring. Shape and placement affect routing: Manhattan distance is the minimum internal hop count. More tiles provide resources only when a workload can use them concurrently. |
| `cols` | 2 | Number of tile columns; rows and columns are independent. For the same tile count, changing the aspect ratio changes neighbor links and path lengths. Place producers near their consumers. Generated routes and application scheduling still need to match the selected placement. |
| `scratchpad_banks` | 8 | Number of independently addressed 64-bit SRAM banks. More banks add storage and bank/control hardware. Requests to different banks can benefit from banking; requests to one bank still contend. Capacity is banks × words per bank × 8 bytes. The current adapter supports up to 16 banks and exposes one host client plus one client for each MST. |
| `scratchpad_bank_words` | 1024 | Number of 64-bit words stored in each SRAM bank. Deeper banks increase capacity and address/storage requirements. Depth alone does not add banks, client ports or memory bandwidth. Banks and words must be powers of two, and total capacity must be 16 bytes to 1 MiB. |
| `cluster_id` | 0 | Logical cluster identifier exported on the generated interface. Changing the ID changes identification and the architecture manifest, rather than tile placement or arithmetic resources. Ownership permissions are configured separately. |
| `clock_gating` | true | Includes a shared clock gate controlled by the external enable. The gate can stop fabric clock activity while idle; its test/scan inputs bypass gating. Keep enable asserted while configuration, traffic or completion obligations need clocks. Disabling the option connects the fabric clock directly. This setting does not add power gating, retention, voltage scaling or clock-domain crossings. |
| `tile_id` | Per tile | Unique logical identity for this tile, independent of its coordinates. The ID identifies native control/event endpoints. Moving a tile preserves its ID; changing the ID requires matching software and configuration bindings. IDs fit 16 bits. CPT event records restrict CPT producer IDs to 0–255. |
| `tile_position` | Per tile | Zero-based row and column of a tile in the generated logical mesh. Moving/swapping tiles changes neighbors and communication distances while preserving their private parameter settings and logical IDs. Regenerate routes and software bindings for the new placement. These coordinates describe connectivity; physical placement and wire lengths are determined by the later implementation flow. |
| `context_depth` | 4 | Four stored context slots per native tile in this adapter. Contexts select runtime programs and operands within the hardware capabilities generated for that tile. They cannot create a disabled FU. Depth four is fixed in this editor. |
| `profile` | Configurable | Selects the integration backend used for a descriptor. The visual editor uses Configurable: native tile control interfaces and local-switch grid transport. Legacy Cluster-MVP descriptors retain their separately qualified composition and lifecycle controller. |
| `lifecycle_timeout` | 65535 | Compatibility field for the legacy Cluster-MVP lifecycle controller. Configurable exports native control interfaces and does not instantiate that controller. Changing this field therefore has no lifecycle timeout effect in the visual fabric. |

For R rows and C columns, there are R × C tiles and R × (C − 1) + C × (R − 1) undirected neighbor links. Maximum Manhattan distance is R + C − 2 hops; configured paths and queueing determine actual transport latency. The 16-bit tile ID space bounds a complete grid to 65,536 unique tile identities.

Scratchpad capacity is banks × words per bank × 8 bytes. Increasing bank depth adds capacity; increasing bank count also changes banking opportunities. With zero MSTs the scratchpad remains host-accessible, while native compute tiles still require stream routes rather than gaining direct SRAM clients.

## Tile classes and independent FUs

### BCT: Basic compute

Scalar integer compute for arithmetic, logic, comparisons and multiply-accumulate.

- Useful for scalar dataflow and control-adjacent arithmetic. Selecting only the operations needed by a workload can remove standalone FU implementations.
- DATA_WIDTH sizes the native payload and MAC accumulator; multiply operands have their own narrower width. RF depth and FU selection can change context encodings.

| FU switch | Function | Enabled | Disabled |
| --- | --- | --- | --- |
| `ENABLE_ALU` | Scalar integer arithmetic, logic, shifts, comparisons and selection. | Enables standalone ALU contexts at DATA_WIDTH. | Standalone ALU contexts are rejected. A MAC may retain its own final-add helper. |
| `ENABLE_MULTIPLIER` | A full product from two independently signed narrow operands. | Enables standalone multiplication using MULTIPLY_OPERAND_WIDTH. | Multiply contexts are rejected. A selected MAC can still contain an internal multiplier. |
| `ENABLE_MAC` | Multiply-add with local accumulator access and DATA_WIDTH-wide results. | Enables MAC contexts and accumulator storage/feedback; it does not enable standalone ALU or multiply operations. | MAC contexts and MAC accumulator access are rejected. |

Shared helpers required by another selected operation can remain present. For example, a MAC can retain its internal multiplier while standalone multiplication is disabled. MST load/store engines retain their own address generators and formatters.

#### BCT parameters

**Compute**

| Parameter | Default | Choices | Meaning and implications |
| --- | ---: | --- | --- |
| `FU_PROFILE` | 1 | 0, 1, 2 | Legacy preset for FU enables that are not explicitly specified. Explicit per-FU enables always override this preset. The visual checkboxes save independent enables, so choosing an operation does not require its former profile peers. |

**Storage**

| Parameter | Default | Choices | Meaning and implications |
| --- | ---: | --- | --- |
| `RF_DEPTH` | 8 | 4, 8, 16, 32 | Number of private scalar register entries. More entries retain more local intermediates but increase storage and selection logic. They do not add read/write ports. Register-address and validity fields can grow, changing the packed context image. |
| `INPUT_FIFO_DEPTH` | 2 | 1, 2, 4, 8 | Private input FIFO capacity per data port. More buffering tolerates input skew and temporary downstream stalls, using additional payload/metadata storage. Sustained service rate is still limited by the execution engine. |
| `RESULT_QUEUE_DEPTH` | 2 | 1, 2, 4, 8 | Capacity reserved for complete results awaiting retirement/output. More entries absorb output backpressure at a storage cost; they do not create arithmetic parallelism or additional output ports. |

**Multiplier**

| Parameter | Default | Choices | Meaning and implications |
| --- | ---: | --- | --- |
| `MULTIPLY_OPERAND_WIDTH` | 16 | 4, 8, 16, 32 | Width of each BCT multiply/MAC multiplicand. A full product uses twice this width and must fit DATA_WIDTH. Wider operands increase multiplication resources and reduce the unused headroom for accumulation. Narrow operands must obey the native canonical zero/sign-extension rules. |
| `MULTIPLY_LATENCY` | 1 | 0–4 | Configured BCT multiplier response delay in enabled clock edges. More response stages add registers and enabled-cycle latency. The current BCT/VCT wrappers instantiate combinational arithmetic and delay aligned results; increasing this value does not itself split the arithmetic critical path or guarantee a higher frequency. Zero selects the combinational response mode where offered. Queueing, operand waits and output backpressure can add end-to-end time. |

**ALU**

| Parameter | Default | Choices | Meaning and implications |
| --- | ---: | --- | --- |
| `ALU_LATENCY` | 1 | 0, 1 | Configured BCT ALU response delay in enabled clock edges. More response stages add registers and enabled-cycle latency. The current BCT/VCT wrappers instantiate combinational arithmetic and delay aligned results; increasing this value does not itself split the arithmetic critical path or guarantee a higher frequency. Zero selects the combinational response mode where offered. Queueing, operand waits and output backpressure can add end-to-end time. |
| `SUPPORT_MINMAX` | 1 | 0, 1 | Permits minimum and maximum comparisons. Useful for clamp, extremum and activation workloads. Disabling rejects corresponding ALU operations and, on VCT, MIN/MAX reductions. |

**MAC**

| Parameter | Default | Choices | Meaning and implications |
| --- | ---: | --- | --- |
| `MAC_LATENCY` | 1 | 0–4 | Configured BCT MAC response delay in enabled clock edges. More response stages add registers and enabled-cycle latency. The current BCT/VCT wrappers instantiate combinational arithmetic and delay aligned results; increasing this value does not itself split the arithmetic critical path or guarantee a higher frequency. Zero selects the combinational response mode where offered. Queueing, operand waits and output backpressure can add end-to-end time. |
| `ACCUMULATOR_COUNT` | 1 | 1, 2, 4, 8 | Number of private BCT MAC accumulator entries. More entries retain more independent partial sums, with additional DATA_WIDTH-wide storage, validity and operand selection. They do not add MAC execution units. |

**Pipeline**

| Parameter | Default | Choices | Meaning and implications |
| --- | ---: | --- | --- |
| `BYPASS_PROFILE` | 1 | 0, 1, 2 | Selects BCT local operand-source connectivity. Richer feedback reduces trips through external streams but adds selection/control choices. The context must explicitly choose each operand source. MAC adds its required accumulator/feedback paths even with the minimal profile. 0: Minimal graph; standalone bypass/previous-result sources need an enabled MAC. 1: Balanced graph includes bypass and previous-result feedback. 2: Flexible graph additionally permits predicate-result operands. |
| `REGISTER_BYPASS` | 0 | 0, 1 | Adds a registered stage when a BCT operation consumes bypass feedback. Registered feedback adds storage and an enabled-cycle delay on that dependency. It does not add read ports or automatically pipeline the arithmetic datapath. 0: Use the available unregistered feedback path. 1: A bypass-sourced operation includes the registered-feedback delay. |

**Protection**

| Parameter | Default | Choices | Meaning and implications |
| --- | ---: | --- | --- |
| `RF_PROTECTION` | 0 | 0, 1, 2 | Error-protection policy for scalar register data. Protection adds redundant storage and checking/correction logic to covered state. It preserves the separate ownership, format and protocol checks. 0: No redundant payload protection; protocol/ownership checks remain. 1: Parity detects odd-bit corruption but cannot correct it. 2: SECDED corrects one-bit errors and detects two-bit errors per protected codeword/stripe; it adds more redundant bits and decode logic. |
| `CONTROL_PROTECTION` | 1 | 0, 1, 2 | Error-protection policy for control, validity and ownership state. Protection adds redundant storage and checking/correction logic to covered state. It preserves the separate ownership, format and protocol checks. 0: No redundant payload protection; protocol/ownership checks remain. 1: Parity detects odd-bit corruption but cannot correct it. 2: SECDED corrects one-bit errors and detects two-bit errors per protected codeword/stripe; it adds more redundant bits and decode logic. |
| `CONTEXT_PROTECTION` | 0 | 0, 1, 2 | Error-protection policy for stored context images. Protection adds redundant storage and checking/correction logic to covered state. It preserves the separate ownership, format and protocol checks. 0: No redundant payload protection; protocol/ownership checks remain. 1: Parity detects odd-bit corruption but cannot correct it. 2: SECDED corrects one-bit errors and detects two-bit errors per protected codeword/stripe; it adds more redundant bits and decode logic. |

**Tile geometry**

| Parameter | Default | Choices | Meaning and implications |
| --- | ---: | --- | --- |
| `DATA_WIDTH` | 32 | 16, 32, 64 | Width of scalar payloads, ALU results and MAC accumulators. Wider values represent larger integers and accumulations but widen registers, arithmetic and local connections. This is integer width, not floating-point precision. Two multiply operand widths must fit this width. It can widen all grid links if it becomes the widest native tile payload. |

**Arithmetic options**

| Parameter | Default | Choices | Meaning and implications |
| --- | ---: | --- | --- |
| `SUPPORT_SATURATION` | 1 | 0, 1 | Permits saturation where an operation supports it. Runtime signedness and saturation controls still select behavior. Saturation clamps overflow to a representable limit rather than retaining only modular low bits. Keeping the capability adds limit/overflow selection logic; disabling it rejects saturating contexts and does not widen arithmetic. |

**Functional units**

| Parameter | Default | Choices | Meaning and implications |
| --- | ---: | --- | --- |
| `ENABLE_ALU` | 1 | 0, 1 | Scalar integer arithmetic, logic, shifts, comparisons and selection. This is an elaboration-time selection. Regenerate RTL and matching context programs after changing capabilities. Existing shared helpers can remain when another selected operation needs them. 0: Standalone ALU contexts are rejected. A MAC may retain its own final-add helper. 1: Enables standalone ALU contexts at DATA_WIDTH. |
| `ENABLE_MULTIPLIER` | 1 | 0, 1 | A full product from two independently signed narrow operands. This is an elaboration-time selection. Regenerate RTL and matching context programs after changing capabilities. Existing shared helpers can remain when another selected operation needs them. 0: Multiply contexts are rejected. A selected MAC can still contain an internal multiplier. 1: Enables standalone multiplication using MULTIPLY_OPERAND_WIDTH. |
| `ENABLE_MAC` | 0 | 0, 1 | Multiply-add with local accumulator access and DATA_WIDTH-wide results. This is an elaboration-time selection. Regenerate RTL and matching context programs after changing capabilities. Existing shared helpers can remain when another selected operation needs them. 0: MAC contexts and MAC accumulator access are rejected. 1: Enables MAC contexts and accumulator storage/feedback; it does not enable standalone ALU or multiply operations. |

Native implementation: [bct.sv](../src/rtl/mosaic_blocks/bct.sv).

### MST: Memory service

Memory/stream service tile with independent load and store engines.

- Use it to move data between SRAM, streams and exposed DMA endpoints. More MSTs add scratchpad clients, which still share bank and fabric bandwidth.
- AGUs and formatters are internal parts of the selected engines. The current adapter uses 128-bit stream payloads and 64-bit memory words, requiring width conversion.

| FU switch | Function | Enabled | Disabled |
| --- | --- | --- | --- |
| `ENABLE_LOAD` | Memory/DMA-to-stream operations using load channels. | Instantiates load-channel workers, including their address and formatting helpers. | Load-class descriptors are rejected before execution; load workers are omitted. |
| `ENABLE_STORE` | Stream/DMA-to-memory and store-channel forwarding operations. | Instantiates store-channel workers and their address and formatting helpers. | Store-class descriptors are rejected. Local copy also requires the store side. |

Shared helpers required by another selected operation can remain present. For example, a MAC can retain its internal multiplier while standalone multiplication is disabled. MST load/store engines retain their own address generators and formatters.

#### MST parameters

**Load engine**

| Parameter | Default | Choices | Meaning and implications |
| --- | ---: | --- | --- |
| `READ_DATA_FIFO_DEPTH` | 8 | 2, 4, 8, 16 | Buffer capacity inside memory-service read/load paths. More entries absorb response bursts and stream backpressure, using more data/metadata storage. Memory issue limits and downstream bandwidth remain separate. |

**Store engine**

| Parameter | Default | Choices | Meaning and implications |
| --- | ---: | --- | --- |
| `WRITE_DATA_FIFO_DEPTH` | 8 | 2, 4, 8, 16 | Buffer capacity inside memory-service store paths. More entries decouple stream arrivals from memory stalls. They do not increase memory port width or the count of outstanding write tags. |

**Protection**

| Parameter | Default | Choices | Meaning and implications |
| --- | ---: | --- | --- |
| `COMMAND_PROTECTION` | 0 | 0, 1, 2 | Error-protection policy for queued memory commands. Protection adds redundant storage and checking/correction logic to covered state. It preserves the separate ownership, format and protocol checks. 0: No redundant payload protection; protocol/ownership checks remain. 1: Parity detects odd-bit corruption but cannot correct it. 2: SECDED corrects one-bit errors and detects two-bit errors per protected codeword/stripe; it adds more redundant bits and decode logic. |
| `FIFO_PROTECTION` | 0 | 0, 1, 2 | Error-protection policy for memory-service fifo records. Protection adds redundant storage and checking/correction logic to covered state. It preserves the separate ownership, format and protocol checks. 0: No redundant payload protection; protocol/ownership checks remain. 1: Parity detects odd-bit corruption but cannot correct it. 2: SECDED corrects one-bit errors and detects two-bit errors per protected codeword/stripe; it adds more redundant bits and decode logic. |
| `CONTROL_PROTECTION` | 1 | 0, 1, 2 | Error-protection policy for control, validity and ownership state. Protection adds redundant storage and checking/correction logic to covered state. It preserves the separate ownership, format and protocol checks. 0: No redundant payload protection; protocol/ownership checks remain. 1: Parity detects odd-bit corruption but cannot correct it. 2: SECDED corrects one-bit errors and detects two-bit errors per protected codeword/stripe; it adds more redundant bits and decode logic. |
| `CONTEXT_PROTECTION` | 0 | 0, 1, 2 | Error-protection policy for stored context images. Protection adds redundant storage and checking/correction logic to covered state. It preserves the separate ownership, format and protocol checks. 0: No redundant payload protection; protocol/ownership checks remain. 1: Parity detects odd-bit corruption but cannot correct it. 2: SECDED corrects one-bit errors and detects two-bit errors per protected codeword/stripe; it adds more redundant bits and decode logic. |

**Address generation**

| Parameter | Default | Choices | Meaning and implications |
| --- | ---: | --- | --- |
| `SUPPORT_2D` | 1 | 0, 1 | Permits nested 2D strided address descriptors. Useful for matrix rows, tiles and pitched image accesses. It adds row/outer-count address handling; disabling it limits accepted descriptors to the simpler address modes. |
| `SUPPORT_CIRCULAR` | 0 | 0, 1 | Circular addressing requires an unreleased MST adapter. The current native MST rejects SUPPORT_CIRCULAR=1 at elaboration. Keep it disabled; this is not an available ring-buffer optimization in this flavor. 0: Supported setting for the released MST. 1: Unavailable: the released MST has no circular-address adapter. 1 is unavailable: Circular addressing requires an unreleased MST adapter. |

**Formatter**

| Parameter | Default | Choices | Meaning and implications |
| --- | ---: | --- | --- |
| `SUPPORT_UNALIGNED` | 1 | 0, 1 | Permits supported unaligned memory/stream accesses. Alignment and fragment handling can serve accesses crossing memory-word boundaries. Those accesses may need extra requests and cycles; aligned access can be cheaper. Disabling requires descriptors and endpoints that satisfy the native alignment rules. |
| `SUPPORT_WIDTH_CONVERSION` | 1 | 0, 1 | Adapts stream-beat width to memory-word width. The current MST adapter uses 128-bit streams and 64-bit memory words, so this option must remain enabled. Conversion packs/splits beats; it does not create more memory bandwidth. |
| `SUPPORT_ELEMENT_CONVERSION` | 1 | 0, 1 | Permits changes of element width inside a transfer. Useful for packing, widening and narrowing data layouts. Descriptors still choose signedness, saturation and compatible formats. Disabling requires matching source/destination element widths. |

**Functional units**

| Parameter | Default | Choices | Meaning and implications |
| --- | ---: | --- | --- |
| `ENABLE_LOAD` | 1 | 0, 1 | Memory/DMA-to-stream operations using load channels. This is an elaboration-time selection. Regenerate RTL and matching context programs after changing capabilities. Existing shared helpers can remain when another selected operation needs them. 0: Load-class descriptors are rejected before execution; load workers are omitted. 1: Instantiates load-channel workers, including their address and formatting helpers. |
| `ENABLE_STORE` | 1 | 0, 1 | Stream/DMA-to-memory and store-channel forwarding operations. This is an elaboration-time selection. Regenerate RTL and matching context programs after changing capabilities. Existing shared helpers can remain when another selected operation needs them. 0: Store-class descriptors are rejected. Local copy also requires the store side. 1: Instantiates store-channel workers and their address and formatting helpers. |

Native implementation: [mst.sv](../src/rtl/mosaic_blocks/mst.sv).

### VCT: Vector compute

Masked integer SIMD lanes, cross-lane reduction and dot products.

- More lanes process more elements per vector operation and replicate arithmetic/storage. They help only when enough independent elements and memory bandwidth are available. Complete vector operations still share the tile issue/retirement path.
- The payload is NUM_LANES × ACC_WIDTH bits, even when element operations use fewer bits. A wide VCT can therefore widen links throughout the entire generated grid.

| FU switch | Function | Enabled | Disabled |
| --- | --- | --- | --- |
| `ENABLE_LANE_ALU` | Per-element integer arithmetic, logic, shifts and comparisons. | Enables lane ALU opcodes across the selected NUM_LANES. | Lane ALU opcodes are rejected; independently selected lane multiply/MAC can remain. |
| `SUPPORT_MUL` | Independent widened multiplication in every vector lane. | Enables element products; product width is twice ELEMENT_WIDTH. | Lane multiply opcodes are rejected; dot product and MAC have independent enables. |
| `SUPPORT_MAC` | Per-lane multiply-add with ACC_WIDTH-wide accumulation. | Enables lane MAC opcodes without requiring standalone lane multiplication or ALU. | Lane MAC opcodes are rejected; other vector operations retain their own enables. |
| `ENABLE_REDUCTION` | Cross-lane SUM, MIN, MAX, AND and OR operations. | Adds the reduction path and enables scalar accumulator storage shared with dot product. | Reduction contexts are rejected; dot product can remain enabled. |
| `ENABLE_DOT_PRODUCT` | Masked products followed by an exact cross-lane sum. | Adds the dot-product path independently of lane multiply and reduction. The accumulator must cover product width plus lane-count growth. | Dot-product contexts are rejected; lane MAC and reduction remain independent. |

Shared helpers required by another selected operation can remain present. For example, a MAC can retain its internal multiplier while standalone multiplication is disabled. MST load/store engines retain their own address generators and formatters.

#### VCT parameters

**Functional units**

| Parameter | Default | Choices | Meaning and implications |
| --- | ---: | --- | --- |
| `FU_PROFILE` | 1 | 0, 1, 2 | Legacy preset for FU enables that are not explicitly specified. Explicit per-FU enables always override this preset. The visual checkboxes save independent enables, so choosing an operation does not require its former profile peers. |
| `ENABLE_LANE_ALU` | 1 | 0, 1 | Per-element integer arithmetic, logic, shifts and comparisons. This is an elaboration-time selection. Regenerate RTL and matching context programs after changing capabilities. Existing shared helpers can remain when another selected operation needs them. 0: Lane ALU opcodes are rejected; independently selected lane multiply/MAC can remain. 1: Enables lane ALU opcodes across the selected NUM_LANES. |
| `ENABLE_REDUCTION` | 1 | 0, 1 | Cross-lane SUM, MIN, MAX, AND and OR operations. This is an elaboration-time selection. Regenerate RTL and matching context programs after changing capabilities. Existing shared helpers can remain when another selected operation needs them. 0: Reduction contexts are rejected; dot product can remain enabled. 1: Adds the reduction path and enables scalar accumulator storage shared with dot product. |
| `ENABLE_DOT_PRODUCT` | 0 | 0, 1 | Masked products followed by an exact cross-lane sum. This is an elaboration-time selection. Regenerate RTL and matching context programs after changing capabilities. Existing shared helpers can remain when another selected operation needs them. 0: Dot-product contexts are rejected; lane MAC and reduction remain independent. 1: Adds the dot-product path independently of lane multiply and reduction. The accumulator must cover product width plus lane-count growth. |

**Vector lanes**

| Parameter | Default | Choices | Meaning and implications |
| --- | ---: | --- | --- |
| `NUM_LANES` | 4 | 2, 4, 8 | Number of parallel integer element lanes. More lanes replicate execution and storage and increase cross-lane reduction/dot work. They require enough valid elements and transport bandwidth to be useful. The native payload is NUM_LANES × ACC_WIDTH bits, which may widen the entire fabric. |
| `ELEMENT_WIDTH` | 8 | 4, 8, 16 | Width of a vector input element. Wider elements represent larger integers and increase lane product width. ACC_WIDTH must be at least twice this value, with extra growth for dot products. Changing element width changes payload packing and the contexts/data formats required. |
| `ACC_WIDTH` | 32 | 16, 32, 64, 128 | Width of each vector-lane accumulator slot. More bits provide accumulation/product headroom but enlarge vector registers and the native payload. This can widen every mesh link, not just this tile. Exact dot products require at least 2 × ELEMENT_WIDTH + ceil(log2(NUM_LANES)) bits. |
| `WRITE_SLICE_WIDTH` | 8 | 1, 2, 4, 8, 16 | Smallest independently valid slice of vector-register storage. Smaller slices permit finer partial writes but require more validity/mask bits. Larger slices reduce that granularity. Slice width must divide both element and accumulator widths; it does not add physical register ports. |
| `LANE_LATENCY` | 1 | 0–4 | Configured VCT lane response delay in enabled clock edges. More response stages add registers and enabled-cycle latency. The current BCT/VCT wrappers instantiate combinational arithmetic and delay aligned results; increasing this value does not itself split the arithmetic critical path or guarantee a higher frequency. Zero selects the combinational response mode where offered. Queueing, operand waits and output backpressure can add end-to-end time. |
| `SUPPORT_SATURATION` | 1 | 0, 1 | Permits saturation where an operation supports it. Runtime signedness and saturation controls still select behavior. Saturation clamps overflow to a representable limit rather than retaining only modular low bits. Keeping the capability adds limit/overflow selection logic; disabling it rejects saturating contexts and does not widen arithmetic. |
| `SUPPORT_MINMAX` | 1 | 0, 1 | Permits minimum and maximum comparisons. Useful for clamp, extremum and activation workloads. Disabling rejects corresponding ALU operations and, on VCT, MIN/MAX reductions. |

**Multiplier**

| Parameter | Default | Choices | Meaning and implications |
| --- | ---: | --- | --- |
| `SUPPORT_MUL` | 1 | 0, 1 | Independent widened multiplication in every vector lane. This is an elaboration-time selection. Regenerate RTL and matching context programs after changing capabilities. Existing shared helpers can remain when another selected operation needs them. 0: Lane multiply opcodes are rejected; dot product and MAC have independent enables. 1: Enables element products; product width is twice ELEMENT_WIDTH. |
| `MUL_LATENCY` | 1 | 0–4 | Compatibility limit for primitive lane-multiply response timing. Must fit within LANE_LATENCY. In this tile wrapper, the primitive multiplier is combinational and lane response delay is controlled by LANE_LATENCY; this parameter does not add a separate multiply pipeline. |

**MAC**

| Parameter | Default | Choices | Meaning and implications |
| --- | ---: | --- | --- |
| `SUPPORT_MAC` | 1 | 0, 1 | Per-lane multiply-add with ACC_WIDTH-wide accumulation. This is an elaboration-time selection. Regenerate RTL and matching context programs after changing capabilities. Existing shared helpers can remain when another selected operation needs them. 0: Lane MAC opcodes are rejected; other vector operations retain their own enables. 1: Enables lane MAC opcodes without requiring standalone lane multiplication or ALU. |
| `MAC_LATENCY` | 1 | 0–4 | Compatibility limit for primitive lane-MAC response timing. Must fit within LANE_LATENCY. In this tile wrapper, primitive MAC latency is zero and LANE_LATENCY controls the aligned response; this parameter does not add a separate MAC pipeline. |

**Reduction**

| Parameter | Default | Choices | Meaning and implications |
| --- | ---: | --- | --- |
| `REDUCTION_LATENCY` | 1 | 0–8 | Configured VCT reduction response delay in enabled clock edges. More response stages add registers and enabled-cycle latency. The current BCT/VCT wrappers instantiate combinational arithmetic and delay aligned results; increasing this value does not itself split the arithmetic critical path or guarantee a higher frequency. Zero selects the combinational response mode where offered. Queueing, operand waits and output backpressure can add end-to-end time. |
| `SCALAR_ACC_DEPTH` | 2 | 1, 2, 4, 8 | Persistent scalar accumulator entries for reduction/dot feedback. More entries retain more independent partial sums but add protected scalar state. They do not add reduction or dot execution units. |

**Dot product**

| Parameter | Default | Choices | Meaning and implications |
| --- | ---: | --- | --- |
| `DOT_LATENCY` | 2 | 0–8 | Configured VCT dot-product response delay in enabled clock edges. More response stages add registers and enabled-cycle latency. The current BCT/VCT wrappers instantiate combinational arithmetic and delay aligned results; increasing this value does not itself split the arithmetic critical path or guarantee a higher frequency. Zero selects the combinational response mode where offered. Queueing, operand waits and output backpressure can add end-to-end time. |

**Storage**

| Parameter | Default | Choices | Meaning and implications |
| --- | ---: | --- | --- |
| `VRF_DEPTH` | 8 | 2, 4, 8, 16, 32, 64 | Number of vector-register entries. More entries retain more vectors and can reduce external transfers, with wider storage and address selection. NUM_LANES, ACC_WIDTH and slice-validity granularity determine the size of each entry. |
| `PREDICATE_DEPTH` | 4 | 2, 4, 8, 16 | Number of local predicate register entries. More entries retain more independent masks/conditions, with additional validity and selection state. Predicate lane width is a separate setting. |
| `VECTOR_ACC_DEPTH` | 2 | 1, 2, 4, 8 | Persistent per-lane vector accumulator entries. More entries retain more vector partial sums at NUM_LANES × ACC_WIDTH bits per entry, plus validity/protection overhead. |
| `INPUT_FIFO_DEPTH` | 2 | 1, 2, 4, 8 | Private input FIFO capacity per data port. More buffering tolerates input skew and temporary downstream stalls, using additional payload/metadata storage. Sustained service rate is still limited by the execution engine. |
| `RESULT_QUEUE_DEPTH` | 2 | 1, 2, 4, 8 | Capacity reserved for complete results awaiting retirement/output. More entries absorb output backpressure at a storage cost; they do not create arithmetic parallelism or additional output ports. |

**Protection**

| Parameter | Default | Choices | Meaning and implications |
| --- | ---: | --- | --- |
| `VRF_PROTECTION` | 0 | 0, 1, 2 | Error-protection policy for vector register data. Protection adds redundant storage and checking/correction logic to covered state. It preserves the separate ownership, format and protocol checks. 0: No redundant payload protection; protocol/ownership checks remain. 1: Parity detects odd-bit corruption but cannot correct it. 2: SECDED corrects one-bit errors and detects two-bit errors per protected codeword/stripe; it adds more redundant bits and decode logic. |
| `CONTROL_PROTECTION` | 0 | 0, 1, 2 | Error-protection policy for control, validity and ownership state. Protection adds redundant storage and checking/correction logic to covered state. It preserves the separate ownership, format and protocol checks. 0: No redundant payload protection; protocol/ownership checks remain. 1: Parity detects odd-bit corruption but cannot correct it. 2: SECDED corrects one-bit errors and detects two-bit errors per protected codeword/stripe; it adds more redundant bits and decode logic. |
| `CONTEXT_PROTECTION` | 0 | 0, 1, 2 | Error-protection policy for stored context images. Protection adds redundant storage and checking/correction logic to covered state. It preserves the separate ownership, format and protocol checks. 0: No redundant payload protection; protocol/ownership checks remain. 1: Parity detects odd-bit corruption but cannot correct it. 2: SECDED corrects one-bit errors and detects two-bit errors per protected codeword/stripe; it adds more redundant bits and decode logic. |

Native implementation: [vct.sv](../src/rtl/mosaic_blocks/vct.sv).

### SFT: Special functions

Fixed-point special functions, programmable approximations and exact operations.

- Useful for lookup-based functions, nonlinear transforms and normalization. LUTs and polynomials need programmed images; reciprocal, RSQRT and exponential use native models.
- Formats and tables trade precision, range and hardware resources. A shared issue engine reserves and retires operations in order: enabling more FUs does not add issue engines. These are fixed-point/integer operations, rather than IEEE floating-point units.

| FU switch | Function | Enabled | Disabled |
| --- | --- | --- | --- |
| `ENABLE_ALU` | Exact scalar integer arithmetic and logic on the shell payload. | Enables standalone scalar ALU operations. | ALU contexts are rejected; an enabled accumulator can retain an internal add helper. |
| `ENABLE_MULTIPLIER` | Exact full-product scalar multiplication. | Enables scalar products using INPUT_WIDTH operands. | Standalone multiply contexts are rejected; other selected FUs keep their own multipliers. |
| `ENABLE_LUT` | Programmable table lookup with optional interpolation. | Adds programmable LUT banks. Table contents must be provisioned before lookup. | Lookup contexts are rejected and the LUT FU is omitted. Existing context image table slots remain reserved by this adapter. |
| `ENABLE_POLYNOMIAL` | Evaluation of a programmed polynomial in a committed input interval. | Adds coefficient banks and the selected iterative/unrolled evaluator. Coefficient storage is included in the generated context image. | Polynomial contexts are rejected and polynomial coefficient image storage is omitted. |
| `ENABLE_RECIPROCAL` | Fixed-point reciprocal approximation, 1/x. | Enables reciprocal independently of polynomial and RSQRT. Seed and internal precision control its numerical implementation. | Reciprocal contexts are rejected; RSQRT remains independently selectable. |
| `ENABLE_RSQRT` | Fixed-point reciprocal-square-root approximation, 1/sqrt(x). | Enables RSQRT independently of reciprocal and polynomial. Runtime domain and exception rules still apply. | RSQRT contexts are rejected; reciprocal remains independently selectable. |
| `ENABLE_EXPONENTIAL` | Fixed-point base-e and base-two exponential approximation. | Adds exponential range reduction, approximation tables and response stages. | Exponential contexts are rejected; no peer FU is disabled automatically. |
| `ENABLE_REDUCTION` | Exact SUM/SUMSQ/MIN/MAX and persistent phased reduction state. | Adds reduction and SUMSQ arithmetic with selected lane geometry and bounded count. | Reduction contexts are rejected and the exact reduction datapath is omitted. |
| `ENABLE_FORMATTER` | Explicit shift, rounding and narrowing to OUTPUT_WIDTH. | Enables format-conversion operations with configured rounding/saturation policies. | Format contexts are rejected. Grid links do not substitute implicit numerical conversion. |
| `ENABLE_ACCUMULATOR` | Persistent scalar clear, load, add and read operations. | Enables standalone accumulator commands and required arithmetic helpers. | Accumulator commands are rejected. State needed for other enabled local feedback operations can remain. |

Shared helpers required by another selected operation can remain present. For example, a MAC can retain its internal multiplier while standalone multiplication is disabled. MST load/store engines retain their own address generators and formatters.

#### SFT parameters

**Functional units**

| Parameter | Default | Choices | Meaning and implications |
| --- | ---: | --- | --- |
| `FU_PROFILE` | 1 | 0, 1, 2, 3 | Legacy preset for FU enables that are not explicitly specified. Explicit per-FU enables always override this preset. The visual checkboxes save independent enables, so choosing an operation does not require its former profile peers. |
| `ENABLE_ALU` | 1 | 0, 1 | Exact scalar integer arithmetic and logic on the shell payload. This is an elaboration-time selection. Regenerate RTL and matching context programs after changing capabilities. Existing shared helpers can remain when another selected operation needs them. 0: ALU contexts are rejected; an enabled accumulator can retain an internal add helper. 1: Enables standalone scalar ALU operations. |
| `ENABLE_MULTIPLIER` | 1 | 0, 1 | Exact full-product scalar multiplication. This is an elaboration-time selection. Regenerate RTL and matching context programs after changing capabilities. Existing shared helpers can remain when another selected operation needs them. 0: Standalone multiply contexts are rejected; other selected FUs keep their own multipliers. 1: Enables scalar products using INPUT_WIDTH operands. |
| `ENABLE_LUT` | 1 | 0, 1 | Programmable table lookup with optional interpolation. This is an elaboration-time selection. Regenerate RTL and matching context programs after changing capabilities. Existing shared helpers can remain when another selected operation needs them. 0: Lookup contexts are rejected and the LUT FU is omitted. Existing context image table slots remain reserved by this adapter. 1: Adds programmable LUT banks. Table contents must be provisioned before lookup. |
| `ENABLE_POLYNOMIAL` | 1 | 0, 1 | Evaluation of a programmed polynomial in a committed input interval. This is an elaboration-time selection. Regenerate RTL and matching context programs after changing capabilities. Existing shared helpers can remain when another selected operation needs them. 0: Polynomial contexts are rejected and polynomial coefficient image storage is omitted. 1: Adds coefficient banks and the selected iterative/unrolled evaluator. Coefficient storage is included in the generated context image. |
| `ENABLE_RECIPROCAL` | 0 | 0, 1 | Fixed-point reciprocal approximation, 1/x. This is an elaboration-time selection. Regenerate RTL and matching context programs after changing capabilities. Existing shared helpers can remain when another selected operation needs them. 0: Reciprocal contexts are rejected; RSQRT remains independently selectable. 1: Enables reciprocal independently of polynomial and RSQRT. Seed and internal precision control its numerical implementation. |
| `ENABLE_RSQRT` | 0 | 0, 1 | Fixed-point reciprocal-square-root approximation, 1/sqrt(x). This is an elaboration-time selection. Regenerate RTL and matching context programs after changing capabilities. Existing shared helpers can remain when another selected operation needs them. 0: RSQRT contexts are rejected; reciprocal remains independently selectable. 1: Enables RSQRT independently of reciprocal and polynomial. Runtime domain and exception rules still apply. |
| `ENABLE_EXPONENTIAL` | 0 | 0, 1 | Fixed-point base-e and base-two exponential approximation. This is an elaboration-time selection. Regenerate RTL and matching context programs after changing capabilities. Existing shared helpers can remain when another selected operation needs them. 0: Exponential contexts are rejected; no peer FU is disabled automatically. 1: Adds exponential range reduction, approximation tables and response stages. |
| `ENABLE_REDUCTION` | 1 | 0, 1 | Exact SUM/SUMSQ/MIN/MAX and persistent phased reduction state. This is an elaboration-time selection. Regenerate RTL and matching context programs after changing capabilities. Existing shared helpers can remain when another selected operation needs them. 0: Reduction contexts are rejected and the exact reduction datapath is omitted. 1: Adds reduction and SUMSQ arithmetic with selected lane geometry and bounded count. |
| `ENABLE_FORMATTER` | 1 | 0, 1 | Explicit shift, rounding and narrowing to OUTPUT_WIDTH. This is an elaboration-time selection. Regenerate RTL and matching context programs after changing capabilities. Existing shared helpers can remain when another selected operation needs them. 0: Format contexts are rejected. Grid links do not substitute implicit numerical conversion. 1: Enables format-conversion operations with configured rounding/saturation policies. |
| `ENABLE_ACCUMULATOR` | 1 | 0, 1 | Persistent scalar clear, load, add and read operations. This is an elaboration-time selection. Regenerate RTL and matching context programs after changing capabilities. Existing shared helpers can remain when another selected operation needs them. 0: Accumulator commands are rejected. State needed for other enabled local feedback operations can remain. 1: Enables standalone accumulator commands and required arithmetic helpers. |

**Number formats**

| Parameter | Default | Choices | Meaning and implications |
| --- | ---: | --- | --- |
| `INPUT_WIDTH` | 16 | 8, 12, 16 | Number of bits in a native fixed-point input operand. Increasing width with unchanged fraction bits increases representable range, not fractional resolution. It also widens the arithmetic that consumes the operand. Input values still travel in the fixed-width SFT shell payload. |
| `INPUT_FRAC_BITS` | 8 | 1–15 | Binary fractional bits in the input format. The quantization step is 2^(-fraction bits). At fixed total width, more fraction bits improve representable resolution but leave fewer bits for integer range. Regenerate inputs, coefficients/tables and software interpretation for a changed scale. Algorithmic accuracy is not determined by fraction count alone. |
| `OUTPUT_WIDTH` | 16 | 8, 16, 24, 32 | Number of bits in a native fixed-point result. With unchanged fraction bits, more bits increase output range. Narrowing can introduce rounding or saturation according to the operation; it does not resize the shell bus. LUT storage also grows with OUTPUT_WIDTH. |
| `OUTPUT_FRAC_BITS` | 12 | 1–31 | Binary fractional bits in the output format. The quantization step is 2^(-fraction bits). At fixed total width, more fraction bits improve representable resolution but leave fewer bits for integer range. Regenerate inputs, coefficients/tables and software interpretation for a changed scale. Algorithmic accuracy is not determined by fraction count alone. |
| `INTERNAL_WIDTH` | 32 | 24, 32, 40, 48, 64 | Working width used by polynomial/exponential arithmetic. More working bits can retain intermediate range and reduce some overflow losses, at an arithmetic/storage cost. Final accuracy still depends on coefficients, tables, rounding and output format. |
| `INTERNAL_FRAC_BITS` | 20 | 1–47 | Binary fractional bits in the working format. The quantization step is 2^(-fraction bits). At fixed total width, more fraction bits improve representable resolution but leave fewer bits for integer range. Regenerate inputs, coefficients/tables and software interpretation for a changed scale. Algorithmic accuracy is not determined by fraction count alone. |

**LUT**

| Parameter | Default | Choices | Meaning and implications |
| --- | ---: | --- | --- |
| `LUT_ADDRESS_WIDTH` | 8 | 1–8 | Number of bits selecting an entry within a LUT bank. Each extra address bit doubles entries per bank, table programming data and nominal table storage. Finer sampling can improve a suitable approximation, but table values must be generated for the chosen geometry. |
| `LUT_INDEX_FRACTION_WIDTH` | 8 | 1–8 | Fractional coordinate precision between adjacent LUT entries. More bits express finer interpolation positions and widen interpolation controls. They do not add integer table entries and help only when interpolation is used. |
| `LUT_BANKS` | 4 | 1, 2, 4 | Number of programmable LUT banks per stored context. More banks provision additional table storage and selector/programming state. They do not add SFT issue engines. Native LUT storage has CONTEXT_DEPTH × LUT_BANKS physical bank slots. Each context image programs one selected bank; more banks do not increase the four context slots. |
| `LUT_PIPELINE_DEPTH` | 2 | 1, 2, 3, 4 | Native LUT lookup response pipeline depth. More stages add response latency and storage. End-to-end tile time also includes bank availability, shared-engine scheduling, retirement and output backpressure. |
| `SUPPORT_INTERPOLATION` | 1 | 0, 1 | Permits interpolation where the selected nonlinear operation supports it. Interpolation can improve approximation between table samples using extra arithmetic. Runtime context controls still select it; enabling capability alone does not interpolate every operation. |

**Polynomial**

| Parameter | Default | Choices | Meaning and implications |
| --- | ---: | --- | --- |
| `POLY_COEFFICIENT_WIDTH` | 18 | 12, 16, 18, 24, 32 | Number of signed bits in a programmed polynomial coefficient. More bits with unchanged INPUT_FRAC_BITS increase coefficient range and storage. Coefficient fraction precision follows the polynomial fraction convention, rather than this width alone. Must exceed INPUT_FRAC_BITS and fit INTERNAL_WIDTH; regenerate coefficient images. |
| `POLY_MAX_DEGREE` | 4 | 1, 2, 3, 4 | Largest polynomial degree the evaluator and bank images can represent. A bank needs degree + 1 coefficients. More degree capacity increases coefficient storage and context image size; iterative evaluation can take more steps, while unrolled evaluation provisions more stages. A higher degree does not by itself guarantee lower approximation error. |
| `POLY_BANKS` | 4 | 1, 2, 4 | Number of programmable polynomial banks per stored context. More banks provision additional coefficient storage and programming state. Native bank slots are CONTEXT_DEPTH × POLY_BANKS. Each context image programs one selected bank; the number of stored contexts and shared issue engines stays fixed. |
| `POLY_EVALUATION_ARCH` | 0 | 0, 1 | Hardware organization of the polynomial evaluator. The tile still has one shared engine with ordered retirement, even when the native polynomial FU has an unrolled pipeline. 0: Iterative Horner evaluation reuses one multiply-add datapath; evaluation takes multiple dependent steps. 1: Unrolled evaluation instantiates elastic stages for the maximum degree, using more arithmetic and pipeline storage. |

**Reciprocal**

| Parameter | Default | Choices | Meaning and implications |
| --- | ---: | --- | --- |
| `RECIP_INTERNAL_WIDTH` | 24 | 16, 24, 32, 48, 64 | Working bit width inside reciprocal refinement. With fixed fraction count, more width adds intermediate range/headroom and widens native arithmetic/storage. It does not change the shared input/output formats. |
| `RECIP_INTERNAL_FRAC_BITS` | 20 | 8–30 | Working fractional bits inside reciprocal refinement. More fraction bits at fixed width improve representable working resolution while reducing integer headroom. Seed precision, iteration quality and final rounding also determine error. |
| `RECIP_SEED_ADDRESS_WIDTH` | 6 | 1–6 | Address precision of the normalized reciprocal seed table. Each extra bit doubles seed intervals and ROM entries. A better initial estimate can improve a selected iteration quality, but accuracy still needs numerical characterization. |

**RSQRT**

| Parameter | Default | Choices | Meaning and implications |
| --- | ---: | --- | --- |
| `RSQRT_INTERNAL_WIDTH` | 28 | 16, 24, 28, 32, 48, 64 | Working bit width inside RSQRT refinement. With fixed fraction count, more width adds intermediate range/headroom and widens native arithmetic/storage. It does not change the shared input/output formats. |
| `RSQRT_INTERNAL_FRAC_BITS` | 22 | 8–30 | Working fractional bits inside RSQRT refinement. More fraction bits at fixed width improve representable working resolution while reducing integer headroom. Seed precision, iteration quality and final rounding also determine error. |
| `RSQRT_SEED_ADDRESS_WIDTH` | 6 | 1–6 | Address precision of the normalized RSQRT seed table. Each extra bit doubles seed intervals and ROM entries. A better initial estimate can improve a selected iteration quality, but accuracy still needs numerical characterization. |

**Exponential**

| Parameter | Default | Choices | Meaning and implications |
| --- | ---: | --- | --- |
| `EXP_RANGE_WIDTH` | 40 | 40, 48, 64 | Working width of the base-two range-reduction coordinate. More headroom can represent larger reduced coordinates and costs wider range logic. It does not expand the final output format or remove exponential overflow/underflow. |
| `EXP_TABLE_ADDRESS_WIDTH` | 6 | 1–6 | Address bits for the fractional exponential approximation table. Each extra bit doubles sample intervals; the endpoint table has 2^bits + 1 entries. Generated assets, storage and approximation characteristics change together. |
| `EXP_PIPELINE_DEPTH` | 5 | 5, 6, 7, 8 | Number of native exponential response pipeline stages. The released implementation requires at least five stages. Additional stages add response delay and storage; they do not add parallel SFT issue engines. |

**Reduction**

| Parameter | Default | Choices | Meaning and implications |
| --- | ---: | --- | --- |
| `REDUCTION_LANES` | 4 | 1, 2, 4, 8 | Elements processed in one exact-reduction beat. More lanes add parallel reduction/SUMSQ work and consume more packed input bits. REDUCTION_LANES × REDUCTION_ELEMENT_WIDTH must fit the shell payload. |
| `REDUCTION_ELEMENT_WIDTH` | 16 | 4, 8, 16 | Bits in each exact-reduction input element. Wider elements increase input range, SUMSQ product width and required accumulator headroom. They also increase the packed input width. |
| `REDUCTION_ACC_WIDTH` | 48 | 32, 40, 48, 64 | Bits in the exact reduction accumulator. Must cover SUMSQ growth: at least 2 × element width + ceil(log2(max elements + 1)). It must also fit the shell result payload; wider state costs more storage/arithmetic. |
| `MAX_REDUCTION_ELEMENTS` | 1024 | 16, 64, 256, 1024 | Maximum accepted element count in a persistent reduction. A larger bound permits longer phased reductions and requires corresponding exact accumulator headroom. It does not add input lanes or per-cycle throughput. |
| `REDUCTION_STATE_DEPTH` | 2 | 1, 2, 4, 8 | Number of independent persistent reduction state entries. More entries retain more context-qualified partial results and counts. They add protected state, rather than additional arithmetic engines. |

**Storage**

| Parameter | Default | Choices | Meaning and implications |
| --- | ---: | --- | --- |
| `LOCAL_RF_DEPTH` | 8 | 2, 4, 8, 16, 32 | Number of SFT local intermediate-result register entries. More entries can reduce external round trips for mapped local chains, with more protected storage and selection logic. Local chaining remains context-programmed. |
| `INPUT_FIFO_DEPTH` | 4 | 1, 2, 4, 8, 16 | Private input FIFO capacity per data port. More buffering tolerates input skew and temporary downstream stalls, using additional payload/metadata storage. Sustained service rate is still limited by the execution engine. |
| `RESULT_QUEUE_DEPTH` | 8 | 1, 2, 4, 8, 16, 32 | Capacity reserved for complete results awaiting retirement/output. More entries absorb output backpressure at a storage cost; they do not create arithmetic parallelism or additional output ports. |
| `MAX_INFLIGHT` | 8 | 1, 2, 4, 8, 16, 32 | Number of operation reservations allowed before retirement. More credits can absorb queued work and blocked results. RESULT_QUEUE_DEPTH must cover every reservation. The SFT executes through one shared ordered engine, so extra credits do not provide parallel FU issue. |

**Protection**

| Parameter | Default | Choices | Meaning and implications |
| --- | ---: | --- | --- |
| `TABLE_PROTECTION` | 0 | 0, 1, 2 | Error-protection policy for lookup/seed/table storage. Protection adds redundant storage and checking/correction logic to covered state. It preserves the separate ownership, format and protocol checks. 0: No redundant payload protection; protocol/ownership checks remain. 1: Parity detects odd-bit corruption but cannot correct it. 2: SECDED corrects one-bit errors and detects two-bit errors per protected codeword/stripe; it adds more redundant bits and decode logic. |
| `COEFFICIENT_PROTECTION` | 0 | 0, 1, 2 | Error-protection policy for programmed polynomial coefficients. Protection adds redundant storage and checking/correction logic to covered state. It preserves the separate ownership, format and protocol checks. 0: No redundant payload protection; protocol/ownership checks remain. 1: Parity detects odd-bit corruption but cannot correct it. 2: SECDED corrects one-bit errors and detects two-bit errors per protected codeword/stripe; it adds more redundant bits and decode logic. |
| `CONTROL_PROTECTION` | 0 | 0, 1, 2 | Error-protection policy for control, validity and ownership state. Protection adds redundant storage and checking/correction logic to covered state. It preserves the separate ownership, format and protocol checks. 0: No redundant payload protection; protocol/ownership checks remain. 1: Parity detects odd-bit corruption but cannot correct it. 2: SECDED corrects one-bit errors and detects two-bit errors per protected codeword/stripe; it adds more redundant bits and decode logic. |
| `CONTEXT_PROTECTION` | 0 | 0, 1, 2 | Error-protection policy for stored context images. Protection adds redundant storage and checking/correction logic to covered state. It preserves the separate ownership, format and protocol checks. 0: No redundant payload protection; protocol/ownership checks remain. 1: Parity detects odd-bit corruption but cannot correct it. 2: SECDED corrects one-bit errors and detects two-bit errors per protected codeword/stripe; it adds more redundant bits and decode logic. |

Native implementation: [sft.sv](../src/rtl/mosaic_blocks/sft.sv).

### CPT: Control processing

Predicate, loop, event/barrier and tagged coordination control.

- Useful for iteration, conditional execution, synchronization and control transactions. Event counts, waits, barriers and action slots are capacities, not additional compute tiles.
- Tagged actions require peers that implement their request/response protocol. Loop tokens and event traffic share exposed output resources and can backpressure execution.

| FU switch | Function | Enabled | Disabled |
| --- | --- | --- | --- |
| `ENABLE_PREDICATE` | Lane predicates, Boolean operations and scalar comparisons. | Adds native predicate and comparison units and enables their command classes. | Predicate/comparison commands are rejected; external predicate qualification is still part of the command shell. |
| `ENABLE_LOOP_CONTROLLER` | Bounded/counting nested loops with index/ordinal output frames. | Adds native loop execution and safe-point control; iteration progress depends on delivery of the complete loop frame. | Loop command classes are rejected; event and action control can operate independently. |
| `ENABLE_EVENT_BARRIER` | Event occurrence counters, ANY/ALL waits and reusable barriers. | Adds the native event/barrier engine with selected counter and participant capacities. | Event/barrier command classes are rejected. Action transport retains its own event records. |
| `ENABLE_ACTIONS` | Tagged requests for lifecycle and context coordination with external peers. | Adds action slots, reliable request/response handling and optional timeout monitoring. | Action commands are rejected; predicate, loop and event engines remain independent. |

Shared helpers required by another selected operation can remain present. For example, a MAC can retain its internal multiplier while standalone multiplication is disabled. MST load/store engines retain their own address generators and formatters.

#### CPT parameters

**Functional units**

| Parameter | Default | Choices | Meaning and implications |
| --- | ---: | --- | --- |
| `FU_PROFILE` | 1 | 0, 1 | Legacy preset for FU enables that are not explicitly specified. Explicit per-FU enables always override this preset. The visual checkboxes save independent enables, so choosing an operation does not require its former profile peers. |
| `ENABLE_PREDICATE` | 1 | 0, 1 | Lane predicates, Boolean operations and scalar comparisons. This is an elaboration-time selection. Regenerate RTL and matching context programs after changing capabilities. Existing shared helpers can remain when another selected operation needs them. 0: Predicate/comparison commands are rejected; external predicate qualification is still part of the command shell. 1: Adds native predicate and comparison units and enables their command classes. |
| `ENABLE_LOOP_CONTROLLER` | 1 | 0, 1 | Bounded/counting nested loops with index/ordinal output frames. This is an elaboration-time selection. Regenerate RTL and matching context programs after changing capabilities. Existing shared helpers can remain when another selected operation needs them. 0: Loop command classes are rejected; event and action control can operate independently. 1: Adds native loop execution and safe-point control; iteration progress depends on delivery of the complete loop frame. |
| `ENABLE_EVENT_BARRIER` | 1 | 0, 1 | Event occurrence counters, ANY/ALL waits and reusable barriers. This is an elaboration-time selection. Regenerate RTL and matching context programs after changing capabilities. Existing shared helpers can remain when another selected operation needs them. 0: Event/barrier command classes are rejected. Action transport retains its own event records. 1: Adds the native event/barrier engine with selected counter and participant capacities. |
| `ENABLE_ACTIONS` | 1 | 0, 1 | Tagged requests for lifecycle and context coordination with external peers. This is an elaboration-time selection. Regenerate RTL and matching context programs after changing capabilities. Existing shared helpers can remain when another selected operation needs them. 0: Action commands are rejected; predicate, loop and event engines remain independent. 1: Adds action slots, reliable request/response handling and optional timeout monitoring. |

**Predicate unit**

| Parameter | Default | Choices | Meaning and implications |
| --- | ---: | --- | --- |
| `PREDICATE_LANES` | 8 | 1, 2, 4, 8, 16 | Number of independently valid bits in a predicate mask. More lanes represent wider SIMD conditions and increase predicate storage/output width. They do not instantiate vector arithmetic or change the number of tiles. |
| `PREDICATE_DEPTH` | 8 | 2, 4, 8, 16 | Number of local predicate register entries. More entries retain more independent masks/conditions, with additional validity and selection state. Predicate lane width is a separate setting. |

**Loop controller**

| Parameter | Default | Choices | Meaning and implications |
| --- | ---: | --- | --- |
| `MAX_LOOP_DEPTH` | 4 | 1, 2, 3, 4 | Maximum nesting levels in the native loop controller. More levels add induction/configuration state and enlarge each context image. Loops reuse the execution path rather than replicating the loop body. |
| `INDEX_WIDTH` | 32 | 4, 8, 16, 32 | Bit width of loop initial values, bounds and induction steps. More bits increase signed/unsigned index range and context/state width. The range must still cover every configured step and bound. |
| `TRIP_COUNT_WIDTH` | 32 | 2, 4, 8, 16, 32 | Bit width of counted-loop trip counts. More bits allow longer counted loops and enlarge loop context/state fields. |
| `LOOP_EXPORT_LEVELS` | 1 | 1, 2, 3, 4 | Maximum number of loop levels exported in an iteration frame. More exports improve index/ordinal visibility but consume more output beats. The loop advances only after complete frame delivery. This value cannot exceed MAX_LOOP_DEPTH. |

**Event barrier**

| Parameter | Default | Choices | Meaning and implications |
| --- | ---: | --- | --- |
| `NUM_EVENTS` | 16 | 1, 2, 4, 8, 16 | Number of distinct event IDs with occurrence counters. More IDs add counter/mask state and allow more independent synchronization conditions. Counter width and wait slots remain separate capacities. |
| `EVENT_COUNT_WIDTH` | 4 | 1, 2, 4, 8 | Bit width of each pending event-occurrence counter. More bits accommodate more pending occurrences with additional counter state. Balanced event production/consumption and overflow handling still matter. |
| `NUM_WAIT_SLOTS` | 4 | 1, 2, 3, 4 | Maximum simultaneous native ANY/ALL event waits. More slots allow more independent wait conditions but add masks, tags and result state. They do not create events or increase the event-output port count. |
| `NUM_BARRIERS` | 4 | 1, 2, 3, 4 | Number of independent reusable barrier records. More records retain more participant/generation state. Completion still depends on the configured participants arriving and release delivery progressing. |
| `MAX_PARTICIPANTS` | 16 | 1, 2, 4, 8, 16 | Maximum participant mask size for barriers and coordination. More participants widen masks and accounting. This is a protocol capacity, not a request to instantiate additional CGRA tiles. |

**Actions**

| Parameter | Default | Choices | Meaning and implications |
| --- | ---: | --- | --- |
| `MAX_OUTSTANDING_ACTIONS` | 4 | 1, 2, 4, 8 | Concurrent tagged coordination/lifecycle action slots. More slots allow more transactions to await peer responses but require more protected tracking and response capacity. Both action queues must cover this bound. |
| `ACTION_QUEUE_DEPTH` | 8 | 1, 2, 4, 8, 16 | Buffer capacity for outgoing tagged action work. More entries absorb a stalled peer/output with additional record storage. Depth must be at least MAX_OUTSTANDING_ACTIONS; it does not increase that active-slot limit. |
| `ACTION_RESPONSE_DEPTH` | 8 | 1, 2, 4, 8, 16 | Buffer capacity for action responses/completions. More entries absorb response/egress stalls at a storage cost. Depth must be at least MAX_OUTSTANDING_ACTIONS; it does not create additional action slots. |
| `SUPPORT_CONTEXT_COORDINATION` | 1 | 0, 1 | Permits tagged context-activation coordination requests. Useful when native peers implement coordinated context changes. Disabling rejects that action capability; it does not remove local context storage. |
| `SUPPORT_CLUSTER_LIFECYCLE` | 1 | 0, 1 | Permits tagged lifecycle requests to cluster/service peers. Requires enabled actions and peers that complete the protocol. Enabling capability does not connect a runtime controller automatically. |
| `SUPPORT_TIMEOUT` | 1 | 0, 1 | Permits deadline monitoring for outstanding control actions. Runtime contexts supply deadline values. Monitoring adds timer/control work and defines timeout containment/query behavior, rather than a clock-frequency target. |

**Storage**

| Parameter | Default | Choices | Meaning and implications |
| --- | ---: | --- | --- |
| `CONTROL_REGISTER_DEPTH` | 8 | 4, 8, 16 | Number of typed private control registers. More entries retain more scalar control values with additional data/type/ownership state. This does not add data ports or arithmetic execution units. |
| `EVENT_INPUT_FIFO_DEPTH` | 8 | 1, 2, 4, 8, 16 | Buffer capacity for incoming event/control records. More entries absorb bursts and internal handling stalls. They add record storage, rather than more event processing ports. |
| `EVENT_OUTPUT_FIFO_DEPTH` | 8 | 1, 2, 4, 8, 16 | Buffer capacity for outgoing event/control records. More entries decouple native sources from a stalled event sink. Sustained output bandwidth remains constrained by the single exposed event stream. |

**Protection**

| Parameter | Default | Choices | Meaning and implications |
| --- | ---: | --- | --- |
| `EVENT_PROTECTION` | 0 | 0, 1 | Error-protection policy for event/control record storage. Protection adds redundant storage and checking/correction logic to covered state. It preserves the separate ownership, format and protocol checks. 0: No redundant payload protection; protocol/ownership checks remain. 1: Parity detects odd-bit corruption but cannot correct it. |
| `CONTEXT_PROTECTION` | 0 | 0, 1, 2 | Error-protection policy for stored context images. Protection adds redundant storage and checking/correction logic to covered state. It preserves the separate ownership, format and protocol checks. 0: No redundant payload protection; protocol/ownership checks remain. 1: Parity detects odd-bit corruption but cannot correct it. 2: SECDED corrects one-bit errors and detects two-bit errors per protected codeword/stripe; it adds more redundant bits and decode logic. |

Native implementation: [cpt.sv](../src/rtl/mosaic_blocks/cpt.sv).

## Numerical formats and capacity examples

- A 16-bit signed fixed-point value with 12 fraction bits has a step of 1/4096 and range −8 to 8 − 1/4096. Raising fraction bits at fixed width improves representable resolution while reducing integer range. Exact integer/bitwise operations do not implicitly rescale their bit patterns.
- A VCT with four lanes and 32-bit accumulators has a 128-bit native payload. Raising accumulators to 64 bits produces a 256-bit payload and can widen every data link in the grid, even if element width remains eight bits.
- A LUT address width of four selects 16 entries per bank; five selects 32. With 16-bit outputs that is 256 versus 512 nominal data bits per bank, before protection and bank metadata. The native SFT allocates context-depth × LUT-bank physical slots.
- Eight banks of 1,024 64-bit words hold 64 KiB. Doubling words per bank doubles capacity without creating more banks. Doubling bank count changes both capacity and banking.
- Parity detects odd-bit corruption without correction. SECDED corrects one-bit and detects two-bit errors per protected codeword/stripe, using more redundant storage and decoding logic. Neither replaces ownership or protocol validation.

## Regenerate this reference

```sh
.venv/bin/python app/configuration_reference.py
```

The editor provides current-value calculations and expandable implications beside controls. Those calculations describe nominal geometry and formats, not measured performance or physical implementation results.
