`timescale 1ns / 1ps
`default_nettype none

module mst_body #(
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
    input logic i_clk,
    input logic i_rstb,
    input logic i_clock_enable,
    input logic [3:0] i_execution_state,
    input logic [OWNER_ID_WIDTH-1:0] i_owner,
    input logic [KERNEL_ID_WIDTH-1:0] i_kernel,
    input logic i_isolate,
    input logic i_monitor_enable,
    input logic [2:0] i_power_state,
    input logic [6:0] i_counter_index,
    output wire [31:0] o_counter_data,
    input logic [CI-1:0] o_body_context_id,
    input logic [V-1:0] o_body_context_version,
    input logic [IM-1:0] o_body_context_image,
    input logic [N-1:0] o_body_context_word_valid,
    input logic o_body_context_active,
    input logic o_body_validate_valid,
    output wire i_body_validate_ready,
    input logic [CI-1:0] o_body_validate_context_id,
    input logic [V-1:0] o_body_validate_context_version,
    input logic [IM-1:0] o_body_validate_context_image,
    input logic [N-1:0] o_body_validate_word_valid,
    output wire i_body_validate_result_valid,
    input logic o_body_validate_result_ready,
    output wire [CI-1:0] i_body_validate_context_id,
    output wire [V-1:0] i_body_validate_context_version,
    output wire i_body_validate_legal,
    output wire [ER-1:0] i_body_validate_error_code,
    input logic o_body_start,
    input logic o_body_suspend_request,
    input logic o_body_resume,
    input logic o_body_drain_request,
    input logic o_body_flush,
    input logic [NI-1:0] o_body_data_in_valid,
    output wire [NI-1:0] i_body_data_in_ready,
    input logic [NI*D-1:0] o_body_data_in_payload,
    input logic [NI*M-1:0] o_body_data_in_metadata,
    input logic [PI-1:0] o_body_predicate_in_valid,
    output wire [PI-1:0] i_body_predicate_in_ready,
    input logic [PI*P-1:0] o_body_predicate_in_payload,
    input logic [PI*PM-1:0] o_body_predicate_in_metadata,
    input logic [INE-1:0] o_body_event_in_valid,
    output wire [INE-1:0] i_body_event_in_ready,
    input logic [E*INE-1:0] o_body_event_in_payload,
    output wire [NO-1:0] i_body_data_out_valid,
    input logic [NO-1:0] o_body_data_out_ready,
    output wire [NO*D-1:0] i_body_data_out_payload,
    output wire [NO*M-1:0] i_body_data_out_metadata,
    output wire [PO-1:0] i_body_predicate_out_valid,
    input logic [PO-1:0] o_body_predicate_out_ready,
    output wire [PO*P-1:0] i_body_predicate_out_payload,
    output wire [PO*PM-1:0] i_body_predicate_out_metadata,
    output wire [EO-1:0] i_body_event_out_valid,
    input logic [EO-1:0] o_body_event_out_ready,
    output wire [E*EO-1:0] i_body_event_out_payload,
    output wire i_body_busy,
    output wire i_body_idle,
    output wire i_body_safe_point,
    output wire i_body_drain_done,
    output wire i_body_completed,
    output wire [S-1:0] i_body_stall_reasons,
    output wire i_body_error,
    output wire i_body_fatal_error,
    output wire [ER-1:0] i_body_error_code,
    output wire i_body_wakeup_required,
    input wire i_descriptor_valid,
    input wire i_rejection_ready,
    input wire i_region_valid,
    input wire i_region_response_ready,
    input wire i_buffer_valid,
    input wire i_buffer_response_ready,
    input wire i_cancel_valid,
    input wire i_completion_ready,
    input wire i_drain,
    input wire i_flush,
    input wire i_session_end,
    input wire i_error_clear,
    output wire o_descriptor_ready,
    output wire o_descriptor_accepted,
    output wire o_descriptor_rejected,
    output wire o_rejection_valid,
    output wire o_region_ready,
    output wire o_region_response_valid,
    output wire o_region_response_error,
    output wire o_buffer_ready,
    output wire o_buffer_response_valid,
    output wire o_buffer_response_error,
    output wire o_cancel_ready,
    output wire o_cancel_accepted,
    output wire o_cancel_not_found,
    output wire o_completion_valid,
    output wire o_mst_idle,
    output wire o_mst_quiescent,
    output wire o_drain_done,
    output wire o_flush_completed,
    output wire o_mst_error,
    output wire o_mst_fatal_error,
    output wire o_event_rejected,
    input wire [IDW-1:0] i_descriptor_identity,
    input wire [MOW-1:0] i_descriptor_mode,
    input wire [ENW-1:0] i_descriptor_source,
    input wire [ENW-1:0] i_descriptor_destination,
    input wire [FOW-1:0] i_descriptor_format,
    input wire [EVW-1:0] i_descriptor_events,
    input wire [CTW-1:0] i_descriptor_control,
    output wire [7:0] o_rejection_code,
    output wire [7:0] o_region_response_code,
    output wire [7:0] o_buffer_response_code,
    output wire [7:0] o_mst_error_code,
    output wire [IDW-1:0] o_rejection_identity,
    output wire [IDW-1:0] o_completion_identity,
    input wire [IDW-1:0] i_cancel_identity,
    input wire [RI-1:0] i_region_index,
    input wire [RGW-1:0] i_region_record,
    input wire [BU-1:0] i_buffer_index,
    input wire [BUW-1:0] i_buffer_record,
    output wire [EP-1:0] o_execution_epoch,
    output wire [HCI-1:0] o_completion_channel,
    output wire [1:0] o_completion_status,
    output wire [7:0] o_completion_error_code,
    output wire [BC-1:0] o_completion_bytes_read,
    output wire [BC-1:0] o_completion_bytes_written,
    output wire [2*C-1:0] o_completion_elements,
    output wire o_completion_partial,
    output wire o_completion_effects_unknown,
    output wire [H*OC-1:0] o_command_occupancy,
    output wire [NM-1:0] o_scratchpad_read_valid,
    input wire [NM-1:0] i_scratchpad_read_ready,
    output wire [NM*A-1:0] o_scratchpad_read_address,
    output wire [NM*MSZ-1:0] o_scratchpad_read_size_log2,
    output wire [NM*MT-1:0] o_scratchpad_read_tag,
    output wire [NM*IDW-1:0] o_scratchpad_read_identity,
    output wire [NM*RI-1:0] o_scratchpad_read_region_id,
    output wire [NM*DG-1:0] o_scratchpad_read_generation,
    output wire [NM*PR-1:0] o_scratchpad_read_priority,
    input wire [NM-1:0] i_scratchpad_read_response_valid,
    input wire [NM-1:0] i_scratchpad_read_response_error,
    output wire [NM-1:0] o_scratchpad_read_response_ready,
    input wire [NM*MT-1:0] i_scratchpad_read_response_tag,
    input wire [NM*IDW-1:0] i_scratchpad_read_response_identity,
    input wire [NM*MD-1:0] i_scratchpad_read_response_data,
    output wire [NM-1:0] o_scratchpad_write_valid,
    input wire [NM-1:0] i_scratchpad_write_ready,
    output wire [NM*A-1:0] o_scratchpad_write_address,
    output wire [NM*MSZ-1:0] o_scratchpad_write_size_log2,
    output wire [NM*MT-1:0] o_scratchpad_write_tag,
    output wire [NM*IDW-1:0] o_scratchpad_write_identity,
    output wire [NM*RI-1:0] o_scratchpad_write_region_id,
    output wire [NM*DG-1:0] o_scratchpad_write_generation,
    output wire [NM*PR-1:0] o_scratchpad_write_priority,
    output wire [NM*MD-1:0] o_scratchpad_write_data,
    output wire [NM*MY-1:0] o_scratchpad_write_strobe,
    input wire [NM-1:0] i_scratchpad_write_response_valid,
    input wire [NM-1:0] i_scratchpad_write_response_error,
    output wire [NM-1:0] o_scratchpad_write_response_ready,
    input wire [NM*MT-1:0] i_scratchpad_write_response_tag,
    input wire [NM*IDW-1:0] i_scratchpad_write_response_identity,
    input wire [NM*MBW-1:0] i_scratchpad_write_response_bytes_committed,
    input wire [NDI-1:0] i_dma_in_valid,
    output wire [NDI-1:0] o_dma_in_ready,
    input wire [NDI*D-1:0] i_dma_in_data,
    input wire [NDI*M-1:0] i_dma_in_metadata,
    output wire [NDO-1:0] o_dma_out_valid,
    input wire [NDO-1:0] i_dma_out_ready,
    output wire [NDO*D-1:0] o_dma_out_data,
    output wire [NDO*M-1:0] o_dma_out_metadata,
    output wire o_completion_overflow,
    output wire o_completion_saturated,
    input wire [NM-1:0] i_scratchpad_conflict,
    output wire [NI-1:0] o_shell_input_admit,
    input wire [NI-1:0] i_external_input_fire,
    input wire [NI*M-1:0] i_external_input_metadata,
    input wire [NO-1:0] i_external_output_fire,
    input wire [NO*M-1:0] i_external_output_metadata,
    input wire [EO-1:0] i_external_event_fire,
    input wire [EO*E-1:0] i_external_event_payload,
    input wire i_external_events_pending
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
        logic saturated;
        logic overflow;
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

    typedef struct packed {
        logic live;
        logic launched;
        logic worker;
        logic reported;
        logic completion_consumed;
        logic event_consumed;
        logic canceled;
        logic claimed;
        logic fatal;
        logic overflow;
        logic saturated;
        logic [HCI-1:0] parent;
        logic [7:0] code;
        descriptor_t descriptor;
    } active_t;

    typedef struct packed {
        logic launched;
        logic closing;
        logic flushing;
        logic flush_seen;
        logic completed;
        logic automatic_pending;
        logic fatal;
        logic [7:0] code;
        logic [EP-1:0] epoch;
        logic [$clog2(COMPLETION_QUEUE_DEPTH+1)-1:0] completion_reservations;
        logic [$clog2(EVENT_QUEUE_DEPTH+1)-1:0] event_reservations;
        logic flush_completed;
    } mst_body_control_t;

    typedef struct packed {
        logic valid;
        logic reserved;
        logic seen;
        logic [15:0] transmit_sequence;
        logic target;
        logic [J-1:0] target_command;
        logic [DG-1:0] target_generation;
        event_t value;
    } event_state_t;

    typedef struct packed {
        logic valid;
        identity_t identity;
        logic [7:0] code;
    } rejection_t;

    typedef struct packed {
        logic valid;
        logic [CI-1:0] context_id;
        logic [V-1:0] version;
        logic legal;
        logic [7:0] code;
    } validation_t;

    localparam int ACTIVE = $bits(active_t);
    localparam int ES = $bits(event_state_t);
    localparam int COMPLETION = $bits(completion_t);
    localparam int KEY = O + J + DG;
    localparam int COUNTERS = 32 + 8 * H;
    wire run = i_rstb === 1'b1;
    wire active_execution = i_execution_state >= tile_shell_pkg::TILE_ACTIVE &&
        i_execution_state <= tile_shell_pkg::TILE_SYNC_STALL;
    wire executing = active_execution ||
        i_execution_state == tile_shell_pkg::TILE_DRAINING;
    wire accepting = run && active_execution &&
        o_body_context_active && i_clock_enable === 1'b1 && i_isolate === 1'b0 &&
        i_flush === 1'b0 && o_body_flush === 1'b0 && i_drain === 1'b0 &&
        (!control.closing || control.automatic_pending) &&!control.flushing &&!o_mst_fatal_error;
    wire flushing_request = i_flush === 1'b1 || o_body_flush === 1'b1;
    mst_body_control_t control;
    mst_body_control_t control_next;
    wire control_bad;
    wire context_bad;
    context_t context_snapshot;
    context_t context_next;
    context_t live_context;
    context_t validation_context;
    assign live_context = o_body_context_image[0+:CONTEXT_BITS];
    assign validation_context = o_body_validate_context_image[0+:CONTEXT_BITS];
    wire [ACTIVE-1:0] active_records [H];
    logic [ACTIVE-1:0] active_next [H];
    wire [H-1:0] active_bad;
    wire [NR*RGW-1:0] regions;
    logic [NR*RGW-1:0] regions_next;
    wire [NB*BUW-1:0] buffers;
    logic [NB*BUW-1:0] buffers_next;
    wire [NR-1:0] region_bad;
    wire [NB-1:0] buffer_bad;
    wire [ES-1:0] event_states [NE];
    logic [ES-1:0] event_next [NE];
    wire [NE-1:0] event_bad;
    management_response_t region_response;
    management_response_t region_response_next;
    management_response_t buffer_response;
    management_response_t buffer_response_next;
    rejection_t rejection;
    rejection_t rejection_next;
    validation_t validation;
    validation_t validation_next;
    wire region_response_bad;
    wire buffer_response_bad;
    wire rejection_bad;
    wire validation_bad;
    wire integrity_bad = control_bad || context_bad || (|active_bad) || (|region_bad) ||
        (|buffer_bad) || (|event_bad) || region_response_bad || buffer_response_bad ||
        rejection_bad || validation_bad || (|queue_bad) || completion_bad || terminal_event_bad;
    logic all_queues_empty;
    logic all_workers_free;
    logic all_endpoints_idle;
    wire no_terminal_records = completion_count == 0 && terminal_event_count == 0 &&
!rejection.valid &&!region_response.valid &&!buffer_response.valid;
    wire quiescent = all_queues_empty && all_workers_free && no_terminal_records &&
