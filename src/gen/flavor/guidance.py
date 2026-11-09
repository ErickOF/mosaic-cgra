"""Configuration guidance grounded in the released native RTL and fabric adapter.

These descriptions express functional and structural trade-offs. They contain no
technology-dependent estimates of area, frequency, power or energy.
"""


def info(description, *implications, choices=None, labels=None, metric=None):
    result = dict(description=description, implications=list(implications))
    if choices:
        result['choice_help'] = {str(key): value for key, value in choices.items()}
    if labels:
        result['choice_labels'] = {str(key): value for key, value in labels.items()}
    if metric:
        result['metric'] = metric
    return result


SCOPE = ('Hardware cost and timing effects are qualitative. Technology libraries, synthesis '
         'and implementation measurements are needed to determine area, frequency, power and energy.')

ARCHITECTURE = {
    'name': info('Names the saved flavor and its output directory.',
        'This label changes the bundle identity and location; the exported Verilog top is cluster.'),
    'rows': info('Number of tile rows, with exactly one tile at every grid position.',
        'More positions add native tiles, local switches, configuration/state ports and wiring.',
        'Shape and placement affect routing: Manhattan distance is the minimum internal hop count. '
        'More tiles provide resources only when a workload can use them concurrently.'),
    'cols': info('Number of tile columns; rows and columns are independent.',
        'For the same tile count, changing the aspect ratio changes neighbor links and path lengths.',
        'Place producers near their consumers. Generated routes and application scheduling still '
        'need to match the selected placement.'),
    'scratchpad_banks': info('Number of independently addressed 64-bit SRAM banks.',
        'More banks add storage and bank/control hardware. Requests to different banks can benefit '
        'from banking; requests to one bank still contend.',
        'Capacity is banks × words per bank × 8 bytes. The current adapter supports up to 16 banks '
        'and exposes one host client plus one client for each MST.'),
    'scratchpad_bank_words': info('Number of 64-bit words stored in each SRAM bank.',
        'Deeper banks increase capacity and address/storage requirements. Depth alone does not '
        'add banks, client ports or memory bandwidth.',
        'Banks and words must be powers of two, and total capacity must be 16 bytes to 1 MiB.'),
    'cluster_id': info('Logical cluster identifier exported on the generated interface.',
        'Changing the ID changes identification and the architecture manifest, rather than tile '
        'placement or arithmetic resources. Ownership permissions are configured separately.'),
    'clock_gating': info('Includes a shared clock gate controlled by the external enable.',
        'The gate can stop fabric clock activity while idle; its test/scan inputs bypass gating. '
        'Keep enable asserted while configuration, traffic or completion obligations need clocks.',
        'Disabling the option connects the fabric clock directly. This setting does not add '
        'power gating, retention, voltage scaling or clock-domain crossings.'),
    'tile_id': info('Unique logical identity for this tile, independent of its coordinates.',
        'The ID identifies native control/event endpoints. Moving a tile preserves its ID; changing '
        'the ID requires matching software and configuration bindings.',
        'IDs fit 16 bits. CPT event records restrict CPT producer IDs to 0–255.'),
    'tile_position': info('Zero-based row and column of a tile in the generated logical mesh.',
        'Moving/swapping tiles changes neighbors and communication distances while preserving '
        'their private parameter settings and logical IDs. Regenerate routes and software bindings '
        'for the new placement.',
        'These coordinates describe connectivity; physical placement and wire lengths are '
        'determined by the later implementation flow.'),
    'context_depth': info('Four stored context slots per native tile in this adapter.',
        'Contexts select runtime programs and operands within the hardware capabilities generated '
        'for that tile. They cannot create a disabled FU. Depth four is fixed in this editor.'),
    'profile': info('Selects the integration backend used for a descriptor.',
        'The visual editor uses Configurable: native tile control interfaces and local-switch '
        'grid transport. Legacy Cluster-MVP descriptors retain their separately qualified '
        'composition and lifecycle controller.'),
    'lifecycle_timeout': info('Compatibility field for the legacy Cluster-MVP lifecycle controller.',
        'Configurable exports native control interfaces and does not instantiate that controller. '
        'Changing this field therefore has no lifecycle timeout effect in the visual fabric.'),
}

