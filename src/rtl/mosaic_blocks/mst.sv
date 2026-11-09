`timescale 1ns / 1ps
`default_nettype none

module mst #(
    // Explicit enables override the legacy profile without coupling peer FUs.
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
        ((ENABLE_LOAD === 0) || (ENABLE_LOAD === 1)) &&
        ((ENABLE_STORE === 0) || (ENABLE_STORE === 1)) &&

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
    input wire i_clk,
    input wire i_rstb,
    input wire i_cfg_clk,
    input wire i_cfg_rstb,
    input wire i_test_enable,
    input wire i_scan_enable,
    output wire o_body_clock_enable,
    output wire o_monitor_clock_enable,
    input wire [NI-1:0] i_data_in_valid,
    output wire [NI-1:0] o_data_in_ready,
    input wire [NI*D-1:0] i_data_in_payload,
    input wire [NI*M-1:0] i_data_in_metadata,
    output wire [NO-1:0] o_data_out_valid,
    input wire [NO-1:0] i_data_out_ready,
    output wire [NO*D-1:0] o_data_out_payload,
    output wire [NO*M-1:0] o_data_out_metadata,
    input wire [PI-1:0] i_predicate_in_valid,
    output wire [PI-1:0] o_predicate_in_ready,
    input wire [PI*P-1:0] i_predicate_in_payload,
    input wire [PI*PM-1:0] i_predicate_in_metadata,
    output wire [PO-1:0] o_predicate_out_valid,
    input wire [PO-1:0] i_predicate_out_ready,
    output wire [PO*P-1:0] o_predicate_out_payload,
    output wire [PO*PM-1:0] o_predicate_out_metadata,
    input wire [INE-1:0] i_event_in_valid,
    output wire [INE-1:0] o_event_in_ready,
    input wire [E*INE-1:0] i_event_in_payload,
    output wire [EO-1:0] o_event_out_valid,
    input wire [EO-1:0] i_event_out_ready,
    output wire [E*EO-1:0] o_event_out_payload,
    input wire i_cfg_request_valid,
    output wire o_cfg_request_ready,
    input wire [2:0] i_cfg_request_command,
    input wire [TI-1:0] i_cfg_request_tile_id,
    input wire [O-1:0] i_cfg_request_owner_id,
    input wire [CI-1:0] i_cfg_request_context_id,
    input wire [WI-1:0] i_cfg_request_word_index,
    input wire [W-1:0] i_cfg_request_write_data,
    input wire [BY-1:0] i_cfg_request_write_strobe,
    input wire [31:0] i_cfg_request_expected_crc,
    input wire [T-1:0] i_cfg_request_tag,
    output wire o_cfg_response_valid,
    input wire i_cfg_response_ready,
    output wire [2:0] o_cfg_response_command,
    output wire [CI-1:0] o_cfg_response_context_id,
    output wire [W-1:0] o_cfg_response_read_data,
    output wire [V-1:0] o_cfg_response_context_version,
    output wire [31:0] o_cfg_response_crc,
    output wire o_cfg_response_error,
    output wire [ER-1:0] o_cfg_response_error_code,
    output wire [T-1:0] o_cfg_response_tag,
    input wire i_runtime_request_valid,
    output wire o_runtime_request_ready,
    input wire [2:0] i_runtime_request_command,
    input wire [O-1:0] i_runtime_request_owner_id,
    input wire [K-1:0] i_runtime_request_kernel_id,
    input wire [CI-1:0] i_runtime_request_context_id,
    input wire [T-1:0] i_runtime_request_tag,
    output wire o_runtime_response_valid,
    input wire i_runtime_response_ready,
    output wire [2:0] o_runtime_response_command,
    output wire [3:0] o_runtime_response_state,
    output wire o_runtime_response_error,
    output wire [ER-1:0] o_runtime_response_error_code,
    output wire [T-1:0] o_runtime_response_tag,
    input wire i_power_request_valid,
    output wire o_power_request_ready,
    input wire [2:0] i_power_request_state,
    output wire o_power_response_valid,
    input wire i_power_response_ready,
    output wire [2:0] o_power_response_state,
    output wire o_power_response_error,
    output wire [ER-1:0] o_power_response_error_code,
    output wire o_body_save,
    input wire i_body_save_done,
    output wire o_body_restore,
    input wire i_body_restore_done,
    output wire o_body_isolate,
    input wire i_body_isolation_ack,
    output wire o_body_power_enable,
    input wire i_body_power_good,
    output wire [TI-1:0] o_status_tile_id,
    output wire [2:0] o_status_tile_class,
    output wire [AV-1:0] o_status_arch_version,
    output wire [CP-1:0] o_status_capability_id,
    output wire [3:0] o_status_execution_state,
    output wire [2:0] o_status_power_state,
    output wire [S-1:0] o_status_stall_reasons,
    output wire [CI-1:0] o_status_active_context,
    output wire [V-1:0] o_status_context_version,
    output wire [O-1:0] o_status_owner_id,
    output wire [K-1:0] o_status_kernel_id,
    output wire [NC-1:0] o_status_context_valid,
    output wire o_status_busy,
    output wire o_status_idle,
    output wire o_status_quiescent,
    output wire o_status_error,
    output wire o_status_fatal_error,
    output wire [ER-1:0] o_status_error_code,
    input wire i_debug_request_valid,
    output wire o_debug_request_ready,
    input wire i_debug_request_write,
    input wire [O-1:0] i_debug_request_owner_id,
    input wire i_debug_request_privileged,
    input wire [7:0] i_debug_request_address,
    input wire [W-1:0] i_debug_request_write_data,
    input wire [BY-1:0] i_debug_request_write_strobe,
    output wire o_debug_response_valid,
    input wire i_debug_response_ready,
    output wire [W-1:0] o_debug_response_read_data,
    output wire o_debug_response_error,
    output wire o_trace_valid,
    input wire i_trace_ready,
    output wire [TR-1:0] o_trace_data,
    output wire o_completion_overflow,
    output wire o_completion_saturated,
    input wire [NM-1:0] i_scratchpad_conflict,
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
    output wire [NDO*M-1:0] o_dma_out_metadata
);
    if (!PARAMETERS_VALID || IM < CONTEXT_BITS || M < STREAM_BITS || E < EVENT_BITS ||
        H > 8 || SP < 2 || ST < CH || PREDICATE_INPUT_PORTS != 1 || PREDICATE_OUTPUT_PORTS != 1 ||
        EVENT_INPUT_PORTS != 1 || EVENT_OUTPUT_PORTS != 1) begin : g_bad_parameters
        mst_parameters_must_be_valid invalid_parameters ();
    end else if (SUPPORT_3D || SUPPORT_CIRCULAR || SUPPORT_GATHER || SUPPORT_SCATTER ||
        SUPPORT_ATOMICS || SUPPORT_MULTICAST || SUPPORT_DIRECT_MEMORY_PROXY ||
        ASYNC_SCRATCHPAD_CLOCK || ASYNC_DMA_CLOCK) begin : g_unreleased_profile
        mst_profile_requires_released_adapter invalid_profile ();
    end else begin : g_mst

    wire [CI-1:0] o_body_context_id;
    wire [V-1:0] o_body_context_version;
    wire [IM-1:0] o_body_context_image;
    wire [N-1:0] o_body_context_word_valid;
    wire o_body_context_active;
    wire o_body_validate_valid;
    wire i_body_validate_ready;
    wire [CI-1:0] o_body_validate_context_id;
    wire [V-1:0] o_body_validate_context_version;
    wire [IM-1:0] o_body_validate_context_image;
    wire [N-1:0] o_body_validate_word_valid;
    wire i_body_validate_result_valid;
    wire o_body_validate_result_ready;
    wire [CI-1:0] i_body_validate_context_id;
    wire [V-1:0] i_body_validate_context_version;
    wire i_body_validate_legal;
    wire [ER-1:0] i_body_validate_error_code;
    wire o_body_start;
    wire o_body_suspend_request;
    wire o_body_resume;
    wire o_body_drain_request;
    wire o_body_flush;
    wire [NI-1:0] o_body_data_in_valid;
    wire [NI-1:0] i_body_data_in_ready;
    wire [NI*D-1:0] o_body_data_in_payload;
    wire [NI*M-1:0] o_body_data_in_metadata;
    wire [PI-1:0] o_body_predicate_in_valid;
    wire [PI-1:0] i_body_predicate_in_ready;
    wire [PI*P-1:0] o_body_predicate_in_payload;
    wire [PI*PM-1:0] o_body_predicate_in_metadata;
    wire [INE-1:0] o_body_event_in_valid;
    wire [INE-1:0] i_body_event_in_ready;
    wire [E*INE-1:0] o_body_event_in_payload;
    wire [NO-1:0] i_body_data_out_valid;
    wire [NO-1:0] o_body_data_out_ready;
    wire [NO*D-1:0] i_body_data_out_payload;
    wire [NO*M-1:0] i_body_data_out_metadata;
    wire [PO-1:0] i_body_predicate_out_valid;
    wire [PO-1:0] o_body_predicate_out_ready;
    wire [PO*P-1:0] i_body_predicate_out_payload;
    wire [PO*PM-1:0] i_body_predicate_out_metadata;
    wire [EO-1:0] i_body_event_out_valid;
    wire [EO-1:0] o_body_event_out_ready;
    wire [E*EO-1:0] i_body_event_out_payload;
    wire i_body_busy;
    wire i_body_idle;
    wire i_body_safe_point;
    wire i_body_drain_done;
    wire i_body_completed;
    wire [S-1:0] i_body_stall_reasons;
    wire i_body_error;
    wire i_body_fatal_error;
    wire [ER-1:0] i_body_error_code;
    wire i_body_wakeup_required;
    wire [CP-1:0] shell_capability;
    wire advance_valid;
    wire advance_ready;
    wire [CI-1:0] advance_context;

    assign advance_valid = 1'b0;
    assign advance_context = '0;

    // Versioned body fingerprint includes every independently configurable
    // capability. It is an identity, not a bit mask of operation encodings.
    function automatic logic [31:0] body_fingerprint();
        logic [31:0] value;
        value = 32'h4d535401;
        value = (value ^ 32'(TILE_ID)) * 32'd16777619;
        value = (value ^ 32'(ADDR_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(SHELL_DATA_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(MEMORY_DATA_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(NUM_STREAM_INPUTS)) * 32'd16777619;
        value = (value ^ 32'(NUM_STREAM_OUTPUTS)) * 32'd16777619;
        value = (value ^ 32'(NUM_LOAD_CHANNELS)) * 32'd16777619;
        value = (value ^ 32'(NUM_STORE_CHANNELS)) * 32'd16777619;
        value = (value ^ 32'(NUM_SCRATCHPAD_CLIENTS)) * 32'd16777619;
        value = (value ^ 32'(NUM_DMA_INGRESS_CHANNELS)) * 32'd16777619;
        value = (value ^ 32'(NUM_DMA_EGRESS_CHANNELS)) * 32'd16777619;
        value = (value ^ 32'(CONTEXT_DEPTH)) * 32'd16777619;
        value = (value ^ 32'(CONFIG_WORD_COUNT)) * 32'd16777619;
        value = (value ^ 32'(COMMAND_QUEUE_DEPTH)) * 32'd16777619;
        value = (value ^ 32'(READ_DATA_FIFO_DEPTH)) * 32'd16777619;
        value = (value ^ 32'(WRITE_DATA_FIFO_DEPTH)) * 32'd16777619;
        value = (value ^ 32'(COMPLETION_QUEUE_DEPTH)) * 32'd16777619;
        value = (value ^ 32'(EVENT_QUEUE_DEPTH)) * 32'd16777619;
        value = (value ^ 32'(MAX_OUTSTANDING_READS)) * 32'd16777619;
        value = (value ^ 32'(MAX_OUTSTANDING_WRITES)) * 32'd16777619;
        value = (value ^ 32'(COUNT_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(MAX_ELEMENT_BYTES)) * 32'd16777619;
        value = (value ^ 32'(NUM_PROTECTION_REGIONS)) * 32'd16777619;
        value = (value ^ 32'(NUM_BUFFER_ROLES)) * 32'd16777619;
        value = (value ^ 32'(NUM_EVENTS)) * 32'd16777619;
        value = (value ^ 32'(OWNER_ID_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(KERNEL_ID_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(PACKAGE_ID_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(CONTEXT_VERSION_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(COMMAND_ID_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(DESCRIPTOR_GENERATION_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(ALLOCATION_GENERATION_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(EXECUTION_EPOCH_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(SPACE_ID_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(STREAM_ID_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(REGION_ID_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(BUFFER_ID_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(DATATYPE_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(PRIORITY_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(TRANSFER_TIMEOUT_CYCLES)) * 32'd16777619;
        value = (value ^ 32'(CANCEL_TIMEOUT_CYCLES)) * 32'd16777619;
        value = (value ^ 32'(SUPPORT_2D)) * 32'd16777619;
        value = (value ^ 32'(SUPPORT_3D)) * 32'd16777619;
        value = (value ^ 32'(SUPPORT_CIRCULAR)) * 32'd16777619;
        value = (value ^ 32'(SUPPORT_GATHER)) * 32'd16777619;
        value = (value ^ 32'(SUPPORT_SCATTER)) * 32'd16777619;
        value = (value ^ 32'(SUPPORT_ATOMICS)) * 32'd16777619;
        value = (value ^ 32'(SUPPORT_LOCAL_COPY)) * 32'd16777619;
        value = (value ^ 32'(SUPPORT_UNALIGNED)) * 32'd16777619;
        value = (value ^ 32'(SUPPORT_WIDTH_CONVERSION)) * 32'd16777619;
        value = (value ^ 32'(SUPPORT_ELEMENT_CONVERSION)) * 32'd16777619;
        value = (value ^ 32'(SUPPORT_EVENT_START)) * 32'd16777619;
        value = (value ^ 32'(SUPPORT_COMMAND_CHAINING)) * 32'd16777619;
        value = (value ^ 32'(SUPPORT_DOUBLE_BUFFER)) * 32'd16777619;
        value = (value ^ 32'(SUPPORT_MULTICAST)) * 32'd16777619;
        if (ENABLE_LOAD != (1))
            value = (value ^ (32'(ENABLE_LOAD) + 32'd1)) * 32'd16777619;
        if (ENABLE_STORE != (1))
            value = (value ^ (32'(ENABLE_STORE) + 32'd2)) * 32'd16777619;
        value = (value ^ 32'(SUPPORT_DIRECT_MEMORY_PROXY)) * 32'd16777619;
        value = (value ^ 32'(SUPPORT_CANCELLATION)) * 32'd16777619;
        value = (value ^ 32'(COMMAND_PROTECTION)) * 32'd16777619;
        value = (value ^ 32'(FIFO_PROTECTION)) * 32'd16777619;
        value = (value ^ 32'(CONTROL_PROTECTION)) * 32'd16777619;
        value = (value ^ 32'(ASYNC_SCRATCHPAD_CLOCK)) * 32'd16777619;
        value = (value ^ 32'(ASYNC_DMA_CLOCK)) * 32'd16777619;
        value = (value ^ 32'(ASYNC_RESET)) * 32'd16777619;
        value = (value ^ 32'(TILE_ID_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(ARCH_VERSION_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(CAPABILITY_ID_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(INPUT_BUFFER_DEPTH)) * 32'd16777619;
        value = (value ^ 32'(OUTPUT_BUFFER_DEPTH)) * 32'd16777619;
        value = (value ^ 32'(PREDICATE_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(PREDICATE_METADATA_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(PREDICATE_INPUT_PORTS)) * 32'd16777619;
        value = (value ^ 32'(PREDICATE_OUTPUT_PORTS)) * 32'd16777619;
        value = (value ^ 32'(EVENT_INPUT_PORTS)) * 32'd16777619;
        value = (value ^ 32'(EVENT_OUTPUT_PORTS)) * 32'd16777619;
        value = (value ^ 32'(CONFIG_DATA_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(CONTEXT_CHECKSUM_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(SUPPORT_CONTEXT_CHECKSUM)) * 32'd16777619;
        value = (value ^ 32'(CONFIG_ASYNC)) * 32'd16777619;
        value = (value ^ 32'(CONFIG_QUEUE_DEPTH)) * 32'd16777619;
        value = (value ^ 32'(RUNTIME_TAG_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(STALL_REASON_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(ERROR_CODE_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(TRACE_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(SUPPORT_TRACE)) * 32'd16777619;
        value = (value ^ 32'(SUPPORT_RETENTION)) * 32'd16777619;
        value = (value ^ 32'(SUPPORT_POWER_OFF)) * 32'd16777619;
        value = (value ^ 32'(CONTEXT_PROTECTION)) * 32'd16777619;
        value = (value ^ 32'(EVENT_WIDTH)) * 32'd16777619;
        value = (value ^ 32'(DATA_METADATA_WIDTH)) * 32'd16777619;
        return value;
    endfunction

    localparam logic [31:0] BODY_CAPABILITY = body_fingerprint();
    assign o_status_capability_id = shell_capability ^ CP'(BODY_CAPABILITY);
    wire [NI-1:0] o_shell_input_admit;
    wire [NI-1:0] shell_data_in_valid = i_data_in_valid & o_shell_input_admit;
    wire [NI-1:0] shell_data_in_ready;
    assign o_data_in_ready = shell_data_in_ready & o_shell_input_admit;
    wire body_debug_select = i_debug_request_address[7] === 1'b1;
    wire shell_debug_request = i_debug_request_valid &&!body_debug_select &&!body_debug_valid;
    wire shell_debug_ready;
    wire shell_debug_response;
    wire [W-1:0] shell_debug_data;
    wire shell_debug_error;
    wire [31:0] body_counter_data;
    wire body_debug_valid;
    wire [W-1:0] body_debug_data;
    wire body_debug_error;
    wire body_debug_accept = i_debug_request_valid === 1'b1 && body_debug_select &&
!body_debug_valid &&!shell_debug_response && i_rstb === 1'b1;
    wire body_debug_authorized = (^ {i_debug_request_owner_id, i_debug_request_privileged,
        i_debug_request_write} !== 1'bx) && i_debug_request_write === 1'b0 &&
        (i_debug_request_privileged === 1'b1 ||
        i_debug_request_owner_id == o_status_owner_id);
    wire body_debug_consume = i_rstb === 1'b1 && body_debug_valid &&
        i_debug_response_ready === 1'b1;
    wire next_debug_valid = body_debug_accept || (body_debug_valid &&!body_debug_consume);

    dff #(.WIDTH(W + 2), .ASYNC_RESET(ASYNC_RESET)) u_debug_response (
        .i_clk(i_clk),
        .i_rstb(i_rstb !== 1'b0),
        .i_enable(body_debug_accept || body_debug_consume),
        .i_d({next_debug_valid,!body_debug_authorized,
            body_debug_authorized ? W'(body_counter_data) : {W{1'b0}}}),
        .o_q({body_debug_valid, body_debug_error, body_debug_data})
    );

    assign o_debug_request_ready = i_rstb === 1'b1 &&!body_debug_valid &&
!shell_debug_response && (body_debug_select || shell_debug_ready);
    assign o_debug_response_valid = i_rstb === 1'b1 &&
        (body_debug_valid || shell_debug_response);
    assign o_debug_response_read_data =!o_debug_response_valid ? '0 :
        body_debug_valid ? body_debug_data : shell_debug_data;
    assign o_debug_response_error = o_debug_response_valid &&
        (body_debug_valid ? body_debug_error : shell_debug_error);

    tile_shell #(
        .TILE_ID(TILE_ID),
        .TILE_ID_WIDTH(TILE_ID_WIDTH),
        .ARCH_VERSION_WIDTH(ARCH_VERSION_WIDTH),
        .CAPABILITY_ID_WIDTH(CAPABILITY_ID_WIDTH),
        .DATA_WIDTH(SHELL_DATA_WIDTH),
        .DATA_METADATA_WIDTH(DATA_METADATA_WIDTH),
        .DATA_INPUT_PORTS(NUM_STREAM_INPUTS),
        .DATA_OUTPUT_PORTS(NUM_STREAM_OUTPUTS),
        .INPUT_BUFFER_DEPTH(INPUT_BUFFER_DEPTH),
        .OUTPUT_BUFFER_DEPTH(OUTPUT_BUFFER_DEPTH),
        .PREDICATE_WIDTH(PREDICATE_WIDTH),
        .PREDICATE_METADATA_WIDTH(PREDICATE_METADATA_WIDTH),
        .PREDICATE_INPUT_PORTS(PREDICATE_INPUT_PORTS),
        .PREDICATE_OUTPUT_PORTS(PREDICATE_OUTPUT_PORTS),
        .EVENT_WIDTH(EVENT_WIDTH),
        .EVENT_INPUT_PORTS(EVENT_INPUT_PORTS),
        .EVENT_OUTPUT_PORTS(EVENT_OUTPUT_PORTS),
        .CONTEXT_DEPTH(CONTEXT_DEPTH),
        .CONFIG_DATA_WIDTH(CONFIG_DATA_WIDTH),
        .CONFIG_WORD_COUNT(CONFIG_WORD_COUNT),
        .CONTEXT_CHECKSUM_WIDTH(CONTEXT_CHECKSUM_WIDTH),
        .SUPPORT_CONTEXT_CHECKSUM(SUPPORT_CONTEXT_CHECKSUM),
        .CONFIG_ASYNC(CONFIG_ASYNC),
        .CONFIG_QUEUE_DEPTH(CONFIG_QUEUE_DEPTH),
        .OWNER_ID_WIDTH(OWNER_ID_WIDTH),
        .KERNEL_ID_WIDTH(KERNEL_ID_WIDTH),
        .CONTEXT_VERSION_WIDTH(CONTEXT_VERSION_WIDTH),
        .RUNTIME_TAG_WIDTH(RUNTIME_TAG_WIDTH),
        .STALL_REASON_WIDTH(STALL_REASON_WIDTH),
        .ERROR_CODE_WIDTH(ERROR_CODE_WIDTH),
        .TRACE_WIDTH(TRACE_WIDTH),
        .SUPPORT_TRACE(SUPPORT_TRACE),
        .SUPPORT_RETENTION(SUPPORT_RETENTION),
        .SUPPORT_POWER_OFF(SUPPORT_POWER_OFF),
        .CONTEXT_PROTECTION(CONTEXT_PROTECTION),
        .CONTROL_PROTECTION(CONTROL_PROTECTION),
        .ASYNC_RESET(ASYNC_RESET),
        .TILE_CLASS(3),
        .BODY_CONTEXT_ADVANCE(0),
        .BODY_DRAIN_EVENTS(1),
        .INPUT_ELASTIC_MASK(INPUT_ELASTIC_MASK),
        .OUTPUT_ELASTIC_MASK(OUTPUT_ELASTIC_MASK)
    ) u_shell (
        .i_data_in_valid(shell_data_in_valid),
        .o_data_in_ready(shell_data_in_ready),
        .i_body_context_advance(advance_valid),
        .i_body_next_context(advance_context),
        .o_body_context_advance_ready(advance_ready),
        .o_status_capability_id(shell_capability),
        .i_debug_request_valid(shell_debug_request),
        .o_debug_request_ready(shell_debug_ready),
        .o_debug_response_valid(shell_debug_response),
        .i_debug_response_ready(i_debug_response_ready &&!body_debug_valid),
        .o_debug_response_read_data(shell_debug_data),
        .o_debug_response_error(shell_debug_error),
        .*
    );

    mst_body #(
        .TILE_ID(TILE_ID),
        .ADDR_WIDTH(ADDR_WIDTH),
        .SHELL_DATA_WIDTH(SHELL_DATA_WIDTH),
        .MEMORY_DATA_WIDTH(MEMORY_DATA_WIDTH),
        .NUM_STREAM_INPUTS(NUM_STREAM_INPUTS),
        .NUM_STREAM_OUTPUTS(NUM_STREAM_OUTPUTS),
        .NUM_LOAD_CHANNELS(NUM_LOAD_CHANNELS),
        .ENABLE_LOAD(ENABLE_LOAD),
        .ENABLE_STORE(ENABLE_STORE),
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
    ) u_body (
        .i_clock_enable(o_body_clock_enable), .i_execution_state(o_status_execution_state),
        .i_owner(o_status_owner_id), .i_kernel(o_status_kernel_id), .i_isolate(o_body_isolate),
        .i_monitor_enable(o_monitor_clock_enable), .i_power_state(o_status_power_state),
        .i_counter_index(i_debug_request_address[6:0]), .o_counter_data(body_counter_data),
        .i_external_input_fire(i_data_in_valid & o_data_in_ready),
        .i_external_input_metadata(i_data_in_metadata),
        .i_external_output_fire(o_data_out_valid & i_data_out_ready),
        .i_external_output_metadata(o_data_out_metadata),
        .i_external_event_fire(o_event_out_valid & i_event_out_ready),
        .i_external_event_payload(o_event_out_payload),
        .i_external_events_pending(|o_event_out_valid), .*
    );
    end
endmodule
`default_nettype wire