!i_external_events_pending;
    wire programming = run && quiescent &&!control.flushing &&!o_mst_fatal_error;
    wire candidate_auto = control.automatic_pending && accepting;
    descriptor_t incoming;
    descriptor_t automatic_descriptor;
    logic incoming_duplicate;
    wire [7:0] incoming_code;
    wire [7:0] automatic_code;
    logic [7:0] admission_code;
    logic [HCI-1:0] incoming_channel;
    wire incoming_valid = candidate_auto || i_descriptor_valid === 1'b1;
    wire incoming_fire = incoming_valid && (candidate_auto ? automatic_ready : o_descriptor_ready);
    wire automatic_ready;
    wire [KEY-1:0] incoming_key = {O'(incoming.identity.owner), J'(incoming.identity.command),
        DG'(incoming.identity.generation)};
    identity_t cancel_identity;
    assign cancel_identity = i_cancel_identity;
    wire [KEY-1:0] cancel_key = {cancel_identity.owner, cancel_identity.command,
        cancel_identity.generation};
    wire cancel_fire = i_cancel_valid === 1'b1 && o_cancel_ready;
    logic cancel_found;
    wire [H-1:0] queue_valid;
    wire [H-1:0] queue_ready;
    wire [H-1:0] queue_duplicate;
    wire [H-1:0] queue_canceled;
    wire [H-1:0] queue_cancel_match;
    wire [H-1:0] queue_bad;
    logic [H-1:0] queue_pop;
    wire [DESC-1:0] queue_data [H];
    wire [H*OC-1:0] queue_count;
    wire [H-1:0] head_event_satisfied;
    wire [H-1:0] head_event_error;
    wire [NE-1:0] head_events [H];
    wire [7:0] head_code [H];
    logic [H-1:0] start_candidates;
    wire start_valid;
    wire [HCI-1:0] start_channel;
    wire start_arbiter_bad;
    wire start_fire;
    wire [H-1:0] terminal_candidates;
    wire terminal_valid;
    wire [HCI-1:0] terminal_channel;
    wire terminal_arbiter_bad;
    wire terminal_fire;
    completion_t terminal_record;
    event_t terminal_event_record;
    wire [COMPLETION-1:0] completion_packet;
    completion_t completion_output;
    assign completion_output = completion_packet;
    wire completion_input_ready;
    wire [31:0] completion_count;
    wire completion_bad;
    wire terminal_event_input_ready;
    wire terminal_event_valid;
    wire [E-1:0] terminal_event_packet;
    wire [31:0] terminal_event_count;
    wire terminal_event_bad;
    wire completion_fire = o_completion_valid && i_completion_ready === 1'b1;
    wire terminal_event_fire = terminal_event_valid && o_body_event_out_ready[0] === 1'b1;
    logic [H-1:0] worker_launch;
    logic [H-1:0] worker_release;
    logic [H-1:0] worker_cancel;
    logic [H-1:0] copy_worker;
    logic [DESC-1:0] worker_descriptor [H];
    wire [H-1:0] worker_done;
    wire [H-1:0] worker_stopping;
    wire [H-1:0] worker_fatal;
    wire [7:0] worker_code [H];
    wire [BC-1:0] worker_bytes_read [H];
    wire [BC-1:0] worker_bytes_written [H];
    wire [2*C-1:0] worker_elements [H];
    wire [H-1:0] worker_progress;
    wire [H-1:0] worker_overflow;
    wire [H-1:0] worker_saturated;
    wire [H-1:0] worker_started;
    wire [H-1:0] worker_request_accepted;
    wire [H-1:0] worker_response_accepted;
    wire [H-1:0] worker_input_accepted;
    wire [H-1:0] worker_output_accepted;
    wire [31:0] worker_outstanding [H];
    wire [H-1:0] source_valid;
    wire [H-1:0] source_ready;
    wire [H-1:0] source_admit;
    logic [D-1:0] source_data [H];
    logic [M-1:0] source_metadata [H];
    logic [H-1:0] source_selected_valid;
    wire [H-1:0] sink_valid;
    logic [H-1:0] sink_ready;
    wire [D-1:0] sink_data [H];
    wire [M-1:0] sink_metadata [H];
    logic [H-1:0] source_commit;
    logic [H-1:0] sink_commit;
    logic [SY-1:0] source_commit_keep [H];
    logic [SY-1:0] sink_commit_keep [H];
    wire [H-1:0] copy_valid;
    logic [H-1:0] copy_ready;
    wire [ED-1:0] copy_data [H];
    wire [H-1:0] copy_error;
    logic [H-1:0] copy_input_valid;
    wire [H-1:0] copy_input_ready;
    logic [ED-1:0] copy_input_data [H];
    logic [H-1:0] copy_input_error;
    wire [H-1:0] memory_valid;
    logic [H-1:0] memory_ready;
    wire [A-1:0] memory_address [H];
    wire [MSZ-1:0] memory_size [H];
    wire [MD-1:0] memory_data [H];
    wire [MY-1:0] memory_strobe [H];
    wire [AT-1:0] memory_tag [H];
    logic [H-1:0] response_valid;
    wire [H-1:0] response_ready;
    logic [AT-1:0] response_tag [H];
    logic [IDW-1:0] response_identity [H];
    logic [MD-1:0] response_data [H];
    logic [H-1:0] response_error;
    logic [MBW-1:0] response_committed [H];
    logic response_route_error;
    logic [NI-1:0] shell_input_admit;
    logic [NI-1:0] body_input_ready;
    logic [NO-1:0] body_output_valid;
    logic [NO*D-1:0] body_output_data;
    logic [NO*M-1:0] body_output_metadata;
    logic [NDI-1:0] dma_input_ready;
    logic [NDO-1:0] dma_output_valid;
    logic [NDO*D-1:0] dma_output_data;
    logic [NDO*M-1:0] dma_output_metadata;
    logic [7:0] event_rejected;
    logic [5:0] pulses;
    wire [5:0] pulse_outputs;
    wire [COUNTERS*32-1:0] counters;
    wire [(H+3)*32-1:0] peaks;
    logic [COUNTERS*32-1:0] increments;
    logic [(H+3)*32-1:0] occupancies;

    always @* begin
        automatic_descriptor = context_snapshot.descriptor;
        automatic_descriptor.identity.owner = i_owner;
        automatic_descriptor.identity.kernel = i_kernel;
        automatic_descriptor.identity.package_id = context_snapshot.package_id;
        automatic_descriptor.identity.allocation = context_snapshot.allocation;
        automatic_descriptor.identity.context_id = o_body_context_id;
        automatic_descriptor.identity.version = o_body_context_version;
        automatic_descriptor.identity.epoch = control.epoch;
        incoming = candidate_auto ? automatic_descriptor :
            {i_descriptor_control, i_descriptor_events, i_descriptor_format,
                i_descriptor_destination, i_descriptor_source, i_descriptor_mode,
                    i_descriptor_identity};
        incoming_channel = load_class(incoming.mode.transfer) ?
            HCI'(incoming.mode.load_channel) : HCI'(NL + int'(incoming.mode.store_channel));
        incoming_duplicate = |queue_duplicate;
        cancel_found = |queue_cancel_match;
        all_queues_empty = (|queue_valid) == 0 && queue_count == 0;
        all_workers_free = 1'b1;
        all_endpoints_idle = 1'b1;

        for (int h = 0; h < H; h++) begin
            active_t a;
            a = active_records[h];
            all_workers_free &=!a.live;
            all_endpoints_idle &=!a.live ||!a.launched || worker_done[h];

            if (a.live && a.descriptor.identity.owner == incoming.identity.owner &&
                a.descriptor.identity.command == incoming.identity.command &&
                a.descriptor.identity.generation == incoming.identity.generation)
                incoming_duplicate = 1'b1;

            if (a.live &&!a.reported && a.descriptor.control.cancelable &&
                a.descriptor.identity === cancel_identity) cancel_found = 1'b1;
        end

        admission_code = candidate_auto ? automatic_code : incoming_code;

        if (incoming_duplicate && admission_code == 0) admission_code = MST_ERR_DUPLICATE;
    end

    assign o_descriptor_ready = accepting &&!candidate_auto &&
        (admission_code != 0 ?!rejection.valid || i_rejection_ready === 1'b1 :
            int'(incoming_channel) < H && queue_ready[incoming_channel]);
    assign automatic_ready = accepting &&
        (admission_code != 0 ?!rejection.valid || i_rejection_ready === 1'b1 :
            int'(incoming_channel) < H && queue_ready[incoming_channel]);
    assign o_descriptor_accepted = pulse_outputs[0];
    assign o_descriptor_rejected = pulse_outputs[1];
    assign o_cancel_accepted = pulse_outputs[2];
    assign o_cancel_not_found = pulse_outputs[3];
    assign o_event_rejected = pulse_outputs[4];
    assign o_flush_completed = run && control.flush_completed;
    assign o_execution_epoch = control.epoch;
    assign o_rejection_valid = run && rejection.valid;
    assign o_rejection_code = rejection.code;
    assign o_rejection_identity = rejection.identity;
    assign o_region_ready = programming && (!region_response.valid || i_region_response_ready ===
        1'b1);
    assign o_region_response_valid = run && region_response.valid;
    assign o_region_response_error = region_response.error;
    assign o_region_response_code = region_response.code;
    assign o_buffer_ready = programming && (!buffer_response.valid || i_buffer_response_ready ===
        1'b1);
    assign o_buffer_response_valid = run && buffer_response.valid;
    assign o_buffer_response_error = buffer_response.error;
    assign o_buffer_response_code = buffer_response.code;
    assign o_cancel_ready = run && SUPPORT_CANCELLATION == 1 &&!control.flushing &&
        (^i_cancel_identity !== 1'bx) && cancel_identity.owner == i_owner &&
        cancel_identity.kernel == i_kernel && cancel_identity.package_id ==
            context_snapshot.package_id &&
        cancel_identity.allocation == context_snapshot.allocation &&
        cancel_identity.context_id == o_body_context_id &&
        cancel_identity.version == o_body_context_version && cancel_identity.epoch == control.epoch;
    assign o_command_occupancy = queue_count;
    assign o_completion_identity = completion_output.identity;
    assign o_completion_channel = completion_output.channel;
    assign o_completion_status = completion_output.status;
    assign o_completion_error_code = completion_output.code;
    assign o_completion_bytes_read = completion_output.bytes_read;
    assign o_completion_bytes_written = completion_output.bytes_written;
    assign o_completion_elements = completion_output.elements;
    assign o_completion_partial = completion_output.partial;
    assign o_completion_effects_unknown = completion_output.effects_unknown;
    assign o_completion_overflow = completion_output.overflow;
    assign o_completion_saturated = completion_output.saturated;
    assign o_mst_error = control.code != 0 || o_mst_fatal_error;
    assign o_mst_fatal_error = run && (control.fatal || integrity_bad || (|worker_fatal) ||
        start_arbiter_bad || terminal_arbiter_bad || response_route_error);
    assign o_mst_error_code = integrity_bad ? MST_ERR_INTEGRITY :
        response_route_error ? MST_ERR_TAG : control.code;
    assign o_mst_idle = run && all_endpoints_idle &&!o_mst_fatal_error;
    assign o_mst_quiescent = run && quiescent &&!control.flushing &&!o_mst_fatal_error;
    assign o_drain_done = o_mst_quiescent;
    assign i_body_idle = o_mst_quiescent;
    assign i_body_busy =!quiescent || control.flushing;
    assign i_body_safe_point = all_workers_free;
    assign i_body_drain_done = o_drain_done;
    assign i_body_completed = control.completed;
    assign i_body_error = o_mst_fatal_error;
    assign i_body_fatal_error = o_mst_fatal_error;
    assign i_body_error_code = o_mst_error_code;
    assign i_body_wakeup_required = (|o_body_event_in_valid) ||
        ((|queue_valid) && executing &&!control.flushing);
    // The shell's generic stream-stall gating cannot observe memory response
    // ports. Keep the body requested while commands own physical obligations.
    assign i_body_stall_reasons = (!all_queues_empty ||!all_workers_free ||
        i_descriptor_valid === 1'b1 || control.automatic_pending) ? '0 : S'(128);
    assign i_body_predicate_in_ready = {PI{1'b1}};
    assign i_body_predicate_out_valid = '0;
    assign i_body_predicate_out_payload = '0;
    assign i_body_predicate_out_metadata = '0;
    assign i_body_validate_ready = run && (!validation.valid || o_body_validate_result_ready ===
        1'b1);
    assign i_body_validate_result_valid = run && validation.valid;
    assign i_body_validate_context_id = validation.context_id;
    assign i_body_validate_context_version = validation.version;
    assign i_body_validate_legal = validation.legal;
    assign i_body_validate_error_code = validation.code;
    assign i_body_event_out_valid = {{(EO - 1){1'b0}}, terminal_event_valid};
    assign i_body_event_out_payload = {{((EO - 1) * E){1'b0}}, terminal_event_packet};
    assign o_shell_input_admit = shell_input_admit;
    assign i_body_data_in_ready = body_input_ready;
    assign i_body_data_out_valid = body_output_valid;
    assign i_body_data_out_payload = body_output_data;
    assign i_body_data_out_metadata = body_output_metadata;
    assign o_dma_in_ready = dma_input_ready;
    assign o_dma_out_valid = dma_output_valid;
    assign o_dma_out_data = dma_output_data;
    assign o_dma_out_metadata = dma_output_metadata;
    assign o_counter_data = int'(i_counter_index) >= 112 &&
        int'(i_counter_index) < 112 + H + 3 ? peaks[(i_counter_index-112)*32+:32] :
        int'(i_counter_index) < COUNTERS ? counters[i_counter_index*32+:32] : 32'b0;
    wire validating_context = o_body_validate_valid && i_body_validate_ready;
    descriptor_t validation_descriptor;

    always @* begin
        validation_descriptor = validation_context.descriptor;
        validation_descriptor.identity.owner = i_owner;
        validation_descriptor.identity.kernel = i_kernel;
        validation_descriptor.identity.package_id = validation_context.package_id;
        validation_descriptor.identity.allocation = validation_context.allocation;
        validation_descriptor.identity.context_id = o_body_validate_context_id;
        validation_descriptor.identity.version = o_body_validate_context_version;
        validation_descriptor.identity.epoch = control.epoch;
    end

    mst_validate #(
        .TILE_ID(TILE_ID),
        .ADDR_WIDTH(ADDR_WIDTH),
        .SHELL_DATA_WIDTH(SHELL_DATA_WIDTH),
        .MEMORY_DATA_WIDTH(MEMORY_DATA_WIDTH),
        .NUM_STREAM_INPUTS(NUM_STREAM_INPUTS),
        .NUM_STREAM_OUTPUTS(NUM_STREAM_OUTPUTS),
        .NUM_LOAD_CHANNELS(NUM_LOAD_CHANNELS),
        .NUM_STORE_CHANNELS(NUM_STORE_CHANNELS),
        .NUM_SCRATCHPAD_CLIENTS(NUM_SCRATCHPAD_CLIENTS),
        .NUM_DMA_INGRESS_CHANNELS(NUM_DMA_INGRESS_CHANNELS),
        .NUM_DMA_EGRESS_CHANNELS(NUM_DMA_EGRESS_CHANNELS),
        .CONTEXT_DEPTH(CONTEXT_DEPTH),
        .CONFIG_WORD_COUNT(CONFIG_WORD_COUNT),
        .COMMAND_QUEUE_DEPTH(COMMAND_QUEUE_DEPTH),
        .READ_DATA_FIFO_DEPTH(READ_DATA_FIFO_DEPTH),
        .WRITE_DATA_FIFO_DEPTH(WRITE_DATA_FIFO_DEPTH),
        .COMPLETION_QUEUE_DEPTH(COMPLETION_QUEUE_DEPTH),
        .EVENT_QUEUE_DEPTH(EVENT_QUEUE_DEPTH),
        .MAX_OUTSTANDING_READS(MAX_OUTSTANDING_READS),
        .MAX_OUTSTANDING_WRITES(MAX_OUTSTANDING_WRITES),
        .COUNT_WIDTH(COUNT_WIDTH),
        .MAX_ELEMENT_BYTES(MAX_ELEMENT_BYTES),
        .NUM_PROTECTION_REGIONS(NUM_PROTECTION_REGIONS),
        .NUM_BUFFER_ROLES(NUM_BUFFER_ROLES),
        .NUM_EVENTS(NUM_EVENTS),
        .OWNER_ID_WIDTH(OWNER_ID_WIDTH),
        .KERNEL_ID_WIDTH(KERNEL_ID_WIDTH),
        .PACKAGE_ID_WIDTH(PACKAGE_ID_WIDTH),
        .CONTEXT_VERSION_WIDTH(CONTEXT_VERSION_WIDTH),
        .COMMAND_ID_WIDTH(COMMAND_ID_WIDTH),
        .DESCRIPTOR_GENERATION_WIDTH(DESCRIPTOR_GENERATION_WIDTH),
        .ALLOCATION_GENERATION_WIDTH(ALLOCATION_GENERATION_WIDTH),
        .EXECUTION_EPOCH_WIDTH(EXECUTION_EPOCH_WIDTH),
        .SPACE_ID_WIDTH(SPACE_ID_WIDTH),
        .STREAM_ID_WIDTH(STREAM_ID_WIDTH),
        .REGION_ID_WIDTH(REGION_ID_WIDTH),
        .BUFFER_ID_WIDTH(BUFFER_ID_WIDTH),
        .DATATYPE_WIDTH(DATATYPE_WIDTH),
        .PRIORITY_WIDTH(PRIORITY_WIDTH),
        .TRANSFER_TIMEOUT_CYCLES(TRANSFER_TIMEOUT_CYCLES),
        .CANCEL_TIMEOUT_CYCLES(CANCEL_TIMEOUT_CYCLES),
        .SUPPORT_2D(SUPPORT_2D),
        .SUPPORT_3D(SUPPORT_3D),
        .SUPPORT_CIRCULAR(SUPPORT_CIRCULAR),
        .SUPPORT_GATHER(SUPPORT_GATHER),
        .SUPPORT_SCATTER(SUPPORT_SCATTER),
        .SUPPORT_ATOMICS(SUPPORT_ATOMICS),
        .SUPPORT_LOCAL_COPY(SUPPORT_LOCAL_COPY),
        .SUPPORT_UNALIGNED(SUPPORT_UNALIGNED),
        .SUPPORT_WIDTH_CONVERSION(SUPPORT_WIDTH_CONVERSION),
        .SUPPORT_ELEMENT_CONVERSION(SUPPORT_ELEMENT_CONVERSION),
        .SUPPORT_EVENT_START(SUPPORT_EVENT_START),
        .SUPPORT_COMMAND_CHAINING(SUPPORT_COMMAND_CHAINING),
        .SUPPORT_DOUBLE_BUFFER(SUPPORT_DOUBLE_BUFFER),
        .SUPPORT_MULTICAST(SUPPORT_MULTICAST),
        .SUPPORT_DIRECT_MEMORY_PROXY(SUPPORT_DIRECT_MEMORY_PROXY),
        .SUPPORT_CANCELLATION(SUPPORT_CANCELLATION),
        .COMMAND_PROTECTION(COMMAND_PROTECTION),
        .FIFO_PROTECTION(FIFO_PROTECTION),
        .CONTROL_PROTECTION(CONTROL_PROTECTION),
        .ASYNC_SCRATCHPAD_CLOCK(ASYNC_SCRATCHPAD_CLOCK),
        .ASYNC_DMA_CLOCK(ASYNC_DMA_CLOCK),
        .ASYNC_RESET(ASYNC_RESET),
        .TILE_ID_WIDTH(TILE_ID_WIDTH),
        .ARCH_VERSION_WIDTH(ARCH_VERSION_WIDTH),
        .CAPABILITY_ID_WIDTH(CAPABILITY_ID_WIDTH),
        .INPUT_BUFFER_DEPTH(INPUT_BUFFER_DEPTH),
        .OUTPUT_BUFFER_DEPTH(OUTPUT_BUFFER_DEPTH),
        .PREDICATE_WIDTH(PREDICATE_WIDTH),
        .PREDICATE_METADATA_WIDTH(PREDICATE_METADATA_WIDTH),
        .PREDICATE_INPUT_PORTS(PREDICATE_INPUT_PORTS),
        .PREDICATE_OUTPUT_PORTS(PREDICATE_OUTPUT_PORTS),
        .EVENT_INPUT_PORTS(EVENT_INPUT_PORTS),
        .EVENT_OUTPUT_PORTS(EVENT_OUTPUT_PORTS),
        .CONFIG_DATA_WIDTH(CONFIG_DATA_WIDTH),
        .CONTEXT_CHECKSUM_WIDTH(CONTEXT_CHECKSUM_WIDTH),
        .SUPPORT_CONTEXT_CHECKSUM(SUPPORT_CONTEXT_CHECKSUM),
        .CONFIG_ASYNC(CONFIG_ASYNC),
        .CONFIG_QUEUE_DEPTH(CONFIG_QUEUE_DEPTH),
        .RUNTIME_TAG_WIDTH(RUNTIME_TAG_WIDTH),
        .STALL_REASON_WIDTH(STALL_REASON_WIDTH),
        .ERROR_CODE_WIDTH(ERROR_CODE_WIDTH),
        .TRACE_WIDTH(TRACE_WIDTH),
        .SUPPORT_TRACE(SUPPORT_TRACE),
        .SUPPORT_RETENTION(SUPPORT_RETENTION),
        .SUPPORT_POWER_OFF(SUPPORT_POWER_OFF),
        .CONTEXT_PROTECTION(CONTEXT_PROTECTION),
        .EVENT_WIDTH(EVENT_WIDTH),
        .DATA_METADATA_WIDTH(DATA_METADATA_WIDTH),
        .INPUT_ELASTIC_MASK(INPUT_ELASTIC_MASK),
        .OUTPUT_ELASTIC_MASK(OUTPUT_ELASTIC_MASK)
    ) u_incoming_validation (
        .i_enable(validating_context ? validation_context.automatic_command :
            i_descriptor_valid === 1'b1),
            .i_dynamic(1'b0),
        .i_descriptor(validating_context ? DESC'(validation_descriptor) :
            {i_descriptor_control, i_descriptor_events, i_descriptor_format,
                i_descriptor_destination, i_descriptor_source, i_descriptor_mode,
                    i_descriptor_identity}),
        .i_owner(i_owner),
        .i_kernel(i_kernel),
        .i_package(validating_context ? PK'(validation_context.package_id) :
            PK'(context_snapshot.package_id)),
        .i_allocation(validating_context ? AL'(validation_context.allocation) :
            AL'(context_snapshot.allocation)),
        .i_context(validating_context ? o_body_validate_context_id : o_body_context_id),
        .i_version(validating_context ? o_body_validate_context_version : o_body_context_version),
        .i_epoch(control.epoch),
        .i_load_mask(validating_context ? NL'(validation_context.loads) :
            NL'(context_snapshot.loads)),
        .i_store_mask(validating_context ? NS'(validation_context.stores) :
            NS'(context_snapshot.stores)),
        .i_region_mask(validating_context ? NR'(validation_context.regions) :
            NR'(context_snapshot.regions)),
        .i_regions(regions),
        .i_buffers(buffers),
        .o_code(incoming_code),
        .o_source_low(),
        .o_source_limit(),
        .o_destination_low(),
        .o_destination_limit()
    );

    mst_validate #(
        .TILE_ID(TILE_ID),
        .ADDR_WIDTH(ADDR_WIDTH),
        .SHELL_DATA_WIDTH(SHELL_DATA_WIDTH),
        .MEMORY_DATA_WIDTH(MEMORY_DATA_WIDTH),
        .NUM_STREAM_INPUTS(NUM_STREAM_INPUTS),
        .NUM_STREAM_OUTPUTS(NUM_STREAM_OUTPUTS),
        .NUM_LOAD_CHANNELS(NUM_LOAD_CHANNELS),
        .NUM_STORE_CHANNELS(NUM_STORE_CHANNELS),
        .NUM_SCRATCHPAD_CLIENTS(NUM_SCRATCHPAD_CLIENTS),
        .NUM_DMA_INGRESS_CHANNELS(NUM_DMA_INGRESS_CHANNELS),
        .NUM_DMA_EGRESS_CHANNELS(NUM_DMA_EGRESS_CHANNELS),
        .CONTEXT_DEPTH(CONTEXT_DEPTH),
        .CONFIG_WORD_COUNT(CONFIG_WORD_COUNT),
        .COMMAND_QUEUE_DEPTH(COMMAND_QUEUE_DEPTH),
        .READ_DATA_FIFO_DEPTH(READ_DATA_FIFO_DEPTH),
        .WRITE_DATA_FIFO_DEPTH(WRITE_DATA_FIFO_DEPTH),
        .COMPLETION_QUEUE_DEPTH(COMPLETION_QUEUE_DEPTH),
        .EVENT_QUEUE_DEPTH(EVENT_QUEUE_DEPTH),
        .MAX_OUTSTANDING_READS(MAX_OUTSTANDING_READS),
        .MAX_OUTSTANDING_WRITES(MAX_OUTSTANDING_WRITES),
        .COUNT_WIDTH(COUNT_WIDTH),
        .MAX_ELEMENT_BYTES(MAX_ELEMENT_BYTES),
        .NUM_PROTECTION_REGIONS(NUM_PROTECTION_REGIONS),
        .NUM_BUFFER_ROLES(NUM_BUFFER_ROLES),
        .NUM_EVENTS(NUM_EVENTS),
        .OWNER_ID_WIDTH(OWNER_ID_WIDTH),
        .KERNEL_ID_WIDTH(KERNEL_ID_WIDTH),
        .PACKAGE_ID_WIDTH(PACKAGE_ID_WIDTH),
        .CONTEXT_VERSION_WIDTH(CONTEXT_VERSION_WIDTH),
        .COMMAND_ID_WIDTH(COMMAND_ID_WIDTH),
        .DESCRIPTOR_GENERATION_WIDTH(DESCRIPTOR_GENERATION_WIDTH),
        .ALLOCATION_GENERATION_WIDTH(ALLOCATION_GENERATION_WIDTH),
        .EXECUTION_EPOCH_WIDTH(EXECUTION_EPOCH_WIDTH),
        .SPACE_ID_WIDTH(SPACE_ID_WIDTH),
        .STREAM_ID_WIDTH(STREAM_ID_WIDTH),
        .REGION_ID_WIDTH(REGION_ID_WIDTH),
        .BUFFER_ID_WIDTH(BUFFER_ID_WIDTH),
        .DATATYPE_WIDTH(DATATYPE_WIDTH),
        .PRIORITY_WIDTH(PRIORITY_WIDTH),
        .TRANSFER_TIMEOUT_CYCLES(TRANSFER_TIMEOUT_CYCLES),
        .CANCEL_TIMEOUT_CYCLES(CANCEL_TIMEOUT_CYCLES),
        .SUPPORT_2D(SUPPORT_2D),
        .SUPPORT_3D(SUPPORT_3D),
        .SUPPORT_CIRCULAR(SUPPORT_CIRCULAR),
        .SUPPORT_GATHER(SUPPORT_GATHER),
        .SUPPORT_SCATTER(SUPPORT_SCATTER),
        .SUPPORT_ATOMICS(SUPPORT_ATOMICS),
        .SUPPORT_LOCAL_COPY(SUPPORT_LOCAL_COPY),
        .SUPPORT_UNALIGNED(SUPPORT_UNALIGNED),
        .SUPPORT_WIDTH_CONVERSION(SUPPORT_WIDTH_CONVERSION),
        .SUPPORT_ELEMENT_CONVERSION(SUPPORT_ELEMENT_CONVERSION),
        .SUPPORT_EVENT_START(SUPPORT_EVENT_START),
        .SUPPORT_COMMAND_CHAINING(SUPPORT_COMMAND_CHAINING),
        .SUPPORT_DOUBLE_BUFFER(SUPPORT_DOUBLE_BUFFER),
        .SUPPORT_MULTICAST(SUPPORT_MULTICAST),
        .SUPPORT_DIRECT_MEMORY_PROXY(SUPPORT_DIRECT_MEMORY_PROXY),
        .SUPPORT_CANCELLATION(SUPPORT_CANCELLATION),
        .COMMAND_PROTECTION(COMMAND_PROTECTION),
        .FIFO_PROTECTION(FIFO_PROTECTION),
        .CONTROL_PROTECTION(CONTROL_PROTECTION),
        .ASYNC_SCRATCHPAD_CLOCK(ASYNC_SCRATCHPAD_CLOCK),
        .ASYNC_DMA_CLOCK(ASYNC_DMA_CLOCK),
        .ASYNC_RESET(ASYNC_RESET),
        .TILE_ID_WIDTH(TILE_ID_WIDTH),
        .ARCH_VERSION_WIDTH(ARCH_VERSION_WIDTH),
        .CAPABILITY_ID_WIDTH(CAPABILITY_ID_WIDTH),
        .INPUT_BUFFER_DEPTH(INPUT_BUFFER_DEPTH),
        .OUTPUT_BUFFER_DEPTH(OUTPUT_BUFFER_DEPTH),
        .PREDICATE_WIDTH(PREDICATE_WIDTH),
        .PREDICATE_METADATA_WIDTH(PREDICATE_METADATA_WIDTH),
        .PREDICATE_INPUT_PORTS(PREDICATE_INPUT_PORTS),
        .PREDICATE_OUTPUT_PORTS(PREDICATE_OUTPUT_PORTS),
        .EVENT_INPUT_PORTS(EVENT_INPUT_PORTS),
        .EVENT_OUTPUT_PORTS(EVENT_OUTPUT_PORTS),
        .CONFIG_DATA_WIDTH(CONFIG_DATA_WIDTH),
        .CONTEXT_CHECKSUM_WIDTH(CONTEXT_CHECKSUM_WIDTH),
        .SUPPORT_CONTEXT_CHECKSUM(SUPPORT_CONTEXT_CHECKSUM),
        .CONFIG_ASYNC(CONFIG_ASYNC),
        .CONFIG_QUEUE_DEPTH(CONFIG_QUEUE_DEPTH),
        .RUNTIME_TAG_WIDTH(RUNTIME_TAG_WIDTH),
        .STALL_REASON_WIDTH(STALL_REASON_WIDTH),
        .ERROR_CODE_WIDTH(ERROR_CODE_WIDTH),
        .TRACE_WIDTH(TRACE_WIDTH),
        .SUPPORT_TRACE(SUPPORT_TRACE),
        .SUPPORT_RETENTION(SUPPORT_RETENTION),
        .SUPPORT_POWER_OFF(SUPPORT_POWER_OFF),
        .CONTEXT_PROTECTION(CONTEXT_PROTECTION),
        .EVENT_WIDTH(EVENT_WIDTH),
        .DATA_METADATA_WIDTH(DATA_METADATA_WIDTH),
        .INPUT_ELASTIC_MASK(INPUT_ELASTIC_MASK),
        .OUTPUT_ELASTIC_MASK(OUTPUT_ELASTIC_MASK)
    ) u_automatic_validation (
        .i_enable(candidate_auto),
        .i_dynamic(1'b0),
        .i_descriptor(automatic_descriptor),
        .i_owner(i_owner),
        .i_kernel(i_kernel),
        .i_package(context_snapshot.package_id),
        .i_allocation(context_snapshot.allocation),
        .i_context(o_body_context_id),
        .i_version(o_body_context_version),
        .i_epoch(control.epoch),
        .i_load_mask(context_snapshot.loads),
        .i_store_mask(context_snapshot.stores),
        .i_region_mask(context_snapshot.regions),
        .i_regions(regions),
        .i_buffers(buffers),
        .o_code(automatic_code),
        .o_source_low(),
        .o_source_limit(),
        .o_destination_low(),
        .o_destination_limit()
    );

    for (genvar h = 0; h < H; h++) begin : g_channel
        descriptor_t head;
        active_t active;
        assign head = queue_data[h];
        assign active = active_records[h];

        mst_command_queue #(
            .WIDTH(DESC),
            .KEY_WIDTH(KEY),
            .DEPTH(Q),
            .PROTECTION(COMMAND_PROTECTION),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_commands (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_valid(incoming_fire && admission_code == 0 && incoming_channel == HCI'(h)),
            .o_ready(queue_ready[h]),
            .i_data(incoming),
            .i_key(incoming_key),
                .i_cancelable(1'(incoming.control.cancelable)),
            .i_query_key(incoming_key),
            .o_duplicate(queue_duplicate[h]),
            .i_cancel(cancel_fire),
            .i_cancel_key(cancel_key),
                .o_cancel_match(queue_cancel_match[h]),
            .o_valid(queue_valid[h]),
            .i_ready(queue_pop[h]),
            .o_data(queue_data[h]),
            .o_canceled(queue_canceled[h]),
            .o_bad(queue_bad[h]),
            .o_count(queue_count[h*OC+:OC])
        );

        mst_validate #(
        .TILE_ID(TILE_ID),
        .ADDR_WIDTH(ADDR_WIDTH),
        .SHELL_DATA_WIDTH(SHELL_DATA_WIDTH),
        .MEMORY_DATA_WIDTH(MEMORY_DATA_WIDTH),
        .NUM_STREAM_INPUTS(NUM_STREAM_INPUTS),
        .NUM_STREAM_OUTPUTS(NUM_STREAM_OUTPUTS),
        .NUM_LOAD_CHANNELS(NUM_LOAD_CHANNELS),
        .NUM_STORE_CHANNELS(NUM_STORE_CHANNELS),
        .NUM_SCRATCHPAD_CLIENTS(NUM_SCRATCHPAD_CLIENTS),
        .NUM_DMA_INGRESS_CHANNELS(NUM_DMA_INGRESS_CHANNELS),
        .NUM_DMA_EGRESS_CHANNELS(NUM_DMA_EGRESS_CHANNELS),
        .CONTEXT_DEPTH(CONTEXT_DEPTH),
        .CONFIG_WORD_COUNT(CONFIG_WORD_COUNT),
        .COMMAND_QUEUE_DEPTH(COMMAND_QUEUE_DEPTH),
        .READ_DATA_FIFO_DEPTH(READ_DATA_FIFO_DEPTH),
        .WRITE_DATA_FIFO_DEPTH(WRITE_DATA_FIFO_DEPTH),
        .COMPLETION_QUEUE_DEPTH(COMPLETION_QUEUE_DEPTH),
        .EVENT_QUEUE_DEPTH(EVENT_QUEUE_DEPTH),
        .MAX_OUTSTANDING_READS(MAX_OUTSTANDING_READS),
        .MAX_OUTSTANDING_WRITES(MAX_OUTSTANDING_WRITES),
        .COUNT_WIDTH(COUNT_WIDTH),
        .MAX_ELEMENT_BYTES(MAX_ELEMENT_BYTES),
        .NUM_PROTECTION_REGIONS(NUM_PROTECTION_REGIONS),
        .NUM_BUFFER_ROLES(NUM_BUFFER_ROLES),
        .NUM_EVENTS(NUM_EVENTS),
        .OWNER_ID_WIDTH(OWNER_ID_WIDTH),
        .KERNEL_ID_WIDTH(KERNEL_ID_WIDTH),
        .PACKAGE_ID_WIDTH(PACKAGE_ID_WIDTH),
        .CONTEXT_VERSION_WIDTH(CONTEXT_VERSION_WIDTH),
        .COMMAND_ID_WIDTH(COMMAND_ID_WIDTH),
        .DESCRIPTOR_GENERATION_WIDTH(DESCRIPTOR_GENERATION_WIDTH),
        .ALLOCATION_GENERATION_WIDTH(ALLOCATION_GENERATION_WIDTH),
        .EXECUTION_EPOCH_WIDTH(EXECUTION_EPOCH_WIDTH),
        .SPACE_ID_WIDTH(SPACE_ID_WIDTH),
        .STREAM_ID_WIDTH(STREAM_ID_WIDTH),
        .REGION_ID_WIDTH(REGION_ID_WIDTH),
        .BUFFER_ID_WIDTH(BUFFER_ID_WIDTH),
        .DATATYPE_WIDTH(DATATYPE_WIDTH),
        .PRIORITY_WIDTH(PRIORITY_WIDTH),
        .TRANSFER_TIMEOUT_CYCLES(TRANSFER_TIMEOUT_CYCLES),
        .CANCEL_TIMEOUT_CYCLES(CANCEL_TIMEOUT_CYCLES),
        .SUPPORT_2D(SUPPORT_2D),
        .SUPPORT_3D(SUPPORT_3D),
        .SUPPORT_CIRCULAR(SUPPORT_CIRCULAR),
        .SUPPORT_GATHER(SUPPORT_GATHER),
        .SUPPORT_SCATTER(SUPPORT_SCATTER),
        .SUPPORT_ATOMICS(SUPPORT_ATOMICS),
        .SUPPORT_LOCAL_COPY(SUPPORT_LOCAL_COPY),
        .SUPPORT_UNALIGNED(SUPPORT_UNALIGNED),
        .SUPPORT_WIDTH_CONVERSION(SUPPORT_WIDTH_CONVERSION),
        .SUPPORT_ELEMENT_CONVERSION(SUPPORT_ELEMENT_CONVERSION),
        .SUPPORT_EVENT_START(SUPPORT_EVENT_START),
        .SUPPORT_COMMAND_CHAINING(SUPPORT_COMMAND_CHAINING),
        .SUPPORT_DOUBLE_BUFFER(SUPPORT_DOUBLE_BUFFER),
        .SUPPORT_MULTICAST(SUPPORT_MULTICAST),
        .SUPPORT_DIRECT_MEMORY_PROXY(SUPPORT_DIRECT_MEMORY_PROXY),
        .SUPPORT_CANCELLATION(SUPPORT_CANCELLATION),
        .COMMAND_PROTECTION(COMMAND_PROTECTION),
        .FIFO_PROTECTION(FIFO_PROTECTION),
        .CONTROL_PROTECTION(CONTROL_PROTECTION),
        .ASYNC_SCRATCHPAD_CLOCK(ASYNC_SCRATCHPAD_CLOCK),
        .ASYNC_DMA_CLOCK(ASYNC_DMA_CLOCK),
        .ASYNC_RESET(ASYNC_RESET),
        .TILE_ID_WIDTH(TILE_ID_WIDTH),
        .ARCH_VERSION_WIDTH(ARCH_VERSION_WIDTH),
        .CAPABILITY_ID_WIDTH(CAPABILITY_ID_WIDTH),
        .INPUT_BUFFER_DEPTH(INPUT_BUFFER_DEPTH),
        .OUTPUT_BUFFER_DEPTH(OUTPUT_BUFFER_DEPTH),
        .PREDICATE_WIDTH(PREDICATE_WIDTH),
        .PREDICATE_METADATA_WIDTH(PREDICATE_METADATA_WIDTH),
        .PREDICATE_INPUT_PORTS(PREDICATE_INPUT_PORTS),
        .PREDICATE_OUTPUT_PORTS(PREDICATE_OUTPUT_PORTS),
        .EVENT_INPUT_PORTS(EVENT_INPUT_PORTS),
        .EVENT_OUTPUT_PORTS(EVENT_OUTPUT_PORTS),
        .CONFIG_DATA_WIDTH(CONFIG_DATA_WIDTH),
        .CONTEXT_CHECKSUM_WIDTH(CONTEXT_CHECKSUM_WIDTH),
        .SUPPORT_CONTEXT_CHECKSUM(SUPPORT_CONTEXT_CHECKSUM),
        .CONFIG_ASYNC(CONFIG_ASYNC),
        .CONFIG_QUEUE_DEPTH(CONFIG_QUEUE_DEPTH),
        .RUNTIME_TAG_WIDTH(RUNTIME_TAG_WIDTH),
        .STALL_REASON_WIDTH(STALL_REASON_WIDTH),
        .ERROR_CODE_WIDTH(ERROR_CODE_WIDTH),
        .TRACE_WIDTH(TRACE_WIDTH),
        .SUPPORT_TRACE(SUPPORT_TRACE),
        .SUPPORT_RETENTION(SUPPORT_RETENTION),
        .SUPPORT_POWER_OFF(SUPPORT_POWER_OFF),
        .CONTEXT_PROTECTION(CONTEXT_PROTECTION),
        .EVENT_WIDTH(EVENT_WIDTH),
        .DATA_METADATA_WIDTH(DATA_METADATA_WIDTH),
        .INPUT_ELASTIC_MASK(INPUT_ELASTIC_MASK),
        .OUTPUT_ELASTIC_MASK(OUTPUT_ELASTIC_MASK)
        ) u_head_validation (
            .i_enable(queue_valid[h]),
            .i_dynamic(1'b1),
            .i_descriptor(queue_data[h]),
            .i_owner(i_owner),
            .i_kernel(i_kernel),
            .i_package(context_snapshot.package_id),
            .i_allocation(context_snapshot.allocation),
            .i_context(o_body_context_id),
            .i_version(o_body_context_version),
            .i_epoch(control.epoch),
            .i_load_mask(context_snapshot.loads),
            .i_store_mask(context_snapshot.stores),
            .i_region_mask(context_snapshot.regions),
            .i_regions(regions),
            .i_buffers(buffers),
            .o_code(head_code[h]),
            .o_source_low(),
            .o_source_limit(),
            .o_destination_low(),
            .o_destination_limit()
        );

        logic [NE-1:0] matched_events;
        logic errors;

        always @* begin
            matched_events = '0;
            errors = 1'b0;

            for (int e = 0; e < NE; e++) begin
                event_state_t event_state;
                event_state = event_states[e];

                if (((head.events.mask >> e) & 1'b1) && event_state.valid &&
                    event_state.value.identity.owner == head.identity.owner &&
                    event_state.value.identity.kernel == head.identity.kernel &&
                    event_state.value.identity.package_id == head.identity.package_id &&
                    event_state.value.identity.allocation == head.identity.allocation &&
                    event_state.value.identity.context_id == head.identity.context_id &&
                    event_state.value.identity.version == head.identity.version &&
                    event_state.value.identity.epoch == head.identity.epoch &&
                    event_state.value.identity.command == head.events.dependency &&
                    event_state.value.identity.generation == head.events.dependency_generation &&
                    (!event_state.target || (event_state.target_command == head.identity.command &&
                        event_state.target_generation == head.identity.generation))) begin
                    matched_events[e] = 1'b1;
                    errors |= event_state.value.error;
                end
            end
        end

        assign head_events[h] = matched_events;
        assign head_event_error[h] = errors;
        assign head_event_satisfied[h] = head.events.start == 0 ||
            (head.events.start == 3 ? matched_events == head.events.mask : (|matched_events));

        banked_scratchpad_state #(
            .WIDTH(ACTIVE),
            .PROTECTION(CONTROL_PROTECTION > COMMAND_PROTECTION ?
                CONTROL_PROTECTION : COMMAND_PROTECTION),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_active (
            .i_clk(i_clk),
            .i_reset_n(i_rstb),
            .i_data(active_next[h]),
            .o_data(active_records[h]),
            .o_bad(active_bad[h])
        );

        mst_channel #(
            .IS_LOAD(h < NL),
            .TILE_ID(TILE_ID),
            .ADDR_WIDTH(ADDR_WIDTH),
            .SHELL_DATA_WIDTH(SHELL_DATA_WIDTH),
            .MEMORY_DATA_WIDTH(MEMORY_DATA_WIDTH),
            .NUM_STREAM_INPUTS(NUM_STREAM_INPUTS),
            .NUM_STREAM_OUTPUTS(NUM_STREAM_OUTPUTS),
            .NUM_LOAD_CHANNELS(NUM_LOAD_CHANNELS),
            .NUM_STORE_CHANNELS(NUM_STORE_CHANNELS),
            .NUM_SCRATCHPAD_CLIENTS(NUM_SCRATCHPAD_CLIENTS),
            .NUM_DMA_INGRESS_CHANNELS(NUM_DMA_INGRESS_CHANNELS),
            .NUM_DMA_EGRESS_CHANNELS(NUM_DMA_EGRESS_CHANNELS),
            .CONTEXT_DEPTH(CONTEXT_DEPTH),
            .CONFIG_WORD_COUNT(CONFIG_WORD_COUNT),
            .COMMAND_QUEUE_DEPTH(COMMAND_QUEUE_DEPTH),
            .READ_DATA_FIFO_DEPTH(READ_DATA_FIFO_DEPTH),
            .WRITE_DATA_FIFO_DEPTH(WRITE_DATA_FIFO_DEPTH),
            .COMPLETION_QUEUE_DEPTH(COMPLETION_QUEUE_DEPTH),
            .EVENT_QUEUE_DEPTH(EVENT_QUEUE_DEPTH),
            .MAX_OUTSTANDING_READS(MAX_OUTSTANDING_READS),
            .MAX_OUTSTANDING_WRITES(MAX_OUTSTANDING_WRITES),
            .COUNT_WIDTH(COUNT_WIDTH),
            .MAX_ELEMENT_BYTES(MAX_ELEMENT_BYTES),
            .NUM_PROTECTION_REGIONS(NUM_PROTECTION_REGIONS),
            .NUM_BUFFER_ROLES(NUM_BUFFER_ROLES),
            .NUM_EVENTS(NUM_EVENTS),
            .OWNER_ID_WIDTH(OWNER_ID_WIDTH),
            .KERNEL_ID_WIDTH(KERNEL_ID_WIDTH),
            .PACKAGE_ID_WIDTH(PACKAGE_ID_WIDTH),
            .CONTEXT_VERSION_WIDTH(CONTEXT_VERSION_WIDTH),
            .COMMAND_ID_WIDTH(COMMAND_ID_WIDTH),
            .DESCRIPTOR_GENERATION_WIDTH(DESCRIPTOR_GENERATION_WIDTH),
            .ALLOCATION_GENERATION_WIDTH(ALLOCATION_GENERATION_WIDTH),
            .EXECUTION_EPOCH_WIDTH(EXECUTION_EPOCH_WIDTH),
            .SPACE_ID_WIDTH(SPACE_ID_WIDTH),
            .STREAM_ID_WIDTH(STREAM_ID_WIDTH),
            .REGION_ID_WIDTH(REGION_ID_WIDTH),
            .BUFFER_ID_WIDTH(BUFFER_ID_WIDTH),
            .DATATYPE_WIDTH(DATATYPE_WIDTH),
            .PRIORITY_WIDTH(PRIORITY_WIDTH),
            .TRANSFER_TIMEOUT_CYCLES(TRANSFER_TIMEOUT_CYCLES),
            .CANCEL_TIMEOUT_CYCLES(CANCEL_TIMEOUT_CYCLES),
            .SUPPORT_2D(SUPPORT_2D),
            .SUPPORT_3D(SUPPORT_3D),
            .SUPPORT_CIRCULAR(SUPPORT_CIRCULAR),
            .SUPPORT_GATHER(SUPPORT_GATHER),
            .SUPPORT_SCATTER(SUPPORT_SCATTER),
            .SUPPORT_ATOMICS(SUPPORT_ATOMICS),
            .SUPPORT_LOCAL_COPY(SUPPORT_LOCAL_COPY),
            .SUPPORT_UNALIGNED(SUPPORT_UNALIGNED),
            .SUPPORT_WIDTH_CONVERSION(SUPPORT_WIDTH_CONVERSION),
            .SUPPORT_ELEMENT_CONVERSION(SUPPORT_ELEMENT_CONVERSION),
            .SUPPORT_EVENT_START(SUPPORT_EVENT_START),
            .SUPPORT_COMMAND_CHAINING(SUPPORT_COMMAND_CHAINING),
            .SUPPORT_DOUBLE_BUFFER(SUPPORT_DOUBLE_BUFFER),
            .SUPPORT_MULTICAST(SUPPORT_MULTICAST),
            .SUPPORT_DIRECT_MEMORY_PROXY(SUPPORT_DIRECT_MEMORY_PROXY),
            .SUPPORT_CANCELLATION(SUPPORT_CANCELLATION),
            .COMMAND_PROTECTION(COMMAND_PROTECTION),
            .FIFO_PROTECTION(FIFO_PROTECTION),
            .CONTROL_PROTECTION(CONTROL_PROTECTION),
            .ASYNC_SCRATCHPAD_CLOCK(ASYNC_SCRATCHPAD_CLOCK),
            .ASYNC_DMA_CLOCK(ASYNC_DMA_CLOCK),
            .ASYNC_RESET(ASYNC_RESET),
            .TILE_ID_WIDTH(TILE_ID_WIDTH),
            .ARCH_VERSION_WIDTH(ARCH_VERSION_WIDTH),
            .CAPABILITY_ID_WIDTH(CAPABILITY_ID_WIDTH),
            .INPUT_BUFFER_DEPTH(INPUT_BUFFER_DEPTH),
            .OUTPUT_BUFFER_DEPTH(OUTPUT_BUFFER_DEPTH),
            .PREDICATE_WIDTH(PREDICATE_WIDTH),
            .PREDICATE_METADATA_WIDTH(PREDICATE_METADATA_WIDTH),
            .PREDICATE_INPUT_PORTS(PREDICATE_INPUT_PORTS),
            .PREDICATE_OUTPUT_PORTS(PREDICATE_OUTPUT_PORTS),
            .EVENT_INPUT_PORTS(EVENT_INPUT_PORTS),
            .EVENT_OUTPUT_PORTS(EVENT_OUTPUT_PORTS),
            .CONFIG_DATA_WIDTH(CONFIG_DATA_WIDTH),
            .CONTEXT_CHECKSUM_WIDTH(CONTEXT_CHECKSUM_WIDTH),
            .SUPPORT_CONTEXT_CHECKSUM(SUPPORT_CONTEXT_CHECKSUM),
            .CONFIG_ASYNC(CONFIG_ASYNC),
            .CONFIG_QUEUE_DEPTH(CONFIG_QUEUE_DEPTH),
            .RUNTIME_TAG_WIDTH(RUNTIME_TAG_WIDTH),
            .STALL_REASON_WIDTH(STALL_REASON_WIDTH),
            .ERROR_CODE_WIDTH(ERROR_CODE_WIDTH),
            .TRACE_WIDTH(TRACE_WIDTH),
            .SUPPORT_TRACE(SUPPORT_TRACE),
            .SUPPORT_RETENTION(SUPPORT_RETENTION),
            .SUPPORT_POWER_OFF(SUPPORT_POWER_OFF),
            .CONTEXT_PROTECTION(CONTEXT_PROTECTION),
            .EVENT_WIDTH(EVENT_WIDTH),
            .DATA_METADATA_WIDTH(DATA_METADATA_WIDTH),
            .INPUT_ELASTIC_MASK(INPUT_ELASTIC_MASK),
            .OUTPUT_ELASTIC_MASK(OUTPUT_ELASTIC_MASK)
        ) u_worker (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_clock_enable(i_clock_enable),
            .i_launch(worker_launch[h]),
            .i_release(worker_release[h]),
            .i_cancel(worker_cancel[h]),
            .i_flush(flushing_request),
            .i_copy_worker(copy_worker[h]),
            .i_descriptor(worker_descriptor[h]),
            .i_source_valid(source_valid[h]),
            .o_source_ready(source_ready[h]),
            .o_source_admit(source_admit[h]),
            .i_source_data(source_data[h]),
            .i_source_metadata(source_metadata[h]),
            .i_source_commit(source_commit[h]),
            .i_source_commit_keep(source_commit_keep[h]),
            .o_sink_valid(sink_valid[h]),
            .i_sink_ready(sink_ready[h]),
            .o_sink_data(sink_data[h]),
            .o_sink_metadata(sink_metadata[h]),
            .i_sink_commit(sink_commit[h]),
            .i_sink_commit_keep(sink_commit_keep[h]),
            .i_copy_valid(copy_input_valid[h]),
            .o_copy_ready(copy_input_ready[h]),
            .i_copy_data(copy_input_data[h]),
            .i_copy_error(copy_input_error[h]),
            .o_copy_valid(copy_valid[h]),
            .i_copy_ready(copy_ready[h]),
            .o_copy_data(copy_data[h]),
            .o_copy_error(copy_error[h]),
            .o_memory_valid(memory_valid[h]),
            .i_memory_ready(memory_ready[h]),
            .o_memory_address(memory_address[h]),
            .o_memory_size(memory_size[h]),
            .o_memory_data(memory_data[h]),
            .o_memory_strobe(memory_strobe[h]),
            .o_memory_tag(memory_tag[h]),
            .i_response_valid(response_valid[h]),
            .o_response_ready(response_ready[h]),
            .i_response_tag(response_tag[h]),
            .i_response_identity(response_identity[h]),
            .i_response_data(response_data[h]),
            .i_response_error(response_error[h]),
            .i_response_committed(response_committed[h]),
            .o_done(worker_done[h]),
            .o_stopping(worker_stopping[h]),
            .o_fatal(worker_fatal[h]),
            .o_code(worker_code[h]),
            .o_bytes_read(worker_bytes_read[h]),
            .o_bytes_written(worker_bytes_written[h]),
            .o_elements(worker_elements[h]),
            .o_outstanding(worker_outstanding[h]),
            .o_progress(worker_progress[h]),
            .o_overflow(worker_overflow[h]),
            .o_saturated(worker_saturated[h]),
            .o_started(worker_started[h]),
            .o_request_accepted(worker_request_accepted[h]),
            .o_response_accepted(worker_response_accepted[h]),
            .o_input_accepted(worker_input_accepted[h]),
            .o_output_accepted(worker_output_accepted[h])
        );

        assign source_valid[h] = source_selected_valid[h];
    end

    // Reserve command completion and event credits before any source is consumed.
    // One round-robin scheduler arbitrates independent queue heads and shared
    // stream bindings. Each memory read/write endpoint has its own arbiter below.
    always @* begin
        start_candidates = '0;

        for (int h = 0; h < H; h++) begin
            descriptor_t d;
            active_t current;
            logic resources;
            logic discard;
            d = queue_data[h];
            current = active_records[h];
            discard = control.flushing || flushing_request || queue_canceled[h];
            resources =!current.live &&
                completion_count + 32'(control.completion_reservations) < COMPLETION_QUEUE_DEPTH &&
                (!d.events.completion_enable || terminal_event_count +
                    32'(control.event_reservations) < EVENT_QUEUE_DEPTH);

            if (!discard && head_code[h] == 0 &&!head_event_error[h]) begin
                if (d.mode.transfer == MST_LOCAL_COPY) begin
                    active_t target;
                    target = active_records[NL+int'(d.mode.store_channel)];
                    resources &=!target.live;
                end

                if (d.events.chain_enable) begin
                    event_state_t event_state;
                    event_state = event_states[d.events.completion_id];
                    resources &=!event_state.valid &&!event_state.reserved;
                end

                for (int other = 0; other < H; other++) begin
                    active_t a;
                    a = active_records[other];

                    if (a.live &&!a.worker) begin
                        if (!memory_source(d.mode.transfer)
                            &&!memory_source(a.descriptor.mode.transfer) &&
                            d.source.space == a.descriptor.source.space &&
                            d.source.channel == a.descriptor.source.channel) resources = 1'b0;

                        if (!memory_destination(d.mode.transfer) &&
!memory_destination(a.descriptor.mode.transfer) &&
                            d.destination.space == a.descriptor.destination.space &&
                            d.destination.channel == a.descriptor.destination.channel) resources =
                                1'b0;
                    end
                end
            end

            start_candidates[h] = run && queue_valid[h] && resources &&!o_mst_fatal_error &&
                (discard || (executing && i_clock_enable === 1'b1 && head_event_satisfied[h]));
        end
    end

    assign start_fire = start_valid && run &&!o_mst_fatal_error;

    round_robin_arbiter #(
        .NUM_REQUESTERS(H),
        .HOLD_PENDING(0),
        .ASYNC_RESET(ASYNC_RESET)
    ) u_scheduler (
        .i_clk(i_clk),
        .i_rstb(i_rstb),
        .i_request(start_candidates),
        .i_eligible({H{1'b1}}),
        .i_lock({H{1'b0}}),
        .i_accept(start_fire),
        .i_flush(1'b0),
        .o_grant_valid(start_valid),
        .o_grant_onehot(),
        .o_grant_index(start_channel),
        .o_grant_lock(),
        .o_grant_accepted(),
        .o_contended(),
        .o_pending(),
        .o_locked(),
        .o_lock_owner(),
        .o_protocol_error(start_arbiter_bad)
    );

    for (genvar h = 0; h < H; h++) begin : g_terminal_candidate
        active_t a;
        active_t child;
        assign a = active_records[h];
        assign child = active_records[NL+int'(a.descriptor.mode.store_channel)];
        assign terminal_candidates[h] =!active_bad[h] && a.live &&!a.worker &&!a.reported &&
            (!a.launched || (worker_done[h] &&
                (a.descriptor.mode.transfer != MST_LOCAL_COPY ||
                    worker_done[NL+int'(a.descriptor.mode.store_channel)])));
    end

    round_robin_arbiter #(
        .NUM_REQUESTERS(H),
        .HOLD_PENDING(0),
        .ASYNC_RESET(ASYNC_RESET)
    ) u_completions (
        .i_clk(i_clk),
        .i_rstb(i_rstb),
        .i_request(terminal_candidates),
        .i_eligible({H{1'b1}}),
        .i_lock({H{1'b0}}),
        .i_accept(terminal_fire),
        .i_flush(1'b0),
        .o_grant_valid(terminal_valid),
        .o_grant_onehot(),
        .o_grant_index(terminal_channel),
        .o_grant_lock(),
        .o_grant_accepted(),
        .o_contended(),
        .o_pending(),
        .o_locked(),
        .o_lock_owner(),
        .o_protocol_error(terminal_arbiter_bad)
    );

    always @* begin
        active_t a;
        active_t child;
        int destination;
        event_state_t event_state;
        a = active_records[terminal_channel];
        destination = a.descriptor.mode.transfer == MST_LOCAL_COPY ?
            NL + int'(a.descriptor.mode.store_channel) : int'(terminal_channel);
        child = active_records[destination];
        terminal_record = '0;
        terminal_record.identity = a.descriptor.identity;
        terminal_record.channel = terminal_channel;
        terminal_record.code = a.code;
        terminal_record.overflow = a.overflow;
        terminal_record.saturated = a.saturated;

        if (a.launched) begin
            terminal_record.bytes_read = worker_bytes_read[terminal_channel];
            terminal_record.bytes_written = worker_bytes_written[destination];
            terminal_record.elements = worker_elements[destination];

            if (terminal_record.code == 0) terminal_record.code = worker_code[terminal_channel];

            if ((terminal_record.code == 0 || terminal_record.code == MST_ERR_CANCELED) &&
                worker_code[destination] != 0) terminal_record.code = worker_code[destination];
        end

        terminal_record.status = terminal_record.code == 0 ? MST_SUCCESS :
            terminal_record.code == MST_ERR_CANCELED ? MST_CANCELED : MST_FAILED;

        if (a.fatal || child.fatal || (a.launched &&
            (worker_fatal[terminal_channel] || worker_fatal[destination]))) begin
            terminal_record.status = MST_CONTAINED;
            terminal_record.effects_unknown = 1'b1;
        end

        terminal_record.partial = terminal_record.code != 0 &&
            (terminal_record.bytes_read != 0 || terminal_record.bytes_written != 0 ||
                terminal_record.effects_unknown);
        event_state = '0;

        if (int'(a.descriptor.events.completion_id) < NE)
            event_state = event_states[a.descriptor.events.completion_id];

        terminal_event_record = '0;
        terminal_event_record.kind = tile_shell_pkg::EVENT_BODY;
        terminal_event_record.context_id = a.descriptor.identity.context_id;
        terminal_event_record.kernel = a.descriptor.identity.kernel;
        terminal_event_record.identity = a.descriptor.identity;
        terminal_event_record.id = a.descriptor.events.completion_id;
        terminal_event_record.sequence_id = event_state.transmit_sequence >=
            event_state.value.sequence_id ? event_state.transmit_sequence + 1'b1 :
            event_state.value.sequence_id + 1'b1;
        terminal_event_record.error = terminal_record.code != 0;
        terminal_event_record.payload = {terminal_record.status, terminal_record.code,
            terminal_record.partial, terminal_record.overflow, 20'(terminal_record.bytes_written)};
    end

    logic selected_event_enable;

    always @* begin
        active_t a;
        a = active_records[terminal_channel];
        selected_event_enable = a.descriptor.events.completion_enable;
    end

    assign terminal_fire = run && terminal_valid && completion_input_ready &&
        (!selected_event_enable || terminal_event_input_ready) &&!integrity_bad;

    tile_shell_queue #(
        .WIDTH(COMPLETION),
        .DEPTH(COMPLETION_QUEUE_DEPTH),
        .PROTECTION(CONTROL_PROTECTION)
    ) u_completion_queue (
        .i_clk(i_clk),
        .i_rstb(i_rstb),
        .i_flush(1'b0),
        .i_admit(run),
        .i_deliver(run),
        .i_valid(terminal_valid && (!selected_event_enable || terminal_event_input_ready)),
        .o_ready(completion_input_ready),
        .i_data(terminal_record),
        .o_valid(o_completion_valid),
        .i_ready(i_completion_ready === 1'b1),
        .o_data(completion_packet),
        .o_count(completion_count),
        .o_bad(completion_bad),
        .o_corrected()
    );

    tile_shell_queue #(
        .WIDTH(E),
        .DEPTH(EVENT_QUEUE_DEPTH),
        .PROTECTION(CONTROL_PROTECTION)
    ) u_event_queue (
        .i_clk(i_clk),
        .i_rstb(i_rstb),
        .i_flush(1'b0),
        .i_admit(run),
        .i_deliver(run),
        .i_valid(terminal_valid && selected_event_enable && completion_input_ready),
        .o_ready(terminal_event_input_ready),
        .i_data(E'(terminal_event_record)),
        .o_valid(terminal_event_valid),
        .i_ready(o_body_event_out_ready[0] === 1'b1),
        .o_data(terminal_event_packet),
        .o_count(terminal_event_count),
        .o_bad(terminal_event_bad),
        .o_corrected()
    );

    wire [NM-1:0] read_grant_valid;
    wire [NM-1:0] write_grant_valid;
    wire [HCI-1:0] read_grant [NM];
    wire [HCI-1:0] write_grant [NM];
    wire [2*NM-1:0] memory_arbiter_bad;

    for (genvar port_index = 0; port_index < NM; port_index++) begin : g_memory_port
        wire [H-1:0] read_requests;

        for (genvar h = 0; h < H; h++) begin : g_read_request
            active_t a;
            assign a = active_records[h];
            assign read_requests[h] = run && i_isolate === 1'b0 && h < NL &&
                a.live && a.launched && memory_valid[h] &&
                a.descriptor.source.channel == CH'(port_index);
        end

        round_robin_arbiter #(.NUM_REQUESTERS(H), .ASYNC_RESET(ASYNC_RESET)) u_read_arbiter (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_request(read_requests),
            .i_eligible({H{1'b1}}),
            .i_lock({H{1'b0}}),
            .i_accept(read_grant_valid[port_index] &&
                i_scratchpad_read_ready[port_index] === 1'b1),
            .i_flush(1'b0),
            .o_grant_valid(read_grant_valid[port_index]),
            .o_grant_onehot(),
            .o_grant_index(read_grant[port_index]),
            .o_grant_lock(),
            .o_grant_accepted(),
            .o_contended(),
            .o_pending(),
            .o_locked(),
            .o_lock_owner(),
            .o_protocol_error(memory_arbiter_bad[port_index*2+0])
        );

        active_t read_selected;
        assign read_selected = active_records[read_grant[port_index]];
        assign o_scratchpad_read_valid[port_index] = read_grant_valid[port_index];
        assign o_scratchpad_read_address[port_index*A+:A] =
            read_grant_valid[port_index] ? memory_address[read_grant[port_index]] : {A{1'b0}};
        assign o_scratchpad_read_size_log2[port_index*MSZ+:MSZ] =
            read_grant_valid[port_index] ? memory_size[read_grant[port_index]] : {MSZ{1'b0}};
        assign o_scratchpad_read_tag[port_index*MT+:MT] =
            read_grant_valid[port_index] ? {read_grant[port_index],
                memory_tag[read_grant[port_index]]} : {MT{1'b0}};
        assign o_scratchpad_read_identity[port_index*IDW+:IDW] =
            read_grant_valid[port_index] ? read_selected.descriptor.identity : {IDW{1'b0}};
        assign o_scratchpad_read_region_id[port_index*RI+:RI] =
            read_grant_valid[port_index] ? read_selected.descriptor.source.region_id : {RI{1'b0}};
        assign o_scratchpad_read_generation[port_index*DG+:DG] =
            read_grant_valid[port_index] ? read_selected.descriptor.source.region_generation :
                {DG{1'b0}};
        assign o_scratchpad_read_priority[port_index*PR+:PR] =
            read_grant_valid[port_index] ? read_selected.descriptor.control.priority_hint :
                {PR{1'b0}};
        assign o_scratchpad_read_response_ready[port_index] = run;

        wire [H-1:0] write_requests;

        for (genvar h = 0; h < H; h++) begin : g_write_request
            active_t a;
            assign a = active_records[h];
            assign write_requests[h] = run && i_isolate === 1'b0 && h >= NL &&
                a.live && a.launched && memory_valid[h] &&
                a.descriptor.destination.channel == CH'(port_index);
        end

        round_robin_arbiter #(.NUM_REQUESTERS(H), .ASYNC_RESET(ASYNC_RESET)) u_write_arbiter (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_request(write_requests),
            .i_eligible({H{1'b1}}),
            .i_lock({H{1'b0}}),
            .i_accept(write_grant_valid[port_index] &&
                i_scratchpad_write_ready[port_index] === 1'b1),
            .i_flush(1'b0),
            .o_grant_valid(write_grant_valid[port_index]),
            .o_grant_onehot(),
            .o_grant_index(write_grant[port_index]),
            .o_grant_lock(),
            .o_grant_accepted(),
            .o_contended(),
            .o_pending(),
            .o_locked(),
            .o_lock_owner(),
            .o_protocol_error(memory_arbiter_bad[port_index*2+1])
        );

        active_t write_selected;
        assign write_selected = active_records[write_grant[port_index]];
        assign o_scratchpad_write_valid[port_index] = write_grant_valid[port_index];
        assign o_scratchpad_write_address[port_index*A+:A] =
            write_grant_valid[port_index] ? memory_address[write_grant[port_index]] : {A{1'b0}};
        assign o_scratchpad_write_size_log2[port_index*MSZ+:MSZ] =
            write_grant_valid[port_index] ? memory_size[write_grant[port_index]] : {MSZ{1'b0}};
        assign o_scratchpad_write_tag[port_index*MT+:MT] =
            write_grant_valid[port_index] ? {write_grant[port_index],
                memory_tag[write_grant[port_index]]} : {MT{1'b0}};
        assign o_scratchpad_write_identity[port_index*IDW+:IDW] =
            write_grant_valid[port_index] ? write_selected.descriptor.identity : {IDW{1'b0}};
        assign o_scratchpad_write_region_id[port_index*RI+:RI] =
            write_grant_valid[port_index] ? write_selected.descriptor.destination.region_id :
                {RI{1'b0}};
        assign o_scratchpad_write_generation[port_index*DG+:DG] =
            write_grant_valid[port_index] ? write_selected.descriptor.destination.region_generation
                : {DG{1'b0}};
        assign o_scratchpad_write_priority[port_index*PR+:PR] =
            write_grant_valid[port_index] ? write_selected.descriptor.control.priority_hint :
                {PR{1'b0}};
        assign o_scratchpad_write_data[port_index*MD+:MD] =
            write_grant_valid[port_index] ? memory_data[write_grant[port_index]] : {MD{1'b0}};
        assign o_scratchpad_write_strobe[port_index*MY+:MY] =
            write_grant_valid[port_index] ? memory_strobe[write_grant[port_index]] : {MY{1'b0}};
        assign o_scratchpad_write_response_ready[port_index] = run;
    end

    always @* begin
        memory_ready = '0;
        response_valid = '0;
        response_error = '0;
        response_route_error = |memory_arbiter_bad;

        for (int h = 0; h < H; h++) begin
            response_tag[h] = '0;
            response_identity[h] = '0;
            response_data[h] = '0;
            response_committed[h] = '0;
        end

        for (int p = 0; p < NM; p++) begin
            if (read_grant_valid[p]) memory_ready[read_grant[p]] =
                i_scratchpad_read_ready[p] === 1'b1;

            if (write_grant_valid[p]) memory_ready[write_grant[p]] =
                i_scratchpad_write_ready[p] === 1'b1;

            if (i_scratchpad_read_response_valid[p] === 1'b1) begin
                logic [MT-1:0] tag;
                int h;
                active_t a;
                tag = i_scratchpad_read_response_tag[p*MT+:MT];
                h = int'(tag[AT+:HCI]);
                a = '0;

                if (h < H) a = active_records[h];

                if (^tag === 1'bx ||!(h < NL) ||!a.live ||!a.launched ||
                    a.descriptor.source.channel != CH'(p) || response_valid[h])
                    response_route_error = 1'b1;
                else begin
                    response_valid[h] = 1'b1;
                    response_tag[h] = tag[0+:AT];
                    response_identity[h] = i_scratchpad_read_response_identity[p*IDW+:IDW];
                    response_error[h] = i_scratchpad_read_response_error[p];
                    response_data[h] = i_scratchpad_read_response_data[p*MD+:MD];
                end
            end else if (i_scratchpad_read_response_valid[p] !== 1'b0)
                response_route_error = 1'b1;

            if (i_scratchpad_write_response_valid[p] === 1'b1) begin
                logic [MT-1:0] tag;
                int h;
                active_t a;
                tag = i_scratchpad_write_response_tag[p*MT+:MT];
                h = int'(tag[AT+:HCI]);
                a = '0;

                if (h < H) a = active_records[h];

                if (^tag === 1'bx ||!(h >= NL && h < H) ||!a.live ||!a.launched ||
                    a.descriptor.destination.channel != CH'(p) || response_valid[h])
                    response_route_error = 1'b1;
                else begin
                    response_valid[h] = 1'b1;
                    response_tag[h] = tag[0+:AT];
                    response_identity[h] = i_scratchpad_write_response_identity[p*IDW+:IDW];
                    response_error[h] = i_scratchpad_write_response_error[p];
                    response_committed[h] = i_scratchpad_write_response_bytes_committed[p*MBW+:MBW];
                end
            end else if (i_scratchpad_write_response_valid[p] !== 1'b0)
                response_route_error = 1'b1;
        end
    end

    // Stream bindings remain exclusive until the command's terminal completion
    // is consumed. The shell still owns context filtering and elastic delivery.
    always @* begin
        shell_input_admit = '0;
        body_input_ready = '0;
        body_output_valid = '0;
        body_output_data = '0;
        body_output_metadata = '0;
        dma_input_ready = '0;
        dma_output_valid = '0;
        dma_output_data = '0;
        dma_output_metadata = '0;
        source_selected_valid = '0;
        sink_ready = '0;
        source_commit = '0;
        sink_commit = '0;
        copy_ready = '0;
        copy_input_valid = '0;
        copy_input_error = '0;

        for (int h = 0; h < H; h++) copy_input_data[h] = '0;

        for (int h = 0; h < H; h++) begin
            active_t a;
            stream_t external_input;
            stream_t external_output;
            a = active_records[h];
            external_input = '0;
            external_output = '0;
            source_data[h] = '0;
            source_metadata[h] = '0;
            source_commit_keep[h] = '0;
            sink_commit_keep[h] = '0;

            if (a.live && a.launched &&!a.worker) begin
                if (a.descriptor.mode.transfer == MST_LOCAL_COPY) begin
                    int target;
                    target = NL + int'(a.descriptor.mode.store_channel);
                    copy_input_valid[target] = copy_valid[h];
                    copy_input_data[target] = copy_data[h];
                    copy_input_error[target] = copy_error[h];
                    copy_ready[h] = copy_input_ready[target];
                end

                if (!memory_source(a.descriptor.mode.transfer)) begin
                    int source;
                    logic admission;
                    source = int'(a.descriptor.source.channel);
                    admission = source_admit[h] &&!worker_stopping[h] &&!worker_cancel[h] &&
                        executing && i_clock_enable === 1'b1 &&!o_mst_fatal_error;

                    if (a.descriptor.source.space == MST_SPACE_TILE_STREAM && source < NI) begin
                        shell_input_admit[source] = admission;
                        body_input_ready[source] = source_ready[h];
                        source_selected_valid[h] = o_body_data_in_valid[source];
                        source_data[h] = o_body_data_in_payload[source*D+:D];
                        source_metadata[h] = o_body_data_in_metadata[source*M+:M];
                        source_commit[h] = i_external_input_fire[source];
                        external_input = i_external_input_metadata[source*M+:STREAM_BITS];
                    end else if (source < NDI) begin
                        dma_input_ready[source] = source_ready[h] && admission;
                        source_selected_valid[h] = i_dma_in_valid[source] && admission;
                        source_data[h] = i_dma_in_data[source*D+:D];
                        source_metadata[h] = i_dma_in_metadata[source*M+:M];
                        source_commit[h] = i_dma_in_valid[source] === 1'b1 &&
                            dma_input_ready[source];
                        external_input = i_dma_in_metadata[source*M+:STREAM_BITS];
                    end
                    source_commit_keep[h] = external_input.keep;
                end

                if (!memory_destination(a.descriptor.mode.transfer)) begin
                    int destination;
                    destination = int'(a.descriptor.destination.channel);

                    if (a.descriptor.destination.space == MST_SPACE_TILE_STREAM && destination < NO)
                        begin
                        body_output_valid[destination] = sink_valid[h];
                        sink_ready[h] = o_body_data_out_ready[destination];
                        body_output_data[destination*D+:D] = sink_data[h];
                        body_output_metadata[destination*M+:M] = sink_metadata[h];
                        external_output = i_external_output_metadata[destination*M+:STREAM_BITS];
                        sink_commit[h] = i_external_output_fire[destination] &&
                            external_output.identity === a.descriptor.identity;
                    end else if (destination < NDO) begin
                        dma_output_valid[destination] = sink_valid[h];
                        sink_ready[h] = i_dma_out_ready[destination] === 1'b1;
                        dma_output_data[destination*D+:D] = sink_data[h];
                        dma_output_metadata[destination*M+:M] = sink_metadata[h];
                        external_output = sink_metadata[h][0+:STREAM_BITS];
                        sink_commit[h] = sink_valid[h] && i_dma_out_ready[destination] === 1'b1;
                    end

                    sink_commit_keep[h] = external_output.keep;
                end
            end
        end
    end

    // Dispatch uses immutable queue heads. Keep handshake outputs separate from
    // next-state updates so downstream ready paths cannot create delta cycles.
    always @* begin
        queue_pop = '0;
        worker_launch = '0;
        worker_release = '0;
        worker_cancel = '0;
        copy_worker = '0;

        for (int h = 0; h < H; h++) begin
            active_t a;
            a = active_records[h];
            worker_descriptor[h] = queue_data[h];

            if (a.live && a.launched) begin
                active_t parent;
                parent = active_records[a.parent];
                copy_worker[h] = a.worker;
                worker_cancel[h] =!a.reported && (a.canceled || control.flushing ||
                    flushing_request || (cancel_fire && a.descriptor.control.cancelable &&
                        a.descriptor.identity === cancel_identity) ||
                    (a.worker && worker_stopping[a.parent]) ||
                    (!a.worker && a.descriptor.mode.transfer == MST_LOCAL_COPY &&
                        worker_stopping[NL+int'(a.descriptor.mode.store_channel)]));
                worker_release[h] =!a.fatal &&!worker_fatal[h] &&
                    (a.worker ? parent.reported && parent.completion_consumed &&
                        parent.event_consumed : a.reported && a.completion_consumed &&
                        a.event_consumed);
            end
        end

        if (start_fire) begin
            descriptor_t d;
            d = queue_data[start_channel];
            queue_pop[start_channel] = 1'b1;

            if (!control.flushing &&!flushing_request &&!queue_canceled[start_channel] &&
                head_code[start_channel] == 0 &&!head_event_error[start_channel]) begin
                worker_launch[start_channel] = 1'b1;

                if (d.mode.transfer == MST_LOCAL_COPY) begin
                    int target;
                    target = NL + int'(d.mode.store_channel);
                    worker_launch[target] = 1'b1;
                    copy_worker[target] = 1'b1;
                    worker_descriptor[target] = d;
                end
            end
        end
    end

    // One-shot events are consumed only by a command that actually reserves its
    // datapath and terminal credits. Stale epochs and repeated sequences never
    // satisfy a new dependency.
    assign i_body_event_in_ready = {INE{run &&!control.flushing &&!o_mst_fatal_error}};

    always @* begin
        control_next = control;
        context_next = context_snapshot;
        regions_next = regions;
        buffers_next = buffers;
        region_response_next = region_response;
        buffer_response_next = buffer_response;
        rejection_next = rejection;
        validation_next = validation;
        pulses = '0;
        event_rejected = '0;
        control_next.flush_completed = 1'b0;

        for (int h = 0; h < H; h++) active_next[h] = active_records[h];

        for (int e = 0; e < NE; e++) event_next[e] = event_states[e];

        if (region_response.valid && i_region_response_ready === 1'b1)
            region_response_next.valid = 1'b0;

        if (buffer_response.valid && i_buffer_response_ready === 1'b1)
            buffer_response_next.valid = 1'b0;

        if (rejection.valid && i_rejection_ready === 1'b1) rejection_next.valid = 1'b0;

        if (validation.valid && o_body_validate_result_ready === 1'b1)
            validation_next.valid = 1'b0;

        if (o_body_validate_valid && i_body_validate_ready) begin
            validation_next.valid = 1'b1;
            validation_next.context_id = o_body_validate_context_id;
            validation_next.version = o_body_validate_context_version;
            validation_next.legal = (^o_body_validate_context_image !== 1'bx) &&
                validation_context.schema == 1 && validation_context.loads != 0 &&
                validation_context.stores != 0 &&
                (!validation_context.automatic_command || incoming_code == MST_OK) &&
                (o_body_validate_context_image >> CONTEXT_BITS) == 0;
            validation_next.code = validation_next.legal ? MST_OK : MST_ERR_CONTEXT;
        end

        if (o_body_start) begin
            context_next = live_context;
            control_next.launched = 1'b1;
            control_next.completed = 1'b0;
            control_next.closing = live_context.terminal;
            control_next.automatic_pending = live_context.automatic_command;

            if (&control.epoch) begin
                control_next.fatal = 1'b1;
                control_next.code = MST_ERR_GENERATION;
            end else control_next.epoch = control.epoch + 1'b1;

            for (int e = 0; e < NE; e++) event_next[e] = '0;
        end

        if (i_session_end === 1'b1 || i_drain === 1'b1 ||
            (o_body_drain_request && i_execution_state == tile_shell_pkg::TILE_DRAINING))
            control_next.closing = 1'b1;

        if (!flushing_request) control_next.flush_seen = 1'b0;

        if (flushing_request &&!control.flush_seen) begin
            control_next.flushing = 1'b1;
            control_next.flush_seen = 1'b1;
            control_next.automatic_pending = 1'b0;
        end

        if (control.flushing && quiescent) begin
            control_next.flushing = 1'b0;
            control_next.flush_completed = 1'b1;

            if (&control.epoch) begin
                control_next.fatal = 1'b1;
                control_next.code = MST_ERR_GENERATION;
            end else control_next.epoch = control.epoch + 1'b1;

            for (int e = 0; e < NE; e++) event_next[e] = '0;
        end

        if (control.launched && control.closing &&!control.automatic_pending && quiescent)
            control_next.completed = 1'b1;

        if (i_error_clear === 1'b1 && quiescent &&!control.fatal)
            control_next.code = MST_OK;

        if (o_mst_fatal_error) begin
            control_next.fatal = 1'b1;
            if (control.code == 0) control_next.code = integrity_bad ?
                MST_ERR_INTEGRITY : MST_ERR_CONTAINMENT;
        end

        if (i_region_valid === 1'b1 && o_region_ready) begin
            region_t r;
            region_t old;
            logic legal;
            r = i_region_record;
            old = regions[i_region_index*RGW+:RGW];
            legal = (^{i_region_index, i_region_record} !== 1'bx) &&
                int'(i_region_index) < NR && r.space == MST_SPACE_SCRATCHPAD &&
                r.base < r.limit && r.limit <= ((A + 1)'(1) << A) &&
                r.base % MY == 0 && r.limit % MY == 0 && r.owner == i_owner &&
                (!old.valid || r.generation > old.generation);

            for (int n = 0; n < NR; n++) begin
                region_t other;
                other = regions[n*RGW+:RGW];

                if (n != int'(i_region_index) && other.valid && r.valid &&
                    r.space == other.space && r.base < other.limit && other.base < r.limit)
                    legal = 1'b0;
            end

            region_response_next.valid = 1'b1;
            region_response_next.error =!legal;
            region_response_next.code = legal ? MST_OK : MST_ERR_REGION;

            if (legal) regions_next[i_region_index*RGW+:RGW] = r;
        end

        if (i_buffer_valid === 1'b1 && o_buffer_ready) begin
            buffer_t b;
            buffer_t old;
            region_t r;
            logic legal;
            b = i_buffer_record;
            old = buffers[i_buffer_index*BUW+:BUW];
            r = regions[b.region_id*RGW+:RGW];
            legal = SUPPORT_DOUBLE_BUFFER == 1 &&
                (^{i_buffer_index, i_buffer_record} !== 1'bx) &&
                int'(i_buffer_index) < NB && int'(b.region_id) < NR && r.valid &&
                b.space == r.space && b.base >= r.base && b.limit <= r.limit &&
                b.base < b.limit && b.owner == i_owner && b.kernel == r.kernel &&
                b.allocation == r.allocation &&
                (b.state == BUFFER_FREE || b.state == BUFFER_FULL) &&
                (!old.valid || b.generation > old.generation);
            buffer_response_next.valid = 1'b1;
            buffer_response_next.error =!legal;
            buffer_response_next.code = legal ? MST_OK : MST_ERR_BUFFER;

            if (legal) buffers_next[i_buffer_index*BUW+:BUW] = b;
        end
        if (incoming_fire) begin
            if (candidate_auto) control_next.automatic_pending = 1'b0;

            if (admission_code == 0) pulses[0] = 1'b1;
            else begin
                pulses[1] = 1'b1;
                rejection_next.valid = 1'b1;
                rejection_next.identity = (^incoming.identity === 1'bx) ? '0 : incoming.identity;
                rejection_next.code = admission_code;
                if (control.code == 0) control_next.code = admission_code;
            end
        end

        if (cancel_fire) begin
            pulses[2] = cancel_found;
            pulses[3] =!cancel_found;
        end

        for (int port_index = 0; port_index < INE; port_index++) begin
            if (o_body_event_in_valid[port_index] && i_body_event_in_ready[port_index]) begin
                event_t ev;
                event_state_t state;
                logic legal;
                ev = o_body_event_in_payload[port_index*E+:EVENT_BITS];
                state = event_next[ev.id];
                legal = (^o_body_event_in_payload[port_index*E+:E] !== 1'bx) &&
                    ev.kind == tile_shell_pkg::EVENT_BODY && int'(ev.id) < NE &&
                    ev.context_id == o_body_context_id && ev.kernel == i_kernel &&
                    ev.identity.owner == i_owner && ev.identity.kernel == i_kernel &&
                    ev.identity.package_id == context_snapshot.package_id &&
                    ev.identity.context_id == o_body_context_id &&
                    ev.identity.version == o_body_context_version &&
                    ev.identity.allocation == context_snapshot.allocation &&
                    ev.identity.epoch == control.epoch &&!state.valid &&!state.reserved &&
                    (!state.seen || ev.sequence_id > state.value.sequence_id);

                if (legal) begin
                    state.valid = 1'b1;
                    state.seen = 1'b1;
                    state.target = 1'b0;
                    state.value = ev;
                    event_next[ev.id] = state;
                end else pulses[4] = 1'b1;
            end
        end

        if (start_fire) begin
            descriptor_t d;
            active_t a;
            d = queue_data[start_channel];
            a = '0;
            a.live = 1'b1;
            a.descriptor = d;
            a.event_consumed =!d.events.completion_enable;
            a.parent = start_channel;
            a.canceled = queue_canceled[start_channel] || control.flushing || flushing_request;
            a.code = a.canceled ? MST_ERR_CANCELED : head_code[start_channel];

            if (a.code == 0 && head_event_error[start_channel]) a.code = MST_ERR_DEPENDENCY;

            a.launched = worker_launch[start_channel];
            a.claimed = a.launched;
            active_next[start_channel] = a;
            control_next.completion_reservations = control_next.completion_reservations + 1'b1;

            if (d.events.completion_enable)
                control_next.event_reservations = control_next.event_reservations + 1'b1;

            if (a.launched && d.mode.transfer == MST_LOCAL_COPY) begin
                active_t child;
                child = a;
                child.worker = 1'b1;
                active_next[NL+int'(d.mode.store_channel)] = child;
            end

            if (!a.canceled && d.events.start != 0) begin
                logic consumed;
                consumed = 1'b0;

                for (int e = 0; e < NE; e++) begin
                    if (((head_events[start_channel] >> e) & 1'b1) &&
                        (d.events.start == 3 ||!consumed)) begin
                        event_state_t state;
                        state = event_next[e];
                        state.valid = 1'b0;
                        event_next[e] = state;
                        consumed = 1'b1;
                    end
                end
            end

            if (a.launched) begin
                for (int side = 0; side < 2; side++) begin
                    endpoint_t endpoint;
                    buffer_t b;
                    endpoint = side == 0 ? d.source : d.destination;

                    if (endpoint.buffer_enable) begin
                        b = buffers_next[endpoint.buffer_id*BUW+:BUW];
                        b.state = side == 0 ? BUFFER_CONSUMING : BUFFER_FILLING;
                        b.generation = b.generation + 1'b1;
                        buffers_next[endpoint.buffer_id*BUW+:BUW] = b;
                    end
                end
            end

            if (d.events.chain_enable) begin
                event_state_t state;
                state = event_next[d.events.completion_id];
                state.reserved = 1'b1;
                state.target = 1'b1;
                state.target_command = d.events.chain_command;
                state.target_generation = d.events.chain_generation;
                event_next[d.events.completion_id] = state;
            end
        end

        for (int h = 0; h < H; h++) begin
            active_t a;
            a = active_next[h];

            if (a.live) begin
                if (a.launched &&!a.reported) begin
                    a.overflow |= worker_overflow[h];
                    a.saturated |= worker_saturated[h];
                    a.fatal |= worker_fatal[h];

                    if (worker_cancel[h]) a.canceled = 1'b1;
                end

                if (completion_fire && completion_output.channel == HCI'(h) &&
                    completion_output.identity === a.descriptor.identity)
                    a.completion_consumed = 1'b1;

                for (int e = 0; e < EO; e++) begin
                    event_t ev;
                    ev = i_external_event_payload[e*E+:EVENT_BITS];

                    if (i_external_event_fire[e] && ev.kind == tile_shell_pkg::EVENT_BODY &&
                        ev.identity === a.descriptor.identity) a.event_consumed = 1'b1;
                end

                if (worker_release[h] || (!a.launched && a.reported &&
                    a.completion_consumed && a.event_consumed)) a = '0;

                active_next[h] = a;
            end
        end

        if (terminal_fire) begin
            active_t a;
            a = active_next[terminal_channel];
            a.reported = 1'b1;

            if (a.code == 0) a.code = terminal_record.code;

            active_next[terminal_channel] = a;
            control_next.completion_reservations = control_next.completion_reservations - 1'b1;

            if (a.descriptor.events.completion_enable)
                control_next.event_reservations = control_next.event_reservations - 1'b1;

            if (terminal_record.code != 0 && control.code == 0)
                control_next.code = terminal_record.code;

            if (a.claimed) begin
                for (int side = 0; side < 2; side++) begin
                    endpoint_t endpoint;
                    buffer_t b;
                    endpoint = side == 0 ? a.descriptor.source : a.descriptor.destination;

                    if (endpoint.buffer_enable) begin
                        b = buffers_next[endpoint.buffer_id*BUW+:BUW];
                        b.generation = b.generation + 1'b1;
                        b.state = terminal_record.code == 0 ?
                            (side == 0 ? BUFFER_FREE : BUFFER_FULL) :
                            terminal_record.partial ? BUFFER_ERROR :
                                (side == 0 ? BUFFER_FULL : BUFFER_FREE);
                        buffers_next[endpoint.buffer_id*BUW+:BUW] = b;
                    end
                end

                a.claimed = 1'b0;
                active_next[terminal_channel] = a;
            end

            if (a.descriptor.events.completion_enable) begin
                event_state_t state;
                state = event_next[a.descriptor.events.completion_id];
                state.transmit_sequence = terminal_event_record.sequence_id;

                if (a.descriptor.events.chain_enable) begin
                    state.valid = 1'b1;
                    state.reserved = 1'b0;
                    state.seen = 1'b1;
                    state.value = terminal_event_record;
                end

                event_next[a.descriptor.events.completion_id] = state;

                if (terminal_event_record.sequence_id == 0) begin
                    control_next.fatal = 1'b1;
                    control_next.code = MST_ERR_GENERATION;
                end
            end
        end
    end

    wire [2*H*BC-1:0] byte_snapshots;
    wire [2*H*BC-1:0] byte_snapshot_next;

    for (genvar h = 0; h < H; h++) begin : g_byte_snapshot
        assign byte_snapshot_next[(2*h)*BC+:BC] = worker_bytes_read[h];
        assign byte_snapshot_next[(2*h+1)*BC+:BC] = worker_bytes_written[h];
    end

    dff #(.WIDTH(2 * H * BC), .ASYNC_RESET(ASYNC_RESET)) u_byte_snapshots (
        .i_clk(i_clk),
        .i_rstb(i_rstb),
        .i_enable(1'b1),
        .i_d(byte_snapshot_next),
        .o_q(byte_snapshots)
    );

    // Lifetime counters are deliberately read-only. Count accepted interfaces,
    // not asserted valids, so backpressure cannot inflate activity or progress.
    always @* begin
        increments = '0;
        occupancies = '0;
        increments[0*32+:32] = 32'(incoming_fire && admission_code == 0);
        increments[1*32+:32] = 32'(incoming_fire && admission_code != 0);
        increments[2*32+:32] = 32'(start_fire);
        increments[3*32+:32] = 32'(terminal_fire);
        increments[4*32+:32] = 32'(completion_fire);
        increments[5*32+:32] = 32'(cancel_fire && cancel_found);
        increments[6*32+:32] = 32'(cancel_fire &&!cancel_found);
        increments[7*32+:32] = 32'(terminal_fire && terminal_record.code == MST_ERR_TIMEOUT);
        increments[8*32+:32] = 32'(terminal_fire && terminal_record.partial);
        increments[9*32+:32] = 32'(pulses[4]);
        increments[10*32+:32] = 32'(terminal_event_fire);
        increments[11*32+:32] = 32'(o_mst_fatal_error);
        increments[12*32+:32] = 32'((|queue_valid) &&!start_fire && executing);
        increments[13*32+:32] = 32'(control.flushing);
        increments[14*32+:32] = 32'(o_body_suspend_request);
        increments[15*32+:32] = 32'(o_body_resume);
        increments[18*32+:32] = 32'((|i_scratchpad_conflict) === 1'b1 &&
            ((|o_scratchpad_read_valid) || (|o_scratchpad_write_valid)));
        occupancies[H*32+:32] = completion_count;
        occupancies[(H+1)*32+:32] = terminal_event_count;

        for (int h = 0; h < H; h++) begin
            increments[(32+8*h)*32+:32] = 32'(worker_started[h]);
            increments[(33+8*h)*32+:32] = 32'(worker_request_accepted[h]);
            increments[(34+8*h)*32+:32] = 32'(worker_response_accepted[h]);
            increments[(35+8*h)*32+:32] = 32'(worker_input_accepted[h]);
            increments[(36+8*h)*32+:32] = 32'(worker_output_accepted[h]);
            increments[(37+8*h)*32+:32] = 32'(worker_overflow[h]);
            increments[(38+8*h)*32+:32] = 32'(worker_saturated[h]);
            increments[(39+8*h)*32+:32] = 32'(memory_valid[h] &&!memory_ready[h]);

            // Per-command byte counters return to zero between commands. Count
            // positive deltas only; reset/retirement must not underflow totals.
            if (worker_bytes_read[h] > byte_snapshots[(2*h)*BC+:BC])
                increments[16*32+:32] = increments[16*32+:32] +
                    32'(worker_bytes_read[h] - byte_snapshots[(2*h)*BC+:BC]);

            if (worker_bytes_written[h] > byte_snapshots[(2*h+1)*BC+:BC])
                increments[17*32+:32] = increments[17*32+:32] +
                    32'(worker_bytes_written[h] - byte_snapshots[(2*h+1)*BC+:BC]);

            occupancies[h*32+:32] = 32'(queue_count[h*OC+:OC]);
            occupancies[(H+2)*32+:32] = occupancies[(H+2)*32+:32] + worker_outstanding[h];
        end
    end

    banked_scratchpad_counters #(
        .COUNT(COUNTERS),
        .PEAKS(H + 3),
        .ASYNC_RESET(ASYNC_RESET)
    ) u_counters (
        .i_clk(i_clk),
        .i_reset_n(i_rstb),
        .i_increments(increments),
        .i_occupancy(occupancies),
        .o_counts(counters),
        .o_peaks(peaks)
    );

    banked_scratchpad_state #(
        .WIDTH($bits(mst_body_control_t)),
        .PROTECTION(CONTROL_PROTECTION),
        .ASYNC_RESET(ASYNC_RESET)
    ) u_control (
        .i_clk(i_clk),
        .i_reset_n(i_rstb),
        .i_data(control_next),
        .o_data(control),
        .o_bad(control_bad)
    );

    banked_scratchpad_state #(
        .WIDTH($bits(context_t)),
        .PROTECTION(COMMAND_PROTECTION),
        .ASYNC_RESET(ASYNC_RESET)
    ) u_context (
        .i_clk(i_clk),
        .i_reset_n(i_rstb),
        .i_data(context_next),
        .o_data(context_snapshot),
        .o_bad(context_bad)
    );

    banked_scratchpad_state #(
        .WIDTH($bits(management_response_t)),
        .PROTECTION(CONTROL_PROTECTION),
        .ASYNC_RESET(ASYNC_RESET)
    ) u_region_response (
        .i_clk(i_clk),
        .i_reset_n(i_rstb),
        .i_data(region_response_next),
        .o_data(region_response),
        .o_bad(region_response_bad)
    );

    banked_scratchpad_state #(
        .WIDTH($bits(management_response_t)),
        .PROTECTION(CONTROL_PROTECTION),
        .ASYNC_RESET(ASYNC_RESET)
    ) u_buffer_response (
        .i_clk(i_clk),
        .i_reset_n(i_rstb),
        .i_data(buffer_response_next),
        .o_data(buffer_response),
        .o_bad(buffer_response_bad)
    );

    banked_scratchpad_state #(
        .WIDTH($bits(rejection_t)),
        .PROTECTION(CONTROL_PROTECTION),
        .ASYNC_RESET(ASYNC_RESET)
    ) u_rejection (
        .i_clk(i_clk),
        .i_reset_n(i_rstb),
        .i_data(rejection_next),
        .o_data(rejection),
        .o_bad(rejection_bad)
    );

    banked_scratchpad_state #(
        .WIDTH($bits(validation_t)),
        .PROTECTION(CONTROL_PROTECTION),
        .ASYNC_RESET(ASYNC_RESET)
    ) u_validation (
        .i_clk(i_clk),
        .i_reset_n(i_rstb),
        .i_data(validation_next),
        .o_data(validation),
        .o_bad(validation_bad)
    );

    for (genvar n = 0; n < NR; n++) begin : g_region
        banked_scratchpad_state #(
            .WIDTH(RGW),
            .PROTECTION(CONTROL_PROTECTION),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_state (
            .i_clk(i_clk),
            .i_reset_n(i_rstb),
            .i_data(regions_next[n*RGW+:RGW]),
            .o_data(regions[n*RGW+:RGW]),
            .o_bad(region_bad[n])
        );
    end

    for (genvar n = 0; n < NB; n++) begin : g_buffer
        banked_scratchpad_state #(
            .WIDTH(BUW),
            .PROTECTION(CONTROL_PROTECTION),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_state (
            .i_clk(i_clk),
            .i_reset_n(i_rstb),
            .i_data(buffers_next[n*BUW+:BUW]),
            .o_data(buffers[n*BUW+:BUW]),
            .o_bad(buffer_bad[n])
        );
    end

    for (genvar n = 0; n < NE; n++) begin : g_event
        banked_scratchpad_state #(
            .WIDTH(ES),
            .PROTECTION(CONTROL_PROTECTION),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_state (
            .i_clk(i_clk),
            .i_reset_n(i_rstb),
            .i_data(event_next[n]),
            .o_data(event_states[n]), .o_bad(event_bad[n])
        );
    end

    dff #(.WIDTH(6), .ASYNC_RESET(ASYNC_RESET)) u_pulses (
        .i_clk(i_clk),
        .i_rstb(i_rstb),
        .i_enable(1'b1),
        .i_d(pulses),
        .o_q(pulse_outputs)
    );
endmodule
`default_nettype wire