TILES = {
    'BCT': info('Scalar integer compute for arithmetic, logic, comparisons and multiply-accumulate.',
        'Useful for scalar dataflow and control-adjacent arithmetic. Selecting only the operations '
        'needed by a workload can remove standalone FU implementations.',
        'DATA_WIDTH sizes the native payload and MAC accumulator; multiply operands have their own '
        'narrower width. RF depth and FU selection can change context encodings.'),
    'MST': info('Memory/stream service tile with independent load and store engines.',
        'Use it to move data between SRAM, streams and exposed DMA endpoints. More MSTs add '
        'scratchpad clients, which still share bank and fabric bandwidth.',
        'AGUs and formatters are internal parts of the selected engines. The current adapter uses '
        '128-bit stream payloads and 64-bit memory words, requiring width conversion.'),
    'VCT': info('Masked integer SIMD lanes, cross-lane reduction and dot products.',
        'More lanes process more elements per vector operation and replicate arithmetic/storage. '
        'They help only when enough independent elements and memory bandwidth are available. '
        'Complete vector operations still share the tile issue/retirement path.',
        'The payload is NUM_LANES × ACC_WIDTH bits, even when element operations use fewer bits. '
        'A wide VCT can therefore widen links throughout the entire generated grid.'),
    'SFT': info('Fixed-point special functions, programmable approximations and exact operations.',
        'Useful for lookup-based functions, nonlinear transforms and normalization. LUTs and '
        'polynomials need programmed images; reciprocal, RSQRT and exponential use native models.',
        'Formats and tables trade precision, range and hardware resources. A shared issue engine '
        'reserves and retires operations in order: enabling more FUs does not add issue engines. '
        'These are fixed-point/integer operations, rather than IEEE floating-point units.'),
    'CPT': info('Predicate, loop, event/barrier and tagged coordination control.',
        'Useful for iteration, conditional execution, synchronization and control transactions. '
        'Event counts, waits, barriers and action slots are capacities, not additional compute tiles.',
        'Tagged actions require peers that implement their request/response protocol. Loop tokens '
        'and event traffic share exposed output resources and can backpressure execution.'),
}

