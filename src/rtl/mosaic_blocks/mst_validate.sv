`timescale 1ns / 1ps
`default_nettype none

module mst_validate #(
    parameter ENABLE_LOAD = 1,
    parameter ENABLE_STORE = 1,
    parameter TILE_ID = 0,
    parameter ADDR_WIDTH = 32,
    parameter SHELL_DATA_WIDTH = 128,
    parameter MEMORY_DATA_WIDTH = 64,
    parameter NUM_STREAM_INPUTS = 2,
    parameter NUM_STREAM_OUTPUTS = 2,
    parameter NUM_LOAD_CHANNELS = 1,
    parameter NUM_STORE_CHANNELS = 1,
    parameter NUM_SCRATCHPAD_CLIENTS = 1,
    parameter NUM_DMA_INGRESS_CHANNELS = 1,
    parameter NUM_DMA_EGRESS_CHANNELS = 1,
    parameter CONTEXT_DEPTH = 4,
    parameter CONFIG_WORD_COUNT = 16,
    parameter COMMAND_QUEUE_DEPTH = 4,
    parameter READ_DATA_FIFO_DEPTH = 8,
    parameter WRITE_DATA_FIFO_DEPTH = 8,
    parameter COMPLETION_QUEUE_DEPTH = 4,
    parameter EVENT_QUEUE_DEPTH = 4,
    parameter MAX_OUTSTANDING_READS = 8,
    parameter MAX_OUTSTANDING_WRITES = 8,
    parameter COUNT_WIDTH = 16,
    parameter MAX_ELEMENT_BYTES = 16,
    parameter NUM_PROTECTION_REGIONS = 8,
    parameter NUM_BUFFER_ROLES = 2,
    parameter NUM_EVENTS = 16,
    parameter OWNER_ID_WIDTH = 16,
    parameter KERNEL_ID_WIDTH = 16,
    parameter PACKAGE_ID_WIDTH = 32,
    parameter CONTEXT_VERSION_WIDTH = 16,
    parameter COMMAND_ID_WIDTH = 16,
    parameter DESCRIPTOR_GENERATION_WIDTH = 16,
    parameter ALLOCATION_GENERATION_WIDTH = 16,
    parameter EXECUTION_EPOCH_WIDTH = 8,
    parameter SPACE_ID_WIDTH = 4,
    parameter STREAM_ID_WIDTH = 8,
    parameter REGION_ID_WIDTH = 4,
    parameter BUFFER_ID_WIDTH = 8,
    parameter DATATYPE_WIDTH = 6,
    parameter PRIORITY_WIDTH = 3,
    parameter TRANSFER_TIMEOUT_CYCLES = 65535,
    parameter CANCEL_TIMEOUT_CYCLES = 4095,
    parameter SUPPORT_2D = 1,
    parameter SUPPORT_3D = 0,
    parameter SUPPORT_CIRCULAR = 0,
    parameter SUPPORT_GATHER = 0,
    parameter SUPPORT_SCATTER = 0,
    parameter SUPPORT_ATOMICS = 0,
    parameter SUPPORT_LOCAL_COPY = 1,
    parameter SUPPORT_UNALIGNED = 1,
    parameter SUPPORT_WIDTH_CONVERSION = 1,
    parameter SUPPORT_ELEMENT_CONVERSION = 1,
    parameter SUPPORT_EVENT_START = 1,
    parameter SUPPORT_COMMAND_CHAINING = 1,
    parameter SUPPORT_DOUBLE_BUFFER = 1,
    parameter SUPPORT_MULTICAST = 0,
    parameter SUPPORT_DIRECT_MEMORY_PROXY = 0,
    parameter SUPPORT_CANCELLATION = 1,
    parameter COMMAND_PROTECTION = 0,
    parameter FIFO_PROTECTION = 0,
    parameter CONTROL_PROTECTION = 0,
    parameter ASYNC_SCRATCHPAD_CLOCK = 0,
    parameter ASYNC_DMA_CLOCK = 0,
    parameter ASYNC_RESET = 0,
    parameter TILE_ID_WIDTH = 16,
    parameter ARCH_VERSION_WIDTH = 16,
    parameter CAPABILITY_ID_WIDTH = 32,
    parameter INPUT_BUFFER_DEPTH = 1,
    parameter OUTPUT_BUFFER_DEPTH = 1,
    parameter PREDICATE_WIDTH = 1,
    parameter PREDICATE_METADATA_WIDTH = 16,
    parameter PREDICATE_INPUT_PORTS = 1,
    parameter PREDICATE_OUTPUT_PORTS = 1,
    parameter EVENT_INPUT_PORTS = 1,
    parameter EVENT_OUTPUT_PORTS = 1,
    parameter CONFIG_DATA_WIDTH = 64,
    parameter CONTEXT_CHECKSUM_WIDTH = 32,
    parameter SUPPORT_CONTEXT_CHECKSUM = 1,
    parameter CONFIG_ASYNC = 0,
    parameter CONFIG_QUEUE_DEPTH = 4,
    parameter RUNTIME_TAG_WIDTH = 8,
    parameter STALL_REASON_WIDTH = 8,
    parameter ERROR_CODE_WIDTH = 8,
    parameter TRACE_WIDTH = 64,
    parameter SUPPORT_TRACE = 0,
    parameter SUPPORT_RETENTION = 0,
    parameter SUPPORT_POWER_OFF = 0,
    parameter CONTEXT_PROTECTION = 0,
    parameter EVENT_WIDTH = 256,
    parameter DATA_METADATA_WIDTH = 256,
    localparam bit PARAMETERS_VALID =
        ((ADDR_WIDTH > 0) === 1'b1) && (^ADDR_WIDTH !== 1'bx) &&
        ((SHELL_DATA_WIDTH > 0) === 1'b1) && (^SHELL_DATA_WIDTH !== 1'bx) &&
        ((MEMORY_DATA_WIDTH > 0) === 1'b1) && (^MEMORY_DATA_WIDTH !== 1'bx) &&
        ((NUM_STREAM_INPUTS > 0) === 1'b1) && (^NUM_STREAM_INPUTS !== 1'bx) &&
        ((NUM_STREAM_OUTPUTS > 0) === 1'b1) && (^NUM_STREAM_OUTPUTS !== 1'bx) &&
        ((NUM_LOAD_CHANNELS > 0) === 1'b1) && (^NUM_LOAD_CHANNELS !== 1'bx) &&
        ((NUM_STORE_CHANNELS > 0) === 1'b1) && (^NUM_STORE_CHANNELS !== 1'bx) &&
        ((NUM_SCRATCHPAD_CLIENTS > 0) === 1'b1) && (^NUM_SCRATCHPAD_CLIENTS !== 1'bx) &&
        ((NUM_DMA_INGRESS_CHANNELS > 0) === 1'b1) && (^NUM_DMA_INGRESS_CHANNELS !== 1'bx) &&
        ((NUM_DMA_EGRESS_CHANNELS > 0) === 1'b1) && (^NUM_DMA_EGRESS_CHANNELS !== 1'bx) &&
        ((CONTEXT_DEPTH > 0) === 1'b1) && (^CONTEXT_DEPTH !== 1'bx) &&
        ((CONFIG_WORD_COUNT > 0) === 1'b1) && (^CONFIG_WORD_COUNT !== 1'bx) &&
        ((COMMAND_QUEUE_DEPTH > 0) === 1'b1) && (^COMMAND_QUEUE_DEPTH !== 1'bx) &&
        ((READ_DATA_FIFO_DEPTH > 0) === 1'b1) && (^READ_DATA_FIFO_DEPTH !== 1'bx) &&
        ((WRITE_DATA_FIFO_DEPTH > 0) === 1'b1) && (^WRITE_DATA_FIFO_DEPTH !== 1'bx) &&
        ((COMPLETION_QUEUE_DEPTH > 0) === 1'b1) && (^COMPLETION_QUEUE_DEPTH !== 1'bx) &&
        ((EVENT_QUEUE_DEPTH > 0) === 1'b1) && (^EVENT_QUEUE_DEPTH !== 1'bx) &&
        ((MAX_OUTSTANDING_READS > 0) === 1'b1) && (^MAX_OUTSTANDING_READS !== 1'bx) &&
        ((MAX_OUTSTANDING_WRITES > 0) === 1'b1) && (^MAX_OUTSTANDING_WRITES !== 1'bx) &&
        ((COUNT_WIDTH > 0) === 1'b1) && (^COUNT_WIDTH !== 1'bx) &&
        ((MAX_ELEMENT_BYTES > 0) === 1'b1) && (^MAX_ELEMENT_BYTES !== 1'bx) &&
        ((NUM_PROTECTION_REGIONS > 0) === 1'b1) && (^NUM_PROTECTION_REGIONS !== 1'bx) &&
        ((NUM_BUFFER_ROLES > 0) === 1'b1) && (^NUM_BUFFER_ROLES !== 1'bx) &&
        ((NUM_EVENTS > 0) === 1'b1) && (^NUM_EVENTS !== 1'bx) &&
        ((OWNER_ID_WIDTH > 0) === 1'b1) && (^OWNER_ID_WIDTH !== 1'bx) &&
        ((KERNEL_ID_WIDTH > 0) === 1'b1) && (^KERNEL_ID_WIDTH !== 1'bx) &&
        ((PACKAGE_ID_WIDTH > 0) === 1'b1) && (^PACKAGE_ID_WIDTH !== 1'bx) &&
        ((CONTEXT_VERSION_WIDTH > 0) === 1'b1) && (^CONTEXT_VERSION_WIDTH !== 1'bx) &&
        ((COMMAND_ID_WIDTH > 0) === 1'b1) && (^COMMAND_ID_WIDTH !== 1'bx) &&
        ((DESCRIPTOR_GENERATION_WIDTH > 0) === 1'b1) && (^DESCRIPTOR_GENERATION_WIDTH !== 1'bx) &&
        ((ALLOCATION_GENERATION_WIDTH > 0) === 1'b1) && (^ALLOCATION_GENERATION_WIDTH !== 1'bx) &&
        ((EXECUTION_EPOCH_WIDTH > 0) === 1'b1) && (^EXECUTION_EPOCH_WIDTH !== 1'bx) &&
        ((SPACE_ID_WIDTH > 0) === 1'b1) && (^SPACE_ID_WIDTH !== 1'bx) &&
        ((STREAM_ID_WIDTH > 0) === 1'b1) && (^STREAM_ID_WIDTH !== 1'bx) &&
        ((REGION_ID_WIDTH > 0) === 1'b1) && (^REGION_ID_WIDTH !== 1'bx) &&
        ((BUFFER_ID_WIDTH > 0) === 1'b1) && (^BUFFER_ID_WIDTH !== 1'bx) &&
        ((DATATYPE_WIDTH > 0) === 1'b1) && (^DATATYPE_WIDTH !== 1'bx) &&
        ((PRIORITY_WIDTH > 0) === 1'b1) && (^PRIORITY_WIDTH !== 1'bx) &&
        ((TRANSFER_TIMEOUT_CYCLES > 0) === 1'b1) && (^TRANSFER_TIMEOUT_CYCLES !== 1'bx) &&
        ((CANCEL_TIMEOUT_CYCLES > 0) === 1'b1) && (^CANCEL_TIMEOUT_CYCLES !== 1'bx) &&
        ((TILE_ID_WIDTH > 0) === 1'b1) && (^TILE_ID_WIDTH !== 1'bx) &&
        ((ARCH_VERSION_WIDTH > 0) === 1'b1) && (^ARCH_VERSION_WIDTH !== 1'bx) &&
        ((CAPABILITY_ID_WIDTH > 0) === 1'b1) && (^CAPABILITY_ID_WIDTH !== 1'bx) &&
        ((PREDICATE_WIDTH > 0) === 1'b1) && (^PREDICATE_WIDTH !== 1'bx) &&
        ((PREDICATE_METADATA_WIDTH > 0) === 1'b1) && (^PREDICATE_METADATA_WIDTH !== 1'bx) &&
        ((CONFIG_DATA_WIDTH > 0) === 1'b1) && (^CONFIG_DATA_WIDTH !== 1'bx) &&
        ((CONTEXT_CHECKSUM_WIDTH > 0) === 1'b1) && (^CONTEXT_CHECKSUM_WIDTH !== 1'bx) &&
        ((CONFIG_QUEUE_DEPTH > 0) === 1'b1) && (^CONFIG_QUEUE_DEPTH !== 1'bx) &&
        ((RUNTIME_TAG_WIDTH > 0) === 1'b1) && (^RUNTIME_TAG_WIDTH !== 1'bx) &&
        ((STALL_REASON_WIDTH > 0) === 1'b1) && (^STALL_REASON_WIDTH !== 1'bx) &&
        ((ERROR_CODE_WIDTH > 0) === 1'b1) && (^ERROR_CODE_WIDTH !== 1'bx) &&
        ((TRACE_WIDTH > 0) === 1'b1) && (^TRACE_WIDTH !== 1'bx) &&
        ((EVENT_WIDTH > 0) === 1'b1) && (^EVENT_WIDTH !== 1'bx) &&
        ((DATA_METADATA_WIDTH > 0) === 1'b1) && (^DATA_METADATA_WIDTH !== 1'bx) &&
        ((SUPPORT_2D === 0) || (SUPPORT_2D === 1)) &&
        ((SUPPORT_3D === 0) || (SUPPORT_3D === 1)) &&
        ((SUPPORT_CIRCULAR === 0) || (SUPPORT_CIRCULAR === 1)) &&
        ((SUPPORT_GATHER === 0) || (SUPPORT_GATHER === 1)) &&
        ((SUPPORT_SCATTER === 0) || (SUPPORT_SCATTER === 1)) &&
        ((SUPPORT_ATOMICS === 0) || (SUPPORT_ATOMICS === 1)) &&
        ((SUPPORT_LOCAL_COPY === 0) || (SUPPORT_LOCAL_COPY === 1)) &&
        ((SUPPORT_UNALIGNED === 0) || (SUPPORT_UNALIGNED === 1)) &&
        ((SUPPORT_WIDTH_CONVERSION === 0) || (SUPPORT_WIDTH_CONVERSION === 1)) &&
        ((SUPPORT_ELEMENT_CONVERSION === 0) || (SUPPORT_ELEMENT_CONVERSION === 1)) &&
        ((SUPPORT_EVENT_START === 0) || (SUPPORT_EVENT_START === 1)) &&
        ((SUPPORT_COMMAND_CHAINING === 0) || (SUPPORT_COMMAND_CHAINING === 1)) &&
        ((SUPPORT_DOUBLE_BUFFER === 0) || (SUPPORT_DOUBLE_BUFFER === 1)) &&
        ((SUPPORT_MULTICAST === 0) || (SUPPORT_MULTICAST === 1)) &&
        ((SUPPORT_DIRECT_MEMORY_PROXY === 0) || (SUPPORT_DIRECT_MEMORY_PROXY === 1)) &&
        ((SUPPORT_CANCELLATION === 0) || (SUPPORT_CANCELLATION === 1)) &&
        ((ASYNC_SCRATCHPAD_CLOCK === 0) || (ASYNC_SCRATCHPAD_CLOCK === 1)) &&
        ((ASYNC_DMA_CLOCK === 0) || (ASYNC_DMA_CLOCK === 1)) &&
        ((ASYNC_RESET === 0) || (ASYNC_RESET === 1)) &&
        ((SUPPORT_CONTEXT_CHECKSUM === 0) || (SUPPORT_CONTEXT_CHECKSUM === 1)) &&
        ((CONFIG_ASYNC === 0) || (CONFIG_ASYNC === 1)) &&
        ((SUPPORT_TRACE === 0) || (SUPPORT_TRACE === 1)) &&
        ((SUPPORT_RETENTION === 0) || (SUPPORT_RETENTION === 1)) &&
        ((SUPPORT_POWER_OFF === 0) || (SUPPORT_POWER_OFF === 1)) &&
        ((COMMAND_PROTECTION === 0) || (COMMAND_PROTECTION === 1) || (COMMAND_PROTECTION === 2))
            &&
        ((FIFO_PROTECTION === 0) || (FIFO_PROTECTION === 1) || (FIFO_PROTECTION === 2)) &&
        ((CONTROL_PROTECTION === 0) || (CONTROL_PROTECTION === 1) || (CONTROL_PROTECTION === 2))
            &&
        ((CONTEXT_PROTECTION === 0) || (CONTEXT_PROTECTION === 1) || (CONTEXT_PROTECTION === 2))
            &&
        ((SHELL_DATA_WIDTH >= 8 && SHELL_DATA_WIDTH <= 256 && SHELL_DATA_WIDTH % 8 == 0) === 1'b1)
            &&
        (((SHELL_DATA_WIDTH / 8) & (SHELL_DATA_WIDTH / 8 - 1)) == 0) &&
        ((MEMORY_DATA_WIDTH >= 8 && MEMORY_DATA_WIDTH <= 256 && MEMORY_DATA_WIDTH % 8 == 0) ===
            1'b1) &&
        (((MEMORY_DATA_WIDTH / 8) & (MEMORY_DATA_WIDTH / 8 - 1)) == 0) &&
        ((NUM_LOAD_CHANNELS <= 8) === 1'b1) &&
        ((NUM_STORE_CHANNELS <= 8) === 1'b1) &&
        ((NUM_SCRATCHPAD_CLIENTS <= 8) === 1'b1) &&
        ((NUM_DMA_INGRESS_CHANNELS <= 8) === 1'b1) &&
        ((NUM_DMA_EGRESS_CHANNELS <= 8) === 1'b1) &&
        ((NUM_STREAM_INPUTS <= 8) === 1'b1) &&
        ((NUM_STREAM_OUTPUTS <= 8) === 1'b1) &&
        ((TILE_ID >= 0) === 1'b1) && (^TILE_ID !== 1'bx) &&
        ((INPUT_BUFFER_DEPTH >= 0) === 1'b1) && (^INPUT_BUFFER_DEPTH !== 1'bx) &&
        ((OUTPUT_BUFFER_DEPTH >= 0) === 1'b1) && (^OUTPUT_BUFFER_DEPTH !== 1'bx) &&
        ((SUPPORT_WIDTH_CONVERSION == 1 || SHELL_DATA_WIDTH == MEMORY_DATA_WIDTH) === 1'b1) &&
        (((MAX_ELEMENT_BYTES & (MAX_ELEMENT_BYTES - 1)) == 0) === 1'b1) &&
        ((MAX_ELEMENT_BYTES <= (SHELL_DATA_WIDTH > MEMORY_DATA_WIDTH ?
            SHELL_DATA_WIDTH : MEMORY_DATA_WIDTH) / 8) === 1'b1) &&
        ((ADDR_WIDTH >= $clog2(MAX_ELEMENT_BYTES > 0 ? MAX_ELEMENT_BYTES : 1)) === 1'b1) &&
        ((128'(NUM_PROTECTION_REGIONS) <= (128'd1 << REGION_ID_WIDTH)) === 1'b1) &&
        ((128'(NUM_BUFFER_ROLES) <= (128'd1 << BUFFER_ID_WIDTH)) === 1'b1) &&
        ((SUPPORT_DOUBLE_BUFFER == 0 || NUM_BUFFER_ROLES >= 2) === 1'b1) &&
        ((CONFIG_DATA_WIDTH >= 8 && CONFIG_DATA_WIDTH % 8 == 0) === 1'b1) &&
        ((CONFIG_ASYNC == 0 || CONFIG_QUEUE_DEPTH >= 2) === 1'b1) &&
        ((128'(TILE_ID) >> TILE_ID_WIDTH) === 128'b0) &&
        ((COUNT_WIDTH <= 32 && ADDR_WIDTH <= 64 && EXECUTION_EPOCH_WIDTH <= 32) === 1'b1) &&
        ((128'(CONFIG_WORD_COUNT) * 128'(CONFIG_DATA_WIDTH) < 128'd2147483647) === 1'b1) &&
        ((128'(NUM_LOAD_CHANNELS + NUM_STORE_CHANNELS) * 128'(COMMAND_QUEUE_DEPTH) *
            (128'(ADDR_WIDTH) * 12 + 128'(DATA_METADATA_WIDTH) + 2048) <
            128'd2147483647) === 1'b1),
    localparam int A = PARAMETERS_VALID ? ADDR_WIDTH : 1,
    localparam int D = PARAMETERS_VALID ? SHELL_DATA_WIDTH : 8,
    localparam int MD = PARAMETERS_VALID ? MEMORY_DATA_WIDTH : 8,
    localparam int ED = D > MD ? D : MD,
    localparam int SY = D / 8,
    localparam int MY = MD / 8,
    localparam int EY = ED / 8,
    localparam int NI = PARAMETERS_VALID ? NUM_STREAM_INPUTS : 1,
    localparam int NO = PARAMETERS_VALID ? NUM_STREAM_OUTPUTS : 1,
    localparam int NL = PARAMETERS_VALID ? NUM_LOAD_CHANNELS : 1,
    localparam int NS = PARAMETERS_VALID ? NUM_STORE_CHANNELS : 1,
    localparam int NM = PARAMETERS_VALID ? NUM_SCRATCHPAD_CLIENTS : 1,
    localparam int NDI = PARAMETERS_VALID ? NUM_DMA_INGRESS_CHANNELS : 1,
    localparam int NDO = PARAMETERS_VALID ? NUM_DMA_EGRESS_CHANNELS : 1,
    localparam int H = NL + NS,
    localparam int HCI = $clog2(H),
    localparam int LCI = NL > 1 ? $clog2(NL) : 1,
    localparam int SCI = NS > 1 ? $clog2(NS) : 1,
    localparam int CHANNEL_COUNT = NI > NO ? NI : NO,
    localparam int DMA_CHANNEL_COUNT = NDI > NDO ? NDI : NDO,
    localparam int ENDPOINT_COUNT = CHANNEL_COUNT > DMA_CHANNEL_COUNT ?
        CHANNEL_COUNT : DMA_CHANNEL_COUNT,
    localparam int MAX_ENDPOINTS = ENDPOINT_COUNT > NM ? ENDPOINT_COUNT : NM,
    localparam int CH = MAX_ENDPOINTS > 1 ? $clog2(MAX_ENDPOINTS) : 1,
    localparam int C = PARAMETERS_VALID ? COUNT_WIDTH : 1,
    localparam int NC = PARAMETERS_VALID ? CONTEXT_DEPTH : 1,
    localparam int CI = NC > 1 ? $clog2(NC) : 1,
    localparam int N = PARAMETERS_VALID ? CONFIG_WORD_COUNT : 1,
    localparam int W = PARAMETERS_VALID ? CONFIG_DATA_WIDTH : 8,
    localparam int IM = N * W,
    localparam int WI = N > 1 ? $clog2(N) : 1,
    localparam int BY = W / 8,
    localparam int Q = PARAMETERS_VALID ? COMMAND_QUEUE_DEPTH : 1,
    localparam int OC = $clog2(Q + 1),
    localparam int NR = PARAMETERS_VALID ? NUM_PROTECTION_REGIONS : 1,
    localparam int NB = PARAMETERS_VALID ? NUM_BUFFER_ROLES : 1,
    localparam int NE = PARAMETERS_VALID ? NUM_EVENTS : 1,
    localparam int EI = NE > 1 ? $clog2(NE) : 1,
    localparam int RI = PARAMETERS_VALID ? REGION_ID_WIDTH : 1,
    localparam int BU = PARAMETERS_VALID ? BUFFER_ID_WIDTH : 1,
    localparam int O = PARAMETERS_VALID ? OWNER_ID_WIDTH : 1,
    localparam int K = PARAMETERS_VALID ? KERNEL_ID_WIDTH : 1,
    localparam int PK = PARAMETERS_VALID ? PACKAGE_ID_WIDTH : 1,
    localparam int V = PARAMETERS_VALID ? CONTEXT_VERSION_WIDTH : 1,
    localparam int J = PARAMETERS_VALID ? COMMAND_ID_WIDTH : 1,
    localparam int DG = PARAMETERS_VALID ? DESCRIPTOR_GENERATION_WIDTH : 1,
    localparam int AL = PARAMETERS_VALID ? ALLOCATION_GENERATION_WIDTH : 1,
    localparam int EP = PARAMETERS_VALID ? EXECUTION_EPOCH_WIDTH : 1,
    localparam int SP = PARAMETERS_VALID ? SPACE_ID_WIDTH : 1,
    localparam int ST = PARAMETERS_VALID ? STREAM_ID_WIDTH : 1,
    localparam int DT = PARAMETERS_VALID ? DATATYPE_WIDTH : 1,
    localparam int PR = PARAMETERS_VALID ? PRIORITY_WIDTH : 1,
    localparam int TW = PARAMETERS_VALID ? $clog2(64'(TRANSFER_TIMEOUT_CYCLES) + 1) : 1,
    localparam int CT = PARAMETERS_VALID ? $clog2(64'(CANCEL_TIMEOUT_CYCLES) + 1) : 1,
    localparam int LOG = $clog2(EY),
    localparam int SZ = LOG > 0 ? $clog2(LOG + 1) : 1,
    localparam int MSZ = MY > 1 ? $clog2($clog2(MY) + 1) : 1,
    localparam int NN = MAX_OUTSTANDING_READS > MAX_OUTSTANDING_WRITES ?
        MAX_OUTSTANDING_READS : MAX_OUTSTANDING_WRITES,
    localparam int SI = PARAMETERS_VALID && NN > 1 ? $clog2(NN) : 1,
    localparam int SG = 64,
    localparam int FI = $clog2(EY + 1),
    localparam int AT = EP + SG + SI + FI,
    localparam int MT = HCI + AT,
    localparam int MBW = $clog2(MY + 1),
    localparam int BC = 2 * C + LOG + 2,
    localparam int VW = A > 2 * C + LOG + 1 ? A : 2 * C + LOG + 1,
    localparam int VC = 2 * C,
    localparam int M = PARAMETERS_VALID ? DATA_METADATA_WIDTH : 1,
    localparam int E = PARAMETERS_VALID ? EVENT_WIDTH : 1,
    localparam int TI = PARAMETERS_VALID ? TILE_ID_WIDTH : 1,
    localparam int AV = PARAMETERS_VALID ? ARCH_VERSION_WIDTH : 1,
    localparam int CP = PARAMETERS_VALID ? CAPABILITY_ID_WIDTH : 1,
    localparam int BI = PARAMETERS_VALID ? INPUT_BUFFER_DEPTH : 1,
    localparam int BO = PARAMETERS_VALID ? OUTPUT_BUFFER_DEPTH : 1,
    localparam int P = PARAMETERS_VALID ? PREDICATE_WIDTH : 1,
    localparam int PM = PARAMETERS_VALID ? PREDICATE_METADATA_WIDTH : 1,
    localparam int PI = PARAMETERS_VALID ? PREDICATE_INPUT_PORTS : 1,
    localparam int PO = PARAMETERS_VALID ? PREDICATE_OUTPUT_PORTS : 1,
    localparam int INE = PARAMETERS_VALID ? EVENT_INPUT_PORTS : 1,
    localparam int EO = PARAMETERS_VALID ? EVENT_OUTPUT_PORTS : 1,
    localparam int T = PARAMETERS_VALID ? RUNTIME_TAG_WIDTH : 1,
    localparam int S = PARAMETERS_VALID ? STALL_REASON_WIDTH : 1,
    localparam int ER = PARAMETERS_VALID ? ERROR_CODE_WIDTH : 1,
    localparam int TR = PARAMETERS_VALID ? TRACE_WIDTH : 1,
    localparam int IDW = (J) + (DG) + (O) + (K) + (PK) + (CI) + (V) + (AL) + (EP),
    localparam int MOW = (3) + (3) + (LCI) + (SCI),
    localparam int ENW = (SP) + (CH) + (RI) + (DG) + (1) + (BU) + (DG) + (A) + (A) + (A),
    localparam int FOW = (SZ) + (SZ) + (SZ) + (DT) + (1) + (1) + (1) + (1),
    localparam int EVW = (2) + (NE) + (J) + (DG) + (1) + (EI) + (1) + (J) + (DG),
    localparam int CTW = (C) + (C) + (PR) + (TW) + (1),
    localparam int RGW = (1) + (DG) + (SP) + (A) + (A + 1) + (O) + (K) + (AL) + (1) + (1) + (1) +
        (1) + (1 << CH) + (NB),
    localparam int BUW = (1) + (DG) + (3) + (SP) + (RI) + (A) + (A + 1) + (O) + (K) + (PK) + (CI) +
        (AL),
    localparam int DESC = IDW + MOW + 2 * ENW + FOW + EVW + CTW,
    localparam int CONTEXT_BITS = 8 + PK + AL + NL + NS + NR + 2 + DESC,
    localparam int STREAM_BITS = CI + V + IDW + 2 * SY + DT + ST + 6 + 2 * SZ,
    localparam int EVENT_BITS = 3 + CI + K + EI + 16 + IDW + 1 + 32,
    parameter INPUT_ELASTIC_MASK = {NI{1'b1}},
    parameter OUTPUT_ELASTIC_MASK = {NO{1'b1}}
) (
    input wire i_enable,
    input wire i_dynamic,
    input wire [DESC-1:0] i_descriptor,
    input wire [O-1:0] i_owner,
    input wire [K-1:0] i_kernel,
    input wire [PK-1:0] i_package,
    input wire [AL-1:0] i_allocation,
    input wire [CI-1:0] i_context,
    input wire [V-1:0] i_version,
    input wire [EP-1:0] i_epoch,
    input wire [NL-1:0] i_load_mask,
    input wire [NS-1:0] i_store_mask,
    input wire [NR-1:0] i_region_mask,
    input wire [NR*RGW-1:0] i_regions,
    input wire [NB*BUW-1:0] i_buffers,
    output logic [7:0] o_code,
    output wire [A:0] o_source_low,
    output wire [A+1:0] o_source_limit,
    output wire [A:0] o_destination_low,
    output wire [A+1:0] o_destination_limit
);
    import mst_pkg::*;
    // Parameter-dependent records. Python layout.py publishes the same
    // LSB-first field catalog; only enums belong to the shared package.
    typedef struct packed {
        logic [EP-1:0] epoch;
        logic [AL-1:0] allocation;
        logic [V-1:0] version;
        logic [CI-1:0] context_id;
        logic [PK-1:0] package_id;
        logic [K-1:0] kernel;
        logic [O-1:0] owner;
        logic [DG-1:0] generation;
        logic [J-1:0] command;
    } identity_t;

    localparam int IDENTITY_BITS = $bits(identity_t);

    typedef struct packed {
        logic [SCI-1:0] store_channel;
        logic [LCI-1:0] load_channel;
        logic [2:0] address_mode;
        logic [2:0] transfer;
    } mode_t;

    localparam int MODE_BITS = $bits(mode_t);

    typedef struct packed {
        logic [A-1:0] outer_stride;
        logic [A-1:0] inner_stride;
        logic [A-1:0] base;
        logic [DG-1:0] buffer_generation;
        logic [BU-1:0] buffer_id;
        logic buffer_enable;
        logic [DG-1:0] region_generation;
        logic [RI-1:0] region_id;
        logic [CH-1:0] channel;
        logic [SP-1:0] space;
    } endpoint_t;

    localparam int ENDPOINT_BITS = $bits(endpoint_t);

    typedef struct packed {
        logic eos;
        logic reverse;
        logic saturate;
        logic signed_mode;
        logic [DT-1:0] datatype;
        logic [SZ-1:0] lane_log2;
        logic [SZ-1:0] destination_log2;
        logic [SZ-1:0] source_log2;
    } format_t;

    localparam int FORMAT_BITS = $bits(format_t);

    typedef struct packed {
        logic [DG-1:0] chain_generation;
        logic [J-1:0] chain_command;
        logic chain_enable;
        logic [EI-1:0] completion_id;
        logic completion_enable;
        logic [DG-1:0] dependency_generation;
        logic [J-1:0] dependency;
        logic [NE-1:0] mask;
        logic [1:0] start;
    } events_t;

    localparam int EVENTS_BITS = $bits(events_t);

    typedef struct packed {
        logic cancelable;
        logic [TW-1:0] timeout;
        logic [PR-1:0] priority_hint;
        logic [C-1:0] outer_count;
        logic [C-1:0] inner_count;
    } control_t;

    localparam int CONTROL_BITS = $bits(control_t);

    typedef struct packed {
        logic [NB-1:0] buffer_mask;
        logic [1<<CH-1:0] channel_mask;
        logic shared_read;
        logic dma_enable;
        logic write_enable;
        logic read_enable;
        logic [AL-1:0] allocation;
        logic [K-1:0] kernel;
        logic [O-1:0] owner;
        logic [A+1-1:0] limit;
        logic [A-1:0] base;
        logic [SP-1:0] space;
        logic [DG-1:0] generation;
        logic valid;
    } region_t;

    localparam int REGION_BITS = $bits(region_t);

    typedef struct packed {
        logic [AL-1:0] allocation;
        logic [CI-1:0] context_id;
        logic [PK-1:0] package_id;
        logic [K-1:0] kernel;
        logic [O-1:0] owner;
        logic [A+1-1:0] limit;
        logic [A-1:0] base;
        logic [RI-1:0] region_id;
        logic [SP-1:0] space;
        logic [2:0] state;
        logic [DG-1:0] generation;
        logic valid;
    } buffer_t;

    localparam int BUFFER_BITS = $bits(buffer_t);

    typedef struct packed {
        control_t control;
        events_t events;
        format_t format;
        endpoint_t destination;
        endpoint_t source;
        mode_t mode;
        identity_t identity;
    } descriptor_t;

    localparam int DESCRIPTOR_BITS = $bits(descriptor_t);

    typedef struct packed {
        logic [SZ-1:0] lane_log2;
        logic [SZ-1:0] element_log2;
        logic error;
        logic eos;
        logic row_last;
        logic row_first;
        logic last;
        logic first;
        logic [ST-1:0] channel;
        logic [DT-1:0] datatype;
        logic [SY-1:0] lanes;
        logic [SY-1:0] keep;
        identity_t identity;
        logic [V-1:0] version;
        logic [CI-1:0] context_id;
    } stream_t;

    typedef struct packed {
        logic [31:0] payload;
        logic error;
        identity_t identity;
        logic [15:0] sequence_id;
        logic [EI-1:0] id;
        logic [K-1:0] kernel;
        logic [CI-1:0] context_id;
        logic [2:0] kind;
    } event_t;

    typedef struct packed {
        descriptor_t descriptor;
        logic [NR-1:0] regions;
        logic [NS-1:0] stores;
        logic [NL-1:0] loads;
        logic terminal;
        logic automatic_command;
        logic [AL-1:0] allocation;
        logic [PK-1:0] package_id;
        logic [7:0] schema;
    } context_t;

    typedef struct packed {
        logic effects_unknown;
        logic partial;
        logic [2*C-1:0] elements;
        logic [BC-1:0] bytes_written;
        logic [BC-1:0] bytes_read;
        logic [7:0] code;
        logic [1:0] status;
        logic [HCI-1:0] channel;
        identity_t identity;
    } completion_t;

    descriptor_t d;
    assign d = i_descriptor;
    wire [SZ-1:0] source_size = d.format.source_log2 + d.format.lane_log2;
    wire [SZ-1:0] destination_size = d.format.destination_log2 + d.format.lane_log2;
    wire [A-1:0] source_step = d.mode.address_mode == MST_ADDR_LINEAR ?
        A'(64'd1 << source_size) : d.source.inner_stride;
    wire [A-1:0] destination_step = d.mode.address_mode == MST_ADDR_LINEAR ?
        A'(64'd1 << destination_size) : d.destination.inner_stride;
    wire [A:0] source_start_limit;
    wire [A:0] destination_start_limit;
    wire source_legal;
    wire destination_legal;
    assign o_source_limit = {1'b0, source_start_limit} +
        (A + 2)'((64'd1 << source_size) - 1'b1);
    assign o_destination_limit = {1'b0, destination_start_limit} +
        (A + 2)'((64'd1 << destination_size) - 1'b1);

    // Ask the shared mathematical checker for the rectangle of element starts
    // using byte alignment, then extend by the true element byte count. This
    // reuses its signed arithmetic without weakening its existing aligned users.
    dma_engine_bounds #(.W(A), .C(C), .SIZE_WIDTH(SZ), .MAX_ELEMENT_LOG2(LOG)) u_source (
        .i_enable(i_enable && memory_source(d.mode.transfer)),
        .i_mode(d.mode.address_mode == MST_ADDR_STRIDED_2D ? 2'b10 : 2'b01),
        .i_base(A'(d.source.base)),
        .i_inner_stride(source_step),
        .i_outer_stride(A'(d.source.outer_stride)),
        .i_inner_count(C'(d.control.inner_count)),
        .i_outer_count(C'(d.control.outer_count)),
        .i_size({SZ{1'b0}}),
        .o_legal(source_legal),
        .o_error(),
        .o_lowest(o_source_low),
        .o_limit(source_start_limit)
    );

    dma_engine_bounds #(.W(A), .C(C), .SIZE_WIDTH(SZ), .MAX_ELEMENT_LOG2(LOG)) u_destination (
        .i_enable(i_enable && memory_destination(d.mode.transfer)),
        .i_mode(d.mode.address_mode == MST_ADDR_STRIDED_2D ? 2'b10 : 2'b01),
        .i_base(A'(d.destination.base)),
        .i_inner_stride(destination_step),
        .i_outer_stride(A'(d.destination.outer_stride)),
        .i_inner_count(C'(d.control.inner_count)),
        .i_outer_count(C'(d.control.outer_count)),
        .i_size({SZ{1'b0}}),
        .o_legal(destination_legal),
        .o_error(),
        .o_lowest(o_destination_low),
        .o_limit(destination_start_limit)
    );

    function automatic logic region_ok(input endpoint_t endpoint,
        input logic write, input logic [A:0] lowest, input logic [A+1:0] limit);
        region_t r;
        logic ok;
        r = '0;
        ok = 1'b0;

        if (int'(endpoint.region_id) < NR) begin
            r = i_regions[endpoint.region_id*RGW+:RGW];
            ok = r.valid && ((i_region_mask >> endpoint.region_id) & 1'b1) &&
                r.generation == endpoint.region_generation && r.space == endpoint.space &&
                r.allocation == d.identity.allocation && lowest >= {1'b0, r.base} &&
                limit <= {1'b0, r.limit} &&
                ((r.channel_mask >> endpoint.channel) & 1'b1) &&
                (!endpoint.buffer_enable || ((r.buffer_mask >> endpoint.buffer_id) & 1'b1)) &&
                (write ? r.write_enable : r.read_enable) &&
                ((!write && r.shared_read) ||
                    (r.owner == d.identity.owner && r.kernel == d.identity.kernel)) &&
                (!(d.mode.transfer == MST_DMA_TO_MEMORY || d.mode.transfer == MST_MEMORY_TO_DMA) ||
                    r.dma_enable);
        end

        return ok;
    endfunction

    function automatic logic buffer_binding_ok(input endpoint_t endpoint,
        input logic [A:0] lowest, input logic [A+1:0] limit);
        buffer_t b;
        logic ok;
        b = '0;
        ok =!endpoint.buffer_enable;

        if (endpoint.buffer_enable && int'(endpoint.buffer_id) < NB) begin
            b = i_buffers[endpoint.buffer_id*BUW+:BUW];
            ok = SUPPORT_DOUBLE_BUFFER == 1 && b.valid && b.space == endpoint.space &&
                b.region_id == endpoint.region_id && lowest >= {1'b0, b.base} &&
                limit <= {1'b0, b.limit} && b.owner == d.identity.owner &&
                b.kernel == d.identity.kernel && b.package_id == d.identity.package_id &&
                b.context_id == d.identity.context_id && b.allocation == d.identity.allocation;
        end

        return ok;
    endfunction

    always @* begin
        logic matrix_ok;
        logic channel_ok;
        logic [A-1:0] source_alignment;
        logic [A-1:0] destination_alignment;
        matrix_ok = 1'b0;
        channel_ok = int'(d.mode.load_channel) < NL && int'(d.mode.store_channel) < NS;
        source_alignment = A'((64'd1 << source_size) - 1'b1);
        destination_alignment = A'((64'd1 << destination_size) - 1'b1);

        case (d.mode.transfer)
            MST_LOAD_STREAM: matrix_ok = d.source.space == MST_SPACE_SCRATCHPAD &&
                d.destination.space == MST_SPACE_TILE_STREAM;
            MST_STORE_STREAM: matrix_ok = d.source.space == MST_SPACE_TILE_STREAM &&
                d.destination.space == MST_SPACE_SCRATCHPAD;
            MST_LOCAL_COPY: matrix_ok = SUPPORT_LOCAL_COPY == 1 &&
                d.source.space == MST_SPACE_SCRATCHPAD && d.destination.space ==
                    MST_SPACE_SCRATCHPAD;
            MST_DMA_TO_STREAM: matrix_ok = d.source.space == MST_SPACE_DMA_STREAM &&
                d.destination.space == MST_SPACE_TILE_STREAM;
            MST_STREAM_TO_DMA: matrix_ok = d.source.space == MST_SPACE_TILE_STREAM &&
                d.destination.space == MST_SPACE_DMA_STREAM;
            MST_DMA_TO_MEMORY: matrix_ok = d.source.space == MST_SPACE_DMA_STREAM &&
                d.destination.space == MST_SPACE_SCRATCHPAD;
            MST_MEMORY_TO_DMA: matrix_ok = d.source.space == MST_SPACE_SCRATCHPAD &&
                d.destination.space == MST_SPACE_DMA_STREAM;
            MST_STREAM_FORWARD: matrix_ok = d.source.space == MST_SPACE_TILE_STREAM &&
                d.destination.space == MST_SPACE_TILE_STREAM;
        endcase

        if (memory_source(d.mode.transfer)) channel_ok &= int'(d.source.channel) < NM;
        else if (d.source.space == MST_SPACE_TILE_STREAM) channel_ok &= int'(d.source.channel) < NI;
        else channel_ok &= int'(d.source.channel) < NDI;

        if (memory_destination(d.mode.transfer)) channel_ok &= int'(d.destination.channel) < NM;
        else if (d.destination.space == MST_SPACE_TILE_STREAM)
            channel_ok &= int'(d.destination.channel) < NO;
        else channel_ok &= int'(d.destination.channel) < NDO;

        o_code = MST_OK;

        if (i_enable) begin
            if (^{i_descriptor, i_owner, i_kernel, i_package, i_allocation, i_context,
                i_version, i_epoch, i_load_mask, i_store_mask, i_region_mask} === 1'bx)
                o_code = MST_ERR_UNKNOWN;
            else if (d.identity.owner != i_owner || d.identity.kernel != i_kernel ||
                d.identity.package_id != i_package || d.identity.allocation != i_allocation ||
                d.identity.context_id != i_context || d.identity.version != i_version ||
                d.identity.epoch != i_epoch) o_code = MST_ERR_IDENTITY;
            else if (!matrix_ok || d.mode.address_mode > MST_ADDR_STRIDED_2D ||
                (d.mode.address_mode == MST_ADDR_STRIDED_2D && SUPPORT_2D == 0))
                o_code = MST_ERR_MODE;
            else if (!channel_ok || (load_class(d.mode.transfer) &&!ENABLE_LOAD) ||
                ((!load_class(d.mode.transfer) || d.mode.transfer == MST_LOCAL_COPY) &&
                    !ENABLE_STORE) ||
                (load_class(d.mode.transfer) &&
                    ((i_load_mask >> d.mode.load_channel) & 1'b1) == 0) ||
                ((!load_class(d.mode.transfer) || d.mode.transfer == MST_LOCAL_COPY) &&
                    ((i_store_mask >> d.mode.store_channel) & 1'b1) == 0))
                o_code = MST_ERR_CHANNEL;
            else if (d.control.inner_count == 0 || d.control.outer_count == 0 ||
                (d.mode.address_mode != MST_ADDR_STRIDED_2D && d.control.outer_count != 1))
                o_code = MST_ERR_COUNT;
            else if (int'(d.format.source_log2) + int'(d.format.lane_log2) > LOG ||
                int'(d.format.destination_log2) + int'(d.format.lane_log2) > LOG ||
                (64'd1 << source_size) > MAX_ELEMENT_BYTES ||
                (64'd1 << destination_size) > MAX_ELEMENT_BYTES)
                o_code = MST_ERR_SIZE;
            else if ((SUPPORT_ELEMENT_CONVERSION == 0 &&
                d.format.source_log2 != d.format.destination_log2) || d.format.datatype > 1)
                o_code = MST_ERR_FORMAT;
            else if (d.control.timeout > TRANSFER_TIMEOUT_CYCLES ||
                (SUPPORT_CANCELLATION == 0 && d.control.cancelable)) o_code = MST_ERR_RESOURCE;
            else if ((d.events.start != 0 &&
                (SUPPORT_EVENT_START == 0 || d.events.mask == 0)) ||
                (d.events.start == 1 && (d.events.mask & (d.events.mask - 1'b1)) != 0) ||
                (d.events.completion_enable && int'(d.events.completion_id) >= NE) ||
                (d.events.start != 0 && d.events.completion_enable &&
                    ((d.events.mask >> d.events.completion_id) & 1'b1) &&
                    d.events.dependency == d.identity.command &&
                    d.events.dependency_generation == d.identity.generation) ||
                (d.events.chain_enable && (SUPPORT_COMMAND_CHAINING == 0 ||
!d.events.completion_enable ||
                    (d.events.chain_command == d.identity.command &&
                        d.events.chain_generation == d.identity.generation)))) o_code =
                            MST_ERR_EVENT;
            else if ((memory_source(d.mode.transfer) &&
                (!source_legal || o_source_limit > ((A + 2)'(1) << A))) ||
                (memory_destination(d.mode.transfer) &&
                (!destination_legal || o_destination_limit > ((A + 2)'(1) << A))))
                o_code = MST_ERR_BOUNDS;
            else if (SUPPORT_UNALIGNED == 0 &&
                ((memory_source(d.mode.transfer) &&
                    ((d.source.base & source_alignment) != 0 ||
                    (source_step & source_alignment) != 0 ||
                    (d.mode.address_mode == MST_ADDR_STRIDED_2D &&
                        (d.source.outer_stride & source_alignment) != 0))) ||
                (memory_destination(d.mode.transfer) &&
                    ((d.destination.base & destination_alignment) != 0 ||
                    (destination_step & destination_alignment) != 0 ||
                    (d.mode.address_mode == MST_ADDR_STRIDED_2D &&
                        (d.destination.outer_stride & destination_alignment) != 0)))))
                o_code = MST_ERR_ALIGNMENT;
            else if ((memory_source(d.mode.transfer) &&
!region_ok(d.source, 1'b0, o_source_low, o_source_limit)) ||
                (memory_destination(d.mode.transfer) &&
!region_ok(d.destination, 1'b1, o_destination_low, o_destination_limit)))
                o_code = MST_ERR_PERMISSION;
            else if ((d.source.buffer_enable && (!memory_source(d.mode.transfer) ||
!buffer_binding_ok(d.source, o_source_low, o_source_limit))) ||
                (d.destination.buffer_enable && (!memory_destination(d.mode.transfer) ||
!buffer_binding_ok(d.destination, o_destination_low, o_destination_limit))) ||
                (d.source.buffer_enable && d.destination.buffer_enable &&
                    d.source.buffer_id == d.destination.buffer_id)) o_code = MST_ERR_BUFFER;
            else if (d.mode.transfer == MST_LOCAL_COPY &&
                o_source_low < o_destination_limit && o_destination_low < o_source_limit)
                o_code = MST_ERR_OVERLAP;

            for (int side = 0; side < 2; side++) begin
                endpoint_t endpoint;
                buffer_t b;
                endpoint = side == 0 ? d.source : d.destination;
                b = '0;

                if (int'(endpoint.buffer_id) < NB)
                    b = i_buffers[endpoint.buffer_id*BUW+:BUW];

                if (o_code == MST_OK && endpoint.buffer_enable) begin
                    if (i_dynamic) begin
                        if (b.generation != endpoint.buffer_generation ||
                            b.generation >= {DG{1'b1}} - DG'(1)) o_code = MST_ERR_GENERATION;
                        else if (b.state != (side == 0 ? BUFFER_FULL : BUFFER_FREE))
                            o_code = MST_ERR_BUFFER;
                    end else if (endpoint.buffer_generation != b.generation &&
!(d.events.start != 0 &&
                            {1'b0, endpoint.buffer_generation} > {1'b0, b.generation} &&
                            {1'b0, endpoint.buffer_generation} <= {1'b0, b.generation} + (DG +
                                1)'(2)))
                        o_code = MST_ERR_GENERATION;
                end
            end
        end
    end
endmodule
`default_nettype wire