# Each independently selectable operation has explicit enabled/disabled semantics.
UNITS = {
    'BCT': {
        'ENABLE_ALU': ('Scalar integer arithmetic, logic, shifts, comparisons and selection.',
            'Enables standalone ALU contexts at DATA_WIDTH.',
            'Standalone ALU contexts are rejected. A MAC may retain its own final-add helper.'),
        'ENABLE_MULTIPLIER': ('A full product from two independently signed narrow operands.',
            'Enables standalone multiplication using MULTIPLY_OPERAND_WIDTH.',
            'Multiply contexts are rejected. A selected MAC can still contain an internal multiplier.'),
        'ENABLE_MAC': ('Multiply-add with local accumulator access and DATA_WIDTH-wide results.',
            'Enables MAC contexts and accumulator storage/feedback; it does not enable standalone '
            'ALU or multiply operations.',
            'MAC contexts and MAC accumulator access are rejected.'),
    },
    'MST': {
        'ENABLE_LOAD': ('Memory/DMA-to-stream operations using load channels.',
            'Instantiates load-channel workers, including their address and formatting helpers.',
            'Load-class descriptors are rejected before execution; load workers are omitted.'),
        'ENABLE_STORE': ('Stream/DMA-to-memory and store-channel forwarding operations.',
            'Instantiates store-channel workers and their address and formatting helpers.',
            'Store-class descriptors are rejected. Local copy also requires the store side.'),
    },
    'VCT': {
        'ENABLE_LANE_ALU': ('Per-element integer arithmetic, logic, shifts and comparisons.',
            'Enables lane ALU opcodes across the selected NUM_LANES.',
            'Lane ALU opcodes are rejected; independently selected lane multiply/MAC can remain.'),
        'SUPPORT_MUL': ('Independent widened multiplication in every vector lane.',
            'Enables element products; product width is twice ELEMENT_WIDTH.',
            'Lane multiply opcodes are rejected; dot product and MAC have independent enables.'),
        'SUPPORT_MAC': ('Per-lane multiply-add with ACC_WIDTH-wide accumulation.',
            'Enables lane MAC opcodes without requiring standalone lane multiplication or ALU.',
            'Lane MAC opcodes are rejected; other vector operations retain their own enables.'),
        'ENABLE_REDUCTION': ('Cross-lane SUM, MIN, MAX, AND and OR operations.',
            'Adds the reduction path and enables scalar accumulator storage shared with dot product.',
            'Reduction contexts are rejected; dot product can remain enabled.'),
        'ENABLE_DOT_PRODUCT': ('Masked products followed by an exact cross-lane sum.',
            'Adds the dot-product path independently of lane multiply and reduction. The accumulator '
            'must cover product width plus lane-count growth.',
            'Dot-product contexts are rejected; lane MAC and reduction remain independent.'),
    },
    'SFT': {
        'ENABLE_ALU': ('Exact scalar integer arithmetic and logic on the shell payload.',
            'Enables standalone scalar ALU operations.',
            'ALU contexts are rejected; an enabled accumulator can retain an internal add helper.'),
        'ENABLE_MULTIPLIER': ('Exact full-product scalar multiplication.',
            'Enables scalar products using INPUT_WIDTH operands.',
            'Standalone multiply contexts are rejected; other selected FUs keep their own multipliers.'),
        'ENABLE_LUT': ('Programmable table lookup with optional interpolation.',
            'Adds programmable LUT banks. Table contents must be provisioned before lookup.',
            'Lookup contexts are rejected and the LUT FU is omitted. Existing context image table '
            'slots remain reserved by this adapter.'),
        'ENABLE_POLYNOMIAL': ('Evaluation of a programmed polynomial in a committed input interval.',
            'Adds coefficient banks and the selected iterative/unrolled evaluator. Coefficient '
            'storage is included in the generated context image.',
            'Polynomial contexts are rejected and polynomial coefficient image storage is omitted.'),
        'ENABLE_RECIPROCAL': ('Fixed-point reciprocal approximation, 1/x.',
            'Enables reciprocal independently of polynomial and RSQRT. Seed and internal precision '
            'control its numerical implementation.',
            'Reciprocal contexts are rejected; RSQRT remains independently selectable.'),
        'ENABLE_RSQRT': ('Fixed-point reciprocal-square-root approximation, 1/sqrt(x).',
            'Enables RSQRT independently of reciprocal and polynomial. Runtime domain and exception '
            'rules still apply.',
            'RSQRT contexts are rejected; reciprocal remains independently selectable.'),
        'ENABLE_EXPONENTIAL': ('Fixed-point base-e and base-two exponential approximation.',
            'Adds exponential range reduction, approximation tables and response stages.',
            'Exponential contexts are rejected; no peer FU is disabled automatically.'),
        'ENABLE_REDUCTION': ('Exact SUM/SUMSQ/MIN/MAX and persistent phased reduction state.',
            'Adds reduction and SUMSQ arithmetic with selected lane geometry and bounded count.',
            'Reduction contexts are rejected and the exact reduction datapath is omitted.'),
        'ENABLE_FORMATTER': ('Explicit shift, rounding and narrowing to OUTPUT_WIDTH.',
            'Enables format-conversion operations with configured rounding/saturation policies.',
            'Format contexts are rejected. Grid links do not substitute implicit numerical conversion.'),
        'ENABLE_ACCUMULATOR': ('Persistent scalar clear, load, add and read operations.',
            'Enables standalone accumulator commands and required arithmetic helpers.',
            'Accumulator commands are rejected. State needed for other enabled local feedback '
            'operations can remain.'),
    },
    'CPT': {
        'ENABLE_PREDICATE': ('Lane predicates, Boolean operations and scalar comparisons.',
            'Adds native predicate and comparison units and enables their command classes.',
            'Predicate/comparison commands are rejected; external predicate qualification is still '
            'part of the command shell.'),
        'ENABLE_LOOP_CONTROLLER': ('Bounded/counting nested loops with index/ordinal output frames.',
            'Adds native loop execution and safe-point control; iteration progress depends on '
            'delivery of the complete loop frame.',
            'Loop command classes are rejected; event and action control can operate independently.'),
        'ENABLE_EVENT_BARRIER': ('Event occurrence counters, ANY/ALL waits and reusable barriers.',
            'Adds the native event/barrier engine with selected counter and participant capacities.',
            'Event/barrier command classes are rejected. Action transport retains its own event records.'),
        'ENABLE_ACTIONS': ('Tagged requests for lifecycle and context coordination with external peers.',
            'Adds action slots, reliable request/response handling and optional timeout monitoring.',
            'Action commands are rejected; predicate, loop and event engines remain independent.'),
    },
}

COMMON = {
    'FU_PROFILE': info('Legacy preset for FU enables that are not explicitly specified.',
        'Explicit per-FU enables always override this preset. The visual checkboxes save independent '
        'enables, so choosing an operation does not require its former profile peers.'),
    'RF_DEPTH': info('Number of private scalar register entries.',
        'More entries retain more local intermediates but increase storage and selection logic. '
        'They do not add read/write ports.',
        'Register-address and validity fields can grow, changing the packed context image.'),
    'LOCAL_RF_DEPTH': info('Number of SFT local intermediate-result register entries.',
        'More entries can reduce external round trips for mapped local chains, with more protected '
        'storage and selection logic. Local chaining remains context-programmed.'),
    'INPUT_FIFO_DEPTH': info('Private input FIFO capacity per data port.',
        'More buffering tolerates input skew and temporary downstream stalls, using additional '
        'payload/metadata storage. Sustained service rate is still limited by the execution engine.'),
    'RESULT_QUEUE_DEPTH': info('Capacity reserved for complete results awaiting retirement/output.',
        'More entries absorb output backpressure at a storage cost; they do not create arithmetic '
        'parallelism or additional output ports.'),
    'SUPPORT_SATURATION': info('Permits saturation where an operation supports it.',
        'Runtime signedness and saturation controls still select behavior. Saturation clamps '
        'overflow to a representable limit rather than retaining only modular low bits.',
        'Keeping the capability adds limit/overflow selection logic; disabling it rejects saturating '
        'contexts and does not widen arithmetic.'),
    'SUPPORT_MINMAX': info('Permits minimum and maximum comparisons.',
        'Useful for clamp, extremum and activation workloads. Disabling rejects corresponding ALU '
        'operations and, on VCT, MIN/MAX reductions.'),
    'BYPASS_PROFILE': info('Selects BCT local operand-source connectivity.',
        'Richer feedback reduces trips through external streams but adds selection/control choices. '
        'The context must explicitly choose each operand source.',
        'MAC adds its required accumulator/feedback paths even with the minimal profile.',
        choices={0: 'Minimal graph; standalone bypass/previous-result sources need an enabled MAC.',
                 1: 'Balanced graph includes bypass and previous-result feedback.',
                 2: 'Flexible graph additionally permits predicate-result operands.'},
        labels={0: 'Minimal', 1: 'Balanced', 2: 'Flexible'}),
    'REGISTER_BYPASS': info('Adds a registered stage when a BCT operation consumes bypass feedback.',
        'Registered feedback adds storage and an enabled-cycle delay on that dependency. It does '
        'not add read ports or automatically pipeline the arithmetic datapath.',
        choices={0: 'Use the available unregistered feedback path.',
                 1: 'A bypass-sourced operation includes the registered-feedback delay.'}),
    'PREDICATE_DEPTH': info('Number of local predicate register entries.',
        'More entries retain more independent masks/conditions, with additional validity and '
        'selection state. Predicate lane width is a separate setting.'),
}

RESPONSE_DELAY = ('More response stages add registers and enabled-cycle latency. The current '
    'BCT/VCT wrappers instantiate combinational arithmetic and delay aligned results; increasing '
    'this value does not itself split the arithmetic critical path or guarantee a higher frequency.')
for _name, _subject in (('ALU_LATENCY', 'BCT ALU'), ('MULTIPLY_LATENCY', 'BCT multiplier'),
        ('MAC_LATENCY', 'BCT MAC'), ('LANE_LATENCY', 'VCT lane'),
        ('REDUCTION_LATENCY', 'VCT reduction'), ('DOT_LATENCY', 'VCT dot-product')):
    COMMON[_name] = info(f'Configured {_subject} response delay in enabled clock edges.',
        RESPONSE_DELAY, 'Zero selects the combinational response mode where offered. Queueing, '
        'operand waits and output backpressure can add end-to-end time.')

BY_TILE = {
    'BCT': {
        'DATA_WIDTH': info('Width of scalar payloads, ALU results and MAC accumulators.',
            'Wider values represent larger integers and accumulations but widen registers, arithmetic '
            'and local connections. This is integer width, not floating-point precision.',
            'Two multiply operand widths must fit this width. It can widen all grid links if it '
            'becomes the widest native tile payload.', metric={'kind': 'bct_payload'}),
        'MULTIPLY_OPERAND_WIDTH': info('Width of each BCT multiply/MAC multiplicand.',
            'A full product uses twice this width and must fit DATA_WIDTH. Wider operands increase '
            'multiplication resources and reduce the unused headroom for accumulation.',
            'Narrow operands must obey the native canonical zero/sign-extension rules.',
            metric={'kind': 'double_bits'}),
        'ACCUMULATOR_COUNT': info('Number of private BCT MAC accumulator entries.',
            'More entries retain more independent partial sums, with additional DATA_WIDTH-wide '
            'storage, validity and operand selection. They do not add MAC execution units.'),
    },
    'MST': {
        'READ_DATA_FIFO_DEPTH': info('Buffer capacity inside memory-service read/load paths.',
            'More entries absorb response bursts and stream backpressure, using more data/metadata '
            'storage. Memory issue limits and downstream bandwidth remain separate.'),
        'WRITE_DATA_FIFO_DEPTH': info('Buffer capacity inside memory-service store paths.',
            'More entries decouple stream arrivals from memory stalls. They do not increase memory '
            'port width or the count of outstanding write tags.'),
        'SUPPORT_2D': info('Permits nested 2D strided address descriptors.',
            'Useful for matrix rows, tiles and pitched image accesses. It adds row/outer-count address '
            'handling; disabling it limits accepted descriptors to the simpler address modes.'),
        'SUPPORT_CIRCULAR': info('Circular addressing requires an unreleased MST adapter.',
            'The current native MST rejects SUPPORT_CIRCULAR=1 at elaboration. Keep it disabled; '
            'this is not an available ring-buffer optimization in this flavor.',
            choices={0: 'Supported setting for the released MST.',
                     1: 'Unavailable: the released MST has no circular-address adapter.'},
            labels={0: 'Disabled', 1: 'Unavailable — requires adapter'}),
        'SUPPORT_UNALIGNED': info('Permits supported unaligned memory/stream accesses.',
            'Alignment and fragment handling can serve accesses crossing memory-word boundaries. '
            'Those accesses may need extra requests and cycles; aligned access can be cheaper.',
            'Disabling requires descriptors and endpoints that satisfy the native alignment rules.'),
        'SUPPORT_WIDTH_CONVERSION': info('Adapts stream-beat width to memory-word width.',
            'The current MST adapter uses 128-bit streams and 64-bit memory words, so this option '
            'must remain enabled. Conversion packs/splits beats; it does not create more memory '
            'bandwidth.'),
        'SUPPORT_ELEMENT_CONVERSION': info('Permits changes of element width inside a transfer.',
            'Useful for packing, widening and narrowing data layouts. Descriptors still choose '
            'signedness, saturation and compatible formats. Disabling requires matching '
            'source/destination element widths.'),
    },
    'VCT': {
        'NUM_LANES': info('Number of parallel integer element lanes.',
            'More lanes replicate execution and storage and increase cross-lane reduction/dot work. '
            'They require enough valid elements and transport bandwidth to be useful.',
            'The native payload is NUM_LANES × ACC_WIDTH bits, which may widen the entire fabric.',
            metric={'kind': 'vector_payload'}),
        'ELEMENT_WIDTH': info('Width of a vector input element.',
            'Wider elements represent larger integers and increase lane product width. ACC_WIDTH '
            'must be at least twice this value, with extra growth for dot products.',
            'Changing element width changes payload packing and the contexts/data formats required.'),
        'ACC_WIDTH': info('Width of each vector-lane accumulator slot.',
            'More bits provide accumulation/product headroom but enlarge vector registers and the '
            'native payload. This can widen every mesh link, not just this tile.',
            'Exact dot products require at least 2 × ELEMENT_WIDTH + ceil(log2(NUM_LANES)) bits.',
            metric={'kind': 'vector_payload'}),
        'WRITE_SLICE_WIDTH': info('Smallest independently valid slice of vector-register storage.',
            'Smaller slices permit finer partial writes but require more validity/mask bits. Larger '
            'slices reduce that granularity. Slice width must divide both element and accumulator '
            'widths; it does not add physical register ports.'),
        'MUL_LATENCY': info('Compatibility limit for primitive lane-multiply response timing.',
            'Must fit within LANE_LATENCY. In this tile wrapper, the primitive multiplier is '
            'combinational and lane response delay is controlled by LANE_LATENCY; this parameter '
            'does not add a separate multiply pipeline.'),
        'MAC_LATENCY': info('Compatibility limit for primitive lane-MAC response timing.',
            'Must fit within LANE_LATENCY. In this tile wrapper, primitive MAC latency is zero and '
            'LANE_LATENCY controls the aligned response; this parameter does not add a separate '
            'MAC pipeline.'),
        'SCALAR_ACC_DEPTH': info('Persistent scalar accumulator entries for reduction/dot feedback.',
            'More entries retain more independent partial sums but add protected scalar state. '
            'They do not add reduction or dot execution units.'),
        'VECTOR_ACC_DEPTH': info('Persistent per-lane vector accumulator entries.',
            'More entries retain more vector partial sums at NUM_LANES × ACC_WIDTH bits per entry, '
            'plus validity/protection overhead.'),
        'VRF_DEPTH': info('Number of vector-register entries.',
            'More entries retain more vectors and can reduce external transfers, with wider storage '
            'and address selection. NUM_LANES, ACC_WIDTH and slice-validity granularity determine '
            'the size of each entry.'),
    },
    'SFT': {
        'INPUT_WIDTH': info('Number of bits in a native fixed-point input operand.',
            'Increasing width with unchanged fraction bits increases representable range, not '
            'fractional resolution. It also widens the arithmetic that consumes the operand.',
            'Input values still travel in the fixed-width SFT shell payload.'),
        'OUTPUT_WIDTH': info('Number of bits in a native fixed-point result.',
            'With unchanged fraction bits, more bits increase output range. Narrowing can introduce '
            'rounding or saturation according to the operation; it does not resize the shell bus.',
            'LUT storage also grows with OUTPUT_WIDTH.'),
        'INTERNAL_WIDTH': info('Working width used by polynomial/exponential arithmetic.',
            'More working bits can retain intermediate range and reduce some overflow losses, at '
            'an arithmetic/storage cost. Final accuracy still depends on coefficients, tables, '
            'rounding and output format.'),
        'LUT_ADDRESS_WIDTH': info('Number of bits selecting an entry within a LUT bank.',
            'Each extra address bit doubles entries per bank, table programming data and nominal '
            'table storage. Finer sampling can improve a suitable approximation, but table values '
            'must be generated for the chosen geometry.', metric={'kind': 'table_entries'}),
        'LUT_INDEX_FRACTION_WIDTH': info('Fractional coordinate precision between adjacent LUT entries.',
            'More bits express finer interpolation positions and widen interpolation controls. '
            'They do not add integer table entries and help only when interpolation is used.'),
        'LUT_BANKS': info('Number of programmable LUT banks per stored context.',
            'More banks provision additional table storage and selector/programming state. '
            'They do not add SFT issue engines.',
            'Native LUT storage has CONTEXT_DEPTH × LUT_BANKS physical bank slots. Each context '
            'image programs one selected bank; more banks do not increase the four context slots.'),
        'LUT_PIPELINE_DEPTH': info('Native LUT lookup response pipeline depth.',
            'More stages add response latency and storage. End-to-end tile time also includes '
            'bank availability, shared-engine scheduling, retirement and output backpressure.'),
        'SUPPORT_INTERPOLATION': info('Permits interpolation where the selected nonlinear operation supports it.',
            'Interpolation can improve approximation between table samples using extra arithmetic. '
            'Runtime context controls still select it; enabling capability alone does not '
            'interpolate every operation.'),
        'POLY_COEFFICIENT_WIDTH': info('Number of signed bits in a programmed polynomial coefficient.',
            'More bits with unchanged INPUT_FRAC_BITS increase coefficient range and storage. '
            'Coefficient fraction precision follows the polynomial fraction convention, rather '
            'than this width alone.',
            'Must exceed INPUT_FRAC_BITS and fit INTERNAL_WIDTH; regenerate coefficient images.'),
        'POLY_MAX_DEGREE': info('Largest polynomial degree the evaluator and bank images can represent.',
            'A bank needs degree + 1 coefficients. More degree capacity increases coefficient '
            'storage and context image size; iterative evaluation can take more steps, while '
            'unrolled evaluation provisions more stages.',
            'A higher degree does not by itself guarantee lower approximation error.'),
        'POLY_BANKS': info('Number of programmable polynomial banks per stored context.',
            'More banks provision additional coefficient storage and programming state. Native bank '
            'slots are CONTEXT_DEPTH × POLY_BANKS. Each context image programs one selected bank; '
            'the number of stored contexts and shared issue engines stays fixed.'),
        'POLY_EVALUATION_ARCH': info('Hardware organization of the polynomial evaluator.',
            'The tile still has one shared engine with ordered retirement, even when the native '
            'polynomial FU has an unrolled pipeline.',
            choices={0: 'Iterative Horner evaluation reuses one multiply-add datapath; evaluation '
                        'takes multiple dependent steps.',
                     1: 'Unrolled evaluation instantiates elastic stages for the maximum degree, '
                        'using more arithmetic and pipeline storage.'},
            labels={0: 'Iterative Horner', 1: 'Unrolled pipeline'}),
        'EXP_RANGE_WIDTH': info('Working width of the base-two range-reduction coordinate.',
            'More headroom can represent larger reduced coordinates and costs wider range logic. '
            'It does not expand the final output format or remove exponential overflow/underflow.'),
        'EXP_TABLE_ADDRESS_WIDTH': info('Address bits for the fractional exponential approximation table.',
            'Each extra bit doubles sample intervals; the endpoint table has 2^bits + 1 entries. '
            'Generated assets, storage and approximation characteristics change together.',
            metric={'kind': 'endpoint_entries'}),
        'EXP_PIPELINE_DEPTH': info('Number of native exponential response pipeline stages.',
            'The released implementation requires at least five stages. Additional stages add '
            'response delay and storage; they do not add parallel SFT issue engines.'),
        'REDUCTION_LANES': info('Elements processed in one exact-reduction beat.',
            'More lanes add parallel reduction/SUMSQ work and consume more packed input bits. '
            'REDUCTION_LANES × REDUCTION_ELEMENT_WIDTH must fit the shell payload.'),
        'REDUCTION_ELEMENT_WIDTH': info('Bits in each exact-reduction input element.',
            'Wider elements increase input range, SUMSQ product width and required accumulator '
            'headroom. They also increase the packed input width.'),
        'REDUCTION_ACC_WIDTH': info('Bits in the exact reduction accumulator.',
            'Must cover SUMSQ growth: at least 2 × element width + ceil(log2(max elements + 1)). '
            'It must also fit the shell result payload; wider state costs more storage/arithmetic.'),
        'MAX_REDUCTION_ELEMENTS': info('Maximum accepted element count in a persistent reduction.',
            'A larger bound permits longer phased reductions and requires corresponding exact '
            'accumulator headroom. It does not add input lanes or per-cycle throughput.'),
        'REDUCTION_STATE_DEPTH': info('Number of independent persistent reduction state entries.',
            'More entries retain more context-qualified partial results and counts. They add '
            'protected state, rather than additional arithmetic engines.'),
        'MAX_INFLIGHT': info('Number of operation reservations allowed before retirement.',
            'More credits can absorb queued work and blocked results. RESULT_QUEUE_DEPTH must '
            'cover every reservation. The SFT executes through one shared ordered engine, so '
            'extra credits do not provide parallel FU issue.'),
    },
    'CPT': {
        'PREDICATE_LANES': info('Number of independently valid bits in a predicate mask.',
            'More lanes represent wider SIMD conditions and increase predicate storage/output '
            'width. They do not instantiate vector arithmetic or change the number of tiles.'),
        'MAX_LOOP_DEPTH': info('Maximum nesting levels in the native loop controller.',
            'More levels add induction/configuration state and enlarge each context image. '
            'Loops reuse the execution path rather than replicating the loop body.'),
        'INDEX_WIDTH': info('Bit width of loop initial values, bounds and induction steps.',
            'More bits increase signed/unsigned index range and context/state width. The range '
            'must still cover every configured step and bound.', metric={'kind': 'integer_range'}),
        'TRIP_COUNT_WIDTH': info('Bit width of counted-loop trip counts.',
            'More bits allow longer counted loops and enlarge loop context/state fields.',
            metric={'kind': 'unsigned_range'}),
        'LOOP_EXPORT_LEVELS': info('Maximum number of loop levels exported in an iteration frame.',
            'More exports improve index/ordinal visibility but consume more output beats. The '
            'loop advances only after complete frame delivery. This value cannot exceed MAX_LOOP_DEPTH.',
            metric={'kind': 'loop_beats'}),
        'NUM_EVENTS': info('Number of distinct event IDs with occurrence counters.',
            'More IDs add counter/mask state and allow more independent synchronization conditions. '
            'Counter width and wait slots remain separate capacities.'),
        'EVENT_COUNT_WIDTH': info('Bit width of each pending event-occurrence counter.',
            'More bits accommodate more pending occurrences with additional counter state. '
            'Balanced event production/consumption and overflow handling still matter.',
            metric={'kind': 'unsigned_range'}),
        'NUM_WAIT_SLOTS': info('Maximum simultaneous native ANY/ALL event waits.',
            'More slots allow more independent wait conditions but add masks, tags and result state. '
            'They do not create events or increase the event-output port count.'),
        'NUM_BARRIERS': info('Number of independent reusable barrier records.',
            'More records retain more participant/generation state. Completion still depends on '
            'the configured participants arriving and release delivery progressing.'),
        'MAX_PARTICIPANTS': info('Maximum participant mask size for barriers and coordination.',
            'More participants widen masks and accounting. This is a protocol capacity, not a '
            'request to instantiate additional CGRA tiles.'),
        'MAX_OUTSTANDING_ACTIONS': info('Concurrent tagged coordination/lifecycle action slots.',
            'More slots allow more transactions to await peer responses but require more protected '
            'tracking and response capacity. Both action queues must cover this bound.'),
        'ACTION_QUEUE_DEPTH': info('Buffer capacity for outgoing tagged action work.',
            'More entries absorb a stalled peer/output with additional record storage. Depth must '
            'be at least MAX_OUTSTANDING_ACTIONS; it does not increase that active-slot limit.'),
        'ACTION_RESPONSE_DEPTH': info('Buffer capacity for action responses/completions.',
            'More entries absorb response/egress stalls at a storage cost. Depth must be at least '
            'MAX_OUTSTANDING_ACTIONS; it does not create additional action slots.'),
        'SUPPORT_CONTEXT_COORDINATION': info('Permits tagged context-activation coordination requests.',
            'Useful when native peers implement coordinated context changes. Disabling rejects '
            'that action capability; it does not remove local context storage.'),
        'SUPPORT_CLUSTER_LIFECYCLE': info('Permits tagged lifecycle requests to cluster/service peers.',
            'Requires enabled actions and peers that complete the protocol. Enabling capability '
            'does not connect a runtime controller automatically.'),
        'SUPPORT_TIMEOUT': info('Permits deadline monitoring for outstanding control actions.',
            'Runtime contexts supply deadline values. Monitoring adds timer/control work and '
            'defines timeout containment/query behavior, rather than a clock-frequency target.'),
        'CONTROL_REGISTER_DEPTH': info('Number of typed private control registers.',
            'More entries retain more scalar control values with additional data/type/ownership '
            'state. This does not add data ports or arithmetic execution units.'),
        'EVENT_INPUT_FIFO_DEPTH': info('Buffer capacity for incoming event/control records.',
            'More entries absorb bursts and internal handling stalls. They add record storage, '
            'rather than more event processing ports.'),
        'EVENT_OUTPUT_FIFO_DEPTH': info('Buffer capacity for outgoing event/control records.',
            'More entries decouple native sources from a stalled event sink. Sustained output '
            'bandwidth remains constrained by the single exposed event stream.'),
    },
}

# The fixed-point convention is a binary scale, not an IEEE floating-point format.
for _name, _width, _subject in (
        ('INPUT_FRAC_BITS', 'INPUT_WIDTH', 'input'),
        ('OUTPUT_FRAC_BITS', 'OUTPUT_WIDTH', 'output'),
        ('INTERNAL_FRAC_BITS', 'INTERNAL_WIDTH', 'working')):
    BY_TILE['SFT'][_name] = info(f'Binary fractional bits in the {_subject} format.',
        'The quantization step is 2^(-fraction bits). At fixed total width, more fraction bits '
        'improve representable resolution but leave fewer bits for integer range.',
        'Regenerate inputs, coefficients/tables and software interpretation for a changed scale. '
        'Algorithmic accuracy is not determined by fraction count alone.',
        metric={'kind': 'fraction', 'width': _width})

for _prefix, _unit, _extra in (('RECIP', 'reciprocal', 0), ('RSQRT', 'RSQRT', 1)):
    BY_TILE['SFT'][f'{_prefix}_INTERNAL_WIDTH'] = info(f'Working bit width inside {_unit} refinement.',
        'With fixed fraction count, more width adds intermediate range/headroom and widens native '
        'arithmetic/storage. It does not change the shared input/output formats.')
    BY_TILE['SFT'][f'{_prefix}_INTERNAL_FRAC_BITS'] = info(
        f'Working fractional bits inside {_unit} refinement.',
        'More fraction bits at fixed width improve representable working resolution while reducing '
        'integer headroom. Seed precision, iteration quality and final rounding also determine error.',
        metric={'kind': 'fraction', 'width': f'{_prefix}_INTERNAL_WIDTH'})
    BY_TILE['SFT'][f'{_prefix}_SEED_ADDRESS_WIDTH'] = info(
        f'Address precision of the normalized {_unit} seed table.',
        'Each extra bit doubles seed intervals and ROM entries. A better initial estimate can '
        'improve a selected iteration quality, but accuracy still needs numerical characterization.',
        metric={'kind': 'seed_entries', 'extra_address_bits': _extra})

PROTECTED_SUBJECTS = {
    'RF_PROTECTION': 'Scalar register data', 'VRF_PROTECTION': 'Vector register data',
    'CONTROL_PROTECTION': 'Control, validity and ownership state',
    'CONTEXT_PROTECTION': 'Stored context images', 'COMMAND_PROTECTION': 'Queued memory commands',
    'FIFO_PROTECTION': 'Memory-service FIFO records', 'TABLE_PROTECTION': 'Lookup/seed/table storage',
    'COEFFICIENT_PROTECTION': 'Programmed polynomial coefficients',
    'EVENT_PROTECTION': 'Event/control record storage',
}


def unit_info(kind, flag):
    description, enabled, disabled = UNITS[kind][flag]
    return dict(description=description, enabled=enabled, disabled=disabled,
        implications=['This is an elaboration-time selection. Regenerate RTL and matching context '
                      'programs after changing capabilities. Existing shared helpers can remain '
                      'when another selected operation needs them.'])


def parameter_info(kind, name):
    """No generic fallback: every exposed parameter needs deliberate documentation."""
    if name in UNITS[kind]:
        unit = unit_info(kind, name)
        return info(unit['description'], *unit['implications'],
            choices={0: unit['disabled'], 1: unit['enabled']},
            labels={0: 'Disabled', 1: 'Enabled'})
    if name in PROTECTED_SUBJECTS:
        return info(f'Error-protection policy for {PROTECTED_SUBJECTS[name].lower()}.',
            'Protection adds redundant storage and checking/correction logic to covered state. '
            'It preserves the separate ownership, format and protocol checks.',
            choices={0: 'No redundant payload protection; protocol/ownership checks remain.',
                     1: 'Parity detects odd-bit corruption but cannot correct it.',
                     2: 'SECDED corrects one-bit errors and detects two-bit errors per protected '
                        'codeword/stripe; it adds more redundant bits and decode logic.'},
            labels={0: 'None', 1: 'Parity', 2: 'SECDED'})
    return BY_TILE.get(kind, {}).get(name) or COMMON[name]
